"""The scripted number layer of an earnings refresh (design: tasks/refresh-data-design.md). For one stock report it
fetches the settled close and everything that follows from it, writes the page's structured fields, and lists the
prose that still carries the old numbers. Prose, analyst consensus and anything from SEC filings stay with the agents.

usage:  py -3 tools/refresh_data.py <slug> [--as-of YYYY-MM-DD|auto] [--out DIR] [--write]
                                          [--window N] [--fix-points]                          the pre-pass
        py -3 tools/refresh_data.py <slug> --post [--check] [--out DIR]                       the post-pass

Pre-pass. As-of = the latest settled close (auto: the latest session whose date's 20:00 New York time has passed,
so never a session still trading). From Yahoo daily bars (split-adjusted, not dividend-adjusted, ~6 years, with the
dividend and split events) and SPY/QQQ: header price and change on the prior close; the chart (the page's points
kept, its last point, the previous as-of, replaced by that month's month-end close once the month is over, the
missing month-ends appended, the as-of close last, all on the page's share basis); the intraday 52-week range with
its dates; 1-year, 5-year and chart-window price returns for the stock, SPY and QQQ; RSI(14) and the 50/200-day
moving averages of daily closes; dividends (TTM, last, frequency, annualised) and the yield on the page's own basis;
trailing P/E = close / the page's EPS (TTM) cell. From Nasdaq: short interest with its settlement date (Nasdaq-listed
stocks only) and the last quarters' EPS against Nasdaq's consensus. Every value goes to <out>/facts.json with its
source URL, fetch time, as-of and basis; <out>/stale_hits.txt lists every line of the page that still shows the old
price, an old chart value, the old 52-week range, P/E or yield, or the old as-of date. --write puts the structured
fields into the page in one batch (tools/reportpatch.py; header price, banner date and chart move together or not
at all) and never touches prose.

Chart window (Oki, 2 Oct 2026): after the new month-ends are appended the oldest points are dropped so the chart keeps
at most --window points (default 61: five years of month-ends plus the as-of point; 0 = no trim); the events move
with it (indices shifted, events that fall off the front dropped and listed). facts.json carries the new window
return with its start month and value (return_chart) and the previous edition's (previous_window); stale_hits lists
the dropped start value and the old window return where the prose shows it. A page whose script uses a chart index
outside the events (FISV) is not trimmed. --fix-points: every kept existing point is compared with Yahoo's month-end
on the page's basis and replaced when more than half a cent off (rule A; fix_points says what is skipped and why);
the replacements are facts.json fixed_points and their old values are stale hits.

Post-pass (after the builder). Re-reads the page against facts.json: as-of, header price, the script's chart points
and the 52-week range must still match (exit 1 if not); the last chart point is re-synced to the header; P/E is
recomputed from the page's final EPS cell, and the yield from a "$X ÷ $price" dividend formula when the page has one;
the delta box's data attributes must name both editions. stale_hits.txt is written again. --check changes nothing
and fails on anything it would have fixed (the publish gate).

No SEC access and no personal data in any request (the Yahoo and Nasdaq calls carry a plain browser User-Agent).
"""
import datetime
import json
import os
import re
import sys
import tempfile
import urllib.error
from http.client import HTTPException
from typing import Any, Callable, NamedTuple

import chart_audit as ca
import refresh_queue as rq
import reportlib as rl
import reportpatch as rp
import repodata as rd
from verify import plain_value

YAHOO_DAILY = ('https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d'
               '&events=div%7Csplit')
NASDAQ_SHORT = 'https://api.nasdaq.com/api/quote/{sym}/short-interest?assetClass=stocks'
NASDAQ_SURPRISE = 'https://api.nasdaq.com/api/company/{sym}/earnings-surprise'
BENCHMARKS = ('SPY', 'QQQ')
DAILY_YEARS = 6            # five-year returns and the chart's first month-end, with room to spare
SETTLED_HOUR = 20          # a session's close counts as settled from 20:00 New York time (after the post-market)
RSI_PERIOD, MA_SHORT, MA_LONG = 14, 50, 200
PE_LABEL = r'Trailing P/?E\b'           # verify.pe_pair's labels
EPS_LABEL = r'(?:Diluted )?EPS \(TTM\b'
YIELD_LABEL = r'Dividend Yield'
OUT_ROOT = os.path.join(tempfile.gettempdir(), 'ttg_refresh_data')
CORE = ('header_price', 'banner_date', 'chart')   # written together or not at all (the chart with its events)
WINDOW = 61   # chart points kept: five years of month-ends plus the as-of point (--window; Oki, 2 Oct 2026)
NET_ERRORS = (urllib.error.URLError, HTTPException, TimeoutError, OSError, ValueError)
BASIS_PRICE = 'Yahoo daily close: split-adjusted, not dividend-adjusted (the page basis)'


class Day(NamedTuple):
    date: str     # YYYY-MM-DD, New York
    high: float
    low: float
    close: float
    adj: float | None = None   # Yahoo adjclose: split- and dividend-adjusted


class Daily(NamedTuple):
    """One symbol's daily bars and events, oldest first."""
    days: list[Day]
    dividends: list[tuple[str, float]]   # (ex-date, amount)
    splits: ca.Splits
    gmtoffset: int                       # seconds, New York's offset when fetched
    url: str
    fetched_at: str


class ChartError(Exception):
    """The page's chart cannot be extended mechanically (labels not monthly, chart past the as-of, no close)."""


Json = dict[str, Any]


# ---------- fetching (cached per symbol per day) ----------

def _cache(name: str) -> str:
    return os.path.join(ca.cache_dir(), name)


def _stamp(path: str) -> str:
    return datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.UTC).isoformat(timespec='seconds')


def parse_daily(body: Json, url: str = '', fetched_at: str = '') -> Daily:
    """A Yahoo v8 daily chart response -> Daily. Bars without a high, low or close are left out; one bar per date."""
    try:
        r = ((body.get('chart') or {}).get('result') or [None])[0]
        if not r:
            raise ca.YahooError('no result')
        offset = int(r['meta'].get('gmtoffset') or 0)
        q = r['indicators']['quote'][0]
        stamps = r.get('timestamp') or []
        adj = ((r['indicators'].get('adjclose') or [{}])[0].get('adjclose')) or [None] * len(stamps)
        by_date: dict[str, Day] = {}
        for ts, h, lo, c, a in zip(stamps, q.get('high') or [], q.get('low') or [], q.get('close') or [], adj):
            if h is None or lo is None or c is None:
                continue
            d = datetime.datetime.fromtimestamp(ts + offset, datetime.UTC).date().isoformat()
            by_date[d] = Day(d, float(h), float(lo), float(c), float(a) if a is not None else None)
        divs = sorted((datetime.datetime.fromtimestamp(int(k) + offset, datetime.UTC).date().isoformat(),
                       float(v['amount'])) for k, v in ((r.get('events') or {}).get('dividends') or {}).items())
        return Daily([by_date[k] for k in sorted(by_date)], divs, ca.split_events(r), offset, url, fetched_at)
    except (KeyError, IndexError, TypeError, AttributeError, ValueError, ZeroDivisionError) as e:
        raise ca.YahooError(f'unreadable daily series ({type(e).__name__})') from e


