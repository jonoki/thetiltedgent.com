/* Checks tables/sim/tcp-engine.js. Run from the repo root:  node tables/checks/tcp_engine_check.js
   1. Hand counts and every edge, counted exactly: once through the engine's suit-isomorphism classes and once by brute
      force (all 22,100 player hands x all 18,424 dealer hands, no grouping), against tables/sim/games.js and the
      house-edge table on tables/three-card-poker.html; the Q-6-4 rule against optimal play; fold rate, average wager,
      dealer qualifying rates.
   2. Hand ranking: an independent ranker in this file agrees with the engine on every hand's category and on the
      order of 2,000,000 random pairs; unit tests (A-2-3 and Q-K-A straights, no K-A-2, ties, kickers, the dealer's
      Queen-high qualifier, the Q-6-4 line); scripted hands settle as the rules say.
   3. A 200,000-hand session with a random bettor (random legal and illegal bets, random play or fold): hand by hand,
      result = expected + deal luck - decision cost + dealer luck; the bankroll balances; deal luck and dealer luck
      average zero; the felt is audited after every bet, deal and decision.
   4. The table refuses every illegal bet on a list and books the legal ones.
   Exits 1 on any failure. */
'use strict';
var fs = require('fs'), path = require('path'), vm = require('vm');
var ROOT = path.join(__dirname, '..', '..');
var E = require(path.join(ROOT, 'tables/sim/tcp-engine.js'));
var fails = 0;
function ok(cond, msg) { if (!cond) { fails++; console.log('  FAIL ' + msg); } return cond; }
function pct(x, d) { return (100 * x).toFixed(d == null ? 3 : d) + '%'; }
function pad(s, n) { s = String(s); while (s.length < n) s += ' '; return s; }
function lpad(s, n) { s = String(s); while (s.length < n) s = ' ' + s; return s; }
function fmt(n) { return n.toLocaleString('en-US'); }
/* card from text: C('Q','s') */
var SU = { s: 0, h: 1, d: 2, c: 3 }, RK = { '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14 };
function C(t) { return (RK[t[0]] - 2) * 4 + SU[t[1]]; }
function H(s) { return s.split(' ').map(C); }

/* ---------- an independent ranker: [category, tiebreak ranks...], compared left to right ---------- */
function rankKey(cards) {
  var r = cards.map(function (c) { return 2 + Math.floor(c / 4); }).sort(function (a, b) { return b - a; });
  var s = cards.map(function (c) { return c % 4; });
  var flush = s[0] === s[1] && s[1] === s[2];
  var straightTop = null;
  if (r[0] === r[1] + 1 && r[1] === r[2] + 1) straightTop = r[0];
  if (r[0] === 14 && r[1] === 3 && r[2] === 2) straightTop = 3;          // A-2-3, the lowest straight
  if (r[0] === r[2]) return [4, r[0]];
  if (straightTop && flush) return [5, straightTop];
  if (straightTop) return [3, straightTop];
  if (flush) return [2, r[0], r[1], r[2]];
  if (r[0] === r[1]) return [1, r[0], r[2]];
  if (r[1] === r[2]) return [1, r[1], r[0]];
  return [0, r[0], r[1], r[2]];
}
function cmpKey(a, b) { for (var i = 0; i < Math.max(a.length, b.length); i++) { var d = (a[i] || 0) - (b[i] || 0); if (d) return d > 0 ? 1 : -1; } return 0; }
function sign(x) { return x > 0 ? 1 : x < 0 ? -1 : 0; }

/* ---------- 1. counts and edges ---------- */
console.log('\n1. Hand counts and house edges, counted exactly (one deck; 22,100 player hands x 18,424 dealer hands)');
var CN = E.counts(), PUB_COUNTS = [16440, 3744, 1096, 720, 52, 48];
console.log('   ' + pad('hand', 18) + lpad('count', 8) + lpad('published', 11) + lpad('chance', 10));
for (var cat = 5; cat >= 0; cat--) {
  ok(CN[cat] === PUB_COUNTS[cat], E.CAT_NAME[cat] + ' count ' + CN[cat] + ' vs ' + PUB_COUNTS[cat]);
  console.log('   ' + pad(E.CAT_NAME[cat], 18) + lpad(fmt(CN[cat]), 8) + lpad(fmt(PUB_COUNTS[cat]), 11) + lpad(pct(CN[cat] / E.N_HANDS, 3), 10));
}
ok(CN.reduce(function (a, b) { return a + b; }, 0) === 22100, 'counts sum to 22,100');

var cls = E.classes(), clsTotal = 0, nOk = true;
cls.forEach(function (e) { clsTotal += e.count; if (e.n !== E.N_DEALER || e.nq + e.w + e.l + e.t !== e.n) nOk = false; });
ok(clsTotal === 22100, 'isomorphism classes cover 22,100 hands: ' + clsTotal);
ok(nOk, 'every class sees exactly 18,424 dealer hands');
console.log('\n   suit isomorphism: ' + fmt(cls.length) + ' classes cover ' + fmt(clsTotal) + ' hands; every class sees 18,424 dealer hands');

/* Brute force, no grouping: every player hand against every dealer hand, with the independent ranker's categories. */
var t0 = Date.now(), BF = { optimal: {}, q64: {}, always: {} }, BONUS_KEYS = E.BONUS_KEYS, bfPlayed = 0;
BONUS_KEYS.forEach(function (b) { BF.optimal[b] = 0; BF.q64[b] = 0; BF.always[b] = 0; });
var classMismatch = 0;
for (var a = 0; a < 52; a++) for (var b = a + 1; b < 52; b++) for (var c = b + 1; c < 52; c++) {
  var v = E.versus(a, b, c), s = E.evaluate(a, b, c), kcat = rankKey([a, b, c])[0], S = v.nq + 2 * (v.w - v.l);
  var e = E.classFor([a, b, c]);
  if (e.nq !== v.nq || e.w !== v.w || e.l !== v.l || e.t !== v.t) classMismatch++;
  BONUS_KEYS.forEach(function (bk) {
    var pn = (E.BONUS[bk][kcat] || 0) * E.N_DEALER + S;
    BF.optimal[bk] += Math.max(pn, -E.N_DEALER);
    BF.q64[bk] += E.q64(s) ? pn : -E.N_DEALER;
    BF.always[bk] += pn;
  });
  if ((E.BONUS['541'][kcat] || 0) * E.N_DEALER + S > -E.N_DEALER) bfPlayed++;
}
ok(classMismatch === 0, classMismatch + ' hands whose dealer counts differ from their isomorphism class');
console.log('   brute force (' + (Date.now() - t0) + ' ms): every hand\'s dealer counts equal its class\'s: ' + (classMismatch ? 'NO' : 'yes'));

var ctx = { window: {} }; vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'tables/sim/games.js'), 'utf8'), ctx);
var GJ = ctx.window.TTG_GAMES['three-card-poker'];
var DEN = E.N_HANDS * E.N_DEALER;
console.log('\n   Ante & Play (per $1 of ante; optimal play = play when EV(play) > -1)');
console.log('   ' + pad('bonus', 7) + pad('strategy', 10) + lpad('edge', 9) + lpad('brute force', 13) + lpad('played', 9) + lpad('avg wager', 11) + lpad('of wagered', 12));
var R = {};
BONUS_KEYS.forEach(function (bk) {
  var g = E.create({ bonus: bk });
  ['optimal', 'q64', 'always'].forEach(function (st) {
    var A = g.ante(st), bf = -BF[st][bk] / DEN;
    ok(Math.abs(A.edge - bf) < 1e-15, bk + ' ' + st + ': classes ' + A.edge + ' vs brute force ' + bf);
    console.log('   ' + pad(E.BONUS_LABEL[bk], 7) + pad(st, 10) + lpad(pct(A.edge, 4), 9) + lpad(pct(bf, 4), 13) + lpad(pct(A.pPlay, 2), 9) + lpad(A.avgWager.toFixed(4), 11) + lpad(pct(A.edgeWagered, 4), 12) +
                (st === 'optimal' ? '   = ' + A.edgeNum + '/' + A.edgeDen : ''));
    R[bk + st] = A;
  });
});
ok(Math.abs(bfPlayed / E.N_HANDS - R['541optimal'].pPlay) < 1e-12, 'share played, brute force vs classes');
/* published: games.js and the house-edge table on three-card-poker.html (to the digits published) */
var A541 = R['541optimal'];
var pubAnte = [['games.js ante-play edge', GJ.bets['ante-play'].edge, A541.edge, 5e-5],
               ['games.js ante-play avgWager', GJ.bets['ante-play'].avgWager, A541.avgWager, 5e-4]];
