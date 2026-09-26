/* Checks tables/sim/games.js, the outcome tables behind every Tables variance simulator.
   Run from the repo root:  node tables/checks/games_check.js      (exit 1 on any failure)

   For every bet of every game:
   1. every row probability is in (0, 1], and an exact table's rows sum to 1 (approximate tables are
      normalised by ttg-sim.js by design: the variant shapes add rows on top of a base shape);
   2. the edge ttg-sim.js simulates (after its own normalise/calibrate, bonus rows included) is within
      0.01 percentage point of the published edge. Published edges are rounded, and the video-poker
      short-pay tables reuse the 9/6 frequencies (games.js says so), which moves them by a few thousandths
      of a point; a wrong row moves the edge much further.
   KNOWN lists tables that fail a check for a documented reason; they are printed, not failed.
   The craps bets have their own, stricter check: tables/checks/craps_engine_check.js. */
'use strict';
var fs = require('fs'), path = require('path'), vm = require('vm');
var ROOT = path.join(__dirname, '..', '..');

var ctx = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'tables/sim/games.js'), 'utf8'), ctx);
vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'tables/sim/ttg-sim.js'), 'utf8'), ctx);
var GAMES = ctx.window.TTG_GAMES, SIM = ctx.window.TTGSim;

var EDGE_TOL = 1e-4, EXACT_SUM_TOL = 1e-9;
var TRIPS = 'labelled exact but its frequencies are rounded (rows sum to 1.0000913) and it has no published edge to check';
var KNOWN = { 'ultimate-texas-holdem/trips-9743': TRIPS, 'ultimate-texas-holdem/trips-8653': TRIPS,
              'ultimate-texas-holdem/trips-9733': TRIPS };
var failures = [], known = [], checked = 0;

Object.keys(GAMES).forEach(function (gid) {
  var bets = GAMES[gid].bets;
  Object.keys(bets).forEach(function (bid) {
    var bet = bets[bid], name = gid + '/' + bid, sum = 0, problems = [];
    checked++;
    bet.rows.forEach(function (r) {
      if (!(r.p > 0 && r.p <= 1)) problems.push('row probability ' + r.p + ' outside (0, 1]');
      sum += r.p;
    });
    if (bet.kind === 'exact' && Math.abs(sum - 1) > EXACT_SUM_TOL) problems.push('rows sum to ' + sum.toFixed(10));
    if (typeof bet.edge !== 'number') problems.push('no published edge');
    else {
      var prep = SIM.prepare(bet);
      if (Math.abs(prep.edge - bet.edge) > EDGE_TOL)
        problems.push('simulated edge ' + (prep.edge * 100).toFixed(4) + '% vs published ' + (bet.edge * 100).toFixed(4) + '%');
    }
    if (!problems.length) return;
    if (KNOWN[name]) known.push(name + ': ' + KNOWN[name]);
    else failures.push(name + ' (' + bet.kind + '): ' + problems.join('; '));
  });
});

console.log(checked + ' bets in ' + Object.keys(GAMES).length + ' games checked');
known.forEach(function (k) { console.log('  KNOWN ' + k); });
if (failures.length) { failures.forEach(function (f) { console.log('  FAIL ' + f); }); process.exit(1); }
console.log('ALL CHECKS PASS');
