"""Connectivity UX/API smoke tests. All model responses mocked; no external cost."""
import importlib
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]

class FakeReply:
    def __init__(self, code=200, content='BIG_BANG_OK'):
        self.status_code=code
        self.content=content
    def json(self):
        return {'choices':[{'message':{'content':self.content}}],
                'usage':{'prompt_tokens':19,'completion_tokens':5,'total_tokens':24}}

class FakeHttp:
    def __init__(self, code=200, reply='BIG_BANG_OK'):
        self.code,self.reply=code,reply
        self.calls=[]
    def post(self, url, headers, json):
        self.calls.append((url,headers,json))
        return FakeReply(self.code,self.reply)

@pytest.fixture()
def setup_app(tmp_path, monkeypatch):
    dat=tmp_path/'data';dat.mkdir();(dat/'uploads').mkdir()
    monkeypatch.setenv('BIGBANG_DATA_DIR',str(dat))
    monkeypatch.setenv('ADMIN_PASSWORD','pass-for-diagnostics-tests')
    monkeypatch.setenv('SESSION_SECRET','test-5-2-session-secret-' + 'a'*50)
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    monkeypatch.setenv('DEEPSEEK_MODEL','deepseek-flash')
    sys.path.insert(0,str(ROOT))
    for mod in ('app','db','v3_routes','v5_routes','bulk_routes','deepseek_diagnostics'):
        sys.modules.pop(mod,None)
    api=importlib.import_module('app')
    diag=importlib.import_module('deepseek_diagnostics')
    client=TestClient(api.app)
    yield client,diag
    client.close()


def test_reject_unauthenticated_and_missing_key(setup_app):
    client,diag=setup_app
    assert client.get('/api/deepseek/status').status_code==401
    assert client.post('/api/deepseek/test',json={}).status_code==401
    assert client.post('/api/login',json={'password':'pass-for-diagnostics-tests'}).status_code==200
    data=client.get('/api/deepseek/status').json()
    assert data['configured'] is False and data['tested'] is False
    response=client.post('/api/deepseek/test',json={})
    assert response.status_code==200
    assert response.json()['state']=='missing_key'
    assert response.json()['ok'] is False
    assert 'DEEPSEEK_API_KEY' not in str(data) or 'key' not in str(data).lower()


def test_authentic_response_marks_connected_and_does_not_send_private_content(setup_app,monkeypatch):
    client,diag=setup_app
    client.post('/api/login',json={'password':'pass-for-diagnostics-tests'})
    monkeypatch.setenv('DEEPSEEK_API_KEY','sk-SECRET-NEVER-RETURN')
    fake=FakeHttp()
    original=diag._probe
    monkeypatch.setattr(diag,'_probe',lambda http_client=None: original(fake))
    response=client.post('/api/deepseek/test',json={})
    data=response.json()
    assert data['ok'] is True and data['state']=='connected'
    assert data['reply']=='BIG_BANG_OK'
    assert data['http_status']==200
    state=client.get('/api/deepseek/status').json()
    assert state['tested'] is True and state['last_test']['ok'] is True
    assert 'SECRET' not in str(state) and 'SECRET' not in response.text
    assert fake.calls[0][0]=='https://api.deepseek.com/chat/completions'
    assert fake.calls[0][2]['messages'][0]['content'].endswith('BIG_BANG_OK and nothing else.')


def test_invalid_key_and_model_switch_invalidate_old_success(setup_app,monkeypatch):
    client,diag=setup_app
    client.post('/api/login',json={'password':'pass-for-diagnostics-tests'})
    monkeypatch.setenv('DEEPSEEK_API_KEY','some-key')
    original=diag._probe
    monkeypatch.setattr(diag,'_probe',lambda http_client=None: original(FakeHttp(code=401)))
    result=client.post('/api/deepseek/test',json={}).json()
    assert result['state']=='invalid_key' and not result['ok']
    assert 'some-key' not in str(result)
    monkeypatch.setenv('DEEPSEEK_MODEL','deepseek-v4-pro')
    assert client.get('/api/deepseek/status').json()['tested'] is False
