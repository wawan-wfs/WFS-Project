# v4.1 Worker claims and artifact recovery

Worker mutators no longer interpret a missing lease as an operator override. Worker and API code use separate entrypoints for fenced runtime events and trusted control-plane audit events. Agent runs carry an internal claim binding that is not returned by run, trace or office APIs. Recovery marks unfinished agent runs interrupted in the same transaction that releases a stale claim. Cancellation and terminal project transitions block old outstanding tasks while holding the write lock. A new claim cannot report success or cancel work from an older claim.

The active pipeline commits task ownership, task approvals, checkpoint and planning handoff together. Manual approval releases the worker in the same transaction. An identical automatic checkpoint retry is a no-op and a changed retry is rejected. This does not make external provider requests exactly once.

The publisher writes exact UTF-8 bytes, fsyncs staged files and syncs directory metadata on POSIX. It retains prior generations under `.wfs-previous-*` after successful replacement. Prior generations are not automatically deleted or restored. This costs disk space on repeated replacement. Windows directory fsync is not claimed. SQLite commit and directory promotion are still distinct durability boundaries. Local tests terminate a child process after promotion before the database commit, confirm the old manifest and previous directory survive, and check the audit reports mismatch.

## Operator recovery

1. Stop the API and worker on an isolated clone or during an authorized maintenance window. Capture matched source, app DB/WAL and artifact directories before making changes.
2. Run `PYTHONPATH=. python scripts/audit-artifact-publication-v40.py --report /private/new-artifact-audit.json` against the clone. Exit 2 requires investigation. The tool does not delete, repair or promote output.
3. Compare manifest hashes to current and previous directories. Use a matched backup or perform a new lease-fenced rebuild after checking billing state. Preserve old generations until reviewed. Do not run an automatic purge or manually mark a damaged project delivered.
