# WFS PROJECT v4.3+ — Close transport and recovery evidence gaps

Continue from the exact v4.2.0-rc1 source ZIP after verifying the distribution digest and internal manifest. Read AGENTS.md, docs/AUTONOMOUS_STATE.json, docs/ACCEPTANCE_MATRIX_V42.md, docs/POSTGRES_QUOTA_LAB_V42.md and docs/ARTIFACT_RECOVERY_V42.md. Preserve the 13 menus, 10 divisions, tenant permissions, MFA, budgets, real telemetry, and claim-fenced worker behavior.

First checkpoint after installing dev requirements on an approved Linux host with AF_UNIX support:

```bash
python scripts/verify-release.py
PYTHONPATH=. python scripts/sse-two-api-lab.py
PYTHONPATH=.:tests python -m pytest -q -rs tests/test_v40_sse_admission.py tests/test_v41_sse_identity.py tests/test_v42_artifact_recovery.py
```

1. Obtain actual UDS evidence from the two-API harness and broker regression. Confirm revocation, restarted authority, rotated credentials, disconnect release, quota fairness, deadlines and explicit unavailable behavior. No TCP substitute for the private Unix test.
2. Keep the PostgreSQL prototype isolated while benchmarking bounded cleanup and larger concurrency. Use an approved disposable replicated cluster to measure acknowledged-write retention through primary failover and to exercise leader fencing before considering integration. Keep current per-event authorization. No production rollout or alternative quota fallback.
3. Verify artifact compensation under persistent filesystem I/O errors and matched restore on Windows Docker Desktop. Retain prior generations for operator review. Add fault cases without deleting real data.
4. Run read-only Windows preflight and then collect separate Chrome/Edge 600-second, hardware VRAM/driver, native zoom 200%, NVDA, MFA recovery and restore evidence on the approved host. Continue safe work if a host is not available. Do not pass a gate from preflight alone.
5. Re-run unit and HTTP/browser/parallel-worker checks, freeze evidence, and issue a versioned ZIP, SHA-256 and the next exact runnable handoff. Continue unblocked batches in the active session without routine prompts, but do not use real secrets, incur costs, deploy, publish or alter production without approval. Keep production admission DENIED until all independent gates pass.
