# WFS PROJECT v4.3.0-rc1 — Test report

Exact published v4.2 baseline SHA-256 `0bd874497d45dab1f70a515ec24c5b643b56038465fc44cc5f984be337436602` and 793 internal files verified. Its VERSION and application metadata were v4.2.0-rc1, but its manifest version field still said v4.1.0-rc1. v4.3 regenerates a consistent manifest.

| Run | Results |
|---|---|
| Main pytest group | 264 passed, 110 subtests, 28 skipped |
| Visual Office group | 19 passed and 8 subtests. 11 base tests were already counted above |
| Release gates | 8 passed |
| **Distinct counted passes** | **280 passed, 118 subtests, 28 skipped** |
| Focused SSE and artifact group | 24 passed, 5 skipped, already counted |
| PostgreSQL scale | 1,200 attempts, 32 clients, 24 admitted, 1,176 quota denials, 0 unavailable. Local p95 361.5 ms |
| PostgreSQL replica | 16 of 16 acknowledged lease IDs retained. Refused promotion while the prior primary ran. Strict mode denied when standby was absent |
| HTTP/browser and workers | Independent Uvicorn and browser demo passed. 3 workers, 9 demo projects, 45 verified artifacts |
| UI and syntax | 13 menus at 1440/820/390. 26 valid fixture PNGs. Python/JS and CI YAML passed syntax checks |

The 28 skips are 20 Unix socket cases, 6 root-owned staging cases, and 2 nginx cases. The two-API Unix harness separately returned exit 77 because AF_UNIX returned EPERM. Neither the real Unix authority nor broker transport was verified. The Windows verifier and updated CI are packaged but not run on those platforms. The PostgreSQL lab used two processes on one machine and did not test independent hosts or automatic leader fencing. The initial 32-client load hit a lock timeout when the reservation path shared the cleanup backlog. The final workload separated bounded cleanup and reported unavailable independently from quota denial. The library runtime emitted an AnyIO compatibility deprecation warning during tests.

See `docs/V43_EVIDENCE/` for raw results and `docs/ACCEPTANCE_MATRIX_V43.md` for blocked gates. Production admission remains **DENIED**.
