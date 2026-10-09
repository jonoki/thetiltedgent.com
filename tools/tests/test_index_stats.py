"""Unit tests for index_stats.py: reading the members' cells, the aggregates and their coverage rule, the cells'
format, the column write and the fine-print rewrite.   Run: py -3 tools/run_checks.py"""
import unittest

import index_rank as ir
import index_stats as xs


def member(slug: str, mcap: float, price: float = 10.0) -> ir.Member:
    return ir.Member(slug, slug.upper(), '2026-09-01', price, mcap, mcap / price, None, True, False)


def figs(**kw: float | None) -> xs.Figures:
    base: dict[str, float | None] = dict(pe=None, fpe=None, dy=None, npm=None, gm=None, g=None, roe=None, de=None,
                                         beta=None, eps=None)
    base.update(kw)
    return xs.Figures(**base)   # type: ignore[arg-type]


class Cells(unittest.TestCase):
    def test_a_cell_counts_only_when_it_starts_with_its_number(self):
        self.assertEqual(xs.cell_figure('35.9×', 'pe'), 35.9)
        self.assertAlmostEqual(xs.cell_figure('+14.2%', 'g') or 0, 0.142)
        self.assertAlmostEqual(xs.cell_figure('−8.32% TTM', 'g') or 0, -0.0832)
        self.assertEqual(xs.cell_figure('~1.1', 'de'), 1.1)
        self.assertIsNone(xs.cell_figure('JP 34.3% · US 20.9%', 'npm'))

    def test_a_cell_the_page_does_not_stand_by_is_not_used(self):
        for cell in ('n/m ⚑', '42.36% (n/m)', '~79% (est.)', 'n/v', '83.2 n/m', '91.57% ⚠ NM'):
            self.assertIsNone(xs.cell_figure(cell, 'gm'), cell)

    def test_no_dividend_counts_as_zero(self):
        for cell in ('None', 'None (0.00%)', 'n/a', '—', '0% (common)'):
            self.assertEqual(xs.cell_figure(cell, 'dy'), 0.0, cell)
        self.assertAlmostEqual(xs.cell_figure('0.94% ($3.28)', 'dy') or 0, 0.0094)

    def test_member_figures_read_the_metrics_table(self):
        page = ('<table class="fin-table"><tr><th>Metric</th><th>ACME</th><th>Industry Avg</th><th>S&amp;P 500</th>'
                '<th>Context</th></tr>'
                '<tr><td>Trailing P/E</td><td>n/m</td><td>—</td><td>—</td><td></td></tr>'
                '<tr><td>EPS (TTM)</td><td>−$1.73 GAAP</td><td>—</td><td>—</td><td></td></tr>'
                '<tr><td>Dividend Yield</td><td>None</td><td>—</td><td>—</td><td></td></tr></table>')
        f = xs.member_figures(page)
        self.assertIsNone(f.pe)
        self.assertEqual(f.eps, -1.73)
        self.assertEqual(f.dy, 0.0)


class Flows(unittest.TestCase):
    def test_earnings_from_pe_else_from_eps_so_a_loss_counts(self):
        self.assertEqual(xs.flows(member('a', 1000.0), figs(pe=20.0), False).e, 50.0)
        self.assertEqual(xs.flows(member('b', 1000.0, price=10.0), figs(eps=-0.5), False).e, -50.0)

    def test_revenue_equity_and_debt_follow_from_earnings(self):
        f = xs.flows(member('a', 1000.0), figs(pe=20.0, npm=0.25, g=0.25, roe=0.5, de=2.0, gm=0.4), False)
        self.assertEqual((f.rev, f.prior, f.eq, f.debt, f.gp), (200.0, 160.0, 100.0, 200.0, 80.0))

    def test_signs_must_agree_and_lenders_have_no_debt_figure(self):
        f = xs.flows(member('a', 1000.0), figs(pe=20.0, npm=-0.1, roe=-0.2, de=1.0), True)
        self.assertIsNone(f.rev)
        self.assertIsNone(f.eq)
        self.assertIsNone(xs.flows(member('b', 1000.0), figs(pe=20.0, roe=0.2, de=1.0), True).debt)


