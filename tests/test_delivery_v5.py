import io, zipfile, sys, os, shutil, importlib, json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture()
def client(tmp_path,monkeypatch):
    dat=tmp_path/'data';dat.mkdir();(dat/'uploads').mkdir()
    shutil.copy2(ROOT/'data/bigbang.sqlite3',dat/'bigbang.sqlite3')
    shutil.copy2(ROOT/'data/uploads/BIG_BANG_ORIGINAL_300.zip',dat/'uploads/BIG_BANG_ORIGINAL_300.zip')
    monkeypatch.setenv('BIGBANG_DATA_DIR',str(dat));monkeypatch.setenv('ADMIN_PASSWORD','TestPass123#')
    monkeypatch.setenv('SESSION_SECRET','a'*64);monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    sys.path.insert(0,str(ROOT))
    for mod in ['db','v3_routes','v5_routes','app']:
        sys.modules.pop(mod,None)
    app=importlib.import_module('app').app
    c=TestClient(app)
    resp=c.post('/api/login',json={'password':'TestPass123#'});assert resp.status_code==200,resp.text
    yield c
    c.close()


def test_domains_on_one_line(client):
    blob='https://mirtvixo.com/ https://gervuno.com/ https://laxvito.com/ https://kivluto.com/ https://soltvixo.com/'
    r=client.post('/api/v5/domains/parse',json={'text':blob});assert r.status_code==200,r.text
    assert r.json()['count']==5
    assert r.json()['domains'][0]=='mirtvixo.com'
    r=client.post('/api/v5/domains/parse',json={'text':'a.com,a.com,c.com,d.com,e.com'})
    assert r.status_code==400


def test_company_zip_and_delivery_export(client):
    import fitz
    pdf=fitz.open(); page=pdf.new_page()
    page.insert_text((40,80),'Company Name: Example Merchant LLC',fontsize=11)
    page.insert_text((40,100),'EIN: 11-1234567',fontsize=11)
    page.insert_text((40,120),'Registered Address: 123 Test Ave, Test City, USA',fontsize=11)
    page.insert_text((40,140),'Country: United States',fontsize=11)
    page.insert_text((40,160),'Phone: +1 202 555 0118',fontsize=11)
    mem=io.BytesIO()
    with zipfile.ZipFile(mem,'w') as z:z.writestr('company/irs.pdf',pdf.tobytes())
    r=client.post('/api/v5/intake/company-zip',files={'file':('company_documents.zip',mem.getvalue(),'application/zip')})
    assert r.status_code==200,r.text
    parsed=r.json();assert parsed['fields']['name']=='Example Merchant LLC'
    assert parsed['file_count']==1
    p=client.post('/api/v3/auto/preview',json={
         'intake_draft_id':parsed['draft_id'],'entity_id':None,'entity':parsed['fields'],
         'domains':['mirtvixo.com','gervuno.com','laxvito.com','kivluto.com','soltvixo.com'],
         'email_prefix':'service'})
    assert p.status_code==200,p.text
    ids=p.json()['items']
    assert len({i['style_family'] for i in ids})==5
    assert len({i['product_family'] for i in ids})==5
    r=client.post('/api/v3/auto/commit',json={'proposal_id':p.json()['proposal_id']})
    assert r.status_code==200,r.text
    batch=r.json()['batch_id']
    summary=client.get('/api/v5/deployments/'+batch)
    assert summary.status_code==200,summary.text
    assert len(summary.json()['stores'])==5
    audit=client.post('/api/v5/deployments/'+batch+'/audit?with_ai=false',json={})
    assert audit.status_code==200,audit.text
    assert audit.json()['store_count']==5
    assert audit.json()['files']==60
    export=client.get('/api/v5/deployments/'+batch+'/export.zip')
    assert export.status_code==200,export.text[:500]
    with zipfile.ZipFile(io.BytesIO(export.content)) as z:
      names=[x for x in z.namelist() if not x.endswith('/')]
      assert len(names)==60
      for domain in ['mirtvixo.com','gervuno.com','laxvito.com','kivluto.com','soltvixo.com']:
        subset=[x for x in names if x.startswith(domain+'/')]
        assert len(subset)==12,(domain,subset)
        assert len([x for x in subset if '/商品文件夹/' in x])==1
        assert len([x for x in subset if '/装修文件夹/' in x])==4
        assert len([x for x in subset if '/条款文件夹/' in x])==7
        company=z.read(next(x for x in subset if x.endswith('07_COMPANY_PROFILE.txt'))).decode('utf8')
        assert 'Example Merchant LLC' in company
        assert 'service@'+domain in company
        assert '[[' not in company
        footer=z.read(next(x for x in subset if x.endswith('04-footer.liquid'))).decode('utf8')
        assert 'Example Merchant LLC' in footer
        assert 'service@'+domain in footer
        docx=next(x for x in subset if x.endswith('.docx'))
        from docx import Document
        content='\n'.join(p.text for p in Document(io.BytesIO(z.read(docx))).paragraphs)
        assert 'Example Merchant LLC' in content
        assert '[[' not in content
    # New app retains an accessible download history after page refresh.
    history=client.get('/api/v5/deployments').json()
    assert any(x['id']==batch for x in history)
    return
