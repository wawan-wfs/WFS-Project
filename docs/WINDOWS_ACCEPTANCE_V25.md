# WFS PROJECT v2.5 — Real Windows / GPU / MFA acceptance

This procedure has **not been executed on an actual Windows 10/11 Docker Desktop GPU** in the release environment. The acceptance script is tooling for YOUR target PC, not substitute evidence.

## Upgrade safely

1. Stop v2.4 API/worker/operator preview containers. Back up **both** `.env` and `data/` to protected offline storage. Store the previous folder separately and do not mix SQLite versions.
2. Extract v2.5 into a NEW folder. Copy only `.env` and `data/` from your backed-up v2.4 install; no older `app/`, `scripts/`, or tests. Keep a second copy for rollback.
3. Confirm Docker Desktop (Linux containers / WSL2), Windows GPU driver, Chrome and Edge. Run `docker version`, `docker compose config --quiet`, then `START_WFS_PROJECT.cmd`.
4. On localhost, sign in. Navigate to Team & Access → Authenticator MFA, enter the current account password, add the displayed Base32 secret to an authenticator, confirm a valid TOTP, and SAVE the eight recovery codes offline. Sign out, sign in with a new valid TOTP. Test one recovery code once only.
5. Do **not** enable MFA until you have verified that encrypted `.env`+SQLite backups can be restored. If an account loses its device and recovery codes, stop services, back up data, and run `python scripts/reset-mfa-local.py --username admin` locally; all sessions will be revoked and the account must re-enroll.

## Real Chrome / Edge 3D acceptance

Install Python Playwright on the Windows testing host: `python -m pip install -r requirements-dev.txt playwright` and `python -m playwright install chromium`. Set browser URL and run *one browser at a time*:

```powershell
$env:WFS_E2E_URL='http://127.0.0.1:8080'
$env:WFS_E2E_CHANNEL='chrome'   # repeat with 'msedge'
$env:WFS_E2E_STABILITY_SECONDS='600'
python scripts/acceptance_v25_windows.py
```

It prompts interactively for password/OTP without saving them. It signs in, checks 13 pages at desktop/tablet/mobile, collects screenshots, performs camera interaction over 10 minutes, collects optional GPU timer-query readings, and logs out. Evidence is written under `data/acceptance-v25/` (which is intentionally excluded from release ZIP). Do not post that folder publicly without reviewing it.

Record manually: Windows version, CPU/GPU model and graphics driver version, browser version, display scale, **actual dedicated/shared VRAM from Windows Task Manager**, CPU/GPU usage, P95 FPS using an external GPU profiler if required, 10-minute tab stability, WFS backup/rollback, 2.5D fallback, reduced motion, 200% zoom and a Windows screen-reader pass. Browser JS `performance.memory` is NOT VRAM. The GPU extension may be unavailable, and optional GPU timer time is not rendered FPS.

## Other acceptance gates

Run `python -m pytest -q`, `python scripts/http-e2e.py`, `python scripts/parallel-e2e.py`, real manual MFA login/logout/recovery with a dedicated test account, private-project revocation and SSE exposure tests, permission denial across roles, Docker QA and preview cleanup. Have an authorized security tester validate host/container isolation and TLS/proxy configuration before exposing outside localhost. A local release cannot be labeled 100% production ready until all gates pass.
