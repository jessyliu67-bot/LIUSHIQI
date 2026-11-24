from pathlib import Path
import json,re,sys,os
from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('ADMIN_PASSWORD','ui_test_only');os.environ.setdefault('SESSION_SECRET','1'*60)
sys.path.insert(0,str(ROOT));import app
client=TestClient(app.app);client.post('/api/login',json={'password':'ui_test_only'})
store=client.get('/api/v10/studio/STORE-001').json()
samples={'/api/v10/studio/STORE-001':store,
 '/api/deepseek/status':{'configured':False,'connected':False},
 '/api/v11/studio/STORE-001/one-click':{'modified_count':8,'version':1,'reused':False,
  'download_url':'/api/v11/studio/STORE-001/download/POLREL-DEMO.zip',
  'warnings':['Actual business rules must be checked'],'ai_status':'未配置DeepSeek密钥',
  'ai_audit_id':None}}
html=(ROOT/'static/studio.html').read_text(encoding='utf-8')
html=re.sub(r'<link[^>]*href="/static/[^>]+>','',html)
html=re.sub(r'<script[^>]*src="/static/[^>]+></script>','',html)
html=html.replace('<head>','<head><base href="http://127.0.0.1:8787/">',1)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for width in [1460,390]:
  page=b.new_page(viewport={'width':width,'height':920 if width>500 else 844})
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.route('**/api/v11/studio/**/download/*.zip',lambda r:r.fulfill(status=200,headers={'Content-Type':'application/zip','Content-Disposition':'attachment; filename=STORE-001.zip'},body=b'PK\x05\x06'+b'\x00'*18))
  page.set_content(html)
  page.add_style_tag(content=(ROOT/'static/studio.css').read_text(encoding='utf-8'))
  page.add_style_tag(content=(ROOT/'static/studio_readability.css').read_text(encoding='utf-8'))
  page.evaluate('''(samples)=>window.fetch=async function(path,opts){let k=String(path);return new Response(JSON.stringify(samples[k]||{detail:'Not mocked'}),{status:samples[k]?200:404,headers:{'content-type':'application/json'}})}''',samples)
  page.add_script_tag(content=(ROOT/'static/studio.js').read_text(encoding='utf-8'))
  page.wait_for_timeout(800)
  assert page.locator('#one-click-policy').count()==1
  page.locator('#one-click-policy').click()
  page.wait_for_timeout(450)
  assert '七份政策和页脚已自动填写' in page.locator('#modal-host').inner_text()
  assert page.locator('#modal-host a[download]').count()==1
  print('width',width,'UI_button_ok','horizontal_overflow',page.evaluate('document.documentElement.scrollWidth>innerWidth'),'errors',errors)
  page.screenshot(path=f'/mnt/data/BIG_BANG_V11_ONE_CLICK_{width}.png',full_page=False)
  page.close()
 b.close()
