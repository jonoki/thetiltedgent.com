"""Earnings dates for the stock reports the Nasdaq calendar does not carry: the non-US home listings (0700.HK,
NESN.SW ...) and the US-listed global names (ADRs and the like) with no print in this run's Nasdaq calendar.
refresh_queue.py adds these prints to Nasdaq's; run alone it prints what it found.
    Run: py -3 tools/global_calendar.py [--today YYYY-MM-DD]

Sources (Oki, 8 Oct 2026), best first when two give the same release (dates within SAME_EVENT_DAYS):
  1. data/ir_calendar.json, kept by hand from the companies' own IR calendars (revenue-only and trading updates);
  2. HKEX board-meeting notifications (www3.hkexnews.hk/reports/bmn/ebmn.htm), for the Hong Kong listings;
  3. each name's stockanalysis.com statistics page ("The next confirmed earnings date is ..." / "The last
     earnings date was ..."), read at most once a day, robots.txt obeyed, PAUSE_S between requests;
  4. what the previous day's run saw as confirmed or reported (a page may move straight on to the next estimate).
A Saturday "confirmed" date on stockanalysis is recorded as estimated. A past date only counts when it was reported
or confirmed. No Yahoo, no JPX/TDnet, and no personal data in any request. Each day's result is cached as
global-YYYY-MM-DD.json in the refresh queue's calendar cache; a second run that day reads it."""
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from http.client import HTTPException
from typing import Callable, Literal, TypedDict
from urllib.parse import urlsplit

import refresh_queue as rq
import repodata as rd

Date = datetime.date
Status = Literal['reported', 'confirmed', 'estimated']
Kind = Literal['ir', 'hkex', 'stockanalysis', 'earlier']

SA_ROOT = 'https://stockanalysis.com'
HKEX_BMN = 'https://www3.hkexnews.hk/reports/bmn/ebmn.htm'
# stockanalysis exchange codes by Yahoo-style suffix (every report's page fetched once to check, 8 Oct 2026)
SA_EXCHANGE = {'HK': 'hkg', 'KS': 'krx', 'SZ': 'she', 'SS': 'sha', 'TW': 'tpe', 'T': 'tyo', 'PA': 'epa', 'SW': 'swx',
               'DE': 'etr', 'MC': 'bme', 'MI': 'bit', 'AS': 'ams', 'ST': 'sto', 'L': 'lon', 'SR': 'tadawul',
               'NS': 'nse', 'AX': 'asx', 'SI': 'sgx'}
# Reports whose home-listing statistics page does not exist on stockanalysis, and the page used instead:
# Ping An's /quote/hkg/2318/statistics/ is a 404 (8 Oct 2026); its Shanghai A share reports the same results the same day.
SA_PAGE = {'pingan': 'https://stockanalysis.com/quote/sha/601318/statistics/'}
# A generic browser user agent (stockanalysis answers it); nothing in any request identifies anyone.
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/140.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
           'Accept-Language': 'en-US,en;q=0.9'}
FETCH_TIMEOUT_S = 30
PAUSE_S = 3.0             # between any two requests (Oki: 2-4 s)
SAME_EVENT_DAYS = 7       # two sources' dates this close are the same release
EARLIER_CACHE_DAYS = 7    # how far back the previous day's cache may be
IR_FILE = os.path.join('data', 'ir_calendar.json')
PRIORITY: dict[str, int] = {'ir': 0, 'hkex': 1, 'stockanalysis': 2, 'earlier': 3}
MONTHS = {m: i + 1 for i, m in enumerate('January February March April May June July August September October '
                                         'November December'.split())}
SATURDAY = 5
NET_ERRORS = (urllib.error.URLError, HTTPException, TimeoutError, OSError)

SA_SENTENCE = re.compile(
    r'The (?:next (?P<kind>confirmed|estimated) earnings date is|last earnings date was) '
    r'[A-Z][a-z]+, (?P<mon>[A-Z][a-z]+) (?P<day>\d{1,2}), (?P<year>\d{4})'
    r'(?:, (?P<tod>before market open|after market close))?')


