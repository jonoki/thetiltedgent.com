/* Checks tables/sim/baccarat-engine.js. Run from the repo root:  node tables/checks/baccarat_engine_check.js
   1. The engine's exact enumeration of the 8-deck tableau (every ordered deal, up to six cards without
      replacement from 416) against an independent enumeration written here from the printed drawing chart,
      and both against the published figures: tables/sim/games.js (probabilities to 6 dp, edges) and the
      house-edge table on tables/baccarat.html (2 dp). Pace against games.js.
   2. The tableau, hand by hand: every Banker total 0-7 against every Player third card (and Player standing),
      naturals, totals mod 10, winners, pairs, and what each bet pays.
   3. A 200,000-hand session with a random bettor (legal and illegal chips, take-downs, a $5,000 buy-in with
      rebuys): every chip the table books or refuses agrees with the rules written here, and after every deal
      every bet on the felt is legal (whole dollars, $10 minimum, table maximum, within the rack) and nothing is
      booked between the deal and the payout. actual = expected + luck, the bankroll balances to the cent,
      every payout matches an independent payout rule, and luck averages zero.
   4. A list of illegal bets the table must refuse and legal ones it must book.
   Exits 1 on any failure. */
'use strict';
var fs = require('fs'), path = require('path'), vm = require('vm');
var ROOT = path.join(__dirname, '..', '..');
var BE = require(path.join(ROOT, 'tables/sim/baccarat-engine.js'));
var fails = 0;
function ok(cond, msg) { if (!cond) { fails++; console.log('  FAIL ' + msg); } return cond; }
function pad(s, n) { s = String(s); while (s.length < n) s += ' '; return s; }
function lpad(s, n) { s = String(s); while (s.length < n) s = ' ' + s; return s; }

var g = BE.create(), g9 = BE.create({ tiePays: 9 }), E = g.enumeration;

/* ---------- the drawing chart, written out independently (rows: Banker's two-card total;
   columns: Player's third card 0-9; D draws, S stands). Player stood: Banker draws on 0-5. ---------- */
var CHART = {
  0: 'DDDDDDDDDD', 1: 'DDDDDDDDDD', 2: 'DDDDDDDDDD',
  3: 'DDDDDDDDSD',      // draws unless the Player's third card is an 8
  4: 'SSDDDDDDSS',      // draws on 2-7
  5: 'SSSSDDDDSS',      // draws on 4-7
  6: 'SSSSSSDDSS',      // draws on 6-7
  7: 'SSSSSSSSSS'
};
function chartDraws(bt, p3) { return p3 == null ? bt <= 5 : CHART[bt].charAt(p3) === 'D'; }

/* ---------- 1. enumeration ---------- */
console.log('\n1. Every deal from a full 8-deck shoe (416 cards, up to 6 drawn without replacement), counted exactly');
/* Independent enumeration: recursive, over card values with counts, the chart above for Banker. Weights are
   probabilities as integer counts over the same D = 416·415·414·413·412·411 so they can be compared exactly. */
function indep(decks) {
  var N = 52 * decks, cnt = [16 * decks, 4 * decks, 4 * decks, 4 * decks, 4 * decks, 4 * decks, 4 * decks, 4 * decks, 4 * decks, 4 * decks];
  var D = 1; for (var i = 0; i < 6; i++) D *= N - i;
  var out = { banker: 0, player: 0, tie: 0 };
  function rest(k) { var t = 1; for (var i = k; i < 6; i++) t *= N - i; return t; }
  function draw(fn, w, k) { for (var v = 0; v < 10; v++) if (cnt[v]) { var ww = w * cnt[v]; cnt[v]--; fn(v, ww, k + 1); cnt[v]++; } }
  function finish(pt, bt, w, k) { var x = w * rest(k); if (pt > bt) out.player += x; else if (bt > pt) out.banker += x; else out.tie += x; }
  draw(function (p1, w, k) { draw(function (b1, w, k) { draw(function (p2, w, k) { draw(function (b2, w, k) {
    var pt = (p1 + p2) % 10, bt = (b1 + b2) % 10;
    if (pt >= 8 || bt >= 8) return finish(pt, bt, w, k);
    if (pt >= 6) { if (bt <= 5) draw(function (b3, w, k) { finish(pt, (bt + b3) % 10, w, k); }, w, k); else finish(pt, bt, w, k); return; }
    draw(function (p3, w, k) {
      var pt3 = (pt + p3) % 10;
      if (chartDraws(bt, p3)) draw(function (b3, w, k) { finish(pt3, (bt + b3) % 10, w, k); }, w, k); else finish(pt3, bt, w, k);
    }, w, k);
  }, w, k); }, w, k); }, w, k); }, 1, 0);
  return { D: D, W: out };
}
var I8 = indep(8);
ok(E.D === I8.D, 'D: engine ' + E.D + ' vs independent ' + I8.D);
ok(E.W.banker + E.W.player + E.W.tie === E.D, 'engine weights sum to D');
ok(E.D < Math.pow(2, 53), 'D below 2^53 (integer arithmetic exact)');
['banker', 'player', 'tie'].forEach(function (k) { ok(E.W[k] === I8.W[k], k + ' weight: engine ' + E.W[k] + ' vs independent ' + I8.W[k]); });
console.log('   D = 416·415·414·413·412·411 = ' + E.D + ' ordered six-card sequences; engine and independent counts agree exactly: ' +
            (E.W.banker === I8.W.banker && E.W.player === I8.W.player && E.W.tie === I8.W.tie ? 'yes' : 'NO'));
