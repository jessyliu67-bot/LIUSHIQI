"""V9 read-only store dossier and source-based composition preview.
Does not execute Shopify Liquid or pretend to be a live storefront screenshot.
"""
from __future__ import annotations
import csv, html, io, re, zipfile, hashlib
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from db import db, row
from pathlib import Path

IMAGE_RE=re.compile(r'https://cdn\.shopify\.com/[a-zA-Z0-9/?&_=.%+\-]+')
ASSIGN_RE=re.compile(r"assign\s+[\w]+_(headline|subtitle|label)\s*=\s*'([^']+)'",re.I)

def build_v9_router(guard):
    router=APIRouter()
    def resolve(template_id):
        with db() as conn:
            r=row(conn.execute('SELECT * FROM templates WHERE id=? OR code=?',(template_id,template_id)))
        if not r:raise HTTPException(404,'店铺模板不存在')
        src=Path(__file__).resolve().parent/'data'/'uploads'/r['archive_path']
        # Honor custom data root used by the parent application.
        from db import DATA
        src=DATA/'uploads'/r['archive_path']
        if not src.exists():raise HTTPException(404,'源ZIP不存在')
        return r,src
    def payload(template_id):
        r,src=resolve(template_id)
        prefix=r['inner_path'].rstrip('/')+'/'
        files=[];products=[];theme=[];policies=[];images=[];headlines=[];content_heading=''
        with zipfile.ZipFile(src) as z:
            paths=[n for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')]
            for filename in paths:
                rel=filename[len(prefix):]
                category='Theme' if filename.endswith('.liquid') else 'Products' if filename.lower().endswith('.csv') else 'Policies'
                files.append({'path':rel,'name':rel.split('/')[-1],'category':category,'bytes':z.getinfo(filename).file_size})
                if category=='Theme':
                    raw=z.read(filename).decode('utf-8-sig','replace')
                    theme.append({'path':rel,'name':rel.split('/')[-1],'lines':len(raw.splitlines()),'snippet':raw[:1600]})
                    if 'homepage' in rel.lower():
                        for k,v in ASSIGN_RE.findall(raw):headlines.append((k,v))
                    if 'content' in rel.lower():
                        for h in re.findall(r'<h2[^>]*>(.*?)</h2>',raw,re.I|re.S):
                            h=re.sub(r'<[^>]+>','',h).strip()
                            if h and '{{' not in h and '{%' not in h:
                                content_heading=h;break
                    for u in IMAGE_RE.findall(raw):
                        u=html.unescape(u).split('&width=')[0]
                        if u not in images:images.append(u)
                elif category=='Products':
                    content=z.read(filename).decode('utf-8-sig','replace')
                    reader=csv.DictReader(io.StringIO(content))
                    seen={}
                    for data in reader:
                        name=(data.get('Title') or '').strip()
                        if not name:continue
                        ident=(data.get('URL handle') or name).strip()
                        if ident not in seen:
                            item={'title':name,'handle':ident,'price':(data.get('Price') or '').strip(),'image':(data.get('Product image URL') or '').strip(),'sku_count':0,'sku_examples':[],'option_values':[]}
                            seen[ident]=item
                        item=seen[ident]; sku=(data.get('SKU') or '').strip()
                        if sku:
                            item['sku_count']+=1
                            if len(item['sku_examples'])<4:item['sku_examples'].append(sku)
                        for option in ['Option1 value','Option2 value','Option3 value']:
                            val=(data.get(option) or '').strip()
                            if val and val not in item['option_values'] and len(item['option_values'])<8:item['option_values'].append(val)
                        if not item['image'] and data.get('Product image URL'):item['image']=data['Product image URL'].strip()
                    products=list(seen.values())[:80]
                else:
                    policies.append({'name':rel.split('/')[-1],'path':rel})
        style_group=(re.search(r'模板(\d+)',r['label']) or [None,''])[1]
        label_text=(r['label'].split('/')[-1] if '/' in r['label'] else r['label'])
        values={k:v for k,v in headlines}
        with db() as conn:
            linked=row(conn.execute('SELECT s.code,s.label,s.status,d.domain,e.name as entity_name,sc.support_email FROM stores s LEFT JOIN store_domains d ON d.store_id=s.id LEFT JOIN entities e ON e.id=s.entity_id LEFT JOIN store_contacts sc ON sc.store_id=s.id WHERE s.template_id=? LIMIT 1',(r['id'],)))
        return {'template_id':r['id'],'template_code':r['code'],'label':label_text,'style_group':style_group,'source_path':r['inner_path'],'source_zip':r['archive_name'],'files':files,'products':products,'theme':theme,'policies':policies,'images':images[:20],'headline':values.get('headline') or 'Everyday essentials.','subtitle':values.get('subtitle') or '', 'content_heading':content_heading,'linked_store':linked,'preview_type':'Source-based composition — not a Shopify-rendered screenshot'}

    @router.get('/api/v9/assets/{template_id}')
    def get_asset(template_id:str,_:bool=Depends(guard)):
        return payload(template_id)

    @router.get('/api/v9/assets/{template_id}/file/{file_index}')
    def source_file(template_id:str,file_index:int,_:bool=Depends(guard)):
        r,src=resolve(template_id)
        prefix=r['inner_path'].rstrip('/')+'/'
        with zipfile.ZipFile(src) as z:
            paths=[n for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')]
            if file_index<0 or file_index>=len(paths):raise HTTPException(404,'文件不存在')
            path=paths[file_index]
            data=z.read(path)
        name=path.split('/')[-1]
        ascii_name=re.sub('[^a-zA-Z0-9._-]','_',name)
        return Response(data,media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{ascii_name}"','X-Content-Type-Options':'nosniff'})

    @router.get('/api/v9/assets/{template_id}/preview',response_class=HTMLResponse)
    def preview(template_id:str,_:bool=Depends(guard)):
        d=payload(template_id)
        esc=html.escape
        # Never insert raw Liquid into an iframe: Shopify controls are not available locally.
        urls=[u for u in d['images'] if urlparse(u).hostname=='cdn.shopify.com']
        first=urls[0] if urls else ''
        second=urls[2] if len(urls)>2 else (urls[1] if len(urls)>1 else '')
        headline=esc(d['headline']); subtitle=esc(d['subtitle']); shop='YOUR STORE'; items=d['products'][:4]
        style=int(d['style_group'] or '1')
        # Flat colors only; visual arrangement derives from source theme group, not invented page screenshot.
        palettes=[('#fff','#151515','#f1f0ec'),('#f5f2eb','#26251f','#d8dfd8'),('#151515','#fff','#404040'),('#e7eef0','#172f3b','#c6d4d7'),('#f6f0e7','#49352b','#e6d0be')]
        bg,ink,secondary=palettes[(style-1)%len(palettes)]
        arrangement='split' if style%3==0 else 'image' if style%3==1 else 'center'
        hero_img=f'<img src="{esc(first,quote=True)}" alt="Original Shopify CDN image" onerror="this.style.display=\'none\';this.parentNode.classList.add(\'missing\')">' if first else ''
        cards=''.join('<article><div class="product-img">'+(f'<img src="{esc(x["image"],quote=True)}" alt="" onerror="this.style.display=\'none\'">' if x['image'] and urlparse(x['image']).hostname in ('m.media-amazon.com','cdn.shopify.com') else '')+'</div><strong>'+esc(x['title'][:45])+'</strong><small>'+esc(x['price'] or 'Price in CSV')+'</small></article>' for x in items)
        block2=f'<img src="{esc(second,quote=True)}" alt="Original Shopify CDN asset" onerror="this.style.display=\'none\'">' if second else ''
        return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
        :root{{--bg:{bg};--ink:{ink};--muted:{secondary}}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif}}header{{height:72px;display:flex;align-items:center;justify-content:space-between;padding:0 5%;border-bottom:1px solid currentColor;gap:16px}}header b{{font-size:19px;letter-spacing:-.05em}}nav{{font-size:11px;letter-spacing:.08em}}nav span{{margin-left:24px}}.hero{{min-height:390px;display:grid;grid-template-columns:{'1fr 1fr' if arrangement=='split' else '1fr'};position:relative}}.hero-media{{position:absolute;inset:0;overflow:hidden;background:var(--muted)}}.hero-media img{{width:100%;height:100%;object-fit:cover}}.hero.image .hero-copy{{background:rgba(0,0,0,.47);color:white;z-index:1;align-self:end;max-width:65%;padding:64px 5%}}.hero.split .hero-media{{left:50%}}.hero.split .hero-copy{{padding:70px 9%;grid-column:1;z-index:2}}.hero.center .hero-media{{height:100%;opacity:.24}}.hero.center .hero-copy{{z-index:1;text-align:center;max-width:75%;margin:auto;padding:60px 0}}.hero-copy h1{{font-family:Georgia,'Times New Roman',serif;font-size:clamp(35px,5vw,80px);letter-spacing:-.05em;line-height:1.05;font-weight:400;margin:14px 0 20px}}.hero-copy p{{font-size:16px;line-height:1.75;max-width:38ch}}.cta{{display:inline-block;margin-top:24px;font-size:12px;letter-spacing:.11em;border:1px solid currentColor;padding:14px 22px}}main{{padding:60px 5%}}main h2{{font:400 36px Georgia,serif;letter-spacing:-.03em}}.products{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px}}.products article{{min-width:0}}.product-img{{aspect-ratio:4/5;background:var(--muted);overflow:hidden;margin-bottom:12px}}.product-img img{{width:100%;height:100%;object-fit:cover}}.products strong,.products small{{display:block;font-size:12px;line-height:1.5;margin-top:5px}}.products small{{opacity:.7}}.feature{{background:var(--muted);display:grid;grid-template-columns:1fr 1fr;margin-top:64px;min-height:270px}}.feature .feature-copy{{padding:45px}}.feature h2{{font:400 38px Georgia,serif;max-width:12ch}}.feature-image{{background:rgba(100,100,100,.1);overflow:hidden}}.feature-image img{{width:100%;height:100%;object-fit:cover}}footer{{padding:40px 5%;font-size:12px;border-top:1px solid currentColor;opacity:.75}}@media(max-width:700px){{header{{height:55px}}nav span:nth-child(n+2){{display:none}}.hero{{min-height:400px;grid-template-columns:1fr!important}}.hero.split .hero-media{{left:0;opacity:.3}}.hero.split .hero-copy{{padding:40px 7%}}.hero.image .hero-copy{{max-width:95%;padding:30px 7%}}.hero.center .hero-copy{{max-width:90%}}.products{{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}main{{padding:35px 5%}}.feature{{grid-template-columns:1fr}}.feature-image{{min-height:230px}}}}
        </style></head><body><header><b>{shop}</b><nav>SHOP <span>NEW ARRIVALS</span><span>ABOUT</span><span>CONTACT</span></nav></header><section class="hero {arrangement}"><div class="hero-media">{hero_img}</div><div class="hero-copy"><small>CURATED COLLECTION / {style:02d}</small><h1>{headline}</h1><p>{subtitle}</p><span class="cta">EXPLORE COLLECTION</span></div></section><main><h2>Discover the collection</h2><section class="products">{cards}</section><div class="feature"><div class="feature-copy"><small>THE EDIT</small><h2>{esc(d.get('content_heading') or 'Content section')}</h2><p>Based on the original 03-content.liquid module.</p></div><div class="feature-image">{block2}</div></div></main><footer>{shop} &nbsp;&nbsp; • &nbsp;&nbsp; Contact / Shipping / Returns</footer></body></html>'''

    return router
