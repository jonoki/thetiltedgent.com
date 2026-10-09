"""Unit tests for refresh_data.py: the computations on hand-worked series, the chart's month-end extension (with a
split and a spin-off), the Yahoo and Nasdaq parsers on saved responses, stale hits, and the pre- and post-pass on a
made-up page.   Run: py -3 tools/run_checks.py"""
import contextlib
import datetime
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import reportlib as rl
import refresh_data as rdt

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def load(name: str) -> dict:
    with open(os.path.join(DATA, name), encoding='utf-8') as fh:
        return json.load(fh)


def bars(closes: dict[str, float]) -> list[rdt.Day]:
    """Bars with a high 1 above and a low 1 below the close."""
    return [rdt.Day(d, c + 1, c - 1, c) for d, c in sorted(closes.items())]


class Computations(unittest.TestCase):
    def test_years_before(self):
        self.assertEqual(rdt.years_before('2026-10-01'), '2025-10-01')
        self.assertEqual(rdt.years_before('2028-02-29'), '2027-02-28')
        self.assertEqual(rdt.years_before('2026-10-01', 5), '2021-10-01')

    def test_settled_as_of_never_takes_a_session_still_trading(self):
        days = bars({'2026-09-30': 1, '2026-10-01': 2})
        ny = -4 * 3600
        at = lambda s: datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.UTC)
        self.assertEqual(rdt.settled_as_of(days, at('2026-10-02T09:45'), ny), '2026-10-01')   # next morning
        self.assertEqual(rdt.settled_as_of(days, at('2026-10-01T22:00'), ny), '2026-09-30')   # 18:00 New York
        self.assertEqual(rdt.settled_as_of(days, at('2026-10-02T00:30'), ny), '2026-10-01')   # 20:30 New York
        with self.assertRaises(ValueError):
            rdt.settled_as_of(days, at('2026-09-30T12:00'), ny)

    def test_range_52w_window_is_after_the_date_a_year_back(self):
        days = [rdt.Day('2025-10-01', 99.0, 1.0, 50.0),            # exactly a year back: outside
                rdt.Day('2025-10-02', 60.0, 40.0, 50.0), rdt.Day('2026-02-06', 70.0, 45.0, 60.0),
                rdt.Day('2026-05-01', 65.0, 40.0, 55.0),              # ties the low: the first day wins
                rdt.Day('2026-10-01', 56.0, 50.0, 55.0), rdt.Day('2026-10-02', 200.0, 0.5, 9.0)]   # after the as-of
        self.assertEqual(rdt.range_52w(days, '2026-10-01'),
                         {'low': 40.0, 'low_date': '2025-10-02', 'high': 70.0, 'high_date': '2026-02-06',
                          'window': ['2025-10-02', '2026-10-01']})
        self.assertEqual(rdt.range_52w(days, '2026-10-01', 2.0)['high'], 140.0)   # a split after the as-of

    def test_price_return_takes_the_last_close_on_or_before_the_base_date(self):
        days = bars({'2025-09-26': 100, '2026-10-01': 125})   # 2025-09-27/28 are a weekend
        self.assertEqual(rdt.price_return(days, '2026-10-01', '2025-09-28'),
                         {'base_date': '2025-09-26', 'base_close': 100, 'close': 125, 'pct': 25.0})
        self.assertIsNone(rdt.price_return(days, '2026-10-02', '2025-09-28'))   # no close on the as-of

    def test_rsi_by_hand(self):
        # changes +1, -1, +2 with period 2: first averages 0.5 / 0.5, then gain (0.5+2)/2 = 1.25, loss 0.5/2 = 0.25,
        # RS 5, RSI 100 - 100/6 = 83.33
        self.assertEqual(rdt.rsi([10, 11, 10, 12], 2), 83.33)
        self.assertEqual(rdt.rsi([1, 2, 3, 4], 2), 100.0)
        self.assertIsNone(rdt.rsi([1, 2], 2))

    def test_sma(self):
        self.assertEqual(rdt.sma([1, 2, 3, 4, 5], 3), 4.0)
        self.assertIsNone(rdt.sma([1, 2], 3))

    def test_dividends(self):
        divs = [('2025-08-08', 0.10), ('2026-02-13', 0.15), ('2026-05-18', 0.15), ('2026-08-07', 0.15)]
        f = rdt.dividend_facts(divs, '2026-10-01', 25.0)
        self.assertEqual((f['ttm'], f['frequency'], f['annualised']), (0.45, 4, 0.6))   # CCL: reinstated in 2026
        self.assertEqual(f['yield_annualised_pct'], 2.4)
        self.assertEqual(rdt.dividend_facts(divs, '2026-09-01', 25.0, 2.0)['last'], ['2026-08-07', 0.3])
        stale = rdt.dividend_facts([('2020-01-02', 1.0), ('2020-04-02', 1.0)], '2026-10-01', 10.0)
        self.assertEqual((stale['ttm'], stale['annualised']), (0, None))           # suspended
        self.assertEqual(rdt.dividend_frequency([('2026-01-01', 1), ('2026-01-31', 1)]), 12)
        self.assertEqual(rdt.dividend_frequency([('2025-01-01', 1), ('2026-01-01', 1)]), 1)

    def test_yield_basis(self):
        div = {'ttm': 0.45, 'annualised': 0.60}
        self.assertEqual(rdt.yield_basis(2.42, 2, 24.76, div), 'annualised')    # CCL's previous edition
        self.assertEqual(rdt.yield_basis(1.82, 2, 24.76, div), 'ttm')
        self.assertIsNone(rdt.yield_basis(3.10, 2, 24.76, div))
        self.assertEqual(rdt.yield_basis(0.11, 2, 299.57, {'ttm': 0.32, 'annualised': 0.32}), 'ttm')   # JBL: equal
        self.assertIsNone(rdt.yield_basis(2.4, 1, 24.76, {'ttm': 0.594, 'annualised': 0.60}))   # both fit at 1 dp

    def test_yield_formula_and_cells(self):
        self.assertEqual(rdt.yield_formula('$0.60 annualised ÷ $25.07. Reinstated at $0.15'), (0.6, 25.07))
        self.assertEqual(rdt.yield_formula('$1.16 × 4 = $4.64 ÷ $1,277.61'), (4.64, 1277.61))
        self.assertIsNone(rdt.yield_formula('Token; buybacks instead.'))
        self.assertEqual(rdt.cell_number('24.1x'), (24.1, 1))
        self.assertEqual(rdt.cell_number('99.9× (GAAP)'), (99.9, 1))
        self.assertEqual(rdt.cell_number('2.39%'), (2.39, 2))
        for bad in ('n/m', 'None (0.00%)', '~257x', '70.3x (n/m)', None):
            self.assertIsNone(rdt.cell_number(bad), bad)

    def test_header_mcap(self):
        t = '<span style="color:var(--text-dim);">Mkt Cap:</span> ~$33.7B</span>'
        self.assertEqual(rdt.header_mcap(t), ('~$33.7B', 33.7e9))
        self.assertEqual(rdt.header_mcap('<span class="lbl">Mkt Cap:</span><b>$1.25T</b>'), ('$1.25T', 1.25e12))