class Target(TypedDict):
    """One report to look up: its slug, its title ticker (the symbol holdings() keys it by) and its page."""
    slug: str
    symbol: str
    url: str


class SaDate(TypedDict):
    """One earnings-date sentence of a stockanalysis page."""
    day: str            # YYYY-MM-DD
    status: Status
    timing: rq.Timing


class HkexRow(TypedDict):
    """One row of HKEX's board-meeting list."""
    day: str            # YYYY-MM-DD (the page writes DD/MM/YYYY)
    code: int
    purpose: str
    period: str


class IrRow(TypedDict):
    """One row of data/ir_calendar.json."""
    date: str
    event: str
    source: str
    timing: rq.Timing


class Event(TypedDict):
    """One dated release for one report, from one source."""
    slug: str
    symbol: str
    day: str            # YYYY-MM-DD, the release date on the home market
    timing: rq.Timing
    status: Status
    kind: Kind
    source: str         # the page the date was read on
    note: str           # HKEX purpose and period / the IR event; '' for stockanalysis


class Fetcher:
    """Polite GETs: robots.txt read once per host and obeyed, PAUSE_S between requests. A host whose robots.txt
    cannot be read is left alone (and said so in `problems`). `get` and `sleep` are injectable for the tests."""

    def __init__(self, get: Callable[[str], str] | None = None, sleep: Callable[[float], None] = time.sleep):
        self.get = get or http_get
        self.sleep = sleep
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.problems: list[str] = []
        self.last = 0.0

    def allowed(self, url: str) -> bool:
        """robots.txt lets us fetch this URL. Read with our own GET, not robotparser's read(): that sends Python's
        user agent, which some sites answer with 403, which robotparser takes as 'disallow all'."""
        host = '{0.scheme}://{0.netloc}'.format(urlsplit(url))
        if host not in self.robots:
            self.robots[host] = self.read_robots(host)
        rp = self.robots[host]
        return rp is not None and rp.can_fetch(HEADERS['User-Agent'], url)

    def read_robots(self, host: str) -> urllib.robotparser.RobotFileParser | None:
        rp = urllib.robotparser.RobotFileParser(host + '/robots.txt')
        try:
            rp.parse(self.fetch(host + '/robots.txt').splitlines())
        except urllib.error.HTTPError as e:
            if e.code not in (404, 410):   # no robots.txt means no rules; any other error means keep off
                self.problems.append(f'global {host}/robots.txt: HTTP {e.code}; host skipped')
                return None
            rp.parse([])
        except NET_ERRORS as e:
            self.problems.append(f'global {host}/robots.txt: {e}; host skipped')
            return None
        return rp

    def fetch(self, url: str) -> str:
        """One GET, at least PAUSE_S after the previous one."""
        wait = self.last + PAUSE_S - time.monotonic()
        if self.last and wait > 0:
            self.sleep(wait)
        try:
            return self.get(url)
        finally:
            self.last = time.monotonic()


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as r:  # nosec B310 - fixed https hosts
        return r.read().decode('utf-8', errors='replace')


# ---- which reports, and where ----

def home_suffix(symbol: str) -> str | None:
    """'HK' for 0700.HK; None for a US ticker (AZN, BRK.B)."""
    _, dot, suffix = symbol.rpartition('.')
    return suffix if dot and suffix in SA_EXCHANGE else None


def sa_url(symbol: str) -> str | None:
    """The stockanalysis statistics page of a title ticker: 0700.HK -> /quote/hkg/0700/, ATCO-A.ST ->
    /quote/sto/ATCO.A/, AZN -> /stocks/azn/. None for a ticker it cannot place."""
    suffix = home_suffix(symbol)
    if suffix:
        code = symbol.rpartition('.')[0]
        if suffix == 'HK':
            code = code.zfill(4)            # the site uses the four-digit code: /hkg/0700/ (/hkg/700/ is a 404)
        elif suffix == 'ST':
            code = code.replace('-', '.')   # share class: ATCO-A -> ATCO.A
        return f'{SA_ROOT}/quote/{SA_EXCHANGE[suffix]}/{code}/statistics/'
    if re.fullmatch(r'[A-Z]+', symbol):
        return f'{SA_ROOT}/stocks/{symbol.lower()}/statistics/'
    return None


