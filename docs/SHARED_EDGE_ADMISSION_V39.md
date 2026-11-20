# v3.9 Design — Distributed SSE and preview admission (NOT DEPLOYED)

The process-local SSE limits (2/session, 64/process), preview limits (4/project, 32/process), and the v3.8 per-IP Nginx snippet are not tenant-safe distributed quotas. A cluster deployment needs a distinct shared admission service at the authenticated edge, not a client-provided `X-User-ID` header and not an IP-based tenant identifier.

**Proposed security contract for a future implementation:**

- The edge asks a trusted internal identity verifier for a short-lived signed scope assertion: session hash, user ID, organization ID, effective MFA status, project grant if applicable, issue/expiry times, request nonce, issuer and audience. Never expose the raw dashboard cookie/token to workloads. The verifier checks actual active session and project ACL before issuing the assertion.
- A shared admission store with atomic compare-and-expire counters enforces per-session and per-organization SSE slots, maximum open requests, and per-project preview budgets. Reserve before the upstream stream starts, release on cancellation/close, and use bounded TTL + heartbeat for crash recovery; consume a unique reservation ID at most once.
- Recheck revocation **on every SSE event** and on **every preview HTTP request**, regardless of a still-valid admission lease. Rate limiting is not authorization. Missing service, invalid signature, stale nonce or store outage must deny new access without falling back to `X-Forwarded-*` or unverified client headers.
- Measure fairness for many users behind NAT, replayed assertions, server restarts, partial disconnections, delayed consumers, queue/reconnect pagination, and concurrent two-organization tests. Never infer production safety from a single-process unit test.
- Keep the public gateway isolated from project SQLite, Docker socket, and model credentials; route only through approved TLS origins and private workload sockets.

**Current disposition:** design-only / `BLOCKED_EXTERNAL` for shared host, TLS and authentic identity edge. Do NOT market this as implemented global quotas. Local v3.9 addresses a different concrete race: artifact publication fencing.
