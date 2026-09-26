# The Tilted Gent — thetiltedgent.com

Static site for The Tilted Gent (TTG): finance/risk education with a Las Vegas poker aesthetic, run by a CFA charterholder with 15+ years in markets and 20+ at the poker table.

## Hosting and repo

- GitHub Pages serves `main` directly at https://thetiltedgent.com. A push to `main` is live within about a minute. No build step, no PRs.
- Keep `CNAME` and `.nojekyll` in the root.
- Plain HTML/CSS, no JavaScript framework; keep it that way. Fonts come from Google Fonts. Line endings are LF.

## Brand system (live — do not reinvent)

**Logo**: the "TG" monogram card — interlocked gold T and G on a playing card tilted about −8.6°, spade pip top-left, crimson accent inside the G, gold neon-tube border with a thinner red neon tube inside, wordmark THE TILTED GENT beneath. Vector files in `assets/`:
- `ttg-logo-neon.svg` — full lockup with wordmark (homepage hero)
- `ttg-mark-neon.svg` — card + monogram only, square (nav, about, footer, avatars)
- `ttg-favicon.svg` — simplified: heavier gold frame, no glow, black rounded square
- `ttg-og.png` — 1200×630 social card (neon lockup on black)
- `favicon-32.png`, `apple-touch-icon.png` (180×180) — raster fallbacks rendered from `ttg-favicon.svg`; the SVG stays the primary icon

**Palette** ("Fremont Street", live since Sep 4 2026; CSS custom properties on the chrome pages, reference copy in `assets/palettes/fremont-street.css`):
`--bg #06050B · --bg2 #0B0913 · --card #120E1C · --card2 #1A1428 · --line #2C2440 · --cream #F1E6CF · --dim #A399A6 · --dim2 #736A78 · --gold #D9A85C · --gold-hi #FFD57A · --gold-deep #B8863E · --pink #FF3E9A · --pink-neon #FF77C0 · --pink-deep #7A1449 · --cyan #1FCBE3 · --cyan-neon #6FF2FF · --cyan-deep #0A4F5C · --violet #7C4DFF · --violet-neon #B79CFF · --violet-deep #2E1A66 · --green #3FA46A · --red #E0384F · --red-neon #FF5C70`

Roles: gold is the brand and the only solid fill; pink is the emphasis (the one glowing phrase per heading, accent rules, first pillar bar), never data; cyan is the interactive tube (ghost buttons, play rings, secondary hovers, focus outline), never in a heading; violet lives only in gradients and shadow, never text; green/red are data only (up/down, win/bust). The logo keeps its crimson tube.

Glows: gold `0 0 14px rgba(255,201,94,.35), 0 0 40px rgba(255,201,94,.16)`; pink `0 0 14px rgba(255,62,154,.55), 0 0 40px rgba(255,62,154,.25)`; cyan `0 0 14px rgba(31,203,227,.50), 0 0 40px rgba(31,203,227,.22)`.

The previous palette (black, gold, crimson; Sep 3–4 2026) is archived at `assets/palettes/original-black-gold-crimson.css` with restore notes. Nav backgrounds are `rgba(6,5,11,…)`.

**Type**: Cinzel 500/600/700 for display and the wordmark (matches the Roman caps of the logo), DM Sans 400/500/700 for body, JetBrains Mono 400/500/700 for kickers and data. Playfair Display was retired from the chrome pages. In the wordmark the word TILTED is an inline-block rotated −5° in `--gold-hi` — deliberate (the "tilt"), keep it.

**Voice**: story first, math second, lecture never; poker/probability as the lens; every page keeps a disclaimer. Do not rewrite copy without asking.

**Reader**: a smart adult who doesn't follow markets. Explain finance jargon in a clause; never define everyday words (data center, AI, EV, CEO). User-facing text never carries a doubt caveat ("unconfirmed", "from Wikipedia, not verified"): prefer a primary or reliable source, and use Wikipedia when nothing better exists.

**Gambling operators**: the Tables pages and any promotional content never name or show one. In the report library, listed casino and betting companies (MGM, WYNN, LVS, FLUT, VICI…) are analysed, named and shown with logos like any other company (Oki, 23 Sep 2026).

## Site map

