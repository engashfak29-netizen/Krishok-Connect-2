/* ============ প্রোফাইল পেজ লজিক ============ */
let profileUser, isMe, activeTab = "posts";

document.addEventListener("DOMContentLoaded", async () => {
  await kcReady;
  if (!KC.currentUserId) return;
  mountIcons();
  renderBottomNav("profile");

  const id = qs("id") || KC.currentUserId;
  try { profileUser = await KC_API.get('/api/v1/users/'+encodeURIComponent(id)); } catch(e) { toast(e.message); return; }
  profileUser._following = !!profileUser.following_by_me;
  isMe = profileUser.id === KC.currentUserId;

  document.getElementById("coverImg").src = profileUser.cover || "https://images.unsplash.com/photo-1500651230702-0e2d8a49d4ad?w=900&h=400&fit=crop";
  document.getElementById("avatarImg").src = profileUser.avatar;
  document.getElementById("pName").textContent = profileUser.name;
  document.getElementById("pVerified").innerHTML = profileUser.verified ? `<span class="badge-verified">${icon('verified',16)}</span>` : '';
  document.getElementById("pStars").innerHTML = stars(profileUser.rating);
  document.getElementById("pRatingText").textContent = `${profileUser.rating} (${profileUser.ratingCount} রেটিং)`;
  document.getElementById("pSub").textContent = typeLabel(profileUser.type);

  const myPostCount = KC.posts.filter(p=>p.userId===profileUser.id).length;
  document.getElementById("statPosts").textContent = profileUser.posts || myPostCount;
  document.getElementById("statFollowers").textContent = fmt(profileUser.followers);
  document.getElementById("statFollowing").textContent = fmt(profileUser.following);

  renderInfo();
  renderActions();
  renderOwnerActions();
  renderTabs();

  document.querySelectorAll(".tab-item").forEach(t=>{
    t.addEventListener("click", ()=>{
      document.querySelectorAll(".tab-item").forEach(x=>x.classList.remove("active"));
      t.classList.add("active");
      activeTab = t.getAttribute("data-tab");
      renderTabs();
    });
  });
});

function fmt(n){ if(n>=1000) return (n/1000).toFixed(1).replace(".0","")+"K"; return n; }
function typeLabel(t){ return { farmer:"কৃষক", business:"বিক্রেতা / নার্সারি", group:"কমিউনিটি গ্রুপ", expert:"কৃষি বিশেষজ্ঞ" }[t] || ""; }

function renderInfo(){
  const rows = [];
  if(profileUser.location) rows.push(`<div class="info-row">${icon('location',15)} ${escapeHtml(profileUser.location)}</div>`);
  if(profileUser.phone) rows.push(`<div class="info-row">${icon('phone',15)} ${escapeHtml(profileUser.phone)}</div>`);
  if(profileUser.email) rows.push(`<div class="info-row">${icon('mail',15)} ${escapeHtml(profileUser.email)}</div>`);
  if(profileUser.bio) rows.push(`<div class="info-row highlight">${icon('check',15)} ${escapeHtml(profileUser.bio)}</div>`);
  if(profileUser.hours) rows.push(`<div class="info-row open">${icon('clock',15)} খোলা আছে (${escapeHtml(profileUser.hours)})</div>`);
  document.getElementById("infoList").innerHTML = rows.join("");
}

function renderActions(){
  const el = document.getElementById("actionRow");
  if(isMe){
    el.innerHTML = `<div style="display:flex;gap:8px;width:100%"><a class="btn btn-outline" style="flex:1" href="orders.html">📦 আমার অর্ডার</a><a class="btn btn-outline" style="flex:1" href="seller-dashboard.html">🏪 বিক্রেতা</a><a class="btn btn-outline" style="flex:1" href="edit-profile.html">${icon('edit',16)}&nbsp;প্রোফাইল এডিট করুন</a></div>`;
    return;
  }
  el.innerHTML = `
    <button class="btn btn-primary" id="msgBtn">${icon('chat',16)}&nbsp;মেসেজ</button>
    <button class="btn btn-outline" id="followBtn">${profileUser._following ? 'ফলো করা হচ্ছে' : 'ফলো করুন'}</button>
  `;
  document.getElementById("msgBtn").addEventListener("click", async()=>{ try { const c=await KC_API.post('/api/v1/conversations?user_id='+encodeURIComponent(profileUser.id)); location.href='chat-room.html?id='+c.id; } catch(e){toast(e.message)} });
  document.getElementById("followBtn").addEventListener("click", async(e)=>{ try { const r=await KC_API.post('/api/v1/users/'+encodeURIComponent(profileUser.id)+'/follow'); profileUser._following=r.following; e.target.textContent=r.following?'ফলো করা হচ্ছে':'ফলো করুন'; toast(r.following?'ফলো করা হয়েছে':'আনফলো করা হয়েছে'); } catch(err){toast(err.message)} });
}

