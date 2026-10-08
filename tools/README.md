# tools

Build and check scripts for the site. Run every one from the repo root with `py -3 tools/<name>.py`.
Each finds the repo from its own location, so the working directory only matters for the paths you pass;
`--repo PATH` points any of them at another checkout. `-h` lists a script's options.

| Script | What it does | Writes |
|---|---|---|
| `manifest.py` | the machine-readable manifest of every stock report | `data/reports.json`, `data/reports/*.json` |
| `style_tags.py` | the Value / Growth / Income … style tags | `data/style_tags.json` |
| `card_tags.py` | everything on a report card besides the index badges; pages that predate a print, from the refresh queue | `data/card_tags.json`, `data/new_results.json` |
| `asset_cards.py` | the ETF, crypto and bond cards on the reports index | `reports/index.html` |
| `chrome.py` | the one site nav and footer on every chrome page | the pages in its `PAGES` list |
| `glossary.py` | the finance and poker & gambling glossaries (Learn · Table Talk) from their data, and their term counts on the Table Talk page; fails when a recurring tear-sheet label has no entry (`--check`: a page or a count out of date) | `learn/table-talk/finance.html`, `learn/table-talk/poker.html`, the counts in `learn/table-talk/index.html` |
| `verify.py` | pre-publish gate for report pages | nothing |
| `chart_audit.py` | every chart point against Yahoo month-end closes | nothing in the repo |
| `auto_refresh.py` | unattended refreshes of the due reports (headless builder + checker), onto a review branch; `--assets`: the monthly numbers-only refresh of the ETF, crypto and bond & cash reports | branch `claude/auto-refresh`, `tasks/queue/runs/` |
| `refresh_queue.py` | which reports went stale on an earnings print, when each refresh is due, its tier | `tasks/queue/` (git-excluded) |
| `global_calendar.py` | earnings dates the Nasdaq calendar misses (home listings abroad, US-listed global names it has no print for), from stockanalysis.com, HKEX board meetings and `data/ir_calendar.json`; run by `refresh_queue.py` | `global-<date>.json` in the queue's calendar cache |
| `refresh_data.py` | the number layer of a refresh: settled close, chart, 52-week range, returns, P/E, yield, short interest, EPS surprise | `facts.json`, `stale_hits.txt`; with `--write` the report's structured fields |
| `build_chips.py` | the chip and card-back SVG masters | `assets/chips/`, `assets/cards/` |

Three shared modules are not run on their own. `reportlib.py` is how a report page is read (the title, as-of
date, header price, chart series, 52-week range, metrics table, page skeleton); `reportpatch.py` is its mirror,
the count-checked writers of those structured fields (each must find its markup exactly once or it raises, naming
the page and the field); `repodata.py` is where the
files are (the repo root, report paths, the index page's cards, the manifest's data files and their record types).
A change to the report markup is made there once, including the metrics-table reader (`table_rows`) and what
makes a page structurally sound (`structure_problems`), which `verify.py` gates on and `manifest.py` records.
The Tables pages have their own builder, `tables/build_tables.py`, and their own checks in `tables/checks/`
(see `tables/CLAUDE.md`).

**Every check at once: `py -3 tools/run_checks.py`** (run it before pushing to main, which deploys). It runs the
tools unit tests (`py -3 -m unittest discover -s tools/tests -t tools`), the Tables builder tests
(`-s tables/checks -t tables`), the node checks of the craps engine, the simulator outcome tables and the
blackjack engine (`tables/checks/*.js`), and `py -3 -m mypy` when mypy is installed (config in `mypy.ini`).
The scripts need Python 3.11 or later and the standard library only (`build_chips.py` alone needs fontTools).
Every script's `main()` returns its exit status.

After a batch of report builds or refreshes: `manifest.py`, then `style_tags.py`, then `card_tags.py`.

## `manifest.py` — builds `data/reports.json` and `data/reports/*.json`

    py -3 tools/manifest.py                  # rebuild the manifest
    py -3 tools/manifest.py --full-metrics   # include the full metrics table

Extracts everything from the published report HTML rather than from any
separate record, so the manifest cannot drift from what is actually on the
site. A field it cannot parse is left out of the record, and the record's
warnings say why; nothing is guessed. Key metrics (P/E, EPS, yield, beta, FCF …)
are stored as a number when the cell is a plain number, otherwise as the cell's
text ("n/m", "$1.2B"); read them with `reportlib.first_number`. Each record's `fin_table` holds the
metrics-table cells the style tags use (P/E, revenue growth, ROIC, debt-to-equity, beta) as page text
(schema_version 2, 26 Sep 2026); `style_tags.py` reads them from there and stops if the manifest is older.

