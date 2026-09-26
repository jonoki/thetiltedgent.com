# Refresh brief — one TTG report, after an earnings print or material news

**Before anything else, read `claude/REPORT_PITFALLS.md`** — the running log of errors earlier runs made, each with the rule that prevents it. Treat every rule there as part of this brief.

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

## TASK A — numbers (always)
New as-of = the most recent settled close (a stockanalysis history row WITH Adj. Close; do not use a row without it). Update:
- header price/change, banner date ("Static data as of <Month D, YYYY> …"), market cap and every price-derived ratio (recompute at the new close);
- chart: keep existing month-ends, add the missing month-end closes (digrin "Real price" / stockanalysis daily), end with the new close; labels/prices equal length; if a split/spin happened since, make the series consistent and label it;
- metrics table from the new quarter (EPS TTM, margins, FCF, debt, etc.), 52-week range as of the new date, consensus/targets as of the new date (drop anything dated after it);
- Section 02 segments, Section 05 analyst calls, Section 06 catalysts (the print moves from "upcoming" to "happened"; add the next one only if dated by the company or labelled estimated).

## TASK B — did the business change? (decide the tier honestly)
- **T1 Rewrite** if ANY: |EPS or revenue surprise| ≥ 10%; earnings-day move ≥ 5% (close-to-close on the first session after the print); guidance changed; OR significant company news since the print (M&A, CEO/CFO change, restructuring, major contract/regulatory/legal event, guidance withdrawal, dividend/buyback policy change). Dow 30 / Nasdaq-100 / mega-cap names default to T1. T1 = rewrite the narrative sections (overview, moat/vulnerabilities, bull/bear, risks, industry commentary) wherever the quarter changed the story.
- **T2 Numbers** otherwise: TASK A plus a short factual paragraph on the quarter; narrative untouched except where now false.
- "The business is unchanged; the multiple re-rated" is a correct and welcome finding. Do not manufacture a narrative to explain a price move.

## Delta box (required)
Insert immediately before the `<!-- ... 01 ... OVERVIEW` comment (the Company Overview section). If the page has no `.tg-d` CSS yet, copy the CSS string from tools/deltabox.py (the `CSS = """ … """` block) into the page's main <style> just before `</style>`. Markup — mirror reports/nvda_analysis.html exactly:

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
Use class `tg-d--fix` instead (tag "Corrected in this edition") ONLY if you find and correct an error in the previous edition — say what it was. If the previous edition already had a delta box, replace it (keep the new prior = the old edition's as-of/price).

Entities: use `&rarr;` `&middot;` `&mdash;` or real UTF-8 characters; never mojibake.

## Verify
`py -3 tools/chart_audit.py <slug>` → 0 wrong points; every previous-edition chart point is re-checked, not assumed (11 of 17 refreshes on 22 Sep found the previous chart wrong).
`py -3 tools/verify.py reports/<slug>_analysis.html` → PASS with pe pair within ±0.1 (or None/None when EPS ≤ 0 and the P/E row reads n/m); `node --check` on the extracted <script>; LF only; no "tg-sitenav"; exactly one `.tg-d` section.

## Return (short, no file contents)
1 verify line · 2 tier (T1/T2) and the trigger(s) that decided it · 3 prior as-of/price → new as-of/price · 4 the print: date, figures vs consensus, guidance change, first-session move · 5 significant news since the print · 6 one-line list of every claim a checker should re-confirm · 7 `PITFALLS:` errors you found in the previous edition or caught in your own draft (letter + example).
