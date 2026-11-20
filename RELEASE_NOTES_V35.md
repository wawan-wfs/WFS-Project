# WFS PROJECT v3.5.0-rc1 — Local Runner Lifecycle + Nginx Syntax Proof

Continued directly from the verified v3.4.0-rc1 partial source, preserving 13 menus, 10 divisions, Master Orchestrator, queue, MFA, org scope, FinOps, approved-preview flows and eight original CC0 GLB assets.

New: operator-only two-stage runner TTL garbage collector with default read-only audit; maintenance lock / pause marker shared with the per-attempt stage importer; rootless daemon/mount negative checks; SQLite nonce age index and multiprocess replay profiling; real local nginx `-t` syntax test revealing/fixing `map_hash_bucket_size` failure; additive DB migration and runbooks. Historical release fixture tests (`test_z_release.py`) now initialize their own isolated database instead of relying on prior test execution order. New unit/negative tests; no public deployment, paid provider call, Docker execution or real client cert revocation.

Local regression groups: 234 tests and 86 subtests passed in separate complete commands. HTTP demo and parallel worker E2E passed. Some combined pytest runs timed out and are marked incomplete, not passed. No new UI screenshot capture; v3.3 fixture gallery reused with explicit provenance.

**PRODUCTION ADMISSION: DENIED.** Independent rootless host, TLS, provider invoices/hard limits, Windows GPU/NVDA/MFA/restore and licensed skeletal GLB proof missing. See `docs/ACCEPTANCE_MATRIX_V35.md` and `docs/AUTONOMOUS_STATE.json`.
