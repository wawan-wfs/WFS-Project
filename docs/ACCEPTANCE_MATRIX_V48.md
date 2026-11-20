# WFS PROJECT v4.8 acceptance

| Gate | Evidence | Result |
|---|---|---|
| v4.7 baseline | Distribution SHA-256 and 1,045 manifest paths verified | PASS_LOCAL |
| Real Linux Unix transport | AF_UNIX EPERM, two-API exit 77, focused suite 8 passed and 9 skipped | BLOCKED_RUNTIME |
| Replica rejoin and replay | 17 retained lease IDs, one new lease on a read-only synchronously enrolled standby, strict work rejected before enrolment | PASS_SINGLE_HOST_LAB |
| Quota scale | 1,200 attempts, 24 admitted, 1,176 denied, zero unavailable | PASS_SINGLE_HOST_LAB |
| Offline recovery | 17 tests. Intact backup matches. Wrong generation with identical IDs and self-consistent files/DB fails the independent fingerprint check | PASS_LOCAL_LAB |
| HTTP, workers and UI | 300 distinct pytest passes, independent local HTTP process, 3 workers, 9 demo projects, 45 artifacts. 13 menus responsive at 3 widths | PASS_LOCAL_DEMO |
| Independent PostgreSQL | No approved independent nodes or fence evidence | BLOCKED_EXTERNAL |
| Windows Docker Desktop | No approved clone, startup, hardware browser, keyboard, NVDA or MFA recovery evidence | BLOCKED_EXTERNAL |
| Independent rootless Docker, TLS/CRL and provider | No approved external infrastructure or scope | BLOCKED_EXTERNAL |
| Production | Independent gates are still open | DENIED |
