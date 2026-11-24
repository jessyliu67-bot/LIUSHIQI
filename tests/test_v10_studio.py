import os,sys,shutil,tempfile,zipfile,json,time,importlib,hashlib
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

@pytest.fixture(scope='module')
def env():
 root=Path(__file__).resolve().parents[1]
 tmp=Path(tempfile.mkdtemp(prefix='bb_v10_smoke_'))
 (tmp/'uploads').mkdir()
 shutil.copy2(root/'data/bigbang.sqlite3',tmp/'bigbang.sqlite3')
 os.environ['BIGBANG_DATA_DIR']=str(tmp)
 os.environ['ADMIN_PASSWORD']='testnotreal'
 os.environ['SESSION_SECRET']='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
 os.environ.pop('DEEPSEEK_API_KEY',None)
 sys.path.insert(0,str(root))
 import app
 client=TestClient(app.app)
 assert client.post('/api/login',json={'password':'testnotreal'}).status_code==200
 yield tmp,client,app
 shutil.rmtree(tmp,ignore_errors=True)

def test_v12_sources(env):
 tmp,c,app=env
 r=c.get('/api/v10/studio/STORE-001')
 assert r.status_code==200,r.text
 doc=r.json()
 assert len(doc['files'])==12
 assert [f['category'] for f in doc['files']].count('Policies')==7
 assert [f['category'] for f in doc['files']].count('Theme')==4
 assert doc['stats']['csv_rows']>0
 assert any(x['rule']=='PRODUCT-UNVERIFIED' for x in doc['quick_issues'])
 assert c.get('/api/v10/studio/STORE-001/file/5').json()['docx']
 assert 'Offline composition' in c.get('/api/v10/studio/STORE-001/preview').text

def test_edit_and_archive_immutable(env):
 tmp,c,app=env
 f=c.get('/api/v10/studio/STORE-001/file/0').json()
 original=f['content']; new=original+'\n/* TEST DRAFT ONLY */\n'
 r=c.post('/api/v10/studio/STORE-001/proposal',json={'file_index':0,'revised_text':new,'expected_hash':f['hash'],'reason':'test'})
 assert r.status_code==200,r.text
 pid=r.json()['id']
 a=c.post('/api/v10/studio/STORE-001/proposal/'+pid+'/approve')
 assert a.status_code==200,a.text
 assert c.get('/api/v10/studio/STORE-001/file/0').json()['content']==new
 original_path=tmp/'uploads/BIG_BANG_V35_SHOPIFY_300.zip'
 with zipfile.ZipFile(original_path) as z:assert z.read('模板1/模板1短袖T恤/装修文件/01-header.liquid').decode('utf-8-sig')==original
 r=c.get('/api/v10/studio/STORE-001/draft.zip')
 assert r.status_code==200
 with zipfile.ZipFile(__import__('io').BytesIO(r.content)) as z:
  assert len(z.namelist())==12
  assert all(x.startswith(('Products/','Theme/','Policies/')) for x in z.namelist())
  assert b'TEST DRAFT' in z.read('Theme/01-header.liquid')

def test_no_key_cannot_claim_ai(env):
 tmp,c,app=env
 r=c.post('/api/v10/studio/STORE-001/audit',json={'use_ai':True})
 assert r.status_code==409
 r=c.post('/api/v10/studio/STORE-001/audit',json={'use_ai':False,'check_live_images':False})
 assert r.status_code==200
 aid=r.json()['audit_id']; result=None
 for i in range(35):
  result=c.get('/api/v10/studio/STORE-001/audit/'+aid).json()
  if result['status'] in ('审核完成','检测失败','部分检查失败'):break
  time.sleep(.1)
 assert result['status']=='审核完成',result
 assert result['results']['coverage']['policies_analyzed_by_ai']==0
 assert not result['results']['coverage']['ai_complete']
 r=c.post('/api/v10/studio/STORE-001/release',json={'acknowledge_unverified':True})
 assert r.status_code==409

def test_autofill_from_provenance(env):
 tmp,c,app=env
 with app.db() as db:
  sid=db.execute('select id from stores where code=?',('STORE-002',)).fetchone()[0]
  db.execute('INSERT INTO entities VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',('ENT-TEST','ENT-T','Confirmed Test Company LLC','12345','US','100 Verified Example Ave, NYC, USA','+12125550123','owner@example.com',5,'待核验',app.now(),app.now()))
  db.execute('UPDATE stores SET entity_id=? WHERE id=?',('ENT-TEST',sid))
  db.execute('INSERT INTO store_domains VALUES(?,?,?,?)',('DOM-T',sid,'example-test.com',app.now()))
  db.execute('INSERT INTO store_contacts VALUES(?,?,?,?)',(sid,'support@example-test.com','待验证',app.now()))
 r=c.post('/api/v10/studio/STORE-002/autofill')
 assert r.status_code==200,r.text
 ids=[x['id'] for x in r.json()['proposals']]
 assert len(ids)>=7
 approved=c.post('/api/v10/studio/STORE-002/proposals/approve-all',json=ids)
 assert approved.status_code==200,approved.text
 cdocx=c.get('/api/v10/studio/STORE-002/file/5').json()
 assert 'Confirmed Test Company LLC' in cdocx['content']
 assert '[[SUPPORT_EMAIL]]' not in cdocx['content']
 after=c.get('/api/v10/studio/STORE-002')
 assert after.status_code==200
 assert len(after.json()['files'])==12

def test_ai_coverage_mock(env,monkeypatch):
 tmp,c,app=env
 import v10_studio
 invocations=[]
 def mock_call(system,content,model='deepseek-flash',image_url=None):
  invocations.append((content[:90],image_url))
  return {'issues':[],'reviewed_scope':'mock-only','limitations':'mock-only'}, {'prompt_tokens':15,'completion_tokens':10}
 monkeypatch.setattr(v10_studio,'call_deepseek',mock_call)
 aid='AUD-MOCK-001'
 with app.db() as db:db.execute('INSERT INTO studio_audits VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,'STORE-003','deepseek','deepseek-flash','排队中',0,'{}','',app.now(),app.now()))
 v10_studio.audit_worker(aid,'STORE-003',True,False,False)
 r=c.get('/api/v10/studio/STORE-003/audit/'+aid)
 assert r.status_code==200,r.text
 result=r.json()['results'];coverage=result['coverage']
 assert coverage['policies_analyzed_by_ai']==7
 assert coverage['theme_analyzed_by_ai']==4
 assert len(invocations)==12 # 7 policies + 4 theme + catalog sample
 assert coverage['image_rights_verified']==False
 assert coverage['official_app_lovin_approval']==False
