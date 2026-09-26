#!/usr/bin/env python3
"""Pre-publish gate for report pages: document skeleton, chart arrays, final chart value == header price,
52-week range, <title> ticker == file name, no embedded site nav.

usage:  py -3 tools/verify.py [report.html ...]      (no arguments = every report in the library)
Prints one PASS/FAIL line per report and exits 1 if any report fails.

P/E is printed as stated/calculated (price ÷ EPS) for a reader to compare, and is deliberately not part of
PASS: the EPS row's wording varies too much between reports for a pattern match to be trusted as a gate
(tasks/lessons.md, 21 Sep 2026). Fix the pattern, not the report's prose, when the two disagree.
"""
import os
import re
import sys

import reportlib as rl


def table_cells(t):
    """First two <td> texts of every table row, keyed by the first: metrics labels are often split into
    tooltip spans ("<span>EPS</span> (<span>TTM</span>)"), so rows are read with tags stripped rather than
    by a loose pattern over the page, which picks up numbers from prose or the next row."""
    rows = {}
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.S):
        cells = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
        if len(cells) >= 2:
            rows.setdefault(cells[0], cells[1])
    return rows


def plain_value(cell):
    """A value cell that is a plain number ('24.1x', '−$1.20'); None for n/m, n/a, ~257x and the like, so an
    unreadable cell yields no P/E check rather than a wrong one."""
    m = re.match(r'^\s*([−-])?\s*\$?([\d,]+(?:\.\d+)?)\s*[x×]?\s*(?:$|\(|—|–|-|\s)', cell)
    return (-1 if m.group(1) else 1) * rl.to_number(m.group(2)) if m else None


def pe_pair(t, price):
    """(stated trailing P/E, price ÷ EPS) when both are readable and EPS is positive, else (None, None)."""
    rows = table_cells(t)
    pe_cell = next((v for k, v in rows.items() if re.match(r'^Trailing P/?E\b', k)), None)
    eps_cell = next((v for k, v in rows.items() if re.match(r'^(?:Diluted )?EPS \(TTM\b', k)), None)
    pe_v, eps_v = (plain_value(pe_cell) if pe_cell else None), (plain_value(eps_cell) if eps_cell else None)
    if pe_v is not None and eps_v and eps_v > 0 and price:
        return pe_v, round(price / eps_v, 2)
    return None, None


def check(path):
    t = rl.read_text(path)
    out = rl.structure_counts(t)   # a missing </head> (EXPD) or </style> (CAT, blank for five weeks) fails here
    price = rl.header_price(t)
    out['price'] = price
    labels, prices = rl.chart_series(t)
    out['n_labels'] = len(labels) if labels is not None else None
    out['n_prices'] = len(prices) if prices is not None else None
    out['last_price'] = prices[-1] if prices else None
    out['price_match'] = bool(price is not None and prices and abs(prices[-1] - price) < rl.PRICE_EXACT)
    out['pe_stated'], out['pe_calc'] = pe_pair(t, price)
    w52 = rl.range_52w(t)
    if w52 and price:
        out['range'] = tuple(w52)
        out['range_ok'] = w52[0] <= price <= w52[1]
    date = re.search(r'Static data as of ([A-Za-z]+ \d+, \d{4})', t)
    out['date'] = date.group(1) if date else None
    # the <title> ticker must match the file name: on 21 Sep 2026 a builder wrote the Cboe report into
    # mtd_analysis.html and a PG&E copy into cboe_analysis.html, and every other check passed
    slug = os.path.basename(path).replace('_analysis.html', '')
    out['title_ticker'] = rl.parse_title(t)[0]
    norm = lambda s: re.sub(r'[.\-]', '', s or '').lower()
    out['title_ok'] = norm(out['title_ticker']) == norm(slug)
    # bond/cash reports (reports/fixed/) carry a third canvas: the yield curve in section 02
    want_canvas = 3 if re.search(r'[\\/]fixed[\\/]', os.path.abspath(path)) else 2
    out['OK'] = (all(out[k] == 1 for k in rl.SKELETON + ('head_close',))
                 and out['canvas'] == want_canvas and out['style_open'] == out['style_close']
                 and out['price_match'] and out['n_labels'] == out['n_prices'] and out['sitenav'] == 0
                 and out.get('range_ok', True) and out['title_ok'])
    return out


def line(path, o):
    skel = ''.join(str(o[k]) for k in ('doctype', 'html', 'head', 'body', 'body_close', 'html_close'))
    return (f"{'PASS' if o['OK'] else 'FAIL'} {os.path.basename(path):22s} price={o['price']} last={o['last_price']} "
            f"n={o['n_labels']}/{o['n_prices']} skel={skel} canvas={o['canvas']} lines={o['lines']} "
            f"pe={o['pe_stated']}/{o['pe_calc']} range={o.get('range_ok')} date={o['date']} title={o['title_ticker']}")


def main(argv=None):
    files = (sys.argv[1:] if argv is None else argv) or rl.report_paths(assets=True)
    failed = 0
    for f in files:
        o = check(f)
        failed += not o['OK']
        print(line(f, o))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
