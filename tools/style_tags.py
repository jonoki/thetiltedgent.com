"""Style tags ("what kind of stock") for every report: inputs, thresholds, tags and tooltip text.

usage: py -3 tools/style_tags.py            writes data/style_tags.json, prints counts
Formulas and rationale: claude/TAG_FORMULAS.md. Read-only on reports; writes one data file.

Inputs per report:
  manifest shard records (data/reports/*.json): price, market_cap, eps_ttm, pe_trailing, yield_pct, fcf, w52, as_of
  the report's own metrics table (.fin-table): Revenue Growth, ROIC, Debt-to-Equity, Beta
  reports/index.html cards: S&P 500 membership (data-sp) and the industry label
Every raw text value is kept next to the parsed number so any tag can be traced back to the page.
"""
import datetime
import json
import os
import re
import statistics
import sys
from collections import Counter
from typing import NotRequired, Sequence, TypedDict

import reportlib as rl

# Reports to leave out of tagging, slug -> reason. Empty: CBOE and MTD were excluded on 22 Sep 2026 over
# swapped <title> tags (bodies were correct); titles fixed the same day.
EXCLUDE: dict[str, str] = {}
# Industry labels are matched at the start of a word, so 'BANKS - REGIONAL' and 'REIT - OFFICE' match.
# Quality is not meaningful for balance-sheet businesses (Oki, 22 Sep 2026).
NO_QUALITY = re.compile(r'\b(?:BANK|INSURANCE|REIT)', re.I)
# Free cash flow is not meaningful for lenders, insurers and brokers (customer money flows through it).
NO_CASH = re.compile(r'\b(?:BANK|INSURANCE|CAPITAL MARKETS)', re.I)
# FCF quoted in another currency cannot be divided by a US-dollar market cap.
FOREIGN_CCY = re.compile(r'[¥€£₩]|(?:NT|HK|C|A|R|S)\$')

GIANT_MCAP = 200e9          # convention, not an official line
BEATEN_DOWN = 0.60          # price <= 60% of the 52-week high
QUALITY_MAX_DE = 1.0
PCT = 0.20                  # top / bottom 20% of S&P 500 members for every rank-based tag

# One report's tag inputs (keys include 'yield', a keyword, hence the functional form). Each number sits next
# to the page text it was read from, under 'raw'; 'tags' is added once the thresholds are known.
TagInputs = TypedDict('TagInputs', {
    'slug': str, 'ticker': str | None, 'as_of': str | None, 'industry': str | None, 'sp500': bool,
    'raw': dict[str, str | float | None], 'price': float | None, 'w52_high': float | None, 'mcap': float | None,
    'fcf': float | None, 'eps': float | None, 'pe': float | None, 'yield': float | None, 'revg': float | None,
    'roic': float | None, 'de': float | None, 'beta': float | None, 'fcf_yield': float | None,
    'excluded': NotRequired[str], 'tags': NotRequired[list[dict[str, str]]],
})


def money(s: str | None) -> float | None:
    """'$99.92B' -> 9.992e10; '-$1.2B' / '($1.2B)' negative."""
    if s is None:
        return None
    m = re.search(r'(\(?)(-?)\s*\$?\s*(\d[\d,]*\.?\d*)\s*([TBMK])?', rl.normalize_dashes(s))
    if not m:
        return None
    v = float(m.group(3).replace(',', '')) * {'T': 1e12, 'B': 1e9, 'M': 1e6, 'K': 1e3, None: 1}[m.group(4)]
    return -v if (m.group(1) or m.group(2)) else v


TABLE_ROWS = {'pe_tbl': r'^(Trailing P/E|P/E\b)', 'revg': r'^Revenue Growth', 'roic': r'^ROIC', 'de': r'^Debt[- ]to[- ]Equity', 'beta': r'^Beta'}


def table_rows(path: str) -> dict[str, str]:
    """The TABLE_ROWS cells of the report's metrics table (class fin-table), keyed as in TABLE_ROWS."""
    m = re.search(r'<table class="fin-table".*?</table>', rl.read_text(path), re.S)
    rows = rl.table_rows(m.group(0)) if m else []
    found = {key: rl.row_value(rows, label, re.I) for key, label in TABLE_ROWS.items()}
    return {key: value for key, value in found.items() if value is not None}