def daily_series(sym: str, today: datetime.date, now_ts: int) -> Daily:
    """Yahoo daily bars from DAILY_YEARS before today to now, fetched once per symbol per day."""
    path = _cache(f'{sym}.d1.{today.isoformat()}.json')
    if not os.path.exists(path):
        p1 = int(datetime.datetime(today.year - DAILY_YEARS, today.month, 1, tzinfo=datetime.UTC).timestamp())
        url = YAHOO_DAILY.format(sym=sym, p1=p1, p2=now_ts)
        ca.fetch_url(url, path)
        rl.write_text(path + '.url', url)
    with open(path, encoding='utf-8') as fh:
        body = json.load(fh)
    url = rl.read_text(path + '.url') if os.path.exists(path + '.url') else ''
    return parse_daily(body, url, _stamp(path))


def nasdaq(kind: str, url: str, sym: str, today: datetime.date) -> tuple[Json, str]:
    """A Nasdaq API response, fetched once per symbol per day: (body, fetched-at)."""
    path = _cache(f'{sym}.{kind}.{today.isoformat()}.json')
    if not os.path.exists(path):
        body = rq.get_json(url, rq.NASDAQ_HEADERS)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(body, fh)
    with open(path, encoding='utf-8') as fh:
        return json.load(fh), _stamp(path)


# ---------- parsing the Nasdaq responses ----------

def _us_date(s: str) -> str | None:
    """'09/15/2026' or '9/29/2026' -> '2026-09-15'."""
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})$', (s or '').strip())
    return f'{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}' if m else None


def parse_short_interest(body: Json, as_of: str) -> Json:
    """The latest short-interest row settled on or before the as-of: settlement date, shares short, average daily
    volume, days to cover. {'value': None, 'note': …} when Nasdaq has none (it covers Nasdaq-listed stocks only)."""
    rows = (((body.get('data') or {}).get('shortInterestTable') or {}).get('rows')) or []
    good = sorted(((_us_date(r.get('settlementDate', '')), r) for r in rows), key=lambda x: x[0] or '')
    good = [(d, r) for d, r in good if d and d <= as_of]
    if not good:
        return {'value': None, 'note': body.get('message') or 'no short-interest row settled by the as-of'}
    d, r = good[-1]
    return {'value': rq.num(str(r.get('interest'))), 'settlement_date': d,
            'avg_daily_volume': rq.num(str(r.get('avgDailyShareVolume'))),
            'days_to_cover': round(float(r['daysToCover']), 2) if r.get('daysToCover') not in (None, '') else None}


def parse_surprises(body: Json, as_of: str) -> list[Json]:
    """Each reported quarter (newest first, reported on or before the as-of): EPS against Nasdaq's consensus."""
    rows = (((body.get('data') or {}).get('earningsSurpriseTable') or {}).get('rows')) or []
    out = []
    for r in rows:
        d = _us_date(r.get('dateReported', ''))
        if not d or d > as_of:
            continue
        out.append({'fiscal_quarter_end': r.get('fiscalQtrEnd'), 'reported': d, 'eps': rq.num(str(r.get('eps'))),
                    'consensus': rq.num(str(r.get('consensusForecast'))),
                    'surprise_pct': rq.num(str(r.get('percentageSurprise')))})
    return sorted(out, key=lambda x: x['reported'], reverse=True)


# ---------- computations on daily bars ----------

def years_before(iso: str, years: int = 1) -> str:
    """The same calendar date `years` earlier (29 Feb -> 28 Feb)."""
    d = datetime.date.fromisoformat(iso)
    try:
        return d.replace(year=d.year - years).isoformat()
    except ValueError:
        return d.replace(year=d.year - years, day=28).isoformat()


def settled_as_of(days: list[Day], now: datetime.datetime, gmtoffset: int) -> str:
    """The latest session whose close has settled at `now`: 20:00 New York time on its date has passed."""
    local = (now.astimezone(datetime.UTC) + datetime.timedelta(seconds=gmtoffset)).replace(tzinfo=None)
    for d in reversed(days):
        if local >= datetime.datetime.fromisoformat(d.date) + datetime.timedelta(hours=SETTLED_HOUR):
            return d.date
    raise ValueError('no settled session in the series')


def on_or_before(days: list[Day], iso: str) -> Day | None:
    """The last bar dated on or before iso."""
    best = None
    for d in days:
        if d.date > iso:
            break
        best = d
    return best


def month_end(days: list[Day], year: int, month: int) -> Day | None:
    """The last bar of a calendar month."""
    key = f'{year:04d}-{month:02d}'
    inside = [d for d in days if d.date[:7] == key]
    return inside[-1] if inside else None


def range_52w(days: list[Day], as_of: str, factor: float = 1.0) -> Json:
    """Intraday low and high over (as-of minus one year, as-of], with their dates (the first day on a tie)."""
    start = years_before(as_of)
    window = [d for d in days if start < d.date <= as_of]
    if not window:
        raise ValueError('no bars in the 52-week window')
    lo = min(window, key=lambda d: d.low)
    hi = max(window, key=lambda d: d.high)
    return {'low': round(lo.low * factor, 2), 'low_date': lo.date, 'high': round(hi.high * factor, 2),
            'high_date': hi.date, 'window': [window[0].date, as_of]}


def price_return(days: list[Day], as_of: str, base_iso: str) -> Json | None:
    """Close-to-close price return from the last close on or before base_iso to the as-of close."""
    base, end = on_or_before(days, base_iso), on_or_before(days, as_of)
    if not base or not end or end.date != as_of or base.date > base_iso:
        return None
    return {'base_date': base.date, 'base_close': round(base.close, 2), 'close': round(end.close, 2),
            'pct': round((end.close / base.close - 1) * 100, 2)}


def rsi(closes: list[float], period: int = RSI_PERIOD) -> float | None:
    """Wilder's RSI at the last close: the first average a simple mean of `period` changes, then smoothed (the same
    method as the pages' computeRSI)."""
    if len(closes) <= period:
        return None
    gain = loss = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gain, loss = gain + max(d, 0), loss + max(-d, 0)
    gain, loss = gain / period, loss / period
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        gain = (gain * (period - 1) + max(d, 0)) / period
        loss = (loss * (period - 1) + max(-d, 0)) / period
    return 100.0 if loss == 0 else round(100 - 100 / (1 + gain / loss), 2)


def sma(closes: list[float], n: int) -> float | None:
    """Simple moving average of the last n closes."""
    return round(sum(closes[-n:]) / n, 2) if len(closes) >= n else None


def dividend_frequency(divs: list[tuple[str, float]]) -> int | None:
    """Payments a year, from the gap between the last two ex-dates: monthly, quarterly, half-yearly or annual."""
    if len(divs) < 2:
        return None
    gap = (datetime.date.fromisoformat(divs[-1][0]) - datetime.date.fromisoformat(divs[-2][0])).days
    return 12 if gap <= 45 else 4 if gap <= 135 else 2 if gap <= 270 else 1


def dividend_facts(divs: list[tuple[str, float]], as_of: str, close: float, factor: float = 1.0) -> Json:
    """Dividends with an ex-date on or before the as-of: the TTM sum, the last payment, its frequency and the
    annualised rate (last × frequency; none when nothing went ex in the last year), and both yields on the close."""
    past = [(d, a * factor) for d, a in divs if d <= as_of]
    start = years_before(as_of)
    ttm_events = [(d, round(a, 4)) for d, a in past if d > start]
    ttm = round(sum(a for _, a in ttm_events), 4)
    freq = dividend_frequency(past)
    last = past[-1] if past else None
    forward = round(last[1] * freq, 4) if last and freq and ttm_events else None
    return {'ttm': ttm, 'ttm_events': ttm_events, 'last': [last[0], round(last[1], 4)] if last else None,
            'frequency': freq, 'annualised': forward,
            'yield_ttm_pct': round(ttm / close * 100, 4) if close else None,
            'yield_annualised_pct': round(forward / close * 100, 4) if forward and close else None}


