# WFS PROJECT v3.1 local upgrade / rollback

1. Stop all workers, operator previews and gateway sessions. Back up v3.0 code and `data/`/`.env` as a matched pair, store separately and record checksums; **do not include plaintext session or model secrets in support bundles**.
2. Extract v3.1 to a fresh directory, verify `python scripts/verify-release.py`, then migrate by copying only approved `data/` and `.env` from v3.0. No schema change is required, but keep the matched backup for rollback.
3. Run `PYTHONPATH=. python -m pytest -q`, `python scripts/http-e2e.py` and `python scripts/parallel-e2e.py`. Test MFA and project revocation using nonproduction accounts.
4. Dynamic preview is **opt-in/disabled by default**. Only configure `WFS_PREVIEW_DYNAMIC_DOMAIN`, `WFS_PREVIEW_SOCKET_ROOT`, and `WFS_PREVIEW_SOCKET_UID` when an operator has independently built the trusted TLS proxy, private socket ownership, and runtime sandbox in `docs/PREVIEW_BROKER_V31.md`.
5. Actual production acceptance still needs independent Linux Docker, real TLS/HAR, official provider costs/caps and Windows GPU/NVDA/TOTP/restore evidence.
6. Rollback: stop v3.1, restore the matched v3.0 source and database+environment backup, then verify private projects/access, queue and MFA. Do not point v3.0 and v3.1 processes simultaneously at one SQLite file or share token/cookie keys across mismatched releases.
