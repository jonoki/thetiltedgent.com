"""Unit tests for reportlib: numbers, dates and what a report page says.   Run from the repo root:  py -3 -m unittest discover -s tools/tests -v"""
import os
import re
import unittest

from fixtures import PAGE
import asset_cards  # noqa: E402
import style_tags  # noqa: E402
import reportlib as rl  # noqa: E402
import repodata as rd  # noqa: E402


class Numbers(unittest.TestCase):
    def test_to_number_reads_a_whole_value(self):
        self.assertEqual(rl.to_number('1,234.5'), 1234.5)
        self.assertEqual(rl.to_number('$12.30'), 12.3)
        self.assertEqual(rl.to_number('4.1%'), 4.1)
        self.assertEqual(rl.to_number('−3.2'), -3.2)
        self.assertIsNone(rl.to_number('n/m'))
        self.assertIsNone(rl.to_number(None))

    def test_first_number_reads_the_first_value_in_a_cell(self):
        self.assertEqual(rl.first_number('12.4x (vs 18x)'), 12.4)
        self.assertEqual(rl.first_number('($1.2B)'), -1.2)
        self.assertEqual(rl.first_number('-0.5'), -0.5)
        self.assertEqual(rl.first_number(7), 7.0)
        self.assertIsNone(rl.first_number('n/m'))
        self.assertIsNone(rl.first_number('not meaningful'))

    def test_money_scales_suffixes(self):
        self.assertEqual(style_tags.money('$99.92B'), 99.92e9)
        self.assertEqual(style_tags.money('($1.5M)'), -1.5e6)
        self.assertEqual(style_tags.money('$2.1T'), 2.1e12)

    def test_iso_date(self):
        self.assertEqual(rl.iso_date('September 10, 2026'), '2026-09-10')
        self.assertEqual(rl.iso_date('Sept 3, 2026'), '2026-09-03')
        self.assertIsNone(rl.iso_date('10/09/2026'))


class ReportPage(unittest.TestCase):
    def test_title(self):
        self.assertEqual(rl.parse_title(PAGE), ('ACME', 'Acme Widgets Inc.'))
        self.assertEqual(rl.parse_title('<title>Acme Widgets (ACME) — Stock Analysis</title>'), ('ACME', 'Acme Widgets'))
        self.assertEqual(rl.parse_title('<title>No ticker here</title>'), (None, None))

    def test_price_chart_and_range(self):
        self.assertEqual(rl.header_price(PAGE), 1234.5)
        labels, prices = rl.chart_series(PAGE)
        self.assertEqual(labels, ["Sep '21", "Oct '21", 'Nov 21'])
        self.assertEqual(prices, [1100.5, 1200.0, 1234.5])
        self.assertEqual(rl.range_52w(PAGE), [1001.0, 1300.0])

    def test_chart_prefers_an_equal_length_pair(self):
        t = "const labels=['a','b'];const prices=[1];var labels=['x'];let prices=[5,6];"
        self.assertEqual(rl.chart_series(t), (['a', 'b'], [5.0, 6.0]))

    def test_structure_counts(self):
        s = rl.structure_counts(PAGE)
        self.assertTrue(all(s[k] == 1 for k in rl.SKELETON))
        self.assertEqual(s['canvas'], 2)
        self.assertEqual(s['style_open'], s['style_close'])

    def test_structure_problems(self):
        problems = lambda t, path='reports/acme_analysis.html': rl.structure_problems(rl.structure_counts(t), path)
        self.assertEqual(problems(PAGE), [])
        self.assertEqual(problems(PAGE, 'reports/fixed/acme_analysis.html'), ['canvas_count:2'])   # bonds add the yield curve
        self.assertEqual(problems(PAGE.replace('</head>', '')), ['document_skeleton_incomplete'])
        self.assertEqual(problems(PAGE.replace('</style>', '')), ['style_unbalanced'])
        self.assertEqual(problems(PAGE.replace('<body>', '<body><nav id="tg-sitenav"></nav>')), ['has_legacy_sitenav'])

    def test_table_rows(self):
        t = ('<table><thead><tr><th>Metric</th><th>ACME</th></tr></thead><tbody>'
             '<tr><td><span class="tip">EPS</span> (<span>TTM</span>)</td><td>$1.20</td></tr>'
             '<tr style="background:#111"><td>Net Interest Margin</td><td>2.96%</td></tr>'   # was missed before 26 Sep 2026
             '<tr><th>CET1\n  Ratio</th><td>9.9%</td></tr><tr><td>lonely</td></tr></tbody></table>')
        rows = rl.table_rows(t)
        self.assertEqual(rows, [('EPS (TTM)', '$1.20'), ('Net Interest Margin', '2.96%'), ('CET1 Ratio', '9.9%')])
        self.assertEqual(rl.row_value(rows, r'net interest', re.I), '2.96%')
        self.assertIsNone(rl.row_value(rows, r'ROTCE'))

    def test_every_asset_family_has_a_tab(self):
        self.assertEqual(tuple(asset_cards.FAMILIES), rd.ASSET_FAMILIES)

    def test_report_path(self):
        self.assertEqual(rd.report_path('aapl', repo='r'), os.path.join('r', 'reports', 'aapl_analysis.html'))
        self.assertEqual(rd.report_path('voo', 'etf', repo='r'), os.path.join('r', 'reports', 'etf', 'voo_analysis.html'))


if __name__ == '__main__':
    unittest.main()
