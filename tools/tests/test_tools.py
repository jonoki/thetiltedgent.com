"""Unit tests for the report tools.   Run from the repo root:  py -3 -m unittest discover -s tools/tests -v

Each test feeds a small, made-up page or record to one parser, so a change to the report markup rules shows up
here before it shows up as a wrong tag or a failed gate on the live library.
"""
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # tools/

import asset_cards  # noqa: E402
import card_tags    # noqa: E402
import deltabox     # noqa: E402
import manifest     # noqa: E402
import reportlib as rl   # noqa: E402
import style_tags   # noqa: E402
import verify       # noqa: E402

PAGE = """<!DOCTYPE html>
<html lang="en"><head><title>ACME — Acme Widgets Inc. | Stock Analysis</title><style>body{}</style></head>
<body>
<div class="price-current">$1,234.50</div>
<p>Static data as of September 10, 2026 (market close). HQ: Springfield, Illinois</p>
<table class="fin-table"><tbody>
<tr><td>Trailing P/E</td><td>24.1x</td></tr>
<tr><td>EPS (TTM)</td><td>$51.22</td></tr>
<tr><td>52-Week Range</td><td>$1,001.00 &ndash; $1,300.00</td></tr>
</tbody></table>
<canvas></canvas><canvas></canvas>
<script>const labels = ['Sep \\'21', "Oct '21", `Nov 21`]; const prices = [1100.5,1200,1234.5];</script>
</body></html>
"""


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


class ManifestFields(unittest.TestCase):
    def test_as_of_date_range_takes_the_first_day(self):
        warn = []
        self.assertEqual(manifest.as_of_date('Static data as of August 19–20, 2026', warn), '2026-08-19')
        self.assertEqual(warn, ['as_of_was_a_date_range'])

    def test_unparseable_page_gives_warnings_not_a_crash(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'blank_analysis.html')
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write('<html></html>')
            rec = manifest.extract(p, {})
        self.assertNotIn('price', rec)
        self.assertIn('price_missing', rec['warnings'])
        self.assertIn('title_unparsed', rec['warnings'])


class AssetCards(unittest.TestCase):
    def test_first_sentence_does_not_split_on_us(self):
        page = ('<body><div class="section-title">01 What it is</div><p>What it is. The U.S. government borrows for ten '
                'years through this note. It pays interest twice a year.</p><div class="section">')
        self.assertEqual(asset_cards.first_sentence(page), 'The U.S. government borrows for ten years through this note.')


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


class ManifestRecords(unittest.TestCase):
    def test_only_listed_shards_are_read(self):
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, 'data', 'reports'))
            def dump(rel, obj):
                with open(os.path.join(repo, rel), 'w', encoding='utf-8') as fh:
                    json.dump(obj, fh)
            dump('data/reports.json', {'shards': {'energy': 'data/reports/energy.json'}})
            dump('data/reports/energy.json', {'reports': [{'slug': 'apa', 'price': 43.81}]})
            dump('data/reports/unclassified.json', {'reports': [{'slug': 'apa', 'price': 1.0}]})   # stale
            self.assertEqual(rl.load_report_records(repo), {'apa': {'slug': 'apa', 'price': 43.81}})


class HeadOffice(unittest.TestCase):
    def label(self, hq):
        h = card_tags.hq_of('x', 'HQ: ' + hq)
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


class Verify(unittest.TestCase):
    def check(self, page, name='acme_analysis.html'):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, name)
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(page)
            return verify.check(p)

    def test_a_sound_page_passes(self):
        o = self.check(PAGE)
        self.assertTrue(o['OK'], o)
        self.assertEqual((o['pe_stated'], o['pe_calc']), (24.1, 24.1))

    def test_each_gate_fails_on_its_own(self):
        self.assertFalse(self.check(PAGE, 'zzz_analysis.html')['OK'])                       # title/file mismatch
        self.assertFalse(self.check(PAGE.replace('1234.5];', '1230];'))['OK'])              # chart end != header
        self.assertFalse(self.check(PAGE.replace('</head>', ''))['OK'])                     # skeleton
        self.assertFalse(self.check(PAGE.replace('<canvas></canvas>', '', 1))['OK'])         # canvas count
        self.assertFalse(self.check(PAGE.replace('$1,300.00', '$1,200.00'))['OK'])           # price outside 52w
        self.assertFalse(self.check(PAGE.replace('<body>', '<body><nav id="tg-sitenav"></nav>'))['OK'])

    def test_pe_is_reported_but_not_a_gate(self):
        o = self.check(PAGE.replace('24.1x', '30.0x'))
        self.assertTrue(o['OK'])
        self.assertEqual((o['pe_stated'], o['pe_calc']), (30.0, 24.1))

    def test_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            good, bad = os.path.join(d, 'acme_analysis.html'), os.path.join(d, 'zzz_analysis.html')
            for p in (good, bad):
                with open(p, 'w', encoding='utf-8') as fh:
                    fh.write(PAGE)
            with open(os.devnull, 'w') as null:
                out, sys.stdout = sys.stdout, null
                try:
                    self.assertEqual(verify.main([good]), 0)
                    self.assertEqual(verify.main([good, bad]), 1)
                finally:
                    sys.stdout = out


class DeltaBox(unittest.TestCase):
    def test_day_has_no_leading_zero_on_any_platform(self):
        self.assertEqual(deltabox.day(datetime.date(2026, 9, 1)), '1 Sep 2026')
        self.assertEqual(deltabox.day(datetime.date(2026, 8, 17)), '17 Aug 2026')

    def test_box_marks_direction_and_carries_the_prior_edition(self):
        b = deltabox.box(deltabox.EDITIONS['stx'])
        self.assertIn('tg-d--price', b)
        self.assertIn('data-prior-as-of="2026-08-17"', b)
        self.assertIn('tg-d-pct dn', b)
        self.assertIn('17 Aug 2026 &rarr; 1 Sep 2026 &middot; 15 days', b)


if __name__ == '__main__':
    unittest.main()
