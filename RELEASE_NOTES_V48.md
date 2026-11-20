# WFS PROJECT 4.8.0-rc1

- Offline backup inventory can now bind delivered IDs, project statuses and artifact manifests to the expected backup generation. A restored database and files that are consistent with each other but not with the independently kept inventory are rejected.
- The CLI verifies files before recording a new inventory. It refuses invalid, duplicate-key, oversized or clone-local inventory files, and does not overwrite an existing reference.
- Legacy subset and exact-ID modes remain compatible. No database schema migration, UI asset change or change to application authentication, budget or worker policies.
- Local release candidate only. External acceptance gates remain open.
