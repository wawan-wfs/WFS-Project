# v3.7 — Bounded SSE subscription admission and replay

**Classification: PASS_LOCAL_TEST; NOT production ingress certification.**

`/api/live/events` now enforces a process-local cap of **2 simultaneous streams per authenticated session**, **64 streams per API process**, and a maximum of **250 delivered events per connection**. Oversubscribed sessions receive HTTP `429` with `Retry-After: 3` *before* streaming begins. Token keys are SHA-256 digests, not raw bearer cookies. The server releases capacity in the streaming generator `finally` on normal end, disconnect/cancellation, and a raised database error. `Last-Event-ID`/`after_id` remains the sole source of reconnect continuity; no fake synthetic agent event is emitted. All per-event revocation and MFA checks from v3.6 remain active.

**Load caveats:** limits are per process, NOT shared across Uvicorn replicas or a distributed edge; reverse proxies need complementary per-identity connection/rate limits. A response constructed but never actually streamed by nonstandard ASGI middleware could retain its slot; standard ASGI streaming must enter and close the generator. A client cannot rely on exact delivery at network disconnect; consumer must treat event IDs as idempotent. The 250-event ceiling bounds a single client connection, not aggregate volume. Real multi-tenant HAR / host load acceptance is still required.

Run `PYTHONPATH=. python -m pytest -q tests/test_v37_sse_backpressure.py tests/test_v36_sse_reauthorization.py` for authentication and pagination tests. Browser fixtures are not live host acceptance.

**Rollback:** restore v3.6 `app/main.py`, remove `app/sse_limits.py`, and restart application workers; no database migration is involved. Do not share a running database between two different code versions.
