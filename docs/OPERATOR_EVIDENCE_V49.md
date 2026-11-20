# v4.9 Operator acceptance handoff

| Operator | Blocker in this session | Next action and required evidence |
|---|---|---|
| Linux | AF_UNIX returns EPERM in this runtime | On approved isolated Linux run `python scripts/run-operator-evidence-v46.py --output evidence-linux.json`. Preserve per-case results proving quota, disconnect release, fail-closed outage, key rotation, revocation, restart and broker deadlines. Exit 77 or skips do not pass. No TCP substitute. |
| PostgreSQL | No approved independent nodes or verified distributed fence | On approved disposable nodes use the approved HA runbook. Capture a verified fence before promotion, old-writer refusal, retry under lag/loss, strict refusal prior to synchronous enrolment and new lease replay on the read-only replacement. Run local lab commands serially as a separate track. |
| Windows | No approved Windows clone, PowerShell or browser hardware | Run `scripts/windows-evidence-preflight.ps1`, then the stopped-clone commands below. Preserve separate summaries for intact, missing and mixed restores. Afterward independently start the intact clone and capture hardware Chrome and Edge for 600 seconds each, native 200% zoom, keyboard, NVDA and test-account MFA recovery. |
| Infrastructure and billing | No approved independent rootless Docker, TLS/CRL or provider scope | Follow the existing operator runbooks after access is approved. Keep public preview and paid execution off. |

## Pin the backup reference and share only the summary

Use the v4.8 recording procedure to generate the reference from the verified stopped backup, not from the restored candidate. Before restoring, record the raw SHA-256 of this reference in a separate trusted backup record. Keep both the reference and this record outside the restore tree. On Windows, obtain the hash using `(Get-FileHash -LiteralPath $inventory -Algorithm SHA256).Hash`; on Linux use `sha256sum`. Use the value saved when the backup was recorded, not a hash calculated from a candidate's file during verification.

```powershell
.\scripts\verify-windows-restore-clone.ps1 -CloneRoot 'C:\wfs-test-restore' -InventoryFile 'D:\test-backups\delivery-inventory.json' -InventorySha256 $expectedBackupInventorySha -SummaryOnly
```

```bash
PYTHONPATH=. python scripts/verify-artifact-generation.py --clone-root /path/to/stopped-restore --inventory-file /independent/delivery-inventory.json --inventory-sha256 "$expected_backup_inventory_sha" --summary-only
```

The underlying CLI returns 0 for the intact clone, 2 with `DELIVERED_MISMATCH` for missing or mixed projects, and 2 with `INVENTORY_CHECKSUM_MISMATCH` if the supplied reference differs byte-for-byte from the pin. A pin mismatch is checked before SQLite or artifact verification. Summary output includes counts and a status, not paths, project IDs, filenames, raw hashes or credentials. `artifact_check_failures` counts failed checks against the candidate's own database manifest, while `different_generations` is measured against the independently kept reference. Missing and additional deliveries are counted separately.

A pin detects a reference replacement only while the saved digest is trusted. It is not a signature or proof of backup origin. Do not copy cookies, recovery codes or other secrets into evidence. The Windows wrapper was not executed in this session.
