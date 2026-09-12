/* =========================================================================
   Krishok Connect — ডেটা স্টোর (ডেমো ডেটা + localStorage পার্সিস্টেন্স)
   একটা সোস্যাল + মার্কেটপ্লেস + AI কৃষি অ্যাপের মক ব্যাকএন্ড হিসেবে কাজ করে।
   ========================================================================= */

const KC_KEY = "kc_state_v1";
const ME = "u1";

const KC_SEED = {
  currentUserId: ME,
  users: {
    u1: { id:"u1", name:"আব্দুল কাদের", type:"farmer", verified:false, avatar:"https://images.unsplash.com/photo-1601412436009-d964bd02edbc?w=200&h=200&fit=crop", cover:"https://images.unsplash.com/photo-1500651230702-0e2d8a49d4ad?w=900&h=400&fit=crop", location:"রংপুর সদর, রংপুর", phone:"01711-223344", email:"abdul.kader@gmail.com", bio:"বেগুন ও ধান চাষী। ১২ বছর ধরে কৃষিকাজে যুক্ত।", followers:340, following:120, rating:4.6, ratingCount:58 },
    u2: { id:"u2", name:"রফিকুল ইসলাম", type:"farmer", verified:false, avatar:"https://images.unsplash.com/photo-1633332755192-727a05c4013d?w=200&h=200&fit=crop", location:"পীরগঞ্জ, রংপুর", phone:"01822-334455", email:"rafiqul.islam@gmail.com", bio:"টমেটো ও শসা চাষী।", followers:120, following:80, rating:4.8, ratingCount:34 },
    u3: { id:"u3", name:"গ্রিন নার্সারি", type:"business", verified:true, avatar:"https://images.unsplash.com/photo-1524863479829-916d8e77f114?w=200&h=200&fit=crop", cover:"https://images.unsplash.com/photo-1585320806297-9794b3e4eeae?w=900&h=400&fit=crop", location:"রংপুর সদর, রংপুর", phone:"01712-345678", email:"green.nursery@gmail.com", bio:"সাধারণত ১ ঘন্টার মধ্যে রিপ্লাই দেন। খোলা আছে (সকাল ৬টা - রাত ৮টা)।", followers:2500, following:120, rating:4.9, ratingCount:320, posts:150, hours:"সকাল ৬টা - রাত ৮টা" },
    u4: { id:"u4", name:"কৃষক বন্ধু গ্রুপ", type:"group", verified:false, avatar:"https://images.unsplash.com/photo-1500937386664-56d1dfef3854?w=200&h=200&fit=crop", location:"রংপুর বিভাগ", phone:"", email:"", bio:"রংপুর অঞ্চলের কৃষকদের সম্মিলিত গ্রুপ।", followers:980, following:0, rating:4.5, ratingCount:12 },
    u5: { id:"u5", name:"মোঃ জাকির হোসেন", type:"farmer", verified:false, avatar:"https://images.unsplash.com/photo-1531384441138-2736e62e0919?w=200&h=200&fit=crop", location:"মিঠাপুকুর, রংপুর", phone:"01911-556677", email:"", bio:"শসা ও সবজি চাষী।", followers:60, following:40, rating:4.7, ratingCount:19 },
    u6: { id:"u6", name:"কৃষি পরামর্শক", type:"expert", verified:true, avatar:"https://images.unsplash.com/photo-1622253692010-333f2da6031d?w=200&h=200&fit=crop", location:"কৃষি সম্প্রসারণ অধিদপ্তর, রংপুর", phone:"01633-778899", email:"agri.expert@gov.bd", bio:"সরকারি কৃষি সম্প্রসারণ কর্মকর্তা। বিনামূল্যে পরামর্শ দিয়ে থাকি।", followers:1500, following:20, rating:4.9, ratingCount:210 },
    u7: { id:"u7", name:"আব্দুল্লাহ আল মামুন", type:"farmer", verified:false, avatar:"https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=200&h=200&fit=crop", location:"বদরগঞ্জ, রংপুর", phone:"", email:"", bio:"", followers:30, following:22, rating:4.4, ratingCount:9 },
    u8: { id:"u8", name:"সাইফুল ইসলাম", type:"farmer", verified:false, avatar:"https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=200&h=200&fit=crop", location:"তারাগঞ্জ, রংপুর", phone:"", email:"", bio:"", followers:15, following:18, rating:4.2, ratingCount:5 },
    u9: { id:"u9", name:"কৃষি বাজার", type:"business", verified:true, avatar:"https://images.unsplash.com/photo-1560493676-04071c5f467b?w=200&h=200&fit=crop", location:"রংপুর সদর, রংপুর", phone:"01555-112233", email:"", bio:"সার, বীজ ও কীটনাশকের পাইকারি ও খুচরা বিক্রেতা।", followers:640, following:5, rating:4.6, ratingCount:140 },
  },

  posts: [
    { id:"p1", userId:"u1", time:"২ ঘন্টা আগে", text:"আমার বেগুন গাছের ফলন এ বছর অনেক ভালো হয়েছে। আলহামদুলিল্লাহ! সবাই দোয়া করবেন।", images:["https://images.unsplash.com/photo-1659261200833-ec8761558af7?w=600&h=450&fit=crop","https://images.unsplash.com/photo-1615485500834-bc10199bc727?w=600&h=450&fit=crop","https://images.unsplash.com/photo-1618512496248-a07fe83aa8cb?w=600&h=450&fit=crop"], likes:256, comments:[{userId:"u2",text:"মাশাল্লাহ ভাই, দাম কত পড়লো প্রতি কেজি?",time:"১ ঘন্টা আগে"},{userId:"u5",text:"অনেক সুন্দর ফলন হয়েছে!",time:"৪৫ মিনিট আগে"}], shares:15, liked:false },
    { id:"p2", userId:"u3", time:"৪ ঘন্টা আগে", text:"নতুন জাতের টমেটো চারা এসেছে 🌱 উচ্চ ফলনশীল, রোগ প্রতিরোধী জাত। স্টক সীমিত, আগে আসলে আগে পাবেন।", images:["https://images.unsplash.com/photo-1592841200221-a6898f307baa?w=600&h=450&fit=crop","https://images.unsplash.com/photo-1524593689594-aae2f26b75ab?w=600&h=450&fit=crop"], likes:128, comments:[{userId:"u7",text:"দাম কত পিস?",time:"৩ ঘন্টা আগে"}], shares:8, liked:true },
    { id:"p3", userId:"u6", time:"গতকাল", text:"⚠️ আবহাওয়া সতর্কতা: আগামী ৩ দিন হালকা থেকে মাঝারি বৃষ্টির সম্ভাবনা আছে। এই সময় কীটনাশক স্প্রে করা থেকে বিরত থাকুন, বৃষ্টিতে ধুয়ে যাবে।", images:[], likes:412, comments:[{userId:"u1",text:"ধন্যবাদ স্যার, সময়মতো জানানোর জন্য।",time:"২২ ঘন্টা আগে"},{userId:"u8",text:"আমার ধান ক্ষেতের জন্য কি করণীয়?",time:"২০ ঘন্টা আগে"}], shares:64, liked:false },
    { id:"p4", userId:"u2", time:"গতকাল", text:"শসা ক্ষেতে সাদা মাছি দেখা যাচ্ছে। কেউ কি ভালো সমাধান জানেন? জৈব উপায়ে দমন করতে চাই।", images:["https://images.unsplash.com/photo-1449300079323-02e209d9d3a6?w=600&h=450&fit=crop"], likes:34, comments:[{userId:"u6",text:"হলুদ আঠালো ফাঁদ ব্যবহার করুন, এবং নিমতেল স্প্রে করতে পারেন সপ্তাহে ২ বার।",time:"১৮ ঘন্টা আগে"}], shares:3, liked:false },
    { id:"p5", userId:"u4", time:"২ দিন আগে", text:"আগামীকাল বিকাল ৪টায় ইউনিয়ন পরিষদ মাঠে কৃষক বন্ধু গ্রুপের মাসিক মিটিং। সবাই সময়মতো আসবেন, নতুন সার ভর্তুকির বিষয়ে আলোচনা হবে।", images:[], likes:89, comments:[{userId:"u1",text:"সবাই সবাইকে জানিয়ে দিন প্লিজ।",time:"১ দিন আগে"}], shares:22, liked:false },
    { id:"p6", userId:"u5", time:"৩ দিন আগে", text:"এই বছর ধানের বীজতলা তৈরি করলাম। আশা করছি ভালো ফলন হবে ইনশাআল্লাহ।", images:["https://images.unsplash.com/photo-1536657464919-892534685dd6?w=600&h=450&fit=crop","https://images.unsplash.com/photo-1500595046743-cd271d694d30?w=600&h=450&fit=crop"], likes:71, comments:[], shares:5, liked:false },
  ],

  products: [
    { id:"pr1", sellerId:"u2", name:"টমেটো", price:"৳ ৬০ / কেজি", category:"সবজি", distanceKm:2.5, rating:4.8, location:"পীরগঞ্জ, রংপুর", images:["https://images.unsplash.com/photo-1592924357228-91a4daadcfad?w=500&h=400&fit=crop"], description:"তাজা দেশি জাতের টমেটো, নিজের ক্ষেতের ফসল। বাজারের চেয়ে কম দামে সরাসরি কৃষক থেকে।", stock:"৫০ কেজি মজুদ আছে" },
    { id:"pr2", sellerId:"u5", name:"শসা", price:"৳ ৪০ / কেজি", category:"সবজি", distanceKm:1.8, rating:4.7, location:"মিঠাপুকুর, রংপুর", images:["https://images.unsplash.com/photo-1449300079323-02e209d9d3a6?w=500&h=400&fit=crop"], description:"একদম তাজা শসা, সকালে তোলা। কীটনাশক কম ব্যবহার করা হয়েছে।", stock:"৩০ কেজি মজুদ আছে" },
    { id:"pr3", sellerId:"u3", name:"টমেটো চারা", price:"৳ ৫ / টি", category:"চারা", distanceKm:3.2, rating:4.9, location:"রংপুর সদর, রংপুর", images:["https://images.unsplash.com/photo-1524593689594-aae2f26b75ab?w=500&h=400&fit=crop","https://images.unsplash.com/photo-1592841200221-a6898f307baa?w=500&h=400&fit=crop"], description:"উচ্চ ফলনশীল, রোগ প্রতিরোধী হাইব্রিড জাতের টমেটো চারা। নার্সারিতে সরাসরি সংগ্রহ করা যাবে।", stock:"২০০০+ চারা আছে" },
    { id:"pr4", sellerId:"u9", name:"ডিএপি সার", price:"৳ ১৩৫০ / বস্তা", category:"সার", distanceKm:2.1, rating:4.6, location:"রংপুর সদর, রংপুর", images:["https://images.unsplash.com/photo-1592982537447-7440770cbfc9?w=500&h=400&fit=crop"], description:"সরকার অনুমোদিত ডিএপি সার, ৫০ কেজি বস্তা। পাইকারি দামে পাওয়া যাচ্ছে।", stock:"বেশি পরিমাণে মজুদ আছে" },
    { id:"pr5", sellerId:"u9", name:"বেগুন বীজ", price:"৳ ৮০ / প্যাকেট", category:"বীজ", distanceKm:2.1, rating:4.5, location:"রংপুর সদর, রংপুর", images:["https://images.unsplash.com/photo-1659261200833-ec8761558af7?w=500&h=400&fit=crop"], description:"উন্নত জাতের হাইব্রিড বেগুন বীজ, রোগ প্রতিরোধী।", stock:"১০০+ প্যাকেট আছে" },
    { id:"pr6", sellerId:"u1", name:"বেগুন", price:"৳ ৩৫ / কেজি", category:"সবজি", distanceKm:0.8, rating:4.6, location:"রংপুর সদর, রংপুর", images:["https://images.unsplash.com/photo-1615485500834-bc10199bc727?w=500&h=400&fit=crop"], description:"নিজের ক্ষেতের তাজা বেগুন, কীটনাশক মুক্ত পদ্ধতিতে চাষ করা।", stock:"৪০ কেজি মজুদ আছে" },
    { id:"pr7", sellerId:"u3", name:"পাওয়ার টিলার", price:"৳ ৪৫,০০০", category:"যন্ত্রপাতি", distanceKm:3.2, rating:4.7, location:"রংপুর সদর, রংপুর", images:["https://images.unsplash.com/photo-1591638246532-fb8a1a5cc3bb?w=500&h=400&fit=crop"], description:"নতুন পাওয়ার টিলার, ওয়ারেন্টিসহ। ডেমো দেখানো হয়।", stock:"স্টকে আছে" },
    { id:"pr8", sellerId:"u9", name:"কীটনাশক স্প্রেয়ার", price:"৳ ১,২০০", category:"যন্ত্রপাতি", distanceKm:2.1, rating:4.4, location:"রংপুর সদর, রংপুর", images:["https://images.unsplash.com/photo-1585320806297-9794b3e4eeae?w=500&h=400&fit=crop"], description:"১৬ লিটার হ্যান্ড স্প্রেয়ার, হালকা ও টেকসই।", stock:"স্টকে আছে" },
  ],

  chats: [
    { id:"c1", userId:"u2", unread:2, lastMsg:"টমেটো কত কেজি লাগবে?", lastFrom:"them", time:"১০:৩০ AM" },
    { id:"c2", userId:"u3", unread:1, lastMsg:"চারা কাল পাঠিয়ে দেবো", lastFrom:"them", time:"১০:১৫ AM" },
    { id:"c3", userId:"u4", unread:0, lastMsg:"আব্দুল: সবাই কাল মিটিং এ আসবেন", lastFrom:"them", time:"৯:৪৫ AM" },
    { id:"c4", userId:"u5", unread:0, lastMsg:"ঠিক আছে ভাই, ধন্যবাদ", lastFrom:"me", time:"৯:২০ AM" },
    { id:"c5", userId:"u6", unread:0, lastMsg:"গাছের ছবি পাঠান, দেখে বলছি", lastFrom:"them", time:"৮:৫০ AM" },
    { id:"c6", userId:"u7", unread:0, lastMsg:"ধন্যবাদ ভাই", lastFrom:"them", time:"গতকাল" },
    { id:"c7", userId:"u8", unread:0, lastMsg:"ঠিক আছে, যোগাযোগ করছি", lastFrom:"me", time:"গতকাল" },
  ],

  messages: {
    c1: [
      { from:"them", text:"সালাম ভাই, আপনার টমেটোর পোস্ট দেখলাম", time:"১০:১৫ AM" },
      { from:"them", text:"টমেটো কত কেজি লাগবে?", time:"১০:৩০ AM" },
    ],
    c2: [
      { from:"me", text:"আসসালামু আলাইকুম, টমেটো চারা লাগবে ৫০ পিস", time:"১০:০৫ AM" },
      { from:"them", text:"ওয়ালাইকুম আসসালাম, ঠিক আছে ব্যবস্থা করছি", time:"১০:১০ AM" },
      { from:"them", text:"চারা কাল পাঠিয়ে দেবো", time:"১০:১৫ AM" },
    ],
    c3: [ { from:"them", text:"আব্দুল: সবাই কাল মিটিং এ আসবেন", time:"৯:৪৫ AM" } ],
    c4: [
      { from:"them", text:"ভাই ধানের বীজ পেয়েছেন?", time:"৯:১৫ AM" },
      { from:"me", text:"ঠিক আছে ভাই, ধন্যবাদ", time:"৯:২০ AM" },
    ],
    c5: [
      { from:"me", text:"স্যার আমার মরিচ গাছের পাতা কুঁকড়ে যাচ্ছে", time:"৮:৪০ AM" },
      { from:"them", text:"গাছের ছবি পাঠান, দেখে বলছি", time:"৮:৫০ AM" },
    ],
    c6: [ { from:"them", text:"ধন্যবাদ ভাই", time:"গতকাল" } ],
    c7: [ { from:"me", text:"ঠিক আছে, যোগাযোগ করছি", time:"গতকাল" } ],
  },

  notifications: [
    { id:"n1", text:"রফিকুল ইসলাম আপনার পোস্টে মন্তব্য করেছেন", time:"১ ঘন্টা আগে", read:false },
    { id:"n2", text:"গ্রিন নার্সারি আপনাকে অনুসরণ করা শুরু করেছেন", time:"৩ ঘন্টা আগে", read:false },
    { id:"n3", text:"কৃষি পরামর্শক একটি গুরুত্বপূর্ণ সতর্কতা পোস্ট করেছেন", time:"গতকাল", read:false },
    { id:"n4", text:"আপনার পণ্য \"বেগুন\" এ নতুন অর্ডার এসেছে", time:"২ দিন আগে", read:true },
    { id:"n5", text:"মোঃ জাকির হোসেন আপনার পোস্ট শেয়ার করেছেন", time:"৩ দিন আগে", read:true },
  ],

  marketPrices: [
    { name:"টমেটো", price:"৳ ৬০/কেজি", change:5, emoji:"🍅" },
    { name:"শসা", price:"৳ ৪০/কেজি", change:-3, emoji:"🥒" },
    { name:"বেগুন", price:"৳ ৩৫/কেজি", change:2, emoji:"🍆" },
    { name:"লাউ", price:"৳ ২৫/কেজি", change:1, emoji:"🥬" },
    { name:"ধান", price:"৳ ১২৮০/মণ", change:4, emoji:"🌾" },
    { name:"আলু", price:"৳ ২২/কেজি", change:-1, emoji:"🥔" },
  ],

  categories: [
    { key:"সবজি", label:"সবজি", icon:"🍅" },
    { key:"চারা", label:"চারা", icon:"🌱" },
    { key:"বীজ", label:"বীজ", icon:"🌾" },
    { key:"সার", label:"সার", icon:"🧪" },
    { key:"যন্ত্রপাতি", label:"যন্ত্রপাতি", icon:"🚜" },
    { key:"প্রাণিসম্পদ", label:"প্রাণিসম্পদ", icon:"🐄" },
    { key:"কীটনাশক", label:"কীটনাশক", icon:"🧴" },
    { key:"অন্যান্য", label:"অন্যান্য", icon:"⋯" },
  ],

  aiChats: [],
};

