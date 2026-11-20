# WFS PROJECT v4.2.0-rc1

Local release candidate. Adds a separately exercised loopback PostgreSQL quota experiment, a two-API Unix authority harness, and safer artifact compensation with an offline exact-match verifier. Preserves the dashboard, MFA, tenant scope, budgets and leased worker behavior. The PostgreSQL experiment is **not wired to the application**. No production or provider configuration was changed.

See [acceptance](docs/ACCEPTANCE_MATRIX_V42.md), [migration](docs/MIGRATION_V42.md), and [next prompt](docs/NEXT_PROMPT.md). Production admission remains **DENIED**.
