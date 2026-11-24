'use strict';
/* BIG BANG V7 — real audit gates, 5-store source comparison, repeatable releases.
   Core deployment logic is retained. No unapproved changes to Shopify stores. */
const V7={comparison:null,gate:null,versions:[],diffs:null,loadingVisual:false,loadingGate:false,
  busy:false,activePanel:'issues',showDiffs:false,currentBatch:'',fingerprintKey:''};
function v7Esc(x){return H(String(x??''))}
function v7StoreCodes(){return (V5.proposal?.items||V5.batch?.stores||[]).map(x=>x.store_code)}
function v7ResetUi(){V7.comparison=null;V7.gate=null;V7.versions=[];V7.diffs=null;V7.currentBatch='';V7.showDiffs=false;V7.loadingGate=false;V7.loadingVisual=false;}
async function v7LoadVisual(){
 const codes=v7StoreCodes();if(!codes.length){V7.comparison=null;return;}
 const key=codes.join('|');V7.fingerprintKey=key;V7.loadingVisual=true;render();
 try {const result=await api('/api/v7/visual/compare',{method:'POST',body:JSON.stringify({store_codes:codes})});
   if(V7.fingerprintKey===key)V7.comparison=result;
 }catch(e){console.warn('Visual comparison unavailable',e);if(V7.fingerprintKey===key)V7.comparison={error:e.message,items:[]};}
 finally{V7.loadingVisual=false;if(S.page==='delivery')render();}
}
async function v7LoadGate(){
 if(!V5.batch?.id)return;
 const id=V5.batch.id;V7.currentBatch=id;V7.loadingGate=true;
 try{const [gate,versions]=await Promise.all([
   api('/api/v7/deployments/'+encodeURIComponent(id)+'/gate'),
   api('/api/v7/deployments/'+encodeURIComponent(id)+'/versions')
 ]);
  if(V7.currentBatch===id){V7.gate=gate;V7.versions=versions;}
 }catch(e){if(V7.currentBatch===id)V7.gate={error:e.message,allowed:false,blockers:[],counts:{}};}
 finally{V7.loadingGate=false;if(S.page==='delivery')render();}
}
const v7PrevMakePreview=v5MakePreview;
v5MakePreview=async function(...args){V7.comparison=null;V7.fingerprintKey='';await v7PrevMakePreview(...args);if(V5.proposal)await v7LoadVisual();};
const v7PrevConfirm=v5Confirm;
v5Confirm=async function(...args){await v7PrevConfirm(...args);if(V5.batch){await Promise.all([v7LoadGate(),v7LoadVisual()]);}};
const v7PrevLoadBatch=v5LoadBatch;
v5LoadBatch=async function(...args){await v7PrevLoadBatch(...args);if(V5.batch){await Promise.all([v7LoadGate(),v7LoadVisual()]);}};
const v7PrevSaveEntity=v5SaveEntity;
v5SaveEntity=async function(...args){await v7PrevSaveEntity(...args);if(V5.batch)await v7LoadGate();};
const v7PrevSaveFix=v5SaveFix;
v5SaveFix=async function(...args){await v7PrevSaveFix(...args);if(V5.batch)await v7LoadGate();};
const v7PrevReset=v5Reset;
v5Reset=function(...args){const r=v7PrevReset(...args);v7ResetUi();return r;};
function v7CompareHtml(){
 if(V7.loadingVisual)return '<section class="v7-module"><div class="v7-title"><b>五店铺差异对比</b><small>正在读取真实模板结构…</small></div></section>';
 if(!V7.comparison||V7.comparison.error)return `<section class="v7-module"><div class="v7-title"><b>五店铺差异对比</b><small>${v7Esc(V7.comparison?.error||'匹配后可查看')}</small></div></section>`;
 const result=V7.comparison;
 return `<section class="v7-module v7-comparison"><div class="v7-title"><div><span class="v7-tag">V7 / SOURCE-BASED REVIEW</span><h3>五店铺差异对比墙</h3><p>每张卡来自原始 Liquid 代码的布局分类及图片引用。不是实际 Shopify 网页截图。</p></div><span class="v7-pill ${result.strict_structure_pass?'positive':'negative'}">${result.strict_structure_pass?'结构与商品大类不重复':'发现相似风险'}</span></div>
 <div class="v7-tile-grid">${result.items.map((x,i)=>`<article class="v7-tile" data-style="${v7Esc(x.style_family)}">
 <div class="v7-thumb ${v7Esc(x.style_family)}">
   ${x.hero_image_source?`<img loading="lazy" alt="${v7Esc(x.template_code)} 原始Liquid引用图片" src="${v7Esc(x.hero_image_source)}">`:''}
   <div class="v7-thumb-copy"><span>0${i+1} / ${v7Esc(x.template_group)}</span><strong>${v7Esc(x.style_name)}</strong></div>
   <span class="v7-origin">素材引用 · 未验证图片可用性</span>
 </div><div class="v7-tile-meta"><b>${v7Esc(x.domain||x.store_code)}</b><span>${v7Esc(x.category)} · ${v7Esc(x.product_family)}</span><small>${v7Esc(x.store_code)} / ${v7Esc(x.template_code)}</small></div></article>`).join('')}</div>
 ${result.diversity_warnings.length?`<div class="v7-risk">${result.diversity_warnings.map(v7Esc).join('；')}</div>`:'<div class="v7-ok-note">严格结构比对未发现同一主体下重复的布局类型或商品大类。最终视觉仍须人工查看真实网站。</div>'}
 <details class="v7-source-detail"><summary>查看判断依据</summary><div>${result.items.map(x=>`<p><b>${v7Esc(x.store_code)}</b>：${v7Esc(x.style_family)} / ${v7Esc(x.product_family)} · <small>${v7Esc(x.source_file)}</small></p>`).join('')}</div></details></section>`;
}
function v7IssueGuide(issue){
 const code=issue.code||'';
 if(code==='ENTITY_PREFLIGHT'||code==='CONTACT_MISSING'||code==='FOOTER_FIELD_MISSING')return '补全并确认主体通用电话、公司英文名称与注册地址，再重新检查。';
 if(code==='CHINESE_IN_CONTENT'||code==='UNRESOLVED_FIELD'||code==='POLICY_UNRESOLVED'||code==='FOOTER_UNRESOLVED')return '查看源文件与导出版本的差异；若是缺少真实资料，不能让AI凭空补充。';
 if(code==='FILE_COUNT_MISMATCH')return '原始文件夹结构不完整，需要修复来源资产后重新运行，不应生成假文件。';
 if(code==='SAME_ENTITY_SIMILAR_STORE')return '请在重新分配流程选择其它未占用的完整组合，不得跨模板拼接商品。';
 return '打开具体文件和审核证据，核实后重新执行规则审核。';
}
function v7GateHtml(){
 const g=V7.gate;
 if(V7.loadingGate&&!g)return `<section class="v7-module"><h3>交付质检门禁</h3><p>正在重新检查本批次的原始资产与导出内容…</p></section>`;
 if(!g)return `<section class="v7-module"><h3>交付质检门禁</h3><p>正在准备审核记录…</p><button class="btn v5-outline" data-v7-action="refresh-gate">刷新</button></section>`;
 if(g.error)return `<section class="v7-module"><h3>质检未完成</h3><p>${v7Esc(g.error)}</p><button class="btn v5-outline" data-v7-action="refresh-gate">重新检测</button></section>`;
 const errors=g.blockers||[];const counts=g.counts||{};
 return `<section class="v7-module v7-release">
 <div class="v7-title"><div><span class="v7-tag">DELIVERY CONTROL / QUALITY GATE</span><h3>正式交付质检</h3><p>每次导出前重新检查，不使用过期的“审核通过”标签。</p></div><span class="v7-pill ${g.allowed?'positive':'negative'}">${g.allowed?'规则检查通过':'正式导出已拦截'}</span></div>
 <div class="v7-metrics"><div><strong>${g.total_files||0}</strong><span>文件总数</span></div><div><strong>${counts.error||0}</strong><span>阻断项</span></div><div><strong>${counts.warning||0}</strong><span>待核验</span></div></div>
 ${errors.length?`<div class="v7-issues">${errors.slice(0,8).map(i=>`<div class="v7-issue"><span class="v7-issue-icon">!</span><div><b>${v7Esc(i.code)} ${v7Esc(i.store_code||'')}</b><p>${v7Esc(i.message)}</p><small>${v7Esc(v7IssueGuide(i))}</small></div></div>`).join('')}${errors.length>8?`<small>另有${errors.length-8}项，请下载完整质检报告。</small>`:''}</div>`:'<p class="v7-ok-note">未发现离线硬性阻断项。主体真实性、邮箱收件能力、图片授权和线上功能仍需要单独核验。</p>'}
 <div class="v7-actions">
 ${errors.some(i=>['ENTITY_PREFLIGHT','CONTACT_MISSING','FOOTER_FIELD_MISSING'].includes(i.code))?'<button class="btn v5-outline" data-v7-action="focus-entity">定位缺失的主体资料</button>':''}
 <button class="btn v5-outline" data-v7-action="refresh-gate">重新质检</button><button class="btn v5-outline" data-v7-action="ai-review">${S.me?.deepseek_connected?'运行 DeepSeek 语义复核':'AI复核（需配置API Key）'}</button>
 <button class="btn v5-outline" data-v7-action="show-diffs">查看自动替换差异</button><button class="btn v5-outline" data-v7-action="report">导出质检报告</button><button class="btn v7-primary" data-v7-action="prepare" ${!g.allowed?'disabled':''}>${g.allowed?'生成正式ZIP并保存版本':'修复阻断项后导出'}</button></div>
 <p class="v7-ai-status">AI状态：${v7Esc(V5.review?.ai_status||'尚未运行语义审核')}。模型建议不能替代实际公司资料或法律审核。</p>
 ${V7.showDiffs?v7DiffHtml():''}
 </section>`;
}
function v7DiffHtml(){
 if(!V7.diffs)return '<div class="v7-diff-box">正在检查原文件与导出文件的差异…</div>';
 if(V7.diffs.error)return `<div class="v7-diff-box">${v7Esc(V7.diffs.error)}</div>`;
 const all=V7.diffs.items||[];
 return `<div class="v7-diff-box"><h4>有依据的字段替换明细</h4><p>对比原始模板和当前生成版本，不代表已对公司资料真实性进行独立验证。</p>${all.length?all.slice(0,25).map(d=>`<details><summary><b>${v7Esc(d.store_code)}</b> · ${v7Esc(d.file)} (${d.changed_lines} 行)</summary><pre>${v7Esc(d.diff_preview.join('\n'))}</pre></details>`).join(''):'<div>没有可显示的文字差异</div>'}${all.length>25?`<small>其余 ${all.length-25} 项已省略显示。</small>`:''}</div>`;
}
function v7VersionsHtml(){
 if(!V5.batch)return '';
 return `<section class="v7-module v7-versions"><div class="v7-title"><div><span class="v7-tag">ARCHIVE / IMMUTABLE RELEASES</span><h3>历史交付版本</h3><p>每次成功导出保存校验值，不会因后续调整主体资料而覆盖旧版ZIP。</p></div></div>
 ${V7.versions.length?`<div class="v7-version-list">${V7.versions.slice(0,8).map((v,i)=>`<div><div><b>${v7Esc(v.id)}</b><small>${v7Esc(v.created_at.replace('T',' ').slice(0,19))} · SHA-256 ${v7Esc(v.content_hash.slice(0,15))}…</small></div><button class="btn v5-outline" data-v7-action="download-version" data-version="${v7Esc(v.id)}">下载历史版本 ↓</button></div>`).join('')}</div>`:'<div class="v7-empty">还没有成功导出的正式版本。先解决阻断项，点击上方“生成正式ZIP并保存版本”。</div>'}</section>`;
}
function v7Enhance(){
 if(S.page!=='delivery')return;
 // V7 release controls are Shopify-only. Never overwrite the V35 SHOPLINE
 // file preview or replace a SHOPLINE download with a legacy Shopify release.
 if(V5.platform==='shopline')return;
 const progress=document.querySelector('.v5-progress');
 // Full-width source review wall sits directly beneath progress, not cramped into the narrow right column.
 if(progress&&(V5.proposal||V5.batch)&&!document.querySelector('.v7-comparison'))progress.insertAdjacentHTML('afterend',v7CompareHtml());
 const tree=document.querySelector('.v5-tree');
 if(V5.batch&&tree){
   if(!document.querySelector('.v7-release'))tree.insertAdjacentHTML('beforebegin',v7GateHtml());
   if(!document.querySelector('.v7-versions')){
     const audit=document.querySelector('.v5-audit-panel');
     if(audit)audit.insertAdjacentHTML('afterend',v7VersionsHtml());
   }
 }
 const dl=document.querySelector('[data-action="v5-export"]');
 if(dl){dl.setAttribute('title','V7：交付时执行新一轮质检并保存不可覆盖的历史版本');dl.textContent=V7.gate?.allowed?'生成并下载英文目录ZIP ↓':'等待质检通过';}
 const oldTree=document.querySelector('.v5-tree');
 if(oldTree&&V5.batch){
   oldTree.querySelectorAll('.v5-folder').forEach(x=>{x.innerHTML='├ Products / products.csv<br>├ Theme / 4 Liquid files<br>└ Policies / 7 policy files';});
 }
}
async function v7ShowDiff(){if(!V5.batch)return;V7.showDiffs=!V7.showDiffs;
 if(V7.showDiffs&&!V7.diffs){render();try{V7.diffs=await api('/api/v7/deployments/'+encodeURIComponent(V5.batch.id)+'/diffs');}catch(e){V7.diffs={error:e.message};}}
 render();}
