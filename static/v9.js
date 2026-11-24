'use strict';
/* V9 — quiet, spacious editorial UI. All asset content remains source-backed. */
const V9={detail:null,tab:'overview',device:'desktop',busy:false,filter:'all',assetQuery:'',activeStore:''};
const V9ICON={
 grid:'<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
 file:'<path d="M7 2h7l5 5v15H7a3 3 0 0 1-3-3V5a3 3 0 0 1 3-3Z"/><path d="M14 2v6h6M9 14h6m-6 4h6"/>',
 layers:'<path d="m12 3 9 5-9 5-9-5 9-5ZM3 13l9 5 9-5M3 17l9 5 9-5"/>',
 bag:'<path d="M5 8h14l1 13H4L5 8Z"/><path d="M9 9V6a3 3 0 0 1 6 0v3"/>',
 monitor:'<rect x="2.5" y="3" width="19" height="14"/><path d="M8 21h8m-4-4v4"/>',
 chevron:'<path d="m9 18 6-6-6-6"/>',
 arrow:'<path d="M5 12h14m-7-7 7 7-7 7"/>',
 search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/>',
 shield:'<path d="M12 2 4 6v6c0 5 3 8 8 10 5-2 8-5 8-10V6l-8-4Z"/><path d="m8 12 3 3 5-5"/>',
 box:'<path d="m3 7 9-4 9 4v10l-9 4-9-4V7Z"/><path d="m3 7 9 5 9-5M12 12v9"/>',
 spark:'<path d="m12 2 2.8 7.2L22 12l-7.2 2.8L12 22l-2.8-7.2L2 12l7.2-2.8L12 2Z"/>',
 close:'<path d="M5 5 19 19M19 5 5 19"/>',
 download:'<path d="M12 3v13m-5-5 5 5 5-5M4 18v3h16v-3"/>',
 check:'<path d="m4 12 5 5 11-11"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
 laptop:'<rect x="3" y="4" width="18" height="13"/><path d="m1 21 2-4h18l2 4H1Z"/>',
 phone:'<rect x="7" y="2" width="10" height="20"/><path d="M11 18h2"/>',
 archive:'<rect x="3" y="4" width="18" height="5"/><path d="M5 9v11h14V9M10 14h4"/>'
};
function v9Icon(name,sz=20){return `<svg class="v9-icon" width="${sz}" height="${sz}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${V9ICON[name]||V9ICON.box}</svg>`}
function v9TopStats(){const st=S.v3stores?.length?S.v3stores:S.stores,counts={stores:st.length,assigned:st.filter(x=>x.entity_id).length,domains:st.filter(x=>x.domain).length,audits:S.audits.length};return counts;}
function v9Overview(){
 const c=v9TopStats(),storeList=(S.v3stores?.length?S.v3stores:S.stores),ready=storeList.filter(s=>s.entity_id&&s.domain).length;
 const rows=storeList.slice(0,300).map((s,i)=>{const state=s?.audit_status&&/通过/.test(s.audit_status)?'passed':s?.entity_id&&s?.domain?'ready':s?.entity_id?'assigned':'unassigned';return `<button class="v9-node ${state}" data-v9-store="${H(s?.id||'')}" title="${H(s?.code||'')} · ${H(s?.domain||'未绑定域名')}" aria-label="查看 ${H(s?.code)}">${String(i+1).padStart(3,'0')}</button>`}).join('');
 const samples=S.templates.slice(0,4).map(t=>`<button class="v9-asset-teaser" data-v9-asset="${H(t.id)}"><span class="v9-teaser-art">${v9Icon('monitor',24)}</span><span class="v9-teaser-copy"><b>${H(t.label.split('/').pop())}</b><small>${H(t.code)} · 12 个源文件</small></span>${v9Icon('chevron',18)}</button>`).join('');
 return `<div class="v9-page v9-home"><header class="v9-hero"><div><div class="v9-kicker">BIG BANG <span class="v9-line"></span> WORKSPACE</div><h1>让每一家店铺，<br><span>清晰可控。</span></h1><p>公司主体、现有商品与装修、域名和质量审核，集中在一个安静而高效的工作空间。</p><div class="v9-hero-actions"><button class="v9-primary" data-action="v3-start">开始单主体部署 ${v9Icon('arrow',18)}</button><button class="v9-subtle" data-action="bb-start">批量主体规划 ${v9Icon('arrow',17)}</button></div></div><div class="v9-hero-side"><span class="v9-hero-amount">${ready}<small> / 300</small></span><span class="v9-hero-caption">已完成主体与域名绑定</span><div class="v9-line-track"><i style="width:${Math.round(100*ready/300)}%"></i></div><span class="v9-hero-note">所有统计来自当前本地数据库</span></div></header>
 <section class="v9-metrics">${[[c.stores,'店铺资源','grid'],[S.entities.length,'公司主体','file'],[c.domains,'已绑定域名','monitor'],[c.audits,'审核记录','shield']].map(([num,label,ico])=>`<div class="v9-metric"><div class="v9-metric-header">${v9Icon(ico,19)}<span>${label}</span></div><div class="v9-metric-value">${num}</div></div>`).join('')}</section>
 <section class="v9-two-col"><div class="v9-white-panel v9-matrix-panel"><header class="v9-panel-head"><div><span class="v9-kicker">ASSET MONITOR</span><h2>300 家店铺状态</h2><p>每个方块都是一套完整店铺。点击即可查看商品、装修、政策与网页效果预览。</p></div><button class="v9-textlink" data-action="go-stores">查看列表 ${v9Icon('arrow',16)}</button></header><div class="v9-matrix-filters"><button class="${V9.filter==='all'?'active':''}" data-v9-filter="all">全部</button><button class="${V9.filter==='unassigned'?'active':''}" data-v9-filter="unassigned">未配置</button><button class="${V9.filter==='ready'?'active':''}" data-v9-filter="ready">已配置</button><button class="${V9.filter==='passed'?'active':''}" data-v9-filter="passed">通过审核</button><span>${c.stores} / 300</span></div><div class="v9-matrix" id="v9-matrix">${rows}</div><div class="v9-matrix-key"><span><i class="unassigned"></i>未配置</span><span><i class="assigned"></i>主体已分配</span><span><i class="ready"></i>主体与域名齐全</span><span><i class="passed"></i>历史审核通过</span></div></div>
 <aside class="v9-sidecol"><div class="v9-white-panel"><header class="v9-panel-head"><div><span class="v9-kicker">QUICK ACCESS</span><h2>你的工作流程</h2></div></header><div class="v9-shortcuts"><button data-action="v3-start">${v9Icon('file')}<span><b>单主体智能部署</b><small>上传主体与域名，生成交付文件</small></span>${v9Icon('arrow',17)}</button><button data-action="bb-start">${v9Icon('layers')}<span><b>批量主体规划</b><small>统一调整分配数量</small></span>${v9Icon('arrow',17)}</button><button data-action="go-audits">${v9Icon('shield')}<span><b>检查与复核</b><small>查看已收集的审核证据</small></span>${v9Icon('arrow',17)}</button></div></div>
 <div class="v9-white-panel"><header class="v9-panel-head"><div><span class="v9-kicker">LIBRARY</span><h2>模板速览</h2><p>打开任意店铺的完整档案</p></div></header><div class="v9-asset-teasers">${samples}</div><button class="v9-textlink" data-action="go-templates">浏览全部300套 ${v9Icon('arrow',16)}</button></div></aside></section></div>`;
}
function v9Templates(){const items=S.templates.filter(t=>(t.code+' '+t.label).toLowerCase().includes(S.query.toLowerCase()));
 return `<div class="v9-page"><header class="v9-library-header"><div><div class="v9-kicker">SOURCE LIBRARY / 300</div><h1>完整店铺资源库</h1><p>每套资源都包含对应商品CSV、4份装修 Liquid 与7份政策。原始组合保持不变。</p></div><button class="v9-primary" data-action="import-templates">导入模板 ZIP ${v9Icon('arrow',17)}</button></header>
 <section class="v9-white-panel v9-library-panel"><div class="v9-library-tools"><label>${v9Icon('search',19)}<input id="search-field" type="search" placeholder="搜索店铺、模板编号或商品品类" value="${H(S.query)}"/></label><span>${items.length} 套资源</span></div>
 <div class="v9-library-table"><div class="v9-lib-column-title"><span>店铺编号与名称</span><span>装修模块</span><span>商品数据</span><span>政策文件</span><span>操作</span></div>${items.map((t,i)=>`<button class="v9-lib-row" data-v9-asset="${H(t.id)}"><span class="v9-lib-identity"><span class="v9-lib-index">${H(t.code)}</span><strong>${H(t.label.split('/').pop())}</strong></span><span>4 个 Liquid 文件</span><span>1 份 CSV</span><span>7 份条款</span><span class="v9-open-link">查看完整档案 ${v9Icon('chevron',17)}</span></button>`).join('')||'<div class="v9-no-results">未找到符合条件的模板。</div>'}</div></section></div>`;
}
function v9Stores(){const st=(S.v3stores?.length?S.v3stores:S.stores);const items=st.filter(x=>([x.code,x.label,x.domain,x.entity_name].join(' ').toLowerCase().includes(S.query.toLowerCase())));
 return `<div class="v9-page"><header class="v9-library-header"><div><div class="v9-kicker">STORE DIRECTORY</div><h1>店铺与域名</h1><p>点击任意店铺，查看完整资产档案。主体、域名和分配关系仍通过原有编辑功能管理。</p></div><div class="v9-flex"><button class="v9-subtle" data-action="export-stores">导出 CSV</button><button class="v9-primary" data-action="add-store">新增店铺 ${v9Icon('arrow',17)}</button></div></header><section class="v9-white-panel v9-library-panel"><div class="v9-library-tools"><label>${v9Icon('search',19)}<input id="search-field" type="search" placeholder="搜索编号、域名、主体" value="${H(S.query)}"/></label><span>${items.length} 家店铺</span></div><div class="v9-library-table"><div class="v9-lib-column-title v9-stores-cols"><span>店铺</span><span>公司主体</span><span>域名</span><span>状态</span><span>操作</span></div>${items.map(s=>`<div class="v9-lib-row v9-stores-cols"><span class="v9-lib-identity"><span class="v9-lib-index">${H(s.code)}</span><strong>${H(s.label||'未命名店铺')}</strong></span><span>${H(s.entity_name||'待分配')}</span><span>${H(s.domain||'未绑定域名')}</span><span>${H(s.status||'待配置')}</span><span class="v9-row-ops"><button data-v9-store="${H(s.id)}">查看档案</button><button data-action="edit-store" data-id="${H(s.id)}">编辑</button></span></div>`).join('')||'<div class="v9-no-results">没有匹配的店铺。</div>'}</div></section></div>`;
}
function v9CleanName(s){return String(s||'').replace(/^.*\//,'')}
function v9DetailMarkup(data){const store=data.linked_store||{},title=store.code||data.template_code, sub=store.domain||data.label;
 return `<div class="v9-detail-screen" role="dialog" aria-modal="true" aria-label="完整店铺档案"><div class="v9-detail-backdrop" data-v9-close></div><section class="v9-detail"><header class="v9-detail-header"><div><div class="v9-kicker">STORE DOSSIER / ${H(title)}</div><h2>${H(data.label)}</h2><p>${H(data.template_code)} · ${H(sub)} · ${data.files.length}份真实源文件</p></div><button class="v9-icon-button" data-v9-close aria-label="关闭">${v9Icon('close',22)}</button></header>
 <nav class="v9-detail-tabs" aria-label="店铺档案栏目">${[['overview','总览'],['preview','网页效果预览'],['products','对应商品'],['theme','装修文件'],['policies','七份条款']].map(([id,label])=>`<button data-v9-tab="${id}" class="${V9.tab===id?'selected':''}">${label}</button>`).join('')}</nav>
 <main class="v9-detail-content">${v9DetailBody(data)}</main><footer class="v9-detail-footer"><span>基于源ZIP提取 · 不代表在线商店已经部署</span><a class="v9-primary v9-download" href="/studio/${encodeURIComponent(store.code||'')}" target="_self">进入 V10 店铺工作室 ${v9Icon('arrow',18)}</a><a class="v9-subtle" href="/api/templates/${encodeURIComponent(data.template_id)}/bundle.zip" download>${v9Icon('download',18)} 下载本套完整资源</a></footer></section></div>`;
}
function v9PreviewFrame(data){return `<div class="v9-preview-note">${v9Icon('info',18)} <span>此页面基于原始 Liquid 标题、图片链接和商品 CSV 重建布局示意，<b>不是 Shopify 运行时的真实截图</b>。外部图片需网络可访问，可能受授权或链接有效性影响。</span></div><div class="v9-preview-bar"><span>${v9Icon('monitor',16)} 来源素材预览</span><div><button data-v9-device="desktop" class="${V9.device==='desktop'?'active':''}" title="桌面端">${v9Icon('laptop',19)}</button><button data-v9-device="mobile" class="${V9.device==='mobile'?'active':''}" title="手机端">${v9Icon('phone',19)}</button></div></div><div class="v9-preview-stage ${V9.device}"><iframe title="源文件构图预览" loading="lazy" src="/api/v9/assets/${encodeURIComponent(data.template_id)}/preview"></iframe></div>`}
function v9DetailBody(data){
 if(V9.tab==='preview')return v9PreviewFrame(data);
 if(V9.tab==='overview')return `<div class="v9-dossier-lead"><div><span class="v9-kicker">COMPLETE ASSET SET</span><h3>一套店铺，所有内容。</h3><p>点击任意区域查看具体文件、商品信息或基于原始图片链接的页面构图预览。</p></div><div class="v9-dossier-number">${data.files.length}<small>源文件</small></div></div><div class="v9-dossier-grid"><button data-v9-tab="products">${v9Icon('bag',25)}<strong>${data.products.length} 款商品</strong><small>SKU、售价、产品图片链接</small>${v9Icon('arrow',18)}</button><button data-v9-tab="theme">${v9Icon('layers',25)}<strong>${data.theme.length} 份装修 Liquid</strong><small>Header / Homepage / Content / Footer</small>${v9Icon('arrow',18)}</button><button data-v9-tab="policies">${v9Icon('file',25)}<strong>${data.policies.length} 份政策</strong><small>隐私、配送、退款与经营主体等</small>${v9Icon('arrow',18)}</button><button data-v9-tab="preview">${v9Icon('monitor',25)}<strong>网页效果示意</strong><small>基于原始标题、布局和CDN素材</small>${v9Icon('arrow',18)}</button></div><div class="v9-dossier-info"><b>源文件档案</b><span>文件夹：${H(data.source_path)}</span><span>源ZIP：${H(data.source_zip)}</span><span>模板组：${H(data.style_group)}</span></div>`;
 if(V9.tab==='products')return `<div class="v9-detail-section-head"><h3>对应商品</h3><p>${data.products.length} 条商品主记录。使用原CSV中的真实名称、价格及图片链接，SKU仅展示部分样例。</p></div><div class="v9-products-grid">${data.products.map(x=>`<article class="v9-product"><div class="v9-product-image">${/^https:\/\/(m\.media-amazon\.com|cdn\.shopify\.com)\//.test(x.image)?`<img loading="lazy" alt="${H(x.title)}" src="${H(x.image)}" onerror="this.classList.add('v9-img-failed')">`:v9Icon('bag',24)}</div><strong>${H(x.title)}</strong><span>${x.price?H(x.price):'价格未录入'} · ${x.sku_count} SKU</span><small>${H(x.option_values.slice(0,4).join(' · '))}</small></article>`).join('')}</div>`;
 if(V9.tab==='theme')return `<div class="v9-detail-section-head"><h3>装修文件</h3><p>这四个Liquid模块来自原始ZIP，可以单独下载或下载整套。这里不编辑原文件。</p></div><div class="v9-file-list">${data.theme.map(t=>{const i=data.files.findIndex(f=>f.path===t.path);return `<details><summary>${v9Icon('layers',19)}<span><strong>${H(t.name)}</strong><small>${t.lines} 行 · Liquid</small></span>${v9Icon('chevron',16)}</summary><div class="v9-file-inside"><pre>${H(t.snippet)}</pre><a href="/api/v9/assets/${encodeURIComponent(data.template_id)}/file/${i}" download>下载原始文件</a></div></details>`}).join('')}</div>`;
 if(V9.tab==='policies')return `<div class="v9-detail-section-head"><h3>七份政策文件</h3><p>所有文件均来自原始资源，没有自动改写公司主体信息。正式发布前必须核对变量与经营规则。</p></div><div class="v9-file-list">${data.policies.map((f,k)=>{const i=data.files.findIndex(x=>x.path===f.path);return `<div class="v9-policy-line">${v9Icon('file',19)}<span><strong>${H(f.name)}</strong><small>原始政策文件 ${String(k+1).padStart(2,'0')} / 07</small></span><a href="/api/v9/assets/${encodeURIComponent(data.template_id)}/file/${i}" download>${v9Icon('download',18)} 下载</a></div>`}).join('')}</div>`;
 return '';
}
async function v9OpenAsset(id){if(!id)return;V9.busy=true;V9.tab='overview';V9.device='desktop';document.getElementById('v9-detail-root').innerHTML='<div class="v9-loading">正在读取完整店铺档案…</div>';
 try{V9.detail=await api('/api/v9/assets/'+encodeURIComponent(id));document.getElementById('v9-detail-root').innerHTML=v9DetailMarkup(V9.detail);document.body.classList.add('v9-modal-open');}
 catch(e){document.getElementById('v9-detail-root').innerHTML='';toast('无法读取店铺档案：'+e.message,true);}finally{V9.busy=false;}}
function v9Close(){document.body.classList.remove('v9-modal-open');document.getElementById('v9-detail-root').innerHTML='';V9.detail=null;}
function v9StoreToTemplate(storeId){const s=(S.v3stores?.length?S.v3stores:S.stores).find(x=>x.id===storeId);return S.templates.find(t=>t.code===s?.template_code)?.id||S.stores.find(x=>x.id===storeId)?.template_id;}
const v9OldOverview=renderOverview,v9OldTemplates=renderTemplates,v9OldStores=renderStores;
renderOverview=v9Overview;renderTemplates=v9Templates;renderStores=v9Stores;
document.body.insertAdjacentHTML('beforeend','<div id="v9-detail-root"></div>');
document.addEventListener('click',async e=>{const a=e.target.closest('[data-v9-asset],[data-v9-store],[data-v9-tab],[data-v9-device],[data-v9-close],[data-v9-filter]');if(!a)return;
 e.preventDefault();e.stopImmediatePropagation();
 if(a.hasAttribute('data-v9-close')){v9Close();return;}
 if(a.dataset.v9Filter){V9.filter=a.dataset.v9Filter;document.querySelectorAll('[data-v9-filter]').forEach(x=>x.classList.toggle('active',x.dataset.v9Filter===V9.filter));document.querySelectorAll('.v9-node').forEach(x=>{x.classList.toggle('dimmed',V9.filter!=='all'&&!x.classList.contains(V9.filter));});return;}
 if(a.dataset.v9Tab){V9.tab=a.dataset.v9Tab;if(V9.detail){const holder=document.getElementById('v9-detail-root');holder.innerHTML=v9DetailMarkup(V9.detail);}return;}
 if(a.dataset.v9Device){V9.device=a.dataset.v9Device;document.querySelector('.v9-detail-content').innerHTML=v9DetailBody(V9.detail);return;}
 const template=a.dataset.v9Asset||v9StoreToTemplate(a.dataset.v9Store);await v9OpenAsset(template);
},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&V9.detail){e.stopImmediatePropagation();v9Close();}},true);
// Replace legacy brand text & emojis in UI chrome with one consistent 24px outline icon system.
const v9SideLogo=document.querySelector('.sidebar-head .bb-symbol');if(v9SideLogo)v9SideLogo.innerHTML=v9Icon('grid',24);
const v9Version=document.querySelector('.side-vnum');if(v9Version)v9Version.textContent='V9.0';
const v9Foot=document.querySelector('.app-foot span:last-child');if(v9Foot)v9Foot.textContent='BIG BANG STUDIO · V9.0';
const v9LoginVersion=document.querySelector('.login-right-foot span');if(v9LoginVersion)v9LoginVersion.textContent='VERSION 9.0 / QUIET STUDIO';
// Replace every sidebar pictogram, including dynamically injected entries, with consistent outline SVGs.
const v9NavIcons={overview:'grid',delivery:'box',setup:'file',bulk:'layers',entities:'file',stores:'bag',templates:'layers',audits:'shield',settings:'monitor'};
document.querySelectorAll('#nav .nav-item').forEach(item=>{const target=item.querySelector('.nav-icon');const icon=v9NavIcons[item.dataset.page]||'box';if(target)target.innerHTML=v9Icon(icon,21);});
const v9MobileMenu=document.getElementById('mobile-menu');if(v9MobileMenu)v9MobileMenu.innerHTML=v9Icon('grid',20);
document.title='BIG BANG V9 · 店铺工作空间';
