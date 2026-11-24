"""Platform-specific multi-store delivery for BIG BANG V23.

Each store keeps its existing allocation and business identity. No database
writes or live merchant API actions. SHOPLINE artifacts are offline candidates,
not proof of SHOPLINE import or theme runtime compatibility.
"""
from __future__ import annotations
import io, re, zipfile
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from v16_routes import store_info, build_bundle
from v5_routes import batch_details


def _fail(message: str, status: int = 409):
    raise HTTPException(status_code=status, detail=message)


def _batch(batch_id):
    result=batch_details(batch_id)
    if not result:
        _fail('交付批次不存在',404)
    if not result['stores']:
        _fail('该交付批次没有已分配的店铺')
    return result


def configured_store(batch, assigned):
    """Do not allow a stale batch to silently export reassigned stores."""
    record=store_info(assigned['code'])
    if record.get('entity_id')!=batch['entity_id']:
        _fail(f'{assigned["code"]} 主体归属发生变化，请重新核对批次')
    if record.get('template_code')!=assigned.get('template_code'):
        _fail(f'{assigned["code"]} 模板分配发生变化，请重新核对批次')
    if record.get('domain')!=assigned.get('domain'):
        _fail(f'{assigned["code"]} 域名配置发生变化，请重新核对批次')
    if record.get('support_email')!=assigned.get('support_email'):
        _fail(f'{assigned["code"]} 客服邮箱配置发生变化，请重新核对批次')
    return record


def render_multistore(batch, platform):
    expected=12 if platform=='shopify' else 11
    ext='.liquid' if platform=='shopify' else '.sline'
    result=io.BytesIO()
    details=[]
    with zipfile.ZipFile(result,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
        for assigned in batch['stores']:
            record=configured_store(batch,assigned)
            domain=str(record['domain'] or '').strip().lower()
            if not re.fullmatch(r'[a-z0-9.-]+',domain) or '..' in domain or domain.startswith('.'):
                _fail(assigned['code']+' 域名不安全，不能用作导出文件夹')
            try:
                individual=build_bundle(record,platform,filled=True)
            except HTTPException as exc:
                _fail(f'{domain} {exc.detail}',exc.status_code)
            except Exception as exc:
                _fail(f'{domain} 文件生成失败：{type(exc).__name__}',500)
            with zipfile.ZipFile(io.BytesIO(individual)) as src:
                names=[n for n in src.namelist() if not n.endswith('/')]
                if src.testzip() is not None or len(names)!=expected:
                    _fail(f'{domain} {platform}文件不完整，应有{expected}份，实际{len(names)}份')
                kinds=Counter(n.split('/')[0] for n in names)
                if kinds!={'Products':1,'Theme':(4 if platform=='shopify' else 3),'Policies':7}:
                    _fail(f'{domain} 商品、装修或政策目录数量不正确')
                if sum(n.lower().endswith(ext) for n in names)!=(4 if platform=='shopify' else 3):
                    _fail(f'{domain} 装修文件类型不属于{platform.upper()}')
                if any(n.lower().endswith('.liquid') for n in names) and platform=='shopline':
                    _fail(f'{domain} SHOPLINE导出包含Shopify Liquid文件')
                for n in names:
                    if n.startswith('/') or '..' in n.split('/'):
                        _fail('生成的资源包含不安全路径')
                    info=zipfile.ZipInfo(f'{domain}/{n}',date_time=(1980,1,1,0,0,0))
                    info.compress_type=zipfile.ZIP_DEFLATED
                    out.writestr(info,src.read(n))
            details.append({'store_code':assigned['code'],'domain':domain,'template_code':assigned['template_code'],
                            'files':expected,'platform':platform})
    result.seek(0)
    with zipfile.ZipFile(result) as check:
        if check.testzip() is not None or len(check.namelist())!=len(details)*expected:
            _fail('最终批量ZIP完整性检查失败',500)
    result.seek(0)
    return result.getvalue(),details


def build_v16_batch_router(guard):
    router=APIRouter(prefix='/api/v16/deployments',dependencies=[Depends(guard)])

    @router.get('/{batch_id}/audit')
    def audit(batch_id:str, platform:str=Query(...,pattern='^(shopify|shopline)$')):
        batch=_batch(batch_id)
        try:
            _,items=render_multistore(batch,platform)
            issues=[{'type':'warning','code':'NOT_LIVE_TESTED','file':'',
                     'message':('SHOPLINE迁移格式CSV、Ajax SLINE及政策已经完成离线结构和变量检查；真实商品导入、SLINE安装、图片授权未验证。' if platform=='shopline'
                                else 'Shopify文件已完成离线结构和变量检查，但尚未验证真实店铺安装和图片授权。'),
                     'store_code':i['store_code'],'domain':i['domain']} for i in items]
            return {'batch_id':batch_id,'platform':platform,'status':'文件结构通过（非线上验收）',
                    'store_count':len(items),'files':sum(i['files'] for i in items),'stores':items,'issues':issues,
                    'issue_counts':{'error':0,'warning':len(issues),'info':0},
                    'ai_status':'仅执行本地结构和政策变量检查；未调用DeepSeek，未验证SHOPLINE真实店铺。'}
        except HTTPException as exc:
            return {'batch_id':batch_id,'platform':platform,'status':'存在阻断问题','store_count':len(batch['stores']),
                    'files':0,'stores':[], 'issues':[{'type':'error','code':'PLATFORM_EXPORT_BLOCKED',
                    'store_code':'BATCH','domain':'','file':'','message':str(exc.detail)}],
                    'issue_counts':{'error':1,'warning':0,'info':0},
                    'ai_status':'平台文件预检失败，未生成配置ZIP'}

    @router.get('/{batch_id}/report.json')
    def report(batch_id:str,platform:str=Query(...,pattern='^(shopify|shopline)$')):
        return audit(batch_id,platform)

    @router.get('/{batch_id}/export.zip')
    def export(batch_id:str, platform:str=Query(...,pattern='^(shopify|shopline)$')):
        batch=_batch(batch_id)
        content,items=render_multistore(batch,platform)
        name=f'BIG_BANG_{platform.upper()}_V35_{batch_id}_CONFIGURED.zip'
        return Response(content,media_type='application/zip',headers={
            'Content-Disposition':f'attachment; filename="{name}"',
            'Cache-Control':'no-store',
            'X-BIGBANG-Platform':platform.upper(),
            'X-BIGBANG-Store-Count':str(len(items)),
            'X-BIGBANG-File-Count':str(sum(i['files'] for i in items)),
            'X-BIGBANG-Online-Validated':'false'})
    return router