**Run it after every batch, and after any index rebuild.** The top-level
`data/reports.json` carries a `reconciliation` block — report files vs index
cards, uncarded reports, orphan cards, structure and chart failures — which is
the check that catches an interrupted publish. It is also the answer to "what is
stale?": the `index` array is `[ticker, slug, sector_key, as_of, price]` for
every report in one ~18 KB fetch, no shard needed. Consumers read the shards
listed under `shards`; a shard file an older build left behind is removed.

### Why it is sharded

A single file is ~208 KB, which cannot be published through the GitHub
connector: one `push_files` call has to carry the whole file, and that is
roughly 113k tokens of minified JSON. Sharding by sector is also the better
shape — a consumer that wants one sector fetches ~18 KB instead of the lot.

## `verify.py` — pre-publish structural gate

    py -3 tools/verify.py reports/aapl_analysis.html   # named reports
    py -3 tools/verify.py                              # every report, stock and asset

Checks document skeleton (including `</head>` and matched `<style>` tags),
exactly two canvases (three for bond/cash reports under `reports/fixed/`, which
add a yield-curve chart), equal `labels`/`prices` array lengths, final chart
value == header price to the cent, that the 52-week range contains the price
(a page with no readable 52-week range fails; every report had one on 26 Sep 2026),
that the `<title>` ticker matches the file name, no embedded site nav, and that the page loads the
pinned Chart.js 4.4.1 build. A path that is not a file is a FAIL. The date column is the as-of date read by
`reportlib.as_of`, the same reader the manifest uses.
Prints one PASS/FAIL line per report and **exits 1 if any report fails**.
P/E is printed as stated/calculated (price ÷ EPS) and is deliberately not part
of PASS: fix the pattern, not the report's prose, when they disagree.

Run it on new reports **before** pushing. Two reports (AEP, DLR) reached the
live site with no doctype, html, head or body tags at all, because they were
built five days before this check existed; they were repaired on 15 Sep 2026.

`chart_audit.py` checks an ETF or crypto report when it is named with its folder
(`etf/arti`, `crypto/btc`; since 5 Oct 2026; its Yahoo symbol is in `YAHOO_SYMBOL`,
e.g. `ARTI.TO`, `BTC-USD`); a run with no names still covers the stock reports only.
Bond reports (`reports/fixed/`) chart yields, not prices, and are checked against
Treasury / Bank of Canada daily files by the checkers' own scripts. `LAUNCH` holds
the first month-end of a security whose Yahoo ticker was recycled (ARTI: Mar 2024):
Yahoo rows before it are dropped, and any chart point before it fails the audit.
Brief: `claude/briefs/BUILD_ASSETS.md`.

## `chart_audit.py` — every chart point vs Yahoo month-end closes

    py -3 tools/chart_audit.py                 # whole library
    py -3 tools/chart_audit.py aapl intc       # named reports
    py -3 tools/chart_audit.py etf/arti crypto/btc   # ETF and crypto reports

`verify.py` only checks that the last chart point equals the header price. This
checks all the others, reading each report's ticker and as-of date from the page
itself, so a new or just-refreshed report is checked before `manifest.py` runs
(a slug with no page is an error, exit 1): a point is wrong when it is more than 3% from Yahoo's
split-adjusted month-end close *and* from its dividend-adjusted close. It also
lists series that are dividend-adjusted without saying so. **Exits 1 on any
wrong point or fetch error.** Read-only on the repo; caches Yahoo responses in
the system temp folder under `ttg_chart_audit/`, and fetches a series again when
the cached one ends before the report's as-of month. Required at 0 wrong points
on every new build and every refresh (see `claude/briefs/`). The 22 Sep 2026 run
found reconstructed month-ends on ~60 live reports.

Two basis steps are not errors and are listed separately as BASIS STEPS: a
split dated after the report's as-of (the report stays on its as-of share
basis, so Yahoo's close is scaled back up), and a real pre-spin close where
Yahoo books the spin-off as a small fractional split (IP, T, WDC, MMM …).
Before 23 Sep 2026 the parser skipped charts declared with `var`/`let` or with
labels like `'Sep \'21'` / `"Oct '21"`, so 13 reports were never audited.

## `refresh_queue.py` — the earnings refresh queue

    py -3 tools/refresh_queue.py                     # as of today; --today YYYY-MM-DD to replay a day

