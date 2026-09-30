"""Unit tests for auto_refresh.py: choosing the work, the prompts, reading the checker's return.
Run: py -3 tools/run_checks.py"""
import unittest

import auto_refresh as ar


def item(slug, tier, status='due', release='2026-09-23', triggers=()):
    return {'slug': slug, 'ticker': slug.upper(), 'tier': tier, 'status': status, 'release': release,
            'as_of': '2026-09-04', 'timing': 'pre', 't2': '2026-09-24', 'triggers': list(triggers), 'eps': 1.39,
            'eps_forecast': 1.35, 'surprise_pct': 2.96, 'first_move_pct': -3.44, 'fiscal_quarter': 'Aug/2026'}


class Select(unittest.TestCase):
    def test_t1_always_t2_capped(self):
        items = [item('a', 'T2', release='2026-09-20'), item('b', 'T1', triggers=['Nasdaq-100']),
                 item('c', 'T2', release='2026-09-22'), item('d', 'T2', 'overdue', '2026-09-10'),
                 item('e', 'T1', 'waiting'), item('f', 'T2', 'upcoming')]
        self.assertEqual([i['slug'] for i in ar.select(items, {}, t2_cap=2)], ['b', 'd', 'a'])   # overdue T2 first

    def test_attempts_and_only(self):
        items = [item('a', 'T1'), item('b', 'T1')]
        self.assertEqual([i['slug'] for i in ar.select(items, {'a': {'2026-09-23': 2}})], ['b'])
        self.assertEqual([i['slug'] for i in ar.select(items, {'a': {'2026-06-01': 2}})], ['a', 'b'])   # older print
        self.assertEqual([i['slug'] for i in ar.select(items, {}, only=['a'])], ['a'])


class Prompts(unittest.TestCase):
    def test_builder(self):
        p = ar.builder_prompt(item('ctas', 'T1', triggers=['Nasdaq-100']), 'C:/wt')
        for s in ('reports/ctas_analysis.html', 'WORKING REPO (overrides the REPO line in the briefs): C:/wt',
                  'T1 (Nasdaq-100)', 'EPS 1.39 vs consensus 1.35', '-3.44%', 'No git commands', ar.UNATTENDED):
            self.assertIn(s, p)

    def test_checker(self):
        p = ar.checker_prompt(item('gis', 'T2'), 'C:/wt', 'x' * 20000)
        self.assertIn(ar.UNATTENDED, p)
        self.assertIn('VERDICT line', p)
        self.assertLess(p.count('x'), 15100)   # the builder's return is truncated

    def test_reading_the_checker(self):
        self.assertTrue(ar.verdict_hold('**VERDICT: HOLD** — the release is not out'))
        self.assertFalse(ar.verdict_hold('VERDICT: PUBLISH. Eleven corrections'))
        self.assertEqual(ar.pitfall_lines('Result\nPITFALLS: F:x; G:y\nSources'), ['PITFALLS: F:x; G:y'])


if __name__ == '__main__':
    unittest.main()
