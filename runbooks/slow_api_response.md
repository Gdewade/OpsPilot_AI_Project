# Slow API Response and High Latency

## Symptoms
- p95 or p99 latency rises; users report slowness.
- Timeouts appear in clients; the queue of waiting requests grows.

## Likely Causes
- Slow database queries or missing indexes.
- External API calls without timeouts.
- Cache is down or its hit rate dropped.
- Resource exhaustion (CPU, memory or connection pool).

## Diagnosis
1. Find the slowest endpoints in monitoring or access logs.
2. Check slow query logs and run `EXPLAIN ANALYZE` on suspicious queries.
3. Check the cache hit rate and Redis latency.
4. Check CPU, memory and connection pool usage.

## Remediation
- Add missing database indexes and optimize the slow queries.
- Add timeouts and caching for expensive external calls.
- Restore the cache service if it is down.
- Scale out or tune worker and pool sizes.

## Escalate When
- Latency stays high without any obvious resource or query problem.
