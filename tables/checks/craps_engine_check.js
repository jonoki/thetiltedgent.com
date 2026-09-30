/* Checks tables/sim/craps-engine.js. Run from the repo root:  node tables/checks/craps_engine_check.js
   1. Every edge, from exact fractions, against tables/sim/games.js and the table on tables/craps.html
      (value and colour band), and the published average rolls per pass / don't pass decision.
   2. Bellman check, exact: for every bet, in every state, under 64 rule sets, the expected value after
      one roll equals the value before — so luck has mean zero by construction, not by sampling.
   3. Every bet at every legal size pays whole dollars.
   4. Monte Carlo cross-check (support only): 200,000 settled bets per bet type.
   5. A 1,000,000-roll session with a random bettor: actual + value on the felt = expected + luck,
      the bankroll balances to the cent, luck per roll averages zero, and after every roll every bet on the felt
      is one a dealer would book (audit).
   6. The table refuses every illegal bet on a list (put bets, come bets on the come-out, odds over the limit or
      in the wrong units or on the wrong side, bets under the minimum or over the $500 maximum, …) and books
      the legal ones at their limits (incl. place and buy on one number, and odds past the table maximum).
   Exits 1 on any failure. */
'use strict';
var fs = require('fs'), path = require('path'), vm = require('vm');
var ROOT = path.join(__dirname, '..', '..');
var CE = require(path.join(ROOT, 'tables/sim/craps-engine.js'));
var num = CE.num, fq = CE.fq, Q = CE.Q;
var fails = 0;
function ok(cond, msg) { if (!cond) { fails++; console.log('  FAIL ' + msg); } return cond; }
function pct(x, d) { return (100 * x).toFixed(d == null ? 3 : d) + '%'; }
function pad(s, n) { s = String(s); while (s.length < n) s += ' '; return s; }
function lpad(s, n) { s = String(s); while (s.length < n) s = ' ' + s; return s; }

var g = CE.create();

/* ---------- 1. edges ---------- */
console.log('\n1. House edge of every bet (default rules: 3-4-5x, field 3x on 12, buy vig on win, lay vig up front)');
console.log('   ' + pad('bet', 20) + pad('pays', 31) + pad('edge (exact)', 16) + lpad('edge', 9) + lpad('rolls', 8) + lpad('per roll', 10) + '  band');
g.catalogue.forEach(function (c) {
  console.log('   ' + pad(c.name, 20) + pad(c.pays, 31) + pad(fq(c.edge), 16) + lpad(c.edgePct.toFixed(3) + '%', 9) +
              lpad(num(c.rolls).toFixed(3), 8) + lpad(c.perRollPct.toFixed(3) + '%', 10) + '  ' + c.band);
});

var ctx = { window: {} }; vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'tables/sim/games.js'), 'utf8'), ctx);
var GJ = ctx.window.TTG_GAMES.craps.bets;
var g2 = CE.create({ field12: 2 });
var vsGames = [['pass', g.byKey.pass], ['dont-pass', g.byKey.dontpass], ['place-6-8', g.byKey.place6], ['place-5-9', g.byKey.place5],
  ['place-4-10', g.byKey.place4], ['field-3x', g.byKey.field], ['field-2x', g2.byKey.field], ['hard-6-8', g.byKey.hard6],
  ['big-6-8', g.byKey.big6], ['hard-4-10', g.byKey.hard4], ['any-craps', g.byKey.anycraps], ['3-or-11', g.byKey.three],
  ['2-or-12', g.byKey.two], ['any-seven', g.byKey.any7]];
