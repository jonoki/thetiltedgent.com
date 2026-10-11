"""The two glossaries: data/glossary_<page>.json -> learn/table-talk/<page>.html (finance, poker), and the term
counts on the Table Talk landing page (learn/table-talk/index.html, each in a <b data-terms="<page>">).

usage: py -3 tools/glossary.py            (writes both pages and the counts; exits non-zero on any problem in the data)
       py -3 tools/glossary.py --check    (writes nothing; non-zero when a page or a count differs from what would be written)

Brief and schema: claude/briefs/GLOSSARY.md. The pages carry the site nav and footer from tools/chrome.py, which
also keeps them current when the nav changes. The finance glossary must explain every label the stock tear
sheets print often (COVERAGE_MIN reports or more): every Key Financial Metrics row and column, plus FIXED_LABELS.
The old URLs (glossary/finance.html, glossary/poker.html) are hand-written redirect stubs that keep the #term anchor.
"""
import collections
import glob
import html
import json
import os
import re
import sys
from typing import Any

import chrome
import reportlib as rl
import repodata as rd

PAGES = ('finance', 'poker')
OUT_DIR = os.path.join('learn', 'table-talk')          # Oki, 8 Oct 2026: the glossaries live under Learn
LANDING = os.path.join(OUT_DIR, 'index.html')          # the Table Talk page, which shows each glossary's term count
COVERAGE_MIN = 50          # a tear-sheet label printed on this many stock reports needs a glossary entry
FIXED_LABELS = ['Mkt Cap', 'Mkt Cap Ranking', 'Next Earnings', 'Static data as of', 'Consensus Rating',
                'Rating Breakdown', 'Average Price Target', 'Target Range', 'Key Institutional Investors',
                'RSI', '50-day', '200-day']
NOT_TERMS = {'metric'}     # the metrics table's first column header names the rows; it is not a term
# Report labels explained by a tooltip in the report viewer instead of a glossary entry (Oki, 10 Oct 2026): a required
# label is covered by a glossary term's `labels` or by an entry here. Read by reports/tips.js too.
TIPS = os.path.join('data', 'report_labels.json')
TIP_WORDS = 30
# Entries taken out of the finance glossary because they describe TTG's own pages or are too basic (Oki, 10 Oct 2026).
# Old links keep working: glossary.js sends an id to its successor term, or says where it is explained now
# ('report': a tooltip on the reports; 'cards': the report cards' own tooltips). Never reuse a retired id.
RETIRED: dict[str, dict[str, str]] = {'finance': {
    **{i: 'report' for i in ('static-data', 'price-change', 'mkt-cap-ranking', 'next-earnings', 'metric-column',
                             'industry-avg', 'context-column', 'estimate-marks', '52-week-range',
                             'rating-breakdown', 'target-range')},
    **{i: 'cards' for i in ('their-hand', 'index-badges', 'style-tags', 'tag-value', 'tag-growth', 'tag-income',
                            'tag-quality', 'tag-cash-machine', 'tag-steady', 'tag-giant', 'tag-beaten-down',
                            'tag-not-yet-profitable', 'tag-dividend', 'tag-head-office', 'tag-updated',
                            'tag-new-results', 'hand-tags', 'key-people-tags')},
    'monthly-closes': 'moving-average', 'all-time-high': 'drawdown', 'holdings': 'etf', 'ticker': 'exchange',
    'market-share': 'segment', 'index-column': 'sp-500',
}, 'poker': {}}
MOVED_NOTE = {   # what glossary.js says when a link names a retired entry with no successor
    'report': 'That entry now lives on the reports themselves: hover over or tap the label to read it.',
    'cards': 'That entry now lives on the report cards: hover over or tap the tag to read it.',
}
FIELDS = ('id', 'term', 'group', 'def')
ID = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
STAMP = '20261010d'       # ?v= on glossary.css / glossary.js: bump when either changes

HEAD = {
    'finance': dict(
        title='Finance Glossary — The Tilted Gent', active='learn', kicker='Learn &middot; Table Talk',
        h1='The <em>Tear-Sheet</em> Glossary',
        desc='Every number, ratio and acronym on The Tilted Gent stock reports, explained in plain English.',
        lede='Every number, ratio and acronym on our stock reports, in plain English: what it measures, how to read '
             'it, and where it sits on the page. <b>Know what the chips are worth before you sit down.</b>',
        lens='At the table',
        callout='<b>The fine print, glossary edition.</b> These definitions explain what a number measures and how '
                'to read it. They are education, not investment advice, and no number here says whether to buy or '
                'sell. Where a report states its own basis for a figure, such as the period behind a beta, the '
                'report&rsquo;s note applies.'),
    'poker': dict(
        title='Poker &amp; Gambling Glossary — The Tilted Gent', active='learn', kicker='Learn &middot; Table Talk',
        h1='Poker &amp; <em>Gambling</em> Glossary',
        desc='The words of the poker table and the casino floor, from pot odds to the house edge, in plain English.',
        lede='The words you&rsquo;ll hear at the poker table and read on The Tables, from pot odds to the house '
             'edge. <b>Learn the language before you learn the game.</b>',
        lens='In the market',
        callout='<b>The fine print, table edition.</b> Everything here is education and entertainment, not gambling '
                'advice, and no definition on this page is an invitation to go test it. Figures are the standard '
                'published game math the game pages use; the table in front of you may differ, and its posted rules '
                'win. If gambling stops being fun, that&rsquo;s the game telling you something; help exists, and '
                'taking it is the +EV play.'),
}


