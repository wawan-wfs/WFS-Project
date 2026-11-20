# WFS PROJECT v3.8 — Cancellation-safe dynamic preview transport

**Evidence: LOCAL TEST ONLY. Internet/public deployment: NOT APPROVED.**

Previously the broker used `run_in_threadpool()` for blocking Unix HTTP and waited for `request.stream()` without an absolute upload deadline. Slow-trickle uploads and upstream servers could occupy broker slots for an indeterminate period.

The v3.8 broker uses `asyncio.open_unix_connection`, verified `SO_PEERCRED`, and pinned `h11==0.16.0` HTTP/1.1 framing. The body upload is bounded by **5 seconds** total and **1 MiB**. Connect is bounded to **2 seconds**; the entire upstream exchange is bounded to **8 seconds**, including slow-trickle chunked output and **4 MiB** maximum response. Client cancellation closes the socket and returns the per-project/per-process slot. Operator-configured gateway admission and per-request authority checks are unchanged.

No arbitrary forwarding of dashboard cookies, bearer tokens, X-Forwarded headers, CORS or generated application's Set-Cookie. `safe_target`, socket ownership and UID checks remain required; untrusted preview code does not receive the dashboard DB or Docker socket. Timeouts fail as preview-unavailable according to the existing gateway API; they do not bypass authorization. These deadlines are currently fixed constants in the source and must be tuned based on measured operator-host latency before deployment.

**Reproduce:** `PYTHONPATH=.:tests pytest -q tests/test_v38_broker_deadlines.py tests/test_v31_dynamic_broker.py tests/test_v37_broker_backpressure.py`. Tests include a real local Unix-socket HTTP server, slow-body, slow-chunked-response and canceled-client cases. No real public TLS or remote Docker workload was involved.

**Rollback:** stop gateway, restore matched v3.7 code and dependency list, restart gateway and test private preview. Never roll back against unmatched production data. No database schema change.
