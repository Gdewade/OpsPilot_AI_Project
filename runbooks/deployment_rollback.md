# Failed Deployment and Rollback

## Symptoms
- Errors, crashes or failed health checks start right after a release.
- New version is unhealthy while the previous version was stable.

## Likely Causes
- Code defect in the new release.
- Missing environment variable, secret or database migration.
- Incompatible dependency or configuration change.

## Diagnosis
1. Note the exact time of the deployment and compare it with the first error.
2. Compare the configuration of the new and the previous release.
3. Check whether a database migration ran and whether it succeeded.
4. Read the startup logs of the new version.

## Remediation
- Roll back to the last known-good image or commit.
- Re-run or fix the database migration before the next attempt.
- Add the missing configuration, then redeploy in a staging environment first.
- Write a short incident note: what changed, what failed, what prevents it next time.

## Escalate When
- The rollback itself fails or the database schema is not compatible with the old version.