console.log('\n   vs tables/sim/games.js');
pubAnte.forEach(function (x) { if (ok(Math.abs(x[1] - x[2]) <= x[3], x[0] + ': ' + x[1] + ' vs ' + x[2])) console.log('   ok   ' + pad(x[0], 30) + lpad(x[1], 8) + '  engine ' + x[2].toFixed(5)); });
var foldPub = GJ.bets['ante-play'].rows[0].p;      // the fold row of the calibrated shape
if (ok(Math.abs(foldPub - A541.pFold) < 5e-4, 'games.js fold share ' + foldPub + ' vs ' + A541.pFold)) console.log('   ok   ' + pad('games.js fold share (x = -1 row)', 30) + lpad(foldPub, 8) + '  engine ' + A541.pFold.toFixed(5));
var PPMAP = { 'pair-plus-40-30-6-3-1': '40-30-6-3-1', 'pair-plus-40-30-6-4-1': '40-30-6-4-1', 'pair-plus-50-30-6-3-1': '50-30-6-3-1' };
Object.keys(PPMAP).forEach(function (k) {
  var mine = E.create({ pp: PPMAP[k] }).pairPlus(), pub = GJ.bets[k].edge;
  // the same edge from the games.js outcome rows
  var rowsEdge = -GJ.bets[k].rows.reduce(function (s, r) { return s + r.p * r.x; }, 0);
  if (ok(Math.abs(pub - mine.edge) <= 5e-5 && Math.abs(rowsEdge - mine.edge) < 1e-12, k + ': games.js ' + pub + ' rows ' + rowsEdge + ' vs engine ' + mine.edge))
    console.log('   ok   ' + pad(k, 30) + lpad(pub, 8) + '  engine ' + mine.edge.toFixed(5) + ' = ' + mine.edgeNum + '/' + mine.edgeDen + ', games.js rows ' + rowsEdge.toFixed(5));
});
if (ok(GJ.pace === E.PACE, 'pace ' + GJ.pace + ' vs engine ' + E.PACE)) console.log('   ok   ' + pad('pace (hands per hour)', 30) + lpad(GJ.pace, 8) + '  engine ' + E.PACE);

