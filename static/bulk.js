'use strict';
// V3.2 bulk entity planner: runs alongside the single-entity V3.1 wizard.
PAGE_TITLES.bulk='批量主体规划';
const B={batchId:'',rows:[],result:null,stage:1,busy:false,opened:new Set(),inventory:null,filter:'',viewAll:false};
function bulkTotals(){const a=B.rows.filter(x=>x.included);return {subjects:a.length,stores:a.reduce((n,x)=>n+(Number(x.count)||0),0),domains:a.reduce((n,x)=>n+(x.domains||'').split(/[\s,，;；]+/).filter(Boolean).length,0)};}
function bulkRowData(r){return {draft_id:r.draft_id,included:r.included,fields:r.fields,count:Number(r.count)||0,domains:r.domains||''};}
function bulkStats(){const total=bulkTotals();const available=B.inventory?.available??S.v3summary?.unassigned??300;const scarce=B.inventory?.special??'—';const mustUseSpecial=B.rows.filter(r=>r.included).reduce((v,r)=>v+Math.max(0,r.count-1),0);
 return `<div class="bb-bulk-stats"><div><span>已选择主体</span><strong>${total.subjects}</strong><small>份公司资料</small></div><div><span>计划店铺</span><strong>${total.stores}</strong><small>待配置完整资源</small></div><div><span>可用资源</span><strong>${available}</strong><small>未分配店铺</small></div><div><span>差异化结构需求</span><strong>${mustUseSpecial}<small> / ${scarce}</small></strong><small>至少需要 / 当前可用的非标准Hero资源</small></div></div>`}
