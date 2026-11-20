# v3.5 — Security delta / residual risks

**Improvements:** runner GC is operator-only and read-only by default; enforces exact staging namespace, root-owned directories, special-file/hardlink rejection, bounded inspection, local host socket validation, rootless daemon and **all-container** bind inspection; quarantine-first and cooling-off deletion; admission shared maintenance lock and pause marker. SQLite durable nonce age now indexed, with genuine local concurrent-process profiling. Nginx proxy renderer adds `map_hash_bucket_size 128` after a real local nginx syntax failure was found, reproduced and fixed.

**Open critical gaps:** No independent rootless host evidence, cgroup/egress/kernel isolation, signed/scanned immutable runner images, daemon-side per-attempt mTLS identities and revocation, audited volume/disk quotas, tested crash cleanup, operator-grade PKI/CRL rotation, wildcard preview TLS on user DNS, provider-origin invoices and actual cap controls, or physical Windows GPU/NVDA/MFA backup/restore evidence. Root with permission to unseal can tamper with staging; this tool is NOT an isolation proof.

**Operational condition:** GC `--apply` is a privileged destructive operation, requiring separate human approval, physical runner maintenance, original daemon inspection and review. The marker and operator lock only serialize the trusted importer and GC; they cannot prevent a different Docker client from starting. Never expose the runner or preview publicly on this basis. The gateway remains forbidden from direct production DB, Docker socket or AI-provider secrets. Screenshots remain fixtures, not live telemetry.

**Security status:** `PRODUCTION_ADMISSION=DENIED`. This release must not authorize unattended untrusted code execution or public preview.
