"""Check a Portfolio Analyzer reference file (schema: analyzer/README.md). Exits 1 and lists every failure.

    py -3 tools/verify_analyzer_ref.py                                  data/analyzer_ref.json vs the report manifest
    py -3 tools/verify_analyzer_ref.py analyzer/test/fixture_ref.json   any other file (no manifest count check)

Fails on: wrong schema/version; a security without type, name, currency, a positive price, an ISO as_of or a source;
an unknown sector, asset class or type; a country that is not ISO alpha-2; a non-numeric beta or an MER outside
0–20%; holdings weights outside (0, 1] or summing above 100%; an allocation or breakdown not summing to 100% (±0.5%);
a holdings row pointing at a missing security; a series with gaps, non-positive values or mismatched lengths;
FX or rf entries that are not positive/numeric; aliases that are not upper case, point nowhere, or miss a ticker;
and, for data/analyzer_ref.json, a stock count different from the manifest's report count.
"""
import json
import math
import os
import re
import sys

import repodata as rd

TYPES = {'stock', 'etf', 'fund', 'bond', 'crypto', 'cash', 'other'}
ASSET_CLASSES = {'equity', 'fixed_income', 'cash', 'crypto', 'other'}
SECTORS = {'communicationservices', 'consumerdiscretionary', 'consumerstaples', 'energy', 'financials', 'healthcare',
           'industrials', 'materials', 'realestate', 'technology', 'utilities'}
LEVELS = {'exact', 'partial', 'estimate'}
BASES = {'total_return', 'price'}
DATE = re.compile(r'\d{4}-\d{2}-\d{2}$')
MONTH = re.compile(r'\d{4}-(0[1-9]|1[0-2])$')
CCY = re.compile(r'[A-Z]{3}$|ZAc$')
ISO2 = re.compile(r'[A-Z]{2}$')
TOL = 0.005


