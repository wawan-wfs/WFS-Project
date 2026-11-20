# WFS PROJECT v4.4.0-rc1 — Test report

Baseline v4.3 source SHA-256 `9fb81921949309051dfa1eb16087e2c70c68c26532873834d66bdb6891b1b3bd`, 847 files verified.

| Check | Observed result |
|---|---|
| Primary pytest group | 267 passed, 110 subtests, 28 skipped |
| Visual Office and base group | 19 passed and 8 subtests. 11 base tests already counted above |
| Independent release tests | 8 passed |
| **Deduplicated total** | **283 passed, 118 subtests, 28 skipped** |
| Focused stopped-clone and recovery tests | 13 passed, already counted |
| Focused SSE checks | 8 passed, 9 socket cases skipped, already counted |
| PostgreSQL replica | 17/17 acknowledged lease IDs retained, paused replay withheld acknowledgement, strict retry waited, read-only rebuilt standby |
| PostgreSQL load | 32 clients, 1,200 attempts, 24 allowed, 1,176 quota denials, 0 unavailable, p95 170.92 ms in this run |
| Independent Uvicorn and browser | Passed local demo, no real provider or Docker |
| Parallel workers | 3 workers, 9 demo projects, 45 verified artifacts |
| UI | 13 menus at 1440/820/390, 26 software-rendered fixtures |

The 28 skips comprise 20 Unix-socket tests, 6 root-owned staging tests and 2 nginx tests. The separate UDS harness returned exit 77 with EPERM. The initial lag experiment was stopped when a synchronous commit continued waiting despite statement timeout. The final harness explicitly canceled that disposable backend's wait and verified the warning/fail-closed path before retrying. The Windows wrapper, independent-node failover, real provider, physical storage, hardware, NVDA and TLS gates were not executed. See docs/V44_EVIDENCE and docs/ACCEPTANCE_MATRIX_V44.md. Production admission **DENIED**.

---

# WFS PROJECT v4.3.0-rc1 — Test report

Exact published v4.2 baseline SHA-256 `0bd874497d45dab1f70a515ec24c5b643b56038465fc44cc5f984be337436602` and 793 internal files verified. Its VERSION and application metadata were v4.2.0-rc1, but its manifest version field still said v4.1.0-rc1. v4.3 regenerates a consistent manifest.

| Run | Results |
|---|---|
| Main pytest group | 264 passed, 110 subtests, 28 skipped |
| Visual Office group | 19 passed and 8 subtests. 11 base tests were already counted above |
| Release gates | 8 passed |
| **Distinct counted passes** | **280 passed, 118 subtests, 28 skipped** |
| Focused SSE and artifact group | 24 passed, 5 skipped, already counted |
| PostgreSQL scale | 1,200 attempts, 32 clients, 24 admitted, 1,176 quota denials, 0 unavailable. Local p95 361.5 ms |
| PostgreSQL replica | 16 of 16 acknowledged lease IDs retained. Refused promotion while the prior primary ran. Strict mode denied when standby was absent |
| HTTP/browser and workers | Independent Uvicorn and browser demo passed. 3 workers, 9 demo projects, 45 verified artifacts |
| UI and syntax | 13 menus at 1440/820/390. 26 valid fixture PNGs. Python/JS and CI YAML passed syntax checks |

The 28 skips are 20 Unix socket cases, 6 root-owned staging cases, and 2 nginx cases. The two-API Unix harness separately returned exit 77 because AF_UNIX returned EPERM. Neither the real Unix authority nor broker transport was verified. The Windows verifier and updated CI are packaged but not run on those platforms. The PostgreSQL lab used two processes on one machine and did not test independent hosts or automatic leader fencing. The initial 32-client load hit a lock timeout when the reservation path shared the cleanup backlog. The final workload separated bounded cleanup and reported unavailable independently from quota denial. The library runtime emitted an AnyIO compatibility deprecation warning during tests.

See `docs/V43_EVIDENCE/` for raw results and `docs/ACCEPTANCE_MATRIX_V43.md` for blocked gates. Production admission remains **DENIED**.

---

# WFS PROJECT v4.2.0-rc1 — test report

The published v4.1 ZIP digest `e8f7926e35e74c340e31142e7feb454ca75cd55c6edfcf9dbf2abc3f3e0648be` and all 734 internal manifest entries matched before editing.

