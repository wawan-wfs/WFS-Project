# WFS PROJECT v3.0.0-rc1 — Acceptance matrix (2026-11-08)

**PARTIAL LOCAL RELEASE CANDIDATE / PRODUCTION ADMISSION DENIED**. Baseline: exact v2.9.0-rc1 source ZIP. This report distinguishes local code execution from missing hardware and external infrastructure evidence.

| Admission requirement | Verified evidence | Status |
|---|---|---|
| Source continuity and preserved functionality | Exact v2.9 ZIP baseline, unchanged 13-menu UI, 10 divisions, agent queue, project events, MFA, org quota, FinOps, local preview | Preserved |
| Strict remote per-attempt staging admission | Container-create inspection plus immediate recheck of immutable FS flags and per-file SHA-256 before each workload | PASS mocked tests; no real daemon |
| Verified container cleanup | `rm` + `inspect` + live `docker info` must succeed to report pass, including timeout/failure paths | PASS mocked tests; no real daemon |
| Remote negative acceptance | Explicit `docker ps` and daemon health verification; cannot report pass when CLI failed or timeout | PASS mocked tests; no real daemon |
| Independent rootless runner and default-deny firewall | Host collector available for real operator-run checks; **no actual independent host available** | NOT RUN |
| cgroup v2, userns, ext4 immutable source | Host collector implemented; unit tests mock values, no actual host flags inspected | NOT RUN |
| Certificate revocation, signed image admission, TTL GC, disk quota, TOCTOU prevention | Not independently deployed or tested | BLOCKED |
| Static HTTPS preview isolated origin | Existing request-by-request checks verified only in local TestClient; no real TLS | LOCAL ONLY |
| Dynamic authenticated HTTPS preview | No isolated live broker for FastAPI/Node/PostgreSQL with port-deny proof | BLOCKED |
| Provider token accounting and offline CSV comparison | Existing v2.9 handling retained, no actual authenticated paid provider export/cap | LOCAL ONLY |
| Provider-side daily caps and independently verified unknown-billing clearance | Neither official provider evidence nor credentials available | BLOCKED |
| Linux/Python backend regression | `PYTHONPATH=. python -m pytest -q` | PASS LOCAL: 187 passed, 46 subtests passed |
| HTTP and multi-worker E2E | `python scripts/http-e2e.py` and `python scripts/parallel-e2e.py` using local demo providers | PASS LOCAL |
| Browser menu/screenshot fixture | Chromium 13 pages @1440/820/390, 26 newly generated desktop/mobile screenshots, CPU 3D | PASS FIXTURE |
| Actual Windows Chrome+Edge GPU driver, FPS, VRAM, NVDA and 200% zoom | No Windows GPU/screen reader environment used | NOT RUN |
| True rigged PBR characters | Existing 8 authored CC0 GLBs have no skeletal rig; GPU gates absent | NOT IMPLEMENTED |
| Live MFA recovery and multi-host rollback | No actual Windows authenticator/host backup performed | NOT RUN |
| Full SHA-256 source verification | `RELEASE_MANIFEST.json` hashed source/package verification | PASS after packaging |

**No claims of production-ready, public Internet security, hardware benchmark or paid billing accuracy are made.**
