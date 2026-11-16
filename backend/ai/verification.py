"""Evidence verification: never trust the model's claims, check them.

- Every quoted log line must exist in the real logs.
- Every cited runbook must have been among the retrieved runbooks.
"""

import re

from backend.analysis.log_analyzer import distinctive_terms, normalize_line


def verify_rca(rca: dict, log_text: str, retrieved: list[dict], min_confidence: float = 0.4) -> dict:
    log_lines = {normalize_line(ln) for ln in log_text.splitlines() if ln.strip()}
    haystack = "\n".join(log_lines)

    supporting = [ln for ln in rca.get("supporting_log_lines", []) if ln.strip()]
    verified = [ln for ln in supporting if normalize_line(ln) in haystack]
    fabricated = [ln for ln in supporting if ln not in verified]

    retrieved_sources = {r["source"] for r in retrieved}
    cited = rca.get("cited_runbooks", [])
    valid_cites = [c for c in cited if c in retrieved_sources]
    invalid_cites = [c for c in cited if c not in retrieved_sources]

    # Grounding: the verified log evidence must share distinctive words with
    # the cited runbooks. Without this, unrelated logs could still "pass"
    # because the quoted line exists and the runbook was retrieved.
    runbook_words = set()
    for r in retrieved:
        if r["source"] in valid_cites:
            runbook_words.update(re.findall(r"[a-z][a-z0-9_]{2,}", r["content"].lower()))
    evidence_words = set()
    for ln in verified:
        evidence_words |= distinctive_terms(ln)
    grounded_terms = sorted(evidence_words & runbook_words)

    confidence = float(rca.get("confidence", 0.0))
    log_ratio = len(verified) / len(supporting) if supporting else 0.0
    cite_ratio = len(valid_cites) / len(cited) if cited else 0.0
    grounded = 1.0 if grounded_terms else 0.0
    score = round(0.4 * log_ratio + 0.25 * cite_ratio + 0.2 * grounded + 0.15 * confidence, 3)

    issues = []
    if not supporting:
        issues.append("No supporting log lines were given.")
    if fabricated:
        issues.append(f"{len(fabricated)} quoted log line(s) do not exist in the logs.")
    if not cited:
        issues.append("No runbook was cited.")
    if invalid_cites:
        issues.append(f"Cited runbook(s) were not retrieved: {', '.join(invalid_cites)}.")
    if confidence < min_confidence:
        issues.append(f"Confidence {confidence:.2f} is below {min_confidence:.2f}.")
    if verified and valid_cites and not grounded_terms:
        issues.append("The log evidence shares no distinctive terms with the cited runbooks.")

    sufficient = bool(
        verified
        and valid_cites
        and grounded_terms
        and not fabricated
        and score >= 0.6
        and confidence >= min_confidence
    )
    return {
        "sufficient": sufficient,
        "score": score,
        "grounded_terms": grounded_terms[:10],
        "verified_log_lines": verified,
        "fabricated_log_lines": fabricated,
        "valid_runbooks": valid_cites,
        "invalid_runbooks": invalid_cites,
        "issues": issues,
    }
