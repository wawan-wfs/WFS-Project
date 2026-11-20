# WFS PROJECT v3.8.0-rc1 — SSE, broker deadlines and worker crash fencing

**Release status:** PARTIAL LOCAL RELEASE CANDIDATE. Production admission DENIED.

Built from exact v3.7.0-rc1 source, preserving all 13 routes, 10 divisions, Master Agent, private projects/RBAC/MFA, cost/quota ledger, offline preview fallback and original licensed GLBs.

Improvements: cancellation-safe asynchronous preview HTTP/1.1 transport over private Unix socket; fixed whole-request deadlines; SSE reservation release before first stream pull; local two-tenant multi-tab isolation tests; operator-only per-IP Nginx ingress snippet; unique worker identity per claim and atomic stale-worker task fencing. Explicitly no changes to user schema or online infrastructure.

See `docs/ACCEPTANCE_MATRIX_V38.md`, `docs/SECURITY_REVIEW_V38.md`, `docs/PREVIEW_TIMEOUTS_V38.md`, `docs/SSE_INGRESS_V38.md`, `docs/WORKER_FENCING_V38.md`, and `docs/MIGRATION_V38.md`.
