# Database Connection Timeout

## Symptoms
- Logs show "database connection timeout", "connection refused" or "too many connections".
- API requests hang and then fail with 500 or 504 errors.
- Services that depend on the database start failing together.

## Likely Causes
- Database server is down, restarting or overloaded.
- Connection pool is exhausted because connections are not released.
- Network rule or security group blocks the database port (5432).
- A long-running query or lock is holding connections.

## Diagnosis
1. Check that the database is reachable: `pg_isready -h <host> -p 5432`.
2. Count active connections: `SELECT count(*) FROM pg_stat_activity;`.
3. Look for slow or blocked queries in `pg_stat_activity` (state, wait_event, query_start).
4. Check firewall, security group and DNS for the database host.

## Remediation
- Restart the database service only if it is unhealthy, and only after approval.
- Terminate idle or stuck sessions: `SELECT pg_terminate_backend(pid)`.
- Increase `max_connections` or fix the application pool size and timeout.
- Make sure the application closes connections after each request.

## Escalate When
- The database does not recover after a restart.
- Data corruption or disk errors appear in the database logs.
