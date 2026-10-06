"""The earnings refresh queue: which stock reports went stale because the company reported after the report's as-of
date, when each refresh becomes due (the T+2 settled close, claude/briefs/REFRESH.md) and its tier (T1 rewrite / T2
numbers).   Run: py -3 tools/refresh_queue.py [--today YYYY-MM-DD] [--ahead N]

Reads the Nasdaq earnings calendar (one file per day, cached), the manifest (as-of dates, index membership),
data/style_tags.json (market caps) and Yahoo daily closes (the first-session move). Writes tasks/queue/queue.json and
tasks/queue/today.md; tasks/ is git-excluded because the repo is served publicly. No AI, no writes to reports."""
import datetime
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from http.client import HTTPException
from typing import Literal, NotRequired, TypedDict

import repodata as rd

Date = datetime.date
Timing = Literal['pre', 'post', 'unknown']
Status = Literal['overdue', 'due', 'waiting', 'upcoming']

NASDAQ_CAL = 'https://api.nasdaq.com/api/calendar/earnings?date={day}'
YAHOO_DAILY = 'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=6mo&interval=1d'
# Nasdaq's API answers a browser user agent only; no personal data goes in any request (claude/briefs/BUILD.md).
NASDAQ_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                'Chrome/140.0 Safari/537.36', 'Accept': 'application/json, text/plain, */*',
                  'Accept-Language': 'en-US,en;q=0.9'}
YAHOO_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
YAHOO_SYMBOL = {'brkb': 'BRK-B', 'bfb': 'BF-B'}   # as in chart_audit.py
FETCH_TIMEOUT_S, FETCH_PAUSE_S = 30, 0.3
# One cache per user, not per checkout: the review worktree's runs must see the release times the nightly run saw.
CAL_CACHE = os.path.join(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir(), 'ttg-refresh-queue', 'calendar')
RECHECK_DAYS = 7  # calendar days this recent are re-fetched every run: Nasdaq fills in actual EPS after the print

# NYSE full closures, from nyse.com/markets/hours-calendars (read 30 Sep 2026). Extend before 2028.
NYSE_HOLIDAYS = frozenset(Date.fromisoformat(d) for d in (
    '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07',
    '2026-11-26', '2026-12-25',
    '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18', '2027-07-05', '2027-09-06',
    '2027-11-25', '2027-12-24'))

# Tier rules, claude/briefs/REFRESH.md TASK B. The queue can see the surprise, the first-session move and index
# membership; guidance changes and company news are judged by the builder, who may still raise a T2 to T1.
T1_SURPRISE_PCT = 10.0
T1_MOVE_PCT = 5.0
MEGA_CAP_USD = 200e9   # "mega-cap names default to T1": our threshold (Oki may change it)
# A new report's first refresh is a full T1 rewrite (Oki, 5 Oct 2026: "new reports clearly need a full rewrite"):
# reports first published on or after this date that have not been refreshed yet. The older library is not included.
FIRST_REFRESH_T1_SINCE = '2026-09-28'
DUE_WITHIN_SESSIONS = 5   # finish within 5 trading days of the release, or the refresh is overdue


class Print(TypedDict):
    """One row of the Nasdaq earnings calendar."""
    day: str                 # the calendar date the release is listed under, YYYY-MM-DD
    symbol: str
    timing: Timing
    eps: float | None        # reported (Nasdaq's basis), None before the print
    eps_forecast: float | None
    surprise_pct: float | None
    fiscal_quarter: str


class Holding(TypedDict):
    """What the queue needs from one report."""
    slug: str
    ticker: str
    as_of: str
    ndx: bool
    dow: bool
    mcap: float | None
    first_as_of: NotRequired[str | None]   # as-of of the first published edition
    refreshed: NotRequired[bool]           # True once the report has a second edition


class Item(TypedDict):
    """One stale (or soon stale) report."""
    ticker: str
    slug: str
    as_of: str
    release: str
    timing: Timing
    first_session: str
    t2: str
    status: Status
    sessions_since_release: int
    tier: Literal['T1', 'T2']
    triggers: list[str]
    eps: float | None
    eps_forecast: float | None
    surprise_pct: float | None
    first_move_pct: float | None
    fiscal_quarter: str


# ---- trading calendar ----

def is_session(d: Date) -> bool:
    return d.weekday() < 5 and d not in NYSE_HOLIDAYS


