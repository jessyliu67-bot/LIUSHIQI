'use strict';
/* BIG BANG V5 | 交付工作台 - one-page, evidence-first deployment */
PAGE_TITLES.delivery='交付工作台';
const V5={fields:{name:'',registration_no:'',country:'',address:'',phone:'',email:''},entityId:'',draftId:'',fileName:'',notes:[],candidates:[],duplicates:[],conflict:false,conflictOK:false,
  rawDomains:'',prefix:'service',domains:[],proposal:null,batch:null,review:null,deliveries:[],loading:false,loadingText:'',error:'',
  service_hours:'',response_time:'',additional_info:'',platform:sessionStorage.getItem('bigbang_v16_delivery_platform')||'shopline'};
function v5Reset(){Object.assign(V5,{fields:{name:'',registration_no:'',country:'',address:'',phone:'',email:''},entityId:'',draftId:'',fileName:'',notes:[],candidates:[],duplicates:[],conflict:false,conflictOK:false,rawDomains:'',prefix:'service',domains:[],proposal:null,batch:null,review:null,error:'',service_hours:'',response_time:'',additional_info:''});}
const v5OriginalRender=render;
render=function(){if(S.page==='delivery'&&S.overview){$('#content').innerHTML=v5Render();return}return v5OriginalRender();};
const v5OriginalHandleAction=handleAction;
handleAction=async function(t){const a=t.dataset.action;
 if(a==='v3-start'){navigate('delivery');return;}
 if(a==='v5-new'){v5Reset();render();return;}
 if(a==='v5-platform-shopline'||a==='v5-platform-shopify'){
   const next=a==='v5-platform-shopline'?'shopline':'shopify';
   if(V5.platform!==next){V5.platform=next;sessionStorage.setItem('bigbang_v16_delivery_platform',next);V5.review=null;render();if(V5.batch)await v5Audit(false);}
   return;
 }
 if(a==='v5-select-file'){$('#v5-file-picker').click();return;}
 if(a==='v5-ai-recognize'){await v5AIRecognize();return;}
 if(a==='v5-preview'){await v5MakePreview();return;}
 if(a==='v5-reroll'){await v5MakePreview();return;}
 if(a==='v5-confirm'){await v5Confirm();return;}
 if(a==='v5-open-delivery'){await v5LoadBatch(t.dataset.id);return;}
 if(a==='v5-audit'){await v5Audit();return;}
 if(a==='v5-save-fix'){await v5SaveFix();return;}
 if(a==='v5-save-entity'){await v5SaveEntity();return;}
 if(a==='v5-export'){if(V5.batch)await v5Download('/api/v16/deployments/'+encodeURIComponent(V5.batch.id)+'/export.zip?platform='+encodeURIComponent(V5.platform),'BIG_BANG_'+V5.platform.toUpperCase()+'_V35_'+V5.batch.id+'_CONFIGURED.zip');else toast('请先生成交付批次',true);return;}
 if(a==='v5-export-report'){if(V5.batch){const id=encodeURIComponent(V5.batch.id);const url=V5.platform==='shopline'?'/api/v16/deployments/'+id+'/report.json?platform=shopline':'/api/v5/deployments/'+id+'/report.json';await v5Download(url,'BIG_BANG_'+V5.platform.toUpperCase()+'_AUDIT_'+V5.batch.id+'.json');}return;}
 return v5OriginalHandleAction(t);
};
const v5OriginalNavigate=navigate;
navigate=function(page){if(page==='setup')page='delivery';v5OriginalNavigate(page);if(page==='delivery')v5LoadHistory();};
// Download with explicit error reporting. Previously navigating directly to a failed ZIP URL
// showed a raw API error, and users couldn't tell why the export didn't start.
async function v5Download(url,filename){
 if(V5.loading)return;
 V5.loading=true;V5.loadingText='正在生成并校验文件，请稍候…';V5.error='';render();
 try{
   const response=await fetch(url,{credentials:'same-origin',cache:'no-store'});
   if(!response.ok){
     let message='导出失败（HTTP '+response.status+'）';
     try{const err=await response.json();message=err.detail||err.message||message;}catch(e){}
     throw Error(message);
   }
   // Do not trust a platform label in the UI or a local filename. The
   // V35 exporter must prove which platform generated this response.
   if(url.includes('/api/v16/deployments/') && url.includes('/export.zip')){
     const expected=new URL(url,window.location.origin).searchParams.get('platform');
     const actual=response.headers.get('X-BIGBANG-Platform');
     if(!expected || !actual || actual.toLowerCase()!==expected.toLowerCase())
       throw Error('平台文件校验失败：选择了'+(expected||'未知')+'，但后端返回'+(actual||'未标记')+'。文件未下载。');
     if(!filename.toUpperCase().includes(expected.toUpperCase()))
       throw Error('ZIP文件名与交付平台不一致，已阻止下载。');
   }
   const file=await response.blob();
   if(!file.size)throw Error('服务器返回了空文件，导出已停止');
   const blobUrl=URL.createObjectURL(file);
   const link=document.createElement('a');link.href=blobUrl;link.download=filename;
   document.body.appendChild(link);link.click();link.remove();
   setTimeout(()=>URL.revokeObjectURL(blobUrl),60000);
   toast('文件已经生成，正在保存到浏览器下载目录：'+filename);
 }catch(e){V5.error=e.message;toast('导出未完成：'+e.message,true)}
 finally{V5.loading=false;render();}
}
async function v5LoadHistory(){try{V5.deliveries=await api('/api/v5/deployments');if(S.page==='delivery')render()}catch(e){console.warn(e)}}
async function v5LoadBatch(id){V5.loading=true;V5.loadingText='正在打开交付记录…';render();try{
 const b=await api('/api/v5/deployments/'+encodeURIComponent(id));V5.batch=b;V5.review=b.review;
 V5.service_hours=b.settings?.service_hours||'';V5.response_time=b.settings?.response_time||'';V5.additional_info=b.settings?.additional_info||'';
 V5.fields={...V5.fields,name:b.entity?.entity_name||'',address:b.entity?.address||'',phone:b.entity?.phone||'',country:b.entity?.country||'',registration_no:b.entity?.registration_no||''};
 V5.proposal=null;V5.error='';
 if(V5.platform==='shopline')await v5Audit(false);
}catch(e){V5.error=e.message;toast(e.message,true)}finally{V5.loading=false;render();}}
async function v5FileUpload(file){if(!file)return;
 V5.loading=true;V5.loadingText='正在检查压缩包并识别登记资料…';V5.error='';render();
 try{const fd=new FormData();fd.append('file',file);
 const zip=/\.zip$/i.test(file.name);
 const result=await api(zip?'/api/v5/intake/company-zip':'/api/v3/intake/extract',{method:'POST',body:fd});
 V5.fileName=file.name;V5.draftId=result.draft_id;V5.fields={...V5.fields,...result.fields};
 V5.notes=[...(result.notes||[]),...(result.warning?[result.warning]:[])];V5.conflict=!!result.conflict;V5.conflictOK=false;
 V5.candidates=result.candidates||[];V5.duplicates=result.duplicates||[];
 if(V5.duplicates.length===1){const old=lookup(S.entities,V5.duplicates[0].id);
  if(old){V5.entityId=old.id;V5.fields={name:old.name,registration_no:old.registration_no,country:old.country,address:old.address,phone:old.phone,email:old.email};V5.notes.unshift('检测到已有主体，已自动关联现有公司记录。');}}
 const checks=v5CoreProblems();if(checks.length)V5.notes.unshift('提交前必须补齐：'+checks.join('；'));
 toast('已读取 '+file.name+'，请核对公司名称、注册地址和主体通用电话');V5.proposal=null;
 }catch(e){V5.error=e.message;toast(e.message,true)}finally{V5.loading=false;render();}
}
async function v5AIRecognize(){
 if(!V5.draftId){toast('请先上传营业执照图片、PDF或公司资料ZIP',true);return;}
 if(!document.getElementById('v5-ocr-consent')?.checked){toast('请先勾选授权；只有点击识别按钮才会传送主体材料',true);return;}
 if(V5.loading)return;
 V5.loading=true;V5.loadingText='已获授权，正在使用DeepSeek提取主体信息…';V5.error='';render();
 try{
   const data=await api('/api/v5/intake/ai-recognize',{method:'POST',body:JSON.stringify({draft_id:V5.draftId,consent:true})});
   V5.fields={...V5.fields,...data.fields};V5.notes=[...(data.notes||[]),'DeepSeek已处理'+data.documents_sent+'份文件。请核对原件；识别不代表公司真实性核验。'];
   V5.conflict=!!data.conflict;V5.conflictOK=false;V5.proposal=null;
   toast('AI识别完成，请核对提取出的公司名称、注册地址和登记编号');
 }catch(e){V5.error=e.message;toast(e.message,true)}finally{V5.loading=false;render();}
}
function v5CoreProblems(){
 const f=V5.fields||{},issues=[];
 const name=(f.name||'').trim(),address=(f.address||'').trim(),phone=(f.phone||'').trim();
 if(!name||name.length<3)issues.push('公司法定名称未识别');
 else if(/[\u3400-\u9fff]/.test(name))issues.push('公司名称仍含中文或误识别为个人，请填写经确认的英文公司名称');
 else if(!/(Co\.?\s*,?\s*Ltd\.?|Limited|LLC|Inc\.?|Corporation|Corp\.?|GmbH|Pte\.?)/i.test(name))issues.push('公司名称缺少组织形式，请核实');
 if(!address)issues.push('公司注册地址未填写');
 else if(/[\u3400-\u9fff]/.test(address))issues.push('注册地址仍包含中文，需要核对英文地址');
 const digits=phone.replace(/\D/g,'');
 if(!phone)issues.push('缺少主体通用客服电话（所有店铺共用）');
 else if(phone.startsWith('+1')&&digits.length!==11)issues.push('主体通用电话格式错误：+1 后应有10位数字，当前是'+(digits.length-1)+'位');
 else if(!/^[+]?[0-9()\s.\-]+$/.test(phone)||digits.length<7||digits.length>15)issues.push('主体通用电话格式错误');
 return issues;
}
async function v5SaveEntity(){
 if(!V5.batch)return;
 if(!document.getElementById('v5-entity-confirm')?.checked){toast('请先确认公司主体信息与原始文件一致',true);return;}
 const errs=v5CoreProblems();if(errs.length){V5.error=errs.join('；');render();return;}
 V5.loading=true;V5.loadingText='正在同步修正该主体名下的店铺，并清除旧审核结果…';V5.error='';render();
 try{
  await api('/api/v5/deployments/'+encodeURIComponent(V5.batch.id)+'/entity',{method:'PUT',body:JSON.stringify({
   name:V5.fields.name,address:V5.fields.address,phone:V5.fields.phone,country:V5.fields.country,
   registration_no:V5.fields.registration_no,confirmed:true})});
  V5.batch=await api('/api/v5/deployments/'+encodeURIComponent(V5.batch.id));
  V5.review=null;await v5Audit(false);toast('主体资料已同步更新，相关审核已重新执行');
 }catch(e){V5.error=e.message;toast(e.message,true)}finally{V5.loading=false;render();}
}
async function v5MakePreview(){
 if(V5.loading)return;
 V5.loading=true;V5.loadingText='检查域名、剩余资源与装修差异…';V5.error='';V5.batch=null;V5.review=null;render();
 try{
   const problems=v5CoreProblems();if(!V5.entityId&&problems.length)throw Error('主体资料尚未通过预检：'+problems.join('；'));
   if(!V5.entityId&&V5.fields.name.trim().length<2)throw Error('请上传主体文件，或填写真实的公司法定名称');
   if(V5.conflict&&!V5.conflictOK)throw Error('主体ZIP可能包含多个公司，请先核对并确认');
   const parsed=await api('/api/v5/domains/parse',{method:'POST',body:JSON.stringify({text:V5.rawDomains})});
   V5.domains=parsed.domains;
   const request={entity_id:V5.entityId||null,intake_draft_id:V5.draftId||null,entity:V5.fields,domains:V5.domains,email_prefix:V5.prefix};
   V5.proposal=await api('/api/v3/auto/preview',{method:'POST',body:JSON.stringify(request)});
   if(!V5.proposal.plan?.can_commit)throw Error('分配仍有冲突，不能确认，请核对结果');
   toast('已生成'+V5.proposal.items.length+'家店铺的完整分配预览');
 }catch(e){V5.error=e.message;toast(e.message,true)}finally{V5.loading=false;render();}
}
async function v5Confirm(){if(!V5.proposal)return;
 if(!$('#v5-data-confirm')?.checked){toast('请先核对主体资料、域名与邮箱配置',true);return;}
 const missing=v5CoreProblems();if(!V5.entityId&&missing.length){V5.error='请补齐后再确认分配：'+missing.join('；');render();return;}
 V5.loading=true;V5.loadingText='正在原子保存分配并生成交付结果…';V5.error='';render();
 try{
 const result=await api('/api/v3/auto/commit',{method:'POST',body:JSON.stringify({proposal_id:V5.proposal.proposal_id})});
 await refresh();await v5LoadHistory();
 V5.batch=await api('/api/v5/deployments/'+encodeURIComponent(result.batch_id));V5.proposal=null;
 V5.loadingText='正在核对交付包中的商品、Liquid、政策结构及变量…';render();
 await v5Audit(false);
 toast('已创建 '+result.assigned+' 家店铺，交付ZIP可直接下载');
 }catch(e){V5.error=e.message;toast(e.message,true)}finally{V5.loading=false;render();}
}
async function v5Audit(explicit=true){if(!V5.batch)return;
 V5.loading=true;V5.loadingText='正在逐店检查文件结构与主体字段'+(S.me?.deepseek_connected?'，并调用DeepSeek语义抽检':'')+'…';render();
 try{
 const query=S.me?.deepseek_connected?'?with_ai=true':'?with_ai=false';
 V5.review=V5.platform==='shopline'
  ?await api('/api/v16/deployments/'+encodeURIComponent(V5.batch.id)+'/audit?platform=shopline')
  :await api('/api/v5/deployments/'+encodeURIComponent(V5.batch.id)+'/audit'+query,{method:'POST',body:'{}'});
 if(explicit)toast('审核完成：'+V5.review.status);
 }catch(e){V5.error=e.message;toast(e.message,true)}finally{V5.loading=false;render()}
}
async function v5SaveFix(){if(!V5.batch)return;
 V5.loading=true;V5.loadingText='正在根据真实配置更新页脚，并重新审核…';render();
 try{
 await api('/api/v5/deployments/'+encodeURIComponent(V5.batch.id)+'/settings',{method:'PUT',body:JSON.stringify({
 service_hours:V5.service_hours,response_time:V5.response_time,additional_info:V5.additional_info})});
 V5.batch=await api('/api/v5/deployments/'+encodeURIComponent(V5.batch.id));
 await v5Audit(false);toast('已按填写内容更新配置并重新核对交付包');
 }catch(e){V5.error=e.message;toast(e.message,true)}finally{V5.loading=false;render()}
}
function v5Field(name,title,placeholder=''){
 return `<label class="v5-input"><span>${title}</span><input class="input" data-v5-field="${name}" value="${H(V5.fields[name]||'')}" placeholder="${H(placeholder)}" autocomplete="off"></label>`;
}
function v5Banner(){return V5.error?`<div class="v5-error"><b>需要处理</b><span>${H(V5.error)}</span></div>`:'';}
function v5Progress(){const step=V5.batch?3:V5.proposal?2:1;return `<div class="v5-progress">${[['01','上传主体与域名'],['02','匹配结果预览'],['03','导出与AI检查']].map(([num,title],i)=>`<div class="${step===i+1?'active':step>i+1?'done':''}"><span>${num}</span><b>${title}</b></div>`).join('')}</div>`}
function v5Deliveries(){const ds=V5.deliveries||[];
 return `<section class="v5-history"><div class="v5-card-title"><h2>最近生成的交付包</h2><p>确认以后不会消失。随时回到这里重新下载和查看审核报告。</p></div>${ds.length?ds.slice(0,9).map(d=>`<div class="v5-history-item"><div><b>${H(d.company_name)}</b><small>${H(d.store_count)} 家店铺 · ${H(d.created_at?.slice(0,16).replace('T',' '))}</small></div><button data-action="v5-open-delivery" data-id="${H(d.id)}">打开交付记录 ↗</button></div>`).join(''):'<div class="v5-muted">尚无已生成的交付包</div>'}</section>`;}
