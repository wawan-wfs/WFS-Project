# Operator Command Hub — WFS PROJECT v1.6

## What it actually does

**Dashboard:** requests jobs; does not run Docker or GitHub operations itself. The operator runs jobs from a dedicated Windows host script after reviewing generated source. No arbitrary shell command can be entered through the API. Operator logs and job results are persisted in the existing SQLite database. No GitHub tokens or Docker socket are attached to the API/worker containers.

## 1. Manual approval for specialist tasks

1. Configure AI API key, choose `Real AI Agents` and `Human gate · per-agent approval` in Mission Control.
2. Submit the project. Master Orchestrator creates specialist tasks and stops at `task_approval` before coding.
3. Open Collaboration Board and select the new project. Read each specialist's ownership and planned output files.
4. Select **Approve** or **Block**, optionally including feedback. Approved feedback is supplied to that specialist when coding begins; a blocked task must subsequently be approved to release the gate.
5. All tasks must be approved. A blocker or nonresponse keeps the worker occupied. Cancel the project or allow the configured timeout when no decision can be made.

A running or finished task cannot be modified by this mechanism. Notes made in the separate operator decision log are for audit only, not AI prompt injection. Changes to completed source require the existing versioned revision workflow.

## 2. Prepare QA and preview requests from dashboard

1. Open **Operator Command Hub**.
2. Select a completed or review-required project and operation:
   - `qa-static`: Python AST, JSON and JS syntax checks; no generated program execution.
   - `qa-fastapi`: explicit import/run smoke of generated FastAPI code inside network-disabled Docker with trusted fixed dependencies; may run pytest.
   - `preview-start`: start generated FastAPI app in a constrained local container for up to 15 minutes; no arbitrary dependencies installed.
   - `preview-stop`: stop that project's preview container.
   - `github-draft`: create a new draft PR, subject to confirmed GitHub ownership, only from a completed project.
3. Click **Queue operator request**. This does not run code or contact GitHub. Request is saved with state `queued`.
4. On the Windows host, in the extracted `WFS_PROJECT` folder:

```powershell
python scripts/operator-runner.py --list
python scripts/operator-runner.py --job JOB_ID
```

Or double-click **`RUN_OPERATOR_JOBS.cmd`** to list requests. Type exactly `RUN <job_id>` to authorize a single request. GitHub publishing then additionally requires `PUBLISH owner/repo` as a separate confirmation.

5. Refresh the Operator Command Hub to inspect results. In preview-start results, open the `http://127.0.0.1:PORT/` link **only on your own machine**. Status `completed` means the Docker command returned successfully; it does not prove the generated app is healthy, and the preview may expire after 15 minutes.

**No blanket background execution**: the host operator must start each job intentionally. A queued request can be cancelled in the dashboard before execution. Running jobs cannot be cancelled from the dashboard; to stop a preview, queue and run `preview-stop` or use Docker Desktop.

## 3. GitHub publishing

Requirements: Windows Git, Python, GitHub CLI `gh`, a valid `gh auth login`, and access to a repository where the operator may push a branch and create a PR. API requests contain only `owner/repo`, not tokens.

- Publisher verifies artifact checksums and delivery state. It refuses modified/missing source and `review_required` output.
- After typed consent, creates a new branch `wfs/<project-id>-<timestamp>`, copies source into `wfs-deliveries/<project-id>/`, pushes and creates a **draft** PR. No auto-merge.
- Read the PR URL from the operator terminal, then review source, CI, licensing and dependencies in GitHub before merging.
- The legacy script `PUBLISH_GITHUB_PR.cmd` remains available for manual dry-runs. It is not called by the backend.

## 4. Sandbox limitations and threat model

- **QA without executing generated code:** isolated Docker `--network none` with read-only source and trusted probes.
- **FastAPI runtime QA:** generated code executes; human opt-in and no-network container required.
- **Local FastAPI preview:** generated application executes with an `--internal` Docker bridge and localhost-only port; this is less isolated than syntax-only QA because it handles local HTTP traffic. It is **not** suitable for confidential credentials or public network access.
- Preview container uses non-root UID 10001, read-only filesystem, project read-only bind mount, ephemeral tmpfs, cap-drop ALL, `no-new-privileges`, CPU/PID/memory limits and 15-minute process exit. No project `.env`, WFS database, API key or Docker socket is mounted.
- Docker Desktop's internal-network behavior and published localhost port must be validated on the target Windows host. A controlled container cannot be treated as a complete security boundary against malicious code or runtime escapes. Do not run software from untrusted third parties without a stronger dedicated VM/host and security review.
- Dependency installation from arbitrary generated requirements is intentionally **not performed**. Only fixed trusted FastAPI/Uvicorn dependencies supplied by `docker/qa-python.Dockerfile` are available. Generated projects requiring external services, a database, or custom libraries may fail; this is a known design limit, not a simulated success.
- Operator jobs remain `running` if the host operator process crashes. Review Docker state, logs and database before manual cleanup; do not blindly rerun remote publishing.

## 5. Upgrade / operational safety

Use **one local administrator**; do not forward port 8080 to a LAN or public internet. Back up `.env` and `data/` before upgrading. Never share `.env` or generated secrets. Code produced by AI requires separate dependency vulnerability scanning, unit/integration tests, security review, and Windows Docker acceptance testing.

## v1.7 addendum

Use **Timeline & result** to inspect durable host stages. **Requeue with new approval** creates a new queued request only after a failed/rejected attempt and never executes it. `react-build` routes React/Vite preview builds to the explicit Windows PowerShell/Docker command; both `RUN <job_id>` and `BUILD` confirmations are required. For details see `OPERATOR_OPERATIONS_V17.md`.
