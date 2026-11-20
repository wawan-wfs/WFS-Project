# WFS PROJECT v3.3.0-rc1 — Opt-in Private mTLS Preview Authority

**Baseline:** exact, verified v3.2.0-rc1 partial source ZIP. **Classification:** partial local release candidate, NOT production-ready.

- Cross-host preview authority client transport supports mandatory operator CA, TLS hostname verification, client certificate/key and existing signed nonce/timestamp requests (`WFS_PREVIEW_AUTHORITY_MODE=mtls`). Keeps local UDS mode.
- Operator server launcher only accepts concrete private/loopback bind IP with TLS client certificate verification. No public bind or plaintext fallback.
- Added real local TLS handshake negative tests, 26 new fixture screenshots, Windows/Docker operator setup, security/migration documentation and a durable **v3.4 → v4.0+ autonomous multi-phase master prompt**.
- Full existing backend/UI/core 3D/worker/FinOps architecture remains intact. No changes to persisted database schema or GLB assets.
- **Not verified:** independent Linux hosts, client certificate revocation policy, rootless Docker negative/egress, authentic public TLS origin, actual provider invoices/hard limits, Windows GPU/NVDA/TOTP/restore or rigged skeletal avatars.

See `TEST_REPORT.md`, `docs/ACCEPTANCE_MATRIX_V33.md`, `docs/MTLS_AUTHORITY_V33.md` and `docs/NEXT_PROMPT.md`.