def yield_basis(cell_value: float, decimals: int, price: float, div: Json) -> str | None:
    """Which dividend the page's yield cell divides by: 'ttm' or 'annualised', when exactly one of them reproduces
    the cell at its precision on the page's price (both, when they are equal, give 'ttm'); else None."""
    tol = 0.5 * 10 ** -decimals + 1e-9
    hits = [b for b, amt in (('ttm', div['ttm']), ('annualised', div['annualised']))
            if amt and abs(amt / price * 100 - cell_value) <= tol]
    if len(hits) == 2 and abs((div['ttm'] or 0) - (div['annualised'] or 0)) > 1e-9:
        return None
    return hits[0] if hits else None


_FORMULA = re.compile(r'\$(\d+(?:\.\d+)?)[^÷$]{0,40}÷\s*\$([\d,]+\.\d+)')


def yield_formula(context: str) -> tuple[float, float] | None:
    """(dividend, price) from a yield context cell that shows its sum: '$0.60 annualised ÷ $25.07'."""
    m = _FORMULA.search(context)
    return (float(m.group(1)), float(m.group(2).replace(',', ''))) if m else None


# ---------- the chart ----------

def extend_series(labels: list[str], prices: list[float], old_as_of: str, as_of: str, days: list[Day],
                  factor: float, splits: ca.Splits) -> Json:
    """The page's chart carried to the as-of: existing points kept (rescaled when a real split went ex between the
    two as-of dates); the last point, the previous as-of, becomes its month's month-end close once that month is
    over (or gives way to the as-of point in the same month); the missing month-ends follow; the as-of close is last.
    Labels follow the page's own styles: its month labels, and its last label's style for the as-of point."""
    pts = [rp.point_label(lab) for lab in labels]
    bad = [lab for lab, p in zip(labels, pts) if p is None]
    if bad or len(labels) < 2:
        raise ChartError(f'labels not read as months: {bad[:3]}' if bad else 'fewer than two chart points')
    yms = [(p.year, p.month) for p in pts if p]
    for a, b in zip(yms, yms[1:]):
        if b[0] * 12 + b[1] - (a[0] * 12 + a[1]) != 1:
            raise ChartError(f'labels are not consecutive months ({a} then {b})')
    last, before = pts[-1], pts[-2]
    assert last and before
    if before.style.kind != 'month':
        raise ChartError(f'the second-last label {labels[-2]!r} is not a month label')
    ay, am = int(as_of[:4]), int(as_of[5:7])
    if (last.year, last.month) > (ay, am):
        raise ChartError(f'the chart runs past the as-of ({labels[-1]!r})')
    real = [(d, r) for d, r in splits if old_as_of < d <= as_of and not (ca.SPIN_RATIO_LO < r < ca.SPIN_RATIO_HI)]
    rescale = 1.0
    for _, r in real:
        rescale *= r
    kept = [round(p / rescale, 2) for p in prices] if rescale != 1.0 else list(prices)
    out_l, out_p = list(labels[:-1]), kept[:-1]
    replaced: list[Json] = []
    appended: list[Json] = []
    y, m = last.year, last.month
    if (y, m) < (ay, am):
        me = month_end(days, y, m)
        if not me:
            raise ChartError(f'no Yahoo close for {y}-{m:02d}')
        lab = rp.format_label(before.style, y, m)
        out_l.append(lab)
        out_p.append(round(me.close * factor, 2))
        replaced.append({'old_label': labels[-1], 'old_value': prices[-1], 'label': lab, 'value': out_p[-1],
                         'date': me.date, 'kind': 'month-end'})
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        while (y, m) < (ay, am):
            me = month_end(days, y, m)
            if not me:
                raise ChartError(f'no Yahoo close for {y}-{m:02d}')
            lab = rp.format_label(before.style, y, m)
            out_l.append(lab)
            out_p.append(round(me.close * factor, 2))
            appended.append({'label': lab, 'value': out_p[-1], 'date': me.date, 'kind': 'month-end'})
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    end = on_or_before(days, as_of)
    if not end or end.date != as_of:
        raise ChartError(f'no Yahoo close on {as_of}')
    lab = rp.format_label(last.style, ay, am, int(as_of[8:]))
    out_l.append(lab)
    out_p.append(round(end.close * factor, 2))
    point = {'label': lab, 'value': out_p[-1], 'date': as_of, 'kind': 'as-of close'}
    if (last.year, last.month) == (ay, am):
        replaced.append({'old_label': labels[-1], 'old_value': prices[-1], **point})
    else:
        appended.append(point)
    return {'labels': out_l, 'prices': out_p, 'replaced': replaced, 'appended': appended,
            'split_rescale': {'ratio': rescale, 'splits': real} if rescale != 1.0 else None}


def window_drop(n_points: int, window: int) -> int:
    """How many of the oldest points to drop so the chart has at most `window` points (0 = no trim). The default 61
    is five years of month-ends plus the as-of point (CLAUDE.md: about 60 monthly closes, a 5-year monthly series)."""
    return max(0, n_points - window) if window else 0


CENT = 0.005    # rule A: a chart point is the source value to the cent; more than half a cent off is wrong


def fix_points(labels: list[str], prices: list[float], idxs: list[int], days: list[Day], factor: float,
               splits: ca.Splits, as_of: str, labelled: bool, source: str) -> Json:
    """Existing chart points (positions idxs) checked against Yahoo's month-end on the page's own basis and replaced,
    in prices, when more than half a cent off. Returns the basis, the fixed points (month, date, old, new, source)
    and the points left alone and why.

    Basis: Yahoo's close (split-adjusted, the page basis), or its adjclose when chart_audit's test classes the series
    as dividend-adjusted (at least ADJ_UNLABELLED_MIN points match the adjusted close and not the close) AND the page
    labels it so (chart_audit.ADJ_LABEL) AND more points sit nearer the adjusted close than the close. A series nearer
    the adjusted close that is not labelled is put on the close (rule A: dividends not adjusted unless labelled).
    Left alone: labels that are not a month; months Yahoo does not have; every point when a split went ex after the
    as-of (Yahoo's basis is then not the page's); basis steps — a point chart_audit classes 'basis step', or, in a
    month before a spin-off booked as a fractional split, a point nearer the real pre-spin close than Yahoo's
    spin-adjusted one (both are allowed bases; a small spin is inside chart_audit's 3%)."""
    ym_as_of = (int(as_of[:4]), int(as_of[5:7]))
    skipped: dict[str, list[str]] = {}

    def skip(why: str, lab: str) -> None:
        skipped.setdefault(why, []).append(lab)

    cand: list[tuple[int, Day, float]] = []
    for i in idxs:
        p = rp.point_label(labels[i])
        if not p or p.style.kind != 'month':
            skip('not a month label', labels[i])
            continue
        if (p.year, p.month) >= ym_as_of:
            skip('the as-of month', labels[i])
            continue
        me = month_end(days, p.year, p.month)
        if not me:
            skip('no Yahoo month', labels[i])
            continue
        if factor != 1.0:
            skip('split after the as-of', labels[i])
            continue
        cand.append((i, me, ca.spin_factor(splits, (p.year, p.month), as_of)))
    adj_pts = sum(ca.classify(prices[i], me.close, me.adj, spin) == 'adjusted' for i, me, spin in cand)
    near_adj = sum(me.adj is not None and abs(prices[i] - me.adj) + CENT < abs(prices[i] - me.close) for i, me, _ in cand)
    near_close = sum(me.adj is not None and abs(prices[i] - me.close) + CENT < abs(prices[i] - me.adj) for i, me, _ in cand)
    adjusted = labelled and adj_pts >= ca.ADJ_UNLABELLED_MIN and near_adj > near_close
    basis = 'adjclose' if adjusted else 'close'
    note = None
    if not adjusted and near_adj >= ca.ADJ_UNLABELLED_MIN and near_adj > near_close:
        note = (f'{near_adj} points sat nearer Yahoo\'s dividend-adjusted close than its close and the series is '
                f"{'not classed dividend-adjusted by chart_audit' if labelled else 'not labelled dividend-adjusted'}: "
                'compared with the close (rule A), so the series is rebased to the close')
    fixed: list[Json] = []
    compared = 0
    for i, me, spin in cand:
        ref = me.adj if adjusted else me.close
        if ref is None:
            skip('no adjclose', labels[i])
            continue
        v = prices[i]
        if ca.classify(v, me.close, me.adj, spin) == 'basis step' or (spin != 1.0 and abs(v - ref * spin) < abs(v - ref)):
            skip('basis step', labels[i])
            continue
        compared += 1
        new = round(ref, 2)
        if abs(v - new) >= CENT:
            fixed.append({'month': labels[i], 'date': me.date, 'old': v, 'new': new, 'source': source,
                          'basis': 'Yahoo adjclose (dividend-adjusted)' if adjusted else 'Yahoo close (split-adjusted)'})
            prices[i] = new
    return {'basis': basis, 'compared': compared, 'fixed': fixed, 'skipped': skipped, 'adjusted_points_3pct': adj_pts, 'nearer_adjclose': near_adj,
            'nearer_close': near_close, 'labelled_adjusted': labelled, 'note': note}