class Aggregates(unittest.TestCase):
    def setUp(self) -> None:
        self.caps = {'a': 600.0, 'b': 300.0, 'c': 100.0}
        self.fl = {'a': xs.flows(member('a', 600.0), figs(pe=30.0, dy=0.01, beta=1.2), False),
                   'b': xs.flows(member('b', 300.0, price=10.0), figs(eps=-0.5, dy=0.02, beta=0.8), False),
                   'c': xs.flows(member('c', 100.0), figs(pe=10.0, beta=1.0), False)}

    def test_pe_is_aggregate_cap_over_aggregate_earnings_losses_included(self):
        # E: a 20, b -15 (shares 30 x -0.5), c 10 -> 1000 / 15
        self.assertAlmostEqual(xs.aggregate('pe', self.caps, self.fl).value or 0, 1000 / 15)

    def test_dividend_yield_is_aggregate_dividends_over_aggregate_cap(self):
        st = xs.aggregate('dy', self.caps, self.fl)
        self.assertAlmostEqual(st.coverage, 0.9)            # c has no dividend row
        self.assertAlmostEqual(st.value or 0, (6 + 6) / 900)

    def test_a_figure_below_coverage_is_a_dash(self):
        fl = dict(self.fl, a=self.fl['a']._replace(div=None))
        st = xs.aggregate('dy', self.caps, fl)
        self.assertIsNone(st.value)
        self.assertAlmostEqual(st.raw or 0, 6 / 300)

    def test_beta_is_one_by_definition_for_the_sp500_and_a_dash_for_the_nasdaq100(self):
        self.assertEqual(xs.index_stats('sp500', self.caps, self.fl)['beta'].value, 1.0)
        self.assertIsNone(xs.index_stats('ndx', self.caps, self.fl)['beta'].value)
        self.assertAlmostEqual(xs.index_stats('ndx', self.caps, self.fl)['beta'].raw or 0, 1.06)


class Format(unittest.TestCase):
    def test_the_company_cells_format(self):
        self.assertEqual(xs.render(26.125, 'pe', xs.cell_format('pe', '35.9×', '')), '26.1×')
        self.assertEqual(xs.render(0.12044, 'g', xs.cell_format('g', '+14.2%', '')), '+12.0%')
        self.assertEqual(xs.render(-0.0312, 'g', xs.cell_format('g', '+14.2%', '')), '−3.1%')
        self.assertEqual(xs.render(0.140812, 'npm', xs.cell_format('npm', '19.53%', '')), '14.08%')
        self.assertEqual(xs.render(0.78, 'de', xs.cell_format('de', '0.78', '')), '0.78')

    def test_defaults_when_the_company_cell_has_no_number(self):
        self.assertEqual(xs.render(20.44, 'fpe', xs.cell_format('fpe', 'n/m', 'x')), '20.4x')
        self.assertEqual(xs.render(0.0108, 'dy', xs.cell_format('dy', 'None', '')), '1.1%')

    def test_rows_naming_one_period_or_another_basis_are_not_filled(self):
        self.assertIsNone(xs.row_key('Revenue Growth (FY2025)'))
        self.assertIsNone(xs.row_key('P/E on Operating EPS'))
        self.assertIsNone(xs.row_key('ROE, reported (Q2 2026)'))
        self.assertEqual(xs.row_key('Forward P/E (FY2026)'), 'fpe')
        self.assertEqual(xs.row_key('Beta (5Y)'), 'beta')


TABLE = ('<table class="fin-table">\n'
         '    <thead><tr><th>Metric</th><th>ACME</th><th>Industry Avg</th><th>S&amp;P 500 (est.)</th><th>Context</th></tr></thead>\n'
         '    <tbody>\n'
         '      <tr><td>Trailing P/E</td><td style="color:var(--red);">35.9×</td><td>~24×</td><td>~33×</td><td>Rich.</td></tr>\n'
         '      <tr><td>PEG Ratio</td><td>3.15</td><td>~1.9</td><td>~2.1</td><td>.</td></tr>\n'
         '      <tr><td>Revenue Growth (FY2025)</td><td>+6.4%</td><td>—</td><td>~+5%</td><td>.</td></tr>\n'
         '      <tr><td>Beta</td><td>1.09</td><td>~1.05</td><td style="color:var(--green);">~1.15</td><td>.</td></tr>\n'
         '    </tbody>\n'
         '  </table>')


