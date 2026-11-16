# High Memory Usage and Out-of-Memory Crashes

## Symptoms
- Memory usage stays above 90 percent.
- The service restarts or crashes; logs show "OutOfMemory", "OOMKilled" or "Killed".
- Response times grow before the crash.

## Likely Causes
- Memory leak in the application (objects or caches that never shrink).
- Container or process memory limit is too low for the workload.
- A large request or batch job loads too much data into memory.
- Unbounded in-memory cache.

## Diagnosis
1. Check current usage: `free -m`, `docker stats` or `kubectl top pod`.
2. Look for OOM kills: `dmesg | grep -i oom` or the container exit code 137.
3. Compare memory growth over time in monitoring to find a leak pattern.
4. Identify which endpoint or job started the growth.

## Remediation
- Restart the affected service to restore availability (requires approval in production).
- Raise the memory limit temporarily while investigating.
- Add limits and eviction to caches; process large data in smaller batches.
- Fix the leak and add a memory alert at 80 percent.

## Escalate When
- Memory returns to high levels within minutes of a restart.
