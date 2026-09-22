# AeroView survey API v1

Base path: `/api/v1`. All endpoints require `Authorization: Bearer <server-only-key>`. Timestamps are UTC ISO 8601. IDs are opaque UUID strings. URLs below are relative to the backend and must be proxied for browser access.

| Method | Path | Input | Result |
|---|---|---|---|
| GET | `/capabilities` | — | Formats, ECW decoder availability, upload limit |
| POST | `/projects` | JSON `{ "name": "Indore" }` | 201 project |
| GET | `/projects` | — | `{ "items": [project] }` |
| POST | `/projects/{id}/imports` | Raw ZIP, `Content-Type: application/zip` | 202 import receipt |
| GET | `/processing-jobs/{id}` | — | Job state |
| GET | `/projects/{id}/layers` | — | `{ "projectId": "...", "items": [layer] }` |
| GET | `/projects/{id}/dashboard` | — | Project, jobs, layers, actual counts and empty inspection fields |
| GET | `/layers/{id}/tiles/{z}/{x}/{y}.png` | XYZ coordinates | PNG tile |
| GET | `/layers/{id}/download` | — | Converted raster TIFF or original point-cloud file |
| GET | `/layers/{id}/preview` | — | Sampled point cloud JSON |

Project response: `id`, `name`, `created_at`.

Import receipt (illustrative IDs, not survey results):

```json
{"jobId":"<uuid>","projectId":"<uuid>","status":"queued","statusUrl":"/api/v1/processing-jobs/<uuid>"}
```

Job response:

```json
{"id":"<uuid>","project_id":"<uuid>","status":"processing","progress":0,"error":null,"created_at":"<ISO timestamp>","updated_at":"<ISO timestamp>"}
```

States: `uploading → queued → processing → completed | partial | failed`. Poll about every 2–5 seconds and stop on a terminal state. `partial` means inspect per-layer errors and display successful layers. `failed` can have no layer records when ZIP validation or the worker failed. Progress is 0–100; a failed job may stop before 100.

Every layer has `id`, `projectId`, `jobId`, `name`, `sourcePath`, `kind`, `status`, `error`, `tileUrl`, `downloadUrl`, `previewUrl`. Kinds: `orthomosaic`, `dsm`, `dtm`, `pointcloud`, `unknown`. Status: `ready` or `failed`. Failed layers have no usable URLs.

Successful rasters additionally have:

- `crs`: source CRS identifier/WKT.
- `bounds`: `[west, south, east, north]` in EPSG:4326, for map navigation.
- `resolution`: `[x, y]` in **source CRS units**, not necessarily metres.
- `width`, `height`, `bands`, `dataType`.
- `elevationUnit`: declared band unit, possibly null. No guessed conversion.
- `displayRange`: sampled percentile range used for display only; original elevations remain in the downloadable COG.
- `displayRangeMethod`: `sampled_percentiles_2_98`.

Successful point clouds additionally have `crs`, `sourcePointCount`, `previewPointCount`, `boundsNative` (`[minX,minY,minZ,maxX,maxY,maxZ]`), `previewOnly: true`.

Preview JSON has `crs`, `origin: [x,y,z]`, `positions: [[dx,dy,dz], ...]`, `sourcePointCount`, `sampled`. Add origin to relative positions to reconstruct source coordinates. Do not treat source coordinates as geographic coordinates without reprojection.

Dashboard returns `project`, `projectType: "land-survey"`, `layers`, `jobs`, `summary: {readyLayers,failedLayers}`, `observations: []`, an explanatory `observationsMessage`, `liveStream: null`, `recordings: []`. These empty fields are intentional: survey rasters cannot establish flight videos or defect detections.

HTTP errors use FastAPI `{"detail": "message"}`; validation errors (422) have a detail array. Common codes: 401/403 unauthorized, 404 not found, 409 layer not ready, 413 upload too large, 415 wrong content type, 422 invalid JSON/parameters, 429 queue full, 503 missing API key. File conversion errors are returned in job/layer JSON, not as a successful fabricated layer.
