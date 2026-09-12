let mode='login';
const $=id=>document.getElementById(id);
function form(){
  const f=$('authForm');
  f.innerHTML=mode==='login'
    ? `<div class="field"><label>ইমেইল / ফোন</label><input id="identifier" required autocomplete="username"></div>
       <div class="field"><label>পাসওয়ার্ড</label><input id="password" type="password" required autocomplete="current-password"></div>
       <button type="submit" class="btn btn-primary btn-full">লগইন করুন</button>`
    : `<div class="field"><label>নাম</label><input id="name" required></div>
       <div class="field"><label>ইমেইল / ফোন</label><input id="contact" required></div>
       <div class="field"><label>পাসওয়ার্ড</label><input id="password" type="password" minlength="8" required></div>
       <div class="field"><label>অ্যাকাউন্ট ধরন</label><select id="type"><option value="farmer">কৃষক</option><option value="business">ব্যবসা</option><option value="expert">বিশেষজ্ঞ</option></select></div>
       <button type="submit" class="btn btn-primary btn-full">রেজিস্টার করুন</button>`;
  $('authForm').onsubmit=submit;
}
$('loginTab').onclick=()=>{mode='login';$('loginTab').className='btn btn-primary';$('registerTab').className='btn btn-outline';form()};
$('registerTab').onclick=()=>{mode='register';$('registerTab').className='btn btn-primary';$('loginTab').className='btn btn-outline';form()};
async function submit(e){
  e.preventDefault();
  const msg=$('authMsg'); msg.textContent='';
  try{
    let d;
    if(mode==='login'){
      d=await KC_API.post('/api/v1/auth/login',{
        identifier:$('identifier').value.trim(),
        password:$('password').value
      });
    }else{
      const c=$('contact').value.trim();
      const password=$('password').value;
      if(password.length<8) throw new Error('পাসওয়ার্ড কমপক্ষে ৮ অক্ষরের হতে হবে');
      d=await KC_API.post('/api/v1/auth/register',{
        name:$('name').value.trim(),
        email:c.includes('@')?c:null,
        phone:c.includes('@')?null:c,
        password,
        type:$('type').value
      });
    }
    KC_API.setToken(d.access_token);
    location.href=(d.user?.type&&['farmer','business','expert'].includes(d.user.type))?'user/':'index.html';
  }catch(err){
    msg.textContent=err.message||'অনুরোধ ব্যর্থ হয়েছে';
    msg.style.color='var(--red)';
  }
}
form();
