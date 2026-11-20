# WFS PROJECT v4.9 acceptance

| Gate | Evidence | Result |
|---|---|---|
| v4.8 baseline | Published ZIP checksum and all 1,093 paths verified | PASS_LOCAL |
| Unix transport | AF_UNIX EPERM, two-API exit 77, eight focused passes and nine skips | BLOCKED_RUNTIME |
| Replica rejoin | 17 lease IDs retained. Strict admission rejected without standby. New lease visible on enrolled read-only standby | PASS_SINGLE_HOST_LAB |
| Quota scale | 1,200 attempts, 24 allowed, 1,176 denied, zero unavailable | PASS_SINGLE_HOST_LAB |
| Offline restore | 20 focused tests. Pinned intact clone accepted. Missing, mixed, and reference-byte mismatch distinguished in redacted JSON | PASS_LOCAL_LAB |
| UI, HTTP and workers | 303 distinct pytest passes. 13 menus at three widths. 3 workers, 9 projects, 45 artifacts | PASS_LOCAL_DEMO |
| Independent PostgreSQL | No approved nodes or distributed fence | BLOCKED_EXTERNAL |
| Windows Docker Desktop | No PowerShell/Windows restore, startup, hardware, NVDA, zoom or MFA recovery evidence | BLOCKED_EXTERNAL |
| Rootless Docker, TLS/CRL and provider | No approved independent infrastructure or scope | BLOCKED_EXTERNAL |
| Production | Independent gates remain open | DENIED |
