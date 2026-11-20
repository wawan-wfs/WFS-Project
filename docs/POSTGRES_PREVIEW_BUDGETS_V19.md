# WFS PROJECT v1.9 — PostgreSQL preview and FinOps budget operations

## Important scope

This is a **trusted-host local release candidate**, not an internet-facing production service. WFS PROJECT does not run arbitrary generated code in the API or AI worker. All runtime preview actions require operator review and a typed confirmation on the Windows host. Real Docker launch and provider billing must be checked on the target machine.

## FastAPI + PostgreSQL — operator-controlled two-service preview

1. Complete or human-approve a **FastAPI** project. Inspect its verified delivered source and check that it uses the environment variable `DATABASE_URL` or `POSTGRES_URL` for database connections; hardcoded credentials are unsupported.
2. In **Operator Command Hub**, select the FastAPI project and choose **Start FastAPI + ephemeral PostgreSQL**. This creates a queued operator job **only**.
3. On Windows, run `python scripts/operator-runner.py --list`, then `python scripts/operator-runner.py --job <ID>` and type exactly `RUN <ID>` after reviewing the source.
4. The runner builds a **trusted** Python preview image from `docker/preview-stack-fastapi.Dockerfile` with FastAPI, Uvicorn, SQLAlchemy and psycopg. It creates a project-specific private Docker bridge, PostgreSQL 16 with a random ephemeral password, and a bounded FastAPI container. It validates the PG readiness check and confirms the backend loopback TCP port is listening. Only FastAPI publishes a `127.0.0.1:<random>` host port; PostgreSQL never publishes a host port. Backend project source is read-only; runtime root filesystem is read-only; process runs as nonroot with CPU/memory/PID/capability limits.
5. View the recorded localhost URL in the Operator Job Timeline. The generated app may still fail specific endpoints or data migrations; TCP readiness confirms **only** that it is listening.
6. To stop the entire preview and **erase its temporary PostgreSQL volume**, queue `preview-stack-stop` and run its ID on the host with fresh confirmation. This does not modify the delivered source.

**Critical lifecycle note:** FastAPI uses a trusted 15-minute alarm. The DB remains available on its isolated Docker network until explicitly stopped; the runner marks both containers with an expiry label. Use the Windows `CLEANUP_EXPIRED_PREVIEWS.cmd` command or `python scripts/operator-runner.py --cleanup-expired` to remove stale project preview containers/networks/volumes once the 15-minute TTL has elapsed. For unattended host cleanup, schedule the command in Windows Task Scheduler under a trusted operator account. **The API does not automatically access Docker.** Preview database data is disposable; never copy real production datasets or secrets into it.

### Backend connection example

The operator-controlled preview supplies `DATABASE_URL=postgresql+psycopg://...` for SQLAlchemy and `POSTGRES_URL=postgresql://...` for native psycopg. The credentials are generated for the preview, not stored in WFS source or the UI. Source code should not print the environment or the credentials.

```python
import os
from fastapi import FastAPI
from sqlalchemy import create_engine, text

app = FastAPI()
engine = create_engine(os.environ['DATABASE_URL'], pool_pre_ping=True)

@app.get('/health')
def health():
    with engine.connect() as c:
        return {'database': c.execute(text('SELECT 1')).scalar_one() == 1}
```

This is a connection example, not a full migrated database application. Do not rely on arbitrary `pip install`; generated dependencies outside the fixed image will not be installed. Database migrations must be explicitly implemented by your application and reviewed.

## FinOps project soft budgets

- Enter operator-defined per-model rates first, then choose a **specific project** and save `limit_usd` and warning percentage (10–99%) under AI Cost Center.
- `0` disables the per-project limit. Changes are authenticated, CSRF-protected and recorded as project audit events. Warning and exceeded events are de-duplicated; changing the limit resets alert thresholds for future calls.
- During new provider calls, the engine rejects a project if the new model rate is missing, previous project usage is unpriced, or the recorded estimate has reached its limit. The older global `WFS_MAX_ESTIMATED_COST_USD` option still works separately.
- **Not a billing guarantee:** concurrent provider calls, retries not represented by usage, requests already started, taxes, discounts, caching and reported-token rounding can exceed the estimate. Keep external provider spending limits and alerts configured.

## CSV audit export

- Open AI Cost Center, set time period and optional project filter, then choose **Export detailed usage CSV**.
- Includes timestamp, project, agent, model, reported input/output tokens, local estimate and saved input/output rate snapshots. Historical rates are not recalculated. Old rows whose rates were unknown have blank snapshots.
- At most 30,000 latest matching usage records are exported. Response header `X-WFS-Report-Truncated: true` and a CSV comment warn if the export is truncated. Spreadsheet formula injection defenses apply to text fields. Requires administrator session; no API key is returned.

## Host operator validation checklist

- [ ] Docker Desktop and Linux containers running on target Windows 10/11
- [ ] Verify source files before enabling untrusted code execution
- [ ] Start a FastAPI demo that actually opens a PG connection
- [ ] Confirm PostgreSQL has **no host-published port** and backend binds only 127.0.0.1
- [ ] Verify 15-minute backend TTL and run cleanup for stale DB
- [ ] Stop and confirm containers, network and temporary volume are removed
- [ ] Set rates and budget, test warning/exceeded events with low-cost provider account
- [ ] Export CSV; verify historic rates and provider invoice reconciliation independently
- [ ] Perform restore drill, supply-chain scan and security review before external deployment