console.log('\n   vs the house-edge table on tables/three-card-poker.html');
var html = fs.readFileSync(path.join(ROOT, 'tables/three-card-poker.html'), 'utf8');
var rows = [], re = /<tr><td>(.*?)<\/td><td class="num \w+">(~?)([\d.]+)(?:&ndash;[\d.]+)?%<\/td><\/tr>/g, m;
while ((m = re.exec(html))) rows.push({ name: m[1].replace(/&amp;/g, '&'), approx: !!m[2], pct: +m[3] });
function ppEdge(pays) { var s = 0; for (var k = 1; k <= 5; k++) s += CN[k] * pays[k]; return -(s - CN[0]) / E.N_HANDS; }
var MAP = [
  [/^Ante & Play, Q-6-4 strategy, as a % of money wagered/, R['541q64'].edgeWagered],
  [/^Pair Plus, 40-30-6-4-1$/, ppEdge(E.PAIRPLUS['40-30-6-4-1'])],
  [/^Ante & Play, 5-4-1 bonus/, A541.edge], [/^Ante & Play, 4-3-1/, R['431optimal'].edge], [/^Ante & Play, 3-2-1/, R['321optimal'].edge],
  [/^Pair Plus, 50-30-6-3-1/, ppEdge(E.PAIRPLUS['50-30-6-3-1'])], [/^Pair Plus, 40-30-6-3-1/, ppEdge(E.PAIRPLUS['40-30-6-3-1'])],
  // corrected 8 Oct 2026 from this count: the page had '40-33-6-4-1 or 35-33-6-4-1: 2.70%' and 'never folding ~5.4%'
  [/^Pair Plus, 40-33-6-4-1$/, ppEdge({ 5: 40, 4: 33, 3: 6, 2: 4, 1: 1 })], [/^Pair Plus, 35-33-6-4-1$/, ppEdge({ 5: 35, 4: 33, 3: 6, 2: 4, 1: 1 })],
  [/^Ante & Play, never folding, of the ante$/, R['541always'].edge]];
/* Rows this table can't settle: printed, not failed (they are the page's copy, not this engine's). */
var NOTES = [
  [/^Six Card Bonus/, function () { return 'not a bet at this table'; }]];
var matched = 0;
rows.forEach(function (r) {
  var hit = MAP.filter(function (x) { return x[0].test(r.name); })[0];
  if (hit) {
    matched++;
    if (ok(Math.abs(100 * hit[1] - r.pct) < 0.005 + 1e-9, r.name + ': page ' + r.pct + '% vs engine ' + (100 * hit[1]).toFixed(4) + '%'))
      console.log('   ok   ' + pad(r.name, 58) + lpad(r.pct.toFixed(2) + '%', 7) + '  engine ' + lpad((100 * hit[1]).toFixed(4) + '%', 9));
    return;
  }
  var note = NOTES.filter(function (x) { return x[0].test(r.name); })[0];
  if (ok(note, 'no mapping for three-card-poker.html row "' + r.name + '"')) console.log('   NOTE ' + pad(r.name, 58) + lpad((r.approx ? '~' : '') + r.pct + '%', 7) + '  ' + note[1]());
});
ok(matched === MAP.length, matched + ' of ' + MAP.length + ' page rows matched');

console.log('\n   Q-6-4 against optimal play');
BONUS_KEYS.forEach(function (bk) {
  var g = E.create({ bonus: bk }), miss = g.q64Misses(), gap = R[bk + 'q64'].edge - R[bk + 'optimal'].edge;
  console.log('   ' + pad(E.BONUS_LABEL[bk], 6) + 'optimal ' + pct(R[bk + 'optimal'].edge, 4) + ' · Q-6-4 ' + pct(R[bk + 'q64'].edge, 4) + ' · gap ' + (100 * gap).toFixed(6) + ' points · hands where they differ: ' + miss.length);
  ok(gap >= -1e-15 && gap < 1e-4, bk + ' Q-6-4 within a hair of optimal: gap ' + gap);
});
/* The line itself: the best hand that folds and the worst that plays. */
var g541 = E.create();
var lo = g541.decision(H('Qs 6h 4d')), lo2 = g541.decision(H('Qs 6h 3d')), lo3 = g541.decision(H('Qs 5h 4d'));
console.log('   EV(play) per $1 of ante: Q-6-4 ' + lo.evPlay.toFixed(5) + ' · Q-6-3 ' + lo2.evPlay.toFixed(5) + ' · Q-5-4 ' + lo3.evPlay.toFixed(5) + '  (fold = -1)');
ok(lo.evPlay > -1 && lo2.evPlay < -1 && lo3.evPlay < -1, 'Q-6-4 plays, Q-6-3 and Q-5-4 fold (offsuit)');

