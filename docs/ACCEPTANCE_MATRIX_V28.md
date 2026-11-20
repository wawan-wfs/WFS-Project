# WFS PROJECT v2.8.0-rc1 — Evidence-first acceptance matrix

**Classification:** PARTIAL local Windows/Docker release candidate. **NOT production admitted.** Base: verified v2.7.0-rc1 strict remote QA ZIP. Date: 2026-11-08. Each row differentiates implemented/tests from actual environment proof.

| Gate | Result and evidence | Status |
|---|---|---|
| Historical v2.7 → v2.8 DB migration | v2.7 code created a project in SQLite; v2.8 initialized the same DB twice; original project ID, organization and default workspace retained. | PASS local |
| Source continuity | Untouched existing 13-page layout shell, 10 divisions, queue/worker/orchestration, project ACL, MFA, QA, local preview; additive new modules and tests. | PASS local |
| Atomic organization/workspace/project estimated admission | `app/quota.py`, `cost_reservations`, `spend_limits`, default workspace migration, `BEGIN IMMEDIATE`; successful concurrent contention, release, settlement, double-settle prevention, tenant price scoping and original model price snapshot after mid-flight rate change. | PASS tests; estimates only |
| Privileged limit update UI/API | `GET/POST /api/finops/limits`, tenant derived from authenticated session, CSRF, owner/manager role, strict schema; AI Cost Center panel wired to real API. | PASS local API/fixture |
| Preview ticket and cookie scoping | `app/preview_gateway.py`, one-time expiring ticket, Secure/HttpOnly path-scoped cookie; per-request revalidation of dashboard session, user, org, project ACL, finished delivery and artifact manifest. | PASS local gateway TestClient only |
| Real isolated HTTPS preview hostname | Example reverse proxy and operational instructions in `docs/PREVIEW_GATEWAY_V28.md`. No DNS/TLS deployment, external origin red team or production gateway service was available. | NOT RUN |
| Dynamic container preview origin isolation | Existing operator FastAPI/Node/Postgres loopback preview ports are NOT behind this new gateway. | BLOCKED |
| Rootless remote runner admission | v2.7 strict policy hardened: expected UID, capabilities, `no-new-privileges`, IPC/cgroup/PID, resource upper bounds, zero network, no socket, memory/swap match. | PASS unit policy |
| Immutable remote stage + SHA preflight | `scripts/runner-stage-package.py`, `scripts/runner-import-seal.py`, Linux `FS_IOC_GETFLAGS` immutability and file hashes before Docker execution; runbook included. | IMPLEMENTED only, not exercised on remote ext4 rootless host |
| Actual rootless Docker / egress negative / mTLS / TTL | Operator test `scripts/acceptance_v28_remote.py` supplied. Docker CLI/daemon absent from this execution environment; per-run client certificate rotation and independent host cleanup need implementation. | NOT RUN |
| Full Python suite | `python -m pytest -q`, **166 passed, 40 subtests** in final v2.8 local regression. | PASS local |
| HTTP E2E | `python scripts/http-e2e.py`, separate uvicorn process login/queue/worker/preview/ZIP/SSE/budget. | PASS localhost |
| Parallel worker | `python scripts/parallel-e2e.py`, 3 worker processes, 9 demo projects, 45 artifacts. | PASS local/demo |
| 13-menu responsive browser fixture | Headless Chromium at 1440/820/390: no horizontal overflow; 26 1440/390 synthetic fixture screenshots captured. | PASS fixture only |
| WebGL GPU benchmark, Windows Chrome+Edge, NVDA, 200% zoom | Headless fixture reported CPU 3D, `gpuTimerSupported:false`, no GPU timing or hardware VRAM; actual Windows/NVDA/zoom acceptance not conducted. | NOT RUN |
| Rigged GLB avatars + licensed real PBR lighting | Retained original 8 CC0 GLB meshes; agent remains stylized/nonrigged. No evidence-driven engine migration. | NOT IMPLEMENTED |
| Live model billing reconciliation | Original provider adapter reads returned token usage and snapshots operator-defined prices; v2.8 reserves a bounded estimate. No provider invoice, token adjustments, refunds or paid provider credentials were used. | NOT RUN / NOT RECONCILED |
| MFA offline recovery exercise | Prior automated MFA security tests retained and re-run. No real authenticator/recovery drill on a Windows user environment. | TEST ONLY |
| Security red team and host attestation | Code-level cross-tenant tests, not an independent penetration test, firewall inspection, or actual privileged host attestation. | INCOMPLETE |

**Admission decision: BLOCKED.** This package can be used for further local development and operator-only testing, not public internet deployment, unattended AI-authored runtime execution or confidential customer multi-tenancy. Source ZIP contains no user secrets, live logs, provider credentials or TLS certificates. All screenshot materials are explicitly synthetic fixtures.
