# WFS PROJECT v4.6 acceptance

| Gate | Evidence | Result |
|---|---|---|
| v4.5 baseline | Published ZIP digest and 946 paths verified | PASS_LOCAL |
| Operator evidence | Six new tests. Per-case output cannot conflate pytest exit 0 with Unix acceptance | PASS_LOCAL |
| Unix transport | Two-API runtime exit 77 (EPERM). Six checks not run. Focused tests 8 passed and 9 skipped | BLOCKED_RUNTIME |
| PostgreSQL replay | Real disposable primary and standby. Acknowledgement withheld under paused replay. Same lease on retry and 17/17 retained. Rebuilt standby read-only | PASS_SINGLE_HOST_LAB |
| PostgreSQL scale | 1,200 requests, 24 admitted, 1,176 denied, zero unavailable in final isolated run | PASS_SINGLE_HOST_LAB |
| Stopped clone | Full expected inventory accepted. Entirely missing or non-delivered expected project rejected | PASS_LOCAL_LAB |
| HTTP, workers, UI | Local HTTP and browser flow. 3 workers, 9 projects and 45 artifacts. All 13 menus at 3 viewport widths | PASS_LOCAL_DEMO |
| Independent PostgreSQL | No approved independent hosts or distributed fence | BLOCKED_EXTERNAL |
| Windows acceptance | No Windows Docker Desktop restore/startup, hardware Chrome/Edge, zoom, NVDA or real MFA recovery test | BLOCKED_EXTERNAL |
| Independent runner, TLS/CRL, provider | No approved independent infrastructure or provider evidence | BLOCKED_EXTERNAL |
| Production | Independent gates still open | **DENIED** |
