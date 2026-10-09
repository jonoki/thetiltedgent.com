"""Unit tests for index_rank.py: ranking, dual-class shares, the rank row (write, insert; a page in neither index left
alone) and the fine-print rewrite.   Run: py -3 tools/run_checks.py"""
import contextlib
import io
import os
import tempfile
import unittest

import index_rank as ir
import refresh_data as rf
import reportlib as rl

ACCENT = ('<span style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:var(--accent);'
          'background:var(--accent-dim);padding:3px 10px;border-radius:4px;">')
DIM = ('<span style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:var(--text-dim);'
       'background:var(--surface2);padding:3px 10px;border-radius:4px;">')
LABEL = '<span style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:var(--accent);">Mkt Cap Ranking:</span>'


def hero(row: str = '') -> str:
    return ('<div class="hero">\n'
            '  <div>\n'
            '    <div class="ticker-block">\n'
            '      <span class="ticker-badge">ACME</span>\n'
            '      <span>Mkt Cap: $10.0B</span>\n'
            '    </div>\n'
            + row +
            '    <div style="margin-top:12px;"><span>S&amp;P 500: MEMBER</span></div>\n'
            '    <div class="company-name">Acme</div>\n'
            '  </div>\n'
            '</div>\n')


OLD_ROW = ('    <div style="margin-top:10px;display:flex;gap:10px;">\n'
           f'      {LABEL}\n'
           f'      {ACCENT}Global: #1226</span>\n'
           f'      {ACCENT}US: ~#600 (est.)</span>\n'
           f'      {ACCENT}S&amp;P 500 member since Aug 27, 2008</span>\n'
           '      <span style="font-size:11px;color:var(--text-dim);">(approximate)</span>\n'
           '    </div>\n')


def member(slug: str, mcap: float, price: float, sp500: bool = True, ndx: bool = False, as_of: str = '2026-09-21') -> ir.Member:
    return ir.Member(slug, slug.upper(), as_of, price, mcap, mcap / price, None, sp500, ndx)


def daily(*closes: tuple[str, float], splits: list[tuple[str, float]] | None = None) -> rf.Daily:
    return rf.Daily([rf.Day(d, c, c, c) for d, c in closes], [], splits or [], 0, '', '')


