"""Unit tests for chart_audit.py: labels, point classification, the Yahoo cache.   Run from the repo root:  py -3 -m unittest discover -s tools/tests -v"""
import contextlib
import datetime
import io
import json
import os
import tempfile
import unittest
import unittest.mock

from fixtures import PAGE
import chart_audit  # noqa: E402


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
                unittest.mock.patch.object(chart_audit, 'CACHE', d), \
                unittest.mock.patch.object(chart_audit, 'fetch', fake_fetch):
            path = os.path.join(d, 'acme.ev.json')
            for cached in ('not json', self.yahoo_json([]), self.yahoo_json([(2026, 7)])):
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(cached)
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    monthly, _ = chart_audit.yahoo('acme', 'ACME', '2026-09-21')
                self.assertIn((2026, 9), monthly)
                self.assertEqual('unreadable' in err.getvalue(), cached == 'not json')   # a corrupt cache is reported
            self.assertEqual(len(fetched), 3)
            chart_audit.yahoo('acme', 'ACME', '2026-09-21')    # now current: read from the cache
            self.assertEqual(len(fetched), 3)

    def test_check_points(self):
        yh = {(2026, 6): (100.0, 95.0), (2026, 7): (100.0, 95.0), (2026, 8): (100.0, 95.0)}
        labels, prices = ["Jun '26", "Jul '26", "Aug '26", "Sep '26"], [101.0, 95.5, 150.0, 999.0]
        row = chart_audit.check_points(labels, prices, yh, [], '2026-09-21')
        self.assertEqual((row['checked'], row['adj_pts'], row['step_pts']), (3, 1, 0))   # the last point is verify.py's
        self.assertEqual(row['bad'], [("Aug '26", 150.0, 100.0, 50.0)])
        # a 2-for-1 split after the as-of: Yahoo's closes are halved, the report's are not
        row = chart_audit.check_points(labels, [100.0, 100.0, 100.0, 0], {k: (50.0, None) for k in yh},
                                       [('2026-10-01', 2.0)], '2026-09-21')
        self.assertEqual((row['checked'], row['bad'], row['splits_after_as_of']), (3, [], 2.0))

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
            with unittest.mock.patch.object(chart_audit, 'yahoo', fake_yahoo):
                row = chart_audit.audit('acme', repo=repo)
            missing = chart_audit.audit('gone', repo=repo)
        self.assertEqual(seen, [('acme', 'ACME', '2026-09-10')])
        self.assertEqual((row['checked'], row['bad']), (2, []))
        self.assertTrue(missing['err'].startswith('no page'))

    def test_an_unknown_slug_fails_the_run(self):
        with contextlib.redirect_stdout(io.StringIO()), \
                unittest.mock.patch.object(chart_audit, 'WORK', tempfile.gettempdir()):
            self.assertEqual(chart_audit.main(['notareport']), 1)


if __name__ == '__main__':
    unittest.main()
