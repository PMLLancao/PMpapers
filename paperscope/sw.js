// PaperScope service worker.
// Pages are network-first so a new build is never hidden behind an old cache;
// the cache is only an offline fallback. Old caches are deleted on activate.
const C = 'paperscope-v8', S = ['./', 'index.html', 'manifest.webmanifest', 'icon.svg'];
self.addEventListener('install', e => { self.skipWaiting(); e.waitUntil(caches.open(C).then(c => c.addAll(S))); });
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok && new URL(e.request.url).origin === location.origin) { const x = r.clone(); caches.open(C).then(c => c.put(e.request, x)); }
    return r;
  }).catch(() => caches.match(e.request)));
});