class Ranking(unittest.TestCase):
    def test_rank_of_counts_larger_caps(self):
        caps = {'a': 300.0, 'b': 100.0, 'c': 200.0}
        self.assertEqual([ir.rank_of(caps, s) for s in 'abc'], [1, 3, 2])

    def test_close_is_the_last_on_or_before_the_date(self):
        d = daily(('2026-09-18', 10.0), ('2026-09-21', 11.0))
        self.assertEqual(ir.close_on(d, '2026-09-20'), 10.0)     # a Sunday: Friday's close
        self.assertEqual(ir.close_on(d, '2026-09-21'), 11.0)
        self.assertIsNone(ir.close_on(d, '2026-09-01'))

    def test_cap_puts_a_later_split_back_on_the_as_of_share_basis(self):
        # the report (as of Sep 1) says 100 shares at $20; a 2:1 split on Sep 10 halves every Yahoo close before it
        m = member('acme', 2000.0, 20.0, as_of='2026-09-01')
        d = daily(('2026-09-01', 10.0), ('2026-09-21', 11.0), splits=[('2026-09-10', 2.0)])
        self.assertAlmostEqual(ir.cap_on(m, d, '2026-09-01') or 0, 2000.0)   # Yahoo $10 x 2 = the report's $20
        self.assertAlmostEqual(ir.cap_on(m, d, '2026-09-21') or 0, 2200.0)   # 200 shares at $11

    def test_ranks_use_each_members_shares_at_the_close_on_the_reports_date(self):
        members = {'big': member('big', 300.0, 30.0, ndx=True), 'mid': member('mid', 200.0, 20.0),
                   'small': member('small', 100.0, 10.0, ndx=True)}
        # on Sep 21 small has tripled: 10 shares x $30 = 300 > mid's 200; big (10 x $25 = 250) falls between
        series = {'big': daily(('2026-09-21', 25.0)), 'mid': daily(('2026-09-21', 20.0)), 'small': daily(('2026-09-21', 30.0))}
        self.assertEqual(ir.ranks_on('small', '2026-09-21', members, series), {'sp500': 1, 'ndx': 1})
        self.assertEqual(ir.ranks_on('big', '2026-09-21', members, series), {'sp500': 2, 'ndx': 2})
        self.assertEqual(ir.ranks_on('mid', '2026-09-21', members, series), {'sp500': 3})

    def test_dual_class_company_ranks_once_at_its_whole_market_cap(self):
        # one card per company: Alphabet's report states A+B+C together; its shares are counted in GOOGL units
        goog = member('googl', 4.33e12, 354.30)
        other = member('msft', 3.76e12, 500.0)
        series = {'googl': daily(('2026-09-21', 354.30)), 'msft': daily(('2026-09-21', 500.0))}
        self.assertAlmostEqual(goog.shares, 4.33e12 / 354.30)
        self.assertEqual(ir.ranks_on('googl', '2026-09-21', {'googl': goog, 'msft': other}, series), {'sp500': 1})

    def test_parse_shares(self):
        self.assertEqual(ir.parse_shares('2.45B'), 2.45e9)
        self.assertEqual(ir.parse_shares('596.00M'), 596e6)
        self.assertEqual(ir.parse_shares('12.1 billion (diluted)'), 12.1e9)
        self.assertIsNone(ir.parse_shares('n/a'))
        self.assertIsNone(ir.parse_shares('191.61'))        # millions, but the cell does not say so

    def test_shares_row_reads_the_current_column(self):
        # CCL, 8 Oct 2026: a "Pre-Crisis | Now" table; the first value cell (2019's 693M) gave a false implied-shares flag
        ccl = ('<table><thead><tr><th>Measure</th><th>Pre-Crisis</th><th>Now</th><th>Change</th><th>What it means</th></tr>'
               '</thead><tbody><tr>\n  <td>Shares outstanding</td>\n  <td style="color:red;">693M</td>\n  <td>1,344.6M</td>\n'
               '  <td>+94.0%</td>\n  <td>693M in fiscal Q1 2019; 1,344.6M on the 10-Q cover.</td>\n</tr></tbody></table>')
        self.assertEqual(ir.shares_cell(ccl), '1,344.6M')
        self.assertEqual(ir.parse_shares(ir.shares_cell(ccl)), 1344.6e6)
        years = ccl.replace('Pre-Crisis', 'FY2019').replace('>Now<', '>FY2026<')
        self.assertEqual(ir.shares_cell(years), '1,344.6M')                        # no "Now": the latest year
        metrics = ('<table class="fin-table"><tr><th>Metric</th><th>ACME</th><th>Industry Avg</th><th>S&amp;P 500</th></tr>'
                   '<tr><td>Shares Outstanding</td><td>2.45B</td><td>1.1B</td><td>—</td></tr></table>')
        self.assertEqual(ir.shares_cell(metrics), '2.45B')                         # a metrics table: its first value
        self.assertEqual(ir.shares_cell('<table><tr><td>Shares outstanding</td><td>596.00M</td></tr></table>'), '596.00M')
        self.assertIsNone(ir.shares_cell('<p>no table</p>'))

    def test_member_flags_implied_vs_stated_shares_and_the_price(self):
        m = ir.Member('acme', 'ACME', '2026-09-21', 20.0, 2000.0, 100.0, 90.0, True, False)
        flags = ir.member_flags(m, daily(('2026-09-21', 21.0)))
        self.assertEqual(len(flags), 2)
        self.assertIn('implied shares', flags[0])
        self.assertIn('header price', flags[1])


