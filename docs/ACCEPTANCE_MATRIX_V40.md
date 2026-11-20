# WFS PROJECT v4.0 — Production acceptance matrix

| Gate | Evidence | Classification |
|---|---|---|
| Exact v3.9 ZIP + manifest baseline | SHA256 `0940494f1c26a71e25634c57329dba10d0d046e6401d91caf61ec72e7ef23d51`, 657 prior files matched | PASS_LOCAL |
| Legacy manifest-only writer shut down | `test_v40_store_fencing`, `store.save_artifacts` fails closed | PASS_LOCAL |
| Worker event/agent/task planning lease fencing | `tests/test_v40_store_fencing.py`; stale lease/cancel and clean E2E | PASS_LOCAL |
| Artifact crash-boundary audit | `tests/test_v40_artifact_audit.py`; read-only backup/stage/mismatch detection | PASS_LOCAL_SIMULATION |
| Local shared SSE authority, quotas, anti-replay | `tests/test_v40_sse_admission.py`, actual child-process Linux UDS, two tenants | PASS_LOCAL |
| Shared edge on **multiple independent hosts** | Service only uses local UDS and local ledger; no external load/cert proofs | NOT_IMPLEMENTED |
| Python regression including release gate | **282 unique tests / 109 subtests** in independent completed processes, logs in `docs/V40_EVIDENCE/` | PASS_LOCAL |
| HTTP+parallel E2E | Independently completed local Uvicorn; 3 workers/9 demo projects/45 validated artifacts | PASS_LOCAL |
| Production Linux rootless Docker, deny-egress and immutable runner | No authorized independent host or daemon contact | BLOCKED_EXTERNAL |
| Production cross-host mTLS TLS/PKI/CRL preview and HAR | No approved infrastructure; no public preview | BLOCKED_EXTERNAL |
| Actual official provider per-response invoice, caps | No credentials/approval/provider calls; billing_unknown preserved | BLOCKED_EXTERNAL |
| Windows Chrome/Edge GPU, NVDA, MFA recovery, matched restore | No physical Windows runner contact | BLOCKED_EXTERNAL |
| Rigged skeletal 3D agents and real GPU evidence | Eight licensed original assets retained unchanged | NOT_IMPLEMENTED |
| 26 screenshots | Existing v3.3 fixture gallery reused; no UI change; no new live captures | REUSED_FIXTURE |
| Final production admission | All mandatory physical evidence absent | **DENIED** |

Monolithic pytest pass is **NOT CLAIMED**. 282 tests are grouped completed runs with no duplicate Visual Office fixture tests counted. Green local tests are not equivalent to host acceptance.
