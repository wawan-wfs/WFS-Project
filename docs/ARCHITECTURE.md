# WFS PROJECT — Architecture v1.2 Extended Local

```text
Windows browser 127.0.0.1:8080
   | HTTPS? NO (localhost-only) / authenticated HTTP API
   v
FastAPI Control Plane (no Docker socket, no generated-code execution)
   |         |              |
   |         + Static / opt-in React preview (CSP sandbox, opaque origin)
   |         + Login, versioned projects, archives, worker diagnostics, files, SHA-256 ZIP, approval API
   v
SQLite WAL on local data volume
   |
   v
Persistent Worker (separate container; no Docker socket)
   |
   + Master Orchestrator + Product Manager plan
   + Architecture Agent + UI/UX Agent (parallel)
   + Specialized Agent file tasks (parallel, ownership bounded)
   + Static QA -> Advisory AI QA -> conditional repair
   + Release Gate: completed OR review_required
   + Artifact delivery + report + usage log

[Opt-in Windows PowerShell operator scripts]
   + syntax QA: no-network Docker containers; optional FastAPI runtime smoke with explicit operator consent
   + React build: controlled npm install, isolated no-network build
   + GitHub draft PR opt-in, backup/restore/runbook
```

## Three floors and ten divisions

- **Floor 01 — Strategy**: Management, Architecture, Operations
- **Floor 02 — Production**: Engineering, Creative Studio, AI & Data, Documentation
- **Floor 03 — Reliability**: Quality Lab, Infrastructure, Security

Subagents adalah invocation model dengan role dan scope file yang terpisah, bukan proses OS independen. Pembagian divisi dapat melibatkan banyak agent atau tidak terlibat, sesuai rencana proyek. AI tidak bisa mengakses Docker atau terminal host langsung.

## State machine

`queued -> running -> completed | review_required | failed | cancelled`.

`review_required -> completed` hanya melalui endpoint approval dengan CSRF oleh administrator. Ini mencatat penerimaan risiko, **bukan** sertifikasi keamanan. `running -> cancel_requested -> cancelled` saat checkpoint. Worker mati dapat menjadi `interrupted`, perlu retry manual; retry mengulang seluruh pipeline dan dapat mengulang biaya model.

## Database

Tabel `projects` (termasuk lineage `parent_id` dan `archived_at`), `events`, `agent_runs`, `artifacts`, `usage`, `provider_attempts`, `worker_instances`, `sessions`, dan `auth_failures`. Migrasi kolom berlangsung idempotent pada startup. Database WAL dan file berada pada volume lokal. API dan worker dibuat terpisah. Worker tidak memiliki HTTP healthcheck karena bukan server web.

## Resource & execution boundary

API dan worker hanya membaca/menyimpan kode, tidak mengeksekusinya. Compose non-root, read-only root, cap-drop, no-new-privileges, PID/CPU/RAM limit. Script Windows opt-in dapat menjalankan syntax QA dalam container dengan jaringan terputus. React build dilakukan di salinan sementara proyek; npm dependency installation memakai ignore-scripts, tahap build tanpa network.

React preview meng-inline CSS/JS build lokal ke satu dokumen sandbox. Bundle dengan dynamic imports atau assets eksternal dapat tidak tampil, dan ini **bukan** pengganti staging web production. FastAPI/React belum otomatis menjalankan server dinamis pada port host tersendiri. Untuk menjalankan aplikasi hasil AI sepenuhnya, gunakan deployment staging terisolasi yang dibuat/diperiksa operator.

## Scaling boundary

Target lokal satu admin, satu host, satu API container, satu worker, dan SQLite WAL. Untuk multiuser/hosting publik diperlukan PostgreSQL, queue broker, RBAC/MFA, audit central, TLS/edge protections, durable rate limits lintas-node, sandbox per proyek, dependency scanning, observability, backups, incident response, dan security review.

## Revision inheritance and artifact integrity

