"""Unit tests for the Tables page builder.   Run from the repo root:  py -3 -m unittest discover -s tables/tests -v

The tests build from small, made-up game records and a fixture source, not the live prose, so an edit to the
source or the game list never breaks them; the builder's run over the real source is its own check.
"""
import os
import sys
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # tables/

import build_tables  # noqa: E402


class TablesBuilder(unittest.TestCase):
    DICE = build_tables.Game('dice', 'dice', 'Dice & Co', 'Dice.', ('b', 'B'), 'Roll them.', 'Try it.', sessions=300,
                             callout='    <div class="callout">Practice</div>')
    CARDS = build_tables.Game('cards', 'cards', 'Cards', 'Cards.', ('d', 'D'), 'Deal them.', None, more='READ')

    def test_page_links(self):
        self.assertIn('<span></span>', build_tables.page_links(None, self.CARDS))
        self.assertIn('href="dice.html"', build_tables.page_links(self.DICE, None))
        self.assertNotIn('class="next"', build_tables.page_links(self.DICE, None))

    def test_crumbs_escape_the_current_title(self):
        c = build_tables.crumbs('Hold & Draw', (('blackjack.html', 'Blackjack'),))
        self.assertTrue(c.endswith('<a href="blackjack.html">Blackjack</a><span>/</span>Hold &amp; Draw</div>'))

    def test_family_tabs(self):
        fam = {'dice': [('dice.html', 'Dice'), ('dice-trainer.html', 'Trainer')]}
        with unittest.mock.patch.object(build_tables, 'FAMILY', fam):
            self.assertEqual(build_tables.family_tabs('dice-trainer'),
                             '<div class="wrap famtabs"><a href="dice.html">Dice</a><a href="dice-trainer.html" class="on">Trainer</a></div>')
            self.assertEqual(build_tables.family_tabs('cards'), '')

    def test_simulator_needs_one_advantage_play_box(self):
        with self.assertRaises(ValueError):
            build_tables.with_sim('<section class="game" id="x"></section>', 'x', 'SIM')
        sec = build_tables.with_sim('<section class="game" id="x">\n' + build_tables.AP_MARKER + '</div></section>', 'x', 'SIM')
        self.assertIn('class="game first"', sec)
        self.assertIn('SIM\n' + build_tables.AP_MARKER, sec)

    def test_game_sim_follows_the_game_record(self):
        sim = build_tables.game_sim(self.DICE)
        self.assertIn('Try it.', sim)
        self.assertTrue(sim.endswith('\n    <div class="callout">Practice</div>'))   # the callout sits after the simulator
        self.assertEqual(build_tables.game_sim(self.CARDS), build_tables.NO_SIM_NOTE)
        self.assertIn('n: 300', build_tables.sim_scripts('dice', self.DICE.sessions))

    def test_replace_once_and_between_name_what_is_missing(self):
        self.assertEqual(build_tables.replace_once('a b c', 'b', 'x'), 'a x c')
        for s in ('a c', 'b b'):
            with self.assertRaisesRegex(ValueError, "'b'"):
                build_tables.replace_once(s, 'b', 'x')
        self.assertEqual(build_tables.between('x<a>1</a>y', '<a>', '</a>'), ('<a>1</a>', 1, 9))
        with self.assertRaisesRegex(ValueError, "'<b>'"):
            build_tables.between('x<a>1</a>y', '<b>', '</a>')

    SOURCE = '''<!DOCTYPE html><html><head><meta charset="UTF-8">
<script>document.documentElement.classList.add('js');</script>
<link rel="stylesheet" href="/assets/site.css">
<style>
.x{}
</style></head><body>
<!-- ================= NAV ================= --><nav>N</nav>
<!-- ================= HERO ================= --><div class="hero"><div>H</div>
</div>
<!-- ================= GRADE BOARD ================= --><section>B</section>
<!-- ================= METHOD ================= --><section>M</section>
<!-- ================= OUTRO ================= --><section>O</section>
<section class="game" id="dice">D</section>
<!-- ================= FOOTER ================= --><footer>F</footer>
<script src="/assets/site.js" defer></script>
</body></html>'''

    def test_site_reads_the_source_and_wraps_pages(self):
        with unittest.mock.patch.object(build_tables, 'GAMES', [self.DICE]), \
                unittest.mock.patch.object(build_tables, 'FAMILY_PAGES', []):
            site = build_tables.Site(self.SOURCE)
            with self.assertRaisesRegex(ValueError, 'OUTRO'):
                build_tables.Site(self.SOURCE.replace('OUTRO', 'CODA'))
        self.assertEqual(site.css, '\n.x{}\n')
        self.assertEqual(site.sections, {'dice': '<section class="game" id="dice">D</section>'})
        head = site.head('Dice & Co', 'A "fair" game', 'dice.html', og_type='website')
        self.assertIn("<script>document.documentElement.classList.add('js');</script>", head)
        self.assertIn('<link rel="stylesheet" href="/assets/site.css">\n<link rel="stylesheet" href="tables.css">', head)
        self.assertIn('<title>Dice &amp; Co — The Tilted Gent</title>', head)
        self.assertIn('content="A &quot;fair&quot; game"', head)
        self.assertIn('og:type" content="website"', head)
        page = site.page('MAIN', '<script>x</script>')
        self.assertTrue(page.startswith('<!-- ================= NAV'))
        self.assertTrue(page.endswith('<footer>F</footer>\n\n<script src="/assets/site.js" defer></script><script>x</script>\n</body>\n</html>\n'))


if __name__ == '__main__':
    unittest.main()
