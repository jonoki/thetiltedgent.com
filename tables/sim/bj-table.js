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
                   unit: 25, showCount: false, showAdvice: false, useIndex: false, autoNext: true, system: 'hilo', bustRemove: 2000, rcEvery: 0, tcEvery: 0, bankroll: 1000, startBankroll: 1000, bonus: 'none', mainChips: [], bonusChips: [], unitSize: 10, rampBets: true };
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
      s.addEventListener('change', function () { S[key] = isNaN(+s.value) || key === 'seat' || key === 'mode' || key === 'system' ? s.value : +s.value; if (key === 'h17' || key === 'das' || key === 'surrender') S[key] = s.value === 'true'; saveSettings(S); if (key === 'bustRemove' || key === 'rcEvery' || key === 'tcEvery' || key === 'bonus') { if (key === 'bonus' && S.bonus === 'none') returnChips('bonus'); renderFelt(); renderBank(); return; } if (key === 'startBankroll') { S.bankroll = S.startBankroll; S.mainChips = []; S.bonusChips = []; S.unitSize = suggestUnit(S.startBankroll); saveSettings(S); } rebuild(); });
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
    bar.appendChild(sel_('Bonus bet', 'bonus', [['none', 'None'], ['21plus3', '21+3 (your two + dealer up)'], ['pairs', 'Perfect Pairs']]));
    bar.appendChild(sel_('Starting bankroll', 'startBankroll', [[500, '$500'], [1000, '$1,000'], [2500, '$2,500'], [5000, '$5,000']]));
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
    tog.appendChild(toggle('Size my bet by the count (ramp × unit)', 'rampBets'));
    wrap.appendChild(tog);

    // main grid: table + side panel
    var grid = el('div', 'bjt-grid');
    var felt = el('div', 'bjt-felt');
    var shoeLine = el('div', 'bjt-shoe'); felt.appendChild(shoeLine);
    var rcBadge = el('div', 'bjt-rcbadge'); rcBadge.hidden = true; felt.appendChild(rcBadge);
    var gaugeRow = el('div', 'bjt-gaugerow');
    gaugeRow.innerHTML = '<div class="bjt-tray" title="discard tray"><div class="stack"></div><span>discards</span></div><div class="bjt-gauge"><div class="segs"></div><div class="fill"></div><div class="cut"></div><div class="lbl"></div></div><div class="bjt-shoebox" title="shoe"><div class="stack"></div><span>shoe</span></div><div class="bjt-tcbox" hidden><b></b><span>true count</span></div>';
    felt.appendChild(gaugeRow);
    var tcBox = gaugeRow.querySelector('.bjt-tcbox'), gauge = gaugeRow.querySelector('.bjt-gauge'), trayStack = gaugeRow.querySelector('.bjt-tray .stack'), shoeStack = gaugeRow.querySelector('.bjt-shoebox .stack');
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
    var declog = el('div', 'bjt-declog'); felt.appendChild(declog);
    var betRow = el('div', 'bjt-bet'); felt.appendChild(betRow);
    grid.appendChild(felt);

    var side = el('div', 'bjt-side');
    var tabs = el('div', 'bjt-tabs'); var panes = {};
    ['Count', 'Strategy', 'Hand values', 'Counting guide', 'Stats', 'Edge'].forEach(function (name, i) {
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
        tile('Hands', st.hands) + tile('Session result', fmt(st.net), st.net < 0 ? 'dn' : st.net > 0 ? 'up' : '', 'rack $' + Math.round(S.bankroll).toLocaleString() + (st.bonusBets ? ' · bonus bets ' + fmt(st.bonusNet) : '')) +
        tile('Strategy accuracy', st.decisions ? acc + '%' : '—', acc >= 95 ? 'up' : acc >= 85 ? '' : 'dn', st.correct + ' of ' + st.decisions + ' decisions') +
        tile('Count checks', st.countChecks ? cacc + '% exact' : '—', cacc >= 90 ? 'up' : '', st.countChecks ? 'average miss ' + (st.countOff / st.countChecks).toFixed(1) : 'none yet') +
        tile('True-count checks', st.tcChecks ? Math.round(100 * (st.tcExact || 0) / st.tcChecks) + '% within ½' : '—', st.tcChecks && (st.tcExact || 0) / st.tcChecks >= 0.9 ? 'up' : '', st.tcChecks ? 'average miss ' + (st.tcOff / st.tcChecks).toFixed(1) : 'none yet') +
        tile('Win / loss / push', st.wins + ' / ' + st.losses + ' / ' + st.pushes) + tile('Shoes dealt', game.shoeNo) + '</div>' +
        '<p class="bjt-help">Basic strategy alone gets the house edge to about half a percent; the count only pays once your strategy accuracy is above 95% and your count checks are exact. Fix the strategy first. The <b>Edge</b> tab prices every decision in dollars and shows what the shoe offered versus what your bets and plays captured.</p>' +
        '<button type="button" class="bjt-btn ghost" id="bjt-reset">Reset session</button>';
      g.querySelector('#bjt-reset').addEventListener('click', function () { S.bankroll = S.startBankroll; S.mainChips = []; S.bonusChips = []; S.unitSize = suggestUnit(S.startBankroll); saveSettings(S); rebuild(true); });
    }
    function tile(k, v, cls, s) { return '<div class="st' + (cls ? ' ' + cls : '') + '"><div class="k">' + k + '</div><div class="v">' + v + '</div>' + (s ? '<div class="s">' + s + '</div>' : '') + '</div>'; }

    /* ---------- rendering the felt ---------- */
    function cardHTML(c, hidden) {
      if (hidden || c.hidden) return '<span class="bjt-card back" aria-label="face-down card"></span>';
      var red = c.s === '♥' || c.s === '♦';
      var tg = S.showCount ? game.system.tags[c.v] : null, tagHTML = tg == null ? '' : '<s class="tag ' + (tg > 0 ? 'up' : tg < 0 ? 'dn' : 'z') + '">' + (tg > 0 ? '+' + tg : tg < 0 ? '−' + (-tg) : '0') + '</s>';
      return '<span class="bjt-card' + (red ? ' red' : '') + '"><b>' + c.label + '</b><i>' + c.s + '</i><u>' + c.s + '</u><em>TG</em>' + tagHTML + '</span>';
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
      rcBadge.hidden = !S.showCount; if (S.showCount) rcBadge.innerHTML = '<span>Running count</span><b>' + sgn(game.rc) + '</b>';
      tcBox.hidden = !S.showCount; if (S.showCount) tcBox.querySelector('b').textContent = sgn(Math.round(game.trueCount() * 10) / 10);
      var trayN = Math.min(12, Math.round(dealt / (totalCards / 12))), shoeN = Math.min(12, Math.ceil(game.shoe.length / (totalCards / 12)));
      trayStack.innerHTML = new Array(trayN + 1).join('<b></b>'); shoeStack.innerHTML = new Array(shoeN + 1).join('<b></b>');
      arcText.textContent = 'BLACKJACK PAYS 3 TO 2  ·  DEALER MUST ' + (S.h17 ? 'HIT SOFT 17' : 'STAND ON ALL 17s') + '  ·  THE TILTED GENT';
      var youIdx0 = S.seat === 'first' ? 0 : S.seat === 'middle' ? Math.floor((S.bots + 1) / 2) : S.bots;
      if (!round) {
        dealerBox.innerHTML = '<div class="bjt-label">Dealer</div><div class="bjt-hand"><div class="cards"><span class="bjt-card back ghost"></span><span class="bjt-card back ghost"></span></div></div>';
        seatsBox.innerHTML = ''; var n0 = S.bots + 1, i0;
        for (i0 = 0; i0 < n0; i0++) { var you0 = youIdx0 === i0; var d0 = el('div', 'bjt-seat' + (you0 ? ' you' : '')); d0.innerHTML = '<div class="bjt-hand"><div class="cards"></div></div>' + circlesHTML(you0 ? null : i0 + 1, you0); seatsBox.appendChild(d0); }
        wireCircles(); placeSeats(); return;
      }
      dealerBox.innerHTML = '<div class="bjt-label">Dealer</div>' + handHTML(round.dealer, round.dealerDone);
      seatsBox.innerHTML = '';
      round.seats.forEach(function (seat) {
        var d = el('div', 'bjt-seat' + (seat.you ? ' you' : ''));
        d.innerHTML = seat.hands.map(function (h) { return handHTML(h, true); }).join('') + circlesHTML(seat.you ? null : seat.n, seat.you, seat);
        seatsBox.appendChild(d);
      });
      wireCircles();
      placeSeats(); renderLive();
    }
    // Betting circles on the felt. Before the deal, your circle shows the chips you've placed (click a chip to take it back,
    // click the circle to target it for the rack); during a round every seat shows its wager as chips.
    function circlesHTML(botN, you, seat) {
      var locked = betLocked(), h = '';
      if (you) {
        var mainChips = round && round.stage !== 'done' ? toChips(seat ? seat.hands.reduce(function (a, x) { return a + x.bet; }, 0) : 0) : S.mainChips;
        var mainSum = sum(mainChips);
        h += '<div class="bjt-circle main' + (target === 'main' && !locked ? ' target' : '') + (locked ? ' locked' : '') + '" data-c="main"><span class="lab">YOU</span>' + (mainChips.length ? stackHTML(mainChips, 'inbet') : '') + '<small>' + (mainSum ? '$' + mainSum.toLocaleString() : 'place bet') + '</small></div>';
        if (S.bonus !== 'none') {
          var bChips = round && round.stage !== 'done' ? (round.bonusStake ? toChips(round.bonusStake) : []) : S.bonusChips, bSum = sum(bChips);
          h += '<div class="bjt-circle bonus' + (target === 'bonus' && !locked ? ' target' : '') + (locked ? ' locked' : '') + '" data-c="bonus"><span class="lab">' + (S.bonus === '21plus3' ? '21+3' : 'PAIRS') + '</span>' + (bChips.length ? stackHTML(bChips, 'inbet') : '') + '<small>' + (bSum ? '$' + bSum.toLocaleString() : 'optional') + '</small></div>';
        }
        return '<div class="bjt-circles' + (S.bonus !== 'none' ? ' two' : '') + '">' + h + '</div>';
      }
      var bet = seat ? seat.hands.reduce(function (a, x) { return a + x.bet; }, 0) : 0;
      return '<div class="bjt-circles"><div class="bjt-circle"><span class="lab">P' + botN + '</span>' + (bet ? stackHTML(toChips(bet), 'inbet') : '') + '<small>' + (bet ? '$' + bet.toLocaleString() : '') + '</small></div></div>';
    }
    function wireCircles() {
      Array.prototype.forEach.call(seatsBox.querySelectorAll('.bjt-seat.you .bjt-circle[data-c]'), function (c) {
        c.addEventListener('click', function (e) {
          var which = c.getAttribute('data-c'); target = which;
          var w = e.target.closest('.chipwrap');
          if (w && !betLocked()) { var arr = which === 'bonus' ? S.bonusChips : S.mainChips; if (arr.length) { S.bankroll += arr.pop(); saveSettings(S); } }
          renderFelt(); renderBank();
        });
      });
    }
    // Seats sit on the arc of the half-ellipse table: seat 1 (first base) on the right, last seat on the left.
    function placeSeats() {
      var seats = seatsBox.children, n = seats.length, i, wide = felt.clientWidth >= 600;
      felt.classList.toggle('arc', wide);
      for (i = 0; i < n; i++) {
        var th = n === 1 ? 90 : 22 + i * (136 / (n - 1)), rad = th * Math.PI / 180;
        var x = 50 + 38 * Math.cos(rad), y = 27 + 45 * Math.sin(rad);
        seats[i].style.left = wide ? x + '%' : ''; seats[i].style.top = wide ? y + '%' : '';
      }
    }
    function renderLive() {
      if (S.showCount) liveCount.innerHTML = '<div class="k">Live count</div><div class="v">RC <b>' + sgn(game.rc) + '</b> · TC <b>' + sgn(Math.round(game.trueCount() * 10) / 10) + '</b> · ' + game.decksRemaining() + ' decks left</div>';
      else liveCount.innerHTML = '<div class="k">Live count hidden</div><div class="v dim">Tick "show live count" above to see it while you learn.</div>';
      var sb = game.suggestedBet(S.unit);
      betAdvice.innerHTML = S.showCount ? '<div class="k">Ramp says</div><div class="v">bet <b>' + fmt(sb) + '</b> (' + (sb / S.unit) + ' unit' + (sb / S.unit === 1 ? '' : 's') + ')</div>' : '';
    }
    function evPct(x) { return (x < 0 ? '−' : '+') + Math.abs(100 * x).toFixed(1) + '%'; }
    function evMoney(x) { return '<b>' + (x < 0 ? '−' : '+') + '$' + Math.abs(x).toFixed(2) + '</b>'; }
    function say(text, cls) { msg.className = 'bjt-msg' + (cls ? ' ' + cls : ''); msg.innerHTML = text; }

    /* ---------- round flow ---------- */
    function wait(fn, ms) { timer = setTimeout(function () { timer = null; if (paused) { pendingCheck = fn; return; } fn(); }, ms == null ? S.speed : ms); }
    function resume() { paused = false; pauseBtn.textContent = 'Pause'; if (pendingCheck) { var f = pendingCheck; pendingCheck = false; f(); } }

    function startRound() {
      if (timer) clearTimeout(timer); timer = null; pendingCheck = false;
      if (game.needShuffle) { game.newShoe(); say('New shoe. Count resets to ' + sgn(game.rc) + '.', 'info'); }
      var bet = sum(S.mainChips); if (bet <= 0) return; lastBet = { main: S.mainChips.slice(), bonus: S.bonusChips.slice() }; S.unit = bet; saveSettings(S);
      var bonusStake0 = sum(S.bonusChips);
      var n = S.bots + 1, youIdx = S.seat === 'first' ? 0 : S.seat === 'middle' ? Math.floor(n / 2) : n - 1, i;
      round = { dealer: { cards: [] }, seats: [], dealerDone: false, stage: 'deal', netBefore: game.stats.net, bonusStake: bonusStake0, tcAtBet: game.trueCount(), betAtStart: bet, costs: 0, bsCosts: 0, gains: 0, missed: 0 };
      for (i = 0; i < n; i++) round.seats.push({ n: i + 1, you: i === youIdx, hands: [{ cards: [], bet: i === youIdx ? bet : S.unitSize }] });
      round.you = round.seats[youIdx];
      stratHi = null; hvHi = null; highlightStrategy(); actions.innerHTML = ''; declog.innerHTML = ''; feedback.innerHTML = ''; say('Dealing…');
      renderFelt(); renderBank();
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
      settleBonus();
      var up = round.dealer.cards[0];
      round.dealEvU = B.dealEv(rulesNow(), round.you.hands[0].cards, up.v, round.tcAtBet);
      if (up.v === 11 && S.mode === 'play') { offerInsurance(); return; }
      checkDealerBJ();
    }
    function offerInsurance() {
      var tc = game.trueCount(), adviceTake = S.useIndex && tc >= 3;
      say('Dealer shows an ace. Insurance?' + (S.showAdvice ? ' <span class="adv">' + (adviceTake ? 'Index play: take it at TC ≥ +3.' : 'Basic strategy: never.') + '</span>' : ''), 'ask');
      actions.innerHTML = '';
      var yes = el('button', 'bjt-btn ghost', 'Take insurance'), no = el('button', 'bjt-btn gold', 'No insurance');
      yes.type = no.type = 'button';
      yes.addEventListener('click', function () { chargeInsurance(true, tc); grade(adviceTake ? 'I' : 'N', 'I', 'Insurance'); round.you.insured = true; S.bankroll -= round.you.hands[0].bet / 2; checkDealerBJ(); });
      no.addEventListener('click', function () { chargeInsurance(false, tc); grade(adviceTake ? 'I' : 'N', 'N', 'Insurance'); checkDealerBJ(); });
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
      hvHi = hvKey(h.cards, up); renderValues(); stratHi = { k: B.handKey(h.cards), u: up }; if (stratHi.k[0] === 'p' && !legal.split) { var tt = B.total(h.cards); stratHi.k = (tt.soft ? 's' : 'h') + tt.t; } highlightStrategy();
      say('Your move' + (seat.hands.length > 1 ? ' (hand ' + (round.handIdx + 1) + ' of ' + seat.hands.length + ')' : '') + '.' + (S.showAdvice ? ' <span class="adv">' + (adv.why === 'index' ? 'Index play' : 'Basic strategy') + ': ' + ACT_NAME[adv.act] + '.</span>' : ''), 'ask');
      actions.innerHTML = '';
      [['H', 'Hit', legal.hit], ['S', 'Stand', true], ['D', 'Double', legal.double], ['P', 'Split', legal.split], ['R', 'Surrender', legal.surrender]].forEach(function (a) {
        var b = el('button', 'bjt-btn' + (a[0] === 'S' ? ' gold' : ' ghost'), a[1] + '<kbd>' + a[0] + '</kbd>'); b.type = 'button'; b.disabled = !a[2];
        b.addEventListener('click', function () { chargeDecision(h, up, legal, a[0], adv, describe(h, up)); grade(adv.act, a[0], describe(h, up), adv.why); applyAction(seat, h, a[0], legal); });
        actions.appendChild(b);
      });
    }
    function describe(h, up) { var t = B.total(h.cards); var k = B.handKey(h.cards); return (k[0] === 'p' ? k.slice(1) + ',' + k.slice(1) : (t.soft ? 'soft ' : '') + t.t) + ' v ' + (up === 11 ? 'A' : up); }
    function grade(correct, chosen, what, why) {
      var st = game.stats; st.decisions++;
      if (correct === chosen) { st.correct++; feedback.innerHTML = '<span class="ok">✓ ' + what + ': ' + (ACT_NAME[chosen] || (chosen === 'I' ? 'take insurance' : 'no insurance')) + ' — correct.</span>'; }
      else { feedback.innerHTML = '<span class="bad">✗ ' + what + ': you chose ' + (ACT_NAME[chosen] || (chosen === 'I' ? 'insurance' : 'no insurance')) + '; ' + (why === 'index' ? 'the index play' : 'basic strategy') + ' says <b>' + (ACT_NAME[correct] || (correct === 'I' ? 'take insurance' : 'no insurance')) + '</b>.</span>'; }
      renderStats(); renderDecLog();
    }
    function renderDecLog() {
      var D = edgeLog().decisions, list = round ? D.filter(function (d) { return d.round === round; }) : [];
      if (!list.length) { declog.innerHTML = ''; return; }
      var h = '<div class="k">This hand</div>';
      list.forEach(function (d, i) {
        var okBS = d.chosen === d.bs, okCount = d.kind === 'ok' || d.kind === 'captured';
        h += '<div class="row"><span class="n">' + (i + 1) + '</span><span class="d">' + d.desc + ' — <b>' + actName(d.chosen) + '</b></span>' +
          '<span class="' + (okBS ? 'ok' : 'bad') + '">' + (okBS ? '✓' : '✗') + ' basic' + (okBS ? '' : ' (' + actName(d.bs) + ')') + '</span>' +
          '<span class="' + (okCount ? 'ok' : 'bad') + '">' + (okCount ? '✓' : '✗') + ' count' + (okCount ? (d.kind === 'captured' ? ' (' + actName(d.bs) + ' by the book; +$' + d.gain.toFixed(2) + ' for deviating)' : '') : ' (' + actName(d.opt) + ')') + '</span>' +
          (okCount ? '' : '<span class="ev">perfect play ' + actName(d.opt) + ' <b>' + evPct(d.evO) + '</b> (' + evMoney(d.evO * d.bet) + ') · your ' + actName(d.chosen) + ' <b>' + evPct(d.evC) + '</b> (' + evMoney(d.evC * d.bet) + ') · net ' + evMoney(-d.cost) + '</span>') + '</div>';
      });
      declog.innerHTML = h;
    }
    function applyAction(seat, h, act, legal) {
      actions.innerHTML = ''; h.active = true;
      if (act === 'R') { h.status = 'sur'; h.statusText = 'Surrendered'; h.surrendered = true; finishHand(h); return; }
      if (act === 'P') {
        var c2 = h.cards.pop(), h2 = { cards: [c2], bet: h.bet, split: true }; h.split = true; if (seat.you) S.bankroll -= h.bet;
        if (c2.v === 11) { h.fromAces = true; h2.fromAces = true; }
        seat.hands.splice(round.handIdx + 1, 0, h2);
        h.cards.push(game.draw()); renderFelt();
        wait(function () { h2.cards.push(game.draw()); renderFelt(); wait(function () { playNext(); }); });
        return;
      }
      if (act === 'D') { if (seat.you) { S.bankroll -= h.bet; } h.bet *= 2; h.doubled = true; h.cards.push(game.draw()); renderFelt(); var t = B.total(h.cards); if (t.t > 21) { h.status = 'bust'; h.statusText = 'Bust'; } wait(function () { finishHand(h); }); return; }
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
          if (seat.you) { st.net += net; st.hands++; if (net > 0) st.wins++; else if (net < 0) st.losses++; else st.pushes++; lines.push(txt + ' ' + (net ? (net > 0 ? '+' : '') + fmt(net).replace('$', '$') : '')); var stake = h.bet + (h === seat.hands[0] && seat.insured ? h.bet / 2 : 0); S.bankroll += stake + net; }
        });
      });
      round.stage = 'done'; var youNet = 0; round.you.hands.forEach(function (h) { var t = B.total(h.cards); }); youNet = st.net - (round.netBefore || 0);
      var rec = recordHand(youNet); S.mainChips.length = 0; saveSettings(S); showPayout(youNet, 'main'); renderFelt(); renderStats(); renderEdge(); renderBank();
      say('Dealer ' + (d.t > 21 ? 'busts' : 'has ' + d.t) + '. You: ' + lines.join(', ') + '. <span class="evline">Deal was worth ' + evMoney(rec.dealEv) + (rec.cost > 0.005 ? ', decisions gave up ' + evMoney(-rec.cost) : '') + ', draw luck ' + evMoney(rec.drawLuck) + '.</span>', 'info');
      actions.innerHTML = '';
      var next = el('button', 'bjt-btn gold', 'Deal next hand'); next.type = 'button'; next.addEventListener('click', autoRebet); actions.appendChild(next);
      // count prompts, at the round boundary
      var wantRC = S.rcEvery > 0 && st.hands > 0 && st.hands % S.rcEvery === 0;
      var dealtNow = S.decks * 52 - game.shoe.length;
      var wantTC = S.tcEvery > 0 && dealtNow - (game.tcMark || 0) >= S.tcEvery;
      if (wantTC) game.tcMark = dealtNow;
      if (wantRC || wantTC) { promptCount(wantRC ? 'rc' : 'tc', function () { if (wantRC && wantTC) promptCount('tc', function () { rebet(); if (S.autoNext) wait(startRoundIfBet, 600); }); else { rebet(); if (S.autoNext) wait(startRoundIfBet, 600); } }); return; }
      wait(function () { rebet(); if (S.autoNext) wait(startRoundIfBet, Math.max(S.speed * 2, 600)); }, 1500);
    }
    function startRoundIfBet() { if (sum(S.mainChips) > 0) startRound(); }
    function rebet() {
      if (sum(S.mainChips) > 0 || betLocked()) return sum(S.mainChips) > 0;
      var mainAmt, bonusAmt = 0;
      if (S.rampBets) { mainAmt = rampUnits(Math.floor(game.trueCount())) * S.unitSize; bonusAmt = lastBet && S.bonus !== 'none' ? sum(lastBet.bonus) : 0; }
      else { if (!lastBet) return false; mainAmt = sum(lastBet.main); bonusAmt = S.bonus !== 'none' ? sum(lastBet.bonus) : 0; }
      if (mainAmt + bonusAmt > S.bankroll) { if (mainAmt <= S.bankroll) bonusAmt = 0; else { renderBank(); say('Not enough in the rack for the next bet. Size down, or rebuy.', 'info'); return false; } }
      toChips(mainAmt).forEach(function (v) { S.mainChips.push(v); S.bankroll -= v; }); toChips(bonusAmt).forEach(function (v) { S.bonusChips.push(v); S.bankroll -= v; });
      saveSettings(S); renderFelt(); renderBank(); return true;
    }
    function autoRebet() { if (rebet()) startRound(); }


    /* ---------- edge pane: what the shoe offered vs what your play captured ----------
       Every decision is priced by the EV engine at the true count in force (the count shifts the card distribution the
       engine plays against), so basic strategy and the count-optimal play can be told apart: a decision is correct,
       a strategy error (worse than basic strategy), a count deviation captured (better than basic strategy because of
       the count) or a count deviation missed (basic strategy when the count said otherwise). Each hand records the true
       count it was bet into and the EV of the two cards it was dealt, so luck splits into the deal and the draw. */
    var DECK_ADJ = { 1: 0.0048, 2: 0.0028, 3: 0.0018, 4: 0.0014, 5: 0.0012, 6: 0.0010, 7: 0.0009, 8: 0.0008 };
    var TIE = 0.002;
    function rulesNow() { return { decks: S.decks, h17: S.h17, das: S.das, surrender: S.surrender, penetration: S.penetration }; }
    function houseEdgeAt(tc) { return B.evEngine(rulesNow(), tc).baseEdge - (DECK_ADJ[S.decks] || 0.001); }
    function edgeAt(tc) { return -houseEdgeAt(tc); } // player edge, signed
    function edgeLog() { return game.edge || (game.edge = { hands: [], decisions: [] }); }
    function classify(evs, chosen, bs, opt) {
      var evC = evs[chosen] != null ? evs[chosen] : -9, evB = evs[bs] != null ? evs[bs] : -9, evO = evs[opt];
      var cost = Math.max(0, evO - evC), d = { chosen: chosen, bs: bs, opt: opt, cost: cost, bsCost: 0, gain: 0, evO: evO, evC: evC, evB: evB };
      if (chosen === opt || cost < TIE) { d.kind = evO - evB >= TIE && chosen !== bs ? 'captured' : 'ok'; if (d.kind === 'captured') d.gain = evO - evB; d.cost = 0; }
      else if (chosen === bs || Math.abs(evC - evB) < TIE) { d.kind = 'missed'; }
      else { d.kind = 'error'; d.bsCost = Math.max(0, evB - evC); }
      return d;
    }
    function chargeDecision(h, up, legal, chosen, adv, desc) {
      var tc = game.trueCount(), ev = B.evFor(rulesNow(), h.cards, up, legal, tc);
      var bs = B.advise(game.T, h.cards, up, legal, null, false).act; if (bs === 'Ds') bs = 'D';
      var d = classify(ev.evs, chosen, bs, ev.best);
      d.desc = desc; d.round = round; d.bet = h.bet; d.tc = tc; d.costU = d.cost; d.cost *= h.bet; d.bsCost *= h.bet; d.gain *= h.bet;
      round.costs += d.cost; round.bsCosts += d.bsCost; round.gains += d.gain; round.missed += d.kind === 'missed' ? d.cost : 0;
      edgeLog().decisions.push(d);
    }
    function chargeInsurance(took, tc) {
      var eng = B.evEngine(rulesNow(), tc), evI = eng.insuranceEv, bet = round.you.hands[0].bet;
      var d = classify({ I: evI, N: 0 }, took ? 'I' : 'N', 'N', evI > 0 ? 'I' : 'N');
      d.desc = 'Insurance at TC ' + sgn(Math.round(tc * 2) / 2); d.round = round; d.bet = bet; d.tc = tc; d.costU = d.cost; d.cost *= bet; d.bsCost *= bet; d.gain *= bet;
      round.costs += d.cost; round.bsCosts += d.bsCost; round.gains += d.gain; round.missed += d.kind === 'missed' ? d.cost : 0;
      edgeLog().decisions.push(d);
    }
    function recordHand(net) {
      var tc = round.tcAtBet, bet = round.betAtStart, tcR = Math.floor(tc), e = edgeAt(tc);
      var rec = { tc: tc, bet: bet, net: net, cost: round.costs, bsCost: round.bsCosts, gain: round.gains, missed: round.missed, e: e, ramp: rampUnits(tcR) * S.unitSize, unit: S.unitSize, dealEv: (round.dealEvU || 0) * bet };
      rec.drawLuck = net - (rec.dealEv - rec.cost); rec.dealLuck = rec.dealEv - bet * e;
      edgeLog().hands.push(rec); return rec;
    }
    function renderEdge() {
      var g = panes['Edge'], L = edgeLog(), H = L.hands, D = L.decisions, base0 = houseEdgeAt(0), n = H.length;
      var money = function (x) { var ax = Math.abs(x); return (x < 0 ? '−' : '') + '$' + (ax < 10 ? ax.toFixed(2) : Math.round(ax).toLocaleString()); };
      var pc = function (x, d) { return (x >= 0 ? '+' : '−') + Math.abs(100 * x).toFixed(d == null ? 2 : d) + '%'; };
      var sumBet = 0, cost = 0, bsCost = 0, gain = 0, missed = 0, net = 0, tcSum = 0, dealEv = 0, dealLuck = 0, drawLuck = 0;
      var W = { flat: { bet: 0, book: 0, you: 0 }, ramp: { bet: 0, book: 0, you: 0 }, mine: { bet: 0, book: 0, you: 0 } };
      H.forEach(function (x) {
        var cu = x.bet ? x.cost / x.bet : 0; sumBet += x.bet; cost += x.cost; bsCost += x.bsCost; gain += x.gain; missed += x.missed; net += x.net; tcSum += x.tc; dealEv += x.dealEv; dealLuck += x.dealLuck; drawLuck += x.drawLuck;
        [['flat', x.unit], ['ramp', x.ramp], ['mine', x.bet]].forEach(function (w) { var o = W[w[0]], b = w[1]; o.bet += b; o.book += b * x.e; o.you += b * (x.e - cu); });
      });
      var yourBS = -base0 - (sumBet ? bsCost / sumBet : 0), avgTc = n ? tcSum / n : 0;
      var h = '<p class="bjt-help">Three things decide your result: the rules, the shoe (the count) and what you do with it — bet sizing and playing. This pane keeps them apart. <b>Player</b> edge is shown positive, house edge negative.</p>';
      h += '<div class="bjt-stats">' +
        tile('Basic strategy, by the book', pc(-base0), 'dn', S.decks + ' deck' + (S.decks > 1 ? 's' : '') + ', ' + (S.h17 ? 'H17' : 'S17') + (S.das ? ', DAS' : '') + (S.surrender ? ', LS' : '') + ' · neutral shoe, flat bets') +
        tile('Basic strategy, as you play it', n ? pc(yourBS) : '—', yourBS >= -base0 - 0.0005 ? '' : 'dn', n ? (bsCost > 0 ? 'strategy errors cost ' + money(bsCost) + ' on ' + money(sumBet) + ' bet' : 'no strategy errors') : 'play some hands') +
        tile('Shoe this session', n ? pc(sumBet ? W.mine.book / sumBet : 0) : '—', W.mine.book > 0 ? 'up' : 'dn', n ? 'edge at your bets over ' + n + ' hands · avg TC ' + sgn(Math.round(avgTc * 10) / 10) : '') +
        tile('Your actual edge', n ? pc(sumBet ? W.mine.you / sumBet : 0) : '—', W.mine.you > 0 ? 'up' : 'dn', n ? 'your bets, your plays' : '') +
        '</div>';
      if (n) {
        h += '<h4>Expected value three ways</h4><div class="tw"><table class="bjt-tags bjt-ev3"><tr><th>Bet sizing</th><th>Wagered</th><th>Book play</th><th>Your play</th><th>Edge</th></tr>';
        [['1 unit flat (' + money(S.unitSize) + ')', W.flat], ['Count-optimal ramp', W.ramp], ['Your sizing', W.mine]].forEach(function (r) { var o = r[1]; h += '<tr><td>' + r[0] + '</td><td>' + money(o.bet) + '</td><td class="' + (o.book >= 0 ? 'up' : 'dn') + '">' + money(o.book) + '</td><td class="' + (o.you >= 0 ? 'up' : 'dn') + '">' + money(o.you) + '</td><td>' + pc(o.bet ? o.you / o.bet : 0) + '</td></tr>'; });
        h += '</table></div><p class="bjt-help">Same shoe, same counts, three ways of betting into it. <b>Book play</b> is the count-optimal play on every hand; <b>your play</b> charges each hand the EV your decisions gave up, scaled to that bet size. Counting pays in two places: the gap between the flat row and the ramp row is bet sizing; the gap between book play and your play is decisions.</p>';
        h += '<h4>Where the money went</h4><div class="bjt-stats">' +
          tile('Expected, your bets & plays', money(W.mine.you), W.mine.you >= 0 ? 'up' : 'dn', 'shoe ' + money(W.mine.book) + ' − decisions ' + money(cost)) +
          tile('Deal luck', money(dealLuck), dealLuck >= 0 ? 'up' : 'dn', 'the two cards you were dealt vs what the count promised') +
          tile('Draw luck', money(drawLuck), drawLuck >= 0 ? 'up' : 'dn', 'the cards after your decisions, and the dealer\'s') +
          tile('Actual result', money(net), net >= 0 ? 'up' : 'dn', 'expected + deal luck + draw luck') +
          '</div>';
        h += '<h4>Decisions</h4><p class="bjt-help">' + D.length + ' priced. Count deviations captured <b class="up">' + money(gain) + '</b> · missed <b class="dn">' + money(missed) + '</b> · strategy errors <b class="dn">' + money(bsCost) + '</b>' + (cost > bsCost + missed + 1e-9 ? ' · other cost vs the count-optimal play ' + money(cost - bsCost - missed) : '') + '.</p>';
        var byKey = {}; D.forEach(function (d) { if (d.kind === 'ok' || d.kind === 'captured') return; var k = d.desc + '|' + d.chosen + '|' + d.opt; (byKey[k] = byKey[k] || { desc: d.desc, chosen: d.chosen, best: d.opt, kind: d.kind, cost: 0, n: 0 }); byKey[k].cost += d.cost; byKey[k].n++; });
        var rows = Object.keys(byKey).map(function (k) { return byKey[k]; }).sort(function (a, b) { return b.cost - a.cost; }).slice(0, 8);
        if (rows.length) { h += '<div class="tw"><table class="bjt-tags bjt-mist"><tr><th>Hand</th><th>You</th><th>Best</th><th>Type</th><th>Times</th><th>Cost</th></tr>';
          rows.forEach(function (r) { h += '<tr><td>' + r.desc + '</td><td>' + actName(r.chosen) + '</td><td>' + actName(r.best) + '</td><td>' + (r.kind === 'error' ? 'strategy' : 'missed index') + '</td><td>' + r.n + '</td><td>' + money(r.cost) + '</td></tr>'; });
          h += '</table></div>'; }
        h += '<p class="bjt-help">Errors are priced by their actual EV at the count, so a wrong stand on 16 v 10 costs cents while a missed double on 11 v 6 costs real money. Index plays are not a separate rulebook here: they are simply the plays the shifted deck makes best.</p>';
      }
      h += '<p class="bjt-help bjt-fine">Model notes: an infinite-deck EV engine for your rule set (adjusted ' + (100 * (DECK_ADJ[S.decks] || 0.001)).toFixed(2) + ' points for ' + S.decks + ' deck' + (S.decks > 1 ? 's' : '') + '; one split, no resplits), re-run at each half-point of true count with the card distribution the count implies (about t more high cards than low per deck at TC +t — Hi-Lo\'s information, not the shoe\'s exact make-up). Good enough to tell you whether your betting and playing are capturing the count — not a simulator-grade number.</p>';
      g.innerHTML = h;
    }
    function actName(a) { return ACT_NAME[a] || (a === 'I' ? 'insure' : a === 'N' ? 'no ins.' : a); }

    /* ---------- hand values pane: EV of every two-card start at the current count ---------- */
    var hvHi = null;
    function renderValues() {
      var g = panes['Hand values'], tc = S.showCount ? B.tcBucket(game.trueCount()) : 0, eng = B.evEngine(rulesNow(), tc), ups = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
      g.innerHTML = '';
      g.appendChild(el('p', 'bjt-help', 'What each two-card hand is worth against each up card, played optimally, as a percentage of the bet — ' + (S.showCount ? 'at the current true count (' + sgn(tc) + ')' : 'at a neutral count (turn on the live count to see it move)') + '. Overall the shoe is worth <b>' + ((-houseEdgeAt(tc) >= 0 ? '+' : '−') + Math.abs(100 * houseEdgeAt(tc)).toFixed(2)) + '%</b> to you here.'));
      function cell(v, key) { var c = v > 0.3 ? 'g3' : v > 0.1 ? 'g2' : v > 0 ? 'g1' : v > -0.15 ? 'r1' : v > -0.35 ? 'r2' : 'r3'; var n = Math.round(v * 100); return '<td class="' + c + (hvHi === key ? ' hi' : '') + '">' + (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(n) + '</td>'; }
      function tbl(title, rows) {
        var h = '<h4>' + title + '</h4><div class="tw"><table class="bjt-strat bjt-hv"><tr><th></th>'; ups.forEach(function (u) { h += '<th>' + (u === 11 ? 'A' : u) + '</th>'; }); h += '</tr>';
        rows.forEach(function (r) { h += '<tr><th>' + r.label + '</th>'; ups.forEach(function (u) { h += cell(eng.startEv(r.a, r.b, u), r.key + 'v' + u); }); h += '</tr>'; });
        return h + '</table></div>';
      }
      var hard = [], soft = [], pairs = [], t;
      for (t = 20; t >= 5; t--) hard.push({ label: String(t), a: t === 13 ? 10 : t - 2, b: t === 13 ? 3 : 2, key: 'h' + t }); // any non-pair, ace-free split of t prices the same (11 would read as an ace)
      for (t = 20; t >= 13; t--) soft.push({ label: 'A,' + (t - 11), a: 11, b: t - 11, key: 's' + t });
      [11, 10, 9, 8, 7, 6, 5, 4, 3, 2].forEach(function (r) { pairs.push({ label: (r === 11 ? 'A' : r) + ',' + (r === 11 ? 'A' : r), a: r, b: r, key: 'p' + r }); });
      g.appendChild(el('div', null, tbl('Hard totals', hard) + tbl('Soft totals', soft) + tbl('Pairs', pairs)));
      g.appendChild(el('p', 'bjt-help', 'A blackjack is worth +150 against everything but an ace or a ten (the dealer might have one too). Read the reds as the price of being dealt the hand: 16 v 10 costs about half your bet whatever you do, which is why surrender exists. The numbers change with the count — at +4 the 12s and 13s against small cards turn into stands and the doubles get fatter.'));
    }
    function hvKey(cards, up) { var t = B.total(cards); var k = cards.length === 2 && cards[0].v === cards[1].v ? 'p' + cards[0].v : (t.soft ? 's' : 'h') + t.t; return k + 'v' + up; }
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
      function finish() { var n = el('button', 'bjt-btn gold', 'Deal next hand'); n.type = 'button'; n.addEventListener('click', autoRebet); actions.appendChild(n); done(); }
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

    /* ---------- chips, bankroll and the betting circles ---------- */
    var DENOMS = [1, 5, 25, 100, 500];
    function chipHTML(v, extra) { return '<span class="chip c' + v + (extra ? ' ' + extra : '') + '"><b>' + (v >= 1000 ? (v / 1000) + 'K' : v) + '</b></span>'; }
    function stackHTML(chips, cls) { var h = '<span class="chipstack' + (cls ? ' ' + cls : '') + '">'; chips.forEach(function (v, i) { h += '<span class="chipwrap" style="bottom:' + (i * 3) + 'px" data-i="' + i + '">' + chipHTML(v) + '</span>'; }); return h + '</span>'; }
    function toChips(amount) { var out = [], i; for (i = DENOMS.length - 1; i >= 0; i--) { while (amount >= DENOMS[i] - 1e-9) { out.push(DENOMS[i]); amount -= DENOMS[i]; } } if (amount > 0.01) out.push(1); return out; }
    function sum(a) { return a.reduce(function (x, y) { return x + y; }, 0); }
    var target = 'main';
    function suggestUnit(bank) { var raw = bank / 100, steps = [1, 2, 5, 10, 25, 50, 100, 250, 500], best = steps[0], i; for (i = 0; i < steps.length; i++) if (steps[i] <= raw) best = steps[i]; return best; }
    function rampUnits(tc) { var ramp = game.system.betRamp, u = ramp[0][1], i; for (i = 0; i < ramp.length; i++) if (tc >= ramp[i][0]) u = ramp[i][1]; return u; }
    function returnChips(which) { var arr = which === 'main' ? S.mainChips : S.bonusChips; S.bankroll += sum(arr); arr.length = 0; saveSettings(S); }
    function betLocked() { return !!(round && round.stage !== 'done'); }

    var bank = el('div', 'bjt-bank');
    var rack = el('div', 'bjt-rack'); bank.appendChild(rack);
    var betctl = el('div', 'bjt-betctl'); bank.appendChild(betctl);
    var feedback = el('div', 'bjt-feedback'); bank.appendChild(feedback);
    var dealBtn = el('button', 'bjt-btn gold', 'Deal'); dealBtn.type = 'button';
    dealBtn.addEventListener('click', function () { if (timer) clearTimeout(timer); timer = null; paused = false; pendingCheck = false; if (sum(S.mainChips) <= 0) { feedback.innerHTML = '<span class="bad">Put chips in the betting circle first — click a chip in your rack.</span>'; return; } startRound(); });
    var rebuy = el('button', 'bjt-btn ghost', 'Rebuy'); rebuy.type = 'button'; rebuy.hidden = true;
    rebuy.addEventListener('click', function () { S.bankroll += S.startBankroll; saveSettings(S); renderBank(); feedback.innerHTML = '<span class="ok">Rebought for $' + S.startBankroll.toLocaleString() + '. The trainer keeps score of how often that happens.</span>'; });
    var btnrow = el('div', 'bjt-bankbtns'); btnrow.appendChild(dealBtn); btnrow.appendChild(rebuy); bank.appendChild(btnrow);
    betRow.appendChild(bank);

    function renderBank() {
      var locked = betLocked();
      rack.innerHTML = '<div class="k">Your rack <b>$' + Math.round(S.bankroll).toLocaleString() + '</b>' + (function () { var d = S.bankroll + sum(S.mainChips) + sum(S.bonusChips) - S.startBankroll; return ' <i>(' + (d >= 0 ? '+' : '−') + '$' + Math.abs(Math.round(d)).toLocaleString() + ' on the session)</i>'; })() + '</div><div class="rackrow"></div>';
      var row = rack.querySelector('.rackrow'), left = S.bankroll;
      DENOMS.forEach(function (v) {
        var n = Math.min(20, Math.floor(left / v)); if (v === 1) n = Math.min(20, Math.round(left)); // show the pile at each denomination
        var pile = el('button', 'pile' + (S.bankroll < v ? ' empty' : ''), stackHTML(new Array(Math.max(1, Math.min(n, 8))).join(',').split(',').map(function () { return v; })) + '<small>$' + v + (n > 8 ? ' ×' + n : '') + '</small>');
        pile.type = 'button'; pile.disabled = locked || S.bankroll < v; pile.title = 'Add a $' + v + ' chip to the ' + (target === 'bonus' ? 'bonus' : 'main') + ' bet';
        pile.addEventListener('click', function () { var arr = target === 'bonus' ? S.bonusChips : S.mainChips; if (target === 'bonus' && S.bonus === 'none') { target = 'main'; arr = S.mainChips; } arr.push(v); S.bankroll -= v; saveSettings(S); renderFelt(); renderBank(); });
        row.appendChild(pile);
      });
      var mainSum = sum(S.mainChips), bonusSum = sum(S.bonusChips);
      betctl.innerHTML = '';
      var unitLab = el('label', 'bjt-field'); unitLab.appendChild(el('span', 'k', '1 unit ($)'));
      var unitIn = el('input'); unitIn.type = 'number'; unitIn.min = '1'; unitIn.step = '1'; unitIn.value = S.unitSize; unitIn.disabled = locked;
      unitIn.addEventListener('change', function () { S.unitSize = Math.max(1, Math.round(+unitIn.value || suggestUnit(S.startBankroll))); saveSettings(S); renderBank(); });
      unitLab.appendChild(unitIn); betctl.appendChild(unitLab);
      var tc = Math.floor(game.trueCount()), units = rampUnits(tc), rampAmt = units * S.unitSize;
      var rampInfo = el('div', 'bjt-rampinfo', S.rampBets
        ? '<div class="k">Ramp</div><div class="v">' + (S.showCount ? 'TC ' + sgn(tc) + ' → ' : '') + '<b>' + units + ' unit' + (units === 1 ? '' : 's') + ' = $' + rampAmt.toLocaleString() + '</b></div><div class="s">1 unit ≈ bankroll ÷ 100. The bet is re-placed at the ramp each hand; ' + (S.showCount ? 'the true count is shown because the live count is on.' : 'the units alone tell you the count is up, so keep counting.') + '</div>'
        : '<div class="k">Flat betting</div><div class="v">ramp off — your last bet is repeated</div>');
      betctl.appendChild(rampInfo);
      var bb = el('div', 'betbtns');
      var rampBtn = el('button', 'bjt-btn ghost small', 'Bet the ramp'); rampBtn.type = 'button'; rampBtn.disabled = locked || rampAmt > S.bankroll + mainSum;
      rampBtn.addEventListener('click', function () { returnChips('main'); toChips(rampAmt).forEach(function (v) { S.mainChips.push(v); S.bankroll -= v; }); saveSettings(S); renderFelt(); renderBank(); });
      var rep = el('button', 'bjt-btn ghost small', 'Repeat last'); rep.type = 'button'; rep.disabled = locked || !lastBet || sum(lastBet.main) + sum(lastBet.bonus) > S.bankroll + mainSum + bonusSum;
      rep.addEventListener('click', function () { returnChips('main'); returnChips('bonus'); lastBet.main.forEach(function (v) { S.mainChips.push(v); S.bankroll -= v; }); if (S.bonus !== 'none') lastBet.bonus.forEach(function (v) { S.bonusChips.push(v); S.bankroll -= v; }); saveSettings(S); renderFelt(); renderBank(); });
      var clear = el('button', 'bjt-btn ghost small danger', 'Clear all bets'); clear.type = 'button'; clear.disabled = locked || (!mainSum && !bonusSum);
      clear.addEventListener('click', function () { returnChips('main'); returnChips('bonus'); renderFelt(); renderBank(); });
      bb.appendChild(rampBtn); bb.appendChild(rep); bb.appendChild(clear); betctl.appendChild(bb);
      dealBtn.disabled = locked || mainSum <= 0;
      rebuy.hidden = !(S.bankroll < 1 && mainSum <= 0);
    }
    var lastBet = null;
    // payout animation: chips appear beside the circle, then flow to the rack (or the bet flows to the dealer)
    function showPayout(net, kind) {
      var c = seatsBox.querySelector(kind === 'bonus' ? '.bjt-seat.you .bjt-circle.bonus' : '.bjt-seat.you .bjt-circle.main'); if (!c) return;
      var fx = el('div', 'payfx ' + (net > 0 ? 'win' : net < 0 ? 'lose' : 'push'));
      if (net > 0) fx.innerHTML = stackHTML(toChips(net), 'pay') + '<b>+$' + net.toLocaleString() + '</b>';
      else if (net < 0) fx.innerHTML = '<b>−$' + Math.abs(net).toLocaleString() + '</b>';
      else fx.innerHTML = '<b>push</b>';
      c.appendChild(fx);
      setTimeout(function () { fx.classList.add('go'); }, 900);
      setTimeout(function () { if (fx.parentNode) fx.parentNode.removeChild(fx); }, 1700);
    }

    /* ---------- bonus side bets (evaluated on the initial deal) ---------- */
    function bonusResult(kind, p1, p2, up) {
      if (kind === 'pairs') {
        if (p1.r !== p2.r) return 0;
        if (p1.s === p2.s) return 25; var red = function (c) { return c.s === '♥' || c.s === '♦'; }; return red(p1) === red(p2) ? 12 : 6;
      }
      var cs = [p1, p2, up], rs = cs.map(function (c) { return c.r === 1 ? 14 : c.r; }).sort(function (a, b) { return a - b; });
      var flush = cs[0].s === cs[1].s && cs[1].s === cs[2].s, trips = rs[0] === rs[2];
      var straight = (rs[2] - rs[1] === 1 && rs[1] - rs[0] === 1) || (rs[0] === 2 && rs[1] === 3 && rs[2] === 14);
      if (trips && flush) return 100; if (straight && flush) return 40; if (trips) return 30; if (straight) return 10; if (flush) return 5; return 0;
    }
    function settleBonus() {
      var bet = sum(S.bonusChips); if (!bet || S.bonus === 'none') return;
      var you = round.you, h = you.hands[0], mult = bonusResult(S.bonus, h.cards[0], h.cards[1], round.dealer.cards[0]);
      var net = mult ? bet * mult : -bet; var st = game.stats; st.bonusNet = (st.bonusNet || 0) + net; st.bonusBets = (st.bonusBets || 0) + 1;
      if (mult) { S.bankroll += bet + bet * mult; feedback.innerHTML = '<span class="ok">Bonus hits: ' + (S.bonus === 'pairs' ? 'pair pays ' : '21+3 pays ') + mult + ':1 — +$' + (bet * mult).toLocaleString() + '.</span>'; }
      S.bonusChips.length = 0; round.bonusStake = 0; saveSettings(S); showPayout(net, 'bonus'); renderFelt(); renderBank();
    }

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
      round = null; feedback.innerHTML = ''; checkOut.innerHTML = ''; root.__game = game; if (typeof S.bankroll !== 'number' || isNaN(S.bankroll)) S.bankroll = S.startBankroll; if (!Array.isArray(S.mainChips)) S.mainChips = []; if (!Array.isArray(S.bonusChips)) S.bonusChips = []; if (!S.unitSize) S.unitSize = suggestUnit(S.startBankroll); renderBank();
      renderGuide(); renderStrategy(); renderValues(); renderStats(); renderEdge(); renderFelt();
      say(S.mode === 'play' ? 'Set your bet and press Deal. Keys: H, S, D, P, R; space pauses.' : 'Count drill: press Deal and everyone plays basic strategy on their own — just keep the count. Space pauses; check your count from the Count tab.', 'info');
    }
    function renderAll() { renderFelt(); renderStats(); renderBank(); }
    rebuild();
  }
  return { mount: mount };
})();
