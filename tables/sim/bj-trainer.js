/* The Tilted Gent — blackjack trainer: basic strategy + card counting practice.
   Vanilla JS, no dependencies. Everything lives under window.BJT.
   Structure: RULES → SHOE → STRATEGY (generated from the rule set) → COUNT SYSTEMS (pluggable)
   → GAME (dealer, bots, the player's seat, timed dealing) → UI (mount). */
window.BJT = (function () {
  'use strict';

  /* ---------- counting systems (add more here: tags per rank, balanced or not, IRC) ---------- */
  var SYSTEMS = {
    hilo: { name: 'Hi-Lo', level: 1, balanced: true, irc: function () { return 0; },
            tags: { 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 0, 8: 0, 9: 0, 10: -1, 11: -1 },
            note: '2–6 count +1, 7–9 count 0, tens and aces count −1. Divide the running count by the decks remaining to get the true count.',
            indexPlays: true, betRamp: [[1, 1], [2, 2], [3, 4], [4, 8], [5, 12]] }
    // e.g. ko:  { name: 'KO (Knock-Out)', level: 1, balanced: false, irc: function(decks){ return 4 - 4*decks; }, tags: {2:1,3:1,4:1,5:1,6:1,7:1,8:0,9:0,10:-1,11:-1}, ... }
    // e.g. hiopt2, zen, omega2 — level-2 systems need a side count of aces for betting; leave a hook.
  };

  /* Illustrious 18 + Fab 4 for Hi-Lo (true-count thresholds). [player total or pair, dealer up, action if TC >= idx, else basic] */
  var INDEX = [
    { k: 'ins', idx: 3, label: 'Insurance at TC ≥ +3' },
    { k: 'h16v10', idx: 0, act: 'S', label: '16 v 10: stand at TC ≥ 0' },
    { k: 'h15v10', idx: 4, act: 'S', label: '15 v 10: stand at TC ≥ +4' },
    { k: 'p10v5', idx: 5, act: 'P', label: '10,10 v 5: split at TC ≥ +5' },
    { k: 'p10v6', idx: 4, act: 'P', label: '10,10 v 6: split at TC ≥ +4' },
    { k: 'h10v10', idx: 4, act: 'D', label: '10 v 10: double at TC ≥ +4' },
    { k: 'h12v3', idx: 2, act: 'S', label: '12 v 3: stand at TC ≥ +2' },
    { k: 'h12v2', idx: 3, act: 'S', label: '12 v 2: stand at TC ≥ +3' },
    { k: 'h11vA', idx: 1, act: 'D', label: '11 v A: double at TC ≥ +1' },
    { k: 'h9v2', idx: 1, act: 'D', label: '9 v 2: double at TC ≥ +1' },
    { k: 'h10vA', idx: 4, act: 'D', label: '10 v A: double at TC ≥ +4' },
    { k: 'h9v7', idx: 3, act: 'D', label: '9 v 7: double at TC ≥ +3' },
    { k: 'h16v9', idx: 5, act: 'S', label: '16 v 9: stand at TC ≥ +5' },
    { k: 'h13v2', idx: -1, act: 'S', neg: true, label: '13 v 2: hit below TC −1' },
    { k: 'h12v4', idx: 0, act: 'S', neg: true, label: '12 v 4: hit below TC 0' },
    { k: 'h12v5', idx: -2, act: 'S', neg: true, label: '12 v 5: hit below TC −2' },
    { k: 'h12v6', idx: -1, act: 'S', neg: true, label: '12 v 6: hit below TC −1' },
    { k: 'h13v3', idx: -2, act: 'S', neg: true, label: '13 v 3: hit below TC −2' },
    { k: 'r14v10', idx: 3, act: 'R', label: 'Surrender 14 v 10 at TC ≥ +3' },
    { k: 'r15v9', idx: 2, act: 'R', label: 'Surrender 15 v 9 at TC ≥ +2' },
    { k: 'r15vA', idx: 1, act: 'R', label: 'Surrender 15 v A at TC ≥ +1' },
    { k: 'r15v10', idx: 0, act: 'R', label: 'Surrender 15 v 10 at TC ≥ 0' }
  ];

  /* ---------- cards & shoe ---------- */
  var SUITS = ['♠', '♥', '♦', '♣'];
  function rng(seed) { var a = seed >>> 0; return function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function makeShoe(decks, rand) {
    var cards = [], d, s, r;
    for (d = 0; d < decks; d++) for (s = 0; s < 4; s++) for (r = 1; r <= 13; r++) {
      var v = r === 1 ? 11 : (r > 10 ? 10 : r);
      cards.push({ r: r, v: v, s: SUITS[s], label: r === 1 ? 'A' : (r === 11 ? 'J' : r === 12 ? 'Q' : r === 13 ? 'K' : String(r)) });
    }
    for (var i = cards.length - 1; i > 0; i--) { var j = Math.floor(rand() * (i + 1)); var t = cards[i]; cards[i] = cards[j]; cards[j] = t; }
    return cards;
  }

  /* ---------- hand maths ---------- */
  function total(cards) { var t = 0, aces = 0, i; for (i = 0; i < cards.length; i++) { t += cards[i].v; if (cards[i].v === 11) aces++; } while (t > 21 && aces > 0) { t -= 10; aces--; } return { t: t, soft: aces > 0 }; }
  function isBJ(cards) { return cards.length === 2 && total(cards).t === 21; }

  /* ---------- basic strategy, generated from rules ----------
     rules: { decks, h17, das, surrender, resplitAces }  actions: H S D P R (D = double else hit, Ds = double else stand) */
  function basicStrategy(rules) {
    var up, i, T = {};  // keys: 'h<total>', 's<total>', 'p<rank>' → array indexed by dealer up 2..11
    function row(fn) { var a = {}; for (up = 2; up <= 11; up++) a[up] = fn(up); return a; }
    var h17 = rules.h17, das = rules.das, sur = rules.surrender, multi = rules.decks >= 4;
    for (i = 5; i <= 8; i++) T['h' + i] = row(function () { return 'H'; });
    T.h9 = row(function (u) { return (u >= 3 && u <= 6) ? 'D' : 'H'; });
    T.h10 = row(function (u) { return u <= 9 ? 'D' : 'H'; });
    T.h11 = row(function (u) { return (u === 11 && !h17 && multi) ? 'H' : 'D'; });
    T.h12 = row(function (u) { return (u >= 4 && u <= 6) ? 'S' : 'H'; });
    for (i = 13; i <= 16; i++) T['h' + i] = row(function (u) { return u <= 6 ? 'S' : 'H'; });
    if (sur) {
      T.h16[9] = 'R'; T.h16[10] = 'R'; T.h16[11] = 'R'; T.h15[10] = 'R';
      if (h17) { T.h15[11] = 'R'; T.h17 = row(function (u) { return u === 11 ? 'R' : 'S'; }); }
    }
    for (i = 17; i <= 21; i++) if (!T['h' + i]) T['h' + i] = row(function () { return 'S'; });
    T.s13 = T.s14 = row(function (u) { return (u === 5 || u === 6) ? 'D' : 'H'; });
    T.s15 = T.s16 = row(function (u) { return (u >= 4 && u <= 6) ? 'D' : 'H'; });
    T.s17 = row(function (u) { return (u >= 3 && u <= 6) ? 'D' : 'H'; });
    T.s18 = row(function (u) { return u <= 6 ? 'Ds' : (u <= 8 ? 'S' : 'H'); });
    T.s19 = row(function (u) { return (h17 && u === 6) ? 'Ds' : 'S'; });
    T.s20 = T.s21 = row(function () { return 'S'; });
    T.pA = row(function () { return 'P'; });
    T.p10 = row(function () { return 'S'; });
    T.p9 = row(function (u) { return (u === 7 || u >= 10) ? 'S' : 'P'; });
    T.p8 = row(function (u) { return (sur && h17 && u === 11) ? 'R' : 'P'; });
    T.p7 = row(function (u) { return u <= 7 ? 'P' : 'H'; });
    T.p6 = row(function (u) { return (u <= 6 && (das || u >= 3)) ? 'P' : 'H'; });
    T.p5 = T.h10;
    T.p4 = row(function (u) { return (das && (u === 5 || u === 6)) ? 'P' : 'H'; });
    T.p3 = T.p2 = row(function (u) { return (u <= 7 && (das || u >= 4)) ? 'P' : 'H'; });
    return T;
  }
  function handKey(cards) {
    var tt = total(cards);
    if (cards.length === 2 && cards[0].v === cards[1].v) return 'p' + (cards[0].v === 11 ? 'A' : cards[0].v);
    if (tt.soft && tt.t <= 21) return 's' + tt.t;
    return 'h' + Math.min(tt.t, 21);
  }
  // Index-play lookup key for a hand: 'h16v10', 'p10v5', 'h11vA' (soft hands have no index plays here).
  function indexKey(cards, up) {
    var u = up === 11 ? 'A' : up;
    if (cards.length === 2 && cards[0].v === cards[1].v && cards[0].v !== 11) return 'p' + cards[0].v + 'v' + u;
    var tt = total(cards); if (tt.soft) return null;
    return 'h' + tt.t + 'v' + u;
  }
  var INDEX_BY_KEY = {}; (function () { for (var i = 0; i < INDEX.length; i++) INDEX_BY_KEY[INDEX[i].k] = INDEX[i]; })();
  // Resolve the recommended action for a hand given what's currently legal. Returns {act, why}.
  function advise(T, cards, up, legal, tc, useIndex) {
    var key = handKey(cards), act = T[key] ? T[key][up] : 'H', why = 'basic';
    if (key[0] === 'p' && !legal.split) { var tt = total(cards); key = (tt.soft ? 's' : 'h') + Math.min(tt.t, 21); act = T[key] ? T[key][up] : 'H'; }
    if (useIndex && typeof tc === 'number') {
      var ik = indexKey(cards, up), ix = ik && INDEX_BY_KEY[ik];
      if (ix && !ix.r) {
        if (ix.neg) { act = tc >= ix.idx ? 'S' : 'H'; why = 'index'; }
        else if (tc >= ix.idx && !(ix.act === 'R' && !legal.surrender) && !(ix.act === 'P' && !legal.split)) { act = ix.act; why = 'index'; }
      }
      if (ik && INDEX_BY_KEY['r' + ik.slice(1)] && legal.surrender && tc >= INDEX_BY_KEY['r' + ik.slice(1)].idx) { act = 'R'; why = 'index'; }
    }
    if (act === 'R' && !legal.surrender) act = (key === 'h17' || key === 'p8') ? (key === 'p8' ? 'P' : 'S') : 'H';
    if (act === 'D' && !legal.double) act = 'H';
    if (act === 'Ds' && !legal.double) act = 'S';
    if (act === 'Ds') act = 'D';
    if (act === 'P' && !legal.split) act = 'H';
    return { act: act, why: why };
  }


  /* ---------- expected-value engine (infinite-deck, composition-independent) ----------
     Prices every action for a hand state against a dealer up card under the rule set. Used to charge each
     deviation from the best play its actual EV cost (not "one error"), and to derive the base house edge.
     State = (hard total with aces counted as 1, has-ace flag); the effective total is hard+10 when that fits. */
  var EV_CACHE = {};
  function evEngine(rules) {
    var key = JSON.stringify(rules); if (EV_CACHE[key]) return EV_CACHE[key];
    var P = {}; for (var r = 2; r <= 9; r++) P[r] = 1 / 13; P[10] = 4 / 13; P[11] = 1 / 13;
    var h17 = !!rules.h17, das = !!rules.das, sur = !!rules.surrender;
    function eff(h, ace) { return (ace && h + 10 <= 21) ? h + 10 : h; }
    function isSoft(h, ace) { return ace && h + 10 <= 21; }
    function cv(c) { return c === 11 ? 1 : c; }
    // dealer final-total distribution from a state
    var dealerMemo = {};
    function dealerDist(h, ace) {
      var k = h + (ace ? 'a' : 'x'); if (dealerMemo[k]) return dealerMemo[k];
      var out = { 17: 0, 18: 0, 19: 0, 20: 0, 21: 0, bust: 0 };
      if (h > 21) { out.bust = 1; dealerMemo[k] = out; return out; }
      var t = eff(h, ace), soft = isSoft(h, ace);
      if (t > 17 || (t === 17 && !(soft && h17))) { out[t] = 1; dealerMemo[k] = out; return out; }
      for (var c = 2; c <= 11; c++) { var sub = dealerDist(h + cv(c), ace || c === 11); for (var q in out) out[q] += P[c] * sub[q]; }
      dealerMemo[k] = out; return out;
    }
    var DUP = {};
    for (var up = 2; up <= 11; up++) {
      var d = dealerDist(cv(up), up === 11), res = { 17: d[17], 18: d[18], 19: d[19], 20: d[20], 21: d[21], bust: d.bust };
      if (up === 11 || up === 10) { // the peek has happened: remove the natural and renormalise
        var pNat = up === 11 ? P[10] : P[11]; res[21] = Math.max(0, res[21] - pNat); var tot = 0; for (var q in res) tot += res[q]; for (var q2 in res) res[q2] /= tot;
      }
      DUP[up] = res;
    }
    function evStandT(t, up) { if (t > 21) return -1; var d = DUP[up], ev = d.bust; for (var f = 17; f <= 21; f++) { if (t > f) ev += d[f]; else if (t < f) ev -= d[f]; } return ev; }
    function evStand(h, ace, up) { return evStandT(eff(h, ace), up); }
    var hitMemo = {};
    function evHit(h, ace, up) { // take one card, then play on optimally (stand/hit only)
      var k = h + (ace ? 'a' : 'x') + 'v' + up; if (hitMemo[k] != null) return hitMemo[k];
      var ev = 0;
      for (var c = 2; c <= 11; c++) { var nh = h + cv(c), na = ace || c === 11;
        var v = nh > 21 ? -1 : (eff(nh, na) >= 21 ? evStand(nh, na, up) : Math.max(evStand(nh, na, up), evHit(nh, na, up))); ev += P[c] * v; }
      hitMemo[k] = ev; return ev;
    }
    function evDouble(h, ace, up) { var ev = 0; for (var c = 2; c <= 11; c++) { var nh = h + cv(c); ev += P[c] * 2 * (nh > 21 ? -1 : evStand(nh, ace || c === 11, up)); } return ev; }
    function evSplit(rank, up) { // one split; each hand takes one card then plays on (aces: one card only); DAS per rules
      var ev = 0, h0 = cv(rank), a0 = rank === 11;
      for (var c = 2; c <= 11; c++) { var h = h0 + cv(c), ace = a0 || c === 11, best;
        if (rank === 11) best = evStand(h, ace, up);
        else { best = Math.max(evStand(h, ace, up), evHit(h, ace, up)); if (das) best = Math.max(best, evDouble(h, ace, up)); }
        ev += P[c] * best; }
      return 2 * ev;
    }
    // t = effective total, soft = flag (as from total()); convert to state
    function toState(t, soft) { return soft ? [t - 10, true] : [t, false]; }
    function actions(t, soft, up, legal, pairRank) {
      var s = toState(t, soft), h = s[0], ace = s[1];
      var o = { S: evStand(h, ace, up), H: t >= 21 ? -1 : evHit(h, ace, up) };
      if (legal.double) o.D = evDouble(h, ace, up);
      if (legal.split && pairRank) o.P = evSplit(pairRank, up);
      if (legal.surrender) o.R = -0.5;
      return o;
    }
    // base edge: enumerate initial hands with best play, blackjack 3:2, dealer natural handled (no insurance)
    var base = 0;
    for (var a = 2; a <= 11; a++) for (var b = 2; b <= 11; b++) for (var u = 2; u <= 11; u++) {
      var pw = P[a] * P[b] * P[u], h = cv(a) + cv(b), ace = a === 11 || b === 11, t = eff(h, ace), soft = isSoft(h, ace);
      var pDealerNat = u === 11 ? P[10] : (u === 10 ? P[11] : 0), playerNat = t === 21, ev;
      if (playerNat) ev = (1 - pDealerNat) * 1.5;
      else { var o = actions(t, soft, u, { double: true, split: a === b, surrender: sur }, a === b ? a : 0), best = -9; for (var k in o) if (o[k] > best) best = o[k]; ev = -pDealerNat + (1 - pDealerNat) * best; }
      base += pw * ev;
    }
    var eng = { actions: actions, baseEdge: -base, rules: rules };
    EV_CACHE[key] = eng; return eng;
  }
  // EV of each legal action for an actual hand (cards) vs up card; returns {evs:{H,S,D,P,R}, best, bestEv, base}
  function evFor(rules, cards, up, legal) {
    var eng = evEngine(rules), tt = total(cards), pairRank = cards.length === 2 && cards[0].v === cards[1].v ? cards[0].v : 0;
    var evs = eng.actions(tt.t, tt.soft, up, legal, pairRank), best = null, bestEv = -9;
    for (var k in evs) if (evs[k] > bestEv) { bestEv = evs[k]; best = k; }
    return { evs: evs, best: best, bestEv: bestEv, base: eng.baseEdge };
  }

  /* ---------- game state machine ---------- */
  function Game(opts) {
    this.opts = opts; this.rand = rng(opts.seed || (Date.now() & 0xffffffff));
    this.system = SYSTEMS[opts.system || 'hilo'];
    this.T = basicStrategy(opts.rules);
    this.newShoe();
    this.stats = { hands: 0, correct: 0, decisions: 0, net: 0, countChecks: 0, countExact: 0, countOff: 0, wins: 0, losses: 0, pushes: 0 };
    this.log = [];
  }
  Game.prototype.newShoe = function () {
    this.shoe = makeShoe(this.opts.rules.decks, this.rand);
    this.cut = Math.floor(this.shoe.length * (1 - this.opts.rules.penetration));
    this.rc = this.system.irc(this.opts.rules.decks); this.dealt = 0; this.shoeNo = (this.shoeNo || 0) + 1; this.needShuffle = false;
  };
  Game.prototype.draw = function (hidden) {
    if (this.shoe.length === 0) this.newShoe();
    var c = this.shoe.pop(); this.dealt++;
    if (!hidden) this.rc += this.system.tags[c.v] || 0; else c.hidden = true;
    if (this.shoe.length <= this.cut) this.needShuffle = true;
    return c;
  };
  Game.prototype.reveal = function (c) { if (c.hidden) { c.hidden = false; this.rc += this.system.tags[c.v] || 0; } };
  Game.prototype.decksRemaining = function () { return Math.max(0.5, Math.round((this.shoe.length / 52) * 2) / 2); };
  Game.prototype.trueCount = function () { return this.rc / this.decksRemaining(); };
  Game.prototype.suggestedBet = function (unit) {
    var tc = Math.floor(this.trueCount()), ramp = this.system.betRamp, b = ramp[0][1], i;
    for (i = 0; i < ramp.length; i++) if (tc >= ramp[i][0]) b = ramp[i][1];
    return b * unit;
  };

  return { SYSTEMS: SYSTEMS, INDEX: INDEX, basicStrategy: basicStrategy, advise: advise, indexKey: indexKey, evEngine: evEngine, evFor: evFor, total: total, isBJ: isBJ, handKey: handKey, Game: Game, makeShoe: makeShoe, rng: rng };
})();
