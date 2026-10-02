"""Unit tests for reportpatch.py: every writer on snippets of each template variant in the library (2 Oct 2026),
and the exactly-once rule.   Run: py -3 tools/run_checks.py"""
import unittest

from tests.fixtures import PAGE
import reportlib as rl
import reportpatch as rp


def row(label: str, value: str, ctx: str = 'context') -> str:
    return f'<tr><td>{label}</td><td>{value}</td><td>—</td><td>{ctx}</td></tr>'


def table(*rows: str) -> str:
    return '<table class="fin-table"><tbody>' + ''.join(rows) + '</tbody></table>'


class Numbers(unittest.TestCase):
    def test_format_like(self):
        self.assertEqual(rp.format_like('11.36', 11.0441), '11.04')
        self.assertEqual(rp.format_like('37.4', 30.7477), '30.7')
        self.assertEqual(rp.format_like('1,234.5', 1500.04), '1,500.0')
        self.assertEqual(rp.format_like('24', 1234.4), '1,234')
        self.assertEqual(rp.format_like('1234.50', 1500), '1500.00')     # a four-figure number without commas stays so

    def test_money(self):
        self.assertEqual(rp.money(1234.5), '1,234.50')
        self.assertEqual(rp.money(1234.5, '1100.00'), '1234.50')
        self.assertEqual(rp.money(99.999), '100.00')


class Header(unittest.TestCase):
    def test_price_variants(self):
        self.assertEqual(rl.header_price(rp.set_header_price(PAGE, 1300.1)), 1300.1)
        self.assertIn('$1,300.10', rp.set_header_price(PAGE, 1300.1))
        hd = '<span class="price"><span class="price-current">$305.48</span></span>'   # HD
        self.assertEqual(rp.set_header_price(hd, 311.2), '<span class="price"><span class="price-current">$311.20</span></span>')
        self.assertIn('$98.00', rp.set_header_price('<div class="price-now big">$97.10</div>', 98))

    def test_price_exactly_once(self):
        two = '<div class="price-current">$1.00</div><div class="price-current">$2.00</div>'
        with self.assertRaises(rp.PatchError) as e:
            rp.set_header_price(two, 3, 'reports/x_analysis.html')
        self.assertIn('reports/x_analysis.html: header price', str(e.exception))
        with self.assertRaises(rp.PatchError):
            rp.set_header_price('<div>no price</div>', 3)

    def test_change_down_to_up_adds_green(self):
        t = '<div class="price-change">−$0.19 (−0.76%)</div>'
        self.assertEqual(rp.set_header_change(t, 0.53, 2.1597),
                         '<div class="price-change" style="color:var(--green);">+$0.53 (+2.16%)</div>')

    def test_change_up_to_down(self):
        t = '<div class="price-change" style="color:var(--green);">▲ +$3.63 &nbsp;(+1.23%) &nbsp; Sep 18, 2026 close</div>'
        got = rp.set_header_change(t, -7.66, -2.7, dates=('2026-09-18', '2026-10-01'))
        self.assertEqual(got, '<div class="price-change" style="color:var(--red);">▼ −$7.66 &nbsp;(−2.70%)'
                              ' &nbsp; Oct 1, 2026 close</div>')

    def test_change_class_variants(self):
        unh = '<div class="price-chg neg mono">−$7.62 (−1.99%)</div>'
        self.assertEqual(rp.set_header_change(unh, 1.5, 0.4), '<div class="price-chg pos mono">+$1.50 (+0.40%)</div>')
        hd = '<span class="chg down">&minus;$5.39&nbsp;&nbsp;(&minus;1.73%)</span>'
        self.assertEqual(rp.set_header_change(hd, -1, -0.33), '<span class="chg down">&minus;$1.00&nbsp;&nbsp;(&minus;0.33%)</span>')
        self.assertEqual(rp.set_header_change(hd, 2, 0.66), '<span class="chg up">+$2.00&nbsp;&nbsp;(+0.66%)</span>')

    def test_change_prose_variants_are_left_to_the_builder(self):
        for t in ('<div class="price-change">+$38.80 (+7.35%) vs. Jul 31, 2026 close of $527.76</div>',   # AXON
                  '<div class="price-change">Session change not verified from sources fetched</div>',     # ED
                  '<div class="price-change" style="color:var(--text-muted);">$0.00 (0.00%) — unchanged</div>',
                  '<div class="price-change">+$1 (+1%)</div><div class="price-change">After-hours: $2.00 (−0.10%)</div>'):
            with self.assertRaises(rp.PatchError):
                rp.set_header_change(t, 1.0, 1.0)


