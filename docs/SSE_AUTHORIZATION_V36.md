# v3.6 — SSE revocation between query and send

`/api/live/events` retrieves up to 100 authorized SQLite events in a batch. A project membership, session or organization MFA policy can change after that DB query but before a queued event is sent. v3.6 now rechecks live account identity, session validity, MFA policy and **each row's project grant** before emitting each event.

For an all-project stream, events from a revoked project are skipped and do not leak their content, while authorized project events continue. A scoped project stream terminates on revoked access. This reduces the query-to-delivery gap but does not provide mathematically atomic permission revocation across an already-sent network frame. Rate/reconnect behavior remains unchanged; fixtures never claim real concurrent multi-tenant browser HAR proof.

Run `PYTHONPATH=. python -m pytest -q tests/test_v36_sse_reauthorization.py`. The four negative tests use a streaming response with controlled access changes; their event payloads are synthetic.
