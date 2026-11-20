# v3.3 → v3.4 upgrade / rollback (local only)

1. Stop WFS services and preview ingress; preserve source v3.3 ZIP and take **matching offline backups** of `.env` plus `data/` with correct owner, permissions and key material. Do not include secrets in the shared release ZIP. Never mix data between two running version folders.
2. Extract the new ZIP into a new directory. Verify `RELEASE_MANIFEST.json` and `SHA256SUMS.txt` with `python scripts/verify-release.py`. Review source changes and license inventory.
3. On a *cloned* trusted SQLite database, run `python -c "from app import store; store.init_db()"` with the cloned WFS data directory configured and verify `preview_authority_nonces(nonce,used_at)` exists. Back up before authorizing any migration on the user's actual database. Migration is additive/idempotent, not a data wipe.
4. Smoke-test existing project grants, MFA, queue, approved preview, FinOps, login/logout, 13 menus, HTTP and parallel E2E. Keep public preview disabled until real TLS/host/certificate revocation tests.
5. Windows acceptance tool `powershell -ExecutionPolicy Bypass -File scripts/ACCEPTANCE_V34_WINDOWS.ps1` is non-destructive preflight. Browser acceptance requires explicit `-RunBrowser` and a dedicated local test account, and runs Chrome plus Edge serially with interactive credentials. Do not execute production migration or MFA recovery on live user data.
6. For rollback disable any ingress, revoke sessions/tickets, stop v3.4, and restore original v3.3 code **and the matched pre-upgrade database+key backup**. Re-run local tests. Never downgrade an independent gateway to a version requiring a database copy.

Host/rootless Docker, official provider reconciliation, TLS and Windows GPU acceptance remain independent operator tasks; the scripts are **not** evidence that these tasks were executed.
