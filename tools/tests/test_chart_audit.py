"""Unit tests for chart_audit.py: labels, point classification, the Yahoo cache.   Run: py -3 tools/run_checks.py"""
import contextlib
import datetime
import io
import json
import os
import tempfile
import unittest
import unittest.mock

from tests.fixtures import PAGE
import chart_audit


class ChartAudit(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(chart_audit.parse_label("Sep '21"), (2021, 9))
        self.assertEqual(chart_audit.parse_label('September 2021'), (2021, 9))
        self.assertEqual(chart_audit.parse_label('2021-09'), (2021, 9))
        self.assertIsNone(chart_audit.parse_label('Q3'))

    def test_classify(self):
        self.assertEqual(chart_audit.classify(102, 100, None, 1.0), 'ok')             # within 3%
        self.assertEqual(chart_audit.classify(90, 100, 91, 1.0), 'adjusted')         # matches the dividend-adjusted close
        self.assertEqual(chart_audit.classify(120, 100, None, 1.2), 'basis step')    # a real pre-spin close
        self.assertEqual(chart_audit.classify(120, 100, 101, 1.0), 'wrong')

    def test_adjusted_label_ignores_negations(self):
        self.assertTrue(chart_audit.adj_labelled('Chart: dividend-adjusted month-end closes'))
        self.assertFalse(chart_audit.adj_labelled('actual month-end closes, split-adjusted not dividend-adjusted'))
        self.assertFalse(chart_audit.adj_labelled('Real price, i.e. unadjusted closes'))
        self.assertFalse(chart_audit.adj_labelled('closes rather than adjusted closes'))

    def test_spin_factor_counts_only_small_splits_between_the_month_and_the_as_of(self):
        splits = [('2024-06-03', 1.1), ('2025-01-10', 2.0), ('2026-12-01', 1.05)]
        self.assertAlmostEqual(chart_audit.spin_factor(splits, (2024, 5), '2026-09-21'), 1.1)   # 2:1 is a real split
        self.assertEqual(chart_audit.spin_factor(splits, (2024, 7), '2026-09-21'), 1.0)

    @staticmethod
    def yahoo_json(months: list[tuple[int, int]], close: float = 100.0, splits: dict | None = None) -> str:
        ts = [int(datetime.datetime(y, m, 1, tzinfo=datetime.UTC).timestamp()) for y, m in months]
        return json.dumps({'chart': {'result': [{
            'meta': {'gmtoffset': 0}, 'timestamp': ts, 'events': {'splits': splits or {}},
            'indicators': {'quote': [{'close': [close] * len(ts)}], 'adjclose': [{'adjclose': [close * 0.9] * len(ts)}]}}]}})

    def test_read_series(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.json')
            split_ts = str(int(datetime.datetime(2026, 1, 5, tzinfo=datetime.UTC).timestamp()))
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(self.yahoo_json([(2025, 11), (2025, 12)], splits={split_ts: {'numerator': 2, 'denominator': 1}}))
            monthly, splits = chart_audit.read_series(p)
            self.assertEqual(monthly, {(2025, 11): (100.0, 90.0), (2025, 12): (100.0, 90.0)})
            self.assertEqual(splits, [('2026-01-05', 2.0)])
            for bad in ('{"chart": {"result": [', '{"chart": {"result": []}}', '{"chart": {"result": [{"meta": {}}]}}'):
                with open(p, 'w', encoding='utf-8') as fh:
                    fh.write(bad)
                with self.assertRaises(chart_audit.YahooError):
                    chart_audit.read_series(p)

    def test_a_corrupt_empty_or_stale_cache_is_fetched_again(self):
        fresh = self.yahoo_json([(2026, 8), (2026, 9)])
        fetched = []

        def fake_fetch(slug, ticker, path):
            fetched.append(slug)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(fresh)
        with tempfile.TemporaryDirectory() as d, \
                unittest.mock.patch.object(chart_audit, 'WORK', d), \
                unittest.mock.patch.object(chart_audit, 'fetch', fake_fetch):
            path = os.path.join(chart_audit.cache_dir(), 'acme.ev.json')
            for cached in ('not json', self.yahoo_json([]), self.yahoo_json([(2026, 7)])):
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(cached)
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    monthly, _ = chart_audit.monthly_series('acme', 'ACME', '2026-09-21')
                self.assertIn((2026, 9), monthly)
                self.assertEqual('unreadable' in err.getvalue(), cached == 'not json')   # a corrupt cache is reported
            self.assertEqual(len(fetched), 3)
            chart_audit.monthly_series('acme', 'ACME', '2026-09-21')    # now current: read from the cache
            self.assertEqual(len(fetched), 3)

    def test_check_points(self):
        series = {(2026, 6): (100.0, 95.0), (2026, 7): (100.0, 95.0), (2026, 8): (100.0, 95.0)}
        labels, prices = ["Jun '26", "Jul '26", "Aug '26", "Sep '26"], [101.0, 95.5, 150.0, 999.0]
        row = chart_audit.check_points(labels, prices, series, [], '2026-09-21')
        self.assertEqual((row['checked'], row['adj_pts'], row['step_pts']), (3, 1, 0))   # the last point is verify.py's
        self.assertEqual(row['bad'], [("Aug '26", 150.0, 100.0, 50.0)])
        # a 2-for-1 split after the as-of: Yahoo's closes are halved, the report's are not
        row = chart_audit.check_points(labels, [100.0, 100.0, 100.0, 0], {k: (50.0, None) for k in series},
                                       [('2026-10-01', 2.0)], '2026-09-21')
        self.assertEqual((row['checked'], row['bad'], row['splits_after_as_of']), (3, [], 2.0))

    def test_points_before_launch_are_flagged_not_compared(self):
        """A recycled ticker: Yahoo's rows before the launch are another security."""
        series = {(2024, 2): (7.7, None), (2024, 3): (10.0, None), (2024, 4): (10.2, None)}
        labels, prices = ["Feb '24", "Mar '24", "Apr '24", "May '24"], [7.7, 10.0, 10.2, 0]
        row = chart_audit.check_points(labels, prices, series, [], '2024-05-31', launch=(2024, 3))
        self.assertEqual((row['checked'], row['bad'], row['pre_launch']), (2, [], ["Feb '24"]))
        self.assertEqual(chart_audit.check_points(labels, prices, series, [], '2024-05-31')['pre_launch'], [])

    def test_asset_slugs_map_to_yahoo_symbols_and_drop_pre_launch_rows(self):
        self.assertEqual(chart_audit.yahoo_symbol('etf/arti', 'ARTI'), 'ARTI.TO')
        self.assertEqual(chart_audit.yahoo_symbol('crypto/btc', 'BTC'), 'BTC-USD')
        with tempfile.TemporaryDirectory() as work, unittest.mock.patch.object(chart_audit, 'WORK', work):
            with open(os.path.join(chart_audit.cache_dir(), 'etf_arti.ev.json'), 'w', encoding='utf-8') as fh:
                fh.write(self.yahoo_json([(2024, 2), (2024, 3), (2024, 4)]))
            monthly, _ = chart_audit.monthly_series('etf/arti', 'ARTI', '2024-04-30')
        self.assertEqual(sorted(monthly), [(2024, 3), (2024, 4)])

    def test_a_report_is_audited_from_its_own_page_not_the_manifest(self):
        """A new build (not in data/reports.json yet) is still checked, with the page's own ticker and as-of date."""
        seen = []

        def fake_yahoo(slug, ticker, as_of):
            seen.append((slug, ticker, as_of))
            return {(2021, 9): (1100.5, None), (2021, 10): (1200.0, None)}, []
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, 'reports'))
            with open(os.path.join(repo, 'reports', 'acme_analysis.html'), 'w', encoding='utf-8') as fh:
                fh.write(PAGE)
            with unittest.mock.patch.object(chart_audit, 'monthly_series', fake_yahoo):
                row = chart_audit.audit('acme', repo=repo)
            missing = chart_audit.audit('gone', repo=repo)
        self.assertEqual(seen, [('acme', 'ACME', '2026-09-10')])
        assert chart_audit.succeeded(row) and chart_audit.failed(missing)
        self.assertEqual((row['checked'], row['bad']), (2, []))
        self.assertTrue(missing['err'].startswith('no page'))

    def test_labels_and_prices_of_different_lengths_are_an_error(self):
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, 'reports'))
            with open(os.path.join(repo, 'reports', 'acme_analysis.html'), 'w', encoding='utf-8') as fh:
                fh.write(PAGE.replace('[1100.5,1200,1234.5]', '[1200,1234.5]'))
            row = chart_audit.audit('acme', repo=repo)
        assert chart_audit.failed(row)
        self.assertEqual(row['err'], '3 labels for 2 prices')

    @staticmethod
    def bars_json(rows: list[tuple[int, int, int, float]], splits: dict | None = None) -> str:
        """A Yahoo chart response with one bar per (year, month, day, close); adjclose = close."""
        ts = [int(datetime.datetime(y, m, d, 13, 30, tzinfo=datetime.UTC).timestamp()) for y, m, d, _ in rows]
        closes = [c for *_, c in rows]
        return json.dumps({'chart': {'result': [{
            'meta': {'gmtoffset': -14400}, 'timestamp': ts, 'events': {'splits': splits or {}},
            'indicators': {'quote': [{'close': closes}], 'adjclose': [{'adjclose': closes}]}}]}})

    # CTVA-like (Vylor spin, 1 Oct 2026, booked by Yahoo as a 6.665:1 "split"): real month-end closes before the spin
    SPIN = ('2026-10-01', 6.665)
    REAL = {(2025, 11): 67.47, (2025, 12): 67.03, (2026, 1): 72.80, (2026, 2): 80.12, (2026, 9): 77.65}
    LABELS = ["Nov '25", "Dec '25", "Jan '26", "Feb '26", "Sep '26", "Oct '26"]

    def spin_feeds(self) -> tuple[str, str]:
        """(monthly, daily) Yahoo responses: the monthly bars mixed (to Dec 2025 real, from Jan 2026 back-adjusted),
        the daily feed back-adjusted throughout, with a mid-month day that is not the month-end."""
        split = {str(int(datetime.datetime(2026, 10, 1, 13, 30, tzinfo=datetime.UTC).timestamp())):
                 {'numerator': 6.665, 'denominator': 1}}
        f = self.SPIN[1]
        monthly = [(y, m, 1, c if (y, m) < (2026, 1) else c / f) for (y, m), c in self.REAL.items()] + [(2026, 10, 1, 13.75)]
        daily = []
        for (y, m), c in self.REAL.items():
            daily += [(y, m, 15, c * 0.8 / f), (y, m, 27, c / f)]   # the 27th stands in for the last trading day
        daily.append((2026, 10, 8, 13.75))
        return self.bars_json(monthly, split), self.bars_json(daily, split)

    def test_a_declared_spin_is_checked_on_daily_month_ends_not_the_mixed_monthly_bars(self):
        monthly_json, daily_json = self.spin_feeds()
        fetched = []

        def fake_fetch(slug, ticker, path, daily=False):
            fetched.append((slug, daily))
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(daily_json if daily else monthly_json)
        prices = [round(c / self.SPIN[1], 2) for c in self.REAL.values()] + [13.75]   # the spin-adjusted chart
        with tempfile.TemporaryDirectory() as d, \
                unittest.mock.patch.object(chart_audit, 'WORK', d), \
                unittest.mock.patch.object(chart_audit, 'fetch', fake_fetch), \
                unittest.mock.patch.object(chart_audit, 'SPINOFFS', {'acme': self.SPIN}):
            series, splits = chart_audit.monthly_series('acme', 'ACME', '2026-10-08')
            mixed, _ = chart_audit.monthly_series('other', 'OTHER', '2026-10-08')
        self.assertEqual(fetched, [('acme', True), ('other', False)])
        self.assertAlmostEqual(series[(2025, 12)][0], 67.03 / 6.665)                  # the month-end, not the 15th
        self.assertEqual(splits, [('2026-10-01', 6.665)])
        row = chart_audit.check_points(self.LABELS, prices, series, splits, '2026-10-08', spin=self.SPIN)
        self.assertEqual((row['checked'], row['bad'], row['step_pts'], row['spin_adj_pts']), (5, [], 0, 5))
        # the mixed monthly bars would flag every point before Jan 2026, which is why a declared spin reads the daily feed
        row = chart_audit.check_points(self.LABELS, prices, mixed, splits, '2026-10-08', spin=self.SPIN)
        self.assertEqual([b[0] for b in row['bad']], ["Nov '25", "Dec '25"])

    def test_real_pre_spin_closes_of_a_declared_spin_are_a_basis_step(self):
        series = {ym: (c / self.SPIN[1], c / self.SPIN[1]) for ym, c in self.REAL.items()}
        prices = list(self.REAL.values()) + [13.75]
        row = chart_audit.check_points(self.LABELS, prices, series, [('2026-10-01', 6.665)], '2026-10-08', spin=self.SPIN)
        self.assertEqual((row['bad'], row['step_pts'], row['spin_adj_pts']), ([], 5, 0))
        # undeclared, the same 6.665 is a real split and the real closes are wrong
        row = chart_audit.check_points(self.LABELS, prices, series, [('2026-10-01', 6.665)], '2026-10-08')
        self.assertEqual(len(row['bad']), 5)

    def test_an_undeclared_10_for_1_split_is_still_a_real_split(self):
        labels, real = ["Jan '26", "Feb '26", "Mar '26", "Apr '26", "May '26"], [500.0, 520.0, 54.0, 55.0, 56.0]
        series = {(2026, 1): (50.0, None), (2026, 2): (52.0, None), (2026, 3): (54.0, None), (2026, 4): (55.0, None)}
        splits = [('2026-03-02', 10.0)]
        row = chart_audit.check_points(labels, real, series, splits, '2026-05-20')      # pre-split points not adjusted
        self.assertEqual([b[0] for b in row['bad']], ["Jan '26", "Feb '26"])
        row = chart_audit.check_points(labels, [50.0, 52.0, 54.0, 55.0, 56.0], series, splits, '2026-05-20')
        self.assertEqual((row['bad'], row['step_pts'], row['spin_adj_pts']), ([], 0, 0))
        self.assertEqual(chart_audit.spin_factor(splits, (2026, 1), '2026-05-20'), 1.0)
        self.assertEqual(chart_audit.spin_factor(splits, (2026, 1), '2026-05-20', declared=('2026-04-01', 2.0)), 2.0)   # only the declared one
        self.assertNotIn('acme', chart_audit.SPINOFFS)   # SPINOFFS is per slug: no other report reads it

    def test_a_spin_adjusted_chart_must_say_so(self):
        self.assertTrue(chart_audit.spin_adjusted_labelled('5-year closes · SPIN-ADJUSTED'))
        self.assertTrue(chart_audit.spin_adjusted_labelled('prices adjusted for the spin: spin-off adjusted closes'))
        self.assertFalse(chart_audit.spin_adjusted_labelled('real closes, not spin-adjusted'))
        self.assertFalse(chart_audit.spin_adjusted_labelled('split-adjusted closes'))
        row = {'slug': 'ctva', 'ticker': 'CTVA', 'as_of': '2026-10-08', 'checked': 59, 'bad': [], 'adj_pts': 0, 'step_pts': 0,
               'splits_after_as_of': 1.0, 'pre_launch': [], 'spin_adj_pts': 59, 'adj_labelled': False}
        for labelled, code in ((True, 0), (False, 1)):
            with contextlib.redirect_stdout(io.StringIO()), \
                    unittest.mock.patch.object(chart_audit, 'WORK', tempfile.gettempdir()), \
                    unittest.mock.patch.object(chart_audit, 'audit', lambda slug, repo, lab=labelled: {**row, 'spin_labelled': lab}):
                self.assertEqual(chart_audit.main(['ctva']), code)

    def test_an_unknown_slug_fails_the_run(self):
        with contextlib.redirect_stdout(io.StringIO()), \
                unittest.mock.patch.object(chart_audit, 'WORK', tempfile.gettempdir()):
            self.assertEqual(chart_audit.main(['notareport']), 1)


if __name__ == '__main__':
    unittest.main()
