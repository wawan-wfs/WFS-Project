# v4.1.0-rc1 to v4.2.0-rc1

No WFS application database schema or SSE protocol changes are required. PostgreSQL is optional and used only by the separate lab. Do not point the app at the lab or share its SQLite file across hosts.

1. Stop the API and workers. Keep a matched backup of the source, configuration, SQLite and project data. Keep any separate SSE ledger and settings separately.
2. Verify the archive SHA-256, extract into a new directory and run `python scripts/verify-release.py`. Restore only the matching data and configuration into an isolated clone first.
3. Run the app with its previous SSE settings and confirm the demo flow. Use the new read-only artifact verifier for matching a restored directory and snapshot. Do not delete retained generations while investigating.
4. To roll back, stop v4.2 and restore the matched v4.1 source/data/configuration together. The PostgreSQL lab has no effect on the WFS DB. Windows Docker, GPU, NVDA and MFA recovery still need separate hardware validation.
