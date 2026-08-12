# HajiriFlow Frontend Experience v5

## Purpose

This layer adds licensed visual media, Motion-powered interaction, and meaningful loading feedback without changing the dynamic demo data provider.

## Open visual media

- Employee and administrator avatars use DiceBear 10.x `notionists-neutral`.
- The selected style is CC0 1.0.
- Avatars are deterministic from a person name or employee identifier.
- Every remote avatar has an initials fallback.
- Images use lazy loading and asynchronous decoding.
- No stock photograph is embedded without a recorded license.

## Motion system

HajiriFlow uses Motion 12.42.1 from a version-pinned jsDelivr ESM import.

Motion is applied to:

- route and dashboard entrances;
- metric, panel, report, device, and payroll card reveals;
- modal and command-menu entrances;
- navigation active-state movement;
- button press feedback;
- newly loaded avatar images.

Rules:

- motion communicates hierarchy or state;
- no looping decorative animation;
- no animation blocks an action;
- transforms and opacity are preferred for performance;
- `prefers-reduced-motion` disables nonessential motion.

## Loading system

The workspace exposes an actual loading lifecycle rather than an ornamental spinner.

- Initial application hydration shows a dashboard-shaped skeleton.
- Route changes briefly show a route skeleton until new content is rendered.
- Avatar placeholders shimmer until the open image loads.
- `aria-busy` is applied to the workspace while loading.
- Skeletons are hidden from assistive technology.
- Loading has a short minimum duration to prevent distracting flashes.

## Security and resilience

- Motion is pinned to an exact version.
- Content Security Policy allows only the fixed CDN origin and DiceBear image origin.
- If either external service is unavailable, the application remains usable.
- The data layer and all core actions remain first-party and browser-local.

## Attribution

- Motion: MIT License, Motion Division.
- DiceBear core: MIT License.
- Notionists Neutral avatar style: CC0 1.0, based on artwork by Zoish.
