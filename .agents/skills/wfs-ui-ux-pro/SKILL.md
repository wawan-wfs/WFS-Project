---
name: wfs-ui-ux-pro
description: End-to-end UX research, visual systems, accessible interaction patterns, responsive implementation, and screenshot-driven UI quality assurance for WFS PROJECT.
---
# WFS UI/UX Pro — project-local skill

Use when creating, auditing, or changing any screen of WFS PROJECT. Do not use generated mockups instead of implementing actual user interactions.

## Required method
1. Read `app/static/index.html`, `app/static/style.css`, `app/static/ux-v22.css`, available feature tests, current API schemas, `docs/DESIGN_SYSTEM_V22.md` and related UI scripts before changes.
2. Enumerate each primary user flow: login, mission creation, queue, agent office, collaboration, operator approval, QA, files, events, costs, permissions.
3. Design in tokens instead of per-screen ad hoc colors. Use consistent typography (system font safe offline), restrained violet/cyan/gold accents, and accessible contrast. Define spacing 4/8/12/16/24/32, radii 8/12/16/24, nav/button/input states.
4. Keep informational hierarchy: top message, action, supporting facts, secondary details. Reduce dense walls of text and unrelated controls.
5. Implement actual keyboard interactions, `aria-*` where useful, visible focus, form labels, empty/loading/error/success states, and mobile overflow protections.
6. Do not invent project statuses, agent jobs, billing numbers, CI results, or runtime capabilities in the live UI. Demo must be clearly named DEMO.
7. Run desktop (>=1440), tablet (820), mobile (390) browser fixtures; open screenshots and fix visible defects. Check actual server E2E separately. Verify no cross-origin dependencies or CSP breaks.
8. Test interactions, not only screenshots. Save BEFORE/AFTER findings with explicit pass/fail and limitations.

## Design language
- Dark navy shell, violet identity, tasteful mint for verified live/positive statuses and muted gold for secondary highlights.
- Compact sidebar, spacious content, rich but readable page hero, unified form controls.
- Support `prefers-reduced-motion`; never rely only on colors to convey status.
- Keep prominent real command actions differentiated from preview/demo actions.
- Never use image-only controls without accessible equivalent.

## Deliverables
- Changes to source + tests
- Screenshots of affected pages in desktop/mobile
- Updated docs and fresh next-phase implementation prompt
- Explicit release readiness and unverified gates
