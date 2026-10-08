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


class Page(unittest.TestCase):
    def test_terms_anchors_and_a_to_z(self):
        out = glossary.page_html('finance', DOC)
        self.assertIn('<article class="term" id="pe-ratio" data-g="metrics"', out)
        self.assertIn('See also: <a href="#eps">EPS</a>', out)
        self.assertIn('<a href="#az-E">E</a><a href="#az-P">P</a>', out)
        self.assertIn('Share price ÷ EPS (TTM)', out)
        self.assertIn('nav class="site"', out)
        self.assertIn('glossary.js?v=' + glossary.STAMP, out)

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


if __name__ == '__main__':
    unittest.main()