/* A single deck too, as a second fixed point of the two enumerations (published 1-deck Banker edge is 1.01%). */
var I1 = indep(1), E1 = BE.enumerate(1);
ok(E1.W.banker === I1.W.banker && E1.W.player === I1.W.player && E1.W.tie === I1.W.tie, '1-deck enumerations agree');
var b1 = 100 * BE.fnum(BE.create({ decks: 1 }).edges.banker);
ok(b1.toFixed(2) === '1.01', '1-deck Banker edge ' + b1 + ' vs baccarat.html 1.01%');
console.log('   single deck: counts agree, Banker edge ' + b1.toFixed(4) + '% (baccarat.html: 1.01%)');

/* Pairs: the hand's two cards are Player's 1st and 3rd card off the shoe (Banker's 2nd and 4th). Enumerated over
   the 13 ranks with the Banker's first card in between; must equal (4d-1)/(52d-1) = 31/415. */
(function () {
  var n = 32, N = 416, hit = 0, all = 0;
  for (var a = 0; a < 13; a++) for (var b = 0; b < 13; b++) for (var c = 0; c < 13; c++) {
    var na = n, w = na; var nb = b === a ? n - 1 : n; w *= nb; var nc = n - (c === a ? 1 : 0) - (c === b ? 1 : 0); w *= nc;
    all += w; if (c === a) hit += w;
  }
  ok(all === N * (N - 1) * (N - 2), 'pair enumeration total');
  var f = BE.F(hit, all);
  ok(f.n === BigInt(E.pair.n) && f.d === BigInt(E.pair.d), 'pair: enumerated ' + BE.fq(f) + ' vs engine ' + E.pair.n + '/' + E.pair.d);
  console.log('   pair (first two cards of a hand, same rank): enumerated ' + BE.fq(f) + ' = ' + (BE.fnum(f) * 100).toFixed(4) + '%');
})();

var ctx = { window: {} }; vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'tables/sim/games.js'), 'utf8'), ctx);
var GB = ctx.window.TTG_GAMES.baccarat;
var pubP = { banker: GB.bets.banker.rows[0].p, player: GB.bets.player.rows[0].p, tie: GB.bets['tie-8'].rows[0].p };
console.log('\n   probabilities vs tables/sim/games.js (6 dp)');
['banker', 'player', 'tie'].forEach(function (k) {
  var mine = E.p[k];
  if (ok(mine.toFixed(6) === pubP[k].toFixed(6), k + ': games.js ' + pubP[k] + ' vs engine ' + mine)) console.log('   ok   ' + pad(k, 8) + pubP[k].toFixed(6) + '   engine ' + mine.toFixed(9) + '  (' + E.W[k] + ' / D)');
});
ok(E.p.pair.toFixed(6) === GB.bets.pair.rows[0].p.toFixed(6), 'pair p: games.js ' + GB.bets.pair.rows[0].p + ' vs engine ' + E.p.pair);
console.log('   ok   pair    ' + GB.bets.pair.rows[0].p.toFixed(6) + '   engine ' + E.p.pair.toFixed(9) + '  (31/415)');

