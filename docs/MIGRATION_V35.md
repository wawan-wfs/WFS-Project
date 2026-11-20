# v3.5 Local upgrade / rollback

1. Stop the **local** WFS application and any operator-created previews. Back up `.env` and `data/` together, preserving encryption/session secrets and original source ZIP. Test restore on a clone before changing active data.
2. Extract v3.5 into a **new directory**. Do not merge extracted source into a live v3.4 tree. Preserve the existing `data/` and `.env` only after backup. No existing project ID, quota, MFA factor, token, or billing record is intentionally transformed.
3. On trusted startup, `store.init_db()` additively creates `idx_preview_authority_nonce_age` on `preview_authority_nonces.used_at`. Existing nonce rows remain intact. Execute only on a backed-up trusted SQLite clone first and verify replay/session access. A database failure continues to deny preview authority requests.
4. For preview mTLS, regenerate the **offline** Nginx configuration. `map_hash_bucket_size 128` must appear at HTTP scope. Test `nginx -t` on the operator's actual configuration before any approved reload. Local test-only certificates do not authorize use in production.
5. For rootless runner staging, keep old v3.4 flows stopped until the operator has verified the exact host. `runner_gc_v35.py` defaults to read-only audit. `--apply` and `--purge` require independent approval and the maintenance procedures documented in `docs/ROOTLESS_GC_V35.md`.
6. Rollback: stop services, revoke preview tickets, restore the **matched v3.4 source and data backup** including `.env`. Never point two software versions at the same SQLite database concurrently. Never bypass newer authority replay checks or delete client certificates automatically to make rollback appear successful.

**No real Windows Docker Desktop or independent-host migration/rollback took place here.**
