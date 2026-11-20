# WFS PROJECT v2.9.0-rc1 — Evidence-based acceptance matrix

**Classification: PARTIAL LOCAL RELEASE CANDIDATE; PRODUCTION ADMISSION DENIED.** Baseline: v2.8.0-rc1 release source. Date: 2026-11-08. The only verified execution environment here is local Linux/Python/Chromium; the user-target Windows 10/11 GPU/Docker Desktop and separate rootless Linux Docker host are not available.

| Gate | Local evidence / limitations | Status |
|---|---|---|
| Source continuity | v2.8 source copied, additive modules, retained thirteen menus, ten divisions, queue, workers, telemetry, MFA and FinOps | Implemented |
| Per-attempt immutable QA archive | v29 bound TAR plus `project_id`, `attempt_id`, SHA-256, no overwrite; negative path/manifest tests; strict remote QA requires exact per-attempt namespace | PASS local policy |
| Real rootless Docker host | No Docker CLI or isolated rootless daemon available; no real cgroup, image admission, TLS daemon, firewall, FS_IOC_GETFLAGS or host socket evidence | **NOT RUN** |
| Client certificate per attempt / TTL GC / crash recovery | Operator runbook only, no daemon-side implementation | **BLOCKED** |
| Provider uncertain charge handling | Ambiguous failed attempts persist as `billing_unknown` and remain fail-closed when spend limit exists; retry errors tracked; missing usage cannot become zero usage | PASS local mock tests |
| Provider response ID deduplication | New nullable `usage.provider_response_id` with unique index, idempotent SQLite migration; cross-tenant duplicate denied by DB | PASS local |
| Cost comparison | Offline, operator-provided per-response CSV + full SHA-256, read-only ledger comparison and tenant-by-workspace aggregation with anomaly flags; no provider/export authentication performed | PASS local tests; **NOT LIVE** |
| Actual paid provider usage / invoice reconciliation / provider-side hard daily caps | No paid credentials or independent official export; unmatched/unknown attempts remain blocked for production | **NOT RUN** |
| Isolated preview static gateway | Retained v2.8 TestClient security controls; gateway not deployed via real DNS/TLS proxy | PASS existing mock tests |
| Dynamic full-stack preview gateway | Real isolated authenticated TLS container proxy not delivered | **BLOCKED** |
| MFA recovery and session invalidation Windows | Existing tests only; no real Windows authenticator device drill | **NOT RUN** |
| 13 UI menus / 26 screenshots | Chromium synthetic fixture at 1440/390 with no horizontal overflow, 820 fixture audit covered; 26 newly captured screenshots labeled FIXTURE | PASS synthetic fixture |
| WebGL2 GPU Windows Chrome+Edge / 10-minute FPS / NVDA / 200% zoom | Fixture CPU 3D; timer not supported, GPU timing absent; actual hardware not available | **NOT RUN** |
| Rigged licensed avatars | Existing eight authored CC0 GLBs unchanged, procedural avatars, no animation rig | **NOT IMPLEMENTED** |
| Python suite | `PYTHONPATH=. python -m pytest -q` — **174 tests, 46 subtests passed** | PASS local |
| HTTP E2E | `python scripts/http-e2e.py` — independent localhost Uvicorn/auth/queue/worker/preview/ZIP/SSE/budget | PASS local demo |
| Parallel worker E2E | `python scripts/parallel-e2e.py` — 3 workers, 9 demo projects, 45 artifacts | PASS local demo |
| Secure installation / restore rollback v2.8 → v2.9 | Additive schema; explicit backup/restore runbook. No production data or Windows restore drill | PARTIAL |
| Independent pentest / adversarial live red team | Automated code-policy tests, not independent intrusion or privilege-escape assessment | **NOT RUN** |

**STOP CONDITION:** No public SaaS deployment, unattended untrusted-code execution, protected customer data, or production-ready label until the host, TLS, billing, MFA, GPU, accessibility, restore, and independent red-team gates have measured evidence.
