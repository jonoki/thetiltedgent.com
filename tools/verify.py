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
from typing import TypedDict

import reportlib as rl
import repodata as rd


class CheckResult(rl.StructureCounts, total=False):
    """verify.check() for one page: its structure counts plus these."""
    price: float | None
    n_labels: int | None
    n_prices: int | None
    last_price: float | None
    price_match: bool
    pe_stated: float | None
    pe_calc: float | None
    range: tuple[float, float]
    range_ok: bool
    date: str | None
    title_ticker: str | None
    title_ok: bool
    ok: bool


def plain_value(cell: str) -> float | None:
    """A value cell that is a plain number ('24.1x', '−$1.20'); None for n/m, n/a, ~257x and the like, so an
    unreadable cell yields no P/E check rather than a wrong one."""
    m = re.match(r'^\s*([−-])?\s*\$?([\d,]+(?:\.\d+)?)\s*[x×]?\s*(?:$|\(|—|–|-|\s)', cell)
    return (-1 if m.group(1) else 1) * float(m.group(2).replace(',', '')) if m else None


def pe_pair(t: str, price: float | None) -> tuple[float | None, float | None]:
    """(stated trailing P/E, price ÷ EPS) when both are readable and EPS is positive, else (None, None). Rows
    are matched by label, not by a loose pattern over the page, which picks up numbers from prose or the next row."""
    rows = rl.table_rows(t)
    pe_cell = rl.row_value(rows, r'Trailing P/?E\b')
    eps_cell = rl.row_value(rows, r'(?:Diluted )?EPS \(TTM\b')
    pe_v, eps_v = (plain_value(pe_cell) if pe_cell else None), (plain_value(eps_cell) if eps_cell else None)
    if pe_v is not None and eps_v and eps_v > 0 and price:
        return pe_v, round(price / eps_v, 2)
    return None, None


def passes(o: CheckResult, path: str) -> bool:
    """The gate: no structure problem (skeleton, canvas count, <style> tags, site nav; reportlib.structure_problems),
    the chart ending on the header price, equal label and price counts, the price inside its 52-week range and
    the title ticker matching the file name."""
    return bool(not rl.structure_problems(o, path)
                and o['price_match'] and o['n_labels'] == o['n_prices']
                and o.get('range_ok', False) and o['title_ok'])   # no readable range (or price) fails


def check(path: str) -> CheckResult:
    t = rl.read_text(path)
    out = CheckResult(**rl.structure_counts(t))
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
        out['range'] = (w52[0], w52[1])
        out['range_ok'] = w52[0] <= price <= w52[1]
    date = re.search(r'Static data as of ([A-Za-z]+ \d+, \d{4})', t)
    out['date'] = date.group(1) if date else None
    # the <title> ticker must match the file name: on 21 Sep 2026 a builder wrote the Cboe report into
    # mtd_analysis.html and a PG&E copy into cboe_analysis.html, and every other check passed
    slug = os.path.basename(path).replace('_analysis.html', '')
    out['title_ticker'] = rl.parse_title(t)[0]
    norm = lambda s: re.sub(r'[.\-]', '', s or '').lower()
    out['title_ok'] = norm(out['title_ticker']) == norm(slug)
    out['ok'] = passes(out, path)
    return out


def result_line(path: str, o: CheckResult) -> str:
    """The one PASS/FAIL line printed for a report."""
    skel = ''.join(str(o[k]) for k in ('doctype', 'html', 'head', 'body', 'body_close', 'html_close'))
    return (f"{'PASS' if o['ok'] else 'FAIL'} {os.path.basename(path):22s} price={o['price']} last={o['last_price']} "
            f"n={o['n_labels']}/{o['n_prices']} skel={skel} canvas={o['canvas']} lines={o['lines']} "
            f"pe={o['pe_stated']}/{o['pe_calc']} range={o.get('range_ok')} date={o['date']} title={o['title_ticker']}")


def main(argv: list[str] | None = None) -> int:
    files = (sys.argv[1:] if argv is None else argv) or rd.report_paths(assets=True)
    failed = 0
    for f in files:
        o = check(f)
        failed += not o['ok']
        print(result_line(f, o))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
