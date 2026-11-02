"""data/analyzer_ref.json — the Portfolio Analyzer's reference data, generated, never hand-edited.

This pass covers the stock reports only: every record of the report manifest (data/reports/<sector>.json, written by
tools/manifest.py from the published pages) plus its head office from data/card_tags.json. Schema and the
analyzer's formulas: analyzer/README.md. Check the output with tools/verify_analyzer_ref.py.

    py -3 tools/analyzer_ref.py           write data/analyzer_ref.json and print what it could not fill
    py -3 tools/analyzer_ref.py --check   exit 1 if the committed file differs from a fresh build

Per stock:
  currency  from the listed ticker's suffix (7974.T -> JPY, LSEG.L -> GBX pence, no suffix -> USD). Not from
            global_exchange: that is the home market, which for an ADR (BABA, TM) is not where the price is quoted.
  country   ISO 3166 alpha-2 of the operating head office, from the card tag's "<place>-based" label; a label that
            names a city maps through CITY; no tag, or a place not in either map, gives null (listed on stdout).
  beta      the report's key-metrics beta; else its metrics-table (fin-table) cell when that is a plain number
            ("~5.2", "n/a" stay null); beta_source says which. Benchmark not stated by the manifest (beta_vs null).
Not yet in the file: ETFs/funds (MER, holdings), crypto, bonds, FX rates, risk-free rate, monthly series.
"""
import json
import os
import re
import sys

import repodata as rd

OUT = os.path.join('data', 'analyzer_ref.json')
GENERATOR = 'tools/analyzer_ref.py'

# Ticker suffix -> listing currency (Yahoo-style suffixes, as the manifest's tickers use them).
SUFFIX_CCY = {
    'T': 'JPY', 'L': 'GBX', 'TO': 'CAD', 'V': 'CAD', 'NE': 'CAD', 'HK': 'HKD', 'NS': 'INR', 'BO': 'INR',
    'DE': 'EUR', 'F': 'EUR', 'PA': 'EUR', 'AS': 'EUR', 'MC': 'EUR', 'MI': 'EUR', 'BR': 'EUR', 'LS': 'EUR',
    'SW': 'CHF', 'KS': 'KRW', 'KQ': 'KRW', 'SS': 'CNY', 'SZ': 'CNY', 'SR': 'SAR', 'SI': 'SGD', 'AX': 'AUD',
    'ST': 'SEK', 'CO': 'DKK', 'OL': 'NOK', 'HE': 'EUR', 'TW': 'TWD', 'SA': 'BRL', 'MX': 'MXN', 'JO': 'ZAc',
}
US_CLASS_SUFFIX = {'A', 'B', 'C'}   # BRK.B, BF.B: US share classes, quoted in USD

COUNTRY = {
    'US': 'US', 'UK': 'GB', 'Switzerland': 'CH', 'Germany': 'DE', 'Canada': 'CA', 'Ireland': 'IE', 'China': 'CN',
    'Japan': 'JP', 'France': 'FR', 'Netherlands': 'NL', 'Sweden': 'SE', 'South Korea': 'KR', 'Spain': 'ES',
    'Singapore': 'SG', 'Brazil': 'BR', 'India': 'IN', 'Taiwan': 'TW', 'Italy': 'IT', 'Bermuda': 'BM',
    'Uruguay': 'UY', 'Belgium': 'BE', 'Saudi Arabia': 'SA', 'Norway': 'NO', 'Denmark': 'DK', 'Australia': 'AU',
    'Hong Kong': 'HK', 'Israel': 'IL', 'Mexico': 'MX', 'Luxembourg': 'LU', 'Finland': 'FI', 'Jersey': 'JE',
    'Argentina': 'AR', 'South Africa': 'ZA', 'Austria': 'AT', 'Portugal': 'PT', 'Greece': 'GR',
}
CITY = {  # card-tag labels that name a city instead of a country
    'Tokyo': 'JP', 'Yamaguchi': 'JP', 'Osaka': 'JP', 'Kyoto': 'JP', 'Beijing': 'CN', 'Shanghai': 'CN',
    'Shenzhen': 'CN', 'Hangzhou': 'CN', 'Gurugram': 'IN', 'Mumbai': 'IN', 'Bengaluru': 'IN', 'Paris': 'FR',
    'Amsterdam': 'NL', 'London': 'GB', 'Sydney': 'AU', 'Melbourne': 'AU', 'Seoul': 'KR', 'Zurich': 'CH',
}


def currency_of(ticker: str) -> str:
    """Listing currency from the ticker's suffix. Raises ValueError on a suffix not in SUFFIX_CCY."""
    if '.' not in ticker:
        return 'USD'
    suffix = ticker.rsplit('.', 1)[1].upper()
    if suffix in SUFFIX_CCY:
        return SUFFIX_CCY[suffix]
    if suffix in US_CLASS_SUFFIX:
        return 'USD'
    raise ValueError(f'{ticker}: ticker suffix .{suffix} has no currency in SUFFIX_CCY')


def country_of(hq: list[str] | None) -> str | None:
    """ISO alpha-2 country of a card tag's head office ['<place>-based', full text], or None."""
    if not hq:
        return None
    place = hq[0].removesuffix('-based')
    if place in COUNTRY:
        return COUNTRY[place]
    if place in CITY:
        return CITY[place]
    full = hq[1] if len(hq) > 1 else ''
    hits = {code for city, code in CITY.items() if city in full}
    return hits.pop() if len(hits) == 1 else None


def plain_number(cell: object) -> float | None:
    """A metrics cell as a number only when it is one: 1.2, '0.96', '-0.3'; '~5.2', '≈0.0', 'n/a' -> None."""
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        return float(cell)
    if isinstance(cell, str) and re.fullmatch(r'-?\d+(\.\d+)?', cell.strip()):
        return float(cell.strip())
    return None


