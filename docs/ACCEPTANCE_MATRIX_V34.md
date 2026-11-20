# WFS PROJECT v3.4.0-rc1 — Evidence and admission gates

**Classification:** PARTIAL LOCAL RELEASE CANDIDATE. **PRODUCTION ADMISSION DENIED**.

| Workstream | Evidence genuinely observed in this environment | Verdict |
|---|---|---|
| Baseline source | Exact v3.3 ZIP SHA-256 `32c963929ca9a4acaac51f467f68f8a58efcb53a73ac479fe4a9c359b10fbdeb`; ZIP member safety + CRC and 547-manifest-file validation | PASS_LOCAL |
| Preview mTLS generator | Private host and IP validation, CA/CRL/client identity selector, stripped headers; 3 tests and 20 subtests | PASS_LOCAL / NGINX NOT RUN |
| Durable HMAC nonce | Real SQLite replay across client lifetimes, duplicate concurrency, missing DB fail-close, TTL | PASS_LOCAL / external restart proof NOT RUN |
| FinOps export semantics | Offline CSV comparison no longer reports authenticated provider reconciliation | PASS_LOCAL / PROVIDER NOT CONNECTED |
| Windows acceptance preparation | Operator-driven PowerShell preflight with explicit browser opt-in; PowerShell runtime unavailable here | SOURCE_PREPARED / NOT_RUN |
| Full Python regression | `PYTHONPATH=. python -m pytest -q`: 215 passed, 82 subtests, 34.45s, exit 0 | PASS_LOCAL (see TEST_REPORT) |
| HTTP E2E / 3 worker | Real local HTTP demo and 3 worker processes, 9 demo projects, 45 artifact validations | PASS_LOCAL / NOT PAID PROVIDER |
| Node + compile | `node --check` for app.js and office3d.js, compileall app/scripts | PASS_LOCAL |
| Preview TLS on real independent host | No independent authority host or deployed nginx/wildcard TLS | BLOCKED_EXTERNAL |
| Rootless runner admission | Docker executable not present here; no signed image/daemon/firewall/userns original evidence | BLOCKED_EXTERNAL |
| Provider authenticated export and hard caps | No official provider account/billing credentials authorized for this run | BLOCKED_EXTERNAL |
| Windows GPU/NVDA/MFA/backup | No Windows 10/11 Chrome/Edge GPU, NVDA or real authenticator access in this environment | BLOCKED_EXTERNAL |
| Licensed rigged agents | Existing eight original GLB assets remain; no licensed skeletal replacement or measured GPU gain | BLOCKED_EXTERNAL |
| Screenshot set | Unchanged UI: 26 pre-existing v3.3 fixture screenshots reused with **V33 FIXTURE REUSED** provenance, not presented as v3.4 live | PASS_FIXTURE (reused) |

**Important:** A passing unit test is not a deployed host attestation. No public release or unattended untrusted code execution is authorized.