DAILY = bars({'2026-07-30': 27.0, '2026-07-31': 27.81, '2026-08-28': 24.76, '2026-08-31': 23.89,
              '2026-09-18': 30.0, '2026-09-30': 24.54, '2026-10-01': 25.07})


class Chart(unittest.TestCase):
    def test_month_labels(self):   # CCL: Aug '26 (the Aug 28 as-of) becomes the Aug 31 month-end
        got = rdt.extend_series(["Jul '26", "Aug '26"], [27.81, 24.76], '2026-08-28', '2026-10-01', DAILY, 1.0, [])
        self.assertEqual(got['labels'], ["Jul '26", "Aug '26", "Sep '26", "Oct '26"])
        self.assertEqual(got['prices'], [27.81, 23.89, 24.54, 25.07])
        self.assertEqual([p['date'] for p in got['replaced'] + got['appended']], ['2026-08-31', '2026-09-30', '2026-10-01'])

    def test_day_label(self):     # JBL: 'Sep 18 26' becomes 'Sep 26', and the as-of point keeps its day
        got = rdt.extend_series(['Aug 26', 'Sep 18 26'], [23.89, 30.0], '2026-09-18', '2026-10-01', DAILY, 1.0, [])
        self.assertEqual(got['labels'], ['Aug 26', 'Sep 26', 'Oct 1 26'])
        self.assertEqual(got['prices'], [23.89, 24.54, 25.07])

    def test_same_month(self):
        got = rdt.extend_series(['Aug 26', 'Sep 18 26'], [23.89, 30.0], '2026-09-18', '2026-09-30', DAILY, 1.0, [])
        self.assertEqual((got['labels'], got['prices']), (['Aug 26', 'Sep 30 26'], [23.89, 24.54]))
        self.assertEqual(got['replaced'][0]['old_value'], 30.0)
        self.assertEqual(got['appended'], [])

    def test_a_split_between_the_editions_rescales_the_kept_points(self):
        # a 2:1 split on Sep 10: Yahoo's closes are post-split, so the page's older points are halved
        got = rdt.extend_series(["Jul '26", "Aug '26"], [55.62, 49.52], '2026-08-28', '2026-10-01', DAILY, 1.0,
                                [('2026-09-10', 2.0)])
        self.assertEqual(got['prices'], [27.81, 23.89, 24.54, 25.07])
        self.assertEqual(got['split_rescale'], {'ratio': 2.0, 'splits': [('2026-09-10', 2.0)]})

    def test_a_split_after_the_as_of_and_a_spin_off(self):
        got = rdt.extend_series(["Jul '26", "Aug '26"], [55.62, 49.52], '2026-08-28', '2026-10-01', DAILY, 2.0,
                                [('2026-09-10', 1.1), ('2026-12-01', 2.0)])
        self.assertEqual(got['prices'], [55.62, 47.78, 49.08, 50.14])   # Yahoo x 2 (split after the as-of)
        self.assertIsNone(got['split_rescale'])                          # a spin is not rescaled (it is flagged)

    def test_refused(self):
        for labels, why in ((["Jun '26", "Aug '26"], 'consecutive'), (['Jul 1', 'Jul 2'], 'not read'),
                            (["Sep '26", "Nov '26"], 'consecutive'), (["Oct '26", "Nov '26"], 'past the as-of'),
                            (['Aug 1 26', 'Sep 18 26'], 'not a month label')):
            with self.assertRaises(rdt.ChartError) as e:
                rdt.extend_series(labels, [1.0, 2.0], '2026-09-18', '2026-10-01', DAILY, 1.0, [])
            self.assertIn(why, str(e.exception))


