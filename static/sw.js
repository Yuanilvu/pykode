/* PyKode — Service Worker (PWA): cache static, network-first untuk halaman */
var CACHE = 'pykode-v2';

self.addEventListener('install', function (e) {
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; })
        .map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  var url = new URL(e.request.url);
  // Aset statis: cache dulu, kalau ada pakai cache (cepat).
  if (url.pathname.indexOf('/static/') !== -1) {
    e.respondWith(
      caches.match(e.request).then(function (hit) {
        return hit || fetch(e.request).then(function (res) {
          var clone = res.clone();
          caches.open(CACHE).then(function (c) { c.put(e.request, clone); });
          return res;
        });
      })
    );
    return;
  }
  // Halaman: network dulu, fallback cache kalau offline.
  e.respondWith(
    fetch(e.request).then(function (res) {
      var clone = res.clone();
      caches.open(CACHE).then(function (c) { c.put(e.request, clone); });
      return res;
    }).catch(function () { return caches.match(e.request); })
  );
});
