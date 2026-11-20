# v4.7 operator handoff

Work on isolated disposable systems. The matrix in this release separates a verified local run from the external evidence still needed.

| Owner | Prerequisite and first action | Evidence required |
|---|---|---|
| Linux test operator | Use an approved isolated Linux host with working AF_UNIX. From the verified source root run `python scripts/run-operator-evidence-v46.py --output evidence-linux.json`. | Genuine two-API evidence for cross-process quota, disconnect release, fail-closed outage, key rotation and revocation. All focused transport and restart/broker deadline cases must run. Keep the per-case JSON. Exit 77 or a skip does not pass. No TCP substitute. |
| PostgreSQL test operator | Use approved independent disposable database nodes with a verified fencing mechanism. Use the operator's own approved fence and promotion procedure. Run the local commands in [POSTGRES_REPLICATION_LAB_V47.md](POSTGRES_REPLICATION_LAB_V47.md) separately as a baseline. | Record fence verification before promotion, evidence the old writer cannot commit, synchronous replay and strict retries under lag/loss, read-only rejoin, and a new lease visible on the enrolled standby. Same-host process stop is not a distributed fence. |
| Windows test operator | Use a separate stopped restore clone and an independent inventory recorded with the backup. Run `scripts/windows-evidence-preflight.ps1`, followed by the clone verifier below. | Intact clone must pass. A separate disposable clone missing an expected delivery must fail. Then start the intact clone and collect 600 seconds each on hardware Chrome and Edge, native 200% zoom, keyboard-only navigation, NVDA and test-account MFA recovery. |
| Infrastructure and billing owners | Obtain approved independent rootless Docker/TLS/CRL infrastructure and scope for provider reconciliation. Use the existing operator runbooks after access and scope are available. | Independent runner, TLS and revocation results and authoritative provider evidence. No live deployment or paid execution authorized here. |

## Exact restore inventory

If the independent list represents **every** completed or review-required project at backup time, use the opt-in exact mode. Substitute real IDs from the test inventory for the examples.

```powershell
.\scripts\verify-windows-restore-clone.ps1 -CloneRoot 'C:\wfs-test-restore' -ExpectedProjectIds @('aaaaaaaaaaaaaaaaaaaa','bbbbbbbbbbbbbbbbbbbb') -ExactInventory
```

The same underlying Python command runs on an offline clone from the source root:

```bash
PYTHONPATH=. python scripts/verify-artifact-generation.py --clone-root /path/to/stopped-clone --require-project aaaaaaaaaaaaaaaaaaaa --require-project bbbbbbbbbbbbbbbbbbbb --exact-inventory
```

An empty or duplicate expected list is invalid in exact mode. Missing and additional delivered IDs both fail verification. The default remains subset matching for operators who have only a partial expected list. Exact inventory verifies set membership and checks artifact bytes against the restored manifest. It does not authenticate the independent inventory, restore any files, or prove backup provenance. Do not save cookies, recovery codes, credentials or private URLs with the evidence.
