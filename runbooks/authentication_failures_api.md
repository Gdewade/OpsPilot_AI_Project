# API Authentication and Authorization Failures

## Symptoms
- Many 401 or 403 responses; users cannot log in or tokens are rejected.
- Logs show "invalid token", "token expired" or "signature verification failed".

## Likely Causes
- Expired or rotated signing keys or API keys.
- Clock difference between services breaks token expiry checks.
- Misconfigured identity provider or callback URL.
- Brute-force or credential stuffing attack.

## Diagnosis
1. Check which clients and endpoints receive the 401 or 403 responses.
2. Verify the token expiry and the signing key used by the service.
3. Compare server clocks (NTP) across services.
4. Look for many failed logins from the same IP addresses.

## Remediation
- Update the rotated key or secret and restart the affected service.
- Synchronize clocks with NTP.
- Block abusive IP addresses and enable rate limiting on login endpoints.
- Force password resets only for accounts that were actually affected.

## Escalate When
- The pattern looks like an active attack or leaked credentials; involve the security team.