class Parsers(unittest.TestCase):
    def test_yahoo_daily(self):
        d = rdt.parse_daily(load('yahoo_daily_ccl.json'), 'u', 't')
        self.assertEqual((d.days[0].date, d.days[-1].date, len(d.days)), ('2026-07-28', '2026-10-01', 47))
        self.assertEqual(d.days[-1], rdt.Day('2026-10-01', 25.17, 24.52, 25.07))
        self.assertEqual(d.dividends[-1], ('2026-08-07', 0.15))
        self.assertEqual((d.splits, d.gmtoffset), ([], -14400))
        w = rdt.range_52w(d.days, '2026-10-01')
        self.assertEqual((w['low'], w['low_date']), (21.45, '2026-09-24'))   # CCL's published low
        with self.assertRaises(rdt.ca.YahooError):
            rdt.parse_daily({'chart': {'result': []}})

    def test_short_interest(self):
        body = load('nasdaq_short_interest_csco.json')
        self.assertEqual(rdt.parse_short_interest(body, '2026-10-01'),
                         {'value': 57677354.0, 'settlement_date': '2026-09-15', 'avg_daily_volume': 13041446.0,
                          'days_to_cover': 4.42})
        self.assertEqual(rdt.parse_short_interest(body, '2026-09-10')['settlement_date'], '2026-08-31')
        self.assertIsNone(rdt.parse_short_interest(body, '2026-01-01')['value'])
        nyse = rdt.parse_short_interest(load('nasdaq_short_interest_nyse.json'), '2026-10-01')
        self.assertIn('only supported for Nasdaq Listed', nyse['note'])

    def test_surprises(self):
        body = load('nasdaq_earnings_surprise_fds.json')
        got = rdt.parse_surprises(body, '2026-10-01')
        self.assertEqual(got[0], {'fiscal_quarter_end': 'Aug 2026', 'reported': '2026-09-30', 'eps': 4.52,
                                  'consensus': 4.32, 'surprise_pct': 4.63})
        self.assertEqual(len(got), 4)
        self.assertEqual(rdt.parse_surprises(body, '2026-09-29')[0]['reported'], '2026-07-01')   # nothing after the as-of


