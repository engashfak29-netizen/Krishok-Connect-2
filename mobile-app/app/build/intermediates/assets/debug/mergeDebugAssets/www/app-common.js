/* =========================================================================
   Krishok Connect — কমন UI লজিক (বটম ন্যাভ, অ্যাকশন শীট, টোস্ট, হেল্পার)
   ========================================================================= */

function escapeHtml(s){
  return String(s||"").replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
}

function renderBottomNav(active){
  const mount = document.getElementById("bottomNav");
  if(!mount) return;
  const item = (key, label, ic, badge) => `
    <a href="${navHref(key)}" class="nav-item ${active===key?'active':''}" style="position:relative;">
      <span style="position:relative; display:inline-block;">
        ${icon(ic,21)}
        ${badge>0 ? `<span class="badge-dot" style="display:flex; top:-6px; right:-9px; border:none;">${badge>9?'9+':badge}</span>` : ''}
      </span>
      <span>${label}</span>
    </a>`;
  mount.innerHTML = `
    ${item('home','হোম','home')}
    ${item('market','মার্কেট','market')}
    <button class="nav-fab" id="fabBtn">${icon('plus',24)}</button>
    ${item('chat','চ্যাট','chat', kcUnreadChats())}
    ${item('profile','প্রোফাইল','profile')}
  `;
  const fab = document.getElementById("fabBtn");
  if(fab) fab.addEventListener("click", openActionSheet);
}
function navHref(key){
  return { home:'index.html', market:'marketplace.html', chat:'chat.html', profile:'profile.html' }[key] || 'index.html';
}

function openActionSheet(){
  let overlay = document.getElementById("kcSheetOverlay");
  if(!overlay){
    overlay = document.createElement("div");
    overlay.className = "sheet-overlay";
    overlay.id = "kcSheetOverlay";
    overlay.innerHTML = `
      <div class="sheet">
        <div class="sheet-handle"></div>
        <div class="sheet-title">কী করতে চান?</div>
        <a class="sheet-action" href="create-post.html">
          <span class="sa-ico" style="background:var(--primary)">${icon('edit',20)}</span>
          <span><span class="sa-title" style="display:block">নতুন পোস্ট লিখুন</span><span class="sa-sub">ফসলের ছবি বা খবর সবাইকে জানান</span></span>
        </a>
        <a class="sheet-action" href="sell-product.html">
          <span class="sa-ico" style="background:var(--accent-dark)">${icon('bag',20)}</span>
          <span><span class="sa-title" style="display:block">পণ্য বিক্রি করুন</span><span class="sa-sub">মার্কেটপ্লেসে ফসল বা পণ্য যোগ করুন</span></span>
        </a>
        <a class="sheet-action" href="ai.html">
          <span class="sa-ico" style="background:var(--teal,#3f7f8c)">${icon('ai',20)}</span>
          <span><span class="sa-title" style="display:block">AI কৃষি সহায়ক জিজ্ঞাসা করুন</span><span class="sa-sub">রোগ, ওষুধ বা পরামর্শ খুঁজুন</span></span>
        </a>
      </div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener("click", (e)=>{ if(e.target===overlay) closeActionSheet(); });
  }
  requestAnimationFrame(()=> overlay.classList.add("show"));
}
function closeActionSheet(){
  const overlay = document.getElementById("kcSheetOverlay");
  if(overlay) overlay.classList.remove("show");
}

function toast(msg){
  let t = document.getElementById("kcToast");
  if(!t){
    t = document.createElement("div");
    t.className = "toast";
    t.id = "kcToast";
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(()=> t.classList.remove("show"), 1800);
}

function setNotifBadge(){
  const el = document.getElementById("notifBadge");
  if(!el) return;
  const n = kcUnreadNotif();
  if(n>0){ el.textContent = n>9?'9+':n; el.style.display='flex'; } else { el.style.display='none'; }
}
function setCartBadge(){
  const el = document.getElementById("cartBadge");
  if(!el) return;
  const n = (KC.cart||[]).length;
  if(n>0){ el.textContent = n; el.style.display='flex'; } else { el.style.display='none'; }
}
function setChatBadge(){
  const el = document.getElementById("chatBadgeNav");
  if(!el) return;
  const n = kcUnreadChats();
  if(n>0){ el.textContent = n>9?'9+':n; el.style.display='flex'; } else { el.style.display='none'; }
}

function qs(name){ return new URLSearchParams(location.search).get(name); }

/* যেকোনো এলিমেন্টে data-icon="name" [data-size="20"] বসালে এটা স্বয়ংক্রিয়ভাবে SVG বসিয়ে দেয় */
function mountIcons(root){
  (root||document).querySelectorAll('[data-icon]').forEach(el=>{
    const name = el.getAttribute('data-icon');
    const size = el.getAttribute('data-size') || 20;
    el.innerHTML = icon(name, size);
  });
}

function timeAgoLabel(t){ return t; } // ডেমো ডেটায় আগে থেকেই বাংলা রিলেটিভ টাইম দেয়া আছে

if("serviceWorker" in navigator){
  window.addEventListener("load", ()=>{
    navigator.serviceWorker.register("sw.js").catch(()=>{});
  });
}

function stars(rating){
  const full = Math.round(rating);
  let s = "";
  for(let i=0;i<5;i++){ s += `<span style="opacity:${i<full?1:0.28}">${icon('star',12)}</span>`; }
  return s;
}