def next_session(d: Date) -> Date:
    """The first session strictly after d."""
    d += datetime.timedelta(days=1)
    while not is_session(d):
        d += datetime.timedelta(days=1)
    return d


def prev_session(d: Date) -> Date:
    """The last session strictly before d."""
    d -= datetime.timedelta(days=1)
    while not is_session(d):
        d -= datetime.timedelta(days=1)
    return d


def first_session(release: Date, timing: Timing) -> Date:
    """The first full session that trades on the news: the release day itself for a pre-market release on a
    session day, else the next session. An unknown time is treated as after the close (the later case)."""
    return release if timing == 'pre' and is_session(release) else next_session(release)


def t2_date(release: Date, timing: Timing) -> Date:
    """The as-of for an earnings refresh: the close of the second full session after the release."""
    return next_session(first_session(release, timing))


def sessions_between(a: Date, b: Date) -> int:
    """Sessions in (a, b]."""
    n, d = 0, a
    while d < b:
        d += datetime.timedelta(days=1)
        n += is_session(d)
    return n


# ---- the Nasdaq calendar ----

def num(s: str | None) -> float | None:
    """'$1.39' -> 1.39, '($0.22)' -> -0.22, '' / 'N/A' -> None."""
    s = (s or '').strip().replace('$', '').replace(',', '')
    neg = s.startswith('(') and s.endswith(')')
    try:
        v = float(s.strip('()'))
    except ValueError:
        return None
    return -v if neg else v


def parse_calendar(body: dict, day: str) -> list[Print]:
    """The rows of one day's calendar response."""
    rows = ((body.get('data') or {}).get('rows')) or []
    timing: dict[str, Timing] = {'time-pre-market': 'pre', 'time-after-hours': 'post'}
    return [{'day': day, 'symbol': r['symbol'].upper(), 'timing': timing.get(r.get('time', ''), 'unknown'),
             'eps': num(r.get('eps')), 'eps_forecast': num(r.get('epsForecast')), 'surprise_pct': num(r.get('surprise')),
             'fiscal_quarter': r.get('fiscalQuarterEnding', '')} for r in rows]


def get_json(url: str, headers: dict[str, str]) -> dict:
    body = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=FETCH_TIMEOUT_S).read()  # nosec B310 - fixed https hosts
    time.sleep(FETCH_PAUSE_S)
    return json.loads(body)


def calendar_day(day: Date, today: Date, cache: str) -> list[Print]:
    """One day's prints, from the cache unless the day is recent enough to still change."""
    path = os.path.join(cache, f'{day.isoformat()}.json')
    cached: dict = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            cached = json.load(fh)
        if (today - day).days > RECHECK_DAYS:
            return parse_calendar(cached, day.isoformat())
    body = keep_known_times(get_json(NASDAQ_CAL.format(day=day.isoformat()), NASDAQ_HEADERS), cached)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(body, fh)
    return parse_calendar(body, day.isoformat())


def keep_known_times(body: dict, cached: dict) -> dict:
    """Nasdaq lists a release as pre-market or after-hours until it happens, then often as "time-not-supplied".
    Keep the time an earlier fetch saw, so the T+2 date does not slip a day."""
    known = {r['symbol']: r['time'] for r in ((cached.get('data') or {}).get('rows') or [])
             if r.get('time') in ('time-pre-market', 'time-after-hours')}
    for r in ((body.get('data') or {}).get('rows') or []):
        if r.get('time') not in ('time-pre-market', 'time-after-hours') and r['symbol'] in known:
            r['time'] = known[r['symbol']]
    return body


# ---- the library ----

def norm(symbol: str) -> str:
    """BRK.B, BRK-B and BRK/B all -> BRKB."""
    return symbol.upper().replace('.', '').replace('-', '').replace('/', '')


def holdings(repo: str = rd.ROOT) -> dict[str, Holding]:
    """Normalised ticker -> the report's queue inputs."""
    with open(os.path.join(repo, 'data', 'style_tags.json'), encoding='utf-8') as fh:
        mcap = {r['slug']: r.get('mcap') for r in json.load(fh)['reports']}
    out: dict[str, Holding] = {}
    for slug, r in rd.load_report_records(repo).items():
        eds = r.get('editions') or []
        out[norm(r['ticker'])] = {'slug': slug, 'ticker': r['ticker'], 'as_of': r['as_of'], 'ndx': bool(r.get('ndx')),
                                  'dow': bool(r.get('dow30_added')), 'mcap': mcap.get(slug),
                                  'first_as_of': str(eds[0][0]) if eds else r['as_of'], 'refreshed': len(eds) > 1}
    return out


