// --- uiRenderer.js ---

window.statsRenderLeaderboard = function() {
  var statSel  = document.getElementById('stats-lb-stat');
  var togSel   = document.getElementById('stats-lb-tog');
  var gamesSel = document.getElementById('stats-lb-games');
  var posSel   = document.getElementById('stats-lb-pos');
  if (!statSel) return;
  
  var key       = statSel.value;
  var togMin    = parseInt(togSel ? togSel.value : META_DEFAULTS.minMinutes, 10);
  var minGames  = parseInt(gamesSel ? gamesSel.value : META_DEFAULTS.minGames, 10);
  var posFilter = parseInt(posSel ? posSel.value : 0, 10);
  var wrap = document.getElementById('stats-lb-table-wrap');
  if (!wrap) return;

  var meta = STAT_META[key] || {label:key, pts:0, floor:false, isNegative:false};
  var rows = [];
  STAT_PLAYERS.forEach(function(sp) {
    if (posFilter > 0 && (!sp.positions || sp.positions.indexOf(posFilter) < 0)) return;
    var r = playerAvg(sp, key, togMin);
    if (!r || r.games < minGames) return;
    rows.push({pid:sp.pid, name:sp.name, positions:sp.positions, avg:r.avg, games:r.games});
  });
  
  rows.sort(function(a,b){
    return meta.isNegative ? a.avg - b.avg : b.avg - a.avg;
  });

  wrap.innerHTML = '';

  if (!rows.length) {
    wrap.innerHTML = '<div class="stats-empty">No players match these filters.</div>';
    return;
  }

  var listContainer = document.createElement('div');
  listContainer.className = 'stats-lb-list';
  var template = document.getElementById('stats-row-template');

  rows.slice(0,50).forEach(function(row, i) {
    var ptsPerGame = (meta.pts !== null) ? (meta.floor ? Math.floor(row.avg * meta.pts) : row.avg * meta.pts) : null;
    var posStr = formatPositions(row.positions);
    
    var clone = template.content.cloneNode(true); 
    
    clone.querySelector('.stats-rank').textContent = (i + 1);
    clone.querySelector('.stats-name').textContent = row.name; 
    clone.querySelector('.stats-score').textContent = fmtRaw(key, row.avg);
    clone.querySelector('.stats-games').textContent = row.games + 'g';

    var posEl = clone.querySelector('.stats-pos');
    if (posStr) posEl.textContent = posStr;
    else posEl.style.display = 'none'; 

    var ptsEl = clone.querySelector('.stats-pts');
    if (ptsPerGame !== null && Math.abs(ptsPerGame) >= 0.05) ptsEl.textContent = fmtPts(ptsPerGame) + ' pts';
    else ptsEl.style.display = 'none';

    listContainer.appendChild(clone);
  });

  wrap.appendChild(listContainer);
};