"""Regression tests for missing Tesseract and explicit AI consent."""
import io, json, sys, os, shutil, importlib, types
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def png():
    f=io.BytesIO();Image.new('RGB',(50,25),'white').save(f,format='PNG');return f.getvalue()


def test_missing_ocr_engine_never_leaks_tesseract_not_found(monkeypatch):
    import v3_services as s
    monkeypatch.setattr(s,'_detect_tesseract',lambda:'')
    s._local_rapidocr_engine.cache_clear()
    monkeypatch.setitem(sys.modules,'rapidocr',None)
    with pytest.raises(s.OCRUnavailableError) as exc:
        s.extract_local_text(png(),'.png')
    msg=str(exc.value)
    assert 'TesseractNotFoundError' not in msg
    assert '修复OCR识别.bat' in msg


def test_local_python_ocr_without_tesseract(monkeypatch):
    import v3_services as s
    monkeypatch.setattr(s,'_detect_tesseract',lambda:'')
    s._local_rapidocr_engine.cache_clear()
    class FakeRapidOCR:
        def __call__(self,img):
            assert img.shape==(25,50,3)
            return types.SimpleNamespace(txts=('名称: 示例贸易有限公司','统一社会信用代码: 911234567890123456','注册地址: 广州市测试路1号'))
    monkeypatch.setitem(sys.modules,'rapidocr',types.SimpleNamespace(RapidOCR=lambda:FakeRapidOCR()))
    text,method=s.extract_local_text(png(),'.png')
    assert '示例贸易有限公司' in text
    fields=s.parse_fields(text)
    assert fields['name']=='示例贸易有限公司'
    assert fields['registration_no']=='911234567890123456'
    assert method=='图片本地OCR'


@pytest.fixture()
def client(tmp_path,monkeypatch):
    dat=tmp_path/'data';dat.mkdir();(dat/'uploads').mkdir()
    shutil.copy2(ROOT/'data/bigbang.sqlite3',dat/'bigbang.sqlite3')
    monkeypatch.setenv('BIGBANG_DATA_DIR',str(dat));monkeypatch.setenv('ADMIN_PASSWORD','TestPass123#');monkeypatch.setenv('SESSION_SECRET','a'*64)
    for mod in ['app','db','v3_routes','v5_routes']:
        sys.modules.pop(mod,None)
    app=importlib.import_module('app').app
    c=TestClient(app)
    assert c.post('/api/login',json={'password':'TestPass123#'}).status_code==200
    yield c
    c.close()


def test_user_explicitly_grants_ai_consent(client,monkeypatch):
    import v3_services, v5_routes
    monkeypatch.setattr(v3_services,'_detect_tesseract',lambda:'')
    v3_services._local_rapidocr_engine.cache_clear()
    monkeypatch.setitem(sys.modules,'rapidocr',None)
    response=client.post('/api/v3/intake/extract',files={'file':('registration.png',png(),'image/png')})
    assert response.status_code==200,response.text
    obj=response.json()
    assert obj['draft_id']
    assert 'TesseractNotFoundError' not in obj.get('warning','')
    draft=obj['draft_id']
    assert client.post('/api/v5/intake/ai-recognize',json={'draft_id':draft,'consent':False}).status_code==400
    resp=client.post('/api/v5/intake/ai-recognize',json={'draft_id':draft,'consent':True})
    assert resp.status_code==400 and 'API Key' in resp.json()['detail']
    monkeypatch.setenv('DEEPSEEK_API_KEY','test_not_a_real_key')
    def fake_extract(data,ext,text):
        assert data.startswith(b'\x89PNG')
        return {'name':'Demo Company','registration_no':'DEMO123456','country':'','address':'','phone':'','email':''}
    monkeypatch.setattr(v5_routes,'ai_extract_image',fake_extract)
    resp=client.post('/api/v5/intake/ai-recognize',json={'draft_id':draft,'consent':True})
    assert resp.status_code==200,resp.text
    assert resp.json()['fields']['name']=='Demo Company'
    assert resp.json()['sent_to_ai'] is True
    assert resp.json()['documents_sent']==1
