#!/usr/bin/env python3
"""Write the ETF, crypto and bond cards on reports/index.html from the reports themselves, and the cards on the
economic-indicators hub (learn/indicators/index.html).

Run from the repo root after adding or renaming a report in reports/etf/, reports/crypto/, reports/fixed/ or
reports/indicators/:
    py -3 tools/asset_cards.py

For each report: ticker and name come from its <title> ("VOO — Vanguard S&P 500 ETF | ETF Analysis"),
the "What it is" line is the first sentence of its section 01, and the category label comes from LABEL below
(add one when you add a report; the script stops if one is missing). The family tab counts are updated too.

The indicator hub lists every indicator in INDICATOR_HUB, built or not: a built one (its page is in
reports/indicators/) links to the report viewer and shows the value and date from its header, the rest show "Coming".
A page in reports/indicators/ that the hub does not list stops the script; so does a built page whose header has no
value or date."""
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
}   # one per repodata.INDEX_FAMILIES folder (a unit test checks); the indicators have the hub below
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
    'cp3m': 'US commercial paper, 3-month', 'ust3y': 'US Treasury note, 3-year',
}
TERM = {'ust3m': 0.25, 'ust10y': 10, 'tips10y': 10.1, 'ust30y': 30, 'goc10y': 10.2,   # years; ties broken by the decimal
        'ust1m': 0.08, 'goc3m': 0.26, 'ust6m': 0.5, 'ust1y': 1, 'ust2y': 2, 'frn2y': 2.05, 'goc2y': 2.1, 'ust5y': 5,
        'tips5y': 5.05, 'goc5y': 5.1, 'gic5y': 5.2, 'ust7y': 7, 'ust20y': 20, 'eebond': 20.5, 'corpaaa': 25,
        'corpbaa': 25.1, 'tips30y': 30.05, 'goc30y': 30.1, 'gocrrb': 30.2, 'ibond': 30.3,
        'cp3m': 0.24, 'ust3y': 3}

CARD_ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.2" y="5" width="10.5" height="14.5" rx="1.8" '
             'transform="rotate(-13 8.5 12.2)"/><rect x="10" y="3.6" width="10.5" height="14.5" rx="1.8" '
             'transform="rotate(11 15.2 10.8)" class="f"/></svg>')


QUOTED_DEFINITION = {'ust30y'}   # its section 01 opens with the definition quoted from TreasuryDirect
# Bonds & cash holds only what a reader can buy. Indicator rates and economic series (not securities) are the
# economic-indicators family, reports/indicators/, with its hub under Learn (Oki, 6 and 8 Oct 2026); SOFR, EFFR and
# CORRA moved there on 8 Oct 2026. GIC5Y stays in Bonds & cash: a deposit you can buy (Oki, 8 Oct 2026).

# The economic-indicators hub (Oki, 8 Oct 2026; first version: rates, inflation, jobs): (group, note, cards), each
# card (slug, code shown on the card, name, one line), plain text. The slugs are tools/indicator_audit.py SERIES (a
# unit test checks). The card copy is a placeholder until Oki reviews it.
INDICATOR_HUB: list[tuple[str, str, list[tuple[str, str, str, str]]]] = [
    ('Rates', 'What money costs: overnight, at the central bank and at the bank counter.', [
        ('sofr', 'SOFR', 'Secured Overnight Financing Rate',
         'What it costs to borrow cash overnight against Treasuries; the US benchmark that replaced LIBOR.'),
        ('effr', 'EFFR', 'Effective Federal Funds Rate',
         "The rate banks pay each other for overnight money, inside the Fed's target range."),
        ('corra', 'CORRA', 'Canadian Overnight Repo Rate Average',
         "Canada's overnight benchmark: borrowing cash overnight against Government of Canada bonds."),
        ('fedtarget', 'FED TARGET', 'Fed funds target range',
         'The range the Federal Reserve sets for overnight lending between banks: the policy rate behind US rates.'),
        ('bocrate', 'BOC RATE', 'Bank of Canada policy rate',
         "The Bank of Canada's target for the overnight rate, its main policy lever."),
        ('prime', 'PRIME', 'US prime rate',
         "The base rate many US banks use to price variable-rate loans; it moves when the Fed's target moves."),
        ('hqm10y', 'HQM 10Y', 'US high-quality corporate bond yield, 10-year',
         "The Treasury's 10-year rate for top-rated (AAA to A) corporate bonds, the curve pension plans use to value what they owe.")]),
    ('Inflation', 'How fast prices are rising.', [
        ('cpi', 'CPI', 'US Consumer Price Index',
         'How fast prices are rising for US households, from the basket the Bureau of Labor Statistics prices monthly.'),
        ('corepce', 'CORE PCE', 'US core PCE inflation',
         "The PCE price index without food and energy; the Fed's 2% goal is set in PCE terms.")]),
    ('Jobs', 'Who is working, and how many jobs were added.', [
        ('unrate', 'UNEMPLOYMENT', 'US unemployment rate',
         'The share of the labor force out of work and looking for it, from the monthly household survey.'),
        ('payrolls', 'PAYROLLS', 'US nonfarm payrolls',
         'How many jobs US employers added or cut last month, from the monthly survey of businesses.')]),
]
# slug: the "why it matters" line under the name on the hub, plain text, ≤ 15 words (Oki, 10 Oct 2026). Checked by an
# independent fact-checker before it is added, like the glossary's.
INDICATOR_WHY: dict[str, str] = {
    'sofr': 'The dominant US dollar benchmark rate, and close to what cash funds pay savers.',
    'effr': 'The market rate the Fed targets, and an anchor for other short-term rates.',
    'corra': "Canada's risk-free benchmark, and the rate that replaced CDOR in Canadian contracts.",
    'fedtarget': 'The rate behind US rates: prime, money market yields and variable-rate loans move with it.',
    'bocrate': 'Canadian prime moves with it, and so do variable-rate loans and what new GICs pay.',
    'prime': 'Many business loans, credit cards and home equity lines charge prime plus a margin.',
    'hqm10y': 'What highly rated companies pay to borrow, from the curve US pension plans use.',
    'cpi': 'Shows how fast money loses buying power, and drives what TIPS and I bonds pay.',
    'corepce': 'Closely watched by the Fed when it sets rates, as a guide to underlying inflation.',
    'unrate': 'Tracks how hard jobs are to find and keep; maximum employment is a Fed goal.',
    'payrolls': 'Shows whether employers are hiring, and bonds and stocks react as traders rethink the Fed.',
}
HUB = os.path.join('learn', 'indicators', 'index.html')
VIEWER = '/reports/view.html?r=indicators/'


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
    repo = rd.parser('Write the ETF, crypto and bond cards on reports/index.html and the indicator hub cards.'
                     ).parse_args(argv).repo
    index, hub = os.path.join(repo, 'reports', 'index.html'), os.path.join(repo, HUB)
    try:
        with open(index, encoding='utf-8', newline='') as fh:
            t = write_cards(fh.read(), repo)
        with open(hub, encoding='utf-8', newline='') as fh:
            h = write_hub(fh.read(), repo)
        rl.write_text(index, t)
        rl.write_text(hub, h)
    except (ValueError, OSError) as e:
        return str(e)
    return 0


