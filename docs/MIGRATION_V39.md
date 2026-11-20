# v3.8 → v3.9 local Windows/Docker migration and rollback

**No schema migration is introduced in v3.9.** The release is not approved for production or Internet exposure.

1. Stop the application, API, worker instances and running preview processes. Confirm no process is writing `data/`. Do not use old and new code simultaneously against the same SQLite file.
2. Copy the existing **matched** `.env` and `data/` to a secure offline backup, retaining access controls. Do not publish credentials or data in release ZIPs.
3. Verify source ZIP checksum, extract v3.9 into a **new clean directory**, run `python scripts/verify-release.py` and test with a disposable copy of data.
4. Copy `.env` and `data/` from the backup into the extracted v3.9 project for local migration. Start via `START_WFS_PROJECT.cmd`; confirm login, MFA, private project permissions, existing artifacts, queue, project approvals, Finance, office telemetry and restricted preview.
5. Inspect any `.wfs-stage-*` or `.wfs-previous-*` directories after an unexpected process crash. Do not delete them automatically; match against DB status and manifest, then use an operator-approved recovery procedure.
6. For rollback, stop v3.9, restore *the matching v3.8 source and its backed-up database/files* as a unit. Do not point the old source at new active files or reuse stale lease identities.

Actual Windows/Docker Desktop backup/restore drill, MFA authenticator recovery and GPU tests remain `BLOCKED_EXTERNAL` pending operator hardware and authorization.
