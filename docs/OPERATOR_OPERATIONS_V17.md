# WFS PROJECT v1.7 — Operator Operations Runbook

## 1. What changed

**Operator Command Hub** now includes a status filter and search bar, a **Timeline & result** dialog, and a **Requeue with new approval** action for failed/rejected requests. A `react-build` type is available only for delivered React/Vite projects. The Virtual AI Office inspector shows recent operator jobs as host-side operations, **not** AI-agent work.

![Operator Hub fixture desktop](V17_OPERATOR_DESKTOP.png)

This image uses sample data, not a real paid AI session.

## 2. Windows commands

In an extracted WFS project directory, after starting WFS and signing into the dashboard:

```powershell
python scripts/operator-runner.py --list
python scripts/operator-runner.py --job <JOB_ID>
```

Inspect the selected project source and type exactly `RUN <JOB_ID>` when asked. For GitHub publishing there is another explicit `PUBLISH owner/repo` confirmation. For React preview build there is a second `BUILD` confirmation. The dashboard can queue, cancel or requeue jobs; **it cannot directly execute host commands**.

React preview jobs require Windows PowerShell, Docker Desktop, a React/Vite project, and access to npm registry for the dependency install step. The build itself runs in a network-disabled disposable container. No AI agent receives GitHub tokens or Docker host socket.

## 3. Timeline lifecycle

A new request receives `queued` stage. After typed operator approval the host runner records `running` and `preflight`, followed by a stage appropriate for the job, then `completed` or `failed`. All state changes are transactionally recorded; only generic bounded stage labels are stored in the timeline. A heartbeat refreshes `updated_at` every ~15 seconds during active host runner execution. If a process disappears, the status may remain `running`; WFS displays a **possibly stalled** warning after 15 minutes and does not auto-retry. Investigate the host process/container before any manual cleanup.

Existing jobs created before v1.7 may have no historical steps. This is expected; history is not synthesized.

## 4. Safe requeue

Only `failed` or `rejected` requests can be retried. A retry creates a new queued job, records `retry_of`, and requires the operator to separately approve it with a new `RUN` command. If the old operation might have partly affected a remote system, verify the external state before retrying. `completed`, `running`, `queued`, or `cancelled` jobs are not retryable.

## 5. Bulk task approval

Create an AI mission and choose **Human gate · per-agent approval**. In Collaboration Board, after the plan appears, select **Approve N pending tasks**, optionally add shared feedback, then confirm. Tasks marked `blocked` are preserved, and stale attempt IDs are rejected. For a blocked task, review it individually before the AI worker can continue. This gate remains blocking for the local worker.

## 6. Deployment warnings

Use only on localhost. Docker Desktop startup, paid provider behavior, GitHub mutation and source security audits must be validated on the final Windows machine. This is not a production certificate, and the FastAPI preview does not require authentication beyond being bound to localhost.