| Group | Observed result |
|---|---|
| Primary regression | 261 passed, 110 subtests passed, 28 skipped |
| Visual office with initialized base | 19 passed, 8 subtests passed. 11 base tests already included in primary regression |
| Standalone release gates | 8 passed |
| **Total unique counted passes** | **277 passed, 118 subtests, 28 skipped** |
| Recovery focus | 18 passed, already counted above |
| PostgreSQL 16.2 | Actual single loopback primary, 8 concurrent clients and 120 reservations, 24 admitted, 96 denied. 295.3 requests/s, p95 61.48 ms. Local synchronous WAL, clean and immediate-stop recovery, rollback and retry verified |
| HTTP and browser | Local Uvicorn, login, demo queue, preview, trace, collaboration and Office verified |
| Parallel worker | 3 separate worker processes, 9 demo projects and 45 validated artifacts |
| Responsive | All 13 menus at 1440/820/390px. 26 labelled fixture images |
| Syntax and PNG integrity | Python compilation, app JavaScript syntax and dimensions of all 26 PNGs passed |

The 28 pytest skips were 20 AF_UNIX cases, 6 root-owned staging fixture cases and 2 nginx cases. The two-API Unix harness separately returned 77 and recorded EPERM on socket creation. It was not counted as a pass. The optional GitHub workflow was syntax-checked locally but not published or run on GitHub. The Windows preflight has not been executed on Windows. No external rootless Docker, TLS/CRL, provider billing, Windows GPU/NVDA/MFA/restore, HA or physical power-loss evidence was collected. Production admission is **DENIED**.

Raw evidence is under `docs/V42_EVIDENCE/`.

---

# WFS PROJECT v4.1.0-rc1 — Local test report

Baseline ZIP SHA-256 `75684b6c65dcd431ebefc734674602498ec7f5bc6438624f02144cd4f3685803`, 681 manifest files verified before editing.

| Completed verification | Result |
|---|---|
| Main pytest group | 252 passed, 106 subtests passed, 28 skipped |
| Visual Office group with initialized test environment | 19 passed, 8 subtests. Of these, 11 base tests also ran in the main group |
| Independent release gates | 8 passed |
| **Total without duplicated base tests** | **268 passed, 114 subtests passed, 28 skipped** |
| Focused rerun | 28 passed including MFA, session, SSE and worker recovery tests already counted |
| HTTP E2E | PASS, local independent Uvicorn, real auth, SSE replay, static preview and export |
| Parallel E2E | PASS, 3 workers, 9 demo projects, 45 verified artifacts |
| Browser E2E | PASS, login → mission → pause/priority/resume → worker → preview → trace → note → Office |
| Responsive fixture | PASS, 13 menus at 1440, 820 and 390px. 26 screenshots at desktop/mobile |
| Python / JS syntax | PASS |

The 28 skips comprise 20 Unix-socket tests (including inherited test cases), 6 root-owned staging fixture tests, and 2 Nginx syntax tests. No host verification is inferred from skipped tests. Starlette emitted an AnyIO alias deprecation warning. Initial retries revealed fixture assumptions from v4.0 and a real browser MFA cleanup bug. The focused and final group runs used corrected fixtures or application code. System Chromium could not launch under the AF_UNIX restriction, while Chromium Headless Shell 153 completed the local browser and fixture checks. The local software-rendered gallery and separate authenticated demo E2E do not imply Windows GPU proof.

In [the acceptance matrix](ACCEPTANCE_MATRIX_V41.md), cross-host ingress/datastore HA, independent rootless Docker, external TLS/CRL, authenticated provider billing/hard caps, Windows GPU/NVDA/MFA/restore and physical power-loss remain open. **Production admission DENIED.**

---

# WFS PROJECT v4.0.0-rc1 — Test report (local evidence only)

**Baseline source:** exact v3.9 distribution SHA-256 `0940494f1c26a71e25634c57329dba10d0d046e6401d91caf61ec72e7ef23d51`; existing manifest of **657 files** passed before edits.

| Completed isolated test process | Test results | Subtests | Evidence |
|---|---:|---:|---|
| Group 1 (foundation and v2.8) | 150 pass | 40 | `docs/V40_EVIDENCE/group1.log` |
| Group 2A (v2.9–v3.1 broker) | 26 pass | 6 | `docs/V40_EVIDENCE/group2a.log` |
| Group 2B (v3.1–v3.4 authority) | 23 pass | 36 | `docs/V40_EVIDENCE/group2b.log` |
| Group 2C (v3.5–v3.6 FinOps) | 25 pass | 11 | `docs/V40_EVIDENCE/group2c.log` |
| Group 3 (v3.6–v4.0 security) | 42 pass | 8 | `docs/V40_EVIDENCE/group3.log` |
| Visual Office (8 visual tests only; `test_system` 11 tests also run but already counted in Group 1) | 8 pass | 8 | `docs/V40_EVIDENCE/visual_with_system.log` |
| Standalone release gate | 8 pass | 0 | `docs/V40_EVIDENCE/release_gate.log` |
| **Unique tests counted** | **282 pass** | **109** | All listed processes completed with exit status 0 |

