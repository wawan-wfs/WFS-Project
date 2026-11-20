# WFS PROJECT v3.9 — Lease-fenced artifact publication and specialist cancellation

**Classification: PASS_LOCAL_TEST only.** Does not prove an independent runner, exactly-once LLM billing, or a crash-consistent distributed filesystem.

## Threat and correction

In v3.8 `validation.deliver(...)` replaced the visible delivery directory, and `store.save_artifacts(...)` then replaced SQLite manifests **without checking worker ownership**. A worker that lost its lease could therefore overwrite a successor's files or checksums. In v3.9 the AI and demo pipeline invoke `store.publish_artifacts(project_id, files, stack, per_claim_worker_id)` instead.

1. Validate and write candidate files into a random private staging directory. No change to visible project artifacts during this step.
2. Open `BEGIN IMMEDIATE` on the same SQLite database used by `claim()` and `recover_stale()`. Reject absent, canceled or different worker identity (`status` must be `running`).
3. Move the old folder into a unique backup, atomically rename the staged folder to the project delivery path, write all manifest rows, and commit. Claim/recover cannot interleave while the transaction is held.
4. On a recoverable filesystem/SQLite exception, roll back the transaction, remove the new directory if promoted, and restore the backup. After commit, removal of the old backup is best effort.
5. The delivery does not automatically finalize the project; only `store.finish(...worker_id=current_lease)` can do so. An interrupted delivery remains non-delivered and must be rebuilt/verified.

**Honest limitation:** SQLite and filesystem rename are not one crash-atomic transaction. SIGKILL or power loss during renames may leave `.wfs-previous-*` or an unmatched project directory. Project status remains non-delivered; do not serve artifacts until status and digest verification pass. Do not automatically delete such remnants without forensic inspection and operator approval. Do not place the WFS data directory on a shared filesystem without dedicated review.

`pipeline.specialist(... worker_id=...)` also rejects canceled project status and invalid leases after model work returns. A canceled or reclaimed coding task cannot report agent `done` or save an approved specialist checkpoint. This does **not** cancel already transmitted provider requests or guarantee no charge; unresolved charges retain their existing billing controls.

## Regression evidence

- `tests/test_v39_artifact_fencing.py`: stale publish rejection after claim recovery, cancellation, wrong/missing lease, validation failure, injected SQLite insert failure with rollback, cancellation during staging.
- `tests/test_v39_specialist_cancel.py`: cancellation and lease takeover while a specialist call returns, with no done event or task result.
- Legacy v3.8 worker/office/HTTP/parallel tests remain mandatory to detect regression.

No change to project DB schema or HTTP routes. Upgrade by stopping all local workers and previews, backing up `.env`/`data/` separately, replacing source with v3.9, and starting **one** version. Roll back with the matched source + database backup, never concurrent versions on one data directory.