Crosses the Nasdaq earnings calendar (one file per day, cached once per user in `%LOCALAPPDATA%/ttg-refresh-queue/calendar` and shared by every checkout; the last 7 days are
re-fetched each run) with each report's as-of date from the manifest. For every report whose company reported
after its as-of: the release date and time, the T+2 as-of (NYSE holidays built in, `claude/briefs/REFRESH.md`),
the status (upcoming, waiting for T+2, due, overdue after 5 sessions), the first-session move (Yahoo daily
closes) and the tier: T1 for Dow 30, Nasdaq-100, a market cap of $200B or more, an EPS surprise of 10% or more,
or a first-session move of 5% or more; T2 otherwise (the builder may still raise it on guidance or news).
Writes `tasks/queue/queue.json` and `tasks/queue/today.md`, never the repo: `tasks/` is excluded from git.
Nasdaq often drops a release's time once it has happened; the queue keeps the time an earlier fetch saw, and
with no time at all it assumes after the close (the later T+2) and takes the larger of the two possible moves.
Exits 1 if any calendar day could not be fetched, or any page of the global calendar (below) failed.
The prints of the names Nasdaq does not list come from `global_calendar.py` and are added to Nasdaq's; queue.json
carries its coverage under `global_calendar` (names looked up, how many have a date, which have none).

## `global_calendar.py` — earnings dates for the names Nasdaq does not list

    py -3 tools/global_calendar.py          # what it finds today (looks up every global name; refresh_queue skips the ones Nasdaq lists)

Covers every report whose `<title>` ticker is a home listing abroad (`.HK .KS .SZ .SS .TW .T .PA .SW .DE .MC .MI
.AS .ST .L .SR .NS .AX .SI`) and every US-listed global name (a card with `data-gl`) that has no print in the run's
Nasdaq calendar (Oki, 8 Oct 2026). Sources, best first when two give the same release (within 7 days):
`data/ir_calendar.json` (kept by hand: revenue-only and trading updates read on the company's own IR calendar, with
that page as `source`); HKEX's board-meeting list (`www3.hkexnews.hk/reports/bmn/ebmn.htm`, results meetings of the
Hong Kong names); each name's stockanalysis.com statistics page (`/quote/<exch>/<code>/statistics/`, US names
`/stocks/<ticker>/statistics/`; `SA_PAGE` holds the exceptions, e.g. Ping An's HK page is a 404 so its Shanghai A share
is read); and what the previous day's run saw confirmed. No Yahoo, no JPX/TDnet. Each stockanalysis page is read at
most once a day: `robots.txt` is read first and obeyed, requests are 3 s apart with a generic browser user agent and
nothing personal, and the day's result (pages with their `<title>`, HKEX rows, merged events) is cached as
`global-YYYY-MM-DD.json` in the queue's calendar cache; a second run that day fetches only what failed. A page gives
either "The next confirmed|estimated earnings date is …" or "The last earnings date was …", sometimes with "before
market open" / "after market close"; a Saturday "confirmed" date is kept as estimated, and a past date counts only
when it was reported or confirmed. The prints carry no EPS, so the tier comes from index membership and the
first-session move (Yahoo daily closes, symbols from `chart_audit.YAHOO_SYMBOL`). T+2 still runs on the NYSE
calendar, not the home market's. Coverage on 8 Oct 2026: all 63 home listings and 31 US-listed global names dated
(dates from stockanalysis for 59 home listings, the IR file for 5, HKEX for 2, some from more than one; 15 home
listings had only an estimated next date).

## `auto_refresh.py` — unattended refreshes onto the review branch

    py -3 tools/auto_refresh.py --dry-run          # what would run today, and the first builder prompt
    py -3 tools/auto_refresh.py                    # the scheduled run (--base origin/main by default)

Keeps its own worktree (`.claude/worktrees/auto-refresh`, branch `claude/auto-refresh`, no upstream), merges the
base in, copies the private agent files in, runs `refresh_queue.py`, and takes the due and overdue reports: every
T1, then up to 8 T2 (`--t2-cap`), at most 2 attempts per report and print. `--tiers T1` or `--tiers T2` limits a run to one tier: the scheduled runs are T1 daily at 06:30 and T2 on Mondays at 17:30, a few hours before the weekly usage reset (Oki, 2 Oct 2026). For each, four at a time (`--jobs`):
a headless `claude -p --agent ttg-report-builder`, then `--agent ttg-report-checker` with the builder's return,
both in `dontAsk` mode with the tool allow-list in the script (no git, no deletes; denials are logged). Then it
re-runs `verify.py` and `chart_audit.py` itself and commits the report only if both pass, LF only, and the checker
did not say HOLD; anything else is reverted, with the rejected page and both agents' JSON results kept in
`tasks/queue/runs/<date>/`. After the reports: manifest, style and card tags, `run_checks.py`, push of the review
branch. Nothing reaches main until Oki merges it. The checkers' PITFALLS lines collect in
`tasks/queue/pitfalls_pending.md` for the next retro. One run at a time: every run except a dry run takes an OS lock
on `tasks/queue/run.lock` in the main checkout, and a run that finds it held waits (polling each minute, up to 12
hours, then ALERT); the OS drops the lock when a run's process ends, so a crash never leaves it held.

