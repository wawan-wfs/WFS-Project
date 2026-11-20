# WFS PROJECT v2.9.0-rc1 — Admission, Uncertain Billing and Offline Audit

**Classification: partial local release candidate, not production ready.** Built on the exact v2.8.0-rc1 source, retaining every existing menu, worker, MFA, tenant, FinOps and office feature. No schema-changing deletions.

Added: per-attempt rootless runner staging operator tools (`scripts/runner-stage-package-v29.py` and `scripts/runner-import-seal-v29.py`); QA strict remote path requires project+attempt namespace; independent read-only provider response-level cost comparator and unique provider-response ID ledger; fail-closed unknown-billing handling, including ambiguous retries; additional adversarial tests; fresh v29 fixture captures, runbooks and acceptance gates.

Proven: 175 pytest tests plus 46 subtests, local HTTP E2E, 3 workers/9 demo projects, 13-screen Chromium fixture and integrity checks. **Not proven:** actual isolated rootless Docker VM, mTLS cert revocation, live provider costs, real TLS dynamic preview, Windows 10/11 GPU/NVDA/MFA, rollback on production data, third-party red team. Do not expose public ports or run unattended generated code.

Upgrade: back up `.env` and `data/` offline together, stop WFS and operator jobs, extract v2.9 to a new directory, copy back only those operator data components. Preserve encryption key `WFS_SESSION_SECRET`. `store.init_db()` adds nullable `provider_response_id` and unique index idempotently; existing AI usage and projects are not deleted. Test project access and MFA recovery on a copy before operating. Roll back using the exact paired v2.8 code+data backup; do not point v2.8 code at a migrated v2.9 database or run simultaneous versions against the same SQLite file.
