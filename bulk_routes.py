"""BIG BANG V3.2: bulk legal-entity intake, editable allocation and atomic commit.

Batch planning is deterministic validation + randomized resource allocation; no legal
identity, email account, copyright permission or regulatory approval is inferred.
Original 300 store packages are immutable and are allocated as whole packages.
"""
from __future__ import annotations
import csv, io, json, zipfile, random, secrets, re, datetime
from pathlib import PurePosixPath
from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, Query
from pydantic import BaseModel, Field
from sqlite3 import IntegrityError
from db import db, uid, now, row, rows, DATA
from auto_match import identify_template, check_diversity, AllocationError
from entity_guard import entity_issues
from v3_services import validate_upload, extract_local_text, parse_fields, clean_domain, email_valid

MAX_BATCH=150
MAX_ARCHIVE_BYTES=70*1024*1024
MAX_DOC_BYTES=12*1024*1024
EXPIRES_MIN=40


def init_bulk():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS bulk_intake_batches (
          id TEXT PRIMARY KEY, filename TEXT NOT NULL, items_json TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT '待规划', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bulk_allocation_proposals (
          id TEXT PRIMARY KEY, intake_batch_id TEXT NOT NULL REFERENCES bulk_intake_batches(id),
          payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT '待确认',
          created_at TEXT NOT NULL, expires_at TEXT NOT NULL, committed_at TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_bulk_proposal ON bulk_allocation_proposals(intake_batch_id,status);
        ''')

FIELDS=('name','registration_no','country','address','phone','email')
CSV_ALIASES={
    'name': ('name','company_name','legal_name','legal_company_name','公司名称','法定公司名称','主体名称'),
    'registration_no': ('registration_no','ein','company_number','登记编号','注册编号','统一社会信用代码'),
    'country':('country','region','注册国家','国家地区','国家'),
    'address':('address','registered_address','注册地址','公司地址'),
    'phone':('phone','support_phone','联系电话','客服电话'),
    'email':('email','company_email','联系邮箱','邮箱'),
    'count':('store_count','count','planned_stores','分配店铺数','店铺数量'),
    'domains':('domains','domain_list','域名','域名列表')
}

def _csv_items(raw:bytes):
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:text=raw.decode('gb18030')
        except UnicodeDecodeError:raise ValueError('CSV文字编码必须为UTF-8或GB18030')
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:raise ValueError('CSV没有表头')
    normalized={re.sub(r'\s+','',str(x or '')).lower():x for x in reader.fieldnames}
    keys={k: next((normalized[a.lower()] for a in aliases if a.lower() in normalized),None)
          for k,aliases in CSV_ALIASES.items()}
    if not keys['name']:raise ValueError('CSV需要 company_name 或 法定公司名称 列')
    out=[]
    for i,x in enumerate(reader,1):
        if i>MAX_BATCH:raise ValueError(f'单次最多导入{MAX_BATCH}个主体')
        if not any(str(y or '').strip() for y in x.values()):continue
        values={field:str(x.get(keys[field],'') or '').strip()[:500] for field in FIELDS}
        value_count=str(x.get(keys['count'],'') or '').strip() if keys['count'] else ''
        try:count=int(value_count) if value_count else 4
        except ValueError:count=-1
        domains=str(x.get(keys['domains'],'') or '')[:4000] if keys['domains'] else ''
        out.append({'draft_id':uid('BROW'),'filename':'CSV · 第'+str(i)+'行',
                    'fields':values,'count':count,'domains':domains,'method':'CSV结构化导入',
                    'warning':'CSV字段尚未与官方登记文件核验', 'storage_name':'','included':True})
    return out


def _read_text_document(name: str, raw: bytes):
    """Decode controlled text documents without OCR, preserving the author's field labels."""
    extension='.'+name.rsplit('.',1)[-1].lower() if '.' in name else ''
    if extension=='.txt':
        from v3_services import decode_company_txt
        return decode_company_txt(raw)[:28000], 'TXT源文件直读'
    if extension=='.docx':
        from docx import Document
        doc=Document(io.BytesIO(raw))
        parts=[p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for r in table.rows:
                parts.extend(cell.text for cell in r.cells if cell.text.strip())
        return '\n'.join(parts)[:28000], 'Word文档文字读取'
    raise ValueError('无法直接读取该文件格式')


def _doc_items(files):
    out=[]
    for name,raw in files:
        if len(out)>=MAX_BATCH:raise ValueError(f'单次最多导入{MAX_BATCH}个主体')
        ext='.'+name.rsplit('.',1)[-1].lower() if '.' in name else ''
        if ext not in ('.txt','.docx'):
            try:ext=validate_upload(name,raw)
            except ValueError as ex:raise ValueError(str(ex)+'：'+name[:80])
        elif len(raw)>MAX_DOC_BYTES:raise ValueError('公司资料文件超过12MB：'+name[:80])
        try:
            if ext in ('.txt','.docx'):
                extracted,method=_read_text_document(name,raw)
            else:extracted,method=extract_local_text(raw,ext)
            fields=parse_fields(extracted)
            missing=[]
            if not fields.get('name'):missing.append('公司名称')
            if not fields.get('address'):missing.append('注册地址')
            if not fields.get('phone'):missing.append('通用电话')
            warning=('需补充：'+'、'.join(missing)) if missing else ''
            if not fields.get('registration_no'):warning+=('；' if warning else '')+'登记编号未提供，需要人工核验（不阻止初步规划）'
            if not fields.get('email'):warning+=('；' if warning else '')+'公司邮箱未提供；各店铺邮箱按域名分别配置'
        except Exception as exc:
            method='本地识别未完成';fields={k:'' for k in FIELDS}
            warning='本地解析失败（'+type(exc).__name__+'），需要人工填写'
        draft_id=uid('INTAKE');storage_name=draft_id+ext
        (DATA/'uploads'/storage_name).write_bytes(raw)
        try:(DATA/'uploads'/storage_name).chmod(0o600)
        except OSError:pass
        out.append({'draft_id':draft_id,'filename':name[:200],'fields':fields,'count':4,'domains':'',
                    'method':method,'warning':warning,'storage_name':storage_name,'included':True})
    return out


def _read_archive(name,raw):
    if len(raw)>MAX_ARCHIVE_BYTES:raise ValueError('ZIP文件最大70MB')
    files=[];total=0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for member in z.infolist():
            if member.is_dir():continue
            filename=PurePosixPath(member.filename.replace('\\','/')).name
            if not filename or filename.startswith('.') or '__MACOSX' in member.filename:continue
            ext='.'+filename.rsplit('.',1)[-1].lower() if '.' in filename else ''
            if ext not in ('.pdf','.jpg','.jpeg','.png','.txt','.docx'):continue
            if member.flag_bits & 1:raise ValueError('不支持加密ZIP文件')
            if member.file_size>MAX_DOC_BYTES:raise ValueError('压缩包中单个文件超过12MB：'+filename)
            if member.compress_size>0 and member.file_size/member.compress_size>150:raise ValueError('压缩包文件压缩比异常：'+filename)
            total+=member.file_size
            if total>MAX_ARCHIVE_BYTES*2:raise ValueError('ZIP解压后总数据过大')
            if len(files)>=MAX_BATCH:raise ValueError('ZIP文件数量超过150份')
            files.append((filename,z.read(member)))
    if not files:raise ValueError('ZIP中未找到可识别的TXT/DOCX/PDF/JPG/PNG公司资料')
    return files


def _norm_domains(text):
    source=text if isinstance(text,str) else '\n'.join(text or [])
    values=[x.strip() for x in re.split(r'[\r\n,，;；\s]+',source.strip()) if x.strip()]
    return [clean_domain(x) for x in values]

class BulkRow(BaseModel):
    draft_id:str
    included:bool=True
    fields:dict[str,str]
    count:int=Field(ge=0,le=8)
    domains:str=''

class BulkPlanRequest(BaseModel):
    batch_id:str
    rows:list[BulkRow]=Field(min_length=1,max_length=MAX_BATCH)

class BulkCommitRequest(BaseModel):
    proposal_id:str


def _random_allocate(c,grouped):
    """Allocate whole, unused store packs with strict per-entity differences.

    Multiple passes are randomized, and a failed global plan never persists partial
    allocations. This is a heuristic feasibility search; no optimality claim.
    """
    pool=rows(c.execute('''SELECT s.id,s.code,s.label,t.code template_code,t.inner_path
        FROM stores s JOIN templates t ON s.template_id=t.id
        WHERE s.entity_id IS NULL AND NOT EXISTS(SELECT 1 FROM store_domains d WHERE d.store_id=s.id)'''))
    for x in pool:x['meta']=identify_template(x['inner_path'])
    pool=[x for x in pool if x['meta']]
    requested=sum(x['count'] for x in grouped)
    if requested>len(pool):raise AllocationError(f'需要{requested}套资源，但仅剩{len(pool)}套未分配完整资源')
    types={x['meta']['style_family'] for x in pool}
    if any(x['count']>len(types) for x in grouped):raise AllocationError('单个主体需要的店铺数超过现有不同装修结构的数量')
    # Bounds apply to any possible assignment; clear warning beats poor allocations.
    hero=sum(x['meta']['style_family']=='hero-scene' for x in pool)
    special=len(pool)-hero
    n_entities=sum(x['count']>0 for x in grouped)
    needed_special=sum(max(0,x['count']-1) for x in grouped)
    if needed_special>special:
        raise AllocationError(f'严格装修差异无法满足：本批至少需要{needed_special}套非标准Hero结构资源，当前只剩{special}套。请减少单主体分配数量或增加真实不同结构的模板。')
    by_style={}
    for x in pool:by_style.setdefault(x['meta']['style_family'],[]).append(x)
    rng=secrets.SystemRandom()
    # A global greedy search with bounded rerolls. Rare styles are consumed only when needed.
    for attempt in range(80):
        groups=sorted(grouped,key=lambda x:(-x['count'],rng.random()))
        available=set(x['id'] for x in pool)
        output={}
        success=True
        for group in groups:
            chosen=[];used_styles=set();used_families=set();used_groups=set();used_categories=set()
            for slot in range(group['count']):
                opts=[x for x in pool if x['id'] in available and
                      x['meta']['style_family'] not in used_styles and
                      x['meta']['product_family'] not in used_families and
                      x['meta']['category'] not in used_categories and
                      x['meta']['group'] not in used_groups]
                if not opts:success=False;break
                # Favor common layouts when there's enough future slack, and spread
                # broad product families. Shuffle ties for useful rerolls.
                rng.shuffle(opts)
                def score(x):
                    style=x['meta']['style_family']
                    spare=sum(y['id'] in available for y in by_style[style])
                    return ((0 if style=='hero-scene' and slot==0 else 1),-spare)
                opts.sort(key=score)
                cand=opts[0];chosen.append(cand);available.remove(cand['id'])
                meta=cand['meta'];used_styles.add(meta['style_family']);used_families.add(meta['product_family']);used_categories.add(meta['category']);used_groups.add(meta['group'])
            if not success:break
            output[group['draft_id']]=chosen
        if success:return output
    raise AllocationError('本批严格分配未找到完整可行方案。可以减少部分主体的店铺数量、分成较小批次尝试，或增加真实差异化模板；未保存任何分配。')


def _compare_entities(c,selected):
    names={};regs={};errors=[];warnings=[]
    for x in selected:
        f=x['fields'];name=f.get('name','').strip();reg=f.get('registration_no','').strip()
        if len(name)<2:errors.append(x['draft_id']+' 缺少已确认的公司法定名称')
        for key,value,seen in [('名称',name.casefold(),names),('登记编号',reg.casefold(),regs)]:
            if not value:continue
            if value in seen:errors.append(x['draft_id']+' 与 '+seen[value]+' 的'+key+'重复')
            else:seen[value]=x['draft_id']
        exists=row(c.execute('SELECT code FROM entities WHERE lower(name)=lower(?)',(name,))) if name else None
        if exists:errors.append(name+' 已作为 '+exists['code']+' 登记，请勿重复创建')
        exists=row(c.execute('SELECT code FROM entities WHERE lower(registration_no)=lower(?)',(reg,))) if reg else None
        if exists:errors.append('登记编号 '+reg+' 已存在于 '+exists['code'])
        if not reg:warnings.append(name+' 未填写登记编号，无法完成主体一致性核验')
        if not f.get('address'):warnings.append(name+' 未填写注册地址')
    return errors,warnings


def build_bulk_router(guard,fail):
    r=APIRouter(prefix='/api/v3/bulk',dependencies=[Depends(guard)])

    @r.get('/inventory')
    def inventory():
        with db() as c:
            pool=rows(c.execute('''SELECT t.inner_path FROM stores s JOIN templates t ON s.template_id=t.id
               WHERE s.entity_id IS NULL AND NOT EXISTS(SELECT 1 FROM store_domains d WHERE d.store_id=s.id)'''))
        styles={}
        for item in pool:
            meta=identify_template(item['inner_path'])
            if meta:styles[meta['style_family']]=styles.get(meta['style_family'],0)+1
        return {'available':len(pool),'styles':styles,
                'special':sum(n for st,n in styles.items() if st!='hero-scene'),
                'hero':styles.get('hero-scene',0),
                'max_distinct_styles':len(styles)}

    @r.post('/intake')
    async def intake(files:list[UploadFile]=File(...)):
        if not files or len(files)>MAX_BATCH:fail('一次最多上传150个文件')
        all_docs=[];all_rows=[];source_names=[]
        for file in files:
            name=PurePosixPath((file.filename or 'file').replace('\\','/')).name[:200]
            raw=await file.read(MAX_ARCHIVE_BYTES+1)
            if not raw:fail('上传了空文件')
            if len(raw)>MAX_ARCHIVE_BYTES:fail('单个上传文件不得超过70MB')
            source_names.append(name)
            try:
                if name.lower().endswith('.zip'):
                    all_docs.extend(_read_archive(name,raw))
                elif name.lower().endswith('.csv'):
                    all_rows.extend(_csv_items(raw))
                else:all_docs.append((name,raw))
            except (ValueError,zipfile.BadZipFile) as ex:fail(str(ex))
        if len(all_rows)+len(all_docs)>MAX_BATCH:fail('单批主体总数不能超过150')
        doc_rows=_doc_items(all_docs) if all_docs else []
        all_rows.extend(doc_rows)
        if not all_rows:fail('未找到任何公司主体资料')
        names={};regs={}
        for entry in all_rows:
            f=entry['fields'];n=f.get('name','').strip().casefold();reg=f.get('registration_no','').strip().casefold()
            if n and n in names:entry['warning']+='；本批次疑似重复主体名称'
            if reg and reg in regs:entry['warning']+='；本批次疑似重复登记编号'
            if n:names[n]=1
            if reg:regs[reg]=1
        bid=uid('BULK')
        with db() as c:
            for item in doc_rows:
                c.execute('INSERT INTO intake_drafts(id,filename,storage_name,method,extracted_json,created_at) VALUES(?,?,?,?,?,?)',
                  (item['draft_id'],item['filename'],item['storage_name'],item['method'],json.dumps(item['fields'],ensure_ascii=False),now()))
            c.execute('INSERT INTO bulk_intake_batches(id,filename,items_json,created_at) VALUES(?,?,?,?)',
                      (bid,', '.join(source_names)[:450],json.dumps(all_rows,ensure_ascii=False),now()))
        return {'batch_id':bid,'count':len(all_rows),'items':all_rows,
                'note':'仅自动提取文件内容，不代表官方公司验证。默认完全本地处理，未发送主体文件到DeepSeek。'}

    @r.get('/{batch_id}')
    def batch_get(batch_id:str):
        with db() as c:saved=row(c.execute('SELECT * FROM bulk_intake_batches WHERE id=?',(batch_id,)))
        if not saved:fail('未找到批量主体文件',404)
        return {'batch_id':saved['id'],'items':json.loads(saved['items_json']),'status':saved['status']}

    def validate_rows(req,c):
        saved=row(c.execute('SELECT * FROM bulk_intake_batches WHERE id=?',(req.batch_id,)))
        if not saved:fail('批量主体导入任务不存在',404)
        if saved['status']!='待规划':fail('本批主体已提交，不可重复分配',409)
        original={x['draft_id']:x for x in json.loads(saved['items_json'])}
        if len(req.rows)!=len(original) or len({x.draft_id for x in req.rows})!=len(original):fail('提交的主体列表与原始导入不符')
        if {x.draft_id for x in req.rows}!=set(original):fail('主体ID不匹配，请重新导入')
        selected=[];domains=set();emails=set();errors=[];warnings=[]
        for x in req.rows:
            source=original[x.draft_id];fields={k:str(x.fields.get(k,'') or '').strip()[:500] for k in FIELDS}
            if not x.included:continue
            try:doms=_norm_domains(x.domains)
            except Exception:errors.append((fields.get('name') or x.draft_id)+' 含无效域名');doms=[]
            if len(doms)>x.count:errors.append(fields['name']+' 提供的域名数量超过计划店铺数')
            if len(doms)!=len(set(doms)):errors.append(fields['name']+' 内部存在重复域名')
            for d in doms:
                if d in domains:errors.append('多个公司主体使用相同域名：'+d)
                domains.add(d)
                old=row(c.execute('SELECT s.code FROM store_domains d JOIN stores s ON s.id=d.store_id WHERE d.domain=?',(d,)))
                if old:errors.append(d+' 已被 '+old['code']+' 使用')
                em='service@'+d
                if em in emails:errors.append('邮箱重复：'+em)
                emails.add(em)
                old=row(c.execute('SELECT s.code FROM store_contacts sc JOIN stores s ON s.id=sc.store_id WHERE lower(sc.support_email)=?',(em,)))
                if old:errors.append('邮箱 '+em+' 已被 '+old['code']+' 使用')
            # Zero-store drafts can remain incomplete; never assign an active store
            # to a company missing its single shared verified-format phone.
            if x.count:
                errors.extend([(fields.get('name') or x.draft_id)+'：'+issue for issue in entity_issues(fields)])
            if not doms and x.count:warnings.append(fields['name']+' 没有域名：分配后仍需配置域名与独立邮箱')
            if len(doms)<x.count and doms:warnings.append(fields['name']+f' 只填写{len(doms)}个域名，还剩{x.count-len(doms)}家店铺待配置')
            selected.append({'draft_id':x.draft_id,'fields':fields,'count':x.count,'domains':doms,
                             'document_storage':source['storage_name'],'filename':source['filename']})
        if not selected:errors.append('至少选择一家主体')
        e,w=_compare_entities(c,selected);errors.extend(e);warnings.extend(w)
        return saved,selected,errors,warnings

    @r.post('/preview')
    def preview(req:BulkPlanRequest):
        with db() as c:
            saved,selected,errors,warnings=validate_rows(req,c)
            if errors:return {'can_commit':False,'errors':errors,'warnings':warnings,'items':[],
                              'summary':{'subjects':len(selected),'requested':sum(x['count'] for x in selected)}}
            requested=sum(x['count'] for x in selected)
            available=c.execute('SELECT COUNT(*) FROM stores s WHERE s.entity_id IS NULL AND NOT EXISTS(SELECT 1 FROM store_domains d WHERE d.store_id=s.id)').fetchone()[0]
            try:assigned=_random_allocate(c,selected)
            except AllocationError as ex:
                return {'can_commit':False,'errors':[str(ex)],'warnings':warnings,'items':[],
                        'summary':{'subjects':len(selected),'requested':requested,'available':available}}
            result=[]
            for entity in selected:
                chosen=assigned.get(entity['draft_id'],[])
                links=[]
                for i,store in enumerate(chosen):
                    domain=entity['domains'][i] if i<len(entity['domains']) else ''
                    email='service@'+domain if domain else ''
                    m=store['meta']
                    links.append({'store_id':store['id'],'store_code':store['code'],
                                  'template_code':store['template_code'],'category':m['category'],
                                  'product_family':m['product_family'], 'style_family':m['style_family'],
                                  'style_name':m['style_name'],'domain':domain,'support_email':email})
                result.append({'draft_id':entity['draft_id'],'entity':entity['fields'],
                               'filename':entity['filename'],'count':entity['count'],'items':links,
                               'document_storage':entity['document_storage']})
            p_id=uid('BPLAN');expires=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=EXPIRES_MIN)).strftime('%Y-%m-%dT%H:%M:%SZ')
            c.execute('INSERT INTO bulk_allocation_proposals(id,intake_batch_id,payload_json,created_at,expires_at) VALUES(?,?,?,?,?)',
                (p_id,req.batch_id,json.dumps(result,ensure_ascii=False),now(),expires))
            return {'can_commit':True,'proposal_id':p_id,'expires_at':expires,'errors':[],
                    'warnings':warnings,'items':result,
                    'summary':{'subjects':len(selected),'requested':requested,'available':available,
                               'without_domain':sum(not it['domain'] for ent in result for it in ent['items'])},
                    'note':'仅预览，不更改已有300套文件；严格避免同主体内重复装修结构及商品大类。未验证邮箱真实性或网站合规。'}

    @r.post('/commit')
    def commit(req:BulkCommitRequest):
        try:
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                proposal=row(c.execute('SELECT * FROM bulk_allocation_proposals WHERE id=?',(req.proposal_id,)))
                if not proposal or proposal['status']!='待确认':fail('方案不存在或已经提交',409)
                if proposal['expires_at']<=now():fail('方案已过期，请重新生成',409)
                parent=row(c.execute('SELECT status,items_json FROM bulk_intake_batches WHERE id=?',(proposal['intake_batch_id'],)))
                if not parent or parent['status']!='待规划':fail('批次状态已变化，请重新生成方案',409)
                plans=json.loads(proposal['payload_json']);ids=[it['store_id'] for x in plans for it in x['items']]
                if len(ids)!=len(set(ids)):fail('分配结果包含重复店铺',409)
                if ids:
                    occupied=rows(c.execute('SELECT code FROM stores WHERE id IN ('+','.join('?' for _ in ids)+') AND entity_id IS NOT NULL',ids))
                    if occupied:fail('店铺已经被其他主体占用：'+','.join(x['code'] for x in occupied),409)
                    real=rows(c.execute('''SELECT s.id,s.code,t.inner_path FROM stores s JOIN templates t ON s.template_id=t.id
                                          WHERE s.id IN ('''+','.join('?' for _ in ids)+')',ids))
                    if len(real)!=len(ids):fail('部分模板资源已经不存在',409)
                    real_map={x['id']:x for x in real}
                    for x in plans:
                        violation=check_diversity([real_map[it['store_id']] for it in x['items']])
                        if violation:fail('严格差异检查失败：'+ '；'.join(violation[:3]),409)
                # Recheck entities, domains and emails at commit time.
                names=set();regs=set();all_domains=set()
                for x in plans:
                    f=x['entity'];name=f['name'].strip();reg=f['registration_no'].strip()
                    if x['count']:
                        check=entity_issues(f)
                        if check:fail('；'.join(check),409)
                    if len(name)<2:fail('主体法定名称缺失',409)
                    if name.casefold() in names:fail('批次存在重复主体名称',409)
                    names.add(name.casefold())
                    if reg:
                        if reg.casefold() in regs:fail('批次存在重复主体登记编号',409)
                        regs.add(reg.casefold())
                    dupe=row(c.execute('SELECT code FROM entities WHERE lower(name)=lower(?) OR (registration_no<>\'\' AND lower(registration_no)=lower(?))',(name,reg)))
                    if dupe:fail('主体已被其他操作创建，请重新检查：'+name,409)
                    for it in x['items']:
                        d=it['domain'];em=it['support_email']
                        if d:
                            if d in all_domains:fail('批次出现重复域名',409)
                            all_domains.add(d)
                            if row(c.execute('SELECT id FROM store_domains WHERE domain=?',(d,))):fail('域名已被其他操作绑定：'+d,409)
                        if em:
                            if not email_valid(em):fail('邮箱格式不合法',409)
                            if row(c.execute('SELECT store_id FROM store_contacts WHERE lower(support_email)=?',(em,))):fail('邮箱已被其他操作使用',409)
                # Exact persisted proposal is the only source of commit data.
                for x in plans:
                    f=x['entity'];eid=uid('ENT')
                    used=c.execute("SELECT code FROM entities WHERE code LIKE 'ENT-%' ORDER BY code DESC LIMIT 1").fetchone()
                    start=int(used[0].split('-')[-1])+1 if used and used[0].split('-')[-1].isdigit() else 1
                    code=f'ENT-{start:03d}'
                    c.execute('''INSERT INTO entities(id,code,name,registration_no,country,address,phone,email,capacity,status,created_at,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(eid,code,f['name'],f['registration_no'],f['country'],f['address'],f['phone'],f['email'],x['count'],'待核验',now(),now()))
                    for it in x['items']:
                        c.execute('UPDATE stores SET entity_id=?,status=?,updated_at=? WHERE id=?',
                          (eid,'待部署' if it['domain'] else '待配置',now(),it['store_id']))
                        if it['domain']:
                            c.execute('INSERT INTO store_domains(id,store_id,domain,created_at) VALUES(?,?,?,?)',
                                      (uid('DOM'),it['store_id'],it['domain'],now()))
                            c.execute('INSERT INTO store_contacts(store_id,support_email,email_status,updated_at) VALUES(?,?,?,?)',
                                      (it['store_id'],it['support_email'],'待验证',now()))
                        c.execute('''INSERT INTO configuration_events(id,batch_id,object_type,object_id,action,before_json,after_json,created_at)
                            VALUES(?,?,?,?,?,?,?,?)''',
                            (uid('EV'),req.proposal_id,'store',it['store_id'],'bulk-assign',
                             json.dumps({'entity_id':None,'domain':''}),json.dumps({'entity_id':eid,**it},ensure_ascii=False),now()))
                    c.execute('INSERT INTO deployment_batches VALUES(?,?,?,?,?)',
                        (uid('DEPLOY'),eid,json.dumps([it['store_id'] for it in x['items']]),'[]',now()))
                    if x['document_storage']:
                        original=row(c.execute('SELECT * FROM intake_drafts WHERE id=? AND status=?',(x['draft_id'],'待确认')))
                        if not original:fail('原始主体文件草稿已失效，请重新导入',409)
                        c.execute('INSERT INTO entity_documents VALUES(?,?,?,?,?,?,?)',
                            (uid('DOC'),eid,original['filename'],original['storage_name'],
                             (DATA/'uploads'/original['storage_name']).stat().st_size,'application/octet-stream',now()))
                        c.execute("UPDATE intake_drafts SET status='已归档' WHERE id=?",(original['id'],))
                c.execute("UPDATE bulk_allocation_proposals SET status='已提交',committed_at=? WHERE id=?",(now(),req.proposal_id))
                c.execute("UPDATE bulk_intake_batches SET status='已提交' WHERE id=?",(proposal['intake_batch_id'],))
                return {'ok':True,'entity_count':len(plans),'store_count':len(ids),
                        'note':'分配已保存，原始300套商品和装修未修改。主体真实性、邮箱实际收件能力与政策合规需另行核验。'}
        except IntegrityError as ex:
            fail('检测到数据库唯一性冲突，已全部回滚：'+str(ex)[:120],409)
    return r
