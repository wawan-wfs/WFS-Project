# Security review — WFS PROJECT v2.5

## Implemented and exercised

- RFC6238 TOTP with ±1 time-step tolerance, replay protection via atomic `mfa_last_step` compare/update in SQLite, and durable five-failure lockout over a five-minute window.
- 160-bit per-account random secret stored AES-256-GCM-encrypted with a domain-separated key derived from `WFS_SESSION_SECRET`, bound via AES-GCM AAD to the account ID. Requires `cryptography>=43,<47` in runtime requirements.
- Enrollment requires active session + CSRF + account password, is bound to its specific session, and expires after 600 seconds. Confirmation atomically turns MFA on and revokes other sessions.
- Login requires a second factor when enrolled; valid TOTP or single-use 80-bit recovery code (8 generated once, hashed in DB). Successful use consumes codes atomically. Disabling MFA requires password + a valid second factor, revokes all sessions and writes an access event.
- The server does not return the MFA secret through `/api/session`, `/api/users`, or `/api/mfa/status`. No secrets in normal logs. Offline operator-only reset is possible with a DB backup and explicit typed confirmation; it is NOT an HTTP route.
- Prior RBAC, private-project scoping, SSE, preview restrictions and Docker operator boundaries remain intact according to existing regression tests.

## Risks and non-claims

- MFA is **opt-in**, not enforced across all organizations or all remote routes. Full multi-organization tenancy, TOTP device-attestation, WebAuthn, hardware keys, real external penetration test, session anomaly controls and secure preview gateway are NOT implemented.
- `.env` contains `WFS_SESSION_SECRET`: preserve this alongside a protected copy of the SQLite DB. Secret rotation invalidates existing encrypted MFA secrets and requires planned enrollment/reset. Backups of `.env` and database MUST be kept encrypted and separately access controlled.
- Browser screenshots must never include MFA setup secret, OTP, recovery codes, API key or session token. The Windows acceptance script intentionally hides the MFA panel in UI captures.
- TOTP enrollment does not prove an identity that was not already authenticated with a password. Reverse proxy TLS, rate-limiting across many external IPs, and operator privilege separation still require deployment-specific acceptance.
- The GPU timer extension can be unsupported for driver/browser/privacy reasons. Never substitute CPU wall time for GPU execution time; do not claim a WebGL2 GPU pass from a CPU renderer fixture.
