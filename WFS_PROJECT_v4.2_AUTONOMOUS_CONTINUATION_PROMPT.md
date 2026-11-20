# WFS PROJECT v4.2+ — Autonomous verification and distributed admission

Continue from the exact published v4.1.0-rc1 source ZIP, verified by distribution SHA-256 and internal manifest. Read AGENTS.md, docs/AUTONOMOUS_STATE.json, docs/ACCEPTANCE_MATRIX_V41.md, docs/SSE_IDENTITY_V41.md, docs/ARTIFACT_RECOVERY_V41.md and all relevant local skills. Keep the 13 menus, 10 divisions, real telemetry, MFA, tenant grants, budgets, licensed original GLBs, and worker leases.

**First executable checkpoint** after extraction, from WFS_PROJECT with requirements-dev installed:

```bash
python scripts/verify-release.py && python -m pytest -q -rs tests/test_v41_sse_identity.py tests/test_v41_worker_recovery.py tests/test_v40_sse_admission.py
```

1. Re-run the actual Linux AF_UNIX assertion and broker tests on an approved host with socket support, independently exercise two API processes, identity-daemon restart, credential rotation, delayed clients and release. Keep scope revocation and fail-closed behavior.
2. Prototype and benchmark atomic lease/replay transactions on PostgreSQL in an approved local disposable environment. Compare datastore restart, rollback and lost acknowledgements before any multi-host claim. Do not enable remote admission without explicit host and PKI approval. Avoid any shared SQLite volume across hosts.
3. Finish artifact recovery evidence with approved hardware or a disposable filesystem lab. Preserve previous generations, test disk-full/fsync/retry and matched restore. Keep provider retry or partial-stream billing unknown until independently reconciled.
4. Run the independent rootless Docker/TLS preview and Windows 10/11 Docker Desktop gates only on approved environments. Obtain Chrome and Edge 600-second stability evidence, native 200% zoom, keyboard, NVDA, test-account MFA recovery and matched restore. Continue safe scripts and checks when external gates are absent.
5. Maintain the baseline UI and truthful telemetry. Re-run the responsive fixture and label any image as fixture or live with exact provenance. Do not substitute visual fixtures for actual Windows/GPU/operator evidence.
6. Run separate grouped regression, authenticated HTTP and multi-process worker tests. Update evidence, acceptance matrix, migration/rollback, checksums and the executable continuation prompt.

Within the current active session, continue through safe unblocked work without routine prompts. On external prerequisites, mark BLOCKED_EXTERNAL and move to the next safe task. Retry transient failures up to twice and record final observed outcomes. Never promise background work. Do not provision, publish, call paid APIs, change production data, or use real secrets without approval. Production admission stays DENIED until independent evidence meets every mandatory gate.
