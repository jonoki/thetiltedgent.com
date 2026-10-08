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
FIELDS = ('id', 'term', 'group', 'def')
ID = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
STAMP = '20261008'         # ?v= on glossary.css / glossary.js: bump when either changes

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


def problems(doc: dict[str, Any], required: list[str]) -> list[str]:
    """Everything wrong with one glossary: missing fields, bad or repeated ids, unknown groups or see-also ids,
    and required tear-sheet labels no term explains."""
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
        out += [f'{name}: {f} holds HTML' for f in ('term', 'def', 'formula', 'example', 'sheet', 'lens')
                if re.search(r'<[a-z/]', t.get(f) or '')]
    covered = {lab.lower() for t in doc.get('terms', []) for lab in t.get('labels', [])}
    out += [f'tear-sheet label {lab!r} has no term' for lab in required if lab.lower() not in covered]
    out += [f'group {g!r} has no terms' for g in groups if not any(t.get('group') == g for t in doc.get('terms', []))]
    return out


def e(s: str) -> str:
    return html.escape(s, quote=True)


def term_html(t: dict[str, Any], names: dict[str, str], lens_label: str) -> str:
    search = ' '.join([t['term'], *t.get('aka', []), *t.get('labels', [])]).lower()
    parts = [f'  <article class="term" id="{t["id"]}" data-g="{t["group"]}" data-s="{e(search)}">',
             f'    <h3><a href="#{t["id"]}">{e(t["term"])}</a></h3>']
    if t.get('aka'):
        parts.append(f'    <p class="aka">Also: {" &middot; ".join(e(a) for a in t["aka"])}</p>')
    parts.append(f'    <p class="def">{e(t["def"])}</p>')
    for key, label in (('formula', 'Formula'), ('example', 'Example'), ('sheet', 'On the tear sheet'), ('lens', lens_label)):
        if t.get(key):
            parts.append(f'    <p class="x x-{key}"><span class="k">{label}</span>{e(t[key])}</p>')
    if t.get('see'):
        links = ', '.join(f'<a href="#{s}">{e(names[s])}</a>' for s in t['see'])
        parts.append(f'    <p class="see">See also: {links}</p>')
    parts.append('  </article>')
    return '\n'.join(parts)


def az_key(name: str) -> str:
    c = re.sub(r'^[^A-Za-z0-9]+', '', name)[:1].upper()
    return c if c.isalpha() else '#'


def page_html(page: str, doc: dict[str, Any]) -> str:
    h = HEAD[page]
    terms = doc['terms']
    names = {t['id']: t['term'] for t in terms}
    chips = ['<button class="chip active" type="button" data-g="">All <span>' + str(len(terms)) + '</span></button>']
    sections = []
    for g in doc['groups']:
        mine = [t for t in terms if t['group'] == g['id']]
        chips.append(f'<button class="chip" type="button" data-g="{g["id"]}">{e(g["title"])} <span>{len(mine)}</span></button>')
        body = '\n'.join(term_html(t, names, h['lens']) for t in mine)
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


def build(repo: str, check: bool) -> int | str:
    required = {'finance': tear_sheet_labels(repo) + FIXED_LABELS, 'poker': []}
    stale = []
    counts = {}
    for page in PAGES:
        doc = load(repo, page)
        bad = problems(doc, required[page])
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