# ---------- reading the page ----------

def header_mcap(t: str) -> tuple[str, float] | None:
    """The header's 'Mkt Cap: ~$33.7B' as (text, dollars)."""
    m = re.search(r'Mkt Cap:(?:\s*</[^>]+>)?\s*(?:<[^>]+>\s*)*([^<]+)', t)
    if not m:
        return None
    n = re.search(r'\$\s*([\d,]+(?:\.\d+)?)\s*(T|B|M|Trillion|Billion)\b', m.group(1))
    if not n:
        return None
    unit = {'T': 1e12, 'Trillion': 1e12, 'B': 1e9, 'Billion': 1e9, 'M': 1e6}[n.group(2)]
    return m.group(1).strip(), float(round(float(n.group(1).replace(',', '')) * unit))


def cell_number(text: str | None) -> tuple[float, int] | None:
    """(value, decimals) of a plain-number cell ('11.04', '24.1x', '2.39%'); None for n/m, None, ranges and prose."""
    if not text or re.search(r'\bn/?[ma]\b|none', text, re.I):
        return None
    m = re.match(r'^\s*\$?(\d[\d,]*(?:\.(\d+))?)\s*(?:[x×%])?\s*(?:$|\()', text)
    return (float(m.group(1).replace(',', '')), len(m.group(2) or '')) if m else None


def delta_attrs(t: str) -> dict[str, str] | None:
    """The data-* attributes of the "what changed" box (the first .tg-d section), or None without one."""
    m = re.search(r'<section class="tg-d[^"]*"([^>]*)>', t)
    return dict(re.findall(r'data-([\w-]+)="([^"]*)"', m.group(1))) if m else None


# ---------- stale hits ----------

def _num_forms(v: float, decimals: int = 2) -> list[str]:
    return sorted({f'{v:.{decimals}f}', f'{v:,.{decimals}f}'}, key=len, reverse=True)


def stale_patterns(old: Json, new: Json) -> list[tuple[str, re.Pattern[str]]]:
    """What the prose should no longer say: each old value that changed, as (what it was, pattern)."""
    pats: list[tuple[str, re.Pattern[str]]] = []

    def number(kind: str, v: float | None, newv: float | None, decimals: int = 2, suffix: str = '') -> None:
        if v is None or (newv is not None and round(v, decimals) == round(newv, decimals)):
            return
        alts = '|'.join(re.escape(f) for f in _num_forms(v, decimals))
        pats.append((f'{kind} {v:.{decimals}f}{suffix}', re.compile(r'(?<![\d.,])(?:' + alts + r')(?!\d)' + re.escape(suffix))))

    number('old header price', old['price'], new['price'])
    for p in new.get('replaced_points', []):
        number(f"old chart value {p['old_label']}", p['old_value'], p['value'])
    for p in new.get('fixed_points') or []:
        number(f"wrong chart value {p['month']} (fixed to {p['new']:.2f})", p['old'], p['new'])
    if new.get('dropped_first'):
        number(f"old chart start {new['dropped_first'][0]} (dropped from the window)", new['dropped_first'][1], None)
    olo, ohi = old.get('range_52w') or (None, None)
    nlo, nhi = new.get('range_52w') or (None, None)
    number('old 52-week low', olo, nlo)
    number('old 52-week high', ohi, nhi)
    if old.get('pe'):
        number('old P/E', old['pe'][0], new.get('pe'), old['pe'][1])
    if old.get('yield'):
        number('old yield', old['yield'][0], new.get('yield'), old['yield'][1], '%')
    merged: dict[str, tuple[str, re.Pattern[str]]] = {}   # one line per place: the old price is often an old chart value
    for kind, pat in pats:
        prev = merged.get(pat.pattern)
        merged[pat.pattern] = (f'{prev[0]} = {kind}' if prev else kind, pat)
    pats = list(merged.values())
    for form in new.get('old_window_forms') or []:
        pats.append((f'old chart-window return {form}%', re.compile(r'(?<![\d.,])' + re.escape(form) + '%')))
    if old.get('as_of') and old['as_of'] != new.get('as_of'):
        d = datetime.date.fromisoformat(old['as_of'])
        names = [rp.FULL_MONTHS[d.month - 1], rp.MON3[d.month - 1] + r'\.?'] + (['Sept\\.?'] if d.month == 9 else [])
        pats.append((f"old as-of date {old['as_of']}", re.compile(
            r'\b(?:' + '|'.join(names) + r')\s+' + str(d.day) + r'\b(?!,?\s*(?!' + str(d.year) + r')\d{4})', re.I)))
    return pats


def _mask(t: str) -> str:
    """The page with what the builder must not chase blanked out (newlines kept, so line numbers hold): the style
    sheet, the delta box (it names the previous edition on purpose) and the chart arrays."""
    spans = [m.span() for m in re.finditer(r'<style[\s>].*?</style>', t, re.S)]
    spans += [m.span() for m in re.finditer(r'<section class="tg-d.*?</section>', t, re.S)]
    spans += [m.span(2) for m in (rp.LABELS_ARRAY.search(t), rp.PRICES_ARRAY.search(t)) if m]
    out = list(t)
    for a, b in spans:
        for i in range(a, b):
            if out[i] != '\n':
                out[i] = ' '
    return ''.join(out)


_WINDOW_WORDS = r'five[- ]year|5[- ]year|5-yr|\b5y\b|five years|over the (?:chart|window)'


