var CACHE = 'jbfa-v3';
var APP_SHELL = [
  './',
  './index.html',
  './style.css',
  './app.js',
  './dataFetcher.js',
  './uiRenderer.js',
  './logo.jpg',
  './data-schema.json'
];

// ── Install: cache app shell ──────────────────────────────────
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE).then(function(cache) {
      return cache.addAll(APP_SHELL);
    })
  );
  self.skipWaiting();
});

// ── Activate: purge old caches ────────────────────────────────
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys
          .filter(function(k) { return k !== CACHE; })
          .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

// ── Fetch ─────────────────────────────────────────────────────
self.addEventListener('fetch', function(e) {
  var url = new URL(e.request.url);

  // Network-first for data.json — bypass the HTTP cache so we always
  // see the freshest copy from origin. Fall back to the SW cache only
  // when offline / network fails. Normalize the cache key so cache-bust
  // query strings (?v=timestamp) don't fragment the offline fallback.
  if (url.pathname.endsWith('data.json')) {
    var cacheKey = new Request(url.origin + url.pathname);
    e.respondWith(
      fetch(e.request, { cache: 'no-store' })
        .then(function(fresh) {
          if (fresh && fresh.status === 200) {
            var clone = fresh.clone();
            caches.open(CACHE).then(function(cache) {
              cache.put(cacheKey, clone);
            });
          }
          return fresh;
        })
        .catch(function() {
          return caches.match(cacheKey);
        })
    );
    return;
  }

  // Network-first for app shell — always serve fresh when online, fall back to cache when offline
  e.respondWith(
    fetch(e.request).then(function(fresh) {
      if (e.request.method === 'GET' && fresh.status === 200) {
        caches.open(CACHE).then(function(cache) {
          cache.put(e.request, fresh.clone());
        });
      }
      return fresh;
    }).catch(function() {
      return caches.match(e.request);
    })
  );
});
