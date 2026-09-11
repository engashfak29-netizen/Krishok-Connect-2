// Optional browser adapter for the existing Krishok Connect frontend.
// Set window.KC_API_URL before loading this file, or use the default local API.
window.KC_API_URL = window.KC_API_URL || 'http://127.0.0.1:8000/api/v1';
window.KCAuth = {
  get token(){ return localStorage.getItem('kc_access_token'); },
  set token(v){ v ? localStorage.setItem('kc_access_token',v) : localStorage.removeItem('kc_access_token'); },
  async request(path, options={}){
    const headers = new Headers(options.headers || {});
    if(options.body && !(options.body instanceof FormData)) headers.set('Content-Type','application/json');
    if(this.token) headers.set('Authorization','Bearer '+this.token);
    const r = await fetch(window.KC_API_URL+path,{...options,headers,body:options.body && !(options.body instanceof FormData) ? JSON.stringify(options.body) : options.body});
    const data = await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(data.detail || 'API request failed');
    return data;
  },
  register(data){ return this.request('/auth/register',{method:'POST',body:data}).then(x=>(this.token=x.access_token,x)); },
  login(identifier,password){ return this.request('/auth/login',{method:'POST',body:{identifier,password}}).then(x=>(this.token=x.access_token,x)); },
  me(){ return this.request('/auth/me'); },
  logout(){ return this.request('/auth/logout',{method:'POST'}).finally(()=>this.token=null); },
  posts(params=''){ return this.request('/posts'+(params?'?'+params:'')); },
  products(params=''){ return this.request('/products'+(params?'?'+params:'')); },
  cart(){ return this.request('/cart'); },
  orders(){ return this.request('/orders'); },
  notifications(){ return this.request('/notifications'); },
  changePassword(current_password,new_password){ return this.request('/auth/change-password',{method:'POST',body:{current_password,new_password}}); },
  deleteAccount(){ return this.request('/auth/account',{method:'DELETE'}).finally(()=>this.token=null); },
  reviews(productId){ return this.request('/products/'+encodeURIComponent(productId)+'/reviews'); },
  addReview(productId,rating,comment){ return this.request('/products/'+encodeURIComponent(productId)+'/reviews',{method:'POST',body:{rating,comment}}); },
  sellerOrders(){ return this.request('/seller/orders'); },
  order(id){ return this.request('/orders/'+encodeURIComponent(id)); },
  adminStats(){ return this.request('/admin/stats'); },
  adminUsers(){ return this.request('/admin/users'); },
  adminReports(){ return this.request('/admin/reports'); }
};
