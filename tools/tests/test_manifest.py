"""Unit tests for the manifest and the pre-publish gate (manifest.py, verify.py).   Run from the repo root:  py -3 -m unittest discover -s tools/tests -v"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

from fixtures import PAGE
import manifest  # noqa: E402
import verify  # noqa: E402
import reportlib as rl  # noqa: E402


class ManifestFields(unittest.TestCase):
    def test_as_of_date_range_takes_the_first_day(self):
        warn: list[str] = []
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


if __name__ == '__main__':
    unittest.main()
