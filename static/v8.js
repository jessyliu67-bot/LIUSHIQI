'use strict';
/* BIG BANG V8 — actionable guided intake, evidence ledger and selective reroll.
   Real API results only; no fabricated verification statuses. */
const V8={sources:null,check:null,busy:false,sourceError:'',checkError:'',lastDraft:'',active:'all'};
function v8Esc(v){return H(String(v??''));}
function v8Data(){return {fields:{...V5.fields},domains:V5.rawDomains||''};}
async function v8RefreshCheck(showErrors=false){
 try{V8.check=await api('/api/v8/intake/check',{method:'POST',body:JSON.stringify(v8Data())});V8.checkError='';}
 catch(e){V8.checkError=e.message;if(showErrors)toast(e.message,true);}
 if(S.page==='delivery')render();
}
async function v8LoadSources(){
 const id=V5.draftId;if(!id){V8.sources=null;return;}
 V8.lastDraft=id;
 try{const result=await api('/api/v8/intake/'+encodeURIComponent(id)+'/sources');if(V8.lastDraft===id){V8.sources=result;V8.sourceError='';}}
 catch(e){if(V8.lastDraft===id){V8.sources=null;V8.sourceError=e.message;}}
 if(S.page==='delivery')render();
}
const v8PrevFileUpload=v5FileUpload;
v5FileUpload=async function(file){V8.sources=null;V8.check=null;V8.sourceError='';await v8PrevFileUpload(file);if(V5.draftId)await v8LoadSources();await v8RefreshCheck();};
const v8PrevAIRecognize=v5AIRecognize;
v5AIRecognize=async function(...args){await v8PrevAIRecognize(...args);if(V5.draftId)await v8LoadSources();await v8RefreshCheck();};
const v8PrevReset=v5Reset;
v5Reset=function(...args){const r=v8PrevReset(...args);V8.sources=null;V8.check=null;V8.sourceError='';V8.checkError='';return r;};
const v8PrevPreview=v5MakePreview;
v5MakePreview=async function(...args){await v8RefreshCheck(false);if(!V8.check?.can_preview){const m=V8.check?.errors?.join('；');if(m){V5.error=m;toast(m,true);render();return;}}await v8PrevPreview(...args);};
async function v8RerollOne(storeId){
 if(V8.busy||!V5.proposal){return;}
 V8.busy=true;V5.loading=true;V5.loadingText='正在严格筛选这家店铺的独立替代组合…';render();
 try{
  const result=await api('/api/v8/proposals/'+encodeURIComponent(V5.proposal.proposal_id)+'/reroll-one',
    {method:'POST',body:JSON.stringify({store_id:storeId})});
  V5.proposal={...V5.proposal,...result,plan:{...V5.proposal.plan,...result.plan}};
  V7.comparison=null;V7.fingerprintKey='';
  toast('仅替换了 '+result.changed_domain+'：'+result.previous_store_code+' → '+result.new_store_code);
  await v7LoadVisual();
 }catch(e){V5.error=e.message;toast(e.message,true);}
 finally{V8.busy=false;V5.loading=false;render();}
}
function v8SourceHtml(){
 const src=V8.sources;
 if(!V5.draftId)return '<div class="v8-evidence muted">上传主体文件后，这里会显示具体文件来源与待核验字段。</div>';
 if(V8.sourceError)return `<div class="v8-evidence warn">来源读取未完成：${v8Esc(V8.sourceError)}</div>`;
 if(!src)return '<div class="v8-evidence muted">正在读取文件清单与字段来源…</div>';
 const fields=[['name','公司名称'],['registration_no','登记编号'],['address','注册地址'],['phone','通用电话'],['email','公司邮箱']];
 return `<div class="v8-evidence"><div class="v8-evidence-head"><b>原始文件依据</b><span>${src.files.length} 份资料</span></div>
 <div class="v8-file-strip">${src.files.slice(0,12).map(f=>`<span title="${v8Esc(f.note)}">${v8Esc(f.file)} <small>${v8Esc(f.type)}</small></span>`).join('')}</div>
 <div class="v8-evidence-table">${fields.map(([key,label])=>{
   const s=src.sources[key]||[];return `<div class="v8-evidence-row"><strong>${label}</strong><span>${s.length?s.map(x=>v8Esc(x.file)).join('、'):'无可确认的文字来源'}</span><small class="${s.length?'v8-f-sourced':'v8-f-check'}">${s.length?'已提取 · 待核原件':'需核实'}</small></div>`;
 }).join('')}</div>
 ${src.conflicts.length?`<div class="v8-alert">${src.conflicts.map(v8Esc).join('<hr>')}</div>`:''}
 <p class="v8-disclaimer">来源追踪仅用于识别字段，不代表公司登记、身份证、地址或电话真实性已核验。扫描图片未在此重复运行OCR。</p></div>`;
}
function v8CheckHtml(){
 const c=V8.check;
 if(!c)return `<div class="v8-check-placeholder"><b>提交前一次看清缺失项</b><button type="button" class="v8-minor" data-v8-action="check">立即检查资料与域名</button></div>`;
 const valid=c.can_preview;
 return `<section class="v8-preflight ${valid?'passed':'blocked'}">
  <div class="v8-check-head"><div><span class="v8-overline">PRE-DEPLOY CHECK</span><h3>智能预检</h3></div>
  <div class="v8-check-result">${valid?'基础字段已齐备':'待处理 '+c.errors.length+' 项'}</div></div>
  <div class="v8-chip-list">${c.domains.map(s=>`<span class="v8-domain-chip">${v8Esc(s)}</span>`).join('')||'<span class="v8-no-domains">尚未识别到有效域名</span>'}</div>
  <div class="v8-check-rows">${c.fields.filter(x=>x.required).map(f=>`<button type="button" class="v8-field-status" data-v8-focus="${f.key}">
   <i class="${f.status==='需处理'?'fail':'ok'}"></i><span>${v8Esc(f.label)}</span><small>${v8Esc(f.status)}</small></button>`).join('')}</div>
  ${c.errors.length?`<div class="v8-check-errors">${c.errors.map(x=>`<p>${v8Esc(x)}</p>`).join('')}</div>`:''}
  ${c.warnings.length?`<details class="v8-warnings"><summary>${c.warnings.length}项额外核验提醒</summary>${c.warnings.map(x=>`<p>${v8Esc(x)}</p>`).join('')}</details>`:''}
  <div class="v8-check-bottom"><span>这是离线格式预检，非官方主体核验</span><button class="v8-minor" type="button" data-v8-action="check">重新检查</button></div>
 </section>`;
}
function v8Enhance(){
 if(S.page!=='delivery')return;
 // Keep source evidence in the first input column; no new navigation maze.
 const upload=document.querySelector('.v5-upload');
 if(upload&&!document.querySelector('.v8-source-panel')){
  upload.insertAdjacentHTML('afterend',`<details class="v8-source-panel" ${V5.draftId?'open':''}><summary><span>资料来源与文件清单</span><span>查看具体依据 +</span></summary>${v8SourceHtml()}</details>`);
 }
 const meta=document.querySelector('.v5-domain-meta');
 if(meta&&!document.querySelector('.v8-preflight')&&!document.querySelector('.v8-check-placeholder'))meta.insertAdjacentHTML('afterend',v8CheckHtml());
 if(V5.proposal&&!V5.batch){
   document.querySelectorAll('.v7-tile').forEach((tile,i)=>{
     if(tile.querySelector('[data-v8-action="reroll"]'))return;
     const item=V5.proposal.items[i];if(!item)return;
     tile.insertAdjacentHTML('beforeend',`<div class="v8-reroll-line"><button type="button" data-v8-action="reroll" data-store-id="${v8Esc(item.store_id)}" ${V8.busy?'disabled':''}>只更换这一家 <span>↻</span></button></div>`);
   });
 }
 // Existing final release and archived versions remain the single source of truth.
 const area=document.querySelector('.v7-comparison');
 if(area)area.classList.add('v8-comparison');
 const main=document.querySelector('.v5-workspace .v5-top');
 if(main&&!document.querySelector('.v8-top-status')){
  const one=!!V5.proposal,two=!!V5.batch;
  main.insertAdjacentHTML('beforeend',`<div class="v8-top-status"><span><i></i> SOURCE CONTROLLED</span><span>${two?'已保存批次':one?'已生成匹配方案':'待配置主体与域名'}</span></div>`);
 }
}
const v8PrevRender=render;
render=function(...args){const result=v8PrevRender(...args);window.requestAnimationFrame(v8Enhance);return result;};
document.addEventListener('click',async e=>{
 const target=e.target.closest?.('[data-v8-action],[data-v8-focus]');if(!target)return;
 e.preventDefault();e.stopImmediatePropagation();
 if(target.dataset.v8Action==='reroll')await v8RerollOne(target.dataset.storeId);
 else if(target.dataset.v8Action==='check')await v8RefreshCheck(true);
 else if(target.dataset.v8Focus){
  const field=target.dataset.v8Focus;
  const details=document.querySelector('.v5-entity-fields');if(details)details.open=true;
  const input=document.querySelector('[data-v5-field="'+field+'"]');
  input?.scrollIntoView({behavior:V6?.motion?'smooth':'auto',block:'center'});input?.focus({preventScroll:true});
 }
},true);
document.addEventListener('focusout',e=>{
 if(e.target?.matches?.('[data-v5-field], #v5-domains')){
  // Do not rerender on each character. Check once when leaving an input.
  window.setTimeout(()=>{if(S.page==='delivery'&&!V5.loading)v8RefreshCheck();},80);
 }
},true);
const v8Label=document.querySelector('.side-vnum');if(v8Label)v8Label.textContent='V8.0';
const v8Footer=document.querySelector('.app-foot span:last-child');if(v8Footer)v8Footer.textContent='GUIDED DELIVERY · V8.0';
const v8Login=document.querySelector('.login-right-foot span');if(v8Login)v8Login.textContent='VERSION 8.0 / INTELLIGENT DELIVERY';
document.title='大爆炸 BIG BANG V8.0 · 智能交付指挥中心';
