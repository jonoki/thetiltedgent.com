/* The Tilted Gent — outcome tables for the variance simulator.
   Every bet is a paytable: rows of {p, x} — probability p of a net result x, in units of the
   base bet (1 unit = the amount you put down first). Rows must sum to 1.
   kind: "exact"  — probabilities from the game's combinatorics (source noted);
         "approx" — a plausible outcome shape calibrated so its EV equals the published house
                    edge and its standard deviation matches the published figure. Approximate
                    tables are labelled as such in the UI.
   Per-bet edges are the standard published figures (Wizard of Odds, fetched Sep 2026).
   Note: for compound bets (pass + odds, ante/play, UTH) "unit" is the FIRST bet; the money at
   risk per round is larger, and `avgWager` says by how much. */
window.TTG_GAMES = (function () {
  var G = {};

  /* ---------- CRAPS (per bet resolved) ---------- */
  G.craps = {
    name: "Craps", pace: 30, paceNote: "line bets resolved per hour at a moderately busy table (~100 rolls)",
    unit: 10, defaultBet: "pass-odds-345",
    bets: {
      "pass-odds-345": { name: "Pass line + 3-4-5x odds", edge: 0.01414, edgeNote: "1.41% of the line bet; 0.37% of all money wagered", kind: "exact", avgWager: 3.78,
        rows: [ {p: 8/36, x: 1}, {p: 4/36, x: -1},
                {p: 6/36 * 1/3, x: 7}, {p: 6/36 * 2/3, x: -4},
                {p: 8/36 * 2/5, x: 7}, {p: 8/36 * 3/5, x: -5},
                {p: 10/36 * 5/11, x: 7}, {p: 10/36 * 6/11, x: -6} ] },
      "pass": { name: "Pass line (no odds)", edge: 0.01414, kind: "exact",
        rows: [ {p: 244/495, x: 1}, {p: 251/495, x: -1} ] },
      "dont-pass": { name: "Don't pass", edge: 0.01364, kind: "exact",
        rows: [ {p: 949/1980, x: 1}, {p: 976/1980, x: -1}, {p: 55/1980, x: 0} ] },
      "place-6-8": { name: "Place 6 or 8", edge: 0.01515, kind: "exact",
        rows: [ {p: 5/11, x: 7/6}, {p: 6/11, x: -1} ] },
      "place-5-9": { name: "Place 5 or 9", edge: 0.04, kind: "exact",
        rows: [ {p: 4/10, x: 1.4}, {p: 6/10, x: -1} ] },
      "place-4-10": { name: "Place 4 or 10", edge: 0.0667, kind: "exact",
        rows: [ {p: 1/3, x: 1.8}, {p: 2/3, x: -1} ] },
      "field-3x": { name: "Field (2x on 2, 3x on 12)", edge: 0.0278, kind: "exact",
        rows: [ {p: 1/36, x: 2}, {p: 1/36, x: 3}, {p: 14/36, x: 1}, {p: 20/36, x: -1} ] },
      "field-2x": { name: "Field (2x on 2 and 12)", edge: 0.0556, kind: "exact",
        rows: [ {p: 2/36, x: 2}, {p: 14/36, x: 1}, {p: 20/36, x: -1} ] },
      "hard-6-8": { name: "Hard 6 / Hard 8", edge: 0.0909, kind: "exact",
        rows: [ {p: 1/11, x: 9}, {p: 10/11, x: -1} ] },
      "big-6-8": { name: "Big 6 / Big 8", edge: 0.0909, kind: "exact",
        rows: [ {p: 5/11, x: 1}, {p: 6/11, x: -1} ] },
      "hard-4-10": { name: "Hard 4 / Hard 10", edge: 0.1111, kind: "exact",
        rows: [ {p: 1/9, x: 7}, {p: 8/9, x: -1} ] },
      "any-craps": { name: "Any craps", edge: 0.1111, kind: "exact",
        rows: [ {p: 4/36, x: 7}, {p: 32/36, x: -1} ] },
      "3-or-11": { name: "3 or 11 (15:1)", edge: 0.1111, kind: "exact",
        rows: [ {p: 2/36, x: 15}, {p: 34/36, x: -1} ] },
      "2-or-12": { name: "2 or 12 (30:1)", edge: 0.1389, kind: "exact",
        rows: [ {p: 1/36, x: 30}, {p: 35/36, x: -1} ] },
      "any-seven": { name: "Any seven", edge: 0.1667, kind: "exact",
        rows: [ {p: 1/6, x: 4}, {p: 5/6, x: -1} ] }
    }
  };

  /* ---------- ROULETTE (per spin) ---------- */
  function wheel(pockets, label) {
    var n = pockets;
    return {
      "even": { name: label + " — even money (red/black, odd/even, high/low)", edge: (n - 36) / n, kind: "exact",
        rows: [ {p: 18/n, x: 1}, {p: (n - 18)/n, x: -1} ] },
      "dozen": { name: label + " — dozen / column (2:1)", edge: (n - 36) / n, kind: "exact",
        rows: [ {p: 12/n, x: 2}, {p: (n - 12)/n, x: -1} ] },
      "corner": { name: label + " — corner (8:1)", edge: (n - 36) / n, kind: "exact",
        rows: [ {p: 4/n, x: 8}, {p: (n - 4)/n, x: -1} ] },
      "split": { name: label + " — split (17:1)", edge: (n - 36) / n, kind: "exact",
        rows: [ {p: 2/n, x: 17}, {p: (n - 2)/n, x: -1} ] },
      "straight": { name: label + " — straight up (35:1)", edge: (n - 36) / n, kind: "exact",
        rows: [ {p: 1/n, x: 35}, {p: (n - 1)/n, x: -1} ] }
    };
  }
  var r0 = wheel(37, "Single zero"), r00 = wheel(38, "Double zero"), r000 = wheel(39, "Triple zero");
  G.roulette = {
    name: "Roulette", pace: 40, paceNote: "spins per hour at a live table (electronic wheels run 60–80)",
    unit: 10, defaultBet: "00-even",
    bets: {
      "0-even-partage": { name: "Single zero, la partage — even money", edge: 0.0135, kind: "exact",
        rows: [ {p: 18/37, x: 1}, {p: 18/37, x: -1}, {p: 1/37, x: -0.5} ] },
      "0-even": r0.even, "0-dozen": r0.dozen, "0-corner": r0.corner, "0-split": r0.split, "0-straight": r0.straight,
      "00-even": r00.even, "00-dozen": r00.dozen, "00-corner": r00.corner, "00-split": r00.split, "00-straight": r00.straight,
      "00-five": { name: "Double zero — five-number bet (6:1)", edge: 0.0789, kind: "exact",
        rows: [ {p: 5/38, x: 6}, {p: 33/38, x: -1} ] },
      "000-even": r000.even, "000-straight": r000.straight
    }
  };

  /* ---------- BACCARAT (8 decks, per hand) ---------- */
  var pB = 0.458597, pP = 0.446247, pT = 0.095156; // Wizard of Odds, 8 decks
  G.baccarat = {
    name: "Baccarat", pace: 70, paceNote: "hands per hour at a full big table (mini-bacc runs 120–150)",
    unit: 25, defaultBet: "banker",
    bets: {
      "banker": { name: "Banker (5% commission)", edge: 0.0106, kind: "exact",
        rows: [ {p: pB, x: 0.95}, {p: pP, x: -1}, {p: pT, x: 0} ] },
      "player": { name: "Player", edge: 0.0124, kind: "exact",
        rows: [ {p: pP, x: 1}, {p: pB, x: -1}, {p: pT, x: 0} ] },
      "tie-9": { name: "Tie at 9:1", edge: 0.0484, kind: "exact",
        rows: [ {p: pT, x: 9}, {p: 1 - pT, x: -1} ] },
      "tie-8": { name: "Tie at 8:1", edge: 0.1436, kind: "exact",
        rows: [ {p: pT, x: 8}, {p: 1 - pT, x: -1} ] },
      "pair": { name: "Player / Banker pair (11:1)", edge: 0.1036, kind: "exact",
        rows: [ {p: 0.074699, x: 11}, {p: 0.925301, x: -1} ] }
    }
  };

  /* ---------- VIDEO POKER (per hand, unit = the full 5-coin bet) ---------- */
  // Jacks or Better hand frequencies under optimal 9/6 strategy (Wizard of Odds).
  var jobF = { royal: 0.0000248, sf: 0.000109, quads: 0.002363, fh: 0.011512, fl: 0.011015, st: 0.011229, trips: 0.074449, twopair: 0.129279, jacks: 0.214585 };
  function jobRows(fh, fl) {
    var f = jobF, none = 1 - (f.royal + f.sf + f.quads + f.fh + f.fl + f.st + f.trips + f.twopair + f.jacks);
    return [ {p: f.royal, x: 799}, {p: f.sf, x: 49}, {p: f.quads, x: 24}, {p: f.fh, x: fh - 1}, {p: f.fl, x: fl - 1},
             {p: f.st, x: 3}, {p: f.trips, x: 2}, {p: f.twopair, x: 1}, {p: f.jacks, x: 0}, {p: none, x: -1} ];
  }
  G["video-poker"] = {
    name: "Video Poker", pace: 500, paceNote: "hands per hour at a steady pace (fast players hit 800+)",
    unit: 1.25, defaultBet: "job-96",
    bets: {
      "job-96": { name: "Jacks or Better 9/6 (full pay)", edge: 0.0046, kind: "exact", rows: jobRows(9, 6) },
      "job-95": { name: "Jacks or Better 9/5", edge: 0.0155, kind: "exact", rows: jobRows(9, 5) },
      "job-86": { name: "Jacks or Better 8/6", edge: 0.0161, kind: "exact", rows: jobRows(8, 6) },
      "job-85": { name: "Jacks or Better 8/5", edge: 0.0270, kind: "exact", rows: jobRows(8, 5) },
      "job-75": { name: "Jacks or Better 7/5", edge: 0.0385, kind: "exact", rows: jobRows(7, 5) },
      "job-65": { name: "Jacks or Better 6/5", edge: 0.0500, kind: "exact", rows: jobRows(6, 5) }
    },
    note: "Frequencies are for optimal 9/6 strategy; the short-pay tables reuse them, which understates their edge by a few hundredths of a percent."
  };

  /* ---------- THREE CARD POKER ---------- */
  // Pair Plus is exact (22,100 three-card hands). Ante/Play is an approximate shape calibrated to 3.37%.
  var T = 22100;
  function pairPlus(sf, tk, st, fl, pr) {
    return [ {p: 48/T, x: sf}, {p: 52/T, x: tk}, {p: 720/T, x: st}, {p: 1096/T, x: fl}, {p: 3744/T, x: pr}, {p: 16440/T, x: -1} ];
  }
  G["three-card-poker"] = {
    name: "Three Card Poker", pace: 70, paceNote: "hands per hour at a moderately busy table",
    unit: 10, defaultBet: "ante-play",
    bets: {
      "ante-play": { name: "Ante & Play (Q-6-4 strategy, 5-4-1 bonus)", edge: 0.0337, edgeNote: "3.37% of the ante; 2.01% of all money wagered", kind: "approx", avgWager: 1.674, sd: 1.64,
        // fold 32.6% of hands (below Q-6-4); dealer fails to qualify on 30.4%; ante bonus on straight or better.
        rows: [ {p: 0.3258, x: -1}, {p: 0.2050, x: 1}, {p: 0.2431, x: 2}, {p: 0.2261, x: -2} ],
        bonusRows: [ {p: 0.0326, add: 1}, {p: 0.00235, add: 4}, {p: 0.00217, add: 5} ] },
      "pair-plus-40-30-6-4-1": { name: "Pair Plus 40-30-6-4-1", edge: 0.0232, kind: "exact", rows: pairPlus(40, 30, 6, 4, 1) },
      "pair-plus-40-30-6-3-1": { name: "Pair Plus 40-30-6-3-1 (the common one)", edge: 0.0728, kind: "exact", rows: pairPlus(40, 30, 6, 3, 1) },
      "pair-plus-50-30-6-3-1": { name: "Pair Plus 50-30-6-3-1", edge: 0.0510, kind: "exact", rows: pairPlus(50, 30, 6, 3, 1) }
    }
  };

  /* ---------- ULTIMATE TEXAS HOLD'EM ---------- */
  // Trips: exact 7-card hand frequencies (royal 0.0032%, straight flush 0.028%, quads 0.17%, full house 2.60%, flush 3.03%, straight 4.62%, trips 4.83%); edge computed from the rows.
  G["ultimate-texas-holdem"] = {
    name: "Ultimate Texas Hold'em", pace: 40, paceNote: "hands per hour at a moderately busy table",
    unit: 10, defaultBet: "ante-blind",
    bets: {
      "ante-blind": { name: "Ante + Blind, optimal strategy", edge: 0.02185, edgeNote: "2.19% of the ante; 0.53% of all money wagered", kind: "approx", avgWager: 4.15, sd: 4.9,
        // Shape: ~38% of hands raised 4x, ~12% 2x, ~30% 1x, ~20% folded. Results in ante units
        // (ante + blind + raise; blind pays only on straight or better, pushes on lesser wins;
        // ante pushes when the dealer fails to qualify). Calibrated to EV −2.185% and SD ≈ 4.9.
        rows: [ {p: 0.16, x: -2},
                {p: 0.27, x: 6}, {p: 0.03, x: 4}, {p: 0.22, x: -6},
                {p: 0.03, x: 3}, {p: 0.02, x: 2}, {p: 0.05, x: -4},
                {p: 0.08, x: 2}, {p: 0.02, x: 1}, {p: 0.12, x: -3} ],
        bonusRows: [ {p: 0.046, add: 1}, {p: 0.030, add: 1.5}, {p: 0.026, add: 3}, {p: 0.0017, add: 10}, {p: 0.0003, add: 50} ] },
      "trips-9743": { name: "Trips — 50-40-30-9-7-4-3 paytable", kind: "exact",
        rows: [ {p: 0.0000323, x: 50}, {p: 0.000279, x: 40}, {p: 0.00168, x: 30}, {p: 0.0260, x: 9}, {p: 0.0303, x: 7}, {p: 0.0462, x: 4}, {p: 0.0483, x: 3}, {p: 0.8473, x: -1} ] },
      "trips-8653": { name: "Trips — 50-40-30-8-6-5-3 paytable", kind: "exact",
        rows: [ {p: 0.0000323, x: 50}, {p: 0.000279, x: 40}, {p: 0.00168, x: 30}, {p: 0.0260, x: 8}, {p: 0.0303, x: 6}, {p: 0.0462, x: 5}, {p: 0.0483, x: 3}, {p: 0.8473, x: -1} ] },
      "trips-9733": { name: "Trips — 50-40-30-9-7-3-3 paytable", kind: "exact",
        rows: [ {p: 0.0000323, x: 50}, {p: 0.000279, x: 40}, {p: 0.00168, x: 30}, {p: 0.0260, x: 9}, {p: 0.0303, x: 7}, {p: 0.0462, x: 3}, {p: 0.0483, x: 3}, {p: 0.8473, x: -1} ] }
    }
  };

  /* ---------- BLACKJACK (approximate shape, calibrated) ---------- */
  // Basic-strategy result shape for a 6-deck H17 DAS game: blackjack 4.5% of hands (paid 3:2 or 6:5),
  // doubled/split hands ~11% (±2), pushes ~8.8%. Win/loss masses calibrated to the published edge
  // and a standard deviation of ~1.15 units per hand.
  function bj(bjPay, edge) {
    return { edge: edge, kind: "approx", sd: 1.15,
      rows: [ {p: 0.0453, x: bjPay}, {p: 0.0600, x: 2}, {p: 0.3300, x: 1}, {p: 0.0880, x: 0}, {p: 0.4260, x: -1}, {p: 0.0507, x: -2} ] };
  }
  G.blackjack = {
    name: "Blackjack", pace: 70, paceNote: "hands per hour with four or five players at the table (heads-up: 200+)",
    unit: 25, defaultBet: "bs-32",
    bets: {
      "bs-32": Object.assign({ name: "Basic strategy, 3:2 blackjack, 6 decks H17 DAS" }, bj(1.5, 0.0055)),
      "bs-32-liberal": Object.assign({ name: "Basic strategy, 3:2, liberal rules (S17, DAS, surrender, few decks)" }, bj(1.5, 0.0030)),
      "bs-65": Object.assign({ name: "Basic strategy, 6:5 blackjack" }, bj(1.2, 0.0194)),
      "feel-32": Object.assign({ name: "Playing by feel, 3:2 table" }, bj(1.5, 0.0200)),
      "feel-65": Object.assign({ name: "Playing by feel, 6:5 table" }, bj(1.2, 0.0340)),
      "insurance": { name: "Insurance (6 decks)", edge: 0.0740, kind: "exact",
        rows: [ {p: 96/311, x: 2}, {p: 215/311, x: -1} ] },
      "lucky-ladies": { name: "Lucky Ladies side bet (typical paytable)", edge: 0.2469, kind: "approx", sd: 5.0,
        rows: [ {p: 0.00001, x: 1000}, {p: 0.0002, x: 125}, {p: 0.004, x: 19}, {p: 0.0045, x: 9}, {p: 0.075, x: 4}, {p: 0.9163, x: -1} ] }
    }
  };

  /* ---------- BLACKJACK VARIANTS (approximate shapes, calibrated to published edges) ---------- */
  function bjv(name, edge, sd, bjPay, extra) {
    var rows = [ {p: 0.0453, x: bjPay}, {p: 0.070, x: 2}, {p: 0.320, x: 1}, {p: 0.10, x: 0}, {p: 0.415, x: -1}, {p: 0.0497, x: -2} ];
    if (extra) rows = rows.concat(extra);
    return { name: name, edge: edge, kind: "approx", sd: sd, rows: rows };
  }
  G["blackjack-variants"] = {
    name: "Blackjack variants", pace: 70, paceNote: "hands per hour at a moderately busy table (Switch: two hands each)",
    unit: 25, defaultBet: "spanish21-s17",
    bets: {
      "spanish21-s17": bjv("Spanish 21, dealer stands on soft 17", 0.0040, 1.25, 1.5, [ {p: 0.004, x: 3}, {p: 0.002, x: 1.5} ]),
      "spanish21-h17": bjv("Spanish 21, hits soft 17, redoubling", 0.0042, 1.25, 1.5, [ {p: 0.004, x: 3}, {p: 0.002, x: 1.5} ]),
      "spanish21-h17-nr": bjv("Spanish 21, hits soft 17, no redoubling", 0.0076, 1.22, 1.5, [ {p: 0.004, x: 3}, {p: 0.002, x: 1.5} ]),
      "switch": bjv("Blackjack Switch, 6 decks H17, full strategy (per hand)", 0.0058, 1.10, 1),
      "switch-simple": bjv("Blackjack Switch, simple switching rule (per hand)", 0.0075, 1.10, 1),
      "free-bet": bjv("Free Bet Blackjack, 6 decks H17", 0.0104, 1.45, 1.5, [ {p: 0.06, x: 2}, {p: 0.04, x: 3} ]),
      "double-exposure-best": bjv("Double Exposure, best-known rules", 0.0026, 1.05, 1),
      "double-exposure-typ": bjv("Double Exposure, typical rules", 0.0067, 1.05, 1),
      "double-exposure-worst": bjv("Double Exposure, worst common rules", 0.0147, 1.02, 1),
      "superfun-1d": bjv("Super Fun 21, single deck", 0.0116, 1.12, 1, [ {p: 0.0012, x: 2} ]),
      "superfun-6d": bjv("Super Fun 21, six decks", 0.0140, 1.12, 1, [ {p: 0.0012, x: 2} ]),
      "super-match": { name: "Switch — Super Match side bet", edge: 0.0255, kind: "approx", sd: 2.6,
        rows: [ {p: 0.000357, x: 40}, {p: 0.0026, x: 8}, {p: 0.0140, x: 5}, {p: 0.0270, x: 3}, {p: 0.30, x: 1}, {p: 0.656, x: -1} ] },
      "match-dealer": { name: "Spanish 21 — Match the Dealer (6 decks)", edge: 0.0306, kind: "approx", sd: 3.1,
        rows: [ {p: 0.006, x: 22}, {p: 0.008, x: 15}, {p: 0.005, x: 14}, {p: 0.14, x: 4}, {p: 0.02, x: 9}, {p: 0.821, x: -1} ] },
      "pot-of-gold": { name: "Free Bet — Pot of Gold side bet", edge: 0.0464, kind: "approx", sd: 3.4,
        rows: [ {p: 0.0008, x: 50}, {p: 0.004, x: 25}, {p: 0.03, x: 10}, {p: 0.06, x: 5}, {p: 0.10, x: 2}, {p: 0.8052, x: -1} ] },
      "push-22": { name: "Free Bet — Push 22 side bet", edge: 0.1176, kind: "approx", sd: 3.0,
        rows: [ {p: 0.003, x: 50}, {p: 0.012, x: 20}, {p: 0.04, x: 8}, {p: 0.03, x: 6}, {p: 0.915, x: -1} ] }
    },
    note: "All variant tables are approximate result shapes calibrated to the published house edge; side-bet paytables are representative examples."
  };

  return G;
})();
