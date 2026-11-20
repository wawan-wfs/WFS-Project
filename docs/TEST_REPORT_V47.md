# WFS PROJECT 4.7.0-rc1 test report

- The published v4.6 ZIP and its 998 source manifest entries matched. The packaging check preserved all existing source paths and verified app/static hashes were unchanged.
- Main pytest group 281 passed, 120 subtests passed and 28 skipped. Visual/system group 19 passed and 8 subtests passed. Release group 8 passed. The total is **297 distinct passes, 128 subtests passed, and 28 skips** after removing 11 repeated system tests. The 14 focused restore tests and eight runnable focused transport-suite tests overlap the main group and are not counted again.
- The Unix test probe returned EPERM. The operator collector recorded six two-API cases as not run and nine focused transport cases skipped. No substitute transport used. The remaining main-suite skips require root-owned fixtures or nginx.
- PostgreSQL 16.2, real primary and standby on one Linux host. The paused replay result remained unacknowledged after 1.214 seconds with a 1.2-second watchdog. Strict retry reused its lease, and 17 of 17 acknowledged leases survived promotion. Strict admission refused a new reservation before the replacement standby was enrolled. After enrolment, a new lease replayed on the read-only standby and a duplicate returned the same lease. The serial load lab passed with 1,200 requests, 24 admissions, 1,176 quota denials and zero unavailable.
- Recovery checks used stopped disposable SQLite clones and actual artifact directories. The exact inventory passed on an intact clone and rejected an extra delivered project. Previous negative controls for missing deliveries, wrong state and altered artifacts still passed. The Windows wrapper was prepared but not executed.
- Independent local HTTP process passed. Three local workers completed nine demo projects with 45 validated artifacts. Chromium Headless Shell 153 completed the local demo and checked all 13 menus at 1440, 820 and 390 px. The gallery contains 26 labeled software-rendered fixtures. No production deployment or paid provider use.

## Reproduction

From the verified source root with dev requirements and optional PostgreSQL lab requirements:

```bash
python scripts/run-operator-evidence-v46.py --output evidence-linux.json
PYTHONPATH=.:tests python -m pytest -q -rs --ignore=tests/test_z_release.py --ignore=tests/test_visual_office.py
PYTHONPATH=.:tests python -m pytest -q tests/test_system.py tests/test_visual_office.py
PYTHONPATH=.:tests python -m pytest -q tests/test_z_release.py
PYTHONPATH=.:tests python -m pytest -q tests/test_v44_clone_recovery.py tests/test_v42_artifact_recovery.py
PYTHONPATH=. python scripts/postgres-replica-lab.py
PYTHONPATH=. python scripts/postgres-quota-lab.py
python scripts/browser-local-e2e.py
WFS_RESPONSIVE_AUDIT_ONLY=1 python scripts/browser-ui-fixture-smoke.py
WFS_V47_CAPTURE=1 python scripts/browser-ui-fixture-smoke.py
```

Run the PostgreSQL labs serially. Set WFS_CHROMIUM_EXECUTABLE if the default Playwright browser is unavailable. See docs/V47_EVIDENCE for logs and docs/OPERATOR_EVIDENCE_V47.md for external gate owners, commands and required proof.
