# WFS PROJECT v4.9.0-rc1 test report

- Verified published v4.8 distribution SHA-256 and all 1,093 source paths. Packaging checked all previous source paths are present and app/static remains byte-identical.
- Main pytest group 287 passed, 120 subtests passed and 28 skipped. Visual/system group 19 passed and 8 subtests passed. Release group 8 passed. Excluding 11 duplicate system tests yields **303 distinct passes, 128 subtests passed and 28 skips**. The 20 focused recovery tests and eight runnable focused SSE checks are already represented.
- The main suite skips consist of 20 AF_UNIX, six root-owned staging and two nginx cases. The Unix runtime probe returned EPERM. The collector recorded two-API exit 77 and nine skips among focused tests. No TCP substitute was used.
- Restoration used stopped disposable SQLite clones and real artifact files. Pinned verification accepted the intact clone, identified one missing delivery in the incomplete clone, and identified one altered generation in the internally consistent mixed clone. A re-encoded but semantically identical inventory did not match the trusted raw SHA-256 and exited before checking any projects. The shareable output contains counts and statuses only. The Windows wrapper and hardware were not run.
- PostgreSQL 16.2 loopback labs ran serially. Replica lab kept 17/17 existing leases, withheld acknowledgement during paused replay, preserved the same lease on strict retry, denied admission before synchronous re-enrolment, and verified a new lease on the read-only replacement. Scale lab had 1,200 attempts with 32 clients, 24 admitted, 1,176 denied and zero unavailable. Same-host evidence only.
- Local HTTP and Chromium Headless Shell 153 demo passed. Three workers completed nine projects with 45 validated artifacts. All 13 menus responsive at 1440/820/390 px. The gallery is labeled software-rendered fixture evidence. No production changes, real credentials or provider request.

## Reproduction

From the verified source root with dev and optional PostgreSQL lab dependencies:

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
WFS_V49_CAPTURE=1 python scripts/browser-ui-fixture-smoke.py
```

Run PostgreSQL commands serially. Set WFS_CHROMIUM_EXECUTABLE if the default Playwright browser is unavailable. See docs/V49_EVIDENCE for checkpoints and docs/OPERATOR_EVIDENCE_V49.md for remaining host owners and proof.
