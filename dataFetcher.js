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
        btn.textContent = 'Send Feedback';
        btn.disabled = false;
        alert('Something went wrong — try again.');
      }
    })
    .catch(function() {
      btn.textContent = 'Send Feedback';
      btn.disabled = false;
      alert('Something went wrong — try again.');
    });
  });
}

function getDataUrl() {
  return './data.json';
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
      
    })
    .catch(function(err) {
      console.error('Remote fetch failed: ' + err);
      alert('Unable to load league data. Please check your connection or data.json deployment.');
    });
}