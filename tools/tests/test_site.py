"""Unit tests for the site writers: asset cards, chrome, chip masters.   Run from the repo root:  py -3 -m unittest discover -s tools/tests -v"""
import os
import tempfile
import unittest
import unittest.mock

import fixtures  # noqa: F401  (puts tools/ on the import path)
import asset_cards  # noqa: E402
import build_chips  # noqa: E402
import chrome  # noqa: E402
import reportlib as rl  # noqa: E402


class AssetCards(unittest.TestCase):
    def test_first_sentence_does_not_split_on_us(self):
        page = ('<body><div class="section-title">01 What it is</div><p>What it is. The U.S. government borrows for ten '
                'years through this note. It pays interest twice a year.</p><div class="section">')
        self.assertEqual(asset_cards.first_sentence(page), 'The U.S. government borrows for ten years through this note.')


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