PAGE = """<!DOCTYPE html>
<html lang="en"><head><title>CCL — Carnival Corporation Ltd. | Stock Analysis</title><style>.x{}</style></head>
<body>
<div>⚠ Static data as of August 28, 2026 close — prices, metrics, and analyst targets will not update</div>
<span>Mkt Cap:</span> ~$34.0B</span>
<div class="price-current">$24.76</div>
<div class="price-change">−$0.19 (−0.76%)</div>
<section class="tg-d tg-d--print" data-prior-as-of="2026-07-01" data-prior-price="27.00" data-as-of="2026-08-28" data-price="24.76"><p>$24.76</p></section>
<table class="fin-table"><tbody>
<tr><td>Trailing P/E</td><td>11.36</td><td>—</td><td>$24.76 ÷ $2.18 = 11.36</td></tr>
<tr><td>EPS (TTM)</td><td>$2.18</td><td>—</td><td>adjusted</td></tr>
<tr><td>Dividend Yield</td><td>2.42%</td><td>—</td><td>$0.60 annualised ÷ $24.76.</td></tr>
<tr><td>52-Week Range</td><td>$23.45 – $34.03</td><td>—</td><td>At $24.76 the stock is above the $23.45 low</td></tr>
</tbody></table>
<p>The stock closed August 28 at $24.76.</p>
<div>RSI — STATIC DATA AS OF AUGUST 28, 2026</div>
<canvas></canvas><canvas></canvas>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
const labels = ['Jun \\'26','Jul \\'26','Aug \\'26'];
const prices = [26.51,27.81,24.76];
</script>
</body></html>
"""


def built(page: str = PAGE) -> tuple[dict, str]:
    daily = rdt.parse_daily(load('yahoo_daily_ccl.json'), 'https://yahoo/ccl', '2026-10-02T09:45:00+00:00')
    return rdt.build('ccl', page, daily, '2026-10-01', {'SPY': 'skipped', 'QQQ': 'skipped'},
                     (load('nasdaq_short_interest_nyse.json'), 'now'), 'offline', 'offline')


class PrePass(unittest.TestCase):
    def test_build(self):
        facts, new = built()
        f = facts['fields']
        self.assertEqual(facts['written'], ['header_price', 'banner_date', 'chart', 'change', 'range_52w',
                                            'trailing_pe', 'dividend_yield'])
        self.assertEqual(facts['previous_edition'], {'as_of': '2026-08-28', 'price': 24.76,
                                                     'source': 'the page before this run'})
        self.assertEqual((rl.header_price(new), rl.as_of(new)[0]), (25.07, '2026-10-01'))
        self.assertEqual(rl.chart_series(new), (["Jun '26", "Jul '26", "Aug '26", "Sep '26", "Oct '26"],
                                                [26.51, 27.81, 23.89, 24.54, 25.07]))
        self.assertIn('<div class="price-change" style="color:var(--green);">+$0.53 (+2.16%)</div>', new)
        self.assertIn('STATIC DATA AS OF OCTOBER 1, 2026', new)
        self.assertIn('<td>11.50</td>', new)        # 25.07 / the page's (old) $2.18; the post-pass redoes it
        self.assertIn('<td>2.39%</td>', new)        # $0.60 / 25.07, from the page's own formula
        self.assertEqual(f['dividend_yield']['page_basis'], 'formula')
        self.assertEqual(rl.range_52w(new), [21.45, 30.22])   # the fixture starts Jul 28: its high is Aug 5
        self.assertIn('Nasdaq Listed', f['short_interest']['note'])
        self.assertEqual(f['eps_surprise']['note'], 'offline')
        self.assertEqual(f['return_1y']['value']['SPY'], {'error': 'skipped'})
        self.assertIn('ESTIMATE', f['market_cap_estimate']['basis'])
        for name, fld in f.items():
            if isinstance(fld, dict):
                self.assertTrue({'value', 'source', 'fetched_at', 'as_of', 'basis'} <= fld.keys(), name)
        self.assertIn('The stock closed August 28 at $24.76.', new)   # prose is never written

    def test_a_core_field_that_cannot_be_written_writes_nothing(self):
        facts, new = built(PAGE.replace('<div class="price-current">$24.76</div>',
                                        '<div class="price-current">$24.76</div><div class="price-current">$1.00</div>'))
        self.assertEqual(facts['written'], [])
        self.assertEqual(set(facts['not_written']), {'header_price', 'banner_date', 'chart'})
        self.assertIn('Static data as of August 28, 2026', new)

    def test_stale_hits(self):
        facts, new = built()
        hits = rdt.stale_hits(new, rdt.stale_patterns(facts['page_before'], facts['new_values']))
        kinds = [h.split(' | ')[0] for h in hits]
        self.assertIn("L10: old header price 24.76 = old chart value Aug '26 24.76", kinds)   # the P/E formula
        self.assertTrue(any('old 52-week low 23.45' in k for k in kinds))
        self.assertTrue(any(h.startswith('L15: old as-of date 2026-08-28') for h in hits))   # 'closed August 28'
        self.assertFalse(any(h.startswith('L7:') for h in hits))      # the delta box is left alone
        self.assertFalse(any(h.startswith('L21:') for h in hits))     # and so are the chart arrays