def load(repo: str, page: str) -> dict[str, Any]:
    with open(os.path.join(repo, 'data', f'glossary_{page}.json'), encoding='utf-8') as fh:
        return json.load(fh)


def tear_sheet_labels(repo: str, min_reports: int = COVERAGE_MIN) -> list[str]:
    """Labels printed on at least min_reports stock tear sheets: Key Financial Metrics rows and column headers."""
    seen: collections.Counter[str] = collections.Counter()
    for p in glob.glob(os.path.join(repo, 'reports', '*_analysis.html')):
        t = rl.read_text(p)
        m = re.search(r'<table[^>]*class="[^"]*fin-table[^"]*"[^>]*>(.*?)</table>', t, re.S)
        if not m:
            continue
        cells = re.findall(r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>', m.group(1), re.S) + re.findall(r'<th[^>]*>(.*?)</th>', m.group(1), re.S)
        seen.update({clean(c) for c in cells if 0 < len(clean(c)) < 45})
    return sorted(k for k, n in seen.items() if n >= min_reports and k.lower() not in NOT_TERMS)


def clean(s: str) -> str:
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s))).strip()


def tip_covers(tip: dict[str, Any], label: str) -> bool:
    """Whether a report_labels.json entry explains a label: its match rule, ignoring case."""
    want, got = tip['label'].lower(), label.lower()
    how = tip.get('match', 'exact')
    return got == want or (how == 'prefix' and got.startswith(want)) or (how == 'contains' and want in got)


def tip_problems(tips: list[dict[str, Any]], doc: dict[str, Any]) -> list[str]:
    """Everything wrong with the report tooltips: missing or over-long text, HTML, an unknown match rule or glossary
    term, a repeated label, and a label the glossary also explains without the tip linking to that entry."""
    out = []
    ids = {t['id'] for t in doc.get('terms', [])}
    by_label = {lab.lower(): t['id'] for t in doc.get('terms', []) for lab in t.get('labels', [])}
    seen: collections.Counter[str] = collections.Counter(str(t.get('label', '')).lower() for t in tips)
    out += [f'tooltip label {lab!r} listed {n} times' for lab, n in seen.items() if n > 1]
    for t in tips:
        lab = t.get('label') or '?'
        if not t.get('label') or not t.get('tip'):
            out.append(f'tooltip {lab}: needs a label and a tip')
            continue
        if t.get('match', 'exact') not in ('exact', 'prefix', 'contains'):
            out.append(f'tooltip {lab}: unknown match {t["match"]!r}')
        if len(t['tip'].split()) > TIP_WORDS:
            out.append(f'tooltip {lab}: {len(t["tip"].split())} words, over {TIP_WORDS}')
        if re.search(r'<[a-z/]', t['tip']):
            out.append(f'tooltip {lab}: tip holds HTML')
        if t.get('term') and t['term'] not in ids:
            out.append(f'tooltip {lab}: term {t["term"]!r} is not a glossary entry')
        owner = by_label.get(lab.lower())
        if owner and t.get('term') != owner:
            out.append(f'tooltip {lab}: the glossary entry {owner!r} explains this label, so the tip must link it (term)')
    return out


