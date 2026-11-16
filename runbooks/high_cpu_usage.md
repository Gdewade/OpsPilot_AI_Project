# High CPU Usage

## Symptoms
- CPU stays above 85 percent for several minutes.
- Requests become slow, queues grow and timeouts appear.

## Likely Causes
- Traffic spike or a retry storm.
- An inefficient query, loop or regular expression.
- A runaway background job or a stuck process.
- Too few instances for the current load.

## Diagnosis
1. Find the busy process: `top` or `ps aux --sort=-%cpu | head`.
2. Check request rate and error rate for a sudden change.
3. Check recent deployments or configuration changes.
4. Profile or review the endpoint that uses the most CPU.

## Remediation
- Scale out (add instances) or raise CPU limits.
- Stop or throttle the runaway job.
- Add rate limiting or backoff for retries.
- Roll back the last deployment if the spike started right after it.

## Escalate When
- CPU stays high after scaling, which suggests a code defect.
