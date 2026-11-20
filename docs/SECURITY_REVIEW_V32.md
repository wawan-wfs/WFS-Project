# WFS PROJECT v3.2 — Security delta and residual exposure

## Implemented, locally tested

- New dynamic-preview authority sidecar separates DB-backed ticket redemption and every-request session, organization, project-grant verification from the isolated gateway. Mandatory remote mode denies static routes and dynamic requests when service unreachable; fallback local mode remains **local-only** for compatibility.
- Unix socket mode/ownership plus `SO_PEERCRED` UID verification; bounded 1KiB service request and 2KiB response; HMAC-SHA256 per-request signature (timestamp/nonce/endpoint/body). Service rejects timestamp skew over 30 seconds and reused nonces. Signed headers do **not** carry raw shared secrets.
- Real local two-process integration test without gateway SQLite access. Test includes wrong host, cross-tenant cookie replay, invalid service key, missing service, session revocation, unsigned, stale and replayed request.

## Risks and boundaries

- The authority sidecar itself reads the trusted WFS SQLite database on the identity/API host. A separate *gateway* process does not need a database copy in dynamic-only mode, but these tests do not prove that two independent machines can communicate safely. Do not share DB via NFS, tunnel the authority UDS to the Internet or expose the authority over public TCP.
- The authority currently uses an operator-managed long-lived secret and in-memory bounded nonce cache per single worker; this is **not** a daemon-side mTLS certificate with per-attempt revocation. Socket ownership and signers must be managed separately and rotated under operator control.
- `WFS_PREVIEW_PUBLIC_ORIGIN` is still required by existing origin-policy code, even for dynamic-only gateway. Static/React content rendering uses the existing trusted local source path; **not independent**. No real TLS gateway or firewall evidence was produced here.
- Rootless Docker host, host-level default-deny egress, immutable source checks, signed image scan/admission, real negative breakout, TTL garbage collection and independent storage credentials remain unverified.
- No signed/authenticated official provider invoice or hard cap evidence. Billing unknown liabilities must remain blocked; no self-supplied CSV clears an unknown bill.
- No hardware GPU benchmark, Windows UI or NVDA, real TOTP recovery, red team, production restore or licensure audit for new rigged avatars. Existing eight CC0 GLBs retained.

**Operator disposition:** keep production admission DENIED. Local releases must be bound to localhost/offline and untrusted execution remain operator approved.
