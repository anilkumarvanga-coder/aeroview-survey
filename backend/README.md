# AeroView survey backend

A working, persistent **single-customer / single-host** ingestion service for processed drone survey deliverables. This is a new backend module; the existing AeroView React screens still use their current demo services until wired to these endpoints. No solar defects, flight telemetry, or observations are invented from terrain data.

## What it does

- Streams a ZIP to disk with a default 2 GiB compressed limit; validates paths, symlinks, duplicate names, encryption and an 8 GiB expanded limit.
- Keeps original source files and sidecars in a persistent volume.
- Imports Ortho / DSM / DTM GeoTIFF or ASC into Cloud Optimized GeoTIFF, preserving source pixel values and CRS.
- Provides authenticated 256px Web Mercator PNG map tiles. Terrain is grayscale with a sampled 2–98 percentile display stretch, **not** a slope or contour product.
- Reads LAS/LAZ and creates at most 50,000 sampled 3D points with native CRS and a local origin. Original point clouds remain downloadable. This is a bounded preview, **not** a full-resolution tiled point-cloud engine.
- Stores projects, jobs and layer metadata in SQLite. A separate worker processes jobs sequentially in subprocesses with time limits. API restarts do not erase queued jobs.
- Gives each failed file an explicit error; mixed successful/failed files produce a `partial` job.

## Input layout

A ZIP can contain a wrapping folder. Use these directory names, case insensitive:

```
Indore/
  Ortho/Ecw/Indore-Ortho.ecw
  Ortho/Ecw/Indore-Ortho.eww
  Ortho/Ecw/Indore-Ortho.prj
  DSM/surface.tif
  DTM/terrain.tif
  POINTCLOUD/survey.laz
```

The exact DSM / DTM / point-cloud formats in the supplied screenshots are unknown. Currently supported formats are TIF/TIFF/ASC and LAS/LAZ; ECW is conditional as below. Other files are reported as unsupported (common sidecars are preserved). Coordinate metadata must be present. Never guess an EPSG code. Raster `.prj` fallback supports same-stem, lowercase `.prj`; preserve world files and original filenames. Vertical units may be null if the source does not declare them. Do not calculate engineering volumes from unverified units/datums.

### ECW requirement

The standard Rasterio wheel/Docker image **does not include an ECW decoder**. The API reports this through `/capabilities`, and ECW imports fail with an actionable message. Use a suitably licensed ECW-enabled GDAL/Rasterio build, or ask the survey provider to export georeferenced GeoTIFF. A working server ECW build and the actual Indore file are required to validate that format. Installing a separate `gdal_translate` binary does not add ECW to Rasterio's bundled GDAL.

References: https://gdal.org/en/stable/drivers/raster/ecw.html and https://gdal.org/en/stable/drivers/raster/cog.html

## Run on a Linux server

Requires Docker Compose. From `backend/`:

```bash
export AEROVIEW_API_KEY="$(openssl rand -hex 32)"
docker compose up --build -d
```

Keep that key in your secret manager for restarts. The API listens only on `127.0.0.1:8000`. Put a trusted HTTPS reverse proxy/application server in front of it. Do not expose the service key through `NEXT_PUBLIC_*`, browser JavaScript, query strings or Git. It grants access to **all projects in this deployment**.

- API docs: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json (also included as `openapi.json`)
- Health: http://localhost:8000/health (process liveness, not worker readiness)
- Persistent volume: `survey-data`; back it up with the database and files together.

For development:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
export AEROVIEW_API_KEY="$(openssl rand -hex 32)"
export AEROVIEW_DATA="$PWD/data"
uvicorn app.main:app --host 127.0.0.1 --port 8000
# In a second terminal with the same environment:
python -m app.worker
```

## API walkthrough

All `/api/v1` requests need `Authorization: Bearer <service-key>`. Requests go from your trusted application server to this backend.

```bash
curl -H "Authorization: Bearer $AEROVIEW_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Indore land survey"}' http://localhost:8000/api/v1/projects

# Copy the returned id into PROJECT_ID.
curl -H "Authorization: Bearer $AEROVIEW_API_KEY" \
  -H 'Content-Type: application/zip' --data-binary @survey.zip \
  "http://localhost:8000/api/v1/projects/$PROJECT_ID/imports"

# Copy the returned jobId into JOB_ID; poll until completed/partial/failed.
curl -H "Authorization: Bearer $AEROVIEW_API_KEY" \
  "http://localhost:8000/api/v1/processing-jobs/$JOB_ID"

curl -H "Authorization: Bearer $AEROVIEW_API_KEY" \
  "http://localhost:8000/api/v1/projects/$PROJECT_ID/dashboard"
```

Upload is **raw ZIP bytes**, not multipart. Processing starts automatically after upload; there is no second start endpoint. Four active uploads/jobs are allowed per deployment. Reverse-proxy body limits/timeouts must accommodate the configured size. Browser uploads should use a streaming authenticated proxy, not an in-memory body parser. Large uploads and processing should run on the survey server, not a Vercel function.

## Connect AeroView

See `API_FORMAT.md` and `ui-types.ts` for the data contract.

1. Authenticate the end user in the application server; check project authorization there. This backend is not the user-login service.
2. Map each frontend project to the backend project UUID; do not reuse solar demo IDs as database identifiers.
3. Replace the demo project/map services with `/projects` and `/projects/{id}/dashboard` responses.
4. Upload ZIP bytes, display real job progress, then load `ready` layers after job completion.
5. Add `tileUrl` to the map as an XYZ raster source (tile size 256, zoom 0–22); use `bounds` in longitude/latitude to fit the map. Proxy tile requests with the user's session and inject the service credential on the server.
6. Use point `positions` plus `origin` in the supplied CRS for a local 3D preview. These are not WGS84 longitude/latitude points.
7. Show actual errors and empty states. Do not show fake observation counts or live streams when only survey maps are available.

Existing observation edits, multi-user login, subscriptions and tenant permissions are not implemented by this import module. Keep the current UI unchanged until its services are deliberately switched over.

## Operational scope and remaining work

This release is executable backend code, not a claim that the full SaaS platform is production-complete. Deploy one isolated instance per customer. Shared multi-tenant hosting needs verified identity/tenant authorization, role enforcement, audit logs, PostgreSQL/object storage, lifecycle quotas and backups, monitoring and a scalable job queue. Source upload access is intended for trusted operators; do not expose native geospatial parsers directly to anonymous users. The worker container has no network and has memory/CPU limits.

The worker uses a Linux file lock; run only one worker for each volume. Interrupted processing jobs are marked failed at worker restart; retry by re-uploading. Uploads interrupted by a hard API crash can remain `uploading`: inspect and remove/mark them during maintenance. Artifacts are retained indefinitely; monitor disk capacity and implement retention before sustained use. Job percentage measures files completed, not exact progress within an individual raster conversion.

Not included: raw-photo photogrammetry, survey accuracy certification, ground classification, contours, slope, cut/fill volumes, full-resolution point-cloud tiling, automatic object detection or live drone connectivity. Those require additional processing and source validation.

## Verification

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests create small real GeoTIFF/LAS fixtures and exercise upload, persistence, conversion, PNG tiles, partial failures, missing CRS, authentication, limits and malicious ZIP paths. They do not replace a conversion test using your actual ECW/DSM/DTM/point-cloud files. Docker deployment itself must also be checked on the target server.
