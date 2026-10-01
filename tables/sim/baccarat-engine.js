/* The Tilted Gent — baccarat engine for the Baccarat Table. Vanilla JS, no dependencies; runs in the browser
   (window.BaccaratEngine) and in Node (module.exports) for tables/checks/baccarat_engine_check.js.

   Rules (punto banco, the standard tableau):
     Card values: A = 1, 2-9 at face, 10/J/Q/K = 0; a hand's total is the last digit of its sum.
     Deal order P, B, P, B. A two-card 8 or 9 on either side is a natural: both hands stand.
     Player draws on 0-5 and stands on 6-7.
     If Player stood, Banker draws on 0-5 and stands on 6-7.
     If Player drew, Banker acts on its total and the value of Player's third card (p3):
       0-2 draws · 3 draws unless p3 = 8 · 4 draws on p3 2-7 · 5 draws on p3 4-7 · 6 draws on p3 6-7 · 7 stands.
   Bets: Player 1:1 · Banker 1:1 less 5% commission (taken from the win) · Player and Banker push on a tie ·
   Tie 8:1 (or 9:1) · Player Pair / Banker Pair 11:1 (that hand's first two cards are the same rank).

   Every probability is counted, not simulated: enumerate() walks every ordered deal from a full shoe
   (up to six cards drawn without replacement from 52 x decks), weighting each finished hand by the number of
   ordered six-card sequences that begin with it, so every weight is an integer and they sum to
   D = N(N-1)(N-2)(N-3)(N-4)(N-5) exactly (N = 416: D = 4.998e15 < 2^53, so double arithmetic is exact).
   Edges are then exact fractions (BigInt):
     Banker  = P(player) - 0.95 P(banker)   = (20 W_P - 19 W_B) / 20D
     Player  = P(banker) - P(player)        = (W_B - W_P) / D
     Tie k:1 = 1 - (k+1) P(tie)             = (D - (k+1) W_T) / D
     Pair    = 1 - 12 P(pair), P(pair) = (4d - 1)/(52d - 1)  (second card matches the first card's rank)
   Published figures these must match (tables/sim/games.js, tables/baccarat.html; Wizard of Odds, 8 decks):
     P(banker) 0.458597, P(player) 0.446247, P(tie) 0.095156; edges Banker 1.06%, Player 1.24%,
     Tie 8:1 14.36%, Tie 9:1 4.84%, pair 10.36%.
   Values: a bet's value before the deal is -edge x amount, for a fresh shoe (the cards already dealt
   shift it by a few hundredths of a percent; the table does not count the shoe). */
