"""Non-destructive source update of BIG BANG from V12 to supplied V13.

Keeps database identities, allocations, audit history, and working copies unchanged.
Only the immutable source archive metadata for 300 existing templates is updated.
"""
from __future__ import annotations
import hashlib, json, shutil, zipfile, csv, io, os
from pathlib import Path
from db import db, DATA, BASE

ARCHIVE_FILENAME='Shopify_300_V13_Clean_Products_Original_Variants (1).zip'
ARCHIVE_STORAGE='BIG_BANG_V13_300.zip'
RESOURCE=BASE/'resources'/ARCHIVE_STORAGE
DEST=DATA/'uploads'/ARCHIVE_STORAGE
MANIFEST=DATA/'ASSET_MANIFEST.json'

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def bootstrap():
    if not RESOURCE.is_file():
        raise RuntimeError('缺少V13原始资源文件：'+str(RESOURCE))
    RESOURCE_SHA=sha256_file(RESOURCE)
    # If the archive previously used for V13 allocations changed in place, STOP.
    # Do not silently rewrite a source zip after stores were already assigned.
    if MANIFEST.is_file():
        try:
            previous_manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
        except (ValueError,OSError) as exc:
            raise RuntimeError('资产清单读取失败，已停止启动以防覆盖资源。请先备份data目录。') from exc
        previous_sha=previous_manifest.get('source_zip_sha256','')
        previous_version=previous_manifest.get('version','')
        if previous_version in ('BIG_BANG_V13','BIG_BANG_V11_2_V13') and previous_sha and previous_sha!=RESOURCE_SHA:
            raise RuntimeError('检测到V13资源ZIP与已登记的SHA256不一致。禁止静默覆盖已分配模板；请先备份并使用新版资源预检功能。')
    if not DEST.is_file() or sha256_file(DEST)!=RESOURCE_SHA:
        # Never overwrite the prior V12 archive or any user records.
        tmp=DEST.with_suffix('.new')
        shutil.copy2(RESOURCE,tmp)
        if sha256_file(tmp)!=RESOURCE_SHA:raise RuntimeError('V13资源复制校验失败')
        tmp.replace(DEST)
    with zipfile.ZipFile(DEST) as z:
        if z.testzip() is not None:raise RuntimeError('V13原始资源ZIP不完整')
        packages={}
        for info in z.infolist():
            if info.is_dir():continue
            p=info.filename.replace('\\','/').split('/')
            if len(p)<3:raise RuntimeError('V13资源出现未知的目录：'+info.filename)
            key='/'.join(p[:2])
            packages.setdefault(key,[]).append(info.filename)
        if len(packages)!=300 or any(len(v)!=12 for v in packages.values()):
            raise RuntimeError('V13源文件必须为300个店铺组合，每店12份文件')
        with db() as c:
            existing=[dict(r) for r in c.execute('SELECT id,code,inner_path,archive_path,checksum FROM templates ORDER BY code')]
        if len(existing)!=300 or set(x['inner_path'] for x in existing)!=set(packages):
            raise RuntimeError('现有300个店铺模板路径与V13不对应。为保护历史分配，自动迁移已中止。')
        # Fingerprint each complete original template so the dashboard never shows
        # old V12 hashes after V13 source import. The original files stay immutable.
        template_hashes={}
        for group,names in packages.items():
            h=hashlib.sha256()
            for filename in sorted(names):
                relative=filename[len(group)+1:]
                h.update(relative.encode('utf-8')+b'\0')
                h.update(hashlib.sha256(z.read(filename)).digest())
            template_hashes[group]=h.hexdigest()
        # Keep assignments, but flag old approvals if source bytes or its mapping changed.
        changing=any(x['archive_path']!=ARCHIVE_STORAGE or x['checksum']!=template_hashes[x['inner_path']] for x in existing)
        if changing and MANIFEST.is_file():
            backup=DATA/'ASSET_MANIFEST.before_V13.json'
            if not backup.exists():shutil.copy2(MANIFEST,backup)
        # Only update the asset metadata after the archive has passed validation.
        with db() as c:
            for t in existing:
                c.execute('UPDATE templates SET archive_name=?,archive_path=?,label=?,checksum=? WHERE id=?',
                    (ARCHIVE_FILENAME,ARCHIVE_STORAGE,t['inner_path'],template_hashes[t['inner_path']],t['id']))
            if changing:
                # Make previously audited stores explicitly due for new review.
                c.execute("UPDATE stores SET status='需复核V13源文件',updated_at=datetime('now') WHERE status LIKE '%通过%' OR status LIKE '%验收%'")
        # Manifest is for visibility; the source ZIP is left byte-for-byte intact.
        if changing or not MANIFEST.is_file() or json.loads(MANIFEST.read_text(encoding='utf-8')).get('scan_schema',0)<3:
            assets=[]
            for t in existing:
                names=packages[t['inner_path']]
                csv_name=next((n for n in names if n.lower().endswith('.csv')),None)
                count=0;variants=0;images=0
                if csv_name:
                    csv_content=z.read(csv_name).decode('utf-8-sig',errors='replace')
                    records=list(csv.DictReader(io.StringIO(csv_content)))
                    count=sum(bool((r.get('Title') or '').strip()) for r in records)
                    variants=sum(bool((r.get('SKU') or r.get('Variant SKU') or '').strip()) for r in records)
                    images=sum(bool((r.get('Product image URL') or r.get('Image Src') or '').strip()) for r in records)
                assets.append({'template_code':t['code'],'relative_path':t['inner_path'],
                    'files':len(names),'liquid':sum(n.lower().endswith('.liquid') for n in names),
                    'csv':sum(n.lower().endswith('.csv') for n in names),
                    'policies':sum(n.lower().endswith(('.txt','.docx')) for n in names),
                    'product_title_rows':count,'variant_sku_rows':variants,'image_url_rows':images,
                    'template_sha256':template_hashes[t['inner_path']]})
            manifest={'version':'BIG_BANG_V13','scan_schema':3,'source_zip':ARCHIVE_FILENAME,
                'source_zip_sha256':RESOURCE_SHA,'stores':300,'files':sum(map(len,packages.values())),
                'notes':['V13原始文件未经修改；保留全部店铺和模板ID','主体、域名和政策必须分别核验'],
                'assets':assets}
            temp=MANIFEST.with_suffix('.json.tmp')
            temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(MANIFEST)
    return {'ok':True,'stores':300,'files':3600,'sha256':RESOURCE_SHA,'changed_source':changing}

if __name__=='__main__':
    from db import init,init_v3
    init();init_v3()
    print(json.dumps(bootstrap(),ensure_ascii=False))
