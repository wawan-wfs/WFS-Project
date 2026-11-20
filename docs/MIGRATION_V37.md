# WFS PROJECT v3.6 → v3.7 local upgrade / rollback

No new columns or database migrations were made. This release modifies SSE/broker request admission behavior only.

1. Stop application processes and private preview proxy; do not run two versions against the same SQLite data.
2. Back up `data/` and `.env` separately to an encrypted, access-restricted location; keep existing session encryption secret unmodified.
3. Verify the new release ZIP and `SHA256SUMS.txt`; extract into a **fresh** directory. Restore only the backed-up user data and `.env`, never overwrite updated source files with older code.
4. Start locally with existing Windows launcher or compose procedure. Check login, 13 menus, queue, a private project, MFA challenge/recovery (on nonproduction account), SSE and authorized preview. Confirm a third concurrent SSE stream for one session receives 429 and the next stream works after releasing a slot. For a provisioned private preview, check 503 only on bounded overload; 404 still hides unauthorized origin.
5. If failing, stop all services and return to a matched v3.6 source and its **matched database backup**. Do not downgrade production data in place.

This guide is an operator procedure; no real Windows restore drill has been performed. Host-level ingress limits are required before public deployment.