console.log('\n   house edges (exact fractions) vs tables/sim/games.js `edge` fields');
var EDGES = [['banker', g.edges.banker, 'banker'], ['player', g.edges.player, 'player'], ['tie-8', g.edges.tie, 'tie'], ['tie-9', g9.edges.tie, 'tie'], ['pair', g.edges.ppair, 'ppair']];
EDGES.forEach(function (r) {
  var pub = GB.bets[r[0]].edge, mine = BE.fnum(r[1]);
  if (ok(Math.abs(pub - mine) < 5e-5, r[0] + ': games.js ' + pub + ' vs engine ' + mine))
    console.log('   ok   ' + pad(r[0], 8) + lpad((100 * pub).toFixed(2) + '%', 7) + '   engine ' + lpad((100 * mine).toFixed(4) + '%', 9) + '   = ' + BE.fq(r[1]));
});
ok(BE.fq(g.edges.bpair) === BE.fq(g.edges.ppair), 'banker pair edge = player pair edge');

console.log('\n   vs the house-edge table on tables/baccarat.html (2 dp)');
var html = fs.readFileSync(path.join(ROOT, 'tables/baccarat.html'), 'utf8'), rows = {}, re = /<tr><td>(.*?)<\/td><td class="num (\w+)">~?([\d.]+)%<\/td><\/tr>/g, m;
while ((m = re.exec(html))) rows[m[1]] = { pct: +m[3], cls: m[2] };
var PAGE = [['Banker (5% commission)', g.edges.banker], ['Player', g.edges.player], ['Tie at 9:1', g9.edges.tie],
            ['Player / Banker pair (11:1)', g.edges.ppair], ['Tie at 8:1', g.edges.tie],
            ['Banker at 4% commission (rare, promotional)', BE.create({ commission: 4 }).edges.banker]];
PAGE.forEach(function (r) {
  var row = rows[r[0]];
  if (!ok(row, 'baccarat.html row "' + r[0] + '" not found')) return;
  var mine = 100 * BE.fnum(r[1]);
  if (ok(mine.toFixed(2) === row.pct.toFixed(2), r[0] + ': page ' + row.pct + '% vs engine ' + mine.toFixed(4) + '%'))
    console.log('   ok   ' + pad(r[0], 44) + lpad(row.pct.toFixed(2) + '%', 7) + '   engine ' + lpad(mine.toFixed(4) + '%', 9) + '   page class ' + row.cls + ', table band ' + g.band(r[1]));
});
ok(BE.PACE.big === GB.pace, 'pace: engine ' + BE.PACE.big + ' vs games.js ' + GB.pace);
ok(/120.150/.test(GB.paceNote) && BE.PACE.mini[0] === 120 && BE.PACE.mini[1] === 150, 'mini pace 120-150 vs games.js paceNote "' + GB.paceNote + '"');
console.log('   pace: ' + BE.PACE.big + ' hands/hour at the big table, ' + BE.PACE.mini.join('–') + ' at mini (games.js: ' + GB.pace + ', "' + GB.paceNote + '")');
console.log('   also: natural ' + (100 * E.p.natural).toFixed(3) + '% · Player draws ' + (100 * E.p.pDraw).toFixed(3) + '% · Banker draws ' + (100 * E.p.bDraw).toFixed(3) + '% of hands');