**Separate end-to-end verification:** `python scripts/http-e2e.py` exited 0 (actual independent local Uvicorn process, authenticated HTTP, preview, SSE). `python scripts/parallel-e2e.py` exited 0: three worker processes, nine demo projects and 45 validated artifacts. Python `compileall` and Node `--check` for the existing UI/Office JS exited 0. The shared SSE admission tests start a real local child process over Unix socket; **no external/production host was used**.

**Honest unsuccessful attempts:** initial monolithic group-2 command was interrupted without an exit summary (`docs/V40_EVIDENCE/group2.log`); all its test modules were rerun successfully in 2A/2B/2C. An initial group-3 command containing the Visual Office test module produced 8 fixture bootstrapping errors because `test_system` was not loaded first. It was rerun as Group 3 plus Visual Office with `test_system`, with exit 0; no initial failure was silently counted as a pass. No monolithic pytest PASS is claimed.

**Security coverage:** reject unfenced artifact manifest edits, stale agent event/success/phase, task plan and handoff ownership after lease recovery, canceled agent state; read-only detect crash-backup/staging, unmanifested files, corrupt digests and symlinks. Shared SSE quota tests exercise multi-process UDS authority, two-tenant NAT fairness, session revocation, replay, restart, stale TTL, 429 over-quota and 503 authority outage. These are local tests, not actual independent host/TLS deployment proof.

External rootless Docker daemon, real TLS/CRL, authenticated per-response provider billing, Windows Docker Desktop GPU, NVDA, MFA recovery, restore and licensed skeletal rigging were **NOT RUN**. Production admission **DENIED**.

---

# WFS PROJECT v3.9.0-rc1 — Test report

Regresi akhir: **124+71+65+2+8 = 270 tests**, **101 subtests** (3 completed grouped processes, 2 standalone specialist tests, and 8 release-gate tests). All recorded exit code 0. Focused 21-test rerun after last cancellation-event fix passed. HTTP E2E and 3-worker / 9 demo projects (45 artifacts) passed. Monolithic suite not claimed; see `docs/V39_EVIDENCE/` and `docs/ACCEPTANCE_MATRIX_V39.md`. Real rootless Docker, TLS, provider billing, Windows GPU/NVDA/MFA and restore remain BLOCKED_EXTERNAL.

---

# WFS PROJECT v3.8 — Test report (local evidence only)

**Baseline:** exact v3.7 SHA-256 `3f0ef0f6505e58fdc801c82187bb9cd5e9c0477d34fe201cf6d5559752f2abd6`; `python scripts/verify-release.py`: checked 607 files, PASS before edits.

| Test | Result | Evidence |
|---|---|---|
| Pytest group 1 | 133 passed, 20 subtests, exit 0 | `docs/V38_EVIDENCE/pytest_group1.log` |
| Pytest group 2 | 85 passed, 66 subtests, exit 0 | `docs/V38_EVIDENCE/pytest_group2.log` |
| Pytest group 3 | 36 passed, 15 subtests, exit 0 | `docs/V38_EVIDENCE/pytest_group3.log` |
| Total grouped (excluding release-gate) | **254 passed, 101 subtests** | Independently completed grouped processes |
| HTTP E2E | PASS, exit 0 | `docs/V38_EVIDENCE/http_e2e.log` |
| Worker E2E | PASS, 3 worker processes, 9 demo projects, 45 validated artifacts | `docs/V38_EVIDENCE/parallel_e2e.log` |
| Python and JavaScript syntax | PASS, exit 0 | `docs/V38_EVIDENCE/syntax.log` |
| Nginx snippet syntax | PASS actual `nginx -t` locally, no deployment | `tests/test_v38_sse_edge_config.py` |
| Release-gate tests | 8 passed, exit 0 | `docs/V38_EVIDENCE/release_gate.log` |
| Source suite incl. release gate | **262 passed, 101 subtests** across independent processes | No monolithic PASS claimed |
| Full monolithic pytest | NOT RUN for v3.8; historical v3.7 timeout not a pass | Group results are not a monolithic pass |
| Windows GPU, NVDA, provider invoice, independent Docker/TLS | BLOCKED_EXTERNAL | No approval or physical host evidence |

