/* The Tilted Gent — craps engine for the Craps Table. Vanilla JS, no dependencies; runs in the browser
   (window.CrapsEngine) and in Node (module.exports) for tables/tests/craps_engine_check.js.
   Every probability is exact: counted from the 36 dice combinations and carried as a fraction.
   A bet's value V (expected net result from now until it settles, per $1) is derived from the same
   step() that settles it at the table, so the edge shown and the money paid cannot disagree.
   Luck: V is a martingale under the dice, so on every roll
     luck = (net of bets that settled) + (V of bets still up) - (V of all bets before the roll)
   has mean exactly zero, and  actual result + value still on the felt = expected result + luck.
   Table rules sources: Wizard of Odds craps basics (working/off on the come-out, 3-4-5x lays 6x,
   commission conventions), fetched 25 Sep 2026. */
(function (root) {
  'use strict';

  /* ---------- exact fractions ---------- */
  function gcd(a, b) { a = Math.abs(a); b = Math.abs(b); while (b) { var t = a % b; a = b; b = t; } return a || 1; }
  function Q(n, d) { if (d === undefined) d = 1; if (d < 0) { n = -n; d = -d; } var g = gcd(n, d); return { n: n / g, d: d / g }; }
  function add(a, b) { return Q(a.n * b.d + b.n * a.d, a.d * b.d); }
  function sub(a, b) { return Q(a.n * b.d - b.n * a.d, a.d * b.d); }
  function mul(a, b) { return Q(a.n * b.n, a.d * b.d); }
  function div(a, b) { return Q(a.n * b.d, a.d * b.n); }
  function num(a) { return a.n / a.d; }
  function eq(a, b) { return a.n === b.n && a.d === b.d; }
  function fq(a) { return a.d === 1 ? String(a.n) : a.n + '/' + a.d; }
  function ratio(a, b) { var g = gcd(a, b); return (a / g) + ':' + (b / g); }       // "6:5"
  var ZERO = Q(0), ONE = Q(1);

  /* ---------- dice ---------- */
  var COMBOS = [];                                   // all 36 ordered rolls
  for (var i = 1; i <= 6; i++) for (var j = 1; j <= 6; j++) COMBOS.push({ d1: i, d2: j, t: i + j, hard: i === j });
  var P36 = Q(1, 36);
  function ways(t) { return 6 - Math.abs(7 - t); }   // 2..12
  var POINTS = [4, 5, 6, 8, 9, 10];

  /* ---------- paytables (net win per $1) ---------- */
  var TRUE = { 4: Q(2), 5: Q(3, 2), 6: Q(6, 5), 8: Q(6, 5), 9: Q(3, 2), 10: Q(2) };   // odds against n before 7
  var PLACE = { 4: Q(9, 5), 5: Q(7, 5), 6: Q(7, 6), 8: Q(7, 6), 9: Q(7, 5), 10: Q(9, 5) };
  var HARD = { 4: Q(7), 6: Q(9), 8: Q(9), 10: Q(7) };
  var PROPS = { any7: { wins: [7], pay: 4 }, anycraps: { wins: [2, 3, 12], pay: 7 },
                two: { wins: [2], pay: 30 }, three: { wins: [3], pay: 15 }, eleven: { wins: [11], pay: 15 }, twelve: { wins: [12], pay: 30 } };
  /* One-roll combination bets: the chips are split evenly across one-roll bets (units per part), each part
     is paid or lost on its own, and the bet settles for the sum. Net per $1 is derived from PROPS. */
  var MULTI = { horn: { two: 1, three: 1, eleven: 1, twelve: 1 }, world: { two: 1, three: 1, eleven: 1, twelve: 1, any7: 1 },
                ce: { anycraps: 1, eleven: 1 }, hilo: { two: 1, twelve: 1 } };
  function multiNet(parts, t) {
    var net = 0, units = 0;
    for (var p in parts) { units += parts[p]; net += PROPS[p].wins.indexOf(t) >= 0 ? PROPS[p].pay * parts[p] : -parts[p]; }
    return Q(net, units);
  }
  function multiUnits(parts) { var u = 0; for (var p in parts) u += parts[p]; return u; }
  var VIG = Q(1, 20);                                // 5% commission on buy and lay bets

  var DEFAULT_RULES = {
    odds: '345',                // '1' '2' '3' '4' '345' '5' '10'
    field12: 3,                 // Field pays 2:1 on the 2 and this on the 12 (2 or 3)
    buyVig: 'win',              // buy bets: 5% of the bet, charged only on a win ('win') or up front ('upfront')
    layVig: 'upfront',          // lay bets: 5% of the win, charged up front ('upfront') or only on a win ('win')
    placeOnComeOut: false,      // place and buy bets are off on the come-out unless called on
    hardOnComeOut: true,        // hardways work on the come-out (Las Vegas); false = Atlantic City
    comeOddsOnComeOut: false,   // odds behind come bets are off on the come-out (returned if the bet settles)
    min: 10                     // table minimum for line, come, field and big 6/8 bets
  };
  var ODDS_LIMITS = ['1', '2', '3', '4', '345', '5', '10'];
  var ODDS_LABEL = { '1': '1x', '2': '2x', '3': '3x', '4': '4x', '345': '3-4-5x', '5': '5x', '10': '10x' };

  function create(rulesIn) {
    var R = {}, k;
    for (k in DEFAULT_RULES) R[k] = DEFAULT_RULES[k];
    for (k in rulesIn || {}) R[k] = rulesIn[k];

    function W(x) { return { r: 'win', x: x }; }
    var LOSE = { r: 'lose', x: Q(-1) }, PUSH = { r: 'push', x: ZERO };
    function MOVE(n) { return { r: 'move', num: n }; }

    /* How bet b settles on a roll. null = no action. comeOut = the puck was off before this roll.
       Upfront commission is paid when the bet goes down (bet.vig), so it never appears here. */
    function step(b, c, comeOut) {
      var t = c.t, n = b.num;
      switch (b.type) {
        case 'pass': case 'come':
          if (n == null) { if (t === 7 || t === 11) return W(ONE); if (t === 2 || t === 3 || t === 12) return LOSE; return MOVE(t); }
          return t === n ? W(ONE) : t === 7 ? LOSE : null;
        case 'dontpass': case 'dontcome':
          if (n == null) { if (t === 2 || t === 3) return W(ONE); if (t === 12) return PUSH; if (t === 7 || t === 11) return LOSE; return MOVE(t); }
          return t === 7 ? W(ONE) : t === n ? LOSE : null;
        case 'odds':
          if (t !== n && t !== 7) return null;
          if (comeOut && b.come && !R.comeOddsOnComeOut) return PUSH;
          return t === n ? W(TRUE[n]) : LOSE;
        case 'layodds':
          if (t !== n && t !== 7) return null;
          return t === 7 ? W(div(ONE, TRUE[n])) : LOSE;
        case 'place': case 'buy':
          if (t !== n && t !== 7) return null;
          if (comeOut && !R.placeOnComeOut) return null;
          if (t === 7) return LOSE;
          return W(b.type === 'place' ? PLACE[n] : R.buyVig === 'win' ? sub(TRUE[n], VIG) : TRUE[n]);
        case 'lay':
          if (t !== n && t !== 7) return null;
          if (t === n) return LOSE;
          var win = div(ONE, TRUE[n]);
          return W(R.layVig === 'win' ? mul(win, Q(19, 20)) : win);
        case 'hard':
          if (comeOut && !R.hardOnComeOut) return null;
          if (t === n && c.hard) return W(HARD[n]);
          return t === 7 || t === n ? LOSE : null;
        case 'big':
          return t === n ? W(ONE) : t === 7 ? LOSE : null;
        case 'field':
          if (t === 2) return W(Q(2));
          if (t === 12) return W(Q(R.field12));
          return t === 3 || t === 4 || t === 9 || t === 10 || t === 11 ? W(ONE) : LOSE;
        default:
          var pr = PROPS[b.type];
          if (pr) return pr.wins.indexOf(t) >= 0 ? W(Q(pr.pay)) : LOSE;
          if (MULTI[b.type]) { var x = multiNet(MULTI[b.type], t); return x.n > 0 ? W(x) : x.n === 0 ? PUSH : { r: 'lose', x: x }; }
      }
      throw new Error('unknown bet ' + b.type);
    }

    /* V per $1 and expected rolls to settle, solved exactly from step() with every bet working:
       V = (sum over settling rolls of p*x + sum over moves of p*V') / (1 - P(no action)).
       A bet that is "off" does nothing on that roll, so being off never changes V. */
    var vMemo = {}, tMemo = {};
    function sig(b) { return b.type + '|' + (b.num == null ? '' : b.num); }
    function value(b) {
      var s = sig(b); if (vMemo[s]) return vMemo[s];
      var acc = ZERO, stay = ZERO;
      COMBOS.forEach(function (c) {
        var res = step(b, c, false);
        if (!res) stay = add(stay, P36);
        else if (res.r === 'move') acc = add(acc, mul(P36, value({ type: b.type, num: res.num })));
        else acc = add(acc, mul(P36, res.x));
      });
      return (vMemo[s] = div(acc, sub(ONE, stay)));
    }
    function rolls(b) {
      var s = sig(b); if (tMemo[s]) return tMemo[s];
      var acc = ONE, stay = ZERO;
      COMBOS.forEach(function (c) {
        var res = step(b, c, false);
        if (!res) stay = add(stay, P36);
        else if (res.r === 'move') acc = add(acc, mul(P36, rolls({ type: b.type, num: res.num })));
      });
      return (tMemo[s] = div(acc, sub(ONE, stay)));
    }
    /* Upfront commission per $1 of bet (0 when it is charged on the win instead). */
    function vigRate(type, n) {
      if (type === 'buy' && R.buyVig === 'upfront') return VIG;
      if (type === 'lay' && R.layVig === 'upfront') return mul(VIG, div(ONE, TRUE[n]));
      return ZERO;
    }
    /* House edge of a fresh bet: expected loss / money put up (bet + any upfront commission). */
    function edge(type, n) {
      var c = vigRate(type, n);
      return div(sub(c, value({ type: type, num: n })), add(ONE, c));
    }

    /* ---------- units, minimums and odds limits ---------- */
    var ODDS_UNIT = { 4: 1, 10: 1, 5: 2, 9: 2, 6: 5, 8: 5 };      // odds pay 2:1, 3:2, 6:5 in whole dollars
    var LAY_UNIT = { 4: 2, 10: 2, 5: 3, 9: 3, 6: 6, 8: 6 };       // lay odds pay 1:2, 2:3, 5:6
    function unit(type, n) {
      switch (type) {
        case 'place': return n === 6 || n === 8 ? 6 : 5;
        case 'odds': return ODDS_UNIT[n];
        case 'layodds': return LAY_UNIT[n];
        case 'buy': return 20;                                      // 5% of $20 = $1
        case 'horn': case 'world': case 'ce': case 'hilo': return multiUnits(MULTI[type]);   // whole dollars on every part
        case 'lay': return 20 * TRUE[n].n / TRUE[n].d;              // lay to win $20: 40 / 30 / 24
      }
      return 1;
    }
    function minBet(type, n) {
      var u = unit(type, n);
      if (type === 'pass' || type === 'dontpass' || type === 'come' || type === 'dontcome' || type === 'field' || type === 'big') return R.min;
      if (type === 'place') return Math.ceil(R.min / u) * u;
      return u;
    }
    function oddsMult(n) { return R.odds === '345' ? { 4: 3, 10: 3, 5: 4, 9: 4, 6: 5, 8: 5 }[n] : +R.odds; }
    /* Most odds allowed behind a flat bet of `flat` on point n. The don't side may lay enough to win
       what the pass odds would win: 3-4-5x lays 6x on every point (Wizard of Odds). */
    function maxOdds(type, n, flat) {
      var m = oddsMult(n) * flat;
      return type === 'odds' ? m : m * TRUE[n].n / TRUE[n].d;
    }
    /* Line bet + full odds: expected loss stays the line bet's; the money wagered grows. */
    function combo(side) {
      var line = side === 'pass' ? 'pass' : 'dontpass', odds = side === 'pass' ? 'odds' : 'layodds';
      var avg = ONE;
      POINTS.forEach(function (p) {
        var m = Q(oddsMult(p)); if (odds === 'layodds') m = mul(m, TRUE[p]);
        avg = add(avg, mul(Q(ways(p), 36), m));
      });
      return { lineEdge: edge(line), avgWager: avg, edge: div(edge(line), avg) };
    }

    /* ---------- the bet catalogue (fresh bets, as offered on the felt) ---------- */
    function band(e) { var x = num(e); return x < 0.02 ? 'up' : x < 0.05 ? 'au' : 'dn'; }
    var NAMES = { pass: 'Pass line', dontpass: 'Don’t pass', come: 'Come', dontcome: 'Don’t come',
                  odds: 'Odds on', layodds: 'Lay odds on', place: 'Place', buy: 'Buy', lay: 'Lay', hard: 'Hard',
                  big: 'Big', field: 'Field', any7: 'Any seven', anycraps: 'Any craps', two: 'Two (aces)',
                  three: 'Three (ace-deuce)', eleven: 'Eleven (yo)', twelve: 'Twelve (boxcars)',
                  horn: 'Horn', world: 'World (whirl)', ce: 'C & E', hilo: 'Hi-Lo' };
    function name(type, n) { return NAMES[type] + (n != null ? ' ' + n : ''); }
    function paysLabel(type, n) {
      switch (type) {
        case 'pass': case 'dontpass': case 'come': case 'dontcome': case 'big': return '1:1';
        case 'odds': return ratio(TRUE[n].n, TRUE[n].d);
        case 'layodds': return ratio(TRUE[n].d, TRUE[n].n);
        case 'place': return ratio(PLACE[n].n, PLACE[n].d);
        case 'buy': return ratio(TRUE[n].n, TRUE[n].d) + ' less 5%';
        case 'lay': return ratio(TRUE[n].d, TRUE[n].n) + ' less 5%';
        case 'hard': return HARD[n].n + ':1';
        case 'field': return '1:1; 2:1 on 2; ' + R.field12 + ':1 on 12';
        case 'horn': return 'split 4 ways: 2, 3, 11, 12';
        case 'world': return 'split 5 ways: horn + any 7';
        case 'ce': return 'split 2 ways: any craps + 11';
        case 'hilo': return 'split 2 ways: 2 + 12';
      }
      return PROPS[type].pay + ':1';
    }
    /* Odds against winning, among the rolls that settle the bet (single-roll-to-settle bets only). */
    function trueOdds(type, n) {
      if (type === 'pass' || type === 'dontpass' || type === 'come' || type === 'dontcome' || type === 'field' || MULTI[type]) return null;
      var w = 0, l = 0;
      COMBOS.forEach(function (c) { var r = step({ type: type, num: n }, c, false); if (r && r.r === 'win') w++; else if (r && r.r === 'lose') l++; });
      return ratio(l, w);
    }
    var catalogue = [];
    function entry(type, n) {
      var e = edge(type, n), t = rolls({ type: type, num: n == null ? null : n });
      catalogue.push({ key: type + (n != null ? n : ''), type: type, num: n == null ? null : n, name: name(type, n),
                       pays: paysLabel(type, n), trueOdds: trueOdds(type, n), edge: e, edgePct: 100 * num(e),
                       rolls: t, perRollPct: 100 * num(e) / num(t), band: band(e),
                       unit: unit(type, n), min: minBet(type, n) });
    }
    ['pass', 'dontpass', 'come', 'dontcome'].forEach(function (t) { entry(t); });
    POINTS.forEach(function (n) { entry('odds', n); });
    POINTS.forEach(function (n) { entry('layodds', n); });
    ['place', 'buy', 'lay'].forEach(function (t) { POINTS.forEach(function (n) { entry(t, n); }); });
    [4, 6, 8, 10].forEach(function (n) { entry('hard', n); });
    [6, 8].forEach(function (n) { entry('big', n); });
    ['field', 'any7', 'anycraps', 'two', 'three', 'eleven', 'twelve', 'horn', 'world', 'ce', 'hilo'].forEach(function (t) { entry(t); });
    var byKey = {}; catalogue.forEach(function (c) { byKey[c.key] = c; });

    return { rules: R, step: step, value: value, rolls: rolls, edge: edge, vigRate: vigRate, unit: unit, minBet: minBet,
             oddsMult: oddsMult, maxOdds: maxOdds, combo: combo, catalogue: catalogue, byKey: byKey, band: band, name: name,
             Table: function (opts) { return new Table(this, opts || {}); } };
  }

  /* ---------- the Odds panel: plain dice probabilities ---------- */
  function diceOdds() {
    var totals = [];
    for (var t = 2; t <= 12; t++) totals.push({ total: t, ways: ways(t), p: Q(ways(t), 36), against: ratio(36 - ways(t), ways(t)) });
    var before7 = POINTS.map(function (n) { return { num: n, p: Q(ways(n), ways(n) + 6), against: ratio(6, ways(n)) }; });
    var comeOut = { natural: Q(8, 36), craps: Q(4, 36), point: Q(24, 36) };
    return { totals: totals, before7: before7, comeOut: comeOut };
  }

  /* ---------- random dice ---------- */
  function seeded(seed) {                            // mulberry32, as in ttg-sim.js
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

  /* ---------- a table: bankroll, bets on the felt, rolls, and the ledger ---------- */
  var LINE = { pass: 1, dontpass: 1, come: 1, dontcome: 1 };
  var NUMBERED = { odds: 1, layodds: 1, place: 1, buy: 1, lay: 1, hard: 1, big: 1 };
  function Table(g, opts) {
    this.g = g; this.rng = opts.rng || (opts.seed ? seeded(opts.seed) : cryptoRng());
    this.point = null; this.bets = []; this.nextId = 1;
    this.bank = opts.bankroll == null ? 1000 : opts.bankroll;
    this.ledger = { rolls: 0, comeOutRolls: 0, actual: 0, expected: 0, luckComeOut: 0, luckPoint: 0, vig: 0, wagered: 0, byKey: {} };
  }
  /* Where a bet's money is tallied in the recap: odds of every point together, everything else by bet. */
  function recapKey(b) { return b.type === 'odds' || b.type === 'layodds' ? b.type : b.type + (NUMBERED[b.type] && b.num != null ? b.num : ''); }
  Table.prototype.v = function (b) { return num(this.g.value(b)) * b.amount; };
  Table.prototype.get = function (id) { for (var i = 0; i < this.bets.length; i++) if (this.bets[i].id === id) return this.bets[i]; return null; };
  Table.prototype.tally = function (b) {
    var k = recapKey(b), L = this.ledger.byKey;
    return L[k] || (L[k] = { key: k, type: b.type, num: NUMBERED[b.type] && b.type !== 'odds' && b.type !== 'layodds' ? b.num : null,
                             bets: 0, wagered: 0, expected: 0, actual: 0 });
  };
  /* Why a bet can't go down (null = it can). spec: {type, num, parent, amount} */
  Table.prototype.check = function (spec) {
    var g = this.g, t = spec.type, n = spec.num, a = spec.amount, cur = this.find(spec), have = cur ? cur.amount : 0;
    if (!(a > 0) || a !== Math.floor(a)) return 'Bets are in whole dollars.';
    if ((t === 'pass' || t === 'dontpass') && this.point != null) return 'Line bets go down on the come-out roll, before a point is set.';
    if ((t === 'come' || t === 'dontcome') && this.point == null) return 'Come bets go down once a point is set; on the come-out, use the line.';
    var nt = n;
    if (t === 'odds' || t === 'layodds') {
      var p = spec.parent != null ? this.get(spec.parent) : null;
      if (!p || p.num == null) return 'Odds go behind a line or come bet that already has a point.';
      if ((t === 'odds') !== (p.type === 'pass' || p.type === 'come')) return t === 'odds' ? 'Take odds behind pass or come; lay odds behind don’t.' : 'Lay odds go behind don’t pass or don’t come.';
      nt = p.num;
      var mx = g.maxOdds(t, nt, p.amount);
      if (have + a > mx) return 'At ' + ODDS_LABEL[g.rules.odds] + ' the most you can ' + (t === 'odds' ? 'take' : 'lay') + ' behind $' + p.amount + ' on the ' + nt + ' is $' + mx + '.';
    } else if (NUMBERED[t] && (n == null || !g.byKey[t + n])) return 'Pick a number for that bet.';
    var u = g.unit(t, nt), mn = g.minBet(t, nt);
    if ((have + a) % u) return name(g, t, nt) + ' goes down in multiples of $' + u + ' so it pays in whole dollars.';
    if (have + a < mn) return 'The minimum for ' + name(g, t, nt) + ' is $' + mn + '.';
    var vig = num(g.vigRate(t, nt)) * a;
    if (a + vig > this.bank) return 'Not enough in the rack.';
    return null;
  };
  function name(g, t, n) { return g.name(t, n); }
  /* The bet a new chip joins: one bet per spot (one come bet waiting in the Come box). */
  Table.prototype.find = function (spec) {
    for (var i = 0; i < this.bets.length; i++) {
      var b = this.bets[i];
      if (b.type !== spec.type) continue;
      if (b.type === 'odds' || b.type === 'layodds') { if (b.parent === spec.parent) return b; continue; }
      if (LINE[b.type]) { if (b.num == null) return b; continue; }
      if (b.num === (spec.num == null ? null : spec.num)) return b;
    }
    return null;
  };
  Table.prototype.place = function (spec) {
    var why = this.check(spec); if (why) return { ok: false, reason: why };
    var g = this.g, t = spec.type, a = spec.amount, b = this.find(spec), p = spec.parent != null ? this.get(spec.parent) : null;
    var n = p ? p.num : (spec.num == null ? null : spec.num);
    var vig = Math.round(num(g.vigRate(t, n)) * a * 100) / 100;
    if (!b) { b = { id: this.nextId++, type: t, num: n, amount: 0, vig: 0 }; if (p) { b.parent = p.id; b.come = p.type === 'come' || p.type === 'dontcome'; } this.bets.push(b); }
    var ev = num(g.value({ type: t, num: n })) * a - vig;
    b.amount += a; b.vig += vig; this.bank -= a + vig;
    var L = this.ledger, T = this.tally(b);
    L.expected += ev; L.actual -= vig; L.vig += vig; L.wagered += a + vig;
    T.bets++; T.wagered += a + vig; T.expected += ev; T.actual -= vig;
    return { ok: true, bet: b };
  };
  /* Contract bets (pass and come once they have a point) stay up until they settle. */
  Table.prototype.removable = function (b) {
    if ((b.type === 'pass' || b.type === 'come') && b.num != null) return false;
    return true;
  };
  Table.prototype.remove = function (id) {
    var b = this.get(id); if (!b || !this.removable(b)) return { ok: false, reason: 'Pass and come bets with a point are contract bets: they stay until they win or lose.' };
    var self = this, out = [b];
    this.bets.forEach(function (x) { if (x.parent === id) out.push(x); });   // taking down a don't takes its lay odds too
    out.forEach(function (x) {
      var v = self.v(x);                              // walking away from a bet gives up its value; that is a choice, not luck
      self.ledger.expected -= v; self.tally(x).expected -= v;
      self.bank += x.amount;
      self.bets.splice(self.bets.indexOf(x), 1);
    });
    return { ok: true, removed: out };
  };
  Table.prototype.roll = function (d1, d2) {
    if (d1 == null) { d1 = 1 + Math.floor(this.rng() * 6); d2 = 1 + Math.floor(this.rng() * 6); }
    var g = this.g, c = { d1: d1, d2: d2, t: d1 + d2, hard: d1 === d2 }, comeOut = this.point == null;
    var L = this.ledger, luck = 0, events = [], keep = [], self = this;
    this.bets.forEach(function (b) {
      var res = g.step(b, c, comeOut), before = self.v(b);
      if (!res) { keep.push(b); return; }
      var T = self.tally(b);
      if (res.r === 'move') {
        b.num = res.num; luck += self.v(b) - before; keep.push(b);
        events.push({ bet: b, r: 'move', num: res.num, amount: b.amount });
        return;
      }
      var net = Math.round(num(res.x) * b.amount * 100) / 100;
      self.bank += b.amount + net; L.actual += net; T.actual += net; luck += net - before;
      events.push({ bet: b, r: res.r, net: net, amount: b.amount });
    });
    this.bets = keep;
    /* A come bet that travels to a number joins any come bet already there. */
    for (var i = 0; i < this.bets.length; i++) for (var j = i + 1; j < this.bets.length; j++) {
      var a = this.bets[i], b = this.bets[j];
      if (a.type === b.type && LINE[a.type] && a.type !== 'pass' && a.type !== 'dontpass' && a.num != null && a.num === b.num) {
        a.amount += b.amount; this.bets.forEach(function (x) { if (x.parent === b.id) x.parent = a.id; });
        this.bets.splice(j, 1); j--;
      }
    }
    var before = this.point;
    if (comeOut) { if (POINTS.indexOf(c.t) >= 0) this.point = c.t; }
    else if (c.t === this.point || c.t === 7) this.point = null;
    L.rolls++; if (comeOut) { L.comeOutRolls++; L.luckComeOut += luck; } else L.luckPoint += luck;
    return { d1: d1, d2: d2, total: c.t, hard: c.hard, comeOut: comeOut, pointBefore: before, pointAfter: this.point, events: events, luck: luck };
  };
  /* Value of everything still on the felt: actual + open = expected + luck, always. */
  Table.prototype.openValue = function () { var s = 0, self = this; this.bets.forEach(function (b) { s += self.v(b); }); return s; };
  Table.prototype.onFelt = function () { var s = 0; this.bets.forEach(function (b) { s += b.amount; }); return s; };

  var API = { create: create, diceOdds: diceOdds, seeded: seeded, ways: ways, POINTS: POINTS, COMBOS: COMBOS,
              DEFAULT_RULES: DEFAULT_RULES, ODDS_LIMITS: ODDS_LIMITS, ODDS_LABEL: ODDS_LABEL,
              Q: Q, add: add, sub: sub, mul: mul, div: div, num: num, eq: eq, fq: fq, ratio: ratio };
  if (typeof module !== 'undefined' && module.exports) module.exports = API; else root.CrapsEngine = API;
})(typeof window !== 'undefined' ? window : this);