# ---- the first-session move ----

def daily_closes(slug: str, ticker: str) -> dict[Date, float]:
    """Yahoo daily closes over the last six months (split-adjusted, not dividend-adjusted)."""
    res = get_json(YAHOO_DAILY.format(sym=YAHOO_SYMBOL.get(slug, ticker.replace('.', '-'))), YAHOO_HEADERS)
    r = res['chart']['result'][0]
    offset = r['meta'].get('gmtoffset') or 0
    closes = r['indicators']['quote'][0].get('close') or []
    return {datetime.datetime.fromtimestamp(ts + offset, datetime.UTC).date(): c
            for ts, c in zip(r.get('timestamp') or [], closes) if c is not None}


def first_move_pct(closes: dict[Date, float], release: Date, timing: Timing) -> float | None:
    """Close-to-close % move on the first session after the print. With an unknown release time both readings are
    taken and the larger move is kept, so an unknown time can only make a T1 trigger more likely, never hide one."""
    cases: list[Timing] = ['pre', 'post'] if timing == 'unknown' else [timing]
    moves = []
    for t in cases:
        s = first_session(release, t)
        before, on = closes.get(prev_session(s)), closes.get(s)
        if before and on:
            moves.append((on / before - 1) * 100)
    return max(moves, key=abs) if moves else None


# ---- tiering and status ----

def tier(h: Holding, p: Print, move: float | None) -> tuple[Literal['T1', 'T2'], list[str]]:
    triggers = []
    if h['dow']:
        triggers.append('Dow 30')
    if h['ndx']:
        triggers.append('Nasdaq-100')
    if h['mcap'] and h['mcap'] >= MEGA_CAP_USD:
        triggers.append(f"mega-cap ${h['mcap'] / 1e9:,.0f}B")
    if p['surprise_pct'] is not None and abs(p['surprise_pct']) >= T1_SURPRISE_PCT:
        triggers.append(f"EPS surprise {p['surprise_pct']:+.1f}%")
    if move is not None and abs(move) >= T1_MOVE_PCT:
        triggers.append(f'first-session move {move:+.1f}%')
    if not h.get('refreshed', True) and (h.get('first_as_of') or '') >= FIRST_REFRESH_T1_SINCE:
        triggers.append('first refresh after the build')
    return ('T1' if triggers else 'T2'), triggers


def status_of(release: Date, t2: Date, today: Date) -> tuple[Status, int]:
    """Where a print stands on `today` (a refresh builds the morning after the T+2 close settles)."""
    since = sessions_between(release, today - datetime.timedelta(days=1))   # sessions closed since the release
    if release >= today:
        return 'upcoming', 0
    if t2 >= today:
        return 'waiting', since
    # built today, the refresh lands in session since+1: once 5 have closed it can no longer land within 5
    return ('overdue' if since >= DUE_WITHIN_SESSIONS else 'due'), since


def build_items(prints: list[Print], lib: dict[str, Holding], today: Date,
                closes_for=daily_closes) -> tuple[list[Item], int]:
    """The queue: for each report, the latest print after its as-of date that has happened, else the next one
    scheduled. Returns the items and how many listed prints were already covered by the report's as-of."""
    by_ticker: dict[str, list[Print]] = {}
    covered = 0
    for p in prints:
        h = lib.get(norm(p['symbol']))
        if not h:
            continue
        if p['day'] <= h['as_of']:
            covered += 1
            continue
        by_ticker.setdefault(norm(p['symbol']), []).append(p)
    items: list[Item] = []
    for key, ps in by_ticker.items():
        h = lib[key]
        past = [p for p in ps if Date.fromisoformat(p['day']) < today]
        p = max(past, key=lambda x: x['day']) if past else min(ps, key=lambda x: x['day'])
        release = Date.fromisoformat(p['day'])
        t2 = t2_date(release, p['timing'])
        st, since = status_of(release, t2, today)
        move = None
        if st != 'upcoming':
            try:
                move = first_move_pct(closes_for(h['slug'], h['ticker']), release, p['timing'])
            except (urllib.error.URLError, HTTPException, TimeoutError, OSError, KeyError, IndexError, TypeError):
                move = None   # shown as "move n/a"; the builder measures it anyway
        tr, triggers = tier(h, p, move)
        items.append({'ticker': h['ticker'], 'slug': h['slug'], 'as_of': h['as_of'], 'release': p['day'],
                      'timing': p['timing'], 'first_session': first_session(release, p['timing']).isoformat(),
                      't2': t2.isoformat(), 'status': st, 'sessions_since_release': since, 'tier': tr,
                      'triggers': triggers, 'eps': p['eps'], 'eps_forecast': p['eps_forecast'],
                      'surprise_pct': p['surprise_pct'], 'first_move_pct': None if move is None else round(move, 2),
                      'fiscal_quarter': p['fiscal_quarter']})
    order = {'overdue': 0, 'due': 1, 'waiting': 2, 'upcoming': 3}
    # due work T1 first; the upcoming list in date order
    items.sort(key=lambda i: (order[i['status']], i['tier'] if i['status'] != 'upcoming' else '', i['release'], i['ticker']))
    return items, covered


