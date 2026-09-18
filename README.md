# AeroView — drone survey demo

React + TypeScript frontend with shared mock authentication, centralized role permissions, project access checks, and lazy feature modules. The live feed, dates, accounts, coordinates, imagery, and inspection records are simulated. No authentication/backend/drone integration is provided. Data mutations last for the current page session.

## Demo access
Client: client@demo.com (or SOL-001 / TRN-001). Firm: superadmin@demo.com, admin@demo.com, manager@demo.com, siteincharge@demo.com, employee@demo.com. All use demo123. Demo role buttons fill credentials.

## Structure
- `src/models.ts`: typed domain models.
- `src/permissions.ts`: role configuration and route/project checks.
- `src/data/`: independent mock factories for users, projects, clients, flights, assets, findings, drones, telemetry.
- `src/services/`: access-scoped services, pagination/filtering, telemetry generation.
- `src/features/`: lazy Solar overview, records, historical flights, comparison, live monitoring, analytics, reports, administration.
- `src/components/`: shared shell, login, map, tables and controls.

## Architecture
Authentication → user/login type → permission configuration → organization → permitted project → project-type resolver → feature module. Other survey types use a planned-module fallback.

All project operations pass through access-scoped services. UI permissions are demonstration behavior, not a security boundary. Replace service internals with authenticated FastAPI calls and server-enforced authorization before production use.

## Mock scale and performance
3 clients, 8 projects (4 solar, 2 transmission, 1 bridge, 1 land), 16 users, 5 drones, 32 historical flights, 1,280 representative inventory assets, and 327 findings. Full-site summary totals are simulated separately from the representative inventory. Data factories load on demand; list services filter/page records. Map renders six block clusters rather than individual panels. Feature modules are lazy. Telemetry updates every 1.5 seconds, has a 40-sample buffer and cleans up on navigation. Synthetic inspection imagery loads only in details.

## Routes
`/login`, `/dashboard`, `/projects`, `/projects/:id/:view`, and operational views `/flights`, `/assets`, `/findings`, `/analytics`, `/reports`, `/clients`, `/drones`, `/users`. The shared shell keeps project context without duplicating client and firm pages. Unauthorized project IDs and views are rejected. Browser back/forward is supported; refresh asks for a demo login again.

## Local checks
Use the selected package manager (pnpm). `pnpm exec tsc --noEmit`, `pnpm lint`, and `pnpm build`. The deployment uses the Sites Vinext/Cloudflare runtime.

## Deliberate demo limitations
Maps are interactive geographic site schematics, not satellite tiles. Photos are synthetic examples and not asset-specific evidence. Reports export TXT and CSV. Firm users can simulate project status changes and finding review/resolution. Non-solar modules are placeholders. Comparison rows are illustrative demo changes. Browser WebMCP integration is feature-detected; unavailable browsers retain the complete visible UI.
