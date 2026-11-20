# WFS PROJECT v4.8.0-rc1 test report

- Verified published v4.7 distribution SHA-256 and every one of its 1,045 manifest paths. The packaging check retained all baseline source paths and preserved app/static byte for byte.
- Main group 284 passed, 28 skipped, 120 subtests passed. Visual/system group 19 passed and 8 subtests passed. Release group 8 passed. Subtracting 11 repeated system tests gives **300 distinct passes, 128 subtests passed, 28 skips**. The focused 17 recovery tests and eight runnable SSE identity/admission cases overlap the primary groups and are not added.
- Runtime socket(AF_UNIX) returned EPERM, so none of the six two-API scenarios ran. Focused transport suite had nine skips. Across the primary pytest groups, 20 skips require AF_UNIX, six root-owned staging fixtures and two nginx. No substitute transport was used.
- The backup inventory passed an intact clone. The new negative control replaced the project artifact and its SQLite manifest hash/length together, preserving the IDs. Exact-ID verification alone passed that clone. Independent fingerprint verification rejected it and identified the mismatched project. Malformed inventories, attempts to write inside the clone and failed backup-byte verification were also rejected. PowerShell was not run.
- The loopback labs ran serially on PostgreSQL 16.2. Seventeen of 17 acknowledged leases survived. The synchronous retry reused its lease, a primary without its replacement refused strict admission, and a new lease was visible on the read-only replacement once enlisted. The 32-client scale run returned 24 admitted, 1,176 quota denials and zero unavailable out of 1,200. Not independent-host evidence.
- HTTP passed against a separate local uvicorn process. Three workers completed nine demo projects with 45 verified artifacts. Chromium Headless Shell 153 completed the local demo and verified 13 menus at 1440, 820 and 390 px. No hardware GPU or Windows evidence is inferred. No production changes, paid provider execution or real credentials.

## Reproduction

With dev dependencies and optional PostgreSQL lab dependencies on a supported host:

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
WFS_V48_CAPTURE=1 python scripts/browser-ui-fixture-smoke.py
```

Run the PostgreSQL scripts serially. Set WFS_CHROMIUM_EXECUTABLE to a compatible installed browser when the default is unavailable. See docs/V48_EVIDENCE for the local checkpoint results and docs/OPERATOR_EVIDENCE_V48.md for blockers and next commands.
