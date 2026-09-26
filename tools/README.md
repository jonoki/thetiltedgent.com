# tools

Build and check scripts for the site. Run every one from the repo root with `py -3 tools/<name>.py`.
Each finds the repo from its own location, so the working directory only matters for the paths you pass.

| Script | What it does | Writes |
|---|---|---|
| `manifest.py` | the machine-readable manifest of every stock report | `data/reports.json`, `data/reports/*.json` |
| `style_tags.py` | the Value / Growth / Income … style tags | `data/style_tags.json` |
| `card_tags.py` | everything on a report card besides the index badges | `data/card_tags.json` |
| `asset_cards.py` | the ETF, crypto and bond cards on the reports index | `reports/index.html` |
| `chrome.py` | the one site nav and footer on every chrome page | the pages in its `PAGES` list |
| `verify.py` | pre-publish gate for report pages | nothing |
| `chart_audit.py` | every chart point against Yahoo month-end closes | nothing in the repo |
| `build_chips.py` | the chip and card-back SVG masters | `assets/chips/`, `assets/cards/` |

`reportlib.py` is not run on its own: it is what every script above knows about the repo and a report page
(the title, header price, chart series, 52-week range, page skeleton, index cards and the manifest's files).
A change to the report markup is made there once, including the metrics-table reader (`table_rows`) and what
makes a page structurally sound (`structure_problems`), which `verify.py` gates on and `manifest.py` records.
The Tables pages have their own builder, `tables/build_tables.py`, and their own checks in `tables/tests/`
(see `tables/CLAUDE.md`).

Tests: `py -3 -m unittest discover -s tools/tests -v`. Standard library only, like the scripts
(`build_chips.py` alone needs fontTools). Every script's `main()` returns its exit status.
Type check: `py -3 -m mypy` from the repo root (config in `mypy.ini`; mypy is not needed to run the scripts).

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
that the `<title>` ticker matches the file name, and no embedded site nav.
Prints one PASS/FAIL line per report and **exits 1 if any report fails**.
P/E is printed as stated/calculated (price ÷ EPS) and is deliberately not part
of PASS: fix the pattern, not the report's prose, when they disagree.

Run it on new reports **before** pushing. Two reports (AEP, DLR) reached the
live site with no doctype, html, head or body tags at all, because they were
built five days before this check existed; they were repaired on 15 Sep 2026.

`chart_audit.py` does not scan `reports/etf/`, `reports/crypto/` or `reports/fixed/`
(24 Sep 2026): the ETF, crypto and bond reports were checked point by point with
the checkers' own scripts against Yahoo (ETF/crypto) or Treasury / Bank of Canada
daily files (bonds). Brief: `claude/briefs/BUILD_ASSETS.md`.

## `chart_audit.py` — every chart point vs Yahoo month-end closes

    py -3 tools/chart_audit.py                 # whole library
    py -3 tools/chart_audit.py aapl intc       # named reports

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

## `build_chips.py` — chip and card-back masters

    py -3 tools/build_chips.py --font cinzel-latin-700-normal.woff --mark ttg-chip.svg

Neither input is in the repo: the font is Cinzel 700 (the `@fontsource/cinzel`
package ships the .woff) and the mark is `ttg-chip.svg`, the Instagram chip
artwork. Needs `py -3 -m pip install fonttools`.
