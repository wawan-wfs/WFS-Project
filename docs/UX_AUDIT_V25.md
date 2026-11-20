# WFS v2.5 UI/UX audit

## Automated evidence

- Chromium fixture navigation: 13 routes × desktop 1440px and mobile 390px, plus the tablet 820px no-overflow audit. The renderer fell back to CPU 3D, with local GLB assets.
- v2.5 screenshots: `docs/V25_SCREENS/DESKTOP_*.png`, `MOBILE_*.png`, `*_MFA_PANEL.png` and `LOGIN_2FA_FIXTURE.png`. They represent the actual frontend rendered with synthetic fixtures, **not** real worker execution or authenticated localhost browser acceptance.
- Tested real interactions in backend TestClient for MFA enrollment, code validation, disable/revoke and recovery. Cross-checked profile UI assets through fixture Chromium; real browser E2E against the running API is not certified.
- Existing 13-menu workflows, sidebar, 3D camera/floor selection, operator detail, project controls and private-project checks remain in the regression set.

## Remaining issues

- Desk geometry is still stylized. Multi-avatar instances do not have rigged bones or advanced animation blending; don't call them photorealistic.
- GPU frame profiling on Windows Chrome/Edge, screen reader test, 200% zoom, external design-review usability research, and live provider API must be performed locally before public production.
- Team & Access is long; MFA panel was intentionally added after project access so owner-level account administration remains at the top. Future iterations should add an account/security subtab and progressive disclosure.
