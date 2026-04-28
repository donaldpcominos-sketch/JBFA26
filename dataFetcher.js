// --- dataFetcher.js ---

function setupFeedbackForm() {
  function closeFeedback() {
    document.getElementById('fmodal').style.display = 'none';
    document.getElementById('fok').style.display = 'none';
    document.getElementById('fform').reset();
  }

  var _fm = document.getElementById('fmodal');
  if (_fm) _fm.addEventListener('click', function(e) {
    if (e.target === this) closeFeedback();
  });

  var _ff = document.getElementById('fform');
  if (_ff) _ff.addEventListener('submit', function(e) {
    e.preventDefault();
    var btn = document.getElementById('fsubmit');
    btn.textContent = 'Sending…';
    btn.disabled = true;

    fetch('https://formspree.io/f/xlgplwnz', {
      method: 'POST',
      body: new FormData(this),
      headers: { 'Accept': 'application/json' }
    })
    .then(function(r) {
      if (r.ok) {
        document.getElementById('fok').style.display = 'block';
        btn.textContent = 'Sent ✓';
        setTimeout(closeFeedback, 2000);
      } else {
        btn.textContent = 'Failed — try again';
        btn.disabled = false;
      }
    })
    .catch(function() {
      btn.textContent = 'Failed — try again';
      btn.disabled = false;
    });
  });
}

function getDataUrl() {
  return './data.json?v=' + Date.now();
}

function fetchLeagueData() {
  fetch(getDataUrl())
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(data) {
      if (typeof window._initApp === 'function') window._initApp(data);
      if (typeof window._initPricePredictor === 'function') window._initPricePredictor(data.beModel || null);

      var loadedRound = data && data.meta && data.meta.currentRound;
      if (loadedRound) {
        window._loadedRound = loadedRound;
        // Side-channel freshness check — bypasses any stale SW/HTTP cache
        // because the unique query string can never match a cached entry.
        setTimeout(checkForNewerRound, 1500);
      }
    })
    .catch(function(err) {
      console.error('Remote fetch failed: ' + err);
      var banner=document.getElementById('error-banner');
      if(banner) banner.classList.add('show');
      var lo=document.getElementById('app-loading');
      if(lo) lo.style.display='none';
    });
}

function checkForNewerRound() {
  fetch('./data.json?freshcheck=' + Date.now(), { cache: 'no-store' })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(fresh) {
      if (!fresh) return;
      var freshRound = fresh.meta && fresh.meta.currentRound;
      if (freshRound && window._loadedRound && freshRound > window._loadedRound) {
        var banner = document.getElementById('round-update-banner');
        if (banner) {
          var msg = banner.querySelector('.rub-msg');
          if (msg) msg.textContent = 'Round ' + freshRound + ' is now available';
          banner.classList.add('visible');
        }
      }
    })
    .catch(function() {});
}

function hardRefresh() {
  var done = function() {
    // Cache-bust the reload URL too, in case the browser tries to serve
    // the HTML itself from disk cache on iOS PWA.
    var u = new URL(window.location.href);
    u.searchParams.set('_r', Date.now());
    window.location.replace(u.toString());
  };
  var p = Promise.resolve();
  if ('caches' in window) {
    p = caches.keys().then(function(keys) {
      return Promise.all(keys.map(function(k) { return caches.delete(k); }));
    }).catch(function() {});
  }
  p.then(function() {
    if ('serviceWorker' in navigator) {
      return navigator.serviceWorker.getRegistrations().then(function(regs) {
        return Promise.all(regs.map(function(r) { return r.unregister(); }));
      }).catch(function() {});
    }
  }).then(done, done);
}