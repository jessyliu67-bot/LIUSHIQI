'use strict';
const S = {page:'overview', entities:[],stores:[],templates:[],audits:[],overview:null,me:null,deepseek:null,query:'',currentAudit:null,polling:false};
const $=x=>document.querySelector(x);
const H=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtDate=d=>d?new Date(d).toLocaleString('zh-CN',{hour12:false}):'—';
const lookup=(arr,id)=>arr.find(x=>x.id===id);
const tag=(str)=>{const s=String(str||'未配置'),c=/通过|已核验|未发现问题|已解决/.test(s)?'ok':/失败|错误|异常|严重|发现问题/.test(s)?'bad':/待|复核|配置|整改|排队|进行中|处理中|采集|分析/.test(s)?'warn':'neutral';return `<span class="state ${c}">${H(s)}</span>`};
function toast(msg,bad=false){const p=$('#toast-root');p.innerHTML=`<div class="toast ${bad?'error':''}">${H(msg)}</div>`;clearTimeout(toast._t);toast._t=setTimeout(()=>p.innerHTML='',4600)}
async function api(path,opts={}){
  let res;
  try{res=await fetch(path,{credentials:'same-origin',...opts,headers:{...(opts.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(opts.headers||{})}})}
  catch(err){throw new Error('无法连接本地大爆炸服务。请检查启动窗口是否仍运行，以及 本地 /api/health 是否可访问；关闭重复启动的旧版本后刷新页面。原始错误：'+String(err.message||err))}
  if(res.status===401){showLogin();throw new Error('登录已过期，请重新登录')}
  let data;try{data=await res.json()}catch{data={detail:'服务器返回了无效数据'}}
  if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:'操作失败，请查看服务器日志');
  return data;
}
async function refresh(){
  const [overview,entities,stores,templates,audits,me,deepseek]=await Promise.all([
    api('/api/overview'),api('/api/entities'),api('/api/stores'),api('/api/templates'),api('/api/audits?limit=100'),api('/api/me'),api('/api/deepseek/status')]);
  Object.assign(S,{overview,entities,stores,templates,audits,me,deepseek});render();
}
function showLogin(){ $('#login').classList.remove('hidden');$('#shell').classList.add('hidden') }
function showApp(){ $('#login').classList.add('hidden');$('#shell').classList.remove('hidden') }
async function checkDesktopSetup(){
  const res=await api('/api/desktop/setup-status');
  if(!res.desktop_mode)return;
  document.body.classList.add('bb-desktop-mode');
  $('#bb-onboard').classList.toggle('hidden',res.api_configured);
  if(!res.api_configured)$('#bb-key').focus();
}
async function boot(){
  $('#today-label').textContent=new Date().toLocaleDateString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit'});
  try{await api('/api/me');showApp();await refresh();await checkDesktopSetup()}catch(e){showLogin()}
  setInterval(async()=>{
    if($('#shell').classList.contains('hidden')||S.polling)return;
    if(!['audits','overview'].includes(S.page))return;
    S.polling=true;
    try{
      const d=await api('/api/audits?limit=100');
      const changed=JSON.stringify(d.map(x=>[x.id,x.status,x.issue_count]))!==JSON.stringify(S.audits.map(x=>[x.id,x.status,x.issue_count]));
      if(changed){S.audits=d;S.overview=await api('/api/overview');render();}
    }catch(e){}finally{S.polling=false}
  },3500);
}
const PAGE_TITLES={overview:'全局指挥中心',entities:'公司主体库',stores:'店铺与域名',templates:'模板资产库',audits:'AI审核中心',settings:'系统设置'};
function navigate(page){S.page=page;S.query='';closeDrawer();document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===page));$('#top-title').textContent=PAGE_TITLES[page];$('#top-eyebrow').textContent='CONTROL ROOM / '+String(Object.keys(PAGE_TITLES).indexOf(page)+1).padStart(2,'0');$('.sidebar').classList.remove('menu-open');render();window.scrollTo(0,0)}
function render(){
 if(!S.overview)return;
 const content=$('#content');
 if(S.page==='overview')content.innerHTML=renderOverview();
 else if(S.page==='entities')content.innerHTML=renderEntities();
 else if(S.page==='stores')content.innerHTML=renderStores();
 else if(S.page==='templates')content.innerHTML=renderTemplates();
 else if(S.page==='audits')content.innerHTML=renderAudits();
 else if(S.page==='settings')content.innerHTML=renderSettings();
}
const sectionHead=(title,subtitle,buttons='')=>`<div class="section-intro"><div><h2>${title}</h2><p>${subtitle}</p></div><div class="action-strip">${buttons}</div></div>`;
const blank=(title,text,button='')=>`<div class="empty"><div class="empty-icon">✳</div><strong>${H(title)}</strong><p>${H(text)}</p>${button}</div>`;
function renderOverview(){
 const x=S.overview, total=300;
 const assigned=S.stores.filter(s=>s.entity_id).length;
 const withDom=S.stores.filter(s=>s.domain).length;
 const ready=S.stores.filter(s=>s.domain && s.entity_id).length;
 const pct=Math.max(0,Math.min(100,Math.round((x.stores||0)/total*100)));
 const dots=Array.from({length:total},(_,i)=>{
   const st=S.stores[i];
   const kind=!st?'idle':st.audit_status&&/通过/.test(st.audit_status)?'checked':st.domain&&st.entity_id?'ready':st.entity_id?'assigned':'registered';
   const t=st?`${st.code} / ${st.domain||'待绑定域名'} / ${st.entity_name||'主体未分配'}`:`预留槽位 ${String(i+1).padStart(3,'0')}`;
   return `<span class="fleet-dot ${kind}" title="${H(t)}"></span>`;
 }).join('');
 const recent=x.recent.map(r=>`<tr><td><span class="code">${H(r.store_code)}</span></td><td>${H(r.domain||'—')}</td><td>${tag(r.status)}</td><td class="code">${H(fmtDate(r.started_at))}</td><td><button class="btn-text" data-action="view-audit" data-id="${H(r.id)}">查看 ↗</button></td></tr>`).join('');
 return `<section class="mission-hero">
   <div class="mission-grid"></div><div class="mission-scanline"></div>
   <div class="mission-intro"><div class="mission-label"><span class="live-square"></span> BIG BANG OPERATIONS / V2.0 <span class="slash">/</span> 001—300</div>
     <h1>让三百家店铺，<br><em>始终尽在掌握。</em></h1>
     <p>主体、域名、资产和 AI 审核。把所有复杂的店铺运营，收拢至一个清晰的控制中心。</p>
     <div class="mission-actions"><button class="btn btn-acid" data-action="go-stores">管理店铺资产 <span>↗</span></button><button class="btn btn-ghost" data-action="go-audits">进入 AI 审核 <span>→</span></button></div>
   </div>
   <div class="mission-gauge" style="--progress:${pct}%"><div class="gauge-head">FLEET / REGISTERED</div><div class="gauge-ring"><div class="gauge-center"><strong>${x.stores}</strong><span>OF ${total} STORES</span></div></div><div class="gauge-meta"><span>${pct}% REGISTERED</span><span class="gauge-signal">● LIVE DATABASE</span></div></div>
   <div class="mission-serial">B.B / SYS.0206</div>
 </section>
 <section class="metrics-row" aria-label="系统统计">
  <div class="metric"><span class="metric-top"><span class="metric-index">01 /</span> 店铺资产</span><div class="metric-value">${x.stores}<small> / 300</small></div><span class="metric-bottom">已登记店铺</span></div>
  <div class="metric"><span class="metric-top"><span class="metric-index">02 /</span> 经营主体</span><div class="metric-value">${x.entities}</div><span class="metric-bottom">公司主体记录</span></div>
  <div class="metric"><span class="metric-top"><span class="metric-index">03 /</span> 模板资产</span><div class="metric-value">${x.templates}</div><span class="metric-bottom">原始文件保持不变</span></div>
  <div class="metric"><span class="metric-top"><span class="metric-index">04 /</span> 审核事件</span><div class="metric-value">${x.audits}</div><span class="metric-bottom">${x.running?`正在处理 ${x.running} 项`:'暂无运行中的任务'}</span></div>
 </section>
 <section class="command-layout">
  <div class="command-primary">
   <div class="panel fleet-panel"><div class="panel-head head-spread"><div><div class="panel-kicker">ASSET CONSTELLATION / 001—300</div><h3>店铺矩阵 <span class="panel-hint">300个资产槽位 · 按登记顺序</span></h3></div><button class="panel-link" data-action="go-stores">查看全部店铺 ↗</button></div>
    <div class="fleet-content"><div class="fleet-meta"><span>FLEET DEPLOYMENT</span><strong>${x.stores}<small> / 300</small></strong></div><div class="fleet-dots">${dots}</div><div class="fleet-legend"><span><i class="idle"></i>未登记</span><span><i class="registered"></i>已登记</span><span><i class="assigned"></i>已分配主体</span><span><i class="ready"></i>主体+域名</span><span><i class="checked"></i>审核状态通过</span></div></div>
   </div>
   <div class="panel activity-panel"><div class="panel-head head-spread"><div><div class="panel-kicker">REVIEW LOG / RECENT</div><h3>最新审核动态</h3></div><button class="panel-link" data-action="go-audits">打开审核中心 ↗</button></div>
   ${x.recent.length?`<div class="table-scroller"><table class="data-table"><thead><tr><th>店铺</th><th>域名</th><th>检测状态</th><th>开始时间</th><th></th></tr></thead><tbody>${recent}</tbody></table></div>`:`<div class="activity-empty"><div class="empty-stroke">↗</div><div><strong>等待第一条审核记录</strong><p>连接域名后，开始规则检查或调用 DeepSeek 辅助分析。</p></div><button class="btn btn-sm" data-action="go-audits">创建审核 →</button></div>`}</div>
  </div>
  <div class="command-side">
   <div class="panel action-panel"><div class="panel-head"><div><div class="panel-kicker">NEXT ACTIONS</div><h3>开始部署</h3></div><span class="panel-count">04 STEPS</span></div><div class="action-list">
    <button data-action="go-entities"><span>01</span><div><strong>录入公司主体</strong><small>${x.entities} 家主体已登记</small></div><b>↗</b></button>
    <button data-action="go-templates"><span>02</span><div><strong>导入完整模板ZIP</strong><small>${x.templates} 套资产已登记</small></div><b>↗</b></button>
    <button data-action="go-stores"><span>03</span><div><strong>分配主体与域名</strong><small>${ready} 家店铺已完成双重配置</small></div><b>↗</b></button>
    <button data-action="go-audits"><span>04</span><div><strong>启动实时审核</strong><small>${x.audits} 条审核记录</small></div><b>↗</b></button>
   </div></div>
   <div class="panel integrity-panel"><div class="panel-head"><div><div class="panel-kicker">SYSTEM HEALTH</div><h3>运行状态</h3></div><span class="health-circle"></span></div>
    <div class="system-rows"><div><span>本地数据库</span><b class="good">● 已连接</b></div><div><span>DeepSeek API</span><b class="${S.deepseek?.last_test?.ok?'good':'pending'}">● ${H(aiConnectionLabel())}</b></div><div><span>站点部署状态</span><b>本地环境</b></div></div>
    <div class="system-foot">当前版本不修改 Shopify 网站，也不代表官方平台认证。<button class="text-link" data-action="go-settings">设置 ↗</button></div>
   </div>
   <div class="registry-snapshot"><div class="snapshot-index">ASSIGNMENT SNAPSHOT</div><div><span>主体已分配</span><strong>${assigned}</strong></div><div class="snapshot-track"><i style="width:${S.stores.length?Math.round(assigned/S.stores.length*100):0}%"></i></div><div><span>域名已绑定</span><strong>${withDom}</strong></div><div class="snapshot-track"><i style="width:${S.stores.length?Math.round(withDom/S.stores.length*100):0}%"></i></div><div class="snapshot-footer">基于 ${x.stores} 家已登记店铺统计</div></div>
  </div>
 </section>`;
}
function renderEntities(){
 const list=S.entities.filter(e=>(e.name+' '+e.code+' '+e.registration_no).toLowerCase().includes(S.query.toLowerCase()));
 const cells=list.map(e=>`<tr><td><span class="code">${H(e.code)}</span></td><td><strong>${H(e.name)}</strong><div class="muted small">${H(e.country||'国家/地区未填写')}</div></td><td>${tag(e.status)}</td><td><strong>${e.assigned}</strong> / ${e.capacity||'不限'}</td><td><span class="code">${H(e.email||'—')}</span></td><td>${e.documents} 份</td><td><div class="action-strip"><button class="btn btn-sm" data-action="edit-entity" data-id="${H(e.id)}">编辑</button><button class="btn btn-sm" data-action="entity-docs" data-id="${H(e.id)}">文件</button></div></td></tr>`).join('');
 return sectionHead('公司主体库','一家主体关联多家店铺，资料统一维护。','<button class="btn btn-dark" data-action="add-entity">＋ 新建公司主体</button>')+
 `<div class="panel"><div class="panel-head"><div><h3>主体清单</h3><p>共 ${S.entities.length} 家主体 · 支持设置每家主体的店铺分配额度</p></div></div><div class="panel-body"><div class="toolbar"><input class="input" id="search-field" placeholder="搜索公司名称、主体编号或登记号" value="${H(S.query)}" /><span class="state neutral">主体证明不会公开展示</span></div></div>
 ${S.entities.length?`<div class="table-scroller"><table class="data-table"><thead><tr><th>主体编号</th><th>法定名称</th><th>资料状态</th><th>店铺额度</th><th>客服邮箱</th><th>证明文件</th><th>操作</th></tr></thead><tbody>${cells||'<tr><td colspan="7">无匹配结果</td></tr>'}</tbody></table></div>`:blank('尚未创建公司主体','点击“新建公司主体”录入真实注册信息和资料。','<button class="btn" data-action="add-entity">添加第一家主体</button>')}</div>`;
}
function renderStores(){
 const list=S.stores.filter(s=>(s.code+' '+s.label+' '+(s.domain||'')+' '+(s.entity_name||'')).toLowerCase().includes(S.query.toLowerCase()));
 const cells=list.map(s=>`<tr><td><span class="code">${H(s.code)}</span><div class="muted small">${H(s.label||'—')}</div></td><td>${H(s.template_code||'未选择')}</td><td>${H(s.entity_name||'未分配')}<div class="muted code">${H(s.entity_code||'')}</div></td><td>${s.domain?`<a class="text-link monospace" target="_blank" rel="noopener noreferrer" href="https://${encodeURI(s.domain)}">${H(s.domain)}</a>`:'<span class="muted">未绑定</span>'}</td><td>${tag(s.status)}</td><td>${tag(s.audit_status||'未审核')}</td><td><button class="btn btn-sm" data-action="edit-store" data-id="${H(s.id)}">管理</button></td></tr>`).join('');
 return sectionHead('店铺与域名分配','将现有完整模板关联到主体和域名，不执行商品/装修匹配。',
 `<a class="btn" href="/static/300_store_blank_import.csv" download>下载300店空白表</a><button class="btn" data-action="import-csv">导入店铺CSV</button><button class="btn" data-action="export-stores">导出CSV</button><button class="btn btn-dark" data-action="add-store">＋ 新建店铺</button>`)+
 `<div class="notice">批量CSV格式：<span class="code">store_code,label,template_code,entity_code,domain</span>。对应编号必须存在；需要留空的主体或域名可不填，系统不会自动匹配。</div><div class="panel"><div class="panel-head"><div><h3>店铺主数据</h3><p>${S.stores.length} 家店铺 · ${S.stores.filter(s=>s.domain).length} 个已绑定域名</p></div></div><div class="panel-body"><div class="toolbar"><input id="search-field" class="input" placeholder="查找编号、公司主体、域名" value="${H(S.query)}" /></div></div>
 ${S.stores.length?`<div class="table-scroller"><table class="data-table"><thead><tr><th>店铺</th><th>模板</th><th>公司主体</th><th>域名</th><th>配置</th><th>审核</th><th>操作</th></tr></thead><tbody>${cells||'<tr><td colspan="7">无匹配结果</td></tr>'}</tbody></table></div>`:blank('店铺库目前为空','可手动建立店铺，或用CSV一次导入300家店铺。','<button class="btn" data-action="add-store">新增店铺</button>')}</div>`;
}
function renderTemplates(){
 const list=S.templates.filter(t=>(t.code+' '+t.label).toLowerCase().includes(S.query.toLowerCase()));
 const cells=list.map(t=>`<tr><td class="code">${H(t.code)}</td><td><strong>${H(t.label)}</strong></td><td>${H(t.archive_name||'—')}</td><td>${t.file_count}</td><td class="code">${H((t.checksum||'').slice(0,10))}…</td><td>${H(fmtDate(t.created_at))}</td><td><a class="text-link" href="/api/templates/${encodeURIComponent(t.id)}/bundle.zip">下载本套</a></td></tr>`).join('');
 return sectionHead('模板资产库','只登记和保存你已经制作好的模板文件，不重新生成或改动商品与装修。','<button class="btn btn-dark" data-action="import-templates">＋ 上传模板ZIP</button>')+
 `<div class="notice info">支持导入包含多层文件夹的ZIP。如果识别到组合目录下至少两类「商品CSV / 装修文件 / 七个条款文件」，就分别建档；不会修改文件内容。最大文件420MB。</div>
 <div class="kpis"><div class="kpi"><div class="k-title">已入库模板</div><div class="k-num">${S.templates.length}</div><div class="k-foot">Target 300</div></div><div class="kpi"><div class="k-title">保持原样</div><div class="k-num">100<span style="font-size:15px">%</span></div><div class="k-foot">No auto matching or rewrite</div></div></div>
 <div class="panel"><div class="panel-head"><h3>模板归档明细</h3><span class="state neutral">保留原始ZIP</span></div><div class="panel-body"><div class="toolbar"><input id="search-field" class="input" placeholder="搜索模板编号或文件路径" value="${H(S.query)}" /></div></div>
 ${S.templates.length?`<div class="table-scroller"><table class="data-table"><thead><tr><th>编号</th><th>内部文件夹 / 模板名称</th><th>源ZIP</th><th>文件数</th><th>SHA256</th><th>导入时间</th><th>独立资源包</th></tr></thead><tbody>${cells}</tbody></table></div>`:blank('等待导入模板文件','上传已完成的ZIP压缩包后系统会扫描目录并建立模板清单。','<button class="btn" data-action="import-templates">选择ZIP文件</button>')}</div>`;
}
function renderAudits(){
 const x=S.audits;
 const records=x.map(a=>`<tr><td class="code">${H(a.store_code)}</td><td>${H(a.domain||'尚未绑定')}</td><td>${a.mode==='ai'?'<span class="state neutral">规则 + DeepSeek</span>':'<span class="state neutral">确定性规则</span>'}</td><td>${tag(a.status)}</td><td>${a.issue_count}</td><td class="code">${H(fmtDate(a.started_at))}</td><td><button class="btn btn-sm" data-action="view-audit" data-id="${H(a.id)}">查看详情</button></td></tr>`).join('');
 return sectionHead('AI审核中心','基于实际网页证据检查公司主体、七份政策、页面与图片基本结构。','<button class="btn" data-action="refresh">刷新记录</button>')+
 `${renderAiConnectionBox(true)}<div class="panel"><div class="panel-head"><div><h3>创建审核任务</h3><p>规则检测不消耗DeepSeek额度；AI模式需要服务端配置API密钥。</p></div>${tag(aiConnectionLabel())}</div>
 <div class="panel-body"><div class="audit-filters"><select class="select" id="audit-store"><option value="">选择要检查的店铺</option>${S.stores.map(s=>`<option value="${H(s.id)}">${H(s.code)} · ${H(s.domain||'未绑定域名')}</option>`).join('')}</select><select class="select" id="audit-mode"><option value="rules">确定性规则审核</option><option value="ai">规则 + DeepSeek AI</option></select><button class="btn btn-dark" data-action="run-audit" ${S.stores.length?'':'disabled'}>立即审核 →</button></div>
 <div class="action-strip" style="margin-top:13px"><button class="btn btn-sm" data-action="run-all" ${S.stores.length?'':'disabled'}>批量审核已登记店铺</button><span class="helper">批量最多300家；本地版顺序执行、支持查看进度，但重启后运行中的任务不能自动续跑。</span></div></div></div>
 <div class="panel"><div class="panel-head"><div><h3>审核历史</h3><p>此处的“规则检查未发现问题”不代表所有合规事项已经通过。</p></div><span class="state neutral">${x.length} 条记录</span></div>
 ${x.length?`<div class="table-scroller"><table class="data-table"><thead><tr><th>店铺</th><th>域名</th><th>模式</th><th>审核状态</th><th>问题数</th><th>开始时间</th><th>操作</th></tr></thead><tbody>${records}</tbody></table></div>`:blank('没有审核记录','导入店铺并绑定域名后，可开始网站检测。')}</div>
 <div class="notice">本版检测公开首页及七份 Pages 政策的可访问性、基础内容和主体文字一致性；暂不读取Shopify后台、执行真实购物车操作或断言商标授权。</div>`;
}
function aiConnectionLabel(){
 const st=S.deepseek;
 if(!st?.configured)return '未配置 API Key';
 if(st.last_test?.ok)return '测试通过 · AI可调用';
 if(st.last_test && !st.last_test.ok)return '最近测试未通过';
 return '密钥已配置 · 尚未测试';
}
function renderAiConnectionBox(compact=false){
 const st=S.deepseek||{};
 const last=st.last_test;
 const state=!st.configured?'missing':last?.ok?'success':last?'failure':'pending';
 const note=last ? last.message : (st.configured?'已经填写 API Key，但尚未验证连接是否可用。':'请在系统设置中填写 DeepSeek API Key。');
 const meta=last ? `<span>最近检测：${H(fmtDate(last.tested_at))}</span><span>响应：${H(last.latency_ms??'—')} ms</span>${last.http_status!=null?`<span>HTTP ${H(last.http_status)}</span>`:''}${last.usage?.total_tokens!=null?`<span>本次 ${H(last.usage.total_tokens)} Token</span>`:''}` : `<span>模型：${H(st.model||S.me?.model||'deepseek-flash')}</span><span>状态不等于已接通</span>`;
 return `<section class="ai-connect ai-connect-${state}${compact?' ai-connect-compact':''}">
  <div class="ai-connect-main"><div><div class="ai-connect-kicker">DEEPSEEK · 实时接口诊断</div><h3>${H(aiConnectionLabel())}</h3><p>${H(note)}</p><div class="ai-connect-meta">${meta}</div></div><button class="btn ai-connect-button" data-action="test-deepseek" ${st.in_progress?'disabled':''}>${st.in_progress?'正在测试…':'测试 AI 是否接通 →'}</button></div>
  ${!compact?`<div class="ai-connect-help">只发送固定的测试文本 <code>BIG_BANG_OK</code>；不传营业执照、客户资料或商品信息。请求会消耗少量 API Token。</div>`:''}
 </section>`;
}
async function testDeepseekButton(){
 const button=document.querySelector('[data-action="test-deepseek"]');
 if(button){button.disabled=true;button.textContent='正在与 DeepSeek 通信…'}
 try{
  const result=await api('/api/deepseek/test',{method:'POST',body:'{}'});
  S.deepseek=await api('/api/deepseek/status');
  render();
  toast(result.ok?'AI连接测试通过，可以使用 DeepSeek。':result.message,!result.ok);
 }catch(e){toast('AI连接测试失败：'+e.message,true);S.deepseek=await api('/api/deepseek/status').catch(()=>S.deepseek);render();}
}
function renderSettings(){
 return sectionHead('系统设置','本地单管理员版本 · 密钥仅保存在服务端配置。')+renderAiConnectionBox()+
 `<div class="two-col"><div><div class="panel"><div class="panel-head"><h3>DeepSeek API 配置</h3>${tag(aiConnectionLabel())}</div><div class="panel-body"><div class="section-article"><h4>API endpoint</h4><div class="mono-frame">https://api.deepseek.com/chat/completions</div></div><div class="section-article"><h4>当前模型</h4><p class="code">${H(S.me.model)}</p></div><div class="section-article"><h4>连接步骤</h4><p>通过首页首次配置窗口设置 DeepSeek API，之后可在系统内更新，无需手动编辑文件。</p><button class="btn btn-dark" type="button" data-action="change-deepseek">更新 DeepSeek API Key</button></div><div class="notice error">不要把 API Key 输入任何公开网页或写进前端代码。密钥由本地服务保存，不会显示在资源文件或导出包中。</div></div></div></div>
 <div><div class="panel"><div class="panel-head"><h3>系统能力与限制</h3></div><div class="panel-body"><div class="list-row"><span>本地 SQLite 持久化</span>${tag('可用')}</div><div class="list-row"><span>主体证明上传 / 下载</span>${tag('可用')}</div><div class="list-row"><span>模板ZIP目录识别</span>${tag('可用')}</div><div class="list-row"><span>批量店铺 CSV</span>${tag('可用')}</div><div class="list-row"><span>公开网站检测</span>${tag('可用')}</div><div class="list-row"><span>DeepSeek文本分析</span>${tag(S.deepseek?.last_test?.ok?'最近测试通过':S.deepseek?.configured?'待测试':'待配置')}</div><div class="list-row"><span>Shopify后台授权</span>${tag('暂未接入')}</div><div class="list-row"><span>生产级任务队列</span>${tag('暂未接入')}</div><div class="list-row"><span>线上多用户权限</span>${tag('暂未接入')}</div></div></div><div class="panel"><div class="panel-head"><h3>数据保护提醒</h3></div><div class="panel-body small muted">主体证件与模板存放在本机 data/uploads，管理员必须定期备份整个 data 目录。当前是本地原型，不能直接部署到公网承载真实敏感资料。外部AI接口只发送被检页面文字和已配置的必要主体字段，不发送营业执照文件。</div></div></div></div>`;
}
function showDrawer(kicker,title,body,footer=''){
 $('#drawer-root').innerHTML=`<div class="drawer-backdrop" id="drawer-overlay"><aside class="drawer" role="dialog" aria-modal="true"><div class="drawer-head"><div><div class="eyebrow">${kicker}</div><h2>${title}</h2></div><button class="drawer-close" data-action="close-drawer" aria-label="关闭">×</button></div><div class="drawer-body">${body}</div>${footer?`<div class="drawer-footer">${footer}</div>`:''}</aside></div>`;
}
function closeDrawer(){$('#drawer-root').innerHTML=''}
const f=(name,label,val='',other='')=>`<div class="form-field"><label for="f-${name}">${label}</label><input class="input" id="f-${name}" name="${name}" value="${H(val)}" ${other}/></div>`;
function entityDrawer(id){
 const x=lookup(S.entities,id)||{};
 const body=`<form id="entity-form" data-id="${H(id||'')}"><div class="form-grid">${f('name','法定公司名称 *',x.name||'','required maxlength="255"')}${f('registration_no','登记编号 / EIN',x.registration_no||'')}${f('country','注册国家 / 地区',x.country||'')}${f('capacity','计划管理店铺数（0=不限）',x.capacity??0,'type="number" min="0" max="10000"')}${f('email','官方客服邮箱',x.email||'','type="email"')}${f('phone','客服电话',x.phone||'')}<div class="span2">${f('address','实际注册地址',x.address||'')}</div><div class="form-field span2"><label>主体资料状态</label><select class="select" name="status">${['待核验','已核验','异常','停用'].map(v=>`<option ${x.status===v?'selected':''}>${v}</option>`).join('')}</select></div></div><div class="notice">“已核验”必须由管理员根据真实登记证明确认，本地系统不会自动验证公司登记真实性。</div></form>`;
 showDrawer('ENTITY RECORD',id?'编辑公司主体':'创建公司主体',body,'<button class="btn" data-action="close-drawer">取消</button><button class="btn btn-dark" data-action="submit-entity">保存主体信息</button>');
}
function storeDrawer(id){
 const x=lookup(S.stores,id)||{};
 const entities=`<option value="">尚未分配</option>`+S.entities.map(e=>`<option value="${H(e.id)}" ${e.id===x.entity_id?'selected':''}>${H(e.code)} · ${H(e.name)} (${e.assigned}/${e.capacity||'∞'})</option>`).join('');
 const templates=`<option value="">暂不选择模板</option>`+S.templates.map(t=>`<option value="${H(t.id)}" ${t.id===x.template_id?'selected':''}>${H(t.code)} · ${H(t.label.slice(0,45))}</option>`).join('');
 const body=`<form id="store-form" data-id="${H(id||'')}"><div class="form-grid">${f('code','店铺编号 *',x.code||'','required '+(id?'readonly':''))}${f('label','备注 / 店铺名称',x.label||'')}<div class="form-field span2"><label>所属公司主体</label><select class="select" name="entity_id">${entities}</select></div><div class="form-field span2"><label>关联现有模板（不修改内容）</label><select class="select" name="template_id">${templates}</select></div><div class="span2">${f('domain','店铺域名',x.domain||'','placeholder="example.com"')}</div><div class="form-field span2"><label>店铺配置状态</label><select class="select" name="status">${['待配置','待部署','待审核','整改中','需复核','验收通过'].map(v=>`<option ${x.status===v?'selected':''}>${v}</option>`).join('')}</select></div></div><div class="notice">更改店铺主体、模板或域名后会自动标记为“需复核”。店铺的“验收通过”在本地MVP中属于手工状态，不能代表AppLovin官方批准。</div></form>`;
 showDrawer('STORE CONFIGURATION',id?'编辑店铺配置':'新增店铺',body,'<button class="btn" data-action="close-drawer">取消</button><button class="btn btn-dark" data-action="submit-store">保存配置</button>');
}
async function docDrawer(id){
 const e=lookup(S.entities,id);if(!e)return;
 const documents=await api('/api/entities/'+id+'/documents');
 const body=`<div class="notice info"><b>${H(e.name)}</b><br>上传原始主体证明文件，系统会在本地私密目录保存。</div>
 <div class="file-line"><b>证明文件上传</b><span class="helper">TXT / PDF / PNG / JPG · 单个文件最大12MB</span><button class="btn btn-dark" data-action="upload-doc" data-id="${H(id)}">选择并上传文件</button></div>
 <div class="section-article"><h4>已上传文件（${documents.length}）</h4>${documents.length?documents.map(d=>`<div class="list-row"><span>${H(d.filename)}<span class="muted small"> · ${(d.byte_size/1024).toFixed(1)} KB</span></span><a class="text-link" href="/api/documents/${encodeURIComponent(d.id)}/download">下载</a></div>`).join(''):'<p class="muted small">暂无证明文件。</p>'}</div>`;
 showDrawer('ENTITY DOCUMENTS','主体证明文件',body);
}
function auditDrawerTemplate(a){
 let sum=a.summary||{};const issues=a.issues||[];const evi=a.evidence||[];
 const issueHtml=issues.map(i=>{
 const kind=i.severity==='严重'?'':i.severity==='一般'?'warn':'review';
 return `<article class="rule"><div class="rule-icon ${kind}">${kind==='review'?'?':'!'}</div><div><h4>${H(i.title)} <span class="state ${kind==='review'?'warn':kind==='warn'?'warn':'bad'}">${H(i.severity)}</span></h4><div class="rule-meta">${H(i.rule_code)} · ${H(i.page_url||'站点配置')} · ${H(i.origin)}</div><p>${H(i.detail)}</p><div class="rule-actions"><select class="select select-small" data-issue-state="${H(i.id)}">${['待处理','处理中','待复检','已解决','已接受风险'].map(s=>`<option ${i.state===s?'selected':''}>${s}</option>`).join('')}</select><span class="helper">状态由人工维护，已解决不替代复检。</span></div></div></article>`}).join('');
 return `<div class="audit-status">${H(a.status)} · ${H(a.mode==='ai'?'规则 + AI':'规则检查')} · ${H(a.store_code)} · ${H(a.domain||'未绑定域名')}</div>
 <div class="report-summary"><div><strong>${sum.pages_checked??evi.length}</strong><span>采集页面</span></div><div><strong style="color:#b6454a">${sum.critical??0}</strong><span>严重问题</span></div><div><strong style="color:#ad7a27">${sum.warning??0}</strong><span>一般问题</span></div><div><strong>${sum.review??0}</strong><span>需人工复核</span></div></div>
 <div class="section-article"><h4>AI分析</h4><p>${H(sum.ai_status||'尚未运行AI')}</p><p class="helper">采集范围：仅公开网站（public_site_only）；未连接Shopify后台。</p></div>
 ${a.error?`<div class="notice error">${H(a.error)}</div>`:''}
 <div class="section-article"><h4>问题明细 (${issues.length})</h4>${issues.length?issueHtml:blank('未发现记录的问题','这不等于已完成所有商业合规或版权核验。')}</div>
 <div class="section-article"><h4>网页证据 (${evi.length})</h4>${evi.length?evi.map(p=>`<details class="section-article"><summary class="code" style="cursor:pointer">HTTP ${H(p.http_status)} · ${H(p.page_url)}</summary><div class="mono-frame">${H(p.excerpt||'页面无文字')}</div></details>`).join(''):'<p class="muted small">暂无网页证据。</p>'}</div>`;
}
async function openAudit(id){
 S.currentAudit=id;
 const a=await api('/api/audits/'+id);
 showDrawer('AUDIT RECORD','审核证据与问题',auditDrawerTemplate(a),`<button class="btn" data-action="download-audit" data-id="${H(id)}">导出JSON</button><button class="btn" data-action="close-drawer">关闭</button>`);
}
async function submitEntity(){
 const form=$('#entity-form');if(!form.reportValidity())return;
 const payload=Object.fromEntries(new FormData(form));payload.capacity=Number(payload.capacity||0);
 const id=form.dataset.id;
 await api(id?'/api/entities/'+id:'/api/entities',{method:id?'PUT':'POST',body:JSON.stringify(payload)});
 closeDrawer();await refresh();toast(id?'主体已更新；关联网店已标记复核':'主体创建成功');
}
async function submitStore(){
 const form=$('#store-form');if(!form.reportValidity())return;
 const payload=Object.fromEntries(new FormData(form));payload.entity_id=payload.entity_id||null;payload.template_id=payload.template_id||null;
 const id=form.dataset.id;
 await api(id?'/api/stores/'+id:'/api/stores',{method:id?'PUT':'POST',body:JSON.stringify(payload)});
 closeDrawer();await refresh();toast(id?'店铺配置已更新':'店铺创建成功');
}
async function handleAction(target){
 const action=target.dataset.action,id=target.dataset.id;
 switch(action){
 case 'add-entity':entityDrawer();break;
 case 'edit-entity':entityDrawer(id);break;
 case 'submit-entity':await submitEntity();break;
 case 'entity-docs':await docDrawer(id);break;
 case 'upload-doc':$('#doc-picker').dataset.entityId=id;$('#doc-picker').click();break;
 case 'add-store':storeDrawer();break;
 case 'edit-store':storeDrawer(id);break;
 case 'submit-store':await submitStore();break;
 case 'import-templates':$('#template-picker').click();break;
 case 'import-csv':$('#csv-picker').click();break;
 case 'export-stores':window.location.href='/api/export/stores.csv';break;
 case 'download-audit':window.location.href='/api/audits/'+encodeURIComponent(id)+'/export.json';break;
 case 'close-drawer':closeDrawer();break;
 case 'view-audit':await openAudit(id);break;
 case 'refresh':await refresh();toast('数据已刷新');break;
 case 'go-entities':navigate('entities');break;
 case 'go-stores':navigate('stores');break;
 case 'go-templates':navigate('templates');break;
 case 'go-audits':navigate('audits');break;
 case 'go-settings':navigate('settings');break;
 case 'test-deepseek':await testDeepseekButton();break;
 case 'change-deepseek':$('#bb-onboard').classList.remove('hidden');$('#bb-key').focus();break;
 case 'logout':await api('/api/logout',{method:'POST',body:'{}'});showLogin();break;
 case 'run-audit':{
  const storeId=$('#audit-store').value,mode=$('#audit-mode').value;if(!storeId){toast('请选择店铺',true);return}
  const out=await api('/api/audits',{method:'POST',body:JSON.stringify({store_ids:[storeId],mode})});toast('审核任务已启动');await refresh();await openAudit(out.audit_ids[0]);break;
 }
 case 'run-all':{
  const mode=$('#audit-mode').value;
  const ids=S.stores.map(s=>s.id).slice(0,300);
  if(!ids.length){toast('请先添加店铺',true);return}
  if(!confirm(`将审核 ${ids.length} 家店铺，模式：${mode==='ai'?'规则+DeepSeek（可能产生API费用）':'确定性规则'}。确认开始？`))return;
  const out=await api('/api/audits',{method:'POST',body:JSON.stringify({store_ids:ids,mode})});toast(`已创建 ${out.created} 项审核任务`);await refresh();break;
 }
 }
}
async function uploadFile(input,endpoint){
 const file=input.files[0];if(!file)return;
 const fd=new FormData();fd.append('file',file);
 const response=await api(endpoint,{method:'POST',body:fd});
 input.value='';return response;
}
function setupEvents(){
 document.addEventListener('click',async e=>{
  const nav=e.target.closest('[data-page]');if(nav){navigate(nav.dataset.page);return}
  const el=e.target.closest('[data-action]');if(el){el.disabled=true;try{await handleAction(el)}catch(ex){toast(ex.message,true)}finally{if(el.isConnected)el.disabled=false}return}
  if(e.target.id==='drawer-overlay')closeDrawer();
 });
 document.addEventListener('submit',async e=>{
  if(e.target.id==='bb-onboard-form'){
    e.preventDefault();
    const b=$('#bb-save-key');b.disabled=true;$('#bb-setup-error').textContent='';
    try{await api('/api/desktop/save-api-key',{method:'POST',body:JSON.stringify({api_key:$('#bb-key').value})});
      $('#bb-key').value='';$('#bb-onboard').classList.add('hidden');await refresh();toast('DeepSeek API 已保存到本地');}
    catch(ex){$('#bb-setup-error').textContent=ex.message;}
    finally{b.disabled=false;}
    return;
  }
  if(e.target.id==='login-form'){
   e.preventDefault();const btn=e.target.querySelector('button');btn.disabled=true;
   try{await api('/api/login',{method:'POST',body:JSON.stringify({password:$('#password').value})});$('#password').value='';$('#login-error').textContent='';showApp();await refresh()}
   catch(ex){$('#login-error').textContent=ex.message}
   finally{btn.disabled=false}
  }else if(['entity-form','store-form'].includes(e.target.id)){e.preventDefault();try{if(e.target.id==='entity-form')await submitEntity();else await submitStore()}catch(ex){toast(ex.message,true)}}
 });
 document.addEventListener('input',e=>{
  if(e.target.id==='search-field'){
   S.query=e.target.value;
   const pos=e.target.selectionStart;
   render();const fresh=$('#search-field');if(fresh){fresh.focus();fresh.setSelectionRange(pos,pos)}
  }
 });
 document.addEventListener('change',async e=>{
  const input=e.target;
  try{
   if(input.id==='template-picker'){toast('正在读取 ZIP 并建立模板目录…');const v=await uploadFile(input,'/api/templates/import');await refresh();toast(v.message||`新增${v.added}个模板记录`)}
   else if(input.id==='csv-picker'){const v=await uploadFile(input,'/api/stores/import-csv');await refresh();toast(`已导入/更新 ${v.imported} 家店铺`)}
   else if(input.id==='doc-picker'){const id=input.dataset.entityId;const v=await uploadFile(input,'/api/entities/'+id+'/documents');await docDrawer(id);await refresh();toast('已保存文件：'+v.filename)}
   else if(input.dataset.issueState){await api('/api/issues/'+input.dataset.issueState,{method:'PATCH',body:JSON.stringify({state:input.value})});toast('处理状态已保存')}
  }catch(ex){toast(ex.message,true);input.value=''}
 });
 $('#mobile-menu').addEventListener('click',()=>$('.sidebar').classList.toggle('menu-open'));
 document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer()});
}
setupEvents();boot();
