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
"""
import json
import os
import sys
from collections import Counter
from typing import TypedDict

import reportlib as rl
from headoffice import hq_of
from style_tags import TagInputs

# S&P 500 badge overrides where the join year shown differs from the card's data-sp date (Oki's decisions)
SP_NOTE: dict[str, list[int | str]] = {
    'lmt': [1984, 'Lockheed Corporation joined in 1984 and merged with Martin Marietta to form Lockheed Martin in 1995.'],
}


class CardTags(TypedDict, total=False):
    """One report's entry in data/card_tags.json; the keys are listed in the module docstring."""
    st: list[list[str]]
    dv: float
    hq: list[str]
    ed: list[str | float]
    ln: str
    sp: list[int | str]
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


def load_json(repo: str, *parts: str, default: dict | None = None) -> dict:
    """A JSON file under the repo; `default` when it does not exist (None: it must exist)."""
    p = os.path.join(repo, *parts)
    if default is not None and not os.path.exists(p):
        return default
    with open(p, encoding='utf-8') as fh:
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


def card_for(slug: str, style: TagInputs, record: rl.ReportRecord | None, text: str, line: str | None,
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
        c['ed'] = [eds[-1][0], eds[-2][0], eds[-2][1]]
    if line:
        c['ln'] = line
    if slug in SP_NOTE:
        c['sp'] = SP_NOTE[slug]
    c.update(hand_tags(hand))
    if logo:
        c['lg'] = logo
    return c


def main(repo: str = rl.ROOT) -> int:
    style: dict[str, TagInputs] = {d['slug']: d for d in load_json(repo, 'data', 'style_tags.json')['reports']}
    lines = load_json(repo, 'claude', 'card_lines.json', default={})
    hand: dict[str, HandTags] = load_json(repo, 'claude', 'hand_tags.json', default={})         # ♥ ♠ ★ tags, checked (brief: claude/briefs/HANDTAGS.md)
    logos = load_json(repo, 'assets', 'logos', 'index.json', default={})     # logo files + where each came from
    records = rl.load_report_records(repo)
    out = {}
    for slug in sorted(style):
        text = rl.read_text(rl.report_path(slug, repo=repo))[:80000]
        out[slug] = card_for(slug, style[slug], records.get(slug), text, lines.get(slug), hand.get(slug, {}),
                             logo_path(repo, slug, logos.get(slug) or {}))
    doc = {'v': 1, 'source': 'tools/card_tags.py', 'cards': out}
    p = os.path.join(repo, 'data', 'card_tags.json')
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(out)} cards -> {os.path.relpath(p, repo)} ({os.path.getsize(p) // 1024} KB)')
    print('HQ labels:', Counter(c['hq'][0] for c in out.values() if 'hq' in c).most_common())
    print('no HQ tag:', [slug for slug, c in out.items() if 'hq' not in c])
    print('refreshed:', sum('ed' in c for c in out.values()), ' one-liners:', sum('ln' in c for c in out.values()),
          ' hand tags:', sum('hw' in c for c in out.values()), ' logos:', sum('lg' in c for c in out.values()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