var allQ = 0;                                       // unconditional dealer qualifying rate
for (var a2 = 0; a2 < 52; a2++) for (var b2 = a2 + 1; b2 < 52; b2++) for (var c2 = b2 + 1; c2 < 52; c2++) if (E.qualifies(E.evaluate(a2, b2, c2))) allQ++;
console.log('\n   averages (5-4-1, optimal): fold ' + pct(A541.pFold, 2) + ' of hands · average wager ' + A541.avgWager.toFixed(4) + ' antes · edge ' + pct(A541.edge, 2) + ' of the ante = ' + pct(A541.edgeWagered, 2) +
            ' of money wagered · dealer qualifies ' + pct(allQ / 22100, 2) + ' of hands (' + fmt(allQ) + ' of 22,100), ' + pct(A541.dealerQualifiesWhenPlaying, 2) + ' of the hands you play');
ok(Math.abs(A541.pFold - 0.326) < 0.0005, 'fold rate ~32.6%');
ok(Math.abs(allQ / 22100 - 0.696) < 0.0005, 'dealer qualifies ~69.6%');
ok(Math.abs(A541.edgeWagered - 0.0201) < 0.00005, 'edge of money wagered 2.01%');

/* ---------- 2. hand ranking ---------- */
console.log('\n2. Hand ranking');
var agreeCat = 0, catBad = 0;
for (var a3 = 0; a3 < 52; a3++) for (var b3 = a3 + 1; b3 < 52; b3++) for (var c3 = b3 + 1; c3 < 52; c3++) {
  if (E.catOf(E.evaluate(a3, b3, c3)) === rankKey([a3, b3, c3])[0]) agreeCat++; else catBad++;
}
ok(catBad === 0, catBad + ' hands where the engine and the independent ranker disagree on the category');
var prng = E.seeded(31), pairsBad = 0, PAIRS = 2000000;
for (var k = 0; k < PAIRS; k++) {
  var d = E.dealSix(prng), x = E.evaluate(d[0], d[1], d[2]), y = E.evaluate(d[3], d[4], d[5]);
  if (sign(x - y) !== cmpKey(rankKey(d.slice(0, 3)), rankKey(d.slice(3)))) pairsBad++;
}
ok(pairsBad === 0, pairsBad + ' of ' + PAIRS + ' random pairs ordered differently by the engine and the independent ranker');
console.log('   independent ranker: category agrees on ' + fmt(agreeCat) + ' of 22,100 hands; order agrees on ' + fmt(PAIRS - pairsBad) + ' of ' + fmt(PAIRS) + ' random pairs');

function sc(s) { var h = H(s); return E.evaluate(h[0], h[1], h[2]); }
var T_RANK = [
  ['A-2-3 is a straight', E.catOf(sc('As 2h 3d')) === 3],
  ['A-2-3 is the lowest straight (below 2-3-4)', sc('As 2h 3d') < sc('2s 3h 4d')],
  ['A-2-3 straight beats an A-K-J flush', sc('As 2h 3d') > sc('Ah Kh Jh')],
  ['Q-K-A is a straight', E.catOf(sc('Qs Kh Ad')) === 3],
  ['Q-K-A is the highest straight (above J-Q-K)', sc('Qs Kh Ad') > sc('Js Qh Kd')],
  ['Q-K-A suited is the top straight flush', sc('Qh Kh Ah') > sc('Js Qs Ks') && E.catOf(sc('Qh Kh Ah')) === 5],
  ['K-A-2 is not a straight (Ace high)', E.catOf(sc('Ks Ah 2d')) === 0],
  ['K-A-2 loses to a pair of 2s', sc('Ks Ah 2d') < sc('2s 2h 3d')],
  ['A-2-3 suited is a straight flush', E.catOf(sc('Ac 2c 3c')) === 5],
  ['straight flush > three of a kind > straight > flush > pair > high card',
    sc('2s 3s 4s') > sc('As Ah Ad') && sc('2s 2h 2d') > sc('Qs Kh Ad') && sc('As 2h 3d') > sc('Ah Kh Jh') && sc('2h 3h 5h') > sc('As Ah Kd') && sc('2s 2h 3d') > sc('As Kh Jd')],
  ['identical ranks tie (K-9-4 vs K-9-4, other suits)', sc('Ks 9h 4d') === sc('Kh 9c 4s')],
  ['kicker order: K-9-5 > K-9-4', sc('Ks 9h 5d') > sc('Kh 9c 4s')],
  ['first card first: K-10-2 > K-9-8', sc('Ks Th 2d') > sc('Kh 9c 8s')],
  ['pair then kicker: 8-8-A > 8-8-K', sc('8s 8h Ad') > sc('8c 8d Ks')],
  ['the pair outranks the kicker: 9-9-2 > 8-8-A', sc('9s 9h 2d') > sc('8c 8d As')],
  ['flushes compare high card first: A-9-3 > K-Q-9', sc('Ah 9h 3h') > sc('Ks Qs 9s')],
  ['K-Q-J suited is a straight flush, not a flush', E.catOf(sc('Ks Qs Js')) === 5],
  ['flush ties on identical ranks', sc('Ah 9h 3h') === sc('As 9s 3s')],
  ['equal straights tie', sc('5s 6h 7d') === sc('5h 6c 7s')],
  ['dealer qualifies with Q-3-2', E.qualifies(sc('Qs 3h 2d'))],
  ['dealer does not qualify with J-10-8', !E.qualifies(sc('Js Th 8d'))],
  ['dealer qualifies with a J-10-9 straight', E.qualifies(sc('Js Th 9d'))],
  ['dealer qualifies with a pair of 2s', E.qualifies(sc('2s 2h 3d'))],
  ['dealer qualifies with a J-high flush', E.qualifies(sc('Jh 9h 7h'))],
  ['dealer qualifies with A-2-4 (Ace high)', E.qualifies(sc('As 2h 4d'))],
  ['dealer qualifies with K-A-2 (Ace high)', E.qualifies(sc('Ks Ah 2d'))],
  ['Q-6-4 rule: Q-6-4 plays, Q-6-3 folds, Q-7-2 plays, J-10-8 folds, 2-2-3 plays',
    E.q64(sc('Qs 6h 4d')) && !E.q64(sc('Qs 6h 3d')) && E.q64(sc('Qs 7h 2d')) && !E.q64(sc('Js Th 8d')) && E.q64(sc('2s 2h 3d'))],
  ['names: "Pair of Eights, A kicker", "Straight, A-2-3", "Straight, Q-K-A", "Ace high, A-K-2"',
    E.describe(sc('8s 8h Ad')) === 'Pair of Eights, A kicker' && E.describe(sc('As 2h 3d')) === 'Straight, A-2-3' && E.describe(sc('Qs Kh Ad')) === 'Straight, Q-K-A' && E.describe(sc('Ks Ah 2d')) === 'Ace high, A-K-2']];
