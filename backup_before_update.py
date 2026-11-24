"""Explicit, offline-only backup of BIG BANG data for Windows upgrades.

BACKUPS ARE NOT ENCRYPTED. Store in a secure private location.
The .env file is deliberately excluded (contains passwords/API keys).
"""
from __future__ import annotations
import argparse,hashlib,json,os,sqlite3,tempfile,zipfile
from pathlib import Path
from datetime import datetime,timezone
# Resolve optional custom BIGBANG_DATA_DIR from local .env before importing db.
_env_path=Path(__file__).resolve().parent/'.env'
if _env_path.is_file():
 for _line in _env_path.read_text(encoding='utf-8').splitlines():
  if '=' in _line and not _line.lstrip().startswith('#'):
   _k,_v=_line.split('=',1)
   if _k.strip()=='BIGBANG_DATA_DIR' and _v.strip():os.environ.setdefault('BIGBANG_DATA_DIR',_v.strip())
from db import DATA,DB,BASE

def make_backup(output_path=None):
 if not DB.is_file():raise RuntimeError('数据库不存在，不能执行备份')
 if output_path is None:
  dest=BASE.parent/'BIG_BANG_PRIVATE_BACKUPS';dest.mkdir(exist_ok=True)
  output_path=dest/('BIG_BANG_DATA_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.zip')
 else:output_path=Path(output_path)
 output_path.parent.mkdir(parents=True,exist_ok=True)
 if output_path.exists():raise FileExistsError('备份目标已存在，拒绝覆盖：'+str(output_path))
 with tempfile.TemporaryDirectory() as td:
  snap=Path(td)/'bigbang.sqlite3'
  source=sqlite3.connect(str(DB));copy=sqlite3.connect(str(snap))
  try:source.backup(copy)
  finally:copy.close();source.close()
  verify=sqlite3.connect(str(snap))
  try:
   if verify.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('数据库备份完整性检查失败')
  finally:verify.close()
  manifest={'created_at':datetime.now(timezone.utc).isoformat(),
            'source_data_directory':str(DATA),'env_included':False,
            'note':'包含私人主体文件。ZIP未加密。单独安全保存旧版.env文件以迁移管理员密码和API配置。',
            'files':{}}
  with zipfile.ZipFile(output_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   items=[('data/bigbang.sqlite3',snap)]
   for file in DATA.rglob('*'):
    if not file.is_file():continue
    if file.resolve()==DB.resolve() or file.name.endswith(('-journal','-wal','-shm')):continue
    rel='data/'+file.relative_to(DATA).as_posix()
    items.append((rel,file))
   for arc,f in items:
    blob=f.read_bytes()
    manifest['files'][arc]={'sha256':hashlib.sha256(blob).hexdigest(),'size':len(blob)}
    z.writestr(arc,blob)
   z.writestr('BACKUP_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
  with zipfile.ZipFile(output_path) as z:
   if z.testzip():raise RuntimeError('备份ZIP完整性校验失败')
 return {'backup':str(output_path),'files':len(manifest['files']),'size_bytes':output_path.stat().st_size,
         'note':'此ZIP未加密，可能包含敏感公司文件；.env需单独安全备份。'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output');args=p.parse_args()
 print(json.dumps(make_backup(args.output),ensure_ascii=False,indent=2))
