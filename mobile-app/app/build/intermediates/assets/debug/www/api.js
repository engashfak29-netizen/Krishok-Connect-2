/* Krishok Connect API client */
window.KC_API_BASE = window.KC_API_BASE || localStorage.getItem('KC_API_BASE') || ((location.protocol === 'http:' || location.protocol === 'https:') ? location.origin : 'http://127.0.0.1:8000');
const KC_API = {
  token(){ return localStorage.getItem('kc_access_token') || ''; },
  setToken(t){ t ? localStorage.setItem('kc_access_token',t) : localStorage.removeItem('kc_access_token'); },
  async request(path, options={}){
    const headers = new Headers(options.headers || {});
    if(options.body && typeof options.body === 'object' && !(options.body instanceof FormData)){
      headers.set('Content-Type','application/json'); options.body=JSON.stringify(options.body);
    }
    const t=this.token(); if(t) headers.set('Authorization','Bearer '+t);
    const res=await fetch(window.KC_API_BASE+path,{...options,headers});
    let data=null; try{data=await res.json();}catch{}
    if(!res.ok){ if(res.status===401){this.setToken(''); if(!location.pathname.endsWith('auth.html')) location.href='auth.html';} throw new Error(data?.detail||data?.message||'অনুরোধ ব্যর্থ হয়েছে'); }
    return data;
  },
  get(p){return this.request(p)}, post(p,b){return this.request(p,{method:'POST',body:b})}, patch(p,b){return this.request(p,{method:'PATCH',body:b})}, del(p){return this.request(p,{method:'DELETE'})},
  upload(file){const fd=new FormData();fd.append('file',file);return this.request('/api/v1/media/upload',{method:'POST',body:fd})}
};
window.KC_API=KC_API;
