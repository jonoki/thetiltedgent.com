"""Unit tests for global_calendar.py: the stockanalysis sentences, Saturday dates, the HKEX board-meeting list, the
IR file, symbol -> URL, robots.txt, merging and the queue's prints. Saved page excerpts, no network.
Run: py -3 tools/run_checks.py"""
import datetime
import email.message
import io
import os
import tempfile
import unittest
import urllib.error

import global_calendar as gc
import refresh_queue as q

D = datetime.date.fromisoformat
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def page(name):
    with open(os.path.join(DATA, name), encoding='utf-8') as fh:
        return fh.read()


def rec(ticker, gl=None):
    return {'ticker': ticker, **({'global_exchange': gl} if gl else {})}


RECORDS = {'tencent': rec('0700.HK', 'HKEX'), 'pingan': rec('2318.HK', 'HKEX'), 'nestle': rec('NESN.SW', 'SIX'),
           'lvmh': rec('MC.PA', 'EURONEXT'), 'azn': rec('AZN', 'LSE'), 'infy': rec('INFY', 'NSE'), 'aapl': rec('AAPL')}


class FakeWeb:
    """A fetcher's GET: a dict of URL -> page text or an HTTP status, counting the calls."""

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def __call__(self, url):
        self.calls.append(url)
        body = self.pages.get(url, 404)
        if isinstance(body, int):
            raise urllib.error.HTTPError(url, body, 'status', email.message.Message(), io.BytesIO(b''))
        return body


def fetcher(pages):
    web = FakeWeb(pages)
    return gc.Fetcher(get=web, sleep=lambda s: None), web


class StockAnalysis(unittest.TestCase):
    def test_next_confirmed(self):   # the sentence sits in the paragraph and in the page data: one date
        self.assertEqual(gc.sa_dates(page('stockanalysis_0700_next_confirmed.html')),
                         [{'day': '2026-11-18', 'status': 'confirmed', 'timing': 'unknown'}])

    def test_last_after_close(self):
        self.assertEqual(gc.sa_dates(page('stockanalysis_nke_last_post.html')),
                         [{'day': '2026-10-01', 'status': 'reported', 'timing': 'post'}])

    def test_estimated_before_open(self):
        html = '<p>The next estimated earnings date is Friday, October 30, 2026, before market open.</p>'
        self.assertEqual(gc.sa_dates(html), [{'day': '2026-10-30', 'status': 'estimated', 'timing': 'pre'}])

    def test_saturday_confirmed_is_estimated(self):
        html = '<p>The next confirmed earnings date is Saturday, October 10, 2026.</p>'
        self.assertEqual(gc.sa_dates(html)[0]['status'], 'estimated')
        html = html.replace('Saturday, October 10', 'Sunday, October 11')   # Tadawul reports on Sundays
        self.assertEqual(gc.sa_dates(html)[0]['status'], 'confirmed')

    def test_no_sentence(self):
        self.assertEqual(gc.sa_dates('<p>No earnings date.</p>'), [])

    def test_urls(self):
        self.assertEqual(gc.sa_url('0700.HK'), 'https://stockanalysis.com/quote/hkg/0700/statistics/')
        self.assertEqual(gc.sa_url('ATCO-A.ST'), 'https://stockanalysis.com/quote/sto/ATCO.A/statistics/')
        self.assertEqual(gc.sa_url('005930.KS'), 'https://stockanalysis.com/quote/krx/005930/statistics/')
        self.assertEqual(gc.sa_url('600519.SS'), 'https://stockanalysis.com/quote/sha/600519/statistics/')
        self.assertEqual(gc.sa_url('NESN.SW'), 'https://stockanalysis.com/quote/swx/NESN/statistics/')
        self.assertEqual(gc.sa_url('AZN'), 'https://stockanalysis.com/stocks/azn/statistics/')
        self.assertIsNone(gc.sa_url('BRK.B'))   # a US class share, not a home-market suffix

    def test_targets(self):
        ts = gc.targets(RECORDS, nasdaq_symbols={'INFY'})   # Nasdaq lists INFY: not looked up again
        self.assertEqual([t['symbol'] for t in ts], ['AZN', 'MC.PA', 'NESN.SW', '2318.HK', '0700.HK'])
        self.assertEqual(ts[3]['url'], 'https://stockanalysis.com/quote/sha/601318/statistics/')   # SA_PAGE


