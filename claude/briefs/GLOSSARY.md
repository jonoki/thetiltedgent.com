# Brief: the two glossaries (finance, poker & gambling)

Pages: `learn/table-talk/finance.html` and `learn/table-talk/poker.html` (Learn · Table Talk; the old `glossary/` URLs redirect), written by `py -3 tools/glossary.py` from
`data/glossary_finance.json` and `data/glossary_poker.json`. Edit the JSON and rebuild; never hand-edit the pages.
The tool fails when a recurring tear-sheet label has neither an entry nor a report tooltip (see "Coverage" below).

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
  "terms": [{
    "id": "pe-ratio",
    "term": "P/E ratio",
    "aka": ["Trailing P/E", "Price-to-earnings ratio"],
    "covers": ["Earnings multiple"],
    "tags": ["stocks", "reports"],
    "why": "Optional, one line ≤ 15 words: why the reader should care. Shown under the name (Oki, 10 Oct 2026).",
    "def": "Plain-English meaning, ≤ 45 words.",
    "formula": "Optional. Share price ÷ EPS (TTM)",
    "example": "Optional, ≤ 30 words. For a term with a formula, the calculation on a well-known company using only figures printed in our own report for it, named with that report's banner date ('Coca-Cola, Aug 12, 2026: $86.71 share price ÷ $3.33 EPS over the last 12 months ≈ 26.0×.'); the result must match the report's printed figure and the term's own formula basis, checked against the report (Oki, 10 Oct 2026). Otherwise round numbers.",
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
- `short` (Oki, 12 Oct 2026): the tooltip line, a dictionary-style definition of 20 words or fewer that is accurate
  on its own (it doesn't repeat the term's name; the tooltip shows the name above it). Every term should have one.
- `match`: the phrases in running text that call up the tooltip, as a reader sees them ("P/E", "P/E ratio";
  list singular and plural separately). Leave out everyday words and words with another common meaning; a wrong
  tooltip is worse than none. A phrase that is right only in one context is an object: {"phrase": "margin",
  "ctx": "futures"}, matched only on pages whose <main data-ctx> includes that word. Contexts: futures, options,
  bonds, stocks, statements, funds, crypto, rates, fed, tables, poker.
- `senses` (optional): [{"ctx": "futures", "short": "...", "example": "..."}] where the same term means something
  different in a context; a page in that context shows that sense's short line. Shown on the glossary page too.

## Tooltips, site-wide (Oki, 12 Oct 2026)

The glossaries are the site's one source of definitions. `tools/glossary.py` writes `data/terms.json` (each term's
name, short line and senses, and the match list); `assets/site.js` reads it on every site page and puts a tooltip on
the first appearance of each matched phrase in the page's running text (not headings, links other than glossary
links, tables, widgets or the lesson sidebars); `reports/view.html` runs it on each report. Poker terms apply on The
Tables and in the lessons' "At the table" boxes. Table Talk itself gets none. The lessons' "Concepts in this lesson"
sidebars (3-8 core terms) and their contexts come from `data/lesson_terms.json` via `tools/lesson_terms.py`.
Matching rules: one tooltip per term per page; the longest phrase wins; a phrase tied to the page's context (`{"phrase": ..., "ctx": ...}`,
contexts from `<main data-ctx>`) beats the same phrase's plain entry; matching ignores case except for acronyms (`GICs` never
matches `GICS`); The Tables use the poker glossary only, poker-table words (ctx `poker`) only on the poker games, and the trainers get
none; the lessons' "At the table" boxes get poker-table words only. Before adding a match phrase, check it can't mean something else
on a page (plain "hedge" fires in "hedge fund"; "face value" on chips): tag it with a context, or leave it out. A word used in its
everyday sense where a tooltip would mislead is wrapped in `<span data-no-terms>`.
- aka holds only true synonyms (the page shows them as AKA, in gold): a reader could put the name in place of the term and mean the same thing. Narrower ideas the entry also explains (sub-types, components, each half of a paired entry, tickers and report codes) go in covers, shown as Covers. Both are searched (Oki, 12 Oct 2026).
- One card per concept (Oki, 12 Oct 2026): two different ideas get two cards, each naming the other in its def where natural ("as opposed to passive management, which ...") and listing it first under see. Keep one card only for a scale or list (Large-cap, mid-cap, mega-cap; the rating scale), one idea with states (in, at and out of the money) or mirror images whose definitions would be reworded copies (beat and miss, hawkish and dovish). A split that retires an id adds it to RETIRED with its successor.
- Each page is one A–Z list (Oki, 12 Oct 2026); the build sorts it, ignoring a leading "The". Every term gets 1–3 `tags` from `TAGS` in tools/glossary.py, most relevant first: the topics whose readers need the term. Finance: stocks, bonds, funds, crypto, futures, options, statements, rates, reports (the stock tear sheets: header, metrics rows, analyst consensus, chart and recurring company-section words). Poker: poker, blackjack, craps, roulette, baccarat, machines, carnival, general. Chips filter the page by tag, and `?tag=<id>` links to a filtered page. The old section groups are retired.
- A match phrase with `"bold": true` (usually with a `ctx`) fires only in a lesson's bold text: an everyday word that is a term where a lesson introduces it ("long", "Hike"). In the lessons every bold phrase that matches gets its tooltip, even when the term had one earlier on the page.

## Coverage (finance; the tool enforces it)

Every label printed on at least ~10% of the stock tear sheets needs an explanation: an entry whose `labels` include
it, or a tooltip in `data/report_labels.json` (shown by the report viewer). That covers every first-column row of the
Key Financial Metrics table, every column header of that table, and these fixed labels: `Mkt Cap`, `Mkt Cap Ranking`,
`Next Earnings`, `Static data as of`, `Consensus Rating`, `Rating Breakdown`, `Average Price Target`, `Target Range`,
`Key Institutional Investors`, `RSI`, `50-day`, `200-day`.

What belongs where (Oki, 10 Oct 2026):
- Glossary: finance and investing terms a reader meets anywhere (P/E, beta, duration, buyback, the S&P 500).
- Report tooltip (`data/report_labels.json`, ≤ 30 words, plain text): how TTG's own page works (the banner date, our
  columns, our rank rows, the marks). When a glossary entry also covers the label, the tooltip names it in `term`.
- Card tooltips (`tools/style_tags.py`, `reports/index.js`): the report cards' tags, each stating its rule.
- Nothing: words every adult knows (all-time high, a fund's holdings).
A removed entry's id goes in `RETIRED` in `tools/glossary.py`, with a successor id or where it is explained now.

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