function bulkPage(){const stage=B.stage;const stats=bulkStats();const top=`<div class="v3-pagehead bb-bulk-head"><div><span class="v3-overline">BIG BANG / MULTI-ENTITY ORCHESTRATION</span><h1>批量主体规划</h1><p>一次导入多家主体，调整每家分配数量；确认前不占用300套原始模板。</p></div><button class="btn v3-outline" data-action="bb-go-single">单主体智能部署 ↗</button></div>`;
 const steps=`<div class="bb-bulk-steps"><span class="${stage>=1?'active':''}">01 批量导入</span><span class="${stage>=2?'active':''}">02 调整分配</span><span class="${stage>=3?'active':''}">03 预览核对</span></div>`;
 if(stage===1)return `${top}${steps}${stats}<div class="bb-bulk-upload"><div class="bb-upload-main"><span class="bb-eye">BATCH INTAKE</span><h2>一次导入所有公司主体</h2><p>直接选TXT、Word、PDF或公司图片，也可以上传包含多家独立TXT的主体ZIP；也支持主体 CSV 名单。上传后先展示识别结果，不会自动建立正式主体。</p><button class="btn btn-dark bb-cta" data-action="bb-upload">＋ 选择主体文件（支持多选）</button><div class="bb-bulk-tiny">TXT / DOCX / PDF / PNG / JPG / ZIP / CSV · 单批最多150个主体 · 文件默认仅在本地识别</div></div><div class="bb-upload-side"><span class="bb-eye">SMART WORKFLOW / 03 STEPS</span><div><b>01</b><span>上传一批公司文件，提取已能识别的名称、登记号、注册地址</span></div><div><b>02</b><span>按行确认主体信息，自由调整分配店铺数量及域名</span></div><div><b>03</b><span>自动差异化挑选完整店铺组合，预览全部结果后再确认</span></div><p>仅提取文档文字不等于官方登记核验，识别不了的字段需要你核对。</p></div></div><div class="bb-bulk-shortcut"><strong>已有CSV主体名单？</strong><span>支持表头：company_name、registration_no、country、address、phone、email、store_count、domains。没有域名也可先规划数量。</span><button class="btn v3-outline" data-action="bb-example">下载导入CSV示例 ↗</button></div>`;
 if(stage===2){const filtered=B.rows.map((r,i)=>({r,i})).filter(({r})=>!B.filter||JSON.stringify(r.fields).toLowerCase().includes(B.filter.toLowerCase())||r.filename.toLowerCase().includes(B.filter.toLowerCase()));
 return `${top}${steps}${stats}<div class="bb-bulk-toolbar"><div><span class="bb-eye">ALLOCATION WORKSPACE</span><h2>调整每个主体的店铺数量</h2><p>${B.rows.length}份资料已导入。可以逐条修改，所有更改会进入最终确认页。</p></div><div class="bb-toolbar-actions"><button class="btn v3-outline" data-action="bb-suggest">智能建议数量</button><button class="btn v3-outline" data-action="bb-add-count">全部 +1</button><button class="btn v3-outline" data-action="bb-less-count">全部 −1</button><button class="btn v3-outline" data-action="bb-reset">重新上传</button></div></div><div class="bb-bulk-filter"><input class="input" id="bb-filter" value="${H(B.filter)}" placeholder="搜索公司名称 / 文件名"/><span>数量可设0–8家；0表示仅登记主体，不分配店铺</span></div><div class="bb-bulk-tablewrap"><table class="bb-bulk-table"><thead><tr><th><input id="bb-select-all" type="checkbox" ${B.rows.every(x=>x.included)?'checked':''} aria-label="全选主体"/></th><th>公司主体</th><th>识别来源</th><th>分配数量</th><th>域名</th><th>配置</th></tr></thead><tbody>${filtered.map(({r,i})=>{
 const n=(r.domains||'').split(/[\s,，;；]+/).filter(Boolean).length;
 return `<tr class="${r.included?'':'bb-muted'}"><td><input type="checkbox" data-bb-field="included" data-bb-index="${i}" ${r.included?'checked':''}/></td><td><strong>${H(r.fields.name||'需确认法定名称')}</strong><small>${H(r.fields.registration_no||'登记编号待填写')}</small>${r.warning?`<small class="bb-note">${H(r.warning)}</small>`:''}</td><td><span>${H(r.filename||'文件')}</span><small>${H(r.method||'—')}</small></td><td><div class="bb-counter"><button data-action="bb-minus" data-index="${i}" aria-label="减少数量">−</button><input type="number" min="0" max="8" step="1" value="${r.count}" data-bb-field="count" data-bb-index="${i}"/><button data-action="bb-plus" data-index="${i}" aria-label="增加数量">+</button></div></td><td><span>${n} / ${r.count} 个</span><small>${n?'已填写部分或全部域名':'可在此先留空'}</small></td><td><button class="bb-inline" data-action="bb-toggle" data-index="${i}">${B.opened.has(i)?'收起':'编辑资料 / 域名'} →</button></td></tr>${B.opened.has(i)?`<tr><td colspan="6"><div class="bb-row-expand"><div class="bb-edit-grid">${[['name','法定公司名称'],['registration_no','注册编号 / EIN（若有）'],['country','国家 / 地区'],['address','注册地址'],['phone','主体通用客服电话 *'],['email','公司邮箱']].map(([key,label])=>`<label><span>${label}</span><input class="input" data-bb-field="${key}" data-bb-index="${i}" value="${H(r.fields[key]||'')}" placeholder="按真实文件确认"/></label>`).join('')}</div><label class="bb-domain-entry"><span>此主体对应域名（每行一个，最多${r.count}个；可暂时不填）</span><textarea data-bb-field="domains" data-bb-index="${i}" rows="3" placeholder="store-a.com&#10;store-b.com">${H(r.domains||'')}</textarea></label><p>每家店铺建议使用不同的 service@对应域名 邮箱，生成地址不代表真实邮箱已开通。</p></div></td></tr>`:''}`}).join('')}</tbody></table>${!filtered.length?'<p class="bb-empty">没有匹配的主体。</p>':''}</div><div class="bb-bulk-actions"><span>可先不填域名，后续在「店铺与域名」里补充。</span><button class="btn btn-dark bb-cta" data-action="bb-preview">分析资源并生成预览 →</button></div>`;}
 const res=B.result||{};const warnings=res.warnings||[];const errors=res.errors||[];
 return `${top}${steps}${stats}<div class="bb-preview-head"><div><span class="bb-eye">ALLOCATION SIMULATION</span><h2>${res.can_commit?'已生成完整预览':'严格规则不允许当前分配'}</h2><p>${res.can_commit?'仅预览，没有更改任何店铺；每个主体内商品大类、装修结构均做差异检查。':'请调整数量或检查主体资料，重新生成预览。系统不会自动降低不相似条件。'}</p></div><div class="bb-toolbar-actions"><button class="btn v3-outline" data-action="bb-back">← 返回调整</button>${res.can_commit?`<button class="btn v3-outline" data-action="bb-reroll">重新随机预览</button><button class="btn v3-outline" data-action="bb-export-plan">导出方案CSV</button>`:''}</div></div>${errors.map(x=>`<div class="bb-error">${H(x)}</div>`).join('')}${warnings.length?`<details class="bb-warnings"><summary>配置提醒（${warnings.length}项）</summary>${warnings.slice(0,18).map(x=>`<p>${H(x)}</p>`).join('')}${warnings.length>18?`<p>其余${warnings.length-18}项未展开</p>`:''}</details>`:''}${res.can_commit?`<div class="bb-result-grid">${res.items.map((e,i)=>`<div class="bb-result"><div class="bb-result-head"><div><small>ENTITY ${String(i+1).padStart(2,'0')}</small><h3>${H(e.entity.name)}</h3></div><strong>${e.count}<small> 家店铺</small></strong></div>${e.items.map(it=>`<div class="bb-match-line"><b>${H(it.store_code)}</b><span>${H(it.category)} · ${H(it.style_name)}</span><small>${H(it.domain||'域名待配置')}</small></div>`).join('')||'<p>仅创建主体，未分配店铺</p>'}</div>`).join('')}</div><label class="bb-bulk-consent"><input id="bb-accept" type="checkbox"/> 我已经核对主体信息、各主体分配数量与域名，理解邮箱仍需开通，主体证明仍需真实性核验。</label><div class="bb-bulk-actions"><span>方案有效期40分钟；提交时会重新验证剩余资源和域名占用情况。</span><button class="btn btn-dark bb-cta" data-action="bb-commit">确认并批量保存 →</button></div>`:`<div class="bb-bulk-actions"><button class="btn btn-dark" data-action="bb-back">返回修改数量</button></div>`}`;
}
const _bulkRefresh=refresh;
refresh=async function(){await _bulkRefresh();try{B.inventory=await api('/api/v3/bulk/inventory')}catch(err){}if(S.page==='bulk')render();};
const _bulkRender=render;
render=function(){if(S.page==='bulk'){$('#content').innerHTML=bulkPage();return;}return _bulkRender();};
const _bulkActions=handleAction;
handleAction=async function(t){const a=t.dataset.action;
 if(a==='bb-go-single'){navigate('delivery');return}
 if(a==='bb-start'){navigate('bulk');return}
 if(a==='bb-upload'){$('#bb-upload-input').click();return}
 if(a==='bb-reset'){B.batchId='';B.rows=[];B.result=null;B.stage=1;B.opened.clear();render();return}
 if(a==='bb-back'){B.stage=2;B.result=null;render();return}
 if(a==='bb-toggle'){const i=Number(t.dataset.index);B.opened.has(i)?B.opened.delete(i):B.opened.add(i);render();return}
 if(a==='bb-plus'||a==='bb-minus'){const r=B.rows[Number(t.dataset.index)];r.count=Math.min(8,Math.max(0,r.count+(a==='bb-plus'?1:-1)));B.result=null;render();return}
 if(a==='bb-suggest'){
   const selected=B.rows.filter(x=>x.included);
   if(!selected.length){toast('请先选择主体',true);return}
   const slots=Math.min(B.inventory?.available??300,selected.length*5);
   let additional=Math.max(0,Math.min((B.inventory?.special??105),slots-selected.length));
   for(const r of selected)r.count=1;
   let index=0;
   while(additional>0&&selected.some(x=>x.count<5)){
     const r=selected[index%selected.length];if(r.count<5){r.count++;additional--}index++;
   }
   for(const r of selected){const domainCount=(r.domains||'').split(/[\s,，;；]+/).filter(Boolean).length;r.count=Math.max(r.count,Math.min(8,domainCount))}
   B.result=null;render();toast('已按可用资源给出保守数量建议；实际仍以严格预览校验为准');return;
 }
 if(a==='bb-add-count'||a==='bb-less-count'){for(const r of B.rows)if(r.included)r.count=Math.min(8,Math.max(0,r.count+(a==='bb-add-count'?1:-1)));B.result=null;render();return}
 if(a==='bb-example'){const csv='company_name,registration_no,country,address,phone,email,store_count,domains\r\nExample Company A LLC,123456,United States,,,,4,"store-a.example.com;store-b.example.com"\r\nExample Company B Ltd,789012,United Kingdom,,,,3,""\r\n';const blob=new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const dl=document.createElement('a');dl.href=url;dl.download='BIG_BANG_Bulk_Entities_Example.csv';dl.click();setTimeout(()=>URL.revokeObjectURL(url),300);return}
 if(a==='bb-export-plan'){
   if(!B.result?.can_commit){toast('请先获得有效预览',true);return}
   const data=[['legal_company','registration_no','store_code','template_code','category','style','domain','support_email']];
   for(const e of B.result.items){if(!e.items.length)data.push([e.entity.name,e.entity.registration_no,'','','','','','']);
    for(const x of e.items)data.push([e.entity.name,e.entity.registration_no,x.store_code,x.template_code,x.category,x.style_name,x.domain,x.support_email])}
   const safe=v=>{let s=String(v??'');if(/^[=+@-]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"'};
   const content='\ufeff'+data.map(x=>x.map(safe).join(',')).join('\r\n');
   const url=URL.createObjectURL(new Blob([content],{type:'text/csv;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='BIG_BANG_Batch_Allocation_Preview.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),300);return;
 }
 if(a==='bb-reroll'||a==='bb-preview'){
  if(!B.batchId){toast('请先上传主体资料',true);return}
  const rows=B.rows.map(bulkRowData);
  const res=await api('/api/v3/bulk/preview',{method:'POST',body:JSON.stringify({batch_id:B.batchId,rows})});
  B.result=res;B.stage=3;render();window.scrollTo({top:0,behavior:'smooth'});if(!res.can_commit)toast('当前规划有约束或资料问题，请返回调整',true);return;
 }
 if(a==='bb-commit'){
  if(!B.result?.can_commit||!B.result.proposal_id){toast('请先生成有效预览',true);return}
  if(!$('#bb-accept')?.checked){toast('请先核对并确认提交',true);return}
  const result=await api('/api/v3/bulk/commit',{method:'POST',body:JSON.stringify({proposal_id:B.result.proposal_id})});
  B.batchId='';B.rows=[];B.result=null;B.stage=1;B.opened.clear();await refresh();navigate('delivery');toast('已保存 '+result.entity_count+' 个主体和 '+result.store_count+' 家店铺；可在最近交付记录中导出各主体的完整ZIP');return;
 }
 return _bulkActions(t);
};
$('#bb-upload-input').addEventListener('change',async e=>{
 const files=Array.from(e.target.files||[]);if(!files.length)return;
 const form=new FormData();for(const f of files)form.append('files',f);
 toast('正在读取TXT、Word及其他主体资料…');
 try{const result=await api('/api/v3/bulk/intake',{method:'POST',body:form});B.batchId=result.batch_id;B.rows=result.items;B.result=null;B.stage=2;B.opened.clear();render();toast(`已识别 ${result.count} 家主体（可逐行展开核对），确认数量后点击预览`)}catch(ex){toast(ex.message,true)}finally{e.target.value=''}
});
document.addEventListener('input',e=>{
 const el=e.target,i=Number(el.dataset.bbIndex);if(el.id==='bb-filter'){B.filter=el.value;const pos=el.selectionStart;render();const fresh=$('#bb-filter');if(fresh){fresh.focus();fresh.setSelectionRange(pos,pos)}return}
 if(!Number.isInteger(i)||!B.rows[i]||!el.dataset.bbField)return;
 const r=B.rows[i];const key=el.dataset.bbField;
 if(key==='domains'){r.domains=el.value;B.result=null;return}
 if(key==='count'){r.count=Math.min(8,Math.max(0,Number(el.value)||0));B.result=null;return}
 if(key in r.fields){r.fields[key]=el.value;B.result=null}
});
document.addEventListener('change',e=>{
 const el=e.target;
 if(el.id==='bb-select-all'){for(const r of B.rows)r.included=el.checked;B.result=null;render();return}
 if(el.dataset.bbField==='included'){
  B.rows[Number(el.dataset.bbIndex)].included=el.checked;B.result=null;render();return;
 }
 if(el.dataset.bbField==='count'){render();return}
 if(el.id==='bb-filter'){render();return}
});
// One additional top-level navigation choice, keeping the rest of V3.1 intact.
const bulkNav=document.querySelector('#nav');if(bulkNav)bulkNav.insertAdjacentHTML('afterbegin',`<button class="nav-item bb-bulk-nav" data-page="bulk"><span class="nav-icon">▦</span><span class="nav-label"><b>批量主体规划</b><small>BATCH PLANNER</small></span><span class="nav-arrow">↗</span></button>`);
const bulkBrand=document.querySelector('.side-vnum');if(bulkBrand)bulkBrand.textContent='V3.2';
const bulkFooter=document.querySelector('.app-foot span:last-child');if(bulkFooter)bulkFooter.textContent='LOCAL WORKSPACE · V3.2';
const bulkLogin=document.querySelector('.login-right-foot span');if(bulkLogin)bulkLogin.textContent='VERSION 3.2 / BATCH PLANNING';