def problems(doc: dict[str, Any], required: list[str], tips: list[dict[str, Any]] | None = None,
             retired: dict[str, str] | None = None) -> list[str]:
    """Everything wrong with one glossary: missing fields, bad or repeated ids, unknown groups or see-also ids,
    required tear-sheet labels that neither a term nor a report tooltip explains, and retired ids that are live
    again or point at a missing successor."""
    tips, retired = tips or [], retired or {}
    out = []
    groups = [g.get('id') for g in doc.get('groups', [])]
    ids: collections.Counter[str] = collections.Counter(t.get('id', '') for t in doc.get('terms', []))
    out += [f'id {i!r} used {n} times' for i, n in ids.items() if n > 1]
    for t in doc.get('terms', []):
        name = t.get('id') or t.get('term') or '?'
        out += [f'{name}: no {f}' for f in FIELDS if not t.get(f)]
        if t.get('id') and not ID.match(t['id']):
            out.append(f'{name}: id is not kebab-case')
        if t.get('group') not in groups:
            out.append(f'{name}: unknown group {t.get("group")!r}')
        out += [f'{name}: see-also {s!r} is not a term' for s in t.get('see', []) if s not in ids]
        out += [f'{name}: {f} holds HTML' for f in ('term', 'why', 'def', 'formula', 'example', 'sheet', 'lens')
                if re.search(r'<[a-z/]', t.get(f) or '')]
    covered = {lab.lower() for t in doc.get('terms', []) for lab in t.get('labels', [])}
    out += [f'tear-sheet label {lab!r} has no term or report tooltip ({TIPS})' for lab in required
            if lab.lower() not in covered and not any(tip_covers(t, lab) for t in tips if t.get('label'))]
    out += [f'retired id {i!r} is a live term again' for i in retired if i in ids]
    out += [f'retired id {i!r} points at {s!r}, which is not a term' for i, s in retired.items()
            if s not in MOVED_NOTE and s not in ids]
    out += [f'group {g!r} has no terms' for g in groups if not any(t.get('group') == g for t in doc.get('terms', []))]
    return out


def e(s: str) -> str:
    return html.escape(s, quote=True)


def term_html(t: dict[str, Any], names: dict[str, str], lens_label: str, group_title: str) -> str:
    """One entry, in reading order: name (and other names), why it matters, definition, formula and example,
    where it sits on the tear sheet, the lens, then its section tag and see-also links. Desktop shows it as a
    narrow row in two columns, phones as a card (glossary.css)."""
    search = ' '.join([t['term'], *t.get('aka', []), *t.get('labels', [])]).lower()
    parts = [f'  <article class="term" id="{t["id"]}" data-g="{t["group"]}" data-s="{e(search)}">',
             f'    <div class="th"><h3><a href="#{t["id"]}">{e(t["term"])}</a></h3>']
    if t.get('aka'):
        parts.append(f'    <p class="aka">Also: {" &middot; ".join(e(a) for a in t["aka"])}</p>')
    parts.append('    </div>')
    if t.get('why'):
        parts.append(f'    <p class="why">{e(t["why"])}</p>')
    parts.append(f'    <p class="def">{e(t["def"])}</p>')
    for key, label in (('formula', 'Formula'), ('example', 'Example'), ('sheet', 'On the tear sheet'), ('lens', lens_label)):
        if t.get(key):
            parts.append(f'    <p class="x x-{key}"><span class="k">{label}</span>{e(t[key])}</p>')
    tag = f'<a class="tag" href="#g-{t["group"]}">{e(group_title)}</a>'
    links = ', '.join(f'<a href="#{s}">{e(names[s])}</a>' for s in t.get('see', []))
    parts.append(f'    <p class="see">{tag}{" See also: " + links if links else ""}</p>')
    parts.append('  </article>')
    return '\n'.join(parts)


def az_key(name: str) -> str:
    c = re.sub(r'^[^A-Za-z0-9]+', '', name)[:1].upper()
    return c if c.isalpha() else '#'


