# WFS PROJECT v4.3 — Acceptance

| Gate | Result | Classification |
|---|---|---|
| Baseline | Exact v4.2 ZIP digest and 793 internal hashes matched | PASS_LOCAL |
| PostgreSQL capacity and cleanup | 1,200 attempts, 32 clients, 24 admitted, 1,176 denied. Bounded cleanup of 10,000 expired rows | PASS_LOCAL_LAB |
| Primary/standby failover | PostgreSQL 16.2, 16/16 acknowledged lease IDs preserved after explicit stop and promotion, no write admitted under strict mode when standby absent | PASS_SINGLE_HOST_LAB |
| Two-API Unix transport and broker | AF_UNIX creation returned EPERM. No TCP substitute used. Session revocation case added to the harness | BLOCKED_RUNTIME |
| Persistent artifact compensation | Three new injected I/O cases, preserved generations and prior SQLite manifest | PASS_LOCAL_FAULT_INJECTION |
| Application regressions | HTTP, browser demo, 3 workers, 9 demo projects, 45 artifacts | PASS_LOCAL_DEMO |
| UI | 13 menus at 1440/820/390, 26 screenshots with visible fixture labels | PASS_FIXTURE |
| Windows | Preflight and stopped-clone verifier included. Windows Docker, hardware GPU, native zoom, NVDA, MFA recovery and restore not run | BLOCKED_EXTERNAL |
| Production HA and identity | No independent hosts, network-partition fence, quorum or WFS API integration | BLOCKED_EXTERNAL |
| Real rootless Docker, TLS/CRL, provider evidence | No approved external infrastructure or credentials used | BLOCKED_EXTERNAL |
| Physical storage failure | Fault injection and process restart only | BLOCKED_EXTERNAL |
| Production admission | Independent acceptance requirements still open | **DENIED** |
