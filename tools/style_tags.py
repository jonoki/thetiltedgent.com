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
import html
import json
import os
import re
import statistics
from collections import Counter

import reportlib as rl
from reportlib import first_number as num

# Reports to leave out of tagging, slug -> reason. Empty: CBOE and MTD were excluded on 22 Sep 2026 over
# swapped <title> tags (bodies were correct); titles fixed the same day.
EXCLUDE = {}
# Quality is not meaningful for balance-sheet businesses (Oki, 22 Sep 2026).
NO_QUALITY = re.compile(r'\bBANK|INSURANCE|REIT\b', re.I)
# Free cash flow is not meaningful for lenders, insurers and brokers (customer money flows through it).
NO_CASH = re.compile(r'\bBANK|INSURANCE|CAPITAL MARKETS\b', re.I)
# FCF quoted in another currency cannot be divided by a US-dollar market cap.
FOREIGN_CCY = re.compile(r'[¥€£₩]|(?:NT|HK|C|A|R|S)\$')

GIANT_MCAP = 200e9          # convention, not an official line
BEATEN_DOWN = 0.60          # price <= 60% of the 52-week high
QUALITY_MAX_DE = 1.0
PCT = 0.20                  # top / bottom 20% of S&P 500 members for every rank-based tag


def money(s: str | None) -> float | None:
    """'$99.92B' -> 9.992e10; '-$1.2B' / '($1.2B)' negative."""
    if s is None:
        return None
    s = str(s).replace('−', '-')
    m = re.search(r'(\(?)(-?)\s*\$?\s*(\d[\d,]*\.?\d*)\s*([TBMK])?', s)
    if not m:
        return None
    v = float(m.group(3).replace(',', '')) * {'T': 1e12, 'B': 1e9, 'M': 1e6, 'K': 1e3, None: 1}[m.group(4)]
    return -v if (m.group(1) or m.group(2)) else v


TABLE_ROWS = {'pe_tbl': r'^(Trailing P/E|P/E\b)', 'revg': r'^Revenue Growth', 'roic': r'^ROIC', 'de': r'^Debt[- ]to[- ]Equity', 'beta': r'^Beta'}


def table_rows(path: str) -> dict[str, str]:
    t = rl.read_text(path)
    m = re.search(r'<table class="fin-table".*?</table>', t, re.S)
    out = {}
    if not m:
        return out
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(0), re.S):
        cells = [html.unescape(re.sub('<[^>]+>', '', c)).strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.S)]
        if len(cells) >= 2:
            for k, pat in TABLE_ROWS.items():
                if k not in out and re.search(pat, cells[0], re.I):
                    out[k] = cells[1]
    return out


def quantile(vals: list[float], p: float) -> float:
    v = sorted(vals)
    k = (len(v) - 1) * p
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def pct_rank(v: float, vals: list[float]) -> int:
    """Share of values strictly below v, in %."""
    return round(100 * sum(x < v for x in vals) / len(vals))


def inputs(slug: str, r: dict, card: dict, tbl: dict[str, str]) -> dict:
    """One report's tag inputs: every parsed number, with the raw text it came from under 'raw'."""
    w52 = r.get('w52') or [None, None]
    d = {
        'slug': slug, 'ticker': card.get('ticker') or r.get('ticker'), 'as_of': r.get('as_of'),
        'industry': card.get('card_industry') or r.get('industry'),
        'sp500': bool((card.get('indices') or {}).get('sp500_added')),
        'raw': {'pe_trailing': r.get('pe_trailing'), 'eps_ttm': r.get('eps_ttm'), 'yield': r.get('yield_pct'),
                'market_cap': r.get('market_cap'), 'fcf': r.get('fcf'), **tbl},
    }
    d['price'] = num(r.get('price'))
    d['w52_high'] = num(w52[1])
    d['mcap'] = money(r.get('market_cap'))
    fcf_raw = r.get('fcf')
    usd_fcf = isinstance(fcf_raw, str) and '$' in fcf_raw and not FOREIGN_CCY.search(fcf_raw)
    d['fcf'] = money(fcf_raw) if usd_fcf else None
    d['eps'] = num(r.get('eps_ttm'))
    d['pe'] = num(r.get('pe_trailing'))
    if d['pe'] is None:
        d['pe'] = num(tbl.get('pe_tbl'))   # manifest missed it; fall back to the table row
    d['yield'] = num(r.get('yield_pct'))
    for k in TABLE_ROWS:
        if k != 'pe_tbl':
            d[k] = num(tbl.get(k))
    cash_ok = d['fcf'] is not None and d['mcap'] and not NO_CASH.search(d['industry'] or '')
    d['fcf_yield'] = round(100 * d['fcf'] / d['mcap'], 2) if cash_ok else None
    if slug in EXCLUDE:
        d['excluded'] = EXCLUDE[slug]
    return d


def load() -> list[dict]:
    cards = rl.parse_index_cards()
    rows = []
    for slug, r in sorted(rl.load_report_records().items()):
        path = os.path.join(rl.ROOT, 'reports', f'{slug}_analysis.html')
        if os.path.exists(path):
            rows.append(inputs(slug, r, cards.get(slug, {}), table_rows(path)))
    return rows


def universe(sp: list[dict]) -> dict[str, list[float]]:
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


