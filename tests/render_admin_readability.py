import json,re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'static/index.html').read_text()
html=re.sub(r'<script[^>]+src="[^"]+"[^>]*></script>','',html)
html=re.sub(r'<link rel="stylesheet" href="[^"]+"\s*/?>','',html)
styles=['styles.css','v2.css','v3.css','bulk.css','v4.css','v5.css','v6.css','v7.css','v8.css','v9.css','admin_readability.css']
scripts=['app.js','v3.js','bulk.js','v4.js','v5.js','v6.js','v7.js','v8.js','v9.js']
fix=json.loads(Path('/mnt/data/BIG_BANG_V9_offline_fixtures.json').read_text())
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-gpu','--disable-dev-shm-usage'])
 for width,height,label in [(1500,960,'DESKTOP'),(390,844,'MOBILE')]:
  page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(html,wait_until='domcontentloaded')
  for f in styles:page.add_style_tag(content=(ROOT/'static'/f).read_text())
  for f in scripts:
   code=(ROOT/'static'/f).read_text()
   if f=='app.js':code=code.replace('setupEvents();boot();','setupEvents();')
   page.add_script_tag(content=code)
  page.evaluate('(fixture)=>{showApp();Object.assign(S,fixture);S.page="overview";render()}',{k:v for k,v in fix.items() if k!='asset'})
  page.wait_for_timeout(350)
  print(label,'overview overflow=',page.evaluate('document.documentElement.scrollWidth>innerWidth'), 'JS errors=',errors, 'metric font=',page.locator('.v9-metric-header').first.evaluate('(x)=>getComputedStyle(x).fontSize'))
  assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
  assert not errors
  page.screenshot(path=f'/mnt/data/BIG_BANG_V10_6_ADMIN_{label}.png',full_page=True)
  page.evaluate('()=>navigate("templates")')
  page.wait_for_timeout(140)
  print(label,'assets=',page.locator('.v9-lib-row').count())
  assert page.locator('.v9-lib-row').count()>0
  page.close()
 browser.close()
