# Refresh brief — one TTG report, after an earnings print or material news

**Before anything else, read `claude/PITFALL_RULES.md`** — the prevention rule for every error class earlier runs made (the full log with examples is `claude/REPORT_PITFALLS.md`; open it only to look up an example). Treat every rule there as part of this brief.

REPO: C:\Users\jon_o\Desktop\Coding projects\thetiltedgent.com (Windows, Git Bash; Python is `py -3`). Edit exactly ONE file: reports/<slug>_analysis.html (it already exists and is live). Do NOT git add/commit/push. Temp files only in $TEMP/ttgref_<slug>/.

Also read and obey every data rule in `claude/briefs/BUILD.md`, including its "Lessons" section: settled close with Adj. Close, header price == last chart point, verbatim quotes only, nothing dated after the banner date, no aggregator/affiliate sites as sole sources (casino/gambling affiliates, DailyPolitical, crypto-exchange news, Substack, forums, TIKR/Quiver-only claims), no personal data in any request.

## When to run (timing window — do not start early)
- **Earnings:** the new as-of is the settled close of the **second full trading session after the release** (T+2). Pre-market release on day D → sessions D and D+1, as-of = close of D+1. After-close release on day D → sessions D+1 and D+2, as-of = close of D+2. Build the morning after that close settles (the stockanalysis row has an Adj. Close). Finish within **5 trading days** of the release; later than that, the queue marks it overdue.
  Why: by T+2 the call transcript is published, the day-1 reaction and day-2 follow-through are both in, the wave of analyst target changes (almost all land on days 1–2) has landed, and consensus pages have rolled forward. Building on the release day produced most of the "read next day", after-hours-vs-close and missing-analyst-call errors in the pitfalls log.
- **10-Q / 10-K details** often file 1–5 business days after the release. If the page needs a filing-only figure that isn't out yet, label it "per the release; 10-Q not yet filed" rather than waiting.
- **Material news without earnings** (M&A, CEO/CFO change, guidance change, recall/regulatory/legal event): as-of = settled close of the **first full session after the news**, built the next morning; if the news broke intraday, that day's session does not count.
- **Price move with no news found:** do not refresh; log "price only" in the queue.

## Why this refresh exists
The company reported earnings, or had material news, after this report's as-of date. The rule (TTG Reports Refresh Policy, 2 Sep 2026): a report is stale when the company reports, not when the price moves.

## Step 1 — read the current report in full
Record: its as-of date and header price (these become the delta box's "previous edition" values), what it says about the business, guidance, segments, catalysts.

Treat the previous edition as a claim to check, not a source. Executive bios, company history (splits, IPO, fiscal-year length), index membership and every count or superlative you keep must be re-confirmed on a fetched page or dropped. On 25 Sep 2026 the AZO edition carried a wrong CFO bio, a false "never split" and a wrong 53-week year; errors you find this way make the delta box `tg-d--fix`.

The same goes for holder lists and stakes, peer market caps and bubbles, segment figures and analyst calls carried in the old edition (29 Oct 2026 retro: 56 of 146 checker returns fixed a carried-over item). But a correction needs a fetched page that contradicts the old figure: a silent page or a failed fetch is not grounds, so keep the item and flag it (rule N; MTB dropped a true CPA, VRSN "corrected" right debt and cash). A `fix_points` change from the data layer is checked against a primary print before the delta box calls it a correction (EL.PA, IBE.MC).

Read the company's EDGAR 8-K list and Reuters/WSJ/Bloomberg news from the previous banner date to the new one, not only the release (missed in Oct: DGX's cyber-incident 8-K on the print day, JNJ's reported DePuy Synthes talks, CFO changes at T and CNC, DISH's Chapter 11 on CCI).

## TASK A — numbers (always)
New as-of = the most recent settled close (a stockanalysis history row WITH Adj. Close; do not use a row without it). Update:
- header price/change, banner date ("Static data as of <Month D, YYYY> …"), market cap and every price-derived ratio (recompute at the new close);
- chart: keep existing month-ends, add the missing month-end closes (digrin "Real price" / stockanalysis daily), end with the new close; labels/prices equal length; if a split/spin happened since, make the series consistent and label it; if `chart_audit.py <slug>` lists the page under ADJ-UNLABELLED, or the series is dividend-adjusted, rebase every point to the plain month-end close (Yahoo close / digrin "Real price") and sweep the prose for the old values (Oki, 8 Oct 2026);
- metrics table from the new quarter (EPS TTM, margins, FCF, debt, etc.), 52-week range as of the new date, consensus/targets as of the new date (drop anything dated after it);
- Global listings (in neither the S&P 500 nor the Nasdaq-100): the hero rank row carries home-market ranks/constituencies dated to the banner date from a fetched source; re-check each at every refresh, and drop any you cannot source as of the banner date (Oki, 8 Oct 2026);
- Section 02 segments, Section 05 analyst calls, Section 06 catalysts (the print moves from "upcoming" to "happened"; add the next one only if dated by the company or labelled estimated).
- Section 05 comes from a ratings table (StockAnalysis, MarketBeat) read at the banner date: every action from the previous edition to the banner date, post-print calls included; prior → new target from the table, never rebuilt from the old edition; an old call stays only if the table still lists it, and goes only when the table shows it superseded (DOV KMI TDY WRB VRSN, Oct 2026).
- Peer market caps and bubbles recomputed at the banner-date close; short interest at the latest settlement published on or before the banner date, dated, never dropped for a caveat; the dividend-yield Context cell holds `dividend ÷ header price` and no other `$x ÷ $y` (the post-pass reads the first one as the yield formula: PEP, GM, NUE).
- After the numbers, grep the page for the previous quarter (its name, period-end date and headline figures) and for "now", "latest", "currently": every such sentence describes the new quarter or carries its date, and metrics rows and pills use the same quarter (FITB, NOC, RF left Q2 statements after Q3). Read the old text as the Reader too, not only what you write: rule M jargon ("re-rating", "operating leverage", unexplained "bps") drew 125 checker fixes in Oct.

