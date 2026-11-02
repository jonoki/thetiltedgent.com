// Tests for analyzer-core.js. Run: node --test analyzer/test/
// Expected values are worked by hand from the fixture; the arithmetic is in the comments.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const A = require('../analyzer-core.js');

const REF = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixture_ref.json'), 'utf8'));
const close = (a, b, tol = 1e-9, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg || ''} expected ${b}, got ${a}`);
const bucket = (res, k) => (res.rows.find(r => r.bucket === k) || { w: 0 }).w;

// Main portfolio. USD values:
//  h1 AAA   10 × 100            = 1000
//  h2 BBB.TO 20 × 50 CAD × 0.72 =  720
//  h3 CCC.L 100 × 500p × 1.30/100 = 650
//  h4 FND1  50 × 20             = 1000
//  h5 FND2  value               = 1000
//  h6 BTC   0.01 × 60000 (user price) = 600
//  h7 cash  value               = 1030
//  total                        = 6000
function portfolio() {
  const p = A.emptyPortfolio();
  p.holdings = [
    { id: 'h1', key: 'aaa', quantity: 10 },
    { id: 'h2', ticker: 'bbb.to', quantity: 20 },
    { id: 'h3', ticker: 'CCC.L', quantity: 100 },
    { id: 'h4', ticker: 'FND1', quantity: 50 },
    { id: 'h5', ticker: 'FND2', value: 1000 },
    { id: 'h6', ticker: 'BTC', quantity: 0.01, price: 60000 },
    { id: 'h7', name: 'Savings', type: 'cash', value: 1030, currency: 'USD' }
  ];
  return p;
}

test('model: empty portfolio validates; bad ones list every error', () => {
  assert.equal(A.validatePortfolio(A.emptyPortfolio()).ok, true);
  assert.equal(A.validatePortfolio(portfolio()).ok, true);
  const bad = { v: 2, base: 'CAD', fx: { cad: 1, GBP: -1 }, holdings: [
    { id: 'a' }, { id: 'a', key: 'x', quantity: -1, type: 'nft', currency: 'usd', fields: { mer: 0.5, asset_class: 'gold' } }
  ] };
  const r = A.validatePortfolio(bad);
  assert.equal(r.ok, false);
  for (const s of ['v must be 1', 'base must be USD', 'bad currency code cad', 'fx.GBP', 'needs key, ticker or name',
    'needs quantity or value', 'duplicates a', '.quantity must be', '.type must be', '.currency must be', '.fields.mer', '.fields.asset_class']) {
    assert.ok(r.errors.some(e => e.includes(s)), 'missing error: ' + s + ' in ' + JSON.stringify(r.errors));
  }
  assert.deepEqual(A.analyze(bad, REF).ok, false);
});

test('model: portfolio round-trips through JSON unchanged', () => {
  const p = portfolio();
  assert.deepEqual(JSON.parse(JSON.stringify(p)), p);
});

test('valuation: prices, overrides, GBX pence, FX, total 6000', () => {
  const v = A.valuePortfolio(portfolio(), REF);
  assert.equal(v.unvalued.length, 0);
  close(v.total_usd, 6000, 1e-9);
  const by = Object.fromEntries(v.positions.map(p => [p.id, p]));
  close(by.h2.value_usd, 720); close(by.h3.value_usd, 650); close(by.h6.value_usd, 600);
  assert.equal(by.h2.key, 'bbb');                 // ticker alias, case-insensitive
  assert.equal(by.h6.price_source, 'user price');
  assert.match(by.h1.price_source, /^reference price as of 2026-10-30/);
  close(by.h1.w, 1000 / 6000);
});

test('valuation: crypto without a price, missing FX and no price are unvalued with a reason', () => {
  const p = A.emptyPortfolio();
  p.holdings = [
    { id: 'c', ticker: 'BTC', quantity: 1 },
    { id: 'e', name: 'Euro thing', value: 100, currency: 'EUR' },
    { id: 'n', name: 'Mystery', quantity: 3 }
  ];
  const v = A.valuePortfolio(p, REF);
  assert.equal(v.positions.length, 0);
  assert.deepEqual(v.unvalued.map(u => u.reason), ['crypto needs a price or a value', 'no exchange rate for EUR', 'no price: enter a price or a value']);
  p.fx = { EUR: 1.1 };                            // user rate beats a missing reference rate
  const v2 = A.valuePortfolio(p, REF);
  close(v2.positions[0].value_usd, 110);
  assert.equal(v2.positions[0].fx_source, 'user');
});

test('asset class: equity 4370/6000, crypto 0.1, cash 1030/6000, fully covered', () => {
  const r = A.analyze(portfolio(), REF);
  close(bucket(r.asset_class, 'equity'), 4370 / 6000);
  close(bucket(r.asset_class, 'crypto'), 0.1);
  close(bucket(r.asset_class, 'cash'), 1030 / 6000);
  close(r.asset_class.covered, 1);
});

// Sector, look-through, in USD:
//  tech  = AAA 1000 + FND1 0.5×1000 + FND2 0.6×0.5×1000          = 1800
//  fin   = BBB 720  + FND1 0.2×1000 + FND2 0.6×0.2×1000          = 1040
//  energy= CCC 650  + FND2 0.4×1000                              = 1050
//  unknown: FND1 unlisted 0.3×1000 = 300; FND2 0.6×0.3×1000 = 180 → covered = 1 − 480/6000 = 0.92
test('sector look-through: hand totals and 92% coverage', () => {
  const s = A.analyze(portfolio(), REF).sector;
  close(bucket(s.lookThrough, 'technology'), 1800 / 6000);
  close(bucket(s.lookThrough, 'financials'), 1040 / 6000);
  close(bucket(s.lookThrough, 'energy'), 1050 / 6000);
  close(bucket(s.lookThrough, '_crypto'), 0.1);
  close(bucket(s.lookThrough, '_cash'), 1030 / 6000);
  close(s.lookThrough.covered, 0.92);
  assert.deepEqual(s.lookThrough.unknown.map(u => u.id), ['h4', 'h5']);
  close(s.lookThrough.unknown[0].w, 300 / 6000);
  close(s.lookThrough.unknown[1].w, 180 / 6000);
  // shares of the covered part sum to 1
  close(s.lookThrough.rows.reduce((t, r) => t + r.share, 0), 1, 1e-12);
  // as held: funds are opaque → covered = 1 − 2000/6000
  close(s.held.covered, 4000 / 6000);
});

test('region and currency', () => {
  const r = A.analyze(portfolio(), REF);
  close(bucket(r.region, 'US'), 1800 / 6000);
  close(bucket(r.region, 'CA'), 1040 / 6000);
  close(bucket(r.region, 'GB'), 1050 / 6000);
  close(bucket(r.currency, 'USD'), 4630 / 6000);  // 1000+1000+1000+600+1030
  close(bucket(r.currency, 'CAD'), 0.12);
  close(bucket(r.currency, 'GBX'), 650 / 6000);
  close(r.currency.covered, 1);
});

// Exposures: AAA 1000 + 500 + 300 = 1800; BBB 720 + 200 + 120 = 1040; CCC 650 + 400 = 1050
// Unlisted: FND1 held 0.3×1000 = 300; FND1 inside FND2 0.6×0.3×1000 = 180 → 480/6000 = 0.08
test('exposures: direct + via funds, unlisted remainder', () => {
  const e = A.analyze(portfolio(), REF).exposures;
  const aaa = e.rows.find(r => r.key === 'aaa');
  close(aaa.direct, 1000 / 6000); close(aaa.via, 800 / 6000); close(aaa.total, 0.3);
  close(e.rows.find(r => r.key === 'bbb').total, 1040 / 6000);
  close(e.rows.find(r => r.key === 'ccc').via, 400 / 6000);
  assert.equal(e.rows[0].key, 'aaa');             // sorted by total
  close(e.unlisted.reduce((t, u) => t + u.w, 0), 0.08);
  close(e.named + 0.08, 1);
});

// Overlap(FND1, FND2): FND1 {aaa .5, bbb .2}; FND2 look-through {aaa .3, bbb .12, ccc .4}
//  = min(.5,.3) + min(.2,.12) = .42, a lower bound (FND1 lists 70%)
test('overlap: Σ min over shared names, flagged lower bound', () => {
  const o = A.overlap(REF, 'fnd1', 'fnd2');
  close(o.overlap, 0.42); close(o.listedA, 0.7); close(o.listedB, 0.82);
  assert.equal(o.lowerBound, true);
  const m = A.analyze(portfolio(), REF).overlap;
  assert.deepEqual(m.funds, ['fnd1', 'fnd2']);
  assert.equal(m.pairs.length, 1);
});

// As held: values 1030, 1000 ×3, 720, 650, 600 → Σv² = 5,361,800 → N_eff = 6000² / 5,361,800
// Look-through: 1800, 1050, 1040, 1030, 600 → Σv² = 6,845,000 → N_eff = 36e6 / 6,845,000 (upper bound)
test('concentration: largest, top-5, N_eff both ways', () => {
  const c = A.analyze(portfolio(), REF).concentration;
  assert.equal(c.held.largest.label, 'Savings');
  close(c.held.top5, (1030 + 3000 + 720) / 6000);
  close(c.held.n_eff, 36e6 / 5361800, 1e-9);
  close(c.lookThrough.largest.w, 0.3);
  close(c.lookThrough.top5, 0.92);
  close(c.lookThrough.n_eff, 36e6 / 6845000, 1e-9);
  assert.equal(c.lookThrough.n_eff_upper_bound, true);
  close(c.lookThrough.unlisted, 0.08);
});

// Fees: FND1 1000 × 0.001 + FND2 1000 × 0.002 = $3/yr; weighted MER 3/6000 = 0.0005
// Drag(n) = 1 − [4000/6000 + (1/6)(0.999ⁿ) + (1/6)(0.998ⁿ)]
test('fees: $/yr, weighted MER, compounded drag', () => {
  const f = A.analyze(portfolio(), REF).fees;
  close(f.usd_per_year, 3); close(f.weighted_mer, 0.0005); close(f.covered, 1);
  const drag = n => 1 - (4 / 6 + Math.pow(0.999, n) / 6 + Math.pow(0.998, n) / 6);
  close(f.drag[10], drag(10)); close(f.drag[25], drag(25));
  close(f.drag[10], 0.0049627, 1e-6);             // hand: (0.009955 + 0.019821) / 6
  close(f.drag_usd[10], drag(10) * 6000);
  assert.deepEqual(f.rows.map(r => r.id), ['h5', 'h4']);
});

// Beta: unstated benchmark AAA 1.2 × 1000 + BBB 0.8 × 720 = 1776 over 1720 → 1.032558…
//       S&P 500 FND1 1.0 × 1000. Overall (1776 + 1000) / 2720. Unknown: CCC (no beta), FND2.
test('beta: equity slice, grouped by benchmark, unknowns listed', () => {
  const b = A.analyze(portfolio(), REF).beta;
  close(b.equity_w, 4370 / 6000);
  close(b.beta, 2776 / 2720);
  const un = b.by_benchmark.find(g => g.benchmark === null);
  close(un.beta, 1776 / 1720); close(un.w, 1720 / 6000);
  close(b.by_benchmark.find(g => g.benchmark === 'S&P 500').beta, 1.0);
  assert.deepEqual(b.unknown.map(u => u.id).sort(), ['h3', 'h5']);
  close(b.covered, 2720 / 6000);
});

test('balanced fund: allocation drives asset class; excluded from equity beta; breakdown drives sector', () => {
  const p = A.emptyPortfolio();
  p.holdings = [{ id: 'b', ticker: 'BAL', value: 1000 }, { id: 'a', key: 'aaa', value: 1000 }];
  const r = A.analyze(p, REF);
  close(bucket(r.asset_class, 'equity'), 0.8);    // (0.6×1000 + 1000) / 2000
  close(bucket(r.asset_class, 'fixed_income'), 0.2);
  assert.deepEqual(r.beta.excluded.map(x => x.id), ['b']);
  close(bucket(r.sector.lookThrough, 'technology'), (300 + 1000) / 2000);
  close(bucket(r.sector.lookThrough, '_fixed_income'), 0.2);
  close(r.fees.usd_per_year, 5);
});

test('proxy: an unseeded fund borrows its proxy\'s holdings, labelled estimate; fee must be entered', () => {
  const p = A.emptyPortfolio();
  p.holdings = [{ id: 'm', name: 'My mutual fund', type: 'fund', value: 1000, proxy: 'fnd1' }];
  const r = A.analyze(p, REF);
  close(bucket(r.sector.lookThrough, 'technology'), 0.5);
  assert.deepEqual(r.sector.lookThrough.estimated, [{ id: 'm', label: 'My mutual fund', via: 'fnd1' }]);
  assert.deepEqual(r.fees.unknown.map(u => u.id), ['m']);
  assert.deepEqual(r.beta.estimated.map(u => u.via), ['fnd1']);
  p.holdings[0].fields = { mer: 0.015 };
  close(A.analyze(p, REF).fees.usd_per_year, 15);
});

test('user fields classify an unknown holding; unclassified stays unknown', () => {
  const p = A.emptyPortfolio();
  p.holdings = [
    { id: 'x', name: 'Private co', type: 'stock', value: 500, fields: { asset_class: 'equity', sector: 'industrials', country: 'CA' } },
    { id: 'y', name: 'No idea', value: 500 }
  ];
  const r = A.analyze(p, REF);
  close(bucket(r.sector.lookThrough, 'industrials'), 0.5);
  close(r.asset_class.covered, 0.5);
  assert.deepEqual(r.asset_class.unknown.map(u => u.id), ['y']);
  assert.deepEqual(r.fees.unknown.map(u => u.id), ['y']);
  // without a type the fee stays unknown even when the asset class is set: equity could be a fund
  delete p.holdings[0].type;
  assert.deepEqual(A.analyze(p, REF).fees.unknown.map(u => u.id), ['x', 'y']);
});

test('fund-of-funds cycle does not loop', () => {
  const ref = JSON.parse(JSON.stringify(REF));
  ref.securities.fnd1.holdings.rows.push({ key: 'fnd2', w: 0.1 });   // fnd1 → fnd2 → fnd1
  delete ref.securities.fnd1.allocation;
  const p = A.emptyPortfolio();
  p.holdings = [{ id: 'a', key: 'fnd1', value: 100 }, { id: 'b', key: 'fnd2', value: 100 }];
  const r = A.analyze(p, ref);
  assert.equal(r.ok, true);
  assert.ok(r.sector.lookThrough.covered < 1 && r.sector.lookThrough.covered > 0);
  assert.ok(isFinite(A.overlap(ref, 'fnd1', 'fnd2').overlap));
});

// ---------- Sharpe ----------
// Two made-up series over 61 month-ends (60 returns). S1 alternates +2%, 0%; S2 earns +1% a month.
// 50/50 → r_p alternates 1.5%, 0.5%. rf = 1.2%/yr = 0.1%/month → e alternates 1.4%, 0.4%.
// mean(e) = 0.9%; deviations ±0.5% → sample sd = √(60 × 0.005² / 59) = 0.00504219…
// SR_m = 0.009 / 0.00504219 = 1.78494; SR = SR_m √12 = 6.18321
// SE = √((1 + SR_m²/2)/60) × √12 = 0.72014
// annual return = (1.015 × 1.005)^6 − 1 = 0.126662; annual vol = sd(r_p) √12 = 0.017467
function months(n, end) {
  const [y, m] = end.split('-').map(Number), out = [];
  for (let i = n - 1; i >= 0; i--) { const t = y * 12 + (m - 1) - i; out.push(`${Math.floor(t / 12)}-${String(t % 12 + 1).padStart(2, '0')}`); }
  return out;
}
function levels(rets) { const v = [100]; rets.forEach(r => v.push(v[v.length - 1] * (1 + r))); return v; }
function sharpeRef(nMonths) {
  const ms = months(nMonths + 1, '2026-10');
  const r1 = Array.from({ length: nMonths }, (_, i) => (i % 2 === 0 ? 0.02 : 0));
  const r2 = Array.from({ length: nMonths }, () => 0.01);
  const sec = (k, r) => ({ type: 'stock', name: k, currency: 'USD', price: 1, as_of: '2026-10-30', source: 't', sector: 'technology', country: 'US',
    series: { basis: 'total_return', source: 't', months: ms, values: levels(r) } });
  return { securities: { s1: sec('s1', r1), s2: sec('s2', r2) }, aliases: {}, rf: { source: 't', months: ms, annual_pct: ms.map(() => 1.2) } };
}

test('sharpe: hand-computed 60-month example', () => {
  const p = A.emptyPortfolio();
  p.holdings = [{ id: 'a', key: 's1', value: 500 }, { id: 'b', key: 's2', value: 500 }];
  const s = A.sharpe(A.valuePortfolio(p, sharpeRef(60)), sharpeRef(60));
  assert.equal(s.months, 60); assert.equal(s.from, '2021-11'); assert.equal(s.to, '2026-10');
  close(s.value, 6.18321, 1e-4);
  close(s.se, 0.72014, 1e-4);
  close(s.annual_return, 0.126662, 1e-5);
  close(s.annual_vol, 0.017467, 1e-5);
  assert.deepEqual(s.basis, ['total_return']);
});

test('sharpe: window caps at 60 of 70 months; cash earns rf', () => {
  const ref = sharpeRef(70);
  const p = A.emptyPortfolio();
  p.holdings = [{ id: 'a', key: 's1', value: 500 }, { id: 'b', key: 's2', value: 500 }];
  const s = A.sharpe(A.valuePortfolio(p, ref), ref);
  assert.equal(s.months, 60); assert.equal(s.to, '2026-10');
  // adding cash at rf leaves excess returns scaled by the risky share: SR unchanged
  p.holdings.push({ id: 'c', name: 'Cash', type: 'cash', value: 1000 });
  const s2 = A.sharpe(A.valuePortfolio(p, ref), ref);
  close(s2.value, s.value, 1e-9);
  assert.deepEqual(s2.basis, ['rf', 'total_return']);
});

test('sharpe: short history excluded; under 80% coverage gives a reason, not a number', () => {
  const p = A.emptyPortfolio();
  p.holdings = [{ id: 'a', key: 'aaa', value: 1000 }];   // fixture AAA has 3 months
  const s = A.sharpe(A.valuePortfolio(p, REF), REF);
  assert.equal(s.value, null);
  assert.match(s.reason, /not enough history: 0% of value covered/);
  assert.equal(s.excluded[0].reason, 'under 36 months of history');
  assert.equal(A.sharpe(A.valuePortfolio(p, { securities: REF.securities }), { securities: REF.securities }).reason, 'no risk-free series');
});
