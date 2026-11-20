# WFS PROJECT v3.7.0-rc1 — SSE & preview backpressure

Source baseline: exact v3.6.0-rc1 ZIP (`2c81cd157ea77e88f7b1a81eed6099e7748db0ae0baa22f8f38e5041560e73e9`).

Local reversible enhancements:
- Bounded per-worker SSE admission: max 2 per session, 64 per process, 250 events/connection; 429/Retry-After, per-event revocation unchanged, cursor reconnect maintained.
- Bounded dynamic preview: max 4 concurrent requests per authorized project, 32 per gateway worker; capacity failures 503/Retry-After *after* auth, slot cleanup on failure, encoded CR/LF/NUL rejection.
- New tests for capacity admission, concurrency, rollback on failure, SSE replay and broker sanitation.
- No UI/GLB redesign, schema changes, paid API calls or operator-host action.

Local tests and source manifest are reported in `docs/ACCEPTANCE_MATRIX_V37.md` and `TEST_REPORT.md`. Production admission remains **DENIED**. The prior v3.3 screenshot fixture gallery may be reused only with explicit provenance labels.
