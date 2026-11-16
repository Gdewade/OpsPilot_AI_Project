# Redis Connection Failure

## Symptoms
- Logs show "Connection refused", "Redis connection timeout" or "MISCONF".
- Cached endpoints become slow or fail; rate limiting or sessions break.

## Likely Causes
- The Redis service is stopped or restarting.
- Wrong host, port or password in the configuration.
- Redis is out of memory or cannot save snapshots to disk.
- Network rule blocks port 6379.

## Diagnosis
1. Test connectivity: `redis-cli -h <host> -p 6379 ping` should return PONG.
2. Check memory: `redis-cli info memory` and the configured `maxmemory` policy.
3. Check the Redis logs for persistence or out-of-memory errors.
4. Confirm the application uses the correct `REDIS_URL`.

## Remediation
- Start or restart Redis (requires approval in production).
- Fix the connection settings and redeploy the application.
- Set a `maxmemory` limit with an eviction policy suitable for a cache.
- Make the application continue to work, with slower responses, when the cache is unavailable.

## Escalate When
- Redis loses data that was not meant to be a cache (for example queues).
