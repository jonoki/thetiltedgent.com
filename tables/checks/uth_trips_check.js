/* Derives the 7-card best-five-hand counts behind the Ultimate Texas Hold'em Trips tables in
   tables/sim/games.js, and checks those tables against them.
   Run from the repo root:  node tables/checks/uth_trips_check.js          (exit 1 on any failure)
                            node tables/checks/uth_trips_check.js --brute  (also enumerates all
                            C(52,7) = 133,784,560 hands one by one as a second derivation; ~1 min)

   Combinatorial derivation (the default, well under a second):
   - Walk every rank multiset of 7 cards (count n_r in 0..4 for each of the 13 ranks, sum 7).
     Its suit assignments number  prod_r C(4, n_r).
   - A flush needs 5+ cards of one suit, and 7 cards hold at most one such suit. For a suit s and a
     set S of the multiset's distinct ranks with |S| >= 5, the assignments in which s holds exactly
     the ranks S number  prod_{r in S} C(3, n_r - 1) * prod_{r present, not in S} C(3, n_r)
     (rank r in S: one card is suit s, the other n_r - 1 come from the other three suits; rank r not
     in S: all n_r from the other three). Times 4 suits. S is a royal flush when it holds T-J-Q-K-A,
     else a straight flush when it holds five consecutive ranks (A-2-3-4-5 counts), else a flush.
   - No 7-card hand holds both a flush and quads or a full house (each would need 8+ cards), so a
     flush assignment is always graded by its suit; every other assignment is graded by ranks alone:
     quads > full house (trips + another pair or trips) > straight > three of a kind > two pair >
     pair > high card.
   Trips pays on the player's final 7-card hand: three of a kind or better wins, anything else loses
   the bet. Edge = -(sum over rows of p * x), with p = count / C(52,7).
   Reference for the counts: the standard 7-card poker hand table (e.g. Wikipedia, "Poker
   probability", 7-card hands): royal 4,324; straight flush 37,260; quads 224,848; full house
   3,473,184; flush 4,047,644; straight 6,180,020; trips 6,461,620; two pair 31,433,400;
   pair 58,627,800; high card 23,294,460. This script derives them; it does not read them. */
'use strict';
var fs = require('fs'), path = require('path'), vm = require('vm');
var ROOT = path.join(__dirname, '..', '..');

var CATS = ['royal', 'sf', 'quads', 'fh', 'flush', 'straight', 'trips', 'twopair', 'pair', 'high'];
var C = function (n, k) { if (k < 0 || k > n) return 0; var r = 1; for (var i = 0; i < k; i++) r = r * (n - i) / (i + 1); return r; };
var N = C(52, 7);

// Rank i = 0..12 for 2..A. Straight masks: A-2-3-4-5 and the nine runs from 2-6 to T-A.
var STRAIGHTS = [(1 << 12) | 0xF];
for (var lo = 0; lo <= 8; lo++) STRAIGHTS.push(0x1F << lo);
var ROYAL = 0x1F << 8;
function hasStraight(mask) { for (var i = 0; i < STRAIGHTS.length; i++) if ((mask & STRAIGHTS[i]) === STRAIGHTS[i]) return true; return false; }
function suitCat(mask) { return (mask & ROYAL) === ROYAL ? 'royal' : hasStraight(mask) ? 'sf' : 'flush'; }
function rankCat(n) {
  var four = 0, three = 0, two = 0, mask = 0;
  for (var r = 0; r < 13; r++) {
    if (n[r]) mask |= 1 << r;
    if (n[r] === 4) four++; else if (n[r] === 3) three++; else if (n[r] === 2) two++;
  }
  if (four) return 'quads';
  if (three >= 2 || (three && two)) return 'fh';
  if (hasStraight(mask)) return 'straight';
  if (three) return 'trips';
  if (two >= 2) return 'twopair';
  if (two) return 'pair';
  return 'high';
}

function derive() {
  var count = {}; CATS.forEach(function (c) { count[c] = 0; });
  var n = new Array(13).fill(0);
  (function walk(r, left) {
    if (r === 13) {
      if (left) return;
      var ways = 1, present = [];
      for (var i = 0; i < 13; i++) { ways *= C(4, n[i]); if (n[i]) present.push(i); }
      var flushWays = 0, k = present.length;
      if (k >= 5) for (var sub = 0; sub < (1 << k); sub++) {
        var bits = 0, w = 1, mask = 0;
        for (var j = 0; j < k; j++) {
          var nr = n[present[j]];
          if (sub & (1 << j)) { bits++; mask |= 1 << present[j]; w *= C(3, nr - 1); } else w *= C(3, nr);
        }
        if (bits < 5 || !w) continue;
        count[suitCat(mask)] += 4 * w;
        flushWays += 4 * w;
      }
      count[rankCat(n)] += ways - flushWays;
      return;
    }
    for (var c = 0; c <= Math.min(4, left); c++) { n[r] = c; walk(r + 1, left - c); }
    n[r] = 0;
  })(0, 7);
  return count;
}