**Test history:** initial POST lacked Content-Length after async transport rewrite (fixed, tests passed). Two-tenant stalled-tab test detected SSE slot leakage on closing an unstarted generator (fixed, tests passed). The initial group3 run failed import-order setup; after pre-importing `test_system` into a clean test process, the group completed successfully with 36 tests. All these failures are recorded, not relabeled as first-run success.

No paid provider, Docker rootless host, public preview endpoint, GPU browser, TOTP recovery or production DB was contacted. 26 unchanged historical fixture screenshots remain labeled `REUSED_FIXTURE`.

---

# WFS PROJECT v3.7.0-rc1 — SSE and preview backpressure local test report

- **Source**: SHA-256 verified v3.6.0-rc1 ZIP, 588 original manifest entries. No new database schema.
- **Actual completed regressions**: 109 + 69 + 59 + 8 = **245 tests** and 20 + 31 + 50 = **101 subtests**, all separate processes exiting 0. Release-gate tests: **8 passed** after manifest regeneration, for **253 tests and 101 subtests** total across completed commands.
- **Monolithic pytest**: reached a displayed 100%, then timed out with no successful exit. Explicitly **NOT PASS**. An initial isolated group lacked `PYTHONPATH`, causing subprocess import failure and unrelated fixture initialization errors; environment-corrected reruns passed.
- **HTTP**: PASS, independent Uvicorn localhost/auth/queue/event/preview suite, exit 0.
- **Parallel worker**: PASS, 3 worker processes/9 demo projects/45 generated test artifacts, exit 0.
- **Static checks**: Python compileall and three Node syntax checks PASS.
- **Test-order isolation:** new v3.7 tests now initialize their deterministic `test_system` environment before importing app config. On one process, new SSE + broker tests together with 8 release-gate tests: **17 passed, 8 subtests**, exit 0. This also passed after clean ZIP extraction.
- **New negative tests**: SSE 429 limits, auth replay pagination, slot cleanup on errors; broker concurrency 503 after authorization, encoded-control-target denial, slot release and legacy preview flows.
- **No actual production proof**: Docker rootless daemon, cross-host DNS/TLS, official provider invoice, Windows GPU, NVDA, MFA recovery and matched restore **NOT RUN**.

See `docs/V37_EVIDENCE/` and `docs/ACCEPTANCE_MATRIX_V37.md`. Production admission: **DENIED**.

---

# WFS PROJECT v2.6.0-rc1 — Local Regression Report (2026-11-08)

**Release status: PARTIAL v2.6, local RC only.** No authenticated external provider or Windows GPU/Docker Desktop production test was run.

| Test | Result | Type |
|---|---|---|
| `PYTHONPATH=. python -m pytest -q` | **149 passed, 20 subtests passed** | real code / isolated SQLite & FastAPI TestClient |
| `python -m unittest discover -s tests -v` | **149 passed** | Python unittest discovery |
| v2.5 source store → v2.6 upgrade | **PASS**, initialized actual legacy v2.5 SQLite, created project and applied current `store.init_db()` twice; ID, default-org ownership and MFA policy preserved | direct legacy migration smoke |
| `python scripts/http-e2e.py` | **PASS**, local Uvicorn/API/worker auth, queue, artifacts, CSP preview, export, SSE, QA, budgets | real local HTTP, offline demo provider |
| `python scripts/parallel-e2e.py` | **PASS**, 3 workers, 9 projects, 45 verified artifacts | real local worker processes, offline demo |
| `node --check app/static/app.js` and `node --check app/static/mfa-ui.js` | **PASS** | actual JS syntax |
| `WFS_V26_CAPTURE=1 python scripts/browser-ui-fixture-smoke.py` | **PASS**, 13 desktop + 13 mobile captures with no horizontal overflow; 2FA browser fixture | synthetic browser fixture |
| Fixture spatial renderer | `cpu-3d`, 9,520 triangles, draw calls 13, GPU timer **unsupported** | CPU-only; NOT physical GPU acceptance |
| WebGL2 GPU on Windows, dedicated VRAM, driver time, physical FPS | **NOT RUN** | Windows hardware required |
| Docker Engine rootless isolation, immutable image, egress negative tests | **NOT RUN / NOT COMPLETED** | isolated host required |
| Live AI provider, authentic official usage reconciliation | **NOT RUN** | credentials/provider required |
| Authenticated Windows Docker Desktop end-to-end browser | **NOT RUN** | target machine required |
| Windows screen readers + 200% zoom | **NOT RUN** | target Windows accessibility pass required |
| TLS preview red-team and organization quotas | **NOT IMPLEMENTED / NOT CERTIFIED** | production-blocking |

