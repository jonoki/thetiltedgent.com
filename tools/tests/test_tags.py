"""Unit tests for the card data: style tags, head office, the what-changed box (style_tags, headoffice, card_tags, deltabox).   Run from the repo root:  py -3 -m unittest discover -s tools/tests -v"""
import datetime
import os
import tempfile
import unittest
from typing import Any, cast

from fixtures import PAGE
import card_tags  # noqa: E402
import deltabox  # noqa: E402
import headoffice  # noqa: E402
import manifest  # noqa: E402
import style_tags  # noqa: E402
import reportlib as rl  # noqa: E402


class StyleTagInputs(unittest.TestCase):
    def test_quantile_and_rank_set_the_twenty_percent_cutoffs(self):
        vals = [1, 2, 3, 4, 5]
        self.assertEqual(style_tags.quantile(vals, 0.2), 1.8)
        self.assertEqual(style_tags.quantile(vals, 0.8), 4.2)
        self.assertEqual(style_tags.pct_rank(4, vals), 60)   # share strictly below, in %

    def test_table_rows_reads_the_fin_table(self):
        page = PAGE.replace('<tr><td>EPS (TTM)</td>', '<tr><td>Revenue Growth</td><td>12.5%</td></tr><tr><td>Beta</td><td>1.10</td></tr><tr><td>EPS (TTM)</td>')
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'acme_analysis.html')
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(page)
            rows = style_tags.table_rows(p)
        self.assertEqual(rows, {'pe_tbl': '24.1x', 'revg': '12.5%', 'beta': '1.10'})

    def test_tag_inputs_prefer_the_card_and_fall_back_to_the_table_pe(self):
        r: rl.ReportRecord = {'ticker': 'ACM', 'industry': 'BANKS - REGIONAL', 'as_of': '2026-09-21', 'price': 50.0, 'w52': [40.0, 100.0],
             'market_cap': '$250.0B', 'fcf': '$20.0B', 'eps_ttm': '$2.00', 'yield_pct': 3.1}
        card: rl.IndexCard = {'ticker': 'ACME', 'card_name': 'Acme', 'card_industry': 'SOFTWARE', 'card_sector_key': None,
                              'indices': {'sp500_added': '2001-01-01', 'nasdaq100': False, 'dow30_added': None,
                                          'global_exchange': None}}
        d = style_tags.tag_inputs('acme', r, card, {'pe_tbl': '25.0x', 'beta': '0.8'})
        self.assertEqual((d['ticker'], d['industry'], d['sp500'], d['pe'], d['beta']), ('ACME', 'SOFTWARE', True, 25.0, 0.8))
        self.assertEqual((d['mcap'], d['fcf_yield'], d['w52_high']), (250e9, 8.0, 100.0))
        d = style_tags.tag_inputs('acme', r, None, {})
        self.assertEqual((d['ticker'], d['sp500'], d['fcf_yield'], d['pe']), ('ACM', False, None, None))   # banks: no FCF yield


class StyleTagRules(unittest.TestCase):
    TH = {'value_pe_max': 15.0, 'pe_median': 22.0, 'growth_revg_min': 12.0, 'revg_median': 5.0,
          'income_yield_min': 3.0, 'yield_median': 1.5, 'cash_fcfy_min': 6.0, 'fcfy_median': 3.5,
          'steady_beta_max': 0.7, 'rollercoaster_beta_min': 1.4, 'quality_roic_min': 20.0, 'roic_median': 10.0,
          'quality_de_max': 1.0, 'giant_mcap_min': 200e9, 'beaten_down_ratio': 0.6}
    U = {k: [1.0, 5.0, 10.0, 20.0, 30.0] for k in ('pe', 'revg', 'yield', 'fcf_yield', 'beta', 'roic')}

    @staticmethod
    def inputs(**kw: Any) -> style_tags.TagInputs:
        d: dict[str, Any] = {'slug': 'acme', 'ticker': 'ACME', 'as_of': '2026-09-21', 'industry': 'SOFTWARE', 'sp500': True,
             'raw': {'eps_ttm': '$2.00', 'market_cap': '$250.0B'}, 'price': 90.0, 'w52_high': 100.0, 'mcap': 50e9,
             'fcf': None, 'eps': 2.0, 'pe': 20.0, 'yield': None, 'revg': 5.0, 'roic': None, 'de': None, 'beta': 1.0,
             'fcf_yield': None}
        d.update(kw)
        return cast(style_tags.TagInputs, d)

    def tags(self, **kw: Any) -> list[str]:
        return [t for t, _ in style_tags.tags_for(self.inputs(**kw), self.TH, self.U)]

    def test_each_tag_at_its_cutoff(self):
        self.assertEqual(self.tags(), [])
        self.assertEqual(self.tags(pe=15.0), ['Value'])
        self.assertEqual(self.tags(pe=15.0, eps=-1.0), ['Not yet profitable'])   # no Value tag for a loss-maker
        self.assertEqual(self.tags(revg=12.0), ['Growth'])
        self.assertEqual(self.tags(**{'yield': 3.0}), ['Income'])
        self.assertEqual(self.tags(fcf_yield=6.0), ['Cash machine'])
        self.assertEqual(self.tags(mcap=200e9), ['Giant'])
        self.assertEqual(self.tags(price=60.0), ['Beaten down'])
        self.assertEqual(self.tags(beta=0.7), ['Steady'])
        self.assertEqual(self.tags(beta=1.4), ['Rollercoaster'])
        self.assertEqual(self.tags(beta=None), [])

    def test_quality_needs_high_roic_low_debt_and_no_balance_sheet_business(self):
        self.assertEqual(self.tags(roic=20.0, de=0.5), ['Quality'])
        self.assertEqual(self.tags(roic=20.0, de=1.0), [])      # debt-to-equity must be under the cut-off
        self.assertEqual(self.tags(roic=20.0, de=-0.1), [])     # negative equity is not low debt
        self.assertEqual(self.tags(roic=20.0, de=0.5, industry='REIT - OFFICE'), [])
        self.assertEqual(self.tags(roic=20.0, de=0.5, industry='BANKS - REGIONAL'), [])

    def test_tooltips_carry_the_date_unless_there_is_none(self):
        (_, tip), = style_tags.tags_for(self.inputs(pe=15.0), self.TH, self.U)
        self.assertTrue(tip.endswith(' Figures as of Sep 21, 2026.'), tip)
        (_, tip), = style_tags.tags_for(self.inputs(pe=15.0, as_of=None), self.TH, self.U)
        self.assertTrue(tip.endswith('the cheapest 20%.'), tip)


