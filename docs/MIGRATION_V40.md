# WFS PROJECT v4.0 — Safe source upgrade and rollback (Windows 10/11)

1. Stop API, worker and all preview sessions. Back up `.env`, `data/` (SQLite including WAL/SHM **as a matched offline set**), source ZIP, and release checksums privately. Test restores on a **nonproduction clone**. Never share a single writable DB between versions.
2. Verify the downloaded v4.0 source ZIP and `RELEASE_MANIFEST.json`/`SHA256SUMS.txt`; extract into a new folder. Copy only matched `.env` and backed-up `data/` from the previous installation. Do not merge older source modules.
3. Run `python scripts/verify-release.py`, then the documented grouped tests and local smoke. Start with the default local SSE limiter; new shared UDS admission is **OFF by default** and must only be enabled after separately provisioning, securing and testing the local admission service.
4. Existing database schema is unchanged by app v4.0; the separate SSE admission ledger is new and only created when its service is started. `store.session_account` adds a field to the selected result, not the DB schema.
5. Run the read-only artifact check on a backed-up clone first; inspect all non-CLEAN results before changing source/data. Do not auto-restore a surviving backup folder.
6. For rollback: stop both versions, remove v4.0 optional SSE admission variables, stop the optional admission service, restore the **matched v3.9 source+data backup**, and run its verification and smoke test. Keep the v4.0 audit output for investigation; do not manipulate production schemas or delete user data as part of rollback.

No Windows, actual rootless Linux host, actual DNS/TLS production deployment, real MFA recovery or real backup-restore was performed in this runtime.