Regression tests added: `tests/test_v26_organization_boundary.py` (6), `tests/test_v26_mfa_policy.py` (2), `tests/test_v26_session_controls.py` (3). The 26 screenshots in `docs/V26_FIXTURE_SCREENS` use synthetic projects and fake login responses. None is an actual AI completion or Windows GPU measurement.

## v2.7.0-rc1 partial runner security extension — 2026-11-08

- `python -m pytest -q`: **157 passed, 40 subtests passed** (includes strict remote runner policy negative tests; no Docker daemon involved in these unit tests).
- `python scripts/http-e2e.py`: PASS on local independent HTTP server.
- `python scripts/parallel-e2e.py`: PASS, 3 worker processes, 9 demo projects, 45 artifacts.
- Real remote Linux rootless Docker engine, staging immutability, user-authenticated preview TLS, Windows GPU/browser acceptance, production isolation red team, billed provider usage and MFA recovery: **NOT RUN**.
- This is not production certification. `docs/ACCEPTANCE_MATRIX_V27.md` is the release gating authority.


## v2.8.0-rc1 — Tenant quota/preview admission local verification — 2026-11-08

- `PYTHONPATH=. python -m pytest -q`: **166 passed, 40 subtests passed**, on local Python/SQLite/FastAPI TestClient. Includes quota concurrency, cross-tenant budget and preview access revocation, original token-price snapshots, strict QA negative policy tests.
- `python scripts/http-e2e.py`: **PASS**, independent local uvicorn process for auth, queue/worker, preview, artifact ZIP, collaboration, SSE, budget APIs. This is NOT a public TLS preview acceptance.
- `python scripts/parallel-e2e.py`: **PASS**, 3 worker processes completed 9 demo projects with 45 verified artifacts. These are offline demo tasks.
- v2.7 historical source DB -> v2.8 migration check: **PASS**, created and persisted project with actual v2.7 `store.init_db()`, opened DB twice under v2.8 `store.init_db()`, verified original project ID and default workspace/organization persisted.
- Synthetic browser fixture: headless Chromium at 1440/820/390 px, 13 routes with no horizontal overflow; generated 26 desktop/mobile fixture screenshots (PLUS separate MFA/other artifacts excluded from delivery gallery). Engine reported `cpu-3d`, `gpuTimerSupported:false`; GPU duration and Windows driver not measured.
- Source manifest SHA-256 verification and distribution ZIP integrity: independently verified after packaging.
- **BLOCKED:** no real remote rootless Linux Docker daemon, immutable ext4 stage, measured network isolation, real TLS preview gateway, dynamic code preview isolation, live provider invoice reconciliation, Windows Chrome/Edge GPU, screen reader NVDA, MFA recovery on Windows, or independent penetration test.

Production acceptance remains blocked. Operator-only local RC; no Internet-facing deployment.

## v2.9.0-rc1 — Per-attempt QA admission and ambiguous billing controls (2026-11-08)

- `PYTHONPATH=. python -m pytest -q`: **175 passed and 46 subtests passed**. Includes new per-attempt TAR namespace/hash/malicious path tests, provider uncertain/failure/retry accounting, response-ID uniqueness and read-only cost comparison with cross-tenant aggregation. Tests use mock provider responses, local SQLite and policy code, not a real paid provider or Docker daemon.
- `python scripts/http-e2e.py`: PASS — independent local Uvicorn server, auth, queue/worker, preview, ZIP, SSE, budget tests.
- `python scripts/parallel-e2e.py`: PASS — 3 worker processes, 9 independent demo projects, 45 verified generated artifacts.
- `WFS_V29_CAPTURE=1 python scripts/browser-ui-fixture-smoke.py`: PASS — 13 menus 1440/390px, 26 new screenshot fixtures, no page overflow. Additional 820px viewport navigation audit was covered separately by `WFS_FULL_UI_AUDIT=1`. Renderer `cpu-3d`, `gpuTimerSupported:false`; GPU timing and Windows driver NOT measured.
- Real v2.8 baseline SQLite → v2.9 source migration: PASS. Actual v2.8 source created an existing project; v2.9 code ran DB initialization twice, preserved project identity/default org and workspace, and added nullable provider response ID column. Separate matched v2.8 code+data backup restored without v2.9 schema changes. This is a local migration smoke, not live Windows backup/restore certification.
- Docker CLI/daemon `command -v docker`: **not installed**; actual rootless host/immutable-stage/mTLS/firewall/provisioning negative and cleanup tests NOT RUN. No AWS/VM or user infrastructure was accessed.
- No live provider usage invoices or provider daily hard caps, independent TLS preview, Windows 10/11 Chrome/Edge GPU/NVDA/TOTP recovery, dynamic preview broker, third-party red-team evidence. **Production acceptance BLOCKED.**

