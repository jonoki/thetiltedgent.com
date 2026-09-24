# Builder brief — TTG ETF, crypto and bond/cash reports (PILOT, 23 Sep 2026)

These three families share the stock reports' document design and section order. Status: pilot — Oki approves each template before any batch.

**Before anything else, read `claude/REPORT_PITFALLS.md` and `claude/briefs/BUILD.md`.** Every data rule, privacy rule and "Lessons from the last checker round" rule in BUILD.md applies here unchanged. Where this brief differs from BUILD.md (template sections, verify expectations, identity step), this brief wins.

REPO (worktree, branch `claude/portfolio-analyzer`): `C:\Users\jon_o\Desktop\Coding projects\Portfolio Analyzer`. Write exactly ONE file, the path you are given. Never write in `...\thetiltedgent.com` (another session works there). Do NOT git add/commit/push. Temp files only in `$TEMP/ttg_<slug>/`.

## Template (all families)
Read `reports/ctsh_analysis.html` in full and copy its CSS, components (static-data banner, hero with price-block and 4 meta-items, `.section` + `.section-title` "0N Title", seg-bar + seg-legend, biz-card, moat-list, risk-list/risk-item, fin-table inside `.fin-scroll`, analyst-bar, chart-container, case-card bull/bear, disclaimer), Chart.js 4.4.1 from cdnjs, and the price-chart script pattern (1/3/10-month MAs). Pick one per-report `--accent`, never red/red-orange, distinct from green/red/amber/blue/purple chart lines.
- Eight numbered sections in the order given for your family, then the Commentary block, then the disclaimer. Keep "Static data as of <Month D, YYYY>" in the banner.
- Slot 07 has exactly two canvases (`priceChart`, second id per family). Any other chart (sector bars, MER bars, yield curve) is built from CSS/inline bars, not a canvas — except the bond yield curve (see below).
- The chart arrays keep the stock names: `const labels = [...]`, `const prices = [...]`, equal length, last value == `.price-current` to the cent (for the bond report: the yield in %, 2 dp).
- `<title>` starts `<TICKER> — ` (e.g. `XEQT — iShares Core Equity ETF Portfolio`).
- Tone: plain and functional. Describe, never recommend. No poker or gambling metaphors (Oki, 23 Sep). Explain finance jargon briefly; never define everyday words.
- No gambling, betting or prediction-market companies or projects named anywhere.
- LF line endings, UTF-8, no "tg-sitenav".

## Rules from the pilot checker rounds (23–24 Sep 2026 — hard rules, all families)
- **No hedge caveats in user-facing text** (Oki, 22 Sep): never "not confirmed", "unconfirmed", "not checked", "could not be fetched", "no later … found". A figure you cannot confirm on a fetched page is "n/v"; a statement you cannot confirm is removed. Process notes go in your Return, not on the page.
- **Nothing read after the banner date.** If a figure (e.g. a rich list) can only be read after it, it is n/v.
- **Sharpe (house formula):** e = r − rf monthly; Sharpe = mean(e) / sd(e) × √12 (sd of EXCESS returns). State it in the metrics note with the rf series.
- **Holdings and disclosures:** each holder's latest figure dated on or before the banner date, the date shown next to it. Check for 8-Ks and company/issuer releases AFTER the last 10-Q — treasury holdings change weekly. Filed figures beat on-chain press reports. Search snippets are never a source.
- **Fees:** every MER / expense ratio with its source document and period; label US "expense ratio / sponsor fee" vs Canadian "MER".
- **People:** name a person only in the role a fetched public page gives; use the current public name (e.g. GitHub profile name field, dated), not old commit-author names.
- **Counts and "latest":** re-count lists you state a number for; "latest version" not "latest release" where maintenance branches exist.
- **Look-through sums:** say whether cash lines are included.
- **Primary-source routes that work from this machine:** sec.gov EDGAR filings via WebFetch; api.congress.gov/v3/bill/…/actions?api_key=DEMO_KEY (congress.gov itself returns 403); Treasury CSV/XML and TreasuryDirect TA_WS JSON via curl; mempool.space and blockchain.info APIs; DefiLlama API; issuer pages vary (iShares US holdings JS-only; Grayscale/WisdomTree/Morgan Stanley 403; use 10-Qs). FRED CSV often hangs — optional.
- **Shell:** never run `py -3 -` without a heredoc (hangs); run scripts from files.

