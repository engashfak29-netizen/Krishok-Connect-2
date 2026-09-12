const typeBn={farmer:'কৃষক',business:'বিক্রেতা / ব্যবসা',expert:'কৃষি বিশেষজ্ঞ'};

document.addEventListener('DOMContentLoaded',async()=>{await kcReady;if(!KC.currentUserId)return;mountIcons();const me=kcMe();document.getElementById('avatar').src=me.avatar||'';document.getElementById('name').textContent=me.name||'কৃষক';document.getElementById('location').textContent=me.location||'আপনার ব্যক্তিগত কৃষি প্যানেল';renderQuick();await load();document.getElementById('logoutBtn').onclick=async()=>{try{await KC_API.post('/api/v1/auth/logout',{})}catch{} localStorage.removeItem('kc_access_token');location.href='../auth.html'};initFarmJournal();});
async function load(){return KC_API.get('/api/v1/dashboard').then(d=>{const s=d.stats||{};document.getElementById('stats').innerHTML=[['📝',s.posts||0,'পোস্ট'],['📦',s.orders||0,'অর্ডার'],['🛒',s.products||0,'পণ্য'],['🔔',s.unread_notifications||0,'নোটিফিকেশন']].map(x=>`<div class="dashboard-stat"><div class="stat-ico">${x[0]}</div><b>${x[1]}</b><span>${x[2]}</span></div>`).join('')}).catch(e=>toast(e.message))}
function renderQuick(){const items=[['../ai.html','🤖','AI কৃষি সহায়ক','রোগ, ফসল ও পরামর্শ'],['../marketplace.html','🛒','মার্কেটপ্লেস','পণ্য দেখুন ও কিনুন'],['../index.html','☁️','আবহাওয়া','আজকের আবহাওয়ার তথ্য'],['../create-post.html','✍️','পোস্ট করুন','কৃষির খবর শেয়ার করুন']];document.getElementById('quick').innerHTML=items.map(x=>`<a class="service-card" href="${x[0]}"><span class="service-icon">${x[1]}</span><span><span class="service-title" style="display:block">${x[2]}</span><span class="service-sub" style="display:block">${x[3]}</span></span></a>`).join('')}

function initFarmJournal(){
  const section=document.getElementById('farmJournalSection');
  const type=kcMe()?.type;
  if(type!=='farmer'){section.style.display='none';document.getElementById('farmSummarySection').style.display='none';return;}
  const input=document.getElementById('farmJournalInput'), send=document.getElementById('journalSend'), voice=document.getElementById('voiceBtn'), status=document.getElementById('voiceStatus');
  let journalSource='text';
  send.onclick=submitFarmJournal;
  input.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')submitFarmJournal()});
  document.getElementById('farmRefresh').onclick=loadFarmSummary;
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){voice.style.display='none';status.textContent='';} else {
    let rec=null, listening=false;
    voice.onclick=()=>{
      if(listening){try{rec.stop()}catch{};return;}
      rec=new SR();rec.lang='bn-BD';rec.interimResults=true;rec.continuous=false;
      let finalText=''; journalSource='voice_transcript'; listening=true; voice.textContent='⏹️'; status.textContent='শুনছি…';
      rec.onresult=e=>{let interim='';for(let i=e.resultIndex;i<e.results.length;i++){const t=e.results[i][0].transcript;if(e.results[i].isFinal)finalText+=t+' ';else interim+=t;}input.value=(input.value?input.value+' ':'')+(finalText+interim).trim()};
      rec.onerror=e=>{status.textContent=e.error==='not-allowed'?'মাইক্রোফোনের অনুমতি দিন':'ভয়েস ইনপুট নেওয়া যায়নি';listening=false;voice.textContent='🎤'};
      rec.onend=()=>{listening=false;voice.textContent='🎤';if(status.textContent==='শুনছি…')status.textContent='';};
      try{rec.start()}catch{listening=false;voice.textContent='🎤';}
    };
  }
  loadFarmSummary();
}

