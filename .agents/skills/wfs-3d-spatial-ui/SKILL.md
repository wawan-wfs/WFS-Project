---
name: wfs-3d-spatial-ui
description: Build real interactive, accessible, secure 3D interfaces for WFS Virtual AI Office, based on authenticated telemetry and bounded GPU/CPU usage.
---
# WFS Spatial 3D Engineer

Use for WebGL, canvas rendering, multi-floor office spaces, camera controls, and avatar-state visualization.

## Non-negotiables
- Real 3D geometry, depth-tested projection, camera orbit and zoom. A flat picture or CSS tilt is never a replacement for 3D.
- Render data from `/api/office/live` under current user's permission scope. No fake working agents. Demo state must say `DEMO / NOT LIVE`.
- Keep the entire control plane usable when WebGL is missing, including a CPU 3D path and an explicitly selectable 2.5D fallback.
- Protect performance: pause when view hidden or tab background; limit pixel ratio; cap software rendering cadence; dispose buffers/observers; avoid unbounded resources.
- Match reduced-motion settings; no camera auto-rotation or seizure-inducing effects.
- Every visually selectable team must have a native HTML control, accessible label, keyboard focus and equivalent status text outside canvas.
- Never inject remote scripts or third-party assets violating Content Security Policy. Do not connect the render loop to Docker, model credentials, or privileged endpoints.
- Browser-test camera operations, floor switching, 3D/2.5D switch, project filtering, agent inspector, demo truthfulness and mobile layout.

## Future visual fidelity path
GLB/GLTF physically based office assets from verified licenses (locally packaged, optimized), Draco/Meshopt depending on supported environments, LOD, lighting baked where appropriate, performance budgets and capability detection; do not claim such asset-based fidelity until assets and builds actually exist.