function v5Preview(){const p=V5.proposal;
 if(!p)return `<div class="v5-empty"><span>02 / 准备中</span><h3>匹配完成后，结果会显示在这里</h3><p>保留原始300套完整组合，严格检查同主体的装修结构和商品大类差异。</p></div>`;
 return `<div class="v5-card-title"><h2>本次匹配：${p.items.length} 家</h2><p>可以重新随机，只有确认后才会占用店铺资源。</p></div><div class="v5-preview-list">${p.items.map((x,i)=>`<div class="v5-preview-item"><div class="v5-number">${String(i+1).padStart(2,'0')}</div><div><b>${H(x.domain)}</b><small>${H(x.store_code)} · ${H(x.template_group)} · ${H(x.style_name)}</small><span>${H(x.category)} / ${H(x.product_family)}</span><small>${H(x.support_email)}（邮箱尚未开通验证）</small></div></div>`).join('')}</div>
 <div class="v5-checks"><span>已检查装修结构不重复</span><span>已检查商品大类不重复</span><span>已检查模板未被占用</span><span>已检查域名冲突</span></div>
 <label class="v5-confirm"><input id="v5-data-confirm" type="checkbox"> 我已确认主体、域名与对应店铺的分配结果，理解邮箱需要实际开通，政策承诺需要核对。</label>
 <div class="v5-row-buttons"><button class="btn v5-outline" data-action="v5-reroll">重新随机匹配</button><button class="btn v5-primary" data-action="v5-confirm">确认并生成交付包 →</button></div>`;
}
function v5Result(){const b=V5.batch;if(!b)return v5Preview();
 const review=V5.review;const issues=review?.issues||[];
 const count=review?.issue_counts||{};
 const blocked=issues.some(i=>i.type==='error')||v5CoreProblems().length>0;
 return `<div class="v5-result-head"><div class="v5-kicker">${blocked?'PREFLIGHT REQUIRED':'DELIVERY READY'}</div><h2>${b.stores.length}家店铺 · ${blocked?'有问题待修复':'可下载交付文件'}</h2><p>${H(b.company_name)} / 批次 ${H(b.id)}</p></div>
 <div class="v5-result-download"><span class="v5-download-glyph">↓</span><div><b>完整 ${V5.platform.toUpperCase()} ${b.stores.length}店铺 ZIP</b><small>${V5.platform==='shopline'?'每家1份SHOPLINE迁移CSV、3份SLINE、7份Word/TXT政策':'每家1份Shopify CSV、4份Liquid、7份Word/TXT政策'}。平台文件严格分开，下载后可在浏览器下载记录中找到。</small></div><button class="btn v5-primary" data-action="v5-export" ${blocked?'disabled title="请先解决主体信息或政策文件的阻断项"':''}>${blocked?'先修复阻断项':'下载完整ZIP ↓'}</button></div>
 <section class="v5-entity-repair"><div class="v5-kicker">SHARED ENTITY IDENTITY</div><h3>一家公司 · 共用一个客服电话</h3><p>这些资料会同步写入本主体的所有店铺页脚和七份政策。保存后自动使旧审核结果失效，不会修改商品和装修匹配。</p>
<div class="v5-fields">${v5Field('name','主体英文公司名称 *')}${v5Field('phone','主体通用客服电话 *')}${v5Field('address','公司注册地址 *')}</div>
${v5CoreProblems().length?`<div class="v5-entity-alert"><b>主体信息未通过：</b>${v5CoreProblems().map(x=>`<span>${H(x)}</span>`).join('')}</div>`:'<div class="v5-entity-ok">主体字段格式已填写；公司真实性和电话接通情况仍需核实。</div>'}
<label class="v5-confirm"><input id="v5-entity-confirm" type="checkbox"> 我已依据真实主体资料核对以上字段，确认更新同一主体名下的全部店铺。</label>
<button class="btn v5-outline" data-action="v5-save-entity">保存主体信息并重新检查</button></section>
<div class="v5-tree"><b>文件夹预览</b>${b.stores.map(s=>`<details><summary><span>${H(s.domain)}</span><small>${H(s.template_code)} · ${V5.platform==='shopline'?'11':'12'}文件</small></summary><div class="v5-folder">${V5.platform==='shopline'?'├ Products / 1份SHOPLINE迁移CSV<br>├ Theme / 3份SLINE<br>└ Policies / 7份Word/TXT政策':'├ Products / 1份Shopify CSV<br>├ Theme / 4份Liquid<br>└ Policies / 7份Word/TXT政策'}</div></details>`).join('')}</div>
 <section class="v5-audit-panel">${renderAiConnectionBox(true)}<div class="v5-card-title"><div class="v5-kicker">${V5.platform==='shopline'?'SHOPLINE / LOCAL QA':'SHOPIFY / AI + RULE AUDIT'}</div><h2>交付包同步审核</h2><p>${H(review?.ai_status||'正在准备规则审核') }</p></div>
 <div class="v5-audit-stats"><span><b>${count.error||0}</b>阻断项</span><span><b>${count.warning||0}</b>待核验</span><span><b>${count.info||0}</b>提示</span></div>
 <p class="v5-audit-status">${H(review?.status||'等待检测')}</p>
 <div class="v5-issue-list">${issues.length?issues.slice(0,28).map(i=>`<div class="v5-issue ${H(i.type)}"><b>${H(i.store_code)} · ${H(i.code)}</b><span>${H(i.message)}</span>${i.file?`<small>${H(i.file)}</small>`:''}</div>`).join(''):'<div class="v5-muted">目前没有审核记录</div>'}${issues.length>28?`<div class="v5-muted">另有 ${issues.length-28} 项，请下载完整报告查看。</div>`:''}</div>
 <div class="v5-fixbox"><h3>补充真实信息并重新修复</h3><p>系统已自动填写有来源的主体、域名、邮箱变量。客服营业时间和响应承诺只有在你填写后才会加入页脚，不会虚构。</p>
 <label>真实客服时间（含时区，可留空）<input class="input" id="v5-hours" value="${H(V5.service_hours)}" placeholder="例如 Mon–Fri 9:00–18:00 PST"></label>
 <label>实际回复时效（可留空）<input class="input" id="v5-response" value="${H(V5.response_time)}" placeholder="例如 Within 2 business days"></label>
 <label>其他已核实的公司信息（可留空）<input class="input" id="v5-additional" value="${H(V5.additional_info)}" placeholder="无则留空"></label>
 <button class="btn v5-outline" data-action="v5-save-fix">保存真实信息 · 重新修复并审核</button>
 </div>
 <div class="v5-row-buttons"><button class="btn v5-outline" data-action="v5-audit">重新检查当前平台文件</button><button class="btn v5-outline" data-action="v5-export-report">查看完整JSON报告</button></div>
 <div class="v5-boundary">这是交付文件的离线质量检查，不代表已审核真实网站、验证图片授权或通过 AppLovin/Shopify 官方审核。</div></section>`;
}
function v5Render(){return `<div class="v5-workspace"><header class="v5-top"><div><div class="v5-kicker">BIG BANG / DELIVERY STUDIO</div><h1>把主体资料变成完整店铺交付包。</h1><p>不再分五步填写。上传主体压缩包、粘贴域名、预览分配，确认后直接下载；右侧同步显示审核问题。</p></div><button class="btn v5-outline" data-action="v5-new">＋ 新建一批</button></header>${v5Progress()}${v5Banner()}
 <section class="v5-platform-picker" aria-label="请选择交付平台"><div><strong>交付平台 · DELIVERY PLATFORM</strong><p>同一批主体和已分配模板，分别生成正确的平台文件。选择 SHOPLINE 时不会导出 Shopify Liquid。</p></div><div class="v5-platform-options"><button type="button" class="v5-platform-choice ${V5.platform==='shopline'?'active':''}" data-action="v5-platform-shopline" aria-pressed="${V5.platform==='shopline'}">SHOPLINE <small>1 CSV · 3 SLINE · 7 Policies</small></button><button type="button" class="v5-platform-choice ${V5.platform==='shopify'?'active':''}" data-action="v5-platform-shopify" aria-pressed="${V5.platform==='shopify'}">Shopify <small>1 CSV · 4 Liquid · 7 Policies</small></button></div></section><div class="v5-columns"><div class="v5-left"><section class="v5-card"><div class="v5-card-title"><div class="v5-kicker">01 / 业务主体</div><h2>直接上传你的公司文件包</h2><p>ZIP可包含营业执照、登记证明、EIN信函及其他TXT、PDF、图片或DOCX。自动读取后仅需核对字段。</p></div>
 <button class="v5-upload" data-action="v5-select-file"><span class="v5-upload-icon">↑</span><b>${H(V5.fileName||'选择主体ZIP文件 / TXT / PDF / 图片')}</b><small>${V5.fileName?'点击可重新上传':'ZIP / TXT / PDF / JPG / PNG · 不需要先逐项手填'}</small></button>
 ${V5.duplicates.length?`<div class="v5-inline-notice">发现已有主体：${V5.duplicates.map(x=>H(x.name)).join('、')}。系统会优先关联已有记录，避免重复建立。</div>`:''}
 ${V5.notes.length?`<div class="v5-notes">${V5.notes.map(n=>`<div>· ${H(n)}</div>`).join('')}</div>`:''}
 ${V5.draftId&&!/\.txt$/i.test(V5.fileName)?`<div class="v5-ocr-actions"><b>上传已完成 · 自动识别补救</b><p>如果公司名称没有自动显示，请上传 TXT 或可复制文字的 PDF，或使用已安装的本地 OCR；也可明确授权DeepSeek识别图片。</p><label><input id="v5-ocr-consent" type="checkbox"> 我同意仅将本次上传的主体图片或PDF（ZIP最多3份）发送给DeepSeek进行文字识别。 </label><button class="btn v5-outline" data-action="v5-ai-recognize">使用 DeepSeek 识别这份主体资料 ↗</button><small>只有点击按钮才发送文件；识别内容还需要核对，不等于工商真实性验证。</small></div>`:''}
 ${v5CoreProblems().length?`<div class="v5-entity-alert"><b>正式交付前必须处理：</b>${v5CoreProblems().map(x=>`<span>${H(x)}</span>`).join('')}</div>`:'<div class="v5-entity-ok">必填主体字段格式已填写，请核对原件后继续。</div>'}
 ${V5.conflict?`<label class="v5-confirm"><input id="v5-conflict-ok" type="checkbox" ${V5.conflictOK?'checked':''}>我已逐份检查，确认这是需要配置的一家公司。</label>`:''}
 <details class="v5-entity-fields" ${V5.fileName?'':'open'}><summary>核对 / 补充公司信息 <span>（自动识别结果可编辑）</span></summary><div class="v5-fields">${v5Field('name','法定公司名称 *','Legal Company Name')}${v5Field('registration_no','注册编号 / EIN')}${v5Field('country','注册国家 / 地区')}${v5Field('address','注册地址')}${v5Field('phone','主体通用客服电话 *（同一公司全部店铺使用）')}${v5Field('email','公司邮箱')}</div></details>
 </section><section class="v5-card"><div class="v5-card-title"><div class="v5-kicker">02 / 目标域名</div><h2>所有域名直接粘贴进来</h2><p>不需要手工换行：一行、空格、逗号、换行分隔都能识别；支持完整 https:// 地址。</p></div>
 <textarea class="v5-domain-input" id="v5-domains" rows="4" spellcheck="false" placeholder="https://shop-a.com/ https://shop-b.com/ https://shop-c.com/ https://shop-d.com/ https://shop-e.com/">${H(V5.rawDomains)}</textarea>
 <div class="v5-domain-meta"><span>严格模式支持 4–5 个不同域名</span><span>当前输入 ${V5.rawDomains.trim()?V5.rawDomains.trim().split(/[\s,，;；|、]+/).filter(Boolean).length:0} 项</span></div>
 <div class="v5-email-setting"><label for="v5-prefix">每店独立邮箱建议</label><select id="v5-prefix" class="input"><option value="service" ${V5.prefix==='service'?'selected':''}>service@各自域名</option><option value="support" ${V5.prefix==='support'?'selected':''}>support@各自域名</option><option value="help" ${V5.prefix==='help'?'selected':''}>help@各自域名</option></select></div>
 <div class="v5-bottom-actions"><button class="btn v5-primary" data-action="v5-preview">分析域名并预览差异化组合 →</button><small>预览不占用资源，确认后才保存。</small></div></section></div>
 <div class="v5-right">${renderAiConnectionBox(true)}<section class="v5-card v5-right-main"><div class="v5-card-title"><div class="v5-kicker">03 / 分配与交付</div><h2>${V5.batch?'你的交付结果':V5.proposal?'核对本次分配':'可随时预览与交付'}</h2></div>${V5.batch?v5Result():v5Preview()}</section>${v5Deliveries()}</div></div>
 ${V5.loading?`<div class="v5-overlay"><div><span class="v5-spinner"></span><b>${H(V5.loadingText||'正在处理…')}</b><small>本地操作仍在进行，完成后显示可追踪结果</small></div></div>`:''}</div>`;}