def quantile(vals: Sequence[float], p: float) -> float:
    v = sorted(vals)
    k = (len(v) - 1) * p
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def pct_rank(v: float, vals: Sequence[float]) -> int:
    """Share of values strictly below v, in %."""
    return round(100 * sum(x < v for x in vals) / len(vals))


def usd_fcf(raw: object) -> float | None:
    """Free cash flow in US dollars, or None when it is missing or quoted in another currency (which cannot be
    divided by a US-dollar market cap)."""
    if isinstance(raw, str) and '$' in raw and not FOREIGN_CCY.search(raw):
        return money(raw)
    return None


def fcf_yield(fcf: float | None, mcap: float | None, industry: str | None) -> float | None:
    """Free cash flow as % of market cap; None where FCF is not meaningful (lenders, insurers, brokers)."""
    if fcf is None or not mcap or NO_CASH.search(industry or ''):
        return None
    return round(100 * fcf / mcap, 2)


def tag_inputs(slug: str, r: rl.ReportRecord, card: rl.IndexCard | None, tbl: dict[str, str]) -> TagInputs:
    """One report's tag inputs: who it is about (the index card wins over the manifest), every parsed number,
    and under 'raw' the page text each number came from."""
    industry = (card['card_industry'] if card else None) or r.get('industry')
    w52 = r.get('w52')
    pe, mcap, fcf = rl.first_number(r.get('pe_trailing')), money(r.get('market_cap')), usd_fcf(r.get('fcf'))
    d: TagInputs = {
        'slug': slug, 'ticker': (card['ticker'] if card else None) or r.get('ticker'), 'as_of': r.get('as_of'),
        'industry': industry, 'sp500': bool(card and card['indices']['sp500_added']),
        'raw': {'pe_trailing': r.get('pe_trailing'), 'eps_ttm': r.get('eps_ttm'), 'yield': r.get('yield_pct'),
                'market_cap': r.get('market_cap'), 'fcf': r.get('fcf'), **tbl},
        'price': rl.first_number(r.get('price')), 'w52_high': w52[1] if w52 else None,
        'mcap': mcap, 'fcf': fcf, 'eps': rl.first_number(r.get('eps_ttm')),
        'pe': pe if pe is not None else rl.first_number(tbl.get('pe_tbl')),   # the table row when the manifest missed it
        'yield': rl.first_number(r.get('yield_pct')),
        'revg': rl.first_number(tbl.get('revg')), 'roic': rl.first_number(tbl.get('roic')),
        'de': rl.first_number(tbl.get('de')), 'beta': rl.first_number(tbl.get('beta')),
        'fcf_yield': fcf_yield(fcf, mcap, industry),
    }
    if slug in EXCLUDE:
        d['excluded'] = EXCLUDE[slug]
    return d


def load_tag_inputs(repo: str = rl.ROOT) -> list[TagInputs]:
    """Tag inputs for every report in the manifest whose page exists, by slug."""
    cards = rl.parse_index_cards(repo)
    rows = []
    for slug, r in sorted(rl.load_report_records(repo).items()):
        path = rl.report_path(slug, repo=repo)
        if os.path.exists(path):
            rows.append(tag_inputs(slug, r, cards.get(slug), table_rows(path)))
    return rows


def universe(sp: list[TagInputs]) -> dict[str, list[float]]:
    """The S&P 500 members' values each rank-based tag is measured against."""
    return {
        'pe': [d['pe'] for d in sp if d['pe'] and d['pe'] > 0 and (d['eps'] is None or d['eps'] > 0)],
        'revg': [d['revg'] for d in sp if d['revg'] is not None],
        'yield': [d['yield'] for d in sp if d['yield'] and d['yield'] > 0],
        'fcf_yield': [d['fcf_yield'] for d in sp if d['fcf_yield'] is not None and d['fcf_yield'] > 0],
        'beta': [d['beta'] for d in sp if d['beta'] is not None],
        'roic': [d['roic'] for d in sp if d['roic'] is not None and not NO_QUALITY.search(d['industry'] or '')],
    }


