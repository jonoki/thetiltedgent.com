# Report pitfalls — what builders keep getting wrong, and the rule that prevents it

Every recurring report run (new builds, earnings refreshes, news updates, chart fixes) **reads this file first** and **appends to it last**. Builders and checkers are briefed to do both (see `claude/briefs/`).

Counts are "times a checker had to correct it", tallied from checker returns. When a category gets a new hit, bump its count and add the example; when a new kind of error appears twice, give it its own entry and a prevention rule, and copy the rule into the relevant brief.

Last tally: **22 Sep 2026** — 64 new S&P builds (batches p–t), 17 earnings refreshes, library chart audit.

---

## A. Chart data that is not real month-end closes — ~70 reports affected
The single most damaging error: it is invisible to `verify.py` (which only checks the last point) and it poisons every return, drawdown and "since" claim in Section 07.

| Variant | Examples |
|---|---|
| "Reconstructed"/approximate points typed from memory | CRWD 42/59 points; DELL Jan-26 $152 vs real $114.44; ORCL Apr-26 $198.60 vs $161.39; ADBE Sep-21 $656 vs $575.72; WMT, AVGO, MRVL; audit: INTC −68%, MU +54%, NFLX/AMZN 26% off |
| Mixed series (dividend-adjusted early, actual later) | TJX, ADI, AVGO |
| Split missed or applied once | CPRT (Nov 2022 2:1 missed → every pre-split point doubled, fake "−57% over 5 yrs") |
| Month-end taken mid-month | ORCL Jul-26 = Jul 24 close; many "Jul 26" single-point misses in the 19 Aug cohort |
| Adjustment basis not labelled | 26 reports dividend-adjusted without saying so; spin-offs (HON FDX MMM CMCSA WDC BDX …) |

**Rules**
- Every point is a real month-end close from a fetched source (digrin "Real price" or Yahoo monthly Close). Never type a value.
- One basis for the whole series, consistent with the header price. Splits always adjusted; dividends not (or labelled if so); spin-offs either adjusted or explicitly labelled "not spin-adjusted" with the gap shown.
- Run `py -3 tools/chart_audit.py <slug>` before handing back. Target: 0 points >3% off Yahoo close/adjclose.

## B. Information dated after the banner date — seen in ~25 reports
The next session's live pages are intraday. Examples: PEG, forward P/E, 52-week change, P/B, market cap read on Sep 22 for a Sep 21 banner; peer market caps at Sep 22 prices; analyst calls dated after the banner (TYL Evercore Sep 22, EG RBC Sep 22, CSCO Piper Sep 22, ADI Bernstein Sep 22); the consensus average changed by a next-day action.

**Rules**
- Everything price-dependent is recomputed at the banner-date close (ours) or removed.
- Every dated item ≤ banner date. If a consensus page was read later, check the latest listed action date and say "read <date>; latest action <date>".
- A stale-looking live figure (e.g. a 52-week high that "looks high") is checked against daily rows for the exact window.

## C. Weak or unacceptable sources — seen in ~40 reports
Casino/gambling affiliates (casino.org, casinoreports), DailyPolitical, crypto-exchange news (Bitget), Substack posts, forum posts, TIKR-only or Quiver-only claims, AI call summaries (Moby, TradingView AI), search-result snippets, Wikipedia as the only source for money figures, law-firm class-action notices stated as fact.

**Rules**
- Primary first: company release / 8-K / 10-Q / proxy (sec.gov via WebFetch, no personal data), then Reuters/Bloomberg/WSJ/CNBC/AP/trade press, then data sites.
- Aggregators and summaries may only be cited *as* summaries ("as summarised by …"), never as the sole basis for a number or quote.
- Class actions: say "alleges"; attribute to the filing firm; never state allegations as fact.

## D. Quotes: not verbatim, truncated, or wrong speaker — ~20 corrections
KR (paraphrase presented as CFO quote), CPT (Austin quote pinned on the wrong exec), TRMB and AOS (CEO vs CFO swapped), ALLE and CLX (quotes cut mid-sentence), GL ("Matt Gordon" in a summary = Matt Darden), INTU ("after hours" was pre-market), NCLH ("vast, vast majority" vs transcript wording).

