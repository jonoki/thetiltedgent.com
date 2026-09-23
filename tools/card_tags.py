"""Card tags for reports/index.html -> data/card_tags.json (loaded by reports/index.js).

usage: py -3 tools/card_tags.py      (run tools/style_tags.py first)

Per report slug:
  st   style tags [label, tooltip] from data/style_tags.json (formulas: claude/TAG_FORMULAS.md)
  dv   dividend yield % (0 = pays none; missing = unknown), from the manifest
  hq   [short label, full head-office text] from the report's "HQ:" line
  ed   [latest edition date, previous edition date, previous price] when the report has been refreshed
  ln   one-line hook (claude/card_lines.json; empty until written)
  sp   [year, sentence] overriding the S&P 500 badge's year and tooltip (SP_NOTE below)
Index badges (S&P 500 / Nasdaq-100 / Dow) are not here: they come from the card's own data attributes.
"""
import glob, html, json, os, re

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

US_STATES = ('Alabama Alaska Arizona Arkansas California Colorado Connecticut Delaware Florida Georgia Hawaii Idaho '
             'Illinois Indiana Iowa Kansas Kentucky Louisiana Maine Maryland Massachusetts Michigan Minnesota '
             'Mississippi Missouri Montana Nebraska Nevada New Hampshire|New Jersey|New Mexico|New York|North Carolina|'
             'North Dakota|Ohio Oklahoma Oregon Pennsylvania Rhode Island|South Carolina|South Dakota|Tennessee Texas Utah '
             'Vermont Virginia Washington West Virginia|Wisconsin Wyoming')
STATE_RE = re.compile(r'\b(' + '|'.join(p.strip() for chunk in US_STATES.split('|') for p in
                      ([chunk] if ' ' in chunk.strip() and chunk.strip() in (
                          'New Hampshire', 'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota',
                          'Rhode Island', 'South Carolina', 'South Dakota', 'West Virginia') else chunk.split())) +
                      r'|D\.?C\.?|USA|U\.S\.A?\.?|United States)\b')
US_ABBR = re.compile(r',\s*(A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]|N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY])\b')
COUNTRY = {'united kingdom': 'UK', 'england': 'UK', 'uk': 'UK', 'the netherlands': 'Netherlands',
           'republic of ireland': 'Ireland', 'people\'s republic of china': 'China', 'south korea': 'South Korea',
           'korea': 'South Korea', 'taiwan (roc)': 'Taiwan',
           # Canadian provinces and a city that appear as the last part of a head-office line
           'ontario': 'Canada', 'alberta': 'Canada', 'quebec': 'Canada', 'québec': 'Canada',
           'british columbia': 'Canada', 'nova scotia': 'Canada', 'n.s.': 'Canada', 'toronto': 'Canada'}
# S&P 500 badge overrides where the join year shown differs from the card's data-sp date (Oki's decisions)
SP_NOTE = {
    'lmt': [1984, 'Lockheed Corporation joined in 1984 and merged with Martin Marietta to form Lockheed Martin in 1995.'],
}
HQ_FALLBACK = {  # the four reports with no "HQ:" line (from Wikipedia's constituent list or the report text)
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


def main():
    style = {d['slug']: d for d in json.load(open(os.path.join(R, 'data', 'style_tags.json'), encoding='utf-8'))['reports']}
    lines_p = os.path.join(R, 'claude', 'card_lines.json')
    lines = json.load(open(lines_p, encoding='utf-8')) if os.path.exists(lines_p) else {}
    man = {}
    for f in sorted(glob.glob(os.path.join(R, 'data', 'reports', '*.json'))):
        shard = os.path.basename(f)[:-5]
        for r in json.load(open(f, encoding='utf-8'))['reports']:
            if r['slug'] in man and shard == 'unclassified':
                continue
            man[r['slug']] = r
    out, no_hq = {}, []
    for slug in sorted(style):
        s, r = style[slug], man.get(slug, {})
        text = open(os.path.join(R, 'reports', f'{slug}_analysis.html'), encoding='utf-8').read(80000)
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
        out[slug] = c
    doc = {'v': 1, 'source': 'tools/card_tags.py', 'cards': out}
    p = os.path.join(R, 'data', 'card_tags.json')
    json.dump(doc, open(p, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, separators=(',', ':'))
    from collections import Counter
    print(f'{len(out)} cards -> {os.path.relpath(p, R)} ({os.path.getsize(p) // 1024} KB)')
    print('HQ labels:', Counter(c['hq'][0] for c in out.values() if 'hq' in c).most_common())
    print('no HQ tag:', no_hq)
    print('refreshed:', sum('ed' in c for c in out.values()), ' one-liners:', sum('ln' in c for c in out.values()))


if __name__ == '__main__':
    main()
