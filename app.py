"""BIG BANG V1 local management API.
Local-only MVP: single administrator and in-process background audits.
Do not bind to a public interface without production security hardening.
"""
from __future__ import annotations
import base64, csv, hashlib, hmac, io, json, os, re, secrets, threading, time, zipfile
from pathlib import Path, PurePosixPath
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Response, Depends, UploadFile, File, Query
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlite3 import IntegrityError

def read_env():
    envfile=Path(__file__).resolve().parent/'.env'
    if not envfile.is_file():return
    for line in envfile.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            k,v=line.split('=',1)
            os.environ.setdefault(k.strip(),v.strip())
read_env()
from db import DATA, init, init_v3, db, uid, now, rows, row
from audit_engine import perform_audit, normalize_host
ROOT=Path(__file__).resolve().parent
app=FastAPI(title='大爆炸 BIG BANG',version='11.4.3-V35')
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
init()
init_v3()
from bootstrap_v16 import bootstrap
bootstrap()
AUTH_PASSWORD=os.getenv('ADMIN_PASSWORD','')
AUTH_SECRET=os.getenv('SESSION_SECRET','').encode()
if not AUTH_PASSWORD or len(AUTH_SECRET)<32:
    raise RuntimeError('Run python setup.py to generate private ADMIN_PASSWORD and SESSION_SECRET before starting.')

