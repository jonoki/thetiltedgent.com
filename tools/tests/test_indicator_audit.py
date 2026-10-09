"""Unit tests for the economic-indicator gates: indicator_audit.py (chart vs the official series) and verify.py on
an indicator page.   Run: py -3 tools/run_checks.py"""
import contextlib
import io
import json
import os
import tempfile
import unittest
import unittest.mock

import indicator_audit as ia
import reportlib as rl
import repodata as rd
import verify


def page(labels: list[str], values: list[float], header: str, rng: str = '12-Month Range',
         cell: str = '2.4 &ndash; 3.4%', title: str = 'CPI — US Consumer Price Index | Economic Indicator',
         cite: str = 'FRED CPIAUCNS') -> str:
    """A minimal indicator page: two canvases, the history arrays, a header value and a range row."""
    return (f'<!DOCTYPE html>\n<html lang="en"><head><title>{title}</title><style>b{{}}</style></head>\n<body>\n'
            f'<div>Static data as of October 15, 2026</div>\n<div class="price-current"{header}</div>\n'
            f'<table class="fin-table"><tr><td>{rng}</td><td>{cell}</td></tr></table>\n<p>Chart: {cite}.</p>\n'
            '<canvas id="priceChart"></canvas><canvas id="yoyChart"></canvas>\n'
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>\n'
            f'<script>const labels = {json.dumps(labels)}; const prices = {json.dumps(values)};</script>\n</body></html>\n')


class Labels(unittest.TestCase):
    def test_month_and_day_labels(self):
        self.assertEqual(ia.parse_label('Oct 21'), (2021, 10, None))
        self.assertEqual(ia.parse_label("Oct '21"), (2021, 10, None))
        self.assertEqual(ia.parse_label('October 2021'), (2021, 10, None))
        self.assertEqual(ia.parse_label('2021-10'), (2021, 10, None))
        self.assertEqual(ia.parse_label('Oct 2 26'), (2026, 10, 2))       # the as-of point of a daily series
        self.assertEqual(ia.parse_label('Oct 21 26'), (2026, 10, 21))     # a day, not October 2021
        self.assertEqual(ia.parse_label('Oct 2, 2026'), (2026, 10, 2))
        self.assertEqual(ia.parse_label('2026-10-02'), (2026, 10, 2))
        self.assertIsNone(ia.parse_label('Q3 26'))


class Sources(unittest.TestCase):
    def test_fred_csv(self):
        text = 'observation_date,SOFR\n2026-09-04,3.65\n2026-09-07,\n2026-09-08,3.64\n2026-09-09,.\n'
        self.assertEqual(ia.parse_fred_csv(text), {'2026-09-04': 3.65, '2026-09-08': 3.64})
        with self.assertRaises(ia.FetchError):
            ia.parse_fred_csv('<html>busy</html>')

    def test_valet_json(self):
        text = json.dumps({'observations': [{'d': '2026-09-29', 'AVG.INTWO': {'v': '2.3100'}},
                                            {'d': '2026-10-01', 'AVG.INTWO': {'v': ''}}]})
        self.assertEqual(ia.parse_valet_json(text, 'AVG.INTWO'), {'2026-09-29': 2.31})
        with self.assertRaises(ia.FetchError):
            ia.parse_valet_json('{"error": 1}', 'AVG.INTWO')


class Official(unittest.TestCase):
    DAILY = {'2026-08-28': 3.65, '2026-08-31': 3.68, '2026-09-29': 3.70, '2026-09-30': 3.90, '2026-10-02': 3.88}
    MONTHLY = {f'{2025 + (m - 1) // 12}-{(m - 1) % 12 + 1:02d}-01': 100.0 + m for m in range(1, 22)}   # Jan 25 -> Sep 26

    def test_daily_month_end_and_day(self):
        s = ia.SERIES['sofr']
        self.assertEqual(ia.official(self.DAILY, s, (2026, 8, None), '2026-10-02'), 3.68)   # last observation in August
        self.assertEqual(ia.official(self.DAILY, s, (2026, 9, None), '2026-09-29'), 3.70)   # nothing after the as-of
        self.assertEqual(ia.official(self.DAILY, s, (2026, 10, 2), None), 3.88)
        self.assertIsNone(ia.official(self.DAILY, s, (2026, 10, 1), None))                  # no value that day

    def test_monthly_transforms(self):
        m = self.MONTHLY   # x = 100 + n for the n-th month from Jan 2025
        self.assertEqual(ia.official(m, ia.SERIES['unrate'], (2026, 9, None), None), 121.0)
        self.assertAlmostEqual(ia.official(m, ia.SERIES['cpi'], (2026, 9, None), None) or 0, 100 * (121 / 109 - 1))
        self.assertEqual(ia.official(m, ia.SERIES['payrolls'], (2026, 9, None), None), 1.0)
        self.assertIsNone(ia.official(m, ia.SERIES['cpi'], (2025, 9, None), None))   # no month a year earlier
        self.assertIsNone(ia.official(m, ia.SERIES['unrate'], (2026, 9, 1), None))   # no day points on a monthly series

    def test_tolerance_is_the_shown_decimal(self):
        s = ia.SERIES['cpi']   # 1 dp
        obs = {'2025-09-01': 100.0, '2026-09-01': 102.95}   # 2.95%: 2.9 and 3.0 both round to it
        self.assertEqual(ia.check_points(['Sep 26'], [3.0], obs, s, None), (1, [], []))
        self.assertEqual(ia.check_points(['Sep 26'], [2.9], obs, s, None), (1, [], []))
        self.assertEqual(ia.check_points(['Sep 26'], [3.1], obs, s, None)[1], [('Sep 26', 3.1, 2.95)])
        self.assertEqual(ia.check_points(['Q3', 'Aug 26'], [1, 2], obs, s, None), (0, [], ['Q3', 'Aug 26']))


