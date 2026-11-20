# WFS PROJECT v2.9 → v3.0 local candidate upgrade and rollback

This release adds runner checks, acceptance tooling and tests. **There is no database schema migration in v3.0.** Previous v2.9 database schema, password hashes, user data, MFA encryption and provider response ID uniqueness are retained.

1. Stop the WFS API, worker and operator preview jobs. Do not run v2.9 and v3.0 concurrently on the same database or preview ports.
2. Back up the matching **v2.9 source ZIP, `.env` and whole `data/` directory** to a protected offline location before extracting. Preserve `WFS_SESSION_SECRET`, required to decrypt enrolled TOTP secrets. Never put secrets in GitHub issue attachments, CI artifacts or screenshots.
3. Extract v3.0 to a **new folder**, verify `RELEASE_MANIFEST.json` with `python scripts/verify-release.py`, and copy only the trusted previous `.env` and `data/` directory. Never overwrite updated `app/` or `scripts/` with older binaries.
4. Run the local regression suite, `scripts/http-e2e.py` and `scripts/parallel-e2e.py` **against disposable test data** before starting the upgraded application against actual data. Confirm own-org and cross-tenant access, MFA sessions and FinOps unknown-billing warnings on backed-up test data.
5. Roll back by stopping v3.0 and restoring **both** original v2.9 code and the matched pre-upgrade `.env`+`data/` snapshot. Never point two releases at a live SQLite database. Independently verify projects, artifact ID/digests, user grants, MFA enrollment and exports after restoration.

Live Windows backup/restore with existing user data was **not run**. The above is a runbook, not completed hardware evidence.
