# WFS PROJECT v3.0.0-rc1 — Runner Admission Proofing (PARTIAL)

Source baseline: WFS PROJECT v2.9.0-rc1, 2026-11-08. Retains all previously working application features. **Not production certified.**

Added strict per-workload FS immutable/SHA staging recheck after container creation, required evidence of `rm`/`inspect`/daemon health after QA, and fail-closed remote acceptance when Docker CLI is unavailable or its cleanup query fails. Added `scripts/acceptance_v30_host.py` for operator collection of *actual* cgroup v2, userns, rootless daemon, ext4 immutable staging and optional host egress observations. Added mocked adversarial regression tests and fixture UI captures.

Not delivered: independently deployed rootless runner, one-time mTLS cert revocation, quota/TTL GC, dynamic TLS preview broker, authentic provider billing exports and daily caps, Windows GPU/MFA/NVDA/rollback validation, rigged avatars. No private host credentials or paid model API requests were used. Refer to `docs/ACCEPTANCE_MATRIX_V30.md`, `docs/SECURITY_REVIEW_V30.md`, and `docs/MIGRATION_V30.md`.
