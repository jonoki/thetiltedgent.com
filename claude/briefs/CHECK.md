# Checker brief — independent check of built or refreshed TTG stock reports

**Before anything else, read `claude/REPORT_PITFALLS.md`** — the running log of errors earlier runs made, each with the rule that prevents it. Treat every rule there as part of this brief.

REPO: C:\Users\jon_o\Desktop\Coding projects\thetiltedgent.com (Windows, Git Bash; Python is `py -3`). You check reports another agent built. They are uncommitted files in reports/. Edit ONLY your assigned reports/<slug>_analysis.html files. Do NOT git add/commit/push. Temp files go ONLY in $TEMP/ttgchk_<slug>/.

The builder rules are in `claude/briefs/BUILD.md` (and `REFRESH.md` for refreshes) — read them; the report must satisfy all of them. The orchestrator gives you the builder's flag list (a notes file path or inline).

## For each assigned report
1. Read the whole report.
2. Read the builder's flags for it — the builder's own list of doubtful claims. Resolve EVERY flag: confirm it on a fetched page, or fix the number, or soften/label it ("reported by …", "not sourced"), or remove it. Never leave an unsourced claim stated as fact.
3. Independently re-confirm, on pages YOU fetch: identity (company, current S&P 500 member), the header price = the settled close for the banner date (stockanalysis history row with Adj. Close, or Yahoo), the last two month-end chart points, market cap, TTM EPS and that Trailing P/E = price ÷ EPS, the 52-week range, every named executive, every named analyst call. Spot-check at least 5 other figures in the metrics table.
4. Split/spin/reverse-split history: if the chart mixes adjusted and unadjusted series, fix it so the series is consistent with the header price and label the adjustment in the chart note.
5. New builds: accent must not be red/red-orange. Existing pages: do NOT change the accent colour (Oki's decision pending).
5a. Run `py -3 tools/chart_audit.py <slug>` — 0 wrong points required; fix the series (and every claim derived from it) if not.
6. Re-run `py -3 tools/verify.py reports/<slug>_analysis.html` (PASS, pe pair within ±0.1) and `node --check` on the extracted script body. LF line endings.

WebFetch needs a domain surfaced by a WebSearch first (one search per new domain). stockanalysis.com blocks curl — use WebFetch.
PRIVACY: never put the user's email, name or any personal data in any request (headers, user-agents, query strings). Read sec.gov with WebFetch; never add a contact user-agent yourself. If WebFetch can't read a page, use another source.

## Return (short, no file contents), one block per report
- PITFALLS: one tag per correction you made, `<letter>:<short example>` using the classes in REPORT_PITFALLS.md (new class → `NEW:<description>`). Required — the orchestrator tallies these into the log.
- VERDICT: PUBLISH or HOLD (+ one-line reason for HOLD)
- verify line
- what you changed (one line each)
- anything still unconfirmed and how it is labelled on the page
- if asked for an index-card record (not the "Their hand" line): slug|Company Name|sectorkey|INDUSTRY LABEL (reuse an existing label from reports/index.html #find options, `&amp;` for &)|S&P add date YYYY-MM-DD|yes/no Nasdaq-100