function kcLoad(){
  try{
    const raw = localStorage.getItem(KC_KEY);
    if(raw){
      const parsed = JSON.parse(raw);
      // seed-এ নতুন কিছু যোগ হলেও পুরনো সেভ করা স্টেট ভাঙবে না
      return Object.assign({}, JSON.parse(JSON.stringify(KC_SEED)), parsed);
    }
  }catch(e){ console.warn("kc state load ব্যর্থ", e); }
  return JSON.parse(JSON.stringify(KC_SEED));
}
function kcSave(){ localStorage.setItem(KC_KEY, JSON.stringify(KC)); }

let KC = kcLoad();

function kcUser(id){ return KC.users[id] || KC.users[ME]; }
function kcMe(){ return KC.users[KC.currentUserId]; }
function kcPost(id){ return KC.posts.find(p=>p.id===id); }
function kcProduct(id){ return KC.products.find(p=>p.id===id); }
function kcChat(id){ return KC.chats.find(c=>c.id===id); }
function kcUnreadNotif(){ return KC.notifications.filter(n=>!n.read).length; }
function kcUnreadChats(){ return KC.chats.reduce((s,c)=>s+c.unread,0); }

/* ================= Backend sync layer ================= */
function kcNormalizePost(p){
  return {id:p.id,userId:p.user_id,text:p.text,images:p.images||[],likes:p.likes||0,shares:p.shares||0,liked:!!p.liked,time:p.created_at?new Date(p.created_at).toLocaleString('bn-BD',{hour:'numeric',minute:'2-digit'}):'এখন',comments:(p.comments||[]).map(c=>({id:c.id,userId:c.user_id,name:c.name,avatar:c.avatar,text:c.text,time:c.created_at?new Date(c.created_at).toLocaleString('bn-BD',{hour:'numeric',minute:'2-digit'}):'এখন'}))};
}
function kcNormalizeProduct(p){
  return {id:p.id,sellerId:p.seller_id,name:p.name,price:'৳ '+Number(p.price).toLocaleString('bn-BD')+(p.unit?' / '+p.unit:''),priceValue:Number(p.price),unit:p.unit||'piece',category:p.category||'অন্যান্য',stockValue:Number(p.stock||0),stock:p.stock!=null?`${Number(p.stock).toLocaleString('bn-BD')} ${p.unit||''} মজুদ আছে`:'',location:p.location||'',description:p.description||'',images:p.images||[],rating:p.rating||0,ratingCount:p.rating_count||0,seller:p.seller};
}
async function kcSyncFromBackend(){
  if(!KC_API.token()) return false;
  const [me,posts,products,cart,notifs,convs,prices]=await Promise.all([
    KC_API.get('/api/v1/auth/me'),KC_API.get('/api/v1/posts?limit=100'),KC_API.get('/api/v1/products?limit=100'),KC_API.get('/api/v1/cart'),KC_API.get('/api/v1/notifications'),KC_API.get('/api/v1/conversations'),KC_API.get('/api/v1/market-prices?limit=100')
  ]);
  const users={};
  users[me.id]=me;
  posts.forEach(p=>{if(p.user)users[p.user.id]=p.user;(p.comments||[]).forEach(c=>{if(c.user_id&&!users[c.user_id])users[c.user_id]={id:c.user_id,name:c.name,avatar:c.avatar};});});
  products.forEach(p=>{if(p.seller)users[p.seller.id]=p.seller;});
  convs.forEach(c=>(c.members||[]).forEach(m=>users[m.id]=users[m.id]||m));
  const chats=[]; const messages={};
  for(const c of convs){
    const peer=(c.members||[]).find(m=>m.id!==me.id);
    let msgs=[]; try{msgs=await KC_API.get('/api/v1/conversations/'+c.id+'/messages');}catch{}
    const last=msgs[msgs.length-1];
    chats.push({id:c.id,userId:peer?.id,unread:0,lastMsg:last?.text||'',lastFrom:last?.sender_id===me.id?'me':'them',time:last?.created_at?'এখন':''});
    messages[c.id]=msgs.map(m=>({id:m.id,from:m.sender_id===me.id?'me':'them',text:m.text||'',time:m.created_at?'এখন':''}));
  }
  KC.currentUserId=me.id; users[me.id]=me;
  KC.users=users; KC.posts=posts.map(kcNormalizePost); KC.products=products.map(kcNormalizeProduct); KC.chats=chats; KC.messages=messages;
  KC.cart=(cart.items||[]).map(x=>({productId:x.product_id,quantity:x.quantity,subtotal:x.subtotal}));
  KC.notifications=(notifs||[]).map(n=>({id:n.id,text:n.text,time:'এখন',read:!!n.read,kind:n.kind}));
  KC.marketPrices=(prices||[]).map(p=>({name:p.crop,price:'৳ '+Number(p.price).toLocaleString('bn-BD')+'/'+(p.unit||'kg'),change:0,emoji:'🌾'}));
  window.dispatchEvent(new Event('kc:ready'));
  return true;
}
const kcReady=(async()=>{
  if(location.pathname.endsWith('auth.html')) return true;
  if(!KC_API.token()){ location.href='auth.html'; return false; }
  try{return await kcSyncFromBackend();}
  catch(e){ console.error(e); console.warn('সার্ভারের সাথে সংযোগ করা যাচ্ছে না'); setTimeout(()=>{if(!location.pathname.endsWith('auth.html')) location.href='auth.html'},0); return false; }
})();
window.kcReady=kcReady;
