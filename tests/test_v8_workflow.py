"""V8 isolated API tests, sourced only from the user's preloaded 300 resources."""
import io, os, json, sys, zipfile, shutil, importlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture()
def api_and_db(tmp_path,monkeypatch):
    dst=tmp_path/'data';dst.mkdir();(dst/'uploads').mkdir()
    shutil.copy2(ROOT/'data/bigbang.sqlite3',dst/'bigbang.sqlite3')
    z=ROOT/'data/uploads/BIG_BANG_ORIGINAL_300.zip'
    try:(dst/'uploads'/z.name).symlink_to(z)
    except OSError:shutil.copy2(z,dst/'uploads'/z.name)
    monkeypatch.setenv('BIGBANG_DATA_DIR',str(dst))
    monkeypatch.setenv('ADMIN_PASSWORD','V8-test-private!')
    monkeypatch.setenv('SESSION_SECRET','8'*64)
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    sys.path.insert(0,str(ROOT))
    for module in ['db','v3_routes','v5_routes','v7_routes','v8_routes','app']:
        sys.modules.pop(module,None)
    app=importlib.import_module('app').app
    client=TestClient(app)
    assert client.get('/api/v8/intake/FAKE-1234567890/sources').status_code==401
    assert client.post('/api/login',json={'password':'V8-test-private!'}).status_code==200
    yield client,importlib.import_module('db')
    client.close()


def test_preflight_and_source_evidence(api_and_db):
    api,database=api_and_db
    fields={'name':'Riverlight Goods LLC','address':'4 Example Avenue, Seattle, WA 98101, USA','phone':''}
    check=api.post('/api/v8/intake/check',json={'fields':fields,'domains':'https://a.example.com/ https://b.example.com/ https://c.example.com/ https://d.example.com/'})
    assert check.status_code==200
    assert not check.json()['can_preview']
    assert any('电话' in x for x in check.json()['errors'])
    fields['phone']='+1 202 555 0112'
    check=api.post('/api/v8/intake/check',json={'fields':fields,'domains':'https://a.example.com/https://b.example.com/ https://c.example.com/ https://d.example.com/'})
    assert check.status_code==200,check.text
    assert check.json()['can_preview'] and len(check.json()['domains'])==4
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('company.txt','Legal Company Name: Riverlight Goods LLC\nRegistered Address: 4 Example Avenue, Seattle, WA 98101, USA\nSupport Phone: +1 202 555 0112')
        z.writestr('identity.jpg',b'not a real jpeg')
    with database.db() as c:
        c.execute('''INSERT INTO intake_drafts(id, filename, storage_name, method, extracted_json,status,created_at)
          VALUES(?,?,?,?,?,?,?)''',('INTAKE-1234567890','company.zip','test-source.zip','本地源文件',
          json.dumps(fields),'待确认',database.now()))
    (database.DATA/'uploads'/'test-source.zip').write_bytes(data.getvalue())
    result=api.get('/api/v8/intake/INTAKE-1234567890/sources')
    assert result.status_code==200,result.text
    assert result.json()['sources']['name'][0]['file']=='company.txt'
    assert any(x['file']=='identity.jpg' for x in result.json()['files'])
    assert result.json()['sources']['phone'][0]['matches_current']


def test_selective_reroll_is_atomic_and_preserves_other_four(api_and_db):
    api,database=api_and_db
    payload={'entity':{'name':'V8 Riverlight Commerce LLC','country':'United States',
              'address':'4 Example Avenue, Seattle, WA 98101, USA','phone':'+1 202 555 0159'},
             'domains':[f'v8store{i}.example.com' for i in range(1,6)]}
    pre=api.post('/api/v3/auto/preview',json=payload)
    assert pre.status_code==200,pre.text
    original=pre.json()
    chosen=original['items'][1]
    reroll=api.post('/api/v8/proposals/'+original['proposal_id']+'/reroll-one',json={'store_id':chosen['store_id']})
    assert reroll.status_code==200,reroll.text
    outcome=reroll.json()
    assert outcome['proposal_id']!=original['proposal_id']
    assert outcome['items'][1]['store_id']!=chosen['store_id']
    assert outcome['items'][1]['domain']==chosen['domain']
    for i in (0,2,3,4):
        assert outcome['items'][i]['store_id']==original['items'][i]['store_id']
        assert outcome['items'][i]['support_email']==original['items'][i]['support_email']
    assert len({x['style_family'] for x in outcome['items']})==5
    assert len({x['product_family'] for x in outcome['items']})==5
    assert api.post('/api/v3/auto/commit',json={'proposal_id':original['proposal_id']}).status_code==409
    new=api.post('/api/v3/auto/commit',json={'proposal_id':outcome['proposal_id']})
    assert new.status_code==200,new.text
    gate=api.get('/api/v7/deployments/'+new.json()['batch_id']+'/gate')
    assert gate.status_code==200 and gate.json()['allowed']
    rel=api.post('/api/v7/deployments/'+new.json()['batch_id']+'/prepare')
    assert rel.status_code==200,rel.text
    with zipfile.ZipFile(io.BytesIO(api.get(rel.json()['download_url']).content)) as z:
        assert len([x for x in z.namelist() if not x.endswith('/')])==60


def test_reroll_rejects_wrong_store_without_mutating_preview(api_and_db):
    api,database=api_and_db
    p=api.post('/api/v3/auto/preview',json={'entity':{'name':'Test Stable Enterprises LLC','address':'10 Example Road, Boston, MA 02108, USA','phone':'+1 202 555 0171'},
      'domains':[f'v8stable{i}.example.com' for i in range(1,6)]})
    assert p.status_code==200,p.text
    pid=p.json()['proposal_id']
    bad=api.post('/api/v8/proposals/'+pid+'/reroll-one',json={'store_id':'STR-DOESNOTEXIST'})
    assert bad.status_code==404
    with database.db() as c:
        entry=database.row(c.execute('SELECT status FROM auto_allocation_proposals WHERE id=?',(pid,)))
    assert entry['status']=='待确认'
