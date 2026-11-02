// The core on the generated data/analyzer_ref.json (stocks only for now): the wiring, not the maths.
// Expected values are read from the same file, so the test survives a price refresh.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const A = require('../analyzer-core.js');

const REF = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'data', 'analyzer_ref.json'), 'utf8'));

test('real ref: US tickers value at the report price; JPY waits for an FX rate', () => {
  const p = A.emptyPortfolio();
  p.holdings = [
    { id: 'a', ticker: 'AAPL', quantity: 10 },
    { id: 'b', ticker: 'brk.b', quantity: 2 },
    { id: 'n', ticker: '7974.T', quantity: 100 }
  ];
  const aapl = REF.securities[REF.aliases.AAPL], brk = REF.securities[REF.aliases['BRK.B']], nin = REF.securities[REF.aliases['7974.T']];
  const r = A.analyze(p, REF);
  assert.equal(r.ok, true);
  assert.ok(Math.abs(r.total_usd - (10 * aapl.price + 2 * brk.price)) < 1e-6);
  assert.deepEqual(r.unvalued, [{ id: 'n', label: nin.name, reason: 'no exchange rate for JPY' }]);
  assert.equal(r.sector.lookThrough.covered, 1);
  assert.equal(r.region.rows[0].bucket, 'US');
  assert.equal(r.data.oldest_price, [aapl.as_of, brk.as_of].sort()[0]);
  p.fx = { JPY: 0.0065 };
  assert.equal(A.analyze(p, REF).unvalued.length, 0);
});

test('real ref: every stock resolves by its own ticker', () => {
  for (const [key, s] of Object.entries(REF.securities)) {
    assert.equal(A.resolve({ ticker: s.ticker.toLowerCase() }, REF).key, key, s.ticker);
  }
});
