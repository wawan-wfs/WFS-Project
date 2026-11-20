# WFS PROJECT v4.4.0-rc1

Local release candidate. Strict PostgreSQL lab retries now require replay acknowledgement even for an existing live lease. The disposable lab tests standby lag, promotion and read-only rejoin. Stopped-clone artifact checks can verify all delivered projects in a batch. Production admission remains DENIED. No application database migration or PostgreSQL API integration.

---

# WFS PROJECT v4.3.0-rc1

This local release adds bounded PostgreSQL receipt cleanup, a verified single-host primary/standby experiment, preservation of artifact generations when compensation fails, and a read-only Windows test-clone verifier. The application remains independent from the PostgreSQL quota lab. No Windows, external HA, UDS runtime, or production acceptance is inferred. See [acceptance](docs/ACCEPTANCE_MATRIX_V43.md) and [migration](docs/MIGRATION_V43.md).

---

# WFS PROJECT v4.2.0-rc1

Local release candidate. Adds a separately exercised loopback PostgreSQL quota experiment, a two-API Unix authority harness, and safer artifact compensation with an offline exact-match verifier. Preserves the dashboard, MFA, tenant scope, budgets and leased worker behavior. The PostgreSQL experiment is **not wired to the application**. No production or provider configuration was changed.

See [acceptance](docs/ACCEPTANCE_MATRIX_V42.md), [migration](docs/MIGRATION_V42.md), and [next prompt](docs/NEXT_PROMPT.md). Production admission remains **DENIED**.

---

# WFS PROJECT v4.1.0-rc1

Local release candidate based on the SHA-256 verified v4.0 package. Adds optional scoped SSE admission assertions, cancellation-aware quota release, strict per-claim worker mutation, truthful orphan-agent recovery, atomic approval checkpoints, and artifact sync plus prior-generation retention. No external provider, independent host, or production deployment was used. Production admission remains **DENIED**.

See [acceptance](docs/ACCEPTANCE_MATRIX_V41.md), [migration](docs/MIGRATION_V41.md) and [continuation](docs/NEXT_PROMPT.md).

The authenticated browser smoke also found and fixed a pre-existing MFA cleanup exception that could keep the login form hidden. The browser test now reaches the demo preview and Office through the real API. Organization-mandatory MFA no longer shows a disabled-by-policy action as available.

---

# WFS PROJECT v4.0.0-rc1

See `RELEASE_NOTES_V40.md`. Production admission DENIED.

---

# WFS PROJECT v3.9.0-rc1

Lease-fenced artifact publication and cancellation-safe specialist completion. Full notes: `RELEASE_NOTES_V39.md`. Production admission DENIED.

---

# WFS PROJECT v3.8.0-rc1 — local-only acceptance

See [v3.8 release notes](RELEASE_NOTES_V38.md). Production admission DENIED.

---

# WFS PROJECT v3.7.0-rc1 — SSE & preview backpressure

Source baseline: exact v3.6.0-rc1 ZIP (`2c81cd157ea77e88f7b1a81eed6099e7748db0ae0baa22f8f38e5041560e73e9`).

Local reversible enhancements:
- Bounded per-worker SSE admission: max 2 per session, 64 per process, 250 events/connection; 429/Retry-After, per-event revocation unchanged, cursor reconnect maintained.
- Bounded dynamic preview: max 4 concurrent requests per authorized project, 32 per gateway worker; capacity failures 503/Retry-After *after* auth, slot cleanup on failure, encoded CR/LF/NUL rejection.
- New tests for capacity admission, concurrency, rollback on failure, SSE replay and broker sanitation.
- No UI/GLB redesign, schema changes, paid API calls or operator-host action.

Local tests and source manifest are reported in `docs/ACCEPTANCE_MATRIX_V37.md` and `TEST_REPORT.md`. Production admission remains **DENIED**. The prior v3.3 screenshot fixture gallery may be reused only with explicit provenance labels.

---

# WFS PROJECT v3.6.0-rc1 — Event Revocation + Read-only Provider Cost Intake

Local continuation from checksum-verified v3.5 source. Adds per-event SSE reauthorization and an operator-only official OpenAI cost aggregate GET adapter, with negative fixture tests and durable handoff. All 13 menus, 10 divisions, original eight GLBs, queue, MFA, quota, preview and existing operator tooling remain unchanged. No schema migration.

**Production classification:** PARTIAL LOCAL RELEASE CANDIDATE; PRODUCTION ADMISSION DENIED. Official provider access, rootless host, cross-host Nginx/TLS, Windows GPU/NVDA/MFA and restore remain externally blocked. See `docs/ACCEPTANCE_MATRIX_V36.md`, `docs/SECURITY_REVIEW_V36.md`, `docs/PROVIDER_OFFICIAL_AGGREGATES_V36.md` and `docs/MIGRATION_V36.md`.

---

# WFS PROJECT v3.5.0-rc1 — Local Runner Lifecycle + Nginx Syntax Proof

Continued directly from the verified v3.4.0-rc1 partial source, preserving 13 menus, 10 divisions, Master Orchestrator, queue, MFA, org scope, FinOps, approved-preview flows and eight original CC0 GLB assets.

New: operator-only two-stage runner TTL garbage collector with default read-only audit; maintenance lock / pause marker shared with the per-attempt stage importer; rootless daemon/mount negative checks; SQLite nonce age index and multiprocess replay profiling; real local nginx `-t` syntax test revealing/fixing `map_hash_bucket_size` failure; additive DB migration and runbooks. Historical release fixture tests (`test_z_release.py`) now initialize their own isolated database instead of relying on prior test execution order. New unit/negative tests; no public deployment, paid provider call, Docker execution or real client cert revocation.

Local regression groups: 234 tests and 86 subtests passed in separate complete commands. HTTP demo and parallel worker E2E passed. Some combined pytest runs timed out and are marked incomplete, not passed. No new UI screenshot capture; v3.3 fixture gallery reused with explicit provenance.

**PRODUCTION ADMISSION: DENIED.** Independent rootless host, TLS, provider invoices/hard limits, Windows GPU/NVDA/MFA/restore and licensed skeletal GLB proof missing. See `docs/ACCEPTANCE_MATRIX_V35.md` and `docs/AUTONOMOUS_STATE.json`.