class Hkex(unittest.TestCase):
    def test_rows(self):
        rows = gc.hkex_rows(page('hkex_ebmn.htm'))
        self.assertEqual(rows[0], {'day': '2026-10-08', 'code': 3991, 'purpose': 'INT DIV', 'period': ''})
        self.assertIn({'day': '2026-11-18', 'code': 700, 'purpose': '3RD QUARTER RES/DIV',
                       'period': '9-MTH-ENDED30/09/26'}, rows)

    def test_events(self):
        ts = gc.targets(RECORDS, set())
        evs = gc.hkex_events(gc.hkex_rows(page('hkex_ebmn.htm')), ts)
        # results meetings of our two HK names only: not the RMB counters (80700, 82318), dividends or CATL's 3750
        self.assertEqual([(e['symbol'], e['day'], e['status'], e['kind']) for e in evs],
                         [('2318.HK', '2026-10-28', 'confirmed', 'hkex'), ('0700.HK', '2026-11-18', 'confirmed', 'hkex')])


class IrFile(unittest.TestCase):
    IR: dict[str, list[gc.IrRow]] = {'lvmh': [{'date': '2026-10-12', 'event': '2026 Q3 revenue', 'timing': 'post',
                    'source': 'https://www.lvmh.com/en/financial-calendar/2026-q3-revenue'}]}

    def test_rows(self):
        e = gc.ir_events(self.IR, RECORDS)[0]
        self.assertEqual((e['symbol'], e['day'], e['timing'], e['status'], e['kind'], e['note']),
                         ('MC.PA', '2026-10-12', 'post', 'confirmed', 'ir', '2026 Q3 revenue'))
        self.assertEqual(gc.ir_problems(self.IR, RECORDS), [])

    def test_problems(self):
        bad: dict[str, list[gc.IrRow]] = {'nope': [{'date': '2026-13-01', 'event': 'x', 'source': 'http://x',
                                                     'timing': 'soon'}]}   # type: ignore[typeddict-item]
        self.assertEqual(len(gc.ir_problems(bad, RECORDS)), 4)   # slug, date, timing, source

    def test_the_repo_file_is_clean(self):
        import repodata as rd
        self.assertEqual(gc.ir_problems(gc.load_ir(rd.ROOT), rd.load_report_records(rd.ROOT)), [])

    def test_ir_beats_stockanalysis(self):
        t: gc.Target = {'slug': 'lvmh', 'symbol': 'MC.PA', 'url': 'u'}
        sa = gc.sa_events(t, [{'day': '2026-10-09', 'status': 'estimated', 'timing': 'unknown'},
                              {'day': '2027-01-27', 'status': 'estimated', 'timing': 'post'}])
        kept = gc.merge(sa + gc.ir_events(self.IR, RECORDS))
        self.assertEqual([(e['day'], e['kind']) for e in kept], [('2026-10-12', 'ir'), ('2027-01-27', 'stockanalysis')])


class Robots(unittest.TestCase):
    def test_disallowed_path_is_skipped(self):
        f, web = fetcher({'https://stockanalysis.com/robots.txt': 'User-agent: *\nDisallow: /quote/\n'})
        self.assertFalse(f.allowed('https://stockanalysis.com/quote/hkg/0700/statistics/'))
        self.assertTrue(f.allowed('https://stockanalysis.com/stocks/azn/statistics/'))
        self.assertEqual(web.calls, ['https://stockanalysis.com/robots.txt'])   # read once per host

    def test_missing_robots_allows_and_unreadable_blocks(self):
        f, _ = fetcher({'https://a.example/robots.txt': 404, 'https://b.example/robots.txt': 403})
        self.assertTrue(f.allowed('https://a.example/x'))
        self.assertFalse(f.allowed('https://b.example/x'))
        self.assertEqual(len(f.problems), 1)

    def test_pause_between_requests(self):
        waits: list[float] = []
        f = gc.Fetcher(get=FakeWeb({'https://a.example/1': '', 'https://a.example/2': ''}), sleep=waits.append)
        f.fetch('https://a.example/1')
        f.fetch('https://a.example/2')
        self.assertEqual(len(waits), 1)
        self.assertGreater(waits[0], 2.0)


