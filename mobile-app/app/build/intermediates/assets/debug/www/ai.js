/* =========================================================================
   Krishok Connect — AI কৃষি সহায়ক পেজ লজিক
   ১) বালাইনাশক/রোগ ফাইন্ডার — পুরনো "ফসল বন্ধু" ইঞ্জিন পুনঃব্যবহার (data-loader + search-engine)
   ২) অনুমোদিত knowledge-base ও AI engine-ভিত্তিক কৃষি সহায়তা চ্যাট
   ========================================================================= */

let INDEXED = [];
let activeCategory = "all";
const EXAMPLES = ["ফিপ্রোনিল", "পাতা মোড়ানো পোকা", "ধানের মাজরা পোকা", "Fungicide", "আগাছানাশক"];

document.addEventListener("DOMContentLoaded", async () => {
  mountIcons();
  renderBottomNav("");
  setupTabs();

  document.getElementById("exampleRow").innerHTML = EXAMPLES.map(e=>`<button class="ai-quick" data-ex="${escapeHtml(e)}">${escapeHtml(e)}</button>`).join("");
  document.querySelectorAll("[data-ex]").forEach(b=>{
    b.addEventListener("click", ()=>{ document.getElementById("searchInput").value = b.getAttribute("data-ex"); runSearch(); });
  });
  document.querySelectorAll("#chipRow .chip").forEach(chip=>{
    chip.addEventListener("click", ()=>{
      document.querySelectorAll("#chipRow .chip").forEach(c=>c.classList.remove("active"));
      chip.classList.add("active");
      activeCategory = chip.getAttribute("data-cat");
      runSearch();
    });
  });
  document.getElementById("searchInput").addEventListener("input", debounce(runSearch, 180));

  setupMic();
  renderEmpty();

  const loaded = await loadPesticideData((status)=>{
    if(status) document.getElementById("resultsMeta").textContent = status;
  });
  INDEXED = buildIndex(loaded.data);
  document.getElementById("resultsMeta").textContent = "";

  setupChat();
});

function debounce(fn, ms){ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); }; }

function setupTabs(){
  document.querySelectorAll(".ai-tab").forEach(tab=>{
    tab.addEventListener("click", ()=>{
      document.querySelectorAll(".ai-tab").forEach(t=>t.classList.remove("active"));
      tab.classList.add("active");
      const key = tab.getAttribute("data-tab");
      document.getElementById("panelFinder").classList.toggle("active", key==="finder");
      document.getElementById("panelChat").classList.toggle("active", key==="chat");
      document.getElementById("chatInputBar").style.display = key==="chat" ? "flex" : "none";
    });
  });
}

/* ================= পালস সার্চ (ফাইন্ডার ট্যাব) ================= */
function runSearch(){
  const q = document.getElementById("searchInput").value.trim();
  if(!q){ renderEmpty(); return; }
  if(INDEXED.length === 0){ document.getElementById("resultsMeta").textContent = "ডেটা লোড হচ্ছে..."; return; }

  const { results, suggestions, fallback } = search(INDEXED, q, activeCategory);

  const suggestBox = document.getElementById("suggestBox");
  const meta = document.getElementById("resultsMeta");
  const list = document.getElementById("results");

  if(suggestions.length){
    suggestBox.innerHTML = `
      <div style="margin:6px 16px 0; background:#fff8ec; border:1.5px solid #f0d8a8; border-radius:14px; padding:13px 15px;">
        <div style="font-size:12.5px; font-weight:700; color:var(--accent-dark); margin-bottom:9px;">🤔 আপনি কি এটি খুঁজছেন?</div>
        <div style="display:flex; flex-wrap:wrap; gap:8px;">
          ${suggestions.map(s=>`<button class="ai-quick" data-sugg="${escapeHtml(s.label)}" style="border-color:var(--accent); color:var(--accent-dark);">${escapeHtml(s.label)}</button>`).join("")}
        </div>
      </div>`;
    suggestBox.querySelectorAll("[data-sugg]").forEach(b=>{
      b.addEventListener("click", ()=>{ document.getElementById("searchInput").value = b.getAttribute("data-sugg"); runSearch(); });
    });
    meta.textContent = "";
    list.innerHTML = "";
    return;
  }
  suggestBox.innerHTML = "";

  if(results.length === 0){
    meta.textContent = "";
    list.innerHTML = `<div class="empty-state"><div class="empty-emoji">🔍</div><div class="empty-title">"${escapeHtml(q)}" এর সাথে কিছু মেলেনি</div><div class="empty-text">অন্য বানানে লিখে দেখুন বা রোগ/সক্রিয় উপাদানের নাম দিয়ে খুঁজুন</div></div>`;
    return;
  }

  meta.textContent = fallback ? "কাছাকাছি মিল পাওয়া গেছে:" : `${results.length}টি ফলাফল পাওয়া গেছে`;
  list.innerHTML = results.map(r => resultCard(r.rec)).join("");
}