@app.middleware('http')
async def local_origin_guard(request:Request,call_next):
    # Desktop mode never accepts DNS-rebound hosts or remote clients.
    if os.getenv('BIGBANG_DESKTOP_MODE') == '1':
        from urllib.parse import urlsplit
        host = (request.headers.get('host') or '').split(':')[0].lower()
        client = request.client.host if request.client else ''
        if host not in ('localhost', '127.0.0.1', '[::1]') or client not in (('127.0.0.1','::1','testclient') if os.getenv('BIGBANG_TEST_MODE')=='1' else ('127.0.0.1','::1')):
            return Response('Local dashboard only',status_code=403)
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin','')
        if origin:
            from urllib.parse import urlsplit
            u=urlsplit(origin)
            if u.netloc!=request.headers.get('host'):
                return Response('Cross-origin mutation blocked',status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='SAMEORIGIN' if (request.url.path.startswith('/api/v9/assets/') or request.url.path.startswith('/api/v10/studio/')) else 'DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://cdn.shopify.com https://m.media-amazon.com; connect-src 'self'; object-src 'none'; frame-src 'self'; frame-ancestors 'self'; base-uri 'self'"
    return response

def make_token():
    body=base64.urlsafe_b64encode(f'admin:{int(time.time())+12*3600}'.encode()).decode().rstrip('=')
    sig=hmac.new(AUTH_SECRET,body.encode(),hashlib.sha256).hexdigest()
    return body+'.'+sig

def verify_token(token):
    try:
        body,sig=token.rsplit('.',1)
        target=hmac.new(AUTH_SECRET,body.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,target):return False
        user,expire=base64.urlsafe_b64decode(body+'===').decode().split(':')
        return user=='admin' and int(expire)>=time.time()
    except Exception:return False

def guard(request:Request):
    if os.getenv('BIGBANG_DESKTOP_MODE') == '1' and request.client and request.client.host in (('127.0.0.1','::1','testclient') if os.getenv('BIGBANG_TEST_MODE')=='1' else ('127.0.0.1','::1')):
        return True
    if not verify_token(request.cookies.get('bigbang_session','')):
        raise HTTPException(status_code=401,detail='请先登录')
    return True

def fail(msg,status=400): raise HTTPException(status_code=status,detail=msg)

@app.get('/api/health')
def health():
    try:
        with db() as c:
            total=c.execute('SELECT count(*) FROM stores').fetchone()[0]
            return {'ok': True, 'version':'11.4.3-V35', 'stores':total, 'database':'connected'}
    except Exception:
        raise HTTPException(status_code=503, detail='本地数据库暂时无法连接，请查看启动窗口错误日志')

@app.get('/',response_class=HTMLResponse)
def home(): return (ROOT/'static'/'index.html').read_text(encoding='utf-8')

@app.get('/quality',response_class=HTMLResponse)
def quality_page(): return (ROOT/'static'/'quality.html').read_text(encoding='utf-8')

class Login(BaseModel):
    password:str

@app.post('/api/login')
def login(payload:Login,response:Response):
    if not hmac.compare_digest(payload.password,AUTH_PASSWORD):fail('登录密码错误',401)
    response.set_cookie('bigbang_session',make_token(),httponly=True,samesite='strict',secure=False,max_age=12*3600,path='/')
    return {'ok':True}

@app.post('/api/logout')
def logout(response:Response, _:bool=Depends(guard)):
    response.delete_cookie('bigbang_session',path='/')
    return {'ok':True}

from deepseek_diagnostics import status as deepseek_status, run_test as deepseek_run_test

class DesktopAPIKey(BaseModel):
    api_key: str = Field(min_length=12, max_length=256)

@app.get('/api/desktop/setup-status')
def desktop_setup_status(_: bool = Depends(guard)):
    return {'desktop_mode':os.getenv('BIGBANG_DESKTOP_MODE')=='1',
            'api_configured':bool(os.getenv('DEEPSEEK_API_KEY','').strip()),
            'model':os.getenv('DEEPSEEK_MODEL','deepseek-flash'),
            'resource':'BIG_BANG_V35',
            'local_only':True}

@app.post('/api/desktop/save-api-key')
def save_desktop_api_key(body:DesktopAPIKey, _: bool=Depends(guard)):
    if os.getenv('BIGBANG_DESKTOP_MODE')!='1':
        raise HTTPException(403,'Only available in local desktop mode')
    key=body.api_key.strip()
    if not (12<=len(key)<=256) or any(ch in key for ch in ('\\r','\\n','\\0','\\x00','\r','\n')):
        raise HTTPException(422,'Invalid API key format')
    filename=ROOT/'.env'
    current=filename.read_text('utf-8') if filename.exists() else ''
    lines=[x for x in current.splitlines() if not x.startswith('DEEPSEEK_API_KEY=')]
    lines.append('DEEPSEEK_API_KEY='+key)
    temp=filename.with_suffix('.env-tmp')
    try:
        with open(temp,'w',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines)+'\n')
        try:os.chmod(temp,0o600)
        except OSError:pass
        os.replace(temp,filename)
    finally:
        temp.unlink(missing_ok=True)
    os.environ['DEEPSEEK_API_KEY']=key
    return {'ok':True,'configured':True,'note':'Saved locally; connection has not been verified.'}

@app.get('/api/deepseek/status')
def get_deepseek_connection_status(_:bool=Depends(guard)):
    return deepseek_status()

@app.post('/api/deepseek/test')
def test_deepseek_connection(_:bool=Depends(guard)):
    # A real, minimal API request; no uploaded documents or store data transmitted.
    return deepseek_run_test()

@app.get('/api/me')
def me(_:bool=Depends(guard)):
    return {'user':'admin','model':os.getenv('DEEPSEEK_MODEL','deepseek-flash'),
            'deepseek_connected':bool(os.getenv('DEEPSEEK_API_KEY','').strip()),'version':'11.4.3-V35'}

def next_code(c,table,prefix):
    used=[int(x['code'].split('-')[-1]) for x in c.execute(f'SELECT code FROM {table} WHERE code LIKE ?', (prefix+'-%',)).fetchall()
          if re.fullmatch(re.escape(prefix)+r'-\d+',x['code'])]
    n=max(used,default=0)+1
    return f'{prefix}-{n:03d}'

