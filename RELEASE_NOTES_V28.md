# WFS PROJECT v2.8.0-rc1 — Tenant budgets & isolated-origin preview admission

**8 November 2026 — PARTIAL local release candidate, not production.** Continued **directly** from v2.7.0-rc1 strict QA package, preserving all 13 menus, 10 specialist divisions, queue/worker behavior, MFA, RBAC, demo/live separation, original GLBs, AI FinOps and local operator preview. No third-party 3D assets were introduced.

## Added

- Atomic estimated-spend reservations across per-organization, per-workspace and per-project scopes with a new tenant-owned default workspace, idempotent schema migrations, token price snapshots fixed at request admission and settlement using reported actual token counts. Pending reservations count against limits and are released on provider failure. The existing global estimate gate is included. This is an **estimated admission policy, not a guaranteed provider billing ceiling**.
- FinOps organization/workspace scope limit form and API with CSRF, authenticated tenant derivation, role policy and rejection of unrecognized fields. No automatic spend limit is enabled on upgrade.
- Dedicated FastAPI static/React preview gateway with one-time 5-minute grants exchanged for secure short-lived cookies; per-request current session/org/project ACL recheck, revocation and strict sandboxed inline HTML. Requires an independent TLS origin and separately authorized loopback reverse proxy. **Local dynamic Docker previews are not covered.**
- Hardened rootless QA policy: immutable `FS_IOC_GETFLAGS` staging checks and SHA-256 preflight; container user, privileges, resource/swap restrictions, host namespace and socket denial. New offline snapshot packaging, privileged Linux import/sealing helper, and optional real remote Docker negative probe.
- New concurrency, tenant-adversarial, preview grant/session revocation and price snapshot tests. Updated UI fixture and responsive audit.

## What is NOT complete

No Docker daemon was available here; Linux rootless service, actual host immutable staging, host egress policy, per-run mTLS credentials and TTL cleanup on the real engine are **not verified**. No real DNS/TLS proxy for preview has been deployed. No public authenticated dynamic container reverse proxy. No production billing/provider reconciliation, physical Windows Chrome/Edge GPU profiling, NVDA, 200% zoom, true rigged avatars or external pentest. See `docs/ACCEPTANCE_MATRIX_V28.md`.

## Upgrade and rollback

See `docs/MIGRATION_V28.md` for additive SQLite migration, backup requirements, data continuity, isolation service setup, and restore instructions. Preserve encrypted `.env`, original `WFS_SESSION_SECRET` and backed-up database; do not run two versions against one live DB. Verify full ZIP SHA-256 and `python scripts/verify-release.py` before installing. Previous v2.7 remains rollback source until all external acceptance gates are met.