def thresholds_for(u: dict[str, list[float]]) -> dict[str, float]:
    """Every cut-off the tags use, rank-based ones from the universe and fixed ones from the constants above.
    Published in data/style_tags.json, and the only source tags_for reads them from."""
    th = {
        'value_pe_max': quantile(u['pe'], PCT), 'pe_median': statistics.median(u['pe']),
        'growth_revg_min': quantile(u['revg'], 1 - PCT), 'revg_median': statistics.median(u['revg']),
        'income_yield_min': quantile(u['yield'], 1 - PCT), 'yield_median': statistics.median(u['yield']),
        'cash_fcfy_min': quantile(u['fcf_yield'], 1 - PCT), 'fcfy_median': statistics.median(u['fcf_yield']),
        'steady_beta_max': quantile(u['beta'], PCT), 'rollercoaster_beta_min': quantile(u['beta'], 1 - PCT),
        'quality_roic_min': quantile(u['roic'], 1 - PCT), 'roic_median': statistics.median(u['roic']),
        'quality_de_max': QUALITY_MAX_DE, 'giant_mcap_min': GIANT_MCAP, 'beaten_down_ratio': BEATEN_DOWN,
    }
    return {k: round(v, 3) for k, v in th.items()}


def as_of_note(d: TagInputs) -> str:
    """' Figures as of Sep 21, 2026.' for the tooltips; empty when the report's date was not extracted."""
    if not d['as_of']:
        return ''
    x = datetime.date.fromisoformat(d['as_of'])
    return f" Figures as of {x:%b} {x.day}, {x.year}."


def tags_for(d: TagInputs, th: dict[str, float], u: dict[str, list[float]]) -> list[list[str]]:
    """[tag, tooltip] pairs for one report, in display order. Formulas and rationale: claude/TAG_FORMULAS.md."""
    when = as_of_note(d)
    return (earnings_tags(d, th, u, when) + rank_tags(d, th, u, when) + beta_tags(d, th, when)
            + size_and_price_tags(d, th, when) + quality_tags(d, th, u, when))


def earnings_tags(d: TagInputs, th: dict[str, float], u: dict[str, list[float]], when: str) -> list[list[str]]:
    """Not yet profitable (a loss over 12 months), else Value (the cheapest 20% by trailing P/E)."""
    tags = []
    profitable = d['eps'] is None or d['eps'] > 0
    if not profitable:
        tags.append(['Not yet profitable', f"Lost money over the last 12 months: earnings per share were {d['raw']['eps_ttm']}." + when])
    if profitable and d['pe'] and 0 < d['pe'] <= th['value_pe_max']:
        tags.append(['Value', f"Priced at {d['pe']:.1f} times last year's earnings, cheaper than {100 - pct_rank(d['pe'], u['pe'])}% of S&P 500 companies. The median S&P 500 stock trades at {th['pe_median']:.1f} times. Value means the cheapest 20%." + when])
    return tags


def rank_tags(d: TagInputs, th: dict[str, float], u: dict[str, list[float]], when: str) -> list[list[str]]:
    """Growth, Income and Cash machine: the top 20% of S&P 500 members by revenue growth, yield and FCF yield."""
    tags = []
    if d['revg'] is not None and d['revg'] >= th['growth_revg_min']:
        tags.append(['Growth', f"Revenue grew {d['revg']:.1f}% over the last year, faster than {pct_rank(d['revg'], u['revg'])}% of S&P 500 companies. The median grew {th['revg_median']:.1f}%. Growth means the fastest-growing 20%." + when])
    if d['yield'] and d['yield'] >= th['income_yield_min']:
        tags.append(['Income', f"Pays a {d['yield']:.2f}% dividend yield, about ${d['yield']:.2f} a year per $100 invested. That beats {pct_rank(d['yield'], u['yield'])}% of S&P 500 dividend payers; the median pays {th['yield_median']:.2f}%. Income means the top 20% of payers." + when])
    if d['fcf_yield'] is not None and d['fcf_yield'] >= th['cash_fcfy_min']:
        tags.append(['Cash machine', f"Free cash flow, the cash left after running and investing in the business, was {d['fcf_yield']:.1f}% of the company's stock-market value, more than {pct_rank(d['fcf_yield'], u['fcf_yield'])}% of S&P 500 companies (median {th['fcfy_median']:.1f}%)." + when])
    return tags


