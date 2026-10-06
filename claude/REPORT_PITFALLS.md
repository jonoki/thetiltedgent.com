# Report pitfalls — what builders keep getting wrong, and the rule that prevents it

This is the full log with examples and tallies. Builders and checkers read **`claude/PITFALL_RULES.md`** first (the rules alone, kept in step with this file); the orchestrator **appends here last** from the checkers' `PITFALLS:` tags (retro protocol below).

Counts are "times a checker had to correct it", tallied from checker returns. When a category gets a new hit, bump its count and add the example; when a new kind of error appears twice, give it its own entry and a prevention rule, and copy the rule into the relevant brief.

Last tally: **6 Oct 2026** — global batch: 83 non-US stocks (33 + 50), 12 ETFs, 4 rate series as of the Oct 2 close (home-market holidays earlier); 132 independent checks/verifies incl. a T1 top-up of 33 stocks built before the T1 rule (404 additions, 87 verifier corrections). All PUBLISH after fixes; CP3M blocked (no data), Roche held on a Yahoo symbol change (ROG.SW → ROP.SW).

6 Oct 2026 tally (1,090 tags): **F ×278** (month-end high quoted as the closing high; broker counts not verifiable; dividend cash on issued incl. own shares) · **C ×177** (brand lists and claims not in the release; data-site figures credited to the company in the disclaimer) · **E ×132** (1260H list status out of date; buyer entity; Berkshire's BYD exit sourced to Wikipedia) · **H ×121** (causes the call never stated; release timing assumed) · **G ×92** (zone vs category table bases; net vs gross buybacks) · **D ×71** (transcript wording softened into a stronger paraphrase; nested quotes) · **B ×68** (data-site live fields read Oct 5; leadership pages read after the banner date) · **I ×39** (a quote dated by the article, not the note; normalised rating scales unlabelled) · **L ×29** ("(est.)", "not available from the sources used") · **J ×26** (verify.py rejected non-US tickers and currencies — fixed in the tool, see BUILD.md "Non-US listings") · **A ×9** · **NEW ×48** (below).

New in this run: (1) **company events after the last results release were missed** — pipeline approvals, pricing/tariff agreements, list designations between the print and the banner date (Roche Gazyva approval, Genentech pricing deal; CATL/BYD 1260H update). Rule: before writing 01/06, read the company's own releases from the last print to the banner date (added to BUILD.md Depth). (2) **builds written before the T1 rule lacked results-vs-consensus and post-print broker moves** even when the quarter was covered — the T1 top-up added 404 items. (3) **Yahoo symbols change** (Roche ROG.SW → ROP.SW): chart_audit's cache hid the 404; clear the cache when a symbol is new. (4) **non-US title and currency formats** varied by builder (pseudo-tickers like "(SAMSUNG)", "26.56 EUR"); now one format in BUILD.md.

Last tally before this: **5 Oct 2026** — asset batch: 30 ETFs + 20 bond/cash reports, as of the Oct 2 close; 50 builders, 50 independent checkers (49 PUBLISH; CORPAAA HOLD and CORPBAA held with it on data licensing).

5 Oct 2026 tally (checker corrections, 355 tags): **F ×102** (VTV/VUG overlap 3.3% → 4.0%, "Apple and Microsoft VUG's two largest" (NVIDIA first), "a flat 2023" at +9.3% total return, unsupported "mid-sized holdings") · **E ×48** (Vanguard renamed its CRSP-index funds "Vanguard Morningstar …" and the indexes "Morningstar US …" on Jul 28–29, 2026; SpaceX sector per the GICS file; manager CFA designations; "began trading" vs "expected to begin") · **C ×47** (undated or mis-dated source pages; sector claims with no index-provider source; Vanguard market price is the official close since Jul 15, 2024, not a bid-ask midpoint) · **L ×43** (process caveats on the page: "our inference from past dates, not an issuer schedule", "our application of the rule") · **B ×36** (issuer API YTD read on Oct 5 replaced with the Sep 30 figure; issuer pages described as "on the banner date" though read later; undated Wikipedia revisions pinned) · **D ×28** (quotes attached to the wrong rule; cut-down SAI sentence without an ellipsis; a Morningstar line not on the announcement) · **G ×21** (preliminary counts stated as final; market-price YTD in a NAV row; after-tax return basis) · **H ×16** (index caps tied to tax law the SAI doesn't name; unsourced causes of sector weights or distribution timing) · **I ×1** (pdftotext shifted a row label: market-price return read as NAV) · **NEW ×13** (see below).

New in this run: (1) **issuer price APIs carry a stale prior-day market price** (Vanguard showed Oct 1 = Sep 30 close for VTI and VWO) — take closes and day changes from Nasdaq/Yahoo daily rows (B; rule added to BUILD_ASSETS.md); (2) **data licensing**: FRED's notes for Moody's DAAA/DBAA say the data is copyrighted by Moody's and may not be reproduced without consent — both reports held for Oki (new rule in BUILD_ASSETS.md: read a third-party series' licence note before building on it); (3) Select Sector index rules: the SAI on EDGAR and S&P's methodology differ on the rebalance pricing date — use the SAI; (4) an S&P 500 change announced before the banner date was missed in 06 (Twilio, Oct 1 announcement); (5) `chart_audit.py` cannot audit yield series in `reports/fixed/` — checkers compared every point against Treasury/BoC/FRED files with their own scripts.

30 Sep 2026 tally (checker corrections, one per error): **F ×14** (CTAS UNF spread "21% below" the offer was the premium, 17.3% below; CTAS "gross margin up five straight years", four; PAYX FCF margin 30.6→30.5%, prior average target "10.2% below" → 8.5%, unchecked sector superlatives, a float estimate never checked against the 10-K; COST FY26 EPS growth 13.9% was net income growth, SPY +78.1% vs "~+55%" on different windows, "record year" for gasoline was record Q4 volumes, "about 0.75 points" vs "a little less than 75 bps", colour key breached ×2; GIS "for a consumer-staples large cap" ×2; DRI 27 analysts vs a tally of 29 unexplained) · **C ×11** (GIS 247wallst → Campbell's 8-K, WSJ via a news feed; DRI LSEG via Quartz → CNBC, undated CNBC figure; CTAS "expansive" CIDs pinned on Bernstein, unsourced macro lines, Wikipedia for a deal value → Cintas release; PAYX UBS dropped though Investing.com had it; COST prior analyst calls labelled errors without proof, an estimate without its formula, sources named that were never read) · **E ×9** (PAYX float sensitivity carried over, "part of the debt would reprice" (all fixed-rate), HQ Rochester only; COST competitor bubbles carried over (Amazon 2024 revenue, Sam's China 55 → 67 clubs), "Industry Avg" not the named peers' average; CTAS "CEO since Aug 1" read as a start date, Stifel date; GIS "only split"; DRI next earnings "not dated" though given on the call) · **D ×8** (GIS CFO leverage lines from a summary, "slower and more expensively", "Remarkability playbook"; DRI paraphrase shown as a quote, line pinned on the wrong speaker, "modest trade-down" was FSR's words; PAYX analyst's framing given to the CFO; COST "6–7% pace for the past year") · **G ×7** (GIS revenue consensus basis, ROIC "after-tax", −3.55% vs −4% average diluted shares; DRI shares outstanding vs weighted diluted; CTAS organic growth already adjusts for workdays; COST FY27 growth from a refund-adjusted base, "counting leases") · **H ×4** (GIS fall presented as caused by Campbell's cut; DRI "management admits trade-down"; PAYX float rise "because Paycor"; COST "the target changes were cuts" when one was a raise) · **I ×3** (short interest without its settlement date: GIS, DRI, PAYX; COST's builder flagged the same) · **B ×2** (GIS stale holder value; CTAS failure odds undated) · **L ×2 pages** (GIS 9 process caveats, PAYX 1; DRI's checker left the template's "not sourced this session" lines, which are on 201 reports — library-wide removal is Oki's call) · **NEW J ×4** (the delta-box CSS header comment held a literal closing style tag, which ends the style element; pasted into all four pages that took the CSS whole; verify.py now fails it) · **NEW I ×1** (an analyst action dated by the news article's date, not the action's) · **NEW C ×2** (WebFetch summaries of sec.gov statements returned wrong numbers: PAYX capex $172.2M and $315.2M vs the 10-K's $234.9M; GIS's builder saw an internally inconsistent volume/price-mix table).