function resultCard(rec){
  const cls = categoryClass(rec.categoryEn);
  const color = { insecticide:"var(--primary)", fungicide:"var(--gold)", herbicide:"var(--red)", acaricide:"var(--blue)" }[cls] || "var(--primary)";
  return `
    <div class="card" style="padding:14px 15px 14px 13px; display:flex; gap:11px;">
      <div style="width:4px; border-radius:4px; background:${color}; flex-shrink:0;"></div>
      <div style="flex:1; min-width:0;">
        <div style="font-size:10px; color:var(--ink-faint); font-weight:700; text-transform:uppercase; letter-spacing:.4px;">${escapeHtml(rec.categoryBn||rec.categoryEn)}</div>
        <div style="display:flex; justify-content:space-between; gap:8px;">
          <div>
            <div style="font-family:'Baloo Da 2',sans-serif; font-size:15.5px; font-weight:700;">${escapeHtml(rec.brand)}</div>
            <div style="font-size:11px; color:var(--ink-muted); margin-top:1px;">${escapeHtml(rec.company)}</div>
          </div>
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:6px; margin:8px 0;">
          ${rec.activeIngredient ? `<span class="tag" style="background:var(--primary-light); color:var(--primary-dark);">${escapeHtml(rec.activeIngredient)}</span>` : ''}
          ${rec.formulation ? `<span class="tag" style="background:var(--surface-2); color:var(--ink-muted);">${escapeHtml(rec.formulation)}</span>` : ''}
        </div>
        <div style="font-size:12.5px; color:var(--ink); line-height:1.55;">${escapeHtml(rec.useCase)}</div>
      </div>
    </div>`;
}
function categoryClass(catEn){
  const c = (catEn||"").toLowerCase();
  if(c.includes("insecticide")) return "insecticide";
  if(c.includes("fungicide")) return "fungicide";
  if(c.includes("herbicide")) return "herbicide";
  if(c.includes("acaricide")) return "acaricide";
  return "insecticide";
}
function renderEmpty(){
  document.getElementById("suggestBox").innerHTML = "";
  document.getElementById("resultsMeta").textContent = "";
  document.getElementById("results").innerHTML = `
    <div class="empty-state">
      <div class="empty-emoji">🌱</div>
      <div class="empty-title">রোগ বা ওষুধের নাম লিখুন অথবা বলুন</div>
      <div class="empty-text">বাংলা, ইংরেজি অথবা ফোনেটিক — যেভাবে ইচ্ছা লিখুন বা মাইক্রোফোনে বলুন।<br>বানান একটু ভুল হলেও সমস্যা নেই।</div>
    </div>`;
}

