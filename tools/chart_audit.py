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


class YahooError(Exception):
    """No usable monthly series for a symbol."""


def parse_label(s):
    """A chart label ('Sep \\'21', 'Sep 2021', '2021-09') -> (year, month), or None."""
    s = s.strip().strip('\'"`').strip()
    m = re.match(r'([A-Za-z]{3})[a-z]*[\s\'’\-]*(\d{2,4})', s)
    if m and m.group(1).lower() in MON:
        y = int(m.group(2))
        return (y + 2000 if y < 100 else y, MON[m.group(1).lower()])
    m = re.match(r'(\d{4})-(\d{2})', s)
    return (int(m.group(1)), int(m.group(2))) if m else None


def fetch(slug, tick, path):
    url = YAHOO_CHART.format(sym=YAHOO_SYMBOL.get(slug, tick.replace('.', '-')))
    if not url.startswith('https://'):
        raise YahooError(f'refusing non-https url {url}')
    try:
        body = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=FETCH_TIMEOUT_S).read()  # nosec B310 - fixed https host
    except Exception as e:                        # network, HTTP or timeout: reported per report, not fatal
        raise YahooError(str(e)) from e
    with open(path, 'wb') as fh:
        fh.write(body)
    time.sleep(FETCH_PAUSE_S)


def read_series(path):
    """Cached Yahoo JSON -> ({(year, month): (close, adjclose)}, [(split date, ratio), ...])."""
    with open(path, encoding='utf-8') as fh:
        j = json.load(fh)
    res = (j.get('chart') or {}).get('result')
    if not res:
        raise YahooError('no result')
    res = res[0]
    closes = res['indicators']['quote'][0].get('close') or []
    adj = ((res['indicators'].get('adjclose') or [{}])[0].get('adjclose')) or [None] * len(closes)
    offset = res['meta'].get('gmtoffset') or 0
    monthly = {}
    for ts, c, a in zip(res.get('timestamp') or [], closes, adj):
        if c is not None:
            d = datetime.datetime.fromtimestamp(ts + offset, datetime.UTC)
            monthly[(d.year, d.month)] = (c, a)
    splits = sorted((datetime.datetime.fromtimestamp(int(k), datetime.UTC).date().isoformat(), v['numerator'] / v['denominator'])
                    for k, v in (res.get('events') or {}).get('splits', {}).items())
    return monthly, splits


def yahoo(slug, tick, asof_ym):
    """The monthly series for a report, from the cache when it reaches the report's as-of month."""
    path = os.path.join(CACHE, slug + '.ev.json')
    if not os.path.exists(path):
        fetch(slug, tick, path)
    monthly, splits = read_series(path)
    if asof_ym and monthly and max(monthly) < asof_ym:
        fetch(slug, tick, path)
        monthly, splits = read_series(path)
    return monthly, splits


def audit(slug, tick, asof):
    t = rl.read_text(os.path.join(rl.ROOT, 'reports', slug + '_analysis.html'))
    labels, prices = rl.chart_series(t)
    if not labels or not prices:
        return {'slug': slug, 'err': 'arrays'}
    asof_ym = tuple(int(x) for x in asof.split('-')[:2]) if asof else None
    try:
        yh, splits = yahoo(slug, tick, asof_ym)
    except YahooError as e:
        return {'slug': slug, 'err': f'yahoo {e}'}
    # Yahoo's close is adjusted for every split it knows, including ones after the report's as-of (the report
    # is on its as-of share basis) and spin-offs booked as fractional "splits" (a report may show the real
    # pre-spin close). Both are a basis step, not a wrong point.
    after = 1.0
    for dt, r in splits:
        if asof and dt > asof:
            after *= r
    bad, n, adj_ok, step_ok = [], 0, 0, 0
    for lab, pr in zip(labels[:-1], prices[:-1]):   # the last point is the as-of close, checked by verify.py
        ym = parse_label(lab)
        if not ym or ym not in yh or (asof_ym and ym >= asof_ym):
            continue
        n += 1
        c, a = yh[ym]
        spin = 1.0
        for dt, r in splits:
            if dt[:7] > f'{ym[0]}-{ym[1]:02d}' and (not asof or dt <= asof) and SPIN_RATIO_LO < r < SPIN_RATIO_HI and r != 1:
                spin *= r
        dev = (pr - c * after) / (c * after)
        if abs(dev) <= TOLERANCE:
            continue
        if a and abs((pr - a * after) / (a * after)) <= TOLERANCE:
            adj_ok += 1
        elif spin != 1.0 and (abs(pr / (c * after * spin) - 1) <= TOLERANCE or (a and abs(pr / (a * after * spin) - 1) <= TOLERANCE)):
            step_ok += 1
        else:
            bad.append((lab, pr, round(c * after, 2), round(dev * 100, 1)))
    return {'slug': slug, 'tick': tick, 'asof': asof, 'checked': n, 'bad': bad, 'adj_pts': adj_ok, 'step_pts': step_ok,
            'splits_after_asof': after, 'adj_labelled': bool(re.search(r'(?i)dividend[- ]adjusted|adjusted (close|price)', t))}


def main(argv=None):
    only = set(sys.argv[1:] if argv is None else argv)
    os.makedirs(CACHE, exist_ok=True)
    rows = [audit(slug, tick, asof) for tick, slug, _sec, asof, _px in rl.load_manifest()['index']
            if not only or slug in only]
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
          [(r['slug'], r['step_pts'], r['splits_after_asof']) for r in rows if r.get('step_pts') or r.get('splits_after_asof', 1) != 1])
    for r in sorted(flag, key=lambda r: -len(r['bad']))[:MAX_LISTED]:
        worst = max(r['bad'], key=lambda b: abs(b[3]))
        print(f"{r['slug']:6} as-of {r['asof']} bad {len(r['bad']):2}/{r['checked']:2}  worst {worst}")
    print('ERR', [(r['slug'], r['err']) for r in errs][:20])
    print('LOWCOUNT', [(r['slug'], r['checked']) for r in unparsed][:40])
    return 1 if (flag or errs) else 0


if __name__ == '__main__':
    sys.exit(main())
