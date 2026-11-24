"""V3 deployment workflow. No mutation to template files or product CSVs."""
from __future__ import annotations
import io,os,re,json,zipfile,hashlib,datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter,Depends,UploadFile,File,HTTPException,Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field
from sqlite3 import IntegrityError
from auto_match import choose_candidates,check_diversity,AllocationError
from db import DATA,db,uid,now,row,rows
from entity_guard import entity_issues
from v3_services import (validate_upload,extract_local_text,parse_fields,ai_extract_image,
       clean_domain,email_valid,email_suggestion,policy_files_from_zip,render_policy,POLICY_NAMES)

class EntityDraft(BaseModel):
    name:str=Field(default='',max_length=255)
    registration_no:str=Field(default='',max_length=100)
    country:str=Field(default='',max_length=100)
    address:str=Field(default='',max_length=500)
    phone:str=Field(default='',max_length=80)
    email:str=Field(default='',max_length=255)

class DeploymentItem(BaseModel):
    store_id:str
    domain:str=Field(default='',max_length=255)
    support_email:str=Field(default='',max_length=255)

class Deployment(BaseModel):
    proposal_id:Optional[str]=None
    entity_id:Optional[str]=None
    intake_draft_id:Optional[str]=None
    entity:EntityDraft
    capacity:int=Field(default=0,ge=0,le=10000)
    items:list[DeploymentItem]=Field(min_length=1,max_length=300)

class AutoMatchRequest(BaseModel):
    entity_id:Optional[str]=None
    intake_draft_id:Optional[str]=None
    entity:EntityDraft=Field(default_factory=EntityDraft)
    domains:list[str]=Field(min_length=4,max_length=5)
    email_prefix:str=Field(default='service',pattern=r'^[a-zA-Z][a-zA-Z0-9._-]{0,30}$')

class AutoCommitRequest(BaseModel):
    proposal_id:str=Field(min_length=12,max_length=70)

class ContactPatch(BaseModel):
    support_email:str=Field(default='',max_length=255)


