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

  return { SYSTEMS: SYSTEMS, INDEX: INDEX, basicStrategy: basicStrategy, advise: advise, indexKey: indexKey, total: total, isBJ: isBJ, handKey: handKey, Game: Game, makeShoe: makeShoe, rng: rng };
})();