## v3.0.0-rc1 — Runner admission proofing / honest evidence (2026-11-08)

- `PYTHONPATH=. python -m pytest -q`: **187 passed, 46 subtests passed**; source tests include mocked strict QA cleanup/daemon-health failure, immutable staging rechecks and local host evidence semantics. These DO NOT prove a live remote Docker daemon, TLS or firewall.
- `python scripts/http-e2e.py`: PASS independent local Uvicorn/demo-provider flow.
- `python scripts/parallel-e2e.py`: PASS, 3 worker processes/9 demo projects/45 verified artifacts.
- `WFS_V30_CAPTURE=1 WFS_FULL_UI_AUDIT=1 python scripts/browser-ui-fixture-smoke.py`: PASS, 13 desktop/mobile route captures, 820px no-overflow audit, CPU-only `cpu-3d` renderer; no actual GPU timer, no Windows screen reader.
- `python -m unittest discover -s tests -q`: **INCOMPLETE / TIMED OUT**, no result claimed; full pytest run above completed successfully.
- Independent Linux rootless host, mTLS revocation, root-owned immutable ext4, host egress denial, real Docker cleanup, TLS preview reverse proxy and full-stack broker, authenticated provider costs, Windows GPU/NVDA/MFA backup recovery: **NOT RUN or NOT IMPLEMENTED**.
- Production admission remains **DENIED**. `docs/ACCEPTANCE_MATRIX_V30.md` is the controlling report.

## v3.1.0-rc1 — Local dynamic broker engineering (2026-11-08)

See `docs/ACCEPTANCE_MATRIX_V31.md`. The new dynamic broker and TLS negative probe have local automated tests. This is NOT a deployed TLS/Docker acceptance or real billing evidence. All previously unverified Windows hardware and host admission gates remain blocked. Exact test counts, result and distribution checksums recorded after packaging.

Final v3.1 local evidence: `PYTHONPATH=. python -m pytest -q` **194 passed, 51 subtests passed**; independent local `python scripts/http-e2e.py` **PASS**; `python scripts/parallel-e2e.py` **PASS** with 3 worker processes, 9 demo projects and 45 verified artifacts. `WFS_V31_CAPTURE=1 WFS_FULL_UI_AUDIT=1 python scripts/browser-ui-fixture-smoke.py` **PASS** (26 new desktop/mobile fixture screenshots, 820px viewport audit, CPU 3D renderer, no Windows GPU timing). Real TLS, provider, rootless host and Windows hardware acceptance **NOT RUN**.

## v3.2.0-rc1 — Independent-process dynamic authority (2026-11-08)

- `PYTHONPATH=. python -m pytest -q`: **201 passed, 51 subtests passed**. Includes independently started local Uvicorn authority Unix socket and gateway with `store.connect()` deliberately disabled, plus timestamp/nonce/HMAC verification, cross-tenant and logout revocation negative tests. These are actual local IPC/processes, **not** Docker host/TLS production proof.
- `python scripts/http-e2e.py`: **PASS** on independent localhost Uvicorn process with demo/offline provider.
- `python scripts/parallel-e2e.py`: **PASS** — 3 worker processes, 9 independent demo projects, 45 artifacts validated.
- `WFS_V32_CAPTURE=1 WFS_FULL_UI_AUDIT=1 python scripts/browser-ui-fixture-smoke.py`: **PASS** — synthetic 13 desktop and 13 mobile screenshots, 820px layout audit. Spatial renderer **cpu-3d**, GPU timer unsupported. No actual Windows Chrome/Edge driver or NVDA test.
- `node --check app/static/app.js` and `node --check app/static/office3d.js`: PASS.
- All eight original CC0 GLB filenames and provenance retained. No licensed skeletal rig, GPU PBR driver proof or realistic avatar claim.
- **NOT RUN / NO PRODUCTION ADMISSION:** independent rootless Docker runner, signed-image attestation, real daemon mTLS/negatives, host egress default deny, public wildcard DNS/TLS, two-tenant HAR on Internet-facing proxy, actual authenticated provider invoices/hard caps, physical Windows GPU/NVDA/TOTP recovery and matched backup/restore drill. No operator secrets or hardware evidence were supplied.
- Source SHA manifest, ZIP extraction validation and distribution checksums are generated and verified by the v3.2 release tool. See `docs/ACCEPTANCE_MATRIX_V32.md`, `docs/SECURITY_REVIEW_V32.md` and `docs/MIGRATION_V32.md`.