_DATE = re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?(?: \d{1,2},)? \d{4}\b')


def indicator_value(page: str) -> tuple[str, str]:
    """(value, date) from an indicator report's header, as printed: the .price-current text ('3.88%', '3.75–4.00%',
    '+29K') and the first date in its first .price-date, month cut to three letters ('Oct 2, 2026', 'Aug 2026'). The hub shows the same
    figure as the report, so it changes when the report is refreshed. ValueError naming what is missing."""
    v = re.search(r'<div\b[^>]*\bclass="price-current\b[^"]*"[^>]*>(.*?)</div>', page, re.S)
    d = re.search(r'<div\b[^>]*\bclass="price-date\b[^"]*"[^>]*>(.*?)</div>', page, re.S)
    if not v or not rl.strip_tags(v.group(1)).strip():
        raise ValueError('no .price-current value in the header')
    m = _DATE.search(rl.strip_tags(d.group(1))) if d else None
    if not m:
        raise ValueError('no date in the header .price-date')
    return rl.strip_tags(v.group(1)).strip(), re.sub(r'^([A-Z][a-z]{2})[a-z]*\.?', r'\1', m.group(0))


def hub_card(slug: str, code: str, name: str, line: str, value: tuple[str, str] | None) -> str:
    """One row on the indicator hub: a link to the report viewer with the report's header value and its date when
    the page is built, else marked Coming."""
    e = lambda s: html.escape(s, quote=False)
    head = f'<span class="ih"><span class="code">{e(code)}</span><h3>{e(name)}</h3></span>'
    body = (f'<span class="why">{e(INDICATOR_WHY[slug])}</span>' if slug in INDICATOR_WHY else '') + f'<p>{e(line)}</p>'
    if value:
        val = f'<span class="val"><b>{e(value[0])}</b> <span class="vd">{e(value[1])}</span></span>'
        return (f'    <a class="card ind" href="{VIEWER}{slug}">{head}{val}{body}'
                f'<span class="more">Read the report</span></a>')
    return f'    <div class="card ind soon">{head}<span class="val"><span class="coming">Coming</span></span>{body}</div>'


def write_hub(t: str, repo: str) -> str:
    """The hub page t with its card block rewritten: every INDICATOR_HUB card, linked when its page is built.
    ValueError when a built page is not on the hub or the marker is missing."""
    paths = {rd.slug_of(p): p for p in rd.family_reports('indicators', repo)}
    built = set(paths)
    listed = {c[0] for _, _, cards in INDICATOR_HUB for c in cards}
    if built - listed:
        raise ValueError(f'add {sorted(built - listed)} to INDICATOR_HUB in tools/asset_cards.py')
    values = {}
    for slug, p in paths.items():
        try:
            values[slug] = indicator_value(rl.read_text(p))
        except ValueError as err:
            raise ValueError(f'{os.path.relpath(p, repo)}: {err}') from err
    groups = []
    for head, note, cards in INDICATOR_HUB:
        gid = 'g-' + re.sub(r'[^a-z]+', '-', head.lower()).strip('-')
        groups.append(f'<section class="igroup" aria-labelledby="{gid}">\n'
                      f'  <h2 class="ghead" id="{gid}">{html.escape(head)}</h2>\n'
                      f'  <p class="gnote">{html.escape(note)}</p>\n  <div class="cards icards">\n'
                      + '\n'.join(hub_card(*c, value=values.get(c[0])) for c in cards) + '\n  </div>\n</section>')
    block = ('<!-- indicator-cards (written by tools/asset_cards.py) -->\n' + '\n'.join(groups)
             + '\n<!-- /indicator-cards -->')
    t, n = re.subn(r'<!-- indicator-cards .*?<!-- /indicator-cards -->', lambda _: block, t, flags=re.S)
    if n != 1:
        raise ValueError(f'marker for the indicator cards not found in {HUB}')
    print(f'indicators: {len(built)} built of {len(listed)} on the hub')
    return t


def write_cards(t: str, repo: str) -> str:
    """The index page t with every family's card block and tab count rewritten from the reports under repo."""
    for folder, (head, note, order) in FAMILIES.items():
        cards = []
        for p in rd.family_reports(folder, repo):
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
