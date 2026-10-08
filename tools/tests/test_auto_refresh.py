"""Unit tests for auto_refresh.py: choosing the work, the prompts, reading the checker's return.
Run: py -3 tools/run_checks.py"""
import os
import subprocess
import tempfile
import unittest
import unittest.mock

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

    def test_tiers(self):   # daily run: T1 only; Monday run: T2 only (Oki, 2 Oct 2026)
        items = [item('a', 'T2', release='2026-09-20'), item('b', 'T1'), item('c', 'T2', 'overdue', '2026-09-10')]
        self.assertEqual([i['slug'] for i in ar.select(items, {}, tiers=('T1',))], ['b'])
        self.assertEqual([i['slug'] for i in ar.select(items, {}, t2_cap=20, tiers=('T2',))], ['c', 'a'])
        self.assertEqual([i['slug'] for i in ar.select(items, {}, t2_cap=0, tiers=('T2',))], ['c', 'a'])   # 0 = no cap
        self.assertEqual((ar.jobs_for(3), ar.jobs_for(9), ar.jobs_for(30), ar.jobs_for(30, 2)), (3, 8, 8, 2))

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
        self.assertEqual(ar.built_tier('2. **Tier T1.** The trigger is new guidance', 'T2'), 'T1')   # FDS, 2 Oct 2026
        self.assertEqual(ar.built_tier('2. Tier: T2. None of the triggers fired', 'T1'), 'T2')
        self.assertEqual(ar.built_tier('no tier line', 'T2'), 'T2')
        self.assertIn('no &&', ar.ONE_COMMAND)
        self.assertEqual(ar.pitfall_lines('Result\nPITFALLS: F:x; G:y\nSources'), ['PITFALLS: F:x; G:y'])


class DataLayer(unittest.TestCase):
    """--data-layer (opt-in): the pre-pass before the builder, the post-pass before the checker, the facts gate."""
    DATA: ar.DataLayer = {'facts': 'C:/runs/ctas/facts.json', 'stale': 'C:/runs/ctas/stale_hits.txt',
                          'summary': 'ctas: as-of 2026-10-01 … left to the builder: change (prose variant)'}

    def test_prompts_unchanged_without_it(self):
        i = item('ctas', 'T1')
        self.assertNotIn('DATA LAYER', ar.builder_prompt(i, 'C:/wt'))
        self.assertEqual(ar.builder_prompt(i, 'C:/wt'), ar.builder_prompt(i, 'C:/wt', None))
        self.assertNotIn('DATA LAYER', ar.checker_prompt(i, 'C:/wt', 'r'))

    def test_builder_prompt(self):
        p = ar.builder_prompt(item('ctas', 'T1'), 'C:/wt', self.DATA)
        for s in ('already updated from C:/runs/ctas/facts.json', "Don't refetch prices", 'use facts.json for every '
                  'price-derived number', 'fix every line listed in C:/runs/ctas/stale_hits.txt',
                  'left to the builder: change (prose variant)', 'EPS (TTM) cell', 'fixed_points',
                  'trimmed to the five-year window', 'Rule A: sweep', '`tg-d--fix`'):
            self.assertIn(s, p)

    def test_checker_prompt(self):
        p = ar.checker_prompt(item('ctas', 'T1'), 'C:/wt', 'r', 'ctas: post-pass FAIL\n  MISMATCH header price')
        self.assertIn('spot-check two', p)
        self.assertIn('MISMATCH header price', p)
        self.assertIn('facts.json fixed_points', p)
        self.assertIn('(rule A)', p)

    def test_commands(self):
        pre = ar.data_layer_cmd('ctas', 'C:/o')
        self.assertEqual(pre[1:], ['tools/refresh_data.py', 'ctas', '--as-of', 'auto', '--out', 'C:/o', '--write',
                                   '--fix-points'])
        self.assertEqual(ar.data_layer_cmd('ctas', 'C:/o', post=True)[1:],
                         ['tools/refresh_data.py', 'ctas', '--post', '--out', 'C:/o'])
        self.assertEqual(ar.data_layer_cmd('ctas', 'C:/o', post=True, check=True)[-1], '--check')

    def test_gate_holds_the_page_to_its_facts(self):
        calls = []

        def fake_run(cmd, cwd, timeout=0):
            calls.append(cmd)
            if 'verify.py' in cmd[1]:
                return subprocess.CompletedProcess(cmd, 0, 'PASS ctas_analysis.html', '')
            if 'chart_audit.py' in cmd[1]:
                return subprocess.CompletedProcess(cmd, 0, 'reports 1 | errors 0 | WRONG points >3% vs x: 0 | y', '')
            return subprocess.CompletedProcess(cmd, 1, 'ctas: post-pass FAIL\n  MISMATCH header price 1 != 2\n', '')
        with tempfile.TemporaryDirectory() as wt, unittest.mock.patch.object(ar, 'run', fake_run):
            os.makedirs(os.path.join(wt, 'reports'))
            with open(os.path.join(wt, 'reports', 'ctas_analysis.html'), 'wb') as fh:
                fh.write(b'<html>\n</html>\n')
            self.assertTrue(ar.gates(wt, 'ctas')[0])                    # without the data layer: as before
            self.assertEqual(len(calls), 2)
            ok, why = ar.gates(wt, 'ctas', 'C:/o')
            self.assertFalse(ok)
            self.assertIn('facts MISMATCH: MISMATCH header price 1 != 2', why)
            self.assertEqual(calls[-1][-1], '--check')

    def test_summary_names_it(self):
        o: ar.Outcome = {'slug': 'ctas', 'ticker': 'CTAS', 'tier': 'T1', 'verdict': 'committed', 'detail': 'ok',
                         'cost_usd': 1.0, 'usage': [], 'denials': [], 'pitfalls': [], 'data_layer': 'used'}
        self.assertIn('data layer used', ar.summary_md('2026-10-02', [o], [], []))
        self.assertNotIn('data layer', ar.summary_md('2026-10-02', [{**o, 'data_layer': 'off'}], [], []))