**Classification: partial release candidate; PUBLIC DEPLOYMENT AND UNATTENDED UNTRUSTED CODE EXECUTION REMAIN DENIED.**

## v3.3.0-rc1 — Opt-in remote preview authority mTLS (2026-11-08)

- Baseline verified from exact `WFS_PROJECT_v3.2_SEGREGATED_PREVIEW_AUTHORITY_PARTIAL_Windows_Docker.zip`, `python scripts/verify-release.py`: 506 files passed before editing.
- Full regression `PYTHONPATH=. python -m pytest -vv`: **207 passed, 62 subtests passed in 32.45s**. Earlier `pytest -q` runs were interrupted by outer tool time limits and **are not** claimed as separate successes; the `-vv` full run completed.
- New real **localhost** TLS integration `PYTHONPATH=. python -m pytest -q tests/test_v33_authority_mtls.py`: **6 passed, 11 subtests passed**. Actual in-process TLS server requests client certificates, validates CA and signed HMAC over HTTPS. Rejected wrong CA, hostname, unsafe private key, invalid URL, unsupported mode and nonprivate listener. These are loopback TLS tests, not physically independent host or production client revocation proof.
- `PYTHONPATH=. python scripts/http-e2e.py`: **PASS** independent local Uvicorn/demo-provider smoke.
- `PYTHONPATH=. python scripts/parallel-e2e.py`: **PASS** 3 worker processes/9 synthetic projects/45 validated artifacts.
- `WFS_V33_CAPTURE=1 WFS_FULL_UI_AUDIT=1 python scripts/browser-ui-fixture-smoke.py`: **PASS**; 26 desktop/mobile screenshots and 820px responsive audit. Renderer `cpu-3d`, 9,520 triangles, GPU timer unsupported. No real Windows GPU.
- `node --check app/static/app.js` and `node --check app/static/office3d.js`, Python compile for new modules: **PASS**.
- **NOT RUN / NO PRODUCTION ADMISSION:** physically independent Linux rootless Docker runner/host-level deny egress; real Docker inspect and daemon certificate revocation; remote authority client certificate revocation/CA lifecycle; external wildcard TLS and concurrent real-browser HAR; authentic provider billing export and hard limits; Windows 10/11 Chrome/Edge GPU 10-minute measurements, NVDA, MFA recovery or matched data restore; rigged GLBs.
- Screenshots are synthetic only, with `docs/V33_SCREENSHOT_PROVENANCE.md`. Production status remains DENIED.

## v3.4.0-rc1 — Autonomous security engineering checkpoint (2026-11-08)

- Input exact v3.3 ZIP SHA-256 `32c963929ca9a4acaac51f467f68f8a58efcb53a73ac479fe4a9c359b10fbdeb`: ZIP CRC/member validation and `python scripts/verify-release.py` **PASS 547 tracked files**.
- Focused newly changed logic: `PYTHONPATH=. python -m pytest -q tests/test_v34_nonce_migration.py tests/test_v34_durable_nonce.py tests/test_v34_mtls_proxy_config.py tests/test_v29_reconciliation.py` **11 passed, 20 subtests**. Includes tampered/malformed cert values, private-address restrictions, transaction replay contention, DB error fail-close, nonce TTL and additive migration. Real nginx and separate hardware NOT RUN.
- `PYTHONPATH=. python scripts/http-e2e.py`: **PASS** local HTTP demo.
- `PYTHONPATH=. python scripts/parallel-e2e.py`: **PASS**, 3 workers/9 demo projects/45 artifacts.
- `node --check app/static/app.js`, `node --check app/static/office3d.js`, Python compileall: **PASS**.
- Initial full pytest commands with 180s/90s shell timeouts were **INCOMPLETE**; an earlier independently recorded run finished **213 passed, 82 subtests** with process exit 0 before the latest two new tests. The final completed run after all v3.4 tests returned **215 passed, 82 subtests passed in 34.45s**, process **EXIT_CODE=0**; earlier interrupted runs are not counted as successes.
- **NOT RUN:** independent Linux rootless Docker, nginx/wildcard TLS deployment, authenticated provider billing, real Windows GPU/NVDA/MFA/restore or licensed skeletal avatar rendering. Existing v3.3 fixture screenshots remain synthetic and were not recaptured for unchanged UI.

