## v2.0 — resilient tasks, RBAC and full-stack gateway

| Capability | Implemented | Acceptance caveat |
|---|---|---|
| Specialist task checkpoint storage | Yes | Atomic SQLite output+done; digest verified; no exactly-once provider semantics |
| Worker recovery | Yes, bounded | Max two automatic stale-lease recoveries, manual resume after failed run with checkpoint |
| Multiuser login and role enforcement | Yes, Owner / Manager / Developer / Viewer | Shared workspace, no MFA/SSO or per-project tenant isolation |
| User audit and revocation | Yes | Owner controls changes and reset; session revocation is immediate |
| 3-service preview request | Yes, FastAPI + prebuilt frontend + Postgres | Host confirmation required; Docker Windows not verified |
| Frontend reverse proxy | Yes, trusted Python gateway | Only `/api` forwarded; backend and bundle must be supplied in same delivered FastAPI project |
| 3-floor virtual office | Retained | Real work via telemetry; demo clearly labeled |
| Production public access | No | Separate security/design/acceptance needed |

---

# Feature Matrix — WFS PROJECT v1.9

| Capability | Status | Evidence / limitation |
|---|---|---|
| Menu navigation: 11 pages | Implemented | Browser UI fixture + source tests |
| Virtual AI Office: 3 floors / 10 divisions | Implemented | CSS/HTML 2.5D visualization, authenticated API |
| Real animation tied to worker heartbeat | Implemented | API test verifies worker + project + agent requirements |
| Offline animated demo tour | Implemented | Explicit `DEMO SCENE · NOT LIVE`; never recorded as real work |
| Agent/task/project inspection | Implemented | Read-only database-backed endpoints |
| Project lifecycle and revision lineage | Preserved | Existing v1.2 tests |
| Rename display title + project notes | Implemented | Auth + CSRF + audit; original source unaffected |
| QA center/operator commands | Implemented | Informational UI; execution remains operator-only |
| Artifact browser and ZIP | Implemented | Stored manifest + SHA-256 verify on read/download |
| Activity logs and search | Implemented | SQLite event ledger, non-immutable |
| System health + visual preferences | Implemented | Models/limits visible; browser prefs saved locally |
| Multi-account RBAC/MFA | Not implemented | Single administrator only |
| Auto full-stack runtime on cloud | Not implemented | No user-code execution in API/worker |
| Browser real server end-to-end | Not verified | Local browser network policy blocks it here; fixture UI tests separately |
| Docker Desktop on target Windows | Not verified | Startup scripts and Docker config supplied |
| Live paid model API | Not verified | Mock-provider tests only |
| Public production security certification | Not achieved | Additional hardening, external audit, load test required |

## v1.4 controls (added)

| Capability | Implementation | Limits |
|---|---|---|
| Queue ordering | Priority 0–3 + queued_at FIFO, SQLite atomic claims | Single-node local queue; no fairness quotas or SLA |
| Hold / resume | Authenticated persistent state transitions | Queued/paused only, never mid-model-call |
| Office checkpoints | Phase labels read from project records | No percent-complete or ETA |
| Agent inspector freshness | Authenticated run detail API | Heartbeat limited and status may change after response |
| Audit JSON | Project events, runs, attempts, checksums, token totals | Not proof of deployment or penetration test |
| Audit history | Cursor-pagination events API + UI | UI loads up to 50 events per page |
| Real HTTP E2E script | Temporary independent Uvicorn and worker, offline template | Not live provider, Docker or browser localhost E2E |

## v1.6 collaboration and live events

| Capability | Status | Evidence / limitation |
|---|---|---|
| Collaboration Board | Implemented | Task ownership for newly executed AI missions only; no fabricated demo tasks |
| Task state persistence | Implemented | Attempt-scoped planned/working/done/failed/blocked; SQL transactional updates |
| Specialist handoff ledger | Implemented | Four real phase boundaries; not autonomous chat transcripts |
| Operator decision/blocker/review log | Implemented | Authenticated append-only notes and audit event; does **not** feed in-flight prompts |
| SSE + reconnect cursor | Implemented | Authenticated, bounded 28s stream, browser EventSource, normal polling fallback |
| Notes and handoffs in project audit | Implemented | Authenticated JSON trace, no secret material |
| Browser fixture desktop/mobile | Verified | Chromium fixture test including collaboration page |
| Docker Windows / live provider / public production | Not verified | See production readiness gates |

## v1.6 operator controls

