# WFS PROJECT v3.2.0-rc1 — Dynamic authority segregation (local RC)

Continues the exact v3.1.0-rc1 source package. No existing menu, telemetry, financial ledger, MFA format, project/data schema, orchestration, worker or GLB asset is replaced. This release adds a dynamic-preview authorization sidecar over private Linux UDS and HMAC-signed short-lived requests, allowing the dynamic-only gateway to operate without reading production SQLite. Includes independent-process tests, negative auth tests and operator docs.

**Production admission remains DENIED.** Actual independent runner, signed images, external TLS wildcard, provider invoice, Windows GPU/NVDA/TOTP and backup/restore trials were not carried out. See `docs/ACCEPTANCE_MATRIX_V32.md`.