**Rules**
- A quote in quotation marks must be read verbatim on a fetched transcript/release, with the speaker named there. Otherwise paraphrase and attribute the paraphrase.
- Never truncate inside a quote without an ellipsis.

## E. Stale or wrong entity facts — ~12 corrections
CSGP named a departed CFO; ADI said Empower "pending" (closed Jul 7); MDT said MiniMed "undecided" (IPO'd Mar 2026); UHS attributed insiders-as-a-group voting to "the family"; HSIC called a close an "all-time high"; PODD compared against all of Medtronic instead of MiniMed; S&P add dates that are Wikipedia placeholders or weekends (UHS 2014-09-20 → 09-22; TXT, AVY unverified).

**Rules**
- Executives, deal status and ownership are checked on the company's own site or latest filing, dated.
- S&P add date from the S&P DJI release when findable; Wikipedia dates labelled.

## F. Arithmetic, counts and superlatives — ~20 corrections
APTV margin 12.7% vs 11.2%; PODD EPS growth measured from the wrong base; MKC "more than twice" (nearly twice); ORCL "57% collapse" (67%); NWSA "five straight years" (four); LDOS "same week" (two weeks apart); DE/others RSI and moving-average claims; "worst month", "first since", "record" claims.

**Rules**
- Every count, streak, superlative and % change is recomputed from the page's own data (or a fetched series) before it is written. If you can't compute it, don't claim it.

## G. Basis confusion in consensus and estimates — ~10 corrections
DE revenue consensus on a different basis from reported revenue; INTU FY consensus set before stock-comp moved into non-GAAP; forward P/E on unstated EPS basis; StockAnalysis TTM EPS vs sum of quarters (KR, DECK, ALB); fiscal-year label offsets (LULU); LOW consensus $4.38 vs $4.22.

**Rules**
- State the basis (GAAP/adjusted, fiscal year, source) next to every estimate; if two sources disagree, show both or pick the primary and say why.

## H. Direction and cause errors — ~8 corrections
PNW said O&M rose faster than rates (it fell); AVY and TJX said the stock fell after Q1 (it rose); LOW blamed fuel for the margin drop (CFO blamed acquisition dilution); DE "−11% on Investor Day" was intraday (close −1.9%).

**Rules**
- Price reactions are close-to-close from daily rows, never intraday or after-hours headlines.
- Causes come from management's own words (call/release) or are labelled as a reading.

## I. Data-site traps
- stockanalysis: the current session's row has no Adj. Close until settled — never use it; live fields are intraday; fiscal-year labels can run a year ahead; odd dates (a Saturday month-end row); analyst name glitches.
- digrin: header price stale (use the table); some tickers live under a different symbol (BF-B not BF.B; old P = Pandora); the "Adjusted" column is dividend-adjusted.
- Wikipedia: add dates can be placeholders (1957/1978/1987) or weekends.
- Yahoo v8 chart API close = split-adjusted, adjclose = + dividends.
- Nasdaq earnings calendar: past dates show "time-not-supplied" — confirm pre/after-market on the company release.

## J. Build hygiene (caught by the gate, but costs a cycle)
Missing `</head>` (≈10 builders), P/E row not labelled exactly `Trailing P/E` (verify can't check it), `.fin-scroll` wrapper missing, red/red-orange accents on older pages (PANW TJX AVGO ORCL ADBE — do not recolour without Oki), mojibake from pasted characters, a checker recolouring an accent unasked.

---

## Retro protocol (run at the end of every recurring run)
1. Each checker returns a line `PITFALLS: <letter>:<short example>; …` for every correction it made.
2. The orchestrator tallies them here: bump counts, add examples, date the tally line at the top.
3. Any category hit ≥2 times in one run whose rule is not already in the relevant brief gets its rule copied into `claude/briefs/`.
4. A genuinely new error class gets a new letter.
5. Log the tally in the vault entry for the run.
