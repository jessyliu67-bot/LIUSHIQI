"""One-click, source-grounded policy/Shopify-footer rendering.

Business details come from assigned, operator-maintained records, never LLM inference.
Source assets remain immutable; outputs are derived only. These checks do not
certify legal compliance, address authenticity or image licensing.
"""
from __future__ import annotations
import io
import re
from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath
from urllib.parse import urlsplit
from docx import Document
from entity_guard import entity_issues, CJK

POLICY_TOKEN = re.compile(r'\[\[([A-Z][A-Z0-9_]*)\]\]')
FOOTER_SENTINEL = re.compile(r'REPLACE_WITH_[A-Z0-9_]+')
DOMAIN_RE = re.compile(r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$', re.I)
EMAIL_RE = re.compile(r'^[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$')
REQUIRED = ('LEGAL_COMPANY_NAME','REGISTERED_BUSINESS_ADDRESS','SUPPORT_PHONE','SUPPORT_EMAIL','STORE_URL','STORE_NAME')

@dataclass
class PolicyContext:
    company:str
    address:str
    phone:str
    email:str
    domain:str
    store_name:str
    effective_date:str
    service_hours:str=''
    response_time:str=''
    additional_info:str=''

    def tokens(self):
        return {
            'LEGAL_COMPANY_NAME':self.company,
            'REGISTERED_BUSINESS_ADDRESS':self.address,
            'SUPPORT_PHONE':self.phone,
            'SUPPORT_EMAIL':self.email,
            'STORE_URL':'https://'+self.domain,
            'STORE_NAME':self.store_name,
            'EFFECTIVE_DATE':self.effective_date,
        }

def from_store(s, *, settings=None):
    settings=settings or {}
    domain=str(s.get('domain') or '').strip().lower()
    domain=re.sub(r'^https?://','',domain).strip('/').split('/')[0]
    domain=domain.removeprefix('www.')
    return PolicyContext(
        company=str(s.get('company') or s.get('name') or s.get('entity_name') or '').strip(),
        address=str(s.get('address') or '').strip(),
        phone=str(s.get('phone') or '').strip(),
        email=str(s.get('support_email') or '').strip(),
        domain=domain,
        store_name=domain,  # factual storefront identifier, not an invented brand
        effective_date=date.today().isoformat(),
        service_hours=str(settings.get('service_hours') or '').strip(),
        response_time=str(settings.get('response_time') or '').strip(),
        additional_info=str(settings.get('additional_info') or '').strip(),
    )

def preflight(c):
    msgs=entity_issues({'name':c.company,'address':c.address,'phone':c.phone})
    if not c.domain or not DOMAIN_RE.fullmatch(c.domain):msgs.append('缺少有效店铺域名')
    if not c.email or not EMAIL_RE.fullmatch(c.email):msgs.append('缺少有效的本店独立客服邮箱')
    if CJK.search(c.email+c.domain):msgs.append('邮箱或域名含中文，无法用于英文交付')
    for key,val in c.tokens().items():
        if key!='EFFECTIVE_DATE' and ('[[' in val or 'REPLACE_WITH_' in val):msgs.append(f'{key} 仍然是模板占位值')
    return list(dict.fromkeys(msgs))

def _updates(c, previous_tokens=None):
    values=c.tokens(); old=previous_tokens or {}
    updates=[]
    for k,new in values.items():
        before=old.get(k)
        if before and new and before!=new:
            updates.append((before,new))
    return sorted(updates,key=lambda x:len(x[0]),reverse=True)

def substitute_text(text,c,previous_tokens=None):
    values=c.tokens()
    text=POLICY_TOKEN.sub(lambda m: values.get(m.group(1),m.group(0)),text)
    for old,new in _updates(c,previous_tokens):text=text.replace(old,new)
    return text

def _all_paragraphs(doc):
    for p in doc.paragraphs:yield p
    for tab in doc.tables:
        for row in tab.rows:
            for cell in row.cells:
                for p in cell.paragraphs:yield p
    for section in doc.sections:
        for segment in (section.header,section.footer):
            for p in segment.paragraphs:yield p
            for tab in segment.tables:
                for row in tab.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:yield p

def _replace_runs_preserving_styles(p,c,previous_tokens=None):
    """Update tokens even when Word split their XML text across runs."""
    runs=list(p.runs)
    if not runs:return 0
    whole=''.join(r.text for r in runs)
    matches=[]
    for hit in POLICY_TOKEN.finditer(whole):
        new=c.tokens().get(hit.group(1))
        if new is not None:matches.append((hit.start(),hit.end(),new))
    # Prior automatic values may already be filled. Update only values
    # written by a previous one-click delivery, preserving unrelated edits.
    for old,new in _updates(c,previous_tokens):
        for hit in re.finditer(re.escape(old),whole):
            if not any(a<hit.end() and hit.start()<b for a,b,_ in matches):
                matches.append((hit.start(),hit.end(),new))
    if not matches:return 0
    chunks=[r.text for r in runs]
    for begin,end,new in sorted(matches,reverse=True):
        cursor=0;first=None;last=None;offsets=[]
        for i,t in enumerate(chunks):
            offsets.append((cursor,cursor+len(t)))
            if first is None and cursor<=begin<cursor+len(t):first=i
            if last is None and cursor<end<=cursor+len(t):last=i
            cursor+=len(t)
        if first is None or last is None:continue
        if first==last:
            a,b=offsets[first];chunks[first]=chunks[first][:begin-a]+new+chunks[first][end-a:]
        else:
            a,_=offsets[first];b,_=offsets[last]
            chunks[first]=chunks[first][:begin-a]+new
            for i in range(first+1,last):chunks[i]=''
            chunks[last]=chunks[last][end-b:]
    for r,t in zip(runs,chunks):
        if r.text!=t:r.text=t
    return len(matches)

def render_docx(blob,c,previous_tokens=None):
    doc=Document(io.BytesIO(blob))
    n=0
    for p in _all_paragraphs(doc):n+=_replace_runs_preserving_styles(p,c,previous_tokens)
    if not n:return blob
    b=io.BytesIO();doc.save(b);return b.getvalue()

FOOTER_ASSIGN={
    'legal_name':'company',
    'registered_address':'address',
    'support_email':'email',
    'support_phone':'phone',
    'service_hours':'service_hours',
    'response_time':'response_time',
    'additional_information':'additional_info',
}

def render_footer(text,c):
    # Replace the seven original Liquid assignments only, never alter layout/images.
    replacements=0
    for suffix,attr in FOOTER_ASSIGN.items():
        val=getattr(c,attr)
        if re.search(r"[%{}]|\\",val):
            raise ValueError(f'页脚配置值 {suffix} 包含Liquid或不安全转义字符')
        safe=val.replace("'",'\\\'')
        pat=re.compile(r"(\{%\s*assign\s+[a-zA-Z][\w]*_"+re.escape(suffix)+r"\s*=\s*)'(?:\\.|[^'])*'",re.I)
        text,count=pat.subn(lambda m:m.group(1)+"'"+safe+"'",text,count=1)
        if suffix in ('legal_name','registered_address','support_email','support_phone') and count!=1:
            raise ValueError('页脚缺少主体必填配置：'+suffix)
        replacements+=count
    # Existing conditionals previously displayed raw placeholders. Now use plain
    # blank checks; the named, verified fields are guaranteed before packaging.
    text=text.replace(" contains 'REPLACE_WITH_'",' == blank')
    # Ensure a false branch never exposes the old template string.
    text=FOOTER_SENTINEL.sub('',text)
    text=re.sub(r'Replace the seven\s+\s*values below with verified business information\.',
                'Business information is sourced from the assigned company record.',text,flags=re.I)
    # Optional promises: if no source evidence, omit their visual elements, not invent hours.
    if not c.service_hours:
        text=re.sub(r'<div class="contact-line"><span>Hours</span><span>\{\{\s*[^}]*_service_hours\s*\|\s*escape\s*\}\}</span></div>','',text,flags=re.I)
    if not c.response_time:
        text=re.sub(r'<div class="contact-line"><span>Response time</span><span>\{\{\s*[^}]*_response_time\s*\|\s*escape\s*\}\}</span></div>','',text,flags=re.I)
    if not c.additional_info:
        text=re.sub(r'<div><dt>Additional business information</dt><dd>\{\{\s*[^}]*_additional_information\s*\|\s*escape\s*\}\}</dd></div>','',text,flags=re.I)
    return text,replacements

def render_file(filename,blob,c,previous_tokens=None):
    low=filename.lower()
    if low.endswith('.docx'):
        return render_docx(blob,c,previous_tokens)
    raw=blob.decode('utf-8-sig')
    if low.endswith('.liquid') and 'footer' in PurePosixPath(filename).name.lower():
        return render_footer(raw,c)[0].encode('utf-8')
    if low.endswith('.txt'):
        return substitute_text(raw,c,previous_tokens).encode('utf-8')
    return blob

def validate_rendered(filename,blob,require_english=True):
    low=filename.lower()
    if low.endswith('.docx'):
        doc=Document(io.BytesIO(blob))
        text='\n'.join(p.text for p in _all_paragraphs(doc))
    elif low.endswith(('.txt','.liquid','.csv')):
        text=blob.decode('utf-8-sig','replace')
    else:return []
    problems=[]
    if (low.endswith(('.txt','.docx','.liquid')) and
        (POLICY_TOKEN.search(text) or FOOTER_SENTINEL.search(text))):problems.append('存在未替换的模板变量')
    if require_english and CJK.search(text):problems.append('文件正文存在中文')
    if '\ufffd' in text:problems.append('文件文本解码包含替换字符')
    return problems
