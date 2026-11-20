# WFS PROJECT v2.6 — acceptance evidence and unsatisfied gates

| Requirement / gate | Verified observation | Classification |
|---|---|---|
| Baseline source v2.5.0 | Used exact `WFS_PROJECT_v2.5_SECURE_SPATIAL_Windows_Docker.zip`; kept all 13 pages, eight original CC0 GLB assets and v2.5 2.5D/CPU fallbacks. Tested an **actual v2.5-initialized SQLite** upgrade to v2.6 (two migration passes) retaining project ID and owner access. | **PASS source continuity / local migration smoke** |
| Organization IDs, default migration, project/resource scope | Three-org adversarial TestClient + SQLite regressions; routes incl files, events, SSE, budgets, previews, operator jobs, prices denied when foreign | **PARTIAL security** (no exhaustive pen test/quotas) |
| Mandatory org TOTP | Setup-only state, secure enrollment + recovery unchanged, MFA disable forbidden, tests | **PARTIAL** (no SSO/WebAuthn) |
| Session/device controls | Account-only inventories, individual and all-other revocations, CSRF and cross-account tests | **PASS local regression** |
| Python regression | `python -m pytest -q` → **149 passed, 20 subtests passed**; `python -m unittest discover -s tests -v` → **149 passed** | **PASS local tests** |
| HTTP API + worker | `python scripts/http-e2e.py` → PASS; `python scripts/parallel-e2e.py` → PASS, 3 worker processes, 9 demo projects and 45 validated artifacts | **PASS local offline demo** |
| 13-menu visual fixture + 26 captures | `WFS_V26_CAPTURE=1 python scripts/browser-ui-fixture-smoke.py`, 13 desktop + 13 mobile screenshots at fixture viewport sizes | **PASS fixture only** |
| 3D locally | Fixture renderer=`cpu-3d`, 9,520 geometry triangles, draw calls 13, GPU timer unsupported | **CPU-only** |
| Licensed rigged GLB + skeletal animation/PBR engine | Existing GLBs are original **non-rigged** procedural assets; pinned offline engine/skin animation not added | **NOT IMPLEMENTED** |
| Real GPU WebGL2 Chrome + Edge on Windows 10/11 | No Windows GPU/driver instrumentation in this environment; VRAM/FPS must be measured on hardware | **NOT RUN** |
| Real Windows Docker Desktop image/host isolation | No trusted isolated Docker Engine/Windows runner; no rootless host, immutable admission or network red-team | **NOT RUN / NOT CERTIFIED** |
| Authenticated expiring HTTPS preview origins | Local authenticated static preview only; no external TLS proxy | **NOT IMPLEMENTED** |
| Live AI provider, actual billing reconciliation | Offline fixture/test provider only; estimated costs are not provider invoices | **NOT RUN** |
| Authenticated browser E2E on actual Docker Desktop | API HTTP E2E completed, not full real browser/TOTP/worker/preview journey | **NOT RUN** |
| Windows screen-reader + 200% zoom | Not executed on real Windows NVDA/Narrator; fixture checks cannot substitute | **NOT RUN** |
| Multi-organization production security/quotas | Initial org boundaries implemented; database, worker quotas, billing and system identity require independent red team | **NOT CERTIFIED** |

## Screenshot provenance

`docs/V26_FIXTURE_SCREENS/DESKTOP_01_overview.png` through `DESKTOP_13_team.png` and `MOBILE_01_overview.png` through `MOBILE_13_team.png` were created using **offline Chromium stubs with synthetic fixture projects/agents**, not authenticated live worker telemetry. Extra MFA and login screenshots also use dummy/fake browser responses. Original v2.5 fixture screenshots remain in `docs/V25_SCREENS/` for comparison. Never submit them as real Windows GPU, docker, human acceptance or evidence of a completed AI assignment.

## Release decision

**LOCAL RELEASE CANDIDATE ONLY — PRODUCTION GATE CLOSED.** A Python, SQLite or fixture browser green test is not a replacement for actual rootless Docker isolation, TLS origin-based preview auth, GPU acceptance, provider metering or MFA recovery exercise on an operator's Windows device.
