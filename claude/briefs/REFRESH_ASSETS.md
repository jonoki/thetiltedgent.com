# Refresh brief — monthly numbers-only refresh of one ETF, crypto, bond & cash or economic-indicator report (Oki, 8 Oct 2026)

ETF, crypto, bond & cash and economic-indicator reports have no earnings print to trigger a refresh, so they would
freeze at their build date. Once a month (first Monday, 17:30) `py -3 tools/auto_refresh.py --assets` takes every
report under `reports/etf/`, `reports/crypto/`, `reports/fixed/` and `reports/indicators/` whose banner as-of is 28
days old or more and gives each to one builder and then one independent checker with this brief. The redirect stubs
left at the old paths of moved reports (`reports/fixed/sofr_analysis.html` and the like, `MOVED_REPORTS` in
`tools/repodata.py`) are not reports and are never taken.

**This is a numbers refresh, not a rewrite.** Every figure that has a newer value on or before the new as-of is
updated; the narrative is left alone except where a sentence is now false.

## Read first
1. `claude/PITFALL_RULES.md` — every rule applies.
2. `claude/briefs/BUILD_ASSETS.md` — the hard rules (privacy, no hedge or process caveats, nothing after the banner
   date, Sharpe house formula, fees with their source document, closes from Nasdaq/Yahoo daily rows not issuer price
   APIs, fund renames, data licensing), your family's section and its batch rules, and "Verify". They all apply.
   Economic indicators: `claude/briefs/BUILD_INDICATORS.md` in full instead of the family sections of BUILD_ASSETS.md.
3. `claude/briefs/BUILD.md` — only "Data rules" and "Lessons from the last checker round".
4. `claude/briefs/REFRESH.md` — only "Delta box" (markup, entities); this brief gives the numbers-only variant.
Where this brief differs from those, this brief wins.

REPO: the worktree path your prompt gives. Edit exactly ONE file, the report path you are given. No git. Temp files
only in `$TEMP/ttgref_<family>_<slug>/` (checker: `$TEMP/ttgchk_<family>_<slug>/`).

## Step 1 — read the report once, in full
Record the previous edition's as-of and header value (they become the delta box's "previous edition"), and make an
inventory of every time-dependent figure: header value and change, banner, chart arrays and their notes, 52-week
range, every metrics-table row with its date column, holdings and weights, distributions, events, and every sentence
in the prose, captions, cards and commentary that carries one of those numbers or dates. Later you look things up
with Grep or a Read with offset/limit; never re-read the whole file.

## Step 2 — the new as-of
- **ETF:** the last settled close on or before the run date — a session counts once 20:00 New York time on its date
  has passed (TSX listings: the TSX session, same rule). Close and day change from Yahoo or Nasdaq daily rows, never
  the issuer's price API.
- **Crypto:** the USD close of the last complete UTC day on or before the run date (Yahoo `<SYM>-USD` daily; Coinbase
  as the fallback when Yahoo drops the bar).
- **Bond & cash:** the latest official daily value published on or before the run date, from the series the page
  already names (U.S. Treasury daily par / par real yield curve, Bank of Canada Valet series id, New York Fed SOFR
  and EFFR, Bank of Canada CORRA, TreasuryDirect rates, the weekly posted rate). Series published a day late (SOFR,
  CORRA) keep the page's wording about when that day's value was published. Rates set twice a year (I bond, EE bond:
  May 1 and November 1) take the rate in force on the as-of date.
- **Economic indicator:** a daily rate (SOFR, EFFR, CORRA, the Fed and Bank of Canada policy rates, prime) as for bond
  & cash, from the series the page names; a monthly series (CPI, core PCE, unemployment, payrolls) takes the latest
  release published on or before the run date, and the banner names the release, its reference period and its date.
- One as-of for the whole page; nothing dated after it (rule B). The banner keeps its wording; only the date, weekday
  and source note change.
- If the new as-of equals the page's as-of (no newer data), change nothing and return `NO CHANGE`.