/* ---------- 2. the tableau, hand by hand ---------- */
function card(v, r) { return { v: v, r: r == null ? (v === 0 ? 12 : v - 1) : r }; }        // value 0 -> a king by default
function deal(cards) { var q = cards.slice(); return BE.play(function () { if (!q.length) throw new Error('ran out of test cards'); return q.shift(); }); }
var cases = 0, bad = 0;
function expect(cond, msg) { cases++; if (!ok(cond, msg)) bad++; }
// Player draws (two-card 0-5) against every Banker total 0-7 and every third card 0-9
for (var pt = 0; pt <= 5; pt++) for (var bt = 0; bt <= 7; bt++) for (var p3 = 0; p3 <= 9; p3++) {
  var h = deal([card(0, 12), card(0, 11), card(pt), card(bt), card(p3), card(4)]);
  expect(h.player.length === 3, 'P' + pt + ' should draw');
  expect((h.banker.length === 3) === chartDraws(bt, p3), 'B' + bt + ' vs P3=' + p3 + ': banker ' + (h.banker.length === 3 ? 'drew' : 'stood') + ', chart says ' + CHART[bt].charAt(p3));
  expect(h.pt === (pt + p3) % 10 && h.bt === (h.banker.length === 3 ? (bt + 4) % 10 : bt), 'totals P' + pt + '+' + p3 + ' B' + bt);
}
// Player stands on 6-7: Banker draws on 0-5, stands on 6-7
for (pt = 6; pt <= 7; pt++) for (bt = 0; bt <= 7; bt++) {
  h = deal([card(0, 12), card(0, 11), card(pt), card(bt), card(3), card(9)]);
  expect(h.player.length === 2, 'P' + pt + ' should stand');
  expect((h.banker.length === 3) === (bt <= 5), 'Player stood on ' + pt + ', Banker ' + bt + ' should ' + (bt <= 5 ? 'draw' : 'stand'));
  expect(h.p3 === null, 'no p3 when Player stands');
}
// naturals: both stand whatever the other hand holds
[[8, 0], [9, 3], [0, 8], [5, 9], [8, 8], [9, 9], [8, 9]].forEach(function (x) {
  h = deal([card(0, 12), card(0, 11), card(x[0]), card(x[1]), card(1), card(1)]);
  expect(h.natural && h.player.length === 2 && h.banker.length === 2, 'natural P' + x[0] + ' B' + x[1] + ': both stand');
  expect(h.winner === (x[0] > x[1] ? 'player' : x[1] > x[0] ? 'banker' : 'tie'), 'natural winner P' + x[0] + ' B' + x[1]);
});
// totals are the last digit; tens and faces count zero; a two-card 18 is an 8 (natural)
h = deal([card(7), card(0, 9), card(8), card(0, 10), card(0, 11), card(0, 12)]);          // P 7+8=15 -> 5, B 10+J = 0
expect(h.p2 === 5 && h.b2 === 0, '7+8 = 5 and 10+J = 0');
h = deal([card(9), card(3), card(9), card(3), card(1), card(1)]);                           // P 9+9 = 18 -> natural 8 v B 3+3 = 6
expect(h.p2 === 8 && h.natural && h.winner === 'player' && h.playerPair && h.bankerPair, '9+9 is a natural 8 and beats 3+3; 9-9 and 3-3 are pairs');
h = deal([card(0, 9), card(1), card(0, 10), card(2), card(5), card(6)]);                     // 10 and J are both 0 but not a pair
expect(!h.playerPair && h.p2 === 0, '10 + J: total 0, not a pair (different ranks)');
h = deal([card(0, 12), card(0, 12), card(0, 12), card(0, 12), card(0, 12), card(0, 12)]);   // all kings: 0 v 0, both draw, tie 0-0
expect(h.winner === 'tie' && h.player.length === 3 && h.banker.length === 3 && h.playerPair && h.bankerPair, 'six kings: 0-0 tie, both draw, both pairs');
// payouts for each bet, both tie rules
(function () {
  var bw = deal([card(0, 12), card(9), card(0, 11), card(0, 10), card(1), card(1)]);        // Banker natural 9 v Player 0
  var pw = deal([card(8), card(0, 12), card(0, 11), card(7), card(1), card(1)]);           // Player natural 8 v Banker 7
  var tw = deal([card(8), card(8), card(0, 11), card(0, 12), card(1), card(1)]);           // 8-8 tie
  var T = [[g, 'banker', 10, bw, 9.5], [g, 'banker', 15, bw, 14.25], [g, 'banker', 10, pw, -10], [g, 'banker', 10, tw, 0],
           [g, 'player', 10, pw, 10], [g, 'player', 10, bw, -10], [g, 'player', 10, tw, 0],
           [g, 'tie', 10, tw, 80], [g9, 'tie', 10, tw, 90], [g, 'tie', 10, bw, -10],
           [g, 'ppair', 10, tw, -10], [g, 'bpair', 10, tw, -10]];
  var pp = deal([card(3, 2), card(0, 12), card(3, 2), card(0, 11), card(1), card(1)]);     // Player 3-3 (pair, 6)
  T.push([g, 'ppair', 10, pp, 110], [g, 'bpair', 10, pp, -10]);
  T.forEach(function (x) { expect(x[0].payout(x[1], x[2], x[3]) === x[4], x[1] + ' $' + x[2] + ' on ' + x[3].winner + ': ' + x[0].payout(x[1], x[2], x[3]) + ' vs ' + x[4]); });
})();
console.log('\n2. Tableau: ' + cases + ' hand-built cases (8 Banker totals x 10 third cards x 6 Player totals, Player standing on 6 and 7, naturals, totals, pairs, payouts): ' + (bad ? bad + ' wrong' : 'all as the chart says'));

