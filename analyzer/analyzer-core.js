/* TTG Portfolio Analyzer — core maths. Pure functions, no DOM, no dependencies.
 * Runs in the browser (window.TTGAnalyzer) and in node (require).
 * Formulas and data shapes: analyzer/README.md. Design: tasks/design.md §1–3.
 *
 * Every result carries its coverage: the share of portfolio value it could use,
 * plus the holdings it could not (`unknown`) and whether any input was an estimate.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.TTGAnalyzer = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var MODEL_VERSION = 1;
  var TYPES = ['stock', 'etf', 'fund', 'bond', 'crypto', 'cash', 'other'];
  var FUND_TYPES = { etf: 1, fund: 1 };
  var ASSET_CLASSES = ['equity', 'fixed_income', 'cash', 'crypto', 'other'];
  var DEFAULT_CLASS = { stock: 'equity', bond: 'fixed_income', cash: 'cash', crypto: 'crypto', other: 'other' };
  var DIMS = ['asset_class', 'sector', 'country'];
  var MAX_DEPTH = 6; // fund-of-funds recursion limit
  var EPS = 1e-9;

  // ---------- holdings model ----------

  /** Empty portfolio in the current model version. Plain JSON, so it can be saved or shared later. */
  function emptyPortfolio() {
    return { v: MODEL_VERSION, base: 'USD', fx: {}, holdings: [] };
  }

  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function isCcy(x) { return typeof x === 'string' && /^[A-Z]{3}$/.test(x); }

  /** Structural check of a portfolio object. Returns {ok, errors[]}; never throws. */
  function validatePortfolio(p) {
    var errors = [];
    if (!p || typeof p !== 'object') return { ok: false, errors: ['portfolio is not an object'] };
    if (p.v !== MODEL_VERSION) errors.push('v must be ' + MODEL_VERSION);
    if (p.base !== 'USD') errors.push('base must be USD');
    if (p.fx != null) {
      if (typeof p.fx !== 'object') errors.push('fx must be an object');
      else Object.keys(p.fx).forEach(function (c) {
        if (!isCcy(c)) errors.push('fx: bad currency code ' + c);
        else if (!isNum(p.fx[c]) || p.fx[c] <= 0) errors.push('fx.' + c + ' must be a positive number (USD per unit)');
      });
    }
    if (!Array.isArray(p.holdings)) { errors.push('holdings must be an array'); return { ok: false, errors: errors }; }
    var seen = {};
    p.holdings.forEach(function (h, i) {
      var at = 'holdings[' + i + ']';
      if (!h || typeof h !== 'object') { errors.push(at + ' is not an object'); return; }
      if (typeof h.id !== 'string' || !h.id) errors.push(at + '.id must be a non-empty string');
      else if (seen[h.id]) errors.push(at + '.id duplicates ' + h.id);
      else seen[h.id] = 1;
      if (!h.key && !h.ticker && !h.name) errors.push(at + ' needs key, ticker or name');
      if (h.type != null && TYPES.indexOf(h.type) < 0) errors.push(at + '.type must be one of ' + TYPES.join('/'));
      var hasQty = h.quantity != null, hasVal = h.value != null;
      if (!hasQty && !hasVal) errors.push(at + ' needs quantity or value');
      if (hasQty && (!isNum(h.quantity) || h.quantity < 0)) errors.push(at + '.quantity must be a number >= 0');
      if (hasVal && (!isNum(h.value) || h.value < 0)) errors.push(at + '.value must be a number >= 0');
      if (h.price != null && (!isNum(h.price) || h.price <= 0)) errors.push(at + '.price must be a number > 0');
      if (h.currency != null && !isCcy(h.currency)) errors.push(at + '.currency must be a 3-letter code (GBX for pence)');
      if (h.fields != null) {
        var f = h.fields;
        if (typeof f !== 'object') errors.push(at + '.fields must be an object');
        else {
          if (f.asset_class != null && ASSET_CLASSES.indexOf(f.asset_class) < 0) errors.push(at + '.fields.asset_class must be one of ' + ASSET_CLASSES.join('/'));
          if (f.beta != null && !isNum(f.beta)) errors.push(at + '.fields.beta must be a number');
          if (f.mer != null && (!isNum(f.mer) || f.mer < 0 || f.mer > 0.2)) errors.push(at + '.fields.mer must be a fraction between 0 and 0.2');
        }
      }
    });
    return { ok: errors.length === 0, errors: errors };
  }

  // ---------- resolution and valuation ----------

  /** Find the reference security for a holding: by key, else by ticker alias (case-insensitive). */
  function resolve(h, ref) {
    var secs = (ref && ref.securities) || {};
    if (h.key && secs[h.key]) return { key: h.key, sec: secs[h.key] };
    if (h.ticker) {
      var k = ((ref && ref.aliases) || {})[String(h.ticker).toUpperCase()];
      if (k && secs[k]) return { key: k, sec: secs[k] };
    }
    return { key: null, sec: null };
  }

  /** USD per one unit of currency c. GBX (pence) is GBP/100. Portfolio fx beats reference fx. */
  function usdPer(c, portfolio, ref) {
    if (c === 'USD') return { rate: 1, source: 'identity' };
    var pfx = (portfolio && portfolio.fx) || {};
    var rfx = (ref && ref.fx && ref.fx.usd_per) || {};
    if (c === 'GBX') {
      var g = usdPer('GBP', portfolio, ref);
      return g.rate == null ? g : { rate: g.rate / 100, source: g.source };
    }
    if (isNum(pfx[c])) return { rate: pfx[c], source: 'user' };
    if (isNum(rfx[c])) return { rate: rfx[c], source: 'ref' };
    return { rate: null, source: null };
  }

  /**
   * Value every holding in USD.
   * value_usd = (value, else quantity × price) × USD-per-unit(currency)
   * price = the holding's own price (override), else the reference price. Crypto needs a user price or value
   * (reference crypto prices go stale within hours).
   */
  function valuePortfolio(portfolio, ref) {
    var positions = [], unvalued = [], total = 0;
    (portfolio.holdings || []).forEach(function (h) {
      var r = resolve(h, ref), sec = r.sec;
      var type = h.type || (sec && sec.type) || null; // null = not classified yet
      var ccy = h.currency || (sec && sec.currency) || 'USD';
      var label = h.name || (sec && sec.name) || h.ticker || h.key || h.id;
      var base = { id: h.id, key: r.key, label: label, type: type, currency: ccy, holding: h, sec: sec };
      var local = null, priceSource = null;
      if (isNum(h.value)) { local = h.value; priceSource = 'user value'; }
      else if (isNum(h.quantity)) {
        if (isNum(h.price)) { local = h.quantity * h.price; priceSource = 'user price'; }
        else if (type === 'crypto') { unvalued.push(Object.assign(base, { reason: 'crypto needs a price or a value' })); return; }
        else if (sec && isNum(sec.price)) { local = h.quantity * sec.price; priceSource = 'reference price as of ' + sec.as_of; }
        else { unvalued.push(Object.assign(base, { reason: 'no price: enter a price or a value' })); return; }
      }
      if (local == null) { unvalued.push(Object.assign(base, { reason: 'needs a quantity or a value' })); return; }
      var fx = usdPer(ccy, portfolio, ref);
      if (fx.rate == null) { unvalued.push(Object.assign(base, { reason: 'no exchange rate for ' + ccy })); return; }
      var usd = local * fx.rate;
      positions.push(Object.assign(base, { value_local: local, fx: fx.rate, fx_source: fx.source, price_source: priceSource, value_usd: usd }));
      total += usd;
    });
    positions.forEach(function (p) { p.w = total > 0 ? p.value_usd / total : 0; });
    return { positions: positions, unvalued: unvalued, total_usd: total };
  }

  // ---------- look-through ----------

  function secOf(ref, key) { return key && ref && ref.securities ? ref.securities[key] || null : null; }
  function isFund(sec) { return !!(sec && FUND_TYPES[sec.type]); }

  function addInto(dst, src, scale) {
    Object.keys(src).forEach(function (k) { dst[k] = (dst[k] || 0) + src[k] * scale; });
  }

  /**
   * Distribution of one unit of security `key` over a dimension's buckets.
   * Returns {dist: {bucket: share}, covered: share of the unit attributed, estimated: bool}.
   * Order: user field override → the security's own field → a fund's published breakdown →
   * a fund's allocation (asset_class only) → recursion through the fund's holdings.
   * Sector and country do not apply to non-equity single holdings without the field: they land in
   * bucket '_' + asset class ('_fixed_income', '_cash', '_crypto', '_other') and count as covered.
   */
  function one(b) { var o = {}; o[b] = 1; return { dist: o, covered: 1, estimated: false }; }
  var NONE = { dist: {}, covered: 0, estimated: false };

  function attrOf(ref, key, sec, dim, fields, depth, stack, type) {
    if (fields && fields[dim] != null) return one(fields[dim]);
    var acField = fields && fields.asset_class;
    if (!isFund(sec) && !(sec == null && FUND_TYPES[type])) {
      var ac = acField || (sec && sec.asset_class) || DEFAULT_CLASS[(sec && sec.type) || type];
      if (dim === 'asset_class') return ac ? one(ac) : NONE;
      if (sec && sec[dim] != null) return one(sec[dim]);
      if (ac && ac !== 'equity') return one('_' + ac);
      return NONE;
    }
    if (!sec) return NONE;
    var est = !!(sec.holdings && sec.holdings.level === 'estimate');
    if (sec.breakdown && sec.breakdown[dim]) return { dist: Object.assign({}, sec.breakdown[dim]), covered: sumVals(sec.breakdown[dim]), estimated: est };
    if (dim === 'asset_class' && sec.allocation) return { dist: Object.assign({}, sec.allocation), covered: sumVals(sec.allocation), estimated: est };
    if (!sec.holdings || depth >= MAX_DEPTH || stack.indexOf(key) >= 0) return { dist: {}, covered: 0, estimated: false };
    var dist = {}, covered = 0;
    sec.holdings.rows.forEach(function (row) {
      var sub = attrOf(ref, row.key, secOf(ref, row.key), dim, row.fields, depth + 1, stack.concat([key]));
      addInto(dist, sub.dist, row.w);
      covered += row.w * sub.covered;
      if (sub.estimated) est = true;
    });
    return { dist: dist, covered: covered, estimated: est };
  }

  function sumVals(o) { return Object.keys(o).reduce(function (s, k) { return s + o[k]; }, 0); }

  /** The security whose data stands in for a position: itself, or a user-chosen proxy (labelled estimate). */
  function lookSource(p, ref) {
    var proxy = p.holding.proxy;
    if (proxy && secOf(ref, proxy) && !(p.sec && (p.sec.holdings || p.sec.breakdown))) {
      return { key: proxy, sec: secOf(ref, proxy), estimated: true, via: proxy };
    }
    return { key: p.key, sec: p.sec, estimated: false, via: null };
  }

  /**
   * Portfolio breakdown along one dimension.
   * opts.lookThrough (default true) — funds decompose into their holdings; false treats each fund as one block
   *   (its asset class from allocation only; sector/country unknown).
   * w = share of total portfolio value; share = share of the covered part. Σw = covered.
   */
  function breakdown(valued, ref, dim, opts) {
    opts = opts || {};
    var look = opts.lookThrough !== false;
    var buckets = {}, covered = 0, unknown = [], estimated = [];
    valued.positions.forEach(function (p) {
      var src = lookSource(p, ref);
      var a;
      if (dim === 'currency') a = { dist: (function () { var o = {}; o[p.currency] = 1; return o; })(), covered: 1, estimated: false };
      else if (!look && isFund(src.sec) && dim !== 'asset_class' && !(p.holding.fields && p.holding.fields[dim] != null)) a = { dist: {}, covered: 0, estimated: false };
      else a = attrOf(ref, src.key, src.sec, dim, p.holding.fields, 0, [], p.type);
      addInto(buckets, a.dist, p.w);
      covered += p.w * a.covered;
      if (a.covered < 1 - 1e-6) unknown.push({ id: p.id, label: p.label, w: p.w * (1 - a.covered) });
      if (a.estimated || src.estimated) estimated.push({ id: p.id, label: p.label, via: src.via });
    });
    var rows = Object.keys(buckets).map(function (k) {
      return { bucket: k, w: buckets[k], share: covered > EPS ? buckets[k] / covered : 0 };
    }).sort(function (x, y) { return y.w - x.w; });
    return { dim: dim, lookThrough: look, rows: rows, covered: covered, unknown: unknown, estimated: estimated, unvalued: valued.unvalued };
  }

  /**
   * Security-level exposure: E_s = w_s,direct + Σ_f w_f · h_f,s, recursing through funds of funds.
   * Fund weight not listed by name is reported as `unlisted` (per fund).
   */
  function exposures(valued, ref) {
    var map = {}, unlisted = [];
    function add(key, label, w, kind, est) {
      var r = map[key] || (map[key] = { key: key, label: label, direct: 0, via: 0, total: 0, estimated: false });
      r[kind] += w; r.total += w; if (est) r.estimated = true;
    }
    function walk(fundKey, sec, w, depth, stack, est, label) {
      var listed = 0;
      sec.holdings.rows.forEach(function (row) {
        var sub = secOf(ref, row.key);
        var ww = w * row.w;
        listed += row.w;
        if (isFund(sub) && sub.holdings && depth < MAX_DEPTH && stack.indexOf(row.key) < 0) {
          walk(row.key, sub, ww, depth + 1, stack.concat([row.key]), est || sub.holdings.level === 'estimate', label);
        } else {
          add(row.key || 'name:' + row.name, (sub && sub.name) || row.name || row.key, ww, 'via', est);
        }
      });
      if (listed < 1 - 1e-6) unlisted.push({ fund: fundKey, label: label, w: w * (1 - listed) });
    }
    valued.positions.forEach(function (p) {
      var src = lookSource(p, ref);
      if (isFund(src.sec) && src.sec.holdings) {
        walk(src.key, src.sec, p.w, 0, [src.key], src.estimated || src.sec.holdings.level === 'estimate', p.label);
      } else if (isFund(src.sec) || (!p.sec && FUND_TYPES[p.type])) {
        unlisted.push({ fund: p.key || p.id, label: p.label, w: p.w });
      } else {
        add(p.key || 'id:' + p.id, p.label, p.w, 'direct', false);
      }
    });
    var rows = Object.keys(map).map(function (k) { return map[k]; }).sort(function (a, b) { return b.total - a.total; });
    var named = rows.reduce(function (s, r) { return s + r.total; }, 0);
    return { rows: rows, named: named, unlisted: unlisted, unvalued: valued.unvalued };
  }

  /** Full look-through weights of one fund by security key (for overlap). */
  function fundWeights(ref, key) {
    var out = {}, listed = 0;
    function walk(sec, w, depth, stack) {
      sec.holdings.rows.forEach(function (row) {
        var sub = secOf(ref, row.key);
        if (isFund(sub) && sub.holdings && depth < MAX_DEPTH && stack.indexOf(row.key) < 0) walk(sub, w * row.w, depth + 1, stack.concat([row.key]));
        else if (row.key) { out[row.key] = (out[row.key] || 0) + w * row.w; listed += w * row.w; }
      });
    }
    var sec = secOf(ref, key);
    if (isFund(sec) && sec.holdings) walk(sec, 1, 0, [key]);
    return { weights: out, listed: listed };
  }

  /** Overlap(A, B) = Σ_s min(h_A,s, h_B,s) over names both list. A lower bound when either fund lists < 100%. */
  function overlap(ref, keyA, keyB) {
    var a = fundWeights(ref, keyA), b = fundWeights(ref, keyB), ov = 0;
    Object.keys(a.weights).forEach(function (s) { if (b.weights[s]) ov += Math.min(a.weights[s], b.weights[s]); });
    return { a: keyA, b: keyB, overlap: ov, listedA: a.listed, listedB: b.listed, lowerBound: a.listed < 1 - 1e-6 || b.listed < 1 - 1e-6 };
  }

  /** Overlap for every pair of funds held. */
  function overlapMatrix(valued, ref) {
    var funds = [];
    valued.positions.forEach(function (p) {
      var src = lookSource(p, ref);
      if (isFund(src.sec) && src.sec.holdings && funds.indexOf(src.key) < 0) funds.push(src.key);
    });
    var pairs = [];
    for (var i = 0; i < funds.length; i++) for (var j = i + 1; j < funds.length; j++) pairs.push(overlap(ref, funds[i], funds[j]));
    return { funds: funds, pairs: pairs };
  }

  // ---------- concentration ----------

  /** largest, top-5 sum and N_eff = 1 / Σ wᵢ² over the given weights (shares of the portfolio). */
  function concentrationOf(items) {
    var ws = items.slice().sort(function (a, b) { return b.w - a.w; });
    var hhi = ws.reduce(function (s, x) { return s + x.w * x.w; }, 0);
    return {
      largest: ws[0] || null,
      top5: ws.slice(0, 5).reduce(function (s, x) { return s + x.w; }, 0),
      n_eff: hhi > 0 ? 1 / hhi : null,
      count: ws.length
    };
  }

  /**
   * Concentration as held (positions) and looked through (named securities).
   * Look-through treats fund weight not listed by name as fully spread (adds nothing to Σw²),
   * so its N_eff is an upper bound.
   */
  function concentration(valued, ref) {
    var held = concentrationOf(valued.positions.map(function (p) { return { key: p.key || p.id, label: p.label, w: p.w }; }));
    var ex = exposures(valued, ref);
    var look = concentrationOf(ex.rows.map(function (r) { return { key: r.key, label: r.label, w: r.total }; }));
    look.unlisted = ex.unlisted.reduce(function (s, u) { return s + u.w; }, 0);
    look.n_eff_upper_bound = look.unlisted > 1e-6;
    return { held: held, lookThrough: look };
  }

  // ---------- fees ----------

  /**
   * Fees on funds. MER f per fund; stocks, bonds, crypto, cash and other carry 0; an unclassified holding is unknown.
   * $/yr = Σ value_usd × f.  Weighted MER = Σ w × f over covered value.
   * Drag after n years on today's value, no growth assumed: 1 − Σ wᵢ (1 − fᵢ)ⁿ / Σ wᵢ  (each fund compounds its own fee).
   */
  function fees(valued, ref, years) {
    years = years || [10, 25];
    var annual = 0, covW = 0, wf = 0, unknown = [], rows = [];
    // A proxy never supplies a fee: a mutual fund's MER can be several times its ETF proxy's, so it must be entered.
    var held = valued.positions.map(function (p) {
      var f = p.holding.fields && isNum(p.holding.fields.mer) ? p.holding.fields.mer
        : (p.sec && isNum(p.sec.mer) ? p.sec.mer
          : (FUND_TYPES[p.type] || isFund(p.sec) || p.type == null ? null : 0));
      return { p: p, f: f };
    });
    held.forEach(function (x) {
      if (x.f == null) { unknown.push({ id: x.p.id, label: x.p.label, w: x.p.w }); return; }
      covW += x.p.w; wf += x.p.w * x.f; annual += x.p.value_usd * x.f;
      if (x.f > 0) rows.push({ id: x.p.id, label: x.p.label, mer: x.f, usd_per_year: x.p.value_usd * x.f, w: x.p.w });
    });
    var drag = {};
    years.forEach(function (n) {
      var keep = held.reduce(function (s, x) { return x.f == null ? s : s + x.p.w * Math.pow(1 - x.f, n); }, 0);
      drag[n] = covW > EPS ? 1 - keep / covW : null;
    });
    return {
      usd_per_year: annual,
      weighted_mer: covW > EPS ? wf / covW : null,
      drag: drag,
      drag_usd: Object.keys(drag).reduce(function (o, n) { o[n] = drag[n] == null ? null : drag[n] * valued.total_usd * covW; return o; }, {}),
      rows: rows.sort(function (a, b) { return b.usd_per_year - a.usd_per_year; }),
      covered: covW, unknown: unknown
    };
  }

  // ---------- beta ----------

  /**
   * Weighted beta of the equity slice: β = Σ wᵢβᵢ / Σ wᵢ over all-equity holdings with a beta,
   * grouped by the benchmark the beta was measured against (`beta_vs`; null = not stated).
   */
  function beta(valued, ref) {
    var groups = {}, equityW = 0, unknown = [], excluded = [], est = [];
    valued.positions.forEach(function (p) {
      var src = lookSource(p, ref);
      var ac = attrOf(ref, src.key, src.sec, 'asset_class', p.holding.fields, 0, [], p.type);
      var eq = ac.dist.equity || 0;
      if (eq < EPS) return;
      if (eq < 1 - 1e-6 || ac.covered < 1 - 1e-6) { excluded.push({ id: p.id, label: p.label, w: p.w, reason: 'not all equity' }); return; }
      equityW += p.w;
      var b = p.holding.fields && isNum(p.holding.fields.beta) ? p.holding.fields.beta : (src.sec && isNum(src.sec.beta) ? src.sec.beta : null);
      if (b == null) { unknown.push({ id: p.id, label: p.label, w: p.w }); return; }
      if (src.estimated && !(p.holding.fields && isNum(p.holding.fields.beta))) est.push({ id: p.id, label: p.label, via: src.via });
      var vs = (p.holding.fields && p.holding.fields.beta != null) ? (p.holding.fields.beta_vs || null) : ((src.sec && src.sec.beta_vs) || null);
      var g = groups[vs || 'unstated'] || (groups[vs || 'unstated'] = { benchmark: vs, w: 0, wb: 0 });
      g.w += p.w; g.wb += p.w * b;
    });
    var out = Object.keys(groups).map(function (k) { var g = groups[k]; return { benchmark: g.benchmark, w: g.w, beta: g.wb / g.w }; });
    var covered = out.reduce(function (s, g) { return s + g.w; }, 0);
    var all = covered > EPS ? out.reduce(function (s, g) { return s + g.w * g.beta; }, 0) / covered : null;
    return { equity_w: equityW, beta: all, by_benchmark: out, covered: covered, unknown: unknown, excluded: excluded, estimated: est };
  }

  // ---------- Sharpe ----------

  function monthIndex(ym) { var a = ym.split('-'); return (+a[0]) * 12 + (+a[1] - 1); }

  /** Monthly returns keyed by month from a level series {months:['YYYY-MM'…], values:[…]} (consecutive months). */
  function returnsOf(series) {
    var out = {};
    for (var i = 1; i < series.months.length; i++) {
      if (monthIndex(series.months[i]) !== monthIndex(series.months[i - 1]) + 1) continue;
      out[series.months[i]] = series.values[i] / series.values[i - 1] - 1;
    }
    return out;
  }

  function mean(a) { return a.reduce(function (s, x) { return s + x; }, 0) / a.length; }
  function sdSample(a) { var m = mean(a); return Math.sqrt(a.reduce(function (s, x) { return s + (x - m) * (x - m); }, 0) / (a.length - 1)); }

  /**
   * Historical Sharpe of today's mix (weights held constant, rebalanced monthly).
   *   r_p,t = Σ wᵢ rᵢ,t   e_t = r_p,t − rf_t   rf_t = rf annual % / 100 / 12
   *   SR = mean(e)/sd(e) × √12   SE ≈ √((1 + SR_m²/2) / T) × √12  (Lo 2002, iid)
   *   annual return = Π(1 + r_p,t)^(12/T) − 1   annual vol = sd(r_p) × √12
   * Window: the last `window` months (default 60) that every included series and rf share, ending at the
   * latest such month. Holdings with fewer than `minMonths` (36) returns are excluded and listed.
   * Not shown if included holdings cover < `minCoverage` (0.8) of value. Cash earns rf.
   */
  function sharpe(valued, ref, opts) {
    opts = opts || {};
    var window = opts.window || 60, minMonths = opts.minMonths || 36, minCov = opts.minCoverage == null ? 0.8 : opts.minCoverage;
    var rf = ref && ref.rf;
    if (!rf || !rf.months || !rf.months.length) return { value: null, reason: 'no risk-free series' };
    var rfm = {};
    rf.months.forEach(function (m, i) { rfm[m] = rf.annual_pct[i] / 100 / 12; });
    var inc = [], excluded = [], basis = {}, est = [];
    valued.positions.forEach(function (p) {
      var src = lookSource(p, ref);
      if (p.type === 'cash' && !(src.sec && src.sec.series)) { inc.push({ p: p, r: null }); basis.rf = 1; return; }
      var s = src.sec && src.sec.series;
      if (!s) { excluded.push({ id: p.id, label: p.label, w: p.w, reason: 'no price history' }); return; }
      var r = returnsOf(s);
      if (Object.keys(r).length < minMonths) { excluded.push({ id: p.id, label: p.label, w: p.w, reason: 'under ' + minMonths + ' months of history' }); return; }
      inc.push({ p: p, r: r });
      basis[s.basis || 'unstated'] = 1;
      if (s.proxy || src.estimated) est.push({ id: p.id, label: p.label, via: s.proxy || src.via });
    });
    var covered = inc.reduce(function (s, x) { return s + x.p.w; }, 0);
    var base = { covered: covered, excluded: excluded, estimated: est, basis: Object.keys(basis).sort() };
    if (covered < minCov - 1e-9) return Object.assign(base, { value: null, reason: 'not enough history: ' + Math.round(covered * 100) + '% of value covered, ' + Math.round(minCov * 100) + '% needed' });
    // months every included series and rf have, newest first
    var months = Object.keys(rfm).filter(function (m) { return inc.every(function (x) { return x.r === null || m in x.r; }); })
      .sort(function (a, b) { return monthIndex(b) - monthIndex(a); });
    var win = [];
    for (var i = 0; i < months.length && win.length < window; i++) {
      if (i > 0 && monthIndex(months[i]) !== monthIndex(months[i - 1]) - 1) break; // keep the window contiguous
      win.push(months[i]);
    }
    win.reverse();
    if (win.length < minMonths) return Object.assign(base, { value: null, reason: 'only ' + win.length + ' shared months; ' + minMonths + ' needed' });
    var rp = win.map(function (m) {
      return inc.reduce(function (s, x) { return s + (x.p.w / covered) * (x.r === null ? rfm[m] : x.r[m]); }, 0);
    });
    var e = rp.map(function (r, i) { return r - rfm[win[i]]; });
    var T = e.length, srm = mean(e) / sdSample(e);
    var growth = rp.reduce(function (g, r) { return g * (1 + r); }, 1);
    return Object.assign(base, {
      value: srm * Math.sqrt(12),
      se: Math.sqrt((1 + srm * srm / 2) / T) * Math.sqrt(12),
      months: T, from: win[0], to: win[T - 1],
      annual_return: Math.pow(growth, 12 / T) - 1,
      annual_vol: sdSample(rp) * Math.sqrt(12)
    });
  }

  // ---------- one call ----------

  /** Everything the results page needs, from one portfolio and one reference file. */
  function analyze(portfolio, ref, opts) {
    var check = validatePortfolio(portfolio);
    if (!check.ok) return { ok: false, errors: check.errors };
    var valued = valuePortfolio(portfolio, ref);
    var asOf = valued.positions.map(function (p) { return p.price_source && p.price_source.indexOf('reference') === 0 ? p.sec.as_of : null; }).filter(Boolean).sort();
    return {
      ok: true,
      total_usd: valued.total_usd,
      positions: valued.positions.map(function (p) {
        return { id: p.id, key: p.key, label: p.label, type: p.type, currency: p.currency, value_usd: p.value_usd, w: p.w, price_source: p.price_source, fx: p.fx, fx_source: p.fx_source };
      }),
      unvalued: valued.unvalued.map(function (u) { return { id: u.id, label: u.label, reason: u.reason }; }),
      asset_class: breakdown(valued, ref, 'asset_class'),
      exposures: exposures(valued, ref),
      overlap: overlapMatrix(valued, ref),
      concentration: concentration(valued, ref),
      sector: { lookThrough: breakdown(valued, ref, 'sector'), held: breakdown(valued, ref, 'sector', { lookThrough: false }) },
      region: breakdown(valued, ref, 'country'),
      currency: breakdown(valued, ref, 'currency'),
      fees: fees(valued, ref, opts && opts.feeYears),
      beta: beta(valued, ref),
      sharpe: sharpe(valued, ref, opts && opts.sharpe),
      data: { oldest_price: asOf[0] || null, newest_price: asOf[asOf.length - 1] || null, ref_generated: ref && ref.generated_at || null, fx: ref && ref.fx ? { as_of: ref.fx.as_of, source: ref.fx.source } : null }
    };
  }

  return {
    MODEL_VERSION: MODEL_VERSION, TYPES: TYPES, ASSET_CLASSES: ASSET_CLASSES, DIMS: DIMS,
    emptyPortfolio: emptyPortfolio, validatePortfolio: validatePortfolio,
    resolve: resolve, usdPer: usdPer, valuePortfolio: valuePortfolio,
    breakdown: breakdown, exposures: exposures, overlap: overlap, overlapMatrix: overlapMatrix,
    concentration: concentration, concentrationOf: concentrationOf,
    fees: fees, beta: beta, sharpe: sharpe, returnsOf: returnsOf, analyze: analyze
  };
});
