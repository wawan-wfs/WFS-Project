# v4.2 to v4.3

There is no WFS application DB migration. The PostgreSQL lab remains optional and separate. Preserve the existing SQLite, Unix SSE and provider configuration.

1. Stop writers and keep matched source, configuration, SQLite including applicable WAL/SHM, and project artifacts.
2. Verify the new ZIP checksum, extract into a new directory and run `python scripts/verify-release.py`.
3. Restore into a stopped test clone and verify known delivered artifacts with `scripts/verify-artifact-generation.py` or its Windows wrapper. Smoke-test login and demo only after matching the backup.
4. To roll back, stop v4.3 and restore the matching v4.2 source/configuration/data pair. Preserve retained generations for review, not automatic cleanup.
