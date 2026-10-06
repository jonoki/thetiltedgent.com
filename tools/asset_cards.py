#!/usr/bin/env python3
"""Write the ETF, crypto and bond cards on reports/index.html from the reports themselves.

Run from the repo root after adding or renaming a report in reports/etf/, reports/crypto/ or reports/fixed/:
    py -3 tools/asset_cards.py

For each report: ticker and name come from its <title> ("VOO — Vanguard S&P 500 ETF | ETF Analysis"),
the "What it is" line is the first sentence of its section 01, and the category label comes from LABEL below
(add one when you add a report; the script stops if one is missing). The family tab counts are updated too."""
import glob
import html
import os
import re
import sys

import reportlib as rl
import repodata as rd

FAMILIES = {  # folder: (heading, one-line note, sort), plain text
    'etf': ('ETFs', 'Exchange-traded funds: one share, a whole basket.', 'az'),
    'crypto': ('Crypto', 'Cryptoassets, priced at the UTC daily close.', 'az'),
    'fixed': ('Bonds & cash', 'Bonds, bills, savings bonds and deposits, priced by their yield. Shortest term first.', 'term'),
}   # one per reportlib.ASSET_FAMILIES folder (a unit test checks)
LABEL = {  # slug: category line on the card, plain text
    'arti': 'AI stocks, active, CAD-hedged', 'bnd': 'US investment-grade bonds', 'gld': 'Gold bullion', 'vfv': 'S&P 500 in Canadian dollars',
    'voo': 'S&P 500', 'xeqt': 'Global stocks, all in one',
    'btc': 'Cryptoasset', 'eth': 'Cryptoasset', 'bnb': 'Cryptoasset', 'xrp': 'Cryptoasset', 'sol': 'Cryptoasset',
    'ust3m': 'US Treasury bill, 3-month', 'ust10y': 'US Treasury note, 10-year', 'tips10y': 'US inflation-protected, 10-year',
    'ust30y': 'US Treasury bond, 30-year', 'goc10y': 'Government of Canada, 10-year',
    # batch of 5 Oct 2026
    'vti': 'Total US stock market', 'qqq': 'Nasdaq-100', 'iwm': 'US small caps', 'vea': 'Developed markets ex-US',
    'vwo': 'Emerging markets', 'vt': 'Global stocks, all countries', 'schd': 'US dividend stocks', 'vug': 'US large-cap growth',
    'vtv': 'US large-cap value', 'rsp': 'S&P 500, equal weight', 'usmv': 'US minimum volatility', 'xlk': 'US technology sector',
    'xlf': 'US financial sector', 'xlv': 'US health care sector', 'xle': 'US energy sector', 'vnq': 'US real estate (REITs)',
    'smh': 'Semiconductors', 'sgov': 'US Treasury bills, 0-3 months', 'tlt': 'US Treasuries, 20+ years',
    'tip': 'US inflation-protected bonds', 'lqd': 'US investment-grade corporates', 'hyg': 'US high-yield corporates',
    'mub': 'US municipal bonds', 'slv': 'Silver bullion', 'jepi': 'US stocks plus option income, active',
    'tqqq': 'Nasdaq-100, 3x daily leverage', 'ibit': 'Spot bitcoin', 'xiu': 'Canada, S&P/TSX 60',
    'zag': 'Canadian bonds, all sectors', 'cash': 'Canadian high-interest savings',
    'ust1m': 'US Treasury bill, 1-month', 'ust6m': 'US Treasury bill, 6-month', 'ust1y': 'US Treasury bill, 1-year',
    'ust2y': 'US Treasury note, 2-year', 'ust5y': 'US Treasury note, 5-year', 'ust7y': 'US Treasury note, 7-year',
    'ust20y': 'US Treasury bond, 20-year', 'tips5y': 'US inflation-protected, 5-year', 'tips30y': 'US inflation-protected, 30-year',
    'frn2y': 'US Treasury floating rate note, 2-year', 'ibond': 'US savings bond, inflation-linked',
    'eebond': 'US savings bond, fixed rate', 'corpaaa': 'US corporate bonds, Aaa', 'corpbaa': 'US corporate bonds, Baa',
    'goc3m': 'Government of Canada bill, 3-month', 'goc2y': 'Government of Canada, 2-year', 'goc5y': 'Government of Canada, 5-year',
    'goc30y': 'Government of Canada, long-term', 'gocrrb': 'Canada real return bond', 'gic5y': 'Canadian 5-year GIC',
    # batch of 5 Oct 2026 (b)
    'vbal': 'Balanced, 60/40, all in one', 'vgro': 'Growth, 80/20, all in one', 'ijh': 'US mid caps', 'ijr': 'US small caps, S&P 600',
    'vig': 'US dividend growers', 'vym': 'US high dividend yield', 'vxus': 'Stocks outside the US', 'xli': 'US industrial sector',
    'xlp': 'US consumer staples sector', 'shy': 'US Treasuries, 1-3 years', 'ief': 'US Treasuries, 7-10 years', 'gdx': 'Gold miners',
    'sofr': 'US overnight secured rate', 'effr': 'US federal funds rate', 'cp3m': 'US commercial paper, 3-month',
    'ust3y': 'US Treasury note, 3-year', 'corra': 'Canada overnight repo rate',
}
TERM = {'ust3m': 0.25, 'ust10y': 10, 'tips10y': 10.1, 'ust30y': 30, 'goc10y': 10.2,   # years; ties broken by the decimal
        'ust1m': 0.08, 'goc3m': 0.26, 'ust6m': 0.5, 'ust1y': 1, 'ust2y': 2, 'frn2y': 2.05, 'goc2y': 2.1, 'ust5y': 5,
        'tips5y': 5.05, 'goc5y': 5.1, 'gic5y': 5.2, 'ust7y': 7, 'ust20y': 20, 'eebond': 20.5, 'corpaaa': 25,
        'corpbaa': 25.1, 'tips30y': 30.05, 'goc30y': 30.1, 'gocrrb': 30.2, 'ibond': 30.3,
        'sofr': 0.001, 'effr': 0.002, 'corra': 0.003, 'cp3m': 0.24, 'ust3y': 3}

