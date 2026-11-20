# WFS PROJECT v2.3 — Spatial Command Design System

**Status:** Implemented in source, tested against browser fixtures. The visual standard is a direction, not a guarantee of production certification.

## Visual system

- A single indigo/navy control-plane palette, WCAG-oriented visible-focus styling, restrained mint for verifiable activity, and gold only as an accent.
- No remote fonts, CSS/JS CDNs, third-party render engines, or asset downloads at runtime.
- Desktop navigation rail / compact topbar / consistent form and panel surfaces. Full-height office stage retains mission context in a separate inspector.
- Hero layout on Mission Control highlights an actual action: **Create a mission**, which focuses the existing form; **Explore 3D studio** navigates to the real office.
- Command palette (`Ctrl+K` or `⌘K`) searches 13 dashboard pages, supports arrow keys and Enter, and never bypasses server authorization. The backend remains responsible for RBAC.
- Form controls preserve semantic labels; loading, empty, and failure states remain owned by the existing page controllers.

## Interactive 3D scope

The office includes (a) a physical three-floor building overview for **navigation only**, (b) floor-specific office geometry with desk layouts, lighting details, glass partitions, (c) original procedural GLB assets, (d) working/resting avatar state tied to authenticated server telemetry, (e) camera orbit, zoom, reset, room focus, quality selector and keyboard controls, and (f) an optional 2.5D fallback.

`app/static/office3d.js` is a dependency-free WebGL2 renderer. It consumes `/api/office/live` indirectly through the existing `studio.js` and only shows `working` motion for `a.live===true` on real telemetry. `DEMO / NOT LIVE` remains explicitly labeled. The building overview does **not** aggregate cross-floor live information, and it is never claimed to do so.

`app/static/office3d-assets.js` parses a deliberate subset of indexed GLB 2.0 with bounds checks. Original, small GLB files are in `app/static/models`, with source generator under `tools/build_original_assets.py` and terms documented at `app/static/models/ASSET_LICENSES.md`. If an asset fails, software/procedural geometry is retained. CPU fallback deliberately does not load high-detail GLB to protect limited devices; this is not a bug.

## Camera / GPU limits

- CPU fallback uses static redraws on demand; it is not a replacement for hardware WebGL shading.
- GPU uses capped device pixel ratio and no auto-rotation. Animation is paused offscreen and when reduced motion is preferred.
- Quality levels `Eco`, `Auto`, `Studio` adjust backing resolution. They do not turn low-poly models into photoreal ones.
- The renderer exposes non-sensitive metrics: triangle count, draw/submit timings and frame submissions. CPU submit timing is not GPU time; record external GPU measurements before claims about hardware FPS.
- No Docker socket, credentials or elevated browser functionality are used by 3D assets or UI.

## Accessibility & testing limitations

Keyboard camera navigation: arrows (orbit/elevation), `+`/`-` (zoom), `Home` (reset). Every location has an equivalent HTML floor/room control. Native dialog and text input serve the command palette. Skip navigation is keyboard accessible. Important status remains textual rather than color-only. Mobile viewport includes 390px checks. **Screen-reader, 200% zoom on Windows, and full WCAG conformance have not been formally audited.**

## Scope guard

The v2.3 original assets are handcrafted **stylized** 3D models, not scanned/photorealistic furniture or licensed commercial character animation. Physically based rendering (PBR), skeletal rigging, shadows, post-processing and cross-browser GPU deployment tests remain future items.
