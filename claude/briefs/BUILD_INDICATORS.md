# Builder brief — one TTG economic-indicator report (Oki, 8 Oct 2026)

Economic indicators are rates and data that are not securities: you cannot buy them. They have their own family,
`reports/indicators/`, and their own hub under Learn (`/learn/indicators/`), not a tab on the reports page. First
version: rates, inflation, jobs. Bonds & cash keeps only what a reader can buy.

**Before anything else, read `claude/PITFALL_RULES.md`**, then in `claude/briefs/BUILD.md` the "Data rules", the
PRIVACY paragraph and "Lessons from the last checker round", and in `claude/briefs/BUILD_ASSETS.md` the "PRIVACY",
"Rules from the pilot checker rounds" and "Verify" sections. They all apply. Where this brief differs, this brief wins.

REPO: the worktree path your prompt gives. Write exactly ONE file: `reports/indicators/<slug>_analysis.html`. Do NOT
git add/commit/push, and do not edit the hub or any tool: the orchestrator runs `py -3 tools/asset_cards.py` after
the merge, which turns the hub card from "Coming" into a link. Temp files only in `$TEMP/ttg_ind_<slug>/`.

## The indicators
| slug | `<title>` code | Publisher (primary source) | Chart series (the audit's) | Chart plots | dp |
|---|---|---|---|---|---|
| `fedtarget` | FEDTARGET | Federal Reserve: FOMC statements and implementation notes | FRED `DFEDTARU` | upper limit of the target range, % (month-end + as-of day; the lower limit `DFEDTARL` may be a second dataset) | 2 |
| `bocrate` | BOCRATE | Bank of Canada: rate announcements | Valet `V39079` | target for the overnight rate, % (month-end + as-of day) | 2 |
| `prime` | PRIME | Federal Reserve H.15, bank prime loan rate | FRED `DPRIME` | prime rate, % (month-end + as-of day) | 2 |
| `cpi` | CPI | BLS, Consumer Price Index (CPI-U, US city average, all items) | FRED `CPIAUCNS` (BLS `CUUR0000SA0`) | 12-month % change, not seasonally adjusted (the basis of BLS's headline 12-month figure) | 1 |
| `corepce` | COREPCE | BEA, Personal Income and Outlays (PCE price index excluding food and energy) | FRED `PCEPILFE` | 12-month % change, seasonally adjusted | 1 |
| `unrate` | UNRATE | BLS, Employment Situation (household survey, CPS) | FRED `UNRATE` (BLS `LNS14000000`) | unemployment rate, %, seasonally adjusted | 1 |
| `payrolls` | PAYROLLS | BLS, Employment Situation (establishment survey, CES) | FRED `PAYEMS` (BLS `CES0000000001`) | monthly change in total nonfarm payrolls, thousands, seasonally adjusted | 0 |

Already built (moved from Bonds & cash on 8 Oct 2026, built as bond pages): `sofr` (FRED `SOFR`), `effr` (FRED `EFFR`),
`corra` (Valet `AVG.INTWO`). Read `reports/indicators/sofr_analysis.html` in full before you start: it is the
reference for components, CSS and the chart script. The series registry is `SERIES` in `tools/indicator_audit.py`; a
new indicator needs a row there and in `INDICATOR_HUB` in `tools/asset_cards.py` first (orchestrator), or the gates fail.

## Template
- Copy the components, CSS and chart script pattern of `reports/indicators/sofr_analysis.html` (static-data banner,
  hero with price-block and 4 meta-items, `.section` + `.section-title` "0N Title", fin-table inside `.fin-scroll`,
  chart-container, timeline, case-cards, risk-list, biz-card commentary, disclaimer), Chart.js 4.4.1 from cdnjs. Pick
  one per-report `--accent`, never red/red-orange, distinct from the green/red/amber/blue/purple chart lines.
- `<title>`: `<CODE> — <Name> | Economic Indicator`, CODE from the table (the official series id is also accepted).
  E.g. `CPI — US Consumer Price Index (CPI-U) | Economic Indicator`.
- Hero: badge = the code; meta items **Publisher · Frequency · Latest release (date, reference period) · Next release
  (date)**; "Family: Economic indicator". `.price-current` = the latest reading with its unit (`3.4%`, `+22K`, `4.2%`).
  When the reading is a range (the Fed's target range, `3.75–4.00%`), add `data-value="4.00"`: the end the chart
  plots. `.price-change` = the change from the prior period, labelled (`+0.2 pp vs August`, `vs +29K in August`);
  `.price-date` = reference period · publisher · release date.
- Banner: `⚠ Static data as of <Month D, YYYY> (<release> for <reference period>, released <date>)`. For a daily rate
  the as-of is the rate's own date, with its publication date when it is published a day later (as SOFR does).
- Eight numbered sections, in this order, then "Indicator Commentary" (2 biz-cards, factual), then the disclaimer:
  1. **01 What It Measures** — what the number is, in plain words first; who publishes it, in which release, how often;
     the publisher's own definition, quoted from a fetched page. Card row: Publisher · Frequency · Seasonally adjusted? ·
     First published (year).
  2. **02 How It's Built** — method from the publisher's documentation: the survey or market data behind it, sample
     size, weights or calculation (median of trades, index basket, survey response), seasonal adjustment, and the
     revision policy (when and how past values change). For a policy rate: who sets it, how often, how it is
     implemented (the corridor or operating band, from the central bank's own pages).
  3. **03 Strengths & Limits** — moat-list of what it captures well; "Key Limitations" risk-list (coverage gaps,
     sampling error the publisher states, lags, revisions, what it leaves out).
  4. **04 Latest Reading** — fin-table, dated column headers: latest value, prior period, a year earlier; the
     `12-Month Range` row (daily rates: `52-Week Range`), which must contain the header value; for inflation the
     monthly change (seasonally adjusted) and the main components (food, energy, core, shelter for CPI); for payrolls
     the revisions to the two prior months as the release states them and the main sectors; for unemployment the
     participation rate and U-6; for rates the policy range and the related rates. Table note: every formula, every
     source with its date.
  5. **05 What Moves It** — the drivers, sourced: policy decisions for the rates; components and their weights for
     inflation; hiring, layoffs and participation for jobs. The central bank's latest published projection for it
     (Fed SEP median with its release date; Bank of Canada MPR), only from the fetched document.
  6. **06 Next Releases** — timeline of the next 2–3 release dates and times from the publisher's own calendar (BLS
     release schedule, BEA release schedule, FOMC calendar, Bank of Canada schedule), reference period for each.
  7. **07 5-Year History** — Chart 1 `priceChart`: the official series (see "Chart" below) + 1/3/10-month MAs, chart
     note naming the series id, the units, "seasonally adjusted" or "not seasonally adjusted", and the source. Chart 2:
     a second view from the same publisher (monthly % change bars for CPI and core PCE, the employment level for
     payrolls, U-6 or participation for unemployment, the spread to the policy rate for a market rate), id named for
     what it shows (`momChart`, `levelChart`, `spreadChart`). No third canvas. h3 "Inflection points" (4–5, dated,
     with the value).
  8. **08 Why It Matters** — for markets and households, mechanically: what a rise or fall does to borrowing costs,
     savings rates, bond yields and share prices. Case-cards "When it rises" / "When it falls". Link to 3–5 related
     reports by slug through the viewer, e.g. `<a href="/reports/view.html?r=fixed/ust2y" target="_top">2-year
     Treasury</a>`, `r=indicators/sofr`, `r=etf/tip`; only slugs whose file exists (`ls reports/<family>/`).
- LF line endings, UTF-8, no `tg-sitenav`, no delta box on a new build.

## Chart
- `const labels = [...]`, `const prices = [...]` (the stock names, kept for the tools), equal length; the last value ==
  the header value (`data-value` when the header shows a range).
- **Monthly series** (cpi, corepce, unrate, payrolls): 60 points, the latest reference month last, labels `'Sep 26'`.
  No extra as-of point. Values at the table's dp, computed from the official series: 12-month change =
  100 × (x_t ÷ x_t−12 − 1); monthly change = x_t − x_t−1.
- **Daily rates** (fedtarget, bocrate, prime): the last observation of each of 60 months (last business day with a
  value — not FRED's monthly average), then the as-of day labelled `'Oct 2 26'`: 61 points, as on SOFR.
- Values are the latest vintage published on or before the banner date. Payrolls and PCE are revised: say so in the
  chart note ("latest revised values as of <banner date>").

## Rules (hard)
- **Data as of the latest release on or before the banner date.** Nothing published after it (rule B), including
  "nowcasts" and news about the next release.
- **Levels vs changes labelled, every time:** an index level, a rate (%), a 12-month % change, a monthly change in
  thousands — say which, and over what period, in every table row, caption and sentence that gives a number.
- **Seasonal adjustment labelled:** "seasonally adjusted" or "not seasonally adjusted" next to every series, in the
  chart note and in 04.
- **Revisions noted:** where the publisher revises (payrolls, PCE, seasonal factors), state its revision policy in 02
  from its own documentation and show the latest revisions in 04 as the release states them.
- **No forecasts** unless from a named, fetched source (Fed SEP, Bank of Canada MPR, a named survey with its date).
  No "economists expect", no consensus figures from news snippets.
- **Sources:** the publisher's own release, tables and calendar first (bls.gov, bea.gov, federalreserve.gov,
  newyorkfed.org, bankofcanada.ca); FRED (fred.stlouisfed.org) and Bank of Canada Valet for the series, cited by
  id. Read the FRED series notes and the publisher's terms for licensing before building (BUILD_ASSETS.md, "Data
  licensing"); a series whose notes restrict reproduction needs Oki's decision (BLOCK and say so).
- **No personal data in any request** (BUILD_ASSETS.md PRIVACY). Fetch FRED with `curl -s --ssl-no-revoke
  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>&cosd=<YYYY-MM-DD>"` and no custom User-Agent (a browser
  or custom User-Agent hangs); Valet with `https://www.bankofcanada.ca/valet/observations/<ID>/json?start_date=<date>`.
- Tone: plain and functional; describe, never recommend. Explain jargon in a clause (basis point, seasonal
  adjustment, core). No doubt caveats on the page: a figure you cannot source is "n/v", a sentence you cannot source
  is removed.

## Gates (run all; report each output verbatim)
```
py -3 tools/verify.py reports/indicators/<slug>_analysis.html
py -3 tools/indicator_audit.py indicators/<slug>
node --check $TEMP/ttg_ind_<slug>/script_<n>.js        (each inline <script> body, extracted)
```
- verify.py → `PASS` (skeleton, 2 canvases, labels/prices equal length, last point == header value, header value
  inside the `12-Month Range` / `52-Week Range` row, title code == slug or series id, Chart.js 4.4.1, no site nav).
- indicator_audit.py → `ok   indicators/<slug>: N points vs <ID> … | wrong 0 | unmatched 0 | series cited True`:
  every chart point equals the official series at the page's dp (tolerance 0.55 of the last digit), and the page
  cites the series id. Chart 2 is not audited by the tool: compare it with the official series in a scratch script
  and report the result.

## Return (short, no file contents)
1 verify line, indicator_audit line, node check, Chart 2 comparison · 2 banner date, header value, release and its
URL · 3 sources used (URL + date) · 4 every figure you calculated, with the formula · 5 anything unsourced or doubtful
· 6 template friction: anything in this brief that did not fit the data · 7 `PITFALLS:` classes from
REPORT_PITFALLS.md you caught mid-build.
