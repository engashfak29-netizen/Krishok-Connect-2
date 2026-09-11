/* Krishok Connect — সার্ভিস ওয়ার্কার (অফলাইন সাপোর্ট + PWA ইনস্টলযোগ্যতা) */

const CACHE_NAME = "krishok-connect-v1";
const APP_SHELL = [
  "./", "./index.html", "./marketplace.html", "./chat.html", "./chat-room.html",
  "./profile.html", "./post.html", "./product.html", "./cart.html",
  "./create-post.html", "./sell-product.html", "./notifications.html",
  "./search.html", "./edit-profile.html", "./settings.html", "./ai.html",
  "./market-prices.html",
  "./style.css", "./icons.js", "./app-data.js", "./app-common.js",
  "./index.js", "./marketplace.js", "./chat.js", "./chat-room.js",
  "./profile.js", "./post.js", "./product.js", "./create-post.js",
  "./sell-product.js", "./search.js", "./ai.js",
  "./ai-data-loader.js", "./ai-search-engine.js", "./ai-fallback-data.js",
  "./manifest.json", "./icons/icon-192.png", "./icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL).catch(()=>{})));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = event.request.url;
  if (url.includes("docs.google.com") || url.includes("unsplash.com")) {
    event.respondWith(fetch(event.request).catch(() => new Response("", { status: 503 })));
    return;
  }
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((res) => {
        const resClone = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, resClone));
        return res;
      }).catch(() => cached);
    })
  );
});