/* ---------- 3. a long session with a random bettor ---------- */
/* The rules, written out here for the audit: a chip of `a` on a bet holding `have` is legal iff the cards are not
   out, `a` is a positive whole number, have + a is between the minimum and the table maximum, and a <= rack. */
function legal(T, type, a) {
  var R = T.g.rules, have = T.bets[type] || 0;
  return T.phase === 'bets' && BE.TYPES.indexOf(type) >= 0 && typeof a === 'number' && a > 0 && a === Math.floor(a) &&
         have + a >= R.min && have + a <= R.max && a <= T.bank;
}
function pays(type, a, h, tie) {                 // independent payout rule, dollars
  var w = h.winner;
  if (type === 'player') return w === 'player' ? a : w === 'banker' ? -a : 0;
  if (type === 'banker') return w === 'banker' ? Math.round(a * 95) / 100 : w === 'player' ? -a : 0;
  if (type === 'tie') return w === 'tie' ? tie * a : -a;
  if (type === 'ppair') return h.playerPair ? 11 * a : -a;
  if (type === 'bpair') return h.bankerPair ? 11 * a : -a;
}
var srng = BE.seeded(20260930), HANDS = 200000, START = 5000;
var T = g.Table({ seed: 17, bankroll: START }), rebuys = 0, tries = 0, booked = 0, refusedOk = 0, disagree = [], illegal = [], afterDeal = 0,
    luckSum = 0, l2 = 0, payBad = 0, removed = 0, shoes = 0, minLeft = 1e9;
function pick(a) { return a[Math.floor(srng() * a.length)]; }
function amount() {
  var u = srng();
  if (u < 0.55) return 10 + Math.floor(srng() * 60);            // ordinary chips
  if (u < 0.70) return pick([25, 50, 100, 250, 500, 1000]);
  if (u < 0.78) return pick([1, 5, 9]);                         // under the minimum unless pressed
  if (u < 0.84) return pick([10.5, 12.25, 0.5]);               // part dollars
  if (u < 0.88) return pick([0, -10, -1]);
  if (u < 0.93) return pick([1001, 1500, 5000]);               // over the maximum
  return Math.floor(srng() * 3000);
}
for (var n = 0; n < HANDS; n++) {
  if (T.bank < 10 && !T.onFelt()) { T.bank = Math.round((T.bank + START) * 100) / 100; rebuys += START; }
  var k = 1 + Math.floor(srng() * 4);
  for (var i = 0; i < k; i++) {
    var t = srng() < 0.02 ? 'dragon' : pick(BE.TYPES), a = amount(), want = legal(T, t, a), r = T.place(t, a);
    tries++; if (r.ok) booked++; else refusedOk++;
    if (r.ok !== want && disagree.length < 5) disagree.push('hand ' + n + ': ' + t + ' $' + a + ' engine ' + (r.ok ? 'booked' : 'refused (' + r.reason + ')') + ', rules say ' + (want ? 'legal' : 'illegal'));
  }
  if (srng() < 0.05) { var ks = Object.keys(T.bets); if (ks.length && T.remove(pick(ks)).ok) removed++; }
  var before = JSON.stringify(T.bets), bankBefore = T.bank;

  var d = T.deal(); if (d.hand.shuffled) shoes++;
  minLeft = Math.min(minLeft, T.cardsLeft() + d.hand.player.length + d.hand.banker.length);   // cards in the shoe when this hand began
  // nothing may be booked after the deal
  var late = T.place(pick(BE.TYPES), 25); if (late.ok) afterDeal++;
  if (T.remove('banker').ok) afterDeal++;
  var wrong = [];
  if (JSON.stringify(T.bets) !== before || T.bank !== bankBefore) wrong.push('felt changed after the deal');
  for (var bt2 in T.bets) {
    var x = T.bets[bt2];
    if (x !== Math.floor(x) || x < g.rules.min || x > g.rules.max) wrong.push(bt2 + ' $' + x);
  }
  if (T.bank < -1e-9) wrong.push('rack overdrawn: ' + T.bank);
  if (wrong.length && illegal.length < 5) illegal.push('hand ' + n + ': ' + wrong.join('; '));
  var mine = 0; for (var bt3 in T.bets) mine += pays(bt3, T.bets[bt3], d.hand, 8);
  var s = T.settle();
  if (Math.abs(s.net - mine) > 1e-9) payBad++;
  luckSum += s.luck; l2 += s.luck * s.luck;
}
var L = T.ledger, luck = L.actual - L.expected;
var bal = T.bank + T.onFelt() - (START + rebuys + L.actual);
var meanL = luckSum / HANDS, sdL = Math.sqrt(l2 / HANDS - meanL * meanL), zL = meanL / (sdL / Math.sqrt(HANDS));
var sumE = 0, sumA = 0; Object.keys(L.byKey).forEach(function (k) { sumE += L.byKey[k].expected; sumA += L.byKey[k].actual; });
console.log('\n3. Session: ' + HANDS.toLocaleString('en-US') + ' hands over ' + (shoes + 1) + ' shoes, $' + START.toLocaleString('en-US') + ' buy-in, $' + rebuys.toLocaleString('en-US') + ' in rebuys; ' +
            tries.toLocaleString('en-US') + ' chips tried, ' + booked.toLocaleString('en-US') + ' booked, ' + refusedOk.toLocaleString('en-US') + ' refused, ' + removed.toLocaleString('en-US') + ' bets taken down');