def window_return_forms(t: str, pct: float, first_label: str) -> list[str]:
    """How the previous edition's chart-window return (its first point -> its as-of price) is written in the prose,
    if it is: '34.5' and/or '35' (no sign; the % follows), each kept only where a line of the prose shows it beside
    five-year wording or the window's first month ('since Sep 2021')."""
    p = rp.point_label(first_label)
    since = ''
    if p:
        names = [rp.FULL_MONTHS[p.month - 1], rp.MON3[p.month - 1] + r'\.?'] + (['Sept\\.?'] if p.month == 9 else [])
        since = r'|\b(?:' + '|'.join(names) + r")\s+(?:'?" + f'{p.year % 100:02d}|{p.year})' + r'\b'
    ctx = re.compile(_WINDOW_WORDS + since, re.I)
    forms = []
    for form in dict.fromkeys((f'{abs(pct):.1f}', f'{abs(pct):.0f}')):
        num = re.compile(r'(?<![\d.,])' + re.escape(form) + '%')
        if any(num.search(line) and ctx.search(line) for line in _mask(t).split('\n')):
            forms.append(form)
    return forms


def stale_hits(t: str, pats: list[tuple[str, re.Pattern[str]]]) -> list[str]:
    """'L<line>: <what> | <text around it>' for every match, in page order."""
    masked = _mask(t)
    lines, raw = masked.split('\n'), t.split('\n')
    hits = []
    for no, line in enumerate(lines, 1):
        for kind, pat in pats:
            for m in pat.finditer(line):
                a, b = max(0, m.start() - 160), m.end() + 160
                cut = re.sub(r'^[^<]*>', '', raw[no - 1][a:b])          # drop a tag cut in half at the start
                ctx = re.sub(r'\s+', ' ', rl.strip_tags(re.sub(r'<[^>]*>', ' ', cut)))
                hits.append(f'L{no}: {kind} | …{ctx[:240]}…')
    return hits


# ---------- the pre-pass ----------

def field(value: Any, source: str, fetched_at: str, as_of: str, basis: str, **extra: Any) -> Json:
    return {'value': value, 'source': source, 'fetched_at': fetched_at, 'as_of': as_of, 'basis': basis, **extra}


def page_values(t: str) -> Json:
    """The structured values a page shows now (the previous edition's, before a pre-pass)."""
    pe, yl = rp.fin_row_texts(t, PE_LABEL), rp.fin_row_texts(t, YIELD_LABEL)
    return {'as_of': rl.as_of(t)[0], 'price': rl.header_price(t), 'range_52w': rl.range_52w(t),
            'pe': cell_number(pe[1]) if pe else None, 'yield': cell_number(yl[1]) if yl else None,
            'mcap': header_mcap(t)}


