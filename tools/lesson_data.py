"""Data for the Lessons' charts that use real prices: learn/lessons/data/crypto.json, read by learn/lessons/lesson.js.

usage: py -3 tools/lesson_data.py           (writes the file)
       py -3 tools/lesson_data.py --check   (writes nothing; non-zero when the file differs from the reports)

The crypto lesson compares $1,000 in bitcoin, ether and the S&P 500 (VOO with dividends reinvested), month by month,
using the monthly closes already published in our own reports (reports/crypto/btc, eth; reports/etf/voo). The file
carries each report's banner date, which the chart prints. Re-run it after those reports are refreshed.
"""
import json
import os
import re
import sys

import reportlib as rl
import repodata as rd

OUT = os.path.join('learn', 'lessons', 'data', 'crypto.json')
SOURCES = {'btc': 'reports/crypto/btc_analysis.html', 'eth': 'reports/crypto/eth_analysis.html',
           'voo': 'reports/etf/voo_analysis.html'}
NAMES = {'btc': 'Bitcoin', 'eth': 'Ether', 'voo': 'S&P 500 (VOO, dividends reinvested)'}


def as_of(t: str) -> str:
    m = re.search(r'Static data as of ([A-Z][a-z]+ \d{1,2}, \d{4})', t)
    if not m:
        raise ValueError('no "Static data as of" date')
    return m.group(1)


def total_return(t: str) -> list[float] | None:
    m = re.search(r'const totalReturn\s*=\s*\[([^\]]*)\]', t)
    return [float(x) for x in m.group(1).split(',') if x.strip()] if m else None


def build(repo: str) -> dict:
    out: dict = {'generated_by': 'tools/lesson_data.py', 'names': NAMES, 'as_of': {}, 'series': {}}
    labels = None
    for key, rel in SOURCES.items():
        t = rl.read_text(os.path.join(repo, rel))
        lab, prices = rl.chart_series(t)
        if not lab or not prices:
            raise ValueError(f'{rel}: no chart arrays')
        if key == 'voo':
            prices = total_return(t) or prices
        # the last point is each report's own banner day ('Sep 22 26' vs 'Sep 23 26'): same month is enough
        month = lab[:-1] + [re.sub(r'^([A-Z][a-z]{2}) \d{1,2} (\d{2})$', r'\1 \2', lab[-1])]
        if labels is None:
            labels = month
        if month != labels or len(prices) != len(labels):
            raise ValueError(f'{rel}: its monthly labels differ from {SOURCES["btc"]}; the chart needs one grid')
        out['as_of'][key] = as_of(t)
        out['series'][key] = prices
    out['labels'] = labels
    return out


def main(argv: list[str] | None = None) -> int | str:
    ap = rd.parser('Write learn/lessons/data/crypto.json from the BTC, ETH and VOO reports.')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    try:
        data = build(args.repo)
    except (OSError, ValueError) as err:
        return str(err)
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n'
    path = os.path.join(args.repo, OUT)
    current = rl.read_text(path) if os.path.exists(path) else None
    if args.check:
        return 0 if current == text else f'out of date (run py -3 tools/lesson_data.py): {OUT}'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rl.write_text(path, text)
    print(f'wrote {OUT}: {len(data["labels"])} months, as of {data["as_of"]}'.replace(os.sep, '/'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