def moved_json(page: str) -> str:
    """The retired ids for glossary.js: id -> successor id, or the note saying where it is explained now."""
    out = {i: ({'note': MOVED_NOTE[s]} if s in MOVED_NOTE else {'to': s}) for i, s in sorted(RETIRED[page].items())}
    return json.dumps(out, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


def page_html(page: str, doc: dict[str, Any]) -> str:
    h = HEAD[page]
    terms = doc['terms']
    names = {t['id']: t['term'] for t in terms}
    chips = ['<button class="chip active" type="button" data-g="">All <span>' + str(len(terms)) + '</span></button>']
    sections = []
    for g in doc['groups']:
        mine = [t for t in terms if t['group'] == g['id']]
        chips.append(f'<button class="chip" type="button" data-g="{g["id"]}">{e(g["title"])} <span>{len(mine)}</span></button>')
        body = '\n'.join(term_html(t, names, h['lens'], g['title']) for t in mine)
        intro = f'\n  <p class="gintro">{e(g["intro"])}</p>' if g.get('intro') else ''
        sections.append(f'<section class="grp" id="g-{g["id"]}" data-g="{g["id"]}">\n  <h2>{e(g["title"])}</h2>{intro}\n'
                        f'  <div class="terms">\n{body}\n  </div>\n</section>')
    by_letter: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for t in sorted(terms, key=lambda t: t['term'].lower()):
        by_letter[az_key(t['term'])].append(t)
    letters = sorted(by_letter, key=lambda c: (c == '#', c))
    bar = ''.join(f'<a href="#az-{"0" if c == "#" else c}">{c}</a>' for c in letters)
    az = '\n'.join(f'  <div class="azl" id="az-{"0" if c == "#" else c}"><h3>{c}</h3><ul>'
                   + ''.join(f'<li><a href="#{t["id"]}">{e(t["term"])}</a></li>' for t in by_letter[c]) + '</ul></div>'
                   for c in letters)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
{chrome.JS_CLASS}
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#06050B">
<meta name="color-scheme" content="dark">
<title>{h['title']}</title>
<meta name="description" content="{h['desc']}">
<link rel="icon" type="image/svg+xml" href="/assets/ttg-favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
{chrome.SITE_CSS}
<link rel="stylesheet" href="glossary.css?v={STAMP}">
</head>
<body>
<!-- Written by tools/glossary.py from data/glossary_{page}.json; edit the data and rebuild. -->

{chrome.nav(h['active'])}

<header class="page">
  <div class="wrap">
    <div class="kicker">{h['kicker']}</div>
    <h1>{h['h1']}</h1>
    <p class="lede">{h['lede']}</p>
  </div>
</header>

<main class="wrap gloss">
<div class="tools">
  <label class="vh" for="q">Search the glossary</label>
  <input id="q" type="search" placeholder="Search {len(terms)} terms" autocomplete="off" spellcheck="false">
  <div class="chips" role="group" aria-label="Sections">{''.join(chips)}</div>
  <p class="count" id="count" aria-live="polite"></p>
</div>
<nav class="azbar" aria-label="A to Z">{bar}</nav>

{chr(10).join(sections)}

<p class="none" id="none" hidden>No term matches that search. Try a shorter word or an abbreviation.</p>

<section class="az" id="a-z" aria-labelledby="az-h">
  <h2 id="az-h">A&ndash;Z</h2>
{az}
</section>

<div class="callout">{h['callout']}</div>
</main>
<script type="application/json" id="moved">{moved_json(page)}</script>

{chrome.footer(chrome.SITE_FINE)}

<script src="glossary.js?v={STAMP}" defer></script>
{chrome.SITE_JS}
</body>
</html>
'''


def with_counts(text: str, counts: dict[str, int]) -> str:
    """The Table Talk page with each glossary's term count written into its <b data-terms="<page>">; ValueError
    naming the page when a marker is missing or repeated."""
    for page, n in counts.items():
        pat = re.compile(rf'(<b data-terms="{page}">)\d+(</b>)')
        if len(pat.findall(text)) != 1:
            raise ValueError(f'{LANDING}: needs exactly one <b data-terms="{page}">N</b>')
        text = pat.sub(rf'\g<1>{n}\g<2>', text)
    return text


def load_tips(repo: str) -> list[dict[str, Any]]:
    with open(os.path.join(repo, TIPS), encoding='utf-8') as fh:
        return json.load(fh)['labels']


def build(repo: str, check: bool) -> int | str:
    required = {'finance': tear_sheet_labels(repo) + FIXED_LABELS, 'poker': []}
    try:
        tips = load_tips(repo)
    except (OSError, ValueError, KeyError) as err:
        return f'{TIPS}: {err}'
    stale = []
    counts = {}
    for page in PAGES:
        doc = load(repo, page)
        mine = tips if page == 'finance' else []
        bad = problems(doc, required[page], mine, RETIRED[page]) + (tip_problems(tips, doc) if page == 'finance' else [])
        if bad:
            return f'data/glossary_{page}.json:\n  ' + '\n  '.join(bad)
        counts[page] = len(doc['terms'])
        out = page_html(page, doc)
        path = os.path.join(repo, OUT_DIR, f'{page}.html')
        current = rl.read_text(path) if os.path.exists(path) else None
        if check:
            if current != out:
                stale.append(path)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if current != out:
            rl.write_text(path, out)
        print(f'{"updated" if current != out else "unchanged"} {OUT_DIR}/{page}.html ({len(doc["terms"])} terms)'.replace(os.sep, '/'))
    landing = os.path.join(repo, LANDING)
    try:
        current = rl.read_text(landing)
        out = with_counts(current, counts)
    except (OSError, ValueError) as err:
        return str(err)
    if check and current != out:
        stale.append(landing)
    elif not check:
        if current != out:
            rl.write_text(landing, out)
        print(f'{"updated" if current != out else "unchanged"} {LANDING} (term counts)'.replace(os.sep, '/'))
    if stale:
        return 'out of date (run py -3 tools/glossary.py): ' + ', '.join(os.path.relpath(p, repo) for p in stale)
    return 0


def main(argv: list[str] | None = None) -> int | str:
    ap = rd.parser('Write learn/table-talk/finance.html and poker.html from data/glossary_*.json, and their counts.')
    ap.add_argument('--check', action='store_true', help='write nothing; fail when a page is out of date')
    args = ap.parse_args(argv)
    return build(args.repo, args.check)


if __name__ == '__main__':
    sys.exit(main())
