"""Unit tests for the site writers: asset cards, chrome, chip masters.   Run: py -3 tools/run_checks.py"""
import contextlib
import io
import os
import re
import tempfile
import unittest
import unittest.mock

import asset_cards
import build_chips
import chrome
import reportlib as rl
import repodata as rd


class AssetCards(unittest.TestCase):
    def test_first_sentence_does_not_split_on_us(self):
        page = ('<body><div class="section-title">01 What it is</div><p>What it is. The U.S. government borrows for ten '
                'years through this note. It pays interest twice a year.</p><div class="section">')
        self.assertEqual(asset_cards.first_sentence(page), 'The U.S. government borrows for ten years through this note.')

    INDEX = ('<a data-fam="stocks"><b class="fam-n">0</b></a><a data-fam="etf"><b class="fam-n">0</b></a>'
             '<a data-fam="crypto"><b class="fam-n">9</b></a><a data-fam="fixed"><b class="fam-n">9</b></a>\n'
             '<a class="rep" href="view.html?r=aapl">AAPL</a>\n'
             + ''.join(f'<!-- asset-cards:{f} old -->x<!-- /asset-cards:{f} -->\n' for f in ('etf', 'crypto', 'fixed')))
    VOO = ('<html><head><title>VOO — Vanguard S&amp;P 500 ETF | ETF Analysis</title></head><body><section class="section">'
           '<div class="section-title">01 What it is</div><p>What it is. VOO holds the five hundred largest US companies '
           'in one fund. Cheap.</p></section></body></html>')

    HUB = '<main>\n<!-- indicator-cards old -->x<!-- /indicator-cards -->\n</main>'

    def repo_with(self, repo: str, index: str, hub: str | None = None) -> None:
        os.makedirs(os.path.join(repo, 'reports', 'etf'))
        with open(os.path.join(repo, 'reports', 'index.html'), 'w', encoding='utf-8') as fh:
            fh.write(index)
        with open(os.path.join(repo, 'reports', 'etf', 'voo_analysis.html'), 'w', encoding='utf-8') as fh:
            fh.write(self.VOO)
        rl.write_text(os.path.join(repo, asset_cards.HUB), self.HUB if hub is None else hub)

    def test_the_indicator_hub_links_built_pages_and_marks_the_rest_coming(self):
        with tempfile.TemporaryDirectory() as repo, contextlib.redirect_stdout(io.StringIO()):
            self.repo_with(repo, self.INDEX)
            rl.write_text(os.path.join(repo, 'reports', 'indicators', 'sofr_analysis.html'), 'x')
            rl.write_text(os.path.join(repo, 'reports', 'fixed', 'sofr_analysis.html'), 'stub')   # a moved report's stub
            self.assertEqual(asset_cards.main(['--repo', repo]), 0)
            hub = rl.read_text(os.path.join(repo, asset_cards.HUB))
            index = rl.read_text(os.path.join(repo, 'reports', 'index.html'))
        self.assertIn('<a class="card ind" href="/reports/view.html?r=indicators/sofr"><span class="code">SOFR</span>', hub)
        self.assertIn('<div class="card ind soon"><span class="code">CPI</span>', hub)
        self.assertEqual(hub.count('class="card ind'), sum(len(cards) for _, _, cards in asset_cards.INDICATOR_HUB))
        self.assertEqual(hub.count('<span class="coming">Coming</span>'), hub.count('class="card ind soon"'))
        for gid in ('g-rates', 'g-inflation', 'g-jobs'):   # learn/index.html links to these anchors
            self.assertIn(f'id="{gid}"', hub)
        self.assertNotIn('fixed/sofr', index)   # the stub is not a Bonds & cash card
        self.assertIn('<h2 class="shead">Bonds &amp; cash <span class="scount">0</span></h2>', index)

    def test_an_indicator_page_missing_from_the_hub_stops_the_script(self):
        with tempfile.TemporaryDirectory() as repo, contextlib.redirect_stdout(io.StringIO()):
            self.repo_with(repo, self.INDEX)
            rl.write_text(os.path.join(repo, 'reports', 'indicators', 'gdp_analysis.html'), 'x')
            self.assertIn("add ['gdp'] to INDICATOR_HUB", str(asset_cards.main(['--repo', repo])))
        with tempfile.TemporaryDirectory() as repo, contextlib.redirect_stdout(io.StringIO()):
            self.repo_with(repo, self.INDEX, hub='<main></main>')
            self.assertIn('marker for the indicator cards', str(asset_cards.main(['--repo', repo])))
            self.assertEqual(rl.read_text(os.path.join(repo, 'reports', 'index.html')), self.INDEX)   # nothing written

    def test_hub_slugs_are_the_audited_series(self):
        import indicator_audit
        self.assertEqual({c[0] for _, _, cards in asset_cards.INDICATOR_HUB for c in cards}, set(indicator_audit.SERIES))

    def test_main_writes_the_cards_and_tab_counts(self):
        with tempfile.TemporaryDirectory() as repo, contextlib.redirect_stdout(io.StringIO()):
            self.repo_with(repo, self.INDEX)
            self.assertEqual(asset_cards.main(['--repo', repo]), 0)
            t = rl.read_text(os.path.join(repo, 'reports', 'index.html'))
        self.assertIn('<span class="tick">VOO</span><h3>Vanguard S&amp;P 500 ETF</h3><span class="sect">S&amp;P 500</span>', t)
        self.assertIn('VOO holds the five hundred largest US companies in one fund.', t)
        self.assertIn('<h2 class="shead">Bonds &amp; cash <span class="scount">0</span></h2>', t)
        counts = dict(re.findall(r'data-fam="(\w+)"><b class="fam-n">(\d+)</b>', t))
        self.assertEqual(counts, {'stocks': '1', 'etf': '1', 'crypto': '0', 'fixed': '0'})

    def test_a_missing_tab_count_is_an_error_and_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as repo, contextlib.redirect_stdout(io.StringIO()):
            index = self.INDEX.replace('<a data-fam="fixed"><b class="fam-n">9</b></a>', '')
            self.repo_with(repo, index)
            self.assertIn('fixed tab', str(asset_cards.main(['--repo', repo])))
            self.assertEqual(rl.read_text(os.path.join(repo, 'reports', 'index.html')), index)


