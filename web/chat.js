/* ============ চ্যাট লিস্ট পেজ লজিক ============ */
document.addEventListener("DOMContentLoaded", async () => {
  await kcReady; if (!KC.currentUserId) return; mountIcons(); renderBottomNav("chat");
  const list=document.getElementById("chatList");
  try {
    const rows=await KC_API.get('/api/v1/conversations');
    if(!rows.length){list.innerHTML=`<div class="empty-state"><div class="empty-emoji">💬</div><div class="empty-title">কোনো চ্যাট নেই</div><div class="empty-text">কোনো পণ্য বা পোস্টে মেসেজ পাঠিয়ে কথোপকথন শুরু করুন</div></div>`;return;}
    list.innerHTML=rows.map(c=>{const u=(c.members||[]).find(m=>m.id!==KC.currentUserId)||(c.members||[])[0]||{};return `<a href="chat-room.html?id=${encodeURIComponent(c.id)}" class="chat-row"><img class="avatar avatar-52" src="${u.avatar||'icons/icon-192.png'}" alt=""><div style="flex:1;min-width:0"><div class="chat-name">${escapeHtml(u.name||'ব্যবহারকারী')}</div><div class="chat-preview">কথোপকথন খুলুন</div></div><div class="chat-side"><div class="chat-time">${escapeHtml(c.created_at||'')}</div></div></a>`}).join('');
  } catch(e){ list.innerHTML=`<div class="empty-state"><div class="empty-title">চ্যাট লোড করা যায়নি</div><div class="empty-text">${escapeHtml(e.message||'আবার চেষ্টা করুন')}</div></div>`; }
});
