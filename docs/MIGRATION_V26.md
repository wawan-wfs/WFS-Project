# WFS PROJECT v2.5.0 → v2.6.0-rc1 — Windows 10/11 upgrade and rollback

This release is an **incremental local security candidate**, not a complete v2.6 production implementation. Existing v2.5 code, menus, files and assets remain; database migration is additive. **Default MFA is optional.**

## Upgrade

1. Stop API, workers, operator runner, and all previews. In PowerShell, from the OLD directory: `docker compose down`. Do not run two versions against one SQLite database.
2. Save **both** OLD `.env` and the entire OLD `data/` directory to encrypted offline storage. Verify backups and store the old v2.5 ZIP/folder separately. These may contain private projects, hashes and encrypted TOTP secrets; do not upload them to tickets or source repositories.
3. Extract `WFS_PROJECT_v2.6_TENANT_BOUNDARY_PARTIAL_Windows_Docker.zip` into a **new** folder. Copy only backed-up `.env` and `data/` to the new folder. Do not overwrite new `app/`, `scripts/`, `.agents/`, or `docs/` with old sources. Do not copy caches.
4. Start Docker Desktop with WSL2/Linux containers, then execute `START_WFS_PROJECT.cmd` from the new folder. Database bootstrap is **transactional**; existing users and projects receive `organization_id='default'`. Verify existing private projects, MFA login/recovery, user shares, worker queue, FinOps and project export.
5. To create another organization, **stop WFS services and back up again**, then run `python scripts/org-provision-local.py --id alpha-org --name "Alpha Organization" --username alpha_admin`. Enter two password prompts, then type the exact provisioning confirmation. It is not available over HTTP.
6. To enforce MFA for an organization, verify encrypted backup/restoration and factor recovery, stop services, then run `python scripts/org-policy-local.py --org alpha-org --require-mfa yes`. Unenrolled accounts can log in with password only to complete Authenticator MFA setup (the rest of the app is denied). To revert policy, use `--require-mfa no`. **An MFA reset under an enforced policy still requires immediate re-enrollment.**
7. During offline operations no other API/worker process should be writing the SQLite file. Do not share these administrator tools with untrusted AI-generated projects.

## Validate locally

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/http-e2e.py
python scripts/parallel-e2e.py
python scripts/verify-release.py
```

With browser tooling installed (`pip install playwright` and `python -m playwright install chromium`) the **offline fixture-only** test is `python scripts/browser-ui-fixture-smoke.py`. Actual Windows Chrome + Edge GPU acceptance must be run on YOUR Windows host following `docs/WINDOWS_ACCEPTANCE_V25.md`; no fixture can replace that evidence. Check organization enforcement with two test organizations, separate browsers and cross-tenant denied project IDs before admitting confidential users.

## Rollback

1. Stop all v2.6 services, previews and running worker containers; preserve a forensic copy of v2.6 `data/` if needed.
2. Restore the **matched original v2.5 source directory**, backed-up v2.5 `data/` and corresponding `.env` together. Do not point v2.5 code at the mutated v2.6 database; tenant-specific columns/cost rates and newer policy states would not be fully understood by old code.
3. Restart v2.5 locally, verify login and MFA using the matching old secret, projects, private grants and export. Reapply only vetted data created after migration, manually with an audited migration tool. Do not attempt to downgrade in-place.

Production status remains **blocked** until actual Docker Engine and Windows GPU, isolated runner, authenticated external TLS preview, live provider, recovery and red-team gates pass.