function renderOwnerActions(){
  const el = document.getElementById("ownerActions");
  if(isMe){
    el.innerHTML = `<a class="icon-btn" href="settings.html">${icon('gear',18)}</a>`;
  } else {
    el.innerHTML = `<button class="icon-btn" id="reportProfileBtn">${icon('more',18)}</button>`;
    document.getElementById('reportProfileBtn').onclick=async()=>{const reason=prompt('রিপোর্টের কারণ লিখুন');if(!reason)return;try{await KC_API.post('/api/v1/reports',{target_type:'user',target_id:profileUser.id,reason});toast('রিপোর্ট পাঠানো হয়েছে')}catch(e){toast(e.message)}};
  }
}

function renderTabs(){
  const el = document.getElementById("tabContent");
  if(activeTab === "posts"){
    const myPosts = KC.posts.filter(p=>p.userId===profileUser.id);
    if(myPosts.length===0){ el.innerHTML = emptyBlock("📝","কোনো পোস্ট নেই"); return; }
    el.innerHTML = `<div class="feed" style="padding-top:14px;">${myPosts.map(postCardMini).join("")}</div>`;
  } else if(activeTab === "products"){
    const myProducts = KC.products.filter(p=>p.sellerId===profileUser.id);
    if(myProducts.length===0){ el.innerHTML = emptyBlock("🛍️","কোনো পণ্য যোগ করা হয়নি"); return; }
    el.innerHTML = `<div class="product-grid">${myProducts.map(p=>`
      <a class="product-card" href="product.html?id=${p.id}">
        <div class="product-img-wrap"><img src="${p.images[0]}" alt=""></div>
        <div class="product-body">
          <div class="product-name">${escapeHtml(p.name)}</div>
          <div class="product-price">${escapeHtml(p.price)}</div>
        </div>
      </a>`).join("")}</div>`;
  } else {
    el.innerHTML = `<div class="section">
      <div class="card" style="padding:14px;">
        <div style="font-size:13px; line-height:1.7; color:var(--ink);">${escapeHtml(profileUser.bio || 'কোনো তথ্য যোগ করা হয়নি।')}</div>
      </div>
    </div>`;
  }
}

function emptyBlock(emoji, title){
  return `<div class="empty-state"><div class="empty-emoji">${emoji}</div><div class="empty-title">${title}</div></div>`;
}

function postCardMini(post){
  const u = kcUser(post.userId);
  const imgClass = post.images.length>=3 ? 'n3' : (post.images.length===2?'n2':'n1');
  const imgs = post.images.length ? `<div class="post-images ${imgClass}">${post.images.slice(0,3).map(i=>`<img src="${i}" alt="">`).join("")}</div>` : ""; const vids=(post.videos||[]).map(v=>`<video src="${v}" controls playsinline style="width:100%;max-height:420px;border-radius:12px;background:#111"></video>`).join("");
  return `<a class="post-card" href="post.html?id=${post.id}" style="display:block;">
      <div class="post-head"><img class="avatar avatar-36" src="${u.avatar}" alt=""><div><div class="post-name">${escapeHtml(u.name)}</div><div class="post-meta">${post.time}</div></div></div>
      <div class="post-text">${escapeHtml(post.text)}</div>
      ${imgs}
      ${vids}
      <div class="post-stats">
        <div class="post-stat">${icon('heart',15)} ${post.likes}</div>
        <div class="post-stat">${icon('comment',15)} ${post.comments.length}</div>
        <div class="post-stat">${icon('share',15)} ${post.shares}</div>
      </div>
    </a>`;
}