class Audit(unittest.TestCase):
    OBS = {f'{2024 + (m - 1) // 12}-{(m - 1) % 12 + 1:02d}-01': 100.0 * 1.003 ** m for m in range(1, 34)}   # Jan 24 -> Sep 26

    def labels_values(self) -> tuple[list[str], list[float]]:
        months = [(2025, 1 + k) if k < 12 else (2026, k - 11) for k in range(21)]   # Jan 25 -> Sep 26
        labels = [f"{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m - 1]} {y % 100}" for y, m in months]
        return labels, [round(ia.official(self.OBS, ia.SERIES['cpi'], (y, m, None), None) or 0, 1) for y, m in months]

    def run_audit(self, html: str) -> tuple[int | str, str]:
        with tempfile.TemporaryDirectory() as repo:
            rl.write_text(rd.report_path('cpi', 'indicators', repo=repo), html)
            out = io.StringIO()
            with unittest.mock.patch.object(ia, 'observations', lambda ser, start: self.OBS), contextlib.redirect_stdout(out):
                code = ia.main(['--repo', repo, 'indicators/cpi'])
        return code, out.getvalue()

    def test_a_clean_page_passes_and_a_wrong_point_fails(self):
        labels, values = self.labels_values()
        code, out = self.run_audit(page(labels, values, f'>{values[-1]}%'))
        self.assertEqual(code, 0, out)
        self.assertIn('ok   indicators/cpi: 21 points vs CPIAUCNS (fred, yoy, 1 dp) | wrong 0 | unmatched 0', out)
        values[5] += 0.2
        code, out = self.run_audit(page(labels, values, f'>{values[-1]}%'))
        self.assertEqual(code, 1)
        self.assertIn(f'wrong {labels[5]}: page {values[5]}', out)

    def test_an_uncited_series_or_unknown_slug_fails(self):
        labels, values = self.labels_values()
        code, out = self.run_audit(page(labels, values, f'>{values[-1]}%', cite='the BLS'))
        self.assertEqual(code, 1)
        self.assertIn('series cited False', out)
        self.assertIn('no SERIES entry', str(ia.audit('indicators/gdp')))


class Verify(unittest.TestCase):
    def check(self, html: str, slug: str = 'cpi') -> verify.CheckResult:
        with tempfile.TemporaryDirectory() as repo:
            path = rd.report_path(slug, 'indicators', repo=repo)
            rl.write_text(path, html)
            return verify.check(path)

    def test_an_indicator_page_passes_on_its_value(self):
        o = self.check(page(['Aug 26', 'Sep 26'], [2.9, 3.0], '>3.0%'))
        self.assertTrue(o['ok'], o)
        self.assertEqual((o['price'], o['range_ok'], o['title_ok']), (3.0, True, True))

    def test_signed_values_ranges_and_series_id_titles(self):
        html = page(['Aug 26', 'Sep 26'], [-13, 22], '>+22K', cell='&minus;13K &ndash; 254K',
                    title='PAYEMS — US Nonfarm Payrolls | Economic Indicator')
        o = self.check(html, 'payrolls')
        self.assertTrue(o['ok'], o)                                  # the title may carry the FRED series id
        self.assertEqual((o['price'], o['range']), (22, (-13, 254)))
        self.assertFalse(self.check(html.replace('>+22K', '>+23K'), 'payrolls')['ok'])   # header != last point

    def test_a_range_header_names_its_charted_end(self):
        html = page(['Sep 26', 'Oct 2 26'], [4.0, 4.0], ' data-value="4.00">3.75&ndash;4.00%', rng='52-Week Range',
                    cell='4.00 &ndash; 4.25%', title='FEDTARGET — Federal Funds Target Range | Economic Indicator')
        self.assertTrue(self.check(html, 'fedtarget')['ok'])
        self.assertFalse(self.check(html.replace(' data-value="4.00"', ''), 'fedtarget')['ok'])   # 3.75 != 4.00

    def test_no_range_row_fails(self):
        self.assertFalse(self.check(page(['Sep 26'], [3.0], '>3.0%', rng='Range'))['ok'])


if __name__ == '__main__':
    unittest.main()
