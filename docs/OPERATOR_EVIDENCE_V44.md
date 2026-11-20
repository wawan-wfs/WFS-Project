# Operator evidence v4.4

## Local gates

```bash
python scripts/run-operator-evidence-v44.py --output evidence-local.json
```

Install application dev requirements first. PostgreSQL gates also need the optional lab requirements and binaries. The runner uses disposable local data, never retries against another address, and records a final status for each requested gate. A missing Unix socket returns 77 and does not prevent later checks. A failed or timed out check returns 1 even if another gate was blocked. Use repeated `--gate` to select a subset. No report treats this run as production acceptance. On Linux with AF_UNIX, separately run the focused broker and assertion regression listed in `docs/NEXT_PROMPT.md`.

## Windows test clone

Restore a matched snapshot into a separate stopped Windows Docker Desktop clone and retain the original. Do not run the verification concurrently with API, worker, or restore operations.

```powershell
.\scripts\windows-evidence-preflight.ps1 -OutputJson .\windows-preflight.json
.\scripts\verify-windows-restore-clone.ps1 -CloneRoot 'C:\wfs-test-restore'
```

The default checks SQLite integrity and artifact manifests for all completed and review-required projects, up to 1,000, in one read-only SQLite transaction. It fails on missing delivery directories, wrong hashes, symbolic paths, junctions, no eligible delivery, or the scan limit. Other project states, configuration, external credentials and unmanifested root data are outside this verification. Use `-ProjectId` for the existing single-project mode.

On the approved clone, then independently start the stack and capture separate browser evidence for Chrome and Edge with 600 seconds each, hardware GPU and VRAM, native 200% zoom, keyboard, NVDA and test-account MFA recovery. Do not save secrets, QR codes, cookies or recovery values in evidence. The wrapper is prepared but has not been run on Windows. The Linux demo and snapshot tests do not replace the Windows gates.
