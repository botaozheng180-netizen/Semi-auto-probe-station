const el=id=>document.getElementById(id), pet=el('pet');
const moves=Object.fromEntries(natureData.states.map(s=>[s.name,s]));
const images={};
const allFrames=[...natureData.states.flatMap(s=>s.frames),...Object.values(natureData.transitions).flat()];
const ready=Promise.all([...new Set(allFrames.map(f=>f.image))].map(name=>new Promise((resolve,reject)=>{const im=new Image();images[name]=im;im.onload=resolve;im.onerror=reject;im.src=name;})));
let generation=0,pose='sit',mode='boot',guided=false,step=0,lastActivity=performance.now(),busy=false;
const tasks=['AutoFocus','FocusMap · focus plane calibration','FocusMap · image stitching','LayoutMap · layout mapping','AutoTest · single device test','AutoTest · auto device test'];
const sit=moves.Welcome.frames[7],stand=moves.Guide.frames[0],rest=moves.Waiting.frames[0];
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
function draw(f){const [x,y,w,h]=f.rect,ctx=pet.getContext('2d'),dw=w*f.scale,dh=h*f.scale;ctx.clearRect(0,0,320,320);ctx.drawImage(images[f.image],x,y,w,h,(320-dw)/2,280-dh-f.lift,dw,dh);}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function active(token){return token===generation;}
async function frames(list,times,token){for(let i=0;i<list.length;i++){if(!active(token))return false;draw(list[i]);await delay(reduced?20:times[i]);}return active(token);}
async function bridge(target,token){if(!active(token))return false;if(pose===target){draw(target==='sit'?sit:target==='stand'?stand:rest);return true;}if(pose!=='sit'&&target!=='sit'){if(!await bridge('sit',token))return false;}const key=pose==='rest'||target==='rest'?'sitRest':'sitStand';let list=natureData.transitions[key];if(target==='sit')list=[...list].reverse();if(!await frames(list,list.map(()=>150),token))return false;pose=target;draw(target==='sit'?sit:target==='stand'?stand:rest);return true;}
async function action(name,token){const m=moves[name];return frames(m.frames,m.ms.map(ms=>Math.min(ms,400)),token);}
function touch(){lastActivity=performance.now();}
function say(text,options=[]){el('bubble').textContent=text;el('choices').replaceChildren();for(const [label,fn] of options){const b=document.createElement('button');b.textContent=label;b.onclick=()=>{touch();fn();};el('choices').append(b);}refresh();}
function refresh(){el('steps').textContent=tasks.map((s,i)=>(i===step?'→ ':'')+s).join('  /  ');el('run').disabled=busy||mode!=='watch';el('success').disabled=busy||mode!=='running';el('failure').disabled=busy||mode!=='running';el('retry').disabled=busy||mode!=='watch';el('status').textContent=`${busy?'Transitioning':mode} · ${pose}${mode==='idle'?' · rest after 10 seconds of inactivity':''}`;}
async function transaction(fn){const token=++generation;busy=true;refresh();try{await fn(token);}finally{if(active(token)){busy=false;touch();refresh();}}}
function idle(text){mode='idle';say(text);touch();}
async function point(token){mode='guiding';say(`Next: ${tasks[step]}.`);if(!await bridge('stand',token))return;if(!await action('Guide',token))return;if(!await bridge('sit',token))return;mode='watch';say(`Ready when you are: ${tasks[step]}.`);}
function startTour(){guided=true;step=0;transaction(point);}
function askNew(){mode='question';say('New user?',[['✔ Yes',()=>{say('Want me to guide you through?',[['✔ Yes',startTour],['❌ No',()=>idle('No problem. Click me whenever you need help.')]]);}],['❌ No',()=>{guided=false;idle('Good to have you back! Have a nice Test~');}]]);}
async function launch(){guided=false;step=0;await transaction(async token=>{mode='welcome';say('Welcome!');if(!await bridge('sit',token))return;if(await action('Welcome',token)){pose='sit';draw(sit);askNew();}});}
el('run').onclick=()=>{touch();mode='running';say(`Watching ${tasks[step]}…`);};
async function result(ok){await transaction(async token=>{mode='feedback';say(ok?'Well done!':'Something needs checking. Let’s try again.');if(!await bridge('stand',token))return;if(!await action(ok?'Success':'Attention',token))return;pose=ok?'sit':'stand';if(!await bridge('sit',token))return;if(guided){if(ok)step++;if(step<tasks.length){await point(token);return;}guided=false;step=tasks.length-1;idle('You’ve finished the guide! Have a nice Test~');}else idle(ok?'Well done!':'Please check the operation and try again.');});}
el('success').onclick=()=>result(true);el('failure').onclick=()=>result(false);el('retry').onclick=()=>transaction(point);el('restart').onclick=launch;
async function help(){if(busy||mode==='running')return;const previous=mode;await transaction(async token=>{if(!await bridge('sit',token))return;mode='help';say('How can I help you?');const input=document.createElement('input');input.placeholder='Ask Nature…';input.setAttribute('aria-label','Question for Nature');const send=document.createElement('button');send.textContent='Send';const back=document.createElement('button');back.textContent='Back';back.onclick=()=>{if(previous==='watch'){mode='watch';say(`Ready when you are: ${tasks[step]}.`);}else if(previous==='question')askNew();else idle('I’m here whenever you need me.');};send.onclick=()=>{if(!input.value.trim())return;transaction(async t=>{mode='thinking';say('Thinking…');if(!await action('Thinking',t))return;draw(sit);mode='help';say('In SAP, your question will open the AI Agent tab. This preview demonstrates the animation only.',[['Continue',()=>{if(guided)transaction(point);else idle('I’m here whenever you need me.');}]]);});};input.onkeydown=e=>{if(e.key==='Enter')send.click();};el('choices').append(input,send,back);input.focus();});}
pet.onclick=help;pet.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();help();}};
document.addEventListener('pointerdown',touch);document.addEventListener('keydown',touch);document.addEventListener('pointermove',touch);
setInterval(()=>{if(!busy&&mode==='idle'&&performance.now()-lastActivity>=10000){transaction(async token=>{mode='rest';say('Resting nearby. Click me whenever you need help.');if(!await bridge('rest',token))return;busy=false;refresh();while(active(token)&&mode==='rest'){if(!await frames(moves.Waiting.frames,moves.Waiting.ms,token))return;}});}},200);
ready.then(launch).catch(()=>say('An animation image could not load. Keep this preview beside its image files.'));
