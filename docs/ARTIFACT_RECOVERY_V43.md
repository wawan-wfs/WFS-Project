# Artifact recovery and Windows clone verification v4.3

If filesystem compensation itself fails, publication reports `ArtifactRecoveryRequired` instead of treating the rollback as complete. The original publication error and the compensation error are preserved for local diagnosis. When the staging directory still exists, it is retained along with any prior or rejected generation. SQLite is rolled back when its transaction remains open. A missing or unmatched delivery still fails verification. Existing ambiguous-commit behavior remains unchanged. Do not consider an in-memory exception an on-disk recovery journal.

Tests use temporary SQLite and disposable project directories. Persistent parent directory sync errors, failure of both promotion and restore renames, and failure to move a rejected directory are covered. Verification distinguishes a matching prior generation from a new unmatched candidate, and a later successful retry does not delete those retained paths. These are injected filesystem errors, not a physical storage or power-loss test.

On an approved Windows Docker Desktop test host, run read-only preflight, then restore a matched backup into a **separate stopped clone**. Compare a known delivered project against the restored SQLite snapshot:

```powershell
.\scripts\windows-evidence-preflight.ps1 -OutputJson .\windows-preflight.json
.\scripts\verify-windows-restore-clone.ps1 -CloneRoot 'C:\wfs-test-restore' -ProjectId '<project-id>'
```

The new PowerShell wrapper is not a restore operation. It does not start Docker, overwrite a source folder, or imply that MFA, browser, NVDA or other projects passed. It has not been executed on Windows in this release. Complete those checks independently following `docs/WINDOWS_ACCEPTANCE_V41.md`.
