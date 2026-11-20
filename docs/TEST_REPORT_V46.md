# WFS PROJECT 4.6.0-rc1 local test report

## Regression

- Main group 279 passed, 118 subtests passed and 28 skipped. Visual/system group 19 passed and 8 subtests passed. Release group 8 passed. Subtract 11 repeated system tests for **295 distinct passes, 126 subtests passed, 28 skips**.
- The 28 skips are 20 AF_UNIX cases, six root-owned fixture cases and two nginx checks. The focused Unix suite independently returned eight passes and nine skips. Its result is not added to the count. The collector recorded all 17 expected cases and the six two-API checks that could not run.
- The standalone clone, watchdog contract and collector suite results overlap the main group. The real replica and scale tests are separate from pytest.

## Runtime and baseline comparison

- The v4.5 ZIP and all 946 baseline paths matched. No app static assets changed. The 13 menus passed the 1440/820/390 responsive sweep. Chromium Headless Shell 153 exercised the local demo through login, queue controls, worker, preview, audit, collaboration and office.
- HTTP ran against an independent local API process. Three independent local workers completed nine demo projects and produced 45 validated artifacts. No paid provider or Docker execution.
- PostgreSQL 16.2 on one host retained 17 of 17 acknowledged leases. The same request returned the original lease after replay. The replacement standby rejected writes. Two initially concurrent lab runs timed out, then replica passed in isolation. The fixed-count scale assertion also failed on the unmodified fixture in isolation. With the harness fixture TTL changed from 12 to 300 seconds and the expiry case still explicit, the final isolated 32-client run returned 24 allowed, 1,176 denied and zero unavailable.
- Windows PowerShell, Docker Desktop, hardware Chrome/Edge, native zoom, NVDA and MFA recovery have no execution evidence here. Independent PostgreSQL, rootless Docker, TLS/CRL and provider gates are also open.

## Reproduction

From the source root with application dev and optional PostgreSQL lab dependencies:

```bash
PYTHONPATH=.:tests python -m pytest -q -rs --ignore=tests/test_z_release.py --ignore=tests/test_visual_office.py
PYTHONPATH=.:tests python -m pytest -q tests/test_system.py tests/test_visual_office.py
PYTHONPATH=.:tests python -m pytest -q tests/test_z_release.py
python scripts/run-operator-evidence-v46.py --output evidence-linux.json
PYTHONPATH=. python scripts/postgres-replica-lab.py
PYTHONPATH=. python scripts/postgres-quota-lab.py
python scripts/browser-local-e2e.py
WFS_RESPONSIVE_AUDIT_ONLY=1 python scripts/browser-ui-fixture-smoke.py
WFS_V46_CAPTURE=1 python scripts/browser-ui-fixture-smoke.py
```

Set WFS_CHROMIUM_EXECUTABLE if Playwright's default browser is unavailable. See docs/V46_EVIDENCE for local observations. Run the lab commands serially. Do not substitute TCP for the Unix-socket tests.