def build_v3_router(guard,fail):
    r=APIRouter(prefix='/api/v3',dependencies=[Depends(guard)])

    @r.get('/summary')
    def summary():
        with db() as c:
            counts={'stores':c.execute('SELECT COUNT(*) FROM stores').fetchone()[0],
                    'templates':c.execute('SELECT COUNT(*) FROM templates').fetchone()[0],
                    'entities':c.execute('SELECT COUNT(*) FROM entities').fetchone()[0],
                    'assigned':c.execute('SELECT COUNT(*) FROM stores WHERE entity_id IS NOT NULL').fetchone()[0],
                    'domains':c.execute('SELECT COUNT(*) FROM store_domains').fetchone()[0],
                    'emails':c.execute("SELECT COUNT(*) FROM store_contacts WHERE support_email<>''").fetchone()[0],
                    'pending_emails':c.execute("SELECT COUNT(*) FROM store_contacts WHERE email_status='待验证'").fetchone()[0],
                    'deployments':c.execute('SELECT COUNT(*) FROM deployment_batches').fetchone()[0],
                    'audits':c.execute('SELECT COUNT(*) FROM audits').fetchone()[0]}
            counts['unassigned']=counts['stores']-counts['assigned']
            counts['without_domain']=counts['stores']-counts['domains']
            counts['without_email']=counts['stores']-counts['emails']
            return counts

    @r.get('/stores')
    def stores_v3():
        with db() as c:
            return rows(c.execute('''SELECT s.id,s.code,s.label,s.entity_id,s.template_id,s.status,d.domain,
                 e.name as entity_name,e.code as entity_code,t.code as template_code,
                 COALESCE(sc.support_email,'') support_email,
                 COALESCE(sc.email_status,'未配置') email_status,
                 (SELECT a.status FROM audits a WHERE a.store_id=s.id ORDER BY a.rowid DESC LIMIT 1) audit_status
                 FROM stores s LEFT JOIN entities e ON e.id=s.entity_id
                 LEFT JOIN templates t ON t.id=s.template_id
                 LEFT JOIN store_domains d ON d.store_id=s.id
                 LEFT JOIN store_contacts sc ON sc.store_id=s.id ORDER BY s.code'''))

    @r.post('/intake/extract')
    async def intake_extract(file:UploadFile=File(...),use_ai:bool=False):
        name=(file.filename or 'company-file').replace('\\','/').split('/')[-1][:200]
        raw=await file.read(12*1024*1024+1)
        try:ext=validate_upload(name,raw)
        except ValueError as ex:fail(str(ex))
        warning=''
        try:
            text,method=extract_local_text(raw,ext)
        except Exception as ex:
            text='';method='本地识别未完成'
            warning=str(ex)[:380] if type(ex).__name__=='OCRUnavailableError' else '文件解析未完成：'+str(ex)[:260]
        fields=parse_fields(text)
        if use_ai and ext!='.txt':
            try:
                interpreted=ai_extract_image(raw,ext,text)
                for key,v in interpreted.items():
                    if v:fields[key]=v
                method+=' + DeepSeek视觉提取'
            except Exception as ex:
                warning=('DeepSeek提取失败：'+str(ex))[:300]+'；可以人工核对。'
        if not any(fields.values()):
            warning=warning or '没有找到可可靠提取的主体字段；请根据原始文件手动核对填写。'
        duplicate=[]
        with db() as c:
            if fields.get('registration_no'):
                duplicate=rows(c.execute('SELECT id,code,name,registration_no FROM entities WHERE lower(registration_no)=lower(?)', (fields['registration_no'],)))
            if not duplicate and fields.get('name'):
                duplicate=rows(c.execute('SELECT id,code,name,registration_no FROM entities WHERE lower(name)=lower(?)',(fields['name'],)))
        ident=uid('INTAKE'); storage=ident+ext
        path=DATA/'uploads'/storage
        path.write_bytes(raw)
        try:path.chmod(0o600)
        except OSError:pass
        with db() as c:
            c.execute('INSERT INTO intake_drafts(id,filename,storage_name,method,extracted_json,created_at) VALUES(?,?,?,?,?,?)',
                      (ident,name,storage,method,json.dumps(fields,ensure_ascii=False),now()))
        return {'draft_id':ident,'filename':name,'fields':fields,'method':method,
                'warning':warning,'duplicates':duplicate,'raw_excerpt':text[:1300],
                'verification':'待人工确认；识别结果不等于官方公司登记核验',
                'sent_to_ai':bool(use_ai and 'DeepSeek视觉' in method)}

    def check_plan(payload:Deployment,c):
        errors=[];warnings=[];items=[]
        ent={k:str(v or '').strip() for k,v in payload.entity.model_dump().items()}
        if payload.entity_id:
            old=row(c.execute('SELECT * FROM entities WHERE id=?',(payload.entity_id,)))
            if not old:errors.append('指定的公司主体不存在')
            else:
                ent={k:old.get(k,'') or '' for k in ('name','registration_no','country','address','phone','email')}
                if old['status']=='停用':errors.append('不能向已停用主体分配店铺')
        elif not ent['name'] or len(ent['name'])<2:
            errors.append('请确认公司法定名称，不能使用猜测或空值')
        # Required business identity + one shared customer-service phone.
        # This is the final preflight, not an optional warning.
        errors.extend(entity_issues(ent))
        if not ent['registration_no']:warnings.append('缺少主体登记编号：主体真实性仍待核验')
        if not ent['address']:warnings.append('缺少注册地址：政策模板将保留未填写变量')
        if payload.intake_draft_id:
            x=row(c.execute('SELECT id FROM intake_drafts WHERE id=? AND status=?',(payload.intake_draft_id,'待确认')))
            if not x:errors.append('主体文件识别草稿不存在或已使用')
        codes=set();domains=set();emails=set();ids=set();
        for it in payload.items:
            if it.store_id in ids:
                errors.append('同一家店铺在本次部署中出现重复');continue
            ids.add(it.store_id)
            st=row(c.execute('''SELECT s.id,s.code,s.label,s.entity_id,s.status,t.code as template_code,
                 d.domain as old_domain, COALESCE(sc.support_email,'') as old_email
                 FROM stores s LEFT JOIN templates t ON t.id=s.template_id
                 LEFT JOIN store_domains d ON d.store_id=s.id
                 LEFT JOIN store_contacts sc ON sc.store_id=s.id WHERE s.id=?''',(it.store_id,)))
            if not st:
                errors.append('部署包含不存在的店铺');continue
            if st['entity_id'] and st['entity_id']!=payload.entity_id:
                errors.append(st['code']+'已绑定其他主体；V3向导不会静默转移归属')
            try:domain=clean_domain(it.domain)
            except ValueError:domain='';errors.append(st['code']+'域名格式不合法')
            email=it.support_email.strip().lower()
            if email and not email_valid(email):errors.append(st['code']+'独立邮箱格式不合法')
            if domain:
                if domain in domains:errors.append('本批次存在重复域名：'+domain)
                domains.add(domain)
                dupe=row(c.execute('SELECT s.code FROM store_domains d JOIN stores s ON s.id=d.store_id WHERE d.domain=? AND d.store_id<>?',(domain,it.store_id)))
                if dupe:errors.append(domain+'已被'+dupe['code']+'占用')
            else:warnings.append(st['code']+'尚未设置域名')
            if email:
                if email in emails:errors.append('本批次存在重复客服邮箱：'+email)
                emails.add(email)
                dupe=row(c.execute('SELECT s.code FROM store_contacts sc JOIN stores s ON s.id=sc.store_id WHERE lower(sc.support_email)=? AND sc.store_id<>?',(email,it.store_id)))
                if dupe:errors.append(email+'已被'+dupe['code']+'占用')
            else:warnings.append(st['code']+'尚未设置独立客服邮箱')
            if email and domain and email.split('@')[1]!=domain:
                warnings.append(st['code']+'邮箱域名与店铺域名不同，请核实确实属于该店铺')
            items.append({'store_id':it.store_id,'store_code':st['code'],'template_code':st['template_code'],
                          'domain':domain,'support_email':email,'old_domain':st['old_domain'] or '',
                          'old_email':st['old_email'],'old_entity_id':st['entity_id'],
                          'label':st['label'],'email_status':'待验证' if email else '未配置'})
        if payload.capacity and len(items)>payload.capacity and not payload.entity_id:
            errors.append(f'分配{len(items)}家超出计划额度{payload.capacity}家')
        if payload.entity_id:
            old=row(c.execute('SELECT capacity,name FROM entities WHERE id=?',(payload.entity_id,)))
            if old and old['capacity']:
                assigned=c.execute('SELECT COUNT(*) FROM stores WHERE entity_id=?',(payload.entity_id,)).fetchone()[0]
                new_count=sum(1 for it in items if not it['old_entity_id'])
                if assigned+new_count>old['capacity']:
                    errors.append(f"主体{old['name']}额度{old['capacity']}，已分配{assigned}，无法再增加{new_count}家")
        if not payload.entity_id and ent.get('registration_no'):
            dup=row(c.execute('SELECT id,code FROM entities WHERE lower(registration_no)=lower(?)',(ent['registration_no'],)))
            if dup:errors.append('登记编号已存在：'+dup['code']+'，请改用已有主体')
        if not payload.entity_id and ent.get('name'):
            dup=row(c.execute('SELECT id,code FROM entities WHERE lower(name)=lower(?)',(ent['name'],)))
            if dup:errors.append('公司名称已存在：'+dup['code']+'，请改用已有主体')
        return {'errors':errors,'warnings':list(dict.fromkeys(warnings)),'entity':ent,'items':items,
                'can_commit':not errors,'requires_manual_confirmation':True}

    def policy_preview_for_item(c,entity,item):
        template=row(c.execute('''SELECT t.archive_path,t.inner_path FROM stores s
           LEFT JOIN templates t ON t.id=s.template_id WHERE s.id=?''',(item['store_id'],)))
        if not template or not template['inner_path']:
            return {'policies':[],'warning':'该店铺暂无已关联模板，无法生成七份政策'}
        path=DATA/'uploads'/template['archive_path']
        try:files=policy_files_from_zip(path,template['inner_path'])
        except Exception as ex:return {'policies':[],'warning':'无法读取原始政策：'+str(ex)[:100]}
        policies=[]
        for fname,original in files:
            store={'label':item['label']}
            rendered,remaining=render_policy(original,entity,store,item['domain'],item['support_email'])
            policies.append({'filename':Path(fname).name,'characters':len(rendered),'unresolved':remaining,
                             'preview':rendered[:820]})
        return {'policies':policies,'warning':'' if len(policies)==7 else f'仅找到{len(policies)}份政策文件，需人工检查'}

    @r.post('/deploy/plan')
    def deployment_plan(payload:Deployment):
        with db() as c:
            plan=check_plan(payload,c)
            if plan['items'] and plan['can_commit']:
                plan['policy_sample']=policy_preview_for_item(c,plan['entity'],plan['items'][0])
            return plan

    @r.post('/deploy/commit')
    def deployment_commit(payload:Deployment):
        # All mutations are performed in one DB transaction. Never change template_id.
        try:
            with db() as c:
                c.execute('BEGIN IMMEDIATE')  # serialize assignment and strict diversity recheck
                if payload.proposal_id:
                    saved=row(c.execute('SELECT * FROM auto_allocation_proposals WHERE id=?',(payload.proposal_id,)))
                    if not saved or saved['status']!='待确认':fail('自动匹配方案已使用或不存在，请重新生成',409)
                    if saved['expires_at']<=now():fail('自动匹配方案已过期，请重新生成',409)
                    expected=json.loads(saved['payload_json'])
                    expected.pop('proposal_id',None)
                    if payload.model_dump(exclude={'proposal_id'})!=expected:
                        fail('自动匹配方案内容已改变，请重新预览后确认',409)
                    # Never allow collisions with previously committed stores on the same entity.
                    refs=[x.store_id for x in payload.items]
                    existing=[]
                    if payload.entity_id:
                        existing=rows(c.execute('''SELECT s.code,t.inner_path FROM stores s
                            JOIN templates t ON t.id=s.template_id WHERE s.entity_id=?''',(payload.entity_id,)))
                    chosen=rows(c.execute('''SELECT s.code,t.inner_path FROM stores s
                        JOIN templates t ON t.id=s.template_id WHERE s.id IN ('''+','.join('?' for _ in refs)+')',refs))
                    violations=check_diversity(existing+chosen)
                    if violations:fail('装修或商品相似性约束不满足：'+'；'.join(violations[:4]),409)
                    occupied=rows(c.execute('SELECT code FROM stores WHERE id IN ('+','.join('?' for _ in refs)+') AND entity_id IS NOT NULL',refs))
                    if occupied:fail('部分店铺已经分配给其他主体，请重新匹配',409)
                plan=check_plan(payload,c)
                if plan['errors']:fail('；'.join(plan['errors']))
                ent_id=payload.entity_id
                if not ent_id:
                    ent_id=uid('ENT')
                    codes=[int(x['code'].split('-')[-1]) for x in c.execute("SELECT code FROM entities WHERE code LIKE 'ENT-%'").fetchall() if x['code'].split('-')[-1].isdigit()]
                    code='ENT-'+str(max(codes,default=0)+1).zfill(3)
                    e=plan['entity']
                    c.execute('''INSERT INTO entities(id,code,name,registration_no,country,address,phone,email,capacity,status,created_at,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(ent_id,code,e['name'],e['registration_no'],e['country'],e['address'],e['phone'],e['email'],payload.capacity,'待核验',now(),now()))
                batch=uid('DEPLOY');snapshot=[]
                for it in plan['items']:
                    sid=it['store_id']
                    prev=row(c.execute('SELECT status,entity_id FROM stores WHERE id=?',(sid,)))
                    snapshot.append({'store_id':sid,'entity_id':prev['entity_id'],'status':prev['status'],
                                     'domain':it['old_domain'],'support_email':it['old_email']})
                    # Do not claim the store is online or officially approved.
                    configured=bool(it['domain'] and it['support_email'])
                    next_status='需复核' if prev['entity_id'] else ('待部署' if configured else '待配置')
                    c.execute('UPDATE stores SET entity_id=?,status=?,updated_at=? WHERE id=?',(ent_id,next_status,now(),sid))
                    c.execute('DELETE FROM store_domains WHERE store_id=?',(sid,))
                    if it['domain']:
                        c.execute('INSERT INTO store_domains(id,store_id,domain,created_at) VALUES(?,?,?,?)',(uid('DOM'),sid,it['domain'],now()))
                    c.execute('''INSERT INTO store_contacts(store_id,support_email,email_status,updated_at)
                         VALUES(?,?,?,?) ON CONFLICT(store_id) DO UPDATE SET support_email=excluded.support_email,
                         email_status=excluded.email_status,updated_at=excluded.updated_at''',
                         (sid,it['support_email'],it['email_status'],now()))
                    c.execute('''INSERT INTO configuration_events(id,batch_id,object_type,object_id,action,before_json,after_json,created_at)
                      VALUES(?,?,?,?,?,?,?,?)''',(uid('EV'),batch,'store',sid,'deploy',json.dumps(snapshot[-1],ensure_ascii=False),json.dumps(it,ensure_ascii=False),now()))
                c.execute('INSERT INTO deployment_batches VALUES(?,?,?,?,?)',
                          (batch,ent_id,json.dumps([it['store_id'] for it in plan['items']]),json.dumps(snapshot,ensure_ascii=False),now()))
                if payload.proposal_id:
                    c.execute("UPDATE auto_allocation_proposals SET status='已提交',deployment_batch_id=? WHERE id=?",
                              (batch,payload.proposal_id))
                if payload.intake_draft_id:
                    draft=row(c.execute('SELECT * FROM intake_drafts WHERE id=? AND status=?',(payload.intake_draft_id,'待确认')))
                    if not draft:fail('源文件草稿已失效')
                    doc_id=uid('DOC')
                    c.execute('''INSERT INTO entity_documents VALUES(?,?,?,?,?,?,?)''',
                              (doc_id,ent_id,draft['filename'],draft['storage_name'],(DATA/'uploads'/draft['storage_name']).stat().st_size,'application/octet-stream',now()))
                    c.execute("UPDATE intake_drafts SET status='已归档' WHERE id=?",(draft['id'],))
                return {'ok':True,'batch_id':batch,'entity_id':ent_id,
                        'assigned':len(plan['items']),'warnings':plan['warnings'],
                        'message':'分配已保存。邮箱仍需实际开通与验证，政策仍需人工审核后发布。'}
        except IntegrityError:fail('数据库检测到重复公司、域名或邮箱，本批操作已整体回滚')

    @r.put('/stores/{store_id}/contact')
    def contact_patch(store_id:str,payload:ContactPatch):
        email=payload.support_email.strip().lower()
        if email and not email_valid(email):fail('邮箱格式错误')
        with db() as c:
            st=row(c.execute('SELECT id FROM stores WHERE id=?',(store_id,)))
            if not st:fail('店铺不存在',404)
            taken=row(c.execute('SELECT store_id FROM store_contacts WHERE lower(support_email)=? AND store_id<>?',(email,store_id))) if email else None
            if taken:fail('这个邮箱已绑定其他店铺')
            c.execute('''INSERT INTO store_contacts VALUES(?,?,?,?) ON CONFLICT(store_id)
                         DO UPDATE SET support_email=excluded.support_email,email_status=excluded.email_status,
                         updated_at=excluded.updated_at''',(store_id,email,'待验证' if email else '未配置',now()))
            c.execute("UPDATE stores SET status='需复核',updated_at=? WHERE id=?",(now(),store_id))
        return {'ok':True,'email_status':'待验证' if email else '未配置'}

    @r.get('/stores/{store_id}/policies')
    def store_policy_preview(store_id:str):
        with db() as c:
            st=row(c.execute('''SELECT s.id,s.code,s.label,s.entity_id,d.domain,sc.support_email
                 FROM stores s LEFT JOIN store_domains d ON d.store_id=s.id
                 LEFT JOIN store_contacts sc ON sc.store_id=s.id WHERE s.id=?''',(store_id,)))
            if not st:fail('店铺不存在',404)
            if not st['entity_id']:fail('请先为店铺分配公司主体')
            ent=row(c.execute('SELECT * FROM entities WHERE id=?',(st['entity_id'],)))
            result=policy_preview_for_item(c,ent,{'store_id':store_id,'label':st['label'],
                        'domain':st['domain'] or '','support_email':st['support_email'] or ''})
            result['store_code']=st['code']
            return result

    @r.get('/stores/{store_id}/policies/export.zip')
    def export_policies(store_id:str):
        with db() as c:
            st=row(c.execute('''SELECT s.id,s.code,s.label,s.entity_id,d.domain,sc.support_email,t.archive_path,t.inner_path
                   FROM stores s LEFT JOIN store_domains d ON d.store_id=s.id
                   LEFT JOIN store_contacts sc ON sc.store_id=s.id
                   LEFT JOIN templates t ON t.id=s.template_id WHERE s.id=?''',(store_id,)))
            if not st:fail('店铺不存在',404)
            if not st['entity_id'] or not st['domain'] or not st['support_email']:
                fail('主体、域名及独立客服邮箱均需先填写才能导出',409)
            ent=row(c.execute('SELECT * FROM entities WHERE id=?',(st['entity_id'],)))
            issues=entity_issues(ent)
            if issues:fail('主体信息不完整：'+'；'.join(issues),409)
            files=policy_files_from_zip(DATA/'uploads'/st['archive_path'],st['inner_path'])
            if len(files)!=7:fail('模板中没有找到完整七份政策文件',409)
            zip_buf=io.BytesIO()
            with zipfile.ZipFile(zip_buf,'w',compression=zipfile.ZIP_DEFLATED) as zout:
                for path,body in files:
                    result,left=render_policy(body,ent,st,st['domain'],st['support_email'])
                    if left:fail('政策仍包含未填写变量：'+', '.join(left),409)
                    filename=Path(path).stem+'.txt'
                    zout.writestr(filename,result)
                zout.writestr('CONFIGURATION.json',json.dumps({'store_code':st['code'],'domain':st['domain'],
                    'company_name':ent['name'],'support_email':st['support_email'],'verification':'邮箱及政策尚未人工确认或发布'},ensure_ascii=False,indent=2))
            zip_buf.seek(0)
            return StreamingResponse(zip_buf,media_type='application/zip',headers={
                'Content-Disposition':f'attachment; filename="BIGBANG_{st["code"]}_POLICIES.zip"'})

    @r.get('/deployments')
    def deployments(limit:int=Query(20,ge=1,le=100)):
        with db() as c:
            return rows(c.execute('''SELECT d.id,d.created_at,d.entity_id,e.name as entity_name,d.store_ids_json
               FROM deployment_batches d JOIN entities e ON e.id=d.entity_id ORDER BY d.created_at DESC LIMIT ?''',(limit,)))


    @r.post('/auto/preview')
    def auto_preview(req:AutoMatchRequest):
        # Only existing *complete storefront packages* can be assigned.
        # Never recombine a product CSV with another group's Liquid files.
        try:
            normalized=[clean_domain(x) for x in req.domains]
        except ValueError as exc:fail('域名格式错误：'+str(exc))
        if len(set(normalized))!=len(normalized):fail('本次输入的域名存在重复',409)
        with db() as c:
            if req.entity_id:
                e=row(c.execute('SELECT * FROM entities WHERE id=?',(req.entity_id,)))
                if not e:fail('主体不存在',404)
                if e['status']=='停用':fail('停用主体不能分配店铺',409)
            else:
                if not req.entity.name.strip() or len(req.entity.name.strip())<2:
                    fail('请先确认公司主体的法定名称')
            try:chosen=choose_candidates(c,len(normalized),req.entity_id)
            except AllocationError as exc:fail(str(exc),409)
            items=[];details=[]
            for domain,store in zip(normalized,chosen):
                email=(req.email_prefix+'@'+domain).lower()
                items.append(DeploymentItem(store_id=store['id'],domain=domain,support_email=email))
                details.append({'store_id':store['id'],'store_code':store['code'],
                                'template_code':store['template_code'],
                                'template_group':store['meta']['template_group'],
                                'category':store['meta']['category'],
                                'product_family':store['meta']['product_family'],
                                'style_family':store['meta']['style_family'],
                                'style_name':store['meta']['style_name'],
                                'domain':domain,'support_email':email})
            capacity=len(normalized) if not req.entity_id else 0
            payload=Deployment(entity_id=req.entity_id,intake_draft_id=req.intake_draft_id,
                entity=req.entity,capacity=capacity,items=items)
            plan=check_plan(payload,c)
            if plan['errors']:fail('；'.join(plan['errors']),409)
            p_id=uid('MATCH')
            expires=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
            c.execute('INSERT INTO auto_allocation_proposals(id,payload_json,created_at,expires_at) VALUES(?,?,?,?)',
                      (p_id,json.dumps(payload.model_dump(),ensure_ascii=False),now(),expires))
            plan['policy_sample']=policy_preview_for_item(c,plan['entity'],plan['items'][0])
            return {'proposal_id':p_id,'expires_at':expires,'mode':'严格随机匹配',
                'match_rules':['同主体不能重复装修结构类型','同主体不能重复装修模板组',
                               '同主体不能重复商品品类','同主体不能重复商品大类',
                               '已分配店铺不再参与匹配'],
                'items':details,'plan':plan,
                'note':'仅从原始300套完整资源中整体选择，不修改商品CSV和Liquid。装修相似性是代码结构启发式，不能替代人工截图复核。'}

    @r.post('/auto/commit')
    def auto_commit(req:AutoCommitRequest):
        with db() as c:
            saved=row(c.execute('SELECT * FROM auto_allocation_proposals WHERE id=?',(req.proposal_id,)))
            if not saved or saved['status']!='待确认':fail('方案不存在或已经提交',409)
            if saved['expires_at']<=now():fail('预览已超过30分钟，请重新匹配',409)
            payload=Deployment.model_validate(json.loads(saved['payload_json']))
        payload.proposal_id=req.proposal_id
        return deployment_commit(payload)

    return r
