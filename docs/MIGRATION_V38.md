# WFS PROJECT v3.7 → v3.8 local-only upgrade/rollback

1. Stop workers, dashboard and any private preview process. Do not use two versions against a shared SQLite file.
2. Back up `.env` and `data/` securely and separately; preserve original session/MFA encryption secret. Do not upload user database, provider keys, or PII with this source ZIP.
3. Extract source v3.8 into a **new** directory; verify SHA-256 file and bundled `RELEASE_MANIFEST.json` with `python scripts/verify-release.py`. Compare expected dependencies and install `h11==0.16.0` in the intended trusted Python environment.
4. Start locally using unchanged Windows launcher. Check login, MFA challenge, private projects, 13 menus, SSE reconnect/429 behavior, QA workflows and (only if already operator-provisioned) dynamic Unix socket preview. Verify worker online telemetry for an active claim.
5. If errors occur, stop all services and restore the **matched** v3.7 source/data backup. No schema migration in v3.8. Do not downgrade in place on shared production data.

The SSE edge config generator is **opt-in, operator-only, no installation**; do not run privileged deployment or expose public ports based solely on these local tests. Real Windows rollback is NOT RUN.