/* ================= ভয়েস সার্চ (Web Speech API) ================= */
function setupMic(){
  const micBtn = document.getElementById("micBtn");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!SR){ micBtn.style.display = "none"; return; }
  const recog = new SR();
  recog.lang = "bn-BD"; recog.interimResults = false; recog.maxAlternatives = 1;
  let listening = false;
  micBtn.addEventListener("click", ()=>{
    if(listening){ recog.stop(); return; }
    try{ recog.start(); listening = true; document.getElementById("listeningHint").style.display = "block"; }
    catch(e){}
  });
  recog.onresult = (e)=>{
    const text = e.results[0][0].transcript;
    document.getElementById("searchInput").value = text;
    runSearch();
  };
  recog.onend = ()=>{ listening = false; document.getElementById("listeningHint").style.display = "none"; };
  recog.onerror = ()=>{ listening = false; document.getElementById("listeningHint").style.display = "none"; toast("ভয়েস শনাক্ত করা যায়নি, আবার চেষ্টা করুন"); };
}

/* ================= উপসর্গ-ভিত্তিক সহজ নিয়মভিত্তিক চ্যাট ================= */
const SYMPTOM_KB = [
  { keys:["হলুদ","পাতা হলুদ"], reply:"পাতা হলুদ হওয়া সাধারণত নাইট্রোজেনের ঘাটতি অথবা মাজরা পোকা/জাব পোকার আক্রমণে হতে পারে। মাটি পরীক্ষা করান এবং ইউরিয়া সার প্রয়োগ বিবেচনা করুন। পোকার আক্রমণ সন্দেহ হলে \"ওষুধ/রোগ খুঁজুন\" ট্যাবে গিয়ে \"জাব পোকা\" লিখে সঠিক কীটনাশক খুঁজে নিন।" },
  { keys:["পাতা কুঁকড়ে","কুকড়ে","কোকড়া"], reply:"পাতা কুঁকড়ে যাওয়া সাধারণত সাদা মাছি বা থ্রিপসের কারণে ভাইরাসজনিত রোগের লক্ষণ হতে পারে। হলুদ আঠালো ফাঁদ ব্যবহার করুন এবং আক্রান্ত পাতা সরিয়ে ফেলুন। বিশেষজ্ঞের সাথে চ্যাটে ছবি পাঠিয়ে নিশ্চিত হতে পারেন।" },
  { keys:["সাদা মাছি","সাদামাছি"], reply:"সাদা মাছি দমনে হলুদ আঠালো ফাঁদ এবং নিমতেল স্প্রে (সপ্তাহে ২ বার) কার্যকর জৈব পদ্ধতি। প্রয়োজনে অনুমোদিত কীটনাশক খুঁজতে \"ওষুধ/রোগ খুঁজুন\" ট্যাবে \"সাদা মাছি\" লিখুন।" },
  { keys:["মাজরা","কাণ্ড পোকা"], reply:"মাজরা পোকা দমনে আক্রান্ত কুশি তুলে ফেলুন এবং আলোর ফাঁদ ব্যবহার করুন। ক্ষেত্রবিশেষে অনুমোদিত কীটনাশক প্রয়োজন হতে পারে — \"ওষুধ/রোগ খুঁজুন\" ট্যাবে বিস্তারিত পাবেন।" },
  { keys:["পচন","গোড়া পচা","ধ্বসা"], reply:"গোড়া পচা রোগ সাধারণত অতিরিক্ত জলাবদ্ধতা ও ছত্রাকের কারণে হয়। জমিতে নিষ্কাশন ব্যবস্থা ঠিক করুন এবং আক্রান্ত গাছ সরিয়ে ফেলুন। ছত্রাকনাশক দরকার হলে \"ওষুধ/রোগ খুঁজুন\" ট্যাবে \"ছত্রাকনাশক\" ফিল্টার ব্যবহার করুন।" },
  { keys:["বৃষ্টি","স্প্রে করব"], reply:"বৃষ্টির পূর্বাভাস থাকলে স্প্রে করা থেকে বিরত থাকুন, ওষুধ ধুয়ে যাবে এবং কার্যকারিতা কমে যাবে। আবহাওয়া পরিষ্কার হওয়ার পর সকালে বা বিকালে স্প্রে করুন।" },
  { keys:["সার","কোন সার"], reply:"সাধারণ ফসলের জন্য NPK (ইউরিয়া, টিএসপি, এমওপি) সুষম অনুপাতে প্রয়োগ করুন। সঠিক মাত্রা জানতে মাটি পরীক্ষা করানো ভালো, অথবা মার্কেটপ্লেসে \"কৃষি বাজার\" বিক্রেতার সাথে যোগাযোগ করুন।" },
];
const KB_FALLBACK = "দুঃখিত, এই উপসর্গের জন্য এখনো নির্দিষ্ট তথ্য যোগ করা হয়নি। \"ওষুধ/রোগ খুঁজুন\" ট্যাবে গিয়ে সরাসরি রোগ বা পোকার নাম লিখে দেখুন, অথবা চ্যাট থেকে সরাসরি কৃষি পরামর্শক-কে মেসেজ করুন।";

