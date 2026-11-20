# WFS PROJECT v3.7 — Security change review

## Mitigations implemented
- Process-local active SSE admission prevents a single account from opening unlimited subscriptions on one worker. A 250-event reconnection ceiling reduces long-lived hot stream pressure while preserving original monotonic event IDs and per-event authorization.
- Dynamic preview broker caps per-project/global in-flight requests and releases tokens via `finally`, including failed upstream requests. Authorized overload is `503` with a bounded retry hint.
- URL sanitizer rejects encoded request-target CR/LF/NUL in addition to path traversal, ambiguous encoding, unsafe separators and upstream header/cookie forwarding protections.
- Negative tests cover cross-client pressure, replay cursor, 429 / 503, multi-task concurrency, and slot release on exceptions.

## Unresolved security boundaries (production blocking)
- The SSE and broker limiters are **in-process only**. Each process has separate counts. Operator must enforce distributed quota and ingress timeouts at the approved proxy.
- A streaming response that is instantiated but never entered by custom middleware can retain an admission slot; standard ASGI disconnection and close are covered through generator cleanup, not independently certified for every HTTP server.
- These local tests do not validate real host firewall, Docker rootless namespaces, GPU, TLS cert rotation, provider invoice authenticity, quota enforcement across independent application nodes, or Windows MFA recovery.
- Keep remote AI code execution and public preview disabled. No broad production schema changes, credentials, external provider billing or destructive cleanup were performed.

## Reviewer commands
`PYTHONPATH=. python -m pytest -q tests/test_v37_sse_backpressure.py tests/test_v37_broker_backpressure.py tests/test_v36_sse_reauthorization.py tests/test_v31_dynamic_broker.py`

**Production admission:** DENIED.
