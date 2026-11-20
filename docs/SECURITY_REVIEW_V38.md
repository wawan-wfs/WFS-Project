# WFS PROJECT v3.8 — Security changes and residual risks

## Local mitigations
- Absolute request body, upstream and connection deadlines for preview; async cancellation of local Unix transport, peer credential verification retained.
- H11 framing enforces bounded HTTP/1.1 response parsing, headers and body size. This is local transport safety, not AI-app sandbox isolation.
- SSE leased iterator closes before first body consumption, avoiding orphaned local admission slots; tenant scoped event authorization continues per event.
- Per-claim worker lease identities and guarded planned-task update block stale finalization, including same-daemon-id reclaim cases.
- Nginx SSE ingress snippets are generated only to a new local folder; `nginx -t` offline, no reload or privileged deployment.

## Unresolved blockers
- No independent authenticated rootless Docker host, cgroup/resource limits, immutable image attestation, actual egress tests, real mTLS client cert revocation or TTL cleanup timing.
- No TLS wildcard preview deployment or full two-tenant real browser HAR; raw public preview exposure must remain disabled.
- SSE and dynamic preview counters are per-process. Per-IP ingress snippets are complementary, not cross-cluster tenant quota.
- Provider actual invoice/response IDs, retries and `billing_unknown` operator clearance are NOT authenticated.
- Windows/GPU/NVDA/MFA recovery/restore proof absent. Existing eight original CC0 GLB assets have not been replaced by rigged avatars.

**Classification: PARTIAL LOCAL RELEASE CANDIDATE — PRODUCTION DENIED.**
