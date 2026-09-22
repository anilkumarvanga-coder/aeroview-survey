import io
import json
import os
import secrets
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.transform import from_bounds
from PIL import Image
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from . import store

MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_BYTES', str(2 * 1024**3)))
security = HTTPBearer()

def authorize(credentials: HTTPAuthorizationCredentials = Depends(security)):
    key = os.environ.get('AEROVIEW_API_KEY', '')
    if len(key) < 32:
        raise HTTPException(503, 'Backend API key is not configured (minimum 32 characters).')
    if not secrets.compare_digest(credentials.credentials, key):
        raise HTTPException(401, 'Invalid API key.')

@asynccontextmanager
async def lifespan(app):
    store.init()
    yield

app = FastAPI(title='AeroView Survey Import API', version='1.0.0', lifespan=lifespan,
              description='Single-customer survey backend. Authenticate through a trusted frontend server; never expose this service key in browser code.')

class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)

def project_exists(id):
    with store.connect() as db:
        row = db.execute('SELECT * FROM projects WHERE id=?', (id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Project not found.')
    return dict(row)

def get_job_row(id):
    with store.connect() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?', (id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Processing job not found.')
    return dict(row)

def layer_row(id):
    with store.connect() as db:
        row = db.execute('SELECT metadata FROM layers WHERE id=?', (id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Layer not found.')
    data = json.loads(row['metadata'])
    # Never serve incomplete output from an interrupted worker.
    if data['status'] != 'ready' or get_job_row(data['jobId'])['status'] not in ('completed', 'partial'):
        raise HTTPException(409, 'Layer is not ready.')
    return data

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/api/v1/capabilities', dependencies=[Depends(authorize)])
def capabilities():
    with rasterio.Env() as env:
        ecw = 'ECW' in env.drivers()
    return {'rasterFormats': ['tif','tiff','asc'] + (['ecw'] if ecw else []),
            'ecwDecoderAvailable': ecw, 'pointCloudFormats': ['las','laz'],
            'maxUploadBytes': MAX_UPLOAD, 'pointCloudPreviewLimit': 50000,
            'deploymentScope': 'single-customer'}

@app.post('/api/v1/projects', status_code=201, dependencies=[Depends(authorize)])
def create_project(body: ProjectInput):
    id = store.uid()
    with store.connect() as db:
        db.execute('INSERT INTO projects VALUES(?,?,?)', (id, body.name.strip(), store.now()))
    return project_exists(id)

@app.get('/api/v1/projects', dependencies=[Depends(authorize)])
def list_projects():
    with store.connect() as db:
        return {'items': [dict(x) for x in db.execute('SELECT * FROM projects ORDER BY created_at DESC')]}

@app.post('/api/v1/projects/{project_id}/imports', status_code=202, dependencies=[Depends(authorize)])
async def upload(project_id: str, request: Request):
    """Send raw ZIP bytes (Content-Type: application/zip). Streaming, not multipart."""
    project_exists(project_id)
    if request.headers.get('content-type','').split(';')[0] != 'application/zip':
        raise HTTPException(415, 'Send raw ZIP bytes with Content-Type: application/zip.')
    length = request.headers.get('content-length')
    if length and (not length.isdigit() or int(length) > MAX_UPLOAD):
        raise HTTPException(413, 'Upload exceeds configured limit or invalid Content-Length.')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT count(*) FROM jobs WHERE status IN ('uploading','queued','processing')").fetchone()[0] >= 4:
            raise HTTPException(429, 'Import queue is full. Wait for existing jobs to finish.')
        id = store.uid()
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)', (id, project_id, 'uploading', 0, None, store.now(), store.now()))
    directory = store.job_dir(id)
    directory.mkdir(parents=True)
    size = 0
    try:
        with (directory / 'upload.part').open('wb') as dst:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, 'Upload exceeds configured limit.')
                dst.write(chunk)
        if size == 0:
            raise HTTPException(400, 'ZIP is empty.')
        (directory / 'upload.part').rename(directory / 'upload.zip')
        store.update_job(id, 'queued', 0)
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        store.update_job(id, 'failed', 0, 'Upload did not complete. Submit the ZIP again.')
        raise
    return {'jobId': id, 'projectId': project_id, 'status': 'queued',
            'statusUrl': f'/api/v1/processing-jobs/{id}'}

@app.get('/api/v1/processing-jobs/{job_id}', dependencies=[Depends(authorize)])
def job_status(job_id: str):
    return get_job_row(job_id)

@app.get('/api/v1/projects/{project_id}/layers', dependencies=[Depends(authorize)])
def layers(project_id: str):
    project_exists(project_id)
    with store.connect() as db:
        rows = db.execute('SELECT l.metadata, j.status AS job_status FROM layers l JOIN jobs j ON l.job_id=j.id WHERE l.project_id=? AND j.status IN (\'completed\',\'partial\',\'failed\')', (project_id,)).fetchall()
    items = []
    for row in rows:
        item = json.loads(row['metadata'])
        if row['job_status'] == 'failed' and item['status'] == 'ready':
            item.update(status='failed', error='Import did not finish; re-upload to retry.',
                        tileUrl=None, downloadUrl=None, previewUrl=None)
        items.append(item)
    return {'projectId': project_id, 'items': items}

@app.get('/api/v1/projects/{project_id}/dashboard', dependencies=[Depends(authorize)])
def dashboard(project_id: str):
    project = project_exists(project_id)
    items = layers(project_id)['items']
    with store.connect() as db:
        jobs = [dict(r) for r in db.execute('SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC', (project_id,))]
    return {'project': project, 'projectType': 'land-survey', 'layers': items, 'jobs': jobs,
            'summary': {'readyLayers': sum(x['status']=='ready' for x in items),
                        'failedLayers': sum(x['status']=='failed' for x in items)},
            'observations': [], 'observationsMessage': 'Survey layers do not automatically provide inspection detections.',
            'liveStream': None, 'recordings': []}

@app.get('/api/v1/layers/{layer_id}/download', dependencies=[Depends(authorize)])
def download(layer_id: str):
    layer = layer_row(layer_id)
    directory = store.job_dir(layer['jobId'])
    source = directory / 'raw' / layer['sourcePath'] if layer['kind']=='pointcloud' else directory / (layer_id+'.tif')
    return FileResponse(source, filename=layer['name'] if layer['kind']=='pointcloud' else Path(layer['name']).stem+'.tif')

@app.get('/api/v1/layers/{layer_id}/preview', dependencies=[Depends(authorize)])
def preview(layer_id: str):
    layer = layer_row(layer_id)
    if layer['kind'] != 'pointcloud':
        raise HTTPException(400, 'Preview endpoint is for point clouds.')
    return FileResponse(store.job_dir(layer['jobId']) / (layer_id+'.json'), media_type='application/json')

@app.get('/api/v1/layers/{layer_id}/tiles/{z}/{x}/{y}.png', dependencies=[Depends(authorize)])
def tile(layer_id: str, z: int, x: int, y: int):
    if not 0 <= z <= 22 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise HTTPException(400, 'Invalid XYZ tile coordinate.')
    layer = layer_row(layer_id)
    if not layer['tileUrl']:
        raise HTTPException(400, 'Layer is not a raster.')
    extent = 20037508.342789244
    span = 2 * extent / 2**z
    bounds = (-extent+x*span, extent-(y+1)*span, -extent+(x+1)*span, extent-y*span)
    with rasterio.Env(GDAL_CACHEMAX=64*1024*1024):
        with rasterio.open(store.job_dir(layer['jobId']) / (layer_id+'.tif')) as src:
            with WarpedVRT(src, crs='EPSG:3857', transform=from_bounds(*bounds, 256, 256),
                           width=256, height=256, add_alpha=rasterio.enums.ColorInterp.alpha not in src.colorinterp) as vrt:
                indexes = [1,2,3] if src.count >= 3 and layer['kind']=='orthomosaic' else [1]
                data = vrt.read(indexes, masked=True).astype('float32')
                valid = (vrt.dataset_mask() > 0) & np.isfinite(data).all(axis=0)
                if src.dtypes[0]=='uint8' and layer['kind']=='orthomosaic':
                    scaled = data.filled(0).clip(0,255).astype('uint8')
                else:
                    low, high = layer['displayRange']
                    scaled = np.nan_to_num((data.filled(low)-low)/max(high-low, 1e-12)*255).clip(0,255).astype('uint8')
                rgb = np.repeat(scaled,3,axis=0) if len(indexes)==1 else scaled
                rgba = np.concatenate((rgb, valid[None].astype('uint8')*255), axis=0).transpose(1,2,0)
    stream = io.BytesIO()
    Image.fromarray(np.asarray(rgba, dtype='uint8')).save(stream, format='PNG')
    return Response(stream.getvalue(), media_type='image/png', headers={'Cache-Control':'private, max-age=3600'})
