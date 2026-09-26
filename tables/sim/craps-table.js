/* The Tilted Gent — Craps Table. CrapsTable.mount('#craps') puts a practice craps table on the page.
   Needs craps-engine.js (the rules, the money and the luck ledger). Vanilla JS, no dependencies.
   The felt is built once and updated in place, so keyboard focus survives every bet.
   Settings and the bankroll persist in localStorage 'ttg-crt'; the session ledger starts fresh on load. */
window.CrapsTable = (function () {
  'use strict';
  var CE = window.CrapsEngine;
  var DEFAULTS = { odds: '345', field12: 3, hardOnComeOut: true, buyVig: 'win', layVig: 'upfront', min: 10, start: 1000, bank: 1000, stayUp: true, chip: 5 };
  function load() { try { var s = JSON.parse(localStorage.getItem('ttg-crt') || 'null'); return Object.assign({}, DEFAULTS, s || {}); } catch (e) { return Object.assign({}, DEFAULTS); } }
  function save(s) { try { localStorage.setItem('ttg-crt', JSON.stringify(s)); } catch (e) {} }

  var CHIPS = [1, 5, 25, 100, 500];
  var WORD = { 4: 'FOUR', 5: 'FIVE', 6: 'SIX', 8: 'EIGHT', 9: 'NINE', 10: 'TEN' };
  var PIPS = { 1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8] };
  var STAY = { pass: 1, dontpass: 1, place: 1, buy: 1, lay: 1, hard: 1, big: 1, field: 1, any7: 1, anycraps: 1, two: 1, three: 1, eleven: 1, twelve: 1 };

  function usd(x) {
    var a = Math.round(Math.abs(x) * 100) / 100;
    return '$' + a.toLocaleString('en-US', { minimumFractionDigits: a % 1 ? 2 : 0, maximumFractionDigits: 2 });
  }
  function signed(x) { x = Math.round(x * 100) / 100; return (x > 0 ? '+' : x < 0 ? '−' : '') + usd(x); }
  function an(n) { return (n === 8 || n === 11 ? 'an ' : 'a ') + n; }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function pct(x, d) { return x.toFixed(d == null ? 2 : d) + '%'; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function toChips(a) { var out = []; for (var i = CHIPS.length - 1; i >= 0; i--) while (a >= CHIPS[i] - 1e-9) { out.push(CHIPS[i]); a -= CHIPS[i]; } return out; }
  function stack(a) {
    if (!(a > 0)) return '';
    var c = toChips(a).slice(0, 6).reverse(), h = '<span class="cstk" aria-hidden="true">';
    c.forEach(function (v, i) { h += '<span class="chip c' + v + '" style="bottom:' + (i * 3) + 'px"></span>'; });
    return h + '</span><span class="camt">' + usd(a) + '</span>';
  }
  /* A flat bet with its odds heeled on top, as a dealer stacks them. */
  function pair(flat, odds) {
    var h = '<span class="cpair" aria-hidden="true">' + (flat > 0 ? stack(flat).replace(/<span class="camt">.*<\/span>$/, '') : '') +
      (odds > 0 ? stack(odds).replace('class="cstk"', 'class="cstk heel"').replace(/<span class="camt">.*<\/span>$/, '') : '') + '</span>';
    return h + '<span class="camt">' + usd(flat) + (odds > 0 ? '<br>+' + usd(odds) : '') + '</span>';
  }
  function dieHTML(v) { var h = ''; for (var i = 0; i < 9; i++) h += '<i' + (PIPS[v].indexOf(i) >= 0 ? ' class="p"' : '') + '></i>'; return h; }

  /* ---------- teaching copy: how each bet works ---------- */
  function how(t, R) {
    var lim = CE.ODDS_LABEL[R.odds];
    switch (t) {
      case 'pass': return 'Bet with the shooter. On the come-out, 7 or 11 wins and 2, 3 or 12 loses; any other number becomes the point, and the bet then wins if the point rolls again before a 7. Once there is a point it is a contract bet: it stays until it settles.';
      case 'dontpass': return 'Bet against the shooter. On the come-out, 2 or 3 wins, 12 pushes (the “bar 12”) and 7 or 11 loses; once a point is set it wins if a 7 comes before the point. You may take it down after the point is set, but by then it is a bet in your favour.';
      case 'come': return 'A pass bet made while the point is on. The next roll is its own come-out: 7 or 11 wins, 2, 3 or 12 loses, and any other number moves the bet to that number, where it wins if the number repeats before a 7.';
      case 'dontcome': return 'A don’t pass bet made while the point is on. Next roll: 2 or 3 wins, 12 pushes, 7 or 11 loses; any other number moves it behind that number, where it wins if a 7 comes first.';
      case 'odds': return 'Extra money behind a pass or come bet once it has a number, paid at the true odds of that number beating the 7. The house has no edge on it at all. This table allows ' + lim + '. Odds behind come bets are off on the come-out roll and come back to you if the bet settles then.';
      case 'layodds': return 'Extra money behind a don’t bet, laid at the true odds against the number. No house edge. At ' + lim + ' you may lay enough to win what the pass-side odds would win' + (R.odds === '345' ? ' (6x your flat bet on any number)' : '') + '.';
      case 'place': return 'Wins if the number rolls before a 7; you choose the number, no come-out needed. Off on the come-out roll. It pays less than the true odds, and that gap is the house edge.';
      case 'buy': return 'A place bet paid at the true odds, less a 5% commission charged ' + (R.buyVig === 'win' ? 'only when it wins' : 'up front, when the bet goes down') + '. Off on the come-out roll.';
      case 'lay': return 'Bets that a 7 comes before the number. Paid at the true odds, less 5% of the win, charged ' + (R.layVig === 'win' ? 'only when it wins' : 'up front') + '. Working on every roll.';
      case 'hard': return 'Wins if the number rolls as a pair (3+3 for hard 6) before it rolls any other way or a 7 shows. ' + (R.hardOnComeOut ? 'Working on the come-out (the Las Vegas rule).' : 'Off on the come-out (the Atlantic City rule).');
      case 'big': return 'Wins even money if the number rolls before a 7. The same event as a Place 6 or 8, which pays 7:6 instead of 1:1.';
      case 'field': return 'One roll. Wins on 2, 3, 4, 9, 10, 11 or 12 and loses on 5, 6, 7 or 8. Seven numbers win and four lose, but the four losers come up 20 times in 36.';
      case 'any7': return 'One roll: wins if the next roll is a 7.';
      case 'anycraps': return 'One roll: wins if the next roll is 2, 3 or 12.';
      case 'two': return 'One roll: wins only on a 2 (1+1).';
      case 'three': return 'One roll: wins only on a 3.';
      case 'eleven': return 'One roll: wins only on an 11.';
      case 'twelve': return 'One roll: wins only on a 12 (6+6).';
      case 'horn': return 'Four one-roll bets in one: your chips are split evenly across 2, 3, 11 and 12. The quarter on the number that rolls is paid at its own odds (30 to 1 or 15 to 1) and the other three quarters lose; any other roll loses the lot. Goes down in multiples of $4.';
      case 'world': return 'The horn plus any seven, split five ways. A 7 pays the any-seven fifth at 4 to 1, which exactly covers the four horn fifths that lose, so a 7 is a push; a 2, 3, 11 or 12 pays its fifth at 30 or 15 to 1 while the other four fifths lose. Goes down in multiples of $5.';
      case 'ce': return 'Any craps and eleven, split in half. 2, 3 or 12 pays the craps half at 7 to 1; 11 pays the eleven half at 15 to 1; the other half loses either way. The two circles marked C and E on a real layout. Goes down in multiples of $2.';
      case 'hilo': return 'The 2 and the 12, split in half. Whichever rolls pays its half at 30 to 1 and the other half loses. Goes down in multiples of $2.';
    }
    return '';
  }

  /* ---------- the felt ---------- */
  function z(t, label, extra, attrs) { return '<button type="button" class="z z-' + t + (extra ? ' ' + extra : '') + '" data-t="' + t + '"' + (attrs || '') + '>' + label + '<span class="stk"></span></button>'; }
  function md(a, b) { return '<span class="md2" aria-hidden="true"><span class="md">' + dieHTML(a) + '</span><span class="md">' + dieHTML(b) + '</span></span>'; }
  var BOX = { 4: '4', 5: '5', 6: 'SIX', 8: '8', 9: 'NINE', 10: '10' };   // as printed on a real layout
  /* One end of a craps table, as the player sees it: the pass line wraps the end with the don't pass bar
     inside it, then field, come and the place numbers; the proposition box sits in the middle of the table. */
  function feltHTML() {
    var h = '<div class="cpt-feltwrap"><div class="cpt-felt" role="group" aria-label="Craps layout">';
    h += '<div class="pass-ext" data-proxy="pass" aria-hidden="true"><span>PASS LINE</span></div>';
    h += '<div class="a-dc">' + z('dontcome', '<b>DON’T COME BAR</b>' + md(6, 6)) + '</div>';
    /* A number column: a LAY box on top, the number itself (where come and don't come bets that
       travel here sit, with their odds heeled on top; clicking it places the number), then PLACE and BUY side by side.
       Clicking your come or don't come stack adds odds to it. */
    CE.POINTS.forEach(function (n) {
      h += '<div class="cpt-num a-n' + n + '" data-num="' + n + '">' +
        z('lay', '<small>LAY</small>', 'spot', ' data-n="' + n + '"') +
        '<div class="nbody" data-proxy="place" data-n="' + n + '">' +
          '<button type="button" class="z z-cstk cs-dc" data-t="layodds" data-of="dontcome" data-n="' + n + '" hidden></button>' +
          '<b class="nw' + (n === 6 || n === 9 ? ' word' : '') + '">' + BOX[n] + '</b>' +
          '<button type="button" class="z z-cstk cs-come" data-t="odds" data-of="come" data-n="' + n + '" hidden></button>' +
        '</div>' +
        '<div class="pbrow">' + z('place', '<small>PLACE</small>', 'spot half', ' data-n="' + n + '"') +
        z('buy', '<small>BUY</small>', 'spot half', ' data-n="' + n + '"') + '</div>' +
        '<span class="puck on" hidden aria-hidden="true">ON</span></div>';
    });
    h += '<div class="a-come">' + z('come', '<b>COME</b>') + '</div>';
    h += '<div class="a-field">' + z('field', '<b>FIELD</b><span class="fn"><i class="ring">2</i>3 · 4 · 9 · 10 · 11<i class="ring">12</i></span><small class="fx"></small>') + '</div>';
    h += '<div class="a-big">' + z('big', '<b>6</b><small>BIG</small>', '', ' data-n="6"') + z('big', '<b>8</b><small>BIG</small>', '', ' data-n="8"') + '</div>';
    // lay odds sit on the don't pass bar next to the flat bet; pass odds sit behind the pass line bet, off the line
    h += '<div class="a-dp">' + z('dontpass', '<b>DON’T PASS BAR</b>' + md(6, 6)) + '</div>';
    h += '<div class="a-lodds">' + z('layodds', '<small>ODDS</small>', 'ring', ' data-of="dontpass" hidden') + '</div>';
    h += '<div class="a-pass">' + z('pass', '<b>PASS LINE</b>') + '</div>';
    h += '<div class="a-podds">' + z('odds', '<small>ODDS</small>', 'ring', ' data-of="pass" hidden') + '</div>';
    h += '<div class="a-props"><div class="pk">ONE ROLL</div>' +
      z('any7', '<b>SEVEN</b><small>4 TO 1</small>', 'wide') +
      '<div class="pk">HARDWAYS</div>' +
      z('hard', md(3, 3) + '<small>9 TO 1</small>', '', ' data-n="6"') + z('hard', md(5, 5) + '<small>7 TO 1</small>', '', ' data-n="10"') +
      z('hard', md(4, 4) + '<small>9 TO 1</small>', '', ' data-n="8"') + z('hard', md(2, 2) + '<small>7 TO 1</small>', '', ' data-n="4"') +
      '<div class="pk">ONE ROLL</div>' +
      z('three', md(1, 2) + '<small>15 TO 1</small>') + z('two', md(1, 1) + '<small>30 TO 1</small>') +
      z('twelve', md(6, 6) + '<small>30 TO 1</small>') + z('eleven', md(5, 6) + '<small>15 TO 1</small>') +
      z('anycraps', '<b>ANY CRAPS</b><small>7 TO 1</small>', 'wide') +
      '<div class="pk">SPLIT BETS</div>' +
      z('horn', '<b>HORN</b><small>2·3·11·12</small>') + z('world', '<b>WORLD</b><small>horn + 7</small>') +
      z('ce', '<b>C &amp; E</b><small>craps + 11</small>') + z('hilo', '<b>HI-LO</b><small>2 + 12</small>') + '</div>';
    h += '<div class="cpt-throw" hidden aria-hidden="true"><div class="cpt-result"></div><span class="die"></span><span class="die"></span></div>';
    return h + '</div></div>';
  }

  function sel(key, label, opts, v) {
    var h = '<label class="cpt-field"><span class="k">' + label + '</span><select data-k="' + key + '">';
    opts.forEach(function (o) { h += '<option value="' + o[0] + '"' + (String(o[0]) === String(v) ? ' selected' : '') + '>' + o[1] + '</option>'; });
    return h + '</select></label>';
  }

  function mount(where) {
    var root = document.querySelector(where); if (!root || !CE) return;
    var S = load(), G, T, rolling = false, lastCard = null, rebuys = 0, lastRoll = null;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    root.innerHTML = '<div class="cpt">' +
      '<div class="cpt-bar">' +
        sel('odds', 'Odds limit', CE.ODDS_LIMITS.map(function (l) { return [l, CE.ODDS_LABEL[l]]; }), S.odds) +
        sel('field12', 'Field pays on 12', [[3, '3:1 (triple)'], [2, '2:1 (double)']], S.field12) +
        sel('hardOnComeOut', 'Hardways on come-out', [['true', 'Working (Las Vegas)'], ['false', 'Off (Atlantic City)']], String(S.hardOnComeOut)) +
        sel('buyVig', 'Buy commission', [['win', 'On the win'], ['upfront', 'Up front']], S.buyVig) +
        sel('layVig', 'Lay commission', [['upfront', 'Up front'], ['win', 'On the win']], S.layVig) +
        sel('min', 'Table minimum', [[5, '$5'], [10, '$10'], [25, '$25']], S.min) +
        sel('start', 'Buy-in', [[500, '$500'], [1000, '$1,000'], [5000, '$5,000']], S.start) +
        '<label class="cpt-toggle"><input type="checkbox" data-k="stayUp"' + (S.stayUp ? ' checked' : '') + '> Winning bets stay up</label>' +
        '<p class="cpt-note">Changing a table rule clears the felt and starts a new session.</p>' +
      '</div>' +
      '<div class="cpt-grid"><div class="cpt-main">' +
        '<div class="cpt-tray">' +
          '<div class="cpt-dice" aria-hidden="true"><span class="die"></span><span class="die"></span></div>' +
          '<div class="cpt-state"><span class="puck off" aria-hidden="true">OFF</span><div><div class="k"></div><div class="v"></div></div></div>' +
          '<button type="button" class="cpt-btn gold cpt-roll">Roll the dice</button>' +
        '</div>' +
        '<div class="cpt-msg" aria-live="polite"></div>' +
        feltHTML(S) +
        '<div class="cpt-hint" aria-live="off"></div>' +
        '<div class="cpt-bank">' +
          '<div class="cpt-rack"><div class="k">Chip <i>— pick one, then tap the felt</i></div><div class="rackrow">' +
            CHIPS.map(function (v) { return '<button type="button" class="pile" data-chip="' + v + '" aria-label="$' + v + ' chip"><span class="chip c' + v + '"></span><small>$' + v + '</small></button>'; }).join('') +
            '<button type="button" class="pile take" data-chip="take"><span class="tk">✕</span><small>Take down</small></button>' +
          '</div></div>' +
          '<div class="cpt-money"><div><span class="k">Rack</span><b class="rack"></b></div><div><span class="k">On the felt</span><b class="onfelt"></b></div>' +
            '<div class="cpt-bankbtns"><button type="button" class="cpt-btn ghost small cpt-clear">Take down all</button><button type="button" class="cpt-btn ghost small cpt-rebuy" hidden>Rebuy</button></div></div>' +
        '</div>' +
      '</div>' +
      '<aside class="cpt-side">' +
        '<div class="cpt-tabs" role="tablist">' +
          '<button type="button" role="tab" class="cpt-tab on" data-p="card" aria-selected="true">Bet card</button>' +
          '<button type="button" role="tab" class="cpt-tab" data-p="odds" aria-selected="false">Odds</button>' +
          '<button type="button" role="tab" class="cpt-tab" data-p="session" aria-selected="false">Session</button>' +
        '</div>' +
        '<div class="cpt-pane" data-p="card" role="tabpanel"></div>' +
        '<div class="cpt-pane" data-p="odds" role="tabpanel" hidden></div>' +
        '<div class="cpt-pane" data-p="session" role="tabpanel" hidden></div>' +
      '</aside></div></div>';

    var $ = function (s) { return root.querySelector(s); }, $$ = function (s) { return [].slice.call(root.querySelectorAll(s)); };
    var felt = $('.cpt-felt'), msg = $('.cpt-msg'), hint = $('.cpt-hint'), dice = $$('.cpt-dice .die');
    var throwEl = $('.cpt-throw'), resultEl = $('.cpt-result'), fly = $$('.cpt-throw .die'), skipThrow = null;

    function rules() { return { odds: S.odds, field12: +S.field12, hardOnComeOut: S.hardOnComeOut === true || S.hardOnComeOut === 'true', buyVig: S.buyVig, layVig: S.layVig, min: +S.min }; }
    function newSession() {
      G = CE.create(rules()); T = G.Table({ bankroll: S.bank }); rebuys = 0; lastRoll = null;
      $('.z-field .fx').textContent = '2 pays double · 12 pays ' + (G.rules.field12 === 3 ? 'triple' : 'double');
      renderOdds(); render(); renderSession();
    }
    function persist() { S.bank = Math.round((T.bank + T.onFelt()) * 100) / 100; save(S); }

    /* ---------- zones <-> bets ---------- */
    function parentFor(el) {
      var of = el.dataset.of, n = el.dataset.n ? +el.dataset.n : null;
      for (var i = 0; i < T.bets.length; i++) {
        var b = T.bets[i];
        if (b.type === of && b.num != null && (n == null || b.num === n)) return b;
      }
      return null;
    }
    function betFor(el) {
      var t = el.dataset.t, n = el.dataset.n ? +el.dataset.n : null;
      if (t === 'odds' || t === 'layodds') { var p = parentFor(el); if (!p) return null; for (var i = 0; i < T.bets.length; i++) if (T.bets[i].parent === p.id) return T.bets[i]; return null; }
      for (var j = 0; j < T.bets.length; j++) {
        var b = T.bets[j]; if (b.type !== t) continue;
        if (t === 'pass' || t === 'dontpass') return b;
        if (t === 'come' || t === 'dontcome') { if (b.num == null) return b; continue; }
        if (n == null || b.num === n) return b;
      }
      return null;
    }
    function keyFor(el) {
      var t = el.dataset.t, n = el.dataset.n ? +el.dataset.n : null;
      if (t === 'odds' || t === 'layodds') { var p = parentFor(el); n = p ? p.num : (el.dataset.of === 'pass' || el.dataset.of === 'dontpass') ? T.point : n; return n ? t + n : null; }
      return t + (n != null ? n : '');
    }

    /* ---------- placing and taking down ---------- */
    function lineBet(type) { for (var i = 0; i < T.bets.length; i++) if (T.bets[i].type === type) return T.bets[i]; return null; }
    function act(el) {
      if (rolling) return;
      var redirected = '';
      // Once the point is set a line bet can't be added to, so chips put behind it are odds, as at a real table.
      if (S.chip !== 'take' && (el.dataset.t === 'pass' || el.dataset.t === 'dontpass') && T.point != null) {
        var lb = lineBet(el.dataset.t);
        if (lb && lb.num != null) {
          el = felt.querySelector(el.dataset.t === 'pass' ? '.z-odds[data-of="pass"]' : '.z-layodds[data-of="dontpass"]');
          redirected = el.dataset.t === 'odds' ? 'With the point on, chips behind the pass line are odds. ' : 'With the point on, chips added to the don’t pass bet are lay odds. ';
        }
      }
      var t = el.dataset.t, spec, p = null;
      showCard(el);
      if (S.chip === 'take') {
        var b = betFor(el);
        if (!b && el.classList.contains('z-cstk')) b = parentFor(el);   // no odds on it: the stack itself is the bet
        if (!b) { say('Nothing on ' + label(el) + ' to take down.', 'info'); return; }
        var v = T.v(b), r = T.remove(b.id);
        if (!r.ok) { say(r.reason, 'info'); return; }
        say('Took down ' + label(el) + ': ' + usd(r.removed.reduce(function (a, x) { return a + x.amount; }, 0)) + ' back to the rack.' +
            (v > 0.005 ? ' <span class="dimn">That bet was worth ' + signed(v) + ' to you on average — taking it down gives that away.</span>' : ''), 'info');
        persist(); render(); renderSession(); return;
      }
      if (t === 'odds' || t === 'layodds') {
        p = parentFor(el);
        if (!p) { say(t === 'odds' ? 'Odds go behind a pass or come bet once it has a number.' : 'Lay odds go behind a don’t pass or don’t come bet once it has a number.', 'info'); return; }
        spec = { type: t, parent: p.id };
      } else spec = { type: t, num: el.dataset.n ? +el.dataset.n : null };
      var n = p ? p.num : spec.num, u = G.unit(t, n), mn = G.minBet(t, n), cur = T.find(spec), have = cur ? cur.amount : 0;
      var a = Math.max(1, Math.round(S.chip / u)) * u, note = '';
      if (a !== S.chip) note = G.name(t, n) + ' goes down in $' + u + ' units so it pays in whole dollars.';
      if (have + a < mn) { a = mn - have; note = 'The minimum on ' + G.name(t, n) + ' is ' + usd(mn) + '.'; }
      if (p) {
        var room = Math.floor((G.maxOdds(t, n, p.amount) - have) / u) * u;
        if (room <= 0) { say('That’s the most ' + CE.ODDS_LABEL[G.rules.odds] + ' odds allow behind ' + usd(p.amount) + ' on the ' + n + ': ' + usd(have) + '.', 'info'); return; }
        if (a > room) { a = room; note = 'Filled to the ' + CE.ODDS_LABEL[G.rules.odds] + ' maximum: ' + usd(have + a) + ' behind ' + usd(p.amount) + '.'; }
      }
      var res = T.place({ type: t, num: spec.num, parent: spec.parent, amount: a });
      if (!res.ok) { say(res.reason, 'info'); return; }
      var vig = res.bet.vig && G.vigRate(t, n).n ? ' (plus ' + usd(CE.num(G.vigRate(t, n)) * a) + ' commission)' : '';
      say(redirected + usd(a) + ' on ' + G.name(t, n) + vig + '.' + (note ? ' <span class="dimn">' + note + '</span>' : ''), 'info');
      persist(); render(); renderSession();
    }
    function label(el) { var k = keyFor(el); return k && G.byKey[k] ? G.byKey[k].name : el.dataset.t === 'odds' ? 'the odds' : 'that spot'; }
    function clearAll() {
      if (rolling) return;
      var back = 0, stuck = [];
      T.bets.slice().forEach(function (b) { if (!T.get(b.id)) return; if (!T.removable(b)) { stuck.push(G.name(b.type, b.num)); return; } var r = T.remove(b.id); if (r.ok) r.removed.forEach(function (x) { back += x.amount; }); });
      say(back ? usd(back) + ' back to the rack.' + (stuck.length ? ' <span class="dimn">' + stuck.join(', ') + ' stay' + (stuck.length === 1 ? 's' : '') + ' up: contract bets.</span>' : '') : 'Nothing to take down.', 'info');
      persist(); render(); renderSession();
    }

    /* ---------- rolling ---------- */
    function roll() {
      if (rolling) { if (skipThrow) skipThrow(); return; }
      if (!T.bets.length) { say('Put a chip down first — the Pass line is the place to start.', 'info'); return; }
      var d1 = 1 + Math.floor(T.rng() * 6), d2 = 1 + Math.floor(T.rng() * 6);
      rolling = true;
      $$('.z.win,.z.lose,.z.move,.cpt-num.win,.cpt-num.lose,.cpt-num.move').forEach(function (e) { e.classList.remove('win', 'lose', 'move'); });
      var call = callFor(d1, d2);
      var placeOff = T.point == null && T.bets.some(function (b) { return (b.type === 'place' || b.type === 'buy') && !G.rules.placeOnComeOut; });
      var res = T.roll(d1, d2);                 // settled now; the felt shows it once the dice are back in the tray
      var net = res.events.reduce(function (a, e) { return a + (e.net || 0); }, 0);
      throwDice(d1, d2, call, net, function () { finish(res, placeOff); });
    }
    /* What the stickman calls, and what it means for the line. */
    function callFor(d1, d2) {
      var t = d1 + d2, p = T.point, even = t === 4 || t === 6 || t === 8 || t === 10;
      var NAME = { 2: 'ACES', 3: 'ACE-DEUCE', 4: 'FOUR', 5: 'FIVE', 6: 'SIX', 7: 'SEVEN', 8: 'EIGHT', 9: 'NINE', 10: 'TEN', 11: 'YO-LEVEN', 12: 'TWELVE' };
      var c = NAME[t] + (even ? (d1 === d2 ? ' THE HARD WAY' : ', EASY') : ''), s;
      if (p == null) s = t === 7 || t === 11 ? 'Natural on the come-out: pass wins' : t === 2 || t === 3 ? 'Craps: pass loses, don’t wins' : t === 12 ? 'Craps: pass loses, don’t pushes' : 'The point is ' + t;
      else s = t === p ? 'Winner: the point is made' : t === 7 ? 'Seven out' : 'The point is still ' + p;
      return { c: c, s: s };
    }
    /* The throw, in four beats:
       1. the dice come in from the middle of the table, bounce, hit the back wall and settle on the felt;
       2. they sit there, un-highlighted, long enough to see where they landed;
       3. the view zooms in on them under a spotlight, with the total and the stickman's call;
       4. they zoom back out into the tray and the felt settles the bets.
       Tap the felt or press Roll to skip. Reduced motion: no travel or zoom; the dice appear, then the result. */
    function tf(x, y, r, s) { return 'translate(' + x + 'px,' + y + 'px) rotate(' + r + 'deg) scale(' + s + ')'; }
    function throwDice(d1, d2, call, net, done) {
      var fr = felt.getBoundingClientRect(), W = fr.width, H = fr.height;
      var vt = Math.max(0, -fr.top), vb = Math.min(H, window.innerHeight - fr.top);
      if (vb - vt < 240) { vt = 0; vb = H; }
      var cy = (vt + vb) / 2, sz = dice[0].offsetWidth || 52;
      function clampY(y) { return Math.max(vt + 6, Math.min(vb - sz - 6, y)); }
      var rest = [[W * 0.28 - sz / 2, clampY(cy + 6)], [W * 0.28 + sz * 0.85, clampY(cy - 20)]], restRot = [13, -19];
      // zoomed: both dice side by side, k times bigger, centred in the visible part of the felt
      var k = Math.min(2.5, (W * 0.34) / sz), Z = k * sz, zy = Math.max(vt + Z / 2 + 14, cy - 40);
      var zoom = [[W / 2 - Z / 2 - 10 - sz / 2, zy - sz / 2], [W / 2 + Z / 2 + 10 - sz / 2, zy - sz / 2]];
      var timers = [], anims = [], iv = null, ended = false;
      function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
      function end() {
        if (ended) return; ended = true; skipThrow = null;
        timers.forEach(clearTimeout); clearInterval(iv);
        anims.forEach(function (a) { try { a.cancel(); } catch (e) {} });
        throwEl.hidden = true; throwEl.style.overflow = ''; throwEl.classList.remove('dim', 'landed'); resultEl.classList.remove('show');
        dice.forEach(function (d) { d.classList.remove('away'); });
        done();
      }
      function move(f, from, to, ms, easing) {
        var a = f.animate([{ transform: from }, { transform: to }], { duration: ms, easing: easing || 'cubic-bezier(.4,0,.2,1)', fill: 'forwards' });
        anims.push(a); return a;
      }
      function land() {
        clearInterval(iv);
        fly[0].innerHTML = dieHTML(d1); fly[1].innerHTML = dieHTML(d2);
        throwEl.classList.add('landed');
        later(zoomIn, reduce ? 700 : 650);
      }
      function zoomIn() {
        throwEl.style.setProperty('--sx', (W / 2) + 'px'); throwEl.style.setProperty('--sy', zy + 'px');
        throwEl.classList.add('dim');
        resultEl.style.top = (zy + Z / 2 + 14) + 'px';
        fly.forEach(function (f, i) {
          if (reduce) f.style.transform = tf(zoom[i][0], zoom[i][1], 0, k);
          else move(f, tf(rest[i][0], rest[i][1], restRot[i], 1), tf(zoom[i][0], zoom[i][1], 0, k), 380, 'cubic-bezier(.2,.8,.25,1)');
        });
        later(function () { resultEl.classList.add('show'); }, reduce ? 0 : 220);
        later(zoomOut, reduce ? 1900 : 1750);
      }
      function zoomOut() {
        resultEl.classList.remove('show'); throwEl.classList.remove('dim');
        if (reduce) { end(); return; }
        var fr2 = felt.getBoundingClientRect(); throwEl.style.overflow = 'visible';
        fly.forEach(function (f, i) {
          var tr = dice[i].getBoundingClientRect();
          move(f, tf(zoom[i][0], zoom[i][1], 0, k), tf(tr.left - fr2.left, tr.top - fr2.top, 0, tr.width / sz), 460);
        });
        later(end, 480);
      }
      skipThrow = end;
      resultEl.innerHTML = '<div class="n">' + (d1 + d2) + '</div><div class="c">' + call.c + '</div><div class="s">' + call.s + '</div>' +
        (net ? '<div class="s ' + (net > 0 ? 'up' : 'dn') + '">Your bets: ' + signed(net) + '</div>' : '') + '<div class="t">tap to continue</div>';
      throwEl.hidden = false;
      dice.forEach(function (d) { d.classList.add('away'); });
      fly.forEach(function (f) { f.style.width = f.style.height = sz + 'px'; });
      if (reduce) {
        fly.forEach(function (f, i) { f.style.transform = tf(rest[i][0], rest[i][1], restRot[i], 1); });
        fly[0].innerHTML = dieHTML(d1); fly[1].innerHTML = dieHTML(d2);
        land(); return;
      }
      // in the air the dice are drawn a little larger; each touch of the felt brings them back to size
      fly.forEach(function (f, i) {
        var s = i ? 1 : -1, y0 = cy - 50 + i * 56;
        anims.push(f.animate([
          { transform: tf(W + 40 + i * 30, y0, 0, 1.35), offset: 0 },
          { transform: tf(W * 0.52 + i * 24, clampY(cy - 14 + i * 26), s * 260, 1), offset: 0.3, easing: 'ease-out' },
          { transform: tf(W * 0.3 + i * 14, clampY(cy - 44 + i * 30), s * 390, 1.16), offset: 0.46, easing: 'ease-in' },
          { transform: tf(W * 0.04 + i * 12, clampY(cy - 4 + i * 22), s * 520, 1), offset: 0.62, easing: 'ease-out' },
          { transform: tf(rest[i][0] - 16, rest[i][1] - 16, restRot[i] + s * 640, 1.07), offset: 0.82, easing: 'ease-in' },
          { transform: tf(rest[i][0], rest[i][1], restRot[i] + s * 720, 1), offset: 1 }
        ], { duration: 1150 + i * 80, easing: 'linear', fill: 'forwards' }));
      });
      iv = setInterval(function () { fly[0].innerHTML = dieHTML(1 + Math.floor(Math.random() * 6)); fly[1].innerHTML = dieHTML(1 + Math.floor(Math.random() * 6)); }, 65);
      later(land, 1250);
    }
    function finish(res, hadPlaceOff) {
      var d1 = res.d1, d2 = res.d2;
      lastRoll = res;
      dice[0].innerHTML = dieHTML(d1); dice[1].innerHTML = dieHTML(d2);
      var up = [], fail = [];
      res.events.forEach(function (e) {
        var b = e.bet, el = zoneEl(b, e.r === 'move' ? e.num : b.num);
        if (el) el.classList.add(e.r === 'win' ? 'win' : e.r === 'lose' ? 'lose' : 'move');
        if (S.stayUp && e.r === 'win' && STAY[b.type]) {
          var r = T.place({ type: b.type, num: b.type === 'pass' || b.type === 'dontpass' ? null : b.num, amount: b.amount });
          if (r.ok) up.push(G.name(b.type, r.bet.num == null ? null : b.num)); else fail.push(G.name(b.type, b.type === 'pass' || b.type === 'dontpass' ? null : b.num));
        }
      });
      narrate(res, hadPlaceOff, up, fail);
      rolling = false;
      persist(); render(); renderSession();
    }
    function zoneEl(b, n) {
      if (b.type === 'come' || b.type === 'dontcome') return n != null ? felt.querySelector('.cpt-num[data-num="' + n + '"]') : felt.querySelector('.z-' + b.type);
      if (b.type === 'odds' || b.type === 'layodds') return b.come ? felt.querySelector('.cpt-num[data-num="' + b.num + '"]') : felt.querySelector('.z-' + (b.type === 'odds' ? 'pass' : 'dontpass'));
      if (b.type === 'pass' || b.type === 'dontpass') return felt.querySelector('.z-' + b.type);
      return felt.querySelector('.z-' + b.type + (b.num != null ? '[data-n="' + b.num + '"]' : ''));
    }
    function short(b) {
      if (b.type === 'odds') return (b.come ? 'Come odds on the ' : 'Pass odds on the ') + b.num;
      if (b.type === 'layodds') return (b.come ? 'Don’t come lay odds on the ' : 'Don’t pass lay odds on the ') + b.num;
      if (b.type === 'come' || b.type === 'dontcome') return G.name(b.type) + (b.num != null ? ' on the ' + b.num : '');
      if (b.type === 'pass' || b.type === 'dontpass') return G.name(b.type);
      return G.name(b.type, b.num);
    }
    function narrate(res, placeOff, up, fail) {
      var t = res.total, story;
      var head = '<span class="roll">' + res.d1 + ' + ' + res.d2 + ' = <b>' + t + '</b>' + (res.hard && t >= 4 && t <= 10 ? ' <em>hard ' + t + '</em>' : '') + '</span> ';
      if (res.comeOut) {
        if (t === 7 || t === 11) story = 'A natural on the come-out: pass wins, don’t pass loses.';
        else if (t === 2 || t === 3) story = 'Craps on the come-out: pass loses, don’t pass wins.';
        else if (t === 12) story = 'Twelve on the come-out: pass loses and don’t pass pushes (the “bar 12”).';
        else story = 'The point is ' + t + '. Pass now wins if ' + an(t) + ' comes before a 7; don’t pass wins if the 7 comes first.';
      } else if (t === res.pointBefore) story = 'Point made: pass wins, don’t pass loses. Next roll is a new come-out.';
      else if (t === 7) story = 'Seven out: pass, come, place and buy bets lose; the don’t side wins. Next roll is a new come-out.';
      else story = 'No decision on the line; the point is still ' + res.pointBefore + '.';
      var lines = [], net = 0;
      res.events.forEach(function (e) {
        if (e.r === 'move') { if (e.bet.type === 'come' || e.bet.type === 'dontcome') lines.push(G.name(e.bet.type) + (e.bet.type === 'come' ? ' moves to the ' : ' goes behind the ') + e.num); return; }
        net += e.net;
        lines.push(short(e.bet) + ' <b class="' + (e.net > 0 ? 'up' : e.net < 0 ? 'dn' : 'au') + '">' + (e.r === 'push' ? 'push' : signed(e.net)) + '</b>');
      });
      var h = head + story;
      if (placeOff && (CE.POINTS.indexOf(t) >= 0 || t === 7)) h += ' <span class="dimn">Place and buy bets were off on the come-out.</span>';
      if (lines.length) h += '<span class="evs">' + lines.join(' · ') + '</span>';
      h += '<span class="evline">This roll: <b class="' + (net > 0 ? 'up' : net < 0 ? 'dn' : '') + '">' + signed(net) + '</b> · luck on the bets you had up: ' + signed(res.luck) +
           (up.length ? ' · back up: ' + up.join(', ') : '') + (fail.length ? ' · not enough in the rack to put back ' + fail.join(', ') : '') + '</span>';
      msg.className = 'cpt-msg'; msg.innerHTML = h;
    }
    function say(h, cls) { msg.className = 'cpt-msg' + (cls ? ' ' + cls : ''); msg.innerHTML = h; }

    /* ---------- rendering ---------- */
    function render() {
      var point = T.point;
      $$('.z').forEach(function (el) {
        var t = el.dataset.t, b = betFor(el), s = el.querySelector('.stk');
        var noParent = (t === 'odds' || t === 'layodds') && !parentFor(el);
        if (t === 'odds' || t === 'layodds') el.hidden = noParent;          // an odds spot exists only behind a bet with a number
        if (s) s.innerHTML = b ? stack(b.amount) : '';
        el.classList.toggle('has', !!b);
        var closed = ((t === 'pass' || t === 'dontpass') && point != null && !b) || ((t === 'come' || t === 'dontcome') && point == null);
        el.classList.toggle('closed', closed);
        var k = keyFor(el), c = k && G.byKey[k];
        el.setAttribute('aria-label', (c ? c.name + ', pays ' + c.pays + ', house edge ' + pct(c.edgePct) : label(el)) + (b ? ', your bet ' + usd(b.amount) : ''));
      });
      // pass and don't pass odds: an empty ring behind the bet until odds go down, then the chips
      [['odds', 'pass'], ['layodds', 'dontpass']].forEach(function (x) {
        var el = felt.querySelector('.z-' + x[0] + '[data-of="' + x[1] + '"]'), b = betFor(el);
        el.querySelector('small').hidden = !!b;
      });
      CE.POINTS.forEach(function (n) {
        var box = felt.querySelector('.cpt-num[data-num="' + n + '"]'), by = {}, co = null, dco = null;
        T.bets.forEach(function (b) { if (b.num === n && b.parent == null) by[b.type] = b; });
        T.bets.forEach(function (b) { if (by.come && b.parent === by.come.id) co = b; if (by.dontcome && b.parent === by.dontcome.id) dco = b; });
        var cs = box.querySelector('.cs-come'), ds = box.querySelector('.cs-dc');
        cs.hidden = !by.come; cs.innerHTML = by.come ? pair(by.come.amount, co ? co.amount : 0) : '';
        ds.hidden = !by.dontcome; ds.innerHTML = by.dontcome ? pair(by.dontcome.amount, dco ? dco.amount : 0) : '';
        if (by.come) cs.setAttribute('aria-label', 'Your come bet on the ' + n + ': ' + usd(by.come.amount) + (co ? ', odds ' + usd(co.amount) : '') + '. Add odds');
        if (by.dontcome) ds.setAttribute('aria-label', 'Your don’t come bet on the ' + n + ': ' + usd(by.dontcome.amount) + (dco ? ', lay odds ' + usd(dco.amount) : '') + '. Lay odds');
        box.querySelector('.puck.on').hidden = point !== n;
        box.classList.toggle('point', point === n);
      });
      var off = $('.cpt-state .puck'); off.hidden = point != null;
      $('.cpt-state .k').textContent = point == null ? 'Come-out roll' : 'Point is ' + point;
      $('.cpt-state .v').textContent = point == null ? 'Puck is off: line bets go down now.' : cap(an(point)) + ' before a 7 wins for pass; the 7 first wins for don’t.';
      if (!lastRoll) { dice[0].innerHTML = dieHTML(6); dice[1].innerHTML = dieHTML(5); }
      $$('.pile').forEach(function (p) { var v = p.dataset.chip; p.setAttribute('aria-pressed', String(v === String(S.chip))); p.disabled = v !== 'take' && +v > T.bank; });
      $('.rack').textContent = usd(T.bank); $('.onfelt').textContent = usd(T.onFelt());
      $('.cpt-rebuy').hidden = !(T.bank < G.minBet('pass') && !T.bets.length);
      if (lastCard) showCard(lastCard);
      renderOddsPoint();
    }

    /* ---------- bet card (side pane + the one-line hint under the felt) ---------- */
    function showCard(el) {
      lastCard = el;
      var t = el.dataset.t, k = keyFor(el), c = k && G.byKey[k], b = betFor(el), R = G.rules;
      var pane = $('.cpt-pane[data-p="card"]');
      if (!c) {
        hint.innerHTML = '<b>' + (t === 'odds' ? 'Odds' : 'Lay odds') + '</b> · true odds · house edge <span class="band up">0.00%</span>';
        pane.innerHTML = '<h4>' + (t === 'odds' ? 'Odds' : 'Lay odds') + '</h4><div class="cpt-edge up"><span>House edge</span><b>0.00%</b><i>0 exactly</i></div><p class="cpt-help">' + how(t, R) + '</p>';
        return;
      }
      var mn = G.minBet(c.type, c.num), u = c.unit;
      hint.innerHTML = '<b>' + esc(c.name) + '</b> · pays ' + esc(c.pays) + (c.trueOdds ? ' · true odds ' + c.trueOdds : '') + ' · house edge <span class="band ' + c.band + '">' + pct(c.edgePct) + '</span>';
      var h = '<h4>' + esc(c.name) + '</h4>' +
        '<div class="cpt-edge ' + c.band + '"><span>House edge</span><b>' + pct(c.edgePct) + '</b><i>' + CE.fq(c.edge) + ' of every dollar' + (c.type === 'buy' && R.buyVig === 'upfront' || c.type === 'lay' && R.layVig === 'upfront' ? ' put up, commission included' : ' bet') + '</i></div>' +
        '<dl class="cpt-dl"><dt>Pays</dt><dd>' + esc(c.pays) + '</dd>' +
        (c.trueOdds ? '<dt>True odds</dt><dd>' + c.trueOdds + ' against</dd>' : '') +
        '<dt>Settles in</dt><dd>' + (CE.num(c.rolls) === 1 ? '1 roll' : CE.num(c.rolls).toFixed(2) + ' rolls on average') + '</dd>' +
        '<dt>Edge per roll</dt><dd>' + pct(c.perRollPct, 3) + '</dd>' +
        '<dt>Bet size</dt><dd>' + (u > 1 ? 'multiples of ' + usd(u) + ', ' : '') + 'minimum ' + usd(mn) + (c.type === 'odds' || c.type === 'layodds' ? ', up to ' + CE.ODDS_LABEL[R.odds] : '') + '</dd>' +
        (b ? '<dt>Your bet</dt><dd>' + usd(b.amount) + ', worth ' + signed(T.v(b)) + ' on average from here</dd>' : '') + '</dl>' +
        '<p class="cpt-help">' + how(c.type, R) + '</p>' +
        (c.type === 'pass' || c.type === 'come' ? '<p class="cpt-help">With full ' + CE.ODDS_LABEL[R.odds] + ' odds behind it, the expected loss is still ' + pct(c.edgePct) + ' of the line bet, but only <b>' + pct(100 * CE.num(G.combo('pass').edge), 3) + '</b> of all the money you put up.</p>' : '') +
        (c.type === 'dontpass' || c.type === 'dontcome' ? '<p class="cpt-help">With full lay odds behind it, the expected loss is ' + pct(c.edgePct) + ' of the flat bet, <b>' + pct(100 * CE.num(G.combo('dontpass').edge), 3) + '</b> of all the money put up.</p>' : '');
      pane.innerHTML = h;
    }

    /* ---------- Odds pane ---------- */
    function renderOdds() {
      var D = CE.diceOdds(), h = '<h4>Every total</h4><p class="cpt-help">Two dice make 36 equally likely rolls. The 7 has the most ways (6), which is why the game turns on it.</p>' +
        '<div class="tw"><table class="cpt-t"><thead><tr><th>Total</th><th>Ways</th><th>Chance</th><th>Odds against</th></tr></thead><tbody>';
      D.totals.forEach(function (r) {
        var ag = (36 - r.ways) / r.ways, agTxt = r.against + (r.against.slice(-2) === ':1' ? '' : ' <small>(' + (+ag.toFixed(1)) + ':1)</small>');
        h += '<tr' + (r.total === 7 ? ' class="seven"' : '') + '><td>' + r.total + '</td><td>' + r.ways + '/36 <span class="bar"><i style="width:' + (r.ways / 6 * 100) + '%"></i></span></td><td>' + pct(100 * CE.num(r.p), 1) + '</td><td>' + agTxt + '</td></tr>';
      });
      h += '</tbody></table></div>';
      h += '<h4>The come-out roll</h4><dl class="cpt-dl"><dt>Natural (7, 11)</dt><dd>8/36 = 22.2%</dd><dt>Craps (2, 3, 12)</dt><dd>4/36 = 11.1%</dd><dt>A point is set</dt><dd>24/36 = 66.7%</dd></dl>';
      h += '<h4>Each number against the 7</h4><p class="cpt-help">Once a number is in play, only that number and the 7 matter. The odds bet pays exactly these odds, which is why it carries no house edge; a place bet pays less, and the gap is the house’s cut.</p>' +
        '<div class="tw"><table class="cpt-t pts"><thead><tr><th>No.</th><th>Before a 7</th><th>True odds = odds pay</th><th>Place pays</th></tr></thead><tbody>';
      D.before7.forEach(function (r) {
        h += '<tr data-n="' + r.num + '"><td>' + r.num + '</td><td>' + CE.fq(r.p) + ' <small>' + pct(100 * CE.num(r.p), 1) + '</small></td><td>' + r.against + '</td><td>' + G.byKey['place' + r.num].pays + '</td></tr>';
      });
      h += '</tbody></table></div>';
      h += '<h4>The price of every bet</h4><p class="cpt-help">House edge per bet settled, at this table’s rules. <span class="band up">Under 2%</span> <span class="band au">2–5%</span> <span class="band dn">5% and up</span></p>' + priceList();
      $('.cpt-pane[data-p="odds"]').innerHTML = h;
      renderOddsPoint();
    }
    function priceList() {
      var groups = {}, order = [];
      G.catalogue.forEach(function (c) {
        if (c.type === 'odds' || c.type === 'layodds' || c.type === 'come' || c.type === 'dontcome') return;
        var gk = c.type + '|' + CE.fq(c.edge) + '|' + c.pays;
        if (!groups[gk]) { groups[gk] = { c: c, nums: [] }; order.push(gk); }
        if (c.num != null) groups[gk].nums.push(c.num);
      });
      var NM = { pass: 'Pass line or come', dontpass: 'Don’t pass or don’t come', place: 'Place', buy: 'Buy', lay: 'Lay', hard: 'Hard', big: 'Big' };
      var rows = order.map(function (gk) { var g = groups[gk], c = g.c; return { name: g.nums.length ? NM[c.type] + ' ' + g.nums.join(' or ') : NM[c.type] || c.name, edge: c.edge, band: c.band, pays: c.pays }; });
      var lim = CE.ODDS_LABEL[G.rules.odds], cp = G.combo('pass'), cd = G.combo('dontpass');
      rows.push({ name: 'Odds or lay odds, any number', edge: CE.Q(0), band: 'up', pays: 'true odds' });
      rows.push({ name: 'Pass or come + ' + lim + ' odds (combined)', edge: cp.edge, band: G.band(cp.edge), pays: '' });
      rows.push({ name: 'Don’t + ' + lim + ' lay odds (combined)', edge: cd.edge, band: G.band(cd.edge), pays: '' });
      rows.sort(function (a, b) { return CE.num(a.edge) - CE.num(b.edge); });
      var h = '<div class="tw"><table class="cpt-t price"><thead><tr><th>Bet</th><th>Pays</th><th>House edge</th></tr></thead><tbody>';
      rows.forEach(function (r) { h += '<tr><td>' + esc(r.name) + '</td><td>' + esc(r.pays) + '</td><td><span class="band ' + r.band + '">' + pct(100 * CE.num(r.edge)) + '</span></td></tr>'; });
      return h + '</tbody></table></div><p class="cpt-fine">“Combined” divides the line bet’s expected loss by all the money a player with full odds puts up. The loss per line bet doesn’t change; the odds only add money the house has no edge on.</p>';
    }
    function renderOddsPoint() { $$('.cpt-t.pts tr[data-n]').forEach(function (r) { r.classList.toggle('on', +r.dataset.n === T.point); }); }

    /* ---------- Session pane ---------- */
    function tile(k, v, cls, s) { return '<div class="st"><div class="k">' + k + '</div><div class="v ' + (cls || '') + '">' + v + '</div>' + (s ? '<div class="s">' + s + '</div>' : '') + '</div>'; }
    function renderSession() {
      var L = T.ledger, luck = L.luckComeOut + L.luckPoint, open = T.openValue(), pane = $('.cpt-pane[data-p="session"]');
      var cls = function (x) { return x > 0.005 ? 'up' : x < -0.005 ? 'dn' : ''; };
      var h = '<div class="cpt-stats">' +
        tile('Rolls', L.rolls.toLocaleString('en-US'), '', L.comeOutRolls + ' come-out') +
        tile('Money put up', usd(L.wagered), '', 'every bet, including presses and commission') +
        tile('Expected result', signed(L.expected), cls(L.expected), 'the house edge on each bet as it went down') +
        tile('Actual result', signed(L.actual), cls(L.actual), 'bets that have settled') +
        tile('Luck', signed(luck), cls(luck), 'come-out ' + signed(L.luckComeOut) + ' · point ' + signed(L.luckPoint)) +
        tile('Still on the felt', usd(T.onFelt()), '', 'worth ' + signed(open) + ' on average') + '</div>' +
        '<p class="cpt-help"><b>Actual + what’s still on the felt = expected + luck.</b> Expected is fixed the moment a bet goes down; luck is everything the dice did after that. Come-out luck is the rolls with the puck off (naturals, craps, which point you got); point luck is the rolls after it (making the point or sevening out).</p>';
      var keys = Object.keys(L.byKey).map(function (k) { return L.byKey[k]; }).sort(function (a, b) { return b.wagered - a.wagered; });
      if (keys.length) {
        h += '<h4>Your bets</h4><div class="tw"><table class="cpt-t recap"><thead><tr><th>Bet</th><th>Edge</th><th>Expected</th><th>Actual</th></tr></thead><tbody>';
        keys.forEach(function (r) {
          var c = G.byKey[r.key], e = r.type === 'odds' || r.type === 'layodds' ? 0 : c.edgePct, band = r.type === 'odds' || r.type === 'layodds' ? 'up' : c.band;
          var nm = r.type === 'odds' ? 'Odds' : r.type === 'layodds' ? 'Lay odds' : c.name;
          h += '<tr><td>' + esc(nm) + '<small>' + usd(r.wagered) + ' in ' + r.bets + (r.bets === 1 ? ' bet' : ' bets') + '</small></td><td><span class="band ' + band + '">' + pct(e) + '</span></td><td class="' + cls(r.expected) + '">' + signed(r.expected) + '</td><td class="' + cls(r.actual) + '">' + signed(r.actual) + '</td></tr>';
        });
        h += '</tbody></table></div>';
        var costPer = L.wagered ? -L.expected / L.wagered * 100 : 0;
        h += '<p class="cpt-help">Your mix of bets has cost ' + pct(costPer, 3) + ' of the money you put up. At about 100 rolls an hour, that is the price of the game; the luck column is why it rarely feels like it.</p>';
      } else h += '<p class="cpt-help">No bets yet this session.</p>';
      h += '<div class="cpt-bankbtns"><button type="button" class="cpt-btn ghost small cpt-reset">New session (' + usd(S.start) + ')</button></div>' +
        (rebuys ? '<p class="cpt-fine">Rebuys this session: ' + rebuys + '.</p>' : '');
      pane.innerHTML = h;
    }

    /* ---------- events ---------- */
    /* The upright arm of the pass line is drawing, not a second button: it hands clicks to the pass line. */
    function zoneOf(t) {
      var z0 = t.closest('.z'); if (z0) return z0;
      var px = t.closest('[data-proxy]'); return px ? felt.querySelector('.z-' + px.dataset.proxy + (px.dataset.n ? '[data-n="' + px.dataset.n + '"]' : '')) : null;
    }
    felt.addEventListener('click', function (e) {
      if (e.target.closest('.cpt-throw')) { if (skipThrow) skipThrow(); return; }
      var el = zoneOf(e.target); if (el) act(el);
    });
    felt.addEventListener('mouseover', function (e) { var el = zoneOf(e.target); if (el && el !== lastCard) showCard(el); });
    felt.addEventListener('focusin', function (e) { var el = e.target.closest('.z'); if (el) showCard(el); });
    $('.cpt-roll').addEventListener('click', roll);
    $('.cpt-clear').addEventListener('click', clearAll);
    $('.cpt-rebuy').addEventListener('click', function () { T.bank += +S.start; rebuys++; persist(); render(); renderSession(); say('Rebought for ' + usd(S.start) + '.', 'info'); });
    $('.rackrow').addEventListener('click', function (e) { var p = e.target.closest('.pile'); if (!p || p.disabled) return; S.chip = p.dataset.chip === 'take' ? 'take' : +p.dataset.chip; save(S); render(); });
    $('.cpt-side').addEventListener('click', function (e) {
      var tb = e.target.closest('.cpt-tab');
      if (tb) { $$('.cpt-tab').forEach(function (x) { var on = x === tb; x.classList.toggle('on', on); x.setAttribute('aria-selected', String(on)); }); $$('.cpt-pane').forEach(function (p) { p.hidden = p.dataset.p !== tb.dataset.p; }); if (tb.dataset.p === 'card' && lastCard) showCard(lastCard); return; }
      if (e.target.closest('.cpt-reset')) { S.bank = +S.start; newSession(); say('New session: ' + usd(S.start) + ' in the rack.', 'info'); persist(); }
    });
    $('.cpt-bar').addEventListener('change', function (e) {
      var k = e.target.dataset.k; if (!k) return;
      if (skipThrow) skipThrow();
      if (k === 'stayUp') { S.stayUp = e.target.checked; save(S); return; }
      persist();
      S[k] = e.target.value;
      if (k === 'start') S.bank = +S.start;
      save(S); newSession();
      say(k === 'start' ? 'New session: ' + usd(S.start) + ' in the rack.' : 'New table rules. The felt is cleared and a new session starts.', 'info');
    });

    if (typeof S.chip !== 'number' && S.chip !== 'take') S.chip = 5;
    newSession();
    say('Pick a chip, put it on the <b>Pass line</b>, and roll. Hover, focus or tap any spot to see what it pays and what it costs.', 'info');
    showCard(felt.querySelector('.z-pass'));
  }

  return { mount: mount };
})();