// Do not rerender while typing; JS state is updated on every input.
document.addEventListener('input',e=>{
 const t=e.target;
 if(t.dataset.v5Field){V5.fields[t.dataset.v5Field]=t.value;V5.proposal=null;return;}
 if(t.id==='v5-domains'){V5.rawDomains=t.value;V5.proposal=null;const x=document.querySelector('.v5-domain-meta span:last-child');if(x)x.textContent='当前输入 '+t.value.trim().split(/[\s,，;；|、]+/).filter(Boolean).length+' 项';}
 if(t.id==='v5-hours')V5.service_hours=t.value;
 if(t.id==='v5-response')V5.response_time=t.value;
 if(t.id==='v5-additional')V5.additional_info=t.value;
},true);
document.addEventListener('change',e=>{
 const t=e.target;
 if(t.id==='v5-file-picker'){const f=t.files[0];t.value='';v5FileUpload(f);}
 if(t.id==='v5-prefix'){V5.prefix=t.value;V5.proposal=null;}
 if(t.id==='v5-conflict-ok')V5.conflictOK=t.checked;
},true);
// Public buttons linking to the old multi-step wizard now open the delivery workbench.
const v5Nav=document.getElementById('nav');
if(v5Nav){const b=document.createElement('button');b.className='nav-item';b.dataset.page='delivery';
 b.innerHTML='<span class="nav-icon">⇩</span><span class="nav-label"><b>交付工作台</b><small>DELIVERY STUDIO</small></span><span class="nav-arrow">↗</span>';
 const first=v5Nav.querySelector('[data-page="overview"]');if(first)first.after(b);else v5Nav.prepend(b);}
const picker=document.createElement('input');picker.id='v5-file-picker';picker.type='file';picker.accept='.zip,.txt,.pdf,.png,.jpg,.jpeg';picker.hidden=true;document.body.appendChild(picker);
document.title='大爆炸 BIG BANG V35 · SHOPLINE / Shopify 双平台交付';

const v5Version=document.querySelector('.side-vnum');if(v5Version)v5Version.textContent='V35';
const v5Footer=document.querySelector('.app-foot span:last-child');if(v5Footer)v5Footer.textContent='DUAL PLATFORM DELIVERY · V35';
const v5LoginVersion=document.querySelector('.login-right-foot span');if(v5LoginVersion)v5LoginVersion.textContent='VERSION 11.4.3 / V35 DUAL PLATFORM DELIVERY';