## TASK B — did the business change? (decide the tier honestly)
- **T1 Rewrite** if ANY: |EPS or revenue surprise| ≥ 10%; earnings-day move ≥ 5% (close-to-close on the first session after the print); guidance changed; OR significant company news since the print (M&A, CEO/CFO change, restructuring, major contract/regulatory/legal event, guidance withdrawal, dividend/buyback policy change). Dow 30 / Nasdaq-100 names default to T1; market cap alone does not (Oki, 8 Oct 2026). T1 = rewrite the narrative sections (overview, moat/vulnerabilities, bull/bear, risks, industry commentary) wherever the quarter changed the story.
- **T2 Numbers** otherwise: TASK A plus a short factual paragraph on the quarter; narrative untouched except where now false.
- "The business is unchanged; the multiple re-rated" is a correct and welcome finding. Do not manufacture a narrative to explain a price move.

## Delta box (required)
Insert immediately before the `<!-- ... 01 ... OVERVIEW` comment (the Company Overview section). If the page has no `.tg-d` CSS yet, copy claude/briefs/delta-box.css (the whole file) into the page's main <style> just before `</style>`. Markup — mirror reports/nvda_analysis.html exactly:

```html
<section class="tg-d tg-d--print" data-prior-as-of="YYYY-MM-DD" data-prior-price="P0" data-as-of="YYYY-MM-DD" data-price="P1">
  <div class="tg-d-top"><span class="tg-d-tag">Updated at the print</span><span class="tg-d-when">D Mon YYYY &rarr; D Mon YYYY &middot; N days</span></div>
  <p class="tg-d-claim">One-sentence verdict: what the quarter changed (or that it didn't).</p>
  <div class="tg-d-move"><div class="tg-d-px">$P0<span>PREVIOUS EDITION</span></div><div class="tg-d-arw">&rarr;</div><div class="tg-d-px">$P1<span>THIS EDITION</span></div><div class="tg-d-pct up|dn">+x.x%</div></div>
  <p><b>Quarter</b>: the headline figures vs consensus, guidance change, first-session reaction (close-to-close %).</p>
  <p>What happened since (news, analyst moves) — only sourced items.</p>
  <p class="tg-d-check">Updated at this edition: <sections>. <b>Not re-verified:</b> <list>.</p>
</section>
```
Use class `tg-d--fix` instead (tag "Corrected in this edition") ONLY if you find and correct an error in the previous edition — say what it was, and name the page that contradicts the old figure (rule N). Before you return: if your PITFALLS line lists any previous-edition error, the class is `tg-d--fix` (9 October refreshes left it `--print`). If the previous edition already had a delta box, replace it (keep the new prior = the old edition's as-of/price).

Entities: use `&rarr;` `&middot;` `&mdash;` or real UTF-8 characters; never mojibake.

## Verify
`py -3 tools/chart_audit.py <slug>` → 0 wrong points; every previous-edition chart point is re-checked, not assumed (11 of 17 refreshes on 22 Sep found the previous chart wrong). On a red or red-orange accent page the moving-average lines and their legend swatches are #cbd5e1, never #ef4444 (JNJ DAL HAL PHM, Oct 2026).
`py -3 tools/verify.py reports/<slug>_analysis.html` → PASS with pe pair within ±0.1 (or None/None when EPS ≤ 0 and the P/E row reads n/m); `node --check` on the extracted <script>; LF only; no "tg-sitenav"; exactly one `.tg-d` section.
`py -3 tools/index_rank.py <slug>` after the new banner date is in: it writes the header's "Mkt Cap Ranking" row (S&P 500 / Nasdaq-100 rank on the banner date) and the fine-print date, on member pages only (a global listing's row is re-checked by hand, TASK A). Member ranks are tool-written, never typed (Oki, 8 Oct 2026).
`py -3 tools/index_stats.py <slug>` after that: it rewrites Section 04's S&P 500 / Nasdaq-100 column for the new banner date from the members' reports, and the methods sentence's date. Never type an index figure; fix by hand any sentence it prints as LEFT (Oki, 8 Oct 2026). Non-US reports carry the same S&P 500 column; their home-index returns stay in the Context column, updated to the new banner date (Oki, 9 Oct 2026).

## Return (short, no file contents)
1 verify line · 2 tier (T1/T2) and the trigger(s) that decided it · 3 prior as-of/price → new as-of/price · 4 the print: date, figures vs consensus, guidance change, first-session move · 5 significant news since the print · 6 one-line list of every claim a checker should re-confirm · 7 `PITFALLS:` errors you found in the previous edition or caught in your own draft (letter + example).
