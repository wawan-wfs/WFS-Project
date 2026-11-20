# WFS PROJECT v2.7.0-rc1 — Operator QA remote-admission hardening

Incremental from v2.6.0-rc1. Adds optional fail-closed `--strict-remote` mode to QA operator CLI with remote TLS daemon/rootless/digest admission, remote file SHA-256 staging attestation and pre-execution Docker inspect. New regression tests and operator documentation included. **The original local QA remains unchanged for compatibility and is not production certified.** No claims of live rootless host execution, autonomous runner, protected TLS previews, rigged 3D characters, Windows GPU or reconciled provider bills. See `docs/ACCEPTANCE_MATRIX_V27.md`.

Upgrade: stop services; back up matched `.env` and `data/`; extract v2.7 into a new folder and restore only `.env` and `data/`. Database schema unchanged from v2.6. Run pytest, HTTP E2E and local worker checks. Rollback: stop v2.7; restore the matching entire v2.6 folder + its own data and environment backup. Do not run concurrent versions on the same SQLite database.
