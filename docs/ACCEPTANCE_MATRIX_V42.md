# WFS PROJECT v4.2 — Acceptance matrix

| Gate | Result | Classification |
|---|---|---|
| Baseline | v4.1 distribution SHA-256 and 734 baseline files verified | PASS_LOCAL |
| PostgreSQL experiment | Actual 16.2 loopback primary, restart/crash recovery, rollback, discarded acknowledgement, expiry, bounded lock wait, session/tenant/global caps | PASS_LOCAL_LAB |
| Local Unix socket with separate API processes | Reproducible harness added. Runtime returned EPERM before socket creation | BLOCKED_RUNTIME |
| Artifact compensation and matched restore | Injected ENOSPC/EIO, successful retry, both generations retained on ambiguous commit, real restored clone and mismatch rejection | PASS_LOCAL_LAB |
| App integration | Browser and HTTP demo, 3 workers, 9 projects, 45 verified artifacts | PASS_LOCAL_DEMO |
| Dashboard | 13 menus at 1440/820/390, 26 labelled screenshots on Linux SwiftShader | PASS_FIXTURE |
| Production PostgreSQL/HA and cross-host identity | Prototype not integrated with HTTP. No separate hosts, TLS, failover or quorum evidence | BLOCKED_EXTERNAL |
| Independent rootless Docker, real TLS preview/CRL | No approved independent hosts | BLOCKED_EXTERNAL |
| Official provider usage, invoice and hard caps | No paid calls or account access. No clearing of unknown billing | BLOCKED_EXTERNAL |
| Windows GPU, native zoom/NVDA, recovery and restore | Read-only preflight prepared, actual Windows acceptance not run | BLOCKED_EXTERNAL |
| Physical power-loss | Process crashes and fault injection only | BLOCKED_EXTERNAL |
| Production admission | Required real-host gates are open | **DENIED** |
