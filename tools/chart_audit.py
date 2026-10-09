"""Audit report 5-year monthly charts against Yahoo monthly closes. Read-only on the repo.

usage: py -3 tools/chart_audit.py [slug ...]      (no args = every stock report; exits 1 on any wrong point or error,
       on a named slug's unlabelled dividend-adjusted series, and on a declared spin-off's unlabelled spin-adjusted chart)
       an ETF or crypto report is named with its folder: etf/arti, crypto/btc
       (economic indicators, reports/indicators/, are audited against FRED / Valet by tools/indicator_audit.py)
Flags any chart point more than 3% from Yahoo's split-adjusted month-end close AND from its dividend-adjusted
close, and lists series that are dividend-adjusted but never say so (a named slug with such a series fails:
every report moves to plain closes at its next refresh). The last point (the as-of close) is
verify.py's job. Yahoo JSON is cached under <temp>/ttg_chart_audit/yh; a cached series that ends before the
report's as-of month is fetched again, so a refreshed report's newest points are never skipped silently.

Known spin-offs booked as large splits (SPINOFFS). Yahoo books most spin-offs as small fractional "splits"
(SPIN_RATIO_LO..HI) and a report may chart the real pre-spin closes (a basis step). A few go in as a large ratio
that cannot be told from a real split (Corteva's 1 Oct 2026 Vylor spin, 1 VYLR per CTVA, is a 6.665:1 "split"),
and for those Yahoo's MONTHLY bars came back partly back-adjusted (CTVA: to Dec 2025 not adjusted, from Jan 2026
adjusted), so neither basis matches the whole series. For a slug declared in SPINOFFS {slug: (ISO date, factor)}:
  - the series is the Yahoo DAILY feed's close on each month's last trading day, which Yahoo back-adjusts for the
    whole history (checked for CTVA on 9 Oct 2026: Nov 2021 = 6.7517 = the real 45.00 / 6.665), instead of the
    mixed monthly bars. A daily feed that was not adjusted would put a labelled spin-adjusted chart 6.665x off
    and fail loudly; it cannot pass silently.
  - a chart on the spin-adjusted basis matches it point for point ('ok'), and the page must say so: a pre-spin
    point on that basis with no "spin-adjusted" label on the page fails the run (spin_unlabelled).
  - a chart of the real pre-spin closes sits the declared factor above it: a basis step, as for small spins.
The split logic itself is unchanged: an undeclared large ratio (2:1, 10:1) is still a real split, and a chart
that ignores one is still wrong. Declare only spins whose factor is outside SPIN_RATIO_LO..HI, with the spin's
completion date and the ratio Yahoo booked, from the company's filing and Yahoo's split event.
"""
import datetime
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from http.client import HTTPException
from typing import Literal, Mapping, TypedDict, TypeGuard

import reportlib as rl
import repodata as rd