def targets(records: dict[str, rd.ReportRecord], nasdaq_symbols: set[str]) -> list[Target]:
    """Every home-listed report, and every US-listed global name (a card with a home exchange) with no print in
    this run's Nasdaq calendar. nasdaq_symbols are normalised (refresh_queue.norm)."""
    out: list[Target] = []
    for slug, r in sorted(records.items()):
        sym = r.get('ticker') or ''
        missed_adr = bool(r.get('global_exchange')) and rq.norm(sym) not in nasdaq_symbols
        url = SA_PAGE.get(slug) or sa_url(sym)
        if url and (home_suffix(sym) or missed_adr):
            out.append({'slug': slug, 'symbol': sym, 'url': url})
    return out


# ---- stockanalysis ----

def sa_timing(tod: str | None) -> rq.Timing:
    return 'pre' if tod == 'before market open' else 'post' if tod == 'after market close' else 'unknown'


def sa_dates(page: str) -> list[SaDate]:
    """The earnings-date sentences of one statistics page, from the raw HTML (the visible paragraph and the
    embedded page data both carry them), one per kind. A Saturday "confirmed" date is recorded as estimated."""
    seen: dict[str, SaDate] = {}
    for m in SA_SENTENCE.finditer(page):
        key = m.group('kind') or 'last'
        if key in seen or m.group('mon') not in MONTHS:
            continue
        d = Date(int(m.group('year')), MONTHS[m.group('mon')], int(m.group('day')))
        status: Status = 'reported' if key == 'last' else 'confirmed' if key == 'confirmed' else 'estimated'
        if status == 'confirmed' and d.weekday() == SATURDAY:
            status = 'estimated'   # unreliable; a company or exchange source can still confirm it
        seen[key] = {'day': d.isoformat(), 'status': status, 'timing': sa_timing(m.group('tod'))}
    return list(seen.values())


def page_title(page: str) -> str:
    """The page's <title>, kept in the cache so a wrong mapping (another company's page) can be seen."""
    m = re.search(r'<title>(.*?)</title>', page, re.S | re.I)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''


def sa_events(t: Target, dates: list[SaDate]) -> list[Event]:
    return [{'slug': t['slug'], 'symbol': t['symbol'], 'day': d['day'], 'timing': d['timing'], 'status': d['status'],
             'kind': 'stockanalysis', 'source': t['url'], 'note': ''} for d in dates]


# ---- HKEX board meetings ----

def hkex_rows(page: str) -> list[HkexRow]:
    """Every row of the board-meeting list: BM date, (flag), short name, code, purpose, period."""
    out: list[HkexRow] = []
    for tr in re.findall(r'<tr>(.*?)</tr>', page, re.S | re.I):
        cells = [re.sub(r'<[^>]+>', '', c).replace('&nbsp;', ' ').strip()
                 for c in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S | re.I)]
        m = re.fullmatch(r'(\d{2})/(\d{2})/(\d{4})', cells[0]) if len(cells) >= 6 else None
        if m and cells[3].isdigit():
            day = Date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
            out.append({'day': day, 'code': int(cells[3]), 'purpose': cells[4], 'period': cells[5]})
    return out


def hkex_events(rows: list[HkexRow], ts: list[Target]) -> list[Event]:
    """Results meetings (the purpose says RES / RESULTS; a dividend-only meeting is not a print) of the Hong
    Kong listings among the targets. HKEX gives no time of day."""
    by_code = {int(t['symbol'].split('.')[0]): t for t in ts if home_suffix(t['symbol']) == 'HK'}
    out: list[Event] = []
    for r in rows:
        t = by_code.get(r['code'])
        if t and re.search(r'\bRES', r['purpose']):
            out.append({'slug': t['slug'], 'symbol': t['symbol'], 'day': r['day'], 'timing': 'unknown',
                        'status': 'confirmed', 'kind': 'hkex', 'source': HKEX_BMN,
                        'note': f"{r['purpose']} {r['period']}".strip()})
    return out


