# Portfolio Analyzer — core

Branch `claude/portfolio-analyzer` only; not linked from the site. Design: `tasks/design.md` (v2, 23 Sep 2026).

| File | What it is |
|---|---|
| `analyzer-core.js` | All the maths. Pure functions, no DOM, no dependencies; `window.TTGAnalyzer` in a browser, `require()` in node. |
| `test/core.test.js` | Hand-computed fixtures for every card (arithmetic in the comments). |
| `test/real_ref.test.js` | The core wired to the generated `data/analyzer_ref.json`. |
| `test/fixture_ref.json` | Made-up reference data the core tests use; passes the verifier. |
| `../tools/analyzer_ref.py` | Writes `data/analyzer_ref.json` (stocks so far). `--check` fails when it is stale. |
| `../tools/verify_analyzer_ref.py` | Schema and sanity checks on any reference file. |

Run everything: `py -3 tools/run_checks.py` (includes `node --test "analyzer/test/*.test.js"` and both verifier runs).

## Holdings model (`v: 1`)

One plain JSON object, so saving or sharing later needs no rework. Nothing leaves the browser.

```json
{ "v": 1, "base": "USD", "fx": { "CAD": 0.72 },
  "holdings": [
    { "id": "h1", "ticker": "AAPL", "quantity": 10 },
    { "id": "h2", "ticker": "XIU.TO", "quantity": 50, "price": 41.2, "currency": "CAD" },
    { "id": "h3", "name": "My mutual fund", "type": "fund", "value": 12000, "currency": "CAD",
      "proxy": "xic", "fields": { "mer": 0.018 } },
    { "id": "h4", "name": "Savings", "type": "cash", "value": 5000 } ] }
```

- Identify a holding by `key` (reference key), `ticker` (looked up case-insensitively in `aliases`) or `name`.
- Value = `value`, else `quantity × price`; `price` is the user's override, else the reference price. **Crypto needs a user price or value.**
- `currency` defaults to the security's listing currency, else USD. `GBX` = pence (GBP/100).
- `fx` is USD per unit and beats the reference rates. No rate → the holding is listed as unvalued, never guessed.
- `fields` fills or overrides `asset_class`, `sector`, `country`, `beta` (+ `beta_vs`), `mer` for one holding.
- `proxy` lends another fund's holdings/breakdown to a fund the data does not cover; every result it touches is labelled an estimate. A proxy never supplies an MER.
- `validatePortfolio(p)` lists every problem; `analyze()` refuses an invalid portfolio.

## Reference data (`schema: ttg-analyzer-ref`, `v: 1`)

`securities[key]` — common: `type` (stock/etf/fund/bond/crypto/cash/other), `name`, `ticker`, `currency`, `price`, `as_of`, `source`. Then by type:

- stock: `sector` (manifest sector key), `country` (ISO alpha-2 of the operating head office), `beta`, `beta_source`, `beta_vs`
- etf/fund: `mer` (fraction), `allocation` {asset class: share}, `breakdown` {asset_class|sector|country: {bucket: share}}, `holdings` {`level` exact/partial/estimate, `as_of`, `source`, `rows` [{`key` or `name`, `w`}]} — rows may sum below 1; the rest is "unlisted"
- bond: `asset_class: fixed_income`, `country`
- optional `series` {`basis` total_return/price, `source`, `months` [YYYY-MM, consecutive], `values`}

Top level: `aliases` {TICKER: key}; optional `fx` {`as_of`, `source`, `usd_per`}; optional `rf` {`source`, `months`, `annual_pct`}.
Buckets starting `_` (`_cash`, `_fixed_income`, `_crypto`, `_other`) mark sector/country "does not apply"; they count as covered.

**In `data/analyzer_ref.json` today:** the 628 stock reports. 624 have a country (no HQ tag: cls, fer, rio, stx) and 577 have a beta. ETFs, funds, crypto, bonds, FX, rf and monthly series are listed under `pending`.

## Formulas

Weights wᵢ = USD value ᵢ / total valued. Every card returns `covered` (share of value it could use), `unknown` (holdings it could not) and `estimated` (holdings resting on a proxy or estimate-level data).

- **Look-through exposure** E_s = w_s,direct + Σ_f w_f · h_f,s, recursing through funds of funds (depth ≤ 6, cycles cut).
- **Breakdowns** (asset class, sector, country): per holding, user field → own field → fund `breakdown` → fund `allocation` (asset class) → recursion through holdings. Currency = listing currency as held (not revenue exposure).
- **Overlap**(A, B) = Σ_s min(h_A,s, h_B,s) over named holdings. A lower bound when either fund lists less than 100%.
- **Concentration**: largest, top 5, N_eff = 1 / Σ wᵢ², as held and looked through. Look-through counts unlisted fund weight as fully spread, so its N_eff is an upper bound (flagged).
- **Fees**: $/yr = Σ valueᵢ · fᵢ; weighted MER = Σ wᵢ fᵢ / Σ wᵢ (covered); drag after n years on today's value, no growth: 1 − Σ wᵢ (1 − fᵢ)ⁿ / Σ wᵢ. Stocks, bonds, crypto, cash, other: f = 0. A fund without an MER, or a holding with no type, is unknown.
- **Beta**: Σ wᵢ βᵢ / Σ wᵢ over all-equity holdings with a beta, grouped by `beta_vs`. Part-equity funds are excluded and listed.
- **Sharpe** (today's mix, held constant, rebalanced monthly): r_p,t = Σ wᵢ rᵢ,t; e_t = r_p,t − rf_t, rf_t = annual % / 1200; SR = mean(e) / sd(e) · √12 (sample sd); SE ≈ √((1 + SR_m²/2)/T) · √12 (Lo 2002, iid); annual return = Π(1 + r_p,t)^(12/T) − 1; annual vol = sd(r_p) · √12. Window = the last 60 months every included series and rf share (contiguous). Holdings under 36 months are excluded and listed; under 80% coverage gives a reason, not a number. Cash earns rf. `basis` reports whether any series is price-only (which understates income-heavy holdings).
