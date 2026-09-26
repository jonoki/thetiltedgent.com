"""Unit tests for the report tools.   Run from the repo root:  py -3 -m unittest discover -s tools/tests -v

Each test feeds a small, made-up page or record to one parser, so a change to the report markup rules shows up
here before it shows up as a wrong tag or a failed gate on the live library.
"""
import contextlib
import datetime
import io
import json
import os
import re
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # tools/

import asset_cards  # noqa: E402
import build_chips  # noqa: E402
import card_tags    # noqa: E402
import chart_audit  # noqa: E402
import chrome       # noqa: E402
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

    def test_tag_inputs_prefer_the_card_and_fall_back_to_the_table_pe(self):
        r = {'ticker': 'ACM', 'industry': 'BANKS - REGIONAL', 'as_of': '2026-09-21', 'price': 50.0, 'w52': [40.0, 100.0],
             'market_cap': '$250.0B', 'fcf': '$20.0B', 'eps_ttm': '$2.00', 'yield_pct': 3.1}
        card = {'ticker': 'ACME', 'card_industry': 'SOFTWARE', 'indices': {'sp500_added': '2001-01-01'}}
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
    def inputs(**kw) -> dict:
        d = {'slug': 'acme', 'ticker': 'ACME', 'as_of': '2026-09-21', 'industry': 'SOFTWARE', 'sp500': True,
             'raw': {'eps_ttm': '$2.00', 'market_cap': '$250.0B'}, 'price': 90.0, 'w52_high': 100.0, 'mcap': 50e9,
             'fcf': None, 'eps': 2.0, 'pe': 20.0, 'yield': None, 'revg': 5.0, 'roic': None, 'de': None, 'beta': 1.0,
             'fcf_yield': None}
        d.update(kw)
        return d

    def tags(self, **kw) -> list[str]:
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
        self.assertEqual(tuple(asset_cards.FAMILIES), rl.ASSET_FAMILIES)

    def test_report_path(self):
        self.assertEqual(rl.report_path('aapl', repo='r'), os.path.join('r', 'reports', 'aapl_analysis.html'))
        self.assertEqual(rl.report_path('voo', 'etf', repo='r'), os.path.join('r', 'reports', 'etf', 'voo_analysis.html'))


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

    INDEX = ('<section class="sgroup" data-s="industrials">'
             '<a class="rep" data-sp="1999-01-01" data-ndx href="view.html?r=acme"><span class="tick">ACME</span>'
             '<h3>Acme Widgets</h3><span class="sect">WIDGETS &amp; GEARS</span><span class="ixrow"></span></a>'
             '<a class="rep" href="view.html?r=gone"><span class="tick">GONE</span>'
             '<h3>Gone Co</h3><span class="sect">NOTHING</span><span class="ixrow"></span></a></section>')

    def test_manifest_main_builds_shards_reconciles_and_prunes(self):
        with tempfile.TemporaryDirectory() as repo:
            for d in ('reports', 'data/reports'):
                os.makedirs(os.path.join(repo, d))
            files = {'reports/index.html': self.INDEX, 'reports/acme_analysis.html': PAGE,
                     'reports/solo_analysis.html': PAGE.replace('ACME', 'SOLO'),
                     'data/reports/old-sector.json': '{}'}                      # left by an older build
            for rel, text in files.items():
                with open(os.path.join(repo, rel), 'w', encoding='utf-8') as fh:
                    fh.write(text)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(manifest.main([repo]), 0)
            doc = rl.load_manifest(repo)
            self.assertEqual(sorted(os.listdir(os.path.join(repo, 'data', 'reports'))), ['industrials.json', 'unclassified.json'])
            self.assertEqual(doc['index'], [['ACME', 'acme', 'industrials', '2026-09-10', 1234.5],
                                            ['SOLO', 'solo', None, '2026-09-10', 1234.5]])
            rec = doc['reconciliation']
            self.assertEqual((rec['uncarded'], rec['orphan_cards'], rec['structure_failures']), (['solo'], ['gone'], []))
            acme = rl.load_report_records(repo)['acme']
            self.assertEqual((acme['industry'], acme['sp500_added'], acme['ndx'], acme['w52']),
                             ('WIDGETS & GEARS', '1999-01-01', True, [1001.0, 1300.0]))
            self.assertIn('not_carded_on_index', rl.load_report_records(repo)['solo']['warnings'])

    def test_a_missing_index_page_is_an_error(self):
        with tempfile.TemporaryDirectory() as repo, self.assertRaises(FileNotFoundError):
            rl.parse_index_cards(repo)


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
        self.assertTrue(o['ok'], o)
        self.assertEqual((o['pe_stated'], o['pe_calc']), (24.1, 24.1))

    def test_each_gate_fails_on_its_own(self):
        self.assertFalse(self.check(PAGE, 'zzz_analysis.html')['ok'])                       # title/file mismatch
        self.assertFalse(self.check(PAGE.replace('1234.5];', '1230];'))['ok'])              # chart end != header
        self.assertFalse(self.check(PAGE.replace('</head>', ''))['ok'])                     # skeleton
        self.assertFalse(self.check(PAGE.replace('<canvas></canvas>', '', 1))['ok'])         # canvas count
        self.assertFalse(self.check(PAGE.replace('$1,300.00', '$1,200.00'))['ok'])           # price outside 52w
        self.assertFalse(self.check(PAGE.replace('52-Week Range', 'Range'))['ok'])            # no 52w range to check
        self.assertFalse(self.check(PAGE.replace('<body>', '<body><nav id="tg-sitenav"></nav>'))['ok'])

    def test_pe_is_reported_but_not_a_gate(self):
        o = self.check(PAGE.replace('24.1x', '30.0x'))
        self.assertTrue(o['ok'])
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
        warn = []
        eds, state = manifest.editions(deltabox.box(self.BOX), '2026-09-01', 816.64, warn)
        self.assertEqual((eds, state, warn), ([['2026-08-17', 994.79, 'previous edition'],
                                               ['2026-09-01', 816.64, 'refreshed']], 'fix', []))
        card = card_tags.card_for('acme', {}, {'editions': eds}, '', None, {}, None)
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


