"""BIG BANG V8: evidence-first intake and selective strict proposal reroll.

No product/layout recombination. No automatic Shopify publication. The source ZIPs
are immutable, and all preview changes require user confirmation before commit.
"""
from __future__ import annotations

import datetime
import io
import json
import re
import secrets
import zipfile
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auto_match import identify_template, check_diversity
from db import DATA, db, now, row, rows, uid
from entity_guard import entity_issues, english_source_fields, phone_issue
from v3_services import clean_domain, parse_fields
from v5_routes import parse_domain_blob

FIELDS = ('name', 'registration_no', 'country', 'address', 'phone', 'email')
LABELS = {'name':'公司名称','registration_no':'登记编号','country':'国家或地区',
          'address':'注册地址','phone':'主体共用电话','email':'公司邮箱'}

class CheckRequest(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict)
    domains: str = Field(default='', max_length=12000)

class RerollRequest(BaseModel):
    store_id: str = Field(min_length=8, max_length=80)


def _summary_fields(values, domains):
    f = {k:str(values.get(k) or '').strip()[:600] for k in FIELDS}
    errors = entity_issues(f)
    warnings=[]
    if not f['registration_no']:warnings.append('尚未提供登记编号；公司登记真实性未核验')
    if not f['email']:warnings.append('未提供公司邮箱；每店独立客服邮箱仍需真实开通')
    try:
        hosts = parse_domain_blob(domains) if domains.strip() else []
    except ValueError as ex:
        hosts=[];errors.append('域名输入有误：'+str(ex))
    if not 4 <= len(hosts) <= 5:
        errors.append(f'智能分配需要4–5个不同域名，当前识别到{len(hosts)}个')
    statuses=[]
    for k in FIELDS:
        value=f[k]
        if k == 'name': problem = any('公司' in x or '名称' in x for x in errors)
        elif k == 'address': problem = any('地址' in x for x in errors)
        elif k == 'phone': problem = bool(phone_issue(value))
        else: problem=False
        statuses.append({'key':k,'label':LABELS[k], 'value':value,
                         'status':'需处理' if problem else ('已填写 · 待核实' if value else '未提供'),
                         'required':k in ('name','address','phone')})
    return {'fields':statuses,'errors':errors,'warnings':warnings,'domains':hosts,
            'store_count':len(hosts),'can_preview':not errors,
            'note':'基本格式核对，不代替登记真实性、电话接通能力或图片授权审核'}


