# WFS PROJECT v4.3.0-rc1

This local release adds bounded PostgreSQL receipt cleanup, a verified single-host primary/standby experiment, preservation of artifact generations when compensation fails, and a read-only Windows test-clone verifier. The application remains independent from the PostgreSQL quota lab. No Windows, external HA, UDS runtime, or production acceptance is inferred. See [acceptance](docs/ACCEPTANCE_MATRIX_V43.md) and [migration](docs/MIGRATION_V43.md).
