/* The Tilted Gent — blackjack trainer table: round flow, bots, timed dealing, and the UI.
   Depends on bj-trainer.js (window.BJT). Mount with BJTable.mount('#trainer'). */
window.BJTable = (function () {
  'use strict';
  var B = window.BJT;
  var ACT_NAME = { H: 'Hit', S: 'Stand', D: 'Double', P: 'Split', R: 'Surrender' };

  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function fmt(n) { return (n < 0 ? '−$' : '$') + Math.abs(n).toLocaleString(); }
  function sgn(n) { return (n > 0 ? '+' : '') + n; }

  var DEFAULTS = { decks: 6, h17: true, das: true, surrender: true, penetration: 0.75, bots: 2, seat: 'last', speed: 500, mode: 'play',
                   unit: 25, showCount: false, showAdvice: false, useIndex: false, autoNext: true, system: 'hilo', bustRemove: 2000, rcEvery: 0, tcEvery: 0 };
  function loadSettings() { try { var s = JSON.parse(localStorage.getItem('ttg-bjt') || 'null'); return s ? Object.assign({}, DEFAULTS, s) : Object.assign({}, DEFAULTS); } catch (e) { return Object.assign({}, DEFAULTS); } }
  function saveSettings(s) { try { localStorage.setItem('ttg-bjt', JSON.stringify(s)); } catch (e) {} }

  function mount(sel) {
    var root = typeof sel === 'string' ? document.querySelector(sel) : sel; if (!root) return;
    var S = loadSettings();
    var game = null, round = null, timer = null, paused = false, pendingCheck = false;

    /* ---------- DOM skeleton ---------- */
    root.innerHTML = '';
    var wrap = el('div', 'bjt');
    // settings bar
    var bar = el('div', 'bjt-bar');
    function sel_(label, key, options) {
      var f = el('label', 'bjt-field'); f.appendChild(el('span', 'k', label));
      var s = el('select'); options.forEach(function (o) { var op = el('option', null, o[1]); op.value = o[0]; s.appendChild(op); }); s.value = String(S[key]);
      s.addEventListener('change', function () { S[key] = isNaN(+s.value) || key === 'seat' || key === 'mode' || key === 'system' ? s.value : +s.value; if (key === 'h17' || key === 'das' || key === 'surrender') S[key] = s.value === 'true'; saveSettings(S); if (key === 'bustRemove' || key === 'rcEvery' || key === 'tcEvery') { renderFelt(); return; } rebuild(); });
      f.appendChild(s); return f;
    }
    bar.appendChild(sel_('Decks', 'decks', [[1, '1 deck'], [2, '2 decks'], [4, '4 decks'], [6, '6 decks'], [8, '8 decks']]));
    bar.appendChild(sel_('Dealer', 'h17', [['true', 'Hits soft 17'], ['false', 'Stands on 17']]));
    bar.appendChild(sel_('Double after split', 'das', [['true', 'Allowed'], ['false', 'Not allowed']]));
    bar.appendChild(sel_('Surrender', 'surrender', [['true', 'Late surrender'], ['false', 'None']]));
    bar.appendChild(sel_('Penetration', 'penetration', [[0.5, '50%'], [0.65, '65%'], [0.75, '75%'], [0.85, '85%']]));
    bar.appendChild(sel_('Other players', 'bots', [[0, 'None'], [1, '1'], [2, '2'], [3, '3'], [4, '4'], [5, '5'], [6, '6']]));
    bar.appendChild(sel_('Your seat', 'seat', [['first', 'First base'], ['middle', 'Middle'], ['last', 'Third base']]));
    bar.appendChild(sel_('Mode', 'mode', [['play', 'Play — I make the decisions'], ['drill', 'Count drill — everyone auto-plays']]));
    bar.appendChild(sel_('Busted hands', 'bustRemove', [[2000, 'Removed after 2 s'], [5000, 'Removed after 5 s'], [0, 'Stay on the table']]));
    bar.appendChild(sel_('Ask my running count', 'rcEvery', [[0, 'Never'], [3, 'Every 3 hands'], [5, 'Every 5 hands'], [10, 'Every 10 hands'], [20, 'Every 20 hands']]));
    bar.appendChild(sel_('Ask my true count', 'tcEvery', [[0, 'Never'], [26, 'Every half deck dealt'], [52, 'Every deck dealt'], [104, 'Every 2 decks dealt']]));
    var spd = el('label', 'bjt-field'); spd.appendChild(el('span', 'k', 'Deal speed'));
    var spdIn = el('input'); spdIn.type = 'range'; spdIn.min = '60'; spdIn.max = '1500'; spdIn.step = '20'; spdIn.value = S.speed;
    var spdOut = el('span', 'bjt-spd', S.speed + ' ms/card');
    spdIn.addEventListener('input', function () { S.speed = +spdIn.value; spdOut.textContent = S.speed + ' ms/card'; saveSettings(S); });
    spd.appendChild(spdIn); spd.appendChild(spdOut); bar.appendChild(spd);
    wrap.appendChild(bar);

    // toggles
    var tog = el('div', 'bjt-toggles');
    function toggle(label, key, onChange) { var l = el('label', 'bjt-toggle'); var c = el('input'); c.type = 'checkbox'; c.checked = !!S[key]; c.addEventListener('change', function () { S[key] = c.checked; saveSettings(S); if (onChange) onChange(); renderAll(); }); l.appendChild(c); l.appendChild(el('span', null, label)); return l; }
    tog.appendChild(toggle('Show live count (training wheels)', 'showCount'));
    tog.appendChild(toggle('Show advice before I act', 'showAdvice'));
    tog.appendChild(toggle('Use index plays (Illustrious 18) in advice', 'useIndex'));
    tog.appendChild(toggle('Auto-deal next hand', 'autoNext'));
    wrap.appendChild(tog);

    // main grid: table + side panel
    var grid = el('div', 'bjt-grid');
    var felt = el('div', 'bjt-felt');
    var shoeLine = el('div', 'bjt-shoe'); felt.appendChild(shoeLine);
    var gaugeRow = el('div', 'bjt-gaugerow');
    gaugeRow.innerHTML = '<div class="bjt-tray" title="discard tray"><div class="stack"></div><span>discards</span></div><div class="bjt-gauge"><div class="segs"></div><div class="fill"></div><div class="cut"></div><div class="lbl"></div></div><div class="bjt-shoebox" title="shoe"><div class="stack"></div><span>shoe</span></div>';
    felt.appendChild(gaugeRow);
    var gauge = gaugeRow.querySelector('.bjt-gauge'), trayStack = gaugeRow.querySelector('.bjt-tray .stack'), shoeStack = gaugeRow.querySelector('.bjt-shoebox .stack');
    var table = el('div', 'bjt-table');
    table.innerHTML = '<div class="bjt-rail"></div><div class="bjt-surface">' +
      '<svg class="bjt-arcsvg" viewBox="0 0 1000 560" preserveAspectRatio="none" aria-hidden="true"><defs><path id="bjt-arc-outer" d="M 58 24 A 442 516 0 0 0 942 24"/></defs>' +
      '<text class="arc1"><textPath href="#bjt-arc-outer" startOffset="50%" text-anchor="middle"></textPath></text>' +
      '</svg>' +
      '<div class="bjt-brand"><img src="../assets/ttg-mark-neon.svg" alt=""><span>THE TILTED GENT</span><small>INSURANCE PAYS 2 TO 1</small></div></div>';
    felt.appendChild(table);
    var surface = table.querySelector('.bjt-surface');
    var arcText = table.querySelector('.arc1 textPath');
    var dealerBox = el('div', 'bjt-dealer'); surface.appendChild(dealerBox);
    var seatsBox = el('div', 'bjt-seats'); surface.appendChild(seatsBox);
    var msg = el('div', 'bjt-msg'); felt.appendChild(msg);
    var actions = el('div', 'bjt-actions'); felt.appendChild(actions);
    var betRow = el('div', 'bjt-bet'); felt.appendChild(betRow);
    grid.appendChild(felt);

    var side = el('div', 'bjt-side');
    var tabs = el('div', 'bjt-tabs'); var panes = {};
    ['Count', 'Strategy', 'Counting guide', 'Stats'].forEach(function (name, i) {
      var b = el('button', 'bjt-tab' + (i === 0 ? ' on' : ''), name); b.type = 'button';
      b.addEventListener('click', function () { Array.prototype.forEach.call(tabs.children, function (x) { x.classList.remove('on'); }); b.classList.add('on'); Object.keys(panes).forEach(function (k) { panes[k].hidden = k !== name; }); });
      tabs.appendChild(b); panes[name] = el('div', 'bjt-pane'); panes[name].hidden = i !== 0;
    });
    side.appendChild(tabs); Object.keys(panes).forEach(function (k) { side.appendChild(panes[k]); });
    grid.appendChild(side); wrap.appendChild(grid);
    root.appendChild(wrap);

    /* ---------- count pane ---------- */
    var cp = panes['Count'];
    cp.appendChild(el('p', 'bjt-help', 'Keep the running count in your head as the cards come out. Pause any time and check yourself — the trainer compares your count to the real one and keeps score. The count includes every card you can see: everyone\'s hands and the dealer\'s up card, then the hole card when it\'s turned over.'));
    var checkRow = el('div', 'bjt-check');
    var rcIn = el('input'); rcIn.type = 'number'; rcIn.step = '1'; rcIn.placeholder = 'your running count';
    var checkBtn = el('button', 'bjt-btn gold', 'Check my count'); checkBtn.type = 'button';
    var pauseBtn = el('button', 'bjt-btn ghost', 'Pause'); pauseBtn.type = 'button';
    checkRow.appendChild(rcIn); checkRow.appendChild(checkBtn); checkRow.appendChild(pauseBtn); cp.appendChild(checkRow);
    var checkOut = el('div', 'bjt-checkout'); cp.appendChild(checkOut);
    var liveCount = el('div', 'bjt-live'); cp.appendChild(liveCount);
    var betAdvice = el('div', 'bjt-betadvice'); cp.appendChild(betAdvice);

    /* ---------- counting guide pane ---------- */
    function renderGuide() {
      var sys = B.SYSTEMS[S.system], g = panes['Counting guide']; g.innerHTML = '';
      g.appendChild(el('h4', null, sys.name + ' — the tags'));
      var t = '<table class="bjt-tags"><tr>'; [2, 3, 4, 5, 6, 7, 8, 9, 10, 11].forEach(function (v) { t += '<th>' + (v === 11 ? 'A' : v === 10 ? '10/J/Q/K' : v) + '</th>'; }); t += '</tr><tr>';
      [2, 3, 4, 5, 6, 7, 8, 9, 10, 11].forEach(function (v) { var x = sys.tags[v]; t += '<td class="' + (x > 0 ? 'up' : x < 0 ? 'dn' : '') + '">' + sgn(x) + '</td>'; }); t += '</tr></table>';
      g.appendChild(el('div', null, t));
      g.appendChild(el('p', 'bjt-help', sys.note + (sys.balanced ? ' The system is balanced: a full shoe counts back to zero.' : '')));
      g.appendChild(el('h4', null, 'Running count → true count'));
      g.appendChild(el('p', 'bjt-help', 'True count = running count ÷ decks remaining (estimate the discard tray to the nearest half deck). A running count of +6 with three decks left is +2 true; with one deck left it is +6 true. The true count is what drives both your bet and the index plays. Each true count point is worth roughly half a percent of edge to whoever it favours.'));
      g.appendChild(el('h4', null, 'Betting ramp (units)'));
      var r = '<table class="bjt-tags"><tr><th>True count</th>'; sys.betRamp.forEach(function (x) { r += '<th>' + (x[0] <= 1 ? '≤ +1' : '+' + x[0]) + '</th>'; }); r += '</tr><tr><td>Bet</td>'; sys.betRamp.forEach(function (x) { r += '<td>' + x[1] + '</td>'; }); r += '</tr></table>';
      g.appendChild(el('div', null, r));
      g.appendChild(el('p', 'bjt-help', 'A 1–12 spread like this is what makes the count worth money; a 1–4 spread barely breaks even against the house edge. It is also what surveillance watches for, which is why real counters camouflage it.'));
      g.appendChild(el('h4', null, 'Index plays — the Illustrious 18 and the Fab 4'));
      var ul = el('ul', 'bjt-index'); B.INDEX.forEach(function (ix) { ul.appendChild(el('li', null, ix.label)); }); g.appendChild(ul);
      g.appendChild(el('p', 'bjt-help', 'These are the deviations from basic strategy that capture most of the value of the count. Turn on "use index plays in advice" and the trainer grades your decisions against them at the current true count. Insurance is the single most valuable one.'));
      g.appendChild(el('p', 'bjt-help bjt-fine', 'Other systems (KO, Hi-Opt II, Zen, Omega II) plug in as a tag table plus an initial running count; the trainer is built to take them. Hi-Lo first, because it is what everyone learns and what the published index plays are for.'));
    }

    /* ---------- strategy pane ---------- */
    var stratHi = null;
    function renderStrategy() {
      var T = game.T, g = panes['Strategy']; g.innerHTML = '';
      g.appendChild(el('p', 'bjt-help', 'Generated for the rules you picked: ' + S.decks + ' deck' + (S.decks > 1 ? 's' : '') + ', dealer ' + (S.h17 ? 'hits' : 'stands on') + ' soft 17, double after split ' + (S.das ? 'allowed' : 'not allowed') + ', ' + (S.surrender ? 'late surrender' : 'no surrender') + '. The highlighted cell is your current hand.'));
      var ups = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
      function tbl(title, keys, labelFn) {
        var h = '<h4>' + title + '</h4><div class="tw"><table class="bjt-strat"><tr><th></th>'; ups.forEach(function (u) { h += '<th>' + (u === 11 ? 'A' : u) + '</th>'; }); h += '</tr>';
        keys.forEach(function (k) { h += '<tr><th>' + labelFn(k) + '</th>'; ups.forEach(function (u) { var a = T[k][u]; h += '<td class="a-' + a.toLowerCase() + '" data-k="' + k + '" data-u="' + u + '">' + a + '</td>'; }); h += '</tr>'; });
        return h + '</table></div>';
      }
      var hard = [], soft = [], pairs = ['pA', 'p10', 'p9', 'p8', 'p7', 'p6', 'p5', 'p4', 'p3', 'p2'], i;
      for (i = 18; i >= 8; i--) hard.push('h' + i); for (i = 20; i >= 13; i--) soft.push('s' + i);
      g.appendChild(el('div', null, tbl('Hard totals', hard, function (k) { var n = +k.slice(1); return n === 18 ? '18+' : n === 8 ? '5–8' : String(n); })));
      g.appendChild(el('div', null, tbl('Soft totals', soft, function (k) { return 'A,' + (+k.slice(1) - 11); })));
      g.appendChild(el('div', null, tbl('Pairs', pairs, function (k) { var r = k.slice(1); return r + ',' + r; })));
      g.appendChild(el('p', 'bjt-help', '<b>H</b> hit · <b>S</b> stand · <b>D</b> double (else hit) · <b>Ds</b> double (else stand) · <b>P</b> split · <b>R</b> surrender (else hit). Learn it in blocks: the stiff hands (12–16) first, then the doubles, then the pairs.'));
      highlightStrategy();
    }
    function highlightStrategy() {
      var g = panes['Strategy']; Array.prototype.forEach.call(g.querySelectorAll('td.hi'), function (td) { td.classList.remove('hi'); });
      if (!stratHi) return;
      var td = g.querySelector('td[data-k="' + stratHi.k + '"][data-u="' + stratHi.u + '"]'); if (td) td.classList.add('hi');
    }

    /* ---------- stats pane ---------- */
    function renderStats() {
      var st = game.stats, g = panes['Stats'];
      var acc = st.decisions ? Math.round(100 * st.correct / st.decisions) : 0, cacc = st.countChecks ? Math.round(100 * st.countExact / st.countChecks) : 0;
      g.innerHTML = '<div class="bjt-stats">' +
        tile('Hands', st.hands) + tile('Session result', fmt(st.net), st.net < 0 ? 'dn' : st.net > 0 ? 'up' : '') +
        tile('Strategy accuracy', st.decisions ? acc + '%' : '—', acc >= 95 ? 'up' : acc >= 85 ? '' : 'dn', st.correct + ' of ' + st.decisions + ' decisions') +
        tile('Count checks', st.countChecks ? cacc + '% exact' : '—', cacc >= 90 ? 'up' : '', st.countChecks ? 'average miss ' + (st.countOff / st.countChecks).toFixed(1) : 'none yet') +
        tile('True-count checks', st.tcChecks ? Math.round(100 * (st.tcExact || 0) / st.tcChecks) + '% within ½' : '—', st.tcChecks && (st.tcExact || 0) / st.tcChecks >= 0.9 ? 'up' : '', st.tcChecks ? 'average miss ' + (st.tcOff / st.tcChecks).toFixed(1) : 'none yet') +
        tile('Win / loss / push', st.wins + ' / ' + st.losses + ' / ' + st.pushes) + tile('Shoes dealt', game.shoeNo) + '</div>' +
        '<p class="bjt-help">Basic strategy alone gets the house edge to about half a percent; the count only pays once your strategy accuracy is above 95% and your count checks are exact. Fix the strategy first.</p>' +
        '<button type="button" class="bjt-btn ghost" id="bjt-reset">Reset session</button>';
      g.querySelector('#bjt-reset').addEventListener('click', function () { rebuild(true); });
    }
    function tile(k, v, cls, s) { return '<div class="st' + (cls ? ' ' + cls : '') + '"><div class="k">' + k + '</div><div class="v">' + v + '</div>' + (s ? '<div class="s">' + s + '</div>' : '') + '</div>'; }

    /* ---------- rendering the felt ---------- */
    function cardHTML(c, hidden) {
      if (hidden || c.hidden) return '<span class="bjt-card back" aria-label="face-down card"></span>';
      var red = c.s === '♥' || c.s === '♦';
      return '<span class="bjt-card' + (red ? ' red' : '') + '"><b>' + c.label + '</b><i>' + c.s + '</i><u>' + c.s + '</u><em>TG</em></span>';
    }
    function handHTML(h, showTotal) {
      if (h.removed) return '<div class="bjt-hand gone"><div class="cards"></div><div class="meta"><em class="bjt-status bust">Bust</em></div></div>';
      var t = B.total(h.cards), s = '';
      h.cards.forEach(function (c) { s += cardHTML(c); });
      var lab = '';
      if (showTotal && !h.cards.some(function (c) { return c.hidden; })) lab = (B.isBJ(h.cards) && !h.split ? 'BJ' : (t.soft && t.t <= 21 ? 'soft ' : '') + t.t);
      var st = h.status ? '<em class="bjt-status ' + h.status + '">' + h.statusText + '</em>' : '';
      return '<div class="bjt-hand' + (h.active ? ' active' : '') + '"><div class="cards">' + s + '</div><div class="meta">' + (lab ? '<span class="tot">' + lab + '</span>' : '') + (h.bet && (h.doubled || h.split) ? '<span class="bet">' + fmt(h.bet) + '</span>' : '') + st + '</div></div>';
    }
    function renderFelt() {
      var decksLeft = game.decksRemaining();
      var totalCards = S.decks * 52, dealt = totalCards - game.shoe.length;
      shoeLine.innerHTML = '<span>Shoe ' + game.shoeNo + '</span>' + (S.showCount ? '<span>' + game.shoe.length + ' cards left · ~' + decksLeft + ' deck' + (decksLeft === 1 ? '' : 's') + '</span>' : '<span>' + S.decks + ' decks · estimate what\'s left from the tray</span>') + '<span>cut card at ' + Math.round(S.penetration * 100) + '%</span>' + (game.needShuffle ? '<span class="warn">shuffle after this hand</span>' : '');
      // shoe gauge: one segment per deck, fill = dealt, cut-card marker at penetration; tray/shoe stacks grow and shrink
      if (gauge.querySelector('.segs').children.length !== S.decks) { var sg = ''; for (var q = 0; q < S.decks; q++) sg += '<i></i>'; gauge.querySelector('.segs').innerHTML = sg; }
      gauge.querySelector('.fill').style.width = (100 * dealt / totalCards) + '%';
      gauge.querySelector('.cut').style.left = (100 * S.penetration) + '%';
      gauge.querySelector('.lbl').textContent = S.showCount ? (Math.round(dealt / 52 * 2) / 2) + ' dealt · ' + decksLeft + ' left' : '';
      var trayN = Math.min(12, Math.round(dealt / (totalCards / 12))), shoeN = Math.min(12, Math.ceil(game.shoe.length / (totalCards / 12)));
      trayStack.innerHTML = new Array(trayN + 1).join('<b></b>'); shoeStack.innerHTML = new Array(shoeN + 1).join('<b></b>');
      arcText.textContent = 'BLACKJACK PAYS 3 TO 2  ·  DEALER MUST ' + (S.h17 ? 'HIT SOFT 17' : 'STAND ON ALL 17s') + '  ·  THE TILTED GENT';
      if (!round) {
        dealerBox.innerHTML = '<div class="bjt-label">Dealer</div><div class="bjt-hand"><div class="cards"><span class="bjt-card back ghost"></span><span class="bjt-card back ghost"></span></div></div>';
        seatsBox.innerHTML = ''; var n0 = S.bots + 1, i0;
        for (i0 = 0; i0 < n0; i0++) { var you0 = (S.seat === 'first' ? 0 : S.seat === 'middle' ? Math.floor(n0 / 2) : n0 - 1) === i0; var d0 = el('div', 'bjt-seat' + (you0 ? ' you' : '')); d0.innerHTML = '<div class="bjt-hand"><div class="cards"></div></div><div class="bjt-circle">' + (you0 ? 'YOU' : i0 + 1) + '</div>'; seatsBox.appendChild(d0); }
        placeSeats(); return;
      }
      dealerBox.innerHTML = '<div class="bjt-label">Dealer</div>' + handHTML(round.dealer, round.dealerDone);
      seatsBox.innerHTML = '';
      round.seats.forEach(function (seat) {
        var d = el('div', 'bjt-seat' + (seat.you ? ' you' : ''));
        d.innerHTML = seat.hands.map(function (h) { return handHTML(h, true); }).join('') + '<div class="bjt-circle' + (seat.you ? ' you' : '') + '">' + (seat.you ? 'YOU' : 'P' + seat.n) + '<small>' + fmt(seat.hands[0].bet) + '</small></div>';
        seatsBox.appendChild(d);
      });
      placeSeats(); renderLive();
    }
    // Seats sit on the arc of the half-ellipse table: seat 1 (first base) on the right, last seat on the left.
    function placeSeats() {
      var seats = seatsBox.children, n = seats.length, i, wide = felt.clientWidth >= 600;
      felt.classList.toggle('arc', wide);
      for (i = 0; i < n; i++) {
        var th = n === 1 ? 90 : 22 + i * (136 / (n - 1)), rad = th * Math.PI / 180;
        var x = 50 + 41 * Math.cos(rad), y = 27 + 46 * Math.sin(rad);
        seats[i].style.left = wide ? x + '%' : ''; seats[i].style.top = wide ? y + '%' : '';
      }
    }
    function renderLive() {
      if (S.showCount) liveCount.innerHTML = '<div class="k">Live count</div><div class="v">RC <b>' + sgn(game.rc) + '</b> · TC <b>' + sgn(Math.round(game.trueCount() * 10) / 10) + '</b> · ' + game.decksRemaining() + ' decks left</div>';
      else liveCount.innerHTML = '<div class="k">Live count hidden</div><div class="v dim">Tick "show live count" above to see it while you learn.</div>';
      var sb = game.suggestedBet(S.unit);
      betAdvice.innerHTML = S.showCount ? '<div class="k">Ramp says</div><div class="v">bet <b>' + fmt(sb) + '</b> (' + (sb / S.unit) + ' unit' + (sb / S.unit === 1 ? '' : 's') + ')</div>' : '';
    }
    function say(text, cls) { msg.className = 'bjt-msg' + (cls ? ' ' + cls : ''); msg.innerHTML = text; }

    /* ---------- round flow ---------- */
    function wait(fn, ms) { timer = setTimeout(function () { timer = null; if (paused) { pendingCheck = fn; return; } fn(); }, ms == null ? S.speed : ms); }
    function resume() { paused = false; pauseBtn.textContent = 'Pause'; if (pendingCheck) { var f = pendingCheck; pendingCheck = false; f(); } }

    function startRound() {
      if (timer) clearTimeout(timer); timer = null; pendingCheck = false;
      if (game.needShuffle) { game.newShoe(); say('New shoe. Count resets to ' + sgn(game.rc) + '.', 'info'); }
      var bet = +betIn.value || S.unit; S.unit = S.unit; saveSettings(S);
      var n = S.bots + 1, youIdx = S.seat === 'first' ? 0 : S.seat === 'middle' ? Math.floor(n / 2) : n - 1, i;
      round = { dealer: { cards: [] }, seats: [], dealerDone: false, stage: 'deal' };
      for (i = 0; i < n; i++) round.seats.push({ n: i + 1, you: i === youIdx, hands: [{ cards: [], bet: i === youIdx ? bet : S.unit }] });
      round.you = round.seats[youIdx];
      stratHi = null; highlightStrategy(); actions.innerHTML = ''; say('Dealing…');
      renderFelt();
      dealCards(0);
    }
    function dealCards(step) {
      // two passes round-robin: seats, then dealer (second dealer card hidden)
      var n = round.seats.length, total = 2 * (n + 1);
      if (step >= total) { afterDeal(); return; }
      var pass = Math.floor(step / (n + 1)), pos = step % (n + 1);
      if (pos < n) round.seats[pos].hands[0].cards.push(game.draw());
      else round.dealer.cards.push(game.draw(pass === 1));
      renderFelt();
      wait(function () { dealCards(step + 1); });
    }
    function afterDeal() {
      var up = round.dealer.cards[0];
      if (up.v === 11 && S.mode === 'play') { offerInsurance(); return; }
      checkDealerBJ();
    }
    function offerInsurance() {
      var tc = game.trueCount(), adviceTake = S.useIndex && tc >= 3;
      say('Dealer shows an ace. Insurance?' + (S.showAdvice ? ' <span class="adv">' + (adviceTake ? 'Index play: take it at TC ≥ +3.' : 'Basic strategy: never.') + '</span>' : ''), 'ask');
      actions.innerHTML = '';
      var yes = el('button', 'bjt-btn ghost', 'Take insurance'), no = el('button', 'bjt-btn gold', 'No insurance');
      yes.type = no.type = 'button';
      yes.addEventListener('click', function () { grade(adviceTake ? 'I' : 'N', 'I', 'Insurance'); round.you.insured = true; checkDealerBJ(); });
      no.addEventListener('click', function () { grade(adviceTake ? 'I' : 'N', 'N', 'Insurance'); checkDealerBJ(); });
      actions.appendChild(yes); actions.appendChild(no);
    }
    function checkDealerBJ() {
      actions.innerHTML = '';
      var up = round.dealer.cards[0], hole = round.dealer.cards[1];
      if ((up.v === 11 || up.v === 10) && B.isBJ([up, hole])) {
        game.reveal(hole); round.dealerDone = true;
        say('Dealer has blackjack.', 'info'); renderFelt();
        settle(); return;
      }
      round.seatIdx = 0; round.handIdx = 0;
      wait(playNext, S.speed);
    }
    function currentHand() { var seat = round.seats[round.seatIdx]; return seat ? seat.hands[round.handIdx] : null; }
    function legalFor(seat, h) {
      var two = h.cards.length === 2, t = B.total(h.cards);
      return { hit: t.t < 21, stand: true, double: two && !h.fromAces, split: two && h.cards[0].v === h.cards[1].v && seat.hands.length < 4 && !h.fromAces, surrender: two && !h.split && S.surrender && !h.fromAces };
    }
    function playNext() {
      var seat = round.seats[round.seatIdx];
      if (!seat) { dealerPlay(); return; }
      var h = seat.hands[round.handIdx];
      if (!h) { round.seatIdx++; round.handIdx = 0; playNext(); return; }
      round.seats.forEach(function (s) { s.hands.forEach(function (x) { x.active = false; }); }); h.active = true;
      var t = B.total(h.cards);
      if (h.fromAces && h.cards.length === 2) { finishHand(h); return; }
      if (B.isBJ(h.cards) && !h.split) { h.status = 'bj'; h.statusText = 'Blackjack'; finishHand(h); return; }
      if (t.t >= 21) { if (t.t > 21) { h.status = 'bust'; h.statusText = 'Bust'; } finishHand(h); return; }
      renderFelt();
      var legal = legalFor(seat, h), up = round.dealer.cards[0].v;
      if (seat.you && S.mode === 'play') { askPlayer(seat, h, legal, up); return; }
      // bot (or drill mode): basic strategy, index plays only for you in drill mode if enabled
      var adv = B.advise(game.T, h.cards, up, legal, game.trueCount(), seat.you && S.useIndex);
      wait(function () { applyAction(seat, h, adv.act, legal); });
    }
    function askPlayer(seat, h, legal, up) {
      var adv = B.advise(game.T, h.cards, up, legal, game.trueCount(), S.useIndex);
      stratHi = { k: B.handKey(h.cards), u: up }; if (stratHi.k[0] === 'p' && !legal.split) { var tt = B.total(h.cards); stratHi.k = (tt.soft ? 's' : 'h') + tt.t; } highlightStrategy();
      say('Your move' + (seat.hands.length > 1 ? ' (hand ' + (round.handIdx + 1) + ' of ' + seat.hands.length + ')' : '') + '.' + (S.showAdvice ? ' <span class="adv">' + (adv.why === 'index' ? 'Index play' : 'Basic strategy') + ': ' + ACT_NAME[adv.act] + '.</span>' : ''), 'ask');
      actions.innerHTML = '';
      [['H', 'Hit', legal.hit], ['S', 'Stand', true], ['D', 'Double', legal.double], ['P', 'Split', legal.split], ['R', 'Surrender', legal.surrender]].forEach(function (a) {
        var b = el('button', 'bjt-btn' + (a[0] === 'S' ? ' gold' : ' ghost'), a[1] + '<kbd>' + a[0] + '</kbd>'); b.type = 'button'; b.disabled = !a[2];
        b.addEventListener('click', function () { grade(adv.act, a[0], describe(h, up), adv.why); applyAction(seat, h, a[0], legal); });
        actions.appendChild(b);
      });
    }
    function describe(h, up) { var t = B.total(h.cards); var k = B.handKey(h.cards); return (k[0] === 'p' ? k.slice(1) + ',' + k.slice(1) : (t.soft ? 'soft ' : '') + t.t) + ' v ' + (up === 11 ? 'A' : up); }
    function grade(correct, chosen, what, why) {
      var st = game.stats; st.decisions++;
      if (correct === chosen) { st.correct++; feedback.innerHTML = '<span class="ok">✓ ' + what + ': ' + (ACT_NAME[chosen] || (chosen === 'I' ? 'take insurance' : 'no insurance')) + ' — correct.</span>'; }
      else { feedback.innerHTML = '<span class="bad">✗ ' + what + ': you chose ' + (ACT_NAME[chosen] || (chosen === 'I' ? 'insurance' : 'no insurance')) + '; ' + (why === 'index' ? 'the index play' : 'basic strategy') + ' says <b>' + (ACT_NAME[correct] || (correct === 'I' ? 'take insurance' : 'no insurance')) + '</b>.</span>'; }
      renderStats();
    }
    function applyAction(seat, h, act, legal) {
      actions.innerHTML = ''; h.active = true;
      if (act === 'R') { h.status = 'sur'; h.statusText = 'Surrendered'; h.surrendered = true; finishHand(h); return; }
      if (act === 'P') {
        var c2 = h.cards.pop(), h2 = { cards: [c2], bet: h.bet, split: true }; h.split = true;
        if (c2.v === 11) { h.fromAces = true; h2.fromAces = true; }
        seat.hands.splice(round.handIdx + 1, 0, h2);
        h.cards.push(game.draw()); renderFelt();
        wait(function () { h2.cards.push(game.draw()); renderFelt(); wait(function () { playNext(); }); });
        return;
      }
      if (act === 'D') { h.bet *= 2; h.doubled = true; h.cards.push(game.draw()); renderFelt(); var t = B.total(h.cards); if (t.t > 21) { h.status = 'bust'; h.statusText = 'Bust'; } wait(function () { finishHand(h); }); return; }
      if (act === 'H') { h.cards.push(game.draw()); renderFelt(); var t2 = B.total(h.cards); if (t2.t > 21) { h.status = 'bust'; h.statusText = 'Bust'; wait(function () { finishHand(h); }); return; } if (t2.t === 21) { wait(function () { finishHand(h); }); return; } wait(playNext); return; }
      finishHand(h); // stand
    }
    function scheduleBustRemoval(h) {
      if (!S.bustRemove || !h.bet) return; var r = round;
      setTimeout(function () { if (round !== r) return; h.removed = true; renderFelt(); }, S.bustRemove);
    }
    function finishHand(h) { h.active = false; if (h.status === 'bust') scheduleBustRemoval(h); round.handIdx++; renderFelt(); wait(playNext, Math.min(S.speed, 300)); }
    function dealerPlay() {
      round.seats.forEach(function (s) { s.hands.forEach(function (x) { x.active = false; }); });
      game.reveal(round.dealer.cards[1]); round.dealerDone = true; renderFelt();
      var anyLive = round.seats.some(function (s) { return s.hands.some(function (x) { return !x.status || x.status === 'bj'; }); });
      var onlyBJ = !round.seats.some(function (s) { return s.hands.some(function (x) { return !x.status; }); });
      function step() {
        var t = B.total(round.dealer.cards);
        if (anyLive && !onlyBJ && (t.t < 17 || (t.t === 17 && t.soft && S.h17))) { round.dealer.cards.push(game.draw()); renderFelt(); wait(step); return; }
        settle();
      }
      wait(step);
    }
    function settle() {
      var d = B.total(round.dealer.cards), dBJ = B.isBJ(round.dealer.cards), st = game.stats, lines = [];
      round.seats.forEach(function (seat) {
        seat.hands.forEach(function (h) {
          var t = B.total(h.cards), net = 0, txt;
          if (h.surrendered) { net = -h.bet / 2; txt = 'surrender −½'; }
          else if (dBJ) { net = (B.isBJ(h.cards) && !h.split) ? 0 : -h.bet; txt = net ? 'dealer BJ' : 'push'; }
          else if (t.t > 21) { net = -h.bet; txt = 'bust'; }
          else if (B.isBJ(h.cards) && !h.split) { net = h.bet * 1.5; txt = 'blackjack 3:2'; }
          else if (d.t > 21) { net = h.bet; txt = 'dealer busts'; }
          else if (t.t > d.t) { net = h.bet; txt = 'win'; }
          else if (t.t < d.t) { net = -h.bet; txt = 'lose'; }
          else { net = 0; txt = 'push'; }
          if (seat.you && h === seat.hands[0] && seat.insured) { net += dBJ ? h.bet : -h.bet / 2; txt += dBJ ? ' + insurance' : ' − insurance'; }
          if (!h.removed) { h.status = net > 0 ? 'win' : net < 0 ? 'lose' : 'push'; h.statusText = txt; }
          if (seat.you) { st.net += net; st.hands++; if (net > 0) st.wins++; else if (net < 0) st.losses++; else st.pushes++; lines.push(txt + ' ' + (net ? (net > 0 ? '+' : '') + fmt(net).replace('$', '$') : '')); }
        });
      });
      renderFelt(); renderStats();
      say('Dealer ' + (d.t > 21 ? 'busts' : 'has ' + d.t) + '. You: ' + lines.join(', ') + '.', 'info');
      actions.innerHTML = '';
      var next = el('button', 'bjt-btn gold', 'Deal next hand'); next.type = 'button'; next.addEventListener('click', startRound); actions.appendChild(next);
      // count prompts, at the round boundary
      var wantRC = S.rcEvery > 0 && st.hands > 0 && st.hands % S.rcEvery === 0;
      var dealtNow = S.decks * 52 - game.shoe.length;
      var wantTC = S.tcEvery > 0 && dealtNow - (game.tcMark || 0) >= S.tcEvery;
      if (wantTC) game.tcMark = dealtNow;
      if (wantRC || wantTC) { promptCount(wantRC ? 'rc' : 'tc', function () { if (wantRC && wantTC) promptCount('tc', function () { if (S.autoNext) wait(startRound, 600); }); else if (S.autoNext) wait(startRound, 600); }); return; }
      if (S.autoNext) wait(startRound, Math.max(S.speed * 2, 900));
    }

    /* ---------- in-table count prompts ---------- */
    function promptCount(kind, done) {
      actions.innerHTML = '';
      var box = el('div', 'bjt-prompt');
      box.innerHTML = '<div class="k">' + (kind === 'rc' ? 'Running count check' : 'True count check') + '</div><p>' + (kind === 'rc' ? 'What is the running count right now?' : 'Estimate the decks left in the shoe and give the true count (to the nearest half).') + '</p>';
      var inp = el('input'); inp.type = 'number'; inp.step = kind === 'rc' ? '1' : '0.5'; inp.placeholder = kind === 'rc' ? 'running count' : 'true count';
      var ok = el('button', 'bjt-btn gold', 'Check'); ok.type = 'button';
      var skip = el('button', 'bjt-btn ghost', 'Skip'); skip.type = 'button';
      var out = el('div', 'out');
      box.appendChild(inp); box.appendChild(ok); box.appendChild(skip); box.appendChild(out); actions.appendChild(box); inp.focus();
      function finish() { var n = el('button', 'bjt-btn gold', 'Deal next hand'); n.type = 'button'; n.addEventListener('click', startRound); actions.appendChild(n); done(); }
      ok.addEventListener('click', function () {
        if (inp.value === '') { inp.focus(); return; }
        var st = game.stats, yours = +inp.value;
        if (kind === 'rc') { var off = Math.abs(yours - game.rc); st.countChecks++; st.countOff += off; if (off === 0) st.countExact++;
          out.innerHTML = '<span class="' + (off === 0 ? 'ok' : 'bad') + '">' + (off === 0 ? '✓ Exact.' : '✗ Off by ' + off + '.') + ' Running count is <b>' + sgn(game.rc) + '</b>.</span>'; }
        else { var tc = Math.round(game.trueCount() * 2) / 2, offt = Math.abs(yours - tc); st.tcChecks = (st.tcChecks || 0) + 1; st.tcOff = (st.tcOff || 0) + offt; if (offt <= 0.5) st.tcExact = (st.tcExact || 0) + 1;
          out.innerHTML = '<span class="' + (offt <= 0.5 ? 'ok' : 'bad') + '">' + (offt <= 0.5 ? '✓ Close enough.' : '✗ Off by ' + offt + '.') + ' True count is <b>' + sgn(tc) + '</b> — running count ' + sgn(game.rc) + ' over ' + game.decksRemaining() + ' decks left (' + game.shoe.length + ' cards).</span>'; }
        ok.disabled = true; skip.disabled = true; renderStats(); setTimeout(finish, 1800);
      });
      skip.addEventListener('click', function () { box.remove(); finish(); });
      inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') ok.click(); });
    }

    /* ---------- bet row + count check ---------- */
    var betIn = el('input'); betIn.type = 'number'; betIn.min = '1'; betIn.step = '5'; betIn.value = S.unit;
    var betLab = el('label', 'bjt-field'); betLab.appendChild(el('span', 'k', 'Your bet ($) for the next hand')); betLab.appendChild(betIn); betRow.appendChild(betLab);
    var feedback = el('div', 'bjt-feedback'); betRow.appendChild(feedback);
    var dealBtn = el('button', 'bjt-btn gold', 'Deal'); dealBtn.type = 'button'; dealBtn.addEventListener('click', function () { if (timer) clearTimeout(timer); timer = null; paused = false; pendingCheck = false; startRound(); }); betRow.appendChild(dealBtn);
    betIn.addEventListener('change', function () { S.unit = Math.max(1, +betIn.value || 25); saveSettings(S); });

    checkBtn.addEventListener('click', function () {
      var yours = +rcIn.value; if (isNaN(yours) || rcIn.value === '') { checkOut.innerHTML = '<span class="bad">Type your running count first.</span>'; return; }
      var st = game.stats, off = Math.abs(yours - game.rc); st.countChecks++; st.countOff += off; if (off === 0) st.countExact++;
      checkOut.innerHTML = '<div class="k">Result</div><div class="v ' + (off === 0 ? 'ok' : 'bad') + '">' + (off === 0 ? '✓ Exact.' : '✗ Off by ' + off + '.') + ' Actual running count <b>' + sgn(game.rc) + '</b> · true count <b>' + sgn(Math.round(game.trueCount() * 10) / 10) + '</b> (' + game.decksRemaining() + ' decks left)</div>' +
        '<div class="s">The ramp would bet ' + fmt(game.suggestedBet(S.unit)) + ' right now.</div>';
      rcIn.value = ''; renderStats();
    });
    pauseBtn.addEventListener('click', function () { if (paused) resume(); else { paused = true; pauseBtn.textContent = 'Resume'; } });
    document.addEventListener('keydown', function (e) {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT')) return;
      var k = e.key.toUpperCase(); var btn = Array.prototype.find.call(actions.querySelectorAll('button'), function (b) { var kb = b.querySelector('kbd'); return kb && kb.textContent === k; });
      if (btn && !btn.disabled) { btn.click(); e.preventDefault(); }
      if (k === ' ') { pauseBtn.click(); e.preventDefault(); }
    });

    window.addEventListener('resize', function () { placeSeats(); });

    /* ---------- build ---------- */
    function rebuild(keepNothing) {
      if (timer) clearTimeout(timer); timer = null; paused = false; pendingCheck = false; pauseBtn.textContent = 'Pause';
      game = new B.Game({ rules: { decks: S.decks, h17: S.h17, das: S.das, surrender: S.surrender, penetration: S.penetration }, system: S.system });
      round = null; feedback.innerHTML = ''; checkOut.innerHTML = ''; root.__game = game;
      renderGuide(); renderStrategy(); renderStats(); renderFelt();
      say(S.mode === 'play' ? 'Set your bet and press Deal. Keys: H, S, D, P, R; space pauses.' : 'Count drill: press Deal and everyone plays basic strategy on their own — just keep the count. Space pauses; check your count from the Count tab.', 'info');
    }
    function renderAll() { renderFelt(); renderStats(); }
    rebuild();
  }
  return { mount: mount };
})();
