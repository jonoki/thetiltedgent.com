# Report pitfalls — what builders keep getting wrong, and the rule that prevents it

Every builder and checker in a recurring report run (new builds, earnings refreshes, news updates, chart fixes) **reads this file first**; the orchestrator **appends to it last** from the checkers' `PITFALLS:` tags (retro protocol below).

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
- After changing any chart point, sweep the page's text (prose, timeline, `events` labels, cards) for the OLD value to the cent and fix every month-end use; leave dated daily closes, moving averages and targets that merely share the number. On 23 Sep 2026 diffs alone missed ~110 stale mentions across 40 reports.
- Compare price return with price return: the S&P/SPY comparator must be its price return over the same window (SPY month-end close → banner-date close), never its total return against the stock's price return (FCX, MET, APD, BAC, MTB were all off by 8–12 points).
- A point within 3% is not proof: the 23 Sep 2026 fix pass found ~960 points in 54 reports more than 0.6% off both bases (typed values that happened to sit near the truth). Copy values from the source; never round or estimate.

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
- digrin "Real price" is **not split-adjusted** (23 Sep 2026: KLAC May-22 shows $364.85 vs split-adjusted $36.49 after the 10:1; NOW 5:1, NFLX 10:1, AMZN/GOOGL 20:1 the same). Divide every pre-split month by the split ratio before charting, or chart Yahoo's close and use digrin only as the cross-check.
- Yahoo books spin-offs and capital returns as small fractional "splits" (IP 1.056 Sylvamo, T 1.324 WBD, WDC 1.323 SanDisk, MMM 1.196 Solventum) and back-adjusts its close for them — a real pre-spin close will not match Yahoo's close. Yahoo also re-bases the whole history for splits dated after a report's as-of (APH 2:1 on 1 Sep 2026): the report stays on its as-of share basis. `tools/chart_audit.py` knows both since 23 Sep and lists them as BASIS STEPS, not errors.
- Wikipedia: add dates can be placeholders (1957/1978/1987) or weekends.
- Yahoo v8 chart API close = split-adjusted, adjclose = + dividends.
- Nasdaq earnings calendar: past dates show "time-not-supplied" — confirm pre/after-market on the company release.

## J. Build hygiene (caught by the gate, but costs a cycle)
A `<title>` tag copied from another report: on 21 Sep, `cboe_analysis.html` shipped titled "PCG — PG&E" and `mtd_analysis.html` titled "CBOE — Cboe" (the bodies were correct). The manifest reads tickers from titles, so the error spread into data. verify.py now fails any report whose title ticker doesn't match its slug. Orchestrators: judge a report by its body and hero, never by the title alone. On 22 Sep that mistake nearly launched a rebuild over a good MTD report. The manifest can also duplicate records into `unclassified.json` (AWK CINF CPAY FFIV Q WRB). Missing `</head>` (≈10 builders), P/E row not labelled exactly `Trailing P/E` (verify can't check it), `.fin-scroll` wrapper missing, red/red-orange accents on older pages (PANW TJX AVGO ORCL ADBE — do not recolour without Oki), mojibake from pasted characters, a checker recolouring an accent unasked.

## K. Card lines ("Their hand" one-liners) — 23 Sep 2026 run: 339 of 494 drafts needed fixing
Writers (Sonnet, one per ~38 companies, working only from each report's hero + sections 01–03 extract) marked all their lines OK. Independent checkers fixed 69%.

| Error | Share of fixes (approx.) | Examples |
|---|---|---|
| Event or deal hook instead of the business model | ~30% | pending mergers (MKC/UL, PSKY/WBD, SWKS/QRVO), dividend cut (BAX), breakup fees (NSC, WTW), spin-offs (FDXF, SOLV, APTV), one quarter's loss (MOS, SPCX) |
| Fact not in the extract, or overstated | ~35% | KHC "$22B write-off", MAS "a third via Home Depot", IBM "100% of mainframes", SO "owns" Vogtle (45.7% stake), CAH "most of America's drugs" (one of three), GEHC 30% "of profit" (it was margin), COIN "nearly half" (a fifth to a quarter) |
| One-quarter figure presented as permanent, or "now"/"just"/"is buying" | ~20% | DIS, TRV, RCL, SHOP, HPQ, J |
| Trivia rather than the business | ~10% | EL family votes, NDAQ can't join its own index, TYL iron-pipe origins |
| Jargon, two dashes, over length | ~5% | P&L, net inventory, 123 characters |

**Rules** (in `claude/briefs/CARDLINE.md` and the checker brief)
- Never trust a writer's OK. Every line gets an independent check against the extract, with length counted by `len()`.
- The hook must be how the money comes in. Deals, cuts, lawsuits, single quarters and trivia are out.
- Parallel agents sharing a scratch folder must use unique file and script names. On 23 Sep one checker ran another's `chk_build.py` by name collision.
- Some errors were in the reports themselves (e.g. GEHC's report mixes up margin and profit share). Log these for the next refresh.

## L. ETF, crypto and bond/cash reports — 23–24 Sep 2026 (16 reports, every one corrected by its checker)
Brief: `claude/briefs/BUILD_ASSETS.md` (its "Rules from the pilot checker rounds" and PRIVACY sections carry every rule below).

| Error | Examples |
|---|---|
| Hedge / process caveats on the page | "not confirmed", "was not sourced", "not established from the sources fetched", "our reading" — found in all 3 pilots and in reference pages later copied |
| Figure read or dated after the banner date | BTC rich list read Sep 24; live issuer AUM fields dated Sep 23; SOL epoch data ending Sep 23; undated validator lists |
| Stale holdings (10-Q copied, later 8-K missed) | Strive 12.8k→26.4k BTC, Strategy one filing behind, Trump Media 9.5k→14.1k, Upexi "2.25M" was fair value ÷ price |
| Enumeration misses (from memory, not EDGAR) | ETHB, OBTC, Galaxy, BTCS, Solmate, BitGo; PHYS larger than two of GLD's "next four" |
| "Highest since" on a partial history | BND "since 2021" (was Jul 2007); UST30Y missed Sep 10–16 2026 readings |
| Selection basis on mismatched dates | VFV Aug 31 vs XIC Sep 23 — re-ranked on a common month-end |
| Non-verbatim quotes / WebFetch summaries as quotes | Shapella, Pectra, Frankendancer, Moody's headline, SEC releases |
| Counts and superlatives | "seven Fed increases" (five in window), "twelve US ETFs" (thirteen), longest outage 17 h (19.7 h) |
| Layout | unbroken URLs overflowed 390 px (TIPS10Y 10 px, GOC10Y 113 px) — every report now has `overflow-wrap: break-word` |
| Privacy | a fix agent sent the owner's email in a sec.gov User-Agent (24 Sep; second time) |

---

## Retro protocol (run at the end of every recurring run)
1. Each checker returns a line `PITFALLS: <letter>:<short example>; …` for every correction it made.
2. The orchestrator tallies them here: bump counts, add examples, date the tally line at the top.
3. Any category hit ≥2 times in one run whose rule is not already in the relevant brief gets its rule copied into `claude/briefs/`.
4. A genuinely new error class gets a new letter.
5. Log the tally in the vault entry for the run.
