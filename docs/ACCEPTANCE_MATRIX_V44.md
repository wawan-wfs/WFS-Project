# WFS PROJECT v4.4 — Acceptance

| Gate | Result | Classification |
|---|---|---|
| v4.3 baseline | ZIP digest and 847 manifest entries verified | PASS_LOCAL |
| PostgreSQL lag and retry | Paused replay withheld acknowledgement. Strict retry waited for replay and returned the same lease | PASS_SINGLE_HOST_LAB |
| PostgreSQL stop/promotion/rejoin | 17/17 leases retained. Old directory rejected by the lab. Rebuilt standby read-only | PASS_SINGLE_HOST_LAB |
| PostgreSQL scale | 1,200 attempts, 24 allowed, 1,176 denied, 0 unavailable in measured run | PASS_LOCAL_LAB |
| Unix SSE and broker transport | AF_UNIX EPERM, no TCP substitute | BLOCKED_RUNTIME |
| Offline batch restore verification | Genuine temporary SQLite snapshot and paired artifact directories. Wrong and missing copies rejected | PASS_LOCAL_LAB |
| Windows startup, restore and hardware | PowerShell wrapper and procedures available. No Windows Docker, Chrome/Edge, NVDA or hardware run | BLOCKED_EXTERNAL |
| Application regression | Local HTTP, real browser demo, three workers and responsive fixtures | PASS_LOCAL_DEMO |
| Independent failover, TLS, Docker, provider | No independent infrastructure or authorized real credentials | BLOCKED_EXTERNAL |
| Production | External gates remain open | **DENIED** |
