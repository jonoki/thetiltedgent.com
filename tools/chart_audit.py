"""Audit report 5-year monthly charts against Yahoo monthly closes. Read-only on the repo.

usage: py -3 tools/chart_audit.py [slug ...]      (no args = whole library; exits 1 on any wrong point or error)
Flags any chart point more than 3% from Yahoo's split-adjusted month-end close AND from its dividend-adjusted
close, and lists series that are dividend-adjusted but never say so. The last point (the as-of close) is
verify.py's job. Yahoo JSON is cached under <temp>/ttg_chart_audit/yh; a cached series that ends before the
report's as-of month is fetched again, so a refreshed report's newest points are never skipped silently.
"""
import datetime
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from typing import Mapping, TypedDict

import reportlib as rl

WORK = os.path.join(tempfile.gettempdir(), 'ttg_chart_audit')
CACHE = os.path.join(WORK, 'yh')
YAHOO_CHART = 'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=6y&interval=1mo&events=split'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
FETCH_TIMEOUT_S, FETCH_PAUSE_S = 30, 0.3
YAHOO_SYMBOL = {'brkb': 'BRK-B', 'bfb': 'BF-B'}   # slugs whose Yahoo symbol is not the ticker with '.' -> '-'
MON = {m: i + 1 for i, m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split())}

TOLERANCE = 0.03          # a point is wrong beyond 3% of both Yahoo's close and its adjusted close
# Spin-offs and capital returns book on Yahoo as small fractional "splits"; 3:2 and up are real splits.
SPIN_RATIO_LO, SPIN_RATIO_HI = 0.9, 1.45
ADJ_UNLABELLED_MIN = 10   # this many adjusted-close matches means the series is dividend-adjusted
MIN_COMPARABLE = 30       # fewer comparable points than this usually means the labels did not parse
MAX_LISTED = 60
CENTURY = 2000          # two-digit chart years ('Sep '21') are 20xx


class AuditRow(TypedDict, total=False):
    """One report's audit result; 'err' alone when it could not be audited."""
    slug: str
    err: str
    ticker: str
    as_of: str | None
    checked: int
    bad: list[tuple[str, float, float, float]]   # (label, chart value, Yahoo close, % off)
    adj_pts: int
    step_pts: int
    splits_after_as_of: float
    adj_labelled: bool


class YahooError(Exception):
    """No usable monthly series for a symbol."""


def parse_label(s: str) -> tuple[int, int] | None:
    """A chart label ('Sep \\'21', 'Sep 2021', '2021-09') -> (year, month), or None."""
    s = s.strip().strip('\'"`').strip()
    m = re.match(r'([A-Za-z]{3})[a-z]*[\s\'’\-]*(\d{2,4})', s)
    if m and m.group(1).lower() in MON:
        y = int(m.group(2))
        return (y + CENTURY if y < 100 else y, MON[m.group(1).lower()])
    m = re.match(r'(\d{4})-(\d{2})', s)
    return (int(m.group(1)), int(m.group(2))) if m else None


def year_month(as_of: str | None) -> tuple[int, int] | None:
    """'2026-09-21' -> (2026, 9); None stays None."""
    return (int(as_of[:4]), int(as_of[5:7])) if as_of else None


def fetch(slug: str, ticker: str, path: str) -> None:
    """Download the Yahoo series for one report into path. Network, HTTP and timeout errors -> YahooError."""
    url = YAHOO_CHART.format(sym=YAHOO_SYMBOL.get(slug, ticker.replace('.', '-')))
    try:
        body = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=FETCH_TIMEOUT_S).read()  # nosec B310 - fixed https host
    except Exception as e:                        # network, HTTP or timeout: reported per report, not fatal
        raise YahooError(str(e)) from e
    with open(path, 'wb') as fh:
        fh.write(body)
    time.sleep(FETCH_PAUSE_S)


Monthly = dict[tuple[int, int], tuple[float, float | None]]   # (year, month) -> (close, adjclose)
Splits = list[tuple[str, float]]                              # (ISO date, ratio), oldest first


