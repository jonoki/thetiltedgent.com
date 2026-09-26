#!/usr/bin/env python3
"""Write the ETF, crypto and bond cards on reports/index.html from the reports themselves.

Run from the repo root after adding or renaming a report in reports/etf/, reports/crypto/ or reports/fixed/:
    py -3 tools/asset_cards.py

For each report: ticker and name come from its <title> ("VOO — Vanguard S&P 500 ETF | ETF Analysis"),
the "What it is" line is the first sentence of its section 01, and the category label comes from LABEL below
(add one when you add a report; the script stops if one is missing). The family tab counts are updated too."""
import glob, html, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'reports', 'index.html')

FAMILIES = {  # folder: (heading, one-line note, sort)
    'etf': ('ETFs', 'Exchange-traded funds: one share, a whole basket.', 'az'),
    'crypto': ('Crypto', 'Cryptoassets, priced at the UTC daily close.', 'az'),
    'fixed': ('Bonds &amp; cash', 'Government bonds and bills, priced by their yield. Shortest term first.', 'term'),
}
LABEL = {  # slug: category line on the card
    'bnd': 'US investment-grade bonds', 'gld': 'Gold bullion', 'vfv': 'S&amp;P 500 in Canadian dollars',
    'voo': 'S&amp;P 500', 'xeqt': 'Global stocks, all in one',
    'btc': 'Cryptoasset', 'eth': 'Cryptoasset', 'bnb': 'Cryptoasset', 'xrp': 'Cryptoasset', 'sol': 'Cryptoasset',
    'ust3m': 'US Treasury bill, 3-month', 'ust10y': 'US Treasury note, 10-year', 'tips10y': 'US inflation-protected, 10-year',
    'ust30y': 'US Treasury bond, 30-year', 'goc10y': 'Government of Canada, 10-year',
}
TERM = {'ust3m': 0.25, 'ust10y': 10, 'tips10y': 10.1, 'ust30y': 30, 'goc10y': 10.2}

CARD_ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.2" y="5" width="10.5" height="14.5" rx="1.8" '
             'transform="rotate(-13 8.5 12.2)"/><rect x="10" y="3.6" width="10.5" height="14.5" rx="1.8" '
             'transform="rotate(11 15.2 10.8)" class="f"/></svg>')


QUOTED_DEFINITION = {'ust30y'}   # its section 01 opens with the definition quoted from TreasuryDirect


def section_01(page):
    page = page[page.find('<body'):]        # the class name also appears in the page's CSS
    m = re.search(r'class="section-title[^>]*>.*?</(?:div|h2)>(.*?)(?:<div class="section"|</section>)', page, re.S)
    if not m:
        sys.exit('no section 01 found')
    return m.group(1)


def quoted_definition(page):
    p = re.search(r'<p[^>]*>(.*?)</p>', section_01(page), re.S)
    txt = html.unescape(re.sub(r'<[^>]+>', '', p.group(1))).strip()
    m = re.match(r'^[A-Za-z]+:\s*"[^"]+"', txt)
    if not m:
        sys.exit('expected a quoted definition')
    return m.group(0)


def first_sentence(page):
    body = section_01(page)
    for p in re.findall(r'<p[^>]*>(.*?)</p>', body, re.S):
        txt = html.unescape(re.sub(r'<[^>]+>', '', p)).strip()
        txt = re.sub(r'^What it is\.\s*', '', txt)
        if re.match(r'^[A-Za-z]+:\s*"', txt):   # a paragraph that opens by quoting a source: use the next one
            continue
        # split on sentence ends, not on "U.S." or a quote that opens the paragraph
        for s in re.split(r'(?<!U\.S)(?<=[.!?])\s+(?=[A-Z])', txt):
            s = s.strip()
            if len(s) >= 30 and not re.match(r'^[A-Za-z]+:\s*"', s):
                return s
    sys.exit('no usable first sentence')


def card(folder, path):
    page = open(path, encoding='utf-8').read()
    slug = os.path.basename(path).split('_')[0]
    title = html.unescape(re.search(r'<title>(.*?)</title>', page, re.S).group(1)).strip()
    tick, name = [x.strip() for x in re.split(r'\s+[—-]\s+', title.split('|')[0], maxsplit=1)]
    if slug not in LABEL:
        sys.exit(f'add a LABEL for {slug} in tools/asset_cards.py')
    line = quoted_definition(page) if slug in QUOTED_DEFINITION else first_sentence(page)
    e = lambda s: html.escape(s, quote=False)
    return slug, (f'      <a class="rep asset" href="view.html?r={folder}/{slug}"><span class="tick">{e(tick)}</span>'
                  f'<h3>{e(name)}</h3><span class="sect">{e(html.unescape(LABEL[slug]).upper())}</span>'
                  f'<div class="play"><span class="play-k">{CARD_ICON}What it is</span><p class="line">{e(line)}</p></div></a>')


def main():
    t = open(INDEX, encoding='utf-8', newline='').read()
    for folder, (head, note, order) in FAMILIES.items():
        cards = [card(folder, p) for p in glob.glob(os.path.join(ROOT, 'reports', folder, '*_analysis.html'))]
        cards.sort(key=(lambda c: TERM.get(c[0], 99)) if order == 'term' else (lambda c: c[0]))
        block = (f'<!-- asset-cards:{folder} (written by tools/asset_cards.py) -->\n<div class="wrap">\n'
                 f'  <h2 class="shead">{head} <span class="scount">{len(cards)}</span></h2>\n'
                 f'  <p class="famnote">{note}</p>\n  <div class="grid">\n' + '\n'.join(c for _, c in cards) +
                 f'\n  </div>\n</div>\n<!-- /asset-cards:{folder} -->')
        t, n = re.subn(r'<!-- asset-cards:%s .*?<!-- /asset-cards:%s -->' % (folder, folder), lambda _: block, t, flags=re.S)
        if n != 1:
            sys.exit(f'marker for {folder} not found in reports/index.html')
        t = re.sub(r'(data-fam="%s"[^>]*>.*?<b class="fam-n">)\d+(</b>)' % folder, r'\g<1>%d\g<2>' % len(cards), t, count=1)
        print(f'{folder}: {len(cards)} cards')
    stocks = len(re.findall(r'<a class="rep"(?! asset)', t))
    t = re.sub(r'(data-fam="stocks"[^>]*>.*?<b class="fam-n">)\d+(</b>)', r'\g<1>%d\g<2>' % stocks, t, count=1)
    open(INDEX, 'w', encoding='utf-8', newline='\n').write(t)
    print(f'stocks: {stocks}')


if __name__ == '__main__':
    main()
