"""Read-only Shopify source archive quality inspection and update preview.

Never rewrites source archives, renumbers stores, infers supplier truth or claims
Shopify/SHOPLINE/AppLovin approval.
"""
from __future__ import annotations
import csv, hashlib, io, json, re, zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

POLICY_DIRS={'policies','七个条款文件','七份条款','terms','policy'}
THEME_DIRS={'theme','装修文件','装修','liquid'}
PRODUCT_DIRS={'products','商品csv','商品文件夹','商品文件','商品'}
MAX_ITEMS=20000
MAX_FILE=30*1024*1024
MAX_UNCOMPRESSED=2*1024**3
SRC_SENTINELS=re.compile(r'\[\[[A-Z][A-Z0-9_]*\]\]|REPLACE_WITH_[A-Z0-9_]+')
COLS={
 'title':('Title','Product Name','商品名称'),
 'handle':('URL handle','Handle','Product Handle'),
 'sku':('SKU','Variant SKU','SKU (Stock Keeping Unit)'),
 'image':('Product image URL','Image Src','Images','Image URL'),
 'description':('Description','Body (HTML)','Product Description')
}

def file_sha256(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def _safe_members(z):
 infos=z.infolist()
 if len(infos)>MAX_ITEMS:raise ValueError('压缩包包含过多文件')
 total=0
 for it in infos:
  p=PurePosixPath(it.filename.replace('\\','/'))
  if p.is_absolute() or '..' in p.parts:raise ValueError('ZIP包含不安全路径')
  if (it.external_attr>>16)&0o170000==0o120000:raise ValueError('ZIP不允许符号链接')
  if it.is_dir():continue
  if it.file_size>MAX_FILE:raise ValueError(f'源文件过大：{p.name}')
  if it.compress_size and it.file_size/it.compress_size>800:raise ValueError(f'压缩比异常：{p.name}')
  total+=it.file_size
  if total>MAX_UNCOMPRESSED:raise ValueError('解压后总文件体积超出安全限制')
 return [it for it in infos if not it.is_dir() and not it.filename.startswith('__MACOSX/')]

def _classify(path):
 bits=path.replace('\\','/').strip('/').split('/')
 if len(bits)<3:return None
 parent=bits[-2].lower()
 if parent in THEME_DIRS:cat='Theme'
 elif parent in PRODUCT_DIRS:cat='Products'
 elif parent in POLICY_DIRS:cat='Policies'
 else:return None
 return '/'.join(bits[:-2]),cat

def _column(fields,key):
 f={str(x).strip().casefold():x for x in fields if x}
 for alias in COLS[key]:
  if alias.casefold() in f:return f[alias.casefold()]
 return None

def _csv_metrics(raw):
 try:s=raw.decode('utf-8-sig')
 except UnicodeDecodeError:return {'error':'商品CSV不是UTF-8编码'}
 reader=csv.DictReader(io.StringIO(s))
 fields=reader.fieldnames or []
 if not fields:return {'error':'CSV缺少表头'}
 names={k:_column(fields,k) for k in COLS}
 missing=[k for k in ('title','sku','image') if names[k] is None]
 if missing:return {'error':'缺少商品CSV字段：'+','.join(missing),'columns':fields[:8]}
 titles=sku_count=image_count=amazon_count=0; malformed=[]; urls=set()
 sku_duplicates=0;seen_sku=set()
 for i,r in enumerate(reader,2):
  title=(r.get(names['title']) or '').strip()
  sku=(r.get(names['sku']) or '').strip()
  img=(r.get(names['image']) or '').strip()
  if title:titles+=1
  if sku:
   sku_count+=1
   if sku in seen_sku:sku_duplicates+=1
   seen_sku.add(sku)
  if img:
   image_count+=1
   urls.add(img)
   u=urlsplit(img)
   if u.scheme not in ('https','http') or not u.netloc:
    if len(malformed)<5:malformed.append(i)
   if 'amazon.' in (u.hostname or '') or 'media-amazon.com' in (u.hostname or ''):amazon_count+=1
 return {'product_title_rows':titles,'sku_rows':sku_count,'image_rows':image_count,
         'unique_image_links':len(urls),'amazon_image_rows':amazon_count,
         'bad_image_url_rows':malformed,'duplicate_sku_rows':sku_duplicates,
         'format':'Shopify CSV (observed columns)' if 'URL handle' in fields else 'CSV (header mapping required)',
         'missing_optional':[]}

def inspect_archive(path, expected=300, include_packages=True):
 path=Path(path)
 if not zipfile.is_zipfile(path):raise ValueError('输入不是有效ZIP')
 with zipfile.ZipFile(path) as z:
  infos=_safe_members(z);groups=defaultdict(list);unclassified=[]
  for it in infos:
   match=_classify(it.filename)
   if match:groups[match[0]].append((match[1],it))
   else:unclassified.append(it.filename)
  packages=[];overall=Counter();issues=[]
  for group in sorted(groups):
   items=groups[group];cats=Counter(x[0] for x in items)
   metrics={'product_title_rows':0,'sku_rows':0,'image_rows':0,'amazon_image_rows':0,
            'duplicate_sku_rows':0,'bad_image_url_rows':[]}
   local=[];source_placeholders=0
   for cat,it in items:
    name=it.filename
    if cat=='Products':
     if not name.lower().endswith('.csv'):local.append('商品文件格式不是CSV');continue
     cm=_csv_metrics(z.read(it))
     if cm.get('error'):local.append(cm['error'])
     else:metrics.update(cm)
    elif cat=='Theme':
     if not name.lower().endswith('.liquid'):local.append('装修文件不是Liquid: '+name.rsplit('/',1)[-1])
     elif b'REPLACE_WITH_' in z.read(it):source_placeholders+=1
    elif cat=='Policies':
     if not name.lower().endswith(('.txt','.docx')):local.append('政策文件格式异常: '+name.rsplit('/',1)[-1])
     elif name.lower().endswith('.txt') and SRC_SENTINELS.search(z.read(it).decode('utf-8-sig','replace')):
      source_placeholders+=1
   for category,count in (('Products',1),('Theme',4),('Policies',7)):
    if cats[category]!=count:local.append(f'{category} 应有{count}份，实际{cats[category]}份')
   if metrics['bad_image_url_rows']:local.append('商品CSV存在无效图片URL')
   if metrics['duplicate_sku_rows']:local.append('商品CSV存在重复SKU')
   status='structure_error' if local else 'structure_ok'
   h=hashlib.sha256()
   for _,file_info in sorted(items,key=lambda pair:pair[1].filename):
    rel=file_info.filename[len(group)+1:]
    h.update(rel.encode('utf-8')+b'\0')
    h.update(hashlib.sha256(z.read(file_info)).digest())
   entry={'path':group,'file_count':len(items),'status':status,'counts':dict(cats),
          'metrics':metrics,'source_template_fields_detected_in_files':source_placeholders,
          'content_sha256':h.hexdigest(),'problems':local}
   packages.append(entry);overall[status]+=1
   overall['product_title_rows']+=metrics.get('product_title_rows',0)
   overall['sku_rows']+=metrics.get('sku_rows',0)
   overall['image_rows']+=metrics.get('image_rows',0)
   overall['amazon_image_rows']+=metrics.get('amazon_image_rows',0)
  if len(packages)!=expected:issues.append(f'应为{expected}套组合，实际识别到{len(packages)}套')
  if unclassified:issues.append(f'{len(unclassified)}个文件不在标准三类目录中，请核对')
  if overall['structure_error']:issues.append(f"{overall['structure_error']}套结构或CSV字段异常")
  summary={'package_count':len(packages),'file_count':len(infos),
           'structure_ok':overall['structure_ok'],'structure_errors':overall['structure_error'],
           'product_title_rows':overall['product_title_rows'],'sku_rows':overall['sku_rows'],
           'image_rows':overall['image_rows'],'amazon_image_rows':overall['amazon_image_rows'],
           'unclassified_count':len(unclassified)}
  notes=[
   '检查结果只证明离线文件结构及格式，不证明产品参数、图片授权、网页可访问性或法律合规。',
   '源政策中的公司变量属于未配置模板，正式交付时必须填充并重新检查。',
   '商品图片使用外部链接时，仅检查URL格式；没有执行联网访问或版权核验。',
   'SHOPLINE CSV与主题需要按目标店铺版本及实际导入格式分别验证。'
  ]
  out={'source_file':path.name,'sha256':file_sha256(path),'summary':summary,
       'passed_structure_check':not issues,'blocking_findings':issues,
       'notes':notes,'unclassified_examples':unclassified[:12]}
  if include_packages:out['packages']=packages
  return out

def compare_archives(old,new,expected=300):
 a=inspect_archive(old,expected=expected)
 b=inspect_archive(new,expected=expected)
 old_map={x['path']:x for x in a['packages']};new_map={x['path']:x for x in b['packages']}
 common=set(old_map)&set(new_map)
 unchanged=sorted(k for k in common if old_map[k]['content_sha256']==new_map[k]['content_sha256'])
 changed=sorted(k for k in common if old_map[k]['content_sha256']!=new_map[k]['content_sha256'])
 return {'current_sha256':a['sha256'],'candidate_sha256':b['sha256'],
         'current':a['summary'],'candidate':b['summary'],
         'same_paths':sorted(common),'unchanged_paths':unchanged,'changed_paths':changed,
         'missing_paths':sorted(set(old_map)-set(new_map)),
         'new_paths':sorted(set(new_map)-set(old_map)),
         'safe_to_auto_activate':False,
         'reason':'只能预检，永不自动切换已有店铺关联。资源版本切换需显式确认并在备份后执行。',
         'candidate_blocking_findings':b['blocking_findings']}

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser()
 parser.add_argument('archive')
 parser.add_argument('--compare-to')
 parser.add_argument('--output',default='')
 args=parser.parse_args()
 result=compare_archives(args.archive,args.compare_to) if args.compare_to else inspect_archive(args.archive)
 text=json.dumps(result,ensure_ascii=False,indent=2)
 if args.output:Path(args.output).write_text(text,encoding='utf-8')
 print(json.dumps({'summary':result.get('summary',result.get('candidate')),'blocking_findings':result.get('blocking_findings',result.get('candidate_blocking_findings'))},ensure_ascii=False,indent=2))