`POST /api/projects/{id}/revisions` requires a completed parent and configured API key. The new project has its own ID and immutable parent reference; it reads parent source after checking each artifact against the recorded byte length and SHA-256 digest. It provides bounded source context to the model, takes only file paths assigned to new specialist tasks and carries unchanged files into the child delivery. The old version is never overwritten.

Read/ZIP/static-preview and revision creation reject modified or missing artifacts. These checks do not protect against an attacker with full write access to both the SQLite database and files. For stronger provenance, add signed release attestations.

## Worker visibility

Every worker pings a database row periodically when idle or running. `/api/diagnostics` reports workers with a recent heartbeat, queue counts and tasks. The live office panel aggregates actual `agent_runs` records, rather than simulated agent animation. The endpoint requires admin authentication.

## External source export

`publish-github.py` is never invoked from the worker. It reads verified delivered files, requests the operator's local Git/gh credentials only on the Windows host, requires an explicit `--publish` flag and typed confirmation, and pushes a unique branch + draft PR. The default is a no-network dry-run.

## v1.3 visual console and read-only agent observation

The UI is split into eight navigable pages while reusing the authenticated FastAPI web service. `app/static/studio.js` handles read-only department/workspace display; all strings originating from user projects or provider responses pass through HTML entity escaping. Division color CSS classes are allowlisted in `style.css`, avoiding inline HTML style attributes that strict Content Security Policy would block.

`GET /api/office/live?floor=1|2|3&project_id=<optional 20hex>` joins persisted agent runs and parent project states; a run is marked **live** only if `agent_runs.status='working'`, `projects.status='running'`, project heartbeat is fresh (<=45 seconds), and the linked worker also reported online. Otherwise an old working run becomes `interrupted` on the visualization; it is **never falsely animated as running**. The UI's optional Demo Tour is a separate local in-browser fixture labeled `DEMO SCENE · NOT LIVE`, not persisted into the database.

Other authenticated read-only endpoints are `/api/agents/directory`, `/api/workspace/activity`, `/api/workspace/artifacts` and `/api/workspace/capabilities`. No secret tokens are returned by capabilities. `POST /api/projects/{id}/metadata` requires session and CSRF, validates input, records an audit event and updates display-only `title` and `notes`; it does not change original user prompt or source files. The `notes` schema field is added by an idempotent SQLite migration.

## v1.4: Durable dispatch and audit observability

`projects` obtains `priority INTEGER DEFAULT 1` and `queued_at TEXT`. `init_db()` performs an idempotent migration of existing databases. Worker `claim()` runs under a SQLite `BEGIN IMMEDIATE`, claiming only `status='queued'`, with ordering `priority DESC,queued_at,id`. Operator mutations (`pause`, `resume`, `priority`) also run within `BEGIN IMMEDIATE` and require CSRF authentication at the API layer. A running project cannot be paused mid-provider call. Paused jobs remain durable across restarts; cancelled jobs can be retried manually.

`/api/queue` returns a bounded, ordered queue snapshot; `/api/workspace/events` uses monotonic event ID cursors (`after_id`) instead of an offset; `/api/projects/{pid}/trace` exports structured read-only audit data. Admin API responses do not disclose raw session token, passwords or model API key. `agent_run_detail` returns a live flag only when the run, project status and fresh worker heartbeat agree. A graceful worker stop deletes its `worker_instances` record.

Virtual Office renders actual phase labels and queue snapshots, not calculated percent-complete. UI refresh is polling-based; no fake streaming claims or background autonomous work beyond the configured worker services.

## v1.5 task ledger and SSE transport

`planned_tasks` stores one immutable planned file-ownership record per `(project, attempt, task_key)` and monotonically advances task status. `agent_handoffs` records phase-boundary handoffs with concise summaries. `operator_notes` stores authenticated append-only annotations and emits an event. An `events` table supplies the cursor for the authenticated Server-Sent Events feed; no pub/sub broker is required for this single-node design. `/api/live/events` rechecks the revocable session, returns an event `id`, emits comment heartbeats, and closes after ~28s so the browser reconnects via `Last-Event-ID`. If SSE fails, regular polling remains available. This is **not** suitable for distributed at-scale fanout without a dedicated message broker and reverse proxy design.
