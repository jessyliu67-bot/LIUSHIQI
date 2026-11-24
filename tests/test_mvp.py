"""Smoke tests for V1, run with pytest -q after running setup.py."""
import io, os, zipfile, tempfile, shutil
from pathlib import Path
from fastapi.testclient import TestClient
# All tests use an isolated copy. Never mutate the shipped 300-store database.
_SOURCE=Path(__file__).resolve().parents[1]
_TEST_DATA=Path(tempfile.mkdtemp(prefix='bigbang-tests-'))
shutil.copy2(_SOURCE/'data'/'bigbang.sqlite3',_TEST_DATA/'bigbang.sqlite3')
(_TEST_DATA/'uploads').mkdir(exist_ok=True)
os.environ['BIGBANG_DATA_DIR']=str(_TEST_DATA)
os.environ.setdefault('ADMIN_PASSWORD','local-unit-test-password')
os.environ.setdefault('SESSION_SECRET','local-test-session-secret-0123456789-abcd')
from app import app
from audit_engine import normalize_host
from app import discover_templates

def test_normalize_domain():
    assert normalize_host(' HTTPS://Example.COM/ ') == 'example.com'
    for text in ['127.0.0.1','http://foo.com/path','www.example.com:443','localhost']:
        try: normalize_host(text)
        except ValueError:pass
        else:raise AssertionError('domain accepted: '+text)

def test_template_scan_structure():
    names=[]
    for i in range(1,301):
        for cat in ('商品CSV','装修文件','七个条款文件'):
            names.append(f'模板{(i-1)//15+1}/模板{i}-{i%15}/{cat}/file.txt')
    assert len(discover_templates(names))==300

def test_login_and_entity_api():
    c=TestClient(app)
    assert c.get('/api/entities').status_code==401
    assert c.post('/api/login',json={'password':'wrong'}).status_code==401
    assert c.post('/api/login',json={'password':os.environ['ADMIN_PASSWORD']}).status_code==200
    id=c.post('/api/entities',json={'name':'Pytest Test Company','capacity':2}).json()['id']
    assert any(e['id']==id for e in c.get('/api/entities').json())
    sample='PYTEST-'+os.urandom(4).hex().upper()
    host=sample.lower()+'.example.com'
    a=c.post('/api/stores',json={'code':sample+'-1','entity_id':id,'domain':host})
    assert a.status_code==200,a.text
    b=c.post('/api/stores',json={'code':sample+'-2','entity_id':id,'domain':host})
    assert b.status_code==400
    assert c.get('/api/export/stores.csv').status_code==200

def test_audit_engine_without_network(monkeypatch):
    import audit_engine as ae
    from db import db, uid
    c=TestClient(app)
    c.post('/api/login',json={'password':os.environ['ADMIN_PASSWORD']})
    domain='audit-'+os.urandom(4).hex()+'.example.com'
    eid=c.post('/api/entities',json={'name':'Audit Test Corporation','email':'audit@example.com'}).json()['id']
    sid=c.post('/api/stores',json={'code':'AUDIT-'+os.urandom(4).hex().upper(),'entity_id':eid,'domain':domain}).json()['id']
    def fake_fetch(url,host):
        assert host==domain
        is_home=url.rstrip('/').endswith(domain)
        label=url.split('/')[-1]
        txt=('Welcome to Audit Test Corporation audit@example.com' if is_home
             else 'Audit Test Corporation audit@example.com '+label+' ' + 'This is policy text for automated test. '*10)
        return {'url':url,'status':404 if label=='privacy-policy' else 200,
                'text':txt,'title':'Audit Test Corporation','anchors':[],
                'images':[],'footer_text':'Audit Test Corporation', 'hash':'0'*64}
    monkeypatch.setattr(ae,'safe_fetch',fake_fetch)
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    aid=uid('AUD')
    with db() as con:
        con.execute('INSERT INTO audits(id,store_id,mode,status) VALUES (?,?,?,?)',(aid,sid,'ai','排队中'))
    ae.perform_audit(aid)
    data=c.get('/api/audits/'+aid).json()
    assert data['summary']['pages_checked']==8
    assert data['summary']['critical']>=1
    assert 'AI模式未执行' in data['error']
    assert data['status']=='部分完成·需处理'
    assert len(data['evidence'])==8
