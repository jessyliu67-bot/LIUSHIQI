"""Isolated API tests against V35 original assets, no external AI request."""
import io,os,shutil,sys,tempfile,zipfile,hashlib,json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def ctx():
    tmp=Path(tempfile.mkdtemp(prefix='bigbang-v11-'))
    (tmp/'uploads').mkdir()
    shutil.copy2(ROOT/'data'/'bigbang.sqlite3',tmp/'bigbang.sqlite3')
    os.environ['BIGBANG_DATA_DIR']=str(tmp)
    os.environ['ADMIN_PASSWORD']='v11_testing_password'
    os.environ['SESSION_SECRET']='abCDefghijkLMNopqrstuVwxYz23456789012345678901234567890'
    os.environ.pop('DEEPSEEK_API_KEY',None)
    sys.path.insert(0,str(ROOT))
    import app
    c=TestClient(app.app)
    assert c.post('/api/login',json={'password':'v11_testing_password'}).status_code==200
    yield (tmp,c,app)
    shutil.rmtree(tmp,ignore_errors=True)

def assign(a,code='STORE-001',phone='+1 313 998 6971'):
    with a.db() as db:
        sid=db.execute('select id from stores where code=?',(code,)).fetchone()[0]
        db.execute('INSERT OR REPLACE INTO entities VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',('ENT-V11','ENT-TESTV11','Confirmed Example Trading LLC','US987654','US','100 North Main Street, City, NY, USA',phone,'owner@example.com',8,'待核验',a.now(),a.now()))
        db.execute('UPDATE stores SET entity_id=? WHERE id=?',('ENT-V11',sid))
        db.execute('INSERT OR REPLACE INTO store_domains VALUES(?,?,?,?)',('DOMAIN-V11',sid,'sample-shop.test',a.now()))
        db.execute('INSERT OR REPLACE INTO store_contacts VALUES(?,?,?,?)',(sid,'service@sample-shop.test','待验证',a.now()))

def test_missing_data_is_blocked_without_changes(ctx):
    t,c,a=ctx
    x=c.post('/api/v11/studio/STORE-001/one-click')
    assert x.status_code==409,x.text
    assert '主体' in x.text
    with a.db() as db:
        assert db.execute('select count(*) from studio_drafts where store_code=?',('STORE-001',)).fetchone()[0]==0
    assign(a,phone='+1 918940945')
    x=c.post('/api/v11/studio/STORE-001/one-click')
    assert x.status_code==409 and '+1' in x.text
    with a.db() as db:
        assert db.execute('select count(*) from policy_delivery_releases').fetchone()[0]==0

def test_one_click_seven_policies_footer_and_zip(ctx):
    t,c,a=ctx
    assign(a)
    rawzip=ROOT/'resources/BIG_BANG_V35_DUAL_600.zip'
    h0=hashlib.sha256(rawzip.read_bytes()).hexdigest()
    x=c.post('/api/v11/studio/STORE-001/one-click')
    assert x.status_code==200,x.text[:600]
    d=x.json();assert d['policy_files']==7 and d['file_count']==12
    assert d['modified_count']==8,d
    assert '待' in d['status'] and not d['verification']['official_approval']
    r=c.get(d['download_url']);assert r.status_code==200,r.text[:100] if r.status_code!=200 else ''
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        names=z.namelist()
        assert len(names)==12 and z.testzip() is None
        assert sum(n.startswith('Policies/') for n in names)==7
        assert sum(n.startswith('Theme/') for n in names)==4
        assert sum(n.startswith('Products/') for n in names)==1
        for p in names:
            b=z.read(p)
            if p.endswith('.docx'):
                from docx import Document
                txt='\n'.join(q.text for q in Document(io.BytesIO(b)).paragraphs)
            else: txt=b.decode('utf-8')
            assert '[[' not in txt and 'REPLACE_WITH_' not in txt,(p,txt[:120])
            assert not any('\u4e00'<=v<='\u9fff' for v in txt),p
            if p.startswith('Policies/'):
                assert 'Confirmed Example Trading LLC' in txt
                assert 'service@sample-shop.test' in txt
        footer=z.read('Theme/04-footer.liquid').decode('utf-8')
        assert '100 North Main Street, City, NY, USA' in footer
        assert '+1 313 998 6971' in footer
        assert '<span>Hours</span>' not in footer
        assert '<span>Response time</span>' not in footer
    assert hashlib.sha256(rawzip.read_bytes()).hexdigest()==h0
    assert c.get('/api/v11/studio/STORE-001/deliveries').json()['releases'][0]['id']==d['id']

def test_rerun_idempotent_and_field_change_version(ctx):
    t,c,a=ctx
    first=c.post('/api/v11/studio/STORE-001/one-click').json()
    assert first['reused'] is True
    assert first['version']==1
    with a.db() as db:
        db.execute('UPDATE entities SET phone=? WHERE id=?',('+1 646 555 0188','ENT-V11'))
    new=c.post('/api/v11/studio/STORE-001/one-click')
    assert new.status_code==200,new.text
    result=new.json()
    assert result['version']==2
    assert result['modified_count']>=1
    with zipfile.ZipFile(io.BytesIO(c.get(result['download_url']).content)) as z:
        assert '+1 646 555 0188' in z.read('Policies/06_CONTACT_INFORMATION.txt').decode()
    assert c.get(first['download_url']).status_code==200

def test_five_store_workbench_uses_shared_policy_renderer(ctx):
    t,c,a=ctx
    from v5_routes import build_package
    with a.db() as db:
        templates=a.rows(db.execute('SELECT s.id,s.code,t.code template_code,t.archive_path,t.inner_path FROM stores s JOIN templates t ON t.id=s.template_id ORDER BY s.code LIMIT 5'))
    stores=[]
    for n,it in enumerate(templates,1):
        stores.append({**it,'domain':f'shop{n}.example.test','support_email':f'service@shop{n}.example.test'})
    batch={'entity_name':'Confirmed Example Trading LLC','address':'100 North Main Street, City, NY, USA',
           'phone':'+1 313 998 6971','email':'owner@example.test','country':'US',
           'registration_no':'TEST123','stores':stores,'settings':{}}
    out,report=build_package(batch)
    assert len(report)==5
    assert all(len(s['issues'])>0 for s in report) # honest external authorization warnings
    assert not any(p['type']=='error' for s in report for p in s['issues'])
    with zipfile.ZipFile(out) as z:
        assert len([n for n in z.namelist() if not n.endswith("/")])==60
        for s in report:
            assert s['file_count']==12
            assert len([n for n in z.namelist() if n.startswith(s['folder']+'/') and not n.endswith('/')])==12
