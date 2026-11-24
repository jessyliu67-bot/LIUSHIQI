'use strict';
// BIG BANG V3: progressive enhancement of the working V2.1 backend.
PAGE_TITLES.setup='主体智能部署';
const W={mode:'auto',autoDomains:'',autoEmailPrefix:'service',autoResult:null,step:1,entityId:'',draftId:'',filename:'',extractMethod:'',extractNote:'',duplicate:[],entity:{name:'',registration_no:'',country:'',address:'',phone:'',email:''},capacity:10,selected:new Set(),rows:{},plan:null,selectionQuery:'',aiConsent:false};
S.v3stores=[];S.v3summary=null;S.deployments=[];S.focusStore=null;
const oldRefresh=refresh;
refresh=async function(){
  await oldRefresh();
  const [v3stores, v3summary, deployments]=await Promise.all([
    api('/api/v3/stores'),api('/api/v3/summary'),api('/api/v3/deployments')]);
  S.v3stores=v3stores;S.v3summary=v3summary;S.deployments=deployments;render();
};
const originalRender=render;
render=function(){
  if(S.page==='setup'){$('#content').innerHTML=renderWizard();return}
  originalRender();
};
const btn=(text,action,cls='btn')=>`<button class="${cls}" data-action="${action}">${text}</button>`;
const val=v=>H(v||'');
const stepNames=['识别主体','确认资料','选择店铺','域名与邮箱','预览与提交'];
function startWizard(entityId=''){
 Object.assign(W,{mode:'auto',autoDomains:'',autoEmailPrefix:'service',autoResult:null,step:1,entityId:entityId||'',draftId:'',filename:'',extractMethod:'',extractNote:'',duplicate:[],entity:{name:'',registration_no:'',country:'',address:'',phone:'',email:''},capacity:10,selected:new Set(),rows:{},plan:null,selectionQuery:'',aiConsent:false});
 if(entityId){const e=lookup(S.entities,entityId);if(e){W.entity={name:e.name||'',registration_no:e.registration_no||'',country:e.country||'',address:e.address||'',phone:e.phone||'',email:e.email||''};W.capacity=e.capacity||10;}}
 navigate('setup');
}
function renderOverview(){
 const d=S.v3summary||{};const st=S.v3stores.length?S.v3stores:S.stores;
 const bound=st.filter(s=>s.entity_id&&s.domain&&s.support_email).length;
 const dots=Array.from({length:300},(_,i)=>{
   const s=st[i];const status=s?(s.audit_status&&/完成|未发现/.test(s.audit_status)?'audited':s.domain&&s.support_email&&s.entity_id?'configured':s.entity_id?'assigned':'unassigned'):'empty';
   return `<button type="button" class="v3-slot ${status}" data-action="v3-open-store" data-id="${H(s?.id||'')}" ${s?'':'disabled'} title="${s?H(s.code+' · '+(s.domain||'未绑定域名')+' · '+(s.support_email||'邮箱待填写')):'预留'}"><span>${s?H(s.code.replace('STORE-','')):''}</span></button>`
 }).join('');
 const recent=(S.audits||[]).slice(0,5).map(a=>`<div class="v3-activity"><b>${H(a.store_code)}</b><span>${H(a.domain||'尚未上线')}</span>${tag(a.status)}<button class="v3-text-action" data-action="view-audit" data-id="${H(a.id)}">查看 →</button></div>`).join('');
 return `<div class="v3-home">
 <section class="v3-masterhead"><div><div class="v3-kicker"><i></i> BIG BANG / CONTROL SYSTEM <span>VERSION 3.2</span></div><h1>300家店铺，<br><em>一个控制中心。</em></h1><p>公司主体、店铺域名、独立邮箱与合规审核，在一个工作流里完成。</p><div class="v3-masteractions">${btn('＋ 单主体智能部署','v3-start','btn btn-dark v3-primary')}${btn('批量主体规划 →','bb-start','btn v3-outline')}</div></div><div class="v3-masterpanel"><small>STORE NETWORK · LIVE</small><strong>${d.stores??S.stores.length}<span> / 300</span></strong><div class="v3-track"><span style="width:${Math.min(100,((d.assigned||0)/(d.stores||1))*100)}%"></span></div><div class="v3-masterpanel-sub"><span>${d.assigned||0} 家已分配主体</span><span>${d.unassigned??0} 家待分配</span></div></div></section>
 <section class="v3-kpis"><div><small>公司主体</small><strong>${d.entities??S.entities.length}</strong><span>登记主体数量</span></div><div><small>已绑定域名</small><strong>${d.domains??0}</strong><span>独立站域名</span></div><div><small>独立客服邮箱</small><strong>${d.emails??0}</strong><span>已保存 · 待实际验证</span></div><div><small>完整基础配置</small><strong>${bound}</strong><span>主体 + 域名 + 邮箱</span></div></section>
 <section class="v3-dashboard-body"><div class="v3-primary-column"><div class="v3-section"><header><div><span class="v3-overline">STORE ASSET MATRIX</span><h2>300店铺总览</h2><p>点击任意编号，即可查看绑定关系与客服信息。原始商品及装修不变。</p></div><div class="v3-matrix-count">${d.stores??300}<small> / 300</small></div></header><div class="v3-matrix">${dots}</div><div class="v3-legend"><span><i class="unassigned"></i>未分配</span><span><i class="assigned"></i>已分配主体</span><span><i class="configured"></i>已填写域名与邮箱</span><span><i class="audited"></i>已完成规则检查</span></div></div>
 <div class="v3-section"><header><div><span class="v3-overline">AUDIT ACTIVITY</span><h2>最新审核</h2></div>${btn('全部记录 ↗','go-audits','btn v3-outline')}</header>${recent||'<div class="v3-empty">还没有审核记录。请先配置主体和域名，再运行实际网站检查。</div>'}</div></div>
 <aside class="v3-side-column"><div class="v3-section v3-next"><span class="v3-overline">QUICK START / 智能部署</span><h2>下一步做什么？</h2><p>不用反复切换页面，按顺序完成主体和店铺配置。</p><div class="v3-next-list"><button data-action="v3-start"><b>01</b><span><strong>上传主体证明</strong><small>自动提取登记名称与地址</small></span><i>↗</i></button><button data-action="v3-start"><b>02</b><span><strong>一键分配店铺</strong><small>${d.unassigned??0} 家尚未分配主体</small></span><i>↗</i></button><button data-action="go-stores"><b>03</b><span><strong>独立域名与邮箱</strong><small>${d.without_email??0} 家未配置邮箱</small></span><i>↗</i></button><button data-action="go-audits"><b>04</b><span><strong>启动AI审核</strong><small>检查已上线的真实网页</small></span><i>↗</i></button></div>${btn('开始一次完整部署 →','v3-start','btn btn-dark v3-primary full')}</div>
 <div class="v3-section v3-integrity"><div class="v3-overline">SYSTEM INTEGRITY</div><h2>系统连接</h2><div><span>本地数据</span><b class="v3-green">正常</b></div><div><span>已入库模板</span><b>${d.templates??300} 套</b></div><div><span>DeepSeek API</span><b>${S.me?.deepseek_connected?'已配置':'未配置'}</b></div><p>当前为本地管理版；邮件生成建议不等于邮箱已开通，内部审核不等于官方认证。</p></div></aside></section></div>`;
}
function renderEntities(){
 const items=S.entities.filter(e=>!S.query||[e.code,e.name,e.registration_no,e.country].join(' ').toLowerCase().includes(S.query.toLowerCase()));
 return `<div class="v3-pagehead"><div><span class="v3-overline">LEGAL ENTITY RECORDS</span><h1>公司主体</h1><p>上传文件自动识别，关联现有店铺，减少重复填写。</p></div>${btn('＋ 智能创建主体','v3-start','btn btn-dark')}</div>
 <div class="v3-actionbar"><input class="input" id="search-field" placeholder="搜索公司名称 / 登记编号 / 国家" value="${H(S.query)}"/><div>${btn('手动录入主体','add-entity','btn v3-outline')}${btn('查看店铺分配','go-stores','btn v3-outline')}</div></div>
 <div class="v3-section v3-table-shell"><table class="v3-table"><thead><tr><th>主体编号</th><th>法定公司名称</th><th>登记号</th><th>已分配店铺</th><th>资料状态</th><th>快捷操作</th></tr></thead><tbody>${items.map(e=>`<tr><td class="v3-mono">${H(e.code)}</td><td><b>${H(e.name)}</b><small>${H(e.country||'国家待填写')}</small></td><td class="v3-mono">${H(e.registration_no||'—')}</td><td><b>${e.assigned}</b> / ${e.capacity||'不限'}</td><td>${tag(e.status)}</td><td><button class="v3-text-action" data-action="v3-start-existing" data-id="${H(e.id)}">分配店铺 ↗</button><button class="v3-text-action" data-action="edit-entity" data-id="${H(e.id)}">编辑</button></td></tr>`).join('')}</tbody></table>${items.length?'':'<div class="v3-empty">尚无主体。点击“智能创建主体”开始上传公司文件。</div>'}</div>`;
}
function renderStores(){
 const all=S.v3stores||[];
 const selected=all.filter(s=>!S.query||[s.code,s.domain,s.entity_name,s.support_email,s.template_code].join(' ').toLowerCase().includes(S.query.toLowerCase()));
 return `<div class="v3-pagehead"><div><span class="v3-overline">STORE REGISTRY / 001—300</span><h1>店铺与域名</h1><p>每家店铺对应自己的域名与客服邮箱。原有模板与商品一律保留。</p></div>${btn('批量分配主体 →','v3-start','btn btn-dark')}</div><div class="v3-actionbar"><input class="input" id="search-field" value="${H(S.query)}" placeholder="输入编号、域名、主体或邮箱"/><div>${btn('导出CSV','export-stores','btn v3-outline')}${btn('导入店铺CSV','import-csv','btn v3-outline')}</div></div>
 <div class="v3-section v3-table-shell"><div class="v3-table-summary">找到 <strong>${selected.length}</strong> 家店铺 <span>· 独立邮箱只存储配置，实际开通需另行验证</span></div><div class="v3-scrolltable"><table class="v3-table"><thead><tr><th>店铺</th><th>原模板</th><th>对应主体</th><th>域名</th><th>独立客服邮箱</th><th>状态</th><th></th></tr></thead><tbody>${selected.map(s=>`<tr><td class="v3-mono">${H(s.code)}</td><td class="v3-mono">${H(s.template_code||'—')}</td><td>${H(s.entity_name||'未分配')}</td><td>${H(s.domain||'待填写')}</td><td>${s.support_email?`<b>${H(s.support_email)}</b><small>待验证可用性</small>`:'<span class="v3-muted">尚未填写</span>'}</td><td>${tag(s.status)}</td><td><button class="v3-text-action" data-action="v3-open-store" data-id="${H(s.id)}">查看 ↗</button></td></tr>`).join('')}</tbody></table></div></div>`;
}
function resetRows(){for(const id of W.selected){if(!W.rows[id]){const s=lookup(S.v3stores,id)||{};W.rows[id]={domain:s.domain||'',support_email:s.support_email||''}}}}
function formInput(field,label,placeholder='',extra=''){
 return `<label class="v3-formfield"><span>${label}</span><input class="input" data-w-entity="${field}" value="${H(W.entity[field])}" placeholder="${H(placeholder)}" ${extra}/></label>`
}
function renderWizard(){
 const titles=W.mode==='auto'?['识别主体','确认资料','填写4–5个域名','查看差异化匹配','最终确认']:stepNames;
 const steps=titles.map((t,i)=>`<button class="v3-step ${W.step===i+1?'current':W.step>i+1?'done':''}" data-action="v3-jump" data-step="${i+1}" ${i+1>W.step?'disabled':''}><small>0${i+1}</small><span>${t}</span></button>`).join('');
 let body='';
 if(W.step===1){body=`<div class="v3-mode-tabs"><button type="button" data-action="v3-mode-auto" class="${W.mode==='auto'?'chosen':''}"><strong>智能随机分配</strong><small>上传一个主体 + 4–5个域名，自动挑选不同装修和品类</small></button><button type="button" data-action="v3-mode-manual" class="${W.mode==='manual'?'chosen':''}"><strong>使用原有固定组合</strong><small>选择已登记的STORE编号，不重新匹配商品和装修</small></button></div><div class="v3-intake-grid"><div><div class="v3-subheading">上传你的公司资料</div><p>支持营业执照、公司登记证明、EIN信函。系统提取信息，但不会自动判定其真实有效。</p><div class="v3-upload" data-action="v3-pick-file" role="button" tabindex="0"><span class="v3-upload-icon">↥</span><strong>${W.filename?H(W.filename):'点击上传主体证明文件'}</strong><small>TXT / PDF / JPG / PNG · 最大12MB · 文件保存在本机</small><span class="v3-upload-button">选择文件 →</span></div><label class="v3-consent"><input type="checkbox" id="v3-ai-consent" ${W.aiConsent?'checked':''}/>允许将主体文件的首张图像发送给 DeepSeek 进行识别（涉及公司证件，仅在勾选后发送）</label>${W.extractNote?`<div class="v3-warning">${H(W.extractNote)}</div>`:''}</div><div class="v3-note-panel"><div class="v3-overline">SMART INTAKE</div><h3>文件上传后自动做什么？</h3><div class="v3-noteline"><b>01</b><span>识别主体名称、注册编号、国家与注册地址</span></div><div class="v3-noteline"><b>02</b><span>查询是否与现有主体重复</span></div><div class="v3-noteline"><b>03</b><span>进入统一确认与分配流程</span></div><div class="v3-note-bottom">也可以不上传文件，直接手工填写主体信息。</div><div class="v3-note-bottom">已有主体可直接进入批量分配，无需再次上传。</div></div></div>`;
 }else if(W.step===2){const existing=W.entityId?lookup(S.entities,W.entityId):null;
 body=`<div class="v3-two-cols"><div><div class="v3-subheading">确认主体信息</div><p>${existing?'使用系统中已登记的主体，不会重复创建。':'请根据证件原文核对识别结果，字段缺失时手动补充。'}</p><div class="v3-entity-fields">${formInput('name','法定公司名称 *','Registered Company Name',existing?'readonly':'')}${formInput('registration_no','登记号 / EIN','Registration Number',existing?'readonly':'')}${formInput('country','注册国家 / 地区','Country',existing?'readonly':'')}${formInput('address','实际注册地址','Full Registered Address',existing?'readonly':'')}${formInput('phone','客服电话（如已确认）','+1 ...',existing?'readonly':'')}${formInput('email','主体官方邮箱（可不填）','info@company.com',existing?'readonly':'')}</div></div><aside class="v3-note-panel"><div class="v3-overline">ENTITY VERIFICATION</div><h3>${existing?'已选择现有主体':'识别结果待人工确认'}</h3><div class="v3-note-bottom">${H(W.extractMethod||'手动填写 · 未运行文件识别')}</div><div class="v3-note-bottom">即使AI正确提取了名称，也不等于已核验营业执照真实性。</div>${W.duplicate.length?`<div class="v3-warning">发现相似的现有主体：${W.duplicate.map(x=>H(x.code+' · '+x.name)).join('，')}。请避免重复创建。</div>`:''}</aside></div>`;
 }else if(W.step===3 && W.mode==='auto'){
 body=`<div class="v3-auto-grid"><div><div class="v3-subheading">填写4–5个店铺域名</div><p>每行一个域名。系统会从你已有的300套完整店铺中随机选择；每个域名绑定一套不重复的装修结构和商品大类。</p><label class="v3-formfield"><span>本次域名清单（4–5个）</span><textarea id="v3-auto-domains" class="input v3-domains" rows="8" placeholder="store-a.com\nstore-b.com\nstore-c.com\nstore-d.com">${H(W.autoDomains)}</textarea></label><label class="v3-formfield"><span>每店独立邮箱前缀（仅生成建议，不开通邮箱）</span><select id="v3-auto-email-prefix" class="input"><option value="service" ${W.autoEmailPrefix==='service'?'selected':''}>service@店铺域名</option><option value="support" ${W.autoEmailPrefix==='support'?'selected':''}>support@店铺域名</option><option value="help" ${W.autoEmailPrefix==='help'?'selected':''}>help@店铺域名</option></select></label></div><div class="v3-note-panel"><div class="v3-overline">STRICT DIFFERENTIATION</div><h3>自动匹配的四道硬约束</h3><div class="v3-noteline"><b>01</b><span>装修结构类型不相同</span></div><div class="v3-noteline"><b>02</b><span>20组装修编号不重复</span></div><div class="v3-noteline"><b>03</b><span>商品品类不重复</span></div><div class="v3-noteline"><b>04</b><span>相近商品大类也不能共用</span></div><div class="v3-note-bottom">例如T恤和Polo衫都归为“上装”；连帽卫衣和圆领卫衣都归为“卫衣”。无法找到足够不相似的组合时，会提示你而不是降低标准。</div></div></div>`;
 }else if(W.step===3){const list=S.v3stores.filter(s=>(!s.entity_id||s.entity_id===W.entityId)&&(!W.selectionQuery||[s.code,s.template_code,s.label,s.domain].join(' ').toLowerCase().includes(W.selectionQuery.toLowerCase())));
 body=`<div class="v3-subheading">选择需要分配的店铺</div><p>只显示尚未分配或已经属于当前主体的店铺。你原来确定好的模板和商品不改变。</p><div class="v3-assign-tools"><label>计划管理数量 <input class="input" id="v3-capacity" type="number" min="1" max="300" value="${W.capacity}"/></label>${btn('自动选择未分配店铺','v3-auto-select','btn btn-dark')}${btn('清空选择','v3-clear-select','btn v3-outline')}<b>${W.selected.size} 家已选</b></div><div class="v3-search-row"><input id="v3-store-filter" class="input" placeholder="搜索店铺编号或模板" value="${H(W.selectionQuery)}"/></div><div class="v3-picker-grid">${list.map(s=>`<label class="v3-pick-item ${W.selected.has(s.id)?'picked':''}"><input type="checkbox" data-w-select="${H(s.id)}" ${W.selected.has(s.id)?'checked':''}/><b>${H(s.code)}</b><span>${H(s.template_code||'—')}</span>${s.entity_id?'<em>已绑定本主体</em>':''}</label>`).join('')}</div><div class="v3-help">已选择 ${W.selected.size} 家 · 先按编号选取，提交前可以逐家编辑域名和邮箱。</div>`;
 }else if(W.step===4 && W.mode==='auto'){
  const a=W.autoResult||{};
  body=`<div class="v3-preview-head"><div><div class="v3-subheading">差异化随机匹配结果</div><p>以下全部来自现有300套固定商品＋装修组合。不拆分，不改动。可以重新随机生成，满意后再保存。</p></div><span class="v3-preview-good">${a.items?.length||0} 家符合严格约束</span></div><div class="v3-match-table"><div class="v3-match-head"><span>域名 / 客服邮箱</span><span>预分配店铺</span><span>装修结构</span><span>商品品类 / 大类</span></div>${(a.items||[]).map(x=>`<div class="v3-match-row"><div><b>${H(x.domain)}</b><small>${H(x.support_email)}</small></div><div><b>${H(x.store_code)}</b><small>${H(x.template_code)} · ${H(x.template_group)}</small></div><div><b>${H(x.style_name)}</b><small>${H(x.style_family)}</small></div><div><b>${H(x.category)}</b><small>${H(x.product_family)}</small></div></div>`).join('')}</div><div class="v3-match-footer"><div>所有候选资源均未分配，且商品大类与装修结构在本主体范围内不重复。代码结构差异并不替代上线后的视觉审核。</div><button type="button" class="btn v3-outline" data-action="v3-reroll">↻ 重新随机匹配</button></div>`;
 }else if(W.step===4){resetRows();const selected=S.v3stores.filter(s=>W.selected.has(s.id));
 body=`<div class="v3-subheading">为每家店铺单独配置域名和邮箱</div><p>系统会根据域名建议 <b>service@对应域名</b>，但不会假装这个邮箱已经开通。每家店铺使用独立配置。</p><div class="v3-edittoolbar">${btn('为已有域名生成邮箱建议','v3-email-suggest','btn btn-dark')}<span>${selected.length} 家店铺</span></div><details class="v3-import-details"><summary>批量粘贴：店铺编号、域名、邮箱</summary><p>每行支持逗号或Tab分隔，例如 <code>STORE-001,example.com,service@example.com</code>。不会自动变更没有选中的店铺。</p><textarea id="v3-paste" rows="4" placeholder="STORE-001,store-a.com,service@store-a.com"></textarea>${btn('应用粘贴内容','v3-import-paste','btn v3-outline')}</details><div class="v3-contact-table"><div class="v3-contact-head"><span>店铺编号</span><span>店铺域名</span><span>独立客服邮箱</span><span>状态</span></div>${selected.map(s=>{const rw=W.rows[s.id];return `<div class="v3-contact-row"><b>${H(s.code)}</b><input class="input" data-w-domain="${H(s.id)}" placeholder="store-domain.com" value="${H(rw.domain)}"/><input class="input" data-w-email="${H(s.id)}" placeholder="service@store-domain.com" value="${H(rw.support_email)}"/><small>${rw.domain&&rw.support_email?'待验证':'待配置'}</small></div>`}).join('')}</div>`;
 }else if(W.step===5){const p=W.plan||{};const selected=p.items||[];const policies=p.policy_sample?.policies||[];
 body=`<div class="v3-preview-head"><div><div class="v3-subheading">最终配置确认</div><p>即将写入 ${selected.length} 家店铺的主体关系、域名与独立邮箱。不会改动已有商品和装修文件。</p></div>${p.errors?.length?`<div class="v3-preview-bad">${p.errors.length} 项阻止提交</div>`:'<div class="v3-preview-good">通过数据冲突检查</div>'}</div>${p.errors?.length?`<div class="v3-warning"><b>必须修复：</b>${p.errors.map(v=>`<div>· ${H(v)}</div>`).join('')}</div>`:''}${p.warnings?.length?`<details class="v3-warnings" open><summary>需要关注：${p.warnings.length} 项</summary>${p.warnings.slice(0,15).map(v=>`<p>· ${H(v)}</p>`).join('')}${p.warnings.length>15?`<p>另有 ${p.warnings.length-15} 项</p>`:''}</details>`:''}<div class="v3-final-list"><div><b>经营主体</b><span>${H(p.entity?.name||'—')}</span></div><div><b>分配数量</b><span>${selected.length} 家</span></div><div><b>独立邮箱</b><span>${selected.filter(x=>x.support_email).length} 家已填写，实际有效性待验证</span></div><div><b>已设置域名</b><span>${selected.filter(x=>x.domain).length} 家</span></div><div><b>审核状态</b><span>待人工核验与上线检查</span></div></div><div class="v3-policy-head"><div class="v3-subheading">七份政策变量预览</div><p>提取你已有模板的原始条款，不改写承诺和业务规则；只替换已确认的主体变量。</p></div>${W.mode==='auto'?`<div class="v3-auto-checks"><b>严格分配检查</b><span>装修结构、商品品类、商品大类、已有主体归属及域名冲突均已复核；原始300套资源不改动。</span></div>`:''}${policies.length?`<div class="v3-policies">${policies.map(x=>`<details><summary>${H(x.filename)} <small>${x.unresolved.length?`未填 ${x.unresolved.length} 项`:'变量已填充'}</small></summary><pre>${H(x.preview)}</pre>${x.unresolved.length?`<div class="v3-warning">仍未填写：${H(x.unresolved.join(' / '))}</div>`:''}</details>`).join('')}</div>`:`<div class="v3-warning">${H(p.policy_sample?.warning||'暂无政策预览')}</div>`}<label class="v3-confirm"><input type="checkbox" id="v3-confirm-box"/> 我已核对实际主体与分配关系，理解邮箱、政策和公司真实性仍需进一步核验。</label>`;
 }
 const footer=`<div class="v3-wizard-footer"><div class="v3-wizard-footnote">${W.step===5?'保存后可继续导出七份政策，并对已上线网站进行审核。':`第 ${W.step} / 5 步 · 数据仅在最终提交后写入店铺配置`}</div><div>${W.step>1?btn('← 上一步','v3-prev','btn v3-outline'):btn('返回总览','go-overview','btn v3-outline')}${W.step===5?btn('确认并保存配置 →','v3-commit','btn btn-dark'):btn('继续下一步 →','v3-next','btn btn-dark')}</div></div>`;
 return `<div class="v3-wizard"><div class="v3-pagehead"><div><span class="v3-overline">SMART DEPLOYMENT WIZARD</span><h1>智能主体部署</h1><p>${W.mode==='auto'?'上传主体 → 4–5个域名 → 随机挑选差异化组合 → 预览并保存。':'主体信息 → 选择已有店铺 → 独立邮箱 → 政策预览并保存。'}</p></div>${btn('退出向导 ×','go-overview','btn v3-outline')}</div><div class="v3-stepper">${steps}</div><div class="v3-wizard-card">${body}</div>${footer}</div>`;
}
async function wizardPlan(){
 resetRows();const entity=W.entityId?lookup(S.entities,W.entityId):W.entity;
 const items=Array.from(W.selected).map(store_id=>({store_id,domain:W.rows[store_id]?.domain||'',support_email:W.rows[store_id]?.support_email||''}));
 return api('/api/v3/deploy/plan',{method:'POST',body:JSON.stringify({entity_id:W.entityId||null,intake_draft_id:W.draftId||null,entity,capacity:W.capacity,items})});
}
async function generateAutoPreview(){
 const domains=W.autoDomains.split(/[\r\n,，;；]+/).map(v=>v.trim()).filter(Boolean);
 if(domains.length<4||domains.length>5){toast('请填写4或5个域名，每行一个',true);return false}
 const entity=W.entityId?lookup(S.entities,W.entityId):W.entity;
 const response=await api('/api/v3/auto/preview',{method:'POST',body:JSON.stringify({entity_id:W.entityId||null,intake_draft_id:W.draftId||null,entity,domains,email_prefix:W.autoEmailPrefix})});
 W.autoResult=response;W.plan=response.plan;return true;
}
async function wizardNext(){
 if(W.step===3 && W.mode==='auto'){if(await generateAutoPreview()){W.step=4;render()}return}
 if(W.step===4 && W.mode==='auto'){W.step=5;render();return}
 if(W.step===2 && !W.entityId && W.entity.name.trim().length<2){toast('请先确认完整的法定公司名称',true);return}
 if(W.step===3){if(!W.selected.size){toast('请至少选择一家店铺',true);return};if(W.capacity && W.selected.size>W.capacity&&!W.entityId){toast('选中店铺数不能超过计划管理数量',true);return}}
 if(W.step===4){W.plan=await wizardPlan();W.step=5;render();return}
 W.step=Math.min(5,W.step+1);render();
}
async function confirmDeployment(){
 if(!W.plan?.can_commit){toast('存在重复或格式问题，请返回修改后再提交',true);return}
 if(!$('#v3-confirm-box')?.checked){toast('请先确认信息真实性与后续审核责任',true);return}
 const entity=W.entityId?lookup(S.entities,W.entityId):W.entity;
 const items=Array.from(W.selected).map(store_id=>({store_id,domain:W.rows[store_id]?.domain||'',support_email:W.rows[store_id]?.support_email||''}));
 const result= W.mode==='auto'
   ? await api('/api/v3/auto/commit',{method:'POST',body:JSON.stringify({proposal_id:W.autoResult?.proposal_id})})
   : await api('/api/v3/deploy/commit',{method:'POST',body:JSON.stringify({entity_id:W.entityId||null,intake_draft_id:W.draftId||null,entity,capacity:W.capacity,items})});
 await refresh();navigate('stores');toast('已保存 '+result.assigned+' 家店铺，政策需复核，邮箱需实际开通');
}
async function openV3Store(id){
 const s=lookup(S.v3stores,id);if(!s)return;
 S.focusStore=id;
 let pol=null;
 if(s.entity_id){try{pol=await api('/api/v3/stores/'+id+'/policies')}catch(e){pol={warning:e.message,policies:[]}}}
 const body=`<div class="v3-store-panel"><div class="v3-subheading">${H(s.code)} <span>· ${H(s.template_code||'—')}</span></div><p>原始模板与商品资料保留，不会在此修改。</p><div class="v3-final-list"><div><b>归属公司</b><span>${H(s.entity_name||'未分配')}</span></div><div><b>网站域名</b><span>${H(s.domain||'未配置')}</span></div><div><b>管理状态</b><span>${H(s.status)}</span></div></div><label class="v3-formfield"><span>独立客服邮箱</span><input class="input" id="v3-store-email" type="email" value="${H(s.support_email)}" placeholder="service@your-store.com"/></label><div class="v3-help">此处仅保存邮箱配置，不会为你注册邮箱或验证收件能力。</div><div class="v3-section"><h3>七份政策</h3><p>已配置主体和完整联系信息后，可导出替换变量的独立政策包。</p>${pol?.policies?.length?pol.policies.map(x=>`<div class="v3-inline-policy">${H(x.filename)} <small>${x.unresolved.length?'待补 '+x.unresolved.length:'预览可用'}</small></div>`).join(''):`<div class="v3-warning">${H(pol?.warning||'需要先分配公司主体')}</div>`}<button class="btn btn-dark full" data-action="v3-policy-export" data-id="${H(id)}">导出七份政策ZIP →</button></div></div>`;
 showDrawer('STORE DETAILS',s.code+' / 店铺配置',body,`<button class="btn v3-outline" data-action="close-drawer">取消</button><button class="btn btn-dark" data-action="v3-email-save" data-id="${H(id)}">保存邮箱</button>`);
}
const oldHandleAction=handleAction;
handleAction=async function(t){
 const a=t.dataset.action;
 if(a==='v3-mode-auto'){W.mode='auto';W.plan=null;W.autoResult=null;render();return}
 if(a==='v3-mode-manual'){W.mode='manual';W.plan=null;W.autoResult=null;render();return}
 if(a==='v3-reroll'){if(await generateAutoPreview())render();toast('已重新随机匹配，旧结果不会自动保存');return}
 if(a==='v3-start'){startWizard();return}
 if(a==='v3-start-existing'){startWizard(t.dataset.id);W.step=2;render();return}
 if(a==='go-overview'){navigate('overview');return}
 if(a==='v3-pick-file'){$('#v3-intake-input').click();return}
 if(a==='v3-next'){await wizardNext();return}
 if(a==='v3-prev'){W.step=Math.max(1,W.step-1);render();return}
 if(a==='v3-jump'){W.step=Math.min(W.step,Number(t.dataset.step));render();return}
 if(a==='v3-auto-select'){
  const desired=Number($('#v3-capacity')?.value||10);
  if(desired<1||desired>300){toast('请输入1到300的店铺数量',true);return}
  W.capacity=desired;
  const pool=S.v3stores.filter(s=>!s.entity_id||s.entity_id===W.entityId);
  W.selected=new Set(pool.slice(0,desired).map(s=>s.id));resetRows();render();return;
 }
 if(a==='v3-clear-select'){W.selected.clear();render();return}
 if(a==='v3-email-suggest'){
  resetRows();for(const id of W.selected){const r=W.rows[id];if(r.domain&&!r.support_email){r.support_email='service@'+r.domain.replace(/^https?:\/\//,'').replace(/\/$/,'').toLowerCase()}}
  render();toast('已生成建议地址，邮箱需实际开通与验证');return;
 }
 if(a==='v3-import-paste'){
   const input=$('#v3-paste').value.trim();const lines=input.split(/\n+/).map(s=>s.trim()).filter(Boolean);
   let applied=0,ignored=0;
   for(const line of lines){const p=line.includes('\t')?line.split('\t'):line.split(',');const code=(p[0]||'').trim().toUpperCase();const s=S.v3stores.find(x=>x.code===code);
    if(!s||!W.selected.has(s.id)||p.length<2){ignored++;continue}
    W.rows[s.id]={domain:(p[1]||'').trim(),support_email:(p[2]||'').trim()};applied++;
   }render();toast(`已应用 ${applied} 条；忽略 ${ignored} 条`);return;
 }
 if(a==='v3-commit'){await confirmDeployment();return}
 if(a==='v3-open-store'){await openV3Store(t.dataset.id);return}
 if(a==='v3-email-save'){
  const v=$('#v3-store-email').value;
  await api('/api/v3/stores/'+t.dataset.id+'/contact',{method:'PUT',body:JSON.stringify({support_email:v})});closeDrawer();await refresh();toast('邮箱信息已保存；仍需验证真实可用性');return;
 }
 if(a==='v3-policy-export'){window.location.href='/api/v3/stores/'+encodeURIComponent(t.dataset.id)+'/policies/export.zip';return}
 return oldHandleAction(t);
};
// Keep wizard state without navigating away or losing the current field focus.
document.addEventListener('input',e=>{
 const t=e.target;
 if(t.dataset.wEntity){W.entity[t.dataset.wEntity]=t.value;return}
 if(t.dataset.wDomain){W.rows[t.dataset.wDomain]??={domain:'',support_email:''};W.rows[t.dataset.wDomain].domain=t.value;return}
 if(t.dataset.wEmail){W.rows[t.dataset.wEmail]??={domain:'',support_email:''};W.rows[t.dataset.wEmail].support_email=t.value;return}
 if(t.id==='v3-capacity')W.capacity=Number(t.value)||0;
 if(t.id==='v3-auto-domains')W.autoDomains=t.value;
 if(t.id==='v3-store-filter'){W.selectionQuery=t.value;const pos=t.selectionStart;render();const fresh=$('#v3-store-filter');if(fresh){fresh.focus();fresh.setSelectionRange(pos,pos)}}
});
document.addEventListener('change',e=>{
 const t=e.target;
 if(t.dataset.wSelect){if(t.checked)W.selected.add(t.dataset.wSelect);else W.selected.delete(t.dataset.wSelect);resetRows();const n=document.querySelector('.v3-assign-tools b');if(n)n.textContent=W.selected.size+' 家已选';t.closest('.v3-pick-item')?.classList.toggle('picked',t.checked);return}
 if(t.id==='v3-ai-consent')W.aiConsent=t.checked;
 if(t.id==='v3-auto-email-prefix')W.autoEmailPrefix=t.value;
});
$('#v3-intake-input').addEventListener('change',async e=>{
 const file=e.target.files[0];if(!file)return;
 const fd=new FormData();fd.append('file',file);toast('正在本地识别主体文件…');
 try{
   const result=await api('/api/v3/intake/extract'+(W.aiConsent?'?use_ai=true':''),{method:'POST',body:fd});
   W.draftId=result.draft_id;W.filename=result.filename;W.extractMethod=result.method;W.extractNote=result.warning;W.duplicate=result.duplicates||[];
   W.entity={...W.entity,...result.fields};W.step=2;render();toast('识别完成。请对照原始文件核对全部字段。');
 }catch(ex){toast(ex.message,true)}finally{e.target.value=''}
});
// Insert a prominent quick start without changing V2.1 auth or navigation logic.
const nav=document.querySelector('#nav');
if(nav){nav.insertAdjacentHTML('afterbegin',`<button class="nav-item v3-quick-nav" data-page="setup"><span class="nav-icon">＋</span><span class="nav-label"><b>智能部署向导</b><small>QUICK SETUP</small></span><span class="nav-arrow">↗</span></button>`)}
const brand=document.querySelector('.side-vnum');if(brand)brand.textContent='V3.2';
const footerVersion=document.querySelector('.app-foot span:last-child');if(footerVersion)footerVersion.textContent='LOCAL WORKSPACE · V3.1';
const loginVersion=document.querySelector('.login-right-foot span');if(loginVersion)loginVersion.textContent='VERSION 3.2 / AUTO MATCHING';