## ETF family — `reports/etf/<slug>_analysis.html`
Identity: confirm on the issuer's page the fund name, ticker, exchange, currency, inception, index.
Hero meta: MER · AUM (net assets) · Holdings · Distribution yield (state which yield the issuer quotes).
- 01 Fund Overview — objective, index or mandate, inception, structure (physical/synthetic, fund-of-funds, currency hedging), distribution frequency; general withholding-tax mechanics only if sourced. Sub-block "Issuer & Index Provider" (in place of Notable Executives).
- 02 What It Holds — seg-bar: asset-class mix; biz-cards: one per underlying fund if fund-of-funds (target/actual weight, that fund's MER, holdings count, region), else top sectors; CSS horizontal bars: sector weights; seg-bar: region/country mix; table: top-10 underlying stock holdings with weights (look-through if the issuer publishes it; say which). h3 "The two numbers that matter": holdings count and top-10 share.
- 03 Structural Strengths & Vulnerabilities — moat-list style strengths; "Key Vulnerabilities" risk-list (concentration, currency, fund-of-funds fee layering, hedging, index quirks).
- 04 Key Fund Metrics — fin-table: MER, management fee, AUM, holdings, distribution yield + frequency, 1/3/5-yr annualised total return (issuer's published NAV returns, with their as-of date), 5-yr annualised volatility and Sharpe (your calculation from monthly total returns — formula and risk-free series in a table note), beta vs S&P 500 (your calculation or sourced, say which). h3 "Notable Fund Events" (MER changes, splits, mergers, index changes).
- 05 Cost & Peer Comparison — table of 3–4 comparable funds: MER, AUM, holdings, and overlap where it can be computed from published holdings (else "n/v"). CSS bars: MER vs peers. Stat row: fee per $10,000 per year; 10- and 25-year fee drag as (1 − MER)^n on an unchanged balance (formula shown). No verdict on which fund is better.
- 06 Upcoming Events & News — next distribution dates, index rebalances, fund changes (sourced, dated ≤ banner date).
- 07 5-Year Price Analysis — Chart 1 `priceChart`: ~60 monthly closes (price) + MAs, plus a dataset of total-return (dividend-adjusted) closes if available, labelled. Chart 2 `drawdownChart`: % below running peak of the total-return series (computed in the script). h3 Inflection points; h3 Relative performance (vs its index / S&P 500 over the same window, your calculation).
- 08 Summary & Key Risks — case-cards "What helps it" / "What hurts it" (market conditions, not forecasts); Top 3 Risks.
- Category Commentary — the product category, factual. Disclaimer.

## Crypto family — `reports/crypto/<slug>_analysis.html`
Price = USD close of the banner date (UTC day). Monthly chart = UTC month-end closes.
Hero meta: Market cap · Circulating supply · Max supply · Launch year.
- 01 Overview — **opens with a general introduction that starts very basic and then gets more detailed** (Oki, 24 Sep): (1) in plain words, what it is; (2) how it was created — who, when, the founding document, the launch, and the context it came out of, all from primary sources (the whitepaper, the genesis block's own data, the founders' or foundation's own pages); (3) the purpose its creators stated, quoting the founding document; (4) only then the mechanics — consensus mechanism, supply and issuance schedule, with the Bitcoin-style detail. No speculation about anonymous founders' identities. Sub-block "Key Supporters & Developers" (in place of Notable Executives): the stewarding body (foundation / core-dev group), maintainers named only from the public repository or foundation page, institutional backers only where they disclosed it.
- 02 Use Cases & Key Projects — seg-bar of usage mix only if a sourced breakdown exists (else a list); biz-cards for 4–6 projects built on it, chosen by a stated, dated measure (value locked, users, capacity) with the source. Selection rule: top projects by the stated measure on the banner date, excluding centralized exchanges and reward/points campaigns, at most one per category (e.g. lending, trading, staking, stablecoin, scaling network), category named on each card. h3 "The two numbers that matter".
- 03 Network Strengths & Vulnerabilities — strengths (network effects, security budget, developer activity, liquidity); Key Vulnerabilities. h3 "Regulatory Status & Litigation": table — regulator/court, classification or case, filing date, status as of the banner date, link (SEC/CFTC/court docket/CSA release). Only primary sources for status.
- 04 Key Network & Market Metrics — fin-table: market cap, circulating/max supply, annual issuance, network fees, active addresses (named source), hash rate/security measure, 5-yr annualised return, volatility, Sharpe, max drawdown, correlation and beta vs S&P 500 over 60 months (your calculation; formula note). h3 "Notable Events" (forks, hacks, outages, halvings).
- 05 Who Holds It — seg-bar: disclosed holders as % of supply (US spot ETFs from issuer pages · public companies from filings · governments from official statements · everyone else). Stat row: share of supply in the top 100 / 1,000 addresses (named explorer, dated). Always show: "An address is not an owner — exchange and custodian wallets pool many customers, so address counts overstate concentration." Never attribute a wallet to a private individual. h3 "Ways to Hold It": listed spot ETFs (US and Canada) with MER; self-custody vs exchange custody (facts).
- 06 Upcoming Catalysts & News — scheduled upgrades, halvings, court dates, ETF decisions.
- 07 5-Year Price Analysis — Chart 1 `priceChart`: monthly closes + MAs, with a button toggling a log y-axis. Chart 2 `drawdownChart`. Inflection points; Relative performance vs S&P 500.
- 08 Summary & Key Risks — Bull / Bear case-cards; Top 3 Risks.
- Sector Commentary. Disclaimer.

## Bond & cash family — `reports/fixed/<slug>_analysis.html`
Source hierarchy: U.S. Treasury (home.treasury.gov daily par yield curve, TreasuryDirect auction results), FRED, Federal Reserve; Bank of Canada Valet for Canadian series.
Header `.price-current` shows the yield (e.g. `4.12%`, 2 dp) for the banner date; chart = month-end daily yields (last business day of each month — NOT FRED's monthly-average series), last point == header yield.
Hero meta: Yield · Maturity/tenor · Modified duration · Credit rating (name the agency).
- 01 Overview — what it is, how an individual buys it (auction/TreasuryDirect, broker secondary market, ETFs — name 2–3 with tickers), tax facts (sourced).
- 02 How It's Priced — the current curve 3-month to 30-year for the banner date, with this tenor highlighted: this family may use a third canvas `curveChart` here. Auction/coupon mechanics; the current on-the-run issue (CUSIP, coupon, maturity, auction date, from TreasuryDirect).
- 03 Strengths & Vulnerabilities — credit quality, liquidity; Key Vulnerabilities (rate, inflation, reinvestment, fiscal/supply).
- 04 Key Figures — fin-table: yield, on-the-run coupon, maturity, modified duration, convexity (your calculation from coupon/yield/maturity; formulas in a note), price change for ±1%, 10-yr breakeven inflation and real yield (TIPS) for the banner date, rating(s).
- 05 Market & Policy Expectations — the central bank's latest published projections (Fed SEP median for the policy rate, with release date); h3 "Ways to Hold It" table (ETFs of similar maturity, MER, from issuer pages).
- 06 Upcoming Events — next auctions, FOMC dates, CPI release dates (official calendars).
- 07 5-Year Yield Analysis — Chart 1 `priceChart`: month-end yields + MAs. Chart 2 `sensChart`: % price change for yield shifts −3% to +3% in 0.25% steps, ΔP/P ≈ −D·Δy + ½·C·Δy² (computed in the script from the fin-table values). Inflection points.
- 08 Summary & Key Risks — case-cards "When it does well" / "When it does poorly" (mechanical: yields falling/rising, inflation surprises); Top 3 Risks.
- Rates Commentary. Disclaimer.

## Verify
- Extract the `<script>` bodies to `$TEMP/ttg_<slug>/` and `node --check` each.
- `py -3 tools/verify.py <your file>` — report the line. Expected pilot gaps, do not work around them: P/E fields absent; bond report has 3 canvases.
- Chart points: compare every monthly point to your source with a scratch script (ETF/crypto: Yahoo `https://query1.finance.yahoo.com/v8/finance/chart/<SYM>?range=6y&interval=1mo`, e.g. `XEQT.TO`, `BTC-USD`; bond: Treasury/FRED daily). 0 points more than 1% off (bond: 0.02 percentage points).

## Return (short, no file contents)
1 verify line + node check + chart comparison result · 2 banner date, header value and its source URL · 3 list of sources used (URL + date) · 4 every figure you calculated, with the formula · 5 anything unsourced, estimated or doubtful · 6 template friction: anything in this brief that did not fit the data (this feeds the final brief) · 7 PITFALLS: classes from REPORT_PITFALLS.md you caught mid-build.