T_DAYS = rdt.parse_daily(load('yahoo_daily_t_monthends.json'), 'https://yahoo/t', 'now')   # T: WBD spin 2022-04-11


def t_close(y: int, m: int) -> float:
    return round(rdt.month_end(T_DAYS.days, y, m).close, 2)


def t_adj(y: int, m: int) -> float:
    return round(rdt.month_end(T_DAYS.days, y, m).adj, 2)


class FixPoints(unittest.TestCase):
    """--fix-points on a saved Yahoo response (T month-ends, Sep 2021 – Oct 2026, with adjclose and the spin)."""
    MONTHS = [(2022, m) for m in range(4, 13)] + [(2023, m) for m in range(1, 4)]   # 12 months after the spin

    def fix(self, labels, prices, days=None, factor=1.0, labelled=False):
        return rdt.fix_points(labels, prices, list(range(len(labels))), days or T_DAYS.days, factor, T_DAYS.splits,
                              '2026-10-01', labelled, 'https://yahoo/t')

    def test_close_basis(self):
        self.assertEqual(rdt.parse_daily(load('yahoo_daily_t_monthends.json')).splits, [('2022-04-11', 1.324)])
        labels = ['Oct 21', 'Mar 22', 'Apr 22', 'May 22', 'Jun 22', 'Oct 1 26']
        prices = [19.06,                      # spin-adjusted, 2 cents off Yahoo's 19.08: wrong (rule A)
                  round(t_close(2022, 3) * 1.324, 2),   # the real pre-spin close: a basis step, left alone
                  t_close(2022, 4),           # right: untouched
                  21.60,                      # 1.5% off Yahoo's 21.29: wrong
                  15.00,                      # June 2022 is missing from the days given: never touched
                  24.30]
        days = [d for d in T_DAYS.days if d.date[:7] != '2022-06']
        got = rdt.fix_points(labels, prices, [0, 1, 2, 3, 4], days, 1.0, T_DAYS.splits, '2026-10-01', False, 'u')
        self.assertEqual([(f['month'], f['old'], f['new'], f['date']) for f in got['fixed']],
                         [('Oct 21', 19.06, 19.08, '2021-10-29'), ('May 22', 21.60, 21.29, '2022-05-31')])
        self.assertEqual(got['fixed'][0]['source'], 'u')
        self.assertEqual(prices, [19.08, 23.63, 18.86, 21.29, 15.00, 24.30])
        self.assertEqual((got['basis'], got['compared'], got['skipped']),
                         ('close', 3, {'no Yahoo month': ['Jun 22'], 'basis step': ['Mar 22']}))

    def test_a_labelled_dividend_adjusted_series_is_compared_with_adjclose(self):
        labels = [f'{rdt.rp.MON3[m - 1]} {y % 100}' for y, m in self.MONTHS]
        prices = [t_adj(y, m) for y, m in self.MONTHS]
        prices[2] = t_close(2022, 6)          # one point on the close: wrong for an adjusted series
        got = self.fix(labels, prices, labelled=True)
        self.assertEqual(got['basis'], 'adjclose')
        self.assertEqual([(f['month'], f['new']) for f in got['fixed']], [('Jun 22', t_adj(2022, 6))])
        self.assertIn('adjclose', got['fixed'][0]['basis'])
        self.assertIsNone(got['note'])

    def test_an_unlabelled_adjusted_series_is_put_on_the_close(self):
        labels = [f'{rdt.rp.MON3[m - 1]} {y % 100}' for y, m in self.MONTHS]
        prices = [t_adj(y, m) for y, m in self.MONTHS]
        got = self.fix(labels, prices, labelled=False)
        self.assertEqual((got['basis'], len(got['fixed'])), ('close', 12))
        self.assertEqual(prices, [t_close(y, m) for y, m in self.MONTHS])
        self.assertIn('rebased to the close', got['note'])

    def test_a_split_after_the_as_of_leaves_every_point(self):
        prices = [19.06, 21.60]
        got = self.fix(['Oct 21', 'May 22'], prices, factor=2.0)
        self.assertEqual((got['fixed'], prices, got['skipped']), ([], [19.06, 21.60],
                                                                  {'split after the as-of': ['Oct 21', 'May 22']}))

    def test_window_drop(self):
        self.assertEqual((rdt.window_drop(62, 61), rdt.window_drop(61, 61), rdt.window_drop(40, 61),
                          rdt.window_drop(62, 0)), (1, 0, 0, 0))


