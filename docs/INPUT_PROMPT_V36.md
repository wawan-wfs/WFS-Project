# WFS PROJECT — Autonomous continuation from v3.5.0-rc1

Continue from the exact checksum-verified `WFS_PROJECT_v3.5_LOCAL_RUNNER_LIFECYCLE_Windows_Docker.zip`. Read `AGENTS.md`, all `.agents/skills/*/SKILL.md`, `docs/AUTONOMOUS_STATE.json`, `docs/ROOTLESS_GC_V35.md`, `docs/ACCEPTANCE_MATRIX_V35.md`, `docs/SECURITY_REVIEW_V35.md`, `docs/MIGRATION_V35.md`, and `TEST_REPORT.md`. Do not recreate modules, rebrand, substitute screenshots for code, or treat local simulation as real host acceptance. Keep the v3.4 autonomous master prompt active within the current available session.

## Next safe engineering loop

1. P0: test the new GC/quarantine/maintenance-lock flow with an **authorized real independent rootless Docker host**, actual sealed ext4 data, original inspect/firewall/cgroup proof, signed pinned images, per-attempt daemon-side mTLS client identity issuance/revocation, disk quota, resource exhaustion, TTL cleanup and crash recovery. If unavailable, `BLOCKED_EXTERNAL` and continue other safe work. Do not run `--apply` without explicit operator approval.
2. P0: deploy trusted private cross-host Nginx mTLS authority on operator-managed hosts; actual Nginx config verification, SAN/CA/CRL rotation, client allowlist and denial, 2 concurrent tenant previews and per-request revocation, redacted HAR, no public raw ports. Obtain prior approval for DNS/TLS/firewall changes.
3. P0: integrate independently authenticated provider usage and billing with response IDs, partial streams, retries, daily caps, operator reviewed `billing_unknown` clearance; no paid calls or credentials without approval. Offline comparison CSV never becomes authenticated invoice evidence.
4. P1: execute actual Windows Docker Desktop Chrome and Edge GPU 600-second acceptance, NVDA/keyboard/200% zoom 13 pages, MFA recovery, matched data backup/rollback, reduced motion and UI responsiveness. Existing fixture screenshots remain clearly labeled.
5. P1/P2: improve real queue/SSE crash recovery, 13-menu UX and accessibility without false telemetry; add skeletal 3D avatars only when verified licenses and GPU measurements justify. Run unit/security/regression/HTTP/worker tests and capture real logs.
6. Continue automatically to subsequent safe unblocked items in the same active session. Use atomic checkpoints, bounded retries, no invented tools or background promises. Only stop at genuine approval/security/external or tool/session limits; leave exact state and next command.

Release gate remains `DENIED` without actual independent runner, TLS, provider, Windows/NVDA/MFA/GPU, restoration and negative test artifacts. Each checkpoint must include source ZIP + SHA256, explicit evidence provenance, migrations, security delta, state and a bounded next prompt.