# ---- the hand-kept IR file ----

def load_ir(repo: str) -> dict[str, list[IrRow]]:
    """data/ir_calendar.json without its notes (keys starting with '_'); {} when there is no file."""
    path = os.path.join(repo, IR_FILE)
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as fh:
        return {k: v for k, v in json.load(fh).items() if not k.startswith('_')}


def ir_problems(ir: dict[str, list[IrRow]], records: dict[str, rd.ReportRecord]) -> list[str]:
    """What is wrong with the IR file: an unknown slug, a bad date or timing, a source that is not a URL."""
    bad = []
    for slug, rows in ir.items():
        if slug not in records:
            bad.append(f'{slug}: no such report')
        for r in rows:
            try:
                Date.fromisoformat(r['date'])
            except (KeyError, ValueError):
                bad.append(f"{slug}: bad date {r.get('date')!r}")
            if r.get('timing') not in ('pre', 'post', 'unknown'):
                bad.append(f"{slug}: bad timing {r.get('timing')!r}")
            if not str(r.get('source', '')).startswith('https://'):
                bad.append(f'{slug}: source is not an https URL')
    return bad


def ir_events(ir: dict[str, list[IrRow]], records: dict[str, rd.ReportRecord]) -> list[Event]:
    return [{'slug': slug, 'symbol': records[slug]['ticker'], 'day': r['date'], 'timing': r['timing'],
             'status': 'confirmed', 'kind': 'ir', 'source': r['source'], 'note': r['event']}
            for slug, rows in ir.items() if slug in records for r in rows]


# ---- merging, and the queue's prints ----

def merge(events: list[Event]) -> list[Event]:
    """One event per release: of two events for one report within SAME_EVENT_DAYS, the better source's stays."""
    kept: list[Event] = []
    for e in sorted(events, key=lambda e: (PRIORITY[e['kind']], e['day'])):
        d = Date.fromisoformat(e['day'])
        if not any(k['slug'] == e['slug'] and abs((Date.fromisoformat(k['day']) - d).days) <= SAME_EVENT_DAYS
                   for k in kept):
            kept.append(e)
    return sorted(kept, key=lambda e: (e['day'], e['symbol']))


def earlier_events(cached: dict | None, today: Date) -> list[Event]:
    """The reported or confirmed dates an earlier day's run held that have now passed."""
    if not cached:
        return []
    out: list[Event] = []
    for e in cached.get('events', []):
        if e['day'] < today.isoformat() and e['status'] in ('reported', 'confirmed'):
            note = e['note'] if e['kind'] == 'earlier' else f"seen {cached.get('date', '')} via {e['kind']} {e['note']}"
            out.append({'slug': e['slug'], 'symbol': e['symbol'], 'day': e['day'], 'timing': e['timing'],
                        'status': e['status'], 'kind': 'earlier', 'source': e['source'], 'note': note.strip()})
    return out


def to_prints(events: list[Event], today: Date, ahead: int) -> list[rq.Print]:
    """The refresh queue's Print rows: past releases that were reported or confirmed, and upcoming ones up to
    `ahead` days out (estimates included). symbol = the report's title ticker, so holdings() matches it; no EPS."""
    last = (today + datetime.timedelta(days=ahead)).isoformat()
    return [{'day': e['day'], 'symbol': e['symbol'], 'timing': e['timing'], 'eps': None, 'eps_forecast': None,
             'surprise_pct': None, 'fiscal_quarter': e['note']}
            for e in events
            if e['day'] <= last and not (e['day'] < today.isoformat() and e['status'] == 'estimated')]


# ---- the daily run ----

def cache_path(cache: str, day: Date) -> str:
    return os.path.join(cache, f'global-{day.isoformat()}.json')


