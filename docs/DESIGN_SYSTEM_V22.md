# WFS PROJECT v2.2 — Spatial Design System

## Visual direction
Dark command interface inspired by high-quality modern developer tooling. Indigo/violet identity, cyan for positive telemetry, champagne-gold only for supplementary contrast. Focus on substance and visual hierarchy, not decorative noise. This is a design implementation, not a new product capability claim.

## Design tokens

| Token | Value | Usage |
|---|---|---|
| Background | `#090d18` | Main shell |
| Sidebar | `#0b1020` | Navigation rail |
| Panel | `#11182a` | Information surfaces |
| Primary text | `#f3f6ff` | Titles/content |
| Secondary text | `#99a8c3` | Labels/details |
| Violet | `#827afa` | Brand/active/primary actions |
| Mint | `#70d5cf` | Verified live states |
| Gold | `#d7c19e` | Limited secondary emphasis |
| Radius | 8/12/17/24px | Controls/cards/hero |
| Spacing | 4/8/12/16/24/32px | Consistent rhythm |

Typography uses local system fonts only, suitable for offline Docker deployments. Native HTML controls are retained and backend routes unchanged. Input labels, error states, motion preferences, and 390px layouts are required.

## Spatial Office
- `office3d.js`: procedural mesh geometry and WebGL2 GPU renderer; depth-test, orbit, zoom, lighting, animated active bots.
- `office3d-software.js`: CPU Canvas2D rasterizer of the same 3D meshes for browsers without WebGL; static frames to reduce CPU consumption.
- `studio.js`: one source of truth from authenticated `/api/office/live` + opt-in clearly labeled demo mode.
- Existing 2.5D scene preserved as a manually selectable fallback.
- Native HTML room list and camera buttons provide keyboard navigation and status equivalents.
- Important: no licensed third-party GLB models or photoreal textures are included. Visual direction is stylized low-poly 3D, not a AAA metaverse.

## UX audit / future fidelity
1. Add compact task drawer in office, floor minimap, keyboard shortcuts, and project timeline in the 3D experience.
2. Add optimized locally bundled GLTF/GLB asset library with explicit attribution and verified licenses if high fidelity is approved.
3. Validate on Windows Chrome/Edge WebGL2 hardware; currently the development browser's GPU is unavailable and CPU 3D fallback is used.
4. Run real API browser E2E on user's Windows/Docker deployment; local API HTTP and browser fixture tests are not equivalent.
5. Test color contrast and screen reader, LCP and frame rate on low-end Android before production claims.