WORK = os.path.join(tempfile.gettempdir(), 'ttg_chart_audit')   # the Yahoo cache is WORK/yh (cache_dir) and the run's rows go here
YAHOO_CHART = 'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=6y&interval=1mo&events=split'
YAHOO_DAILY_CHART = 'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=6y&interval=1d&events=split'   # SPINOFFS slugs
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
FETCH_TIMEOUT_S, FETCH_PAUSE_S = 30, 0.3
YAHOO_SYMBOL = {'brkb': 'BRK-B', 'bfb': 'BF-B',   # slugs whose Yahoo symbol is not the ticker with '.' -> '-'
                'etf/arti': 'ARTI.TO', 'etf/vfv': 'VFV.TO', 'etf/xeqt': 'XEQT.TO',   # TSX listings
                'etf/xiu': 'XIU.TO', 'etf/zag': 'ZAG.TO', 'etf/cash': 'CASH.TO',
                'crypto/btc': 'BTC-USD', 'crypto/eth': 'ETH-USD', 'crypto/bnb': 'BNB-USD',
                'crypto/sol': 'SOL-USD', 'crypto/xrp': 'XRP-USD',
                'etf/vbal': 'VBAL.TO', 'etf/vgro': 'VGRO.TO',
                # global stocks on their home market (5 Oct 2026 batch): slug -> Yahoo symbol
                'tencent': '0700.HK', 'samsung': '005930.KS', 'skhynix': '000660.KS', 'byd': '1211.HK',
                'catl': '300750.SZ', 'xiaomi': '1810.HK', 'foxconn': '2317.TW', 'mediatek': '2454.TW',
                'keyence': '6861.T', 'tokyoel': '8035.T', 'softbank': '9984.T', 'nintendo': '7974.T',
                'hitachi': '6501.T', 'lvmh': 'MC.PA', 'nestle': 'NESN.SW', 'roche': 'ROP.SW', 'siemens': 'SIE.DE',
                'hermes': 'RMS.PA', 'loreal': 'OR.PA', 'schneidr': 'SU.PA', 'airbus': 'AIR.PA', 'allianz': 'ALV.DE',
                'rheinmtl': 'RHM.DE', 'inditex': 'ITX.MC', 'aramco': '2222.SR', 'reliance': 'RELIANCE.NS',
                'cba': 'CBA.AX',
                'dtelekom': 'DTE.DE', 'sienergy': 'ENR.DE', 'mercedes': 'MBG.DE', 'bmw': 'BMW.DE', 'vw': 'VOW3.DE',
                'infineon': 'IFX.DE', 'munichre': 'MUV2.DE', 'deutschb': 'DBK.DE', 'safran': 'SAF.PA', 'bnp': 'BNP.PA',
                'essilor': 'EL.PA', 'iberdrol': 'IBE.MC', 'unicred': 'UCG.MI', 'abb': 'ABBN.SW', 'zurich': 'ZURN.SW',
                'richemnt': 'CFR.SW', 'rollsroy': 'RR.L', 'lseg': 'LSEG.L', 'glencore': 'GLEN.L', 'prosus': 'PRX.AS',
                'adyen': 'ADYEN.AS', 'atlascop': 'ATCO-A.ST', 'mitsubc': '8058.T', 'fastretl': '9983.T',
                'shinetsu': '4063.T', 'advantst': '6857.T', 'mhi': '7011.T', 'moutai': '600519.SS', 'pingan': '2318.HK',
                'icbc': '1398.HK', 'meituan': '3690.HK', 'tcs': 'TCS.NS', 'bharti': 'BHARTIARTL.NS', 'hyundai': '005380.KS',
                'dbs': 'D05.SI', 'cslltd': 'CSL.AX'}
# First month-end that belongs to the security, where Yahoo's earlier rows are another one (a recycled ticker):
# Evolve's ARTI launched 22 Mar 2024 (first trade 25 Mar); Yahoo ARTI.TO from Nov 2021 is another security.
LAUNCH = {'etf/arti': (2024, 3)}
# Spin-offs Yahoo books as a large "split" (see the module docstring): slug -> (completion date, factor = Yahoo's ratio).
# CTVA: Vylor spin-off completed 1 Oct 2026, 1 VYLR per CTVA (the report cites Corteva's 8-K filed 5 Oct 2026);
# Yahoo's split event for CTVA: 2026-10-01, 6.665:1;
# every prior-edition month-end x 6.665 = Yahoo's real close to the cent (refresh builder, 9 Oct 2026). Oki, 9 Oct 2026.
SPINOFFS: dict[str, tuple[str, float]] = {'ctva': ('2026-10-01', 6.665)}
SPIN_LABEL = re.compile(r'(?i)spin(-?off)?[- ]adjusted')   # the page says its chart is on the post-spin basis
MON = {m: i + 1 for i, m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split())}

TOLERANCE = 0.03          # a point is wrong beyond 3% of both Yahoo's close and its adjusted close
# Spin-offs and capital returns book on Yahoo as small fractional "splits"; 3:2 and up are real splits.
SPIN_RATIO_LO, SPIN_RATIO_HI = 0.9, 1.45
ADJ_UNLABELLED_MIN = 10   # this many adjusted-close matches means the series is dividend-adjusted
ADJ_LABEL = re.compile(r'(?i)dividend[- ]adjusted|adjusted (close|price)')   # the page says its series is adjusted
# ...unless the phrase is negated ("not dividend-adjusted", "rather than adjusted closes"), which says the opposite
ADJ_NEGATED = re.compile(r'(?i)(\bnot|\bnever|\bnor|\bno|\brather than|\binstead of|\bun)[\s,;:(-]*(\w+[\s,]+){0,2}$')
MIN_COMPARABLE = 30       # fewer comparable points than this usually means the labels did not parse
MAX_LISTED = 60
CENTURY = 2000          # two-digit chart years ('Sep '21') are 20xx


Verdict = Literal['ok', 'adjusted', 'basis step', 'wrong']


class PointCheck(TypedDict):
    """check_points(): how many chart points were compared, and the adjusted, basis-step and wrong ones."""
    checked: int
    bad: list[tuple[str, float, float, float]]   # (label, chart value, Yahoo close, % off)
    adj_pts: int
    step_pts: int
    splits_after_as_of: float
    pre_launch: list[str]                          # chart labels dated before the security existed
    spin_adj_pts: int                              # pre-spin points on a declared spin's adjusted basis (SPINOFFS)


