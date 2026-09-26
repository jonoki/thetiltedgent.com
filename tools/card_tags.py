"""Card tags for reports/index.html -> data/card_tags.json (loaded by reports/index.js).

usage: py -3 tools/card_tags.py      (run tools/style_tags.py first)

Per report slug:
  st   style tags [label, tooltip] from data/style_tags.json (formulas: claude/TAG_FORMULAS.md)
  dv   dividend yield % (0 = pays none; missing = unknown), from the manifest
  hq   [short label, full head-office text] from the report's "HQ:" line
  ed   [latest edition date, previous edition date, previous price] when the report has been refreshed
  ln   one-line hook (claude/card_lines.json; empty until written)
  sp   [year, sentence] overriding the S&P 500 badge's year and tooltip (SP_NOTE below)
  hw   ♥ what you know them for, th ♠ big themes, pp ★ key people: [label, tooltip(, since YYYY-MM)] from claude/hand_tags.json
  lg   logo path (assets/logos/<slug>.<ext>; sources in assets/logos/index.json)
Index badges (S&P 500 / Nasdaq-100 / Dow) are not here: they come from the card's own data attributes.
"""
import html
import json
import os
import re
from collections import Counter

import reportlib as rl

ROOT = rl.ROOT

# Full names only, so a street or city word ("West Wen Yi Road", "New Delhi", "Prince Edward Island") never
# reads as a state; multi-word names are matched whole, longest first.
US_STATES = [
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut', 'Delaware', 'Florida',
    'Georgia', 'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana', 'Maine',
    'Maryland', 'Massachusetts', 'Michigan', 'Minnesota', 'Mississippi', 'Missouri', 'Montana', 'Nebraska',
    'Nevada', 'New Hampshire', 'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota', 'Ohio',
    'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota', 'Tennessee', 'Texas',
    'Utah', 'Vermont', 'Virginia', 'Washington', 'West Virginia', 'Wisconsin', 'Wyoming',
]
STATE_RE = re.compile(r'\b(' + '|'.join(re.escape(s) for s in sorted(US_STATES, key=len, reverse=True))
                      + r'|D\.?C\.?|USA|U\.S\.A?\.?|United States)\b')
US_ABBR = re.compile(r',\s*(A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY])\b')
COUNTRY = {'united kingdom': 'UK', 'england': 'UK', 'uk': 'UK', 'the netherlands': 'Netherlands',
           'republic of ireland': 'Ireland', 'people\'s republic of china': 'China', 'south korea': 'South Korea',
           'korea': 'South Korea', 'taiwan (roc)': 'Taiwan',
           # Canadian provinces and a city that appear as the last part of a head-office line
           'ontario': 'Canada', 'alberta': 'Canada', 'quebec': 'Canada', 'québec': 'Canada',
           'british columbia': 'Canada', 'nova scotia': 'Canada', 'n.s.': 'Canada', 'toronto': 'Canada',
           'manitoba': 'Canada', 'saskatchewan': 'Canada', 'new brunswick': 'Canada',
           'prince edward island': 'Canada', 'newfoundland and labrador': 'Canada'}
# S&P 500 badge overrides where the join year shown differs from the card's data-sp date (Oki's decisions)
SP_NOTE = {
    'lmt': [1984, 'Lockheed Corporation joined in 1984 and merged with Martin Marietta to form Lockheed Martin in 1995.'],
}
HQ_FALLBACK = {  # reports with no "HQ:" line (from Wikipedia's constituent list or the report text)
    'hd': 'Atlanta, Georgia', 'unh': 'Minnetonka, Minnesota',
}


