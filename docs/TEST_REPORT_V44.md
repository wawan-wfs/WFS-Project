# WFS PROJECT v4.4.0-rc1 — Test report

Baseline v4.3 source SHA-256 `9fb81921949309051dfa1eb16087e2c70c68c26532873834d66bdb6891b1b3bd`, 847 files verified.

| Check | Observed result |
|---|---|
| Primary pytest group | 267 passed, 110 subtests, 28 skipped |
| Visual Office and base group | 19 passed and 8 subtests. 11 base tests already counted above |
| Independent release tests | 8 passed |
| **Deduplicated total** | **283 passed, 118 subtests, 28 skipped** |
| Focused stopped-clone and recovery tests | 13 passed, already counted |
| Focused SSE checks | 8 passed, 9 socket cases skipped, already counted |
| PostgreSQL replica | 17/17 acknowledged lease IDs retained, paused replay withheld acknowledgement, strict retry waited, read-only rebuilt standby |
| PostgreSQL load | 32 clients, 1,200 attempts, 24 allowed, 1,176 quota denials, 0 unavailable, p95 170.92 ms in this run |
| Independent Uvicorn and browser | Passed local demo, no real provider or Docker |
| Parallel workers | 3 workers, 9 demo projects, 45 verified artifacts |
| UI | 13 menus at 1440/820/390, 26 software-rendered fixtures |

The 28 skips comprise 20 Unix-socket tests, 6 root-owned staging tests and 2 nginx tests. The separate UDS harness returned exit 77 with EPERM. The initial lag experiment was stopped when a synchronous commit continued waiting despite statement timeout. The final harness explicitly canceled that disposable backend's wait and verified the warning/fail-closed path before retrying. The Windows wrapper, independent-node failover, real provider, physical storage, hardware, NVDA and TLS gates were not executed. See docs/V44_EVIDENCE and docs/ACCEPTANCE_MATRIX_V44.md. Production admission **DENIED**.