var rankOk = 0; T_RANK.forEach(function (t) { if (ok(t[1], t[0])) rankOk++; });
console.log('   unit tests: ' + rankOk + ' of ' + T_RANK.length + ' pass');

/* Scripted hands: cards fixed, every bet's settlement worked out by hand from the rules. */
function scripted(rules, bets, cards, choice, want, why) {
  var g = E.create(rules), X = g.Table({ bankroll: 10000, seed: 1 });
  if (bets.ante) X.place({ type: 'ante', amount: bets.ante });
  if (bets.pp) X.place({ type: 'pp', amount: bets.pp });
  var r = X.deal(H(cards)), h = r.hand;
  if (!h.done) h = X.act(choice).hand;
  var got = {}; h.lines.forEach(function (l) { got[l.bet] = (got[l.bet] || 0) + l.net; });
  var good = true; Object.keys(want).forEach(function (k) { if ((got[k] || 0) !== want[k]) good = false; });
  Object.keys(got).forEach(function (k) { if (want[k] == null && got[k] !== 0) good = false; });
  good = good && X.bank === 10000 + h.net;
  return ok(good, 'scripted: ' + why + ' got ' + JSON.stringify(got) + ' want ' + JSON.stringify(want));
}
var SCRIPT = [
  [{}, { ante: 10 }, 'As Kh 9d Js Th 8d', 'play', { ante: 10, play: 0 }, 'dealer J-10-8 does not qualify: Ante 1:1, Play pushes'],
  [{}, { ante: 10 }, '2s 4h 6d Qs 3h 2c', 'play', { ante: -10, play: -10 }, 'dealer Q-3-2 qualifies and beats 6-4-2'],
  [{}, { ante: 10 }, 'Ks 9h 4d Kh 9c 4s', 'play', { ante: 0, play: 0 }, 'identical ranks: both push'],
  [{}, { ante: 10 }, '5s 6h 7d 8s 8h 8d', 'play', { ante: -10, play: -10, bonus: 10 }, 'a straight loses to trips but the 5-4-1 bonus still pays 1:1'],
  [{}, { ante: 10 }, 'Ah Kh Qh 2s 3h 5d', 'play', { ante: 10, play: 0, bonus: 50 }, 'straight flush, dealer does not qualify: Ante 1:1 + 5:1 bonus, Play pushes'],
  [{ bonus: '321' }, { ante: 10 }, '7s 7h 7d As Kh Jd', 'play', { ante: 10, play: 10, bonus: 20 }, '3-2-1: trips beat Ace high, bonus 2:1'],
  [{}, { ante: 10, pp: 10 }, '8s 8h 2d As Kh Jd', 'fold', { ante: -10, pp: 10 }, 'folding a pair: Ante lost, Pair Plus still pays 1:1'],
  [{}, { pp: 10 }, '2h 7h Jh As Kh Jd', null, { pp: 30 }, 'Pair Plus alone, a flush on 40-30-6-3-1 pays 3:1, no decision'],
  [{ pp: '40-30-6-4-1' }, { pp: 10 }, '2h 7h Jh As Kh Jd', null, { pp: 40 }, 'Pair Plus alone, a flush on 40-30-6-4-1 pays 4:1'],
  [{ pp: '50-30-6-3-1' }, { ante: 10, pp: 10 }, '9c Tc Jc 2s 2h 3d', 'play', { ante: 10, play: 10, bonus: 50, pp: 500 }, 'straight flush on 50-30-6-3-1: Pair Plus 50:1'],
  [{}, { ante: 10, pp: 10 }, 'As Kh 9d Qs Qh 3d', 'play', { ante: -10, play: -10, pp: -10 }, 'Ace high loses to a pair of Queens; Pair Plus loses on high card'],
  [{}, { ante: 10 }, 'Qs 6h 4d Js Th 8d', 'fold', { ante: -10 }, 'a fold loses the Ante only']];
var scrOk = 0; SCRIPT.forEach(function (s) { if (scripted(s[0], s[1], s[2], s[3], s[4], s[5])) scrOk++; });
console.log('   scripted hands: ' + scrOk + ' of ' + SCRIPT.length + ' settle as the rules say');