class Chrome(unittest.TestCase):
    def test_nav_marks_only_the_active_section(self):
        n = chrome.nav('tables')
        self.assertEqual(n.count('aria-current="page"'), 1)
        self.assertIn('<a href="/tables/casino-games.html" aria-current="page">The Tables</a>', n)
        self.assertNotIn('aria-current', chrome.nav(None))

    def test_a_page_keeps_its_own_fine_print(self):
        own = '<footer><p><b>The fine print, craps edition.</b> A practice table.</p></footer>'
        self.assertEqual(chrome.old_fine(own), '<b>The fine print, craps edition.</b> A practice table.')
        self.assertEqual(chrome.old_fine('<footer><p>Nothing here.</p></footer>'), chrome.SITE_FINE)

    def test_write_chrome_replaces_the_nav_once(self):
        page = ('<html><head><meta charset="UTF-8"><style></style></head><body><nav>old</nav>'
                '<footer><p><b>The fine print:</b> ours.</p></footer></body></html>')
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'page.html')
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(page)
            self.assertTrue(chrome.write_chrome(p, 'reports', True))
            self.assertFalse(chrome.write_chrome(p, 'reports', True))   # a second run changes nothing
            out = rl.read_text(p)
        self.assertIn('aria-current="page">Reports</a>', out)
        self.assertIn('<b>The fine print:</b> ours.', out)
        self.assertIn('<meta charset="UTF-8">\n' + chrome.JS_CLASS, out)
        self.assertIn(chrome.SITE_CSS + '\n<style>', out)
        self.assertIn(chrome.SITE_JS + '\n</body>', out)

    def test_missing_anchors_for_the_shared_wiring_are_errors(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'page.html')
            for page, missing in (('<html><head></head><body><nav></nav></body></html>', 'charset'),
                                  ('<html><head><meta charset="UTF-8"></head><body><nav></nav></html>', '</body>')):
                with open(p, 'w', encoding='utf-8') as fh:
                    fh.write(page)
                with self.assertRaisesRegex(ValueError, missing):
                    chrome.write_chrome(p, None, False)
            with open(p, 'w', encoding='utf-8') as fh:   # no stylesheet yet: site.css goes before </head>
                fh.write('<html><head><meta charset="UTF-8"></head><body><nav></nav></body></html>')
            chrome.write_chrome(p, None, False)
            self.assertIn(chrome.SITE_CSS + '\n</head>', rl.read_text(p))

    def test_a_page_without_a_nav_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'page.html')
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write('<html><body></body></html>')
            with self.assertRaises(ValueError):
                chrome.write_chrome(p, None, False)


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
                monthly, _ = chart_audit.yahoo('acme', 'ACME', '2026-09-21')
                self.assertIn((2026, 9), monthly)
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


class Chips(unittest.TestCase):
    def test_eight_alternating_edge_spots(self):
        s = build_chips.spots('#aaa', '#bbb')
        self.assertEqual(s.count('<path '), 8)
        self.assertEqual((s.count('#aaa'), s.count('#bbb')), (4, 4))

    def test_read_mark_names_the_missing_part(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'mark.svg')
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write('<svg><defs><linearGradient id="gold"></linearGradient></defs>'
                         + build_chips.MONOGRAM_GROUP + '<path d="M0 0"/></g></svg>')
            self.assertEqual(build_chips.read_mark(p),
                             ('<defs><linearGradient id="gold"></linearGradient></defs>', '<path d="M0 0"/>'))
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write('<svg><defs></defs></svg>')
            with self.assertRaisesRegex(ValueError, 'monogram group'):
                build_chips.read_mark(p)

    def test_a_chip_takes_its_own_gradients(self):
        font = unittest.mock.Mock(spec=build_chips.Font)
        font.text_path.return_value = ''
        defs = '<defs><radialGradient id="body">old</radialGradient><radialGradient id="disc">old</radialGradient></defs>'
        svg = build_chips.chip_svg(font, defs, '', build_chips.CHIPS[0])
        self.assertIn('<radialGradient id="body" cx="38%" cy="30%" r="78%"><stop offset="0" stop-color="#F4EBD6"/>', svg)
        self.assertIn('<stop offset="0.62" stop-color="#F1E6CF"/>', svg)
        self.assertIn('aria-label="The Tilted Gent $1 chip"', svg)
        self.assertNotIn('>old<', svg)


if __name__ == '__main__':
    unittest.main()
