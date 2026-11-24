"""Read-only V9 dossier tests against bundled 300 source combinations."""
from __future__ import annotations
import os
from pathlib import Path
os.environ.setdefault('ADMIN_PASSWORD','TestOnlyLocalAdmin!')
os.environ.setdefault('SESSION_SECRET','testonlynonproductionsecret' * 4)
from fastapi.testclient import TestClient
from app import app
from db import db,row,rows,DATA

client=TestClient(app)
def auth():
    client.post('/api/login',json={'password':os.environ['ADMIN_PASSWORD']})

def first():
    with db() as c:
        return row(c.execute('SELECT * FROM templates ORDER BY code LIMIT 1'))

def test_v9_requires_auth():
    test=TestClient(app)
    r=test.get('/api/v9/assets/'+first()['id'])
    assert r.status_code==401

def test_v9_complete_dossier():
    auth()
    r=client.get('/api/v9/assets/'+first()['id'])
    assert r.status_code==200,r.text[:400]
    d=r.json()
    assert d['template_code']=='TPL-001'
    assert len(d['files'])==12
    assert len(d['theme'])==4
    assert len(d['policies'])==7
    assert len(d['products'])>=1
    assert d['preview_type'].endswith('not a Shopify-rendered screenshot')

def test_v9_separate_original_file_download():
    auth()
    r=client.get('/api/v9/assets/'+first()['id']+'/file/0')
    assert r.status_code==200 and len(r.content)>100
    assert r.headers['content-disposition'].startswith('attachment')
    assert client.get('/api/v9/assets/'+first()['id']+'/file/999').status_code==404

def test_v9_preview_references_actual_headline():
    auth()
    r=client.get('/api/v9/assets/'+first()['id']+'/preview')
    assert r.status_code==200
    assert b'A different perspective on tees.' in r.content
    assert 'SAMEORIGIN'==r.headers['x-frame-options']
    assert b'<iframe' not in r.content

def test_v9_data_preserved():
    with db() as c:
        t=c.execute('SELECT COUNT(*) FROM templates').fetchone()[0]
        s=c.execute('SELECT COUNT(*) FROM stores').fetchone()[0]
    assert t==300 and s==300
