"""An old delivery with a person's name and missing shared phone must fail closed."""
from __future__ import annotations
import os,json,io,zipfile,shutil,sys,importlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def prepared(tmp_path,monkeypatch):
    target=tmp_path/'data';(target/'uploads').mkdir(parents=True)
    shutil.copy2(ROOT/'data/bigbang.sqlite3',target/'bigbang.sqlite3')
    shutil.copy2(ROOT/'data/uploads/BIG_BANG_ORIGINAL_300.zip',target/'uploads/BIG_BANG_ORIGINAL_300.zip')
    monkeypatch.setenv('BIGBANG_DATA_DIR',str(target));monkeypatch.setenv('ADMIN_PASSWORD','ExamplePass123!')
    monkeypatch.setenv('SESSION_SECRET','T'*64)
    sys.path.insert(0,str(ROOT))
    for mod in ('app','db','v3_routes','v5_routes','bulk_routes'):
        sys.modules.pop(mod,None)
    from app import app
    from db import db,now
    import uuid
    sid='ENTITY-LEGACY-EXAMPLE'
    bid='DEPLOY-LEGACY-EXAMPLE'
    domains=['store-a.example.com','store-b.example.com','store-c.example.com','store-d.example.com','store-e.example.com']
    with db() as c:
        c.execute('INSERT INTO entities VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (sid,'ENT-LEGACY','个人姓名','','China','错误个人住址','','',5,'待核验',now(),now()))
        stores=c.execute('SELECT id FROM stores ORDER BY code LIMIT 5').fetchall()
        for idx,store in enumerate(stores):
            store_id=store[0]
            c.execute('UPDATE stores SET entity_id=?,status=? WHERE id=?',(sid,'待部署',store_id))
            c.execute('INSERT INTO store_domains VALUES(?,?,?,?)',('DOM-EX-'+str(idx),store_id,domains[idx],now()))
            c.execute('INSERT INTO store_contacts VALUES(?,?,?,?)',(store_id,'service@'+domains[idx],'待验证',now()))
        c.execute('INSERT INTO deployment_batches VALUES(?,?,?,?,?)',(bid,sid,json.dumps([x[0] for x in stores]),'[]',now()))
    client=TestClient(app)
    assert client.post('/api/login',json={'password':'ExamplePass123!'}).status_code==200
    yield client,bid
    client.close()


def test_legacy_bad_entity_blocked_then_repaired(prepared):
    c,batch=prepared
    audit=c.post(f'/api/v5/deployments/{batch}/audit?with_ai=false',json={})
    assert audit.status_code==200,audit.text
    assert audit.json()['issue_counts']['error']>0
    assert c.get(f'/api/v5/deployments/{batch}/export.zip').status_code==409
    bad=c.put(f'/api/v5/deployments/{batch}/entity',json={
        'name':'Demo Merchant LLC','address':'123 Example Avenue, USA','phone':'+1 918940945','confirmed':True})
    assert bad.status_code==409
    good=c.put(f'/api/v5/deployments/{batch}/entity',json={
        'name':'Demo Merchant LLC','address':'123 Example Avenue, USA','phone':'+1 202 555 0118','confirmed':True})
    assert good.status_code==200,good.text
    again=c.post(f'/api/v5/deployments/{batch}/audit?with_ai=false',json={})
    assert again.status_code==200,again.text
    assert again.json()['issue_counts'].get('error',0)==0,[(x['code'],x['message']) for x in again.json()['issues'] if x['type']=='error'][:5]
    exported=c.get(f'/api/v5/deployments/{batch}/export.zip')
    assert exported.status_code==200,exported.text[:200]
    with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
        names=[n for n in z.namelist() if not n.endswith('/')]
        assert len(names)==60
        for n in names:
            if n.endswith(('.txt','.liquid','.csv')):
                text=z.read(n).decode('utf8',errors='replace')
                assert '个人姓名' not in text
                assert 'Demo Merchant LLC' in text if n.endswith(('04-footer.liquid','07_COMPANY_PROFILE.txt')) else True
            if n.endswith('07_COMPANY_PROFILE.txt'):
                assert '+1 202 555 0118' in z.read(n).decode('utf8')