console.log('   wagered $' + Math.round(L.wagered).toLocaleString('en-US') + ' · expected $' + L.expected.toFixed(2) + ' · actual $' + L.actual.toFixed(2) + ' · luck $' + luck.toFixed(2));
console.log('   actual - (expected + luck summed hand by hand) = ' + (L.actual - (L.expected + luckSum)).toExponential(2));
console.log('   rack + felt - (buy-in + rebuys + actual) = ' + bal.toExponential(2));
console.log('   recap rows sum to the ledger: expected ' + (sumE - L.expected).toExponential(2) + ', actual ' + (sumA - L.actual).toExponential(2));
console.log('   luck per hand: mean $' + meanL.toFixed(4) + ', sd $' + sdL.toFixed(2) + ', z = ' + zL.toFixed(2));
var fr = { banker: L.wins.banker / HANDS, player: L.wins.player / HANDS, tie: L.wins.tie / HANDS };
console.log('   outcomes: Banker ' + (100 * fr.banker).toFixed(2) + '% · Player ' + (100 * fr.player).toFixed(2) + '% · Tie ' + (100 * fr.tie).toFixed(2) + '% (enumerated 45.86 / 44.62 / 9.52) · pairs P ' +
            (100 * L.pairs.player / HANDS).toFixed(2) + '% B ' + (100 * L.pairs.banker / HANDS).toFixed(2) + '% (7.47) · fewest cards left at a deal: ' + minLeft);
ok(Math.abs(L.actual - (L.expected + luckSum)) < 1e-6 * Math.max(1, L.wagered / 1e6), 'actual = expected + luck');
ok(Math.abs(bal) < 1e-3, 'bankroll balance ' + bal);
ok(Math.abs(sumE - L.expected) < 1e-3 && Math.abs(sumA - L.actual) < 1e-3, 'recap sums');
ok(Math.abs(zL) < 3.29, 'luck mean z ' + zL);
ok(payBad === 0, payBad + ' payouts differ from the independent rule');
ok(minLeft > g.rules.cut && minLeft >= 6, 'a hand started with too few cards left: ' + minLeft);
['banker', 'player', 'tie'].forEach(function (k) { var p = E.p[k], z = (fr[k] - p) / Math.sqrt(p * (1 - p) / HANDS); ok(Math.abs(z) < 3.29, k + ' frequency z ' + z.toFixed(2)); });
ok(afterDeal === 0, afterDeal + ' bets booked or taken down after the deal');
console.log('   every chip agrees with the rules: ' + (disagree.length ? 'NO' : 'yes') + ' · felt audited after every deal (' + HANDS.toLocaleString('en-US') + ' times): ' +
            (illegal.length ? 'ILLEGAL BETS FOUND' : 'every bet legal, nothing booked or taken down after the deal') + ' · payouts match the independent rule: ' + (payBad ? 'NO' : 'yes'));
disagree.forEach(function (x) { ok(false, x); });
illegal.forEach(function (x) { ok(false, x); });

