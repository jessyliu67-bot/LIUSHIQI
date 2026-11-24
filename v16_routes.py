"""V23 cross-platform immutable source view and per-platform offline bundles.

No live SHOPLINE product import, theme install or policy publishing happens here.
"""
from __future__ import annotations
import io,zipfile,hashlib,json,os,re,html
from pathlib import Path
from fastapi import APIRouter, Depends,HTTPException,Query
from fastapi.responses import Response, HTMLResponse
from db import db, DATA,row,rows
from v16_resources import RAW, inspect,PLATFORM_PARTS
from policy_pipeline import from_store,preflight,render_file,validate_rendered,POLICY_TOKEN,FOOTER_SENTINEL
from v7_routes import _deterministic_docx

ROOT=Path(__file__).resolve().parent

def err(msg,code=400):raise HTTPException(code,msg)

def store_info(code):
    with db() as c:
        item=row(c.execute('''SELECT s.code store_code,s.status status,t.code template_code,t.inner_path,t.checksum,
         e.name company,e.address,e.phone,s.entity_id,d.domain,co.support_email
         FROM stores s JOIN templates t ON t.id=s.template_id
         LEFT JOIN entities e ON s.entity_id=e.id
         LEFT JOIN store_domains d ON d.store_id=s.id
         LEFT JOIN store_contacts co ON co.store_id=s.id
         WHERE s.code=? OR t.code=? LIMIT 1''',(code,code)))
    if not item:err('未知的店铺或模板编号',404)
    return item

def file_map(z,prefix,platform):
    if platform not in PLATFORM_PARTS:err('不支持的平台',400)
    # Existing DB identities use "模板X/模板X品类". V23 files are platform-rooted.
    platform_root='Shopify/' if platform=='shopify' else 'SHOPLINE/'
    files=[]
    for part,(count,extension) in PLATFORM_PARTS[platform].items():
        folder=platform_root+prefix+part+'/'
        names=sorted(n for n in z.namelist() if n.startswith(folder) and not n.endswith('/'))
        if len(names)!=count:err(f'{platform}资源不完整: {part} 需要{count}份，实际{len(names)}份',409)
        for name in names:
            if extension and not name.lower().endswith(extension):err(f'{platform}文件扩展名错误: {name}',409)
            filename=name.rsplit('/',1)[-1]
            if part=='商品文件':
                dest='Products/'+('products.csv' if platform=='shopify' else filename)
            elif part=='装修文件':dest='Theme/'+filename
            else:dest='Policies/'+filename
            files.append((name,dest))
    return files

SHOPLINE_IDENTITY={
 'BUSINESS_DETAILS_REQUIRED_BEFORE_PUBLISHING':'company',
 'BUSINESS_ADDRESS_REQUIRED_BEFORE_PUBLISHING':'address',
 'BUSINESS_EMAIL_REQUIRED_BEFORE_PUBLISHING':'email',
 'BUSINESS_PHONE_REQUIRED_BEFORE_PUBLISHING':'phone',
}

def render_shopline_footer(blob,ctx):
    """V23 footer is intentionally hidden until identity fields have been confirmed.

    Only rewrite clearly documented identity placeholders. The immutable source
    is never modified. Do not turn public preflight errors into "success".
    """
    text=blob.decode('utf-8-sig')
    for marker,field in SHOPLINE_IDENTITY.items():
        if text.count(marker)!=1:
            err('V23 SHOPLINE页脚缺少或重复身份字段：'+marker,409)
        value=html.escape(getattr(ctx,field),quote=True)
        text=text.replace(marker,value)
    if text.count('href="#contact-details-required"')!=2:
        err('SHOPLINE页脚的邮箱和电话号码链接结构不符合V23',409)
    safe_mail=html.escape(ctx.email,quote=True)
    safe_tel=re.sub(r'[^0-9+]','',ctx.phone)
    if not safe_tel:err('SHOPLINE页脚缺少有效电话',409)
    text=text.replace('href="#contact-details-required"','href="mailto:'+safe_mail+'"',1)
    text=text.replace('href="#contact-details-required"','href="tel:'+safe_tel+'"',1)
    # Remove the source-only CSS hiding the legal and contact information.
    hidden=r'<style\s+id="bb-v23-unconfigured-identity"[^>]*>.*?</style>'
    text,count=re.subn(hidden,'',text,count=1,flags=re.I|re.S)
    if count!=1:err('无法解除SHOPLINE页脚主体信息隐藏状态',409)
    if 'REQUIRED_BEFORE_PUBLISHING' in text or '#contact-details-required' in text:
        err('SHOPLINE页脚仍含未配置的主体信息',409)
    return text.encode('utf-8')