def _source_evidence(draft_id):
    with db() as c:
        draft=row(c.execute('SELECT id, filename, storage_name,method,extracted_json,status FROM intake_drafts WHERE id=?',(draft_id,)))
    if not draft:raise HTTPException(404,detail='没有找到这次上传的主体资料')
    filename=draft['storage_name']
    if PurePosixPath(filename).name != filename:
        raise HTTPException(409,detail='主体资料路径不合法')
    stored=DATA/'uploads'/filename
    if not stored.is_file():raise HTTPException(404,detail='原始主体资料文件缺失')
    extracted=json.loads(draft['extracted_json'] or '{}')
    items=[];sources={k:[] for k in FIELDS}
    def examine(name, ext, data):
        origin=PurePosixPath(name).name
        if ext not in ('.txt','.docx','.pdf'):
            items.append({'file':origin,'type':'图片' if ext in ('.png','.jpg','.jpeg') else '未分析文件',
                          'fields':[],'note':'未再次运行OCR；请对照原始文件人工确认'})
            return
        try:
            if ext=='.txt':
                # Existing source notes may be UTF-8 or GB18030.
                from v3_services import decode_company_txt
                content=decode_company_txt(data)
                parsed={**parse_fields(content), **english_source_fields(content)}
            elif ext=='.docx':
                from docx import Document
                doc=Document(io.BytesIO(data));content='\n'.join([p.text for p in doc.paragraphs]+[
                  p.text for table in doc.tables for rr in table.rows for cell in rr.cells for p in cell.paragraphs])
                parsed=parse_fields(content)
            else:
                import fitz
                pdf=fitz.open(stream=data,filetype='pdf')
                content='\n'.join(page.get_text() for page in list(pdf)[:5]);parsed=parse_fields(content)
            found=[]
            for k in FIELDS:
                val=str(parsed.get(k) or '').strip()
                if val:
                    found.append(k)
                    sources[k].append({'file':origin,'value':val[:180],
                       'matches_current':val.casefold()==str(extracted.get(k) or '').strip().casefold()})
            items.append({'file':origin,'type':ext.lstrip('.').upper(), 'fields':found,
                         'note':'提取出的资料需对照原件，不能据此认为主体已通过登记核验'})
        except Exception:
            items.append({'file':origin,'type':ext.lstrip('.').upper(),'fields':[],
                          'note':'无法可靠读取文本，不将该文件猜测为主体来源'})
    suffix=stored.suffix.lower()
    if suffix=='.zip':
        with zipfile.ZipFile(stored) as z:
            entries=[x for x in z.infolist() if not x.is_dir()]
            if len(entries)>150:raise HTTPException(409,detail='主体压缩包文件数量超过安全限制')
            for item in entries:
                path=PurePosixPath(item.filename.replace('\\','/'))
                if path.is_absolute() or '..' in path.parts:continue
                ext=path.suffix.lower()
                if item.file_size>12*1024*1024:
                    items.append({'file':path.name,'type':'过大','fields':[],'note':'单文件超过12MB，本次未分析'});continue
                if ext in ('.txt','.docx','.pdf','.png','.jpg','.jpeg'):
                    examine(item.filename,ext,z.read(item))
    else:examine(draft['filename'],suffix,stored.read_bytes())
    conflicts=[]
    for k,found in sources.items():
        values={x['value'].casefold() for x in found}
        if len(values)>1:conflicts.append(LABELS[k]+'在不同文档中不一致，请核对：'+ '、'.join(x['file'] for x in found))
    return {'draft_id':draft_id,'method':draft['method'],'files':items,
       'sources':sources,'conflicts':conflicts,
       'extracted':{k:extracted.get(k,'') for k in FIELDS},
       'note':'TXT/DOCX/PDF文字层的字段溯源，不包含证件真实性核验；图片和扫描件需要单独核对'}


def _describe_item(c,sid,domain,email):
    rec=row(c.execute('''SELECT s.id,s.code,t.code template_code,t.inner_path FROM stores s
      JOIN templates t ON s.template_id=t.id WHERE s.id=?''',(sid,)))
    if not rec:raise HTTPException(409,detail='匹配资源已不存在')
    m=identify_template(rec['inner_path'])
    if not m:raise HTTPException(409,detail='来源模板目录结构无法识别')
    return {'store_id':sid,'store_code':rec['code'],'template_code':rec['template_code'],
            'template_group':m['template_group'],'category':m['category'],'product_family':m['product_family'],
            'style_family':m['style_family'],'style_name':m['style_name'],
            'domain':domain,'support_email':email}