/* ---------- 3. a long session with a random bettor ---------- */
/* What a dealer would accept on the felt right now. Returns what is wrong. */
function audit(T) {
  var bad = [], b = T.bets, R = T.g.rules;
  ['ante', 'pp', 'play'].forEach(function (k) { if (b[k] < 0 || b[k] !== Math.floor(b[k])) bad.push(k + ' $' + b[k] + ': not whole dollars'); });
  ['ante', 'pp'].forEach(function (k) { if (b[k] && (b[k] < R.min || b[k] > R.max)) bad.push(k + ' $' + b[k] + ': outside $' + R.min + '-$' + R.max); });
  if (T.phase === 'bet' && b.play) bad.push('a Play bet before the deal');
  if (b.play && b.play !== b.ante) bad.push('Play $' + b.play + ' is not the Ante $' + b.ante);
  if (b.play && !b.ante) bad.push('Play with no Ante');
  if (T.phase === 'decide' && !b.ante) bad.push('a hand waiting for a decision with no Ante');
  if (T.bank < -1e-9) bad.push('rack overdrawn: $' + T.bank);
  Object.keys(b).forEach(function (k) { if (['ante', 'pp', 'play'].indexOf(k) < 0) bad.push('unknown bet ' + k); });
  return bad;
}
var srng = E.seeded(20260930), HANDS = 200000, START = 1e9;
function pick(arr) { return arr[Math.floor(srng() * arr.length)]; }
var SIZES = [1, 5, 10, 10, 15, 25, 25, 50, 100, 100, 250, 500, 999, 1000, 1001, 2000, 10.5, 0, -10];
var maxes = E.MAXES, sess = [];
function runSession(rules, hands, seed, bankroll) {
  var g = E.create(rules), X = g.Table({ seed: seed, bankroll: bankroll });
  var st = { hands: 0, booked: 0, refused: 0, plays: 0, folds: 0, refusedPlay: 0, audits: 0, illegal: [], identWorst: 0, dl: 0, dl2: 0, rl: 0, rl2: 0, nr: 0, bal: 0 };
  function check(where) { st.audits++; var w = audit(X); if (w.length && st.illegal.length < 5) st.illegal.push(where + ': ' + w.join('; ')); }
  for (var n = 0; n < hands; n++) {
    var tries = 1 + Math.floor(srng() * 4);
    for (var t = 0; t < tries; t++) {
      var type = srng() < 0.15 ? pick(['play', 'six', 'ante']) : pick(['ante', 'ante', 'pp']);
      var r = X.place({ type: type, amount: pick(SIZES) });
      if (r.ok) st.booked++; else st.refused++;
      check('hand ' + n + ' after a bet');
    }
    if (srng() < 0.1 && X.bets.ante) X.remove('ante');
    if (!X.bets.ante && !X.bets.pp) { if (!X.place({ type: 'pp', amount: 10 }).ok) { X.bank += 1000; X.rebuys = (X.rebuys || 0) + 1000; X.place({ type: 'pp', amount: 10 }); } }
    var bankBefore = X.bank + X.onFelt(), dr = X.deal();
    if (!ok(dr.ok, 'deal refused: ' + dr.reason)) break;
    check('hand ' + n + ' after the deal');
    var h = dr.hand;
    if (!h.done) {
      if (X.place({ type: 'pp', amount: 10 }).ok || X.place({ type: 'ante', amount: 10 }).ok) ok(false, 'a bet was booked after the deal');
      if (X.place({ type: 'play', amount: X.bets.ante + 1 }).ok) ok(false, 'a Play bet unequal to the Ante was booked');
      var choice = srng() < 0.7 ? 'play' : 'fold';
      var ar = X.act(choice);
      if (!ar.ok) { st.refusedPlay++; ok(!X.canAffordPlay(), 'Play refused with money in the rack: ' + ar.reason); ar = X.act('fold'); choice = 'fold'; }
      ok(ar.ok, 'fold refused');
      h = ar.hand;
      if (choice === 'play') st.plays++; else st.folds++;
    }
    check('hand ' + n + ' after settling');
    var ident = h.net - (h.V0 + h.dealLuck - h.decisionCost + h.dealerLuck);
    st.identWorst = Math.max(st.identWorst, Math.abs(ident));
    ok(h.decisionCost > -1e-9, 'negative decision cost');
    ok(Math.abs(X.bank + X.onFelt() - (bankBefore + h.net)) < 1e-9, 'hand ' + n + ': bank moved by ' + (X.bank + X.onFelt() - bankBefore) + ', result ' + h.net);
    st.dl += h.dealLuck; st.dl2 += h.dealLuck * h.dealLuck;
    if (h.ante) { st.rl += h.dealerLuck; st.rl2 += h.dealerLuck * h.dealerLuck; st.nr++; }
    st.hands++;
  }
  var L = X.ledger;
  st.L = L; st.T = X;
  st.cum = L.actual - (L.expected + L.dealLuck - L.decisionCost + L.dealerLuck);
  st.bal = X.bank + X.onFelt() - (bankroll + L.actual) - (X.rebuys || 0);
  st.sumExp = L.byKey.ante.expected + L.byKey.pp.expected - L.expected;
  st.sumAct = L.byKey.ante.actual + L.byKey.pp.actual - L.actual;
  st.sumWag = L.byKey.ante.wagered + L.byKey.pp.wagered - L.wagered;
  return st;
}
var t3 = Date.now();
var S1 = runSession({ max: 1000 }, HANDS, 77, START);
var S2 = runSession({ max: 500, bonus: '321', pp: '50-30-6-3-1' }, 20000, 78, START);
var S3 = runSession({ max: 5000, bonus: '431', pp: '40-30-6-4-1' }, 20000, 79, 300);    // a short rack: Play is often unaffordable
console.log('\n3. Random sessions (' + (Date.now() - t3) + ' ms)');
[['default table, $1,000 max', S1, START], ['3-2-1 / 50-30-6-3-1, $500 max', S2, START], ['4-3-1 / 40-30-6-4-1, $5,000 max, $300 rack', S3, 300]].forEach(function (x) {
  var s = x[1], L = s.L, zd = (s.dl / s.hands) / Math.sqrt((s.dl2 / s.hands - Math.pow(s.dl / s.hands, 2)) / s.hands),
      zr = (s.rl / s.nr) / Math.sqrt((s.rl2 / s.nr - Math.pow(s.rl / s.nr, 2)) / s.nr);
  console.log('   ' + x[0] + ': ' + fmt(s.hands) + ' hands, ' + fmt(s.booked) + ' bets booked, ' + fmt(s.refused) + ' refused; ' + fmt(s.plays) + ' played, ' + fmt(s.folds) + ' folded' +
              (s.refusedPlay ? ' (' + fmt(s.refusedPlay) + ' Play refused: rack short)' : ''));
  console.log('     wagered $' + fmt(Math.round(L.wagered)) + ' · expected $' + L.expected.toFixed(2) + ' · actual $' + L.actual.toFixed(2) + ' · deal luck $' + L.dealLuck.toFixed(2) +
              ' · dealer luck $' + L.dealerLuck.toFixed(2) + ' · decision cost $' + L.decisionCost.toFixed(2));
  console.log('     actual - (expected + deal luck - decision cost + dealer luck) = ' + s.cum.toExponential(2) + ' (worst single hand ' + s.identWorst.toExponential(2) + ')');
  console.log('     bankroll + chips on felt - (start + actual) = ' + s.bal.toExponential(2) + ' · recap rows sum to the ledger: ' + [s.sumExp, s.sumAct, s.sumWag].map(function (v) { return v.toExponential(1); }).join(', '));
  console.log('     deal luck per hand z = ' + zd.toFixed(2) + ' · dealer luck per played-or-folded hand z = ' + zr.toFixed(2));
  console.log('     felt audited ' + fmt(s.audits) + ' times: ' + (s.illegal.length ? 'ILLEGAL BETS FOUND' : 'every bet legal'));
  ok(Math.abs(s.cum) < 1e-6 * Math.max(1, L.wagered / 1e6), x[0] + ': identity ' + s.cum);
  ok(s.identWorst < 1e-9, x[0] + ': per-hand identity ' + s.identWorst);
  ok(Math.abs(s.bal) < 1e-6, x[0] + ': bankroll balance ' + s.bal);
  var tol = 1e-12 * Math.max(1e6, L.wagered);   // float sums over 200,000 hands: relative, not absolute
  ok(Math.abs(s.sumExp) < tol && Math.abs(s.sumAct) < tol && Math.abs(s.sumWag) < tol, x[0] + ': recap sums ' + [s.sumExp, s.sumAct, s.sumWag]);
  ok(Math.abs(zd) < 3.29, x[0] + ': deal luck mean z ' + zd);
  ok(Math.abs(zr) < 3.29, x[0] + ': dealer luck mean z ' + zr);
  s.illegal.forEach(function (w) { ok(false, x[0] + ' ' + w); });
});
ok(S3.refusedPlay > 0, 'the short-rack session exercised an unaffordable Play');

