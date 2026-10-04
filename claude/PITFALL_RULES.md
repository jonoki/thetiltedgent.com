# Pitfall rules — read this first (every report builder and checker)

The prevention rules only. The full log with examples and run tallies is `claude/REPORT_PITFALLS.md`: open it only to look up an example. Checkers tag every correction `PITFALLS: <letter>:<short example>`.

**A. Chart data.** Every point is a real month-end close copied from a fetched source (Yahoo monthly Close, or digrin "Real price" — see I); never type, round or estimate a value. One basis for the whole series, matching the header price: splits adjusted, dividends not (or labelled), spin-offs adjusted or labelled "not spin-adjusted". Run `py -3 tools/chart_audit.py <slug>`: 0 wrong points. After changing any point, sweep the text (prose, timeline, `events` labels, cards) for the old value and fix every month-end use. Compare price return with price return over the same window (SPY month-end close → banner-date close).

**B. Nothing after the banner date.** Everything price-dependent is recomputed at the banner-date close or removed. Every dated item ≤ banner date; a consensus page read later says "read <date>; latest action <date>". Check a stale-looking live figure against daily rows for the exact window.

**C. Sources.** Primary first (release, 8-K, 10-Q, proxy — sec.gov via WebFetch, no personal data in any request), then Reuters/Bloomberg/WSJ/CNBC/AP/trade press, then data sites. Aggregators, AI summaries and search snippets only *as* summaries, never the sole basis for a number or quote. Never: casino/gambling affiliates, DailyPolitical, crypto-exchange news, Substack, forums, TIKR/Quiver-only claims. Class actions: "alleges", attributed to the filing firm.

**D. Quotes.** Quotation marks only for words read verbatim on a fetched transcript or release, with the speaker named there; otherwise paraphrase and attribute. No truncation inside a quote without an ellipsis.

**E. Entity facts.** Executives, deal status, ownership: the company's own site or latest filing, dated. Facts carried over from the previous edition are re-verified, not inherited. S&P add date from the S&P DJI release when findable; Wikipedia dates labelled.

**F. Arithmetic, counts, superlatives.** Recompute every count, streak, superlative and % change from the page's data or a fetched series before writing it; if you can't compute it, don't claim it. Trailing P/E = header price ÷ the page's EPS (TTM) cell, never a data site's P/E field.

**G. Basis.** State the basis (GAAP/adjusted, fiscal year, source) beside every estimate; if sources disagree, show both or pick the primary and say why.

**H. Direction and cause.** Price reactions are close-to-close from daily rows, never intraday or after-hours headlines. Causes come from management's own words or are labelled as a reading.

**I. Data-site traps.** stockanalysis: the current session's row has no Adj. Close until settled — don't use it; live fields are intraday; fiscal-year labels can run a year ahead. digrin: header price stale (use the table); "Adjusted" is dividend-adjusted; "Real price" is not split-adjusted and can be back-adjusted for a spin-off — cross-check against Yahoo. Yahoo: close = split-adjusted, adjclose = + dividends; spin-offs appear as fractional "splits". Short interest carries its settlement date, never the read date. Date an analyst action from the ratings table or the firm's note, not the news article. Financial-statement figures (capex, cash flow, segments, debt) from the filing's raw text, never a WebFetch summary. Nasdaq calendar past dates lose the release time — confirm on the release. A ticker can be recycled: Yahoo ARTI.TO carries another security before the fund's 25 Mar 2024 launch — check the launch date on the issuer page and chart only from it.

**J. Build hygiene.** Title ticker matches the slug; `</head>` present; the P/E row labelled exactly `Trailing P/E`; `.fin-scroll` wrapper kept; existing accent colours stay (red-accent pages: 200-day MA #cbd5e1); no literal closing style tag inside a CSS comment; no mojibake; delta box `tg-d--fix` whenever the edition corrects the previous one.

**K. Card lines** (card runs only): see `claude/briefs/CARDLINE.md`. **L. ETF / crypto / bond reports**: see `claude/briefs/BUILD_ASSETS.md`. On every page: no hedge or process caveats ("not sourced", "not confirmed", "our reading" as a doubt marker) — source it or remove the sentence.

**Working economically** (each tool call re-sends everything read so far): read the report once in full, then look things up with Grep or a Read with offset/limit — never re-read the whole file; fetch each source once and keep what you need in a temp file; one command per Bash call. **Batch your edits**: put every numeric replacement (prices, ratios, dates, chart arrays) in one Python script with a list of exact old → new pairs, run it once, and check each pair matched exactly once — not one Edit call per number (2 Oct 2026: JBL and FDS builders spent 51 and 61 separate edits). Use Edit for prose.
