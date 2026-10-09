"""Card tags for reports/index.html -> data/card_tags.json (loaded by reports/index.js).

usage: py -3 tools/card_tags.py      (run tools/style_tags.py first)

Per report slug:
  st   style tags [label, tooltip] from data/style_tags.json (formulas: claude/TAG_FORMULAS.md)
  dv   dividend yield % (0 = pays none; missing = unknown), from the manifest
  hq   [short label, full head-office text] from the report's "HQ:" line (tools/headoffice.py)
  ed   [latest edition date, previous edition date, previous price] when the report has been refreshed
  ln   one-line hook (claude/card_lines.json; empty until written)
  sp   [year, sentence] overriding the S&P 500 badge's year and tooltip (SP_NOTE below)
  hw   ♥ what you know them for, th ♠ big themes, pp ★ key people: [label, tooltip(, since YYYY-MM)] from claude/hand_tags.json
  lg   logo path (assets/logos/<slug>.<ext>; sources in assets/logos/index.json)
Index badges (S&P 500 / Nasdaq-100 / Dow) are not here: they come from the card's own data attributes.

Also writes data/new_results.json from the refresh queue (tasks/queue/queue.json, tools/refresh_queue.py): per slug
[release date, show-from date, page as-of, company name] for every print after the page's as-of, including the
queue's next 14 days, so the "New results" tag (reports/index.js) and the viewer's line (reports/view.html) appear
on their own once the show-from date arrives and go when the refresh is merged. Show-from is the release day for a
pre-market release, else the next day. No queue file: new_results.json is left as it is.
"""
import datetime
import re
import json
import os
import sys
from collections import Counter
from typing import Any, TypedDict

import reportlib as rl
import repodata as rd
from headoffice import hq_of

# S&P 500 badge overrides where the join year shown differs from the card's data-sp date (Oki's decisions)
SP_NOTE: dict[str, tuple[int, str]] = {
    'lmt': (1984, 'Lockheed Corporation joined in 1984 and merged with Martin Marietta to form Lockheed Martin in 1995.'),
}


class CardTags(TypedDict, total=False):
    """One report's entry in data/card_tags.json; the keys are listed in the module docstring."""
    st: list[list[str]]
    dv: float
    hq: tuple[str, str]                      # (label, full head-office text)
    ed: tuple[str | float | None, str | float | None, str | float | None]   # (latest as-of, previous as-of, previous price)
    ln: str
    sp: tuple[int, str]                      # (year, sentence)
    hw: list[list[str]]
    th: list[list[str]]
    pp: list[list[str]]
    lg: str


class HandTags(TypedDict, total=False):
    """One report's entry in claude/hand_tags.json: [label, tooltip] tags per family, and the New CEO's start month."""
    hw: list[list[str]]
    th: list[list[str]]
    pp: list[list[str]]
    since: str


def load_json(repo: str, *parts: str) -> Any:
    """A JSON file under the repo, as parsed; the caller states its shape. FileNotFoundError when it is missing:
    every input is required, so a missing file cannot silently strip every card."""
    with open(os.path.join(repo, *parts), encoding='utf-8') as fh:
        return json.load(fh)


def hand_tags(h: HandTags) -> CardTags:
    """The ♥ what-you-know-them-for, ♠ theme and ★ key-people tags the report has."""
    c: CardTags = {}
    if h.get('hw'):
        c['hw'] = h['hw']
    if h.get('th'):
        c['th'] = h['th']
    if h.get('pp'):
        # a New CEO tag carries its start month so the page can drop it after two years
        c['pp'] = [p + [h['since']] if (p[0] == 'New CEO' and h.get('since')) else p for p in h['pp']]
    return c


def logo_path(repo: str, slug: str, logo: dict[str, str]) -> str | None:
    """The card's logo path relative to reports/, when assets/logos/index.json lists one and the file is there."""
    ext = logo.get('ext')
    if ext and os.path.exists(os.path.join(repo, 'assets', 'logos', f'{slug}.{ext}')):
        return f'../assets/logos/{slug}.{ext}'
    return None


def card_for(slug: str, *, style: rd.TagInputs, record: rd.ReportRecord | None, text: str, line: str | None,
             hand: HandTags, logo: str | None) -> CardTags:
    """Everything on one report card besides its index badges (keys listed in the module docstring)."""
    c: CardTags = {}
    if style.get('tags'):
        c['st'] = [[t['tag'], t['tip']] for t in style['tags']]
    dividend = style['yield']
    if dividend is not None:
        c['dv'] = dividend
    hq = hq_of(slug, text)
    if hq:
        c['hq'] = hq
    eds = (record.get('editions') if record else None) or []
    if len(eds) > 1:
        c['ed'] = (eds[-1][0], eds[-2][0], eds[-2][1])
    if line:
        c['ln'] = line
    if slug in SP_NOTE:
        c['sp'] = SP_NOTE[slug]
    c.update(hand_tags(hand))
    if logo:
        c['lg'] = logo
    return c


