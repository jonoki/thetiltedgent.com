"""Unit tests for glossary.py: the data checks and the written page.   Run: py -3 tools/run_checks.py"""
import os
import tempfile
import unittest

import glossary

DOC = {'v': 1, 'page': 'finance', 'groups': [{'id': 'metrics', 'title': 'Key Financial Metrics', 'intro': 'The table.'}],
       'terms': [{'id': 'pe-ratio', 'term': 'P/E ratio', 'aka': ['Trailing P/E'], 'group': 'metrics',
                  'def': 'Price paid for each $1 of yearly profit per share.', 'formula': 'Share price ÷ EPS (TTM)',
                  'labels': ['Trailing P/E'], 'see': ['eps']},
                 {'id': 'eps', 'term': 'EPS', 'group': 'metrics', 'def': 'Profit per share.', 'labels': ['EPS (TTM)']}]}


class Problems(unittest.TestCase):
    def test_a_clean_glossary_has_none(self):
        self.assertEqual(glossary.problems(DOC, ['Trailing P/E', 'eps (ttm)']), [])   # labels match ignoring case

    def test_every_kind_of_problem_is_named(self):
        bad = {**DOC, 'terms': DOC['terms'] + [
            {'id': 'eps', 'term': 'EPS again', 'group': 'metrics', 'def': 'x'},
            {'id': 'Bad_Id', 'term': '<b>x</b>', 'group': 'nowhere', 'see': ['ghost']},
        ]}
        out = glossary.problems(bad, ['Beta'])
        for needle in ("id 'eps' used 2 times", 'Bad_Id: no def', 'Bad_Id: id is not kebab-case',
                       "Bad_Id: unknown group 'nowhere'", "Bad_Id: see-also 'ghost' is not a term",
                       'Bad_Id: term holds HTML', "tear-sheet label 'Beta' has no term"):
            self.assertTrue(any(needle in p for p in out), needle)

    def test_a_group_without_terms_is_a_problem(self):
        doc = {**DOC, 'groups': DOC['groups'] + [{'id': 'chart', 'title': 'Chart'}]}
        self.assertIn("group 'chart' has no terms", glossary.problems(doc, []))

    def test_a_report_tooltip_covers_a_label_by_its_match_rule(self):
        tips = [{'label': 'Static data as of', 'match': 'prefix', 'tip': 'x'},
                {'label': 'Industry Avg', 'match': 'contains', 'tip': 'x'}, {'label': 'Context', 'tip': 'x'}]
        self.assertEqual(glossary.problems(DOC, ['Static data as of', 'Beverage Industry Avg', 'context'], tips), [])
        self.assertTrue(glossary.problems(DOC, ['Contextual'], tips))   # exact means exact

    def test_retired_ids_stay_retired_and_point_somewhere_real(self):
        self.assertEqual(glossary.problems(DOC, [], retired={'old': 'eps', 'gone': 'report'}), [])
        out = glossary.problems(DOC, [], retired={'eps': 'report', 'old': 'ghost'})
        self.assertIn("retired id 'eps' is a live term again", out)
        self.assertIn("retired id 'old' points at 'ghost', which is not a term", out)