(function (root) {
  'use strict';

  /* ---------- cards ---------- */
  var RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];
  var SUITS = ['♠', '♥', '♦', '♣'];
  function rankValue(r) { return r < 9 ? r + 1 : 0; }           // rank index 0..12 -> baccarat value
  function total(cards) { var s = 0; for (var i = 0; i < cards.length; i++) s += cards[i].v; return s % 10; }

  /* ---------- the tableau (one copy, used by the table and by the enumeration) ---------- */
  function playerDraws(pt) { return pt <= 5; }
  function bankerDraws(bt, p3) {                 // p3 = value of Player's third card, or null if Player stood
    if (p3 == null) return bt <= 5;
    switch (bt) {
      case 0: case 1: case 2: return true;
      case 3: return p3 !== 8;
      case 4: return p3 >= 2 && p3 <= 7;
      case 5: return p3 >= 4 && p3 <= 7;
      case 6: return p3 === 6 || p3 === 7;
      default: return false;                     // 7 stands (8 and 9 are naturals, settled before this)
    }
  }
  /* Plays one hand from draw() (returns the next card {r, s, v}). */
  function play(draw) {
    var P = [draw()], B = [draw()];
    P.push(draw()); B.push(draw());
    var p2 = total(P), b2 = total(B), natural = p2 >= 8 || b2 >= 8, p3 = null, pDrew = false, bDrew = false;
    if (!natural) {
      if (playerDraws(p2)) { P.push(draw()); p3 = P[2].v; pDrew = true; }
      if (bankerDraws(b2, p3)) { B.push(draw()); bDrew = true; }
    }
    var pt = total(P), bt = total(B);
    return { player: P, banker: B, p2: p2, b2: b2, pt: pt, bt: bt, natural: natural, p3: p3, pDrew: pDrew, bDrew: bDrew,
             winner: pt > bt ? 'player' : bt > pt ? 'banker' : 'tie',
             playerPair: P[0].r === P[1].r, bankerPair: B[0].r === B[1].r };
  }

  /* ---------- exact enumeration of the tableau ---------- */
  var enumMemo = {};
  function enumerate(decks) {
    if (enumMemo[decks]) return enumMemo[decks];
    var N = 52 * decks, c = [16 * decks];                 // value 0: 10, J, Q, K
    for (var v = 1; v <= 9; v++) c.push(4 * decks);
    var tail = [];                                          // tail[k] = (N-k)(N-k-1)...(N-5): ways to fill the unused positions
    for (var k = 0; k <= 6; k++) { var t = 1; for (var i = k; i <= 5; i++) t *= (N - i); tail[k] = t; }
    var D = tail[0];
    var W = { banker: 0, player: 0, tie: 0, natural: 0, pDraw: 0, bDraw: 0 };
    function tally(pt, bt, w) { if (pt > bt) W.player += w; else if (bt > pt) W.banker += w; else W.tie += w; }
    for (var p1 = 0; p1 < 10; p1++) { var w1 = c[p1]; c[p1]--;
      for (var b1 = 0; b1 < 10; b1++) { var w2 = w1 * c[b1]; c[b1]--;
        for (var p2 = 0; p2 < 10; p2++) { var w3 = w2 * c[p2]; c[p2]--;
          for (var b2 = 0; b2 < 10; b2++) { var w4 = w3 * c[b2]; if (!w4) continue; c[b2]--;
            var pt = (p1 + p2) % 10, bt = (b1 + b2) % 10;
            if (pt >= 8 || bt >= 8) { W.natural += w4 * tail[4]; tally(pt, bt, w4 * tail[4]); }
            else if (!playerDraws(pt)) {
              if (bankerDraws(bt, null)) {
                W.bDraw += w4 * tail[4];
                for (var x = 0; x < 10; x++) { var w5 = w4 * c[x]; if (w5) tally(pt, (bt + x) % 10, w5 * tail[5]); }
              } else tally(pt, bt, w4 * tail[4]);
            } else {
              W.pDraw += w4 * tail[4];
              for (var p3 = 0; p3 < 10; p3++) { var w5p = w4 * c[p3]; if (!w5p) continue; c[p3]--;
                var pt3 = (pt + p3) % 10;
                if (bankerDraws(bt, p3)) {
                  W.bDraw += w5p * tail[5];
                  for (var b3 = 0; b3 < 10; b3++) { var w6 = w5p * c[b3]; if (w6) tally(pt3, (bt + b3) % 10, w6); }
                } else tally(pt3, bt, w5p * tail[5]);
                c[p3]++;
              }
            }
            c[b2]++;
          }
          c[p2]++;
        }
        c[b1]++;
      }
      c[p1]++;
    }
    var R = { decks: decks, N: N, D: D, W: W,
              p: { banker: W.banker / D, player: W.player / D, tie: W.tie / D, natural: W.natural / D, pDraw: W.pDraw / D, bDraw: W.bDraw / D },
              pair: { n: 4 * decks - 1, d: N - 1 } };
    R.p.pair = R.pair.n / R.pair.d;
    return (enumMemo[decks] = R);
  }

  /* ---------- exact fractions (BigInt) ---------- */
  function big(x) { return BigInt(x); }
  function bgcd(a, b) { if (a < 0) a = -a; if (b < 0) b = -b; while (b) { var t = a % b; a = b; b = t; } return a; }
  function F(n, d) { n = big(n); d = big(d); var g = bgcd(n, d) || big(1); return { n: n / g, d: d / g }; }
  function fnum(f) {                              // to a double, keeping precision for big numerators
    var s = big(1000000000000000), q = f.n * s / f.d;
    return Number(q) / 1e15;
  }
  function fq(f) { return f.d === big(1) ? String(f.n) : f.n + '/' + f.d; }

  /* ---------- rules and the bet catalogue ---------- */
  var DEFAULT_RULES = { decks: 8, tiePays: 8, min: 10, max: 1000, cut: 14, burn: 1, commission: 5 };
  var TIE_PAYS = [8, 9], MAXES = [500, 1000, 2000, 5000];
  /* Pace, as in tables/sim/games.js G.baccarat (pace 70; paceNote: mini-bacc runs 120-150). */
  var PACE = { big: 70, mini: [120, 150] };
  var TYPES = ['player', 'banker', 'tie', 'ppair', 'bpair'];
  var NAMES = { player: 'Player', banker: 'Banker', tie: 'Tie', ppair: 'Player Pair', bpair: 'Banker Pair' };

  function create(rulesIn) {
    var R = {}, k;
    for (k in DEFAULT_RULES) R[k] = DEFAULT_RULES[k];
    for (k in rulesIn || {}) R[k] = rulesIn[k];
    R.tiePays = +R.tiePays; R.max = +R.max; R.min = +R.min;
    var E = enumerate(R.decks), D = E.D, W = E.W;
    var c20 = 100 / R.commission;                 // 5% -> 20: Banker wins pay (20-1)/20
    var edges = {
      banker: F(big(c20) * big(W.player) - big(c20 - 1) * big(W.banker), big(c20) * big(D)),
      player: F(big(W.banker) - big(W.player), big(D)),
      tie: F(big(D) - big(R.tiePays + 1) * big(W.tie), big(D)),
      ppair: F(E.pair.d - 12 * E.pair.n, E.pair.d),
      bpair: F(E.pair.d - 12 * E.pair.n, E.pair.d)
    };
    /* Net result per $1 for each bet on each outcome. Banker's win is paid less the commission. */
    function net(type, hand) {
      var w = hand.winner;
      switch (type) {
        case 'player': return w === 'player' ? 1 : w === 'banker' ? -1 : 0;
        case 'banker': return w === 'banker' ? 1 - R.commission / 100 : w === 'player' ? -1 : 0;
        case 'tie': return w === 'tie' ? R.tiePays : -1;
        case 'ppair': return hand.playerPair ? 11 : -1;
        case 'bpair': return hand.bankerPair ? 11 : -1;
      }
      throw new Error('unknown bet ' + type);
    }
    function payout(type, amount, hand) {        // dollars, to the cent
      return Math.round(net(type, hand) * amount * 100) / 100;
    }
    function band(e) { var x = fnum(e); return x < 0.02 ? 'up' : x < 0.05 ? 'au' : 'dn'; }
    function ratio(a, b) { return (Math.round(a / b * 100) / 100) + ':1'; }
    var p = E.p;
    var info = {
      player: { pays: '1:1', win: p.player, push: p.tie, lose: p.banker, trueOdds: null, noTie: p.player / (p.player + p.banker) },
      banker: { pays: '1:1 less ' + R.commission + '%', win: p.banker, push: p.tie, lose: p.player, trueOdds: null, noTie: p.banker / (p.player + p.banker) },
      tie: { pays: R.tiePays + ':1', win: p.tie, push: 0, lose: 1 - p.tie, trueOdds: ratio(1 - p.tie, p.tie) },
      ppair: { pays: '11:1', win: p.pair, push: 0, lose: 1 - p.pair, trueOdds: ratio(1 - p.pair, p.pair), exact: true },
      bpair: { pays: '11:1', win: p.pair, push: 0, lose: 1 - p.pair, trueOdds: ratio(1 - p.pair, p.pair), exact: true }
    };
    var catalogue = TYPES.map(function (t) {
      var e = edges[t], I = info[t];
      return { key: t, type: t, name: NAMES[t], pays: I.pays, edge: e, edgePct: 100 * fnum(e), band: band(e), exactSmall: !!I.exact,
               pWin: I.win, pPush: I.push, pLose: I.lose, trueOdds: I.trueOdds, noTie: I.noTie == null ? null : I.noTie, min: R.min, max: R.max };
    });
    var byKey = {}; catalogue.forEach(function (c) { byKey[c.key] = c; });
    /* Value of a bet before the deal, fresh shoe: -edge x amount. */
    function value(type, amount) { return -fnum(edges[type]) * amount; }
    return { rules: R, enumeration: E, edges: edges, net: net, payout: payout, value: value, catalogue: catalogue, byKey: byKey,
             band: band, name: function (t) { return NAMES[t]; },
             Table: function (opts) { return new Table(this, opts || {}); } };
  }

  /* ---------- random numbers ---------- */
  function seeded(seed) {                            // mulberry32, as in ttg-sim.js and craps-engine.js
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

  /* ---------- a table: the shoe, the bets, the hands and the ledger ---------- */
  /* The rack is kept to the cent: Banker pays 95%, and float sums of cents drift otherwise. */
  function cents(x) { return Math.round(x * 100) / 100; }
  /* phase 'bets': bets may go down or come off. deal() draws the hand and locks the bets ('dealt');
     settle() pays them and opens betting again. Nothing can be booked between deal() and settle(). */
  function Table(g, opts) {
    this.g = g; this.rng = opts.rng || (opts.seed ? seeded(opts.seed) : cryptoRng());
    this.bank = cents(opts.bankroll == null ? 1000 : opts.bankroll);
    this.bets = {}; this.phase = 'bets'; this.hand = null; this.shoeNo = 0; this.cards = []; this.pos = 0; this.burned = [];
    this.ledger = { hands: 0, wagered: 0, expected: 0, actual: 0, wins: { banker: 0, player: 0, tie: 0 }, pairs: { player: 0, banker: 0 }, byKey: {} };
    this.shuffle();
  }
  Table.prototype.shuffle = function () {
    var R = this.g.rules, a = [];
    for (var d = 0; d < R.decks; d++) for (var s = 0; s < 4; s++) for (var r = 0; r < 13; r++) a.push({ r: r, s: s, v: rankValue(r), rank: RANKS[r], suit: SUITS[s] });
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(this.rng() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; }   // Fisher-Yates
    this.cards = a; this.pos = 0; this.shoeNo++;
    this.burned = a.slice(0, R.burn); this.pos = R.burn;                     // burn card(s) off the top
  };
  Table.prototype.cardsLeft = function () { return this.cards.length - this.pos; };
  /* The cut card sits `cut` cards from the end; once it is out, the shoe is shuffled before the next hand. */
  Table.prototype.cutOut = function () { return this.cardsLeft() <= this.g.rules.cut; };
  Table.prototype.onFelt = function () { var s = 0; for (var t in this.bets) s += this.bets[t]; return s; };
  Table.prototype.value = function () { var s = 0; for (var t in this.bets) s += this.g.value(t, this.bets[t]); return s; };
  /* Why a chip can't go down (null = it can). */
  Table.prototype.check = function (type, amount) {
    var g = this.g, R = g.rules;
    if (this.phase !== 'bets') return 'No more bets: the cards are out. Bets go down between hands.';
    if (TYPES.indexOf(type) < 0) return 'There is no such bet on this table.';
    if (typeof amount !== 'number' || !isFinite(amount)) return 'Bets are in whole dollars.';
    if (amount <= 0) return 'A bet has to be a positive amount.';
    if (amount !== Math.floor(amount)) return 'Bets are in whole dollars.';
    var have = this.bets[type] || 0;
    if (have + amount < R.min) return 'The minimum on ' + NAMES[type] + ' is $' + R.min + '.';
    if (have + amount > R.max) return 'The most ' + NAMES[type] + ' can hold is $' + R.max.toLocaleString('en-US') + ' (the table maximum).';
    if (amount > this.bank) return 'Not enough in the rack.';
    return null;
  };
  Table.prototype.place = function (type, amount) {
    var why = this.check(type, amount); if (why) return { ok: false, reason: why };
    this.bets[type] = (this.bets[type] || 0) + amount; this.bank = cents(this.bank - amount);
    return { ok: true, amount: this.bets[type] };
  };
  Table.prototype.remove = function (type) {
    if (this.phase !== 'bets') return { ok: false, reason: 'The cards are out: bets stay until the hand is paid.' };
    var a = this.bets[type]; if (!a) return { ok: false, reason: 'Nothing on ' + (NAMES[type] || 'that spot') + '.' };
    delete this.bets[type]; this.bank = cents(this.bank + a);
    return { ok: true, amount: a };
  };
  Table.prototype.tally = function (type) {
    var L = this.ledger.byKey;
    return L[type] || (L[type] = { key: type, bets: 0, wagered: 0, expected: 0, actual: 0, won: 0, lost: 0, pushed: 0 });
  };
  /* Locks the bets, books what they are worth, and deals. `cards` (optional) forces the next cards, for tests. */
  Table.prototype.deal = function (cards) {
    if (this.phase !== 'bets') return { ok: false, reason: 'The hand is already dealt.' };
    var shuffled = false;
    if (!cards && this.cutOut()) { this.shuffle(); shuffled = true; }
    var self = this, q = cards ? cards.slice() : null;
    var hand = play(function () { return q ? q.shift() : self.cards[self.pos++]; });
    var L = this.ledger, expected = 0;
    for (var t in this.bets) {
      var a = this.bets[t], ev = this.g.value(t, a), T = this.tally(t);
      T.bets++; T.wagered += a; T.expected += ev; L.wagered += a; L.expected += ev; expected += ev;
    }
    L.hands++; L.wins[hand.winner]++; if (hand.playerPair) L.pairs.player++; if (hand.bankerPair) L.pairs.banker++;
    hand.shuffled = shuffled; hand.expected = expected; hand.bets = Object.assign({}, this.bets);
    this.hand = hand; this.phase = 'dealt';
    return { ok: true, hand: hand };
  };
  /* Pays the hand. Returns each bet's result, the hand's net, its expected value and the luck (net - expected). */
  Table.prototype.settle = function () {
    if (this.phase !== 'dealt') return { ok: false, reason: 'No hand to settle.' };
    var g = this.g, h = this.hand, L = this.ledger, events = [], net = 0;
    for (var t in this.bets) {
      var a = this.bets[t], x = g.payout(t, a, h), T = this.tally(t);
      this.bank = cents(this.bank + a + x); L.actual += x; T.actual += x; net += x;
      if (x > 0) T.won++; else if (x < 0) T.lost++; else T.pushed++;
      events.push({ type: t, amount: a, net: x, r: x > 0 ? 'win' : x < 0 ? 'lose' : 'push' });
    }
    this.bets = {}; this.phase = 'bets';
    return { ok: true, events: events, net: net, expected: h.expected, luck: net - h.expected };
  };

  var API = { create: create, enumerate: enumerate, play: play, total: total, playerDraws: playerDraws, bankerDraws: bankerDraws,
              rankValue: rankValue, RANKS: RANKS, SUITS: SUITS, TYPES: TYPES, NAMES: NAMES, DEFAULT_RULES: DEFAULT_RULES,
              TIE_PAYS: TIE_PAYS, MAXES: MAXES, PACE: PACE, seeded: seeded, cryptoRng: cryptoRng, F: F, fnum: fnum, fq: fq };
  if (typeof module !== 'undefined' && module.exports) module.exports = API; else root.BaccaratEngine = API;
})(typeof window !== 'undefined' ? window : this);
