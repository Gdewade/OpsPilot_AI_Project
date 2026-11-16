# HTTP 5xx Error Spike

## Symptoms
- Error rate for 500, 502, 503 or 504 responses rises sharply.
- Users report failures; health checks may start failing.

## Likely Causes
- A recent deployment introduced a bug.
- A dependency (database, cache, external API) is failing.
- The service is overloaded or out of workers.
- The reverse proxy cannot reach the upstream service.

## Diagnosis
1. Identify which endpoints and which status codes are failing.
2. Read the application logs around the first error for the stack trace.
3. Check the dependencies: database, Redis, third-party APIs.
4. Compare the start time of the errors with the last deployment.

## Remediation
- Roll back the latest deployment if it matches the start of the errors.
- Restart unhealthy instances and scale out if the load is too high.
- Enable fallbacks or timeouts so one failing dependency does not break everything.

## Escalate When
- Errors continue after a rollback, or the cause is an outage at a cloud provider.
