/* The Tilted Gent — house-edge colour bands for the Tables trainers, in one place. Vanilla JS, no dependencies; runs in
   the browser (window.TtgEdgeBands, loaded before the engines) and in Node (module.exports, required by the engines).
   A house edge e (a fraction, 0.0106 = 1.06%) gets the class
     'up' (green)  when e <  lo
     'au' (gold)   when lo <= e < hi
     'dn' (red)    when e >= hi
   with [lo, hi] set per game below. The colours are the game pages' (.up / .au / .dn in tables/tables.css and each
   trainer stylesheet).
   The standard is the published house-edge table on each game page (tables/craps.html, baccarat.html,
   three-card-poker.html, generated from tables/_source/casino-games-source.html, where every row's class is set by
   hand). Those pages grade each game on its own scale, so no single site-wide [lo, hi] reproduces them:
     craps.html   Place 5 or 9 at 4.00% is gold, but three-card-poker.html Ante & Play 4-3-1 at 3.83% is red;
     craps.html   Buy 4 or 10 at 1.67% is green, but three-card-poker.html Pair Plus 40-33-6-4-1 at 1.61% is gold.
   Each game's [lo, hi] is therefore chosen inside the range its own page allows (Oki, 8 Oct 2026: "Keep rules, match
   colours"):
     craps     lo in (1.67%, 2.44%], hi in (4.00%, 5.56%]   -> 2% / 5%    (the trainers' scale before 8 Oct 2026)
     baccarat  lo in (1.24%, 4.84%], hi in (1.24%, 4.84%]   -> 2% / 4%    (Tie 9:1 at 4.84% is red on the page)
     tcp       lo in (0, 1.61%],     hi in (3.37%, 3.83%]   -> 1.5% / 3.5% (Pair Plus 40-33-6-4-1 at 1.61% gold; 4-3-1 red)
   tables/checks/{craps,baccarat,tcp}_engine_check.js fail when any row of the page's house-edge table has a class other
   than this band of the engine's exact edge for that bet, so the page and the trainer cannot drift apart again. */
(function (root) {
  'use strict';
  var BANDS = { craps: [0.02, 0.05], baccarat: [0.02, 0.04], tcp: [0.015, 0.035] };

  function band(game, e) {
    var b = BANDS[game];
    if (!b) throw new Error('no edge bands for ' + game);
    return e < b[0] ? 'up' : e < b[1] ? 'au' : 'dn';
  }
  function num(x) { return String(+(100 * x).toFixed(2)); }        // 0.015 -> '1.5', 0.02 -> '2'
  /* The key printed under each trainer's price list: Under 2% · 2–5% · 5% and up. */
  function legend(game) {
    var b = BANDS[game];
    return '<span class="band up">Under ' + num(b[0]) + '%</span> <span class="band au">' + num(b[0]) + '–' + num(b[1]) +
           '%</span> <span class="band dn">' + num(b[1]) + '% and up</span>';
  }

  var API = { BANDS: BANDS, band: band, legend: legend };
  if (typeof module !== 'undefined' && module.exports) module.exports = API; else root.TtgEdgeBands = API;
})(typeof window !== 'undefined' ? window : this);
