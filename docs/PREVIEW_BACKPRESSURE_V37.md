# v3.7 — Dynamic preview admission and URL sanitization

**Classification: PASS_LOCAL_TEST. NOT proof of real TLS, rootless Docker or trusted inter-host networking.**

Every authorized dynamic preview request passes a process-local broker concurrency gate: maximum **4 simultaneous requests per project** and **32 total per gateway process**. Slots are released after successful transport, exception, or request failure. Overload is signaled as HTTP `503` with `Retry-After: 2` only *after* per-request authority verification; untrusted or unknown project access keeps a generic `404`. No upstream cookie, dashboard token, authorization or CORS headers are forwarded to the AI-generated workload.

`safe_target` now rejects encoded CR, LF or NUL in both the raw path and query, besides its existing traversal, percent re-decoding and encoded-slash protections. Tests use isolated fake workload transports and do **not** open any Internet ingress.

**Residual risks:** caps apply only to the Python process. Cross-process/cluster edge admission, incoming body timeouts, untrusted worker denial-of-service, proper TLS wildcard origin, cert/CRL rotation, and multi-tenant browser proof require real operator infrastructure. Never expose raw preview ports or mount dashboard SQLite into a gateway. Operator must configure strict edge request body and concurrency limits before enabling external preview.

Run `PYTHONPATH=. python -m pytest -q tests/test_v37_broker_backpressure.py tests/test_v31_dynamic_broker.py`.

**Rollback:** restore v3.6 `app/dynamic_broker.py` and `app/preview_gateway.py`; no schema change.
