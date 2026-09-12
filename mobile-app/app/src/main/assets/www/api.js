/* Krishok Connect API client — single frontend/backend connection layer */
(function(){
  function resolveBase(){
    const configured = (window.KC_API_BASE || localStorage.getItem('KC_API_BASE') || '').trim();
    if(configured) return configured.replace(/\/$/,'');
    if(location.protocol === 'http:' || location.protocol === 'https:') return location.origin;
    return 'http://127.0.0.1:8000';
  }

  window.KC_API_BASE = resolveBase();

  const KC_API = {
    token(){ return localStorage.getItem('kc_access_token') || ''; },
    setToken(t){
      if(t) localStorage.setItem('kc_access_token',t);
      else localStorage.removeItem('kc_access_token');
    },
    async request(path, options={}){
      const headers = new Headers(options.headers || {});
      let body = options.body;
      if(body && typeof body === 'object' && !(body instanceof FormData) && !(body instanceof Blob)){
        headers.set('Content-Type','application/json');
        body = JSON.stringify(body);
      }
      const t=this.token();
      if(t) headers.set('Authorization','Bearer '+t);
      const res=await fetch(resolveBase()+path,{...options,body,headers});
      let data=null;
      try{data=await res.json();}catch{}
      if(!res.ok){
        if(res.status===401){
          this.setToken('');
          if(!location.pathname.endsWith('auth.html') && !location.pathname.endsWith('/login.html')){
            const authPath = location.pathname.includes('/') ? '../auth.html' : 'auth.html';
            location.href=authPath;
          }
        }
        throw new Error(data?.detail||data?.message||'অনুরোধ ব্যর্থ হয়েছে');
      }
      return data;
    },
    get(p){return this.request(p)},
    post(p,b){return this.request(p,{method:'POST',body:b})},
    patch(p,b){return this.request(p,{method:'PATCH',body:b})},
    del(p){return this.request(p,{method:'DELETE'})},
    upload(file){const fd=new FormData();fd.append('file',file);return this.request('/api/v1/media/upload',{method:'POST',body:fd})}
  };

  /* Backward-compatible adapter for management pages already using A(). */
  window.A = function(path, options){ return KC_API.request(path, options || {}); };

  /* Backward-compatible adapter for the older admin UI. */
  window.KCAuth = {
    get token(){ return KC_API.token(); },
    set token(v){ KC_API.setToken(v); },
    request(path, options={}){
      const p=String(path||'');
      return KC_API.request(p.startsWith('/api/')?p:'/api/v1'+(p.startsWith('/')?p:'/'+p), options);
    },
    register(data){ return this.request('/auth/register',{method:'POST',body:data}).then(x=>(this.token=x.access_token,x)); },
    login(identifier,password){ return this.request('/auth/login',{method:'POST',body:{identifier,password}}).then(x=>(this.token=x.access_token,x)); },
    me(){ return this.request('/auth/me'); },
    logout(){ return this.request('/auth/logout',{method:'POST'}).finally(()=>this.token=null); }
  };

  window.KC_API=KC_API;
})();
