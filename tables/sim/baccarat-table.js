/* The Tilted Gent — Baccarat Table. BaccaratTable.mount('#baccarat') puts a practice baccarat table on the page.
   Needs edge-bands.js and baccarat-engine.js (the rules, the shoe, the exact odds and the ledger). Vanilla JS, no dependencies.
   The felt is built once and updated in place, so keyboard focus survives every bet.
   Settings and the bankroll persist in localStorage 'ttg-bct'; the session ledger starts fresh on load. */
window.BaccaratTable = (function () {
  'use strict';
  var BE = window.BaccaratEngine, EB = window.TtgEdgeBands;
  var DEFAULTS = { tiePays: 8, max: 1000, start: 1000, bank: 1000, rebet: true, chip: 25 };
  function load() { try { var s = JSON.parse(localStorage.getItem('ttg-bct') || 'null'); return Object.assign({}, DEFAULTS, s || {}); } catch (e) { return Object.assign({}, DEFAULTS); } }
  function save(s) { try { localStorage.setItem('ttg-bct', JSON.stringify(s)); } catch (e) {} }

  var CHIPS = [1, 5, 25, 100, 500];
  var ORDER = ['banker', 'player', 'tie', 'ppair', 'bpair'];
  /* The drawing chart in words, for the narration (the engine holds the rule itself). */
  var BANKER_RULE = { 0: 'Banker draws on 0, 1 or 2 whatever Player drew', 1: 'Banker draws on 0, 1 or 2 whatever Player drew', 2: 'Banker draws on 0, 1 or 2 whatever Player drew',
    3: 'on 3, Banker draws unless Player’s third card is an 8', 4: 'on 4, Banker draws when Player’s third card is 2 to 7',
    5: 'on 5, Banker draws when Player’s third card is 4 to 7', 6: 'on 6, Banker draws only when Player’s third card is a 6 or 7', 7: 'Banker stands on 7' };

  function usd(x) {
    var a = Math.round(Math.abs(x) * 100) / 100;
    return '$' + a.toLocaleString('en-US', { minimumFractionDigits: a % 1 ? 2 : 0, maximumFractionDigits: 2 });
  }
  function signed(x) { x = Math.round(x * 100) / 100; return (x > 0 ? '+' : x < 0 ? '−' : '') + usd(x); }
  function pct(x, d) { return x.toFixed(d == null ? 2 : d) + '%'; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function toChips(a) { var out = []; for (var i = CHIPS.length - 1; i >= 0; i--) while (a >= CHIPS[i] - 1e-9) { out.push(CHIPS[i]); a -= CHIPS[i]; } return out; }
  function stack(a) {
    if (!(a > 0)) return '';
    var c = toChips(a).slice(0, 6).reverse(), h = '<span class="cstk" aria-hidden="true">';
    c.forEach(function (v, i) { h += '<span class="chip c' + v + '" style="bottom:' + (i * 3) + 'px"></span>'; });
    return h + '</span><span class="camt">' + usd(a) + '</span>';
  }
  function cardHTML(c, fresh) {
    var red = c.s === 1 || c.s === 2;
    return '<span class="bct-card' + (red ? ' red' : '') + (fresh ? ' in' : '') + '" role="img" aria-label="' + c.rank + ' of ' + ['spades', 'hearts', 'diamonds', 'clubs'][c.s] + '">' +
      '<b>' + c.rank + '</b><i>' + c.suit + '</i><u>' + c.suit + '</u><em>TG</em></span>';
  }

  /* ---------- teaching copy: how each bet works ---------- */
  function how(t, G) {
    var E = G.enumeration.p, R = G.rules, tieFair = (1 - E.tie) / E.tie, pairFair = (1 - E.pair) / E.pair;
    switch (t) {
      case 'player': return 'A bet that the Player hand finishes closer to 9. Player is only the name of the hand: nobody plays it, the drawing rules do. Pays even money; on a tie the bet pushes and stays yours.';
      case 'banker': return 'A bet that the Banker hand finishes closer to 9. Banker draws last and its rules react to Player’s third card, so it wins a little more often than Player; the house takes ' + R.commission + '% of every winning Banker bet to make up for it, and still falls slightly short. On a tie the bet pushes.';
      case 'tie': return 'A bet that the two hands finish level. A tie comes about once every ' + (1 / E.tie).toFixed(1) + ' hands, so a fair price would be ' + tieFair.toFixed(2) + ' to 1; this table pays ' + R.tiePays + ' to 1' + (R.tiePays === 8 ? ' (some pay 9 to 1: change it in the settings and watch the edge fall)' : '') + '.';
      case 'ppair': return 'A bet that Player’s first two cards are the same rank: two 7s, two kings. A 10 and a king both count zero but are not a pair. Pays 11 to 1 on a ' + pairFair.toFixed(2) + ' to 1 shot.';
      case 'bpair': return 'A bet that Banker’s first two cards are the same rank. Same odds and the same price as the Player Pair: pays 11 to 1 on a ' + pairFair.toFixed(2) + ' to 1 shot.';
    }
    return '';
  }

  /* ---------- the felt ---------- */
  function z(t, label, extra) { return '<button type="button" class="z z-' + t + (extra ? ' ' + extra : '') + '" data-t="' + t + '">' + label + '<span class="stk"></span></button>'; }
  function feltHTML() {
    return '<div class="bct-feltwrap"><div class="bct-felt" role="group" aria-label="Baccarat layout">' +
      '<div class="bct-hands">' +
        '<div class="bct-hand" data-h="player"><div class="lab"><span>PLAYER</span><b class="tot" aria-live="off"></b></div><div class="cards"></div></div>' +
        '<div class="bct-hand" data-h="banker"><div class="lab"><span>BANKER</span><b class="tot" aria-live="off"></b></div><div class="cards"></div></div>' +
      '</div>' +
      '<div class="bct-zones">' +
        '<div class="row3">' + z('ppair', '<b>P PAIR</b><small>11 TO 1</small>') + z('tie', '<b>TIE</b><small class="tiep">8 TO 1</small>') + z('bpair', '<b>B PAIR</b><small>11 TO 1</small>') + '</div>' +
        z('banker', '<b>BANKER</b><small>1 TO 1 · 5% COMMISSION</small>', 'arc') +
        z('player', '<b>PLAYER</b><small>1 TO 1</small>', 'arc') +
      '</div>' +
    '</div></div>';
  }
  function sel(key, label, opts, v) {
    var h = '<label class="bct-field"><span class="k">' + label + '</span><select data-k="' + key + '">';
    opts.forEach(function (o) { h += '<option value="' + o[0] + '"' + (String(o[0]) === String(v) ? ' selected' : '') + '>' + o[1] + '</option>'; });
    return h + '</select></label>';
  }

  function mount(where) {
    var root = document.querySelector(where); if (!root || !BE) return;
    var S = load(), G, T, dealing = false, skipDeal = null, lastCard = null, rebuys = 0, lastSpread = null;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    root.innerHTML = '<div class="bct">' +
      '<div class="bct-bar">' +
        sel('tiePays', 'Tie pays', [[8, '8 to 1 (standard)'], [9, '9 to 1']], S.tiePays) +
        sel('max', 'Table maximum', BE.MAXES.map(function (m) { return [m, usd(m)]; }), S.max) +
        sel('start', 'Buy-in', [[500, '$500'], [1000, '$1,000'], [5000, '$5,000']], S.start) +
        '<label class="bct-toggle"><input type="checkbox" data-k="rebet"' + (S.rebet ? ' checked' : '') + '> Same bets next hand</label>' +
        '<p class="bct-note">8 decks, cut card ' + BE.DEFAULT_RULES.cut + ' cards from the end, $' + BE.DEFAULT_RULES.min + ' minimum on every bet. Changing a table rule clears the felt and starts a new session.</p>' +
      '</div>' +
      '<div class="bct-grid"><div class="bct-main">' +
        '<div class="bct-tray">' +
          '<div class="bct-shoe"><div class="k"></div><div class="v"></div><div class="gauge" aria-hidden="true"><i></i><s></s></div></div>' +
          '<button type="button" class="bct-btn gold bct-deal">Deal</button>' +
        '</div>' +
        '<div class="bct-msg" aria-live="polite"></div>' +
        feltHTML() +
        '<div class="bct-hint"></div>' +
        '<div class="bct-yours"></div>' +
        '<div class="bct-bank">' +
          '<div class="bct-rack"><div class="k">Chip <i>— pick one, then tap the felt</i></div><div class="rackrow">' +
            CHIPS.map(function (v) { return '<button type="button" class="pile" data-chip="' + v + '" aria-label="$' + v + ' chip"><span class="chip c' + v + '"></span><small>$' + v + '</small></button>'; }).join('') +
            '<button type="button" class="pile take" data-chip="take"><span class="tk">✕</span><small>Take down</small></button>' +
          '</div></div>' +
          '<div class="bct-money"><div><span class="k">Rack</span><b class="rack"></b></div><div><span class="k">On the felt</span><b class="onfelt"></b></div>' +
            '<div class="bct-bankbtns"><button type="button" class="bct-btn ghost small bct-clear">Take down all</button><button type="button" class="bct-btn ghost small bct-rebuy" hidden>Rebuy</button></div></div>' +
        '</div>' +
      '</div>' +
      '<aside class="bct-side">' +
        '<div class="bct-tabs" role="tablist">' +
          '<button type="button" role="tab" class="bct-tab on" data-p="card" aria-selected="true">Bet card</button>' +
          '<button type="button" role="tab" class="bct-tab" data-p="odds" aria-selected="false">Averages</button>' +
          '<button type="button" role="tab" class="bct-tab" data-p="session" aria-selected="false">Session</button>' +
        '</div>' +
        '<div class="bct-pane" data-p="card" role="tabpanel"></div>' +
        '<div class="bct-pane" data-p="odds" role="tabpanel" hidden></div>' +
        '<div class="bct-pane" data-p="session" role="tabpanel" hidden></div>' +
      '</aside></div></div>';

    var $ = function (s) { return root.querySelector(s); }, $$ = function (s) { return [].slice.call(root.querySelectorAll(s)); };
    var felt = $('.bct-felt'), msg = $('.bct-msg'), hint = $('.bct-hint');
    var handEl = { player: $('.bct-hand[data-h="player"]'), banker: $('.bct-hand[data-h="banker"]') };

    function rules() { return { tiePays: +S.tiePays, max: +S.max }; }
    function newSession() {
      G = BE.create(rules()); T = G.Table({ bankroll: +S.bank }); rebuys = 0; lastSpread = null;
      $('.z-tie .tiep').textContent = G.rules.tiePays + ' TO 1';
      clearCards(); renderOdds(); render(); renderSession();
    }
    function persist() { S.bank = Math.round((T.bank + T.onFelt()) * 100) / 100; save(S); }

    /* ---------- placing and taking down ---------- */
    function act(el) {
      var t = el.dataset.t, c = G.byKey[t], R = G.rules;
      showCard(el);
      if (dealing || T.phase !== 'bets') { say('No more bets: the cards are out. Bets go down between hands.', 'info'); return; }
      if (S.chip === 'take') {
        var r = T.remove(t);
        say(r.ok ? 'Took down ' + c.name + ': ' + usd(r.amount) + ' back to the rack.' : 'Nothing on ' + c.name + ' to take down.', 'info');
        persist(); render(); return;
      }
      var have = T.bets[t] || 0, a = S.chip, note = '';
      if (have >= R.max) { say(c.name + ' is at the table maximum: ' + usd(have) + '.', 'info'); return; }
      if (have + a < R.min) { a = R.min - have; note = 'The minimum on ' + c.name + ' is ' + usd(R.min) + '.'; }
      if (have + a > R.max) { a = R.max - have; note = 'Filled to the table maximum: ' + usd(R.max) + ' on ' + c.name + '.'; }
      var res = T.place(t, a);
      if (!res.ok) { say(res.reason, 'info'); return; }
      say(usd(a) + ' on ' + c.name + (have ? ', ' + usd(res.amount) + ' in all' : '') + '.' + (note ? ' <span class="dimn">' + note + '</span>' : ''), 'info');
      persist(); render();
    }
    function clearAll() {
      if (dealing || T.phase !== 'bets') return;
      var back = 0; Object.keys(T.bets).forEach(function (t) { var r = T.remove(t); if (r.ok) back += r.amount; });
      say(back ? usd(back) + ' back to the rack.' : 'Nothing to take down.', 'info');
      persist(); render();
    }

    /* ---------- dealing ---------- */
    function clearCards() {
      ['player', 'banker'].forEach(function (k) { handEl[k].querySelector('.cards').innerHTML = ''; handEl[k].querySelector('.tot').textContent = ''; handEl[k].classList.remove('won', 'tied'); });
    }
    function deal() {
      if (dealing) { if (skipDeal) skipDeal(); return; }
      if (!Object.keys(T.bets).length) { say('Put a chip down first. Banker is the cheapest bet on the table.', 'info'); return; }
      $$('.z.win,.z.lose,.z.push').forEach(function (e) { e.classList.remove('win', 'lose', 'push'); });
      lastSpread = Object.assign({}, T.bets);
      var d = T.deal(); if (!d.ok) { say(d.reason, 'info'); return; }
      var h = d.hand;
      dealing = true; clearCards(); render();
      $('.bct-deal').textContent = 'Skip';
      say((h.shuffled ? 'New shoe: shuffled, one card burned. ' : '') + 'No more bets.', 'info');
      // deal order: Player, Banker, Player, Banker, then Player's third card, then Banker's
      var seq = [['player', 0], ['banker', 0], ['player', 1], ['banker', 1]];
      if (h.player[2]) seq.push(['player', 2]);
      if (h.banker[2]) seq.push(['banker', 2]);
      var i = 0, timers = [], ended = false;
      function show(n) {
        var s = seq[n], cards = h[s[0]].slice(0, s[1] + 1), el = handEl[s[0]];
        el.querySelector('.cards').insertAdjacentHTML('beforeend', cardHTML(cards[s[1]], !reduce));
        el.querySelector('.tot').textContent = BE.total(cards);
      }
      function end() {
        if (ended) return; ended = true; skipDeal = null; timers.forEach(clearTimeout);
        while (i < seq.length) show(i++);
        finish(h);
      }
      skipDeal = end;
      if (reduce) { end(); return; }
      (function next() {
        if (ended) return;
        if (i >= seq.length) { timers.push(setTimeout(end, 250)); return; }
        show(i++);
        timers.push(setTimeout(next, i === 4 ? 650 : 360));     // a beat before the third cards
      })();
    }
    function finish(h) {
      var s = T.settle();
      dealing = false; $('.bct-deal').textContent = 'Deal';
      handEl.player.classList.toggle('won', h.winner === 'player'); handEl.banker.classList.toggle('won', h.winner === 'banker');
      handEl.player.classList.toggle('tied', h.winner === 'tie'); handEl.banker.classList.toggle('tied', h.winner === 'tie');
      s.events.forEach(function (e) { var el = felt.querySelector('.z-' + e.type); if (el) el.classList.add(e.r); });
      var up = [], fail = [];
      if (S.rebet && lastSpread) ORDER.forEach(function (t) {
        if (!lastSpread[t]) return;
        var r = T.place(t, lastSpread[t]);
        (r.ok ? up : fail).push(G.byKey[t].name);
      });
      narrate(h, s, up, fail);
      persist(); render(); renderSession();
    }
    function narrate(h, s, up, fail) {
      var W = { player: 'Player wins', banker: 'Banker wins', tie: 'A tie' }[h.winner];
      var head = '<span class="hd">Player <b>' + h.pt + '</b> · Banker <b>' + h.bt + '</b></span> ' + W + (h.winner === 'tie' ? ': Player and Banker bets push.' : '.');
      var story = [];
      if (h.natural) {
        var nat = [];
        if (h.p2 >= 8) nat.push('Player');
        if (h.b2 >= 8) nat.push('Banker');
        story.push(nat.length > 1 ? 'Both hands are naturals (Player ' + h.p2 + ', Banker ' + h.b2 + '): nobody draws.'
                                  : nat[0] + ' has a natural ' + (nat[0] === 'Player' ? h.p2 : h.b2) + ': both hands stand.');
      } else {
        story.push(h.pDrew ? 'Player had ' + h.p2 + ' and drew (Player draws on 0 to 5).' : 'Player stood on ' + h.p2 + '.');
        if (h.p3 == null) story.push(h.bDrew ? 'Banker had ' + h.b2 + ' and drew (with Player standing, Banker draws on 0 to 5).' : 'Banker stood on ' + h.b2 + '.');
        else story.push('Banker had ' + h.b2 + ' against Player’s third card of ' + h.p3 + ': ' + BANKER_RULE[h.b2] + ', so Banker ' + (h.bDrew ? 'drew.' : 'stood.'));
      }
      if (h.playerPair || h.bankerPair) story.push((h.playerPair && h.bankerPair ? 'Both hands' : h.playerPair ? 'Player' : 'Banker') + ' opened with a pair.');
      var lines = s.events.slice().sort(function (a, b) { return ORDER.indexOf(a.type) - ORDER.indexOf(b.type); }).map(function (e) { return G.byKey[e.type].name + ' <b class="' + (e.net > 0 ? 'up' : e.net < 0 ? 'dn' : 'au') + '">' + (e.r === 'push' ? 'push' : signed(e.net)) + '</b>'; });
      var html = head + ' <span class="dimn">' + story.join(' ') + '</span>';
      if (lines.length) html += '<span class="evs">' + lines.join(' · ') + '</span>';
      html += '<span class="evline">This hand: <b class="' + (s.net > 0 ? 'up' : s.net < 0 ? 'dn' : '') + '">' + signed(s.net) + '</b> · expected ' + signed(s.expected) + ' · luck ' + signed(s.luck) +
        (up.length ? ' · same bets back down' : '') + (fail.length ? ' · not enough in the rack to put back ' + fail.join(', ') : '') + '</span>';
      msg.className = 'bct-msg'; msg.innerHTML = html;
    }
    function say(h, cls) { msg.className = 'bct-msg' + (cls ? ' ' + cls : ''); msg.innerHTML = h; }

    /* ---------- rendering ---------- */
    function render() {
      $$('.z').forEach(function (el) {
        var t = el.dataset.t, a = T.bets[t] || 0, c = G.byKey[t];
        el.querySelector('.stk').innerHTML = stack(a);
        el.classList.toggle('has', a > 0);
        el.setAttribute('aria-label', c.name + ', pays ' + c.pays + ', house edge ' + pct(c.edgePct) + (a ? ', your bet ' + usd(a) : ''));
      });
      var left = T.cardsLeft(), all = G.rules.decks * 52;
      $('.bct-shoe .k').textContent = 'Shoe ' + T.shoeNo + (dealing ? ' · cards out' : T.phase === 'bets' ? ' · place your bets' : '');
      $('.bct-shoe .v').textContent = left + ' cards left' + (T.cutOut() ? ' · cut card is out: new shoe next hand' : '');
      $('.bct-shoe .gauge i').style.width = (100 * (all - left) / all) + '%';
      $('.bct-shoe .gauge s').style.left = (100 * (all - G.rules.cut) / all) + '%';
      $$('.pile').forEach(function (p) { var v = p.dataset.chip; p.setAttribute('aria-pressed', String(v === String(S.chip))); p.disabled = v !== 'take' && +v > T.bank; });
      $('.rack').textContent = usd(T.bank); $('.onfelt').textContent = usd(T.onFelt());
      $('.bct-rebuy').hidden = !(T.bank < G.rules.min && !T.onFelt());
      $('.bct-deal').disabled = false;
      renderYours();
      if (lastCard) showCard(lastCard);
      if (!$('.bct-pane[data-p="odds"]').hidden) renderCost();
    }
    /* Your bets: what is down, what each bet costs, what the spread is worth before the cards come out. */
    function spreadOf(bets) {
      var amt = 0, ev = 0, rows = [];
      ORDER.forEach(function (t) { if (!bets[t]) return; var v = G.value(t, bets[t]); amt += bets[t]; ev += v; rows.push({ t: t, a: bets[t], v: v }); });
      return { amt: amt, ev: ev, rows: rows, edge: amt ? -ev / amt * 100 : 0 };
    }
    function renderYours() {
      var sp = spreadOf(T.bets), el = $('.bct-yours');
      var h = '<div class="k">Your bets <i>— ' + (dealing ? 'locked in: the cards are out' : 'value now = minus the house edge times the bet, off the top of a fresh 8-deck shoe') + '</i></div>';
      if (!sp.rows.length) { el.innerHTML = h + '<p class="bct-empty">No bets down. Pick a chip and tap Banker, Player, Tie or a pair.</p>'; return; }
      h += '<div class="tw"><table class="bct-t yours"><thead><tr><th>Bet</th><th>Amount</th><th>House edge</th><th>Value now</th></tr></thead><tbody>';
      sp.rows.forEach(function (r) {
        var c = G.byKey[r.t];
        h += '<tr><td>' + esc(c.name) + '<small>pays ' + esc(c.pays) + '</small></td><td>' + usd(r.a) + '</td><td><span class="band ' + c.band + '">' + pct(c.edgePct) + '</span></td><td class="dn">' + signed(r.v) + '</td></tr>';
      });
      h += '</tbody><tfoot><tr><td>On the felt</td><td>' + usd(sp.amt) + '</td><td><span class="band ' + bandOf(sp.edge) + '">' + pct(sp.edge) + '</span><small>combined</small></td><td class="dn">' + signed(sp.ev) + '</td></tr></tfoot></table></div>';
      h += '<p class="bct-fine">At ' + BE.PACE.big + ' hands an hour (a full big table) this spread costs about <b>' + usd(-sp.ev * BE.PACE.big) + '</b> an hour; at mini-baccarat speed (' + BE.PACE.mini.join('–') + ' hands) about ' +
           usd(-sp.ev * BE.PACE.mini[0]) + '–' + usd(-sp.ev * BE.PACE.mini[1]) + '.</p>';
      el.innerHTML = h;
    }
    function bandOf(p) { return EB.band('baccarat', p / 100); }   // p in percent

    /* ---------- bet card (side pane + the one-line hint under the felt) ---------- */
    function showCard(el) {
      lastCard = el;
      var t = el.dataset.t, c = G.byKey[t], R = G.rules, a = T.bets[t] || 0;
      hint.innerHTML = '<b>' + esc(c.name) + '</b> · pays ' + esc(c.pays) + ' · wins ' + pct(100 * c.pWin) + ' of hands · house edge <span class="band ' + c.band + '">' + pct(c.edgePct) + '</span>';
      var h = '<h4>' + esc(c.name) + '</h4>' +
        '<div class="bct-edge ' + c.band + '"><span>House edge</span><b>' + pct(c.edgePct) + '</b><i>' +
          (c.exactSmall ? BE.fq(c.edge) + ' of every dollar bet, exactly' : 'of every dollar bet, counted over every possible deal from a full 8-deck shoe (' + pct(c.edgePct, 4) + ')') + '</i></div>' +
        '<dl class="bct-dl"><dt>Pays</dt><dd>' + esc(c.pays) + '</dd>' +
        '<dt>Wins</dt><dd>' + pct(100 * c.pWin) + ' of hands' + (c.exactSmall ? ' (' + G.enumeration.pair.n + '/' + G.enumeration.pair.d + ')' : '') + '</dd>' +
        (c.pPush ? '<dt>Pushes</dt><dd>' + pct(100 * c.pPush) + ' (a tie)</dd>' : '') +
        '<dt>Loses</dt><dd>' + pct(100 * c.pLose) + '</dd>' +
        (c.trueOdds ? '<dt>True odds</dt><dd>' + c.trueOdds + ' against</dd>' : '<dt>Ties aside</dt><dd>wins ' + pct(100 * c.noTie) + ' of hands that don’t tie</dd>') +
        '<dt>Bet size</dt><dd>whole dollars, minimum ' + usd(R.min) + ', maximum ' + usd(R.max) + '</dd>' +
        (a ? '<dt>Your bet</dt><dd>' + usd(a) + ', worth ' + signed(G.value(t, a)) + ' on average</dd>' : '') + '</dl>' +
        '<p class="bct-help">' + how(t, G) + '</p>';
      $('.bct-pane[data-p="card"]').innerHTML = h;
    }

    /* ---------- Averages pane ---------- */
    function renderOdds() {
      var E = G.enumeration, p = E.p, noTie = p.banker + p.player;
      var h = '<h4>How a hand ends</h4><p class="bct-help">Counted over every possible deal from a full 8-deck shoe, not simulated.</p>' +
        '<div class="tw"><table class="bct-t"><thead><tr><th>Result</th><th>Chance</th><th>Ties aside</th></tr></thead><tbody>' +
        '<tr><td>Banker wins</td><td>' + pct(100 * p.banker) + '</td><td>' + pct(100 * p.banker / noTie) + '</td></tr>' +
        '<tr><td>Player wins</td><td>' + pct(100 * p.player) + '</td><td>' + pct(100 * p.player / noTie) + '</td></tr>' +
        '<tr><td>Tie</td><td>' + pct(100 * p.tie) + '</td><td>—</td></tr>' +
        '<tr><td>Player pair</td><td>' + pct(100 * p.pair) + '</td><td>' + E.pair.n + '/' + E.pair.d + '</td></tr>' +
        '<tr><td>Banker pair</td><td>' + pct(100 * p.pair) + '</td><td>' + E.pair.n + '/' + E.pair.d + '</td></tr>' +
        '</tbody></table></div>' +
        '<dl class="bct-dl"><dt>Natural</dt><dd>' + pct(100 * p.natural) + ' of hands (an 8 or 9 on two cards: nobody draws)</dd>' +
        '<dt>Player draws</dt><dd>' + pct(100 * p.pDraw) + '</dd><dt>Banker draws</dt><dd>' + pct(100 * p.bDraw) + '</dd></dl>';
      h += '<h4>The price of every bet</h4><p class="bct-help">House edge per hand bet. ' + EB.legend('baccarat') + '</p>' +
        '<div class="tw"><table class="bct-t price"><thead><tr><th>Bet</th><th>Pays</th><th>House edge</th></tr></thead><tbody>';
      var other = BE.create({ tiePays: G.rules.tiePays === 8 ? 9 : 8 }).byKey.tie;
      var rows = G.catalogue.map(function (c) { return { name: c.name + (c.type === 'tie' ? ' (this table)' : ''), pays: c.pays, pct: c.edgePct, band: c.band }; });
      rows.push({ name: 'Tie at ' + other.pays + ' (other tables)', pays: other.pays, pct: other.edgePct, band: other.band, dim: true });
      rows.sort(function (a, b) { return a.pct - b.pct; });
      rows.forEach(function (r) { h += '<tr' + (r.dim ? ' class="dim"' : '') + '><td>' + esc(r.name) + '</td><td>' + esc(r.pays) + '</td><td><span class="band ' + r.band + '">' + pct(r.pct) + '</span></td></tr>'; });
      h += '</tbody></table></div>';
      h += '<h4>Hands per hour, and what they cost</h4><div class="bct-cost"></div>';
      h += '<h4>The drawing rules</h4><p class="bct-help">Nobody chooses anything after the bets. Player draws on 0 to 5 and stands on 6 or 7; an 8 or 9 on two cards is a natural and both hands stand. If Player stood, Banker draws on 0 to 5. If Player drew, Banker follows this chart:</p>' +
        '<div class="tw"><table class="bct-t chart"><thead><tr><th>Banker</th>';
      for (var x = 0; x <= 9; x++) h += '<th>' + x + '</th>';
      h += '</tr></thead><tbody>';
      for (var b = 0; b <= 7; b++) {
        h += '<tr><td>' + b + '</td>';
        for (x = 0; x <= 9; x++) { var d = BE.bankerDraws(b, x); h += '<td class="' + (d ? 'dr' : 'st') + '">' + (d ? 'D' : 'S') + '</td>'; }
        h += '</tr>';
      }
      h += '</tbody></table></div><p class="bct-fine">Columns: the value of Player’s third card. D draws, S stands.</p>';
      $('.bct-pane[data-p="odds"]').innerHTML = h;
      renderCost();
    }
    function renderCost() {
      var el = $('.bct-cost'); if (!el) return;
      var sp = spreadOf(T.onFelt() ? T.bets : lastSpread || {}), mine = sp.rows.length;
      if (!mine) sp = spreadOf({ banker: 25 });
      var pace = [['Big table', BE.PACE.big], ['Mini', BE.PACE.mini[0]], ['Mini, fast', BE.PACE.mini[1]]];
      var h = '<p class="bct-help">' + (mine ? 'Your spread: ' + usd(sp.amt) + ' a hand at a combined ' + pct(sp.edge) + '.' : 'No bets down, so here is a ' + usd(25) + ' Banker bet.') +
        ' Same game, same edge; the faster table simply deals more hands.</p>' +
        '<div class="tw"><table class="bct-t"><thead><tr><th>Table</th><th>Hands / hour</th><th>Cost / hour</th></tr></thead><tbody>';
      pace.forEach(function (r) { h += '<tr><td>' + r[0] + '</td><td>' + r[1] + '</td><td class="dn">' + usd(-sp.ev * r[1]) + '</td></tr>'; });
      el.innerHTML = h + '</tbody></table></div>';
    }

    /* ---------- Session pane ---------- */
    function tile(k, v, cls, s) { return '<div class="st"><div class="k">' + k + '</div><div class="v ' + (cls || '') + '">' + v + '</div>' + (s ? '<div class="s">' + s + '</div>' : '') + '</div>'; }
    function renderSession() {
      var L = T.ledger, luck = L.actual - L.expected, pane = $('.bct-pane[data-p="session"]');
      var cls = function (x) { return x > 0.005 ? 'up' : x < -0.005 ? 'dn' : ''; };
      var h = '<div class="bct-stats">' +
        tile('Hands', L.hands.toLocaleString('en-US'), '', 'Banker ' + L.wins.banker + ' · Player ' + L.wins.player + ' · Tie ' + L.wins.tie) +
        tile('Money put up', usd(L.wagered), '', 'every bet, every hand') +
        tile('Expected result', signed(L.expected), cls(L.expected), 'the house edge on each bet, booked at the deal') +
        tile('Actual result', signed(L.actual), cls(L.actual), 'what the cards paid') +
        tile('Luck', signed(luck), cls(luck), 'actual minus expected') +
        tile('Shoe', String(T.shoeNo), '', T.cardsLeft() + ' cards left') + '</div>' +
        '<p class="bct-help"><b>Actual = expected + luck.</b> Expected is fixed the moment the cards come out; luck is everything they did after that. Over a few hands luck is most of the story. Over a few thousand, the expected column is.</p>';
      var keys = ORDER.filter(function (k) { return L.byKey[k]; }).map(function (k) { return L.byKey[k]; });
      if (keys.length) {
        h += '<h4>Bet by bet</h4><div class="tw"><table class="bct-t recap"><thead><tr><th>Bet</th><th>Edge</th><th>Expected</th><th>Actual</th></tr></thead><tbody>';
        keys.forEach(function (r) {
          var c = G.byKey[r.key];
          h += '<tr><td>' + esc(c.name) + '<small>' + usd(r.wagered) + ' in ' + r.bets + (r.bets === 1 ? ' hand' : ' hands') + ' · won ' + r.won + ', lost ' + r.lost + (r.pushed ? ', pushed ' + r.pushed : '') + '</small></td>' +
               '<td><span class="band ' + c.band + '">' + pct(c.edgePct) + '</span></td><td class="' + cls(r.expected) + '">' + signed(r.expected) + '</td><td class="' + cls(r.actual) + '">' + signed(r.actual) + '</td></tr>';
        });
        h += '</tbody></table></div>';
        var costPer = L.wagered ? -L.expected / L.wagered * 100 : 0, perHand = L.hands ? L.expected / L.hands : 0;
        h += '<p class="bct-help">Your mix of bets has cost ' + pct(costPer, 3) + ' of the money you put up, ' + usd(-perHand) + ' a hand on average. At ' + BE.PACE.big + ' hands an hour that is ' + usd(-perHand * BE.PACE.big) + ' an hour; the luck column is why it rarely feels like it.</p>';
      } else h += '<p class="bct-help">No hands yet this session.</p>';
      h += '<div class="bct-bankbtns"><button type="button" class="bct-btn ghost small bct-reset">New session (' + usd(S.start) + ')</button></div>' +
        (rebuys ? '<p class="bct-fine">Rebuys this session: ' + rebuys + '.</p>' : '');
      pane.innerHTML = h;
    }

    /* ---------- events ---------- */
    felt.addEventListener('click', function (e) {
      if (dealing && e.target.closest('.bct-hands')) { if (skipDeal) skipDeal(); return; }
      var el = e.target.closest('.z'); if (el) act(el);
    });
    felt.addEventListener('mouseover', function (e) { var el = e.target.closest('.z'); if (el && el !== lastCard) showCard(el); });
    felt.addEventListener('focusin', function (e) { var el = e.target.closest('.z'); if (el) showCard(el); });
    $('.bct-deal').addEventListener('click', deal);
    $('.bct-clear').addEventListener('click', clearAll);
    $('.bct-rebuy').addEventListener('click', function () { T.bank = Math.round((T.bank + +S.start) * 100) / 100; rebuys++; persist(); render(); renderSession(); say('Rebought for ' + usd(S.start) + '.', 'info'); });
    $('.rackrow').addEventListener('click', function (e) { var p = e.target.closest('.pile'); if (!p || p.disabled) return; S.chip = p.dataset.chip === 'take' ? 'take' : +p.dataset.chip; save(S); render(); });
    $('.bct-side').addEventListener('click', function (e) {
      var tb = e.target.closest('.bct-tab');
      if (tb) {
        $$('.bct-tab').forEach(function (x) { var on = x === tb; x.classList.toggle('on', on); x.setAttribute('aria-selected', String(on)); });
        $$('.bct-pane').forEach(function (p) { p.hidden = p.dataset.p !== tb.dataset.p; });
        if (tb.dataset.p === 'card' && lastCard) showCard(lastCard);
        if (tb.dataset.p === 'odds') renderCost();
        return;
      }
      if (e.target.closest('.bct-reset')) { if (dealing && skipDeal) skipDeal(); S.bank = +S.start; newSession(); say('New session: ' + usd(S.start) + ' in the rack.', 'info'); persist(); }
    });
    $('.bct-bar').addEventListener('change', function (e) {
      var k = e.target.dataset.k; if (!k) return;
      if (dealing && skipDeal) skipDeal();
      if (k === 'rebet') { S.rebet = e.target.checked; save(S); return; }
      persist();                                    // chips on the felt go back to the rack
      S[k] = +e.target.value;
      if (k === 'start') S.bank = +S.start;
      save(S); newSession();
      say(k === 'start' ? 'New session: ' + usd(S.start) + ' in the rack.' : 'New table rules. The felt is cleared and a new session starts.', 'info');
    });

    if (typeof S.chip !== 'number' && S.chip !== 'take') S.chip = 25;
    newSession();
    say('Pick a chip, put it on <b>Banker</b> or <b>Player</b>, and deal. Hover, focus or tap any spot to see what it pays and what it costs.', 'info');
    showCard(felt.querySelector('.z-banker'));
  }

  return { mount: mount };
})();
