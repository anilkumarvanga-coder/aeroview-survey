import io
import zipfile
import stat
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from fastapi.testclient import TestClient
from app import store
from app.main import app
from app.processing import unpack, ImportFailure, process

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    monkeypatch.setenv('AEROVIEW_API_KEY', 'test-key-' + 'x'*40)
    with TestClient(app) as c:
        c.headers['Authorization'] = 'Bearer test-key-' + 'x'*40
        yield c

def archive(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        for name, data in files.items():
            z.writestr(name, data)
    return b.getvalue()

def submit(c, files):
    p = c.post('/api/v1/projects', json={'name':'Real survey test'}).json()['id']
    r = c.post(f'/api/v1/projects/{p}/imports', content=archive(files), headers={'Content-Type':'application/zip'})
    assert r.status_code==202, r.text
    job = r.json()['jobId']
    process(job)
    return p, job

def raster(tmp_path, crs='EPSG:4326', alpha=False):
    p = tmp_path/'input.tif'
    with rasterio.open(p, 'w', driver='GTiff', width=32, height=32, count=4 if alpha else 1,
                       dtype='uint8', crs=crs, transform=from_origin(75,23,.001,.001)) as dst:
        for band in range(1, (5 if alpha else 2)):
            dst.write(np.full((32,32), 255 if band==4 else 120, dtype='uint8'),band)
        if alpha:
            dst.colorinterp = (rasterio.enums.ColorInterp.red,rasterio.enums.ColorInterp.green,rasterio.enums.ColorInterp.blue,rasterio.enums.ColorInterp.alpha)
    return p.read_bytes()

def test_auth(client):
    assert client.get('/api/v1/projects', headers={'Authorization':'Bearer wrong'}).status_code==401

def test_missing_project(client):
    assert client.get('/api/v1/projects/unknown/layers').status_code==404

@pytest.mark.parametrize('alpha', [False,True])
def test_import_cog_and_tile(client,tmp_path,alpha):
    p,j = submit(client, {'Ortho/test.tif':raster(tmp_path,alpha=alpha)})
    assert client.get('/api/v1/processing-jobs/'+j).json()['status']=='completed'
    layers = client.get(f'/api/v1/projects/{p}/layers').json()['items']
    layer = layers[0]
    assert layer['bounds'][0] == pytest.approx(75)
    assert layer['crs']=='EPSG:4326'
    assert layer['status']=='ready'
    r=client.get(layer['tileUrl'].replace('{z}','0').replace('{x}','0').replace('{y}','0'))
    assert r.status_code==200 and r.content.startswith(b'\x89PNG')
    assert client.get(layer['downloadUrl']).status_code==200
    assert client.get(f'/api/v1/layers/{layer["id"]}/tiles/23/0/0.png').status_code==400
    assert client.get(f'/api/v1/projects/{p}/dashboard').json()['observations']==[]

def test_partial_and_no_crs(client,tmp_path):
    p,j=submit(client,{'DSM/good.tif':raster(tmp_path), 'DTM/missing.tif':raster(tmp_path,crs=None)})
    assert client.get('/api/v1/processing-jobs/'+j).json()['status']=='partial'
    items=client.get(f'/api/v1/projects/{p}/layers').json()['items']
    assert len([x for x in items if x['status']=='failed'])==1

def test_ecw_explicit_error(client):
    p,j=submit(client, {'Ortho/Ecw/Indore-Ortho.ecw':b'not a raster', 'Ortho/Ecw/Indore-Ortho.prj':b'invalid'})
    assert client.get('/api/v1/processing-jobs/'+j).json()['status']=='failed'
    layer=client.get(f'/api/v1/projects/{p}/layers').json()['items'][0]
    assert layer['error'] and layer['tileUrl'] is None

@pytest.mark.parametrize('path', ['../escape', '/absolute', 'C:/data', 'a\\b'])
def test_zip_traversal(tmp_path,path):
    p=tmp_path/'bad.zip';p.write_bytes(archive({path:b'x'}))
    with pytest.raises(ImportFailure): unpack(p,tmp_path/'raw')

def test_zip_symlink(tmp_path):
    p=tmp_path/'bad.zip'
    with zipfile.ZipFile(p,'w') as z:
        entry=zipfile.ZipInfo('link');entry.external_attr=(stat.S_IFLNK|0o777)<<16
        z.writestr(entry,'/etc/passwd')
    with pytest.raises(ImportFailure):unpack(p,tmp_path/'raw')

def test_point_cloud(client,tmp_path):
    import laspy
    from pyproj import CRS
    h=laspy.LasHeader(point_format=3,version='1.2');h.add_crs(CRS.from_epsg(32643))
    las=laspy.LasData(h);las.x=np.array([500000.,500001.]);las.y=np.array([2500000.,2500001.]);las.z=np.array([100.,102.])
    path=tmp_path/'cloud.las';las.write(path)
    p,j=submit(client,{'POINTCLOUD/cloud.las':path.read_bytes()})
    assert client.get('/api/v1/processing-jobs/'+j).json()['status']=='completed'
    layer=client.get(f'/api/v1/projects/{p}/layers').json()['items'][0]
    data=client.get(layer['previewUrl']).json()
    assert len(data['positions'])==2 and data['sourcePointCount']==2
    assert data['origin']==[500000.,2500000.,100.]

def test_upload_limit(client,monkeypatch):
    import app.main as main
    monkeypatch.setattr(main,'MAX_UPLOAD',10)
    p=client.post('/api/v1/projects',json={'name':'P'}).json()['id']
    assert client.post(f'/api/v1/projects/{p}/imports',content=b'x'*11,headers={'Content-Type':'application/zip'}).status_code==413

def test_persistence(client):
    p=client.post('/api/v1/projects',json={'name':'Persistent'}).json()['id']
    store.init()
    assert p in [x['id'] for x in client.get('/api/v1/projects').json()['items']]

def test_tile_contains_survey_pixels(client,tmp_path):
    import math
    from PIL import Image
    p,j=submit(client,{'Ortho/test.tif':raster(tmp_path)})
    layer=client.get(f'/api/v1/projects/{p}/layers').json()['items'][0]
    z=16;lon=75.016;lat=22.984
    x=int((lon+180)/360*2**z)
    y=int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**z)
    r=client.get(f'/api/v1/layers/{layer["id"]}/tiles/{z}/{x}/{y}.png')
    pixels=np.asarray(Image.open(io.BytesIO(r.content)))
    assert pixels[:,:,3].max()==255
    assert pixels[:,:,0].max()==120

def test_worker_persistent_queue(client,tmp_path,monkeypatch):
    from app.worker import run_one
    monkeypatch.setenv('AEROVIEW_DATA',str(tmp_path))
    p=client.post('/api/v1/projects',json={'name':'Worker test'}).json()['id']
    r=client.post(f'/api/v1/projects/{p}/imports',content=archive({'DTM/test.tif':raster(tmp_path)}),headers={'Content-Type':'application/zip'})
    j=r.json()['jobId']
    assert run_one()
    assert client.get('/api/v1/processing-jobs/'+j).json()['status']=='completed'
    assert not run_one()

def test_bad_zip_worker_failure(client,tmp_path,monkeypatch):
    from app.worker import run_one
    monkeypatch.setenv('AEROVIEW_DATA',str(tmp_path))
    p=client.post('/api/v1/projects',json={'name':'Bad ZIP'}).json()['id']
    r=client.post(f'/api/v1/projects/{p}/imports',content=b'not a zip',headers={'Content-Type':'application/zip'})
    assert run_one()
    assert client.get('/api/v1/processing-jobs/'+r.json()['jobId']).json()['status']=='failed'