Builders' own finds in the previous editions (fixed before checking): CTAS and COST dividend-adjusted chart points and highs (A); PAYX founder/chairman, founding year, earnings date, goodwill attribution (E ×4); GIS intraday move quoted as the close ×2 (H); DRI net debt/EBITDA 3.09x vs its own 3.7x (F). New rules copied into BUILD.md: short interest carries its settlement date; financial-statement figures are read from the filing's raw text, not a WebFetch summary.

26 Sep 2026: fix run: trailing P/E on 10 reports (CTAS DHR GM IRM MCHP MRK ROST V WAT XYZ) and the SONY chart, 3 checkers.

26 Sep 2026 tally: **F ×10** (trailing P/E copied from the data site's P/E field, which divides by unrounded EPS, instead of header price ÷ the page's EPS: CTAS 40.95→40.83, DHR 38.31→38.21, GM 44.20→44.10, IRM 80.48→80.64, MCHP 109.32→109.07, MRK 104.4→104.7, ROST 28.02→27.89, V 30.9→30.8, WAT 181.34→181.74, XYZ 134.41→134.02; prose quoting the old figure in DHR ×4, MCHP hero, ROST premium ~15%→~14%, WAT 181×→182× ×3); **G ×3** (StockAnalysis TTM EPS vs the sum of reported quarters: MRK 1.27 vs 1.25, WAT 2.21 vs 3.99 after the share count rose 59.7M→98.2M, XYZ 0.59 vs 0.56 — basis now stated on the page); **A ×1 + I new** (SONY: digrin "Real price" was back-adjusted for the Sep 2025 SFGI spin, ~×0.967 before Sep 2025, while the page said the series was not spin-adjusted — 48 points rebuilt from Yahoo close; derived prose: 5-yr return 10.3%→6.6%, Apr 2026 RSI 31.2→29.8).

