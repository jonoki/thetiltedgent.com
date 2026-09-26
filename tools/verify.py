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
from typing import NotRequired

import reportlib as rl
import repodata as rd


# every report loads this Chart.js build (from cdnjs, or jsdelivr on two older pages); a page on any other version fails
CHART_JS = re.compile(r'<script src="https://(?:cdnjs\.cloudflare\.com/ajax/libs/Chart\.js/4\.4\.1/'
                      r'|cdn\.jsdelivr\.net/npm/chart\.js@4\.4\.1/dist/)chart\.umd\.min\.js"')


class CheckResult(rl.StructureCounts):
    """verify.check() for one page: its structure counts plus these. range and range_ok are absent when the page
    has no readable 52-week range or price."""
    price: float | None
    n_labels: int | None
    n_prices: int | None
    last_price: float | None
    price_match: bool
    pe_stated: float | None
    pe_calc: float | None
    range: NotRequired[tuple[float, float]]
    range_ok: NotRequired[bool]
    date: str | None               # the as-of date, YYYY-MM-DD (reportlib.as_of)
    chart_js: bool
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
    the chart ending on the header price, equal label and price counts, the pinned Chart.js build, the price inside
    its 52-week range (a page with no readable range fails) and the title ticker matching the file name."""
    return bool(not rl.structure_problems(o, path)
                and o['price_match'] and o['n_labels'] == o['n_prices'] and o['chart_js']
                and o.get('range_ok', False) and o['title_ok'])


def title_matches(ticker: str | None, path: str) -> bool:
    """The <title> ticker names the file: on 21 Sep 2026 a builder wrote the Cboe report into mtd_analysis.html
    and a PG&E copy into cboe_analysis.html, and every other check passed."""
    norm = lambda s: re.sub(r'[.\-]', '', s or '').lower()
    return norm(ticker) == norm(rd.slug_of(path))


def check(path: str) -> CheckResult:
    t = rl.read_text(path)
    price = rl.header_price(t)
    labels, prices = rl.chart_series(t)
    pe_stated, pe_calc = pe_pair(t, price)
    ticker = rl.parse_title(t)[0]
    out = CheckResult(
        **rl.structure_counts(t), price=price,
        n_labels=len(labels) if labels is not None else None, n_prices=len(prices) if prices is not None else None,
        last_price=prices[-1] if prices else None,
        price_match=bool(price is not None and prices and abs(prices[-1] - price) < rl.PRICE_EXACT),
        pe_stated=pe_stated, pe_calc=pe_calc, date=rl.as_of(t)[0], chart_js=bool(CHART_JS.search(t)),
        title_ticker=ticker, title_ok=title_matches(ticker, path), ok=False)
    w52 = rl.range_52w(t)
    if w52 and price:
        out['range'] = (w52[0], w52[1])
        out['range_ok'] = w52[0] <= price <= w52[1]
    out['ok'] = passes(out, path)
    return out


def result_line(path: str, o: CheckResult) -> str:
    """The one PASS/FAIL line printed for a report."""
    skel = ''.join(str(o[k]) for k in ('doctype', 'html', 'head', 'body', 'body_close', 'html_close'))
    return (f"{'PASS' if o['ok'] else 'FAIL'} {os.path.basename(path):22s} price={o['price']} last={o['last_price']} "
            f"n={o['n_labels']}/{o['n_prices']} skel={skel} canvas={o['canvas']} lines={o['lines']} "
            f"pe={o['pe_stated']}/{o['pe_calc']} range={o.get('range_ok')} chartjs={o['chart_js']} date={o['date']} "
            f"title={o['title_ticker']}")


def main(argv: list[str] | None = None) -> int:
    files = (sys.argv[1:] if argv is None else argv) or rd.report_paths(assets=True)
    failed = 0
    for f in files:
        if not os.path.isfile(f):
            failed += 1
            print(f'FAIL {f}: no such file')
            continue
        o = check(f)
        failed += not o['ok']
        print(result_line(f, o))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
