/* The Tilted Gent — Three Card Poker Table. TcpTable.mount('#tcp') puts a practice Three Card Poker table on the page.
   Needs tcp-engine.js (the rules, the exact values and the ledger). Vanilla JS, no dependencies.
   The felt is built once and updated in place, so keyboard focus survives every bet.
   Settings and the bankroll persist in localStorage 'ttg-tcp'; the session ledger starts fresh on load. */
window.TcpTable = (function () {
  'use strict';
  var TE = window.TcpEngine;
  var DEFAULTS = { bonus: '541', pp: '40-30-6-3-1', max: 1000, start: 1000, bank: 1000, same: true, chip: 5 };
  function load() { try { var s = JSON.parse(localStorage.getItem('ttg-tcp') || 'null'); return Object.assign({}, DEFAULTS, s || {}); } catch (e) { return Object.assign({}, DEFAULTS); } }
  function save(s) { try { localStorage.setItem('ttg-tcp', JSON.stringify(s)); } catch (e) {} }

  var CHIPS = [1, 5, 25, 100, 500];
  var SUIT_NAME = ['spades', 'hearts', 'diamonds', 'clubs'];
  var NAME = { ante: 'Ante', play: 'Play', pp: 'Pair Plus', bonus: 'Ante bonus' };
  var CAT_ORDER = [5, 4, 3, 2, 1, 0];

  function usd(x, cents) {
    var a = Math.round(Math.abs(x) * 100) / 100;
    return '$' + a.toLocaleString('en-US', { minimumFractionDigits: cents || a % 1 ? 2 : 0, maximumFractionDigits: 2 });
  }
  function signed(x, cents) { x = Math.round(x * 100) / 100; return (x > 0 ? '+' : x < 0 ? '−' : '') + usd(x, cents); }
  function pct(x, d) { return (100 * x).toFixed(d == null ? 2 : d) + '%'; }
  function cls(x) { return x > 0.005 ? 'up' : x < -0.005 ? 'dn' : ''; }
  function toChips(a) { var out = []; for (var i = CHIPS.length - 1; i >= 0; i--) while (a >= CHIPS[i] - 1e-9) { out.push(CHIPS[i]); a -= CHIPS[i]; } return out; }
  function stack(a) {
    if (!(a > 0)) return '';
    var c = toChips(a).slice(0, 6).reverse(), h = '<span class="cstk" aria-hidden="true">';
    c.forEach(function (v, i) { h += '<span class="chip c' + v + '" style="bottom:' + (i * 3) + 'px"></span>'; });
    return h + '</span><span class="camt">' + usd(a) + '</span>';
  }
  function cardHTML(c, mode, i) {
    var anim = mode && mode.anim ? ' in" style="animation-delay:' + (i * mode.step) + 'ms' : '';
    if (c == null || mode && mode.back) return '<span class="tcp-card back' + (c == null && !(mode && mode.back) ? ' ghost' : '') + anim + '" role="img" aria-label="face-down card"></span>';
    var r = TE.rank(c), s = TE.suit(c), red = s === 1 || s === 2;
    return '<span class="tcp-card' + (red ? ' red' : '') + anim + '" role="img" aria-label="' + TE.RANK_LABEL[r].replace('J', 'Jack').replace('Q', 'Queen').replace('K', 'King').replace('A', 'Ace') + ' of ' + SUIT_NAME[s] + '">' +
      '<b>' + TE.RANK_LABEL[r] + '</b><i>' + TE.SUITS[s] + '</i><u>' + TE.SUITS[s] + '</u><em>TG</em></span>';
  }
  /* Shown high to low, as a player arranges them; the deal order doesn't matter in this game. */
  function sorted(cards) { return cards.slice().sort(function (a, b) { return TE.rank(b) - TE.rank(a) || TE.suit(a) - TE.suit(b); }); }

  /* ---------- teaching copy: how each bet works ---------- */
  function how(t, G) {
    var B = TE.BONUS[G.rules.bonus];
    switch (t) {
      case 'ante': return 'Your bet against the dealer, made before the cards come out. Once you see your three cards you Play (put up a second bet equal to the Ante) or fold and lose the Ante. The dealer needs Queen high to qualify: if they don’t, the Ante pays 1 to 1 and the Play pushes. If they do, the better hand wins both bets at 1 to 1 and a tie pushes both. Whenever you Play, the Ante bonus pays on a straight or better (' + B[5] + ' to 1, ' + B[4] + ' to 1, ' + B[3] + ' to 1), win or lose.';
      case 'play': return 'The second half of the Ante bet. It goes down after the deal, only beside an Ante, and only for exactly the Ante. Pushes when the dealer doesn’t qualify; otherwise wins or loses 1 to 1 with the Ante. Its price is counted in the Ante’s house edge, which assumes you Play and fold correctly.';
      case 'pp': return 'A side bet on your own three cards. The dealer’s hand doesn’t matter, so it settles even if you fold, and you can make it without an Ante. It wins on a pair or better and loses on anything less, which is three hands in four.';
    }
    return '';
  }
  function ppPaysText(G) { var P = TE.PAIRPLUS[G.rules.pp]; return 'Pair 1, flush ' + P[2] + ', straight ' + P[3] + ', trips ' + P[4] + ', straight flush ' + P[5] + ' (to 1)'; }

  function sel(key, label, opts, v) {
    var h = '<label class="tcp-field"><span class="k">' + label + '</span><select data-k="' + key + '">';
    opts.forEach(function (o) { h += '<option value="' + o[0] + '"' + (String(o[0]) === String(v) ? ' selected' : '') + '>' + o[1] + '</option>'; });
    return h + '</select></label>';
  }
  function spot(t, label) { return '<button type="button" class="z z-' + t + '" data-t="' + t + '"><b>' + label + '</b><span class="stk"></span></button>'; }

  function mount(where) {
    var root = document.querySelector(where); if (!root || !TE) return;
    var S = load(), G, T, lastCard = 'ante', rebuys = 0, last = null;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (TE.BONUS_KEYS.indexOf(S.bonus) < 0) S.bonus = DEFAULTS.bonus;
    if (TE.PAIRPLUS_KEYS.indexOf(S.pp) < 0) S.pp = DEFAULTS.pp;
    if (TE.MAXES.indexOf(+S.max) < 0) S.max = DEFAULTS.max;

    root.innerHTML = '<div class="tcp">' +
      '<div class="tcp-bar">' +
        sel('bonus', 'Ante bonus', TE.BONUS_KEYS.map(function (k) { return [k, TE.BONUS_LABEL[k]]; }), S.bonus) +
        sel('pp', 'Pair Plus pays', TE.PAIRPLUS_KEYS.map(function (k) { return [k, k + (k === '40-30-6-3-1' ? ' (the common one)' : '')]; }), S.pp) +
        sel('max', 'Table maximum', TE.MAXES.map(function (m) { return [m, usd(m)]; }), S.max) +
        sel('start', 'Buy-in', [[500, '$500'], [1000, '$1,000'], [5000, '$5,000']], S.start) +
        '<label class="tcp-toggle"><input type="checkbox" data-k="same"' + (S.same ? ' checked' : '') + '> Same bets next hand</label>' +
        '<p class="tcp-note">$10 minimum on the Ante and on Pair Plus. Changing a table rule clears the felt and starts a new session.</p>' +
      '</div>' +
      '<div class="tcp-grid"><div class="tcp-main">' +
        '<div class="tcp-tray">' +
          '<div class="tcp-state"><div class="k"></div><div class="v"></div></div>' +
          '<div class="tcp-actions">' +
            '<button type="button" class="tcp-btn gold tcp-deal">Deal</button>' +
            '<button type="button" class="tcp-btn gold tcp-play" hidden>Play</button>' +
            '<button type="button" class="tcp-btn ghost tcp-fold" hidden>Fold</button>' +
          '</div>' +
        '</div>' +
        '<div class="tcp-msg" aria-live="polite"></div>' +
        '<div class="tcp-feltwrap"><div class="tcp-felt" role="group" aria-label="Three Card Poker layout">' +
          '<div class="tcp-dealer"><div class="tcp-lbl">DEALER</div><div class="tcp-cards" data-who="dealer"></div><div class="tcp-hname" data-who="dealer"></div></div>' +
          '<div class="tcp-rule">DEALER PLAYS WITH QUEEN HIGH OR BETTER</div>' +
          '<div class="tcp-pt tcp-pt-pp"></div><div class="tcp-pt tcp-pt-ab"></div>' +
          '<div class="tcp-seat">' +
            '<div class="tcp-spots">' + spot('pp', 'PAIR PLUS') + spot('ante', 'ANTE') + spot('play', 'PLAY') + '</div>' +
            '<div class="tcp-hand"><div class="tcp-lbl">YOUR HAND</div><div class="tcp-cards" data-who="player"></div><div class="tcp-hname" data-who="player"></div></div>' +
          '</div>' +
        '</div></div>' +
        '<div class="tcp-hint"></div>' +
        '<div class="tcp-bets" aria-live="off"></div>' +
        '<div class="tcp-bank">' +
          '<div class="tcp-rack"><div class="k">Chip <i>— pick one, then tap Ante or Pair Plus</i></div><div class="rackrow">' +
            CHIPS.map(function (v) { return '<button type="button" class="pile" data-chip="' + v + '" aria-label="$' + v + ' chip"><span class="chip c' + v + '"></span><small>$' + v + '</small></button>'; }).join('') +
            '<button type="button" class="pile take" data-chip="take"><span class="tk">✕</span><small>Take down</small></button>' +
          '</div></div>' +
          '<div class="tcp-money"><div><span class="k">Rack</span><b class="rack"></b></div><div><span class="k">On the felt</span><b class="onfelt"></b></div>' +
            '<div class="tcp-bankbtns"><button type="button" class="tcp-btn ghost small tcp-clear">Take down all</button><button type="button" class="tcp-btn ghost small tcp-rebuy" hidden>Rebuy</button></div></div>' +
        '</div>' +
      '</div>' +
      '<aside class="tcp-side">' +
        '<div class="tcp-tabs" role="tablist">' +
          '<button type="button" role="tab" class="tcp-tab on" data-p="card" aria-selected="true">Bet card</button>' +
          '<button type="button" role="tab" class="tcp-tab" data-p="math" aria-selected="false">The math</button>' +
          '<button type="button" role="tab" class="tcp-tab" data-p="session" aria-selected="false">Session</button>' +
        '</div>' +
        '<div class="tcp-pane" data-p="card" role="tabpanel"></div>' +
        '<div class="tcp-pane" data-p="math" role="tabpanel" hidden></div>' +
        '<div class="tcp-pane" data-p="session" role="tabpanel" hidden></div>' +
      '</aside></div></div>';

    var $ = function (s) { return root.querySelector(s); }, $$ = function (s) { return [].slice.call(root.querySelectorAll(s)); };
    var felt = $('.tcp-felt'), msg = $('.tcp-msg'), hint = $('.tcp-hint');
    var btnDeal = $('.tcp-deal'), btnPlay = $('.tcp-play'), btnFold = $('.tcp-fold');

    function rules() { return { bonus: S.bonus, pp: S.pp, max: +S.max }; }     // $10 minimum, no setting (as at the Craps Table)
    function newSession() {
      G = TE.create(rules()); T = G.Table({ bankroll: S.bank }); rebuys = 0; last = null;
      renderPaytables(); renderMath(); render(); renderSession();
    }
    function persist() { S.bank = T.bank + T.onFelt(); save(S); }
    function eA() { return G.ante().edge; }
    function eP() { return G.pairPlus().edge; }

    /* ---------- betting ---------- */
    function act(t) {
      showCard(t);
      if (t === 'play') {
        if (T.phase === 'decide') { decide('play'); return; }
        say('The Play bet goes down after the deal, once you’ve seen your cards. It is always exactly the Ante.', 'info'); return;
      }
      if (T.phase !== 'bet') { say('Bets are locked once the cards are out. Play or fold.', 'info'); return; }
      if (S.chip === 'take') {
        var r0 = T.remove(t);
        say(r0.ok ? 'Took down ' + NAME[t] + ': ' + usd(r0.amount) + ' back to the rack.' : 'Nothing on ' + NAME[t] + ' to take down.', 'info');
        persist(); render(); return;
      }
      var R = G.rules, have = T.bets[t], a = S.chip, note = '';
      if (have >= R.max) { say(NAME[t] + ' is at the table maximum: ' + usd(have) + '.', 'info'); return; }
      if (have + a < R.min) { a = R.min - have; note = 'The minimum on ' + NAME[t] + ' is ' + usd(R.min) + '.'; }
      if (have + a > R.max) { a = R.max - have; note = 'Filled to the table maximum: ' + usd(R.max) + ' on ' + NAME[t] + '.'; }
      var res = T.place({ type: t, amount: a });
      if (!res.ok) { say(res.reason, 'info'); return; }
      say(usd(a) + ' on ' + NAME[t] + '.' + (note ? ' <span class="dimn">' + note + '</span>' : ''), 'info');
      persist(); render();
    }
    function clearAll() {
      if (T.phase !== 'bet') { say('Bets are locked once the cards are out. Play or fold.', 'info'); return; }
      var back = 0; ['ante', 'pp'].forEach(function (k) { var r = T.remove(k); if (r.ok) back += r.amount; });
      say(back ? usd(back) + ' back to the rack.' : 'Nothing to take down.', 'info');
      persist(); render();
    }

    /* ---------- the hand ---------- */
    function deal() {
      if (T.phase !== 'bet') return;
      var hadFocus = document.activeElement === btnDeal;
      var r = T.deal();
      if (!r.ok) { say(r.reason, 'info'); return; }
      clearMarks();
      var h = r.hand;
      drawCards(h, true);
      if (h.done) { finish(h, hadFocus); return; }       // Pair Plus alone: settled on the deal
      var d = h.d, pp = h.pp ? ' <span class="dimn">Pair Plus is already decided by these cards: ' + (h.ppNet > 0 ? 'it pays ' + usd(h.ppNet) : 'it loses') + '.</span>' : '';
      var short_ = T.canAffordPlay() ? '' : ' <span class="dimn">The rack holds ' + usd(T.bank) + ', not enough to Play ' + usd(T.bets.ante) + '. You can still fold.</span>';
      say('<b>' + d.name + '.</b> Play ' + usd(T.bets.ante) + ' or fold?' + pp + short_);
      persist(); render();
      if (hadFocus) (T.canAffordPlay() ? btnPlay : btnFold).focus();
    }
    function decide(choice) {
      if (T.phase !== 'decide') return;
      var hadFocus = document.activeElement === btnPlay || document.activeElement === btnFold;
      var r = T.act(choice);
      if (!r.ok) { say(r.reason, 'info'); return; }
      drawCards(r.hand, false, true);
      finish(r.hand, hadFocus);
    }
    function finish(h, hadFocus) {
      last = h;
      markSpots(h);
      var again = '';
      if (S.same) {
        var miss = [];
        ['ante', 'pp'].forEach(function (k) { if (h.bets[k] && !T.place({ type: k, amount: h.bets[k] }).ok) miss.push(NAME[k]); });
        if (miss.length) again = ' · not enough in the rack to put back ' + miss.join(' and ');
      }
      narrate(h, again);
      persist(); render(); renderSession();
      if (hadFocus) btnDeal.focus();
    }
    function narrate(h, again) {
      var d = h.d, story;
      if (h.outcome === 'pponly') story = 'Pair Plus only. <b>' + d.name + '</b>: ' + (h.ppNet > 0 ? 'Pair Plus pays ' + d.ppPays + ' to 1.' : 'less than a pair, so Pair Plus loses.') + ' <span class="dimn">The dealer’s hand doesn’t matter to this bet.</span>';
      else if (h.outcome === 'fold') story = 'You fold. The dealer had ' + h.dealerName + '.';
      else if (h.outcome === 'nq') story = 'Dealer has ' + h.dealerName + ': no Queen, no qualifier. Ante pays, Play pushes.';
      else if (h.outcome === 'win') story = 'Dealer qualifies with ' + h.dealerName + '. Yours wins: ' + d.name + '.';
      else if (h.outcome === 'lose') story = 'Dealer qualifies with ' + h.dealerName + ', which beats yours: ' + d.name + '.';
      else story = 'Dealer has ' + h.dealerName + ': the same hand as yours. Ante and Play push.';
      var lines = h.lines.map(function (l) {
        return NAME[l.bet] + ' <b class="' + (l.net > 0 ? 'up' : l.net < 0 ? 'dn' : 'au') + '">' + (l.r === 'push' ? 'push' : signed(l.net)) + '</b>';
      });
      var dec = '';
      if (h.ante) {
        var best = h.d.best === 'fold' ? 'folding' : 'playing';
        if (h.decisionCost > 0.005) dec = ' · <span class="dn">' + (h.choice === 'fold' ? 'Folding' : 'Playing') + ' cost ' + usd(h.decisionCost, true) + ' against ' + best + (h.forced ? ' (the rack couldn’t cover the Play)' : '') + '</span>';
        else dec = ' · decision: the right one';
      }
      var h2 = story + '<span class="evs">' + lines.join(' · ') + '</span>' +
        '<span class="evline">This hand: <b class="' + cls(h.net) + '">' + signed(h.net) + '</b> · deal luck ' + signed(h.dealLuck, true) + (h.ante ? ' · dealer luck ' + signed(h.dealerLuck, true) : '') + dec + again + '</span>';
      say(h2);
    }
    function say(h, c) { msg.className = 'tcp-msg' + (c ? ' ' + c : ''); msg.innerHTML = h; }
    function clearMarks() { $$('.z.win,.z.lose,.z.push').forEach(function (e) { e.classList.remove('win', 'lose', 'push'); }); }
    function markSpots(h) {
      var by = {}; h.lines.forEach(function (l) { var k = l.bet === 'bonus' ? 'ante' : l.bet; by[k] = (by[k] || 0) + l.net; });
      Object.keys(by).forEach(function (k) { var el = felt.querySelector('.z-' + k); if (el) el.classList.add(by[k] > 0 ? 'win' : by[k] < 0 ? 'lose' : 'push'); });
    }

    /* ---------- cards on the felt ---------- */
    function drawCards(h, dealing, reveal) {
      var P = sorted(h.player), Dl = sorted(h.dealer);
      var step = reduce ? 0 : 110, pc = $('.tcp-cards[data-who="player"]'), dc = $('.tcp-cards[data-who="dealer"]');
      var showDealer = h.done;
      if (dealing) {
        pc.innerHTML = P.map(function (c, i) { return cardHTML(c, { anim: !reduce, step: step }, i * 2); }).join('');
        dc.innerHTML = Dl.map(function (c, i) { return cardHTML(c, { anim: !reduce, step: step, back: !showDealer }, i * 2 + 1); }).join('');
      }
      if (reveal || (dealing && showDealer)) dc.innerHTML = Dl.map(function (c, i) { return cardHTML(c, { anim: !reduce, step: reduce ? 0 : 90 }, i); }).join('');
      $('.tcp-hname[data-who="player"]').textContent = h.d.name;
      $('.tcp-hname[data-who="dealer"]').textContent = showDealer || reveal ? h.dealerName + (h.qualifies ? ' · qualifies' : ' · doesn’t qualify') : '';
      felt.classList.toggle('folded', h.choice === 'fold');
    }
    function emptyCards() {
      $('.tcp-cards[data-who="player"]').innerHTML = [0, 1, 2].map(function () { return cardHTML(null); }).join('');
      $('.tcp-cards[data-who="dealer"]').innerHTML = [0, 1, 2].map(function () { return cardHTML(null); }).join('');
      $$('.tcp-hname').forEach(function (e) { e.textContent = ''; });
    }

    /* ---------- rendering ---------- */
    function render() {
      var b = T.bets, decideP = T.phase === 'decide';
      $$('.z').forEach(function (el) {
        var t = el.dataset.t, a = b[t];
        el.querySelector('.stk').innerHTML = stack(a);
        el.classList.toggle('has', a > 0);
        el.classList.toggle('closed', t === 'play' ? !decideP : decideP);
        var e = t === 'pp' ? eP() : eA();
        el.setAttribute('aria-label', NAME[t] + (t === 'play' ? (decideP ? ': play ' + usd(b.ante) : ', after the deal') : ', house edge ' + pct(e)) + (a ? ', your bet ' + usd(a) : ''));
      });
      $('.tcp-state .k').textContent = decideP ? 'Your move' : 'Place your bets';
      $('.tcp-state .v').textContent = decideP ? 'Play to match the Ante, or fold and lose it.' : 'Ante, Pair Plus, or both. $10 minimum, ' + usd(G.rules.max) + ' maximum.';
      btnDeal.hidden = decideP; btnPlay.hidden = !decideP; btnFold.hidden = !decideP;
      btnDeal.disabled = !(b.ante || b.pp);
      if (decideP) { btnPlay.textContent = 'Play ' + usd(b.ante); btnPlay.disabled = !T.canAffordPlay(); }
      $$('.pile').forEach(function (p) { var v = p.dataset.chip; p.setAttribute('aria-pressed', String(v === String(S.chip))); p.disabled = decideP || (v !== 'take' && +v > T.bank); });
      $('.rack').textContent = usd(T.bank); $('.onfelt').textContent = usd(T.onFelt());
      $('.tcp-clear').disabled = decideP;
      $('.tcp-rebuy').hidden = !(T.bank < G.rules.min && !T.onFelt() && T.phase === 'bet');
      renderBets(); showCard(lastCard); renderCost();
    }
    function renderPaytables() {
      var P = TE.PAIRPLUS[G.rules.pp], B = TE.BONUS[G.rules.bonus];
      function row(n, v) { return '<span>' + n + '</span><b>' + v + ' TO 1</b>'; }
      $('.tcp-pt-pp').innerHTML = '<div class="h">PAIR PLUS</div><div class="g">' + row('Straight flush', P[5]) + row('Three of a kind', P[4]) + row('Straight', P[3]) + row('Flush', P[2]) + row('Pair', P[1]) + '</div>';
      $('.tcp-pt-ab').innerHTML = '<div class="h">ANTE BONUS</div><div class="g">' + row('Straight flush', B[5]) + row('Three of a kind', B[4]) + row('Straight', B[3]) + '</div>';
    }

    /* ---------- Your bets: amount, house edge and value now ---------- */
    function renderBets() {
      var b = T.bets, box = $('.tcp-bets'), decideP = T.phase === 'decide', h = T.hand, rows = '', tot = 0;
      if (!b.ante && !b.pp) {
        box.innerHTML = '<div class="tcp-bh"><span class="k">Your bets</span></div><p class="tcp-help">No bets down.' + (last ? '' : ' Put a chip on the Ante (and Pair Plus, if you like) and deal.') + '</p>' + lastLine();
        return;
      }
      function tr(name, sub, amt, edge, band, v, vsub) {
        tot += v;
        return '<tr><td>' + name + (sub ? '<small>' + sub + '</small>' : '') + '</td><td>' + usd(amt) + '</td><td><span class="band ' + band + '">' + pct(edge) + '</span></td><td class="' + cls(v) + '">' + signed(v, true) + (vsub ? '<small>' + vsub + '</small>' : '') + '</td></tr>';
      }
      if (b.ante) {
        if (!decideP) rows += tr('Ante', 'Play to come', b.ante, eA(), G.band(eA()), -eA() * b.ante, '−' + pct(eA()) + ' × ' + usd(b.ante));
        else rows += tr('Ante', 'cards seen', b.ante, eA(), G.band(eA()), b.ante * Math.max(h.d.evPlay, -1), 'if you make the better choice');
      }
      if (b.pp) {
        if (!decideP) rows += tr('Pair Plus', G.rules.pp, b.pp, eP(), G.band(eP()), -eP() * b.pp, '−' + pct(eP()) + ' × ' + usd(b.pp));
        else rows += tr('Pair Plus', 'decided by your cards', b.pp, eP(), G.band(eP()), h.ppNet, h.ppNet > 0 ? h.d.name.split(',')[0] + ' pays ' + h.d.ppPays + ' to 1' : 'less than a pair: lost');
      }
      var out = '<div class="tcp-bh"><span class="k">Your bets</span><span class="s">' + (decideP ? 'value now, with your cards on the table' : 'value now, before the cards come out') + '</span></div>' +
        '<div class="tw"><table class="tcp-t bets"><thead><tr><th>Bet</th><th>Amount</th><th>House edge</th><th>Value now</th></tr></thead><tbody>' + rows +
        '<tr class="tot"><td>Total</td><td>' + usd(b.ante + b.pp) + '</td><td></td><td class="' + cls(tot) + '">' + signed(tot, true) + '</td></tr></tbody></table></div>';
      if (decideP && b.ante) out += decisionBox(h);
      else out += '<p class="tcp-fine">Value now is what the bets are worth on average from here. Before the deal it is minus the house edge times the bet; the Ante’s edge assumes you Play and fold correctly afterwards.</p>';
      box.innerHTML = out + lastLine();
    }
    function decisionBox(h) {
      var d = h.d, a = h.ante, play = a * d.evPlay, fold = -a, diff = Math.abs(play - fold);
      var best = d.best === 'fold' ? 'Fold' : 'Play', agree = d.q64 === (d.best === 'fold' ? 'fold' : 'play');
      return '<div class="tcp-dec"><div class="dh">Your call: <b>' + d.name + '</b></div>' +
        '<div class="opts"><div class="o' + (d.best !== 'fold' ? ' best' : '') + '"><span class="k">Play</span><b class="' + cls(play) + '">' + signed(play, true) + '</b><small>' + (d.evPlay >= 0 ? '+' : '−') + Math.abs(d.evPlay).toFixed(4) + ' per $1 of Ante</small></div>' +
        '<div class="o' + (d.best === 'fold' ? ' best' : '') + '"><span class="k">Fold</span><b class="dn">' + signed(fold, true) + '</b><small>the Ante is lost</small></div></div>' +
        '<p class="tcp-help"><b>Better: ' + best + '</b>, by ' + usd(diff, true) + '. The Q-6-4 rule says <b>' + (d.q64 === 'play' ? 'Play' : 'Fold') + '</b>' + (agree ? ' too.' : '.') +
        ' Of the ' + TE.N_DEALER.toLocaleString('en-US') + ' hands the dealer can hold against yours, ' + d.nq.toLocaleString('en-US') + ' don’t qualify; of the rest you beat ' + d.w.toLocaleString('en-US') + ', lose to ' + d.l.toLocaleString('en-US') + ' and tie ' + d.t.toLocaleString('en-US') + '.' +
        (d.bonus ? ' Playing also collects the Ante bonus: ' + d.bonus + ' to 1.' : '') + '</p></div>';
    }
    function lastLine() {
      if (!last) return '';
      var h = last;
      return '<p class="tcp-last"><span class="k">Last hand</span> expected ' + signed(h.V0, true) + ' · deal luck ' + signed(h.dealLuck, true) +
        (h.ante ? ' · decision cost ' + usd(h.decisionCost, true) + ' · dealer luck ' + signed(h.dealerLuck, true) : '') + ' = result <b class="' + cls(h.net) + '">' + signed(h.net) + '</b></p>';
    }

    /* ---------- bet card (side pane + the one-line hint under the felt) ---------- */
    function showCard(t) {
      lastCard = t;
      var pane = $('.tcp-pane[data-p="card"]'), R = G.rules, b = T.bets[t], A = G.ante(), e = t === 'pp' ? eP() : eA(), band = G.band(e), B = TE.BONUS[R.bonus];
      var pays = t === 'pp' ? ppPaysText(G) : t === 'ante' ? '1 to 1, plus the Ante bonus when you Play: straight ' + B[3] + ', trips ' + B[4] + ', straight flush ' + B[5] + ' (to 1)' : '1 to 1; pushes when the dealer doesn’t qualify';
      hint.innerHTML = '<b>' + NAME[t] + '</b> · pays ' + (t === 'pp' ? 'on a pair or better' : '1:1') + ' · house edge <span class="band ' + band + '">' + pct(e) + '</span>' + (t === 'play' ? ' <span class="dimn">(counted with the Ante)</span>' : '');
      var edgeNote = t === 'pp' ? 'of every dollar bet on Pair Plus, ' + R.pp + ' paytable' :
        'of the Ante with correct play, ' + TE.BONUS_LABEL[R.bonus] + ' bonus; ' + pct(A.edgeWagered) + ' of all the money put up (Ante + Play)';
      pane.innerHTML = '<h4>' + NAME[t] + '</h4>' +
        '<div class="tcp-edge ' + band + '"><span>House edge</span><b>' + pct(e) + '</b><i>' + edgeNote + '</i></div>' +
        '<dl class="tcp-dl"><dt>Pays</dt><dd>' + pays + '</dd>' +
        (t === 'pp' ? '<dt>Wins</dt><dd>' + pct(1 - TE.counts()[0] / TE.N_HANDS, 1) + ' of hands (a pair or better)</dd>' : '') +
        (t === 'ante' ? '<dt>You Play</dt><dd>' + pct(A.pPlay, 1) + ' of hands (Q-6-4 or better); fold the other ' + pct(A.pFold, 1) + '</dd>' : '') +
        '<dt>Bet size</dt><dd>' + (t === 'play' ? 'exactly the Ante' : 'minimum ' + usd(R.min) + ', maximum ' + usd(R.max)) + '</dd>' +
        (b ? '<dt>Your bet</dt><dd>' + usd(b) + '</dd>' : '') + '</dl>' +
        '<p class="tcp-help">' + how(t, G) + '</p>';
    }

    /* ---------- The math pane ---------- */
    function renderMath() {
      var A = G.ante(), AA = G.ante('always'), miss = G.q64Misses(), P = G.pairPlus(), CN = TE.counts(), dq = 0;
      TE.classes().forEach(function (e) { if (TE.qualifies(e.score)) dq += e.count; });
      var h = '<h4>The averages at this table</h4><dl class="tcp-dl">' +
        '<dt>Ante edge</dt><dd>' + pct(A.edge) + ' of the Ante with correct play (' + TE.BONUS_LABEL[G.rules.bonus] + ' bonus) = <b>' + pct(A.edgeWagered) + '</b> of all the money you put up</dd>' +
        '<dt>Pair Plus edge</dt><dd>' + pct(P.edge) + ' on the ' + G.rules.pp + ' paytable</dd>' +
        '<dt>You fold</dt><dd>' + pct(A.pFold, 1) + ' of hands: everything below Queen-Six-Four</dd>' +
        '<dt>Average wager</dt><dd>' + A.avgWager.toFixed(3) + ' Antes a hand (the Ante, plus the Play on the ' + pct(A.pPlay, 1) + ' you play)</dd>' +
        '<dt>Dealer qualifies</dt><dd>' + pct(dq / TE.N_HANDS, 1) + ' of hands; ' + pct(A.dealerQualifiesWhenPlaying, 1) + ' of the hands you play</dd>' +
        '<dt>Q-6-4 rule</dt><dd>' + (miss.length ? 'costs ' + (100 * (G.ante('q64').edge - A.edge)).toFixed(4) + ' points against perfect play' : 'exactly as good as perfect play: every hand it plays is worth playing and every hand it folds is worth folding') + '</dd>' +
        '<dt>Never folding</dt><dd>' + pct(AA.edge) + ' of the Ante (' + pct(AA.edgeWagered) + ' of the money put up)</dd>' +
        '<dt>Pace</dt><dd>about ' + TE.PACE + ' hands an hour</dd>' +
        '<dt>Cost per hour</dt><dd class="tcp-cost"></dd></dl>';
      h += '<h4>Hands and what they pay</h4><div class="tw"><table class="tcp-t"><thead><tr><th>Hand</th><th>Of 22,100</th><th>Chance</th><th>Pair Plus</th><th>Ante bonus</th></tr></thead><tbody>';
      CAT_ORDER.forEach(function (c) {
        h += '<tr><td>' + TE.CAT_NAME[c] + '</td><td>' + CN[c].toLocaleString('en-US') + '</td><td>' + pct(CN[c] / TE.N_HANDS) + '</td><td>' + (c ? G.ppPays(c) + ' to 1' : 'loses') + '</td><td>' + (G.bonus(c) ? G.bonus(c) + ' to 1' : '—') + '</td></tr>';
      });
      h += '</tbody></table></div><p class="tcp-fine">With three cards a straight is rarer than a flush, so it ranks higher. A-2-3 is the lowest straight and Q-K-A the highest; K-A-2 is just Ace high.</p>';
      h += '<h4>The price of each bet</h4><p class="tcp-help">Every paytable you can pick here, counted exactly. This table’s rules are marked. <span class="band up">Under 2%</span> <span class="band au">2–5%</span> <span class="band dn">5% and up</span></p>';
      var rows = [];
      TE.BONUS_KEYS.forEach(function (k) { var g = TE.create({ bonus: k }), a = g.ante(); rows.push({ name: 'Ante & Play, ' + TE.BONUS_LABEL[k] + ' bonus, of the Ante', e: a.edge, on: k === G.rules.bonus }); rows.push({ name: 'Ante & Play, ' + TE.BONUS_LABEL[k] + ', of all money put up', e: a.edgeWagered, on: k === G.rules.bonus }); });
      TE.PAIRPLUS_KEYS.forEach(function (k) { rows.push({ name: 'Pair Plus, ' + k, e: TE.create({ pp: k }).pairPlus().edge, on: k === G.rules.pp }); });
      rows.push({ name: 'Ante & Play, never folding (' + TE.BONUS_LABEL[G.rules.bonus] + '), of the Ante', e: AA.edge, on: false });
      rows.sort(function (x, y) { return x.e - y.e; });
      h += '<div class="tw"><table class="tcp-t"><thead><tr><th>Bet</th><th>House edge</th></tr></thead><tbody>' +
        rows.map(function (r) { return '<tr' + (r.on ? ' class="on"' : '') + '><td>' + r.name + (r.on ? ' <small>this table</small>' : '') + '</td><td><span class="band ' + G.band(r.e) + '">' + pct(r.e) + '</span></td></tr>'; }).join('') +
        '</tbody></table></div><p class="tcp-fine">Every figure counts all 22,100 hands you can be dealt against all 18,424 hands the dealer can hold, with the Play-or-fold choice made correctly for each one.</p>';
      $('.tcp-pane[data-p="math"]').innerHTML = h;
      renderCost();
    }
    /* Expected cost per hour at the bets now on the felt (or the last hand's, or a $10 Ante). */
    function renderCost() {
      var el = $('.tcp-cost'); if (!el) return;
      var b = T.bets.ante || T.bets.pp ? T.bets : last ? last.bets : { ante: 10, pp: 0 };
      var per = eA() * b.ante + eP() * b.pp, hr = per * TE.PACE;
      el.innerHTML = usd(hr, true) + ' expected, at ' + (b.ante ? usd(b.ante) + ' Ante' : '') + (b.ante && b.pp ? ' + ' : '') + (b.pp ? usd(b.pp) + ' Pair Plus' : '') + ' a hand (' + usd(per, true) + ' × ' + TE.PACE + ')';
    }

    /* ---------- Session pane ---------- */
    function tile(k, v, c, s) { return '<div class="st"><div class="k">' + k + '</div><div class="v ' + (c || '') + '">' + v + '</div>' + (s ? '<div class="s">' + s + '</div>' : '') + '</div>'; }
    function renderSession() {
      var L = T.ledger, pane = $('.tcp-pane[data-p="session"]');
      var h = '<div class="tcp-stats">' +
        tile('Hands', L.hands.toLocaleString('en-US'), '', L.decisions ? L.plays + ' played · ' + L.folds + ' folded' : '') +
        tile('Money put up', usd(L.wagered), '', 'Antes, Plays and Pair Plus') +
        tile('Expected result', signed(L.expected, true), cls(L.expected), 'the house edge on each bet as it was dealt') +
        tile('Actual result', signed(L.actual), cls(L.actual), 'what the rack says') +
        tile('Deal luck', signed(L.dealLuck, true), cls(L.dealLuck), 'the cards you got: value once seen, minus value before') +
        tile('Dealer luck', signed(L.dealerLuck, true), cls(L.dealerLuck), 'the dealer’s cards: result, minus value after your decision') +
        tile('Decision cost', usd(L.decisionCost, true), L.decisionCost > 0.005 ? 'dn' : '', L.decisions ? (L.decisions - L.mistakes) + ' of ' + L.decisions + ' decisions right' + (L.forced ? ' · ' + L.forced + ' forced by a short rack' : '') : 'value given up by a wrong Play or fold') +
        tile('Q-6-4 rule', L.decisions ? L.q64Agree + ' of ' + L.decisions : '—', '', 'decisions that matched it') + '</div>' +
        '<p class="tcp-help"><b>Actual = expected + deal luck − decision cost + dealer luck.</b> Expected is fixed when the cards are dealt. Deal luck is what your three cards turned the bets into; decision cost is what a wrong Play or fold gave back; dealer luck is everything the dealer’s three cards did after that.</p>';
      var K = L.byKey, rows = [['Ante & Play', K.ante, eA(), 'Ante, Play and bonus'], ['Pair Plus', K.pp, eP(), G.rules.pp]].filter(function (r) { return r[1].bets; });
      if (rows.length) {
        h += '<h4>Your bets</h4><div class="tw"><table class="tcp-t recap"><thead><tr><th>Bet</th><th>Edge</th><th>Expected</th><th>Actual</th></tr></thead><tbody>';
        rows.forEach(function (r) {
          h += '<tr><td>' + r[0] + '<small>' + usd(r[1].wagered) + ' in ' + r[1].bets + (r[1].bets === 1 ? ' hand' : ' hands') + '</small></td><td><span class="band ' + G.band(r[2]) + '">' + pct(r[2]) + '</span></td><td class="' + cls(r[1].expected) + '">' + signed(r[1].expected, true) + '</td><td class="' + cls(r[1].actual) + '">' + signed(r[1].actual) + '</td></tr>';
        });
        h += '</tbody></table></div>';
        var perHand = L.hands ? -L.expected / L.hands : 0;
        h += '<p class="tcp-help">Your mix of bets has cost ' + pct(L.wagered ? -L.expected / L.wagered : 0, 3) + ' of the money you put up, ' + usd(perHand, true) + ' a hand on average' +
          (L.decisionCost > 0.005 ? ', plus ' + usd(L.decisionCost / L.hands, true) + ' a hand in decisions' : '') + '. At about ' + TE.PACE + ' hands an hour that is the price of the chair.</p>';
      } else h += '<p class="tcp-help">No hands yet this session.</p>';
      h += '<div class="tcp-bankbtns"><button type="button" class="tcp-btn ghost small tcp-reset">New session (' + usd(S.start) + ')</button></div>' +
        (rebuys ? '<p class="tcp-fine">Rebuys this session: ' + rebuys + '.</p>' : '');
      pane.innerHTML = h;
    }

    /* ---------- events ---------- */
    felt.addEventListener('click', function (e) { var z = e.target.closest('.z'); if (z) act(z.dataset.t); });
    felt.addEventListener('mouseover', function (e) { var z = e.target.closest('.z'); if (z && z.dataset.t !== lastCard) showCard(z.dataset.t); });
    felt.addEventListener('focusin', function (e) { var z = e.target.closest('.z'); if (z) showCard(z.dataset.t); });
    btnDeal.addEventListener('click', deal);
    btnPlay.addEventListener('click', function () { decide('play'); });
    btnFold.addEventListener('click', function () { decide('fold'); });
    $('.tcp-clear').addEventListener('click', clearAll);
    $('.tcp-rebuy').addEventListener('click', function () { T.bank += +S.start; rebuys++; persist(); render(); renderSession(); say('Rebought for ' + usd(S.start) + '.', 'info'); });
    $('.rackrow').addEventListener('click', function (e) { var p = e.target.closest('.pile'); if (!p || p.disabled) return; S.chip = p.dataset.chip === 'take' ? 'take' : +p.dataset.chip; save(S); render(); });
    $('.tcp-side').addEventListener('click', function (e) {
      var tb = e.target.closest('.tcp-tab');
      if (tb) { $$('.tcp-tab').forEach(function (x) { var on = x === tb; x.classList.toggle('on', on); x.setAttribute('aria-selected', String(on)); }); $$('.tcp-pane').forEach(function (p) { p.hidden = p.dataset.p !== tb.dataset.p; }); return; }
      if (e.target.closest('.tcp-reset')) { S.bank = +S.start; newSession(); emptyCards(); clearMarks(); say('New session: ' + usd(S.start) + ' in the rack.', 'info'); persist(); }
    });
    $('.tcp-bar').addEventListener('change', function (e) {
      var k = e.target.dataset.k; if (!k) return;
      if (k === 'same') { S.same = e.target.checked; save(S); return; }
      persist();
      S[k] = e.target.value;
      if (k === 'start') S.bank = +S.start;
      save(S); newSession(); emptyCards(); clearMarks(); felt.classList.remove('folded');
      say(k === 'start' ? 'New session: ' + usd(S.start) + ' in the rack.' : 'New table rules. The felt is cleared and a new session starts.', 'info');
    });

    if (typeof S.chip !== 'number' && S.chip !== 'take') S.chip = 5;
    if (!(+S.bank >= 0)) S.bank = +S.start;
    S.bank = +S.bank;
    newSession(); emptyCards();
    say('Pick a chip, put it on the <b>Ante</b>, and deal. Add <b>Pair Plus</b> if you like. Hover, focus or tap a spot to see what it pays and what it costs.', 'info');
  }

  return { mount: mount };
})();
