"""V7 isolated integration: safety gate, source comparison, English ZIP, version rollback.
   Requires the preloaded original assets. Never touches the user's active DB.
"""
import io, json, os, zipfile, shutil, sys, importlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture()
def system(tmp_path,monkeypatch):
    storage=tmp_path/'bb-data';storage.mkdir();(storage/'uploads').mkdir()
    shutil.copy2(ROOT/'data/bigbang.sqlite3',storage/'bigbang.sqlite3')
    src=ROOT/'data/uploads/BIG_BANG_ORIGINAL_300.zip'
    try:(storage/'uploads'/src.name).symlink_to(src)
    except OSError:shutil.copy2(src,storage/'uploads'/src.name)
    monkeypatch.setenv('BIGBANG_DATA_DIR',str(storage))
    monkeypatch.setenv('ADMIN_PASSWORD','UnitTestV7!')
    monkeypatch.setenv('SESSION_SECRET','Q'*64)
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    sys.path.insert(0,str(ROOT))
    for key in ['db','v3_routes','v5_routes','v7_routes','app']:
        sys.modules.pop(key,None)
    app=importlib.import_module('app').app
    api=TestClient(app)
    # No unauthenticated export or company record access.
    assert api.get('/api/v7/deployments/FAKE/gate').status_code==401
    assert api.post('/api/login',json={'password':'UnitTestV7!'}).status_code==200
    yield api,importlib.import_module('db'),storage
    api.close()


def test_release_gate_english_archive_history_and_phone_block(system):
    api,database,storage=system
    payload={'entity':{'name':'V7 Example Commerce LLC','registration_no':'QA-00007',
            'country':'USA','address':'200 Example Street, Portland, Oregon, USA',
            'phone':'+1 202 555 0118'},
            'domains':[f'test-v7-{i}.example.com' for i in range(1,6)]}
    proposal=api.post('/api/v3/auto/preview',json=payload)
    assert proposal.status_code==200,proposal.text
    plan=proposal.json();codes=[x['store_code'] for x in plan['items']]
    visual=api.post('/api/v7/visual/compare',json={'store_codes':codes})
    assert visual.status_code==200
    assert visual.json()['strict_structure_pass']
    assert len({x['style_family'] for x in visual.json()['items']})==5
    assert len({x['product_family'] for x in visual.json()['items']})==5
    assert all(x['hero_image_source'].startswith('https://cdn.shopify.com/') for x in visual.json()['items'])
    commit=api.post('/api/v3/auto/commit',json={'proposal_id':plan['proposal_id']})
    assert commit.status_code==200,commit.text
    batch_id=commit.json()['batch_id']
    gate=api.get(f'/api/v7/deployments/{batch_id}/gate').json()
    assert gate['allowed'] and gate['total_files']==60
    diffs=api.get(f'/api/v7/deployments/{batch_id}/diffs')
    assert diffs.status_code==200 and len(diffs.json()['items'])>=30
    created=api.post(f'/api/v7/deployments/{batch_id}/prepare')
    assert created.status_code==200,created.text
    first=created.json()
    assert first['integrity']['file_count']==60
    downloaded=api.get(first['download_url'])
    assert downloaded.status_code==200
    saved_bytes=downloaded.content
    with zipfile.ZipFile(io.BytesIO(saved_bytes)) as package:
        names=[x for x in package.namelist() if not x.endswith('/')]
        assert len(names)==60
        assert all(x.isascii() for x in names)
        for domain in payload['domains']:
            files=[x for x in names if x.startswith(domain+'/')]
            assert sum('/Products/' in x for x in files)==1
            assert sum('/Theme/' in x for x in files)==4
            assert sum('/Policies/' in x for x in files)==7
            assert domain+'/Products/products.csv' in files
            policy=package.read(domain+'/Policies/07_COMPANY_PROFILE.txt').decode('utf-8')
            assert 'V7 Example Commerce LLC' in policy
            assert '+1 202 555 0118' in policy
    again=api.post(f'/api/v7/deployments/{batch_id}/prepare')
    assert again.status_code==200 and again.json()['reused']
    versions=api.get(f'/api/v7/deployments/{batch_id}/versions').json()
    assert len(versions)==1
    with database.db() as conn:
        conn.execute('UPDATE entities SET phone=? WHERE id=?',('+1 918940945',commit.json()['entity_id']))
    invalid=api.get(f'/api/v7/deployments/{batch_id}/gate').json()
    assert not invalid['allowed']
    assert any('10位' in i['message'] for i in invalid['blockers'])
    assert api.post(f'/api/v7/deployments/{batch_id}/prepare').status_code==409
    # The old immutable package remains downloadable, rather than disappearing.
    assert api.get(first['download_url']).content==saved_bytes
    with database.db() as conn:
        conn.execute('UPDATE entities SET phone=? WHERE id=?',('+1 202 555 0165',commit.json()['entity_id']))
    second=api.post(f'/api/v7/deployments/{batch_id}/prepare')
    assert second.status_code==200 and not second.json()['reused']
    assert second.json()['sha256']!=first['sha256']
    assert len(api.get(f'/api/v7/deployments/{batch_id}/versions').json())==2
    assert api.get(first['download_url']).content==saved_bytes
    # No test record should leak into packaged V7 baseline: fixture is external.
    assert storage!=ROOT/'data'
