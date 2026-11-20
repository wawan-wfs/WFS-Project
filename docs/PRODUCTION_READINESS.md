# Production-readiness acceptance — WFS PROJECT v2.1

**Classification:** Local release candidate. This package is intended for evaluation on a trusted Windows machine behind localhost; it is **NOT certified for public/internet-facing production use**.

## Implemented controls

- Local multiuser authentication with four RBAC roles, hashed passwords, session revocation and session cookies; CSRF protection, localhost binding and restrictive CSP.
- Durable SQLite state, atomic worker claims, active-project cap, recovery of stale running workers, project artifacts with SHA-256 verification.
- Nonblocking manual approval checkpoints, bounded per-project model calls/tokens, operator-controlled pricing estimates (not real billing), provider usage audit and SSE updates.
- Explicit external host operator workflow for Docker QA, bounded preview and draft GitHub PR. AI worker cannot access Docker daemon or GitHub credentials directly.
- Static source validation, browser fixture tests, independent Python HTTP smoke and three worker-process local smoke.

## Mandatory external acceptance gates before public production

| Category | Current result | Required next step |
|---|---|---|
| Windows Docker Desktop | **UNVERIFIED** | Full fresh-install and upgrade test with Docker Engine, 3 workers and preview container lifecycle |
| Live provider API | **UNVERIFIED** | Paid end-to-end model calls, rate limits, token/billing reconciliation, provider-side budget controls |
| Browser real backend | **UNVERIFIED** | Playwright/Chromium login → projects → approval → preview → cost center against actual app on target Windows |
| Runtime app preview | **UNVERIFIED** | Node/FastAPI runtime URLs, Docker isolation flags, TTL, stop/restart, CSP and failure handling |
| Backup and restore | **NOT DONE** | Restore a real copied dataset and encrypted credential backup after a failure simulation |
| Multiuser identity | **PARTIAL: local RBAC + project ACL implemented** | Add MFA/SSO, full organization/tenant isolation and external identity audit before external users |
| TLS / public ingress | **NOT IMPLEMENTED** | Secure public ingress proxy, HTTPS, cookies with secure flag, host allowlist and rate limiting |
| Security assurance | **NOT DONE** | Dependency/SBOM scan, secrets scanning, container policy review, threat model, penetration testing |
| Availability and scale | **NOT IMPLEMENTED** | Broker-backed workers, managed transactional DB, observability/alerting, retention and disaster recovery |
| Billing correctness | **PARTIAL estimates only** | Provider invoice reconciliation, cached token and retry policies, FX/tax handling and hard provider spending caps |

Do not label the system '100% production-ready' until these gates pass in the real deployment environment. Generated source code also requires individual code review, tests, secure configuration and deployment acceptance.

## v1.9 additional acceptance

- **FastAPI + PostgreSQL preview:** actual Docker Engine test of both containers, real DB query, database network isolation, bridge and localhost port binding, health validation, explicit stop and expiry cleanup. This test was NOT executed in the packaging environment.
- **Soft project budget:** test a real low-cost API account; reconcile cached tokens, retries and model rate differences with the provider bill. Never treat the estimate budget as a hard limit.
- **Supply chain:** scan and pin trusted preview image digests before production; image builds currently use a fixed trusted Dockerfile but version ranges for PostgreSQL libraries.
- **Credential handling:** generated PostgreSQL password remains private to host Docker container environment; it must not be logged or copied into generated source.

## v2.0 additional acceptance

- Confirm on Windows Docker Desktop that the three-service frontend/FastAPI/PostgreSQL preview starts, returns a real `/api` response and database query, and tears down all containers, network and volume. Verify the gateway image and network isolation at runtime.
- Confirm that a worker killed during the second coding task can resume from the first task result without reissuing the first model call, and test bounded retry/cost implications against a real provider.
- Confirm all four roles against a real browser and against direct API requests. All users still share the same projects; this is not enterprise tenant isolation.
- Test a full v1.9 database restore and upgrade in a protected Windows environment, with live and inactive sessions.

## v2.1 additional acceptance

- Test that an unauthorized existing session receives 404 for all private project paths, source and preview, with no secret project references in global activity or FinOps responses. Covered by deterministic tests, **not** a penetration test.
- Confirm access revocation while a browser keeps SSE open; no subsequent private event data may appear. Server re-checks ACL on each SSE retrieval and terminates targeted private streams.
- Reconcile legacy `workspace` projects, imported or restored project trees, and generated preview URLs before granting access to external users. Existing projects stay workspace-shared by migration design.
- Validate the UI via real Windows browser and authenticated FastAPI backend, not solely offline fixtures. Test the v2.0-to-v2.1 SQLite upgrade with a backed-up dataset.
- Evaluate MFA/SSO, strict tenant separation, secure operator preview routing, and endpoint/host hardening before public production.


## v2.2 UI/3D deployment gates (2026-11-08)

- [x] Original client side 3D code bundled locally under CSP `script-src 'self'`.
- [x] Native HTML controls for orbit/zoom/reset, room inspector and manual fallback to 2.5D.
- [x] Demo status is distinguished from actual authenticated telemetry.
- [x] Python regressions, API HTTP E2E, 3-worker demo execution, and UI Chromium fixtures.
- [ ] Real Windows Docker Desktop startup and real Chrome/Edge browser against authenticated backend.
- [ ] GPU WebGL2 path smoke and sustained FPS/VRAM profiling on low/mid-spec Windows and Android devices.
- [ ] Screen reader and formal contrast audit; keyboard-only, 200% zoom, mobile touch across all menus.
- [ ] Real AI model API, billing provider reconciliation, production security deployment acceptance.

Until these gates pass, label the release **Local Release Candidate**. No claims of production certification.