def build_bundle(item,platform,filled=False):
    if platform not in PLATFORM_PARTS:err('不支持的平台',400)
    prefix=item['inner_path'].rstrip('/')+'/'
    ctx=None
    if filled:
        ctx=from_store(item)
        errors=preflight(ctx)
        if errors:err('正式配置缺少已确认的信息：'+'；'.join(errors),409)
    result=io.BytesIO();checks=[]
    expected=12 if platform=='shopify' else 11
    with zipfile.ZipFile(RAW) as z,zipfile.ZipFile(result,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
        files=file_map(z,prefix,platform)
        for source,dest in files:
            data=z.read(source)
            if filled and dest.startswith('Policies/'):
                data=render_file(dest,data,ctx)
            elif filled and platform=='shopify' and dest=='Theme/04-footer.liquid':
                data=render_file(dest,data,ctx)
            elif filled and platform=='shopline' and dest=='Theme/03-footer.sline':
                data=render_shopline_footer(data,ctx)
            if filled:
                errors=validate_rendered(dest,data)
                if errors:checks.extend(f'{dest}: {reason}' for reason in errors)
                if dest.startswith('Theme/') and b'REQUIRED_BEFORE_PUBLISHING' in data:
                    checks.append(dest+':仍有尚未填充的主体变量')
            if filled and dest.endswith('.docx'):data=_deterministic_docx(data)
            zi=zipfile.ZipInfo(dest,date_time=(1980,1,1,0,0,0))
            zi.compress_type=zipfile.ZIP_DEFLATED
            out.writestr(zi,data)
        if checks:err('交付文件检查未通过：'+'；'.join(checks[:8]),409)
    with zipfile.ZipFile(io.BytesIO(result.getvalue())) as valid:
        names=valid.namelist()
        if valid.testzip() is not None or len(names)!=expected:err('输出ZIP完整性失败',500)
        if platform=='shopline':
            from v16_resources import verify_shopline_products
            try:verify_shopline_products(valid.read('Theme/02-homepage-content.sline'),valid.read(next(n for n in names if n.endswith('.csv'))))
            except (ValueError,StopIteration) as exc:err('SHOPLINE商品加载代码校验失败：'+str(exc),500)
        if platform=='shopline' and (sum(x.endswith('.sline') for x in names)!=3 or any(x.endswith('.liquid') for x in names)):
            err('SHOPLINE ZIP混入旧版装修或文件缺失',500)
    return result.getvalue()


def build_v16_router(guard):
    r=APIRouter(prefix='/api/v16',dependencies=[Depends(guard)])

    @r.get('/status')
    def status():
        from db import DATA
        path=DATA/'ASSET_MANIFEST.json'
        source=json.loads(path.read_text('utf8')) if path.exists() else {}
        with db() as c:
            counts={'templates':c.execute('select count(*) from templates').fetchone()[0],
                    'stores':c.execute('select count(*) from stores').fetchone()[0],
                    'assigned':c.execute('select count(*) from stores where entity_id is not null').fetchone()[0]}
        return {'version':'35','resource_version':'V35','source_sha256':source.get('source_zip_sha256',''),
                'counts':counts,'platforms':{'shopify':{'files_per_store':12,'format':'1 CSV, 4 Liquid, 1 DOCX+6 TXT'},
                                               'shopline':{'files_per_store':11,'format':'1 Shopify-migration CSV, 3 SLINE, 1 DOCX+6 TXT'}},
                'notice':'结构检查不能证明平台在线兼容、商品合法授权或法律合规'}

    @r.get('/stores')
    def stores():
        with db() as c:
            items=rows(c.execute('''SELECT s.code store_code,s.status,t.code template_code,t.inner_path,e.name company,e.address,
               e.phone,d.domain,co.support_email
               FROM stores s JOIN templates t ON t.id=s.template_id
               LEFT JOIN entities e ON s.entity_id=e.id
               LEFT JOIN store_domains d ON d.store_id=s.id
               LEFT JOIN store_contacts co ON co.store_id=s.id ORDER BY s.code'''))
        # Present missing configuration before the operator clicks 'configured export'.
        for item in items:
            item['configuration_issues']=preflight(from_store(item))
            item['filled_export_allowed']=not item['configuration_issues']
        return {'items':items,'count':len(items)}

    @r.get('/templates/{code}')
    def describe(code:str):
        item=store_info(code)
        prefix=item['inner_path'].rstrip('/')+'/'
        with zipfile.ZipFile(RAW) as z:
            result={platform:[{'source':source,'output':dest,'bytes':z.getinfo(source).file_size}
                     for source,dest in file_map(z,prefix,platform)] for platform in ('shopify','shopline')}
        return {'store':item,'platform_files':result,'filled_export_allowed':not preflight(from_store(item)),
                'limitations':['源文件含商家资料变量，未填充不得直接发布','SHOPLINE迁移CSV与Ajax SLINE尚未经过真实店铺完整安装和导入测试']}

    @r.get('/templates/{code}/download')
    def download(code:str,platform:str=Query(default='shopify',pattern='^(shopify|shopline)$'),mode:str=Query(default='source',pattern='^(source|filled)$')):
        item=store_info(code)
        data=build_bundle(item,platform,filled=mode=='filled')
        safe_code=re.sub(r'[^A-Za-z0-9_-]','_',item['store_code'])
        name=f'{safe_code}_{platform.upper()}_V35_{"CONFIGURED" if mode=="filled" else "SOURCE_DRAFT"}.zip'
        return Response(data,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="{name}"',
                                                               'Cache-Control':'no-store','X-BIGBANG-Platform':platform.upper(), 'X-BIGBANG-Source-SHA256':json.loads((DATA/'ASSET_MANIFEST.json').read_text('utf8')).get('source_zip_sha256','')})
    return r
