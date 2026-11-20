# WFS PROJECT v3.0 — 26 fixture screenshot evidence

**All images here are synthetic browser fixtures, not authenticated live user sessions, Windows GPU runs, paid AI model outputs, or production screenshots.** Captured against the unchanged v3.0 app UI code using local Chromium headless browser and the project's `scripts/browser-ui-fixture-smoke.py` fixture. Source assets and 13 menu routes remain from the v2.9 baseline. `WFS_V30_CAPTURE=1 WFS_FULL_UI_AUDIT=1` produced desktop/mobile frames and checked responsive navigation at 1440, 820 and 390 CSS pixels. 200% native Windows browser zoom and screen-reader behavior were not tested.

Each of the thirteen routes (`overview`, `projects`, `queue`, `office`, `collaboration`, `operator`, `agents`, `quality`, `deliverables`, `activity`, `finops`, `system`, `team`) has one 1440x900 DESKTOP screenshot and one 390x844 MOBILE screenshot. The fixture includes project and user data fabricated solely for UI regression checks. The 3D panel ran with `cpu-3d`, `gpuTimerSupported=false`, and no real hardware GPU timings.

Do not use these images as proof of real live task telemetry or accepted security gates. Independent live Windows Chrome+Edge screenshots are required for production admission.