class Banner(unittest.TestCase):
    def test_variants(self):
        cases = [
            ('⚠ Static data as of September 18, 2026 (Friday settled close) — prices',
             '⚠ Static data as of October 1, 2026 (Thursday settled close) — prices'),
            ('Static data as of August 28, 2026 close — prices', 'Static data as of October 1, 2026 close — prices'),
            ('Static data as of Friday, September 18, 2026 — prices', 'Static data as of Thursday, October 1, 2026 — prices'),
            ('Static data as of the September 18, 2026 close — x', 'Static data as of the October 1, 2026 close — x'),
        ]
        for old, new in cases:
            old_iso = '2026-08-28' if 'August' in old else '2026-09-18'
            self.assertEqual(rp.set_banner_date(old, old_iso, '2026-10-01'), (new, 0))

    def test_copies_in_their_own_style(self):
        t = ('<div>⚠ Static data as of August 18, 2026 — prices</div><div>⚠ STATIC DATA AS OF AUG 18, 2026</div>'
             '<div>Static data as of Aug 18, 2026. RSI measures</div><div>STATIC DATA AS OF AUGUST 18, 2026</div>'
             '<p>Static data as of July 1, 2026 is an older note</p>')
        got, copies = rp.set_banner_date(t, '2026-08-18', '2026-10-01')
        self.assertEqual(copies, 3)
        for s in ('as of October 1, 2026 — prices', 'STATIC DATA AS OF OCT 1, 2026<', 'as of Oct 1, 2026. RSI',
                  'STATIC DATA AS OF OCTOBER 1, 2026<', 'July 1, 2026 is an older'):
            self.assertIn(s, got)
        self.assertEqual(rl.as_of(got)[0], '2026-10-01')

    def test_refused(self):
        for t in ('⚠ Static data as of August 19–20, 2026 — prices',   # FCX: a range
                  '⚠ Static data as of August 18, 2026 — prices',       # not the date the caller says it is
                  'no banner'):
            with self.assertRaises(rp.PatchError):
                rp.set_banner_date(t, '2026-08-19', '2026-10-01')


class Labels(unittest.TestCase):
    def test_every_style_round_trips(self):
        for s, ymd in [('Sep 21', (2021, 9, None)), ("Sep '21", (2021, 9, None)), ('Sep 2021', (2021, 9, None)),
                       ('Sep 26*', (2026, 9, None)), ('Oct 1 26', (2026, 10, 1)), ('Sep 18 26', (2026, 9, 18)),
                       ("Sep 10 '26", (2026, 9, 10)), ('Sep 21, 2026', (2026, 9, 21)), ('Sep 21 2026', (2026, 9, 21)),
                       ('18 Sep 26', (2026, 9, 18)), ('Jun 1 26 (debut)', (2026, 6, 1))]:
            p = rp.point_label(s)
            assert p is not None, s
            self.assertEqual((p.year, p.month, p.day), ymd, s)
            self.assertEqual(rp.format_label(p.style, *ymd), s)
        for bad in ('Q3 2026', 'Jul 1', 'Sept 26', ''):
            self.assertIsNone(rp.point_label(bad), bad)

    def test_month_style_drops_the_day(self):
        p = rp.point_label("Sep '21")
        assert p
        self.assertEqual(rp.format_label(p.style, 2026, 10, 1), "Oct '26")


CHART = """<script>
const labels = ['Jul \\'26','Aug \\'26',
  'Sep 18 \\'26'];
const prices = [27.81, 24.76,
  299.57];
const events = [{ idx: 1, label: 'x' }, { idx: 2, label: 'y' }, { idx: 0, label: 'z' }];
const ma3 = sma(prices, 3);
</script>"""