def hq_of(slug, text):
    m = re.search(r'HQ:?\s*</span>\s*([^<]{3,160})|HQ:\s*([^<]{3,160})', text)
    full = html.unescape((m.group(1) or m.group(2)).strip()) if m else HQ_FALLBACK.get(slug)
    if not full:
        return None
    full = re.sub(r'\s+', ' ', full).strip(' ·;')
    # classify on the stated head office only, not on notes in brackets ("(executive offices in Columbus, Ohio)")
    main = re.split(r'\s*[·;]', re.sub(r'\([^)]*\)', '', full))[0].strip(' ,')
    if ',' not in main:             # "Mayfield Village (300 N. Commons Blvd., Mayfield, OH 44143)": the place is in the brackets
        main = full
    if STATE_RE.search(main) or US_ABBR.search(main) or re.search(r'\b[A-Z]{2} \d{5}\b', main):
        return ['US-based', full]
    parts = [p.strip() for p in main.split(',') if p.strip()]
    country = parts[-1] if parts else main
    country = COUNTRY.get(country.lower(), country)
    if len(country) > 18:           # free text we can't reduce to a country: show no tag rather than a wrong one
        return None
    return [f'{country}-based', full]


def load_json(*parts, default=None):
    """A JSON file under the repo; `default` when it does not exist (None: it must exist)."""
    p = os.path.join(ROOT, *parts)
    if default is not None and not os.path.exists(p):
        return default
    with open(p, encoding='utf-8') as fh:
        return json.load(fh)


def main():
    style = {d['slug']: d for d in load_json('data', 'style_tags.json')['reports']}
    lines = load_json('claude', 'card_lines.json', default={})
    hand = load_json('claude', 'hand_tags.json', default={})           # ♥ ♠ ★ tags, checked (brief: claude/briefs/HANDTAGS.md)
    logos = load_json('assets', 'logos', 'index.json', default={})     # logo files + where each came from
    man = rl.load_report_records(ROOT)
    out, no_hq = {}, []
    for slug in sorted(style):
        s, r = style[slug], man.get(slug, {})
        text = rl.read_text(os.path.join(ROOT, 'reports', f'{slug}_analysis.html'))[:80000]
        c = {}
        if s.get('tags'):
            c['st'] = [[t['tag'], t['tip']] for t in s['tags']]
        if s.get('yield') is not None:
            c['dv'] = s['yield']
        h = hq_of(slug, text)
        if h:
            c['hq'] = h
        else:
            no_hq.append(slug)
        eds = r.get('editions') or []
        if len(eds) > 1:
            c['ed'] = [eds[-1][0], eds[-2][0], eds[-2][1]]
        if lines.get(slug):
            c['ln'] = lines[slug]
        if slug in SP_NOTE:
            c['sp'] = SP_NOTE[slug]
        h = hand.get(slug) or {}
        for k in ('hw', 'th'):
            if h.get(k):
                c[k] = h[k]
        if h.get('pp'):
            # a New CEO tag carries its start month so the page can drop it after two years
            c['pp'] = [p + [h['since']] if (p[0] == 'New CEO' and h.get('since')) else p for p in h['pp']]
        lg = logos.get(slug) or {}
        if lg.get('ext') and os.path.exists(os.path.join(ROOT, 'assets', 'logos', f"{slug}.{lg['ext']}")):
            c['lg'] = f"../assets/logos/{slug}.{lg['ext']}"
        out[slug] = c
    doc = {'v': 1, 'source': 'tools/card_tags.py', 'cards': out}
    p = os.path.join(ROOT, 'data', 'card_tags.json')
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(out)} cards -> {os.path.relpath(p, ROOT)} ({os.path.getsize(p) // 1024} KB)')
    print('HQ labels:', Counter(c['hq'][0] for c in out.values() if 'hq' in c).most_common())
    print('no HQ tag:', no_hq)
    print('refreshed:', sum('ed' in c for c in out.values()), ' one-liners:', sum('ln' in c for c in out.values()),
          ' hand tags:', sum('hw' in c for c in out.values()), ' logos:', sum('lg' in c for c in out.values()))


if __name__ == '__main__':
    main()
