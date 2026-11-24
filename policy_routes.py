"""BIG BANG V11: a single action fills 7 policies + footer, validates, archives.

This is a source-based document-preparation operation, NOT a declaration of
legal compliance, rights ownership or official AppLovin approval.
"""
from __future__ import annotations
import io
import os
import json
import re
import threading
import hashlib
import zipfile
from pathlib import Path
from collections import Counter
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from policy_pipeline import from_store, preflight, render_file, validate_rendered
from db import db, DATA, now, uid, row, rows
from v10_studio import resolve, getbytes, sha, err, audit_worker
from v7_routes import _deterministic_docx

FOLDERS={'Products':1,'Theme':4,'Policies':7}


def init_policy_pipeline():
    (DATA/'policy_deliveries').mkdir(parents=True,exist_ok=True)
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS policy_delivery_releases (
          id TEXT PRIMARY KEY,store_code TEXT NOT NULL, version INTEGER NOT NULL,
          archive_file TEXT NOT NULL, content_hash TEXT NOT NULL, sha256 TEXT NOT NULL,
          report_json TEXT NOT NULL, ai_audit_id TEXT, created_at TEXT NOT NULL,
          UNIQUE(store_code,version), UNIQUE(store_code,content_hash));
        ''')


def _category(name):
    if name.lower().endswith('.csv'):return 'Products'
    if name.lower().endswith('.liquid'):return 'Theme'
    return 'Policies'


def _name(name):
    group=_category(name)
    if group=='Products':return 'Products/products.csv'
    return group+'/'+name.split('/')[-1]


def _zip_blob(files):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for _,name,body in files:
            if name.endswith('.docx'):body=_deterministic_docx(body)
            zi=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(zi,body)
    return b.getvalue()


def _start_ai(code):
    if not os.environ.get('DEEPSEEK_API_KEY','').strip():return None
    with db() as c:
        existing=row(c.execute("SELECT id FROM studio_audits WHERE store_code=? AND status NOT IN ('审核完成','部分检查失败','检测失败') ORDER BY rowid DESC LIMIT 1",(code,)))
        if existing:return existing['id']
        aid=uid('V11AUD')
        c.execute('''INSERT INTO studio_audits VALUES(?,?,?,?,?,?,?,?,?,?)''',
                  (aid,code,'deepseek',os.environ.get('DEEPSEEK_MODEL','deepseek-flash'),
                   '排队中',0,'{}','',now(),now()))
    threading.Thread(target=audit_worker,args=(aid,code,True,False,False),daemon=True).start()
    return aid


def one_click(code):
    info,archive,names=resolve(code)
    ctx=from_store(info)
    problems=preflight(ctx)
    if problems:err('缺少或不正确的主体/域名信息：'+'；'.join(problems),409)
    with db() as c:
        previous=row(c.execute('SELECT report_json FROM policy_delivery_releases WHERE store_code=? ORDER BY version DESC LIMIT 1',(code,)))
    old_values=json.loads(previous['report_json']).get('_bound_values',{}) if previous else {}
    original=[];rendered=[];counts=Counter();changed=[];blocked=[]
    # All or nothing: pre-render every file before updating database/delivery history.
    for i,raw_name in enumerate(names):
        raw,_,_,rev,basehash=getbytes(code,i)
        dest=_name(raw_name)
        category=_category(raw_name);counts[category]+=1
        try:
            out=render_file(dest,raw,ctx,old_values)
        except Exception as exc:
            blocked.append(f'{dest} 无法正确填充：{str(exc)[:150]}')
            continue
        p=validate_rendered(dest,out)
        if p:blocked.extend(dest+'：'+x for x in p)
        if out!=raw:changed.append({'index':i,'name':dest,'before':sha(raw),'after':sha(out),'bytes':len(out)})
        original.append((i,dest,raw,basehash,rev))
        rendered.append((i,dest,out))
    for folder,need in FOLDERS.items():
        if counts[folder]!=need:blocked.append(f'{folder} 文件应为{need}份，实际{counts[folder]}份')
    if len(rendered)!=12:blocked.append(f'无法渲染完整12份文件：当前仅{len(rendered)}份')
    if blocked:err('交付文件尚不能生成：'+'；'.join(blocked[:8]),409)
    # Check actual complete output and do not claim operational truth from a template.
    warnings=[
      '政策文件的退货、物流、退款及数据披露条款尚需与实际经营规则核实。',
      '客服邮箱是否能实际收件、主体登记真实性尚未由本操作验证。',
      '商品尺寸材质与外链图片授权未核实；不得将本文件包称为完全合规。',
      '未执行线上Shopify购物车/支付流程及AppLovin官方审批。',
    ]
    blob=_zip_blob(rendered)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        if z.testzip() is not None:err('生成的ZIP完整性校验失败',500)
        got=Counter(name.split('/')[0] for name in z.namelist())
        if any(got[k]!=v for k,v in FOLDERS.items()):err('ZIP目录结构验证失败',500)
    content_hash=hashlib.sha256(b''.join(n.encode()+b'\x00'+hashlib.sha256(b).digest() for _,n,b in rendered)).hexdigest()
    report={
       'status':'政策与页脚填充完成，仍待真实业务合规复核',
       'store_code':code,'domain':ctx.domain,'company':ctx.company,
       'policy_files':7,'theme_files':4,'product_files':1,'file_count':12,
       'replaced_files':[x['name'] for x in changed],
       'modified_count':len(changed),'blocked':[],'warnings':warnings,
       '_bound_values':ctx.tokens(),
       'verification':{'policy_variables_filled':True,'footer_synced':True,
                       'english_content_checked':True,'file_structure_checked':True,
                       'ai_completed':False,'business_terms_confirmed':False,
                       'image_rights_verified':False,'official_approval':False},
    }
    # For self-consistency, both drafts and release metadata are committed in one db txn.
    with db() as c:
        existing=row(c.execute('''SELECT * FROM policy_delivery_releases WHERE store_code=? AND content_hash=?''',
                               (code,content_hash)))
        if existing:
            rid=existing['id'];ver=existing['version'];file=existing['archive_file'];reused=True
        else:
            ver=c.execute('SELECT COALESCE(MAX(version),0)+1 FROM policy_delivery_releases WHERE store_code=?',(code,)).fetchone()[0]
            rid=uid('POLREL');file=f'{code}_POLICIES_V{ver:03d}.zip';reused=False
            # Preserve all original content, and never override unrelated working edits.
            by_index={i:(n,b) for i,n,b in rendered}
            for i,name,raw,basehash,rev in original:
                out=by_index[i][1]
                if out==raw:continue
                c.execute('''INSERT INTO studio_drafts(store_code,file_index,content,base_hash,current_hash,rev,updated_at)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(store_code,file_index) DO UPDATE SET
                    content=excluded.content,current_hash=excluded.current_hash,rev=excluded.rev,updated_at=excluded.updated_at''',
                    (code,i,out,basehash,sha(out),rev+1,now()))
                c.execute('INSERT INTO studio_revisions VALUES(?,?,?,?,?,?,?)',
                          (uid('REV'),code,i,rev+1,out,sha(out),now()))
            target=DATA/'policy_deliveries'/file
            target.write_bytes(blob)
            report['version']=ver
            c.execute('''INSERT INTO policy_delivery_releases VALUES(?,?,?,?,?,?,?,?,?)''',
                      (rid,code,ver,file,content_hash,sha(blob),json.dumps(report,ensure_ascii=False),None,now()))
    aid=_start_ai(code)
    if aid:
        with db() as c:c.execute('UPDATE policy_delivery_releases SET ai_audit_id=? WHERE id=?',(aid,rid))
    report.pop('_bound_values',None)  # internal binding snapshot must not appear in browser response
    report.update({'id':rid,'version':ver,'reused':reused,
                   'download_url':f'/api/v11/studio/{code}/download/{rid}.zip',
                   'ai_audit_id':aid,'ai_status':'DeepSeek已自动开始逐文件审查' if aid else '未配置DeepSeek密钥；只完成本地规则检查'})
    return report


def build_policy_router(guard):
    r=APIRouter(prefix='/api/v11',dependencies=[Depends(guard)])
    @r.post('/studio/{code}/one-click')
    def run(code:str):
        return one_click(code)
    @r.get('/studio/{code}/deliveries')
    def history(code:str):
        resolve(code)
        with db() as c:
            releases=rows(c.execute('''SELECT id,version,sha256,created_at,ai_audit_id,report_json FROM policy_delivery_releases
                                       WHERE store_code=? ORDER BY version DESC LIMIT 40''',(code,)))
        for x in releases:
            x['report']=json.loads(x.pop('report_json'))
            x['report'].pop('_bound_values',None)
            x['download_url']=f'/api/v11/studio/{code}/download/{x["id"]}.zip'
        return {'releases':releases}
    @r.get('/studio/{code}/download/{rid}.zip')
    def download(code:str,rid:str):
        with db() as c:
            rec=row(c.execute('SELECT * FROM policy_delivery_releases WHERE id=? AND store_code=?',(rid,code)))
        if not rec:err('交付版本不存在',404)
        path=DATA/'policy_deliveries'/rec['archive_file']
        if not path.is_file():err('交付ZIP文件丢失',404)
        blob=path.read_bytes()
        if sha(blob)!=rec['sha256']:err('ZIP校验值不一致，请检查磁盘文件',500)
        return Response(blob,media_type='application/zip',headers={
          'Content-Disposition':f'attachment; filename="{rec["archive_file"]}"'})
    return r