function setupChat(){
  addChatMsg("bot", "আসসালামু আলাইকুম! আমি আপনার AI কৃষি সহায়ক। আপনার ফসলের সমস্যা বা উপসর্গ লিখে জানান — যেমন \"পাতা হলুদ হয়ে যাচ্ছে\" বা \"সাদা মাছি দেখা যাচ্ছে\"।");
  document.getElementById("chatSendBtn").addEventListener("click", sendChat);
  const img=document.getElementById("imageInput");
  img.addEventListener("change",()=>{
    const f=img.files&&img.files[0], box=document.getElementById("imagePreview");
    if(!f){box.style.display="none";box.innerHTML="";return;}
    const url=URL.createObjectURL(f); box.style.display="block";
    box.innerHTML=`<img src="${url}" style="max-width:180px;max-height:140px;border-radius:12px;border:1px solid var(--line)"><div style="font-size:11px;color:var(--ink-muted);margin-top:4px;">ছবি প্রস্তুত — উপসর্গ লিখে পাঠান</div>`;
  });
  document.getElementById("chatInput").addEventListener("keydown", e=>{ if(e.key==="Enter") sendChat(); });
}
function addChatMsg(who, text){
  const body = document.getElementById("chatBody");
  const div = document.createElement("div");
  div.className = "ai-msg " + (who==="user"?"user":"bot");
  div.textContent = text;
  body.appendChild(div);
  window.scrollTo(0, document.body.scrollHeight);
}
async function sendChat(){
  const input=document.getElementById("chatInput"); const text=input.value.trim();
  const crop=(document.getElementById("cropInput")?.value||"").trim();
  const img=document.getElementById("imageInput")?.files?.[0];
  if(!text && !crop && !img)return;
  addChatMsg("user",text || (img?"📷 ফসলের সমস্যার ছবি পাঠালাম":"")); input.value="";
  try{
    if(img || crop){
      const fd=new FormData(); fd.append("symptom",text); fd.append("crop",crop); if(img) fd.append("image",img);
      const r=await KC_API.request('/api/v1/ai/diagnose',{method:'POST',body:fd}); addChatMsg("bot",r.answer);
      if(r.visual_observation) addChatMsg("bot","ছবিতে দেখা লক্ষণ: "+r.visual_observation);
    }else{
      const r=await KC_API.post('/api/v1/ai/chat',{message:text}); addChatMsg("bot",r.answer);
    }
  }catch(e){
    const lower=text.toLowerCase(); const match=SYMPTOM_KB.find(k=>k.keys.some(key=>lower.includes(key.toLowerCase()))); addChatMsg("bot",match?match.reply:KB_FALLBACK+" ছবি দিলে আরও ভালোভাবে বিশ্লেষণ করা যাবে।");
  }
}
