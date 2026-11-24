'use strict';
/* BIG BANG V6: opt-in/opt-out visual polish and interaction helpers.
   No changes to entity data, assignment rules, downloads or audits. */
const V6 = (() => {
  const key = 'bigbang.motion.enabled.v6';
  const prefersReduce = !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  let stored = null;
  try { stored = window.localStorage.getItem(key); } catch (_) {}
  return {motion: stored === null ? !prefersReduce : stored === 'true', commandsOpen: false, scanTimer: null};
})();
function v6ApplyMotion(){
  document.body.classList.toggle('v6-motion',V6.motion);
  document.querySelectorAll('[data-v6-motion]').forEach(b=>{
    b.setAttribute('aria-pressed',String(V6.motion));
    b.setAttribute('title',V6.motion?'关闭动态效果':'开启动态效果');
    const t=b.querySelector('[data-v6-motion-label]');if(t)t.textContent=V6.motion?'动效已开':'动效已关';
  });
  try{window.localStorage.setItem('bigbang.motion.enabled.v6',String(V6.motion));}catch(_){}
}
function v6CloseCommands(){
  const el=document.getElementById('v6-command-pop');if(el)el.hidden=true;
  V6.commandsOpen=false;const button=document.getElementById('v6-command-trigger');if(button)button.setAttribute('aria-expanded','false');
}
function v6OpenCommands(){
  const el=document.getElementById('v6-command-pop');if(!el)return;
  if(V6.commandsOpen){v6CloseCommands();return;}
  el.hidden=false;V6.commandsOpen=true;
  document.getElementById('v6-command-trigger')?.setAttribute('aria-expanded','true');
  el.querySelector('button')?.focus();
}
function v6EnhanceContent(){
  if(!document.getElementById('shell')||document.getElementById('shell').classList.contains('hidden'))return;
  const hero=document.querySelector('.v4-welcome');
  if(hero&&!hero.querySelector('.v6-hero-art')){
    const deco=document.createElement('div');deco.className='v6-hero-art';deco.setAttribute('aria-hidden','true');hero.prepend(deco);
  }
  const control=document.querySelector('.v4-board-controls');
  if(control&&!control.querySelector('.v6-matrix-action')){
    const btn=document.createElement('button');btn.type='button';btn.className='v6-matrix-action';btn.dataset.v6Scan='';btn.title='仅播放状态矩阵视觉扫描，不会启动网站审核';btn.innerHTML='<b>↗</b> 点亮矩阵';
    control.appendChild(btn);
  }
  document.querySelectorAll('.v4-slot:not([data-v6-initialized])').forEach((b,i)=>{
    b.dataset.v6Initialized='1';b.style.setProperty('--v6-delay',String(i%29));
    if(V6.motion){b.classList.add('v6-first-paint');b.addEventListener('animationend',()=>b.classList.remove('v6-first-paint'),{once:true});}
  });
  document.querySelectorAll('.v5-preview-item:not([data-v6-initialized])').forEach((b,i)=>{
    b.dataset.v6Initialized='1';b.style.setProperty('--v6-delay',String(Math.min(i,8)));
    if(V6.motion){b.classList.add('v6-new-item');b.addEventListener('animationend',()=>b.classList.remove('v6-new-item'),{once:true});}
  });
}
function v6ScanMatrix(){
  const matrix=document.getElementById('v4-matrix');if(!matrix)return;
  if(!V6.motion){window.alert('动效当前已关闭。可以通过右上角的「动效」按钮开启。');return;}
  matrix.classList.remove('v6-scanning');void matrix.offsetWidth;matrix.classList.add('v6-scanning');
  if(V6.scanTimer)window.clearTimeout(V6.scanTimer);
  V6.scanTimer=window.setTimeout(()=>matrix.classList.remove('v6-scanning'),1650);
}
function v6DoCommand(target){
  v6CloseCommands();
  if(target==='delivery' || target==='bulk' || target==='overview' || target==='audits' || target==='entities')navigate(target);
}
function v6InitChrome(){
  const target=document.querySelector('.top-right');
  if(target&&!document.getElementById('v6-command-trigger')){
    const wrap=document.createElement('div');wrap.className='v6-top-tools';
    wrap.innerHTML='<button type="button" class="v6-tool" id="v6-command-trigger" aria-expanded="false" aria-controls="v6-command-pop"><span class="v6-tool-icon">⌘</span><span>快捷操作</span></button>'+
     '<button type="button" class="v6-tool" data-v6-motion aria-pressed="true"><span class="v6-tool-icon">✦</span><span data-v6-motion-label>动效已开</span></button>';
    const search=target.querySelector('#v4-launch-search');
    if(search)search.after(wrap);else target.prepend(wrap);
    const panel=document.createElement('div');panel.id='v6-command-pop';panel.className='v6-command-pop';panel.hidden=true;
    panel.innerHTML='<div class="v6-command-title">快速进入工作区 <span>BIG BANG / V6</span></div><div class="v6-command-grid">'+
     '<button data-v6-go="delivery"><i>01</i> 新建主体交付 <small>交付工作台 ↗</small></button>'+
     '<button data-v6-go="bulk"><i>02</i> 批量规划主体 <small>批量分配 ↗</small></button>'+
     '<button data-v6-go="audits"><i>03</i> AI审核中心 <small>真实检查 ↗</small></button>'+
     '<button data-v6-go="entities"><i>04</i> 查看公司主体 <small>资料管理 ↗</small></button>'+
     '<button data-v6-go="overview"><i>05</i> 回到总控中心 <small>300家矩阵 ↗</small></button></div><div class="v6-command-note">快捷键 Alt + G 打开操作面板；Esc 关闭。所有操作仍由原系统执行。</div>';
    document.body.appendChild(panel);
  }
  const version=document.querySelector('.side-vnum');if(version)version.textContent='V6.0';
  const foot=document.querySelector('.app-foot span:last-child');if(foot)foot.textContent='KINETIC CONTROL INTERFACE · V6.0';
  const login=document.querySelector('.login-right-foot span');if(login)login.textContent='VERSION 6.0 / KINETIC OBSIDIAN';
  document.title='大爆炸 BIG BANG V6.0 · 智能店铺控制中心';
  v6ApplyMotion();
}
// Current render always handles actual server data. Enhancement merely decorates it.
const v6OriginalRender=render;
render=function(...args){const result=v6OriginalRender(...args);window.requestAnimationFrame(v6EnhanceContent);return result;};
v6InitChrome();window.requestAnimationFrame(v6EnhanceContent);
// Capture controls so generic action handlers never interpret these as business operations.
document.addEventListener('click',function(e){
 const toggle=e.target.closest('[data-v6-motion]');
 if(toggle){e.preventDefault();e.stopImmediatePropagation();V6.motion=!V6.motion;v6ApplyMotion();return;}
 if(e.target.closest('#v6-command-trigger')){e.preventDefault();e.stopImmediatePropagation();v6OpenCommands();return;}
 const command=e.target.closest('[data-v6-go]');
 if(command){e.preventDefault();e.stopImmediatePropagation();v6DoCommand(command.dataset.v6Go);return;}
 const scan=e.target.closest('[data-v6-scan]');
 if(scan){e.preventDefault();e.stopImmediatePropagation();v6ScanMatrix();return;}
 if(V6.commandsOpen&&!e.target.closest('#v6-command-pop'))v6CloseCommands();
 const button=e.target.closest('.btn, .v4-flow-card, .v6-command-grid button');
 if(button && V6.motion && !button.disabled){
   const rect=button.getBoundingClientRect();const ripple=document.createElement('span');ripple.className='v6-ripple';
   ripple.style.left=(e.clientX-rect.left)+'px';ripple.style.top=(e.clientY-rect.top)+'px';
   button.appendChild(ripple);window.setTimeout(()=>ripple.remove(),640);
 }
},true);
document.addEventListener('keydown',function(e){
 if(e.altKey&&!e.ctrlKey&&!e.metaKey&&e.key.toLowerCase()==='g'){
   if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName))return;
   e.preventDefault();v6OpenCommands();
 }
 if(e.key==='Escape'&&V6.commandsOpen){e.preventDefault();v6CloseCommands();}
});
// Dragging a legitimate company file onto the existing upload surface uses the same upload code.
for(const name of ['dragover','dragenter','dragleave','drop']){
 document.addEventListener(name,function(e){
   const surface=e.target.closest?.('.v5-upload');if(!surface)return;
   e.preventDefault();e.stopPropagation();
   if(name==='dragover'||name==='dragenter')surface.classList.add('v6-drag-over');
   else if(name==='dragleave'){if(!surface.contains(e.relatedTarget))surface.classList.remove('v6-drag-over');}
   else {surface.classList.remove('v6-drag-over');const f=e.dataTransfer?.files?.[0];if(!f)return;
     if(!/\.(zip|txt|pdf|png|jpe?g)$/i.test(f.name)){toast('主体文件仅支持 ZIP / TXT / PDF / PNG / JPG',true);return;}
     v5FileUpload(f);
   }
 },true);
}
// Hover-only detailed peek for the true 300-store grid.
(function(){
 const tip=document.createElement('div');tip.id='v6-slot-tip';tip.className='v6-slot-tip';tip.hidden=true;
 const heading=document.createElement('b'),detail=document.createElement('small'),state=document.createElement('span');
 tip.append(heading,detail,state);document.body.appendChild(tip);
 const label={unassigned:'未分配主体',assigned:'已分配主体',configured:'基础配置齐全',audited:'已有通过记录',empty:'未登记'};
 function place(x,y){let left=Math.min(window.innerWidth-310,Math.max(10,x+15));let top=Math.min(window.innerHeight-126,Math.max(8,y+14));tip.style.left=left+'px';tip.style.top=top+'px';}
 document.addEventListener('pointerover',e=>{
   if(e.pointerType==='touch')return;
   const item=e.target.closest?.('.v4-slot');if(!item||item.classList.contains('is-dimmed'))return;
   const title=(item.getAttribute('title')||'').split(' · ');
   heading.textContent=title[0]||'店铺';detail.textContent=title.slice(1).join(' · ')||'点击进入店铺详情';
   state.textContent=label[item.dataset.v4State]||'店铺资料';tip.hidden=false;place(e.clientX,e.clientY);
 },true);
 document.addEventListener('pointermove',e=>{if(!tip.hidden)place(e.clientX,e.clientY);},true);
 document.addEventListener('pointerout',e=>{if(e.target.closest?.('.v4-slot'))tip.hidden=true;},true);
 document.addEventListener('scroll',()=>{tip.hidden=true;},true);
})();
