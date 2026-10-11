# Corrections log — fixes made to a live report without a new edition

Oki, 10 Oct 2026: a correction to a published report that keeps its banner date (a "same-edition" fix) is **not shown on
the live page**. It is recorded here instead, so builders and checkers learn from it: the orchestrator tallies each
row's pitfall class into `claude/REPORT_PITFALLS.md`, and a class that keeps recurring gets its rule into
`claude/PITFALL_RULES.md`, which every builder and checker reads first. (A refresh that corrects the previous edition
keeps its "Corrected in this edition" box, per `claude/briefs/REFRESH.md`.)

Add one row per corrected figure or claim, newest first. Class letters are those in `claude/PITFALL_RULES.md`.

| Date | Report | Was | Now | Why it was wrong | Class |
|---|---|---|---|---|---|
| 2026-10-10 | AAPL | Trailing P/E 35.9×, PEG 3.15 | 35.4×, 3.10 | Computed at the Aug 7 close, not the Aug 10 banner close | B |
| 2026-10-10 | AAPL | Upside +4.6%; EPS YoY +32.6% | +4.5%; +32.3% | Not recomputed from the page's own target and filings | F |
| 2026-10-10 | AAPL | Row label "P/E (Trailing)" | "Trailing P/E" | Non-standard label; verify and the index tools could not read it | J |
| 2026-10-10 | AXP | 5-yr total return ~+118% | ~+120% (dividends reinvested) | Matched neither basis (+115.4% added back, +120.3% reinvested) | F |
| 2026-10-10 | AXP | S&P 500 5-yr +80% price / +93% with dividends; lead 25 pp | +71% / +83%; 37 pp | Index figures wrong on every basis | F |
| 2026-10-10 | AXP | "Half the gain in eighteen months" | More than the whole gain in 26 months | Span miscounted; the run ($224) exceeded the 5-yr gain ($178) | F |
| 2026-10-10 | AXP | "22% drawdown" Dec→Mar | 18% | The two month-end closes cited give 18.2% | F |
| 2026-10-10 | DIS | Debt-to-equity 0.39 | 0.42 | Divided by equity incl. noncontrolling interests; the page names shareholders' equity | G |
| 2026-10-10 | GS | 5-yr price return +150.4%; total ~170%; ~22% a year | +150.8%; ~182%; ~23% | Not recomputed from the endpoints and Yahoo dividends | F |
| 2026-10-10 | GS | "Fell 22% in 2022"; "lost 27% to the Oct 2023 trough"; "cost 29% in 2022" | 31% (Jan–Jun 2022 closes); 34% from the Nov 2021 high; Oct 2023 a higher low | Peak and trough read from month-ends and prose, not daily closes | F |
| 2026-10-10 | GS | "Essentially all of the return since Nov 2024" | About 83% since Oct 2024 | Superlative not computed | F |
| 2026-10-10 | GS | Chart marker "Nov 2021 — cycle peak" | Aug 2021 month-end high | Marker sat on a month-end dip | A |
| 2026-10-10 | MCD | Forward P/E 20.13 (and "20.1x" ×4) | 20.63 | Not the page's own price ÷ its stated consensus EPS | F |
| 2026-10-10 | NFLX | Drawdown −46% | −49.5% close to close | Matched no basis; closing high set against an intraday low | F |
| 2026-10-10 | NFLX | "~40% below its high"; "rebound recouped a third" | ~43%; recovered the whole loss | Not recomputed at the banner close | F |
| 2026-10-10 | NFLX | Q2 drop "~9%" in one session; Apr 2022 "~$35 to ~$19 in one session" | ~9% over two sessions; $34.86 to $22.62 | Multi-day or month-end moves stated as one session | H |
| 2026-10-10 | NFLX | 2022 low "June 2022"; −76% from the series start | May 11, 2022 close; −76% from the Nov 2021 closing high | Date and base not checked against daily rows | F |