LEGAL_SUFFIX = re.compile(r',? (Inc\.|Corporation|Corp\.|plc|N\.V\.|Ltd\.)$')


def new_results(items: list[dict[str, Any]], records: dict[str, rd.ReportRecord]) -> dict[str, list[str]]:
    """{slug: [release, show_from, as_of, name]} for the latest queued print after each page's as-of (as-of from
    the manifest, so a refresh committed after the queue ran is not flagged). A release on the as-of day counts
    unless it came before that session's open."""
    out: dict[str, list[str]] = {}
    for i in sorted(items, key=lambda i: i['release']):
        if i['slug'] in rd.ARCHIVED or i['slug'] in rd.RENAMED:   # a queue written before the archive or the rename
            continue
        rec = records.get(i['slug']) or {}
        as_of = rec.get('as_of') or i['as_of']
        if i['release'] < as_of or (i['release'] == as_of and i.get('timing') == 'pre'):
            continue
        day = datetime.date.fromisoformat(i['release'])
        show = day if i.get('timing') == 'pre' else day + datetime.timedelta(days=1)
        out[i['slug']] = [i['release'], show.isoformat(), as_of, LEGAL_SUFFIX.sub('', rec.get('name') or i['ticker'])]
    return out


def write_new_results(repo: str, records: dict[str, rd.ReportRecord]) -> str:
    """data/new_results.json from the queue; the line to print."""
    qpath = os.path.join(repo, 'tasks', 'queue', 'queue.json')
    if not os.path.exists(qpath):
        return 'new results: no tasks/queue/queue.json (run tools/refresh_queue.py); data/new_results.json left as it is'
    with open(qpath, encoding='utf-8') as fh:
        q = json.load(fh)
    nr = new_results(q['items'], records)
    rd.write_json(os.path.join(repo, 'data', 'new_results.json'),
                  {'v': 1, 'source': 'tools/card_tags.py', 'queue_date': q.get('today'), 'cards': nr})
    return f"new results: {len(nr)} pages predate a print (queue of {q.get('today')})"


def main(argv: list[str] | None = None) -> int | str:
    """0 when data/card_tags.json is written, else which input is missing (run style_tags.py first)."""
    repo = rd.parser('Write data/card_tags.json, the tags on every report card.').parse_args(argv).repo
    try:
        style: dict[str, rd.TagInputs] = {d['slug']: d for d in load_json(repo, 'data', 'style_tags.json')['reports']}
        lines: dict[str, str] = load_json(repo, 'claude', 'card_lines.json')
        hand: dict[str, HandTags] = load_json(repo, 'claude', 'hand_tags.json')   # ♥ ♠ ★ tags (claude/briefs/HANDTAGS.md)
        logos: dict[str, dict[str, str]] = load_json(repo, 'assets', 'logos', 'index.json')   # logo files and sources
        records = rd.load_report_records(repo)
    except FileNotFoundError as e:
        return f'missing input {os.path.relpath(e.filename, repo)} (card_tags runs after manifest.py and style_tags.py)'
    out = {}
    for slug in sorted(style):
        text = rl.read_text(rd.report_path(slug, repo=repo))[:80000]
        out[slug] = card_for(slug, style=style[slug], record=records.get(slug), text=text, line=lines.get(slug),
                             hand=hand.get(slug, {}), logo=logo_path(repo, slug, logos.get(slug) or {}))
    doc = {'v': 1, 'source': 'tools/card_tags.py', 'cards': out}
    p = os.path.join(repo, 'data', 'card_tags.json')
    rd.write_json(p, doc)
    print(f'{len(out)} cards -> {os.path.relpath(p, repo)} ({os.path.getsize(p) // 1024} KB)')
    print('HQ labels:', Counter(c['hq'][0] for c in out.values() if 'hq' in c).most_common())
    print('no HQ tag:', [slug for slug, c in out.items() if 'hq' not in c])
    print(write_new_results(repo, records))
    print('refreshed:', sum('ed' in c for c in out.values()), ' one-liners:', sum('ln' in c for c in out.values()),
          ' hand tags:', sum('hw' in c for c in out.values()), ' logos:', sum('lg' in c for c in out.values()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
