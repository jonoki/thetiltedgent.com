/* The Tilted Gent — Three Card Poker engine for the Three Card Poker Table. Vanilla JS, no dependencies; runs in
   the browser (window.TcpEngine) and in Node (module.exports) for tables/checks/tcp_engine_check.js.
   Every figure is counted, not simulated: one 52-card deck, 22,100 three-card hands for the player and, for each,
   the C(49,3) = 18,424 hands the dealer can hold. Player hands that differ only by a relabelling of suits have
   the same value, so they are grouped (suit isomorphism) and each group is enumerated once against the dealer.
   Rules (Three Card Poker as dealt in North American casinos; Wizard of Odds "Three Card Poker", fetched for
   tables/three-card-poker.html): ranks high to low straight flush, three of a kind, straight, flush, pair, high card;
   A-2-3 is the lowest straight and Q-K-A the highest, K-A-2 is not a straight; ties are broken card by card.
   Ante then Play (equal to the Ante) or fold. The dealer qualifies with Queen-high or better. Dealer doesn't qualify:
   Ante pays 1:1, Play pushes. Dealer qualifies: the better hand wins Ante and Play 1:1, a tie pushes both.
   The Ante bonus is paid on the Ante whenever the player plays, whatever the dealer holds. Pair Plus is paid on the
   player's three cards alone, fold or not, and loses on high card.
   Values (per $1 of ante):
     EV(fold) = -1
     EV(play) = B(hand) + [ nq + 2*(W - L) ] / 18424
       nq = dealer hands that don't qualify (Ante +1, Play 0); W / L = qualifying dealer hands the player beats / loses to
       (Ante and Play +1 each / -1 each); ties are 0; B = the Ante bonus for the player's hand.
     Ante edge = -(1/22100) * sum over player hands of max(EV(play), -1)       (optimal play)
     Pair Plus edge = -(1/22100) * sum over player hands of pays(hand), with pays(high card) = -1. */