def beta_of(r: rd.ReportRecord) -> tuple[float | None, str | None]:
    """(beta, where it came from) for one manifest record."""
    km = plain_number(r.get('beta'))
    if km is not None:
        return km, 'key metrics'
    ft = plain_number(r.get('fin_table', {}).get('beta'))
    if ft is not None:
        return ft, 'fin-table'
    return None, None


def build(repo: str) -> tuple[dict[str, object], list[str]]:
    """The reference object and the lines to print about what it could not fill."""
    manifest = rd.load_manifest(repo)
    recs = rd.load_report_records(repo)
    with open(os.path.join(repo, 'data', 'card_tags.json'), encoding='utf-8') as fh:
        cards = json.load(fh)['cards']
    shard_of = {}
    for sector, rel in manifest['shards'].items():
        shard_of[sector] = rel.replace('\\', '/')
    secs: dict[str, dict[str, object]] = {}
    aliases: dict[str, str] = {}
    notes: list[str] = []
    no_country: list[str] = []
    no_beta: list[str] = []
    beta_conflicts: list[str] = []
    for slug in sorted(recs):
        r = recs[slug]
        ticker = r['ticker']
        hq = cards.get(slug, {}).get('hq')
        country = country_of(hq)
        if country is None:
            no_country.append(f"{slug} ({hq[0] if hq else 'no hq tag'})")
        beta, beta_source = beta_of(r)
        if beta is None:
            no_beta.append(slug)
        ft = plain_number(r.get('fin_table', {}).get('beta'))
        km = r.get('beta')
        if isinstance(km, (int, float)) and ft is not None and abs(km - ft) > 0.005:
            beta_conflicts.append(f'{slug} (key metrics {km}, fin-table {ft})')
        secs[slug] = {
            'type': 'stock', 'name': r['name'], 'ticker': ticker, 'currency': currency_of(ticker),
            'price': r['price'], 'as_of': r['as_of'],
            'source': f"reports/{slug}_analysis.html via {shard_of.get(r['sector_key'], 'data/reports')}",
            'sector': r['sector_key'], 'industry': r.get('industry'), 'country': country,
            'country_source': 'data/card_tags.json hq' if country else None,
            'beta': beta, 'beta_source': beta_source, 'beta_vs': None, 'market_cap_usd': r.get('market_cap_usd'),
            'exchange': r.get('exchange'),
        }
        key = ticker.upper()
        if key in aliases:
            raise ValueError(f'ticker {ticker} is on two reports: {aliases[key]} and {slug}')
        aliases[key] = slug
    ref: dict[str, object] = {
        'schema': 'ttg-analyzer-ref', 'v': 1,
        'generated_at': manifest['generated_at'],   # the manifest's time, so a rebuild of the same inputs is identical
        'generator': GENERATOR,
        'sources': {
            'stocks': 'data/reports.json shards (tools/manifest.py, from the published report pages)',
            'country': 'data/card_tags.json hq (tools/headoffice.py, from each report\'s HQ line)',
        },
        'pending': ['etf', 'fund', 'crypto', 'bond', 'cash', 'fx', 'rf', 'series'],
        'counts': {'stock': len(secs), 'stock_no_country': len(no_country), 'stock_no_beta': len(no_beta)},
        'securities': secs,
        'aliases': dict(sorted(aliases.items())),
    }
    notes.append(f'{len(secs)} stocks · {len(secs) - len(no_country)} with a country · {len(secs) - len(no_beta)} with a beta')
    notes.append(f'no country ({len(no_country)}): ' + ', '.join(no_country))
    notes.append(f'no beta ({len(no_beta)}): ' + ', '.join(no_beta[:30]) + (' …' if len(no_beta) > 30 else ''))
    notes.append(f'beta: key metrics and fin-table disagree ({len(beta_conflicts)}): ' + ', '.join(beta_conflicts))
    ccys: dict[str, int] = {}
    for s in secs.values():
        ccys[str(s['currency'])] = ccys.get(str(s['currency']), 0) + 1
    notes.append('currencies: ' + ', '.join(f'{c} {n}' for c, n in sorted(ccys.items(), key=lambda x: -x[1])))
    return ref, notes


def serialise(ref: dict[str, object]) -> str:
    """Stable text: top-level keys in order, one security per line, so a diff shows which ones changed."""
    secs = ref['securities']
    assert isinstance(secs, dict)
    head = {k: v for k, v in ref.items() if k not in ('securities', 'aliases')}
    lines = ['{']
    for k, v in head.items():
        lines.append(f'  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},')
    lines.append('  "securities": {')
    items = list(secs.items())
    for i, (k, v) in enumerate(items):
        lines.append(f'    {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}' + (',' if i < len(items) - 1 else ''))
    lines.append('  },')
    lines.append(f'  "aliases": {json.dumps(ref["aliases"], ensure_ascii=False)}')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def main() -> int:
    ap = rd.parser(__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='exit 1 if the committed file differs from a fresh build')
    args = ap.parse_args()
    ref, notes = build(args.repo)
    text = serialise(ref)
    path = os.path.join(args.repo, OUT)
    if args.check:
        try:
            with open(path, encoding='utf-8', newline='') as fh:
                same = fh.read() == text
        except FileNotFoundError:
            same = False
        print(f"{OUT}: {'up to date' if same else 'STALE — run py -3 tools/analyzer_ref.py'}")
        return 0 if same else 1
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    print(f'wrote {OUT} ({os.path.getsize(path):,} bytes)')
    for n in notes:
        print('  ' + n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
