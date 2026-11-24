import os,sys,json
from pathlib import Path
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('ADMIN_PASSWORD','testnotreal')
os.environ.setdefault('SESSION_SECRET','ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
sys.path.insert(0,str(ROOT))
import app
c=TestClient(app.app)
assert c.post('/api/login',json={'password':'testnotreal'}).status_code==200
samples={
 '/api/v10/studio/STORE-001':c.get('/api/v10/studio/STORE-001').json(),
 '/api/deepseek/status':{'configured':False,'connected':False},
 '/api/v10/studio/STORE-001/file/6':c.get('/api/v10/studio/STORE-001/file/6').json(),
 '/api/v10/studio/STORE-001/history':{'revisions':[],'releases':[],'proposals':[]}
}
html=(ROOT/'static/studio.html').read_text(encoding='utf-8')
css=(ROOT/'static/studio.css').read_text(encoding='utf-8') + '\n' + (ROOT/'static/studio_readability.css').read_text(encoding='utf-8')
js=(ROOT/'static/studio.js').read_text(encoding='utf-8')
import re
html=re.sub(r'<link[^>]+/static/studio(?:_readability)?.css[^>]*>','',html)
html=re.sub(r'<script[^>]+/static/studio.js[^>]*></script>','',html)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for w,h,label in [(1500,950,'DESKTOP'),(390,844,'MOBILE')]:
  ctx=b.new_context(viewport={'width':w,'height':h},device_scale_factor=1)
  page=ctx.new_page()
  errors=[];page.on('pageerror',lambda ex:errors.append(str(ex)))
  page.set_content(html,wait_until='domcontentloaded')
  page.add_style_tag(content=css)
  page.evaluate('''(samples)=>{window.fetch=async function(path,opts={}){const key=String(path);if(!(key in samples))return new Response(JSON.stringify({detail:'Mock endpoint not connected'}),{status:404,headers:{'content-type':'application/json'}});return new Response(JSON.stringify(samples[key]),{status:200,headers:{'content-type':'application/json'}})}}''',samples)
  page.add_script_tag(content=js)
  page.evaluate('load()')
  page.wait_for_timeout(900)
  print('DEBUG',page.locator('#tab-content').inner_text()[:150])
  print(label,'title',page.title(),'store',page.locator('#stat-store').inner_text(),'files',page.locator('.file-row').count(),'overflow',page.evaluate('document.documentElement.scrollWidth>innerWidth'),'errors',errors)
  page.screenshot(path=f'/mnt/data/BIG_BANG_V10_6_STUDIO_{label}.png',full_page=True)
  page.locator('[data-file="6"]').click();page.wait_for_timeout(450)
  print('editor loaded?',page.locator('#file-editor').count(), 'text length',len(page.locator('#file-editor').input_value()) if page.locator('#file-editor').count() else None)
  page.screenshot(path=f'/mnt/data/BIG_BANG_V10_6_EDITOR_{label}.png',full_page=True)
  page.locator('[data-tab="preview"]').click();page.wait_for_timeout(300)
  src=c.get('/api/v10/studio/STORE-001/preview').text
  page.locator('iframe').evaluate('(el,source)=>{el.removeAttribute("src");el.srcdoc=source}',src)
  page.wait_for_timeout(700)
  page.screenshot(path=f'/mnt/data/BIG_BANG_V10_6_PREVIEW_{label}.png',full_page=True)
  print('preview iframe',page.locator('iframe').count(),'errors',errors)
  ctx.close()
 b.close()