class AuditResult(PointCheck):
    """One audited report."""
    slug: str
    ticker: str
    as_of: str | None
    adj_labelled: bool
    spin_labelled: bool                            # the page calls its chart spin-adjusted


class AuditFailure(TypedDict):
    """A report that could not be audited, and why."""
    slug: str
    err: str


AuditRow = AuditResult | AuditFailure


def failed(row: AuditRow) -> TypeGuard[AuditFailure]:
    return 'err' in row


def succeeded(row: AuditRow) -> TypeGuard[AuditResult]:
    return 'err' not in row


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


def yahoo_symbol(slug: str, ticker: str) -> str:
    """The Yahoo symbol of a report: BRK.B -> BRK-B, or the override in YAHOO_SYMBOL."""
    return YAHOO_SYMBOL.get(slug, ticker.replace('.', '-'))


def fetch(slug: str, ticker: str, path: str, daily: bool = False) -> None:
    """Download the Yahoo monthly (or, for a SPINOFFS slug, daily) series for one report into path. Network, HTTP
    and timeout errors -> YahooError."""
    fetch_url((YAHOO_DAILY_CHART if daily else YAHOO_CHART).format(sym=yahoo_symbol(slug, ticker)), path)


def fetch_url(url: str, path: str) -> None:
    """Download one Yahoo chart response into path (also used by refresh_data.py for the daily series).
    Network, HTTP and timeout errors -> YahooError."""
    try:
        body = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=FETCH_TIMEOUT_S).read()  # nosec B310 - fixed https host
    except (urllib.error.URLError, HTTPException, TimeoutError, OSError) as e:   # reported per report, not fatal
        raise YahooError(str(e)) from e
    with open(path, 'wb') as fh:
        fh.write(body)
    time.sleep(FETCH_PAUSE_S)


Monthly = dict[tuple[int, int], tuple[float, float | None]]   # (year, month) -> (close, adjclose)
Splits = list[tuple[str, float]]                              # (ISO date, ratio), oldest first


def monthly_closes(res: dict) -> Monthly:
    """{(year, month): (close, adjclose)} from one Yahoo chart result; months without a close are left out. Rows
    come oldest first and a later row of the same month replaces an earlier one, so a daily result gives each
    month's last trading day."""
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


def cache_dir() -> str:
    """Where fetched Yahoo series are kept: WORK/yh, created on first use."""
    path = os.path.join(WORK, 'yh')
    os.makedirs(path, exist_ok=True)
    return path


def cached_series(path: str, as_of: str | None) -> tuple[Monthly, Splits] | None:
    """The cached series when it reads and is current: it has data and, when the report has an as-of date, reaches
    that month. None (saying why when the file is unreadable) when it has to be fetched again."""
    if not os.path.exists(path):
        return None
    try:
        monthly, splits = read_series(path)
    except YahooError as e:
        print(f'  {os.path.basename(path)}: cached series {e}; fetching it again', file=sys.stderr)
        return None
    if not monthly:
        return None
    as_of_ym = year_month(as_of)
    return (monthly, splits) if as_of_ym is None or max(monthly) >= as_of_ym else None


def monthly_series(slug: str, ticker: str, as_of: str | None) -> tuple[Monthly, Splits]:
    """The monthly series for a report: from the cache when it is readable and current, else fetched again (a
    refreshed report's newest points are never skipped silently). Rows before the security's LAUNCH are dropped.
    A SPINOFFS slug gets the daily feed's month-end closes instead of the monthly bars (module docstring)."""
    daily = slug in SPINOFFS
    path = os.path.join(cache_dir(), slug.replace('/', '_') + ('.d.json' if daily else '.ev.json'))
    cached = cached_series(path, as_of)
    if not cached:
        if daily:
            fetch(slug, ticker, path, daily=True)
        else:
            fetch(slug, ticker, path)
    monthly, splits = cached or read_series(path)
    launch = LAUNCH.get(slug)
    return ({ym: v for ym, v in monthly.items() if ym >= launch} if launch else monthly), splits


def splits_after(splits: Splits, as_of: str | None) -> float:
    """Product of the splits dated after the as-of: Yahoo's closes are adjusted for them, the report is not."""
    f = 1.0
    for dt, r in splits:
        if as_of and dt > as_of:
            f *= r
    return f


