"""Survey import: no fabricated detections or coordinates."""
import json
import math
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
import numpy as np
import rasterio
from rasterio.shutil import copy as raster_copy
from rasterio.warp import transform_bounds
from . import store

MAX_EXPANDED = 8 * 1024**3
MAX_ENTRIES = 10000
RASTERS = {'.tif': 'GTiff', '.tiff': 'GTiff', '.ecw': 'ECW', '.asc': 'AAIGrid'}
SIDECARS = {'.prj', '.eww', '.tfw', '.wld', '.xml', '.txt', '.json'}

class ImportFailure(ValueError):
    pass

def unpack(archive, destination):
    """Validate entire central directory before extracting any bytes."""
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if len(entries) > MAX_ENTRIES:
            raise ImportFailure('ZIP has more than 10000 entries.')
        total = 0
        names = set()
        for item in entries:
            p = PurePosixPath(item.filename)
            if (p.is_absolute() or '..' in p.parts or '\\' in item.filename or ':' in item.filename
                    or stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1):
                raise ImportFailure('ZIP contains an unsafe path, symlink, or encrypted entry.')
            name = str(p).casefold()
            if name in names:
                raise ImportFailure('ZIP contains duplicate paths.')
            names.add(name)
            total += item.file_size
            if total > MAX_EXPANDED:
                raise ImportFailure('Expanded ZIP exceeds 8 GiB.')
        written = 0
        for item in entries:
            target = destination / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(item) as src, target.open('xb') as dst:
                while chunk := src.read(1024 * 1024):
                    written += len(chunk)
                    if written > MAX_EXPANDED:
                        raise ImportFailure('Expanded ZIP exceeds 8 GiB.')
                    dst.write(chunk)

def kind_for(path):
    parts = {x.lower() for x in path.parts}
    for folder, kind in [('dsm','dsm'), ('dtm','dtm'), ('ortho','orthomosaic'), ('pointcloud','pointcloud')]:
        if folder in parts:
            return kind
    return 'unknown'

def raster_layer(source, output, kind):
    # Restrict native decoders to expected data formats; never open user-supplied VRTs.
    driver = RASTERS[source.suffix.lower()]
    with rasterio.Env(GDAL_CACHEMAX=128*1024*1024, GDAL_NUM_THREADS='1') as env:
        if driver not in env.drivers():
            raise ImportFailure(f'{driver} decoder is unavailable. For ECW, install a licensed compatible ECW-enabled GDAL/Rasterio build or supply GeoTIFF.')
        with rasterio.open(source, driver=driver) as src:
            crs = src.crs
            prj = source.with_suffix('.prj')
            if crs is None and prj.exists():
                crs = rasterio.crs.CRS.from_wkt(prj.read_text())
            if crs is None:
                raise ImportFailure('Missing coordinate reference system; supply a valid PRJ or georeferenced raster.')
            if src.transform == rasterio.Affine.identity():
                raise ImportFailure('Missing georeferencing; preserve world-file sidecars.')
            if src.width * src.height > 4_000_000_000:
                raise ImportFailure('Raster exceeds configured pixel limit.')
            bounds = list(transform_bounds(crs, 'EPSG:4326', *src.bounds, densify_pts=21))
            if not all(math.isfinite(x) for x in bounds) or not (-180 <= bounds[0] <= bounds[2] <= 180 and -90 <= bounds[1] <= bounds[3] <= 90):
                raise ImportFailure('Invalid WGS84 bounds; verify the source CRS.')
            sample = src.read(1, out_shape=(min(512, src.height), min(512, src.width)), masked=True)
            values = sample.compressed()
            values = values[np.isfinite(values)]
            display = [float(np.percentile(values, 2)), float(np.percentile(values, 98))] if values.size else [0.0, 1.0]
            metadata = dict(crs=crs.to_string(), bounds=bounds, width=src.width, height=src.height,
                            bands=src.count, resolution=list(src.res), dataType=src.dtypes[0],
                            elevationUnit=src.units[0] if kind in ('dsm','dtm') else None,
                            displayRange=display, displayRangeMethod='sampled_percentiles_2_98')
        # Copy preserves source pixel values. Apply PRJ fallback to the output only.
        intermediate = output.with_suffix('.stage.tif')
        raster_copy(source, intermediate, driver='GTiff', tiled=True, compress='DEFLATE', BIGTIFF='IF_SAFER')
        with rasterio.open(intermediate, 'r+') as ds:
            ds.crs = crs
        raster_copy(intermediate, output, driver='COG', compress='DEFLATE', blocksize=512, BIGTIFF='IF_SAFER', NUM_THREADS='1')
        intermediate.unlink()
        return metadata

