# WFS PROJECT v1.8 — Engineering design, API contracts and operator runbook

## Queue and checkpoint state machine

```text
queued --atomic claim--> running:planning
   -> planned_tasks + task_reviews
       automatic: running:architecture -> implementation -> quality -> delivered
       manual: project_checkpoints saved -> awaiting_approval (worker released)
                pending/blocked reviews -> approved by operator
                all approved -> queued (same attempt)
                atomic claim -> running:architecture -> implementation -> quality -> delivered
```

**Durability boundary:** plan, tasks, review decisions, attempts and events persist in SQLite. `project_checkpoints` stores the validated plan and file ownership for a single active attempt. Reclaim after approval **does not increment the attempt counter**; normal retry after interruption deletes the checkpoint and plans a new attempt. The API and AI worker do not execute generated source directly. SQLite's `BEGIN IMMEDIATE` protects each claim and the global `WFS_MAX_ACTIVE_PROJECTS` counter against concurrent worker processes; scale workers only on the same trusted local host. A blocked manual task prevents automatic resume. Calling cancel while awaiting review marks project cancelled without reopening the queue.

There is no per-task distributed message broker, multi-node lease service or resumable individual model call. Model calls remain synchronous inside an assigned worker and specialist concurrency is bounded by `WFS_MAX_PARALLEL`. For HA deployment, replace SQLite with a supported broker/managed DB and implement strong worker leases and idempotent external actions.

### Config

| Environment | Default | Meaning |
|---|---:|---|
| `WFS_MAX_ACTIVE_PROJECTS` | 3 | Maximum simultaneous claimed project records, 1–8 locally |
| `WFS_MAX_PARALLEL` | 2 | Coding threads within each project, 1–4 |
| `WFS_MAX_MODEL_CALLS` | 24 | Per-project model call limit |
| `WFS_MAX_TOTAL_TOKENS` | 300000 | Per-project provider token usage limit (checked between calls) |
| `WFS_MAX_ESTIMATED_COST_USD` | 0 | Optional soft USD threshold. 0 = no additional estimated-cost gate |
| `OPENAI_MODEL`, `WFS_MODEL_MASTER`, `WFS_MODEL_WORKER`, `WFS_MODEL_QA` | configurable | Model routing; tariffs must be separately set by operator |

### Authenticated API additions

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/concurrency` | Running/queued/waiting count, configured capacity, worker list |
| GET | `/api/finops/report?period=7d\|30d\|all&project_id=...` | Token usage, attempts, by-model, by-agent, by-project, by-day USD estimates, unpriced count |
| GET | `/api/finops/prices` | Operator-entered model price records (no keys) |
| POST | `/api/finops/prices` | CSRF protected; `{model, input_usd_per_million, output_usd_per_million}` |
| POST | `/api/projects/{id}/tasks/{task_key}/review` | Approve/block one task and atomically requeue if all have been approved |
| POST | `/api/projects/{id}/tasks/approve-pending` | Approve still-pending tasks; blocked tasks remain blocked |

All routes require a valid admin session; mutations additionally require CSRF. No provider secrets or session IDs are sent to the dashboard. The dashboard only displays accepted backend state; `demo tour` is labeled fake.

## Node Web / API preview contract

New stack: **`node-web`**. To generate compatible projects, require:

- `server.js` using Node.js core `http` (and optionally other core libraries) to serve API routes and static HTML; listens to `0.0.0.0` on `process.env.PORT || 8000`.
- `package.json` object with a `scripts` object. External `dependencies` and `devDependencies` must be absent. No generated `npm install` will be invoked by the preview.
- Plain text project files, SHA-256 verified against delivered manifest before operator actions.

Example `server.js` (for clarity only; not executed in the WFS API service):

```js
const http = require('node:http');
const port = Number(process.env.PORT || 8000);
http.createServer((request, response) => {
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  if (request.url === '/api/health') return response.end(JSON.stringify({ok:true}));
  return response.end(JSON.stringify({message:'WFS Node Web preview'}));
}).listen(port, '0.0.0.0');
```

**Operator workflow:** Once the Node Web or FastAPI source is delivered, queue `preview-start` from Operator Command Hub, inspect source, run `python scripts/operator-runner.py --job <ID>`, and type `RUN <ID>`. Container startup returns a fresh `http://127.0.0.1:<port>/` URL; the result appears in the dashboard. Use `preview-stop` with a fresh approval to stop earlier; TTL is 15 minutes. Static web and React/Vite still have their own sandboxed HTML preview mechanisms. All URLs are *local only*.

Security posture: fixed trusted Node image `node:22-alpine`, network `wfs-preview-internal` created with `docker network create --internal`, loopback-only published host port, `--user 10001:10001`, `--cap-drop ALL`, `--read-only`, `--pids-limit 64`, `--memory 512m`, `--cpus 1`, `no-new-privileges`, read-only volume, bounded tmpfs and wrapper time limit. **Run only after reviewing source**. Cannot guarantee isolation under every Docker Desktop version; requires real Windows validation and is not intended for exposure to external users. An operator-approved runtime is inherently higher risk than syntax-only QA.

## FinOps accounting model

- `model_pricing` stores user-provided USD input/output prices per **one million tokens** with `updated_at`.
- Each `usage` record contains model, role, input tokens, output tokens, time and `estimated_usd`. A missing rate yields NULL; changing a tariff does not modify recorded historical costs.
- API response splits by model, project, agent and day; includes unsuccessful provider attempt **counts** separately. Failed responses may still incur charges provider-side even when usage metadata is unavailable.
- The report is capped at the 30,000 latest matching usage records and flags `truncated=true` if more exist. If any usage row has NULL cost, `price_coverage_complete=false`; partial USD should never be presented as a complete invoice.
- Budget controls are pre-call soft checks only. Current call, overlapping calls, cached token pricing and billing adjustments can exceed estimate. Check provider dashboards to control real spending.

## Local test checklist

1. Log in as admin and create multiple **demo** missions while running three worker replicas. Confirm unique claims, every job completes once, and `AI Cost Center` reports capacity.
2. Submit one real AI project with **Human gate**, verify `awaiting_approval` and no occupied worker, approve tasks, verify resumption at the same attempt.
3. Configure correct model rates from the provider's own pricing documentation; run one low-budget AI project, inspect token/attempt breakdown, modify rate and verify earlier snapshots remain unchanged.
4. Generate FastAPI and Node Web apps; run `preview-start`, test their local HTTP routes, and verify TTL/stop and resource flags using `docker inspect`.
5. Generate React/Vite, consent to npm dependency install and sandboxed build, then inspect the dashboard preview. Test QA/PR separately as required.
6. Verify security with guest/CSRF tests, check browser UI on desktop/mobile against the actual API, and execute backup plus restore drill.

**Unverified here:** full Docker Desktop runtime and real paid API pricing/provider billing. See `PRODUCTION_READINESS.md`.
