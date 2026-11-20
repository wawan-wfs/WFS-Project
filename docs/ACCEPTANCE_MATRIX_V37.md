# WFS PROJECT v3.7.0-rc1 — Evidence & acceptance matrix

| Gate | Evidence | Result |
|---|---|---|
| Source baseline | Exact v3.6 ZIP SHA-256 `2c81cd157ea77e88f7b1a81eed6099e7748db0ae0baa22f8f38e5041560e73e9`; `scripts/verify-release.py` checked 588 original source files | PASS_LOCAL |
| SSE backpressure, per-session/global cap, release and pagination | `tests/test_v37_sse_backpressure.py` and v3.6 stream authorization; local async mocks | PASS_LOCAL_TEST |
| Dynamic preview admission, resource release, path sanitization | `tests/test_v37_broker_backpressure.py` and legacy broker regression; fake Unix workload | PASS_LOCAL_TEST |
| Backend tests | 109+69+59+8=245 tests and 20+31+50=101 subtests in independently completed groups; 8 release-gate tests passed after manifest regeneration | PASS_LOCAL_GROUPED; 253 tests including release checks; COMBINED TIMEOUT |
| HTTP E2E | `docs/V37_EVIDENCE/http_e2e.log`: localhost Uvicorn, auth, queue, preview, SSE | PASS_LOCAL |
| Multi-worker demo | `docs/V37_EVIDENCE/parallel_e2e.log`: 3 real local workers, 9 demo projects, 45 test artifacts | PASS_LOCAL |
| Combined v3.7 + release test fixture | After patching deterministic test import order, 17 tests and 8 subtests in one process, exit 0 | PASS_LOCAL |
| Source syntax | `compileall`, JS `node --check` | PASS_LOCAL |
| Real independent rootless Docker | No Docker CLI/daemon or authorized host available | BLOCKED_EXTERNAL |
| Actual Nginx mTLS across separate hosts, two-tenant HAR | No authorized DNS/TLS, host, cert rotation or browser HAR | BLOCKED_EXTERNAL |
| Official authenticated provider cost invoice and cap | No approved provider credentials, paid calls or statement | BLOCKED_EXTERNAL |
| Windows Chrome/Edge GPU, NVDA, MFA recovery, matched restore | No physical Windows operator host | BLOCKED_EXTERNAL |
| 3D skeletal avatar proof | Existing 8 CC0 meshes, no licensed rigged replacement or GPU evidence | NOT_RUN |
| Screenshots | Unchanged **26 v3.3 browser fixtures** reused from v3.6 | REUSED_FIXTURE |
| Production classification | All independent host/TLS/provider/Windows/recovery gates missing | **DENIED** |

Timeout of one monolithic pytest execution is explicitly NOT a pass. Group results have separate exit codes; do not add failed or duplicated runs to test totals. No user-host infrastructure was modified.