def monthly_closes(res: dict) -> Monthly:
    """{(year, month): (close, adjclose)} from one Yahoo chart result; months without a close are left out."""
    closes = res['indicators']['quote'][0].get('close') or []
    adj = ((res['indicators'].get('adjclose') or [{}])[0].get('adjclose')) or [None] * len(closes)
    offset = res['meta'].get('gmtoffset') or 0
    monthly = {}
    for ts, c, a in zip(res.get('timestamp') or [], closes, adj):
        if c is not None:
            d = datetime.datetime.fromtimestamp(ts + offset, datetime.UTC)
            monthly[(d.year, d.month)] = (c, a)
    return monthly


def split_events(res: dict) -> Splits:
    """[(ISO date, ratio), ...] of the splits in one Yahoo chart result, oldest first."""
    events = (res.get('events') or {}).get('splits', {})
    return sorted((datetime.datetime.fromtimestamp(int(k), datetime.UTC).date().isoformat(), v['numerator'] / v['denominator'])
                  for k, v in events.items())


def read_series(path: str) -> tuple[Monthly, Splits]:
    """Cached Yahoo JSON -> (monthly closes, splits). A file that is not a Yahoo chart response (truncated, an
    error page, a changed schema) raises YahooError, like a failed fetch."""
    try:
        with open(path, encoding='utf-8') as fh:
            results = (json.load(fh).get('chart') or {}).get('result')
        if not results:
            raise YahooError('no result')
        return monthly_closes(results[0]), split_events(results[0])
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, ZeroDivisionError) as e:   # JSONDecodeError is a ValueError
        raise YahooError(f'unreadable series ({type(e).__name__})') from e


def cached_series(path: str, as_of: str | None) -> tuple[Monthly, Splits] | None:
    """The cached series when it reads and reaches the report's as-of month; None (saying why when the file
    is unreadable) when it has to be fetched again."""
    if not os.path.exists(path):
        return None
    try:
        monthly, splits = read_series(path)
    except YahooError as e:
        print(f'  {os.path.basename(path)}: cached series {e}; fetching it again', file=sys.stderr)
        return None
    if monthly and max(monthly) >= (year_month(as_of) or min(monthly)):
        return monthly, splits
    return None


def yahoo(slug: str, ticker: str, as_of: str | None) -> tuple[Monthly, Splits]:
    """The monthly series for a report: from the cache when it is readable and current, else fetched again (a
    refreshed report's newest points are never skipped silently)."""
    path = os.path.join(CACHE, slug + '.ev.json')
    cached = cached_series(path, as_of)
    if cached:
        return cached
    fetch(slug, ticker, path)
    return read_series(path)


def splits_after(splits: Splits, as_of: str | None) -> float:
    """Product of the splits dated after the as-of: Yahoo's closes are adjusted for them, the report is not."""
    f = 1.0
    for dt, r in splits:
        if as_of and dt > as_of:
            f *= r
    return f


def spin_factor(splits: Splits, ym: tuple[int, int], as_of: str | None) -> float:
    """Product of the small fractional "splits" (spin-offs, capital returns) dated after month ym and by the
    as-of; a real pre-spin close sits this factor above Yahoo's back-adjusted one."""
    f = 1.0
    for dt, r in splits:
        if dt[:7] > f'{ym[0]}-{ym[1]:02d}' and (not as_of or dt <= as_of) and SPIN_RATIO_LO < r < SPIN_RATIO_HI and r != 1:
            f *= r
    return f


def classify(point: float, close: float, adjclose: float | None, spin: float) -> str:
    """'ok' within 3% of the close; else 'adjusted' when it matches the dividend-adjusted close, 'basis step'
    when it matches a real pre-spin close, otherwise 'wrong'."""
    if abs((point - close) / close) <= TOLERANCE:
        return 'ok'
    if adjclose and abs((point - adjclose) / adjclose) <= TOLERANCE:
        return 'adjusted'
    if spin != 1.0 and (abs(point / (close * spin) - 1) <= TOLERANCE or (adjclose and abs(point / (adjclose * spin) - 1) <= TOLERANCE)):
        return 'basis step'
    return 'wrong'