(function (root) {
  'use strict';

  /* ---------- cards: 0..51, rank = 2 + (c >> 2) (14 = ace), suit = c & 3 ---------- */
  var SUITS = ['♠', '♥', '♦', '♣'];
  var RANK_LABEL = { 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9', 10: '10', 11: 'J', 12: 'Q', 13: 'K', 14: 'A' };
  var RANK_NAME = { 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six', 7: 'Seven', 8: 'Eight', 9: 'Nine', 10: 'Ten', 11: 'Jack', 12: 'Queen', 13: 'King', 14: 'Ace' };
  var RANK_PLURAL = { 2: 'Twos', 3: 'Threes', 4: 'Fours', 5: 'Fives', 6: 'Sixes', 7: 'Sevens', 8: 'Eights', 9: 'Nines', 10: 'Tens', 11: 'Jacks', 12: 'Queens', 13: 'Kings', 14: 'Aces' };
  function rank(c) { return 2 + (c >> 2); }
  function suit(c) { return c & 3; }
  function label(c) { return RANK_LABEL[rank(c)] + SUITS[suit(c)]; }

  /* ---------- hand ranking ---------- */
  var SF = 5, TRIPS = 4, STRAIGHT = 3, FLUSH = 2, PAIR = 1, HIGH = 0;
  var CAT_NAME = ['High card', 'Pair', 'Flush', 'Straight', 'Three of a kind', 'Straight flush'];
  /* score = cat * 4096 + r1 * 256 + r2 * 16 + r3: a higher score is a better hand, equal scores tie.
     r1..r3 are the ranks in the order they are compared: high card and flush high to low; pair: the pair, the pair,
     the kicker; straights by their top card, with A-2-3 scored as 3-2-1 so it is the lowest. */
  function evaluate(c1, c2, c3) {
    var a = rank(c1), b = rank(c2), c = rank(c3), t;
    if (a < b) { t = a; a = b; b = t; }
    if (b < c) { t = b; b = c; c = t; }
    if (a < b) { t = a; a = b; b = t; }
    var flush = suit(c1) === suit(c2) && suit(c2) === suit(c3);
    if (a === b && b === c) return TRIPS * 4096 + a * 256 + a * 16 + a;
    if (a === b) return PAIR * 4096 + a * 256 + a * 16 + c;
    if (b === c) return PAIR * 4096 + b * 256 + b * 16 + a;
    var straight = (a - b === 1 && b - c === 1), wheel = (a === 14 && b === 3 && c === 2);
    if (wheel) { a = 3; b = 2; c = 1; straight = true; }
    var cat = straight ? (flush ? SF : STRAIGHT) : flush ? FLUSH : HIGH;
    return cat * 4096 + a * 256 + b * 16 + c;
  }
  function catOf(score) { return score >> 12; }
  var QUALIFY = 12 * 256;                                 // Queen-high: every score from Q-3-2 up
  function qualifies(score) { return score >= QUALIFY; }
  /* The Q-6-4 rule: play Queen-Six-Four or better, fold anything worse. */
  var Q64 = 12 * 256 + 6 * 16 + 4;
  function q64(score) { return score >= Q64; }
  function describe(score) {
    var cat = catOf(score), r1 = (score >> 8) & 15, r2 = (score >> 4) & 15, r3 = score & 15;
    function L(r) { return r === 1 ? 'A' : RANK_LABEL[r]; }
    switch (cat) {
      case SF: return 'Straight flush, ' + L(r3) + '-' + L(r2) + '-' + L(r1);
      case TRIPS: return 'Three ' + RANK_PLURAL[r1];
      case STRAIGHT: return 'Straight, ' + L(r3) + '-' + L(r2) + '-' + L(r1);
      case FLUSH: return 'Flush, ' + L(r1) + '-' + L(r2) + '-' + L(r3);
      case PAIR: return 'Pair of ' + RANK_PLURAL[r1] + ', ' + L(r3) + ' kicker';
    }
    return RANK_NAME[r1] + ' high, ' + L(r1) + '-' + L(r2) + '-' + L(r3);
  }

  /* ---------- every three-card hand, scored once ---------- */
  var N_HANDS = 22100, N_DEALER = 18424;                 // C(52,3), C(49,3)
  var HC = new Int8Array(N_HANDS * 3), SCORE = new Int32Array(N_HANDS);
  (function () {
    var i = 0;
    for (var a = 0; a < 52; a++) for (var b = a + 1; b < 52; b++) for (var c = b + 1; c < 52; c++) {
      HC[i * 3] = a; HC[i * 3 + 1] = b; HC[i * 3 + 2] = c; SCORE[i] = evaluate(a, b, c); i++;
    }
  })();
  /* Hands per category, out of 22,100. */
  function counts() {
    var n = [0, 0, 0, 0, 0, 0];
    for (var i = 0; i < N_HANDS; i++) n[catOf(SCORE[i])]++;
    return n;
  }

  /* The dealer's 18,424 possible hands against a player hand: how many don't qualify, and of the ones that do,
     how many the player beats, loses to and ties. */
  function versus(p1, p2, p3) {
    var ps = evaluate(p1, p2, p3), nq = 0, w = 0, l = 0, t = 0, n = 0;
    for (var i = 0; i < N_HANDS; i++) {
      var a = HC[i * 3], b = HC[i * 3 + 1], c = HC[i * 3 + 2];
      if (a === p1 || a === p2 || a === p3 || b === p1 || b === p2 || b === p3 || c === p1 || c === p2 || c === p3) continue;
      var ds = SCORE[i]; n++;
      if (ds < QUALIFY) nq++; else if (ps > ds) w++; else if (ps < ds) l++; else t++;
    }
    return { nq: nq, w: w, l: l, t: t, n: n };
  }

  /* Suit isomorphism: sort the cards by rank (high first, then suit), relabel suits in order of first appearance.
     Two hands with the same key are the same hand under a permutation of suits, so they have the same value. */
  function keyOf(cards) {
    var s = cards.slice().sort(function (x, y) { return rank(y) - rank(x) || suit(x) - suit(y); }), map = {}, next = 0, k = '';
    s.forEach(function (c) { var su = suit(c); if (map[su] == null) map[su] = next++; k += rank(c) + 'abcd'.charAt(map[su]) + ' '; });
    return k;
  }
  var CLASSES = null, BY_KEY = null;
  /* One entry per isomorphism class: a representative hand, how many of the 22,100 hands it stands for,
     its score and its dealer counts. Built once (about 12 million comparisons). */
  function classes() {
    if (CLASSES) return CLASSES;
    BY_KEY = {}; CLASSES = [];
    for (var i = 0; i < N_HANDS; i++) {
      var cards = [HC[i * 3], HC[i * 3 + 1], HC[i * 3 + 2]], k = keyOf(cards), e = BY_KEY[k];
      if (!e) { e = BY_KEY[k] = { key: k, cards: cards, count: 0, score: SCORE[i] }; CLASSES.push(e); }
      e.count++;
    }
    CLASSES.forEach(function (e) { var v = versus(e.cards[0], e.cards[1], e.cards[2]); e.nq = v.nq; e.w = v.w; e.l = v.l; e.t = v.t; e.n = v.n; });
    return CLASSES;
  }
  function classFor(cards) { classes(); return BY_KEY[keyOf(cards)]; }

  /* ---------- paytables ---------- */
  var BONUS = { '541': { 5: 5, 4: 4, 3: 1 }, '431': { 5: 4, 4: 3, 3: 1 }, '321': { 5: 3, 4: 2, 3: 1 } };
  var BONUS_LABEL = { '541': '5-4-1', '431': '4-3-1', '321': '3-2-1' };
  var PAIRPLUS = { '40-30-6-3-1': { 5: 40, 4: 30, 3: 6, 2: 3, 1: 1 }, '40-30-6-4-1': { 5: 40, 4: 30, 3: 6, 2: 4, 1: 1 }, '50-30-6-3-1': { 5: 50, 4: 30, 3: 6, 2: 3, 1: 1 } };
  var BONUS_KEYS = ['541', '431', '321'], PAIRPLUS_KEYS = ['40-30-6-3-1', '40-30-6-4-1', '50-30-6-3-1'];
  var MAXES = [500, 1000, 2000, 5000];
  var PACE = 70;                                          // hands per hour: tables/sim/games.js G["three-card-poker"].pace
  var DEFAULT_RULES = { bonus: '541', pp: '40-30-6-3-1', min: 10, max: 1000 };

  function gcd(a, b) { a = Math.abs(a); b = Math.abs(b); while (b) { var t = a % b; a = b; b = t; } return a || 1; }

  function create(rulesIn) {
    var R = {}, k;
    for (k in DEFAULT_RULES) R[k] = DEFAULT_RULES[k];
    for (k in rulesIn || {}) R[k] = rulesIn[k];
    var B = BONUS[R.bonus], PP = PAIRPLUS[R.pp];
    if (!B || !PP) throw new Error('unknown paytable');
    function bonus(cat) { return B[cat] || 0; }
    function ppPays(cat) { return cat === HIGH ? -1 : PP[cat]; }

    /* EV(play) per $1 of ante, as an exact numerator over 18,424. */
    function playNum(e) { return bonus(catOf(e.score)) * N_DEALER + e.nq + 2 * (e.w - e.l); }
    /* Ante & Play over all 22,100 hands under a strategy: 'optimal', 'q64' or 'always'. Exact, as integers over
       22,100 x 18,424; also the share of hands played, the average wager in antes (1 + share played) and the
       dealer's qualifying rate on the hands that are played. */
    var anteMemo = {};
    function ante(strategy) {
      strategy = strategy || 'optimal';
      if (anteMemo[strategy]) return anteMemo[strategy];
      var tot = 0, played = 0, dq = 0, dn = 0;
      classes().forEach(function (e) {
        var pn = playNum(e), play = strategy === 'always' ? true : strategy === 'q64' ? q64(e.score) : pn > -N_DEALER;
        tot += e.count * (play ? pn : -N_DEALER);
        if (play) { played += e.count; dq += e.count * (e.n - e.nq); dn += e.count * e.n; }
      });
      var den = N_HANDS * N_DEALER, g = gcd(tot, den), edge = -tot / den, pPlay = played / N_HANDS;
      return (anteMemo[strategy] = { strategy: strategy, edge: edge, edgeNum: -tot / g, edgeDen: den / g, played: played, pPlay: pPlay,
        pFold: 1 - pPlay, avgWager: 1 + pPlay, edgeWagered: edge / (1 + pPlay), dealerQualifiesWhenPlaying: dn ? dq / dn : 0 });
    }
    /* Hands where the strategies disagree: Q-6-4 against optimal play. */
    function q64Misses() {
      var out = [];
      classes().forEach(function (e) {
        var pn = playNum(e), opt = pn > -N_DEALER, rule = q64(e.score);
        if (opt !== rule) out.push({ cards: e.cards, count: e.count, score: e.score, evPlay: pn / N_DEALER, optimal: opt ? 'play' : 'fold', q64: rule ? 'play' : 'fold',
                                     cost: Math.abs(pn + N_DEALER) / N_DEALER });
      });
      return out;
    }
    function pairPlus() {
      var n = counts(), s = 0;
      for (var c = 0; c <= 5; c++) s += n[c] * ppPays(c);
      var g = gcd(s, N_HANDS);
      return { edge: -s / N_HANDS, edgeNum: -s / g, edgeDen: N_HANDS / g };
    }
    /* Everything a player needs at the decision: the hand, EV of each choice per $1 of ante, the better one, what
       the Q-6-4 rule says, and the dealer counts behind it. */
    function decision(cards) {
      var e = classFor(cards), s = evaluate(cards[0], cards[1], cards[2]), pn = playNum(e);
      return { score: s, cat: catOf(s), name: describe(s), evPlay: pn / N_DEALER, evPlayNum: pn, evFold: -1,
               best: pn > -N_DEALER ? 'play' : pn === -N_DEALER ? 'either' : 'fold', q64: q64(s) ? 'play' : 'fold',
               nq: e.nq, w: e.w, l: e.l, t: e.t, n: e.n, bonus: bonus(catOf(s)), ppPays: ppPays(catOf(s)) };
    }
    function band(x) { return x < 0.02 ? 'up' : x < 0.05 ? 'au' : 'dn'; }
    return { rules: R, bonus: bonus, ppPays: ppPays, ante: ante, pairPlus: pairPlus, q64Misses: q64Misses, decision: decision, band: band,
             Table: function (opts) { return new Table(this, opts || {}); } };
  }

  /* ---------- random cards ---------- */
  function seeded(seed) {                                 // mulberry32, as in ttg-sim.js and craps-engine.js
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function cryptoRng() {
    var c = (typeof crypto !== 'undefined' && crypto.getRandomValues) ? crypto : null;
    if (!c) return seeded((Math.random() * 4294967296) >>> 0);
    var buf = new Uint32Array(1);
    return function () { c.getRandomValues(buf); return buf[0] / 4294967296; };
  }
  /* A fresh 52-card deck, Fisher-Yates shuffled; only the six cards dealt are needed. */
  function dealSix(rng) {
    var d = []; for (var i = 0; i < 52; i++) d.push(i);
    for (var j = 0; j < 6; j++) { var r = j + Math.floor(rng() * (52 - j)), t = d[j]; d[j] = d[r]; d[r] = t; }
    return d.slice(0, 6);
  }

  /* ---------- a table: bankroll, bets, the hand, and the ledger ----------
     A hand's accounting, in dollars:
       V0 = value at the deal  = -(ante edge) * ante - (Pair Plus edge) * pairplus      (the expected result)
       V1 = value once the cards are seen = ante * max(EV play, -1) + Pair Plus's settled result
       V2 = value of the choice made      = ante * EV(choice) + Pair Plus's settled result
       R  = the result
     deal luck = V1 - V0, decision cost = V1 - V2 (never negative), dealer luck = R - V2, so
       R = V0 + deal luck - decision cost + dealer luck,  exactly, hand by hand. */
  function Table(g, opts) {
    this.g = g; this.rng = opts.rng || (opts.seed ? seeded(opts.seed) : cryptoRng());
    this.bank = opts.bankroll == null ? 1000 : opts.bankroll;
    this.phase = 'bet'; this.bets = { ante: 0, pp: 0, play: 0 }; this.hand = null;
    this.ledger = { hands: 0, decisions: 0, plays: 0, folds: 0, mistakes: 0, q64Agree: 0, forced: 0, wagered: 0, expected: 0, actual: 0,
                    dealLuck: 0, dealerLuck: 0, decisionCost: 0,
                    byKey: { ante: { bets: 0, wagered: 0, expected: 0, actual: 0 }, pp: { bets: 0, wagered: 0, expected: 0, actual: 0 } } };
  }
  var BET_NAME = { ante: 'Ante', play: 'Play', pp: 'Pair Plus' };
  function usd(x) { return '$' + x.toLocaleString('en-US'); }
  /* Why a bet can't go down (null = it can). spec: {type: 'ante' | 'pp' | 'play', amount} */
  Table.prototype.check = function (spec) {
    var R = this.g.rules, t = spec.type, a = spec.amount;
    if (!BET_NAME[t]) return 'There is no such bet at this table.';
    if (!(a > 0) || a !== Math.floor(a)) return 'Bets are in whole dollars.';
    if (t === 'play') {
      if (this.phase !== 'decide') return 'The Play bet goes down after the deal, once you have seen your cards.';
      if (!this.bets.ante) return 'Play goes beside an Ante, and there is no Ante on this hand.';
      if (this.bets.play) return 'You are already playing this hand.';
      if (a !== this.bets.ante) return 'The Play bet is exactly the Ante: ' + usd(this.bets.ante) + '.';
      if (a > this.bank) return 'Not enough in the rack to Play: it takes ' + usd(a) + '. You can still fold.';
      return null;
    }
    if (this.phase !== 'bet') return 'Bets are locked once the cards are out. Play or fold, and bet again on the next hand.';
    var have = this.bets[t];
    if (have + a < R.min) return 'The minimum on ' + BET_NAME[t] + ' is ' + usd(R.min) + '.';
    if (have + a > R.max) return 'The table maximum is ' + usd(R.max) + ' a bet.';
    if (a > this.bank) return 'Not enough in the rack.';
    return null;
  };
  Table.prototype.place = function (spec) {
    var why = this.check(spec); if (why) return { ok: false, reason: why };
    if (spec.type === 'play') return this.act('play');
    this.bets[spec.type] += spec.amount; this.bank -= spec.amount;
    return { ok: true };
  };
  /* Take a bet back before the deal. */
  Table.prototype.remove = function (type) {
    if (this.phase !== 'bet') return { ok: false, reason: 'Bets are locked once the cards are out.' };
    var a = this.bets[type]; if (!a) return { ok: false, reason: 'Nothing on ' + BET_NAME[type] + '.' };
    this.bets[type] = 0; this.bank += a;
    return { ok: true, amount: a };
  };
  Table.prototype.onFelt = function () { return this.bets.ante + this.bets.pp + this.bets.play; };
  /* Value of what's on the felt right now, in dollars. */
  Table.prototype.valueNow = function () {
    var g = this.g, b = this.bets;
    if (this.phase === 'bet') return -g.ante().edge * b.ante - g.pairPlus().edge * b.pp;
    return this.hand.V1;
  };
  /* Deal one hand from a fresh deck. cards (optional) = [p1, p2, p3, d1, d2, d3]. */
  Table.prototype.deal = function (cards) {
    if (this.phase !== 'bet') return { ok: false, reason: 'Finish this hand first: Play or fold.' };
    var b = this.bets; if (!b.ante && !b.pp) return { ok: false, reason: 'Put a bet down first: an Ante, a Pair Plus, or both.' };
    var g = this.g, c = cards || dealSix(this.rng), L = this.ledger;
    var player = c.slice(0, 3), dealer = c.slice(3, 6), d = g.decision(player);
    var eA = g.ante().edge, eP = g.pairPlus().edge;
    var ppNet = b.pp ? b.pp * d.ppPays : 0;
    var V0 = -eA * b.ante - eP * b.pp, V1 = (b.ante ? b.ante * Math.max(d.evPlay, -1) : 0) + ppNet;
    this.hand = { player: player, dealer: dealer, d: d, ante: b.ante, pp: b.pp, ppNet: ppNet, V0: V0, V1: V1, done: false };
    L.hands++; L.expected += V0; L.wagered += b.ante + b.pp;
    if (b.ante) { L.byKey.ante.bets++; L.byKey.ante.wagered += b.ante; L.byKey.ante.expected += -eA * b.ante; }
    if (b.pp) { L.byKey.pp.bets++; L.byKey.pp.wagered += b.pp; L.byKey.pp.expected += -eP * b.pp; }
    this.phase = 'decide';
    if (!b.ante) return { ok: true, hand: this.settle(null) };          // Pair Plus alone: no decision to make
    return { ok: true, hand: this.hand };
  };
  /* The decision: 'play' (put up the Play bet, equal to the Ante) or 'fold'. */
  Table.prototype.act = function (choice) {
    if (this.phase !== 'decide' || !this.hand) return { ok: false, reason: 'There is no hand to play. Bet, then deal.' };
    if (choice === 'play') {
      var why = this.check({ type: 'play', amount: this.bets.ante }); if (why) return { ok: false, reason: why };
      this.bets.play = this.bets.ante; this.bank -= this.bets.play;
      this.ledger.wagered += this.bets.play; this.ledger.byKey.ante.wagered += this.bets.play;
    } else if (choice !== 'fold') return { ok: false, reason: 'Play or fold.' };
    return { ok: true, hand: this.settle(choice) };
  };
  Table.prototype.canAffordPlay = function () { return this.phase === 'decide' && this.bets.ante > 0 && this.bank >= this.bets.ante; };
  Table.prototype.settle = function (choice) {
    var h = this.hand, d = h.d, L = this.ledger, b = this.bets, a = h.ante, ds = evaluate(h.dealer[0], h.dealer[1], h.dealer[2]);
    var lines = [], R = 0;
    h.dealerScore = ds; h.dealerName = describe(ds); h.qualifies = qualifies(ds); h.choice = choice;
    if (a) {
      var ev = choice === 'play' ? d.evPlay : -1;
      h.V2 = a * ev + h.ppNet;
      if (choice === 'fold') { lines.push({ bet: 'ante', net: -a, r: 'lose' }); h.outcome = 'fold'; }
      else {
        var anteNet, playNet;
        if (!h.qualifies) { anteNet = a; playNet = 0; h.outcome = 'nq'; }
        else if (d.score > ds) { anteNet = a; playNet = a; h.outcome = 'win'; }
        else if (d.score < ds) { anteNet = -a; playNet = -a; h.outcome = 'lose'; }
        else { anteNet = 0; playNet = 0; h.outcome = 'tie'; }
        lines.push({ bet: 'ante', net: anteNet, r: anteNet > 0 ? 'win' : anteNet < 0 ? 'lose' : 'push' });
        lines.push({ bet: 'play', net: playNet, r: playNet > 0 ? 'win' : playNet < 0 ? 'lose' : 'push' });
        if (d.bonus) lines.push({ bet: 'bonus', net: a * d.bonus, r: 'win' });
      }
      var anteR = lines.reduce(function (s, x) { return s + x.net; }, 0);
      L.byKey.ante.actual += anteR; R += anteR;
      L.decisions++;
      if (choice === 'play') L.plays++; else L.folds++;
      var cost = h.V1 - h.V2;
      if (cost > 1e-9) { L.mistakes++; if (choice === 'fold' && this.bank < a) { L.forced++; h.forced = true; } }
      if (choice === d.q64) L.q64Agree++;
      h.decisionCost = cost; L.decisionCost += cost;
    } else { h.V2 = h.V1; h.decisionCost = 0; h.outcome = 'pponly'; }
    if (h.pp) { lines.push({ bet: 'pp', net: h.ppNet, r: h.ppNet > 0 ? 'win' : 'lose' }); L.byKey.pp.actual += h.ppNet; R += h.ppNet; }
    h.lines = lines; h.net = R; h.dealLuck = h.V1 - h.V0; h.dealerLuck = R - h.V2;
    L.actual += R; L.dealLuck += h.dealLuck; L.dealerLuck += h.dealerLuck;
    this.bank += b.ante + b.pp + b.play + R;
    h.bets = { ante: b.ante, pp: b.pp, play: b.play };
    this.bets = { ante: 0, pp: 0, play: 0 }; this.phase = 'bet'; h.done = true;
    return h;
  };

  var API = { create: create, evaluate: evaluate, describe: describe, catOf: catOf, qualifies: qualifies, q64: q64, counts: counts, versus: versus,
              classes: classes, classFor: classFor, keyOf: keyOf, seeded: seeded, dealSix: dealSix, rank: rank, suit: suit, label: label,
              SUITS: SUITS, RANK_LABEL: RANK_LABEL, CAT_NAME: CAT_NAME, BONUS: BONUS, BONUS_LABEL: BONUS_LABEL, BONUS_KEYS: BONUS_KEYS,
              PAIRPLUS: PAIRPLUS, PAIRPLUS_KEYS: PAIRPLUS_KEYS, MAXES: MAXES, PACE: PACE, DEFAULT_RULES: DEFAULT_RULES,
              N_HANDS: N_HANDS, N_DEALER: N_DEALER, CAT: { SF: SF, TRIPS: TRIPS, STRAIGHT: STRAIGHT, FLUSH: FLUSH, PAIR: PAIR, HIGH: HIGH } };
  if (typeof module !== 'undefined' && module.exports) module.exports = API; else root.TcpEngine = API;
})(typeof window !== 'undefined' ? window : this);