def num(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def month_index(m: str) -> int:
    y, mo = m.split('-')
    return int(y) * 12 + int(mo) - 1


def check_months(where: str, months: object, errs: list[str]) -> None:
    if not isinstance(months, list) or not months or not all(isinstance(m, str) and MONTH.match(m) for m in months):
        errs.append(f'{where}: months must be a non-empty list of YYYY-MM')
        return
    gaps = [months[i] for i in range(1, len(months)) if month_index(months[i]) != month_index(months[i - 1]) + 1]
    if gaps:
        errs.append(f'{where}: months not consecutive at {gaps[:3]}')


def check_dist(where: str, d: object, keys: set[str] | None, errs: list[str], exact: bool = True) -> None:
    """A {bucket: share} split: shares in [0, 1], keys known (or '_'-prefixed non-applicable buckets), sum 100%."""
    if not isinstance(d, dict) or not d:
        errs.append(f'{where}: must be a non-empty object')
        return
    for k, v in d.items():
        if not num(v) or not 0 <= v <= 1:
            errs.append(f'{where}.{k}: share must be a number in [0, 1]')
        if keys is not None and k not in keys and not (k.startswith('_') and k[1:] in ASSET_CLASSES):
            errs.append(f'{where}: unknown bucket {k}')
    total = sum(v for v in d.values() if num(v))
    if (exact and abs(total - 1) > TOL) or total > 1 + TOL:
        errs.append(f'{where}: shares sum to {total:.4f}, not 1')


def check_security(key: str, s: object, secs: dict[str, object], errs: list[str]) -> None:
    at = f'securities.{key}'
    if not isinstance(s, dict):
        errs.append(f'{at}: not an object')
        return
    t = s.get('type')
    if t not in TYPES:
        errs.append(f'{at}.type: {t!r} not one of {sorted(TYPES)}')
    for f in ('name', 'source'):
        if not isinstance(s.get(f), str) or not s.get(f):
            errs.append(f'{at}.{f}: missing')
    if not isinstance(s.get('currency'), str) or not CCY.match(s['currency']):
        errs.append(f'{at}.currency: {s.get("currency")!r} is not a currency code')
    if not num(s.get('price')) or s['price'] <= 0:
        errs.append(f'{at}.price: must be a number > 0')
    if not isinstance(s.get('as_of'), str) or not DATE.match(s['as_of']):
        errs.append(f'{at}.as_of: must be YYYY-MM-DD')
    if s.get('sector') is not None and s['sector'] not in SECTORS:
        errs.append(f'{at}.sector: unknown {s["sector"]!r}')
    if t == 'stock' and s.get('sector') is None:
        errs.append(f'{at}.sector: a stock needs one')
    if s.get('asset_class') is not None and s['asset_class'] not in ASSET_CLASSES:
        errs.append(f'{at}.asset_class: unknown {s["asset_class"]!r}')
    if s.get('country') is not None and not (isinstance(s['country'], str) and ISO2.match(s['country'])):
        errs.append(f'{at}.country: {s["country"]!r} is not ISO alpha-2')
    if s.get('beta') is not None and not num(s['beta']):
        errs.append(f'{at}.beta: must be a number or null')
    if s.get('mer') is not None and not (num(s['mer']) and 0 <= s['mer'] <= 0.2):
        errs.append(f'{at}.mer: must be a fraction in [0, 0.2]')
    if s.get('allocation') is not None:
        check_dist(f'{at}.allocation', s['allocation'], ASSET_CLASSES, errs)
    bd = s.get('breakdown')
    if bd is not None:
        if not isinstance(bd, dict):
            errs.append(f'{at}.breakdown: must be an object')
        else:
            for dim, d in bd.items():
                keys = {'asset_class': ASSET_CLASSES, 'sector': SECTORS}.get(dim)
                if dim not in ('asset_class', 'sector', 'country'):
                    errs.append(f'{at}.breakdown: unknown dimension {dim}')
                check_dist(f'{at}.breakdown.{dim}', d, keys, errs)
    h = s.get('holdings')
    if h is not None:
        if t not in ('etf', 'fund'):
            errs.append(f'{at}.holdings: only funds hold securities')
        if not isinstance(h, dict) or not isinstance(h.get('rows'), list):
            errs.append(f'{at}.holdings: needs rows')
        else:
            if h.get('level') not in LEVELS:
                errs.append(f'{at}.holdings.level: not one of {sorted(LEVELS)}')
            if not isinstance(h.get('as_of'), str) or not DATE.match(h['as_of']):
                errs.append(f'{at}.holdings.as_of: must be YYYY-MM-DD')
            if not h.get('source'):
                errs.append(f'{at}.holdings.source: missing')
            total = 0.0
            for i, row in enumerate(h['rows']):
                w = row.get('w') if isinstance(row, dict) else None
                if not num(w) or not 0 < w <= 1:
                    errs.append(f'{at}.holdings.rows[{i}].w: must be in (0, 1]')
                else:
                    total += w
                rk = row.get('key') if isinstance(row, dict) else None
                if rk is None and not (isinstance(row, dict) and row.get('name')):
                    errs.append(f'{at}.holdings.rows[{i}]: needs key or name')
                if rk is not None and rk not in secs:
                    errs.append(f'{at}.holdings.rows[{i}].key: {rk} is not a security')
            if total > 1 + 1e-6:
                errs.append(f'{at}.holdings: weights sum to {total:.4f}, above 1')
    se = s.get('series')
    if se is not None:
        if not isinstance(se, dict):
            errs.append(f'{at}.series: must be an object')
        else:
            if se.get('basis') not in BASES:
                errs.append(f'{at}.series.basis: not one of {sorted(BASES)}')
            if not se.get('source'):
                errs.append(f'{at}.series.source: missing')
            check_months(f'{at}.series', se.get('months'), errs)
            vals = se.get('values')
            if not isinstance(vals, list) or not isinstance(se.get('months'), list) or len(vals) != len(se['months']):
                errs.append(f'{at}.series: values and months differ in length')
            elif not all(num(v) and v > 0 for v in vals):
                errs.append(f'{at}.series.values: must all be > 0')


def verify(ref: object, manifest_count: int | None = None) -> list[str]:
    errs: list[str] = []
    if not isinstance(ref, dict):
        return ['file is not a JSON object']
    if ref.get('schema') != 'ttg-analyzer-ref' or ref.get('v') != 1:
        errs.append('schema must be ttg-analyzer-ref, v 1')
    for f in ('generated_at', 'generator'):
        if not ref.get(f):
            errs.append(f'{f}: missing')
    secs = ref.get('securities')
    if not isinstance(secs, dict) or not secs:
        return errs + ['securities: missing or empty']
    for k, s in secs.items():
        check_security(k, s, secs, errs)
    aliases = ref.get('aliases')
    if not isinstance(aliases, dict):
        errs.append('aliases: missing')
    else:
        for a, k in aliases.items():
            if a != a.upper():
                errs.append(f'aliases.{a}: must be upper case')
            if k not in secs:
                errs.append(f'aliases.{a}: points at missing {k}')
        for k, s in secs.items():
            if isinstance(s, dict) and s.get('ticker') and aliases.get(str(s['ticker']).upper()) != k:
                errs.append(f'aliases: ticker {s["ticker"]} does not resolve to {k}')
    fx = ref.get('fx')
    if fx is not None:
        if not isinstance(fx, dict) or not fx.get('source') or not DATE.match(str(fx.get('as_of', ''))):
            errs.append('fx: needs source and as_of')
        usd_per = fx.get('usd_per') if isinstance(fx, dict) else None
        if not isinstance(usd_per, dict) or not all(CCY.match(c) and num(r) and r > 0 for c, r in usd_per.items()):
            errs.append('fx.usd_per: currency -> positive USD per unit')
    rf = ref.get('rf')
    if rf is not None:
        if not isinstance(rf, dict) or not rf.get('source'):
            errs.append('rf: needs source')
        else:
            check_months('rf', rf.get('months'), errs)
            pct = rf.get('annual_pct')
            if not isinstance(pct, list) or len(pct) != len(rf.get('months') or []) or not all(num(x) for x in pct):
                errs.append('rf.annual_pct: one number per month')
    if manifest_count is not None:
        n = sum(1 for s in secs.values() if isinstance(s, dict) and s.get('type') == 'stock')
        if n != manifest_count:
            errs.append(f'stock count {n} != manifest report count {manifest_count}')
    return errs


def main() -> int:
    ap = rd.parser(__doc__.split('\n')[0])
    ap.add_argument('path', nargs='?', help='reference file (default data/analyzer_ref.json, checked against the manifest)')
    args = ap.parse_args()
    path = args.path or os.path.join(args.repo, 'data', 'analyzer_ref.json')
    with open(path, encoding='utf-8') as fh:
        ref = json.load(fh)
    count = rd.load_manifest(args.repo)['count'] if args.path is None else None
    errs = verify(ref, count)
    n = len(ref.get('securities') or {}) if isinstance(ref, dict) else 0
    if errs:
        print(f'FAIL {path}: {len(errs)} problem(s) in {n} securities')
        for e in errs[:200]:
            print('  ' + e)
        return 1
    print(f'ok {path}: {n} securities' + (f', stock count = manifest ({count})' if count is not None else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
