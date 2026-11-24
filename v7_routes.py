"""BIG BANG V7: source-grounded visual comparison, release gate, immutable delivery versions.

No template or product recombination. Only verified entity/contact substitutions from V5.
No false claims of screenshots, account verification, image rights or AppLovin approval.
"""
from __future__ import annotations

import hashlib
import difflib
import html
import io
import json
import os
import re
import zipfile
from collections import Counter
from pathlib import PurePosixPath
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from auto_match import check_diversity, identify_template
from db import DATA, db, now, row, rows, uid
from entity_guard import CJK, TOKEN, entity_issues
from v5_routes import batch_details, build_package, audit_batch, render_one_store, SHOP_FOLDERS

# English-only directories in *generated* Shopify deliverables.  Originals untouched.
KIND_EN = {'商品文件夹':'Products', '装修文件夹':'Theme', '条款文件夹':'Policies'}
RELEASE_DIR = DATA / 'deliveries'
RELEASE_DIR.mkdir(exist_ok=True, parents=True)


def init_v7():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS delivery_versions (
          id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES deployment_batches(id),
          content_hash TEXT NOT NULL, size_bytes INTEGER NOT NULL,
          storage_name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
          report_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_delivery_versions_batch ON delivery_versions(batch_id,created_at);
        ''')


def _required_batch(batch_id):
    batch = batch_details(batch_id)
    if batch is None:
        raise HTTPException(404,detail='交付批次不存在')
    return batch


def _store_rows(c,store_codes):
    unique=list(dict.fromkeys(store_codes))
    if not unique or len(unique)>10:
        raise HTTPException(400, detail='请选择1到10家店铺进行比较')
    if len(unique)!=len(store_codes):
        raise HTTPException(400,detail='店铺编号重复')
    q=','.join('?' for _ in unique)
    items=rows(c.execute(f'''SELECT s.code,t.inner_path,t.archive_path,t.code template_code,
        d.domain FROM stores s JOIN templates t ON s.template_id=t.id
        LEFT JOIN store_domains d ON s.id=d.store_id
        WHERE s.code IN ({q})''',unique))
    lookup={r['code']:r for r in items}
    if len(items)!=len(unique):
        raise HTTPException(404,detail='部分店铺编号不存在')
    return [lookup[k] for k in unique]


class VisualSelection(BaseModel):
    store_codes:list[str]=Field(min_length=1,max_length=10)


def _hero_image(source):
    # Only existing customer-supplied image references. Never construct new images.
    found=re.findall(r'https://cdn\.shopify\.com/[A-Za-z0-9_\-/%?.=&;]+',source)
    for x in found:
        value=html.unescape(x)
        if 'cdn.shopify.com' in urlparse(value).netloc and re.search(r'\.(?:jpg|jpeg|png|webp)(?:\?|$)',value,re.I):
            return value
    return ''


def _visual_rows(items):
    result=[]
    zipcache={}
    try:
        for item in items:
            meta=identify_template(item['inner_path'])
            if meta is None:
                raise HTTPException(409,detail=item['code']+' 目录不是已知的原始完整组合')
            file=DATA/'uploads'/item['archive_path']
            if not file.is_file():
                raise HTTPException(409,detail=item['code']+' 的原始ZIP不存在')
            key=str(file)
            if key not in zipcache:
                zipcache[key]=zipfile.ZipFile(file)
            name=item['inner_path'].rstrip('/')+'/装修文件/02-homepage.liquid'
            try: source=zipcache[key].read(name).decode('utf-8-sig',errors='replace')
            except KeyError:raise HTTPException(409,detail=item['code']+' 的首页Liquid不存在')
            html_classes=re.findall(r'class=["\']([^"\']+)',source)
            classes=sorted(set(x for cl in html_classes for x in cl.split() if x.startswith(('hero','campaign','home','ritual','experimental','launch','mosaic','editorial','scene','pop'))))[:14]
            img=_hero_image(source)
            result.append({**meta,'store_code':item['code'],'template_code':item['template_code'],
                'domain':item.get('domain') or '', 'hero_image_source':img,
                'layout_markers':classes, 'source_file':name,
                'render_method':'原始 Liquid 结构指纹 + 源码内图片引用（不是 Shopify 实际渲染截图）'})
        diversity=check_diversity([{'inner_path':x['inner_path'],'code':x['code']} for x in items])
        return {'items':result,'diversity_warnings':diversity,'strict_structure_pass':not diversity,
                'method':'源代码结构启发式比较，不是线上网站视觉相似性验证；图片链接状态及使用授权未验证'}
    finally:
        for z in zipcache.values():z.close()


def _release_gate(batch):
    # Regenerate from source every time: no stale audit result can grant release.
    _, report = build_package(batch)
    issues=[{'store_code':s['store_code'],'domain':s['domain'],**issue} for s in report for issue in s['issues']]
    if not 1<=len(report)<=5:
        issues.append({'store_code':'','domain':'','type':'error','code':'BATCH_SIZE_INVALID',
                       'file':'','message':'当前交付模式每批最多5家店铺','fixable':False})
    for entity_problem in entity_issues({'name':batch['entity_name'],'address':batch.get('address'),'phone':batch.get('phone')}):
        if not any(i['code']=='ENTITY_PREFLIGHT' and i['message']==entity_problem for i in issues):
            issues.append({'store_code':'','domain':'','type':'error','code':'ENTITY_PREFLIGHT',
                           'file':'','message':entity_problem,'fixable':True})
    if any(not s['domain'] or not s['support_email'] for s in batch['stores']):
        issues.append({'store_code':'','domain':'','type':'error','code':'CONTACT_MISSING','file':'',
                       'message':'仍有店铺缺少域名或独立邮箱','fixable':True})
    for msg in check_diversity(batch['stores']):
        issues.append({'store_code':'','domain':'','type':'error','code':'SAME_ENTITY_SIMILAR_STORE',
                       'file':'','message':msg,'fixable':False})
    blockers=[x for x in issues if x['type']=='error']
    counts=dict(Counter(x['type'] for x in issues))
    return {'batch_id':batch['id'],'checked_at':now(),
            'allowed':not blockers,'blockers':blockers,'issues':issues,
            'counts':counts,'total_files':sum(x['file_count'] for x in report),
            'stores':report, 'overall':'正式文件可生成（仅离线规则检查）' if not blockers else '存在阻断项，禁止生成正式ZIP',
            'scope':'仅验证离线素材、主体配置和政策变量；不验证Shopify在线功能、邮箱收件、图片授权或广告平台资格',
            'ai_verified':False}


def _deterministic_docx(data:bytes)->bytes:
    """Normalize ZIP entry timestamps in generated DOCX without changing contents."""
    out=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as dst:
        for entry in src.infolist():
            zi=zipfile.ZipInfo(entry.filename,date_time=(1980,1,1,0,0,0))
            zi.compress_type=zipfile.ZIP_DEFLATED
            zi.external_attr=entry.external_attr
            dst.writestr(zi,src.read(entry))
    return out.getvalue()


def _convert_to_english(package_bytes):
    out=io.BytesIO()
    with zipfile.ZipFile(package_bytes) as source, zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as dest:
        for item in source.infolist():
            parts=PurePosixPath(item.filename).parts
            if len(parts)<2:continue
            translated=[parts[0]]+[KIND_EN.get(p,p) for p in parts[1:]]
            # The supplied product file has a Chinese basename; preserve CSV bytes,
            # only normalize the exported filename.
            if len(parts)>2 and translated[1]=='Products' and translated[-1].lower().endswith('.csv'):
                translated[-1]='products.csv'
            filename='/'.join(translated)
            if CJK.search(filename):
                raise ValueError('导出路径仍含中文：'+filename)
            if item.is_dir():
                filename=filename.rstrip('/')+'/'
                body=b''
            else:
                body=source.read(item)
                if filename.lower().endswith('.docx'):
                    body=_deterministic_docx(body)
            zi=zipfile.ZipInfo(filename,date_time=(1980,1,1,0,0,0))
            zi.compress_type=zipfile.ZIP_DEFLATED
            dest.writestr(zi,body)
    out.seek(0)
    return out


def _validate_zip(archive,expected_stores):
    counts=Counter()
    filenames=[]
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('ZIP压缩包完整性检查失败')
        for item in z.infolist():
            if item.is_dir():continue
            p=PurePosixPath(item.filename)
            if len(p.parts)!=3:raise ValueError('文件结构错误，必须是「域名/类别/文件」')
            folder,kind,name=p.parts
            if kind not in ('Products','Theme','Policies'):
                raise ValueError('出现非预期文件夹 '+kind)
            if CJK.search(item.filename):raise ValueError('文件路径中仍含中文')
            counts[(folder,kind)]+=1
            filenames.append(item.filename)
    if len({k[0] for k in counts})!=expected_stores:raise ValueError('店铺目录数量不正确')
    for folder in {k[0] for k in counts}:
        for kind,n in [('Products',1),('Theme',4),('Policies',7)]:
            if counts[(folder,kind)]!=n:
                raise ValueError(f'{folder} / {kind} 需要 {n} 份，实际 {counts[(folder,kind)]} 份')
    if len(filenames)!=12*expected_stores:raise ValueError('交付文件总数不正确')
    return {'store_count':expected_stores,'file_count':len(filenames),'filenames':filenames}


def _build_release(batch,gate):
    source,_=build_package(batch)
    converted=_convert_to_english(source)
    integrity=_validate_zip(converted,len(batch['stores']))
    blob=converted.getvalue()
    return blob,integrity


def build_v7_router(guard):
    r=APIRouter(prefix='/api/v7',dependencies=[Depends(guard)])

    @r.post('/visual/compare')
    def visual_compare(data:VisualSelection):
        with db() as c:items=_store_rows(c,data.store_codes)
        return _visual_rows(items)

    @r.get('/deployments/{batch_id}/gate')
    def release_gate(batch_id:str):
        return _release_gate(_required_batch(batch_id))

    @r.get('/deployments/{batch_id}/versions')
    def versions(batch_id:str):
        _required_batch(batch_id)
        with db() as c:
            return rows(c.execute('''SELECT id,batch_id,content_hash,size_bytes,created_at
               FROM delivery_versions WHERE batch_id=? ORDER BY rowid DESC LIMIT 50''',(batch_id,)))

    @r.post('/deployments/{batch_id}/prepare')
    def prepare_release(batch_id:str):
        batch=_required_batch(batch_id)
        gate=_release_gate(batch)
        if not gate['allowed']:
            causes=list(dict.fromkeys(i['message'] for i in gate['blockers']))
            raise HTTPException(409,detail='交付预检未通过：'+'；'.join(causes[:8]))
        try:blob,integrity=_build_release(batch,gate)
        except ValueError as exc:raise HTTPException(409,detail='ZIP校验未通过：'+str(exc))
        digest=hashlib.sha256(blob).hexdigest()
        with db() as c:
            last=row(c.execute('''SELECT * FROM delivery_versions WHERE batch_id=?
              ORDER BY rowid DESC LIMIT 1''',(batch_id,)))
            if last and last['content_hash']==digest and (RELEASE_DIR/last['storage_name']).is_file():
                return {'version_id':last['id'],'reused':True,'sha256':digest,
                        'size_bytes':last['size_bytes'],'integrity':integrity,
                        'download_url':'/api/v7/versions/'+last['id']+'/download.zip'}
            ident=uid('REL');filename=ident+'.zip'
            dest=RELEASE_DIR/filename
            dest.write_bytes(blob)
            try:dest.chmod(0o600)
            except OSError:pass
            c.execute('''INSERT INTO delivery_versions(id,batch_id,content_hash,size_bytes,storage_name,created_at,report_json)
              VALUES(?,?,?,?,?,?,?)''',(ident,batch_id,digest,len(blob),filename,now(),
                    json.dumps({'integrity':integrity,'gate':{'checked_at':gate['checked_at'],
                    'blockers':len(gate['blockers']),'warnings':gate['counts'].get('warning',0)}},ensure_ascii=False)))
        return {'version_id':ident,'reused':False,'sha256':digest,
                'size_bytes':len(blob),'integrity':integrity,
                'download_url':'/api/v7/versions/'+ident+'/download.zip'}

    @r.get('/versions/{version_id}/download.zip')
    def download_version(version_id:str):
        with db() as c:
            v=row(c.execute('SELECT * FROM delivery_versions WHERE id=?',(version_id,)))
        if not v:raise HTTPException(404,detail='交付版本不存在')
        if not re.fullmatch(r'REL-[A-Z0-9]{12}\.zip',v['storage_name']):
            raise HTTPException(500,detail='存储路径格式异常')
        path=RELEASE_DIR/v['storage_name']
        if not path.is_file():raise HTTPException(404,detail='归档ZIP缺失')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=v['content_hash']:
            raise HTTPException(409,detail='历史ZIP校验失败')
        return FileResponse(path,filename=f'BIG_BANG_{v["batch_id"]}_{version_id}.zip',
                            media_type='application/zip',headers={'Cache-Control':'no-store'})

    @r.get('/deployments/{batch_id}/diffs')
    def verified_diffs(batch_id:str):
        batch=_required_batch(batch_id)
        changes=[]
        for store in batch['stores']:
            src=DATA/'uploads'/store['archive_path']
            with zipfile.ZipFile(src) as z:
                items,_,_=render_one_store(z,store['inner_path'],
                    {'name':batch['entity_name'],'address':batch['address'],
                     'phone':batch['phone'],'email':batch['email'],
                     'country':batch['country'],'registration_no':batch['registration_no']},
                     store,{k:batch['settings'].get(k,'') for k in
                     ('service_hours','response_time','additional_info')})
                for relative,modified in items:
                    if not (relative.startswith('条款文件夹/') or relative.endswith('footer.liquid')):
                        continue
                    orig_kind={v:k for k,v in SHOP_FOLDERS.items()}[relative.split('/')[0]]
                    original_path=store['inner_path'].rstrip('/')+'/'+orig_kind+'/'+relative.split('/')[-1]
                    original=z.read(original_path)
                    if original==modified:continue
                    try:
                        if relative.endswith('.docx'):
                            from docx import Document
                            def paragraphs(blob):
                                doc=Document(io.BytesIO(blob)); lines=[p.text for p in doc.paragraphs]
                                for table in doc.tables:
                                    for rr in table.rows:
                                        for cell in rr.cells:lines.extend(p.text for p in cell.paragraphs)
                                return lines
                            before=paragraphs(original);after=paragraphs(modified)
                        else:
                            before=original.decode('utf-8-sig','replace').splitlines()
                            after=modified.decode('utf-8-sig','replace').splitlines()
                        diff=[x for x in difflib.unified_diff(before,after,n=0)
                              if x and x[0] in '+-' and not x.startswith(('+++','---'))]
                        # Do not send the entire legal policy into the UI by default.
                        if diff:
                            changes.append({'store_code':store['code'], 'domain':store['domain'],
                                'file':relative, 'changed_lines':len(diff),
                                'diff_preview':[x[:240] for x in diff[:12]],
                                'truncated':len(diff)>12})
                    except (ValueError,KeyError):
                        changes.append({'store_code':store['code'],'file':relative,
                            'changed_lines':-1,'diff_preview':[],'truncated':False})
        return {'batch_id':batch_id,'items':changes[:70],
                'scope':'仅显示真实源文件与待导出版本之间的差异；最终人工核验真实性和法律措辞'}

    @r.get('/deployments/{batch_id}/release-report.json')
    def release_report(batch_id:str):
        batch=_required_batch(batch_id)
        result=_release_gate(batch)
        return Response(content=json.dumps(result,ensure_ascii=False,indent=2),
            media_type='application/json',headers={'Content-Disposition':f'attachment; filename="BIG_BANG_QA_{batch_id}.json"',
                                                  'Cache-Control':'no-store'})
    return r