# CTVA-like: a spin-off Yahoo books as a large "split" (chart_audit.SPINOFFS). Yahoo's daily closes before it are
# spin-adjusted (the real close / 6.665); the previous edition (Aug 28 as-of) charted the real pre-spin closes.
SPIN = ('2026-10-01', 6.665)
SPIN_SPLITS = [SPIN]
SPIN_DAYS = bars({'2026-07-31': 10.00, '2026-08-28': 9.50, '2026-08-31': 9.60, '2026-09-30': 9.80,
                  '2026-10-01': 13.10, '2026-10-02': 13.40})


class DeclaredSpinOff(unittest.TestCase):
    """A declared spin-off is never a real split: the chart, --fix-points and build() handle it as chart_audit does."""

    def test_the_chart_is_not_rescaled_and_new_pre_spin_month_ends_go_on_the_real_basis(self):
        got = rdt.extend_series(["Jul '26", "Aug '26"], [66.65, 63.32], '2026-08-28', '2026-10-02', SPIN_DAYS, 1.0,
                                SPIN_SPLITS, SPIN)
        self.assertEqual(got['labels'], ["Jul '26", "Aug '26", "Sep '26", "Oct '26"])
        self.assertEqual(got['prices'], [66.65, 63.98, 65.32, 13.40])   # 9.60 and 9.80 x 6.665; post-spin as is
        self.assertIsNone(got['split_rescale'])
        self.assertEqual(got['spin_crossed'], {'date': '2026-10-01', 'factor': 6.665})

    def test_undeclared_the_same_ratio_is_a_real_split(self):   # chart_audit's rule for any large ratio
        got = rdt.extend_series(["Jul '26", "Aug '26"], [66.65, 63.32], '2026-08-28', '2026-10-02', SPIN_DAYS, 1.0,
                                SPIN_SPLITS)
        self.assertEqual(got['prices'], [10.0, 9.6, 9.8, 13.4])
        self.assertEqual(got['split_rescale'], {'ratio': 6.665, 'splits': SPIN_SPLITS})
        self.assertIsNone(got['spin_crossed'])

    def test_before_the_spin_it_is_a_plain_split_after_the_as_of(self):
        got = rdt.extend_series(["Jul '26", "Aug '26"], [66.65, 63.32], '2026-08-28', '2026-09-30', SPIN_DAYS, 6.665,
                                SPIN_SPLITS, SPIN)
        self.assertEqual((got['prices'], got['spin_crossed']), ([66.65, 63.98, 65.32], None))

    def test_a_later_refresh_keeps_whichever_basis_the_page_charts(self):
        got = rdt.extend_series(["Sep '26", 'Oct 1 26'], [65.32, 13.10], '2026-10-01', '2026-10-02', SPIN_DAYS, 1.0,
                                SPIN_SPLITS, SPIN)
        self.assertEqual((got['prices'], got['spin_crossed'], got['split_rescale']), ([65.32, 13.40], None, None))

    def fix(self, prices, spin=SPIN, as_of='2026-10-02'):
        return rdt.fix_points(['Jul 26', 'Aug 26', 'Sep 26'], prices, [0, 1, 2], SPIN_DAYS,
                              rdt.ca.splits_after(SPIN_SPLITS, as_of), SPIN_SPLITS, as_of, False, 'u', spin)

    def test_fix_points_leaves_real_pre_spin_closes(self):
        prices = [66.65, 63.98, 65.32]
        got = self.fix(prices)
        self.assertEqual((got['fixed'], prices), ([], [66.65, 63.98, 65.32]))
        self.assertEqual(got['skipped'], {'basis step': ['Jul 26', 'Aug 26', 'Sep 26']})

    def test_fix_points_compares_a_spin_adjusted_chart_with_yahoo(self):
        prices = [10.00, 9.61, 9.80]
        got = self.fix(prices)
        self.assertEqual(([(f['month'], f['new']) for f in got['fixed']], got['compared']), ([('Aug 26', 9.6)], 3))

    def test_undeclared_fix_points_would_pull_real_closes_down(self):   # what the declaration prevents
        prices = [66.65, 63.98, 65.32]
        self.fix(prices, spin=None)
        self.assertEqual(prices, [10.0, 9.6, 9.8])

    def test_fix_points_before_the_spin_skips_every_point(self):   # factor 6.665: a split after the as-of
        self.assertEqual(self.fix([66.65, 63.98, 65.32], as_of='2026-09-30')['skipped'],
                         {'split after the as-of': ['Jul 26', 'Aug 26'], 'the as-of month': ['Sep 26']})

    def test_build_warns_and_checks_on_the_daily_feed(self):
        daily = rdt.parse_daily(load('yahoo_daily_ccl.json'), 'https://yahoo/ccl', 'now')._replace(
            splits=[('2026-09-15', 6.665)])
        monthly = ({(2026, 6): (26.51 / 6.665, None), (2026, 7): (27.81 / 6.665, None)}, daily.splits)
        with mock.patch.dict(rdt.ca.SPINOFFS, {'ccl': ('2026-09-15', 6.665)}):
            facts, new = rdt.build('ccl', PAGE, daily, '2026-10-01', {'SPY': 'skipped', 'QQQ': 'skipped'},
                                   'offline', 'offline', monthly)
        chart = facts['fields']['chart']
        self.assertEqual(rl.chart_series(new)[1], [26.51, 27.81, round(23.89 * 6.665, 2), 24.54, 25.07])
        self.assertIsNone(chart['split_rescale'])
        self.assertEqual(chart['spin_crossed'], {'date': '2026-09-15', 'factor': 6.665})
        check = chart['existing_points_check']
        self.assertEqual((check['wrong'], check['basis_steps']), ([], 2))   # real pre-spin closes: basis steps
        self.assertIn('interval=1d', check['source'])
        self.assertTrue(any(w.startswith('declared spin-off 2026-09-15') for w in facts['warnings']))