async function submitFarmJournal(){
  const input=document.getElementById('farmJournalInput'), send=document.getElementById('journalSend'), result=document.getElementById('journalResult');
  const text=input.value.trim(); if(!text){toast('আগে আপনার কথাটি লিখুন বা বলুন');return;}
  send.disabled=true;send.textContent='সংরক্ষণ…';
  try{
    const data=await KC_API.post('/api/v1/farmer/farm/journal',{text,source_type:journalSource});
    journalSource='text';
    input.value='';
    journalSource='text';
    renderJournalResult(data);
    await loadFarmSummary();
    await loadJournalHistory();
  }catch(e){toast(e.message)}finally{send.disabled=false;send.textContent='পাঠান';}
}

function renderJournalResult(data){
  const el=document.getElementById('journalResult');
  const p=data.parsed||{}; const applied=(data.applied?.created||[]).length+(data.applied?.changes||[]).length;
  const unresolved=(p.unresolved||[]).length;
  el.innerHTML=`<div class="card" style="padding:10px;font-size:13px"><b>${unresolved?'তথ্য নেওয়া হয়েছে':'তথ্য সংরক্ষণ হয়েছে'}</b><div class="muted" style="margin-top:4px">${applied?`${applied}টি তথ্য আপডেট/সংরক্ষণ করা হয়েছে।`: 'আরও একটু তথ্য প্রয়োজন হতে পারে।'}</div>${unresolved?`<div style="margin-top:6px">${(p.unresolved||[]).map(escapeHtml).join('<br>')}</div>`:''}</div>`;
}

async function loadFarmSummary(){
  const el=document.getElementById('farmSummary');
  try{
    const [data,journal]=await Promise.all([KC_API.get('/api/v1/farmer/farm'),KC_API.get('/api/v1/farmer/farm/journal?limit=5')]);
    const farm=data.farm||{}, plots=data.plots||[];
    const active=plots.filter(p=>p.active); const total=active.reduce((n,p)=>n+Number(p.area_decimal||0),0);
    el.innerHTML=`<div class="card" style="padding:11px"><div style="display:flex;justify-content:space-between;gap:10px"><div><b>${escapeHtml(farm.name||'আমার খামার')}</b><div class="muted" style="font-size:12px;margin-top:3px">মোট সক্রিয় জমি: ${formatDecimal(total)} শতক</div></div><div class="muted" style="font-size:12px">${active.length}টি প্লট</div></div>${active.length?`<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">${active.slice(0,6).map(p=>`<span class="chip" style="font-size:12px">${escapeHtml(p.name)} · ${escapeHtml(String(p.area_value))} ${escapeHtml(p.area_unit)}</span>`).join('')}</div>`:'<div class="muted" style="margin-top:7px">এখনও কোনো সক্রিয় প্লট নেই। জমির তথ্য কৃষি ডায়েরির মাধ্যমে জানাতে পারেন।</div>'}</div>`;
    renderJournalHistory(journal||[]); try{await KC_API.post('/api/v1/farmer/notifications/generate',{});}catch{}
  }catch(e){el.innerHTML='<div class="card" style="padding:11px">জমির তথ্য এখন লোড করা যাচ্ছে না।</div>';}
}
function formatDecimal(n){return Number(n||0).toLocaleString('bn-BD',{maximumFractionDigits:2});}
async function loadJournalHistory(){try{const j=await KC_API.get('/api/v1/farmer/farm/journal?limit=5');renderJournalHistory(j||[])}catch{}}
function renderJournalHistory(rows){
  const old=document.getElementById('farmJournalHistory');
  if(old)old.remove();
  if(!rows.length)return;
  const sec=document.getElementById('farmSummarySection');
  const box=document.createElement('div');box.id='farmJournalHistory';box.style.marginTop='8px';
  box.innerHTML=`<div class="muted" style="font-size:12px;margin-bottom:5px">সাম্প্রতিক কৃষিকাজ</div>`+rows.slice(0,3).map(r=>`<div class="card" style="padding:9px;margin-top:5px"><div style="font-size:13px">${escapeHtml(r.entry_text)}</div><div class="muted" style="font-size:11px;margin-top:3px">${escapeHtml(r.created_at||'')}</div></div>`).join('');
  sec.appendChild(box);
}
