# v4.5 PostgreSQL replay acknowledgement

This disposable experiment is loopback only and not reachable from the WFS HTTP application. The application database, authentication, SSE authority and worker leases are unchanged.

Strict mode (`remote_apply`) starts a client watchdog immediately before COMMIT, with a default of 2 seconds and a lab-only permitted range of 0.1 to 10 seconds. If it fires, it attempts nonblocking libpq cancellation and refuses to acknowledge the result. The client also checks monotonic elapsed time and treats PostgreSQL warnings as uncertain outcomes. Strict mode requires a libpq build with nonblocking cancellation (libpq 17 or newer). The ordinary single-primary lab is not subject to this new requirement.

Do not infer rollback from an unavailable result. The primary can flush WAL before the synchronous acknowledgement wait ends. Retry with the exact original request identity while it remains valid. An already committed allowed receipt forces another synchronous WAL barrier, so a successful retry does not allocate a second slot or acknowledge before replay. A cancel request is best effort. This is not a hard end-to-end network timeout and must not be used as one. Keep an outer operator-runner timeout for the disposable test.

```bash
python -m pip install -r requirements-postgres-lab.txt
PYTHONPATH=. python scripts/postgres-replica-lab.py
PYTHONPATH=. python scripts/postgres-quota-lab.py
```

The real single-host harness pauses replay and observes the SyncRep wait. The client rejects the first acknowledgement without an operator-side cancel. The harness confirms the receipt exists on the primary and not on the paused standby. The retry waits until replay resumes and returns the same lease. Seventeen identical receipts are retained across stop-before-promotion and the replacement standby is read-only. The replacement was not enrolled for strict post-promotion writes. No distributed fence, independent-host test, end-to-end network deadline, or production durability claim is made.