CARD_ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.2" y="5" width="10.5" height="14.5" rx="1.8" '
             'transform="rotate(-13 8.5 12.2)"/><rect x="10" y="3.6" width="10.5" height="14.5" rx="1.8" '
             'transform="rotate(11 15.2 10.8)" class="f"/></svg>')


QUOTED_DEFINITION = {'ust30y'}   # its section 01 opens with the definition quoted from TreasuryDirect
# Not securities (Oki, 6 Oct 2026): indicator rates and economic series move to their own economic-indicators section
# when it is built. Until then they stay on the Bonds & cash tab. Never add new ones there.
INDICATORS = {'sofr', 'effr', 'corra'}   # overnight / repo / policy-linked rates
INDICATOR_REVIEW = {'gic5y'}   # a deposit you can buy, but the page charts the Bank of Canada's posted-rate series: Oki to decide


def section_01(page: str) -> str:
    page = page[page.find('<body'):]        # the class name also appears in the page's CSS
    m = re.search(r'class="section-title[^>]*>.*?</(?:div|h2)>(.*?)(?:<div class="section"|</section>)', page, re.S)
    if not m:
        raise ValueError('no section 01 found')
    return m.group(1)


def quoted_definition(page: str) -> str:
    p = re.search(r'<p[^>]*>(.*?)</p>', section_01(page), re.S)
    if not p:
        raise ValueError('section 01 has no <p> paragraph')
    m = re.match(r'^[A-Za-z]+:\s*"[^"]+"', rl.strip_tags(p.group(1)))
    if not m:
        raise ValueError('section 01 does not open with a quoted definition')
    return m.group(0)


def first_sentence(page: str) -> str:
    body = section_01(page)
    for p in re.findall(r'<p[^>]*>(.*?)</p>', body, re.S):
        txt = re.sub(r'^What it is\.\s*', '', rl.strip_tags(p))
        if re.match(r'^[A-Za-z]+:\s*"', txt):   # a paragraph that opens by quoting a source: use the next one
            continue
        # split on sentence ends, not on "U.S." or a quote that opens the paragraph
        for s in re.split(r'(?<!U\.S)(?<=[.!?])\s+(?=[A-Z])', txt):
            s = s.strip()
            if len(s) >= 30 and not re.match(r'^[A-Za-z]+:\s*"', s):
                return s
    raise ValueError('no sentence of 30+ characters in section 01')