class MergeBase(unittest.TestCase):
    """A conflict only in generated data/ is healed by regenerating; any other conflict aborts cleanly (7-8 Oct 2026)."""
    def repo(self, d, path, ours, theirs):
        import subprocess
        g = lambda *a: subprocess.run(['git', *a], cwd=d, capture_output=True, text=True, check=True)
        g('init', '-q', '-b', 'main'); g('config', 'user.email', 't@t'); g('config', 'user.name', 't')
        os.makedirs(os.path.join(d, 'tools'), exist_ok=True)
        for tool in ('manifest.py', 'style_tags.py', 'card_tags.py'):   # stand-ins for the real generators
            open(os.path.join(d, 'tools', tool), 'w').write('pass\n')
        os.makedirs(os.path.dirname(os.path.join(d, path)), exist_ok=True)
        open(os.path.join(d, path), 'w').write('base\n'); g('add', '-A'); g('commit', '-q', '-m', 'base')
        g('checkout', '-q', '-b', 'review'); open(os.path.join(d, path), 'w').write(ours + '\n'); g('commit', '-qam', 'ours')
        g('checkout', '-q', 'main'); open(os.path.join(d, path), 'w').write(theirs + '\n'); g('commit', '-qam', 'theirs')
        g('checkout', '-q', 'review')
        return g

    def test_generated_data_conflict_is_healed(self):
        with tempfile.TemporaryDirectory() as d:
            g = self.repo(d, 'data/card_tags.json', 'ours', 'theirs')
            ar.merge_base(d, 'main')
            self.assertEqual(open(os.path.join(d, 'data', 'card_tags.json')).read(), 'theirs\n')
            self.assertEqual(g('status', '--porcelain').stdout, '')
            self.assertIn('healed by regenerating', g('log', '-1', '--format=%s').stdout)

    def test_an_open_alert_heads_the_morning_list(self):
        import datetime
        import refresh_queue as rq
        md = rq.today_md([], datetime.date(2026, 10, 8), '2026-10-08T18:30', '2026-10-08T06:30 auto_refresh failed: boom\n')
        self.assertIn('**ALERT', md.splitlines()[2])
        self.assertIn('boom', md)
        self.assertNotIn('ALERT', rq.today_md([], datetime.date(2026, 10, 8), 'x'))

    def test_other_conflicts_abort_and_raise(self):
        with tempfile.TemporaryDirectory() as d:
            g = self.repo(d, 'reports/x_analysis.html', 'ours', 'theirs')
            with self.assertRaisesRegex(RuntimeError, 'merge aborted'):
                ar.merge_base(d, 'main')
            self.assertEqual(g('status', '--porcelain').stdout, '')   # not left half-merged
            self.assertEqual(open(os.path.join(d, 'reports', 'x_analysis.html')).read(), 'ours\n')


if __name__ == '__main__':
    unittest.main()