PAGE_W = (PAGE.replace("const prices = [26.51,27.81,24.76];\n",
                       "const prices = [26.51,27.50,24.76];\nconst events = [\n  { idx: 0, label: 'Jun 2026 start' },"
                       "\n  { idx: 1, label: 'Jul 2026 $27.50' },\n  { idx: 2, label: 'Aug 2026 close' }\n];\n")
          .replace('<p>The stock closed August 28 at $24.76.</p>',
                   '<p>The stock closed August 28 at $24.76. Over five years, from $26.51 in June 2026, it fell 6.6%; '
                   'July closed at $27.50.</p>'))


class ChartWindow(unittest.TestCase):
    """build() with the window trim and --fix-points: the page, facts.json, stale hits and the summary line."""

    def setUp(self):
        daily = rdt.parse_daily(load('yahoo_daily_ccl.json'), 'https://yahoo/ccl', '2026-10-02T09:45:00+00:00')
        self.jul = round(rdt.month_end(daily.days, 2026, 7).close, 2)
        self.facts, self.new = rdt.build('ccl', PAGE_W, daily, '2026-10-01', {'SPY': 'skipped', 'QQQ': 'skipped'},
                                         'offline', 'offline', 'offline', window=4, fix=True)

    def test_page(self):
        self.assertEqual(rl.chart_series(self.new), (["Jul '26", "Aug '26", "Sep '26", "Oct '26"],
                                                     [self.jul, 23.89, 24.54, 25.07]))
        self.assertIn("const events = [\n  { idx: 0, label: 'Jul 2026 $27.50' },\n  { idx: 1, label: 'Aug 2026 close' }\n];",
                      self.new)
        self.assertIn('it fell 6.6%', self.new)     # prose is never written

    def test_facts(self):
        f = self.facts
        trim = f['fields']['chart']['trim']
        self.assertEqual((trim['dropped'], trim['events_kept'], trim['events_dropped']),
                         (1, 2, [{'idx': 0, 'label': 'Jun 2026 start'}]))
        self.assertEqual(trim['dropped_points'], [{'label': "Jun '26", 'value': 26.51}])
        self.assertEqual([(p['month'], p['old'], p['new']) for p in f['fixed_points']], [("Jul '26", 27.50, self.jul)])
        rc = f['fields']['return_chart']
        self.assertEqual((rc['start_label'], rc['start_value'], rc['start_date'], rc['points']),
                         ("Jul '26", self.jul, '2026-07-31', 4))
        self.assertEqual(rc['pct_on_chart'], round((25.07 / self.jul - 1) * 100, 2))
        self.assertEqual(f['previous_window'], {'start_label': "Jun '26", 'start_value': 26.51, 'as_of': '2026-08-28',
                                                'price': 24.76, 'pct': -6.6, 'points': 3, 'prose_forms': ['6.6']})

    def test_stale_hits_and_summary(self):
        hits = rdt.stale_hits(self.new, rdt.stale_patterns(self.facts['page_before'], self.facts['new_values']))
        kinds = [h.split(' | ')[0] for h in hits]
        self.assertIn(f"L15: wrong chart value Jul '26 (fixed to {self.jul:.2f}) 27.50", kinds)   # the prose
        self.assertIn(f"L23: wrong chart value Jul '26 (fixed to {self.jul:.2f}) 27.50", kinds)   # the events label
        self.assertIn("L15: old chart start Jun '26 (dropped from the window) 26.51", kinds)
        self.assertIn('L15: old chart-window return 6.6%', kinds)
        self.assertEqual(rdt.chart_summary(self.facts), 'trimmed 1 points (window 4), events dropped: Jun 2026 start '
                                                        '| fixed 1 chart points (close basis, 1 compared)')

    def test_post_pass_holds_the_fixed_points(self):
        with tempfile.TemporaryDirectory() as repo:
            out = os.path.join(repo, 'out')
            os.makedirs(out)
            rdt.write_outputs(out, self.facts, self.new, True)
            reverted = self.new.replace(f"const prices = [{self.jul:.2f},", 'const prices = [27.50,')
            self.assertNotEqual(reverted, self.new)
            rl.write_text(os.path.join(repo, 'reports', 'ccl_analysis.html'), reverted)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(rdt.postpass('ccl', repo, out, True), 1)
            self.assertIn(f"MISMATCH fixed chart point Jul '26 27.5 != facts {self.jul}", buf.getvalue())

    def test_off_by_default(self):
        daily = rdt.parse_daily(load('yahoo_daily_ccl.json'), 'u', 't')
        facts, _ = rdt.build('ccl', PAGE_W, daily, '2026-10-01', {}, 'offline', 'offline', 'offline')
        self.assertEqual((facts['fields']['chart']['trim']['dropped'], facts['fixed_points']), (0, []))
        self.assertEqual(rdt.chart_summary(facts), 'not trimmed (--window 0) | points not checked (--fix-points off)')


