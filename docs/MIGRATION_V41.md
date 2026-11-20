# v4.0.0-rc1 to v4.1.0-rc1

1. Stop the API, workers and previews. Keep the old source package and a matched offline copy of `.env`, SQLite (including WAL/SHM if present) and the project files. If shared SSE is enabled, stop that service and back up its separate ledger and config. Never share a live writable DB between versions.
2. Verify the distribution SHA-256 and extract into a new directory. Run `python scripts/verify-release.py`. Restore only the appropriate matched data and configuration to a nonproduction clone first.
3. Startup adds the nullable internal `agent_runs.claim_id` column. Older working runs have no trustworthy claim association and are marked interrupted. Completed run history stays unchanged. No migration is required for the existing quota ledger.
4. Start with the unchanged default process-local SSE limits. The optional Linux assertion daemon is documented in [SSE identity](SSE_IDENTITY_V41.md). Test scoped access and outage handling before use.
5. Check the clone's artifact audit and run HTTP/worker tests. Keep old artifact generations until an operator verifies their provenance and retention requirements.
6. To roll back, stop both application versions and the optional daemon. Restore matched v4.0 source, configuration, data and SSE ledger together. Retain the v4.1 data for inspection. Do not downgrade an active database in place.
