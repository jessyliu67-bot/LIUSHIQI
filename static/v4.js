'use strict';
/* BIG BANG V4 visual & usability layer. Existing allocation, audit, policy and API actions stay unchanged. */
PAGE_TITLES.overview='运营总控';
PAGE_TITLES.setup='单主体部署';
PAGE_TITLES.bulk='批量主体规划';
const V4 = {filter:'all', query:'', searchOpen:false};
function v4Status(store){
 if(!store)return 'empty';
 if(store.audit_status && /通过|未发现问题/.test(store.audit_status) && !/未通过|不通过|部分/.test(store.audit_status))return 'audited';
 if(store.entity_id&&store.domain&&store.support_email)return 'configured';
 if(store.entity_id)return 'assigned';
 return 'unassigned';
}
function v4Counts(st){let r={all:st.length,unassigned:0,assigned:0,configured:0,audited:0};for(const s of st)r[v4Status(s)]++;return r;}
function v4Num(n){return Number(n??0).toLocaleString('zh-CN');}
function v4RenderOverview(){
 const d=S.v3summary||{}, st=(S.v3stores?.length?S.v3stores:S.stores)||[], counts=v4Counts(st), assigned=st.filter(x=>!!x.entity_id).length;
 const domains=st.filter(x=>!!x.domain).length, emails=st.filter(x=>!!x.support_email).length;
 const verified=st.filter(x=>v4Status(x)==='audited').length;
 const filled=st.filter(x=>x.entity_id&&x.domain&&x.support_email).length;
 const progress=Math.round(100*filled/Math.max(1,st.length));
 const items=Array.from({length:Math.max(300,st.length)},(_,i)=>{
   const s=st[i],status=v4Status(s),label=s?`${s.code} · ${s.domain||'域名待绑定'} · ${s.entity_name||'未分配主体'}`:`尚未登记 / ${i+1}`;
   const code=s?.code||`STORE-${String(i+1).padStart(3,'0')}`;
   return `<button type="button" class="v4-slot ${status}" data-v4-state="${status}" data-v4-searchable="${H([code,s?.domain,s?.entity_name,s?.support_email].filter(Boolean).join(' ').toLowerCase())}" data-action="v3-open-store" data-id="${H(s?.id||'')}" title="${H(label)}" aria-label="${H(label)}" ${!s?'disabled':''}><span>${String(i+1).padStart(3,'0')}</span></button>`;
 }).join('');
 const controls=[['all','全部',counts.all],['unassigned','未分配',counts.unassigned],['assigned','已分配',counts.assigned],['configured','已配置',counts.configured],['audited','已审核',counts.audited]].map(([key,label,n])=>`<button type="button" class="v4-segment ${V4.filter===key?'is-active':''}" data-v4-filter="${key}" aria-pressed="${V4.filter===key}">${label}<span>${n}</span></button>`).join('');
 const audits=(S.audits||[]).slice(0,4).map((a,i)=>`<button class="v4-audit-line" data-action="view-audit" data-id="${H(a.id)}"><span class="v4-audit-n">${String(i+1).padStart(2,'0')}</span><span class="v4-audit-desc"><b>${H(a.store_code||'未命名店铺')}</b><small>${H(a.domain||'域名待配置')}</small></span>${tag(a.status)}<span class="v4-arrow">↗</span></button>`).join('');
 return `<div class="v4-home">
 <section class="v4-welcome">
   <div class="v4-welcome-copy"><div class="v4-label"><span class="v4-spark"></span> BIG BANG <span class="v4-slash">/</span> 工作空间 <span class="v4-release">V8.0</span></div>
     <h1>让300家店铺，<em>有序运转。</em></h1>
     <p>主体、域名、完整模板与AI审核集中管理。先配置，再检查，所有结果清楚可追踪。</p>
     <div class="v4-welcome-actions"><button class="btn v4-solid" data-action="v3-start">新增主体并分配 <span>↗</span></button><button class="btn v4-line" data-action="bb-start">批量规划主体 <span>→</span></button></div>
   </div>
   <div class="v4-welcome-progress"><div class="v4-progress-top"><span>当前配置进度</span><b>${progress}%</b></div><div class="v4-progress-track"><span style="width:${progress}%"></span></div><strong>${filled}<span> / ${st.length} 家</span></strong><small>已填写主体、域名和独立邮箱</small><div class="v4-progress-bottom"><span><i class="v4-mini-dot"></i>${assigned} 家已关联主体</span><span>${st.length-assigned} 家待分配</span></div></div>
 </section>
 <section class="v4-stat-bar" aria-label="系统关键指标">
 <div><small>店铺资产 <span>01</span></small><strong>${v4Num(st.length)}</strong><p>已登记完整资源</p></div>
 <div><small>公司主体 <span>02</span></small><strong>${v4Num(d.entities??S.entities.length)}</strong><p>已保存主体记录</p></div>
 <div><small>域名绑定 <span>03</span></small><strong>${v4Num(domains)}</strong><p>已填写域名</p></div>
 <div><small>审核记录 <span>04</span></small><strong>${v4Num(S.audits.length)}</strong><p>${verified} 家曾通过规则检查</p></div>
 </section>
 <section class="v4-workflow-head"><div><div class="v4-label">WORKFLOW / 快速开始</div><h2>选择你的工作方式</h2></div><p>两种流程，共用同一套300家原始店铺资源，不更换已经确定的商品与装修组合。</p></section>
 <section class="v4-workflows">
   <button class="v4-flow-card" data-action="v3-start"><span class="v4-flow-icon">01</span><span class="v4-flow-inner"><b>单主体 · 智能部署</b><small>上传一家公司的资料，输入4–5个域名，预览严格差异化的随机匹配。</small><span>开始部署 <span>↗</span></span></span></button>
   <button class="v4-flow-card v4-flow-alt" data-action="bb-start"><span class="v4-flow-icon">02</span><span class="v4-flow-inner"><b>批量主体 · 集中规划</b><small>一次导入多家主体，自由调整每家公司对应的店铺数量，统一预览后保存。</small><span>进入规划 <span>↗</span></span></span></button>
 </section>
 <section class="v4-board-layout">
   <div class="v4-board-main"><div class="v4-panel v4-fleet">
     <header class="v4-panel-head"><div><div class="v4-label">FLEET / 001—300</div><h2>店铺状态矩阵 <span class="v4-count">${Math.max(300,st.length)} 个槽位</span></h2><p>每个矩形代表一个店铺。可按状态筛选，点击查看详情。</p></div><button class="v4-panel-link" data-action="go-stores">店铺列表 ↗</button></header>
     <div class="v4-board-controls"><div class="v4-segments" role="group" aria-label="按店铺状态筛选">${controls}</div><label class="v4-matrix-search"><span>⌕</span><input id="v4-matrix-search" type="search" placeholder="搜索编号 / 域名" value="${H(V4.query)}" aria-label="搜索店铺编号或域名"/></label></div>
     <div class="v4-matrix" id="v4-matrix">${items}</div>
     <div class="v4-matrix-footer"><div class="v4-key"><span><i class="unassigned"></i>未分配</span><span><i class="assigned"></i>已分配主体</span><span><i class="configured"></i>基础配置齐全</span><span><i class="audited"></i>已有通过记录</span></div><strong id="v4-visible-count">${st.length} 家可见</strong></div>
   </div>
   <div class="v4-panel v4-review"><header class="v4-panel-head"><div><div class="v4-label">AUDIT / 任务记录</div><h2>最近审核</h2><p>问题从检测到复核，保留完整追踪。</p></div><button class="v4-panel-link" data-action="go-audits">审核中心 ↗</button></header><div class="v4-audits">${audits||'<div class="v4-no-data"><b>还没有审核任务</b><span>为店铺完成域名绑定后，可运行真实网站检查。</span><button class="btn v4-line" data-action="go-audits">打开审核中心 ↗</button></div>'}</div></div></div>
   <aside class="v4-board-aside">
     <div class="v4-panel v4-next"><div class="v4-label">NEXT / 待处理事项</div><h2>下一步行动</h2><p>优先解决阻碍店铺上线的配置问题。</p><button data-action="go-entities"><span class="v4-task-number">01</span><span><b>公司主体管理</b><small>${d.entities??S.entities.length} 份主体资料已保存</small></span><i>↗</i></button><button data-action="go-stores"><span class="v4-task-number">02</span><span><b>域名与独立邮箱</b><small>${st.length-domains} 家缺域名 · ${st.length-emails} 家缺邮箱</small></span><i>↗</i></button><button data-action="go-audits"><span class="v4-task-number">03</span><span><b>启动网站审核</b><small>验证已上线页面的真实内容</small></span><i>↗</i></button></div>
     <div class="v4-panel v4-integrity"><div class="v4-label">ENVIRONMENT / 运行状态</div><h3>系统状态</h3><div><span>本地数据库</span><b><i></i>已连接</b></div><div><span>原始资源</span><b>${v4Num(d.templates??S.templates.length)} 套</b></div><div><span>DeepSeek API</span><b>${S.me?.deepseek_connected?'已配置':'未配置'}</b></div><p>AI审核和邮箱建议不等于官方核验或邮箱开通。</p></div>
   </aside>
 </section></div>`;
}
renderOverview = v4RenderOverview;
const v4PreviousRender=render;
render=function(){const output=v4PreviousRender();if(S.page==='overview')queueMicrotask(v4ApplyFilter);return output;};
function v4ApplyFilter(){
 const input=document.getElementById('v4-matrix-search');if(input)V4.query=input.value;
 const q=V4.query.trim().toLowerCase();let visible=0;
 for(const item of document.querySelectorAll('#v4-matrix .v4-slot')){
   const matchesStatus=V4.filter==='all'||item.dataset.v4State===V4.filter;
   const matchesQuery=!q||item.dataset.v4Searchable.includes(q);
   const matched=matchesStatus&&matchesQuery&&item.dataset.v4State!=='empty';
   item.classList.toggle('is-dimmed',!matched);if(matched)visible++;
 }
 document.querySelectorAll('[data-v4-filter]').forEach(btn=>{let selected=btn.dataset.v4Filter===V4.filter;btn.classList.toggle('is-active',selected);btn.setAttribute('aria-pressed',String(selected))});
 const target=document.getElementById('v4-visible-count');if(target)target.textContent=`${visible} 家匹配`;
}
// Global search is an overlay only; existing CRUD functions and access control are reused.
function v4SearchItems(query){
 const q=query.trim().toLowerCase();if(!q)return[];
 const storeItems=(S.v3stores?.length?S.v3stores:S.stores).filter(x=>[x.code,x.domain,x.entity_name,x.support_email].join(' ').toLowerCase().includes(q)).slice(0,7).map(x=>({kind:'店铺',title:x.code,detail:x.domain||'域名待填写',page:'stores',query:x.code}));
 const entityItems=S.entities.filter(x=>[x.code,x.name,x.registration_no].join(' ').toLowerCase().includes(q)).slice(0,3).map(x=>({kind:'主体',title:x.name,detail:x.registration_no||x.code,page:'entities',query:x.name}));
 return [...storeItems,...entityItems].slice(0,8);
}
function v4OpenSearch(){
 if(document.getElementById('v4-palette'))return;
 document.body.insertAdjacentHTML('beforeend',`<div id="v4-palette" class="v4-palette-backdrop"><section class="v4-palette" role="dialog" aria-modal="true" aria-label="全局搜索"><div class="v4-palette-input"><span>⌕</span><input id="v4-global-input" placeholder="搜索店铺编号、域名、公司主体…" autocomplete="off"/><button data-v4-close aria-label="关闭搜索">ESC</button></div><div id="v4-palette-results" class="v4-palette-results"><div class="v4-palette-hint">输入关键词，快速定位300家店铺或公司主体。</div></div><footer>BIG BANG · 快速定位</footer></section></div>`);
 document.getElementById('v4-global-input').focus();V4.searchOpen=true;
}
function v4CloseSearch(){document.getElementById('v4-palette')?.remove();V4.searchOpen=false;}
function v4UpdateSearch(q){
 const items=v4SearchItems(q);const results=document.getElementById('v4-palette-results');if(!results)return;
 results.innerHTML=!q.trim()?'<div class="v4-palette-hint">输入关键词，快速定位300家店铺或公司主体。</div>':items.length?items.map((x,i)=>`<button class="v4-palette-result" data-v4-target="${x.page}" data-v4-query="${H(x.query)}"><span>${x.kind}</span><b>${H(x.title)}</b><small>${H(x.detail)}</small><i>↗</i></button>`).join(''):'<div class="v4-palette-hint">没有找到匹配的店铺或主体。</div>';
}
// Capture phase prevents dashboard controls from entering old generic action handlers.
document.addEventListener('click',e=>{
 const filter=e.target.closest('[data-v4-filter]');if(filter){e.preventDefault();e.stopImmediatePropagation();V4.filter=filter.dataset.v4Filter;v4ApplyFilter();return;}
 if(e.target.closest('#v4-launch-search')){e.preventDefault();e.stopImmediatePropagation();v4OpenSearch();return;}
 if(e.target.closest('[data-v4-close]')||e.target.id==='v4-palette'){e.preventDefault();e.stopImmediatePropagation();v4CloseSearch();return;}
 const target=e.target.closest('[data-v4-target]');if(target){e.preventDefault();e.stopImmediatePropagation();const page=target.dataset.v4Target,query=target.dataset.v4Query;v4CloseSearch();navigate(page);S.query=query;render();const searchField=document.getElementById('search-field');if(searchField)searchField.value=query;return;}
},true);
document.addEventListener('input',e=>{if(e.target.id==='v4-matrix-search')v4ApplyFilter();if(e.target.id==='v4-global-input')v4UpdateSearch(e.target.value);},true);
document.addEventListener('keydown',e=>{
 if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();if(V4.searchOpen)v4CloseSearch();else v4OpenSearch();}
 if(e.key==='Escape'&&V4.searchOpen){e.preventDefault();v4CloseSearch();}
});
const v4Nav=document.getElementById('nav');
if(v4Nav){
 const overview=v4Nav.querySelector('[data-page="overview"]'),setup=v4Nav.querySelector('[data-page="setup"]'),bulk=v4Nav.querySelector('[data-page="bulk"]');
 if(overview&&setup&&bulk)v4Nav.prepend(overview,setup,bulk);
 v4Nav.setAttribute('aria-label','管理导航');
}
const v4Sidebar=document.querySelector('.sidebar');
if(v4Sidebar){const info=document.createElement('div');info.className='v4-sidebar-note';info.innerHTML='<span class="v4-sidebar-note-mark"></span><div><b>300套原始资源已保留</b><small>模板与商品组合不自动更改</small></div>';v4Sidebar.insertBefore(info,v4Sidebar.querySelector('.sidebar-bottom'));}
const v4Top=document.querySelector('.top-right');
if(v4Top){const command=document.createElement('button');command.id='v4-launch-search';command.className='v4-search-trigger';command.type='button';command.innerHTML='<span>⌕</span> 搜索店铺 / 主体 <kbd>Ctrl K</kbd>';v4Top.prepend(command);}
const v4Ver=document.querySelector('.side-vnum');if(v4Ver)v4Ver.textContent='V4.0';
const v4Foot=document.querySelector('.app-foot span:last-child');if(v4Foot)v4Foot.textContent='LOCAL CONTROL · V4.0';
const v4Login=document.querySelector('.login-right-foot span');if(v4Login)v4Login.textContent='VERSION 4.0 / DESIGN REFINED';
document.title='大爆炸 · BIG BANG V4.0 | 智能店铺控制台';
