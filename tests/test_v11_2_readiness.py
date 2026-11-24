"""Run alone in an isolated temporary data directory, no mutations to bundled data."""
from __future__ import annotations
import os,sys,shutil,tempfile,zipfile,io,json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def app_client():
 tmp=Path(tempfile.mkdtemp(prefix='bigbang-v112-test-'))
 (tmp/'uploads').mkdir()
 shutil.copy2(ROOT/'data'/'bigbang.sqlite3',tmp/'bigbang.sqlite3')
 shutil.copy2(ROOT/'data'/'ASSET_MANIFEST.json',tmp/'ASSET_MANIFEST.json')
 os.environ['BIGBANG_DATA_DIR']=str(tmp)
 os.environ['ADMIN_PASSWORD']='v112-test-secret'
 os.environ['SESSION_SECRET']='wxy1234567890___wxy1234567890___wxy1234567890___'
 sys.path.insert(0,str(ROOT))
 import app
 client=TestClient(app.app)
 assert client.post('/api/login',json={'password':'v112-test-secret'}).status_code==200
 yield client,tmp
 shutil.rmtree(tmp,ignore_errors=True)

def test_readiness_initial_and_auth(app_client):
 c,tmp=app_client
 d=c.get('/api/v11_2/diagnostics');assert d.status_code==200,d.text
 data=d.json();assert data['version']=='11.4.3-V35';assert data['can_use_local_workflows']
 assert data['counts']['stores']==300 and data['counts']['templates']==300
 assert c.get('/quality').status_code==200
 assert '系统体检' not in c.get('/quality').text  # title is 运行准备中心

def test_asset_inspection_and_no_mutation(app_client):
 c,tmp=app_client
 result=c.get('/api/v11_2/assets/scan');assert result.status_code==200,result.text[:300]
 r=result.json();assert r['summary']['package_count']==300 and r['summary']['file_count']==6900
 assert r['summary']['structure_errors']==0
 assert r['summary']['shopify_files']==3600 and r['summary']['shopline_files']==3300
 assert r['summary']['sku_rows']>10000 and r['summary']['amazon_image_rows']>0
 assert c.get('/api/v11_2/platforms').json()['platforms']['shopline']['theme_conversion']=='not_implemented'

def test_future_zip_only_previews(app_client):
 c,tmp=app_client
 original=ROOT/'resources/BIG_BANG_V35_DUAL_600.zip'
 out=c.post('/api/v11_2/assets/preview',files={'file':('future.zip',original.read_bytes(),'application/zip')})
 assert out.status_code==200,out.text[:500]
 data=out.json();assert not data['safe_to_auto_activate']
 assert len(data['same_paths'])==300 and len(data['unchanged_paths'])==300 and not data['changed_paths'] and not data['new_paths'] and not data['missing_paths']
 with open(tmp/'ASSET_MANIFEST.json',encoding='utf-8') as f:raw=json.load(f)
 assert raw['source_zip_sha256']==data['current_sha256']

def test_bad_upload_rejected(app_client):
 c,_=app_client
 x=c.post('/api/v11_2/assets/preview',files={'file':('broken.zip',b'not a zip','application/zip')})
 assert x.status_code==400

def test_backup_is_private_and_restorable(app_client):
 _,tmp=app_client
 from backup_before_update import make_backup
 path=tmp.parent/'test-backup-v112.zip'
 result=make_backup(path)
 assert result['files']>0
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  assert 'data/bigbang.sqlite3' in z.namelist()
  assert '.env' not in ' '.join(z.namelist())
  m=json.loads(z.read('BACKUP_MANIFEST.json'))
  assert not m['env_included']
 path.unlink()

def test_old_template_append_is_guarded(app_client):
 c,_=app_client
 x=c.post('/api/templates/import',files={'file':('next-300.zip',b'fake','application/zip')})
 assert x.status_code==409 and '300' in x.text

def test_resource_change_requires_preview(tmp_path):
 from resource_doctor import compare_archives
 def make(path,change):
  with zipfile.ZipFile(path,'w') as z:
   for i in range(4):z.writestr(f'Store1/Store1/Theme/0{i+1}-block.liquid','<p>hello</p>')
   for i in range(7):z.writestr(f'Store1/Store1/Policies/policy{i+1}.txt',f'Policy {i+1} '+('changed' if change and i==2 else 'original'))
   z.writestr('Store1/Store1/Products/items.csv', 'Title,SKU,Product image URL\nSample,ST-001,https://example.com/img.jpg\n')
 a=tmp_path/'old.zip';b=tmp_path/'new.zip'
 make(a,False);make(b,True)
 x=compare_archives(a,b,expected=1)
 assert len(x['same_paths'])==1 and len(x['changed_paths'])==1
 assert not x['unchanged_paths'] and not x['safe_to_auto_activate']

def test_resource_drift_stops_startup(tmp_path,monkeypatch):
 import bootstrap_v13 as m
 candidate=tmp_path/'candidate.zip'
 with zipfile.ZipFile(candidate,'w') as z:z.writestr('probe.txt','changed')
 manifest=tmp_path/'manifest.json'
 manifest.write_text(json.dumps({'version':'BIG_BANG_V35','source_zip_sha256':'00000000'}),encoding='utf-8')
 monkeypatch.setattr(m,'RESOURCE',candidate)
 monkeypatch.setattr(m,'MANIFEST',manifest)
 monkeypatch.setattr(m,'DEST',tmp_path/'not-touch.zip')
 with pytest.raises(RuntimeError,match='SHA256'):
  m.bootstrap()
 assert not (tmp_path/'not-touch.zip').exists()