def build(slug: str, t: str, daily: Daily, as_of: str, bench: dict[str, Daily | str],
          short: tuple[Json, str] | str, surprise: tuple[Json, str] | str,
          monthly: tuple[ca.Monthly, ca.Splits] | str, window: int = 0, fix: bool = False) -> tuple[Json, str]:
    """facts.json for one page and the page with its structured fields written (not saved). Pure: every fetch is
    an argument (a string where it failed), so the golden check and the tests run it on saved responses.
    window: the chart keeps at most this many points (0 = no trim; the command line's default is WINDOW); fix:
    replace existing chart points that are off Yahoo's month-end (fix_points)."""
    ticker = rl.parse_title(t)[0] or slug.upper()
    old = page_values(t)
    if not old['as_of'] or old['price'] is None:
        raise ChartError('the page has no readable as-of date or header price')
    if as_of < old['as_of']:
        raise ChartError(f"as-of {as_of} is before the page's own {old['as_of']}")
    factor = ca.splits_after(daily.splits, as_of)
    days = [d for d in daily.days if d.date <= as_of]
    end = days[-1] if days else None
    if not end or end.date != as_of:
        raise ChartError(f'Yahoo has no close on {as_of} (not a session?)')
    src, at = daily.url, daily.fetched_at
    close = round(end.close * factor, 2)
    prior = days[-2]
    prior_close = round(prior.close * factor, 2)
    labels, prices = rl.chart_series(t)
    if not labels or not prices or len(labels) != len(prices):
        raise ChartError('the page has no chart arrays of equal length')
    chart = extend_series(labels, prices, old['as_of'], as_of, days, factor, daily.splits)
    f: Json = {}
    warnings: list[str] = []
    page = f'reports/{slug}_analysis.html'
    n_exist = len(labels) - 1          # the page's points the new series keeps (its last point is replaced)
    drop = window_drop(len(chart['labels']), window)
    if drop > n_exist:
        raise ChartError(f'a {window}-point window would drop points this run adds')
    trim: Json = {'window': window, 'dropped': 0, 'dropped_points': [], 'events_kept': None, 'events_dropped': []}
    if drop:
        try:
            _, kept_events, gone = rp.shift_events(t, drop, page)
            trim.update(dropped=drop, events_kept=kept_events, events_dropped=gone,
                        dropped_points=[{'label': lab, 'value': v} for lab, v in zip(labels[:drop], prices[:drop])])
        except rp.PatchError as e:
            warnings.append(f'chart not trimmed to {window} points (the events cannot move with it): {e}')
            drop = 0
    fixinfo: Json | None = None
    if fix:
        fixinfo = fix_points(chart['labels'], chart['prices'], list(range(drop, n_exist)), days, factor, daily.splits,
                             as_of, bool(ca.ADJ_LABEL.search(t)), src)
        if fixinfo['basis'] == 'adjclose':   # the new month-ends on the series' own basis
            pos = {lab: i for i, lab in enumerate(chart['labels'])}
            for pt in chart['replaced'] + chart['appended']:
                d = on_or_before(days, pt['date'])
                if pt['kind'] == 'month-end' and d and d.adj is not None:
                    pt['value'] = chart['prices'][pos[pt['label']]] = round(d.adj * factor, 2)
                    pt['basis'] = 'Yahoo adjclose (the series is labelled dividend-adjusted)'
        if fixinfo['note']:
            warnings.append(fixinfo['note'])
    chart['labels'], chart['prices'] = chart['labels'][drop:], chart['prices'][drop:]
    f['close'] = field(close, src, at, as_of, BASIS_PRICE, date=as_of,
                       note=f'scaled by {factor} for splits after the as-of' if factor != 1 else None)
    f['prior_close'] = field(prior_close, src, at, as_of, BASIS_PRICE, date=prior.date)
    chg = round(close - prior_close, 2)
    f['change'] = field(chg, src, at, as_of, 'as-of close minus the prior close', pct=round(chg / prior_close * 100, 2))
    if isinstance(monthly, str):
        check: Json = {'error': monthly}
    else:
        pc = ca.check_points(chart['labels'], chart['prices'], monthly[0], monthly[1], as_of)
        check = {'checked': pc['checked'], 'wrong': pc['bad'], 'dividend_adjusted_points': pc['adj_pts'],
                 'basis_steps': pc['step_pts'], 'source': ca.YAHOO_CHART.format(sym=ca.yahoo_symbol(slug, ticker))}
        if pc['bad']:
            warnings.append(f"{len(pc['bad'])} existing chart points are >3% off Yahoo's month-end close: "
                            + ', '.join(f'{b[0]} {b[1]} (Yahoo {b[2]})' for b in pc['bad'][:8]))
    f['chart'] = field({'labels': chart['labels'], 'prices': chart['prices']}, src, at, as_of,
                       BASIS_PRICE + '; month-end = the last session of the month',
                       replaced=chart['replaced'], appended=chart['appended'], split_rescale=chart['split_rescale'],
                       existing_points_check=check, trim=trim, fix_points=fixinfo)
    if chart['split_rescale']:
        warnings.append(f"split between the editions: existing chart points divided by {chart['split_rescale']['ratio']}"
                        ' — say so on the page')
    spins = [(d, r) for d, r in daily.splits if old['as_of'] < d <= as_of and ca.SPIN_RATIO_LO < r < ca.SPIN_RATIO_HI]
    if spins:
        warnings.append(f'Yahoo books a spin-off or capital return as a fractional split {spins}: older chart points '
                        'may be on the pre-spin basis — label the series')
    w = range_52w(days, as_of, factor)
    f['range_52w'] = field([w['low'], w['high']], src, at, as_of,
                           'intraday low and high over (as-of minus one year, as-of], Yahoo daily bars', **w)
    closes = [d.close * factor for d in days]
    r = rsi(closes)
    f['rsi14_daily'] = field(r, src, at, as_of, "Wilder RSI(14) of daily closes (the page's chart RSI is monthly)")
    for n in (MA_SHORT, MA_LONG):
        ma = sma(closes, n)
        f[f'ma{n}'] = field(ma, src, at, as_of, f'simple average of the last {n} daily closes',
                            close_vs_ma_pct=round((close / ma - 1) * 100, 2) if ma else None)
    first = rp.point_label(chart['labels'][0])
    windows = {'1y': years_before(as_of, 1), '5y': years_before(as_of, 5)}
    if first:
        me = month_end(daily.days, first.year, first.month)
        if me:
            windows['chart'] = me.date
    for key, base in windows.items():
        row: Json = {}
        for sym, series in [(ticker, daily), *bench.items()]:
            if isinstance(series, str):
                row[sym] = {'error': series}
                continue
            pr = price_return(series.days, as_of, base)
            row[sym] = pr if pr else {'error': f'no close on {as_of} or before {base}'}
        basis = {'1y': 'price return, last close on or before the same date a year earlier -> as-of close',
                 '5y': 'price return, last close on or before the same date five years earlier -> as-of close',
                 'chart': "price return from the chart's first month-end close -> as-of close"}[key]
        f[f'return_{key}'] = field(row, src, at, as_of, basis + '; dividends excluded, same dates for SPY and QQQ',
                                   bench_sources={s: (b if isinstance(b, str) else b.url) for s, b in bench.items()})
    if 'return_chart' in f:   # the window the chart now shows: its first point -> the as-of close
        f['return_chart'].update(start_label=chart['labels'][0], start_value=chart['prices'][0],
                                 start_date=windows['chart'], points=len(chart['labels']),
                                 pct_on_chart=round((close / chart['prices'][0] - 1) * 100, 2))
    prev_pct = round((old['price'] / prices[0] - 1) * 100, 2) if prices[0] else None
    prev_window = {'start_label': labels[0], 'start_value': prices[0], 'as_of': old['as_of'], 'price': old['price'],
                   'pct': prev_pct, 'points': len(labels),
                   'prose_forms': window_return_forms(t, prev_pct, labels[0]) if prev_pct is not None else []}
    div = dividend_facts(daily.dividends, as_of, close, factor)
    f['dividends'] = field(div, src, at, as_of, 'Yahoo dividend events by ex-date; TTM = ex-dates in (as-of minus '
                           'one year, as-of]; annualised = last payment x payments a year')
    written: list[str] = []
    not_written: dict[str, str] = {}
    new = t
    try:
        new = rp.set_header_price(new, close, page)
        new, copies = rp.set_banner_date(new, old['as_of'], as_of, page)
        new = rp.set_chart_series(new, chart['labels'], chart['prices'], page, drop=drop)
        new = rp.shift_events(new, drop, page)[0]
        written += ['header_price', 'banner_date', 'chart']
        f['banner_copies'] = copies
    except rp.PatchError as e:
        new = t
        for k in CORE:
            not_written[k] = str(e)
    if written:
        optional: list[tuple[str, Callable[[str], str]]] = [
            ('change', lambda s: rp.set_header_change(s, chg, chg / prior_close * 100, page, (old['as_of'], as_of))),
            ('range_52w', lambda s: rp.set_range_52w(s, w['low'], w['high'], page)),
        ]
        for name, fn in optional:
            try:
                new = fn(new)
                written.append(name)
            except rp.PatchError as e:
                not_written[name] = str(e)
    # P/E from the page's EPS cell (the builder updates EPS; the post-pass recomputes)
    eps_cells, pe_cells = rp.fin_row_texts(t, EPS_LABEL), rp.fin_row_texts(t, PE_LABEL)
    eps = plain_value(eps_cells[1]) if eps_cells else None
    pe_now = cell_number(pe_cells[1]) if pe_cells else None
    pe_val = round(close / eps, 4) if eps and eps > 0 else None
    f['trailing_pe'] = field(round(pe_val, pe_now[1]) if pe_val and pe_now else pe_val, 'the page', at, as_of,
                             "as-of close / the page's EPS (TTM) cell (the previous edition's until the builder "
                             'updates it; the post-pass recomputes)', eps_cell=eps_cells[1] if eps_cells else None)
    if written and pe_val and pe_now:
        try:
            new = rp.set_fin_number(new, PE_LABEL, pe_val, page)
            written.append('trailing_pe')
        except rp.PatchError as e:
            not_written['trailing_pe'] = str(e)
    elif written:
        not_written['trailing_pe'] = 'EPS not positive or P/E cell not a number (n/m): left to the builder'
    # dividend yield on the page's own basis
    yrow = rp.fin_row_texts(t, YIELD_LABEL)
    ycell = cell_number(yrow[1]) if yrow else None
    formula = yield_formula(yrow[-1]) if yrow else None
    ybasis: str | None = None
    amount: float | None = None
    if formula and abs(formula[1] - old['price']) < rl.PRICE_EXACT:
        ybasis, amount = 'formula', formula[0]
    elif ycell:
        before = dividend_facts(daily.dividends, old['as_of'], old['price'], ca.splits_after(daily.splits, old['as_of']))
        ybasis = yield_basis(ycell[0], ycell[1], old['price'], before)
        amount = div['ttm'] if ybasis == 'ttm' else div['annualised'] if ybasis == 'annualised' else None
    yv = round(amount / close * 100, 4) if amount and close else None
    f['dividend_yield'] = field(round(yv, ycell[1]) if yv is not None and ycell else yv, src, at, as_of,
                                {'formula': "the page's own dividend in its '$X ÷ $price' context, on the as-of close",
                                 'ttm': 'TTM dividends (the basis the previous edition used) / as-of close',
                                 'annualised': 'last dividend x payments a year (the basis the previous edition used) '
                                               '/ as-of close'}.get(ybasis or '', 'basis not determined: left to the builder'),
                                page_basis=ybasis, dividend=amount)
    if written and yv is not None and ycell:
        try:
            new = rp.set_fin_number(new, YIELD_LABEL, yv, page)
            written.append('dividend_yield')
        except rp.PatchError as e:
            not_written['dividend_yield'] = str(e)
    elif written:
        not_written['dividend_yield'] = ('no dividend on the page' if not ycell else
                                         "the page's dividend basis is not TTM or annualised Yahoo: left to the builder")
    if old['mcap'] and old['price']:
        est = old['mcap'][1] * close / old['price']
        f['market_cap_estimate'] = field(round(est), 'the page', at, as_of,
                                         "ESTIMATE: the previous edition's header market cap x (as-of close / its "
                                         'price); holds only if the share count did not change: take shares from '
                                         'the latest filing', previous_text=old['mcap'][0])
    sym = ticker
    if isinstance(short, str):
        f['short_interest'] = field(None, NASDAQ_SHORT.format(sym=sym), '', as_of, 'Nasdaq short interest',
                                    note=short)
    else:
        si = parse_short_interest(short[0], as_of)
        f['short_interest'] = field(si.pop('value'), NASDAQ_SHORT.format(sym=sym), short[1], as_of,
                                    'shares short at the settlement date (FINRA via Nasdaq); always cite the '
                                    'settlement date, never the read date', **si)
    if isinstance(surprise, str):
        f['eps_surprise'] = field(None, NASDAQ_SURPRISE.format(sym=sym), '', as_of, 'Nasdaq consensus', note=surprise)
    else:
        f['eps_surprise'] = field(parse_surprises(surprise[0], as_of), NASDAQ_SURPRISE.format(sym=sym), surprise[1],
                                  as_of, "Nasdaq's EPS and Nasdaq's consensus, on Nasdaq's own adjusted basis: label it "
                                  "'Nasdaq consensus'. It can differ from the company's reported or adjusted EPS (JBL "
                                  'Q4 FY2026: Nasdaq 4.17 vs 3.89; company core EPS $4.40), so the company figure '
                                  'comes from the release')
    newvals = {'as_of': as_of, 'price': close, 'range_52w': [w['low'], w['high']],
               'pe': f['trailing_pe']['value'], 'yield': f['dividend_yield']['value'],
               'replaced_points': chart['replaced'], 'fixed_points': fixinfo['fixed'] if fixinfo else [],
               'dropped_first': [labels[0], prices[0]] if drop else None,
               'old_window_forms': prev_window['prose_forms']}
    facts: Json = {
        'schema': 1, 'slug': slug, 'ticker': ticker, 'page': page, 'as_of': as_of,
        'generated_at': datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds'),
        'previous_edition': {'as_of': old['as_of'], 'price': old['price'], 'source': 'the page before this run'},
        'page_before': {k: v for k, v in old.items() if k != 'mcap'},
        'fields': f, 'written': written, 'not_written': not_written, 'warnings': warnings, 'new_values': newvals,
        'fixed_points': fixinfo['fixed'] if fixinfo else [], 'previous_window': prev_window}
    return facts, new


