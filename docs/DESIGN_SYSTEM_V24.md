# WFS PROJECT v2.4 — Spatial Workbench / UI Design System

**Implemented source:** `app/static/ux-v23.css`, `ux-v24.css`, `office3d.js`, `office3d-assets.js`, and the retained real controllers. No new remotely hosted CSS, JS, fonts, or imagery. This is an engineering implementation, not a visual-only mockup.

## Design tokens

- Navy foundation (`#080d18`), elevated surfaces (`#18243a`), violet for primary operations (`#a89afb`), mint for **verified** current activity (`#88e0c3`), restrained gold for spatial navigation (`#efdcaa`). Never use a color without a textual status.
- Hierarchy: page heading → primary action → current data → supporting records. Shared `page-hero`, `panel`, `collab-panel`, button, input and inspector styles serve all 13 routes.
- Spacing follows 4/8/12/16/24/32px increments. Input focus, disabled actions, and high-contrast/reduced-motion states have distinct styles. Primary buttons must retain genuine event handlers.
- 1440px desktop, 820px tablet and 390px mobile navigation/overflow checks were run against Chromium fixtures. This does **not** prove native mobile browsers, real server rendering, screen readers, or Windows 200% scaling.

## 3D renderer changes

- Eight **original CC0 GLB** models now loaded by both the WebGL2 and on-demand CPU software renderer; each has a glTF 2.0 `pbrMetallicRoughness` material. Reproducible generator: `tools/build_original_assets.py`.
- WebGL2 pipeline evaluates an approximate Cook–Torrance-style metallic/roughness BRDF with a single directional key light and ambient fill. No physically accurate environment IBL, texture maps, shadows, normal maps, skeletal bones, camera collision or HDR postprocessing. Describing the system as photorealistic would be incorrect.
- GPU / CPU geometry now carries 13 floats per vertex (position, normal, color, glow, work-motion, metalness, roughness). CPU uses simplified shading. WebGL2 compilation on target GPUs remains an acceptance gate.
- The `office-3d-task-inspector` is a native HTML equivalent to selection inside the 3D scene. It displays permitted backend telemetry, disables an open-agent control when no run is recorded, and uses an explicit `DEMO · NOT LIVE` indication.
- `office-3d-rooms` controls support focus, selected-state outline, `aria-pressed`, mouse and keyboard. The scene is paused offscreen or on hidden tab, and the optional 2.5D fallback remains.

## Disclosure

Synthetic fixture status is never live telemetry. An idle workstation remains unoccupied. Task changes and live state are driven by the existing authenticated `/api/office/live` response, not random animations or local simulated conversations. Screenshot gallery files in `docs/V24_SCREENS` come from fixtures, not live AI runs.