| Feature | Implemented | What is not implied |
|---|---|---|
| Task approval before coding | Yes, opt-in per new AI project | Not a mid-call cancellation or task reassignment engine |
| Per-task feedback | Yes, approved prompts receive bounded feedback | No automatic re-planning; blocked tasks wait for approval |
| Operator job board | Yes, authenticated creation/list/cancel and durable results | Web server never directly runs Docker or GitHub |
| Host operator runner | Yes, explicit typed approval for every action | No unattended production deployment |
| FastAPI runtime QA | Host runner supported with no-network Docker | Not tested here on Windows Docker Desktop |
| Local full-stack FastAPI preview | Dedicated time-limited Docker runtime, 127.0.0.1 bound | No arbitrary dependencies/DB services; not security-certified |
| GitHub draft PR | Verified source + new branch workflow via `gh`, explicit confirmation | No automatic merge and not live-tested against GitHub |
| Android/desktop Operator Hub UI | Chromium fixture passed at 390px and 1540px | Fixture is not a real API/model execution |

## v1.8 — Parallel Preview & FinOps (2026-11-07)

| Capability | Implemented | Verified / limitations |
|---|---|---|
| Operator-confirmed Node.js web/API preview | Yes, via runner and `node:22-alpine` | HTTP builtin only; no external npm install; Docker Windows not tested here |
| Operator-confirmed FastAPI preview | Existing feature retained | Isolated container; no arbitrary pip install; Docker Windows not tested here |
| Static & React preview | Retained | Static dashboard preview; React requires separately approved build |
| Nonblocking human approval | Yes; persistent checkpoint and worker release | On approval, queued job resumes same attempt without repeat planning; individual model call still blocking within its worker |
| Multi-project parallel execution | Atomic SQLite claims, capped active projects, multiple worker replicas | Real offline HTTP/multiprocess test with 3 workers, 9 demo projects, 45 artifacts; no live provider load test |
| AI Cost Center | Per-model, per-project, per-day tokens, call outcomes, estimated USD | Prices are operator entered, snapshot on each usage record, not provider invoices |
| Soft estimated spending cap | Optional via env | Pre-call estimate, may differ from provider charges and cannot enforce hard billing cap |
| Mobile/desktop UI | 12 navigation pages including Cost Center | Browser uses fixture; localhost browser E2E blocked in execution environment |
| Production cloud readiness | No | See PRODUCTION_READINESS.md; Docker Windows and live paid model not verified |

## v1.9 — multi-service preview & cost budgets

| Capability | Implemented | Verification / limitation |
|---|---|---|
| FastAPI + temporary PostgreSQL preview | Yes, operator-host runner with 2 Docker containers | Contract-tested with Docker commands mocked; no actual Docker Engine in build environment |
| Private database and localhost web port | Network `--internal`, no DB `-p`, backend `127.0.0.1` only | Must verify Docker port binding on target Windows |
| Preview cleanup | Explicit stop and CLI cleanup of expired resources | PG remains until host cleanup; Windows Task Scheduler can run cleaner |
| Per-project soft estimate limits | Authenticated budget form + provider pre-call gate | Soft gate only; in-flight and parallel calls may overshoot |
| Budget warning events | Idempotent SQLite alert rows at configurable percentage and exceeded limit | Verified through tests; events not external billing alarms |
| FinOps CSV detail | Authenticated export, per-call rates captured at time of use | Older usage has no rate snapshots; 30,000 newest rows max |
| UI 12-page regression | Desktop/mobile Chromium fixture test | Direct real browser localhost blocked in this environment |
| Windows/Docker production status | **NOT VERIFIED** | Local release candidate only; acceptance checklist required |


## v2.2 — Spatial Studio & UI/UX (2026-11-08)

| Capability | Implemented | Verified / limitations |
|---|---|---|
| 3D office geometry | Original WebGL2 + CPU projected 3D | CPU screenshot and orbit tested in Chromium; hardware WebGL2 runtime not available to test |
| Spatial camera controls | Orbit/pinch via drag, wheel zoom, rotate/reset buttons | Chromium fixture tested, mobile width 390px no horizontal overflow |
| Telemetry & demo truth | Authenticated `office/live` snapshot, demo truth label | Fixture state verified; live provider agent run not tested |
| Accessibility fallback | HTML division cards, keyboard buttons, reduced motion, retained 2.5D | Browser fixture/contract checks; screen-reader test outstanding |
| New UX theme | CSS tokens, cards, hero, sidebar, form controls and mobile layout | Chromium desktop/mobile fixture screenshots captured |
| Click handler regression | Project-only scoping of `data-id` handlers | Browser Operator job Timeline works again |
| Three project-local UX skills | Files bundled under `.agents/skills` and `AGENTS.md` | Existence/tests checked; third-party ChatGPT plugin not automatically installed |