def audit(slug: str, repo: str = rl.ROOT) -> AuditRow:
    """One report's chart against Yahoo, with its ticker and as-of date read from the page itself (so a new or
    just-refreshed report is checked before the manifest is rebuilt); {'slug', 'err'} when it cannot be audited
    (no such page, no ticker in the title, no chart arrays, no Yahoo series)."""
    path = rl.report_path(slug, repo=repo)
    if not os.path.exists(path):
        return {'slug': slug, 'err': f'no page {os.path.relpath(path, repo)}'}
    t = rl.read_text(path)
    ticker, as_of = rl.parse_title(t)[0], rl.as_of(t)[0]
    if not ticker:
        return {'slug': slug, 'err': 'no ticker in the <title>'}
    labels, prices = rl.chart_series(t)
    if not labels or not prices:
        return {'slug': slug, 'err': 'arrays'}
    try:
        yh, splits = yahoo(slug, ticker, as_of)
    except YahooError as e:
        return {'slug': slug, 'err': f'yahoo {e}'}
    row = check_points(labels, prices, yh, splits, as_of)
    row.update({'slug': slug, 'ticker': ticker, 'as_of': as_of,
                'adj_labelled': bool(re.search(r'(?i)dividend[- ]adjusted|adjusted (close|price)', t))})
    return row


def check_points(labels: list[str], prices: list[float], yh: Mapping[tuple[int, int], tuple[float, float | None]],
                 splits: Splits, as_of: str | None) -> AuditRow:
    """Every chart point with a Yahoo month-end before the as-of month (the last point, the as-of close, is
    verify.py's job): how many were compared, and the adjusted, basis-step and wrong ones.

    Yahoo's close is adjusted for every split it knows, including ones after the report's as-of (the report
    is on its as-of share basis) and spin-offs booked as fractional "splits" (a report may show the real
    pre-spin close). Both are a basis step, not a wrong point."""
    as_of_ym = year_month(as_of)
    after = splits_after(splits, as_of)
    row: AuditRow = {'checked': 0, 'bad': [], 'adj_pts': 0, 'step_pts': 0, 'splits_after_as_of': after}
    for lab, pr in zip(labels[:-1], prices[:-1]):
        ym = parse_label(lab)
        if not ym or ym not in yh or (as_of_ym and ym >= as_of_ym):
            continue
        row['checked'] += 1
        c, a = yh[ym]
        verdict = classify(pr, c * after, a * after if a else None, spin_factor(splits, ym, as_of))
        row['adj_pts'] += verdict == 'adjusted'
        row['step_pts'] += verdict == 'basis step'
        if verdict == 'wrong':
            row['bad'].append((lab, pr, round(c * after, 2), round((pr - c * after) / (c * after) * 100, 1)))
    return row


def main(argv: list[str] | None = None) -> int:
    """Audit the named slugs, or every stock report page; 1 when any point is wrong or any report could not be audited."""
    slugs = (sys.argv[1:] if argv is None else argv) or [os.path.basename(p).replace('_analysis.html', '')
                                                          for p in rl.report_paths()]
    os.makedirs(CACHE, exist_ok=True)
    rows = sorted((audit(slug) for slug in slugs), key=lambda r: r.get('ticker') or r['slug'])   # the manifest's order
    with open(os.path.join(WORK, 'chart_audit.json'), 'w', encoding='utf-8') as fh:
        json.dump(rows, fh, indent=0)
    errs = [r for r in rows if 'err' in r]
    flag = [r for r in rows if r.get('bad')]
    unparsed = [r for r in rows if 'err' not in r and r['checked'] < MIN_COMPARABLE]
    adj_unl = [r for r in rows if r.get('adj_pts', 0) >= ADJ_UNLABELLED_MIN and not r.get('adj_labelled')]
    print('reports', len(rows), '| errors', len(errs), '| WRONG points >3% vs both close and adjclose:', len(flag),
          '| dividend-adjusted but unlabelled:', len(adj_unl), '| <30 comparable', len(unparsed))
    print('ADJ-UNLABELLED', [r['slug'] for r in adj_unl])
    print('BASIS STEPS (pre-spin real closes / split after as-of; not errors)',
          [(r['slug'], r['step_pts'], r['splits_after_as_of']) for r in rows if r.get('step_pts') or r.get('splits_after_as_of', 1) != 1])
    for r in sorted(flag, key=lambda r: -len(r['bad']))[:MAX_LISTED]:
        worst = max(r['bad'], key=lambda b: abs(b[3]))
        print(f"{r['slug']:6} as-of {r['as_of']} bad {len(r['bad']):2}/{r['checked']:2}  worst {worst}")
    print('ERR', [(r['slug'], r['err']) for r in errs][:20])
    print('LOWCOUNT', [(r['slug'], r['checked']) for r in unparsed][:40])
    return 1 if (flag or errs) else 0


if __name__ == '__main__':
    sys.exit(main())