async function v7Prepare(){if(!V5.batch)return;
 if(V7.busy)return;
 V7.busy=true;
 try{
   // V7's historic release endpoint ALWAYS generates Shopify content.
   // Route SHOPLINE through the V35 platform-specific audit and exporter.
   if(V5.platform==='shopline'){
     const id=encodeURIComponent(V5.batch.id);
     const audit=await api('/api/v16/deployments/'+id+'/audit?platform=shopline');
     V5.review=audit;
     if((audit.issue_counts?.error||0)>0 || audit.status==='存在阻断问题'){
       const reasons=(audit.issues||[]).filter(x=>x.type==='error').map(x=>x.message).slice(0,4).join('；');
       throw new Error('SHOPLINE离线交付预检未通过：'+(reasons||audit.status));
     }
     await v5Download('/api/v16/deployments/'+id+'/export.zip?platform=shopline',
       'BIG_BANG_SHOPLINE_V35_'+V5.batch.id+'_CONFIGURED.zip');
     return;
   }
   const out=await api('/api/v7/deployments/'+encodeURIComponent(V5.batch.id)+'/prepare',{method:'POST'});
   toast(out.reused?'与上一版本一致，下载已有归档':'正式ZIP已校验并保存历史版本');
   await v7LoadGate();
   await v5Download(out.download_url,'BIG_BANG_'+V5.batch.id+'_'+out.version_id+'.zip');
 }catch(e){V5.error=e.message;toast('交付被拦截：'+e.message,true);render();}
 finally{V7.busy=false;}
}
const v7PrevRender=render;
render=function(...args){const out=v7PrevRender(...args);window.requestAnimationFrame(v7Enhance);return out;};
// Capture V5's old export button; it must use new V7 safety checks and versioning.
document.addEventListener('click',async e=>{
 const old=e.target.closest?.('[data-action="v5-export"]');
 if(old){e.preventDefault();e.stopImmediatePropagation();await v7Prepare();return;}
 const control=e.target.closest?.('[data-v7-action]');if(!control)return;
 e.preventDefault();e.stopImmediatePropagation();
 const action=control.dataset.v7Action;
 if(action==='refresh-gate')await v7LoadGate();
 if(action==='ai-review'){await v5Audit(true);await v7LoadGate();}
 if(action==='focus-entity'){const target=document.querySelector('.v5-entity-repair');target?.scrollIntoView({behavior:V6.motion?'smooth':'auto',block:'center'});const field=target?.querySelector('[data-v5-field=phone]');field?.focus({preventScroll:true});}
 if(action==='show-diffs')await v7ShowDiff();
 if(action==='prepare')await v7Prepare();
 if(action==='report'&&V5.batch)await v5Download('/api/v7/deployments/'+encodeURIComponent(V5.batch.id)+'/release-report.json','BIG_BANG_QA_'+V5.batch.id+'.json');
 if(action==='download-version')await v5Download('/api/v7/versions/'+encodeURIComponent(control.dataset.version)+'/download.zip','BIG_BANG_ARCHIVE_'+control.dataset.version+'.zip');
},true);
document.addEventListener('error',e=>{if(e.target?.matches?.('.v7-thumb img'))e.target.style.display='none';},true);
// Compact extra navigation; do not crowd sidebar with more decorative menu entries.
const v7Version=document.querySelector('.side-vnum');if(v7Version)v7Version.textContent='V7.0';
const v7Footer=document.querySelector('.app-foot span:last-child');if(v7Footer)v7Footer.textContent='RELEASE CONTROL · V7.0';
const v7LoginVersion=document.querySelector('.login-right-foot span');if(v7LoginVersion)v7LoginVersion.textContent='VERSION 7.0 / SOURCE VERIFIED';
document.title='大爆炸 BIG BANG V7.0 · 视觉差异与交付质量控制';