class Tips(unittest.TestCase):
    def test_clean_tips_have_no_problems(self):
        tips = [{'label': 'Context', 'tip': 'A note on each figure.'},
                {'label': 'Trailing P/E', 'tip': 'Price over profit.', 'term': 'pe-ratio'}]
        self.assertEqual(glossary.tip_problems(tips, DOC), [])

    def test_every_kind_of_tip_problem_is_named(self):
        tips = [{'label': 'Context', 'tip': ' '.join(['word'] * 31)}, {'label': 'context', 'tip': '<b>x</b>'},
                {'label': 'Odd', 'tip': 'x', 'match': 'fuzzy'}, {'label': 'Ghost', 'tip': 'x', 'term': 'ghost'},
                {'label': 'Trailing P/E', 'tip': 'x'}, {'label': 'Empty'}]
        out = glossary.tip_problems(tips, DOC)
        for needle in ("tooltip label 'context' listed 2 times", 'Context: 31 words', 'context: tip holds HTML',
                       "Odd: unknown match 'fuzzy'", "Ghost: term 'ghost' is not a glossary entry",
                       "Trailing P/E: the glossary entry 'pe-ratio' explains this label", 'Empty: needs a label and a tip'):
            self.assertTrue(any(needle in p for p in out), needle)

    def test_the_live_tips_file_passes(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assertEqual(glossary.tip_problems(glossary.load_tips(root), glossary.load(root, 'finance')), [])


class Page(unittest.TestCase):
    def test_terms_anchors_and_a_to_z(self):
        out = glossary.page_html('finance', DOC)
        self.assertIn('<article class="term" id="pe-ratio" data-g="metrics"', out)
        self.assertIn('See also: <a href="#eps">EPS</a>', out)
        self.assertIn('<a href="#az-E">E</a><a href="#az-P">P</a>', out)
        self.assertIn('Share price ÷ EPS (TTM)', out)
        self.assertIn('nav class="site"', out)
        self.assertIn('glossary.js?v=' + glossary.STAMP, out)
        self.assertIn('"ticker":{"to":"exchange"}', out)                 # retired anchors, read by glossary.js
        self.assertIn('"static-data":{"note":"That entry now lives on the reports', out)

    def test_text_is_escaped(self):
        doc = {**DOC, 'terms': [{**DOC['terms'][1], 'def': 'R&D < revenue'}]}
        self.assertIn('R&amp;D &lt; revenue', glossary.page_html('finance', doc))

    def test_labels_come_from_the_metrics_table(self):
        page = ('<table class="fin-table"><tr><th>Metric</th><th>Industry Avg</th></tr>'
                '<tr><td>Trailing P/E</td><td>20</td></tr></table><table><tr><td>Elsewhere</td></tr></table>')
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, 'reports'))
            for i in range(2):
                with open(os.path.join(repo, 'reports', f'r{i}_analysis.html'), 'w', encoding='utf-8') as fh:
                    fh.write(page)
            self.assertEqual(glossary.tear_sheet_labels(repo, min_reports=2), ['Industry Avg', 'Trailing P/E'])


class Learn(unittest.TestCase):
    def test_counts_are_written_into_the_table_talk_page(self):
        page = '<p><b data-terms="finance">1</b> terms</p><p><b data-terms="poker">2</b> terms</p>'
        out = glossary.with_counts(page, {'finance': 154, 'poker': 150})
        self.assertEqual(out, '<p><b data-terms="finance">154</b> terms</p><p><b data-terms="poker">150</b> terms</p>')

    def test_a_missing_or_repeated_count_is_named(self):
        with self.assertRaisesRegex(ValueError, 'data-terms="poker"'):
            glossary.with_counts('<b data-terms="finance">1</b>', {'finance': 3, 'poker': 4})
        with self.assertRaisesRegex(ValueError, 'data-terms="finance"'):
            glossary.with_counts('<b data-terms="finance">1</b><b data-terms="finance">1</b>', {'finance': 3})

    def test_the_pages_live_under_learn(self):
        out = glossary.page_html('finance', DOC)
        self.assertIn('<div class="kicker">Learn &middot; Table Talk</div>', out)
        self.assertIn('<summary class="on">Learn</summary>', out)
        self.assertIn('href="/assets/ttg-favicon.svg"', out)   # root-relative at any depth

    def test_the_old_urls_redirect_and_keep_the_anchor(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for page in glossary.PAGES:
            new = f'/learn/table-talk/{page}.html'
            with open(os.path.join(root, 'glossary', f'{page}.html'), encoding='utf-8') as fh:
                stub = fh.read()
            self.assertIn(f"location.replace('{new}' + location.hash)", stub)
            self.assertIn(f'<link rel="canonical" href="https://thetiltedgent.com{new}">', stub)
            self.assertIn(f'url={new}"', stub)
            self.assertIn('<meta name="robots" content="noindex">', stub)


if __name__ == '__main__':
    unittest.main()
