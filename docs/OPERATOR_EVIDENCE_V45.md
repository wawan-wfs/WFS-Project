# Operator evidence and stopped clone inventory v4.5

## Linux

Use an approved host with Unix-socket support and disposable application data. Install dev dependencies and run from the checksum-verified source root.

```bash
python scripts/run-operator-evidence-v44.py --output evidence-linux.json --gate manifest --gate uds --gate http --gate workers
PYTHONPATH=.:tests python -m pytest -q -rs tests/test_v40_sse_admission.py tests/test_v38_broker_deadlines.py tests/test_v41_sse_identity.py
```

The v4.4 runner is still the supported collector. Exit 77 identifies a blocked runtime, not a transport pass. A successful pytest process can also contain skips. Close the gate only with genuine Unix-socket service evidence and the transport cases executed. Do not use TCP as a substitute.

## Windows restore verification

Save the expected IDs of completed and review-required projects independently at backup time and keep the inventory alongside the snapshot. The check cannot detect a fully missing project whose ID was never supplied. Restore into a separate stopped test clone and keep the original untouched. Replace the sample IDs with the IDs from the independent inventory.

```powershell
.\scripts\windows-evidence-preflight.ps1 -OutputJson .\windows-preflight.json
.\scripts\verify-windows-restore-clone.ps1 -CloneRoot 'C:\wfs-test-restore' -ExpectedProjectIds @('aaaaaaaaaaaaaaaaaaaa','bbbbbbbbbbbbbbbbbbbb')
```

The verifier checks SQLite integrity and all manifest-backed delivered projects. In batch mode, repeated `--require-project` arguments on the underlying Python CLI require those IDs to be present with a delivered state. Incomplete inventory returns `DELIVERED_MISMATCH` and exit 2, with sorted missing IDs. Omit the list only when a scan of the clone's own eligible records is sufficient. The check does not restore, start services, prove snapshot provenance or inspect unrelated data. `-ProjectId` remains available for a single-project check and is mutually exclusive with an expected inventory.

Independently start the Windows clone only after read-only verification, then collect Chrome and Edge GPU traces for 600 seconds each, native 200% zoom, keyboard-only paths, NVDA and test-account MFA recovery. Do not retain cookies, recovery codes or other secrets. The PowerShell wrapper, Windows startup and hardware paths were not executed in this release environment.