def size_and_price_tags(d: TagInputs, th: dict[str, float], when: str) -> list[list[str]]:
    """Giant (market cap over the cut-off) and Beaten down (price at or under the ratio of its 52-week high)."""
    tags = []
    if d['mcap'] and d['mcap'] >= th['giant_mcap_min']:
        tags.append(['Giant', f"Worth about {d['raw']['market_cap']} on the stock market, one of the world's largest companies." + when])
    if d['price'] and d['w52_high'] and d['price'] <= th['beaten_down_ratio'] * d['w52_high']:
        tags.append(['Beaten down', f"Trading {100 * (1 - d['price'] / d['w52_high']):.0f}% below its 52-week high of ${d['w52_high']:,.2f}." + when])
    return tags


def beta_tags(d: TagInputs, th: dict[str, float], when: str) -> list[list[str]]:
    """Steady (calmest 20%) or Rollercoaster (most volatile 20%), from the report's 5-year beta."""
    if d['beta'] is None:
        return []
    if d['beta'] <= th['steady_beta_max']:
        return [['Steady', f"Beta of {d['beta']:.2f}: when the market has moved 10%, this stock has typically moved about {10 * d['beta']:.0f}%. Among the calmest 20% of the S&P 500." + when]]
    if d['beta'] >= th['rollercoaster_beta_min']:
        return [['Rollercoaster', f"Beta of {d['beta']:.2f}: when the market has moved 10%, this stock has typically moved about {10 * d['beta']:.0f}%, in either direction. Among the most volatile 20% of the S&P 500." + when]]
    return []


def quality_tags(d: TagInputs, th: dict[str, float], u: dict[str, list[float]], when: str) -> list[list[str]]:
    """Quality: top-20% ROIC outside banks, insurers and REITs, with debt-to-equity from 0 up to the cut-off."""
    roic, de = d['roic'], d['de']
    if (roic is None or de is None or NO_QUALITY.search(d['industry'] or '') or roic < th['quality_roic_min']
            or not 0 <= de < th['quality_de_max']):
        return []
    return [['Quality', f"Earns {roic:.1f}% a year on the money invested in the business, better than {pct_rank(roic, u['roic'])}% of S&P 500 companies outside banks, insurers and REITs, while carrying little debt (debt-to-equity {de:.2f})." + when]]


def main(repo: str = rl.ROOT) -> int:
    rows = load_tag_inputs(repo)
    live = [d for d in rows if 'excluded' not in d]
    sp = [d for d in live if d['sp500']]
    u = universe(sp)
    th = thresholds_for(u)
    for d in live:
        d['tags'] = [{'tag': t, 'tip': tip} for t, tip in tags_for(d, th, u)]
    out = {'generated_by': 'tools/style_tags.py', 'formulas': 'claude/TAG_FORMULAS.md',
           'universe': 'thresholds from S&P 500 members on reports/index.html (data-sp); applied to every report',
           'thresholds': th, 'sample_sizes': {k: len(v) for k, v in u.items()}, 'excluded': EXCLUDE, 'reports': rows}
    with open(os.path.join(repo, 'data', 'style_tags.json'), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)

    print(f"{len(rows)} reports ({len(live)} tagged, {len(rows) - len(live)} excluded); S&P members used for thresholds: {len(sp)}")
    for k, v in th.items():
        print(f'  {k:24} {v}')
    for k, v in Counter(t['tag'] for d in live for t in d['tags']).most_common():
        print(f'  {k:20} {v}')
    print('  untagged:', sum(1 for d in live if not d['tags']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
