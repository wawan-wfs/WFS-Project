# v2.9 execution evidence inventory — local only

Evidence recorded 2026-11-08 in the generator environment. Command logs are included separately as `docs/V29_LOGS/*.txt`. Raw secrets, active credentials, host identifiers and private URLs are not included. All tests exercise local source or synthetic fixtures, never an authorized real operator's infrastructure.

| Command | Result |
|---|---|
| `PYTHONPATH=. python -m pytest -q` | 175 passed, 46 subtests passed |
| `python scripts/http-e2e.py` | PASS independent localhost API/worker |
| `python scripts/parallel-e2e.py` | PASS 3 workers, 9 demo projects, 45 artefacts |
| `WFS_V29_CAPTURE=1 WFS_FULL_UI_AUDIT=1 python scripts/browser-ui-fixture-smoke.py` | PASS Chromium fixture; 26 desktop/mobile captures + 820px audit |
| Source v2.8 SQLite → source v2.9 DB init twice, separate backup restore check | PASS local persistence smoke |
| `command -v docker` | unavailable; no live remote runner evidence |
| Real TLS preview, paid provider CSV, Windows GPU, NVDA, MFA recovery, dedicated runner | NOT RUN |

The fresh screenshots in `V29_FIXTURE_SCREENS` and 26-file gallery ZIP are **SYNTHETIC**. Do not use them to claim actual AI work or GPU acceptance.
