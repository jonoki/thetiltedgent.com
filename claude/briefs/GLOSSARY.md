# Brief: the two glossaries (finance, poker & gambling)

Pages: `learn/table-talk/finance.html` and `learn/table-talk/poker.html` (Learn · Table Talk; the old `glossary/` URLs redirect), written by `py -3 tools/glossary.py` from
`data/glossary_finance.json` and `data/glossary_poker.json`. Edit the JSON and rebuild; never hand-edit the pages.
The tool fails when a recurring tear-sheet label has no entry (see "Coverage" below).

## Reader and voice (from CLAUDE.md, binding)

- A smart adult who doesn't follow markets or casinos. Explain jargon in plain words; never define everyday words
  (data center, AI, EV as in electric vehicle, CEO, employee, headquarters).
- Never talk down. No "simply put", no "in other words", no exclamation marks, no emoji.
- No doubt caveats in the text ("unconfirmed", "reportedly", "may or may not"). If something isn't solid, leave it out.
- No advice: describe what a number means and how to read it, never whether to buy, sell or bet.
- Gambling operators (casinos, sportsbooks, online sites, their brands) are never named or shown.
- Plain text only, no HTML. Use ÷ × − ≈ and % as needed. Sentence case. American spelling. Round numbers in examples.

## Schema (one JSON file per page, UTF-8)

```json
{
  "v": 1,
  "page": "finance",
  "groups": [{"id": "metrics", "title": "Key Financial Metrics", "intro": "One or two sentences, ≤ 30 words."}],
  "terms": [{
    "id": "pe-ratio",
    "term": "P/E ratio",
    "aka": ["Trailing P/E", "Price-to-earnings ratio"],
    "group": "metrics",
    "def": "Plain-English meaning, ≤ 45 words.",
    "formula": "Optional. Share price ÷ EPS (TTM)",
    "example": "Optional, round numbers, ≤ 30 words.",
    "sheet": "Finance only, optional: where it shows on the tear sheet and how to read it there, ≤ 40 words.",
    "lens": "Optional, ≤ 25 words: the poker parallel (finance page) or the money parallel (poker page). Only where it truly clarifies; at most one term in four.",
    "labels": ["Trailing P/E"],
    "see": ["eps", "forward-pe"]
  }]
}
```

- `id`: kebab-case, unique, stable (it is the link anchor: `finance.html#pe-ratio`). Never rename one once published.
- `aka`: other names and abbreviations a reader might search for.
- `labels` (finance only): the exact strings the tear sheets print that this term explains. Matched case-insensitively.
- `see`: ids of related terms on the same page. Every id must exist.
- Order terms inside a group the way a reader meets them on the page; the page also offers A–Z.

## Coverage (finance; the tool enforces it)

Every label printed on at least ~10% of the stock tear sheets needs an entry whose `labels` include it: every
first-column row of the Key Financial Metrics table, every column header of that table, and these fixed labels:
`Mkt Cap`, `Mkt Cap Ranking`, `Next Earnings`, `Static data as of`, `Consensus Rating`, `Rating Breakdown`,
`Average Price Target`, `Target Range`, `Key Institutional Investors`, `RSI`, `50-day`, `200-day`.

## Accuracy

- Read real pages before writing what a page shows. Stocks: `reports/aapl_analysis.html`, `nke`, `jpm` (a bank),
  `o` (a REIT), `nvda`, `xom`. Families: `reports/etf/voo_analysis.html`, `etf/xeqt`, `crypto/btc_analysis.html`,
  `fixed/ust10y_analysis.html`, `fixed/tips10y_analysis.html`. Card tags: `claude/TAG_FORMULAS.md` and the tooltips
  in `reports/index.js`. Tables: every page in `tables/` (and `tables/CLAUDE.md`).
- A `sheet` line describes what the pages actually do (grep the library before claiming "every report shows…").
- Formulas are the standard ones (CFA curriculum, SEC Investor.gov, the exchange or index provider). Where reports
  differ in basis (beta, revenue growth), say what the number generally means, not one report's basis.
- Gambling numbers (house edges, payouts) only as the Tables pages state them, so the site agrees with itself.
- An independent fact-checker checks every entry before the pages ship.