def stat(v: float | None) -> xs.Stat:
    return xs.Stat(v, 1.0, 1, 0, v)


class Column(unittest.TestCase):
    def test_header_cells_and_colour(self):
        stats = {k: stat(None) for k in xs.ROWS} | {'pe': stat(26.13), 'g': stat(0.12), 'beta': stat(1.0)}
        new, counts, index = xs.write_column(TABLE, stats)
        self.assertEqual(index, 'sp500')
        self.assertIn('<th>S&amp;P 500</th>', new)
        self.assertIn('<td>~24×</td><td>26.1×</td>', new)              # industry and company cells untouched
        self.assertIn('<td style="color:var(--red);">35.9×</td>', new)
        self.assertIn('<td>~1.9</td><td>—</td>', new)                  # PEG: no aggregate
        self.assertIn('<td>—</td><td>—</td><td>.</td>', new)           # FY2025 growth: not the aggregate's basis
        self.assertIn('<td>~1.05</td><td>1.00</td>', new)               # colour gone
        self.assertEqual(counts, {'pe': 1, 'beta': 1, '—': 2})
        self.assertEqual(xs.write_column(new, stats)[0], new)


def page(prose: str, disclaimer: str) -> str:
    return ('<div class="section">\n  <div class="section-title"><span class="num">04</span> Key Financial Metrics</div>\n'
            f'  <p class="prose">{prose}</p>\n  {TABLE}\n</div>\n'
            f'<div class="disclaimer">\n  <p>Data as of August 10, 2026.</p>\n  <p>{disclaimer}</p>\n'
            '  <p>This document is for educational purposes only.</p>\n</div>\n')


class FinePrint(unittest.TestCase):
    def run_twice(self, t: str) -> tuple[str, list[str]]:
        new, _, left = xs.rewrite_fine_print(t, 'sp500', 'August 10, 2026')
        again, notes, _ = xs.rewrite_fine_print(new, 'sp500', 'August 10, 2026')
        self.assertEqual(again, new)
        self.assertEqual(notes, [])
        return new, left

    def test_a_pair_keeps_its_industry_half_and_the_methods_sentence_follows(self):
        new, left = self.run_twice(page('ACME vs peers.', 'Sources: SEC. Industry-average and S&amp;P 500 columns '
                                        'in Section 04 are "—". Prices from Yahoo.'))
        self.assertIn('The figures in the industry-average column in Section 04 are "—". S&amp;P 500 column in '
                      'Section 04: our aggregate', new)
        self.assertIn('(formulas in the finance glossary). Prices from Yahoo.', new)
        self.assertEqual(left, [])

    def test_a_clause_about_the_index_alone_goes_and_a_list_item_keeps_its_heading(self):
        new, _ = self.run_twice(page('Industry and index averages are approximations from screener data.',
                                     '<strong>Estimates:</strong> the "S&amp;P 500" column of the metrics table; '
                                     'competitor revenue. The S&amp;P 500 column uses SPY as a proxy.'))
        self.assertIn('Industry averages are approximations from screener data.', new)
        self.assertIn('<strong>Estimates:</strong> competitor revenue.', new)
        self.assertNotIn('SPY', new)
        self.assertEqual(new.count('column in Section 04: our aggregate'), 1)

    def test_true_statements_about_the_index_stay_and_the_date_is_kept_current(self):
        t = page('x.', 'The benchmark index is the <strong>S&amp;P 500</strong>, which ACME joined in 2008. '
                       'Market-cap ranks: our calculation on August 10, 2026 — shares × closing price for every index '
                       'member.')
        new, _ = self.run_twice(t)
        self.assertIn('which ACME joined in 2008.', new)
        self.assertIn('every index member. S&amp;P 500 column in Section 04', new)
        later, _, _ = xs.rewrite_fine_print(new, 'sp500', 'October 2, 2026')
        self.assertIn('weighted by market cap on October 2, 2026', later)
        self.assertEqual(later.count('column in Section 04: our aggregate'), 1)

    def test_what_cannot_be_rewritten_is_listed(self):
        _, left = self.run_twice(page('x.', 'The S&amp;P 500 column in Section 04, and any Industry Avg cell marked '
                                            '"est.", are estimates.'))
        self.assertEqual(len(left), 1)


if __name__ == '__main__':
    unittest.main()