def today_md(items: list[Item], today: Date, generated: str) -> str:
    """The short list read in the morning."""
    lines = [f'# Refresh queue — {today.isoformat()}', '', f'_Generated {generated} by tools/refresh_queue.py. '
             'Due = the T+2 close has settled; overdue = more than 5 trading days since the release._', '']
    for st, title in (('overdue', 'Overdue'), ('due', 'Due now'), ('waiting', 'Reported, waiting for T+2'),
                      ('upcoming', 'Next 14 days')):
        rows = [i for i in items if i['status'] == st]
        lines.append(f'## {title} ({len(rows)})')
        for i in rows[:60]:
            eps = '' if i['eps'] is None else f" · EPS {i['eps']} vs {i['eps_forecast']}"
            mv = '' if i['first_move_pct'] is None else f" · day-1 {i['first_move_pct']:+.1f}%"
            why = f" ({', '.join(i['triggers'])})" if i['triggers'] else ''
            lines.append(f"- {i['ticker']} {i['tier']}{why} · released {i['release']} {i['timing']} · T+2 {i['t2']}"
                         f" · page as of {i['as_of']}{eps}{mv}")
        if len(rows) > 60:
            lines.append(f'- … {len(rows) - 60} more in queue.json')
        lines.append('')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = rd.parser('The earnings refresh queue (tasks/queue/queue.json and today.md).')
    ap.add_argument('--today', help='run as of this date, YYYY-MM-DD (default: the local date)')
    ap.add_argument('--ahead', type=int, default=14, help='calendar days of upcoming prints to list (default 14)')
    ap.add_argument('--cache', default=CAL_CACHE, help='calendar cache folder (default: one per user, shared by every '
                    'checkout, so a release time seen before the print is kept)')
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[union-attr]  # the summary line uses '·'
    today = Date.fromisoformat(args.today) if args.today else Date.today()
    out_dir = os.path.join(args.repo, 'tasks', 'queue')
    cache = args.cache
    os.makedirs(cache, exist_ok=True)
    lib = holdings(args.repo)
    start = Date.fromisoformat(min(h['as_of'] for h in lib.values()))
    prints: list[Print] = []
    failed = []
    d = start
    while d <= today + datetime.timedelta(days=args.ahead):
        if d.weekday() < 5:
            try:
                prints += calendar_day(d, today, cache)
            except (urllib.error.URLError, HTTPException, TimeoutError, OSError, ValueError) as e:
                failed.append(f'{d.isoformat()}: {e}')
        d += datetime.timedelta(days=1)
    items, covered = build_items(prints, lib, today)
    generated = datetime.datetime.now().isoformat(timespec='minutes')
    counts = {st: sum(i['status'] == st for i in items) for st in ('overdue', 'due', 'waiting', 'upcoming')}
    rd.write_json(os.path.join(out_dir, 'queue.json'), {
        'generated_at': generated, 'today': today.isoformat(), 'calendar_from': start.isoformat(),
        'rules': {'t1_surprise_pct': T1_SURPRISE_PCT, 't1_move_pct': T1_MOVE_PCT, 'mega_cap_usd': MEGA_CAP_USD,
                  'due_within_sessions': DUE_WITHIN_SESSIONS},
        'counts': counts, 'prints_already_covered': covered, 'calendar_failures': failed, 'items': items}, indent=1)
    with open(os.path.join(out_dir, 'today.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(today_md(items, today, generated))
    print(f"queue {today}: " + ' · '.join(f'{k} {v}' for k, v in counts.items())
          + f" · covered {covered}" + (f" · CALENDAR FAILURES {len(failed)}" if failed else ''))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
