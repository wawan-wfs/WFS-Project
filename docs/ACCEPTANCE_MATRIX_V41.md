# WFS PROJECT v4.1 — Acceptance matrix

| Gate | Observation | Classification |
|---|---|---|
| v4.0 baseline | Distribution SHA-256 matched, 681 manifest files verified | PASS_LOCAL |
| Assertion issuer and quota ledger | Real SQLite fixtures, signed scope, one-use admission, live revocation, replay/TTL, tenant fairness and late-cancel cleanup | PASS_LOCAL |
| Real local Unix transport | Runtime returns EPERM on AF_UNIX. Child-process assertion transport test is included for capable hosts | BLOCKED_RUNTIME |
| Agent ownership and task/approval checkpoint | Reclaim/orphan cleanup, rejection of missing or stale claims, transaction rollback and retry idempotency | PASS_LOCAL |
| Artifact crash boundary | Real child process interrupted between directory promotion and SQLite commit. Previous bytes and old manifest retained, mismatch reported | PASS_LOCAL_PROCESS_DEATH |
| End-to-end flows | Independent local HTTP, real browser against Uvicorn, 3 workers/9 demo projects/45 verified artifacts | PASS_LOCAL_DEMO |
| 13-menu UI and gallery | 1440/820/390 checks, 26 newly captured images, fixture MFA, Linux SwiftShader | PASS_FIXTURE |
| Cross-host shared quota and PKI | PostgreSQL/Redis tradeoffs documented. No live datastore or HA bench | BLOCKED_EXTERNAL |
| Independent rootless Docker and TLS/CRL | No independent approved host or ingress | BLOCKED_EXTERNAL |
| Authentic provider billing and hard caps | No authorized credentials, paid requests, or official per-response evidence | BLOCKED_EXTERNAL |
| Windows GPU, NVDA, MFA recovery and matched restore | Checklist included. No Windows hardware execution | BLOCKED_EXTERNAL |
| Production | Mandatory external gates remain open | **DENIED** |
