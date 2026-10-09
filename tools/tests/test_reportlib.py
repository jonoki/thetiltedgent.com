"""Unit tests for reportlib: numbers, dates and what a report page says.   Run: py -3 tools/run_checks.py"""
import os
import re
import tempfile
import unittest

from tests.fixtures import PAGE
import asset_cards
import style_tags
import reportlib as rl
import repodata as rd


class Numbers(unittest.TestCase):
    def test_to_number_reads_a_whole_value(self):
        self.assertEqual(rl.to_number('1,234.5'), 1234.5)
        self.assertEqual(rl.to_number('$12.30'), 12.3)
        self.assertEqual(rl.to_number('4.1%'), 4.1)
        self.assertEqual(rl.to_number('−3.2'), -3.2)
        self.assertIsNone(rl.to_number('n/m'))

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

    def test_usd_cap_reads_the_first_dollar_amount_with_its_scale(self):
        """The reports index sorts by this number (manifest market_cap_usd -> card_tags 'mc')."""
        self.assertEqual(rl.usd_cap('$1.2T'), 1.2e12)
        self.assertEqual(rl.usd_cap('$41.89B'), 41.89e9)
        self.assertEqual(rl.usd_cap('$950M'), 950e6)
        self.assertEqual(rl.usd_cap('~$4.50 Trillion'), 4.5e12)
        self.assertEqual(rl.usd_cap('US$488.1B (HK$3.83T)'), 488.1e9)          # a global listing: US dollars first
        self.assertEqual(rl.usd_cap('$134.02B (R$700.08B at the BCB PTAX rate)'), 134.02e9)
        self.assertEqual(rl.usd_cap('US$134.1B (HK$1,052.0B)'), 134.1e9)
        self.assertIsNone(rl.usd_cap('HK$673.76B'))                            # a local currency is not US dollars
        self.assertIsNone(rl.usd_cap('n/a'))
        self.assertIsNone(rl.usd_cap(''))
        self.assertIsNone(rl.usd_cap(None))                                    # missing

    def test_header_mcap_reads_past_a_tooltip_span(self):
        t = '<span>Mkt Cap:</span> <span class="tip" title="All 9.1B shares at HK$73.90">$85.87B (HK$673.76B)</span>'
        self.assertEqual(rl.header_mcap(t), ('$85.87B (HK$673.76B)', 85.87e9))
        self.assertEqual(rl.header_mcap('<b>Mkt Cap:</b><span>$337.4B</span>'), ('$337.4B', 337.4e9))
        self.assertIsNone(rl.header_mcap('<span>Mkt Cap:</span> n/a</span>'))
        self.assertIsNone(rl.header_mcap('<p>no header</p>'))


