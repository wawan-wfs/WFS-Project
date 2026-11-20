# WFS PROJECT v4.1.0-rc1

Local release candidate based on the SHA-256 verified v4.0 package. Adds optional scoped SSE admission assertions, cancellation-aware quota release, strict per-claim worker mutation, truthful orphan-agent recovery, atomic approval checkpoints, and artifact sync plus prior-generation retention. No external provider, independent host, or production deployment was used. Production admission remains **DENIED**.

See [acceptance](docs/ACCEPTANCE_MATRIX_V41.md), [migration](docs/MIGRATION_V41.md) and [continuation](docs/NEXT_PROMPT.md).

The authenticated browser smoke also found and fixed a pre-existing MFA cleanup exception that could keep the login form hidden. The browser test now reaches the demo preview and Office through the real API. Organization-mandatory MFA no longer shows a disabled-by-policy action as available.
