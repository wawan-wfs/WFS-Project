# WFS PROJECT v4.2.0-rc1 — test report

The published v4.1 ZIP digest `e8f7926e35e74c340e31142e7feb454ca75cd55c6edfcf9dbf2abc3f3e0648be` and all 734 internal manifest entries matched before editing.

| Group | Observed result |
|---|---|
| Primary regression | 261 passed, 110 subtests passed, 28 skipped |
| Visual office with initialized base | 19 passed, 8 subtests passed. 11 base tests already included in primary regression |
| Standalone release gates | 8 passed |
| **Total unique counted passes** | **277 passed, 118 subtests, 28 skipped** |
| Recovery focus | 18 passed, already counted above |
| PostgreSQL 16.2 | Actual single loopback primary, 8 concurrent clients and 120 reservations, 24 admitted, 96 denied. 295.3 requests/s, p95 61.48 ms. Local synchronous WAL, clean and immediate-stop recovery, rollback and retry verified |
| HTTP and browser | Local Uvicorn, login, demo queue, preview, trace, collaboration and Office verified |
| Parallel worker | 3 separate worker processes, 9 demo projects and 45 validated artifacts |
| Responsive | All 13 menus at 1440/820/390px. 26 labelled fixture images |
| Syntax and PNG integrity | Python compilation, app JavaScript syntax and dimensions of all 26 PNGs passed |

The 28 pytest skips were 20 AF_UNIX cases, 6 root-owned staging fixture cases and 2 nginx cases. The two-API Unix harness separately returned 77 and recorded EPERM on socket creation. It was not counted as a pass. The optional GitHub workflow was syntax-checked locally but not published or run on GitHub. The Windows preflight has not been executed on Windows. No external rootless Docker, TLS/CRL, provider billing, Windows GPU/NVDA/MFA/restore, HA or physical power-loss evidence was collected. Production admission is **DENIED**.

Raw evidence is under `docs/V42_EVIDENCE/`.
