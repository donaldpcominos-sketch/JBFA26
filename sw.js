var CACHE = 'jbfa-v2';
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

  // Stale-while-revalidate for data.json:
  // Respond instantly from cache, then fetch fresh in background.
  // If the fresh copy differs, notify all open tabs.
  if (url.pathname.endsWith('data.json')) {
    e.respondWith(
      caches.open(CACHE).then(function(cache) {
        return cache.match(e.request).then(function(cached) {
          var fetchPromise = fetch(e.request.clone()).then(function(fresh) {
            if (cached) {
              // Compare to detect round updates
              Promise.all([cached.clone().text(), fresh.clone().text()])
                .then(function(texts) {
                  if (texts[0] !== texts[1]) {
                    self.clients.matchAll({ includeUncontrolled: true }).then(function(clients) {
                      clients.forEach(function(c) {
                        c.postMessage({ type: 'DATA_UPDATED' });
                      });
                    });
                  }
                })
                .catch(function() {});
            }
            cache.put(e.request, fresh.clone());
            return fresh;
          }).catch(function() {
            return cached;
          });

          // Serve cached immediately if available, otherwise wait for network
          return cached || fetchPromise;
        });
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
