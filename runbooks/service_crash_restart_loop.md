# Service Crash and Restart Loop

## Symptoms
- The container or process keeps restarting; status shows "CrashLoopBackOff" or "Restarting".
- Logs end abruptly right after startup.

## Likely Causes
- Missing or invalid environment variables or secrets.
- A dependency is unavailable at startup (database, Redis).
- Out-of-memory kill (exit code 137) or an unhandled exception.
- Port already in use or a bad configuration file.

## Diagnosis
1. Read the last logs before each crash: `docker logs <container>` or `kubectl logs --previous`.
2. Check the exit code and the restart count.
3. Verify all required environment variables are set.
4. Start the service manually in a shell to see the real error.

## Remediation
- Fix the configuration or secret and redeploy.
- Make sure dependencies are healthy before starting the service (health checks and retries).
- Raise memory limits if the exit code is 137.
- Roll back to the last working version.

## Escalate When
- The service still crashes with a known-good version and configuration.