### `--assets` — the monthly numbers-only refresh of the ETF, crypto and bond & cash reports

    py -3 tools/auto_refresh.py --assets --dry-run                     # what would refresh today, and one builder prompt
    py -3 tools/auto_refresh.py --assets --dry-run --today 2026-11-02  # what a later run would take
    py -3 tools/auto_refresh.py --assets --builder-model sonnet        # the scheduled run

These reports have no earnings print, so they would freeze at their build date (Oki, 8 Oct 2026). The asset run
takes every report under `reports/etf/`, `reports/crypto/` and `reports/fixed/` whose banner as-of is 28 days old or
more (`--min-age`; `--families etf,crypto,fixed`; `--only etf/voo` or `voo`), oldest first, and gives each to a
headless builder and then a checker with `claude/briefs/REFRESH_ASSETS.md` (new as-of = the last settled close or
the latest official daily value on or before the run date; header, banner, chart month-ends, 52-week range, metrics,
holdings, distributions, events and every sentence whose number changed; a `tg-d--price` "Monthly update" delta
box). The indicator-rate pages (`INDICATORS` in `asset_cards.py`: SOFR, EFFR, CORRA) are refreshed like the others
for now. Same worktree, branch, allow-list, parallelism and commit-or-revert as the earnings run; the gates are
`verify.py`, `chart_audit.py` for ETF and crypto pages (bond pages chart yields, which the agents check against the
official daily file), `node --check` on every inline script, exactly one delta box, LF only. A builder that finds no
newer data changes nothing (`unchanged`, no checker). Attempts count per report and run month (2 a month). After the
reports: `asset_cards.py`, the manifest and the tags, `run_checks.py`, push; the summary is
`tasks/queue/runs/<date>-assets.md`, and any report not committed raises an ALERT. 28 days is the shortest gap
between two first Mondays, so every page refreshed at one monthly run is due at the next. The dry run reads the pages
of the checkout it runs from (`--repo`) and touches no worktree. Scheduled by
`%LOCALAPPDATA%\ttg-refresh-queue\ttg-assets.cmd` (first Monday, 17:30).

## `refresh_data.py` — the scripted number layer of a refresh

    py -3 tools/refresh_data.py ccl --as-of auto --out DIR --write   # pre-pass (before the builder)
    py -3 tools/refresh_data.py ccl --post --out DIR [--check]       # post-pass (after it); --check changes nothing

Design and Oki's decisions: `tasks/refresh-data-design.md`. As-of `auto` = the latest session whose date's 20:00
New York time has passed (never a session still trading). From Yahoo daily bars and SPY/QQQ it computes the header
price and change, the chart carried to the as-of (existing points kept; the old as-of point becomes its month-end
close; missing month-ends appended; labels in the page's own style; points rescaled and flagged if a split went ex
between the editions), the intraday 52-week range with dates, 1-year / 5-year / chart-window price returns, RSI(14)
and 50/200-day averages, dividends and the yield on the page's own basis (its "$X ÷ $price" formula, else TTM or
annualised, whichever reproduces the previous edition), trailing P/E from the page's EPS cell; from Nasdaq, short
interest (Nasdaq-listed stocks only) and EPS against Nasdaq's consensus. `facts.json` carries every value with its
source URL, fetch time, as-of and basis; `stale_hits.txt` lists each line still showing an old price, chart value,
range, P/E, yield or as-of date. `--write` changes structured fields only, never prose; the header price, banner
date and chart are written together or not at all. The post-pass fails (exit 1) when the page no longer matches
facts.json (as-of, price, the script's chart points, 52-week range, the delta box's data attributes) and
recomputes P/E and a formula yield from the page's final cells. Analyst consensus and SEC figures stay with the
agents. Coverage on 2 Oct 2026: header price and 52-week range on all 544 stock reports, banner 543 (FCX's date
range), chart 540 (DOW hard-codes ma3/ma10/rsi; FDXF, HONA, SPCX are not monthly), change 537 (prose variants).
`auto_refresh.py --data-layer` runs both passes around the builder and gates on `--post --check` (opt-in).
The pre-pass trims the chart to `--window` points (default 61: five years of month-ends + the as-of point; `0` = off),
shifting the `events` indices and dropping those that fall off (FISV, whose script hard-codes an index, is not
trimmed); `--fix-points` (on under `--data-layer`) replaces kept points more than half a cent off Yahoo's month-end on
the page's basis, skipping spin basis steps, missing months and post-as-of splits, and lists them in facts.json
`fixed_points` and stale_hits (rule A).

## `build_chips.py` — chip and card-back masters

    py -3 tools/build_chips.py --font cinzel-latin-700-normal.woff --mark ttg-chip.svg

Neither input is in the repo: the font is Cinzel 700 (the `@fontsource/cinzel`
package ships the .woff) and the mark is `ttg-chip.svg`, the Instagram chip
artwork. Needs `py -3 -m pip install fonttools`.
