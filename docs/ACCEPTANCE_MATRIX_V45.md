# WFS PROJECT v4.5 — Acceptance

| Gate | Observed result | Classification |
|---|---|---|
| Baseline | v4.4 archive SHA-256 and all 899 source hashes verified | PASS_LOCAL |
| PostgreSQL COMMIT | Replay paused, SyncRep observed, 1.2 s watchdog with no operator cancel. Client returned unavailable at 1.215 s despite local commit | PASS_SINGLE_HOST_LAB |
| PostgreSQL retry and rejoin | Same request waited for replay and returned the same lease. 17/17 preserved. Promoted only after stopping old writer, rebuilt standby read-only | PASS_SINGLE_HOST_LAB |
| PostgreSQL scale | 1,200 attempts across 32 clients. 24 admitted, 1,176 denied, 0 unavailable | PASS_SINGLE_HOST_LAB |
| Stopped-clone restore verifier | Complete inventory accepted. Entirely absent expected delivery and undelivered state rejected | PASS_LOCAL_LAB |
| HTTP, worker and UI | Local API, Chromium demo, 3 workers, 9 projects, 45 verified artifacts. 13 routes responsive at 3 widths | PASS_LOCAL_DEMO |
| Unix SSE and broker | AF_UNIX EPERM, exit 77. Focused pytest 8 passed, 9 transport skips | BLOCKED_RUNTIME |
| Windows Docker, restore and hardware | Wrapper prepared, no Windows Docker host, hardware Chrome/Edge, NVDA, zoom or MFA recovery acceptance | BLOCKED_EXTERNAL |
| Independent PostgreSQL, rootless Docker, TLS/CRL and provider | No independent disposable hosts or approved production credentials | BLOCKED_EXTERNAL |
| Production | Independent gates remain open | **DENIED** |
