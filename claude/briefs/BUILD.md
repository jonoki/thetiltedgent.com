# Builder brief — one TTG stock report

**Before anything else, read `claude/REPORT_PITFALLS.md`** — the running log of errors earlier runs made, each with the rule that prevents it. Treat every rule there as part of this brief.

REPO: C:\Users\jon_o\Desktop\Coding projects\thetiltedgent.com (Windows, Git Bash). Write exactly ONE file: reports/<slug>_analysis.html (slug = lowercase ticker, dots removed). Touch nothing else in the repo. Do NOT git add/commit/push — the orchestrator verifies and publishes. Temp files go ONLY in a per-ticker folder $TEMP/ttg_<slug>/ (other builders run in parallel and share $TEMP — never use generic names).

## Step 0 — identity
Confirm on a fetched page what company trades under the ticker, where it came from (renames, mergers, spin-offs), and that it is a current S&P 500 constituent. Tickers get recycled: digrin's "P" page is old Pandora, not Everpure. If it is not in the S&P 500 or identity is unclear, STOP, write nothing, report why.

## Template
Accent colour: never red or red-orange (it clashes with the site's loss/bear red); pick a colour distinct from green/red/amber/blue/purple chart lines.
Copy structure, CSS, section order and chart script of reports/ctsh_analysis.html exactly (read the whole file). House style: Playfair headings; one distinct per-company --accent (also used in the chart gradient rgba). Sections in CTSH order: amber "⚠ Static data as of <Month D, YYYY> (...)" banner, hero, 01 Company Overview, 02 Core Businesses (seg-bar + biz-cards), 03 Moat & Vulnerabilities, 04 Key Financial Metrics, 05 Analyst Consensus, 06 Catalysts, 5-year price + RSI charts, bull/bear, risks, disclaimer.
Adapt metrics to the model: banks — NIM/ROTCE/CET1/efficiency, gross margin & current ratio n/m; REITs — lead with FFO/AFFO; insurers — combined ratio (not brokers); utilities — rate base, allowed ROE.
REQUIRED vs CTSH: wrap the metrics table as `<div class="fin-scroll"><table class="fin-table">…</table></div>` and add right after the .fin-table CSS rules:
.fin-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.fin-scroll > .fin-table { min-width: 760px; }
The metrics table must have a row whose label cell is exactly `EPS (TTM)` (tooltip span allowed) and a `Trailing P/E` row. Never include the string "tg-sitenav". LF line endings, UTF-8.

## Data rules (hard — a plausible fabrication is the worst outcome)
- Price: the most recent settled close — a stockanalysis.com/stocks/<t>/history/ row that HAS an Adj. Close value. (WebFetch needs a domain surfaced by a WebSearch first; one search per new domain.) Header .price-current == LAST value of `prices` to the cent. Banner date = that close's date.
- Chart: ~60 MONTHLY closes: `const labels = [...]`, `const prices = [...]`, equal lengths, last point = the settled close. digrin.com/stocks/detail/<T>/price "Real price" column is the usual source (ignore its header price); cross-check the last two month-ends against stockanalysis daily rows. Yahoo finance.yahoo.com/quote/<T>/history/?frequency=1mo is the fallback. Never daily or <5y data under a 5-year heading; if <5y of history exists, say so in the heading/note.
- Every number from a fetched page. Unsourced → "n/v"/"—"/"not sourced". Estimates labelled. Trailing P/E == price ÷ TTM EPS (check arithmetic): compute it from the page's own price and EPS cells, never copy a data site's P/E field, which divides by unrounded EPS (10 reports were off on 26 Sep 2026). 52-week range must contain the price. If you recompute market cap etc. at your price, say so.
- Named analyst calls, executives and quotes ONLY if seen on a fetched page.
- Voice, reader and gambling-company rules: CLAUDE.md (Voice, Reader, Gambling operators). Keep the disclaimer.
- Check history (splits, spin-offs, mergers, bankruptcies) before trusting long-run per-share series.

## Verify
`py -3 tools/chart_audit.py <slug>` must report 0 wrong points (every chart point within 3% of Yahoo's month-end close, or of its dividend-adjusted close if the chart says it is dividend-adjusted).
`py -3 tools/verify.py reports/<slug>_analysis.html` must print PASS and its pe=stated/calc pair must agree (±0.1). Extract the <script> body to $TEMP and `node --check` it. Fix until clean.

## Return (short, no file contents)
1 verify line + chart_audit line · 2 index-card company name · 3 sector key (communicationservices consumerdiscretionary consumerstaples energy financials healthcare industrials materials realestate technology utilities) · 4 industry label in index style — reuse one of the existing labels in reports/index.html's #find options when one fits · 5 S&P 500 add date YYYY-MM-DD + source · 6 Nasdaq-100 member now? · 7 price, date, source URLs · 8 anything unsourced or doubtful (brief) · 9 `PITFALLS:` any error class from REPORT_PITFALLS.md you caught yourself mid-build (letter + one-line example) — this feeds the log.

PRIVACY: never put the user's email, name or any personal data in any request (headers, user-agents, query strings). Read sec.gov with WebFetch; never add a contact user-agent yourself. If WebFetch can't read a page, use another source.

## Lessons from the last checker round (hard rules)
- Nothing dated AFTER the banner date may appear (analyst calls, news, "52-week change", RSI, peer quotes). stockanalysis/companiesmarketcap live fields during the next session are intraday — recompute at the banner-date close or omit.
- Peer market caps: price at the banner-date close × shares outstanding, labelled as our calculation.
- Quotes must be verbatim from a fetched page; otherwise paraphrase and attribute.
- Analyst calls: firm, analyst, rating, prior→new target and date must all be on a fetched page; drop what isn't.
- Search-result snippets and AI "summaries" are not sources. Label them ("as summarised by …") or leave the claim out.
- Never write a count or superlative ("five straight years", "only cut", "same week") without checking it against your own data.
