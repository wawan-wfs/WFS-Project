# WFS PROJECT v4.5+ — Close independent host gates

Use the published v4.4 source ZIP and verify SHA-256 and internal manifest. Read AGENTS.md, docs/AUTONOMOUS_STATE.json, docs/ACCEPTANCE_MATRIX_V44.md, docs/POSTGRES_REPLICATION_LAB_V44.md and docs/OPERATOR_EVIDENCE_V44.md. Preserve all 13 menus, 10 divisions, truthful telemetry, tenant/MFA/budget policy and leased workers.

On an approved Linux host with AF_UNIX and the dev requirements:

```bash
python scripts/run-operator-evidence-v44.py --output evidence-linux.json --gate manifest --gate uds --gate http --gate workers
PYTHONPATH=.:tests python -m pytest -q -rs tests/test_v40_sse_admission.py tests/test_v38_broker_deadlines.py tests/test_v41_sse_identity.py
```

1. Finish actual two-API Unix and broker evidence, including release, active revocation, timeout, rotation and restart. Never substitute TCP when AF_UNIX is blocked.
2. On independent disposable PostgreSQL hosts, require a real fence before promotion, verify the synchronous retry barrier under lag and failure, and demonstrate old-writer rejection and read-only rejoin. Keep the quota prototype separate from application HTTP. Record synchronous commit waits and acknowledgement ambiguity without assuming physical durability from a local lab.
3. On an approved Windows Docker Desktop clone, run batch exact-match restore verification, independent startup, 600-second Chrome and Edge GPU checks, native zoom, keyboard, NVDA and test-account MFA recovery.
4. If infrastructure is unavailable, mark the relevant gate blocked and continue other safe batches. Re-run regression, browser, workers and checksums, freeze evidence and produce the next runnable handoff. No production change, real credential use or cost without authorization. Production admission remains DENIED until all independent gates pass.