def write_outputs(out: str, facts: Json, page_text: str, written: bool, post: bool = False) -> list[str]:
    """facts.json (pre-pass only) and stale_hits.txt; returns the hits."""
    old = dict(facts['page_before'])
    hits = stale_hits(page_text, stale_patterns(old, facts['new_values']))
    if not post:
        rd.write_json(os.path.join(out, 'facts.json'), facts, indent=1)
    where = ('after the post-pass' if post else 'after the pre-pass; page written' if written else
             'after the pre-pass; page NOT written: line numbers are of the page as the pre-pass would write it')
    pe, yl = old['pe'], old['yield']
    head = (f"# stale hits for {facts['page']} ({where})\n"
            f"# previous edition: as-of {old['as_of']}, price {old['price']}, 52-week {old['range_52w']}, "
            f"P/E {pe[0] if pe else None}, yield {f'{yl[0]}%' if yl else None}. Each line is a place the page may "
            "still show an old value: fix it, or leave it when it is about that date on purpose.\n")
    rl.write_text(os.path.join(out, 'stale_hits.txt'), head + '\n'.join(hits) + ('\n' if hits else ''))
    return hits


def fetch_all(slug: str, ticker: str, as_of_arg: str, now: datetime.datetime) -> tuple[Daily, str, Json]:
    """The stock's daily series, the as-of, and the other fetches (each a string where it failed)."""
    today = now.date()
    now_ts = int(now.timestamp())
    daily = daily_series(ca.yahoo_symbol(slug, ticker), today, now_ts)
    settled = settled_as_of(daily.days, now, daily.gmtoffset)
    if as_of_arg == 'auto':
        as_of = settled
    else:
        as_of = datetime.date.fromisoformat(as_of_arg).isoformat()
        if as_of > settled:
            raise ValueError(f'{as_of} has not settled (latest settled close: {settled})')
    other: Json = {'bench': {}}
    for b in BENCHMARKS:
        try:
            other['bench'][b] = daily_series(b, today, now_ts)
        except (ca.YahooError, *NET_ERRORS) as e:
            other['bench'][b] = f'{type(e).__name__}: {e}'
    for key, url in (('short', NASDAQ_SHORT), ('surprise', NASDAQ_SURPRISE)):
        try:
            other[key] = nasdaq(key, url.format(sym=ticker), ticker, today)
        except NET_ERRORS as e:
            other[key] = f'{type(e).__name__}: {e}'
    try:
        other['monthly'] = ca.monthly_series(slug, ticker, as_of)
    except ca.YahooError as e:
        other['monthly'] = f'yahoo {e}'
    return daily, as_of, other


def chart_summary(facts: Json) -> str:
    """The summary line's chart part: 'trimmed K points (window N)[, events dropped: …] | fixed K chart points (…)'."""
    chart = facts['fields']['chart']
    trim, fixinfo = chart['trim'], chart['fix_points']
    out = f"trimmed {trim['dropped']} points (window {trim['window']})" if trim['window'] else 'not trimmed (--window 0)'
    if trim['events_dropped']:
        out += ', events dropped: ' + '; '.join(e['label'] for e in trim['events_dropped'])
    if fixinfo is None:
        return out + ' | points not checked (--fix-points off)'
    return out + (f" | fixed {len(fixinfo['fixed'])} chart points ({fixinfo['basis']} basis, {fixinfo['compared']} "
                  'compared' + ''.join(f", {len(v)} skipped: {k}" for k, v in fixinfo['skipped'].items()) + ')')


def prepass(slug: str, repo: str, as_of_arg: str, out: str, write: bool, now: datetime.datetime,
            window: int = WINDOW, fix: bool = False) -> int:
    path = rd.report_path(slug, repo=repo)
    if not os.path.isfile(path):
        print(f'no page {path}')
        return 1
    t = rl.read_text(path)
    ticker = rl.parse_title(t)[0]
    if not ticker:
        print(f'{slug}: no ticker in the <title>')
        return 1
    try:
        daily, as_of, other = fetch_all(slug, ticker, as_of_arg, now)
        facts, new = build(slug, t, daily, as_of, other['bench'], other['short'], other['surprise'], other['monthly'],
                           window, fix)
    except (ca.YahooError, ChartError, ValueError, *NET_ERRORS) as e:
        print(f'{slug}: pre-pass failed: {type(e).__name__}: {e}')
        return 1
    os.makedirs(out, exist_ok=True)
    core_ok = all(k in facts['written'] for k in CORE)
    if write and core_ok:
        rl.write_text(path, new)
    hits = write_outputs(out, facts, new, write and core_ok)
    prev = facts['previous_edition']
    print(f"{slug}: as-of {as_of} close {facts['fields']['close']['value']} (previous edition {prev['as_of']} "
          f"{prev['price']}) | {chart_summary(facts)}"
          f" | {'wrote' if write and core_ok else 'would write'}: {', '.join(facts['written']) or 'nothing'}"
          f" | left to the builder: {', '.join(f'{k} ({v})' for k, v in facts['not_written'].items()) or 'none'}"
          f" | stale hits {len(hits)} | {os.path.join(out, 'facts.json')}")
    for wmsg in facts['warnings']:
        print('  WARNING ' + wmsg)
    for fp in facts['fixed_points'][:12]:
        print(f"  fixed {fp['month']}: {fp['old']} -> {fp['new']} ({fp['basis']}, {fp['date']})")
    if len(facts['fixed_points']) > 12:
        print(f"  … and {len(facts['fixed_points']) - 12} more in facts.json")
    return 0 if core_ok else 1


# ---------- the post-pass ----------

