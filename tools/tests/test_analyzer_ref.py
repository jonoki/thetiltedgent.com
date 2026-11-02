"""Unit tests for analyzer_ref.py (currency, country, beta rules; a fresh build verifies and matches the committed
file) and verify_analyzer_ref.py (the fixture passes; each broken copy fails for its own reason).
Run: py -3 tools/run_checks.py"""
import copy
import json
import os
import unittest

import analyzer_ref as ar
import repodata as rd
import verify_analyzer_ref as va

FIXTURE = os.path.join(rd.ROOT, 'analyzer', 'test', 'fixture_ref.json')


class Rules(unittest.TestCase):
    def test_currency_from_ticker_suffix(self) -> None:
        cases = {'AAPL': 'USD', 'BRK.B': 'USD', 'BABA': 'USD', '7974.T': 'JPY', 'LSEG.L': 'GBX', 'RY.TO': 'CAD',
                 'ATCO-A.ST': 'SEK', '0700.HK': 'HKD', 'NESN.SW': 'CHF', '005930.KS': 'KRW', 'MC.PA': 'EUR'}
        for t, c in cases.items():
            self.assertEqual(ar.currency_of(t), c, t)
        with self.assertRaises(ValueError):
            ar.currency_of('XYZ.QQ')

    def test_country_from_card_tag(self) -> None:
        self.assertEqual(ar.country_of(['US-based', 'Cupertino, California']), 'US')
        self.assertEqual(ar.country_of(['UK-based', 'London']), 'GB')
        self.assertEqual(ar.country_of(['Tokyo-based', 'Minato-ku, Tokyo']), 'JP')
        # a malformed label falls back to a single city named in the full text
        self.assertEqual(ar.country_of(['Nariman Point)-based', 'Mumbai (registered office: Nariman Point)']), 'IN')
        self.assertIsNone(ar.country_of(None))
        self.assertIsNone(ar.country_of(['Atlantis-based', 'somewhere']))
        self.assertIsNone(ar.country_of(['Atlantis-based', 'offices in London and Paris']))   # two cities: no guess

    def test_beta_prefers_key_metrics_then_plain_fin_table(self) -> None:
        self.assertEqual(ar.beta_of({'beta': 1.2, 'fin_table': {'beta': '1.3'}}), (1.2, 'key metrics'))   # type: ignore[typeddict-item]
        self.assertEqual(ar.beta_of({'fin_table': {'beta': '0.96'}}), (0.96, 'fin-table'))
        self.assertEqual(ar.beta_of({'beta': 'n/a', 'fin_table': {'beta': '~5.2'}}), (None, None))   # type: ignore[typeddict-item]


class Build(unittest.TestCase):
    def test_fresh_build_verifies_and_matches_committed_file(self) -> None:
        ref, _ = ar.build(rd.ROOT)
        self.assertEqual(va.verify(ref, rd.load_manifest(rd.ROOT)['count']), [])
        with open(os.path.join(rd.ROOT, ar.OUT), encoding='utf-8', newline='') as fh:
            self.assertEqual(fh.read(), ar.serialise(ref), 'data/analyzer_ref.json is stale: run py -3 tools/analyzer_ref.py')
        self.assertEqual(json.loads(ar.serialise(ref)), ref)


class Verify(unittest.TestCase):
    def setUp(self) -> None:
        with open(FIXTURE, encoding='utf-8') as fh:
            self.ref = json.load(fh)

    def broken(self, edit: str) -> list[str]:
        r = copy.deepcopy(self.ref)
        s = r['securities']
        if edit == 'price':
            s['aaa']['price'] = 0
        elif edit == 'as_of':
            s['aaa']['as_of'] = 'Oct 30'
        elif edit == 'source':
            del s['bbb']['source']
        elif edit == 'country':
            s['bbb']['country'] = 'Canada'
        elif edit == 'sector':
            s['bbb']['sector'] = 'banks'
        elif edit == 'mer':
            s['fnd1']['mer'] = 0.5
        elif edit == 'weights':
            s['fnd1']['holdings']['rows'].append({'key': 'ccc', 'w': 0.4})
        elif edit == 'row key':
            s['fnd2']['holdings']['rows'][1]['key'] = 'zzz'
        elif edit == 'allocation':
            s['bal']['allocation'] = {'equity': 0.6, 'fixed_income': 0.3}
        elif edit == 'series gap':
            s['aaa']['series']['months'] = ['2026-07', '2026-09', '2026-10']
        elif edit == 'alias':
            del r['aliases']['FND2']
        elif edit == 'fx':
            r['fx']['usd_per']['CAD'] = -1
        return va.verify(r)

    def test_fixture_passes(self) -> None:
        self.assertEqual(va.verify(self.ref), [])

    def test_each_break_is_caught_by_its_own_rule(self) -> None:
        expect = {'price': 'aaa.price', 'as_of': 'aaa.as_of', 'source': 'bbb.source', 'country': 'bbb.country',
                  'sector': 'bbb.sector', 'mer': 'fnd1.mer', 'weights': 'fnd1.holdings: weights sum',
                  'row key': 'zzz is not a security', 'allocation': 'bal.allocation: shares sum',
                  'series gap': 'not consecutive', 'alias': 'ticker FND2', 'fx': 'fx.usd_per'}
        for edit, needle in expect.items():
            errs = self.broken(edit)
            self.assertTrue(any(needle in e for e in errs), f'{edit}: {errs}')

    def test_manifest_count_mismatch(self) -> None:
        self.assertTrue(any('stock count 3' in e for e in va.verify(self.ref, 628)))


if __name__ == '__main__':
    unittest.main()