def point_layer(source, output):
    import laspy
    with laspy.open(source) as reader:
        header = reader.header
        crs = header.parse_crs()
        if crs is None:
            raise ImportFailure('LAS/LAZ has no CRS. Re-export with coordinate-system metadata.')
        count = header.point_count
        if count < 1:
            raise ImportFailure('Point cloud is empty.')
        # Bounded preview, original retained for download. Not a full-resolution octree.
        step = max(1, math.ceil(count / 50000))
        points, offset = [], 0
        origin = [float(v) for v in header.mins]
        for chunk in reader.chunk_iterator(100000):
            indices = np.arange((-offset) % step, len(chunk), step)
            xyz = np.column_stack((np.asarray(chunk.x)[indices], np.asarray(chunk.y)[indices], np.asarray(chunk.z)[indices]))
            if not np.isfinite(xyz).all():
                raise ImportFailure('Point cloud contains non-finite coordinates.')
            points.extend((xyz - origin).tolist())
            offset += len(chunk)
        output.write_text(json.dumps({'crs': crs.to_string(), 'origin': origin, 'positions': points,
                                      'sourcePointCount': count, 'sampled': count > len(points)}, allow_nan=False))
        return {'crs': crs.to_string(), 'sourcePointCount': count, 'previewPointCount': len(points),
                'boundsNative': [float(x) for x in header.mins] + [float(x) for x in header.maxs],
                'previewOnly': True}

def process(job_id):
    with store.connect() as db:
        job = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    directory = store.job_dir(job_id)
    raw = directory / 'raw'
    raw.mkdir(exist_ok=True)
    unpack(directory / 'upload.zip', raw)
    files = sorted(p for p in raw.rglob('*') if p.is_file())
    candidates = [p for p in files if p.suffix.lower() not in SIDECARS]
    if not candidates:
        raise ImportFailure('No survey data files found.')
    results = []
    for i, source in enumerate(candidates):
        relative = source.relative_to(raw)
        kind = kind_for(relative)
        layer_id = store.uid()
        layer = {'id': layer_id, 'projectId': job['project_id'], 'jobId': job_id,
                 'name': source.name, 'sourcePath': str(relative), 'kind': kind, 'status': 'failed',
                 'error': None, 'tileUrl': None, 'downloadUrl': None, 'previewUrl': None}
        target = directory / (layer_id + '.tif')
        try:
            if kind == 'unknown':
                raise ImportFailure('Place this file beneath Ortho, DSM, DTM, or POINTCLOUD.')
            if kind == 'pointcloud' and source.suffix.lower() in ('.las', '.laz'):
                target = directory / (layer_id + '.json')
                layer.update(point_layer(source, target))
                layer['previewUrl'] = f'/api/v1/layers/{layer_id}/preview'
            elif kind != 'pointcloud' and source.suffix.lower() in RASTERS:
                layer.update(raster_layer(source, target, kind))
                layer['tileUrl'] = f'/api/v1/layers/{layer_id}/tiles/{{z}}/{{x}}/{{y}}.png'
            else:
                raise ImportFailure('Unsupported file format. Raster: TIF/TIFF/ASC/ECW; point cloud: LAS/LAZ.')
            layer['status'] = 'ready'
            layer['downloadUrl'] = f'/api/v1/layers/{layer_id}/download'
        except Exception as exc:
            layer['error'] = str(exc)[:1000]
        store.save_layer(layer)
        results.append(layer)
        store.update_job(job_id, 'processing', int(95 * (i+1) / len(candidates)))
    ready = sum(x['status'] == 'ready' for x in results)
    status = 'completed' if ready == len(results) else 'partial' if ready else 'failed'
    store.update_job(job_id, status, 100, None if status == 'completed' else 'Some inputs could not be processed. Inspect layer errors.')
