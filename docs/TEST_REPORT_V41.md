# WFS PROJECT v4.1.0-rc1 — Local test report

Baseline ZIP SHA-256 `75684b6c65dcd431ebefc734674602498ec7f5bc6438624f02144cd4f3685803`, 681 manifest files verified before editing.

| Completed verification | Result |
|---|---|
| Main pytest group | 252 passed, 106 subtests passed, 28 skipped |
| Visual Office group with initialized test environment | 19 passed, 8 subtests. Of these, 11 base tests also ran in the main group |
| Independent release gates | 8 passed |
| **Total without duplicated base tests** | **268 passed, 114 subtests passed, 28 skipped** |
| Focused rerun | 28 passed including MFA, session, SSE and worker recovery tests already counted |
| HTTP E2E | PASS, local independent Uvicorn, real auth, SSE replay, static preview and export |
| Parallel E2E | PASS, 3 workers, 9 demo projects, 45 verified artifacts |
| Browser E2E | PASS, login → mission → pause/priority/resume → worker → preview → trace → note → Office |
| Responsive fixture | PASS, 13 menus at 1440, 820 and 390px. 26 screenshots at desktop/mobile |
| Python / JS syntax | PASS |

The 28 skips comprise 20 Unix-socket tests (including inherited test cases), 6 root-owned staging fixture tests, and 2 Nginx syntax tests. No host verification is inferred from skipped tests. Starlette emitted an AnyIO alias deprecation warning. Initial retries revealed fixture assumptions from v4.0 and a real browser MFA cleanup bug. The focused and final group runs used corrected fixtures or application code. System Chromium could not launch under the AF_UNIX restriction, while Chromium Headless Shell 153 completed the local browser and fixture checks. The local software-rendered gallery and separate authenticated demo E2E do not imply Windows GPU proof.

In [the acceptance matrix](ACCEPTANCE_MATRIX_V41.md), cross-host ingress/datastore HA, independent rootless Docker, external TLS/CRL, authenticated provider billing/hard caps, Windows GPU/NVDA/MFA/restore and physical power-loss remain open. **Production admission DENIED.**
