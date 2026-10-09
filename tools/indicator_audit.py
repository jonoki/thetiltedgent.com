"""Audit an economic-indicator report's 5-year chart against the official series (FRED or Bank of Canada Valet).
Read-only on the repo.

usage: py -3 tools/indicator_audit.py indicators/cpi [indicators/sofr ...]   (no args = every indicator report;
       'cpi' works too)
Every chart point, the last one included, is compared with the official value for its label:
  a month label ('Sep 26', "Sep '26", '2026-09')  the month's observation of a monthly series, or the last
                                                  observation in that month, on or before the as-of, of a daily one
  a day label ('Oct 2 26', 'Oct 2, 2026')         that day's observation (a daily series only)
after the series' transform (SERIES: level, 12-month % change, or monthly change). A point is wrong when it is more
than TOLERANCE_UNITS units of the last decimal the page shows (SERIES dp) away from the official value, and
unmatched when its label does not parse or the series has no value for it. The page must also cite the series id.
Exits 1 on any wrong or unmatched point, an uncited series, or a report that could not be audited.

Values are compared with the series as published today (the latest vintage): a point revised after the page's as-of
(payrolls are revised for two months, and every February) shows as wrong until the next refresh updates it.
Downloads are cached under <temp>/ttg_indicator_audit for CACHE_HOURS. No personal data goes in any request.
"""
import csv
import datetime
import io
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from http.client import HTTPException
from typing import Literal, NamedTuple, TypedDict, TypeGuard

import reportlib as rl
import repodata as rd

FAMILY = 'indicators'
WORK = os.path.join(tempfile.gettempdir(), 'ttg_indicator_audit')
FRED_CSV = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}'
VALET_JSON = 'https://www.bankofcanada.ca/valet/observations/{sid}/json?start_date={start}'
# No User-Agent of our own: Python's default ('Python-urllib/3.x') carries no personal data, and FRED left requests
# with a browser-like or custom User-Agent hanging until the timeout (9 Oct 2026), while answering the default in <1 s.
HEADERS: dict[str, str] = {}
FETCH_TIMEOUT_S, FETCH_TRIES, FETCH_PAUSE_S = 60, 2, 0.5
CACHE_HOURS = 6
TOLERANCE_UNITS = 0.55   # a hair over half a unit, so a value on a rounding boundary (2.95 -> 3.0 or 2.9) passes
YEARS_BACK = 7           # fetched history: five years of chart, plus the 12 months a year-over-year change needs


class Series(NamedTuple):
    """The official series behind one indicator report's chart (the prices array)."""
    source: Literal['fred', 'valet']
    series_id: str                  # FRED id or Valet series name; the page must cite it
    freq: Literal['daily', 'monthly']
    transform: Literal['level', 'yoy', 'change']   # yoy = 100 × (x_t / x_t−12 − 1); change = x_t − x_t−1
    dp: int                         # decimals the page shows
    plots: str                      # what the chart plots, for the brief and the audit line


# One per indicator slug (the hub's list in tools/asset_cards.py INDICATOR_HUB; a unit test checks the two agree).
SERIES: dict[str, Series] = {
    'sofr': Series('fred', 'SOFR', 'daily', 'level', 2, 'SOFR, %, New York Fed'),
    'effr': Series('fred', 'EFFR', 'daily', 'level', 2, 'effective federal funds rate, %, New York Fed'),
    'corra': Series('valet', 'AVG.INTWO', 'daily', 'level', 2, 'CORRA, %, Bank of Canada'),
    'fedtarget': Series('fred', 'DFEDTARU', 'daily', 'level', 2,
                        'upper limit of the FOMC federal funds target range, %, Federal Reserve'),
    'bocrate': Series('valet', 'V39079', 'daily', 'level', 2, 'target for the overnight rate, %, Bank of Canada'),
    'prime': Series('fred', 'DPRIME', 'daily', 'level', 2, 'bank prime loan rate, %, Federal Reserve H.15'),
    'hqm10y': Series('fred', 'HQMCB10YR', 'monthly', 'level', 2,
                     'HQM corporate bond 10-year spot rate, %, monthly average, U.S. Treasury'),
    'cpi': Series('fred', 'CPIAUCNS', 'monthly', 'yoy', 1,
                  'CPI-U all items, 12-month % change, not seasonally adjusted, BLS (CUUR0000SA0)'),
    'corepce': Series('fred', 'PCEPILFE', 'monthly', 'yoy', 1,
                      'PCE price index excluding food and energy, 12-month % change, seasonally adjusted, BEA'),
    'unrate': Series('fred', 'UNRATE', 'monthly', 'level', 1, 'unemployment rate, %, seasonally adjusted, BLS (LNS14000000)'),
    'payrolls': Series('fred', 'PAYEMS', 'monthly', 'change', 0,
                       'total nonfarm payrolls, monthly change in thousands, seasonally adjusted, BLS (CES0000000001)'),
}