## Step 3 — update the numbers
1. **Header and banner.** Header value and change (ETF/crypto: $ and % vs the prior session's close; bonds: pp vs
   the prior published value, in the page's format), the banner date.
2. **Chart.** Keep every existing point as it is, except the old as-of point, which becomes that month's month-end
   close (or month-end yield) with a plain month label (`'Sep 23 26'` → `'Sep 26'`). Append every missing month-end,
   then the new as-of point labelled like the old one (`'Oct 30 26'`). Hold the five-year window: drop the oldest
   points so the series stays at 61 (60 month-ends + the as-of point); a fund younger than five years keeps every
   point since launch. Move every parallel array the same way: `totalReturn` (dividend-adjusted, rebased to the
   first point — rebase again if the first point changed), `events` (shift the indices; drop those that fell off),
   bond `curveNow` / `curveYearAgo` with their date comments, and the bond constants `MOD_DURATION` / `CONVEXITY`.
   Update the chart notes and captions ("60 month-end closes Oct 2021 → Sep 2026 + Oct 30, 2026 close"). Every
   value is copied from a fetched source, never typed or estimated (rule A). After the chart changes, sweep the text
   for the old values (old header value, old as-of point, dropped months) and fix every use.
3. **52-week range** as of the new as-of, on the basis the row states ("closing price", "NAV", UTC daily close,
   daily yields).
4. **Metrics table (section 04), by family:**
   - **ETF:** expense ratio / MER and management fee from the latest issuer document (prospectus or 497 supplement;
     Canadian MRFP or fund profile) with its date and period, and any waiver with its end date; net assets / AUM,
     holdings count, distribution yield and SEC yield with the issuer's as-of; bond funds add yield to maturity,
     effective duration and average maturity; commodity trusts the metal per share and the trust's ounces or
     tonnes; 1/3/5/10-yr NAV returns from the issuer with their as-of date (the issuer's month-end or quarter-end).
   - **Crypto:** market cap (price × circulating supply at the as-of), circulating and max supply, annual issuance,
     network fees, active addresses, hash rate or amount staked — each from the source the page names, dated on or
     before the as-of.
   - **Bond & cash:** yield, the on-the-run issue when a newer auction settled (CUSIP, coupon, maturity, auction date,
     high yield, bid-to-cover from TreasuryDirect or the Bank of Canada), modified duration and convexity recomputed
     at the new yield with the page's formulas, ±1 pp price change, model price, real yield and breakeven, spreads;
     the Fed SEP or the Bank of Canada MPR only when a newer release came out on or before the as-of; a rating only
     when the agency's own page shows a change.
   - **Economic indicator:** the latest reading, the prior period and a year earlier, the 12-month (or 52-week)
     range, the components and related rates in 04, the revisions the new release states for earlier months (and
     the chart points they change: a monthly series is charted at its latest vintage, so a revised month is updated
     and the delta box says so), the central bank's projection only when a newer one was published on or before the
     as-of, and the next release dates in 06 from the publisher's calendar. A monthly series appends one point per new
     reference month and drops the oldest, staying at 60; it has no as-of day point. SOFR, EFFR and CORRA were built
     as bond & cash pages: at their first refresh in this family the hero's "Family: Bonds &amp; cash" becomes
     "Family: Economic indicator" (no other layout change).
   - **Recomputed (ETF and crypto):** 5-yr annualised return, volatility, Sharpe (house formula: e = r − rf monthly;
     mean(e) / sd(e) × √12, rf series as the page states it), beta and correlation vs the S&P 500, maximum drawdown —
     on the 60 monthly returns ending at the latest month-end on or before the new as-of (younger funds: since
     launch), same series and method as the page's calculation note; update the note's window and averages.
     Relative-performance tables in 07 move to the same window.
5. **Holdings.** ETF top-10 holdings and weights, sector, region and underlying-fund weights where the issuer
   publishes them, each with its date. Crypto section 05: spot-ETF holdings where the issuer publishes them daily;
   company and government holdings only from a filing or statement newer than the page's and on or before the
   as-of. A figure with no newer value on or before the as-of stays, with its date; a live-only figure (an
   explorer's rich list read today) is never written over a dated one.
6. **Distributions.** Every distribution declared or paid since the previous as-of (ex-date, pay date, amount, from
   the issuer); the trailing yield recomputed on the page's own basis.
7. **Upcoming events (06).** Items dated on or before the new as-of leave "upcoming": a past calendar item (an
   auction, a record date) is removed, a past event that matters moves to the page's news form. Add the next dated
   items from official calendars (issuer distribution schedule, index rebalance releases, Treasury auction schedule,
   FOMC and Bank of Canada dates, CPI release dates, a foundation's upgrade date). A date inferred from a pattern is
   shown as the month ("Dec 2026") with no commentary.
8. **Sentences with numbers.** Every sentence whose number or date changed is rewritten with the new value — no other
   edit to it. A sentence that is now false (a fee cut, a renamed fund or index, "near its 52-week high", "the curve
   is inverted") is corrected in the fewest words. No new analysis, no new sections, no forecasts. The commentary
   block is untouched unless a sentence in it is now false.

## Delta box (numbers-only variant)
Insert immediately before the `<!-- ============ 01 ...` comment; if the page already has one, replace it (the new
prior = the old edition's as-of and value). If the page has no `.tg-d` CSS, copy `claude/briefs/delta-box.css` (the
whole file) into the main style element just before its closing tag. `data-prior-price` / `data-price` are plain
numbers (no $, %, commas): the price, or the yield for a bond page.

```html
<section class="tg-d tg-d--price" data-prior-as-of="YYYY-MM-DD" data-prior-price="P0" data-as-of="YYYY-MM-DD" data-price="P1">
  <div class="tg-d-top"><span class="tg-d-tag">Monthly update</span><span class="tg-d-when">D Mon YYYY &rarr; D Mon YYYY &middot; N days</span></div>
  <p class="tg-d-claim">One factual sentence: what moved most since the last edition. No forecast, no verdict.</p>
  <div class="tg-d-move"><div class="tg-d-px">$P0<span>PREVIOUS EDITION</span></div><div class="tg-d-arw">&rarr;</div><div class="tg-d-px">$P1<span>THIS EDITION</span></div><div class="tg-d-pct up|dn">+x.x%</div></div>
  <p>Two to four sourced changes besides the price: a fee change, a distribution, a new on-the-run issue, a holdings shift, a new SEP.</p>
  <p class="tg-d-check">Updated at this edition: <sections>. <b>Carried over with their dates:</b> <figures with no newer value on or before the as-of>.</p>
</section>
```
Bond pages show yields (`4.12%` → `4.30%`) and the change in pp (`+0.18 pp`); `up` / `dn` follow the sign of the
value's change. Use `tg-d--fix` (tag "Corrected in this edition") only when you correct an error in the previous
edition, and say what it was.

## Verify
- ETF and crypto: `py -3 tools/chart_audit.py <family>/<slug>` → 0 wrong points.
- Economic indicator: `py -3 tools/indicator_audit.py indicators/<slug>` → `ok`, wrong 0, unmatched 0, series cited
  True (every chart point against FRED / Bank of Canada Valet at the page's dp).
- Bond & cash: compare every point you appended or changed with the official daily file (scratch script in your temp
  folder): each equal to the source at the page's 2 dp.
- `py -3 tools/verify.py reports/<family>/<slug>_analysis.html` → PASS (header value == last chart point, 52-week
  range contains it).
- Extract each inline `<script>` body to your temp folder and `node --check` it. LF only; no `tg-sitenav`; exactly one
  `.tg-d` section.
The runner re-runs verify, chart_audit (ETF and crypto), indicator_audit (indicators), node --check and the
delta-box count itself, and commits nothing that fails.

## Return (short, no file contents)
`NO CHANGE` (and why) when there was no newer data; otherwise: 1 verify line, chart_audit or bond comparison
result, node check · 2 previous as-of/value → new as-of/value, with the source URL · 3 every changed figure,
one line each: old → new, source and its date · 4 every recomputed figure with its formula and window · 5 figures
carried over with their dates (no newer value on or before the as-of) · 6 flag list for the checker (claim — why
doubtful — where you looked) · 7 `PITFALLS:` errors found in the previous edition or caught in your own draft.

## Checker (independent check of the refreshed report)
Read `claude/PITFALL_RULES.md` and this brief. Never trust the builder's "verified": re-confirm on pages you fetch.
- Resolve every builder flag: confirm, fix, or remove. No hedge or process caveats on the page.
- Re-confirm: the header value for the as-of date and its change; the as-of is the latest settled close / published
  value on or before the run date and nothing on the page is dated after it; every chart point appended or changed
  (ETF/crypto: chart_audit; bonds: the official daily file); the 52-week range; the fee and its document; net assets
  or market cap; one distribution or the yield; at least three other changed metrics; the events moved and added.
- Recompute volatility, Sharpe, beta and drawdown from your own monthly series: each within rounding of the page.
- Grep the page for the previous edition's header value, as-of date, 52-week bounds and the dropped chart months:
  every remaining use must be about that date on purpose (rule A).
- Delta box: exactly one `.tg-d`, `tg-d--price` (or `tg-d--fix` when the edition corrects the previous one), data
  attributes equal to the page's values.
- Run the checks in "Verify" and report them verbatim. Return in your agent file's format with a `VERDICT:` line
  (PUBLISH, or HOLD with the reason) and a `PITFALLS:` line.
