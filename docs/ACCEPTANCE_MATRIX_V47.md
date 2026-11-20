# WFS PROJECT v4.7 acceptance

| Gate | Evidence | Classification |
|---|---|---|
| v4.6 baseline | Published digest and all 998 source manifest paths match | PASS_LOCAL |
| Unix transport | AF_UNIX socket creation EPERM. Two-API exit 77. Focused suite 8 pass and 9 skip | BLOCKED_RUNTIME |
| PostgreSQL replication | Original 17 lease IDs survive promotion. Strict admission rejected before enrolment. One new acknowledged lease visible on synchronously enrolled read-only standby | PASS_SINGLE_HOST_LAB |
| PostgreSQL scale | 1,200 attempts with 32 clients. 24 admitted, 1,176 denied, zero unavailable | PASS_SINGLE_HOST_LAB |
| Stopped restore clone | Exact complete inventory accepted. Missing or extra delivered projects rejected. 14 focused recovery tests passed | PASS_LOCAL_LAB |
| App, workers and browser | 297 distinct tests pass. Local HTTP, 3 workers, 9 demo projects, 45 artifacts, 13 menus at 3 widths | PASS_LOCAL_DEMO |
| Independent PostgreSQL | No approved independent nodes or verified distributed fencing | BLOCKED_EXTERNAL |
| Windows acceptance | No approved Windows Docker Desktop clone, hardware browser, NVDA or test-account MFA recovery evidence | BLOCKED_EXTERNAL |
| Independent rootless Docker, TLS/CRL and provider | No approved external infrastructure and scope | BLOCKED_EXTERNAL |
| Production | External gates open | **DENIED** |