class EntityInput(BaseModel):
    name:str=Field(min_length=2,max_length=255)
    registration_no:str=Field(default='',max_length=100)
    country:str=Field(default='',max_length=100)
    address:str=Field(default='',max_length=500)
    phone:str=Field(default='',max_length=80)
    email:str=Field(default='',max_length=255)
    capacity:int=Field(default=0,ge=0,le=10000)
    status:str='待核验'

def entity_valid(x:EntityInput):
    if x.status not in ['待核验','已核验','异常','停用']:fail('主体状态无效')

@app.get('/api/entities')
def entities(_:bool=Depends(guard)):
    with db() as c:
        return rows(c.execute('''SELECT e.*, (SELECT COUNT(*) FROM stores s WHERE s.entity_id=e.id) as assigned,
                      (SELECT COUNT(*) FROM entity_documents d WHERE d.entity_id=e.id) as documents FROM entities e ORDER BY e.created_at DESC'''))

@app.post('/api/entities')
def create_entity(x:EntityInput,_:bool=Depends(guard)):
    entity_valid(x)
    with db() as c:
        id=uid('ENT');code=next_code(c,'entities','ENT')
        c.execute('INSERT INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                  (id,code,x.name.strip(),x.registration_no.strip(),x.country.strip(),x.address.strip(),x.phone.strip(),x.email.strip(),x.capacity,x.status,now(),now()))
    return {'id':id,'code':code}

@app.put('/api/entities/{id}')
def update_entity(id:str,x:EntityInput,_:bool=Depends(guard)):
    entity_valid(x)
    with db() as c:
        old=row(c.execute('SELECT * FROM entities WHERE id=?',(id,)))
        if not old:fail('主体不存在',404)
        assigned=c.execute('SELECT COUNT(*) FROM stores WHERE entity_id=?',(id,)).fetchone()[0]
        if x.capacity and x.capacity<assigned:fail(f'当前已分配{assigned}家，不能将额度降低到{x.capacity}')
        c.execute('''UPDATE entities SET name=?,registration_no=?,country=?,address=?,phone=?,email=?,capacity=?,status=?,updated_at=? WHERE id=?''',
                  (x.name.strip(),x.registration_no.strip(),x.country.strip(),x.address.strip(),x.phone.strip(),x.email.strip(),x.capacity,x.status,now(),id))
        changed=any(old[k]!=getattr(x,k) for k in ['name','registration_no','address','phone','email'])
        if changed:
            c.execute("UPDATE stores SET status='需复核',updated_at=? WHERE entity_id=?",(now(),id))
    return {'ok':True,'affected_stores':assigned if changed else 0}

@app.post('/api/entities/{id}/documents')
async def upload_entity_document(id:str,file:UploadFile=File(...),_:bool=Depends(guard)):
    with db() as c:
        if not row(c.execute('SELECT id FROM entities WHERE id=?',(id,))):fail('主体不存在',404)
    name=(file.filename or '').split('/')[-1].split('\\')[-1]
    suffix=Path(name).suffix.lower()
    data=await file.read(12*1024*1024+1)
    from v3_services import validate_upload
    try:suffix=validate_upload(name,data)
    except ValueError as ex:fail(str(ex))
    ident=uid('DOC')
    dest=DATA/'uploads'/(ident+suffix)
    dest.write_bytes(data)
    try:dest.chmod(0o600)
    except OSError:pass
    with db() as c:
        c.execute('INSERT INTO entity_documents VALUES (?,?,?,?,?,?,?)',(ident,id,name,dest.name,len(data),file.content_type or '',now()))
    return {'id':ident,'filename':name}

@app.get('/api/entities/{id}/documents')
def list_entity_documents(id:str,_:bool=Depends(guard)):
    with db() as c:return rows(c.execute('SELECT id,filename,byte_size,uploaded_at FROM entity_documents WHERE entity_id=? ORDER BY uploaded_at DESC',(id,)))

@app.get('/api/documents/{id}/download')
def download_document(id:str,_:bool=Depends(guard)):
    with db() as c:
        record=row(c.execute('SELECT * FROM entity_documents WHERE id=?',(id,)))
    if not record:fail('文件不存在',404)
    p=DATA/'uploads'/record['storage_name']
    if not p.exists():fail('文件丢失',404)
    return FileResponse(p,filename=record['filename'],media_type='application/octet-stream')

CATEGORY_MARKERS={'商品csv','商品文件','商品csv文件','products','productcsv','装修文件','装修','liquid','design','七个条款文件','七份条款文件','条款文件','policies','policy'}

def discover_templates(file_names):
    grouped={}
    for name in file_names:
        path=PurePosixPath(name.replace('\\','/'))
        parts=path.parts
        if len(parts)<2:continue
        for i,x in enumerate(parts[:-1]):
            low=x.lower().replace(' ','').replace('_','').replace('-','')
            marker=low in CATEGORY_MARKERS or ('装修' in x or '条款' in x or '商品csv' in low)
            if marker and i>0:
                parent='/'.join(parts[:i])
                grouped.setdefault(parent,set()).add('policy' if '条款' in x or 'polic' in low else 'design' if '装修' in x or 'liquid' in low or 'design' in low else 'products')
    found=[p for p,types in grouped.items() if len(types)>=2]
    # Keep deep, leaf-level template folders, rather than an enclosing directory.
    return sorted(p for p in found if not any(x.startswith(p+'/') for x in found))

@app.get('/api/templates')
def templates(_:bool=Depends(guard)):
    with db() as c:return rows(c.execute('SELECT * FROM templates ORDER BY created_at DESC,code ASC'))

@app.get('/api/templates/{id}/download')
def download_template(id:str,_:bool=Depends(guard)):
    with db() as c:
        r=row(c.execute('SELECT archive_name,archive_path FROM templates WHERE id=?',(id,)))
    if not r:fail('模板不存在',404)
    p=DATA/'uploads'/r['archive_path']
    if not p.is_file():fail('源ZIP已丢失',404)
    return FileResponse(p,filename=r['archive_name'],media_type='application/zip')

@app.get('/api/templates/{id}/bundle.zip')
def download_one_template_bundle(id:str,_:bool=Depends(guard)):
    """Download only the unmodified files under one registered leaf folder."""
    with db() as c:
        r=row(c.execute('SELECT label,archive_path,inner_path FROM templates WHERE id=?',(id,)))
    if not r:fail('模板不存在',404)
    src=DATA/'uploads'/r['archive_path']
    if not src.is_file():fail('源ZIP文件不存在',404)
    base=(r['inner_path'] or '').strip('/')
    if not base:fail('当前模板未指定独立的原始文件夹',400)
    output=io.BytesIO()
    with zipfile.ZipFile(src,'r') as zin, zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zout:
        names=[n for n in zin.namelist() if n.startswith(base+'/') and not n.endswith('/')]
        if not names:fail('源ZIP中未找到对应模板文件夹',404)
        for name in names:
            rel=name[len(base)+1:]
            if not rel or rel.startswith('/') or '..' in PurePosixPath(rel).parts:continue
            zout.writestr(rel,zin.read(name))
    output.seek(0)
    return StreamingResponse(output,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="BIGBANG_{id[-6:]}.zip"'})

@app.post('/api/templates/import')
async def import_template_zip(file:UploadFile=File(...),_:bool=Depends(guard)):
    filename=(file.filename or 'templates.zip').split('/')[-1].split('\\')[-1]
    with db() as check_db:
        current=check_db.execute('SELECT COUNT(*) FROM templates').fetchone()[0]
    if current>=300:
        fail('当前已有300套模板。请到「运行准备中心」预检新版ZIP；禁止直接追加造成模板编号错乱。',409)
    if not filename.lower().endswith('.zip'):fail('请选择ZIP压缩包')
    data=await file.read(420*1024*1024+1)
    if not data or len(data)>420*1024*1024:fail('ZIP文件过大（上限420MB）')
    checksum=hashlib.sha256(data).hexdigest()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            info=z.infolist()
            if len(info)>100000:fail('ZIP条目数量异常')
            if sum(x.file_size for x in info)>5_000_000_000:fail('ZIP解压后体积异常')
            for x in info:
                p=PurePosixPath(x.filename.replace('\\','/'))
                if p.is_absolute() or '..' in p.parts:fail('ZIP包含不安全的文件路径')
            paths=[x.filename for x in info if not x.is_dir() and not x.filename.startswith('__MACOSX')]
            groups=discover_templates(paths)
            if not groups:
                groups=['']
    except zipfile.BadZipFile:fail('ZIP文件损坏或格式不正确')
    with db() as c:
        existing=rows(c.execute('SELECT code FROM templates WHERE checksum=?',(checksum,)))
        if existing:return {'added':0,'duplicate':True,'total':len(existing),'message':'同一ZIP已导入，已跳过重复内容'}
    storage=uid('ARC')+'.zip'
    target=DATA/'uploads'/storage
    target.write_bytes(data)
    try:target.chmod(0o600)
    except OSError:pass
    added=[]
    try:
        with db() as c:
            for group in groups:
                code=next_code(c,'templates','TPL')
                title=group or filename.removesuffix('.zip')
                count=sum(1 for p in paths if p.startswith(group+'/')) if group else len(paths)
                id=uid('TPL')
                c.execute('INSERT INTO templates VALUES (?,?,?,?,?,?,?,?,?)',
                          (id,code,title,filename,storage,group,count,checksum,now()))
                added.append({'id':id,'code':code,'label':title})
    except Exception:
        target.unlink(missing_ok=True);raise
    return {'added':len(added),'total':len(groups),'items':added[:12], 'message':'仅登记模板，不修改商品和装修内容'}

class StoreInput(BaseModel):
    code:Optional[str]=None
    label:str=Field(default='',max_length=120)
    entity_id:Optional[str]=None
    template_id:Optional[str]=None
    domain:str=Field(default='',max_length=255)
    status:str='待配置'

ALLOWED_STORE_STATUS=['待配置','待部署','待审核','整改中','需复核','验收通过']

def store_assign(c,id,x:StoreInput,editing=False):
    if x.status not in ALLOWED_STORE_STATUS:fail('店铺状态不正确')
    if x.entity_id:
        ent=row(c.execute('SELECT * FROM entities WHERE id=?',(x.entity_id,)))
        if not ent:fail('主体不存在')
        count=c.execute('SELECT COUNT(*) FROM stores WHERE entity_id=? AND id<>?',(x.entity_id,id)).fetchone()[0]
        if ent['capacity'] and count>=ent['capacity']:fail(f'主体 {ent["name"]} 已达到分配数量上限')
    if x.template_id and not row(c.execute('SELECT id FROM templates WHERE id=?',(x.template_id,))):fail('模板不存在')
    domain=normalize_host(x.domain) if x.domain.strip() else ''
    if domain:
        taken=row(c.execute('SELECT store_id FROM store_domains WHERE domain=?',(domain,)))
        if taken and taken['store_id']!=id:fail('域名已经绑定到另一家店铺')
    if editing:
        c.execute('UPDATE stores SET label=?,entity_id=?,template_id=?,status=?,updated_at=? WHERE id=?',
                  (x.label.strip(),x.entity_id,x.template_id,x.status,now(),id))
    else:
        code=(x.code or next_code(c,'stores','STORE')).strip().upper()
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{1,39}',code):fail('店铺编号只能包含英文、数字、-和_')
        c.execute('INSERT INTO stores VALUES (?,?,?,?,?,?,?,?)',
                  (id,code,x.label.strip(),x.entity_id,x.template_id,x.status,now(),now()))
    c.execute('DELETE FROM store_domains WHERE store_id=?',(id,))
    if domain:c.execute('INSERT INTO store_domains VALUES (?,?,?,?)',(uid('DOM'),id,domain,now()))

def all_stores(c):
    return rows(c.execute('''SELECT s.*,e.code as entity_code,e.name as entity_name,t.code as template_code,t.label as template_label,d.domain,
      (SELECT a.status FROM audits a WHERE a.store_id=s.id ORDER BY a.started_at DESC, a.rowid DESC LIMIT 1) as audit_status,
      (SELECT COUNT(*) FROM audit_issues i JOIN audits a ON a.id=i.audit_id WHERE a.store_id=s.id AND a.id=(SELECT a2.id FROM audits a2 WHERE a2.store_id=s.id ORDER BY a2.started_at DESC,a2.rowid DESC LIMIT 1)) as issue_count
      FROM stores s LEFT JOIN entities e ON e.id=s.entity_id LEFT JOIN templates t ON t.id=s.template_id
      LEFT JOIN store_domains d ON d.store_id=s.id ORDER BY s.code'''))

@app.get('/api/stores')
def stores(_:bool=Depends(guard)):
    with db() as c:return all_stores(c)

@app.post('/api/stores')
def create_store(x:StoreInput,_:bool=Depends(guard)):
    with db() as c:
        id=uid('STORE')
        try:store_assign(c,id,x)
        except IntegrityError:fail('店铺编号或域名重复')
    return {'id':id}

@app.put('/api/stores/{id}')
def update_store(id:str,x:StoreInput,_:bool=Depends(guard)):
    with db() as c:
        old=row(c.execute('SELECT * FROM stores WHERE id=?',(id,)))
        if not old:fail('店铺不存在',404)
        prior=row(c.execute('SELECT domain FROM store_domains WHERE store_id=?',(id,)))
        if prior and prior['domain']!=x.domain or old['entity_id']!=x.entity_id or old['template_id']!=x.template_id:
            x.status='需复核'
        try:store_assign(c,id,x,True)
        except IntegrityError:fail('域名重复')
    return {'ok':True}

@app.post('/api/stores/import-csv')
async def import_stores_csv(file:UploadFile=File(...),_:bool=Depends(guard)):
    data=await file.read(3*1024*1024+1)
    if len(data)>3*1024*1024:fail('CSV不能超过3MB')
    try:
        reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
        if not reader.fieldnames or 'store_code' not in reader.fieldnames:fail('CSV必须包含store_code列')
        input_rows=list(reader)
    except UnicodeError:fail('CSV请保存为UTF-8编码')
    if len(input_rows)>2000:fail('单次最多导入2000行')
    if not input_rows:fail('CSV没有有效数据')
    done=0
    try:
        with db() as c:
            entities_map={x['code']:x['id'] for x in rows(c.execute('SELECT code,id FROM entities'))}
            templates_map={x['code']:x['id'] for x in rows(c.execute('SELECT code,id FROM templates'))}
            for num,r in enumerate(input_rows,2):
                code=(r.get('store_code') or '').strip().upper()
                if not code:fail(f'第{num}行缺少store_code')
                ent=(r.get('entity_code') or '').strip().upper()
                tpl=(r.get('template_code') or '').strip().upper()
                if ent and ent not in entities_map:fail(f'第{num}行找不到主体编号 {ent}')
                if tpl and tpl not in templates_map:fail(f'第{num}行找不到模板编号 {tpl}')
                old=row(c.execute('SELECT id FROM stores WHERE code=?',(code,)))
                x=StoreInput(code=code,label=r.get('label') or '',entity_id=entities_map.get(ent),
                             template_id=templates_map.get(tpl),domain=r.get('domain') or '',status='待配置')
                store_assign(c,old['id'] if old else uid('STORE'),x,bool(old))
                done+=1
    except IntegrityError:fail('CSV中存在重复编号或域名，已回滚整批导入')
    return {'imported':done}

@app.get('/api/overview')
def overview(_:bool=Depends(guard)):
    with db() as c:
        ent=c.execute('SELECT COUNT(*) FROM entities').fetchone()[0]
        tpl=c.execute('SELECT COUNT(*) FROM templates').fetchone()[0]
        stores=c.execute('SELECT COUNT(*) FROM stores').fetchone()[0]
        domain=c.execute('SELECT COUNT(*) FROM store_domains').fetchone()[0]
        audit=c.execute('SELECT COUNT(*) FROM audits').fetchone()[0]
        active=c.execute("SELECT COUNT(*) FROM audits WHERE status IN ('排队中','正在采集','DeepSeek分析中')").fetchone()[0]
        latest=rows(c.execute('''SELECT a.id,a.status,a.mode,a.started_at,s.code as store_code,d.domain,a.summary_json
          FROM audits a JOIN stores s ON a.store_id=s.id LEFT JOIN store_domains d ON d.store_id=s.id
          ORDER BY a.rowid DESC LIMIT 10'''))
    return {'entities':ent,'templates':tpl,'stores':stores,'domains':domain,'audits':audit,'running':active,'recent':latest}

class AuditRequest(BaseModel):
    store_ids:list[str]=Field(min_length=1,max_length=300)
    mode:str='rules'


def async_audit_runner(ids):
    for aid in ids:
        try:perform_audit(aid)
        except Exception as exc:
            with db() as c:c.execute('UPDATE audits SET status=?,error=?,finished_at=? WHERE id=?',('检测失败',str(exc)[:1000],now(),aid))

@app.post('/api/audits')
def start_audits(payload:AuditRequest,_:bool=Depends(guard)):
    if payload.mode not in ('rules','ai'):fail('审核模式无效')
    distinct=list(dict.fromkeys(payload.store_ids))
    with db() as c:
        if len(distinct)>300:fail('单批最多300家店铺')
        found=c.execute('SELECT COUNT(*) FROM stores WHERE id IN ('+','.join('?' for _ in distinct)+')',distinct).fetchone()[0]
        if found!=len(distinct):fail('包含不存在的店铺')
        if c.execute("SELECT COUNT(*) FROM audits WHERE status IN ('排队中','正在采集','DeepSeek分析中')").fetchone()[0]>320:
            fail('正在执行的审核任务过多，请先完成当前任务')
        batch=uid('BATCH') if len(distinct)>1 else None
        ids=[]
        for store_id in distinct:
            aid=uid('AUD')
            c.execute('INSERT INTO audits(id,store_id,batch_id,mode,status) VALUES (?,?,?,?,?)',(aid,store_id,batch,payload.mode,'排队中'))
            ids.append(aid)
    threading.Thread(target=async_audit_runner,args=(ids,),daemon=True,name='bigbang-audit').start()
    return {'created':len(ids),'audit_ids':ids,'batch_id':batch}

@app.get('/api/audits')
def get_audits(limit:int=Query(60,ge=1,le=500),_:bool=Depends(guard)):
    with db() as c:
        return rows(c.execute('''SELECT a.*,s.code as store_code,d.domain,(
           SELECT COUNT(*) FROM audit_issues i WHERE i.audit_id=a.id) as issue_count
           FROM audits a JOIN stores s ON s.id=a.store_id LEFT JOIN store_domains d ON d.store_id=s.id
           ORDER BY a.rowid DESC LIMIT ?''',(limit,)))

@app.get('/api/audits/{id}')
def get_audit(id:str,_:bool=Depends(guard)):
    with db() as c:
        audit=row(c.execute('''SELECT a.*,s.code as store_code,d.domain FROM audits a
           JOIN stores s ON s.id=a.store_id LEFT JOIN store_domains d ON d.store_id=s.id WHERE a.id=?''',(id,)))
        if not audit:fail('审核记录不存在',404)
        audit['issues']=rows(c.execute('SELECT * FROM audit_issues WHERE audit_id=? ORDER BY CASE severity WHEN "严重" THEN 1 WHEN "一般" THEN 2 ELSE 3 END,id',(id,)))
        audit['evidence']=rows(c.execute('SELECT * FROM audit_evidence WHERE audit_id=? ORDER BY checked_at',(id,)))
    try:audit['summary']=json.loads(audit['summary_json'])
    except Exception:audit['summary']={}
    return audit

class IssuePatch(BaseModel):
    state:str
@app.patch('/api/issues/{id}')
def patch_issue(id:str, x:IssuePatch,_:bool=Depends(guard)):
    if x.state not in ('待处理','处理中','待复检','已解决','已接受风险'):fail('无效问题状态')
    with db() as c:
        changed=c.execute('UPDATE audit_issues SET state=? WHERE id=?',(x.state,id)).rowcount
        if not changed:fail('问题不存在',404)
    return {'ok':True}

@app.get('/api/audits/{id}/export.json')
def export_audit(id:str,_:bool=Depends(guard)):
    payload=get_audit(id,True)
    blob=json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8')
    return StreamingResponse(io.BytesIO(blob),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="{id}.json"'})

@app.get('/api/export/stores.csv')
def export_stores(_:bool=Depends(guard)):
    with db() as c: data=all_stores(c)
    out=io.StringIO()
    writer=csv.writer(out)
    writer.writerow(['store_code','label','template_code','entity_code','domain','status','audit_status','issue_count'])
    for v in data:
        writer.writerow([v.get(k) or '' for k in ('code','label','template_code','entity_code','domain','status','audit_status','issue_count')])
    return StreamingResponse(io.BytesIO(('\ufeff'+out.getvalue()).encode('utf-8')),media_type='text/csv',
           headers={'Content-Disposition':'attachment; filename="BIG_BANG_stores.csv"'})

# V3 routes are intentionally isolated from the original V2.1 template registry.
from v3_routes import build_v3_router
app.include_router(build_v3_router(guard, fail))
from bulk_routes import init_bulk, build_bulk_router
init_bulk()
app.include_router(build_bulk_router(guard, fail))

# V5: customer-facing deliverable workbench and export
from v5_routes import init_v5, build_v5_router
init_v5()
app.include_router(build_v5_router(guard, fail))

# V7: immutable delivery versions, strict preflight, source-grounded comparison.
from v7_routes import init_v7, build_v7_router
init_v7()
app.include_router(build_v7_router(guard))

from v8_routes import build_v8_router
app.include_router(build_v8_router(guard))

from v9_routes import build_v9_router
app.include_router(build_v9_router(guard))

# V10.5 Studio: working-copy editing, evidence-based DeepSeek policy/theme audit and releases.
from v10_studio import init_v10,build_v10_router,build_v10_autofill_router
init_v10()
app.include_router(build_v10_router(guard))
app.include_router(build_v10_autofill_router(guard))


# BIG BANG V11: single-action policy/footer rendering and archive
from policy_routes import init_policy_pipeline, build_policy_router
init_policy_pipeline()
app.include_router(build_policy_router(guard))

# V11.2: read-only quality center, safe source update preflight and honest dual-platform capability status.
from readiness_api import build_readiness_router
app.include_router(build_readiness_router(guard))

# V23 raw SHOPLINE + Shopify source and platform-specific exports.
from v16_routes import build_v16_router
app.include_router(build_v16_router(guard))
from v16_batch_delivery import build_v16_batch_router
app.include_router(build_v16_batch_router(guard))
@app.get("/platform-assets",response_class=HTMLResponse)
def platform_asset_ui():return (ROOT/"static"/"platform_assets.html").read_text(encoding="utf-8")