class PostPass(unittest.TestCase):
    def run_post(self, repo: str, out: str, check: bool) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = rdt.postpass('ccl', repo, out, check)
        return code, buf.getvalue()

    def test_post(self):
        facts, new = built()
        with tempfile.TemporaryDirectory() as repo:
            path = os.path.join(repo, 'reports', 'ccl_analysis.html')
            out = os.path.join(repo, 'out')
            os.makedirs(out)
            rdt.write_outputs(out, facts, new, True)
            # the builder: new EPS, the yield formula on the new price, the delta box for this edition
            page = (new.replace('<td>$2.18</td>', '<td>$2.27</td>').replace('÷ $24.76.', '÷ $25.07.')
                    .replace('data-prior-as-of="2026-07-01" data-prior-price="27.00" data-as-of="2026-08-28" '
                             'data-price="24.76"', 'data-prior-as-of="2026-08-28" data-prior-price="24.76" '
                             'data-as-of="2026-10-01" data-price="25.07"'))
            rl.write_text(path, page)
            code, text = self.run_post(repo, out, check=True)
            self.assertEqual(code, 1)
            self.assertIn('would fix: P/E 11.5 -> 11.04', text)
            self.assertEqual(rl.read_text(path), page)              # --check changes nothing
            code, text = self.run_post(repo, out, check=False)
            self.assertEqual(code, 0, text)
            self.assertIn('<td>11.04</td>', rl.read_text(path))
            self.assertEqual(self.run_post(repo, out, check=True)[0], 0)
            # a builder that moved a script-owned number fails
            rl.write_text(path, rl.read_text(path).replace('$25.07</div>', '$25.10</div>'))
            code, text = self.run_post(repo, out, check=False)
            self.assertEqual(code, 1)
            self.assertIn('MISMATCH header price 25.1 != facts close 25.07', text)

    def test_stale_formula_and_delta_box(self):
        facts, new = built()
        with tempfile.TemporaryDirectory() as repo:
            out = os.path.join(repo, 'out')
            os.makedirs(out)
            rdt.write_outputs(out, facts, new, True)
            rl.write_text(os.path.join(repo, 'reports', 'ccl_analysis.html'), new)
            code, text = self.run_post(repo, out, check=False)
            self.assertEqual(code, 1)
            self.assertIn('the yield context still divides by $24.76', text)
            self.assertIn('delta box data-as-of="2026-08-28" != 2026-10-01', text)


if __name__ == '__main__':
    unittest.main()