class Run(unittest.TestCase):
    TODAY = D('2026-10-08')
    SA = 'https://stockanalysis.com'

    def web(self, robots='User-agent: *\nDisallow: /e/\n'):
        return {f'{self.SA}/robots.txt': robots, 'https://www3.hkexnews.hk/robots.txt': 404,
                gc.HKEX_BMN: page('hkex_ebmn.htm'),
                f'{self.SA}/quote/hkg/0700/statistics/': page('stockanalysis_0700_next_confirmed.html'),
                f'{self.SA}/quote/sha/601318/statistics/': '<title>Ping An</title><p>nothing</p>',
                f'{self.SA}/quote/swx/NESN/statistics/':
                    '<p>The next estimated earnings date is Thursday, February 18, 2027, before market open.</p>',
                f'{self.SA}/quote/epa/MC/statistics/':
                    '<p>The last earnings date was Monday, October 5, 2026, after market close.</p>',
                f'{self.SA}/stocks/azn/statistics/': 500}

    def test_collect_cache_and_prints(self):
        with tempfile.TemporaryDirectory() as cache:
            f, web = fetcher(self.web())
            day = gc.collect(RECORDS, set(), self.TODAY, cache, repo=cache, fetcher=f)
            self.assertEqual(day['failures'], [f'global azn: HTTP Error 500: status ({self.SA}/stocks/azn/statistics/)',
                                               f'global infy: HTTP Error 404: status ({self.SA}/stocks/infy/statistics/)'])
            self.assertEqual(gc.coverage(day)['missing'], ['AZN', 'INFY'])
            # a second run the same day reads the cache: only the pages that failed are asked for again
            f2, web2 = fetcher(self.web())
            gc.collect(RECORDS, set(), self.TODAY, cache, repo=cache, fetcher=f2)
            self.assertEqual([u for u in web2.calls if 'robots' not in u],
                             [f'{self.SA}/stocks/azn/statistics/', f'{self.SA}/stocks/infy/statistics/'])
            prints = gc.to_prints(day['events'], self.TODAY, ahead=14)
            self.assertEqual([(p['symbol'], p['day'], p['timing']) for p in prints], [('MC.PA', '2026-10-05', 'post')])
            self.assertEqual(set(prints[0]), set(q.Print.__annotations__))
            self.assertEqual(len(gc.to_prints(day['events'], self.TODAY, ahead=60)), 3)   # + 2318 and 0700 (HKEX)

    def test_robots_disallow_skips_the_page(self):
        with tempfile.TemporaryDirectory() as cache:
            f, web = fetcher(self.web(robots='User-agent: *\nDisallow: /quote/hkg/\n'))
            day = gc.collect(RECORDS, {'AZN', 'INFY'}, self.TODAY, cache, repo=cache, fetcher=f)
            self.assertEqual(day['robots_skipped'], [f'{self.SA}/quote/hkg/0700/statistics/'])
            self.assertFalse(any('/quote/hkg/' in u for u in web.calls))
            self.assertEqual(day['pages']['pingan']['title'], 'Ping An')

    def test_estimated_past_dates_are_dropped_and_earlier_confirmed_kept(self):
        ev = {'slug': 'x', 'symbol': 'X.PA', 'timing': 'unknown', 'kind': 'stockanalysis', 'source': 'u', 'note': ''}
        events = [{**ev, 'day': '2026-10-06', 'status': 'estimated'}, {**ev, 'slug': 'y', 'day': '2026-10-07', 'status': 'confirmed'}]
        self.assertEqual([p['day'] for p in gc.to_prints(events, self.TODAY, 14)], ['2026-10-07'])   # type: ignore[arg-type]
        earlier = gc.earlier_events({'date': '2026-10-07', 'events': events}, self.TODAY)
        self.assertEqual([(e['slug'], e['kind']) for e in earlier], [('y', 'earlier')])

    def test_queue_matches_title_ticker(self):
        lib = {q.norm('MC.PA'): {'slug': 'lvmh', 'ticker': 'MC.PA', 'as_of': '2026-10-02', 'ndx': False, 'dow': False,
                                 'mcap': None}}
        prints = gc.to_prints([{'slug': 'lvmh', 'symbol': 'MC.PA', 'day': '2026-10-05', 'timing': 'post',
                                'status': 'reported', 'kind': 'stockanalysis', 'source': 'u', 'note': ''}], self.TODAY, 14)
        items, _ = q.build_items(prints, lib, self.TODAY, closes_for=lambda slug, t: {})   # type: ignore[arg-type]
        self.assertEqual([(i['slug'], i['status'], i['t2']) for i in items], [('lvmh', 'due', '2026-10-07')])


if __name__ == '__main__':
    unittest.main()