class HeadOffice(unittest.TestCase):
    def label(self, hq):
        h = headoffice.hq_of('x', 'HQ: ' + hq)
        return h[0] if h else None

    def test_us_head_offices(self):
        for hq in ('Cupertino, California', 'Charleston, West Virginia', 'New York, New York', 'Providence, Rhode Island',
                   'Manchester, New Hampshire', 'Round Rock, TX 78682', 'Washington, D.C.'):
            self.assertEqual(self.label(hq), 'US-based', hq)

    def test_street_and_city_words_are_not_states(self):
        # the three live cards this regex used to tag US-based (fixed 26 Sep 2026)
        self.assertEqual(self.label('960-1 West Wen Yi Road, Yu Hang District, Hangzhou, China'), 'China-based')
        self.assertEqual(self.label('935 de La Gauchetière Street West, Montreal, Quebec'), 'Canada-based')
        self.assertEqual(self.label('Parkmore Business Park West, Ballybrit, Galway, Ireland'), 'Ireland-based')
        self.assertEqual(self.label('New Delhi, India'), 'India-based')
        self.assertEqual(self.label('Charlottetown, Prince Edward Island'), 'Canada-based')
        self.assertEqual(self.label('Chichester, West Sussex, England'), 'UK-based')

    def test_unreducible_text_gets_no_tag(self):
        self.assertIsNone(self.label('Offices across several continents and a registered seat elsewhere'))


class DeltaBox(unittest.TestCase):
    def test_day_has_no_leading_zero_on_any_platform(self):
        self.assertEqual(deltabox.day(datetime.date(2026, 9, 1)), '1 Sep 2026')
        self.assertEqual(deltabox.day(datetime.date(2026, 8, 17)), '17 Aug 2026')

    BOX = deltabox.DeltaBox(prior_date='2026-08-17', prior_price=994.79, as_of='2026-09-01', price=816.64,
                            state='fix', claim='It fell.', paras=['One.', 'Two.'], check='Checked.')

    def test_box_marks_direction_and_carries_the_prior_edition(self):
        b = deltabox.box(self.BOX)
        self.assertIn('tg-d--fix', b)
        self.assertIn('<span class="tg-d-tag">Corrected in this edition</span>', b)
        self.assertIn('data-prior-as-of="2026-08-17"', b)
        self.assertIn('tg-d-pct dn">-17.9%', b)
        self.assertIn('17 Aug 2026 &rarr; 1 Sep 2026 &middot; 15 days', b)
        self.assertIn('<p>One.</p>\n  <p>Two.</p>', b)

    def test_the_box_round_trips_through_the_manifest_to_the_card(self):
        """deltabox writes the prior edition into the page; manifest reads it back; card_tags shows it."""
        warn: list[str] = []
        eds, state = manifest.editions(deltabox.box(self.BOX), '2026-09-01', 816.64, warn)
        self.assertEqual((eds, state, warn), ([['2026-08-17', 994.79, 'previous edition'],
                                               ['2026-09-01', 816.64, 'refreshed']], 'fix', []))
        card = card_tags.card_for('acme', StyleTagRules.inputs(), {'editions': eds}, '', None, {}, None)
        self.assertEqual(card['ed'], ['2026-09-01', '2026-08-17', 994.79])

    def test_insert_box_adds_css_once_and_never_a_second_box(self):
        page = ('<html><head><style>a{}</style><style>b{}</style></head><body>\n'
                '<!-- ======== 01 COMPANY OVERVIEW ======== -->\n</body></html>')
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'acme_analysis.html')
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(page)
            self.assertTrue(deltabox.insert_box(p, self.BOX))
            self.assertFalse(deltabox.insert_box(p, self.BOX))
            t = rl.read_text(p)
        self.assertEqual(t.count(deltabox.CSS), 1)
        self.assertLess(t.index('<style>b{}' + deltabox.CSS), t.index('</style></head>'))   # before the last </style>
        self.assertLess(t.index('class="tg-d '), t.index('01 COMPANY OVERVIEW'))


if __name__ == '__main__':
    unittest.main()
