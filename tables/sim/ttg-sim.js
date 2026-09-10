/* The Tilted Gent — variance simulator. Vanilla JS, no dependencies.
   Usage: TTGSim.mount('#sim', {game: 'craps'})  — bet tables come from tables/sim/games.js.
   Everything is derived from a bet's outcome table: EV and SD analytically, sample paths and
   confidence bands from a seeded Monte Carlo, so a shared link reproduces the same picture. */
window.TTGSim = (function () {
  'use strict';

  /* ---------- small deterministic PRNG (mulberry32) ---------- */
  function rng(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* ---------- outcome table maths ---------- */
  function normalise(rows) {
    var s = 0, i; for (i = 0; i < rows.length; i++) s += rows[i].p;
    return rows.map(function (r) { return { p: r.p / s, x: r.x }; });
  }
  // For "approx" tables: scale winning and losing probabilities so EV hits the published edge.
  function calibrate(rows, targetEV) {
    var Pw = 0, Pl = 0, P0 = 0, Sw = 0, Sl = 0, i;
    for (i = 0; i < rows.length; i++) {
      var r = rows[i];
      if (r.x > 0) { Pw += r.p; Sw += r.p * r.x; } else if (r.x < 0) { Pl += r.p; Sl += r.p * r.x; } else P0 += r.p;
    }
    var det = Pw * Sl - Pl * Sw;
    if (Math.abs(det) < 1e-12) return rows;
    var a = ((1 - P0) * Sl - Pl * targetEV) / det;
    var b = (Pw * targetEV - (1 - P0) * Sw) / det;
    return rows.map(function (r) { return { p: r.x > 0 ? r.p * a : (r.x < 0 ? r.p * b : r.p), x: r.x }; });
  }
  function moments(rows) {
    var m = 0, v = 0, i;
    for (i = 0; i < rows.length; i++) m += rows[i].p * rows[i].x;
    for (i = 0; i < rows.length; i++) v += rows[i].p * (rows[i].x - m) * (rows[i].x - m);
    return { mean: m, sd: Math.sqrt(v) };
  }
  function bonusMoments(bonus) {
    if (!bonus) return { mean: 0, v: 0 };
    var m = 0, e2 = 0, i;
    for (i = 0; i < bonus.length; i++) { m += bonus[i].p * bonus[i].add; e2 += bonus[i].p * bonus[i].add * bonus[i].add; }
    return { mean: m, v: e2 - m * m };
  }
  function prepare(bet) {
    var rows = normalise(bet.rows), bm = bonusMoments(bet.bonusRows);
    if (bet.kind === 'approx' && typeof bet.edge === 'number') rows = calibrate(rows, -bet.edge - bm.mean);
    var mo = moments(rows);
    var mean = mo.mean + bm.mean, sd = Math.sqrt(mo.sd * mo.sd + bm.v);
    // cumulative table for sampling
    var cum = [], c = 0, i;
    for (i = 0; i < rows.length; i++) { c += rows[i].p; cum.push(c); }
    cum[cum.length - 1] = 1;
    var bcum = null;
    if (bet.bonusRows) { bcum = []; c = 0; for (i = 0; i < bet.bonusRows.length; i++) { c += bet.bonusRows[i].p; bcum.push(c); } }
    return { rows: rows, cum: cum, bonus: bet.bonusRows || null, bcum: bcum, mean: mean, sd: sd, edge: -mean };
  }

  /* ---------- Monte Carlo ---------- */
  function simulate(prep, n, paths, seed, checkpoints, samplePaths) {
    var rand = rng(seed), K = checkpoints, step = n / K;
    var atCk = new Float64Array(paths * K);      // path value at each checkpoint
    var finals = new Float64Array(paths), maxDD = new Float64Array(paths), everDown = 0;
    var samples = [];
    var rows = prep.rows, cum = prep.cum, bonus = prep.bonus, bcum = prep.bcum, nr = rows.length;
    var p, i, j, u, x, val, peak, dd, ck, nextCk, sp;
    for (p = 0; p < paths; p++) {
      val = 0; peak = 0; dd = 0; ck = 0; nextCk = step; var down = false;
      sp = p < samplePaths ? [0] : null;
      for (i = 1; i <= n; i++) {
        u = rand();
        for (j = 0; j < nr - 1; j++) if (u < cum[j]) break;
        x = rows[j].x;
        if (bonus) { u = rand(); for (j = 0; j < bcum.length; j++) if (u < bcum[j]) { x += bonus[j].add; break; } }
        val += x;
        if (val > peak) peak = val;
        if (peak - val > dd) dd = peak - val;
        if (val < 0) down = true;
        if (i >= nextCk - 1e-9 && ck < K) { atCk[p * K + ck] = val; if (sp) sp.push(val); ck++; nextCk += step; }
      }
      while (ck < K) { atCk[p * K + ck] = val; if (sp) sp.push(val); ck++; }
      finals[p] = val; maxDD[p] = dd; if (down) everDown++;
      if (sp) samples.push(sp);
    }
    // percentile bands per checkpoint
    var q = [0.025, 0.15, 0.5, 0.85, 0.975], bands = q.map(function () { return new Float64Array(K); });
    var col = new Float64Array(paths), k;
    for (k = 0; k < K; k++) {
      for (p = 0; p < paths; p++) col[p] = atCk[p * K + k];
      var sorted = Array.prototype.slice.call(col).sort(function (a, b) { return a - b; });
      for (j = 0; j < q.length; j++) bands[j][k] = sorted[Math.min(paths - 1, Math.floor(q[j] * (paths - 1)))];
    }
    var fs = Array.prototype.slice.call(finals).sort(function (a, b) { return a - b; });
    var ds = Array.prototype.slice.call(maxDD).sort(function (a, b) { return a - b; });
    var lossCount = 0; for (p = 0; p < paths; p++) if (finals[p] < 0) lossCount++;
    function pct(arr, q) { return arr[Math.min(arr.length - 1, Math.floor(q * (arr.length - 1)))]; }
    return {
      n: n, paths: paths, K: K, step: step, bands: bands, samples: samples,
      pLoss: lossCount / paths, pEverDown: everDown / paths,
      best: fs[fs.length - 1], worst: fs[0], median: pct(fs, 0.5),
      f025: pct(fs, 0.025), f15: pct(fs, 0.15), f85: pct(fs, 0.85), f975: pct(fs, 0.975),
      ddMedian: pct(ds, 0.5), dd95: pct(ds, 0.95), ddMax: ds[ds.length - 1]
    };
  }

  /* ---------- formatting ---------- */
  function money(v, unit, digits) {
    var d = typeof digits === 'number' ? digits : (Math.abs(v * unit) >= 100 ? 0 : 2);
    var s = Math.abs(v * unit).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
    return (v < 0 ? '−$' : (v > 0 ? '+$' : '$')) + s;
  }
  function pctf(v, d) { return (v * 100).toFixed(typeof d === 'number' ? d : 1) + '%'; }
  function num(v) { return Math.round(v).toLocaleString(); }

  /* ---------- chart ---------- */
  var C = { bg: '#120E1C', line: '#2C2440', cream: '#F1E6CF', dim: '#A399A6', dim2: '#736A78', gold: '#D9A85C', goldHi: '#FFD57A',
            cyan: '#1FCBE3', red: '#FF5C70', green: '#3FA46A' };
  function draw(canvas, sim, prep, unit) {
    var dpr = window.devicePixelRatio || 1, W = canvas.clientWidth, H = canvas.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    var g = canvas.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
    var padL = 64, padR = 16, padT = 18, padB = 34, pw = W - padL - padR, ph = H - padT - padB;
    var K = sim.K, n = sim.n, i;
    // y range: cover the 95% band, the sample paths, and zero, with a little headroom
    var lo = 0, hi = 0;
    for (i = 0; i < K; i++) { lo = Math.min(lo, sim.bands[0][i]); hi = Math.max(hi, sim.bands[4][i]); }
    sim.samples.forEach(function (s) { for (i = 0; i < s.length; i++) { lo = Math.min(lo, s[i]); hi = Math.max(hi, s[i]); } });
    var span = Math.max(hi - lo, 1) * 1.06; lo -= (span - (hi - lo)) / 2; hi = lo + span;
    function X(k) { return padL + (k / K) * pw; }           // k = checkpoint index 0..K (0 = start)
    function Y(v) { return padT + (hi - v) / (hi - lo) * ph; }
    // gridlines
    var ticks = niceTicks(lo * unit, hi * unit, 5);
    g.strokeStyle = C.line; g.lineWidth = 1; g.font = '11px "JetBrains Mono", monospace'; g.fillStyle = C.dim2; g.textAlign = 'right';
    ticks.forEach(function (t) { var y = Y(t / unit); g.beginPath(); g.moveTo(padL, y); g.lineTo(W - padR, y); g.stroke(); g.fillText(money(t / unit, unit, 0).replace('+', ''), padL - 8, y + 4); });
    g.textAlign = 'center';
    var xt = niceTicks(0, n, 6);
    xt.forEach(function (t) { var x = X(t / sim.step); g.fillText(num(t), x, H - padB + 18); });
    // bands
    function band(loB, hiB, alpha) {
      g.beginPath(); g.moveTo(X(0), Y(0));
      for (i = 0; i < K; i++) g.lineTo(X(i + 1), Y(hiB[i]));
      for (i = K - 1; i >= 0; i--) g.lineTo(X(i + 1), Y(loB[i]));
      g.closePath(); g.fillStyle = 'rgba(31,203,227,' + alpha + ')'; g.fill();
    }
    band(sim.bands[0], sim.bands[4], 0.10);
    band(sim.bands[1], sim.bands[3], 0.16);
    // sample paths
    g.lineWidth = 1; g.strokeStyle = 'rgba(163,153,166,.30)';
    sim.samples.forEach(function (s) { g.beginPath(); g.moveTo(X(0), Y(0)); for (i = 1; i < s.length; i++) g.lineTo(X(i), Y(s[i])); g.stroke(); });
    // zero line
    g.strokeStyle = 'rgba(241,230,207,.35)'; g.setLineDash([4, 4]); g.beginPath(); g.moveTo(padL, Y(0)); g.lineTo(W - padR, Y(0)); g.stroke(); g.setLineDash([]);
    // expectation (straight line)
    g.strokeStyle = C.goldHi; g.lineWidth = 1.5; g.setLineDash([8, 5]); g.beginPath(); g.moveTo(X(0), Y(0)); g.lineTo(X(K), Y(prep.mean * n)); g.stroke(); g.setLineDash([]);
    // median path
    g.strokeStyle = C.gold; g.lineWidth = 2.2; g.beginPath(); g.moveTo(X(0), Y(0)); for (i = 0; i < K; i++) g.lineTo(X(i + 1), Y(sim.bands[2][i])); g.stroke();
    // axes labels
    g.fillStyle = C.dim; g.textAlign = 'right'; g.font = '10.5px "JetBrains Mono", monospace';
    g.fillText('BETS →', W - padR, H - 6);
    g.save(); g.translate(12, padT + ph / 2); g.rotate(-Math.PI / 2); g.textAlign = 'center'; g.fillText('PROFIT / LOSS', 0, 0); g.restore();
  }
  function niceTicks(lo, hi, count) {
    var span = hi - lo, raw = span / count, mag = Math.pow(10, Math.floor(Math.log10(raw))), norm = raw / mag, step;
    step = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10; step *= mag;
    var out = [], t = Math.ceil(lo / step) * step; while (t <= hi + 1e-9) { out.push(t); t += step; }
    return out;
  }

  /* ---------- UI ---------- */
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function readHash() {
    var h = {}; (location.hash || '').replace(/^#/, '').split('&').forEach(function (kv) { var p = kv.split('='); if (p[0]) h[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || ''); });
    return h;
  }
  function writeHash(state) {
    var s = Object.keys(state).map(function (k) { return k + '=' + encodeURIComponent(state[k]); }).join('&');
    if (history.replaceState) history.replaceState(null, '', '#' + s); else location.hash = s;
  }

  function mount(sel, opts) {
    var root = typeof sel === 'string' ? document.querySelector(sel) : sel;
    if (!root || !window.TTG_GAMES) return;
    var game = window.TTG_GAMES[opts.game]; if (!game) return;
    var h = readHash();
    var state = { bet: game.bets[h.bet] ? h.bet : game.defaultBet, unit: +h.unit > 0 ? +h.unit : game.unit,
                  n: +h.n > 0 ? Math.min(Math.round(+h.n), 20000) : (opts.n || 500), seed: +h.seed > 0 ? +h.seed : 20260910 };
    root.innerHTML = '';
    var wrap = el('div', 'simbox');
    var form = el('div', 'simform');
    var betSel = el('select'); Object.keys(game.bets).forEach(function (k) { var o = el('option', null, game.bets[k].name); o.value = k; betSel.appendChild(o); });
    betSel.value = state.bet;
    var unitIn = el('input'); unitIn.type = 'number'; unitIn.min = '0.05'; unitIn.step = 'any'; unitIn.value = state.unit;
    var nIn = el('input'); nIn.type = 'number'; nIn.min = '10'; nIn.max = '20000'; nIn.step = '10'; nIn.value = state.n;
    var hoursOut = el('span', 'simhours');
    var run = el('button', 'simrun', 'Run 1,000 sessions'); run.type = 'button';
    var reroll = el('button', 'simroll', '↻ New dice'); reroll.type = 'button';
    function field(label, node, extra) { var f = el('label', 'simfield'); f.appendChild(el('span', 'k', label)); f.appendChild(node); if (extra) f.appendChild(extra); return f; }
    form.appendChild(field('Bet', betSel));
    form.appendChild(field('Unit ($)', unitIn));
    form.appendChild(field('Bets', nIn, hoursOut));
    var btns = el('div', 'simbtns'); btns.appendChild(run); btns.appendChild(reroll); form.appendChild(btns);
    wrap.appendChild(form);
    var meta = el('p', 'simmeta'); wrap.appendChild(meta);
    var stats = el('div', 'simstats'); wrap.appendChild(stats);
    var cwrap = el('div', 'simchart'); var canvas = el('canvas'); cwrap.appendChild(canvas);
    var legend = el('div', 'simlegend', '<span><i class="l-med"></i>median session</span><span><i class="l-ev"></i>expectation</span><span><i class="l-70"></i>70% of sessions</span><span><i class="l-95"></i>95% of sessions</span><span><i class="l-smp"></i>20 sample sessions</span>');
    wrap.appendChild(cwrap); wrap.appendChild(legend);
    var foot = el('p', 'simfoot'); wrap.appendChild(foot);
    root.appendChild(wrap);

    var last = null;
    function updateHours() { var hrs = state.n / game.pace; hoursOut.textContent = '≈ ' + (hrs < 10 ? hrs.toFixed(1) : Math.round(hrs)) + ' hr at ' + game.pace + '/hr'; }
    function tile(k, v, cls, sub) { return '<div class="st' + (cls ? ' ' + cls : '') + '"><div class="k">' + k + '</div><div class="v">' + v + '</div>' + (sub ? '<div class="s">' + sub + '</div>' : '') + '</div>'; }
    function render() {
      state.bet = betSel.value; state.unit = Math.max(0.05, +unitIn.value || game.unit); state.n = Math.max(10, Math.min(20000, Math.round(+nIn.value || 500)));
      unitIn.value = state.unit; nIn.value = state.n; updateHours();
      var bet = game.bets[state.bet], prep = prepare(bet), n = state.n, unit = state.unit;
      var paths = 1000, K = Math.min(n, 200);
      var sim = simulate(prep, n, paths, state.seed, K, 20);
      last = { sim: sim, prep: prep, unit: unit };
      var evTot = prep.mean * n, sdTot = prep.sd * Math.sqrt(n);
      var nStar = prep.mean < 0 ? Math.pow(1.96 * prep.sd / -prep.mean, 2) : Infinity;
      var hrs = n / game.pace, perHour = prep.mean * game.pace * unit;
      var cls = function (v) { return v < 0 ? 'dn' : (v > 0 ? 'up' : ''); };
      meta.innerHTML = '<b>' + bet.name + '</b> · house edge <b>' + pctf(prep.edge, 2) + '</b>' + (bet.edgeNote ? ' <span class="dim">(' + bet.edgeNote + ')</span>' : '') +
        ' · SD per bet <b>' + prep.sd.toFixed(2) + ' units</b>' + (bet.avgWager ? ' · average money at risk per round <b>' + bet.avgWager.toFixed(2) + ' units</b>' : '') +
        ' · outcome table: <b>' + (bet.kind === 'exact' ? 'exact' : 'approximate, calibrated to the published edge') + '</b>';
      stats.innerHTML =
        tile('Expected result', money(evTot, unit), cls(evTot), num(n) + ' bets of ' + money(1, unit, unit % 1 ? 2 : 0).replace('+', '') + ' · ' + (hrs < 10 ? hrs.toFixed(1) : Math.round(hrs)) + ' hr') +
        tile('Expected cost per hour', money(perHour, 1), cls(perHour), 'at ' + game.pace + ' bets/hr · ' + game.paceNote) +
        tile('Standard deviation', money(sdTot, unit, 0).replace('+', '±'), '', 'per bet: ' + money(prep.sd, unit).replace('+', '±') + ' · the noise is ' + (Math.abs(evTot) > 0 ? (sdTot / Math.abs(evTot)).toFixed(1) : '∞') + '× the signal') +
        tile('Chance you’re losing at the end', pctf(sim.pLoss), sim.pLoss > 0.5 ? 'dn' : 'up', 'ever behind during the session: ' + pctf(sim.pEverDown)) +
        tile('70% of sessions land between', money(sim.f15, unit, 0) + ' and ' + money(sim.f85, unit, 0), '', '95%: ' + money(sim.f025, unit, 0) + ' to ' + money(sim.f975, unit, 0)) +
        tile('Best / worst of 1,000', money(sim.best, unit, 0) + ' / ' + money(sim.worst, unit, 0), '', 'median ' + money(sim.median, unit, 0)) +
        tile('Biggest drawdown', money(-sim.ddMedian, unit, 0), 'dn', 'typical session; 1 in 20 sees ' + money(-sim.dd95, unit, 0) + ' or worse') +
        tile('Bets until the edge is undeniable', isFinite(nStar) ? num(nStar) : '—', '', isFinite(nStar) ? '≈ ' + num(nStar / game.pace) + ' hours before 95% of players are behind' : 'no house edge on this bet');
      writeHash({ bet: state.bet, unit: state.unit, n: state.n, seed: state.seed });
      draw(canvas, sim, prep, unit);
      foot.innerHTML = '1,000 simulated sessions of ' + num(n) + ' bets, drawn from the bet’s actual outcome table (not a normal approximation). Bands are the empirical 15th–85th and 2.5th–97.5th percentiles across sessions at each point. Seed ' + state.seed + ' — the link in your address bar reproduces this exact chart. Education, not advice: the point is to see what the edge looks like from inside a session.';
    }
    run.addEventListener('click', render);
    reroll.addEventListener('click', function () { state.seed = Math.floor(Math.random() * 1e9) + 1; render(); });
    betSel.addEventListener('change', render);
    nIn.addEventListener('input', updateHours);
    [unitIn, nIn].forEach(function (i) { i.addEventListener('keydown', function (e) { if (e.key === 'Enter') render(); }); });
    var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { if (last) draw(canvas, last.sim, last.prep, last.unit); }, 120); });
    render();
  }

  return { mount: mount, prepare: prepare, simulate: simulate, calibrate: calibrate, moments: moments };
})();
