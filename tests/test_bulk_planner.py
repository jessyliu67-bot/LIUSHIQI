"""Run with isolated BIGBANG_DATA_DIR to leave bundled 300 assets unchanged."""
import csv,io,uuid,zipfile
from fastapi.testclient import TestClient
from app import app
from db import db
from auto_match import check_diversity
import os

def make_csv(entries):
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=['company_name','registration_no','country','address','phone','store_count','domains'])
    writer.writeheader();writer.writerows(entries)
    return out.getvalue().encode('utf-8-sig')

def test_batch_csv_preview_commit_preserves_templates():
    cl=TestClient(app)
    assert cl.post('/api/login',json={'password':os.environ['ADMIN_PASSWORD']}).status_code==200
    with db() as c:
        templates_before=c.execute('SELECT COUNT(*),SUM(length(checksum)) FROM templates').fetchone()
        unassigned_before=c.execute('SELECT COUNT(*) FROM stores WHERE entity_id IS NULL').fetchone()[0]
    suffix=uuid.uuid4().hex[:7]
    rows=[{'company_name':f'Bulk Entity {suffix} Alpha LLC','registration_no':f'XX-{suffix}-1','country':'US','address':'Example address','phone':'+1 202 555 0118','store_count':'4','domains':f'a-{suffix}.example.com;b-{suffix}.example.com'},
          {'company_name':f'Bulk Entity {suffix} Beta LLC','registration_no':f'XX-{suffix}-2','country':'US','address':'Example address','phone':'+1 202 555 0118','store_count':'3','domains':f'c-{suffix}.example.com'},
          {'company_name':f'Bulk Entity {suffix} Gamma LLC','registration_no':f'XX-{suffix}-3','country':'US','address':'Example address','phone':'+1 202 555 0118','store_count':'0','domains':''}]
    res=cl.post('/api/v3/bulk/intake',files={'files':('companies.csv',make_csv(rows),'text/csv')})
    assert res.status_code==200,res.text
    items=res.json()['items'];batch_id=res.json()['batch_id']
    assert len(items)==3 and items[0]['count']==4
    request={'batch_id':batch_id,'rows':[{'draft_id':x['draft_id'],'included':x['included'],'fields':x['fields'],'count':x['count'],'domains':x['domains']} for x in items]}
    # Before saving, the backend must validate domains across legal entities.
    bad={'batch_id':batch_id,'rows':[dict(x) for x in request['rows']]}
    bad['rows'][1]=dict(bad['rows'][1],domains=rows[0]['domains'].split(';')[0])
    invalid=cl.post('/api/v3/bulk/preview',json=bad).json()
    assert invalid['can_commit'] is False and any('相同域名' in x for x in invalid['errors'])
    preview=cl.post('/api/v3/bulk/preview',json=request)
    assert preview.status_code==200,preview.text
    result=preview.json();assert result['can_commit'],result
    assert len(result['items'])==3
    assert sum(len(x['items']) for x in result['items'])==7
    for entity in result['items']:
        it=entity['items'];assert len({x['style_family'] for x in it})==len(it)
        assert len({x['product_family'] for x in it})==len(it)
    all_codes=[s['store_code'] for e in result['items'] for s in e['items']]
    assert len(all_codes)==len(set(all_codes))
    committed=cl.post('/api/v3/bulk/commit',json={'proposal_id':result['proposal_id']})
    assert committed.status_code==200,committed.text
    assert committed.json()['entity_count']==3 and committed.json()['store_count']==7
    assert cl.post('/api/v3/bulk/commit',json={'proposal_id':result['proposal_id']}).status_code==409
    with db() as c:
        assert c.execute('SELECT COUNT(*),SUM(length(checksum)) FROM templates').fetchone()==templates_before
        assert c.execute('SELECT COUNT(*) FROM stores WHERE entity_id IS NULL').fetchone()[0]==unassigned_before-7
        for e in c.execute('SELECT id FROM entities WHERE name LIKE ?',('%'+suffix+'%',)):
            records=[dict(r) for r in c.execute('SELECT s.code,t.inner_path FROM stores s JOIN templates t ON s.template_id=t.id WHERE s.entity_id=?',(e['id'],))]
            assert not check_diversity(records)


def test_strict_large_batch_rejects_insufficient_distinct_layouts():
    cl=TestClient(app)
    assert cl.post('/api/login',json={'password':os.environ['ADMIN_PASSWORD']}).status_code==200
    suffix=uuid.uuid4().hex[:7]
    inp=[{'company_name':f'Large Batch {suffix} {i} LLC','registration_no':f'{suffix}-{i}', 'country':'US','address':'122 Test Street', 'phone':'+1 202 555 0118', 'store_count':'4','domains':''} for i in range(60)]
    upload=cl.post('/api/v3/bulk/intake',files={'files':('many.csv',make_csv(inp),'text/csv')})
    assert upload.status_code==200,upload.text
    obj=upload.json()
    request={'batch_id':obj['batch_id'],'rows':[{'draft_id':x['draft_id'],'included':True,'fields':x['fields'],'count':x['count'],'domains':x['domains']} for x in obj['items']]}
    res=cl.post('/api/v3/bulk/preview',json=request)
    assert res.status_code==200,res.text
    d=res.json();assert not d['can_commit']
    assert any('严格装修差异无法满足' in x or '资源不足' in x for x in d['errors'])


def test_documents_zip_extracts_into_editable_batch():
    import fitz
    cl=TestClient(app)
    assert cl.post('/api/login',json={'password':os.environ['ADMIN_PASSWORD']}).status_code==200
    doc=fitz.open();page=doc.new_page();page.insert_text((50,80),'Company Name: Archive Example LLC\nRegistration No: EX-2026-1234\nRegistered Address: 42 Sample Avenue, London')
    raw=doc.tobytes();doc.close()
    container=io.BytesIO()
    with zipfile.ZipFile(container,'w') as z:
        z.writestr('company_001.pdf',raw)
        z.writestr('notes.txt',b'ignored')
    out=cl.post('/api/v3/bulk/intake',files={'files':('registrations.zip',container.getvalue(),'application/zip')})
    assert out.status_code==200,out.text
    entry=out.json()['items'][0]
    assert entry['filename']=='company_001.pdf' and entry['draft_id']
    assert 'Archive Example LLC' in entry['fields']['name']
    assert '主体' not in entry['method'] or entry['method']
