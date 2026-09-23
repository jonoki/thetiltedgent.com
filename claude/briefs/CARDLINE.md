# Card-line brief: the "Their hand" line on each report card

Each card on `reports/index.html` carries one line, framed as **Their hand**, that tells a newcomer **what the company does and how it makes money**. The curiosity comes from something surprising about that business model. Approved pilot (Oki, 23 Sep 2026): see `claude/card_lines.json` for nvda, tsla, ko, lmt, jpm, cost, mtd, cboe, o, fisv, pcg, deck.

## The line
- **What it says:** what the business is and how the money comes in, and the surprising part of that. Examples:
  - where most of the profit really comes from (Costco: membership fees);
  - what it really sells versus what people think (Coca-Cola: concentrate, not bottles);
  - an unexpected customer or a concentration (Lockheed: one jet is about a quarter of revenue);
  - an unusual right or structure (Cboe: exclusive S&P 500 options; Realty Income: tenants pay the costs).
- **Never:** stock-price moves, CEO biography or trivia, one-off events, records or backlogs, analyst views, "random factoids". Oki: "insight into what the business does, not random factoids."
- **Length:** 70–120 characters. One sentence, or two short ones.
- **Reader:** smart but doesn't follow markets. Explain jargon with a plain word (no "FCF", "NIM", "EPS", "TAM"). Never define everyday words (data center, AI, CEO).
- **Voice:** story first, plain, confident. No hype, no exclamation marks, no buy/sell language, no verdicts ("undervalued", "cheap", "must-own"), no price targets. Never name a gambling operator; for casino-exposed companies describe the business without naming operators.
- **Durability:** the line must stay true past the report's date. No "this year", "today" or "recently". Round counts that grow ("over 15,000 buildings"). Prefer shares and structures over exact figures that change quarterly.
- **Facts:** every fact must be in that company's report (extract: `cardline_src/<slug>.txt`, hero + sections 01–03). No outside knowledge. Numbers exact or obviously rounded (92.5% → "over 90%"). If the report has no clear "what they do + surprising angle", write the plainest accurate description of the business and mark it `WEAK`.

## Return, per slug
`slug | line | chars | verbatim support (≤ 30 words, quoted from the extract) | OK or WEAK`

## Checker (independent)
For each line:
1. Every fact is present in the extract, verbatim or plainly implied.
2. Numbers match.
3. It is about the business model, not a factoid.
4. 70–120 characters.
5. No banned language or operator names.
6. It stays true past the as-of date.

Fix or rewrite anything failing and return `slug | final line | PASS or FIXED(reason)`. Tag every fix with a pitfall class from `claude/REPORT_PITFALLS.md` (or `NEW:`).
