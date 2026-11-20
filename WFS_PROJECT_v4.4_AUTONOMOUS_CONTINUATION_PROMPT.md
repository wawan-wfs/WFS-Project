# WFS PROJECT v4.4+ — Operator evidence and distributed durability

Continue from the published v4.3 ZIP after SHA-256 and internal manifest verification. Read AGENTS.md, docs/AUTONOMOUS_STATE.json, docs/ACCEPTANCE_MATRIX_V43.md, docs/POSTGRES_REPLICATION_LAB_V43.md, and docs/ARTIFACT_RECOVERY_V43.md. Preserve all 13 menus and 10 divisions, real telemetry, tenant isolation, MFA, budgets, and per-claim worker leases.

Start with the first runnable gate. On approved Linux with AF_UNIX enabled:

```bash
python scripts/verify-release.py
PYTHONPATH=. python scripts/sse-two-api-lab.py
PYTHONPATH=.:tests python -m pytest -q -rs tests/test_v40_sse_admission.py tests/test_v38_broker_deadlines.py tests/test_v41_sse_identity.py
```

1. Collect real Unix socket evidence across two API processes: release after disconnect, active session revocation, rotation, restart, timeout and tenant fairness. If the runtime rejects Unix sockets, record BLOCKED_RUNTIME and do not substitute TCP.
2. Run the primary/standby and scale labs. For independently hosted disposable PostgreSQL, verify acknowledged writes across a fenced primary loss, lag, replica restart, and a deliberately withheld promotion. Prove the old writer cannot rejoin as primary. Never enable WFS API integration or production routing based on single-host evidence.
3. Close the operator recovery gap with an approved Windows 10/11 Docker Desktop clone. Collect exact-match restore, independent startup, Chrome and Edge 600-second hardware validation, native 200% zoom, keyboard, NVDA and test-account MFA recovery. Keep any secrets and recovery values out of logs.
4. Add low-risk evidence improvements as gates permit. Rerun grouped pytest, HTTP, browser, parallel workers and manifest verification. Record exact skips and failure reasons. Package source, checksum, evidence and an executable handoff.
5. Continue other unblocked batches without routine prompts. Do not change production, publish to a repo, use real credentials or incur costs without explicit approval. Keep production admission DENIED until independent acceptance is demonstrated.