def build_v8_router(guard):
    r=APIRouter(prefix='/api/v8',dependencies=[Depends(guard)])

    @r.post('/intake/check')
    def intake_check(req:CheckRequest):
        return _summary_fields(req.fields,req.domains)

    @r.get('/intake/{draft_id}/sources')
    def intake_sources(draft_id:str):
        if not re.fullmatch(r'INTAKE-[A-Za-z0-9-]{8,70}',draft_id):
            raise HTTPException(400,detail='主体资料编号格式不合法')
        return _source_evidence(draft_id)

    @r.post('/proposals/{proposal_id}/reroll-one')
    def reroll_one(proposal_id:str,req:RerollRequest):
        if not re.fullmatch(r'MATCH-[A-Z0-9]{12}',proposal_id):
            raise HTTPException(400,detail='匹配方案编号不合法')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            saved=row(c.execute('SELECT * FROM auto_allocation_proposals WHERE id=?',(proposal_id,)))
            if not saved or saved['status']!='待确认':
                raise HTTPException(409,detail='匹配方案已提交、已替换或已失效，请重新匹配')
            if saved['expires_at']<=now():
                raise HTTPException(409,detail='预览超过有效期，请重新匹配')
            payload=json.loads(saved['payload_json']);items=payload['items']
            changed_idx=next((i for i,x in enumerate(items) if x['store_id']==req.store_id),-1)
            if changed_idx<0:raise HTTPException(404,detail='指定店铺不在当前匹配方案中')
            other_ids=[x['store_id'] for i,x in enumerate(items) if i!=changed_idx]
            existing=[]
            if payload.get('entity_id'):
                existing=rows(c.execute('''SELECT s.code,t.inner_path FROM stores s
                    JOIN templates t ON s.template_id=t.id WHERE s.entity_id=?''',(payload['entity_id'],)))
            other=[]
            for sid in other_ids:
                st=row(c.execute('''SELECT s.code,t.inner_path,s.entity_id,d.domain FROM stores s
                    JOIN templates t ON s.template_id=t.id LEFT JOIN store_domains d ON d.store_id=s.id
                    WHERE s.id=?''',(sid,)))
                if not st or st['entity_id'] or st['domain']:
                    raise HTTPException(409,detail='另一个候选店铺状态已发生改变，请重新匹配')
                other.append(st)
            if check_diversity(existing+other):
                raise HTTPException(409,detail='现有资源不再满足严格差异要求，请重新匹配')
            old=row(c.execute('''SELECT s.code,t.inner_path FROM stores s JOIN templates t ON s.template_id=t.id
               WHERE s.id=?''',(req.store_id,)))
            old_meta=identify_template(old['inner_path']) if old else None
            pool=rows(c.execute('''SELECT s.id,s.code,t.inner_path,t.code template_code
               FROM stores s JOIN templates t ON s.template_id=t.id
               WHERE s.entity_id IS NULL AND NOT EXISTS(SELECT 1 FROM store_domains d WHERE d.store_id=s.id)'''))
            rng=secrets.SystemRandom();rng.shuffle(pool)
            chosen=None
            # Prefer replacing both the category and the layout family (when possible).
            def matches(new):
                return not check_diversity(existing+other+[{'code':new['code'],'inner_path':new['inner_path']}])
            stronger=[x for x in pool if x['id'] not in other_ids and x['id']!=req.store_id
                and identify_template(x['inner_path']) and matches(x)
                and (not old_meta or (identify_template(x['inner_path'])['style_family']!=old_meta['style_family']
                      and identify_template(x['inner_path'])['product_family']!=old_meta['product_family']))]
            if stronger:chosen=stronger[0]
            else:
                chosen=next((x for x in pool if x['id'] not in other_ids and x['id']!=req.store_id
                    and identify_template(x['inner_path']) and matches(x)),None)
            if not chosen:
                raise HTTPException(409,detail='剩余完整资源中找不到满足严格差异要求的单店替代方案，未修改现有方案')
            updated=json.loads(json.dumps(payload))
            updated['items'][changed_idx]['store_id']=chosen['id']
            ident=uid('MATCH')
            expires=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
            c.execute("UPDATE auto_allocation_proposals SET status='已替代' WHERE id=? AND status='待确认'",(proposal_id,))
            c.execute('INSERT INTO auto_allocation_proposals(id,payload_json,created_at,expires_at) VALUES(?,?,?,?)',
                      (ident,json.dumps(updated,ensure_ascii=False),now(),expires))
            details=[_describe_item(c,x['store_id'],x['domain'],x['support_email']) for x in updated['items']]
            return {'proposal_id':ident,'replaces':proposal_id,'expires_at':expires,'items':details,
                'changed_domain':updated['items'][changed_idx]['domain'],
                'previous_store_code':old['code'] if old else '',
                'new_store_code':chosen['code'],
                'note':'仅更换一套完整的原始店铺组合；其余域名、店铺和邮箱保留。尚未实际保存，须最终确认。',
                'plan':{'can_commit':True,'policy_sample':{'policies':[],
                  'warning':'更换方案后，政策全文将在确认分配前的服务端校验阶段重新生成'}}}
    return r
