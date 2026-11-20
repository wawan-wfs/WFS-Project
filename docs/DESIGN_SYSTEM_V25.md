# WFS PROJECT v2.5 — Secure Spatial UI design notes

Builds on v2.4. The **same thirteen routes** and ten divisions are preserved; no menu has been replaced with a static mockup.

- Own-account **Authenticator MFA** is located in Team & Access, below project membership. This is a real browser UI wired to authenticated/CSRF-protected backend endpoints. Its empty and enabled states include text as well as color cues. The setup secret and the eight recovery codes are shown once and cleared from DOM on logout / session loss; they must never be captured in screenshots or stored in localStorage.
- The login screen exposes a second-factor control only after the server confirms that the password was valid and the account needs a second factor. The form supports 6-digit TOTP or WFS-prefixed recovery code.
- v2.5 Spatial Office can display up to three *simultaneous* verified workers as avatar instances in one room. Room labels continue to report the complete live worker count beyond the scene cap. There is no simulated typing or movement on an idle workstation.
- The WebGL2 renderer now exports **optional EXT_disjoint_timer_query_webgl2 measurements**. The metric is GPU elapsed query time, **not** FPS or VRAM. The fallback reports CPU submission wall time as a separate value, never as GPU performance.
- Existing accessibility: native room buttons, arrow navigation, visible focus, mobile overflow check, 2.5D fallback, reduced-motion, and task inspector are retained. Validation on actual Windows screen readers, accessibility contrast automation, 200% zoom and cross-browser devices remains pending.
- The environment's Chromium fixture yielded a CPU-3D screenshot, not a GPU render. All screenshots under V25_SCREENS are synthetic and explicitly tagged as fixture-only.

## Still unimplemented / open for v2.6

True skeletal 3D character animation and PBR texture mapping/IBL/shadows; production GPU profile, secure cloud preview gateway, separate organizations, MFA mandates on remote access, full penetration testing and real Windows Docker acceptance.