- `index.html` — homepage, restyled to the brand Sep 3 2026 (hero with the neon lockup, ticker strip, curriculum pillars, "Le Degens" series cards, toolbox, about, merch teaser, footer).
- `reports/index.html` — 544 report cards grouped by sector with filter chips (incl. Dow 30); brand chrome. Cards carry tags added at load by `reports/index.js` from `data/card_tags.json`: index badges with the join year, style tags (Value, Growth, Income, Quality…), dividend, headquarters, and "Updated" for 60 days after a refresh, each with a tooltip on hover, tap or focus. Rebuild with `py -3 tools/style_tags.py && py -3 tools/card_tags.py` after any batch of builds or refreshes. Formulas: `claude/TAG_FORMULAS.md`. Since 23 Sep 2026 each card also has: a company logo on a cream plate (`assets/logos/`, sources in `assets/logos/index.json`: Wikidata/Commons first, else the company's site icon; 508 of 544), a **Their hand** one-liner (`claude/card_lines.json`; brief `claude/briefs/CARDLINE.md`), and hand-picked ♥ what-you-know-them-for / ♠ theme / ★ key-people tags (`claude/hand_tags.json`; brief `claude/briefs/HANDTAGS.md`). Every line and tag is checked against its report by an independent agent before merging (pitfalls: section K of `claude/REPORT_PITFALLS.md`). Cards show at most six tags besides the index badges, spread across families, with a +N chip for the rest; the card's link is a stretched overlay so tapping a tag or +N never opens the report. Cards run 3 across on desktop (Oki, 23 Sep 2026).
- `reports/view.html` — iframe viewer (`view.html?r=aapl`) that loads `<ticker>_analysis.html` and removes the report's embedded `#tg-sitenav`; brand chrome.
- `reports/*_analysis.html` — one self-contained tear-sheet per ticker (`ls reports/*_analysis.html | wc -l`; 544 on 25 Sep 2026) (Playfair headings, Chart.js price chart, per-company accent). **These are documents, not chrome: leave their internal design alone.** Each embeds static data as of its own date, with a "Static data as of …" banner at the top. Reports never embed a site nav: `tools/verify.py` fails any report containing `tg-sitenav`. New and refreshed reports wrap their `.fin-table` in a `.fin-scroll` div so the metrics table scrolls inside the page at phone widths instead of widening it. Older reports without it: `grep -L fin-scroll reports/*_analysis.html` (299 of 544 on 25 Sep 2026). The library-wide patch was approved on 16 Sep 2026 (branch `claude/fin-scroll`) and has not been applied to every page yet.
- `reports/etf/`, `reports/crypto/`, `reports/fixed/` — ETF, crypto and bond/cash reports (24 Sep 2026): XEQT VOO BND GLD VFV · BTC ETH BNB XRP SOL · UST3M UST10Y UST30Y TIPS10Y GOC10Y. Same document design and eight-section order as the stock reports, per family content (brief `claude/briefs/BUILD_ASSETS.md`). Not yet linked from `reports/index.html`, and `reports/view.html` only loads root-level reports. Built for the Portfolio Analyzer, which is developed on branch `claude/portfolio-analyzer` (worktree folder `Coding projects/Portfolio Analyzer`).
- `tables/` — Pillar 02, "The Tables": casino-game pages, variance simulators, Blackjack Variants and the Blackjack Trainer. **The game pages are generated** from `tables/_source/casino-games-source.html` by `py -3 tables/build_tables.py` — edit the source and rebuild, never hand-edit the outputs. Figures are published game math; no operators named; keep both disclaimers. Full map in `tables/CLAUDE.md`.
- `brand.html` — brand system reference (marks, palette tokens, type, wordmark rules, components, voice); brand chrome, `noindex`. Rebuilt Sep 4 2026.

The chrome pages are `index.html`, `reports/index.html`, `reports/view.html` and the eleven `tables/*.html` pages.

**Mobile nav**: `index.html`, `brand.html` and the `tables/` pages carry a toggle + drawer below 820px (`.navtoggle` button, `.navlinks#navmenu` panel). A one-line script in `<head>` adds `js` to `<html>` before paint so the drawer starts closed; without JS the links degrade to a plain stacked list instead of disappearing. `.navrow` sets its own horizontal padding (28px, 18px on the reports index) because it shares an element with `.wrap` and would otherwise override it.

## Building or fixing report pages

- Re-fetch the current price yourself; the header price must equal the final chart value.
- Use about 60 monthly closes (a 5-year monthly series), never daily closes under a 5-year heading.
- Never trust an agent's self-reported "verified". Named analyst calls only if seen on a fetched page.

## Recurring runs learn from their own mistakes

- Briefs for builders, checkers and refreshes live in `claude/briefs/` (BUILD, CHECK, REFRESH). Use them; don't rewrite them per session.
- `claude/REPORT_PITFALLS.md` is the running log of every error class checkers have had to correct, with the rule that prevents each. Every builder and checker reads it first. At the end of every run the orchestrator tallies the checkers' `PITFALLS:` tags into it and copies any repeated rule into the briefs (retro protocol at the bottom of that file).
- Earnings refreshes wait for the T+2 settled close (second full session after the release) so the call, day-2 follow-through and analyst revisions are in; news-driven updates wait for the first full session after the news. Details in `claude/briefs/REFRESH.md`.
- `py -3 tools/chart_audit.py <slug>` must show 0 wrong chart points before anything publishes.

## Working agreements

- Push straight to `main`; small, descriptive commits.
- Before touching any chrome page, open them in a browser (or Playwright) at desktop and 390px mobile widths and check the result; `prefers-reduced-motion` must keep disabling the ticker animation.
- Never change the report documents' layout in bulk without asking.
- When you finish something, tell the owner what to look at on the live site.
