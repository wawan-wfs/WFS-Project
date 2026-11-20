# WFS PROJECT v3.9 — Acceptance matrix

| Gate | Evidence | Classification |
|---|---|---|
| Exact v3.8 ZIP baseline | ZIP SHA-256 `5d3aeb36b8dcae45f6ec85c00ca52535b7155e2885b0ef4e938db9eb39c4abb0`; 632 SHA256SUMS entries valid | PASS_LOCAL |
| Artifact delivery lease fencing | `tests/test_v39_artifact_fencing.py` incl. injected SQL error, stale lease, cancellation | PASS_LOCAL |
| Parallel specialist cancellation | `tests/test_v39_specialist_cancel.py`; mocked provider, changed lease and cancellation | PASS_LOCAL |
| Grouped regression | `docs/V39_EVIDENCE/pytest_group1..3.log` (124+71+65 passed, 101 subtests), standalone specialist (2), release gate (8) = **270 distinct tests** | PASS_LOCAL |
| HTTP and parallel workers | `docs/V39_EVIDENCE/http_e2e.log`, `parallel_e2e.log`, `.exit` | PASS_LOCAL |
| Independent rootless Docker/mTLS/egress/image scan | No authorized host; no daemon contact | BLOCKED_EXTERNAL |
| Real TLS dynamic preview + two-tenant HAR | No approved DNS/host/PKI | BLOCKED_EXTERNAL |
| Shared-edge per-identity SSE quota | Design only in `docs/SHARED_EDGE_ADMISSION_V39.md`; process-local code unchanged | NOT_IMPLEMENTED |
| Authenticated official provider per-response invoice and caps | No authorized records; no paid calls | BLOCKED_EXTERNAL |
| Real Windows Chrome/Edge/NVDA/MFA recovery/restore | No operator Windows access | BLOCKED_EXTERNAL |
| Licensed skeletal PBR/rigged 3D and GPU proof | Eight original meshes unchanged, hardware proof absent | NOT_RUN |
| 26 screenshots | Reused v3.3 fixture gallery; no v3.9 live captures | REUSED_FIXTURE |
| Production admission | Multiple independent mandatory proofs absent | **DENIED** |

Monolithic pytest PASS is not claimed: grouped processes are logged separately. Even all-green local unit tests are not substitute production host evidence.
