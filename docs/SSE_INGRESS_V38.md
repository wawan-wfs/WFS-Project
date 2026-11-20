# WFS PROJECT v3.8 — SSE reservation lifecycle and optional ingress limits

**Evidence class: PASS_LOCAL; actual shared-edge deployment BLOCKED_EXTERNAL.**

`app.sse_limits.LeasedStream` wraps the stream iterator to release admission on normal end, exception, client cancellation, `aclose()` **before first iteration**, or garbage collection. This fixes a resource leak in the v3.7 streaming generator's `finally` when custom middleware abandoned a response before ever entering it. It preserves SHA-256 hashed session keys and per-event MFA/org/project revocation checks and monotonic `Last-Event-ID` reconnect cursors.

Two-tenant test creates distinct SQLite organizations, scoped projects, real sessions, separate event records and multiple stalled tabs; confirms 429 within the same session, independent capacity for another tenant and zero cross-tenant event leakage. Not a cluster load benchmark.

An **operator-only** `scripts/render_sse_edge_v38.py --output-dir /absolute/new/folder` renders `http_zones.conf` and `location_sse.conf`, refuses existing targets, and does not install or reload Nginx. It uses `$binary_remote_addr` for per-IP connection/open-request limits, and turns off buffering for a 40-second SSE read window. The Nginx syntax passes `nginx -t` locally on the test harness. These controls are per IP, **not** shared per-account session counters; a tenant behind NAT could be unfairly limited. Production requires approved TLS, trusted source-IP handling, host allowlists, real proxy load/HAR, tenant quota and observable 429s.

**Reproduce:** `PYTHONPATH=.:tests pytest -q tests/test_v38_sse_tenant_load.py tests/test_v38_sse_edge_config.py tests/test_v37_sse_backpressure.py tests/test_v36_sse_reauthorization.py`.

**Rollback:** restore v3.7 `app/main.py`, `app/sse_limits.py` and remove generated uninstalled snippets. No DB migration.
