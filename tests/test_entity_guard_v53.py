"""V5.3 entity preflight tests. All company details are synthetic."""
from __future__ import annotations
import io, zipfile
from entity_guard import phone_issue, entity_issues, chinese_credit_code_valid
from v5_routes import extract_document_zip, footer_verified_patch


def test_phone_validation_and_company_name():
    assert '10位' in phone_issue('+1 918940945')
    assert phone_issue('+1 202 555 0118') == ''
    assert '缺少' in phone_issue('')
    assert entity_issues({'name':'A Person','address':'somewhere','phone':'+1 202 555 0118'})
    assert entity_issues({'name':'Demo Trading LLC','address':'123 Main St, USA','phone':'+1 202 555 0118'})==[]
    assert chinese_credit_code_valid('91440106MAEJ70NR5F')
    assert not chinese_credit_code_valid('91440106MAEJ7ONR5F')


def test_txt_in_zip_has_priority_over_identity_photo():
    info='''**Operated by:** Demo Trading LLC\n**Business License Entity:** Demo Trading LLC\n**Customer Service:** +1 202 555 0118\n**Registered Address:** 12 Example Road, London, United Kingdom\n**Email:** service@你的域名\n'''
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w') as z:
        z.writestr('evidence/bad_name.jpeg',b'fake-image')
        z.writestr('evidence/verified-text.txt',info)
    f,_,notes,n,conflict=extract_document_zip('c.zip',raw.getvalue())
    assert f['name']=='Demo Trading LLC'
    assert f['phone']=='+1 202 555 0118'
    assert f['address'].startswith('12 Example Road')
    assert not f['email']
    assert not conflict


def test_overwrite_earlier_bad_footer_legal_identity():
    original="{% assign s16_legal_name = 'Wrong Individual' %}\n{% assign s16_registered_address = 'Wrong Address' %}\n{% assign s16_support_phone = 'REPLACE_WITH_CUSTOMER_SERVICE_PHONE' %}\n"
    corrected,changes,missing=footer_verified_patch(original,{'name':'Demo Trading LLC','address':'123 Main St, USA','phone':'+1 202 555 0118','support_email':'service@example.com'})
    assert 'Wrong Individual' not in corrected
    assert 'Demo Trading LLC' in corrected
    assert '123 Main St' in corrected
    assert '+1 202 555 0118' in corrected
    assert not any(x in missing for x in ('name','address','phone'))
