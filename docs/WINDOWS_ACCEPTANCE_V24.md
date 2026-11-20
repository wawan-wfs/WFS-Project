# WFS PROJECT v2.4 — Windows and GPU acceptance procedure

**Run on a real Windows 10/11 PC with Docker Desktop, Linux containers, GPU drivers and Chrome/Edge installed.** This document contains instructions; its gates have **not** been run on that platform in the delivery environment.

## Safe preparation

1. Back up `.env` and `data/` from v2.3, stop old services and operator previews, and extract v2.4 into a new directory. Preserve the original directory for rollback.
2. From PowerShell confirm `docker version`, `docker compose version`, `docker info`, and `docker compose config --quiet`. Do not expose TCP Docker socket to the HTTP API.
3. Start using `START_WFS_PROJECT.cmd`, then check `docker compose ps` and `docker compose logs --tail=100 api worker`. Verify `http://127.0.0.1:8080/ready` responds and login uses HTTPS before any remote access.
4. Install QA dependencies in an isolated Python environment: `python -m pip install -r requirements-dev.txt playwright`; `python -m playwright install chromium`.
5. Run the source/API acceptance: `python -m pytest -q`, `python scripts/http-e2e.py`, `python scripts/parallel-e2e.py`. Run Docker QA and preview tests only on a dedicated/approved host using the provided operator scripts.

## Authenticated browser and WebGL2 measurement

PowerShell example (do **not** save the password in a file or command history):

```powershell
$env:WFS_E2E_URL = 'http://127.0.0.1:8080'
$env:WFS_E2E_USERNAME = 'admin'
$secure = Read-Host 'WFS password' -AsSecureString
$env:WFS_E2E_PASSWORD = [System.Net.NetworkCredential]::new('', $secure).Password
$env:WFS_E2E_CHANNEL = 'chrome'    # or msedge
python scripts/acceptance_v24_browser.py
Remove-Item Env:WFS_E2E_PASSWORD
```

This procedure creates `data/acceptance/ACCEPTANCE_RESULTS.json` and screenshots for 13 routes at 1440/820/390px. Review browser-specific rendering, JS errors, horizontal overflow, asset count, VRAM externally (OS GPU tools/Chrome task manager), camera motion, and visual PBR material output. The optional Chromium heap measurement is **not** GPU VRAM. `window.WFSOffice3D.metrics().meanFrameSubmitMs` is a draw/submit timing, **not** an authoritative GPU frame render time.

## Mandatory pass/fail evidence

Record Windows version, CPU/GPU model, driver version, browser version, viewport, display scaling, Chrome/Edge mode, 3D frame timing under actual movement, memory use before/after 10 minutes, 2.5D fallback, reduced motion, screen-reader and keyboard usage, private project access tests, multiworker recovery, preview cleanup, network isolation, CSRF and logout. Attach screenshots, logs and failing traces. Mark incomplete measurements **NOT VERIFIED**.

## Rollback

Stop v2.4 containers and previews. Keep the v2.4 directory and its data backup for diagnosis; restore the independent v2.3 application directory plus its original `.env` and `data/` backup, then restart. Never run two versions concurrently against the same SQLite database.