def as_of_note(d: dict) -> str:
    x = datetime.date.fromisoformat(d['as_of'])
    return f" Figures as of {x:%b} {x.day}, {x.year}."


def tags_for(d: dict, th: dict[str, float], u: dict[str, list[float]]) -> list[list[str]]:
    """[tag, tooltip] pairs for one report. Formulas and rationale: claude/TAG_FORMULAS.md."""
    tags, when = [], as_of_note(d)
    profitable = d['eps'] is None or d['eps'] > 0
    if not profitable:
        tags.append(['Not yet profitable', f"Lost money over the last 12 months: earnings per share were {d['raw']['eps_ttm']}." + when])
    if profitable and d['pe'] and 0 < d['pe'] <= th['value_pe_max']:
        tags.append(['Value', f"Priced at {d['pe']:.1f} times last year's earnings, cheaper than {100 - pct_rank(d['pe'], u['pe'])}% of S&P 500 companies. The median S&P 500 stock trades at {th['pe_median']:.1f} times. Value means the cheapest 20%." + when])
    if d['revg'] is not None and d['revg'] >= th['growth_revg_min']:
        tags.append(['Growth', f"Revenue grew {d['revg']:.1f}% over the last year, faster than {pct_rank(d['revg'], u['revg'])}% of S&P 500 companies. The median grew {th['revg_median']:.1f}%. Growth means the fastest-growing 20%." + when])
    if d['yield'] and d['yield'] >= th['income_yield_min']:
        tags.append(['Income', f"Pays a {d['yield']:.2f}% dividend yield, about ${d['yield']:.2f} a year per $100 invested. That beats {pct_rank(d['yield'], u['yield'])}% of S&P 500 dividend payers; the median pays {th['yield_median']:.2f}%. Income means the top 20% of payers." + when])
    if d['fcf_yield'] is not None and d['fcf_yield'] >= th['cash_fcfy_min']:
        tags.append(['Cash machine', f"Free cash flow, the cash left after running and investing in the business, was {d['fcf_yield']:.1f}% of the company's stock-market value, more than {pct_rank(d['fcf_yield'], u['fcf_yield'])}% of S&P 500 companies (median {th['fcfy_median']:.1f}%)." + when])
    tags += beta_tags(d, th, when)
    if d['mcap'] and d['mcap'] >= GIANT_MCAP:
        tags.append(['Giant', f"Worth about {d['raw']['market_cap']} on the stock market, one of the world's largest companies." + when])
    if d['price'] and d['w52_high'] and d['price'] <= BEATEN_DOWN * d['w52_high']:
        tags.append(['Beaten down', f"Trading {100 * (1 - d['price'] / d['w52_high']):.0f}% below its 52-week high of ${d['w52_high']:,.2f}." + when])
    if quality(d, th):
        tags.append(['Quality', f"Earns {d['roic']:.1f}% a year on the money invested in the business, better than {pct_rank(d['roic'], u['roic'])}% of S&P 500 companies outside banks, insurers and REITs, while carrying little debt (debt-to-equity {d['de']:.2f})." + when])
    return tags


def beta_tags(d: dict, th: dict[str, float], when: str) -> list[list[str]]:
    if d['beta'] is None:
        return []
    if d['beta'] <= th['steady_beta_max']:
        return [['Steady', f"Beta of {d['beta']:.2f}: when the market has moved 10%, this stock has typically moved about {10 * d['beta']:.0f}%. Among the calmest 20% of the S&P 500." + when]]
    if d['beta'] >= th['rollercoaster_beta_min']:
        return [['Rollercoaster', f"Beta of {d['beta']:.2f}: when the market has moved 10%, this stock has typically moved about {10 * d['beta']:.0f}%, in either direction. Among the most volatile 20% of the S&P 500." + when]]
    return []


def quality(d: dict, th: dict[str, float]) -> bool:
    return (d['roic'] is not None and not NO_QUALITY.search(d['industry'] or '') and d['roic'] >= th['quality_roic_min']
            and d['de'] is not None and 0 <= d['de'] < QUALITY_MAX_DE)


def main() -> None:
    rows = load()
    live = [d for d in rows if 'excluded' not in d]
    sp = [d for d in live if d['sp500']]
    u = universe(sp)
    th = thresholds_for(u)
    for d in live:
        d['tags'] = [{'tag': t, 'tip': tip} for t, tip in tags_for(d, th, u)]
    out = {'generated_by': 'tools/style_tags.py', 'formulas': 'claude/TAG_FORMULAS.md',
           'universe': 'thresholds from S&P 500 members on reports/index.html (data-sp); applied to every report',
           'thresholds': th, 'sample_sizes': {k: len(v) for k, v in u.items()}, 'excluded': EXCLUDE, 'reports': rows}
    with open(os.path.join(rl.ROOT, 'data', 'style_tags.json'), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)

    print(f"{len(rows)} reports ({len(live)} tagged, {len(rows) - len(live)} excluded); S&P members used for thresholds: {len(sp)}")
    for k, v in th.items():
        print(f'  {k:24} {v}')
    for k, v in Counter(t['tag'] for d in live for t in d['tags']).most_common():
        print(f'  {k:20} {v}')
    print('  untagged:', sum(1 for d in live if not d['tags']))


if __name__ == '__main__':
    main()