def read_cache(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def latest_earlier_cache(cache: str, today: Date) -> dict | None:
    """The most recent cache of the EARLIER_CACHE_DAYS before today, if any."""
    for back in range(1, EARLIER_CACHE_DAYS + 1):
        c = read_cache(cache_path(cache, today - datetime.timedelta(days=back)))
        if c:
            return c
    return None


def fetch_pages(day: dict, ts: list[Target], fetcher: Fetcher) -> tuple[list[str], list[str]]:
    """Fill day['pages'] (and day['hkex']) with what today's cache does not have yet. Returns (failures, the URLs
    robots.txt kept us off). A failed page is not cached, so the next run tries it again."""
    failures: list[str] = []
    skipped: list[str] = []
    for t in ts:
        if day['pages'].get(t['slug'], {}).get('url') == t['url']:
            continue
        if not fetcher.allowed(t['url']):
            skipped.append(t['url'])
            continue
        try:
            html = fetcher.fetch(t['url'])
            day['pages'][t['slug']] = {'url': t['url'], 'title': page_title(html), 'dates': sa_dates(html)}
        except NET_ERRORS as e:
            failures.append(f"global {t['slug']}: {e} ({t['url']})")
    if day.get('hkex') is None and any(home_suffix(t['symbol']) == 'HK' for t in ts):
        if not fetcher.allowed(HKEX_BMN):
            skipped.append(HKEX_BMN)
        else:
            try:
                day['hkex'] = hkex_rows(fetcher.fetch(HKEX_BMN))
            except NET_ERRORS as e:
                failures.append(f'global HKEX board meetings: {e}')
    return failures, skipped


def collect(records: dict[str, rd.ReportRecord], nasdaq_symbols: set[str], today: Date, cache: str, repo: str,
            fetcher: Fetcher | None = None) -> dict:
    """Today's global calendar, from today's cache where it has a page, else fetched, and cached again.
    Returns the cache record: date, targets, pages ({slug: url, title, dates}), hkex, events (merged), failures,
    robots_skipped."""
    fetcher = fetcher or Fetcher()
    path = cache_path(cache, today)
    day = read_cache(path) or {'date': today.isoformat(), 'pages': {}, 'hkex': None}
    ts = targets(records, nasdaq_symbols)
    failures, skipped = fetch_pages(day, ts, fetcher)
    ir = load_ir(repo)
    failures += fetcher.problems + [f'global {IR_FILE}: {p}' for p in ir_problems(ir, records)]
    in_scope = {t['slug'] for t in ts}
    events = [e for t in ts for e in sa_events(t, day['pages'].get(t['slug'], {}).get('dates', []))]
    events += hkex_events(day.get('hkex') or [], ts)
    events += [e for e in ir_events(ir, records) + earlier_events(latest_earlier_cache(cache, today), today)
               if e['slug'] in in_scope]
    day.update({'targets': [t['symbol'] for t in ts], 'events': merge(events), 'failures': failures,
                'robots_skipped': skipped})
    os.makedirs(cache, exist_ok=True)
    rd.write_json(path, day, indent=1)
    return day


def coverage(day: dict) -> dict:
    """How many of the names looked up have any date, and which have none."""
    dated = {e['symbol'] for e in day['events']} & set(day['targets'])
    return {'names': len(day['targets']), 'dated': len(dated), 'missing': sorted(set(day['targets']) - dated),
            'robots_skipped': day['robots_skipped']}


def main(argv: list[str] | None = None) -> int:
    ap = rd.parser('Earnings dates for the reports the Nasdaq calendar misses (stockanalysis, HKEX, IR file).')
    ap.add_argument('--today', help='run as of this date, YYYY-MM-DD (default: the local date)')
    ap.add_argument('--cache', default=rq.CAL_CACHE, help="cache folder (default: the refresh queue's)")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[union-attr]
    today = Date.fromisoformat(args.today) if args.today else Date.today()
    day = collect(rd.load_report_records(args.repo), set(), today, args.cache, args.repo)
    for e in day['events']:
        print(f"{e['day']} {e['timing']:7} {e['status']:9} {e['kind']:13} {e['symbol']:13} {e['note']}")
    cov = coverage(day)
    print(f"{cov['dated']}/{cov['names']} names dated; missing: {', '.join(cov['missing']) or 'none'}")
    for f in day['failures']:
        print('FAIL', f)
    return 1 if day['failures'] else 0


if __name__ == '__main__':
    sys.exit(main())