def spin_factor(splits: Splits, ym: tuple[int, int], as_of: str | None, declared: tuple[str, float] | None = None) -> float:
    """Product of the small fractional "splits" (spin-offs, capital returns) dated after month ym and by the
    as-of, and of the report's declared SPINOFFS spin (which replaces Yahoo's split on that date); a real pre-spin
    close sits this factor above Yahoo's back-adjusted one."""
    f = 1.0
    events = [(dt, r) for dt, r in splits if not declared or dt != declared[0]]
    for dt, r in events + ([declared] if declared else []):
        is_spin = (dt, r) == declared or (SPIN_RATIO_LO < r < SPIN_RATIO_HI and r != 1)
        if dt[:7] > f'{ym[0]}-{ym[1]:02d}' and (not as_of or dt <= as_of) and is_spin:
            f *= r
    return f


def spin_adjusted_labelled(text: str) -> bool:
    """True when the page says somewhere, without negating it, that its chart is spin-adjusted."""
    return any(not ADJ_NEGATED.search(text[max(0, m.start() - 40):m.start()]) for m in SPIN_LABEL.finditer(text))


def adj_labelled(text: str) -> bool:
    """True when the page says somewhere, without negating it, that its series is dividend-adjusted."""
    return any(not ADJ_NEGATED.search(text[max(0, m.start() - 40):m.start()]) for m in ADJ_LABEL.finditer(text))


def classify(point: float, close: float, adjclose: float | None, spin: float) -> Verdict:
    """'ok' within 3% of the close; else 'adjusted' when it matches the dividend-adjusted close, 'basis step'
    when it matches a real pre-spin close, otherwise 'wrong'."""
    if abs((point - close) / close) <= TOLERANCE:
        return 'ok'
    if adjclose and abs((point - adjclose) / adjclose) <= TOLERANCE:
        return 'adjusted'
    if spin != 1.0 and (abs(point / (close * spin) - 1) <= TOLERANCE or (adjclose and abs(point / (adjclose * spin) - 1) <= TOLERANCE)):
        return 'basis step'
    return 'wrong'


def audit(slug: str, repo: str = rd.ROOT) -> AuditRow:
    """One report's chart against Yahoo, with its ticker and as-of date read from the page itself (so a new or
    just-refreshed report is checked before the manifest is rebuilt); {'slug', 'err'} when it cannot be audited
    (no such page, no ticker in the title, no chart arrays, no Yahoo series)."""
    if slug.startswith('indicators/'):   # values from FRED / Valet, not Yahoo closes
        return {'slug': slug, 'err': 'an economic indicator: audit it with tools/indicator_audit.py'}
    path = rd.report_path(slug, repo=repo)
    if not os.path.exists(path):
        return {'slug': slug, 'err': f'no page {os.path.relpath(path, repo)}'}
    t = rl.read_text(path)
    ticker, as_of = rl.parse_title(t)[0], rl.as_of(t)[0]
    if not ticker:
        return {'slug': slug, 'err': 'no ticker in the <title>'}
    labels, prices = rl.chart_series(t)
    if not labels or not prices:
        return {'slug': slug, 'err': 'arrays'}
    if len(labels) != len(prices):
        return {'slug': slug, 'err': f'{len(labels)} labels for {len(prices)} prices'}
    try:
        series, splits = monthly_series(slug, ticker, as_of)
    except YahooError as e:
        return {'slug': slug, 'err': f'yahoo {e}'}
    return {**check_points(labels, prices, series, splits, as_of, LAUNCH.get(slug), SPINOFFS.get(slug)), 'slug': slug,
            'ticker': ticker, 'as_of': as_of, 'adj_labelled': adj_labelled(t), 'spin_labelled': spin_adjusted_labelled(t)}


