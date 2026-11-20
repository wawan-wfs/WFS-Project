# WFS PROJECT v3.8 — Unique per-claim worker fencing

**Local verification, no real daemon-crash/restart proof.**

A stable worker daemon ID was previously stored directly as the project lease; if an overlapping old attempt and a newly reclaimed task reused the same daemon ID, the old attempt could finalize the new claim. Every `execute_one` now creates a cryptographically random **per-claim lease identity** and uses it for claim, heartbeat, task checkpoints, completion, and owner checks. The worker instance registry also publishes this per-claim ID while the worker is active, preserving truthful `office_live` and agent directory telemetry. It returns to the stable idle daemon ID after the claim closes; no fake working states are emitted.

`block_outstanding_tasks(pid, worker_id=lease_id)` now performs a **single guarded SQLite UPDATE**, preventing a check-then-update race in which an expired worker could block a replacement worker's tasks. Explicit admin cleanup still uses the legacy trusted `worker_id=None` call. `store.finish(...worker_id=...)` now only finalizes running/cancel-requested projects with a matching lease.

`tests/test_v38_worker_fencing.py` simulates reclaiming an interrupted checkpoint under a second claim **using the same daemon base ID**, asserts that stale heartbeats, task mutation, and finalization are ineffective, and that the new claim succeeds. `tests/test_visual_office.py` confirms existing state truthfulness.

Residual: broader legacy internal store calls that omit `worker_id` are trusted and not reworked here, and artifact publication paths still require a separate end-to-end crash/stale-runner adversarial review. This does not prove exactly-once execution of external model calls; retries can duplicate externally billed calls unless reconciled.

**Rollback:** restore matched v3.7 worker/store files. No schema change. After rollback clear stale per-claim status only through existing recovery controls, not manual SQL changes to production.