MON = {m: i + 1 for i, m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split())}
Label = tuple[int, int, int | None]          # (year, month, day or None for a month label)
Observations = dict[str, float]              # ISO date -> value, missing values left out


class AuditResult(TypedDict):
    slug: str
    series: str
    as_of: str | None
    checked: int
    wrong: list[tuple[str, float, float]]    # (label, page value, official value)
    unmatched: list[str]
    cited: bool


class AuditFailure(TypedDict):
    slug: str
    err: str


class FetchError(Exception):
    """No usable series from the publisher."""


def parse_label(s: str) -> Label | None:
    """A chart label -> (year, month, day or None): 'Oct 21', "Oct '21", 'October 2021', '2021-10' are months;
    'Oct 2 26', 'Oct 2, 2026', '2026-10-02' are days. Two-digit years are 20xx."""
    s = s.strip().strip('\'"`').strip()
    m = re.match(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+['’]?(\d{4}|\d{2})$", s)
    if m and m.group(1).lower() in MON:
        y = int(m.group(3))
        return (y + 2000 if y < 100 else y, MON[m.group(1).lower()], int(m.group(2)))
    m = re.match(r"([A-Za-z]{3})[a-z]*\.?[\s'’\-]*(\d{4}|\d{2})$", s)
    if m and m.group(1).lower() in MON:
        y = int(m.group(2))
        return (y + 2000 if y < 100 else y, MON[m.group(1).lower()], None)
    m = re.match(r'(\d{4})-(\d{2})(?:-(\d{2}))?$', s)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else None)
    return None


def parse_fred_csv(text: str) -> Observations:
    """FRED's graph CSV ('observation_date,ID' then one row a date) -> {date: value}; '' and '.' rows are left out."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or len(rows[0]) < 2 or not re.match(r'(?i)(observation_)?date', rows[0][0]):
        raise FetchError('not a FRED CSV')
    out = {}
    for row in rows[1:]:
        if len(row) >= 2 and re.match(r'\d{4}-\d{2}-\d{2}$', row[0]):
            v = rl.to_number(row[1])
            if v is not None:
                out[row[0]] = v
    return out


def parse_valet_json(text: str, sid: str) -> Observations:
    """Bank of Canada Valet observations JSON -> {date: value}."""
    try:
        obs = json.loads(text)['observations']
        out = {}
        for o in obs:
            v = rl.to_number(((o.get(sid) or {}).get('v')) or '')
            if v is not None:
                out[o['d']] = v
        return out
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise FetchError(f'not a Valet response ({type(e).__name__})') from e


def fetch_text(url: str) -> str:
    """The body of url, tried FETCH_TRIES times; FetchError when every try fails."""
    err: Exception | None = None
    for _ in range(FETCH_TRIES):
        try:
            body = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=FETCH_TIMEOUT_S).read()  # nosec B310 - fixed https hosts
            time.sleep(FETCH_PAUSE_S)
            return body.decode('utf-8-sig')
        except (urllib.error.URLError, HTTPException, TimeoutError, OSError, UnicodeDecodeError) as e:
            err = e
    raise FetchError(str(err))


def observations(ser: Series, start: str) -> Observations:
    """The series from start on, from the cache when it is under CACHE_HOURS old, else downloaded."""
    os.makedirs(WORK, exist_ok=True)
    path = os.path.join(WORK, f'{ser.source}_{ser.series_id}_{start}.txt')
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < CACHE_HOURS * 3600
    if fresh:
        text = rl.read_text(path)
    else:
        url = (FRED_CSV if ser.source == 'fred' else VALET_JSON).format(sid=ser.series_id, start=start)
        text = fetch_text(url)
    obs = parse_fred_csv(text) if ser.source == 'fred' else parse_valet_json(text, ser.series_id)
    if not obs:
        raise FetchError('no observations')
    if not fresh:
        rl.write_text(path, text)
    return obs


def shift_month(y: int, m: int, k: int) -> tuple[int, int]:
    """(y, m) moved k months (k may be negative)."""
    n = y * 12 + (m - 1) + k
    return n // 12, n % 12 + 1


def official(obs: Observations, ser: Series, lab: Label, as_of: str | None) -> float | None:
    """The official value for one chart label, after the series' transform; None when there is none."""
    y, m, d = lab
    if ser.freq == 'monthly':
        if d is not None:
            return None   # a monthly series has no day points

        def at(k: int) -> float | None:
            yy, mm = shift_month(y, m, k)
            return obs.get(f'{yy:04d}-{mm:02d}-01')
        x = at(0)
        if x is None or ser.transform == 'level':
            return x
        prev = at(-12 if ser.transform == 'yoy' else -1)
        if not prev:
            return None
        return 100 * (x / prev - 1) if ser.transform == 'yoy' else x - prev
    if ser.transform != 'level':
        return None   # daily series are charted as levels
    if d is not None:
        return obs.get(f'{y:04d}-{m:02d}-{d:02d}')
    prefix = f'{y:04d}-{m:02d}-'
    days = [k for k in obs if k.startswith(prefix) and (not as_of or k <= as_of)]
    return obs[max(days)] if days else None


def check_points(labels: list[str], values: list[float], obs: Observations, ser: Series,
                 as_of: str | None) -> tuple[int, list[tuple[str, float, float]], list[str]]:
    """(points compared, wrong points as (label, page, official), unmatched labels) for one chart."""
    tol = TOLERANCE_UNITS * 10 ** -ser.dp
    checked, wrong, unmatched = 0, [], []
    for lab, v in zip(labels, values):
        parsed = parse_label(lab)
        want = official(obs, ser, parsed, as_of) if parsed else None
        if want is None:
            unmatched.append(lab)
            continue
        checked += 1
        if abs(v - want) > tol:
            wrong.append((lab, v, round(want, ser.dp + 2)))
    return checked, wrong, unmatched


def bare_slug(slug: str) -> str:
    """'indicators/cpi' or 'cpi' -> 'cpi'."""
    return slug.split('/', 1)[1] if slug.startswith(FAMILY + '/') else slug


def audit(slug: str, repo: str = rd.ROOT) -> AuditResult | AuditFailure:
    """One indicator report's chart against its official series."""
    s = bare_slug(slug)
    path = rd.report_path(s, FAMILY, repo=repo)
    if s not in SERIES:
        return {'slug': slug, 'err': f'no SERIES entry for {s} in tools/indicator_audit.py'}
    if not os.path.exists(path):
        return {'slug': slug, 'err': f'no page {os.path.relpath(path, repo)}'}
    t = rl.read_text(path)
    as_of = rl.as_of(t)[0]
    labels, values = rl.chart_series(t)
    if not labels or not values:
        return {'slug': slug, 'err': 'no labels/prices arrays'}
    if len(labels) != len(values):
        return {'slug': slug, 'err': f'{len(labels)} labels for {len(values)} values'}
    ser = SERIES[s]
    first = parse_label(labels[0])
    start_year = (first[0] if first else datetime.date.today().year - 5) - (YEARS_BACK - 5)
    try:
        obs = observations(ser, f'{start_year}-01-01')
    except FetchError as e:
        return {'slug': slug, 'err': f'{ser.source} {ser.series_id}: {e}'}
    checked, wrong, unmatched = check_points(labels, values, obs, ser, as_of)
    return {'slug': f'{FAMILY}/{s}', 'series': f'{ser.series_id} ({ser.source}, {ser.transform}, {ser.dp} dp)',
            'as_of': as_of, 'checked': checked, 'wrong': wrong, 'unmatched': unmatched,
            'cited': ser.series_id in t}


def main(argv: list[str] | None = None) -> int | str:
    """Audit the named indicator reports, or all of them; 1 when any point is wrong or unmatched, a series id is not
    cited on its page, or a report could not be audited."""
    ap = rd.parser('Audit economic-indicator charts against the official series (FRED, Bank of Canada Valet).')
    ap.add_argument('slugs', nargs='*', help='indicators/<slug> or <slug> (default: every indicator report)')
    args = ap.parse_args(argv)
    slugs = args.slugs or [rd.slug_of(p) for p in rd.family_reports(FAMILY, args.repo)]
    bad = 0
    for s in slugs:
        r = audit(s, args.repo)
        if failed(r):
            bad += 1
            print(f"ERROR {r['slug']}: {r['err']}")
        elif succeeded(r):
            bad += not passes(r)
            print(result_line(r))
    print(f'reports {len(slugs)} | failing {bad}')
    return 1 if bad else 0


def failed(row: AuditResult | AuditFailure) -> TypeGuard[AuditFailure]:
    return 'err' in row


def succeeded(row: AuditResult | AuditFailure) -> TypeGuard[AuditResult]:
    return 'err' not in row


def passes(r: AuditResult) -> bool:
    """The gate: every point matched and within tolerance, and the page cites its series id."""
    return not r['wrong'] and not r['unmatched'] and r['cited']


def result_line(r: AuditResult) -> str:
    """The audit's lines for one report: the verdict, then any wrong points and unmatched labels."""
    out = [f"{'ok  ' if passes(r) else 'FAIL'} {r['slug']}: {r['checked']} points vs {r['series']} | wrong "
           f"{len(r['wrong'])} | unmatched {len(r['unmatched'])} | series cited {r['cited']} | as-of {r['as_of']}"]
    out += [f'     wrong {lab}: page {page} vs official {want}' for lab, page, want in r['wrong'][:24]]
    if r['unmatched']:
        out.append(f"     unmatched labels: {r['unmatched'][:12]}")
    return '\n'.join(out)


if __name__ == '__main__':
    sys.exit(main())
