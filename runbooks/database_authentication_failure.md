# Database Authentication Failure

## Symptoms
- Logs show "password authentication failed" or "authentication failed for user".
- The application cannot start or loses database access after a deployment.

## Likely Causes
- Password or username in the environment variable or secret is wrong.
- Credentials were rotated but the application still uses the old ones.
- The user has no permission on the target database.
- `pg_hba.conf` does not allow the client address.

## Diagnosis
1. Confirm which `DATABASE_URL` the running service uses (without printing the password in logs).
2. Try the same credentials manually with `psql`.
3. Check that the role exists and can log in: `\du` in psql.
4. Review `pg_hba.conf` and the database server logs for rejected attempts.

## Remediation
- Update the secret or environment variable with the correct credentials and restart the service.
- Grant the required privileges: `GRANT CONNECT ON DATABASE ... TO ...`.
- Add the client network to `pg_hba.conf` and reload the configuration.

## Escalate When
- Repeated failed logins from unknown addresses suggest a security incident.
