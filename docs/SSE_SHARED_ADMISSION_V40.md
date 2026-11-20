# v4.0 — Optional cross-process SSE admission control (PASS_LOCAL only)

This is an optional **separate local Linux Unix-socket service**, not a distributed multi-host edge or TLS deployment. It is disabled by default. Without activation, v3.8's existing 2/session, 64/process admission remains. Once activated, failure to contact the service produces HTTP 503, **never local fallback**. The SSE API continues validating the real session, organization, MFA, grants and monotonic cursor on every event.

## Architecture and trust

- `app.sse_admission.AdmissionServer` owns a **separate SQLite ledger** with transactionally reserved leases, no project source and no production users/sessions table.
- API authenticates `auth.current_session`, rechecks `store.session_valid`, and reads the organization from **server-side** `session_account`. Never use `X-Org-ID`, IP, Host, user-controlled claims, or any preview workload header as authority.
- HMAC-SHA256, a 32–512 character service secret, timestamp window (+/-30s), and transactional one-use nonce protect each IPC control request. Only the authenticated API tier may know this secret. It transmits SHA-256 session digest, not raw bearer token.
- One atomic `BEGIN IMMEDIATE` transaction enforces max 2 concurrent streams per session, 24 per organization and 64 total by default (server CLI may lower these). TTL 65s bounds orphan leases after disconnect/crash; the existing SSE stream normally reconnects at 28s. RELEASE is idempotent. Denied requests receive 429, unavailable authority 503; both fail closed.
- The Unix socket and parent must be private (0600 and 0700 respectively) and owned by the API/authority service UID. Ledger and parent must also be private. Same-UID separation and shared secret do **not** provide independent host identity or cross-host global quotas.

## Operator-only local Linux example (no service started during installation)

1. Use a dedicated non-root service user and a **new** 0700 directory such as `/run/user/<uid>/wfs-sse-admission`. Keep SQLite persistent in a separate private 0700 directory, e.g. `/var/lib/wfs-sse-admission`. Do not put the ledger on NFS/SMB.
2. Generate an independent random 32+ character HMAC credential out of band and supply it to both the admission daemon and trusted API processes via secure secret injection. Never commit or echo it, and do not give it to the public preview gateway.
3. Start the supervised local service with `WFS_SSE_EDGE_SECRET=<secret> python -m app.sse_admission --help` to inspect args; then (only on an approved host) run `python -m app.sse_admission --socket <private_dir>/admission.sock --db <private_dir>/ledger.sqlite3`. For deployment, use separate private persistent ledger directory.
4. Set the API workers' `WFS_SSE_EDGE_SOCKET=<private_dir>/admission.sock` and `WFS_SSE_EDGE_SECRET` to the same credential; restart workers. Verify 2-session quota, organization fairness behind NAT, stale nonce rejection, outage 503 and grant revocation.
5. Disable by removing `WFS_SSE_EDGE_SOCKET` and restarting API workers. This restores **local-only** limits (not a security-certified remote fallback). Do not enable public/shared deployment without separate authority review and actual TLS/host proof.

## Evidence, limitations and rollback

`tests/test_v40_sse_admission.py` runs a real child-process local UDS server, two tenant sessions, replay, restart, expiry and revocation; it is **PASS_LOCAL** only. No real distributed HTTPS ingress, HA failover, mTLS host separation, cert revocation, Windows compatibility, or large-scale performance benchmark was performed. Crashed connections can temporarily occupy quota until TTL. Per-session/org admission is not a replacement for reauthorization on each event. Rollback both API and service config in a maintenance window; no WFS application DB migration is required.
