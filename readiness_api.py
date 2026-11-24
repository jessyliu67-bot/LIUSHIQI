"""Read-only diagnostics, existing asset verification, future replacement preview."""
from __future__ import annotations
import hashlib, io, json, os, sqlite3, tempfile, zipfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from db import DATA,db
from resource_doctor import file_sha256
from v16_resources import inspect as inspect_dual, compare as compare_dual
from platform_registry import platform_capabilities

BASE=Path(__file__).resolve().parent
from v16_resources import RAW as SOURCE


def _counts(c):
 return {
  'stores':c.execute('SELECT COUNT(*) FROM stores').fetchone()[0],
  'templates':c.execute('SELECT COUNT(*) FROM templates').fetchone()[0],
  'entities':c.execute('SELECT COUNT(*) FROM entities').fetchone()[0],
  'assigned_stores':c.execute('SELECT COUNT(*) FROM stores WHERE entity_id IS NOT NULL').fetchone()[0],
  'bound_domains':c.execute('SELECT COUNT(*) FROM store_domains').fetchone()[0]
 }

def local_diagnostics():
 checks={}
 with db() as c:
  counts=_counts(c)
  checks['sqlite_quick_check']=c.execute('PRAGMA quick_check').fetchone()[0]
  checks['foreign_key_issues']=len(c.execute('PRAGMA foreign_key_check').fetchall())
  template_archives=[dict(r) for r in c.execute('SELECT DISTINCT archive_path FROM templates')]
  checks['template_archive_paths']=[r['archive_path'] for r in template_archives]
 manifest=DATA/'ASSET_MANIFEST.json'
 expected=None
 if manifest.is_file():
  try:expected=json.loads(manifest.read_text('utf-8')).get('source_zip_sha256')
  except (OSError,ValueError):pass
 if SOURCE.is_file():
  checks['bundled_asset_sha256']=file_sha256(SOURCE)
 else:checks['bundled_asset_sha256']=None
 checks['manifest_asset_sha256']=expected
 checks['source_hash_matches_manifest']=bool(expected and checks['bundled_asset_sha256']==expected)
 checks['source_archive_exists']=SOURCE.exists()
 checks['unverified_ai_key_configured']=bool(os.getenv('DEEPSEEK_API_KEY','').strip())
 checks['data_location']=str(DATA)
 notices=[]
 if not checks['source_hash_matches_manifest']:notices.append('资源包与记录的清单哈希不同。停止批量使用，先核查版本与备份。')
 if checks['sqlite_quick_check']!='ok' or checks['foreign_key_issues']:notices.append('数据库完整性检查失败，需要恢复备份。')
 if counts['stores']!=300 or counts['templates']!=300:notices.append('当前店铺或模板数量不是300，请检查是否存在真实的历史变更。')
 if not checks['unverified_ai_key_configured']:notices.append('未配置DeepSeek API Key；离线规则检查仍可使用。')
 return {'version':'11.4.3-V35','counts':counts,'checks':checks,'notices':notices,
         'can_use_local_workflows':checks['sqlite_quick_check']=='ok' and checks['foreign_key_issues']==0 and checks['source_hash_matches_manifest'],
         'scope':'本地文件与数据库状态，不代表外部链接、公司真实性或广告合规通过'}

_scan_cache={}
def source_scan():
 if not SOURCE.exists():raise HTTPException(503,'本地V35资源文件不存在')
 stat=SOURCE.stat();key=(stat.st_size,stat.st_mtime_ns)
 if key not in _scan_cache:
  _scan_cache.clear();_scan_cache[key]=inspect_dual(SOURCE)
 return _scan_cache[key]

def build_readiness_router(guard):
 router=APIRouter(prefix='/api/v11_2',dependencies=[Depends(guard)])
 @router.get('/diagnostics')
 def diagnostics():return local_diagnostics()
 @router.get('/assets/scan')
 def assets_scan():return source_scan()
 @router.get('/platforms')
 def platforms():return platform_capabilities()
 @router.post('/assets/preview')
 async def preview(file:UploadFile=File(...)):
  name=(file.filename or 'new-assets.zip').split('/')[-1].split('\\')[-1]
  if not name.lower().endswith('.zip'):raise HTTPException(400,'请选择ZIP压缩包')
  limit=420*1024*1024
  with tempfile.NamedTemporaryFile(prefix='bb_preflight_',suffix='.zip',delete=False) as temp:
   temp_path=Path(temp.name);total=0
   try:
    while chunk:=await file.read(1024*1024):
     total+=len(chunk)
     if total>limit:raise HTTPException(413,'源ZIP超过420MB，请分卷或优化资源包')
     temp.write(chunk)
   except Exception:
    temp_path.unlink(missing_ok=True);raise
  try:
   if not zipfile.is_zipfile(temp_path):raise HTTPException(400,'ZIP内容损坏，未修改任何资源')
   report=compare_dual(SOURCE,temp_path)
   report['candidate_filename']=name
   report['action']='仅生成预检和映射计划；没有替换300套资源、占用店铺或修改数据库'
   return report
  except ValueError as exc:raise HTTPException(400,str(exc))
  finally:temp_path.unlink(missing_ok=True)
 return router