/* ---------- 4. the table refuses every illegal bet ---------- */
function refuses(rules, setup, spec, why) {
  var X = E.create(rules).Table({ seed: 3, bankroll: 1e6 }); setup(X);
  var before = JSON.stringify(X.bets), bank = X.bank, phase = X.phase, r = X.place(spec);
  return ok(!r.ok && JSON.stringify(X.bets) === before && X.bank === bank && X.phase === phase, 'should refuse: ' + why + (r.ok ? ' (it was booked)' : ''));
}
var none = function () {};
function dealt(ante, pp) { return function (X) { if (ante) X.place({ type: 'ante', amount: ante }); if (pp) X.place({ type: 'pp', amount: pp }); X.deal(H('As Kh 9d Js Th 8d')); }; }
var CASES = [
  [{}, none, { type: 'play', amount: 10 }, 'Play with no Ante and no hand'],
  [{}, function (X) { X.place({ type: 'pp', amount: 10 }); X.deal(H('As Kh 9d Js Th 8d')); }, { type: 'play', amount: 10 }, 'Play after a Pair Plus-only hand (no Ante)'],
  [{}, function (X) { X.place({ type: 'ante', amount: 10 }); }, { type: 'play', amount: 10 }, 'Play before the deal'],
  [{}, dealt(20), { type: 'play', amount: 10 }, 'Play less than the Ante'],
  [{}, dealt(20), { type: 'play', amount: 40 }, 'Play more than the Ante'],
  [{}, dealt(20), { type: 'ante', amount: 10 }, 'adding to the Ante after the deal'],
  [{}, dealt(20), { type: 'pp', amount: 10 }, 'a Pair Plus bet after the deal'],
  [{}, function (X) { dealt(20)(X); X.act('play'); }, { type: 'play', amount: 20 }, 'a second Play after the hand settled'],
  [{}, none, { type: 'ante', amount: 5 }, 'an Ante under the $10 minimum'],
  [{}, none, { type: 'pp', amount: 5 }, 'a Pair Plus under the $10 minimum'],
  [{}, none, { type: 'ante', amount: 1001 }, 'an Ante over the $1,000 default maximum'],
  [{}, none, { type: 'pp', amount: 1500 }, 'a Pair Plus over the $1,000 default maximum'],
  [{ max: 500 }, none, { type: 'ante', amount: 510 }, 'an Ante over a $500 maximum'],
  [{}, function (X) { X.place({ type: 'ante', amount: 1000 }); }, { type: 'ante', amount: 1 }, 'pressing an Ante past the maximum'],
  [{}, none, { type: 'ante', amount: 10.5 }, 'a part-dollar Ante'],
  [{}, none, { type: 'pp', amount: 12.25 }, 'a part-dollar Pair Plus'],
  [{}, none, { type: 'ante', amount: 0 }, 'a zero bet'],
  [{}, none, { type: 'ante', amount: -10 }, 'a negative bet'],
  [{}, function (X) { X.bank = 50; }, { type: 'ante', amount: 60 }, 'an Ante over the bankroll'],
  [{}, function (X) { X.bank = 1010; X.place({ type: 'ante', amount: 1000 }); X.deal(H('As Kh 9d Js Th 8d')); }, { type: 'play', amount: 1000 }, 'a Play the rack cannot cover'],
  [{}, none, { type: 'six', amount: 10 }, 'a bet this table does not offer']];
