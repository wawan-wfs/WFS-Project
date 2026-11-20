# WFS PROJECT 4.5.0-rc1 test report

Tested on Linux on 2026-11-14 using Python 3.12, PostgreSQL 16.2, psycopg 3.3.9 with libpq 18, and Chromium Headless Shell 153. The v4.4 ZIP SHA-256 matched the distribution listing and all 899 baseline manifest paths matched. UI source assets are unchanged.

- **286 distinct pytest tests passed, 126 subtests passed, 28 skipped.** Main group 270 passed and 118 subtests. Visual/system group 19 passed and 8 subtests, with 11 repeated system tests excluded from the distinct count. Release group 8 passed. The separate focused UDS group is not added again.
- **28 skips.** 20 unavailable AF_UNIX cases, 6 requiring root-owned staging, and 2 requiring nginx. The focused Unix suite returned 8 passed, 9 skipped and 5 subtests. The two-API socket lab returned 77 with EPERM. No TCP fallback was used.
- **PostgreSQL.** Client watchdog fired after the configured 1.2 s replay wait. Unavailable at 1.215 s without manual cancel, local receipt committed and not on the paused replica. Exact retry waited for replay and reused the lease. Stop-before-promote preserved 17/17 receipts. Rebuilt standby was read-only. In the separate 32-client lab, 1,200 attempts yielded 24 admitted, 1,176 denied and zero unavailable.
- **Restore clone.** Temporary real SQLite and artifact snapshots verified. Tests cover a missing whole delivery, a non-delivered expected project, invalid inventory, altered files and a missing delivery directory. PowerShell not executed.
- **Local application.** Independent uvicorn HTTP demo passed. Three worker processes completed nine independent demo projects, producing 45 verified artifacts. Chromium demo covered login, mission creation, queue hold/priority/resume, preview, audit, collaboration and office. Responsive fixture covered all 13 menus at 1440, 820 and 390 px. The downloadable gallery has 26 labelled fixtures.
- **Not tested.** Windows Docker Desktop launch, actual Windows restore execution, hardware GPU, NVDA, independent PostgreSQL promotion, independent rootless Docker, public TLS/CRL and real provider billing. No production or paid execution.

See `docs/V45_EVIDENCE/` for recorded local outcomes. Reproduce Linux checks using the commands in `docs/OPERATOR_EVIDENCE_V45.md` and `docs/POSTGRES_REPLICATION_LAB_V45.md`.