def card(folder: str, path: str) -> tuple[str, str]:
    """(slug, card markup) for one report. Raises ValueError, saying what is missing, when the page cannot
    be made into a card; main() adds the file name."""
    page = rl.read_text(path)
    slug = rd.slug_of(path)
    if slug not in LABEL:
        raise ValueError(f'add a LABEL for {slug} in tools/asset_cards.py')
    tick, name = rl.parse_title(page)
    if not tick or not name:
        raise ValueError('expected a <title> like "VOO — Vanguard S&P 500 ETF | ETF Analysis"')
    line = quoted_definition(page) if slug in QUOTED_DEFINITION else first_sentence(page)
    e = lambda s: html.escape(s, quote=False)
    return slug, (f'      <a class="rep asset" href="view.html?r={folder}/{slug}"><span class="tick">{e(tick)}</span>'
                  f'<h3>{e(name)}</h3><span class="sect">{e(LABEL[slug].upper())}</span>'
                  f'<div class="play"><span class="play-k">{CARD_ICON}What it is</span><p class="line">{e(line)}</p></div></a>')


def set_family_count(t: str, family: str, n: int) -> str:
    """t with the count on the family's tab set to n; ValueError when the tab has no count to set."""
    t, found = re.subn(rf'(data-fam="{family}"[^>]*>.*?<b class="fam-n">)\d+(</b>)', rf'\g<1>{n}\g<2>', t, count=1)
    if not found:
        raise ValueError(f'no count on the {family} tab in reports/index.html')
    return t


def main(argv: list[str] | None = None) -> int | str:
    """0 when the cards are written, else what stopped it (a report that cannot be made into a card, a missing
    marker or tab count, a file that cannot be read or written)."""
    repo = rd.parser('Write the ETF, crypto and bond cards on reports/index.html.').parse_args(argv).repo
    index = os.path.join(repo, 'reports', 'index.html')
    try:
        with open(index, encoding='utf-8', newline='') as fh:
            t = write_cards(fh.read(), repo)
        rl.write_text(index, t)
    except (ValueError, OSError) as e:
        return str(e)
    return 0


def write_cards(t: str, repo: str) -> str:
    """The index page t with every family's card block and tab count rewritten from the reports under repo."""
    for folder, (head, note, order) in FAMILIES.items():
        cards = []
        for p in glob.glob(rd.report_path('*', folder, repo=repo)):
            try:
                cards.append(card(folder, p))
            except ValueError as e:
                raise ValueError(f'{os.path.relpath(p, repo)}: {e}') from e
        cards.sort(key=(lambda c: TERM.get(c[0], 99)) if order == 'term' else (lambda c: c[0]))
        block = (f'<!-- asset-cards:{folder} (written by tools/asset_cards.py) -->\n<div class="wrap">\n'
                 f'  <h2 class="shead">{html.escape(head)} <span class="scount">{len(cards)}</span></h2>\n'
                 f'  <p class="famnote">{html.escape(note)}</p>\n  <div class="grid">\n' + '\n'.join(c for _, c in cards) +
                 f'\n  </div>\n</div>\n<!-- /asset-cards:{folder} -->')
        t, n = re.subn(rf'<!-- asset-cards:{folder} .*?<!-- /asset-cards:{folder} -->', lambda _: block, t, flags=re.S)
        if n != 1:
            raise ValueError(f'marker for {folder} not found in reports/index.html')
        t = set_family_count(t, folder, len(cards))
        print(f'{folder}: {len(cards)} cards')
    stocks = len(re.findall(r'<a class="rep"(?! asset)', t))
    t = set_family_count(t, 'stocks', stocks)
    print(f'stocks: {stocks}')
    return t


if __name__ == '__main__':
    sys.exit(main())