var refused = 0; CASES.forEach(function (c) { if (refuses(c[0], c[1], c[2], c[3])) refused++; });
/* Other refusals: dealing with no bets, dealing twice, deciding with no hand. And a short rack can still fold. */
var Y = E.create().Table({ seed: 3, bankroll: 1e6 });
var other = [['deal with no bets', !Y.deal().ok], ['decide with no hand', !Y.act('fold').ok]];
Y.place({ type: 'ante', amount: 10 }); Y.deal(); other.push(['deal again before the decision', !Y.deal().ok]); other.push(['an unknown decision', !Y.act('raise').ok]);
var Z = E.create().Table({ seed: 3, bankroll: 1010 }); Z.place({ type: 'ante', amount: 1000 }); Z.deal(H('As Kh 9d Js Th 8d'));
other.push(['a short rack can still fold', Z.act('fold').ok && Z.bank === 10]);
var Q = E.create().Table({ seed: 3, bankroll: 100 }); Q.place({ type: 'ante', amount: 50 }); Q.place({ type: 'pp', amount: 10 });
other.push(['taking a bet back before the deal', Q.remove('ante').ok && Q.bank === 90]); Q.deal(H('As Kh 9d Js Th 8d'));
other.push(['no taking bets back after the deal', !Q.remove('pp').ok]);
var otherOk = 0; other.forEach(function (o) { if (ok(o[1], o[0])) otherOk++; });

var LEGAL = [
  [{}, none, [{ type: 'pp', amount: 10 }], 'Pair Plus alone ($10)'],
  [{}, none, [{ type: 'ante', amount: 1000 }], 'a $1,000 Ante at the default maximum'],
  [{}, none, [{ type: 'ante', amount: 25 }, { type: 'pp', amount: 10 }], 'Ante + Pair Plus'],
  [{}, none, [{ type: 'ante', amount: 1000 }, { type: 'pp', amount: 1000 }], '$1,000 Ante + $1,000 Pair Plus'],
  [{ max: 5000 }, none, [{ type: 'ante', amount: 5000 }], 'a $5,000 Ante at a $5,000 maximum'],
  [{}, none, [{ type: 'ante', amount: 10 }, { type: 'ante', amount: 5 }], 'pressing an Ante from $10 to $15'],
  [{}, dealt(20), [{ type: 'play', amount: 20 }], 'Play equal to a $20 Ante'],
  [{}, function (X) { X.bank = 2000; X.place({ type: 'ante', amount: 1000 }); X.deal(H('As Kh 9d Js Th 8d')); }, [{ type: 'play', amount: 1000 }], 'a $1,000 Play with exactly $1,000 left in the rack']];
var booked = 0;
LEGAL.forEach(function (c) {
  var X = E.create(c[0]).Table({ seed: 3, bankroll: 1e6 }); c[1](X);
  var all = c[2].every(function (s) { return X.place(s).ok; });
  if (ok(all && !audit(X).length, 'should book: ' + c[3])) booked++;
});
console.log('\n4. Table rules: ' + refused + ' of ' + CASES.length + ' illegal bets refused; ' + otherOk + ' of ' + other.length + ' other refusals and permissions hold; ' + booked + ' of ' + LEGAL.length + ' legal bets booked');
console.log('   refused: ' + CASES.map(function (c) { return c[3]; }).join('; '));
console.log('   booked: ' + LEGAL.map(function (c) { return c[3]; }).join('; '));

console.log('\n' + (fails ? 'FAILED: ' + fails + ' check(s)' : 'ALL CHECKS PASS'));
process.exit(fails ? 1 : 0);
