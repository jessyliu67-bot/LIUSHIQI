"""V23 non-destructive resource migration; keeps all existing 300 allocations.

Module import remains bootstrap_v16 for backward compatibility.
"""
from __future__ import annotations
from pathlib import Path
import json, zipfile, hashlib, sqlite3, shutil
from db import DATA, DB, db
from v16_resources import RAW, SHOPIFY_ARCHIVE, inspect, classify, legacy_shopify_path, sha256
from resource_archive import materialize_resource_archive

TARGET=DATA/'uploads'/SHOPIFY_ARCHIVE
MANIFEST=DATA/'ASSET_MANIFEST.json'
CURRENT_VERSION='BIG_BANG_V35'

def _snapshot_previous(manifest):
    folder=DATA/'pre_v35_backup';folder.mkdir(exist_ok=True)
    destination=folder/'bigbang_before_v35.sqlite3'
    if not destination.exists() and DB.exists():
        source=sqlite3.connect(DB);dest=sqlite3.connect(destination)
        try:source.backup(dest)
        finally:dest.close();source.close()
    past=folder/'ASSET_MANIFEST.before_v35.json'
    if MANIFEST.exists() and not past.exists():shutil.copy2(MANIFEST,past)

def _hashes(archive):
    with zipfile.ZipFile(archive) as z:
        folders={}
        for item in z.infolist():
            if not item.is_dir():folders.setdefault('/'.join(item.filename.split('/')[:2]),[]).append(item.filename)
        result={}
        for folder,names in folders.items():
            h=hashlib.sha256()
            for name in sorted(names):
                relative=name[len(folder)+1:]
                h.update(relative.encode('utf8')+b'\0');h.update(hashlib.sha256(z.read(name)).digest())
            result[folder]=h.hexdigest()
        return result

def bootstrap():
    materialize_resource_archive()
    if not RAW.is_file():raise RuntimeError('缺少V35双平台原始资源：'+str(RAW))
    old={}
    if MANIFEST.exists():
        try:old=json.loads(MANIFEST.read_text('utf8'))
        except (ValueError,OSError) as exc:raise RuntimeError('旧资源清单无法读取，请先恢复备份') from exc
    sourcehash=sha256(RAW)
    if old.get('version') not in (None,'BIG_BANG_V13','BIG_BANG_V23','BIG_BANG_V23_1','BIG_BANG_V34',CURRENT_VERSION):
        raise RuntimeError('未知资源版本：拒绝覆盖现有资源清单')
    if old.get('version')==CURRENT_VERSION and old.get('source_zip_sha256')!=sourcehash:
        raise RuntimeError('V35原始资源哈希改变，拒绝静默覆盖')
    verified=inspect(RAW)
    if verified['blocking_findings']:raise RuntimeError('V35资源结构不完整：'+'；'.join(verified['blocking_findings'][:5]))
    with db() as c:
        existing=[dict(x) for x in c.execute('SELECT id,code,inner_path,archive_path,checksum FROM templates ORDER BY code')]
    expected=set(x['path'] for x in verified['packages'])
    if len(existing)!=300 or set(x['inner_path'] for x in existing)!=expected:
        raise RuntimeError('V35原始目录与旧300套模板身份不吻合，已中止升级以免错配')
    if old.get('version')==CURRENT_VERSION and TARGET.exists() and old.get('shopify_archive_sha256') and sha256(TARGET)!=old['shopify_archive_sha256']:
        raise RuntimeError('Shopify兼容包被外部修改，请备份后处理')
    rebuild=not TARGET.exists() or old.get('version')!=CURRENT_VERSION
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if rebuild:
        temp=TARGET.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(RAW) as src,zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as dst:
                for item in src.infolist():
                    if not item.is_dir() and item.filename.startswith('Shopify/') and classify(item.filename):
                        zi=zipfile.ZipInfo(legacy_shopify_path(item.filename),date_time=(1980,1,1,0,0,0))
                        zi.compress_type=zipfile.ZIP_DEFLATED
                        dst.writestr(zi,src.read(item))
            with zipfile.ZipFile(temp) as test:
                if test.testzip() is not None or len(test.namelist())!=3600:raise RuntimeError('Shopify兼容包CRC或文件数量错误')
            _snapshot_previous(old)
            temp.replace(TARGET)
        finally:temp.unlink(missing_ok=True)
    hashes=_hashes(TARGET)
    if set(hashes)!=expected:raise RuntimeError('Shopify兼容包的300个目录不符合既有映射')
    changed=any(t['checksum']!=hashes[t['inner_path']] for t in existing)
    if old.get('version')!=CURRENT_VERSION:_snapshot_previous(old)
    with db() as c:
        for t in existing:
            c.execute('UPDATE templates SET archive_name=?,archive_path=?,checksum=?,file_count=? WHERE id=?',
                      (RAW.name,SHOPIFY_ARCHIVE,hashes[t['inner_path']],12,t['id']))
        # Store delivery states are historical business data; never rewrite them during resource upgrade.
    output={'version':CURRENT_VERSION,'scan_schema':6,'source_zip':RAW.name,'source_zip_sha256':sourcehash,
            'shopify_archive':SHOPIFY_ARCHIVE,'shopify_archive_sha256':sha256(TARGET),
            'stores':300,'platform_bundles':600,'files':6900,
            'shopify_files':3600,'shopline_files':3300,'metadata_files':0,
            'source_preserved':True,'resource_label':'V35','shopify_source_changed':(old.get('shopify_source_changed',changed) if old.get('version')==CURRENT_VERSION else changed),'affected_template_groups':list(range(1,21)), 'live_revalidation_required':True,'notes':verified['notes']}
    if old!=output:
        tmp=MANIFEST.with_suffix('.tmp')
        tmp.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(MANIFEST)
    return output

if __name__=='__main__':
    from db import init,init_v3
    init();init_v3();print(json.dumps(bootstrap(),ensure_ascii=False,indent=2))
