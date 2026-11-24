"""BIG BANG V35 dual-platform source inspection.

Legacy import name intentionally retained: existing routes call v16_resources.
The original V23 ZIP is immutable; Shopify legacy layout is built separately.
600 platform bundles = 300 matched template identities x 2 platforms.
"""
from __future__ import annotations
from pathlib import Path, PurePosixPath
from collections import Counter, defaultdict
import hashlib, re, zipfile, csv, io

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'resources' / 'BIG_BANG_V35_DUAL_600.zip'
SHOPIFY_ARCHIVE = 'BIG_BANG_V35_SHOPIFY_300.zip'
PLATFORM_PARTS = {
    'shopify': {'装修文件': (4, '.liquid'), '商品文件': (1, '.csv'), '条款文件': (7, None)},
    'shopline': {'装修文件': (3, '.sline'), '商品文件': (1, '.csv'), '条款文件': (7, None)},
}
TARGET_ROWS=300
MAX_FILES=8200
MAX_MEMBER=32*1024*1024
MAX_UNCOMPRESSED=3*1024**3
LEGACY_DIRS={'装修文件':'装修文件','商品文件':'商品CSV','条款文件':'七个条款文件'}

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as fh:
        for b in iter(lambda: fh.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def classify(name):
    a=name.replace('\\','/').split('/')
    if len(a)!=5 or a[0] not in ('Shopify','SHOPLINE'):
        return None
    if not re.fullmatch(r'模板(?:[1-9]|1\d|20)',a[1]) or not a[2].startswith(a[1]):return None
    platform={'Shopify':'shopify','SHOPLINE':'shopline'}[a[0]]
    if a[3] not in PLATFORM_PARTS[platform]:return None
    return '/'.join(a[1:3]),platform,a[3]

def legacy_shopify_path(name):
    parts=name.split('/')
    if classify(name) and parts[0]=='Shopify':
        return '/'.join(parts[1:3]+[LEGACY_DIRS[parts[3]]]+parts[4:])
    raise ValueError('Not a Shopify V23 member: '+name)

def inspect(path=RAW,include_packages=True):
    path=Path(path)
    if not zipfile.is_zipfile(path):raise ValueError('不是有效的V35 ZIP文件')
    groups=defaultdict(list); problems=[]; unknown=[]; total=0; all_paths=set()
    with zipfile.ZipFile(path) as z:
        members=[x for x in z.infolist() if not x.is_dir()]
        if len(members)>MAX_FILES:raise ValueError('文件数量超出限制')
        for item in members:
            name=item.filename.replace('\\','/');p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or name in all_paths:raise ValueError('ZIP包含不安全或重复路径')
            all_paths.add(name)
            if (item.external_attr>>16)&0o170000==0o120000:raise ValueError('ZIP包含符号链接')
            if item.file_size>MAX_MEMBER or (item.compress_size and item.file_size/item.compress_size>1200):raise ValueError('ZIP成员体积异常')
            total+=item.file_size
            if total>MAX_UNCOMPRESSED:raise ValueError('解压体积超出限制')
            record=classify(name)
            if record:groups[record[0]].append((record[1],record[2],name,item))
            else:unknown.append(name)
        # Archive read check. Each member also read below while hashing.
        packs=[];summary=Counter()
        for key in sorted(groups):
            grouped=groups[key];local=[];h=hashlib.sha256()
            for platform,parts in PLATFORM_PARTS.items():
                for part,(count,extension) in parts.items():
                    rows=[name for plat,folder,name,_ in grouped if plat==platform and folder==part]
                    if len(rows)!=count:local.append(f'{platform}/{part}:应有{count}份，实际{len(rows)}份')
                    if extension and any(not x.lower().endswith(extension) for x in rows):local.append(platform+'/'+part+'扩展名不匹配')
                    if part=='条款文件':
                        if sum(x.lower().endswith('.docx') for x in rows)!=1 or sum(x.lower().endswith('.txt') for x in rows)!=6:local.append(platform+'政策应为1份DOCX与6份TXT')
            for platform,_,name,_ in sorted(grouped,key=lambda x:x[2]):
                blob=z.read(name)
                h.update(name.encode('utf8')+b'\0');h.update(hashlib.sha256(blob).digest())
                if name.lower().endswith('.csv'):
                    try:
                        text=blob.decode('utf-8-sig')
                        parsed=csv.DictReader(io.StringIO(text))
                        for row in parsed:
                            sku=(row.get('SKU') or row.get('Variant SKU') or '').strip()
                            image=(row.get('Product image URL') or row.get('Image Src') or '').strip()
                            if sku:summary['sku_rows']+=1
                            if image:
                                summary['image_rows']+=1
                                if 'amazon.' in image.lower() or 'media-amazon.com' in image.lower():summary['amazon_image_rows']+=1
                    except (UnicodeError,csv.Error) as exc:
                        local.append('CSV解析错误：'+name)
            try:
                home=next(name for plat,_,name,_ in grouped if plat=='shopline' and name.endswith('/02-homepage-content.sline'))
                product=next(name for plat,_,name,_ in grouped if plat=='shopline' and name.endswith('.csv'))
                verify_shopline_products(z.read(home),z.read(product))
            except (ValueError,StopIteration) as exc:local.append('SHOPLINE product verification: '+str(exc))
            summary['shopify_files']+=sum(x[0]=='shopify' for x in grouped)
            summary['shopline_files']+=sum(x[0]=='shopline' for x in grouped)
            summary['structure_errors']+=bool(local)
            packs.append({'path':key,'file_count':len(grouped),'status':'structure_ok' if not local else 'structure_error',
                          'problems':local,'content_sha256':h.hexdigest(),
                          'counts':{'Shopify':sum(x[0]=='shopify' for x in grouped),'SHOPLINE':sum(x[0]=='shopline' for x in grouped)}})
        if len(groups)!=TARGET_ROWS:problems.append(f'应有300组双平台映射，实际{len(groups)}')
        if summary['structure_errors']:problems.append(f'{summary["structure_errors"]}套文件结构错误')
        if summary['shopify_files']!=3600 or summary['shopline_files']!=3300:problems.append('V35双平台文件总量不匹配')
        if unknown:problems.append(f'有{len(unknown)}份未识别资源（例：{unknown[0]}）')
        out={'source_file':path.name,'sha256':sha256(path),'resource_version':'V35',
             'summary':{'package_count':len(groups),'platform_bundle_count':len(groups)*2,'file_count':len(members),
                        'store_files':summary['shopify_files']+summary['shopline_files'],
                        'shopify_files':summary['shopify_files'],'shopline_files':summary['shopline_files'],
                        'structure_ok':len(groups)-summary['structure_errors'],
                        'structure_errors':summary['structure_errors'],'metadata_files':0,'sku_rows':summary['sku_rows'],'image_rows':summary['image_rows'],
                        'amazon_image_rows':summary['amazon_image_rows']},
             'blocking_findings':problems,'passed_structure_check':not problems,
             'notes':['V35单独归档，不覆盖V23.1。300组映射对应Shopify与SHOPLINE各300份交付组合。',
                      'SHOPLINE使用1份Shopify迁移CSV、3份SLINE及7份Word/TXT政策。',
                      '离线结构检查不等于线上商品导入、商品图片授权、SLINE安装或政策法律验收。']}
        if include_packages:out['packages']=packs
        return out

def verify_shopline_products(home, csv_blob):
    import json
    s=home.decode('utf-8-sig')
    handles=re.findall(r'all_products \| get\("([^"]+)"\)',s)
    match=re.search(r'const configuredHandles = (\[.*?\]);',s)
    if len(handles)!=8 or len(set(handles))!=8 or not match or json.loads(match.group(1))!=handles:
        raise ValueError('SHOPLINE native product loader or fallback handles are missing or inconsistent')
    if 'data-bb23-product-grid hidden' in s or 'No matching published products are available in this store yet' in s:
        raise ValueError('Obsolete Ajax-only product loader detected')
    rows=csv.DictReader(io.StringIO(csv_blob.decode('utf-8-sig')))
    published={row.get('Handle','') for row in rows if str(row.get('Published','')).strip().lower()=='true'}
    if not set(handles)<=published:
        raise ValueError('SHOPLINE homepage product handles do not match the published product CSV')
    return handles

def compare(old,new):
    a=inspect(old);b=inspect(new)
    am={x['path']:x for x in a['packages']};bm={x['path']:x for x in b['packages']};common=set(am)&set(bm)
    unchanged=sorted(x for x in common if am[x]['content_sha256']==bm[x]['content_sha256'])
    return {'current_sha256':a['sha256'],'candidate_sha256':b['sha256'],'current':a['summary'],'candidate':b['summary'],
            'same_paths':sorted(common),'unchanged_paths':unchanged,
            'changed_paths':sorted(common-set(unchanged)),'new_paths':sorted(set(bm)-set(am)),
            'missing_paths':sorted(set(am)-set(bm)),'candidate_blocking_findings':b['blocking_findings'],
            'safe_to_auto_activate':False,'reason':'只读检查；正式更换必须备份、检查映射与验证原始文件哈希。'}
