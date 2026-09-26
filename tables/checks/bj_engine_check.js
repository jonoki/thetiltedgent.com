/* Checks the Blackjack Trainer's engine, tables/sim/bj-trainer.js: the generated basic-strategy chart, the
   expected-value engine behind the Edge tab, and the two against each other.
   Run from the repo root:  node tables/checks/bj_engine_check.js      (exit 1 on any failure)

   No published figure is hard-coded here. The checks are textbook chart cells, the directions every
   blackjack reference agrees on (H17 costs the player, DAS and surrender help, a higher count lowers the
   house edge), the insurance index the trainer itself teaches, and consistency: at a true count of 0 the
   chart's hard-total play must be the engine's best play, or within MARGIN of it. The chart is for a
   multi-deck shoe and the engine is infinite-deck, so near-ties can fall either way. */
'use strict';
var fs = require('fs'), path = require('path'), vm = require('vm');
var ROOT = path.join(__dirname, '..', '..');
var ctx = { window: {}, Date: Date, Math: Math, JSON: JSON };
vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'tables/sim/bj-trainer.js'), 'utf8'), ctx);
var BJT = ctx.window.BJT;

var SHOE = { decks: 6, h17: true, das: true, surrender: false, penetration: 0.75 };
var MARGIN = 0.02;   // units of the bet: a chart play this close to the engine's best counts as agreeing
var failures = [], checks = 0;
function check(ok, what) { checks++; if (!ok) failures.push(what); }
function rules(over) { var r = {}, k; for (k in SHOE) r[k] = SHOE[k]; for (k in over) r[k] = over[k]; return r; }

// 1. textbook cells of the generated chart (6 decks, H17, DAS, no surrender); up cards 2..10, 11 = ace
var T = BJT.basicStrategy(SHOE);
[['h16', 10, 'H'], ['h12', 4, 'S'], ['h12', 3, 'H'], ['h13', 2, 'S'], ['h11', 6, 'D'], ['h10', 10, 'H'],
 ['h9', 3, 'D'], ['h17', 11, 'S'], ['s18', 9, 'H'], ['s18', 7, 'S'], ['s17', 2, 'H'], ['pA', 11, 'P'],
 ['p8', 10, 'P'], ['p10', 6, 'S'], ['p9', 7, 'S'], ['p5', 9, 'D']].forEach(function (c) {
  check(T[c[0]][c[1]] === c[2], 'chart ' + c[0] + ' v ' + c[1] + ': ' + T[c[0]][c[1]] + ', textbook ' + c[2]);
});
var TS = BJT.basicStrategy(rules({ surrender: true }));
check(TS.h16[10] === 'R' && TS.h15[10] === 'R', 'chart with surrender: 16 v 10 and 15 v 10 surrender');

// 2. the chart's hard-total plays are the engine's best plays at TC 0, or within MARGIN
var eng = BJT.evEngine(SHOE, 0), CODE = { H: 'H', S: 'S', D: 'D', Ds: 'D' };
for (var t = 5; t <= 20; t++) for (var up = 2; up <= 11; up++) {
  var evs = eng.actions(t, false, up, { double: true, split: false, surrender: false }, 0), best = -9, k;
  for (k in evs) if (evs[k] > best) best = evs[k];
  var play = CODE[T['h' + t][up]];
  check(play in evs && best - evs[play] <= MARGIN,
        'hard ' + t + ' v ' + up + ': chart ' + T['h' + t][up] + ' is ' + (best - (evs[play] || -9)).toFixed(4) + ' below the best play');
}

// 3. directions every reference agrees on
function edge(over, tc) { return BJT.evEngine(rules(over || {}), tc || 0).baseEdge; }
var base = edge();
check(base > 0 && base < 0.02, 'house edge at TC 0 should be a small positive number, got ' + base);
check(edge({ h17: false }) < base, 'standing on soft 17 should cost the house');
check(edge({ das: false }) > base, 'no double after split should help the house');
check(edge({ surrender: true }) < base, 'late surrender should cost the house');
for (var tc = -4; tc < 6; tc++) check(edge({}, tc + 1) < edge({}, tc), 'house edge should fall from TC ' + tc + ' to ' + (tc + 1));
check(eng.startEv(11, 10, 6) === 1.5, 'a blackjack against a 6 pays exactly 1.5, got ' + eng.startEv(11, 10, 6));

// 4. insurance turns favourable where the trainer's index says (INDEX 'ins')
var ins = BJT.INDEX.filter(function (x) { return x.k === 'ins'; })[0].idx;
check(BJT.evEngine(SHOE, ins - 1).insuranceEv < 0, 'insurance should lose one count below its index (TC ' + (ins - 1) + ')');
check(BJT.evEngine(SHOE, ins + 1).insuranceEv > 0, 'insurance should win one count above its index (TC ' + (ins + 1) + ')');

console.log(checks + ' checks; house edge at TC 0 (6 decks, H17, DAS) ' + (base * 100).toFixed(2) + '%');
if (failures.length) { failures.forEach(function (f) { console.log('  FAIL ' + f); }); process.exit(1); }
console.log('ALL CHECKS PASS');