25 Sep 2026: AZO earnings refresh (T1): 10 tags from the builder's self-check, 13 from the independent checker. Before that, 22 Sep 2026: 64 new S&P builds (batches p–t), 17 earnings refreshes, library chart audit.

25 Sep 2026 tally (AZO): **E ×5** (carried over from the previous edition: CFO bio "from Nielsen… a CPA" — joined from Hertz, no CPA; "has never split its stock" — 2:1 in 1992 and 1994; FY2025 called a 53-week year — the release says 52; "Nasdaq-100 holds no meaningful auto-aftermarket exposure" — ORLY is a member) · **F ×6** (RSI "20s–30s" when it ran 33–42; "23% drop" beside its own −20.9%; a "$2,950–$3,200 band" contradicted by May 2024 $2,769.94; −14.3% → −14.4%; "more than almost anything else on the NYSE"; "130,000+" employees) · **B ×3** (stockanalysis forecast panel and average target include Sep 24 actions; companiesmarketcap rank at Sep 25 prices) · **D ×3** (a WebFetch summary gave one executive's line to another, twice; a full stop moved inside a quote) · **G ×2** (a quarter's 34% read as full-year; an inferred "GAAP basis") · **C ×1** (May 27 analyst names not on the fetched page) · **H ×1** (buybacks presented as the cause of 97.98% institutional ownership) · **I ×1** (stockanalysis cash-flow statistics still on the prior quarter) · **L ×1** (a process caveat on the page) · **J ×1** (delta box `--print` when the edition also corrects errors: use `--fix`). New rule copied into REFRESH.md: facts carried over from the previous edition are re-verified, not inherited (E hit 5 times in one refresh).

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
- Trailing P/E is computed as header price ÷ the page's own EPS (TTM) cell, never copied from a data site's P/E field (those divide by unrounded EPS; 10 reports off by 0.1–0.4 on 26 Sep 2026). Sweep the prose for the old figure.

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
- digrin "Real price" can be **back-adjusted for a spin-off** (26 Sep 2026: SONY ×~0.967 before the Sep 2025 SFGI spin). Check a pre-spin month against Yahoo's close or a daily history row before charting from it.
- Wikipedia: add dates can be placeholders (1957/1978/1987) or weekends.
- Yahoo v8 chart API close = split-adjusted, adjclose = + dividends.
- Nasdaq earnings calendar: past dates show "time-not-supplied" — confirm pre/after-market on the company release.
- Recycled tickers: Yahoo's ARTI.TO history starts Nov 2021, but Evolve's fund launched 22 Mar 2024 at a $10.00 NAV (first trade 25 Mar); the earlier rows (~$7.7) are another security (3 Oct 2026). Confirm the launch date on the issuer page and use only rows from it — any 5-year pull (refresh_data, Portfolio Analyzer) must start there.
- Short interest (stockanalysis, MarketBeat, Nasdaq) is a twice-monthly exchange snapshot: state its settlement date (e.g. "at the Sep 15 settlement"), never "as of" the read date (30 Sep 2026: GIS, DRI, PAYX).
- News-article dates are not action dates: an analyst call reported on Sep 16 may have been made Jul 2 (GIS J.P. Morgan, 30 Sep 2026). Date the action from the firm's note or the ratings table.
- WebFetch summaries of long sec.gov filings misread tables: PAYX capex came back $172.2M and $315.2M against the 10-K's $234.9M (30 Sep 2026). Read cash-flow, segment and balance-sheet figures from the filing's raw text (R-pages or the .htm itself), never from a summary.

## J. Build hygiene (caught by the gate, but costs a cycle)
A literal closing style tag inside a CSS comment ends the style element and prints the rest of the CSS as text (30 Sep 2026: the delta-box CSS header, pasted into COST CTAS DRI GIS; fixed at source, and verify.py now fails `style_tag_in_css_comment`). A `<title>` tag copied from another report: on 21 Sep, `cboe_analysis.html` shipped titled "PCG — PG&E" and `mtd_analysis.html` titled "CBOE — Cboe" (the bodies were correct). The manifest reads tickers from titles, so the error spread into data. verify.py now fails any report whose title ticker doesn't match its slug. Orchestrators: judge a report by its body and hero, never by the title alone. On 22 Sep that mistake nearly launched a rebuild over a good MTD report. The manifest can also duplicate records into `unclassified.json` (AWK CINF CPAY FFIV Q WRB). Missing `</head>` (≈10 builders), P/E row not labelled exactly `Trailing P/E` (verify can't check it), `.fin-scroll` wrapper missing, red/red-orange accents on older pages (~103 of 544; decided 25 Sep 2026: accents stay, and on red-accent pages the 200-day MA is #cbd5e1 instead of #ef4444), mojibake from pasted characters, a checker recolouring an accent unasked.

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
   Any new or changed rule also goes into `claude/PITFALL_RULES.md` (the short file agents read).
4. A genuinely new error class gets a new letter.
5. Log the tally in the vault entry for the run.
