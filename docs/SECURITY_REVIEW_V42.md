# v4.2 security review

- The PostgreSQL experiment is a trusted-input test backend only. It does not accept requests through WFS HTTP. Numeric loopback and explicit connection parameters limit the lab target. No production quota backend or new ingress is configured.
- Single-row locking, database time and unique request/nonce/lease identifiers prevent duplicate local allocation in the tested experiment. A retry is safe only for the identical request identity within its time window. Local WAL durability is not replica acknowledgement or HA. Application authorization and event rechecks are unchanged.
- The private Unix transport remains unchanged. A new disposable harness exercises restart/rotation/disconnect on suitable hosts. Runtime EPERM prevented execution of those transport checks here. Do not treat fixture or single-primary evidence as a substitute.
- Artifact rollback holds the write transaction through compensation where possible. An ambiguous commit retains both generations. The offline verifier does not execute artifacts, switch directories or mutate SQLite. It assumes no concurrent filesystem writer. File-level integrity cannot prove an entire backup or physical crash consistency.
- No production or provider operations were performed. No unknown charges were cleared. All external gates remain open.
