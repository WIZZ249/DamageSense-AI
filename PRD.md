# DamageSense AI — Watermelon UI and Global Damage Map PRD

**Status:** Implemented release specification
**Author:** Manus AI
**Date:** 2026-09-03

## Product intent

DamageSense AI is a high-trust visual field-inspection workspace for humanitarian and infrastructure-response teams. The product accepts an image of a road, vehicle, building, or other structure, returns a structured first-pass damage assessment, persists the result, and helps teams understand where risk signals are clustering.

This release replaces the generic field-operations visual language with a **Watermelon UI** system: zinc-black canvases, bento-grid information density, emerald operational states, coral-crimson hazards, and deliberate motion. It also introduces the **Global Damage Cluster Map**, a protected Leaflet/OpenStreetMap surface with severity filters, marker clustering, location capture, and a clear distinction between device GPS and estimated legacy/demo zones.

> AI output is decision support, not an engineering certification, emergency declaration, or substitute for professional inspection.

## Users and jobs to be done

| User | Job | Success signal |
|---|---|---|
| Field assessor | Upload or capture an image and receive an actionable result immediately | The result renders in the same workspace response and is saved to history |
| Operations lead | Scan geographic patterns across response zones | The map loads clustered points and filters by severity |
| Administrator | Monitor all assessment activity and manage users | Admin-only map scope, metrics, audit trail, and exports remain available |

## Release requirements

### Assessment and location

Every new assessment accepts an optional browser geolocation payload. The server validates latitude and longitude ranges, stores coordinates separately from the AI JSON, and records the source as `gps`. If a historical assessment has no coordinates, the map uses a deterministic estimated response-zone coordinate and labels it as estimated rather than presenting it as device telemetry.

### Global Damage Cluster Map

The map is available to authenticated users at `/map`. Regular users see their own assessment points; administrators see the global assessment scope. The `/api/map-data` endpoint returns point records and summary counts. Leaflet renders OpenStreetMap tiles, marker clusters, severity-colored pins, popups, a severity filter, a global fit view, and a browser location control.

### Visual system

The core palette is zinc-950 `#09090B`, zinc-900 `#18181B`, zinc-800 `#27272A`, coral-crimson `#F43F5E` for critical/high hazards, emerald `#34D399` for stable/low states, sky `#7DD3FC` for actions and focus, and amber `#FBBF24` for medium attention. Components should remain legible in low-bandwidth, low-light, and mobile browser conditions.

### Safety and accessibility

The server remains the authorization boundary. Map access is authenticated, admin data scope is determined server-side, and location permission is optional. User-facing copy must disclose estimated points and retain human-review language. Keyboard focus, contrast, reduced-motion preferences, and mobile layouts must be preserved.

## Acceptance criteria

| Area | Acceptance test |
|---|---|
| Location persistence | A scan submitted with valid browser coordinates stores latitude, longitude, and `gps` source |
| Invalid location | Out-of-range or malformed coordinates are ignored without failing the scan |
| Map scope | An ordinary user cannot receive another user's points through `/api/map-data`; an admin can see global points |
| Map interaction | Severity filters, clusters, popups, and locate control work on desktop and mobile |
| Legacy data | Records without coordinates appear only as explicitly labeled estimated zones |
| Regression safety | Existing login, logout, immediate result, history, admin, exports, verification, robots, sitemap, and health flows remain functional |
| Deployment | Existing PostgreSQL data is preserved through additive startup migration |

## Out of scope

This release does not infer location from image content, perform reverse geocoding, certify structural safety, expose the map publicly for SEO, or replace professional GIS systems. A future release may add a geocoder, polygon zones, time windows, heatmap intensity, and offline-first field sync.
