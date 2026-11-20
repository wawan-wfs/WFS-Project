# v3.6 — Security delta

**SSE:** Each queued event is reauthorized against current session, account, MFA enrollment and project grants immediately before emission. A permission change after a frame has already left the server cannot be retroactively recalled. Reauth adds DB lookups per streamed event (maximum 100 per query); benchmark real-scale concurrency before public deployment.

**FinOps:** New operator-only official aggregate costs fetch. Fixed HTTPS endpoint, no redirects, short timeouts, bounded pagination, finite nonnegative USD, private exclusive output, no tokens in responses and no DB mutation. Credential is passed through a process environment and never saved by code. Shell history, administrator account permissions and downstream handling of exported billing metadata remain operator risks. The result is **not** transaction-level proof or a successful real billing read in this release; `billing_unknown` cannot be released from it.

**Unchanged critical blockers:** rootless daemon independent from web nodes, egress-denied container admission, signed pinned images, per-attempt daemon mTLS revocation, verified immutable ext4 cleanup, real Nginx/TLS origin deployment, provider request-level invoice and hard caps, real Windows GPU/NVDA/MFA recovery and matched backup restore. Production admission stays DENIED.
