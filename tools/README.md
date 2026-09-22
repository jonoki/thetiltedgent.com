# tools

Build and check scripts for the report library. Both read the repo; neither
writes anything but `data/`.

## `manifest.py` — builds `data/reports.json` and `data/reports/*.json`

    python3 tools/manifest.py .                  # rebuild the manifest
    python3 tools/manifest.py . --full-metrics   # include the full metrics table

Extracts everything from the published report HTML rather than from any
separate record, so the manifest cannot drift from what is actually on the
site. Anything it cannot parse is recorded as a warning rather than guessed.

**Run it after every batch, and after any index rebuild.** The top-level
`data/reports.json` carries a `reconciliation` block — report files vs index
cards, uncarded reports, orphan cards, structure and chart failures — which is
the check that catches an interrupted publish. It is also the answer to "what is
stale?": the `index` array is `[ticker, slug, sector_key, as_of, price]` for
every report in one ~18 KB fetch, no shard needed.

### Why it is sharded

A single file is ~208 KB, which cannot be published through the GitHub
connector: one `push_files` call has to carry the whole file, and that is
roughly 113k tokens of minified JSON. Sharding by sector is also the better
shape — a consumer that wants one sector fetches ~18 KB instead of the lot.

## `verify.py` — pre-publish structural gate

    python3 tools/verify.py reports/*_analysis.html

Checks document skeleton, exactly two canvases, equal `labels`/`prices` array
lengths, final chart value == header price, P/E ≈ price ÷ EPS, and that the
52-week range contains the price.

Run it on new reports **before** pushing. Two reports (AEP, DLR) reached the
live site with no doctype, html, head or body tags at all, because they were
built five days before this check existed; they were repaired on 15 Sep 2026.

## `chart_audit.py` — every chart point vs Yahoo month-end closes

    py -3 tools/chart_audit.py                 # whole library
    py -3 tools/chart_audit.py aapl intc       # named reports

`verify.py` only checks that the last chart point equals the header price. This
checks all the others: a point is wrong when it is more than 3% from Yahoo's
split-adjusted month-end close *and* from its dividend-adjusted close. It also
lists series that are dividend-adjusted without saying so. Read-only on the
repo; caches Yahoo responses under `$TEMP/ttg_chart_audit/`. Required at 0
wrong points on every new build and every refresh (see `claude/briefs/`).
The 22 Sep 2026 run found reconstructed month-ends on ~60 live reports.
