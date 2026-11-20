# WFS PROJECT v3.8.0-rc1 — Evidence-gated acceptance

| Workstream | Evidence | Status |
|---|---|---|
| Verified v3.7 source | exact source SHA-256 `3f0ef0f6505e58fdc801c82187bb9cd5e9c0477d34fe201cf6d5559752f2abd6`; 607 file manifest matches before edit | PASS_LOCAL |
| Preview deadlines/cancellation | `test_v38_broker_deadlines.py`, legacy v31/v37; real local Unix socket | PASS_LOCAL |
| SSE abandonment/cursor/2-tenant isolation | `test_v38_sse_tenant_load.py`, v36/v37 SSE tests | PASS_LOCAL |
| SSE trusted-edge snippets | `test_v38_sse_edge_config.py`, real local `nginx -t`, NOT installed | PASS_LOCAL_SYNTAX |
| Worker per-claim crash fencing | `test_v38_worker_fencing.py`, v20 recovery and office telemetry | PASS_LOCAL |
| Regression tests | `docs/V38_EVIDENCE/pytest_group*.log`, independent exit files | PASS_LOCAL_GROUPED |
| Release-gate regression | `docs/V38_EVIDENCE/release_gate.log`, 8 tests exit0 | PASS_LOCAL |
| HTTP E2E | `docs/V38_EVIDENCE/http_e2e.log` | PASS_LOCAL |
| 3 worker / 9 project E2E | `docs/V38_EVIDENCE/parallel_e2e.log` | PASS_LOCAL |
| Node/Python syntax | `docs/V38_EVIDENCE/syntax.log` | PASS_LOCAL |
| Real independent rootless Docker / firewall / immutable staging / signed images | No authorized Docker host | BLOCKED_EXTERNAL |
| Actual cross-host TLS, per-project preview, HAR concurrency | No approved real DNS/TLS/host | BLOCKED_EXTERNAL |
| Actual provider per-response billing and caps | No authorized provider evidence | BLOCKED_EXTERNAL |
| Windows GPU, NVDA, TOTP recovery, DB restore | No operator Windows host | BLOCKED_EXTERNAL |
| Licensed rigged avatars, measured GPU PBR | No evidence qualifying production addition | NOT_RUN |
| Screenshots | Previously labeled 26 v3.3 fixtures reused (no v3.8 UI changes) | REUSED_FIXTURE |
| Production admission | Independent proof gates remain absent | **DENIED** |

Per-process SSE limits **do not** imply shared-edge per-tenant limits. Test totals are reported as actually completed individual groups, not any timed-out monolithic invocation.
