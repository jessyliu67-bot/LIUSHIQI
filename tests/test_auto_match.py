"""Integration checks for strict random assignment. Uses isolated test DB."""
import os,uuid
from fastapi.testclient import TestClient
from app import app
from db import db
from auto_match import check_diversity

def test_auto_preview_and_commit():
    api=TestClient(app)
    assert api.post('/api/login',json={'password':os.environ['ADMIN_PASSWORD']}).status_code==200
    suffix=uuid.uuid4().hex[:8]
    ds=[f'bb-{suffix}-{i}.example.org' for i in range(5)]
    payload={'entity':{'name':f'QA Allocation {suffix} Ltd','registration_no':f'QA-{suffix}','address':'120 Example Street, New York, USA','phone':'+1 202 555 0118'},'domains':ds}
    preview=api.post('/api/v3/auto/preview',json=payload)
    assert preview.status_code==200,preview.text
    plan=preview.json();assigned=plan['items']
    assert len(assigned)==5
    assert len({x['style_family'] for x in assigned})==5
    assert len({x['product_family'] for x in assigned})==5
    assert len({x['category'] for x in assigned})==5
    assert len({x['template_group'] for x in assigned})==5
    assert set(x['domain'] for x in assigned)==set(ds)
    assert all(x['support_email']=='service@'+x['domain'] for x in assigned)
    illegal=api.post('/api/v3/auto/preview',json={**payload,'domains':[ds[0],ds[0],ds[2],ds[3]]})
    assert illegal.status_code==409
    committed=api.post('/api/v3/auto/commit',json={'proposal_id':plan['proposal_id']})
    assert committed.status_code==200,committed.text
    assert committed.json()['assigned']==5
    assert api.post('/api/v3/auto/commit',json={'proposal_id':plan['proposal_id']}).status_code==409
    with db() as c:
        eid=committed.json()['entity_id']
        rec=[dict(x) for x in c.execute('SELECT s.code,t.inner_path FROM stores s JOIN templates t ON s.template_id=t.id WHERE s.entity_id=?',(eid,))]
        assert len(rec)==5 and not check_diversity(rec)

def test_category_restriction_is_stricter_than_naming():
    from auto_match import identify_template
    assert identify_template('模板1/模板1体恤')['product_family']==identify_template('模板2/模板2Polo衫')['product_family']
    assert identify_template('模板2/模板2长袖T恤')['style_family']==identify_template('模板11/模板11棒球帽')['style_family']