**Classification:** PARTIAL LOCAL RELEASE CANDIDATE. PRODUCTION ADMISSION DENIED.


## v3.5.0-rc1 — Operator runner lifecycle and local Nginx parse (2026-11-08)

- Verified exact v3.4 baseline ZIP SHA-256 and 557 release manifest entries.
- Three fully completed pytest subset commands: **59 passed / 40 subtests** (v3.0–v3.5 security), **92 passed / 38 subtests** (v1.9–v2.9 history), **83 passed / 8 subtests** (core). Aggregate **234 passing tests and 86 subtests**, NOT a single unified completion. Initial full -q/-vv attempts timed out; uncompleted runs are NOT counted as passes.
- `python scripts/http-e2e.py`: PASS localhost Uvicorn/demo provider.
- `python scripts/parallel-e2e.py`: PASS, 3 workers/9 demo projects/45 verified artifacts.
- `node --check app/static/app.js`, `node --check app/static/office3d.js`, `python -m compileall -q app scripts`: PASS.
- Real LOCAL `nginx -t` test: initial failure due to map hash bucket; renderer fixed, parsing then passed using test-only PKI and loopback listen substitution. No remote nginx/deployment/TLS evidence.
- Local nonce process contention: 64 distinct accepted; only one of 4 same-nonce contenders accepted, using a disposable SQLite DB. See `docs/V35_LOCAL_NONCE_EVIDENCE.json`.
- GC/importer maintenance controls are policy/test proof ONLY: **no live Docker, no host chattr, firewall, host quota, per-run daemon mTLS or cleanup measured**. No paid provider or Windows hardware/rollback tests. 26 screenshots are unchanged v3.3 synthetic fixtures. **PRODUCTION ADMISSION DENIED**.
- Fixed `tests/test_z_release.py` independent fixture initialization: `PYTHONPATH=. python -m pytest -q tests/test_z_release.py` **8 passed**, and core regression group again **83 passed / 8 subtests**.

## v3.6.0-rc1 — SSE authorization and optional official aggregate cost API (2026-11-08)

- Baseline: `WFS_PROJECT_v3.5_LOCAL_RUNNER_LIFECYCLE_Windows_Docker.zip`, 570 SHA256SUMS entries verified on clean extraction; 572 ZIP entries, no unsafe names/symlinks, CRC OK.
- New offline tests: `PYTHONPATH=. python -m pytest -q tests/test_v36_sse_reauthorization.py tests/test_v36_official_costs.py` **10 passed, 7 subtests, exit 0**.
- `PYTHONPATH=. python -m pytest -q` wrote a complete pytest summary **244 passed, 93 subtests passed in 33.83s** (`docs/V36_EVIDENCE/pytest_full.log`). The wrapping command's exit code was **not captured**; report the finished pytest summary without claiming a recorded shell exit status.
- `PYTHONPATH=. python scripts/http-e2e.py` **PASS, exit 0** — independent localhost Uvicorn/demo stack, auth, SSE, operator, queue and artifacts.
- `PYTHONPATH=. python scripts/parallel-e2e.py` **PASS, exit 0** — 3 worker processes, 9 demo projects, 45 artifacts.
- Official costs API tests mock the HTTPS transport; **NO LIVE OPERATOR CREDENTIAL, REAL API REQUEST OR PROVIDER BILLING VERIFIED.**
- **BLOCKED_EXTERNAL:** independent rootless Docker host, real nginx wildcard TLS/CRL rotation, actual provider invoice/caps, Windows Docker Desktop GPU/NVDA/TOTP/restore, third-party licensed skeletal assets. Production admission remains DENIED.

- Recheck after flaky combined timeout: **group 1 150 passed/40 subtests, exit 0; group 2 78 passed/53 subtests, exit 0; group 3 16 passed, exit 0**. Aggregate 244 tests/93 subtests, independently completed in three commands. Logs: `docs/V36_EVIDENCE/pytest_group{1,2,3}.log`. Combined suite remains FLAKY/NOT ACCEPTED as a single command.