class Row(unittest.TestCase):
    def test_replace_keeps_label_and_styles_drops_old_pills(self):
        new, what = ir.write_row(hero(OLD_ROW), {'sp500': 7, 'ndx': 3})
        self.assertEqual(what, 'replaced')
        self.assertIn(f'      {LABEL}\n      {ACCENT}S&amp;P 500: #7</span>\n'
                      f'      {ir.dim_from(ACCENT)}Nasdaq-100: #3</span>\n', new)
        self.assertIn('member since Aug 27, 2008', new)            # a membership pill stays, after the ranks
        for gone in ('Global: #1226', 'US: ~#600', '(approximate)'):
            self.assertNotIn(gone, new)
        self.assertEqual(ir.write_row(new, {'sp500': 7, 'ndx': 3}), (new, 'unchanged'))

    def test_second_pill_uses_the_rows_own_dim_style(self):
        row = OLD_ROW.replace(f'{ACCENT}US:', f'{DIM}US:')
        new, _ = ir.write_row(hero(row), {'sp500': 7, 'ndx': 3})
        self.assertIn(f'{DIM}Nasdaq-100: #3</span>', new)

    def test_nasdaq_only_member_gets_the_accent_pill(self):
        new, _ = ir.write_row(hero(OLD_ROW), {'ndx': 12})
        self.assertIn(f'{ACCENT}Nasdaq-100: #12</span>', new)
        self.assertNotIn('S&amp;P 500: #', new)

    def test_insert_under_the_ticker_block(self):
        page = hero()
        new, what = ir.write_row(page, {'sp500': 400})
        self.assertEqual(what, 'inserted')
        self.assertIn('    </div>\n    ' + ir.DEFAULT_OPEN + '\n      ' + ir.DEFAULT_LABEL + '\n      '
                      + ir.DEFAULT_ACCENT + 'S&amp;P 500: #400</span>\n    </div>\n    <div style="margin-top:12px;">', new)
        self.assertEqual(ir.write_row(new, {'sp500': 400}), (new, 'unchanged'))

    def test_page_in_neither_index_is_left_alone(self):
        # a global listing keeps its home-market rank row as it is (Oki, 8 Oct 2026)
        self.assertEqual(ir.write_row(hero(OLD_ROW), {}), (hero(OLD_ROW), 'global'))
        self.assertEqual(ir.write_row(hero(), {}), (hero(), 'global'))

    def test_page_that_left_both_indexes_loses_its_rank_pills(self):
        # CTVA left the S&P 500 on 6 Oct 2026: its row held only the S&P pill, so the row goes; --check flags it until then
        sp_only = (f'    <div style="margin-top:10px;">\n      {LABEL}\n      {ACCENT}S&amp;P 500: #208</span>\n    </div>\n')
        new, what = ir.write_row(hero(sp_only), {})
        self.assertEqual((new, what), (hero(), 'row removed'))
        self.assertEqual(ir.write_row(new, {}), (new, 'global'))
        mixed = OLD_ROW.replace('Global: #1226', 'Nasdaq-100: #101')
        new, what = ir.write_row(hero(mixed), {})
        self.assertEqual(what, 'pills removed')
        self.assertNotIn('Nasdaq-100: #', new)
        self.assertIn(f'      {LABEL}\n      {ACCENT}US: ~#600 (est.)</span>\n', new)   # anything else stays
        self.assertEqual(ir.write_row(new, {}), (new, 'global'))

    def test_check_flags_a_non_member_still_showing_an_index_rank(self):
        card = ('<a class="rep" href="view.html?r={s}"><span class="tick">{S}</span><h3>{S}</h3><span class="sect">X</span>'
                '<span class="ixrow"></span></a>\n')
        sp_only = f'    <div style="margin-top:10px;">\n      {LABEL}\n      {ACCENT}S&amp;P 500: #208</span>\n    </div>\n'
        pages = {'ctva': hero(sp_only), 'nestle': hero(OLD_ROW.replace('S&amp;P 500 member since Aug 27, 2008', 'SMI'))}
        with tempfile.TemporaryDirectory() as repo, contextlib.redirect_stdout(io.StringIO()) as out:
            os.makedirs(os.path.join(repo, 'reports'))
            rl.write_text(os.path.join(repo, 'reports', 'index.html'),
                          ''.join(card.format(s=s, S=s.upper()) for s in pages))
            for s, page in pages.items():
                rl.write_text(os.path.join(repo, 'reports', f'{s}_analysis.html'),
                              '<div>Static data as of October 2, 2026</div>\n' + page)
            self.assertEqual(ir.main(['--repo', repo, '--check']), 1)
            self.assertIn('still showing an S&P 500 / Nasdaq-100 rank: ctva', out.getvalue())
            self.assertIn("rows that differ from what would be written: 1 ['ctva']", out.getvalue())   # not the global page
            self.assertEqual(ir.main(['--repo', repo]), 0)
            self.assertEqual(ir.main(['--repo', repo, '--check']), 0)
            self.assertNotIn('Mkt Cap Ranking', rl.read_text(os.path.join(repo, 'reports', 'ctva_analysis.html')))

    def test_class_styled_row(self):
        row = ('    <div class="rank-row">\n      <span class="rank-label">Mkt Cap Ranking:</span>\n'
               '      <span class="rank-pill">Global: #53</span>\n      <span class="rank-pill">US: #40</span>\n    </div>\n')
        new, _ = ir.write_row(hero(row), {'sp500': 30})
        self.assertIn('<span class="rank-label">Mkt Cap Ranking:</span>\n      <span class="rank-pill">S&amp;P 500: #30</span>\n    </div>', new)

    def test_label_suffix_and_case(self):
        row = OLD_ROW.replace('>Mkt Cap Ranking:<', '>MKT CAP RANKING (Aug 18 edition, not refreshed):<')
        new, _ = ir.write_row(hero(row), {'sp500': 1})
        self.assertIn('>MKT CAP RANKING:</span>', new)
        self.assertNotIn('Aug 18 edition', new)