/* ---------- 4. illegal bets refused, legal ones booked ---------- */
function table(rules, bank) { return BE.create(rules || {}).Table({ seed: 5, bankroll: bank == null ? 1e6 : bank }); }
function refuses(X, type, a, why) {
  var bets = JSON.stringify(X.bets), bank = X.bank, r = X.place(type, a);
  return ok(!r.ok && JSON.stringify(X.bets) === bets && X.bank === bank, 'should refuse: ' + why + (r.ok ? ' (it was booked)' : ''));
}
function dealt(X) { X.place('banker', 10); X.deal(); return X; }
var ILLEGAL = [
  [table(), 'player', 5, 'Player under the $10 minimum'],
  [table(), 'tie', 5, 'Tie under the $10 minimum'],
  [table(), 'ppair', 1, 'a $1 Player Pair (under the minimum)'],
  [table(), 'banker', 10.5, 'a part-dollar bet'],
  [table(), 'banker', 0.5, 'fifty cents'],
  [table(), 'player', -10, 'a negative bet'],
  [table(), 'player', 0, 'a zero bet'],
  [table(), 'player', NaN, 'NaN'],
  [table(), 'player', '10', 'a string amount'],
  [table(), 'banker', 1001, 'Banker over the $1,000 default maximum'],
  [table(), 'tie', 1010, 'Tie over the $1,000 maximum'],
  [(function () { var X = table(); X.place('banker', 1000); return X; })(), 'banker', 1, 'pressing Banker past the maximum'],
  [table({ max: 500 }), 'player', 600, 'Player $600 at a $500 maximum'],
  [table({ max: 2000 }), 'player', 2001, 'Player $2,001 at a $2,000 maximum'],
  [dealt(table()), 'player', 10, 'a bet after the deal'],
  [dealt(table()), 'banker', 10, 'adding to Banker after the deal'],
  [table({}, 100), 'banker', 200, 'more than the rack ($200 with $100)'],
  [(function () { var X = table({}, 100); X.place('player', 60); return X; })(), 'banker', 50, 'more than what is left in the rack'],
  [table(), 'dragon', 10, 'a bet this table does not offer']
];
var refused = 0; ILLEGAL.forEach(function (c) { if (refuses(c[0], c[1], c[2], c[3])) refused++; });
var Xr = dealt(table()); var noTake = !Xr.remove('banker').ok; ok(noTake, 'should refuse: taking a bet down after the deal');
var LEGAL = [
  ['both sides at once', function (X) { return X.place('player', 10).ok && X.place('banker', 10).ok; }],
  ['$1,000 Banker at the default maximum', function (X) { return X.place('banker', 1000).ok; }],
  ['$1,000 Tie at the default maximum', function (X) { return X.place('tie', 1000).ok; }],
  ['$10 Tie, $10 Player Pair, $10 Banker Pair', function (X) { return X.place('tie', 10).ok && X.place('ppair', 10).ok && X.place('bpair', 10).ok; }],
  ['every bet at once', function (X) { return BE.TYPES.every(function (t) { return X.place(t, 25).ok; }); }],
  ['$5 pressed onto a $10 Player bet', function (X) { return X.place('player', 10).ok && X.place('player', 5).ok && X.bets.player === 15; }],
  ['$5,000 Banker at a $5,000 maximum', function (X) { return X.place('banker', 5000).ok; }, { max: 5000 }],
  ['the whole rack ($100 of $100)', function (X) { return X.place('banker', 100).ok && X.bank === 0; }, {}, 100],
  ['betting again once the hand is paid', function (X) { X.place('banker', 10); X.deal(); X.settle(); return X.place('player', 10).ok; }]
];
var bookedL = 0; LEGAL.forEach(function (c) { if (ok(c[1](table(c[2], c[3])), 'should book: ' + c[0])) bookedL++; });
console.log('\n4. Table rules: ' + refused + ' of ' + ILLEGAL.length + ' illegal bets refused (under the minimum, part-dollar, zero, negative, not a number, over the $500/$1,000/$2,000 maximum, pressed past it, after the deal, more than the rack, no such bet); ' +
            'bets after the deal stay put: ' + (noTake ? 'yes' : 'NO') + '; ' + bookedL + ' of ' + LEGAL.length + ' legal bets booked (' + LEGAL.map(function (c) { return c[0]; }).join('; ') + ')');

console.log('\n' + (fails ? 'FAILED: ' + fails + ' check(s)' : 'ALL CHECKS PASS'));
process.exit(fails ? 1 : 0);
