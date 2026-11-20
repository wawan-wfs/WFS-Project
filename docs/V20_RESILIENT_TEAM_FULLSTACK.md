# WFS PROJECT v2.0 — Resilient Tasks, Team & Integrated Preview

Release class: **local Windows/Docker release candidate**. Not a certification for public or enterprise production deployment.

## Upgrade from v1.9

1. Stop API, worker and **all** operator preview containers with v1.9 tools. Run preview cleanup before upgrading. Do not interrupt an active live model call.
2. Back up the complete `data/` directory and the `.env` file **separately**, with protected permissions. Test that your backups can be read; do not include them in screenshots or support tickets.
3. Extract v2.0 to a **new folder**. Copy only the previous `data/` and `.env` into it, not the old Python code or scripts.
4. Start Docker Desktop in Linux-container mode and run `START_WFS_PROJECT.cmd`. SQLite migrations are idempotent: they add `users`, `access_events`, `task_results`, `sessions.user_id` and `projects.recovery_count` while preserving deliveries and historic usage. Existing unexpired administrator sessions map to the built-in Owner account.
5. Sign in as `admin` using the original administrator password, then open **Team & Access**. Create non-owner accounts as needed. The Owner's password is still managed by `scripts/reset-password.py` / `.env` so older reset tooling continues to work.
6. Check older projects, operator requests, and AI Cost Center; run an offline demo. Test a backup restore before removing the older installation.

## Roles and visibility

| Role | Project reading | Creating projects / revisions | Queue, approval, operator jobs, budgets | Model price changes / team management / permanent deletion |
|---|---|---|---|---|
| Owner | Yes | Yes | Yes | Yes |
| Manager | Yes | Yes | Yes | No |
| Developer | Yes | Yes, plus operator notes | No | No |
| Viewer | Yes | No | No | No |

- Rights are enforced by the API and sessions, not CSS buttons. All account changes revoke the changed account's active sessions and add an access audit entry. Passwords are PBKDF2-SHA256 hashed with per-user salts; never sent to a model.
- Owner can create a Manager, Developer or Viewer, disable/enable accounts, change roles or reset another account's password. New users log in with their own username. User names are case-insensitive and unique.
- **Shared local workspace:** All roles can read all projects and artifacts. There is **no per-project tenant isolation**, MFA, SSO, organization separation or public cloud security certification. Use only on a trusted local machine/network. Protect `.env` and database backups.
- Login attempts have persistent IP-based throttling, and write endpoints require CSRF. If you want external access, a separate reviewed design with TLS, secure cookies, origin protection and identity controls is still mandatory.

## Durable specialist checkpoints

- The Master Orchestrator persists an attempt-scoped plan before coding. Each successful specialist task atomically stores its exact approved file map and SHA-256 digest in SQLite while marking the task `done` in the **same transaction**.
- On worker heartbeat expiry, tasks still in progress return to `planned` and the existing task plan is requeued. Completed results are checksum-verified and reused instead of re-calling those specialist agents.
- A job is recovered automatically **at most twice** for a single attempt. Further interruption requires operator inspection. If a project fails normally and has a checkpoint, use **Projects → Resume completed agent tasks** or `POST /api/projects/{id}/resume-tasks` to resume; standard `Retry Mission` still creates a fresh attempt instead.
- Atomic worker leases protect source-result commits from an outdated worker. This does **not** stop an in-flight external model call that was already submitted; the provider may still bill it and it may have to be retried. It does **not** make calls exactly-once, nor provide an HA distributed queue.
- Architecture/design calls may run again on resume. Results are only retained until successful project delivery or cancellation. Keep the provider budget checks enabled.

## Three-service preview (prebuilt frontend + FastAPI + PostgreSQL)

This builds upon v1.9's operator-confirmed FastAPI/PostgreSQL preview. The project must be a **completed FastAPI delivery** containing a recognized backend entry point (`app/main.py`, `main.py`, `src/main.py`, etc.) and a ready-to-serve frontend in one of:

- `frontend/dist/index.html` (preferred prebuilt React/Vite output), `web/dist/index.html`
- `frontend/index.html`, `web/index.html`, `dist/index.html`, `public/index.html`

**This does not automatically compile React or install user-defined requirements.** The frontend must already contain bundled assets. A standalone React project is not currently pairable with an unrelated FastAPI project automatically. Source is checksum-verified by the host runner before launch.

1. Open **Operator Command Hub**, choose the FastAPI project and queue `preview-trio-start`.
2. On the **Windows host**, execute `python scripts/operator-runner.py --list`, inspect your generated source, then `python scripts/operator-runner.py --job JOB_ID` and type the exact `RUN JOB_ID` confirmation.
3. The runner starts three bounded containers on a private, internal Docker network: PostgreSQL (no published port), FastAPI (localhost-only), and a trusted Python frontend gateway (localhost-only). The gateway serves prebuilt static files and forwards `/api` requests to the FastAPI backend over the private network.
4. Open the `frontend_url` from the completed operator job. You may test frontend ↔ `/api` ↔ backend ↔ PostgreSQL connectivity manually.
5. Queue and confirm `preview-trio-stop` after inspection. It removes all three preview containers, the network and the ephemeral database volume. Optionally run `CLEANUP_EXPIRED_PREVIEWS.cmd` periodically to clean up resources that outlive the 15-minute request.

Boundaries: no generated Dockerfile/Compose execution, no arbitrary npm/pip dependency installation, no Docker socket or credential access inside AI workers, localhost-only preview ports, read-only source mounts, dropped Linux capabilities, nonroot gateway, process/memory/CPU limits and a 15-minute backend wrapper. **Untrusted browser JavaScript and server code still run**; inspect the source first. Only use locally, not on a public host. Image signatures/digests, Docker Desktop runtime checks, network isolation and cleanup still require verification on your Windows machine.

## Validation commands

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -q
python scripts/http-e2e.py
python scripts/parallel-e2e.py
python scripts/browser-ui-fixture-smoke.py
python -m compileall -q app scripts tests
node --check app/static/team.js
node --check app/static/studio.js
node --check app/static/app.js
node --check app/static/operator.js
python scripts/verify-release.py
```

For a real Chromium browser against the running local API, run `set WFS_CHROMIUM_EXECUTABLE=C:\path\to\chromium.exe` (if needed) and `python scripts/browser-local-e2e.py` from the Windows system. This environment can test the HTTP server, but its Chromium is blocked by an administrator rule when navigating to localhost; the fixture browser UI test does **not** substitute for real-browser E2E.

## Production acceptance gates

Still required: real Docker Desktop startup and three-service preview test (including a real DB query and cleanup), paid-provider end-to-end/billing reconciliation, live Chromium-to-API E2E on target Windows, threat-model review and penetration test, dependency & container scanning, signed/locked image supply chain, encrypted restore drill, MFA/SSO and per-project authorization, TLS/secure cookies for remote access, failure/load soak testing, centralized telemetry, managed queue/DB and disaster recovery. Never label this local candidate as 100% public production-ready.