class Chart(unittest.TestCase):
    def test_extends_keeping_the_unchanged_text(self):
        got = rp.set_chart_series(CHART, ["Jul '26", "Aug '26", "Sep '26", "Oct 1 '26"], [27.81, 24.76, 24.54, 25.07])
        self.assertIn("const labels = ['Jul \\'26','Aug \\'26','Sep \\'26','Oct 1 \\'26'];", got)
        self.assertIn('const prices = [27.81, 24.76, 24.54, 25.07];', got)
        self.assertIn("{ idx: 1, label: 'x' }", got)
        self.assertEqual(rl.chart_series(got), (["Jul '26", "Aug '26", "Sep '26", "Oct 1 '26"], [27.81, 24.76, 24.54, 25.07]))

    def test_unchanged_is_a_no_op_and_a_new_first_point_rewrites(self):
        self.assertEqual(rp.set_chart_series(CHART, ["Jul '26", "Aug '26", "Sep 18 '26"], [27.81, 24.76, 299.57]), CHART)
        got = rp.set_chart_series(CHART, ['A', 'B'], [1, 2.5])
        self.assertIn("const labels = ['A','B'];", got)
        self.assertIn('const prices = [1.00, 2.50];', got)

    def test_quote_styles_and_var(self):
        t = 'var labels = ["Aug 26", "Sep 26"]; var prices = [10,11];'
        got = rp.set_chart_series(t, ['Aug 26', 'Sep 26', "Oct '26"], [10, 11, 12])
        self.assertEqual(got, 'var labels = ["Aug 26", "Sep 26", "Oct \'26"]; var prices = [10,11,12.00];')

    def test_refused(self):
        with self.assertRaises(rp.PatchError):
            rp.set_chart_series(CHART, ['a'], [1, 2])
        with self.assertRaises(rp.PatchError):   # two label arrays
            rp.set_chart_series(CHART + "<script>const labels = ['x'];</script>", ['a'], [1])
        dow = CHART + '<script>const rsi = [null, 50.1, 48.2];</script>'   # DOW hard-codes ma3/ma10/rsi
        with self.assertRaises(rp.PatchError) as e:
            rp.set_chart_series(dow, ['a', 'b', 'c', 'd'], [1, 2, 3, 4])
        self.assertIn("'rsi' runs parallel", str(e.exception))


class FinTable(unittest.TestCase):
    T = table(row('Trailing <span class="tip" title="Price to 12.5 earnings">P/E</span>', '11.36'),
              row('Forward P/E', '9.9'),
              row('<span class="tip" title="x">EPS</span> (<span class="tip" title="y">TTM</span>)', '$2.18'),
              row('Dividend Yield', '<span title="1.5 a year">2.42%</span>'),
              row('52-Week Range', '$1,023.45 &ndash; $1,340.00'),
              row('Beta', 'n/m'))

    def test_set_fin_number(self):
        got = rp.set_fin_number(self.T, r'Trailing P/?E\b', 11.0441)
        self.assertIn('<td>11.04</td>', got)
        self.assertIn('<td>9.9</td>', got)                         # Forward P/E untouched
        got = rp.set_fin_number(self.T, 'Dividend Yield', 2.3933)
        self.assertIn('<span title="1.5 a year">2.39%</span>', got)   # the number in the attribute is not text
        self.assertEqual(rp.fin_row_texts(got, 'Dividend Yield'), ['Dividend Yield', '2.39%', '—', 'context'])
        self.assertIn('24.1x', rp.set_fin_number(table(row('Trailing P/E', '25.0x')), 'Trailing P/E', 24.08))

    def test_refused(self):
        with self.assertRaises(rp.PatchError):
            rp.set_fin_number(self.T, 'Beta', 1.2)                 # n/m
        with self.assertRaises(rp.PatchError):
            rp.set_fin_number(self.T + self.T, 'Beta', 1.2)        # two rows
        with self.assertRaises(rp.PatchError):
            rp.set_fin_row(self.T, 'ROIC', '1%')                   # none

    def test_set_fin_row_keeps_the_cell_attributes(self):
        t = table('<tr><td>ROE</td><td style="color:var(--red);">24.00%</td></tr>')
        self.assertIn('<td style="color:var(--red);">25.10%</td>', rp.set_fin_row(t, 'ROE', '25.10%'))

    def test_range(self):
        got = rp.set_range_52w(self.T, 1001.5, 1400)
        self.assertIn('$1,001.50 &ndash; $1,400.00', got)
        self.assertEqual(rl.range_52w(got), [1001.5, 1400.0])
        hd = ('<table class="metrics"><tr><td><span class="tip" title="52-Week Range: the lowest and highest">52-Week Range'
              '</span></td>\n<td class="tk neu">$289.10 – $426.75</td><td class="cmp">—</td><td class="ctx">At $305.48 HD sits'
              '</td></tr></table>')
        got = rp.set_range_52w(hd, 280, 430.5)
        self.assertIn('<td class="tk neu">$280.00 – $430.50</td>', got)
        self.assertIn('At $305.48 HD', got)                       # the context (prose) cell is not touched
        self.assertEqual(rl.range_52w(rp.set_range_52w(PAGE, 1, 2)), [1.0, 2.0])


if __name__ == '__main__':
    unittest.main()