def disclaimer(*paragraphs: str) -> str:
    return '<div class="disclaimer">\n' + ''.join(f'  <p>{p}</p>\n' for p in paragraphs) + '</div>\n'


NEW = ir.NEW_CLAUSE.format(date='September 21, 2026')


class FinePrint(unittest.TestCase):
    def rewrite(self, html: str, date: str | None = 'September 21, 2026') -> str:
        return ir.rewrite_fine_print(html, date)[0]

    def test_sentence_replaced_and_its_echo_removed(self):
        page = disclaimer('Prices from stockanalysis.com. Global market-cap rank from companiesmarketcap.com. '
                          'US and NYSE market-cap ranks are marked estimates. Next earnings date is an estimate.')
        self.assertEqual(self.rewrite(page), disclaimer(f'Prices from stockanalysis.com. {NEW}. Next earnings date is an estimate.'))

    def test_sentence_across_inline_tags(self):
        page = disclaimer('Global market-cap rank from <strong>companiesmarketcap.com</strong>. Other.')
        self.assertEqual(self.rewrite(page), disclaimer(f'{NEW}. Other.'))

    def test_list_item_removed_and_punctuation_repaired(self):
        page = disclaimer('Items marked <strong>(est.)</strong> are approximations: the US and NYSE market-cap rank '
                          'pills, the PEG arithmetic, and the next earnings date.')
        self.assertEqual(self.rewrite(page), disclaimer('Items marked <strong>(est.)</strong> are approximations: the PEG '
                                                        f'arithmetic and the next earnings date. {NEW}.'))

    def test_last_list_item_removed(self):
        page = disclaimer('Market shares, TAM figures and the NYSE market-cap rank are labelled estimates.')
        self.assertEqual(self.rewrite(page), disclaimer(f'Market shares and TAM figures are labelled estimates. {NEW}.'))

    def test_source_clause_in_a_semicolon_list(self):
        page = disclaimer('Sources: SEC filings; CompaniesMarketCap (global market-cap rank); MarketBeat (analyst actions).')
        new_clause = NEW[0].lower() + NEW[1:]
        self.assertEqual(self.rewrite(page), disclaimer(f'Sources: SEC filings; {new_clause}; MarketBeat (analyst actions).'))

    def test_page_in_neither_index_keeps_its_fine_print(self):
        page = disclaimer('Global market-cap rank from companiesmarketcap.com.', 'Other note.')
        self.assertEqual(ir.rewrite_fine_print(page, None), (page, [], []))

    def test_own_sentence_gets_the_new_date(self):
        page = disclaimer(f'{NEW}. Other.')
        self.assertEqual(self.rewrite(page, 'October 2, 2026'), disclaimer(f'{ir.NEW_CLAUSE.format(date="October 2, 2026")}. Other.'))
        self.assertEqual(self.rewrite(page, None), page)                 # a page in neither index: left alone

    def test_mixed_sentence_is_listed_not_forced(self):
        page = disclaimer('Market-cap rank and long-run price history: CompaniesMarketCap.com.')
        new, edits, left = ir.rewrite_fine_print(page, 'September 21, 2026')
        self.assertEqual((new, edits), (page, []))
        self.assertEqual(left, ['Market-cap rank and long-run price history: CompaniesMarketCap.com.'])

    def test_heading_survives_when_its_first_clause_goes(self):
        page = disclaimer('Flagged items: global, US and NYSE market-cap ranks are approximations; the Q3 date is estimated.')
        self.assertEqual(self.rewrite(page), disclaimer('Flagged items: the Q3 date is estimated.'))

    def test_prose_mention_of_the_old_source_is_not_rewritten(self):
        page = disclaimer('Market cap $45.8B, matching companiesmarketcap.com ($45.78B, global rank #569); other.')
        self.assertEqual(self.rewrite(page), page)

    def test_rank_only(self):
        self.assertTrue(ir.rank_only('Market-cap rankings (Global #31 / US #24 / NYSE #11) are approximate and move with daily prices.'))
        self.assertFalse(ir.rank_only('CompaniesMarketCap (market capitalisation and global ranking)'))   # a market-cap source too
        self.assertFalse(ir.rank_only('The NYSE market-cap rank and the next earnings date are estimates.'))


if __name__ == '__main__':
    unittest.main()
