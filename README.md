# OpsPilot AI

AI-assisted incident response. Paste the logs of a production incident and OpsPilot finds the
most likely root cause, **checks its own answer against the real logs and runbooks**, proposes a
fix, and routes that fix to a human for approval. Every step is written to an audit trail.

```
Streamlit UI ──► FastAPI ──► Investigation workflow (LangGraph)
                    │            analyze logs → retrieve runbooks → root cause → VERIFY
                    │                              ▲                               │
                    │                              └── rewrite query (retry) ◄─────┤ weak
                    │                                                              ▼
                    │                                              escalate to a human (needs_human)
                    ├──► PostgreSQL  incidents · investigations · approvals · audit log
                    └──► Redis       optional cache + rate limiting (app works without it)
```

## What makes it more than a prompt wrapper

- **Verification, not trust.** The model must quote log lines and cite runbooks. The server checks
  that every quoted line really exists in the logs, that every cited runbook was actually retrieved,
  and that the evidence shares distinctive terms with the runbook. An invented log line or an
  unrelated runbook fails the check.
- **Retry, then escalate.** If evidence is weak, the query is rewritten with a different strategy
  (up to `MAX_RCA_ATTEMPTS`). If it is still weak the incident becomes `needs_human`. It never
  presents a guess as a conclusion.
- **Human in the loop.** A verified fix opens an approval request. Nothing is executed
  automatically, and the requester cannot approve their own request. A request can be decided once.
  Approving the fix marks the incident `resolved` (a person accepted it; OpsPilot does not run
  anything), rejecting it sends the incident to `needs_human`. Both changes are audited.
- **Hybrid retrieval.** Runbooks are chunked by markdown heading. BM25 and vector similarity are
  fused with Reciprocal Rank Fusion. Embeddings are cached on disk.
- **Works offline.** Without an OpenAI key it uses hashing embeddings and a rule-based analyzer.
  Results are clearly labelled `offline`, and the UI says so.
- **Untrusted input.** Logs are fenced and the model is told to treat them as data. Likely
  prompt-injection text in logs is flagged in the investigation trace.

## Quick start

```bash
cp .env.example .env        # optional: add OPENAI_API_KEY for LLM mode
docker compose up --build
```

- Dashboard: http://localhost:8501
- API docs: http://localhost:8000/docs

Try it: **Incidents → Report a new incident** (paste logs like
`ERROR Database connection timeout after 30s`), then **Investigate → Run investigation**, then
approve the proposed fix on **Approvals** (use a different name than the requester).

Demo data (9 incidents, some resolved, some waiting for a human, some with pending approvals):

```bash
python scripts/seed_demo.py     # the app must be running; safe to run again
```

Without Docker:

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
STORAGE=memory uvicorn backend.main:app --reload     # no database needed (data lost on restart)
streamlit run frontend/app.py                        # in a second terminal
```

## Tests and evaluation

```bash
pytest -q                 # unit + API tests, no external services needed
python -m eval.run_eval   # accuracy on 17 labelled incidents
```

Offline-mode evaluation on the bundled set (15 known incidents, 2 unknown):

| Metric | Result |
|---|---|
| Retrieval top-1 | 13/15 (87%) |
| Retrieval top-3 | 15/15 (100%) |
| End-to-end root cause correct | 14/15 (93%) |
| Unknown incidents escalated to a human | 2/2 |

**Read these numbers carefully.** The cases were written by the same author as the runbooks, so
wording overlaps and the results are optimistic. They show the pipeline works and catches
regressions; they are not a measure of accuracy on real production logs. One case (a Java
`OutOfMemoryError`) fails in offline mode and is kept on purpose.

## API

| Method | Path | Purpose |
|---|---|---|
| POST/GET | `/incidents` | create (severity derived from logs) / list with filters and pagination |
| GET | `/incidents/{id}` | one incident (cached in Redis if available) |
| PATCH | `/incidents/{id}/status` | change status (audited) |
| POST | `/incidents/{id}/investigate` | run the investigation (rate limited) |
| GET | `/incidents/{id}/investigation` | latest saved result |
| GET | `/incidents/{id}/audit` | audit trail |
| POST/GET | `/approvals` | create / list approval requests |
| POST | `/approvals/{id}/decision` | approve or reject (once, by someone else) |
| POST/GET | `/runbooks/search`, `/runbooks` | hybrid search / list |
| GET | `/health` | database, Redis, AI mode, embedder |

## Configuration

See `.env.example`. Key settings: `OPENAI_API_KEY` (enables LLM mode), `API_KEY` (require
`X-API-Key` on every call), `STORAGE` (`postgres` or `memory`), `MAX_RCA_ATTEMPTS`,
`RATE_LIMIT_PER_MINUTE`.

## Layout

```
backend/
  analysis/   log parsing, severity, signals, injection check
  ai/         embeddings, hybrid retrieval, LLM + offline RCA, verification, LangGraph workflow
  db/         PostgreSQL (psycopg pool) and in-memory repositories, schema.sql
  infra/      optional Redis cache + rate limiter
  services/   investigation orchestration (persist, audit, approval)
  api/        FastAPI routes
frontend/     Streamlit dashboard
runbooks/     sample runbooks (markdown, one ## section per topic)
tests/  eval/ pytest suite and labelled evaluation set
```

## Known limitations

- **Identity is not authentication.** One shared API key protects the API. Names on approvals and
  the audit trail are typed in by the user, so they can be spoofed. Real SSO/JWT is future work.
- The investigation runs inside the request (usually seconds). A job queue with polling would be
  better for long analyses.
- Offline mode matches shared words, not meaning. LLM mode with OpenAI embeddings is far stronger.
- Runbooks are a small sample set. Index is rebuilt when runbook files change; there is no
  upload UI yet.
- Not yet deployed to a cloud environment, and no LLM tracing/observability.