// Second derivation: every 7-card hand, one at a time. Card id = 4 * rank + suit.
function brute() {
  var count = {}; CATS.forEach(function (c) { count[c] = 0; });
  var n = new Array(13).fill(0), sm = [0, 0, 0, 0], sc = [0, 0, 0, 0], h = [];
  function add(id, d) { var r = id >> 2, s = id & 3; n[r] += d; sc[s] += d; sm[s] ^= 1 << r; }
  (function pick(start, depth) {
    if (depth === 7) {
      for (var s = 0; s < 4; s++) if (sc[s] >= 5) {
        // a 7-card flush hand never holds quads or a full house (see above)
        count[suitCat(sm[s])]++; return;
      }
      count[rankCat(n)]++; return;
    }
    for (var id = start; id <= 52 - (7 - depth); id++) { add(id, 1); pick(id + 1, depth + 1); add(id, -1); }
  })(0, 0);
  return count;
}

var failures = [];
var derived = derive(), total = 0;
CATS.forEach(function (c) { total += derived[c]; });
console.log('7-card best-five-hand counts (derived):');
CATS.forEach(function (c) { console.log('  ' + (c + '         ').slice(0, 9) + ' ' + derived[c].toLocaleString('en-US')); });
console.log('  total     ' + total.toLocaleString('en-US') + '  (C(52,7) = ' + N.toLocaleString('en-US') + ')');
if (total !== N) failures.push('counts sum to ' + total + ', not C(52,7) = ' + N);

if (process.argv.indexOf('--brute') >= 0) {
  var b = brute();
  CATS.forEach(function (c) { if (b[c] !== derived[c]) failures.push('brute-force ' + c + ' ' + b[c] + ' vs combinatorial ' + derived[c]); });
  console.log('brute-force enumeration of all ' + N.toLocaleString('en-US') + ' hands: ' + (failures.length ? 'MISMATCH' : 'identical counts'));
}

// games.js: every Trips table must be exactly these counts over C(52,7), with its edge field matching.
var ctx = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'tables/sim/games.js'), 'utf8'), ctx);
var bets = ctx.window.TTG_GAMES['ultimate-texas-holdem'].bets, seen = 0;
var WIN = ['royal', 'sf', 'quads', 'fh', 'flush', 'straight', 'trips'], LOSS = derived.twopair + derived.pair + derived.high;
Object.keys(bets).filter(function (id) { return /^trips-/.test(id); }).forEach(function (id) {
  var bet = bets[id], rows = bet.rows, ev = 0;
  seen++;
  if (bet.kind !== 'exact') failures.push(id + ': kind ' + bet.kind + ', expected exact');
  if (rows.length !== 8) { failures.push(id + ': ' + rows.length + ' rows, expected 8'); return; }
  WIN.forEach(function (c, i) {
    if (rows[i].p !== derived[c] / N) failures.push(id + ' row ' + i + ' (' + c + '): p ' + rows[i].p + ' vs ' + derived[c] + '/' + N);
    ev += derived[c] * rows[i].x;
  });
  if (rows[7].p !== LOSS / N || rows[7].x !== -1) failures.push(id + ' loss row: ' + JSON.stringify(rows[7]) + ' vs p ' + LOSS + '/' + N + ', x -1');
  ev = (ev - LOSS) / N;
  var pays = rows.slice(0, 7).map(function (r) { return r.x; }).join('-');
  console.log('  ' + id + ' (' + pays + '): exact edge ' + (-ev * 100).toFixed(4) + '%, games.js edge ' + (bet.edge * 100).toFixed(4) + '%');
  if (typeof bet.edge !== 'number' || Math.abs(bet.edge + ev) > 5e-6) failures.push(id + ': edge field ' + bet.edge + ' vs exact ' + (-ev));
});
if (!seen) failures.push('no Trips tables found in games.js');

if (failures.length) { failures.forEach(function (f) { console.log('  FAIL ' + f); }); process.exit(1); }
console.log('ALL CHECKS PASS (' + seen + ' Trips tables)');
