"""Unit tests for refresh_queue.py: the trading calendar, T+2, the calendar parser, tiering and status.
Run: py -3 tools/run_checks.py"""
import datetime
import unittest

import refresh_queue as q

D = datetime.date.fromisoformat


def row(symbol, time='time-not-supplied', eps='', fc='', surprise='N/A'):
    return {'symbol': symbol, 'time': time, 'eps': eps, 'epsForecast': fc, 'surprise': surprise,
            'fiscalQuarterEnding': 'Aug/2026'}


def holding(slug, ticker, as_of, ndx=False, dow=False, mcap=50e9):
    return {'slug': slug, 'ticker': ticker, 'as_of': as_of, 'ndx': ndx, 'dow': dow, 'mcap': mcap}


class Calendar(unittest.TestCase):
    def test_sessions(self):
        self.assertFalse(q.is_session(D('2026-11-26')))   # Thanksgiving
        self.assertTrue(q.is_session(D('2026-11-27')))    # early close is still a session
        self.assertEqual(q.next_session(D('2026-09-04')), D('2026-09-08'))   # over Labor Day
        self.assertEqual(q.prev_session(D('2026-09-08')), D('2026-09-04'))
        self.assertEqual(q.sessions_between(D('2026-09-23'), D('2026-09-29')), 4)

    def test_t2(self):
        self.assertEqual(q.t2_date(D('2026-09-23'), 'pre'), D('2026-09-24'))    # GIS: sessions D and D+1
        self.assertEqual(q.t2_date(D('2026-09-24'), 'post'), D('2026-09-28'))   # COST: Fri and Mon
        self.assertEqual(q.t2_date(D('2026-09-24'), 'unknown'), D('2026-09-28'))   # unknown = the later case
        self.assertEqual(q.t2_date(D('2026-11-25'), 'post'), D('2026-11-30'))   # over Thanksgiving
        self.assertEqual(q.t2_date(D('2026-10-03'), 'pre'), D('2026-10-06'))    # a Saturday release

    def test_parse(self):
        body = {'data': {'rows': [row('CTAS', 'time-pre-market', '$1.39', '$1.35', '2.96'),
                                  row('MANU', eps='($0.22)'), row('brk.b', 'time-after-hours')]}}
        ps = q.parse_calendar(body, '2026-09-23')
        self.assertEqual([p['timing'] for p in ps], ['pre', 'unknown', 'post'])
        self.assertEqual((ps[0]['eps'], ps[0]['eps_forecast'], ps[0]['surprise_pct']), (1.39, 1.35, 2.96))
        self.assertEqual(ps[1]['eps'], -0.22)
        self.assertIsNone(ps[1]['surprise_pct'])
        self.assertEqual(q.norm(ps[2]['symbol']), 'BRKB')
        self.assertEqual(q.parse_calendar({'data': None}, '2026-09-26'), [])   # a weekend answers with no data

    def test_keep_known_times(self):
        cached = {'data': {'rows': [row('CCL', 'time-pre-market')]}}
        fresh = {'data': {'rows': [row('CCL'), row('JBL', 'time-pre-market')]}}
        times = [r['time'] for r in q.keep_known_times(fresh, cached)['data']['rows']]
        self.assertEqual(times, ['time-pre-market', 'time-pre-market'])


class Queue(unittest.TestCase):
    CLOSES = {D('2026-09-22'): 100.0, D('2026-09-23'): 91.0, D('2026-09-24'): 92.0, D('2026-09-25'): 93.0}

    def test_first_move(self):
        self.assertAlmostEqual(q.first_move_pct(self.CLOSES, D('2026-09-23'), 'pre'), -9.0)
        self.assertAlmostEqual(q.first_move_pct(self.CLOSES, D('2026-09-23'), 'post'), 1.0989, places=3)
        self.assertAlmostEqual(q.first_move_pct(self.CLOSES, D('2026-09-23'), 'unknown'), -9.0)   # the larger
        self.assertIsNone(q.first_move_pct({}, D('2026-09-23'), 'pre'))

    def test_tier(self):
        p = q.parse_calendar({'data': {'rows': [row('X', eps='$1.10', fc='$1.00', surprise='10.0')]}}, '2026-09-23')[0]
        self.assertEqual(q.tier(holding('x', 'X', '2026-09-01'), p, 1.0), ('T1', ['EPS surprise +10.0%']))
        p['surprise_pct'] = 2.0
        self.assertEqual(q.tier(holding('x', 'X', '2026-09-01'), p, -4.9), ('T2', []))
        self.assertEqual(q.tier(holding('x', 'X', '2026-09-01', dow=True, mcap=250e9), p, -5.0)[1],
                         ['Dow 30', 'mega-cap $250B', 'first-session move -5.0%'])

    def test_status(self):
        rel = D('2026-09-23')
        t2 = q.t2_date(rel, 'pre')   # Sep 24
        self.assertEqual(q.status_of(D('2026-10-01'), D('2026-10-02'), D('2026-09-30'))[0], 'upcoming')
        self.assertEqual(q.status_of(rel, t2, D('2026-09-24'))[0], 'waiting')   # T+2 close not settled yet
        self.assertEqual(q.status_of(rel, t2, D('2026-09-25')), ('due', 1))       # one session closed since
        self.assertEqual(q.status_of(rel, t2, D('2026-09-30')), ('due', 4))       # lands on day 5
        self.assertEqual(q.status_of(rel, t2, D('2026-10-01')), ('overdue', 5))   # would land on day 6

    def test_build_items(self):
        lib = {'GIS': holding('gis', 'GIS', '2026-09-21'), 'AZO': holding('azo', 'AZO', '2026-09-23'),
               'MU': holding('mu', 'MU', '2026-08-10', ndx=True)}
        cal = [('2026-09-22', row('AZO')), ('2026-09-23', row('GIS', 'time-pre-market', '$0.75', '$0.72', '4.17')),
               ('2026-09-30', row('MU', 'time-after-hours')), ('2026-09-23', row('NOTOURS'))]
        prints = [p for day, r in cal for p in q.parse_calendar({'data': {'rows': [r]}}, day)]
        items, covered = q.build_items(prints, lib, D('2026-09-28'), closes_for=lambda slug, t: self.CLOSES)
        self.assertEqual(covered, 1)   # AZO's page already postdates its print
        self.assertEqual([(i['ticker'], i['status'], i['tier']) for i in items],
                         [('GIS', 'due', 'T1'), ('MU', 'upcoming', 'T1')])   # GIS: first-session move -9%
        self.assertEqual(items[0]['t2'], '2026-09-24')
        self.assertEqual(items[0]['triggers'], ['first-session move -9.0%'])


if __name__ == '__main__':
    unittest.main()
