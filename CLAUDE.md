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

**Voice**: story first, math second, lecture never; poker/probability as the lens; never name or show gambling operators; every page keeps a disclaimer. Do not rewrite copy without asking.

## Site map

- `index.html` — homepage, restyled to the brand Sep 3 2026 (hero with the neon lockup, ticker strip, curriculum pillars, "Le Degens" series cards, toolbox, about, merch teaser, footer).
- `reports/index.html` — 189 report cards grouped by sector with filter chips (incl. Dow 30); brand chrome.
- `reports/view.html` — iframe viewer (`view.html?r=aapl`) that loads `<ticker>_analysis.html` and removes the report's embedded `#tg-sitenav`; brand chrome.
- `reports/*_analysis.html` — 189 self-contained tear-sheets (Playfair headings, Chart.js price chart, per-company accent). **These are documents, not chrome: leave their internal design alone.** Each embeds static data as of its own date, with a "Static data as of …" banner at the top. Eleven of them (aapl, amgn, bac, crwd, ge, ibm, lin, meta, nflx, pgr, unh) embed a `#tg-sitenav` block right after `<body>`; the rest have no site nav.
- `tables/` — Pillar 02, "The Tables" (Sep 10 2026). `casino-games.html` is the index: grade board, game cards, method, outro. One page per game — `blackjack.html`, `video-poker.html`, `craps.html`, `baccarat.html`, `ultimate-texas-holdem.html`, `three-card-poker.html`, `roulette.html`, `slots.html` — each with the full analysis (how it plays, house edge bet by bet, best/worst bets, quirks, advantage play with legality/acceptance, Gent's Grade) and a **variance simulator** (slots gets a note explaining why there isn't one). Shared chrome in `tables/tables.css`. **The pages are generated**: `python3 tables/build_tables.py` rebuilds all nine from `tables/_source/casino-games-source.html` (the prose source of truth) — edit the source and rebuild, don't hand-edit the outputs. Figures are published game math; no operators named; keep both disclaimers.
- `tables/sim/games.js` — every bet as an outcome table `{p, x}` in units of the first bet; `kind: "exact"` (from the game's combinatorics) or `"approx"` (a shape calibrated at load to the published edge; labelled in the UI). `tables/sim/ttg-sim.js` — the engine (analytic EV/SD, seeded Monte Carlo, 1,000 sessions, empirical 70%/95% bands, drawdowns, canvas chart, URL-hash state `#bet=…&unit=…&n=…&seed=…`). Vanilla JS, no dependencies. Cross-check after any table edit: every computed edge must match its `edge` field (node one-liner in the 10 Sep vault log).
- `tables/blackjack-variants.html` — Blackjack Variants (Sep 10 2026): Free Bet, Switch, Spanish 21, Double Exposure, Super Fun 21 — generated by the builder from the `blackjack-variants` section of the source (the `EXTRA` list: family pages that are not on the grade board), with its own simulator tables (`blackjack-variants` in games.js, all approximate/calibrated). The three blackjack pages share a `.famtabs` strip (Blackjack · Variants · Trainer) — `FAMILY` in the builder; the trainer page carries it by hand.
- `tables/blackjack-trainer.html` — Blackjack Trainer (Sep 10 2026): a hand-written page (not generated; own stylesheet `tables/sim/bj-trainer.css`) mounting `tables/sim/bj-trainer.js` (rules → shoe → basic strategy generated from the rule set → pluggable counting systems, Hi-Lo first, with the Illustrious 18 + Fab 4 index plays) and `tables/sim/bj-table.js` (round flow, bot players, timed dealing, play / count-drill modes, count check, strategy + counting-guide + stats panes; settings in localStorage `ttg-bjt`; options for busted-hand removal delay, running-count prompts every N hands, true-count prompts every N cards dealt; a discard-tray / shoe-gauge visual with the cut card — the numeric cards-left readout shows only with the live count on). Add a counting system by adding an entry to `BJT.SYSTEMS`. Linked from `blackjack.html` and the index card.
- `brand.html` — brand system reference (marks, palette tokens, type, wordmark rules, components, voice); brand chrome, `noindex`. Rebuilt Sep 4 2026.

The chrome pages are `index.html`, `reports/index.html`, `reports/view.html` and the ten `tables/*.html` pages.

**Mobile nav**: `index.html`, `brand.html` and the `tables/` pages carry a toggle + drawer below 820px (`.navtoggle` button, `.navlinks#navmenu` panel). A one-line script in `<head>` adds `js` to `<html>` before paint so the drawer starts closed; without JS the links degrade to a plain stacked list instead of disappearing. `.navrow` sets its own horizontal padding (28px, 18px on the reports index) because it shares an element with `.wrap` and would otherwise override it.

## Building or fixing report pages

- Re-fetch the current price yourself; the header price must equal the final chart value.
- Use about 60 monthly closes (a 5-year monthly series), never daily closes under a 5-year heading.
- Never trust an agent's self-reported "verified". Named analyst calls only if seen on a fetched page.

## Working agreements

- Push straight to `main`; small, descriptive commits.
- Before touching any of the three chrome pages, open them in a browser (or Playwright) at desktop and 390px mobile widths and check the result; `prefers-reduced-motion` must keep disabling the ticker animation.
- Never change the 189 report documents' layout in bulk without asking.
- When you finish something, tell the owner what to look at on the live site.