class Chrome(unittest.TestCase):
    def test_nav_marks_only_the_active_section(self):
        n = chrome.nav('tables')   # a section is a <details>; its summary carries the mark
        self.assertEqual(n.count('class="on"'), 1)
        self.assertIn('<summary class="on">The Tables</summary>', n)
        self.assertNotIn('aria-current', n)
        self.assertEqual(chrome.nav('about').count('aria-current="page"'), 1)
        self.assertNotIn('aria-current', chrome.nav(None))
        self.assertNotIn('class="on"', chrome.nav(None))

    def test_nav_sections_and_badges(self):
        n = chrome.nav(None)
        self.assertEqual(n.count('<details class="navmenu"'), 3)
        for href in ('/tables/craps-table.html', '/tables/blackjack-trainer.html', '/reports/?f=etf', '/reports/?f=fixed',
                     '/learn/', '/learn/table-talk/finance.html', '/learn/table-talk/poker.html', '/learn/indicators/'):
            self.assertIn(f'<a href="{href}">', n)
        self.assertIn('data-menu="learn"><summary>Learn</summary>', n)   # Learn is a section now, not Soon
        self.assertNotIn('Learn <span class="soon">', n)
        self.assertIn('Le Degens <span class="soon">Soon</span></a>', n)
        self.assertNotIn('/glossary/', n)   # the old glossary URLs are redirect stubs only
        self.assertNotIn('/#tools', n)   # the Toolbox is a homepage section, in the footer only
        self.assertIn('/#tools', chrome.footer(chrome.SITE_FINE))

    def test_asset_stamp_replaces_an_old_one(self):
        with tempfile.TemporaryDirectory() as repo:
            p = os.path.join(repo, 'x.html')
            rl.write_text(p, '<html><head><meta charset="UTF-8">\n<link rel="stylesheet" href="/assets/site.css?v=1">\n'
                             '</head><body><nav>x</nav>\n<script src="/assets/site.js" defer></script>\n</body></html>')
            chrome.write_chrome('x.html', None, False, repo)
            out = rl.read_text(p)
        self.assertEqual(out.count('/assets/site.css'), 1)
        self.assertEqual(out.count('/assets/site.js'), 1)
        self.assertIn(chrome.SITE_CSS, out)
        self.assertIn(chrome.SITE_JS, out)

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
        self.assertIn('<summary class="on">Reports</summary>', out)
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


class LibraryMoves(unittest.TestCase):
    """Renamed and archived stock reports (tools/repodata.py RENAMED, ARCHIVED), checked on the repo itself."""

    def test_a_renamed_report_redirects_and_the_viewer_maps_it(self):
        view = rl.read_text(os.path.join(rd.ROOT, 'reports', 'view.html'))
        moved = dict(re.findall(r"(\w+): '(\w+)'", re.search(r'var moved = \{(.*?)\};', view).group(1)))
        cards = rd.parse_index_cards()
        for old, new in rd.RENAMED.items():
            self.assertEqual(moved.get(old), new)
            self.assertTrue(os.path.exists(rd.report_path(new)))
            stub = rl.read_text(rd.report_path(old))
            self.assertIn(f"location.replace('/reports/{new}_analysis.html' + location.hash)", stub)
            self.assertIn(f'url=/reports/{new}_analysis.html', stub)
            self.assertNotIn(old, cards)
            self.assertIn(new, cards)

    def test_an_archived_report_keeps_its_page_and_line_but_no_card(self):
        cards = rd.parse_index_cards()
        for slug, line in rd.ARCHIVED.items():
            self.assertIn(line, rl.read_text(rd.report_path(slug)))
            self.assertNotIn(slug, cards)


if __name__ == '__main__':
    unittest.main()