class ReportPage(unittest.TestCase):
    def test_title(self):
        self.assertEqual(rl.parse_title(PAGE), ('ACME', 'Acme Widgets Inc.'))
        self.assertEqual(rl.parse_title('<title>Acme Widgets (ACME) — Stock Analysis</title>'), ('ACME', 'Acme Widgets'))
        self.assertEqual(rl.parse_title('<title>No ticker here</title>'), (None, None))
        self.assertEqual(rl.parse_title('<title>0700.HK — Tencent Holdings | Stock Analysis</title>'), ('0700.HK', 'Tencent Holdings'))

    def test_non_us_currency_markers(self):
        """Global reports quote prices in their home currency: €26.56, HK$421.20, ₩276,000.00, or '26.56 EUR'."""
        for cell, want in (('€26.56', 26.56), ('HK$421.20', 421.2), ('₩276,000.00', 276000.0), ('26.56 EUR', 26.56), ('$9.50', 9.5)):
            self.assertEqual(rl.header_price(f'<div class="price-current">{cell}</div>'), want, cell)
        page = '<tr><td>52-Week Range</td><td>€23.53 – €34.36</td></tr>'
        self.assertEqual(rl.range_52w(page), [23.53, 34.36])

    def test_a_global_slug_matches_its_exchange_ticker(self):
        import verify
        self.assertTrue(verify.title_matches('0700.HK', os.path.join('reports', 'tencent_analysis.html')))
        self.assertTrue(verify.title_matches('AAPL', os.path.join('reports', 'aapl_analysis.html')))
        self.assertFalse(verify.title_matches('PCG', os.path.join('reports', 'cboe_analysis.html')))

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
        self.assertEqual(problems(PAGE.replace('</style>', '/* paste into <style>, just before </style> */</style>')),
                         ['style_tag_in_css_comment'])   # balanced counts, but the browser ends the style at the comment
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

    def test_every_index_family_has_a_tab(self):
        self.assertEqual(tuple(asset_cards.FAMILIES), rd.INDEX_FAMILIES)
        self.assertEqual(set(rd.ASSET_FAMILIES) - set(rd.INDEX_FAMILIES), {'indicators'})   # on the Learn hub instead

    def test_family_and_canvases(self):
        self.assertEqual(rl.family_of(os.path.join('x', 'reports', 'indicators', 'cpi_analysis.html')), 'indicators')
        self.assertIsNone(rl.family_of(os.path.join('x', 'reports', 'aapl_analysis.html')))
        self.assertEqual(rl.expected_canvases('reports/indicators/cpi_analysis.html'), (2, 3))
        problems = lambda t, path: rl.structure_problems(rl.structure_counts(t), path)
        self.assertEqual(problems(PAGE, 'reports/indicators/cpi_analysis.html'), [])   # history chart + one other
        self.assertEqual(problems(PAGE.replace('<canvas', '<canvas id="x"></canvas><canvas', 1),
                                  'reports/indicators/sofr_analysis.html'), [])           # + the curve chart
        self.assertEqual(problems(PAGE.replace('<canvas', '<x', 1), 'reports/indicators/cpi_analysis.html'),
                         ['canvas_count:1'])

    def test_header_value(self):
        page = lambda inner, attrs='': f'<div class="hero"><div class="price-current"{attrs}>{inner}</div></div>'
        self.assertEqual(rl.header_value(page('3.88%')), 3.88)
        self.assertEqual(rl.header_value(page('\u22120.2 pp')), -0.2)
        self.assertEqual(rl.header_value(page('+142K <span>jobs</span>')), 142)
        self.assertEqual(rl.header_value(page('1,234')), 1234)
        self.assertEqual(rl.header_value(page('3.75\u20134.00%', ' data-value="4.00"')), 4.0)   # a range names its point
        self.assertIsNone(rl.header_value(page('n/a')))
        self.assertIsNone(rl.header_value('<div class="price">3.88</div>'))

    def test_indicator_range(self):
        row = lambda label, cell: f'<table><tr><td>{label}</td><td>{cell}</td></tr></table>'
        self.assertEqual(rl.indicator_range(row('52-Week Range', '3.50 \u2013 4.31%')), [3.5, 4.31])
        self.assertEqual(rl.indicator_range(row('12-Month Range', '\u221213K \u2013 254K')), [-13, 254])
        self.assertEqual(rl.indicator_range(row('12-month range', '2.4 to 3.1%')), [2.4, 3.1])
        self.assertEqual(rl.indicator_range(row('12-Month Range', '-0.2 - 0.4')), [-0.2, 0.4])
        self.assertIsNone(rl.indicator_range(row('Range', '1 \u2013 2')))

    def test_moved_reports_are_stubs_not_reports(self):
        with tempfile.TemporaryDirectory() as d:
            for fam, slug in (('fixed', 'sofr'), ('fixed', 'ust10y'), ('indicators', 'sofr')):
                rl.write_text(rd.report_path(slug, fam, repo=d), 'x')
            self.assertEqual([rd.slug_of(p) for p in rd.family_reports('fixed', d)], ['ust10y'])
            self.assertEqual(sorted(os.path.relpath(p, d).replace(os.sep, '/') for p in rd.report_paths(d, assets=True)),
                             ['reports/fixed/ust10y_analysis.html', 'reports/indicators/sofr_analysis.html'])
        for old, new in rd.MOVED_REPORTS.items():   # every stub redirects to its new page, keeping the anchor
            stub = rl.read_text(rd.report_path(old, repo=rd.ROOT))
            self.assertIn(f"location.replace('/reports/{new}_analysis.html' + location.hash)", stub)
            self.assertIn(f'url=/reports/{new}_analysis.html"', stub)
            self.assertIn('<meta name="robots" content="noindex">', stub)
            self.assertTrue(os.path.exists(rd.report_path(new, repo=rd.ROOT)))
        view = rl.read_text(os.path.join(rd.ROOT, 'reports', 'view.html'))   # and ?r=fixed/sofr still opens it
        for old, new in rd.MOVED_REPORTS.items():
            self.assertIn(f"'{old}': '{new}'", view)

    def test_report_path(self):
        self.assertEqual(rd.report_path('aapl', repo='r'), os.path.join('r', 'reports', 'aapl_analysis.html'))
        self.assertEqual(rd.report_path('voo', 'etf', repo='r'), os.path.join('r', 'reports', 'etf', 'voo_analysis.html'))

    def test_report_paths_leave_out_renamed_stubs_and_archived_reports(self):
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, 'reports', 'etf'))
            for rel in ('aapl', 'wbd', 'psky', 'skyd', os.path.join('etf', 'voo')):
                rl.write_text(os.path.join(repo, 'reports', rel + '_analysis.html'), 'x')
            slugs = lambda **kw: [rd.slug_of(p) for p in rd.report_paths(repo, **kw)]
            self.assertEqual(slugs(), ['aapl', 'skyd'])                      # psky is a redirect stub, wbd archived
            self.assertEqual(slugs(assets=True, archived=True), ['aapl', 'voo', 'skyd', 'wbd'])


if __name__ == '__main__':
    unittest.main()