console.log('\n   vs tables/sim/games.js (published figures to 4-5 digits)');
vsGames.forEach(function (r) {
  var pub = GJ[r[0]].edge, mine = num(r[1].edge), d = Math.abs(pub - mine);
  if (ok(d < 5e-5, r[0] + ': games.js ' + pub + ' vs engine ' + mine)) console.log('   ok   ' + pad(r[0], 14) + lpad(pct(pub, 3), 8) + '  engine ' + pct(mine, 4));
});
var c345 = g.combo('pass');
ok(Math.abs(num(c345.avgWager) - GJ['pass-odds-345'].avgWager) < 0.005, 'pass-odds-345 avgWager');
console.log('   ok   pass-odds-345   avgWager ' + GJ['pass-odds-345'].avgWager + '  engine ' + num(c345.avgWager).toFixed(4) + ' (' + fq(c345.avgWager) + ')');

/* The published table on tables/craps.html: every row, value to 2 dp and its colour class. */
console.log('\n   vs the house-edge table on tables/craps.html (value to 2 dp, colour class)');
var html = fs.readFileSync(path.join(ROOT, 'tables/craps.html'), 'utf8');
var rows = [], re = /<tr><td>(.*?)<\/td><td class="num (\w+)">([\d.]+)%<\/td><\/tr>/g, m;
while ((m = re.exec(html))) rows.push({ name: m[1].replace(/&middot;/g, '·').replace(/&amp;/g, '&').replace(/&#39;|&rsquo;/g, "'"), cls: m[2], pct: +m[3] });
function comboAt(limit) { return CE.create({ odds: limit }).combo('pass').edge; }
var horn = g.byKey.horn.edge;
/* A split bet's edge must equal the unit-weighted average of its parts' edges (computed independently). */
var SPLITS = { horn: { two: 1, three: 1, eleven: 1, twelve: 1 }, world: { two: 1, three: 1, eleven: 1, twelve: 1, any7: 1 }, ce: { anycraps: 1, eleven: 1 }, hilo: { two: 1, twelve: 1 } };
console.log('\n   split bets vs the unit-weighted average of their parts');
Object.keys(SPLITS).forEach(function (k) {
  var sum = Q(0), u = 0; Object.keys(SPLITS[k]).forEach(function (p) { sum = CE.add(sum, CE.mul(Q(SPLITS[k][p]), g.byKey[p].edge)); u += SPLITS[k][p]; });
  var avg = CE.div(sum, Q(u));
  if (ok(CE.eq(avg, g.byKey[k].edge), k + ': engine ' + fq(g.byKey[k].edge) + ' vs parts ' + fq(avg))) console.log('   ok   ' + pad(g.byKey[k].name, 16) + pad(fq(g.byKey[k].edge), 8) + lpad(g.byKey[k].edgePct.toFixed(3) + '%', 9));
});
ok(Math.abs(100 * num(g.byKey.ce.edge) - 11.11) < 0.005, 'C&E vs craps.html 11.11%');
var MAP = [
  [/^Free odds/, g.byKey.odds4.edge], [/^Pass line \+ 3-4-5x/, comboAt('345')], [/^Pass line \+ 2x/, comboAt('2')],
  [/^Pass line \+ 1x/, comboAt('1')], [/^Don't pass/, g.byKey.dontpass.edge], [/^Pass line \/ come/, g.byKey.pass.edge],
  [/^Place 6 or 8/, g.byKey.place6.edge], [/^Buy 4 or 10/, g.byKey.buy4.edge], [/^Lay 4 or 10/, g.byKey.lay4.edge],
  [/^Field \(2x on 2, 3x/, g.byKey.field.edge], [/^Place 5 or 9/, g.byKey.place5.edge], [/^Field \(2x on both/, g2.byKey.field.edge],
  [/^Place 4 or 10/, g.byKey.place4.edge], [/^Hard 6/, g.byKey.hard6.edge], [/^Big 6/, g.byKey.big6.edge], [/^Hard 4/, g.byKey.hard4.edge],
  [/^Any craps/, g.byKey.anycraps.edge], [/^Horn/, horn], [/^2 or 12/, g.byKey.two.edge], [/^Any seven/, g.byKey.any7.edge]];
ok(rows.length === MAP.length, 'craps.html has ' + rows.length + ' edge rows, expected ' + MAP.length);
rows.forEach(function (r) {
  var hit = MAP.filter(function (x) { return x[0].test(r.name); })[0];
  if (!ok(hit, 'no engine mapping for craps.html row "' + r.name + '"')) return;
  var mine = 100 * num(hit[1]), band = g.band(hit[1]);
  var good = ok(Math.abs(mine - r.pct) < 0.005 + 1e-9, r.name + ': page ' + r.pct + '% vs engine ' + mine.toFixed(4) + '%') &
             ok(band === r.cls, r.name + ': page class ' + r.cls + ' vs engine band ' + band);
  if (good) console.log('   ok   ' + pad(r.name, 44) + lpad(r.pct.toFixed(2) + '%', 8) + '  engine ' + lpad(mine.toFixed(4) + '%', 9) + '  ' + band);
});

console.log('\n   average rolls per decision and edge per roll vs Wizard of Odds craps basics (pass 3.38 / 0.42%; don’t pass 3.47 / 0.40%)');
var passT = g.rolls({ type: 'pass', num: null });
var dpNoPush = num(passT) / (1 - 1 / 36);   // Wizard counts rolls per non-push decision for the don't
ok(num(passT).toFixed(2) === '3.38', 'pass rolls ' + num(passT));
ok(g.byKey.pass.perRollPct.toFixed(2) === '0.42', 'pass per roll');
ok(dpNoPush.toFixed(2) === '3.47', "don't pass rolls per non-push decision " + dpNoPush);
ok(g.byKey.dontpass.perRollPct.toFixed(2) === '0.40', "don't pass per roll");
console.log('   pass: ' + fq(passT) + ' = ' + num(passT).toFixed(4) + ' rolls, ' + g.byKey.pass.perRollPct.toFixed(4) + '% per roll');
console.log('   don’t pass: ' + dpNoPush.toFixed(4) + ' rolls per non-push decision, ' + g.byKey.dontpass.perRollPct.toFixed(4) + '% per roll');

console.log('\n   line bet + full odds, every limit (loss per line bet is unchanged; the money wagered grows)');
console.log('   ' + pad('limit', 8) + pad('pass: avg wager', 18) + lpad('combined', 10) + '   ' + pad('don’t: avg wager', 18) + lpad('combined', 10));
CE.ODDS_LIMITS.forEach(function (L) {
  var e = CE.create({ odds: L }), a = e.combo('pass'), b = e.combo('dontpass');
  ok(eq(a.lineEdge, g.byKey.pass.edge), 'line edge constant ' + L);
  console.log('   ' + pad(CE.ODDS_LABEL[L], 8) + pad(num(a.avgWager).toFixed(3), 18) + lpad(pct(num(a.edge)), 10) + '   ' +
              pad(num(b.avgWager).toFixed(3), 18) + lpad(pct(num(b.edge)), 10));
});
function eq(a, b) { return CE.eq(a, b); }

/* ---------- 2. Bellman check ---------- */
function allBets() {
  var out = [];
  ['pass', 'dontpass', 'come', 'dontcome'].forEach(function (t) { out.push({ type: t, num: null }); CE.POINTS.forEach(function (n) { out.push({ type: t, num: n }); }); });
  CE.POINTS.forEach(function (n) {
    [false, true].forEach(function (cm) { out.push({ type: 'odds', num: n, come: cm }); out.push({ type: 'layodds', num: n, come: cm }); });
    ['place', 'buy', 'lay'].forEach(function (t) { out.push({ type: t, num: n }); });
  });
  [4, 6, 8, 10].forEach(function (n) { out.push({ type: 'hard', num: n }); });
  [6, 8].forEach(function (n) { out.push({ type: 'big', num: n }); });
  ['field', 'any7', 'anycraps', 'two', 'three', 'eleven', 'twelve', 'horn', 'world', 'ce', 'hilo'].forEach(function (t) { out.push({ type: t, num: null }); });
  return out;
}
var checks = 0, variants = 0;
[2, 3].forEach(function (f12) { ['win', 'upfront'].forEach(function (bv) { ['win', 'upfront'].forEach(function (lv) {
  [false, true].forEach(function (pc) { [false, true].forEach(function (hc) { [false, true].forEach(function (cc) {
    var e = CE.create({ field12: f12, buyVig: bv, layVig: lv, placeOnComeOut: pc, hardOnComeOut: hc, comeOddsOnComeOut: cc }); variants++;
    allBets().forEach(function (b) { [false, true].forEach(function (comeOut) {
      var v = e.value(b), s = Q(0);
      CE.COMBOS.forEach(function (c) {
        var r = e.step(b, c, comeOut), x = !r ? v : r.r === 'move' ? e.value({ type: b.type, num: r.num }) : r.x;
        s = CE.add(s, CE.mul(Q(1, 36), x));
      });
      checks++;
      ok(CE.eq(s, v), 'Bellman ' + JSON.stringify(b) + ' comeOut=' + comeOut + ' rules ' + JSON.stringify(e.rules) + ': ' + fq(s) + ' vs ' + fq(v));
    }); });
  }); }); });
}); }); });
console.log('\n2. Bellman check (exact fractions): ' + checks + ' bet/state/rule cases across ' + variants + ' rule sets — E[value after roll] = value before in every one: ' + (fails ? 'see failures above' : 'yes'));

/* ---------- 3. whole-dollar payouts ---------- */
var payChecks = 0, payBad = 0;
[CE.create(), CE.create({ buyVig: 'upfront', layVig: 'win' })].forEach(function (e) {
  e.catalogue.forEach(function (c) {
    for (var k = 0; k < 12; k++) {
      var a = c.min + k * c.unit, win = null;
      CE.COMBOS.forEach(function (d) { var r = e.step({ type: c.type, num: c.num }, d, false); if (r && r.r === 'win') { var p = num(r.x) * a; if (Math.abs(p - Math.round(p)) > 1e-9) win = p; } });
      var vig = num(e.vigRate(c.type, c.num)) * a;
      payChecks++;
      if (win != null || Math.abs(vig - Math.round(vig)) > 1e-9) { payBad++; ok(false, c.name + ' $' + a + ' pays ' + win + ' vig ' + vig); }
    }
  });
});
console.log('\n3. Whole-dollar payouts and commissions: ' + payChecks + ' bet sizes checked, ' + payBad + ' fractional');

/* ---------- 4. Monte Carlo cross-check ---------- */
console.log('\n4. Monte Carlo cross-check (support only; seed 20260925; 200,000 settled bets each; |z| < 3.29 passes)');
var rng = CE.seeded(20260925), N = 200000, worst = 0;
function die() { return 1 + Math.floor(rng() * 6); }
g.catalogue.forEach(function (c) {
  var s = 0, s2 = 0;
  for (var i = 0; i < N; i++) {
    var b = { type: c.type, num: c.num }, x = null;
    while (x === null) {
      var d1 = die(), d2 = die(), r = g.step(b, { d1: d1, d2: d2, t: d1 + d2, hard: d1 === d2 }, false);
      if (!r) continue;
      if (r.r === 'move') { b.num = r.num; continue; }
      x = num(r.x);
    }
    x -= num(g.vigRate(c.type, c.num));       // upfront commission, per $1
    s += x; s2 += x * x;
  }
  var mean = s / N, sd = Math.sqrt(s2 / N - mean * mean), exact = num(g.value({ type: c.type, num: c.num })) - num(g.vigRate(c.type, c.num));
  var z = sd ? (mean - exact) / (sd / Math.sqrt(N)) : 0; worst = Math.max(worst, Math.abs(z));
  ok(Math.abs(z) < 3.29, c.name + ' MC mean ' + mean + ' vs exact ' + exact + ' z=' + z.toFixed(2));
});
console.log('   ' + g.catalogue.length + ' bets; largest |z| = ' + worst.toFixed(2));

/* ---------- 5. a long session with a random bettor ---------- */
/* Every bet on the felt must be one a dealer would book: whole dollars, the bet's unit and minimum, odds behind the
   right side of a bet with a number and within the limit, nothing but odds over the table maximum, and (between rolls) no line
   bet without a point and nothing left in the come boxes. Returns what is wrong. */
function audit(T) {
  var bad = [], lines = {};
  T.bets.forEach(function (b) {
    var odds = b.type === 'odds' || b.type === 'layodds', p = odds ? T.get(b.parent) : null, n = odds ? (p && p.num) : b.num;
    var tag = b.type + (n != null ? n : '') + ' $' + b.amount;
    if (b.amount !== Math.floor(b.amount) || b.amount <= 0) bad.push(tag + ': not whole dollars');
    if (odds) {
      if (!p || p.num == null) { bad.push(tag + ': odds with no point behind them'); return; }
      if ((b.type === 'odds') !== (p.type === 'pass' || p.type === 'come')) bad.push(tag + ': odds on the wrong side');
      if (b.amount > g.maxOdds(b.type, p.num, p.amount) + 1e-9) bad.push(tag + ': over the ' + g.rules.odds + ' limit behind $' + p.amount);
    }
    if (b.amount % g.unit(b.type, n)) bad.push(tag + ': not a multiple of $' + g.unit(b.type, n));
    if (b.amount < g.minBet(b.type, n)) bad.push(tag + ': under the $' + g.minBet(b.type, n) + ' minimum');
    if (!odds && b.amount > g.maxBet(b.type, n)) bad.push(tag + ': over the $' + g.rules.max + ' table maximum');
    if ((b.type === 'pass' || b.type === 'dontpass') && (lines[b.type] = (lines[b.type] || 0) + 1) > 1) bad.push(tag + ': two line bets');
    if ((b.type === 'pass' || b.type === 'dontpass') && (b.num == null) !== (T.point == null)) bad.push(tag + ': line bet out of step with the point');
    if ((b.type === 'come' || b.type === 'dontcome') && b.num == null) bad.push(tag + ': still in the come box after the roll');
  });
  return bad;
}
var srng = CE.seeded(7), T = g.Table({ seed: 11, bankroll: 1e9 }), ROLLS = 1000000, ls = 0, ls2 = 0, placed = 0, removed = 0,
    audits = 0, illegal = [];
function pick(a) { return a[Math.floor(srng() * a.length)]; }
for (var r = 0; r < ROLLS; r++) {
  for (var tries = 0; tries < 2; tries++) {
    var c = pick(g.catalogue), spec;
    if (c.type === 'odds' || c.type === 'layodds') {
      var want = c.type === 'odds' ? ['pass', 'come'] : ['dontpass', 'dontcome'];
      var parents = T.bets.filter(function (b) { return want.indexOf(b.type) >= 0 && b.num != null; });
      if (!parents.length) continue;
      var p = pick(parents), u = g.unit(c.type, p.num);
      spec = { type: c.type, parent: p.id, amount: u * (1 + Math.floor(srng() * 6)) };
    } else spec = { type: c.type, num: c.num, amount: c.min + c.unit * Math.floor(srng() * 4) };
    if (T.place(spec).ok) placed++;
  }
  if (srng() < 0.05 && T.bets.length) { var b = pick(T.bets); if (T.removable(b) && T.remove(b.id).ok) removed++; }
  var res = T.roll(); ls += res.luck; ls2 += res.luck * res.luck;
  var wrong = audit(T); audits++;
  if (wrong.length && illegal.length < 5) illegal.push('roll ' + r + ': ' + wrong.join('; '));
}
var L = T.ledger, luck = L.luckComeOut + L.luckPoint, open = T.openValue();
var ident = L.actual + open - (L.expected + luck), bal = T.bank + T.onFelt() - (1e9 + L.actual);
var mean = ls / ROLLS, sd = Math.sqrt(ls2 / ROLLS - mean * mean), zl = mean / (sd / Math.sqrt(ROLLS));
var sumExp = 0, sumAct = 0; Object.keys(L.byKey).forEach(function (k) { sumExp += L.byKey[k].expected; sumAct += L.byKey[k].actual; });
console.log('\n5. Session: ' + ROLLS.toLocaleString('en-US') + ' rolls, ' + placed.toLocaleString('en-US') + ' bets placed or pressed, ' + removed.toLocaleString('en-US') + ' taken down');
console.log('   wagered $' + Math.round(L.wagered).toLocaleString('en-US') + ' · expected $' + L.expected.toFixed(2) + ' · actual $' + L.actual.toFixed(2) +
            ' · luck $' + luck.toFixed(2) + ' (come-out $' + L.luckComeOut.toFixed(2) + ', point $' + L.luckPoint.toFixed(2) + ') · still on felt: value $' + open.toFixed(2));
console.log('   actual + open value - (expected + luck) = ' + ident.toExponential(2));
console.log('   bankroll + chips on felt - (start + actual) = ' + bal.toExponential(2));
console.log('   recap rows sum to ledger: expected ' + (sumExp - L.expected).toExponential(2) + ', actual ' + (sumAct - L.actual).toExponential(2));
console.log('   luck per roll: mean $' + mean.toFixed(4) + ', sd $' + sd.toFixed(2) + ', z = ' + zl.toFixed(2));
ok(Math.abs(ident) < 1e-6 * Math.max(1, L.wagered / 1e6), 'identity actual + open = expected + luck: ' + ident);
ok(Math.abs(bal) < 1e-3, 'bankroll balance ' + bal);
ok(Math.abs(sumExp - L.expected) < 1e-3 && Math.abs(sumAct - L.actual) < 1e-3, 'recap sums');
ok(Math.abs(zl) < 3.29, 'luck mean z ' + zl);
console.log('   felt audited after every roll (' + audits.toLocaleString('en-US') + ' times): ' + (illegal.length ? 'ILLEGAL BETS FOUND' : 'every bet legal'));
illegal.forEach(function (x) { ok(false, x); });

/* ---------- 6. the table refuses every illegal bet ---------- */
function refuses(setup, spec, why) {
  var X = g.Table({ seed: 3, bankroll: 1e6 }); setup(X);
  var before = X.bets.length, bank = X.bank, r = X.place(spec);
  return ok(!r.ok && X.bets.length === before && X.bank === bank, 'should refuse: ' + why + (r.ok ? ' (it was booked)' : ''));
}
function withPoint(X, n) { X.place({ type: 'pass', amount: 10 }); X.place({ type: 'dontpass', amount: 10 }); X.roll(n === 4 ? 1 : 2, n - (n === 4 ? 1 : 2)); }
var pass = function (X) { return X.bets.filter(function (b) { return b.type === 'pass'; })[0]; };
var dont = function (X) { return X.bets.filter(function (b) { return b.type === 'dontpass'; })[0]; };
var none = function () {}, pt6 = function (X) { withPoint(X, 6); }, pt5 = function (X) { withPoint(X, 5); };
var CASES = [
  [none, { type: 'pass', amount: 5 }, 'a line bet under the $10 minimum'],
  [none, { type: 'pass', amount: 10.5 }, 'a bet in part-dollars'],
  [none, { type: 'come', amount: 10 }, 'a come bet on the come-out'],
  [none, { type: 'dontcome', amount: 10 }, 'a don’t come bet on the come-out'],
  [pt6, { type: 'pass', amount: 10 }, 'a pass line bet after the point is set (a put bet)'],
  [pt6, { type: 'dontpass', amount: 10 }, 'adding to don’t pass after the point is set'],
  [none, { type: 'odds', parent: 1, amount: 10 }, 'odds with no point'],
  [pt6, { type: 'odds', parent: 1, amount: 55 }, 'odds over 5x on the 6 behind $10'],
  [pt5, { type: 'odds', parent: 1, amount: 39 }, 'odds on the 5 in an odd amount (3:2 needs $2 units)'],
  [pt6, { type: 'odds', parent: 1, amount: 12 }, 'odds on the 6 not in $5 units'],
  [pt6, { type: 'layodds', parent: 1, amount: 12 }, 'lay odds behind the pass line'],
  [pt6, { type: 'odds', parent: 2, amount: 10 }, 'take odds behind don’t pass'],
  [pt6, { type: 'layodds', parent: 2, amount: 66 }, 'lay odds on the 6 over the 6x-to-win limit behind $10'],
  [none, { type: 'place', num: 6, amount: 10 }, 'place 6 not in $6 units'],
  [none, { type: 'place', num: 6, amount: 6 }, 'place 6 under the table minimum ($12 at a $10 table)'],
  [none, { type: 'place', num: 7, amount: 10 }, 'a place bet on the 7'],
  [none, { type: 'buy', num: 4, amount: 25 }, 'a buy bet that is not a multiple of $20'],
  [none, { type: 'lay', num: 4, amount: 30 }, 'a lay on the 4 that is not a multiple of $40'],
  [none, { type: 'hard', num: 5, amount: 5 }, 'a hard 5'],
  [none, { type: 'horn', amount: 5 }, 'a horn bet not in $4 units'],
  [none, { type: 'field', amount: 5 }, 'a field bet under the minimum'],
  [none, { type: 'pass', amount: 510 }, 'a pass line bet over the $500 table maximum'],
  [none, { type: 'place', num: 6, amount: 504 }, 'place 6 over the maximum ($498 in $6 units at a $500 table)'],
  [function (X) { X.place({ type: 'field', amount: 500 }); }, { type: 'field', amount: 1 }, 'pressing a field bet past the maximum'],
];
var refused = 0; CASES.forEach(function (c) { if (refuses(c[0], c[1], c[2])) refused++; });
var X = g.Table({ seed: 3, bankroll: 1e6 }); withPoint(X, 6);
var contract = !X.remove(pass(X).id).ok, dontOff = X.remove(dont(X).id).ok;
ok(contract, 'should refuse: taking down a pass line bet with a point');
ok(dontOff, 'a don’t pass bet may be taken down');
var legal = [[pt6, { type: 'odds', parent: 1, amount: 50 }], [pt6, { type: 'layodds', parent: 2, amount: 60 }], [pt5, { type: 'odds', parent: 1, amount: 40 }],
             [pt6, { type: 'come', amount: 10 }], [none, { type: 'place', num: 6, amount: 12 }], [none, { type: 'buy', num: 4, amount: 20 }],
             [none, { type: 'lay', num: 4, amount: 40 }], [none, { type: 'hard', num: 8, amount: 1 }], [none, { type: 'horn', amount: 4 }],
             [function (X) { X.place({ type: 'place', num: 8, amount: 12 }); }, { type: 'buy', num: 8, amount: 20 }],   // placed and bought (Oki: allowed)
             [none, { type: 'place', num: 6, amount: 498 }],
             [function (X) { X.place({ type: 'pass', amount: 500 }); X.roll(2, 4); }, { type: 'odds', parent: 1, amount: 2500 }]];   // odds past the table max
var booked = 0; legal.forEach(function (c) { var Y = g.Table({ seed: 3, bankroll: 1e6 }); c[0](Y); if (ok(Y.place(c[1]).ok, 'should book: ' + JSON.stringify(c[1]))) booked++; });
console.log('\n6. Table rules: ' + refused + ' of ' + CASES.length + ' illegal bets refused, pass line with a point stays up: ' + (contract ? 'yes' : 'NO') +
            '; ' + booked + ' of ' + legal.length + ' legal bets booked (full 3-4-5x odds, lay to 6x, $12 place 6, $20 buy, $40 lay, $1 hard 8, $4 horn, place and buy on one number, $498 place 6, $2,500 odds behind a $500 pass)');

console.log('\n' + (fails ? 'FAILED: ' + fails + ' check(s)' : 'ALL CHECKS PASS'));
process.exit(fails ? 1 : 0);
