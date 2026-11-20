# v4.1 Windows 10/11 acceptance checklist

**Not executed on Windows for this release.** Use an isolated approved workstation with Windows Docker Desktop, a clean v4.1 extraction and a dedicated test account. Do not reuse production credentials, projects or backups.

1. Verify the source manifest and use the existing Windows launcher. Run `VERIFY_WFS_PROJECT.cmd` and keep the redacted Docker/health results.
2. Run `python scripts/acceptance_v25_windows.py` separately with `WFS_E2E_CHANNEL=chrome` and `WFS_E2E_CHANNEL=msedge`, `WFS_E2E_STABILITY_SECONDS=600`, and the local instance URL. Use the interactive credential prompt. Retain 13-menu desktop/tablet/mobile output and independent driver/VRAM observations from Windows Task Manager. WebGL2 alone does not prove hardware acceleration.
3. Independently use native browser zoom at 200%, keyboard only and NVDA. Record focus order, command palette, all menus, dialog return focus, and the HTML equivalent of 3D status. Do not capture secrets or recovery values.
4. On the isolated account, test MFA recovery and verify that used recovery codes and revoked sessions cannot be used again. Record only pass/fail and timestamps.
5. Stop the clone, capture matched source/config/SQLite/artifact backup, restore into a separate test directory, and compare manifest, access and demo smoke. Do not run restore against the only copy of a data directory.