def postpass(slug: str, repo: str, out: str, check_only: bool) -> int:
    """Hold the page to facts.json after the builder; fix what follows from the page's own final cells."""
    path = rd.report_path(slug, repo=repo)
    fpath = os.path.join(out, 'facts.json')
    if not os.path.isfile(path) or not os.path.isfile(fpath):
        print(f'{slug}: post-pass needs {path} and {fpath}')
        return 1
    with open(fpath, encoding='utf-8') as fh:
        facts = json.load(fh)
    t = rl.read_text(path)
    page = facts['page']
    f = facts['fields']
    close = f['close']['value']
    fails: list[str] = []
    fixes: list[str] = []
    notes: list[str] = []
    new = t
    if rl.as_of(t)[0] != facts['as_of']:
        fails.append(f"banner as-of {rl.as_of(t)[0]} != facts {facts['as_of']}")
    price = rl.header_price(t)
    if price is None or abs(price - close) >= rl.PRICE_EXACT:
        fails.append(f'header price {price} != facts close {close}')
    labels, prices = rl.chart_series(t)
    if labels and prices and len(labels) == len(prices) and price is not None:
        if abs(prices[-1] - price) >= rl.PRICE_EXACT:
            fixes.append(f'last chart point {prices[-1]} -> header {price}')
            try:
                new = rp.set_chart_series(new, labels, prices[:-1] + [price], page)
            except rp.PatchError as e:
                fails.append(str(e))
        pos = {lab: i for i, lab in enumerate(labels)}
        for pt in f['chart']['replaced'] + f['chart']['appended']:
            i = pos.get(pt['label'])
            if i is None or (i != len(labels) - 1 and abs(prices[i] - pt['value']) >= rl.PRICE_EXACT):
                fails.append(f"chart point {pt['label']} {prices[i] if i is not None else 'missing'} != facts {pt['value']}")
        for fp in facts.get('fixed_points') or []:
            i = pos.get(fp['month'])
            if i is not None and abs(prices[i] - fp['new']) >= rl.PRICE_EXACT:
                fails.append(f"fixed chart point {fp['month']} {prices[i]} != facts {fp['new']} (was {fp['old']})")
    else:
        fails.append('chart arrays unreadable or of unequal length')
    w = rl.range_52w(t)
    want = f['range_52w']['value']
    if not w or abs(w[0] - want[0]) >= rl.PRICE_EXACT or abs(w[1] - want[1]) >= rl.PRICE_EXACT:
        fails.append(f'52-week range {w} != facts {want}')
    if price is not None:
        eps_cells, pe_cells = rp.fin_row_texts(new, EPS_LABEL), rp.fin_row_texts(new, PE_LABEL)
        eps = plain_value(eps_cells[1]) if eps_cells else None
        pe_now = cell_number(pe_cells[1]) if pe_cells else None
        if eps and eps > 0:
            want_pe = price / eps
            if not pe_now:
                fails.append(f"P/E cell {pe_cells[1] if pe_cells else 'missing'!r} but EPS {eps} > 0")
            elif round(want_pe, pe_now[1]) != round(pe_now[0], pe_now[1]):
                fixes.append(f'P/E {pe_now[0]} -> {round(want_pe, pe_now[1])} (= {price} / {eps})')
                try:
                    new = rp.set_fin_number(new, PE_LABEL, want_pe, page)
                except rp.PatchError as e:
                    fails.append(str(e))
        elif pe_now:
            fails.append(f'P/E {pe_now[0]} shown but the EPS cell is not a positive number ({eps_cells and eps_cells[1]!r})')
        yrow = rp.fin_row_texts(new, YIELD_LABEL)
        ycell = cell_number(yrow[1]) if yrow else None
        formula = yield_formula(yrow[-1]) if yrow else None
        if formula and ycell:
            if abs(formula[1] - price) >= rl.PRICE_EXACT:
                fails.append(f'the yield context still divides by ${formula[1]} (header ${price})')
            want_y = formula[0] / price * 100
            if round(want_y, ycell[1]) != round(ycell[0], ycell[1]):
                fixes.append(f'yield {ycell[0]}% -> {round(want_y, ycell[1])}% (= ${formula[0]} / ${price})')
                try:
                    new = rp.set_fin_number(new, YIELD_LABEL, want_y, page)
                except rp.PatchError as e:
                    fails.append(str(e))
        elif ycell and f['dividend_yield']['value'] is not None and \
                round(ycell[0], ycell[1]) != round(f['dividend_yield']['value'], ycell[1]):
            notes.append(f"yield {ycell[0]}% differs from the pre-pass's {f['dividend_yield']['value']}% "
                         f"({f['dividend_yield']['page_basis']} basis): fine if the builder used a newly declared rate")
    box = delta_attrs(new)
    prev = facts['previous_edition']
    if box is None:
        notes.append('no delta box (.tg-d) on the page')
    else:
        want_box = {'as-of': facts['as_of'], 'price': close, 'prior-as-of': prev['as_of'], 'prior-price': prev['price']}
        for k, v in want_box.items():
            got = box.get(k)
            same = got == v if isinstance(v, str) else (rl.to_number(got or '') is not None and
                                                         abs((rl.to_number(got or '') or 0) - v) < rl.PRICE_EXACT)
            if not same:
                fails.append(f'delta box data-{k}="{got}" != {v}')
    if fixes and check_only:
        fails += [f'would fix: {x}' for x in fixes]
    elif fixes:
        rl.write_text(path, new)
    hits = write_outputs(out, facts, new if not check_only else t, bool(fixes) and not check_only, post=True)
    rd.write_json(os.path.join(out, 'post.json'), {'fails': fails, 'fixes': fixes, 'notes': notes,
                                                   'stale_hits': len(hits)}, indent=1)
    print(f"{slug}: post-pass {'FAIL' if fails else 'ok'} | fixed: {'; '.join(fixes) if fixes and not check_only else 'nothing'}"
          f" | stale hits {len(hits)} ({os.path.join(out, 'stale_hits.txt')})")
    for x in fails:
        print('  MISMATCH ' + x)
    for x in notes:
        print('  note ' + x)
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    ap = rd.parser('The scripted number layer of an earnings refresh: facts.json, stale_hits.txt and the structured '
                   'fields of one stock report.')
    ap.add_argument('slug', help='report slug, e.g. ccl')
    ap.add_argument('--as-of', default='auto', help='YYYY-MM-DD or auto (the latest settled close; default)')
    ap.add_argument('--out', help=f'folder for facts.json and stale_hits.txt (default {OUT_ROOT}/<slug>)')
    ap.add_argument('--write', action='store_true', help='write the structured fields into the page')
    ap.add_argument('--window', type=int, default=WINDOW, help=f'chart points kept, oldest dropped, events re-indexed '
                    f'(default {WINDOW}: five years of month-ends + the as-of point; 0 = no trim)')
    ap.add_argument('--fix-points', action='store_true', help="replace existing chart points more than half a cent "
                    "off Yahoo's month-end on the page's basis (listed in facts.json fixed_points)")
    ap.add_argument('--post', action='store_true', help='the post-pass, after the builder (reads <out>/facts.json)')
    ap.add_argument('--check', action='store_true', help='with --post: change nothing; fail on anything it would fix')
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[union-attr]
    out = args.out or os.path.join(OUT_ROOT, args.slug)
    if args.post:
        return postpass(args.slug, args.repo, out, args.check)
    return prepass(args.slug, args.repo, args.as_of, out, args.write, datetime.datetime.now(datetime.UTC),
                   args.window, args.fix_points)


if __name__ == '__main__':
    sys.exit(main())