def check_points(labels: list[str], prices: list[float], series: Mapping[tuple[int, int], tuple[float, float | None]],
                 splits: Splits, as_of: str | None, launch: tuple[int, int] | None = None,
                 spin: tuple[str, float] | None = None) -> PointCheck:
    """Every chart point with a Yahoo month-end before the as-of month (the last point, the as-of close, is
    verify.py's job): how many were compared, and the adjusted, basis-step and wrong ones. labels and prices
    pair by position (audit() rejects a page whose arrays differ in length).

    Yahoo's close is adjusted for every split it knows, including ones after the report's as-of (the report
    is on its as-of share basis) and spin-offs booked as fractional "splits" (a report may show the real
    pre-spin close). Both are a basis step, not a wrong point. A label before launch (a recycled ticker's earlier
    security) is listed in pre_launch, which fails the audit like a wrong point.

    spin is the report's SPINOFFS entry (date, factor): a real pre-spin close is a basis step at that factor, and
    a pre-spin point that matches the (spin-adjusted) series is counted in spin_adj_pts, which needs a label."""
    as_of_ym = year_month(as_of)
    after = splits_after(splits, as_of)
    spin_on = spin if spin and (not as_of or spin[0] <= as_of) else None   # a spin after the as-of is a plain split
    spin_ym = year_month(spin_on[0]) if spin_on else None
    row: PointCheck = {'checked': 0, 'bad': [], 'adj_pts': 0, 'step_pts': 0, 'splits_after_as_of': after, 'pre_launch': [],
                       'spin_adj_pts': 0}
    for lab, pr in zip(labels[:-1], prices[:-1]):
        ym = parse_label(lab)
        if ym and launch and ym < launch:
            row['pre_launch'].append(lab)
            continue
        if not ym or ym not in series or (as_of_ym and ym >= as_of_ym):
            continue
        row['checked'] += 1
        c, a = series[ym]
        verdict = classify(pr, c * after, a * after if a else None, spin_factor(splits, ym, as_of, spin_on))
        row['adj_pts'] += verdict == 'adjusted'
        row['step_pts'] += verdict == 'basis step'
        row['spin_adj_pts'] += bool(spin_ym and ym < spin_ym and verdict in ('ok', 'adjusted'))
        if verdict == 'wrong':
            row['bad'].append((lab, pr, round(c * after, 2), round((pr - c * after) / (c * after) * 100, 1)))
    return row


def main(argv: list[str] | None = None) -> int | str:
    """Audit the named slugs, or every stock report page; 1 when any point is wrong or any report could not be audited."""
    ap = rd.parser('Audit report charts against Yahoo month-end closes.')
    ap.add_argument('slugs', nargs='*', help='report slugs (default: every stock report)')
    args = ap.parse_args(argv)
    slugs = args.slugs or [rd.slug_of(p) for p in rd.report_paths(args.repo)]
    rows = [audit(slug, repo=args.repo) for slug in slugs]
    rd.write_json(os.path.join(WORK, 'chart_audit.json'), rows, indent=0)
    errs = [r for r in rows if failed(r)]
    done = sorted((r for r in rows if succeeded(r)), key=lambda r: r['ticker'])   # the manifest's order
    flag = [r for r in done if r['bad'] or r['pre_launch']]
    unparsed = [r for r in done if r['checked'] < MIN_COMPARABLE]
    adj_unl = [r for r in done if r['adj_pts'] >= ADJ_UNLABELLED_MIN and not r['adj_labelled']]
    spin_unl = [r for r in done if r['spin_adj_pts'] and not r['spin_labelled']]   # declared spins only (SPINOFFS)
    print('reports', len(rows), '| errors', len(errs), '| WRONG points >3% vs both close and adjclose, or before launch:', len(flag),
          '| dividend-adjusted but unlabelled:', len(adj_unl), '| spin-adjusted but unlabelled:', len(spin_unl),
          '| <30 comparable', len(unparsed))
    print('ADJ-UNLABELLED', [r['slug'] for r in adj_unl])
    print('DECLARED SPIN-OFFS (daily month-end closes; pre-spin points on the spin-adjusted basis, labelled)',
          [(r['slug'], SPINOFFS[r['slug']], r['spin_adj_pts'], r['spin_labelled']) for r in done if r['slug'] in SPINOFFS])
    print('SPIN-UNLABELLED', [r['slug'] for r in spin_unl])
    print('BASIS STEPS (pre-spin real closes / split after as-of; not errors)',
          [(r['slug'], r['step_pts'], r['splits_after_as_of']) for r in done if r['step_pts'] or r['splits_after_as_of'] != 1])
    for r in sorted(flag, key=lambda r: -len(r['bad']))[:MAX_LISTED]:
        if r['pre_launch']:
            print(f"{r['slug']:6} as-of {r['as_of']} {len(r['pre_launch'])} points before launch: {r['pre_launch'][:6]}")
        if r['bad']:
            worst = max(r['bad'], key=lambda b: abs(b[3]))
            print(f"{r['slug']:6} as-of {r['as_of']} bad {len(r['bad']):2}/{r['checked']:2}  worst {worst}")
    print('ERR', [(r['slug'], r['err']) for r in sorted(errs, key=lambda r: r['slug'])][:20])
    print('LOWCOUNT', [(r['slug'], r['checked']) for r in unparsed][:40])
    named = [r for r in adj_unl if args.slugs]   # a build or refresh gate names its slug: an unlabelled adjusted series
    return 1 if (flag or errs or named or spin_unl) else 0   # fails it (rebased to plain closes at refresh; Oki, 8 Oct 2026)


if __name__ == '__main__':
    sys.exit(main())
