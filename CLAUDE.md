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

**Palette** (CSS custom properties on the chrome pages):
`--bg #070607 · --bg2 #0D0A0B · --card #131011 · --line #2B2225 · --cream #F1E6CF · --dim #9C9189 · --gold #D9A85C · --gold-hi #FFD57A · --gold-deep #B8863E · --red #E0384F · --red-neon #FF5C70 · --red-deep #7F1122 · --green #3FA46A`

Glows: gold `0 0 14px rgba(255,201,94,.35), 0 0 40px rgba(255,201,94,.16)`; red `0 0 14px rgba(224,56,79,.55), 0 0 40px rgba(224,56,79,.25)`.

**Type**: Cinzel 500/600/700 for display and the wordmark (matches the Roman caps of the logo), DM Sans 400/500/700 for body, JetBrains Mono 400/500/700 for kickers and data. Playfair Display was retired from the chrome pages. In the wordmark the word TILTED is an inline-block rotated −5° in `--gold-hi` — deliberate (the "tilt"), keep it.

**Voice**: story first, math second, lecture never; poker/probability as the lens; never name or show gambling operators; every page keeps a disclaimer. Do not rewrite copy without asking.

## Site map

- `index.html` — homepage, restyled to the brand Sep 3 2026 (hero with the neon lockup, ticker strip, curriculum pillars, "Le Degens" series cards, toolbox, about, merch teaser, footer).
- `reports/index.html` — 189 report cards grouped by sector with filter chips (incl. Dow 30); brand chrome.
- `reports/view.html` — iframe viewer (`view.html?r=aapl`) that loads `<ticker>_analysis.html` and removes the report's embedded `#tg-sitenav`; brand chrome.
- `reports/*_analysis.html` — 189 self-contained tear-sheets (Playfair headings, Chart.js price chart, per-company accent). **These are documents, not chrome: leave their internal design alone.** Each embeds static data as of its own date, with a "Static data as of …" banner at the top. Eleven of them (aapl, amgn, bac, crwd, ge, ibm, lin, meta, nflx, pgr, unh) embed a `#tg-sitenav` block right after `<body>`; the rest have no site nav.
- `brand.html` — brand board from before the final logo; stale.

The three "chrome pages" are `index.html`, `reports/index.html`, `reports/view.html`.

## Building or fixing report pages

- Re-fetch the current price yourself; the header price must equal the final chart value.
- Use about 60 monthly closes (a 5-year monthly series), never daily closes under a 5-year heading.
- Never trust an agent's self-reported "verified". Named analyst calls only if seen on a fetched page.

## Working agreements

- Push straight to `main`; small, descriptive commits.
- Before touching any of the three chrome pages, open them in a browser (or Playwright) at desktop and 390px mobile widths and check the result; `prefers-reduced-motion` must keep disabling the ticker animation.
- Never change the 189 report documents' layout in bulk without asking.
- When you finish something, tell the owner what to look at on the live site.
