#!/usr/bin/env python3
"""Build data/reports.json and data/reports/<sector>.json — the machine-readable manifest of every live report.

Extracts from the report HTML itself rather than re-researching, so the manifest can never disagree with
what is actually published. A field that cannot be parsed is left out of the record (a missing key means
"not extracted") and the record's warnings say why; nothing is guessed.

usage:  py -3 tools/manifest.py [repo-root] [-o data/reports.json] [--full-metrics]
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Mapping, cast

import reportlib as rl

SCHEMA_VERSION = 1
GENERATOR = 'tools/manifest.py'

# Metrics a client-side live-price recompute needs: everything price-derived on the page can be rebuilt
# from a live quote plus these static values. Each is stored as a number when the cell parses as one,
# otherwise as the cell's text ("n/m", "$1.2B") — consumers read numbers with reportlib.first_number.
KEY_METRICS = {
    'Trailing P/E': 'pe_trailing', 'Forward P/E': 'pe_forward', 'PEG Ratio': 'peg',
    'EPS (TTM)': 'eps_ttm', 'Dividend Yield': 'yield_pct', 'Beta': 'beta',
    'Shares Outstanding': 'shares_out', 'Free Cash Flow': 'fcf',
}
MIN_METRICS = 5


def blob_sha(path: str) -> tuple[str, int]:
    """Git's blob id for the file (what `git hash-object` prints) and its size. SHA-1 here is git's object
    naming, not a security control."""
    with open(path, 'rb') as fh:
        b = fh.read()
    return hashlib.sha1(b'blob %d\0' % len(b) + b, usedforsecurity=False).hexdigest(), len(b)


def extract_metrics(t: str) -> dict[str, rl.Metric]:
    """The metrics table as a label -> {text, number} map.

    Deliberately generic: REIT reports carry P/FFO where others carry P/E, banks carry NIM and CET1.
    Capturing the table as-is keeps those without the manifest needing to know every sector's
    substitutions in advance. The first row with a label wins; labels over 60 characters are prose, not metrics.
    """
    metrics: dict[str, rl.Metric] = {}
    for label, value in rl.table_rows(t):
        if label and value and len(label) <= 60 and label not in metrics:
            metrics[label] = {'text': value, 'number': rl.to_number(value)}
    return metrics


# ---------- one field group at a time; each returns its values and adds to warn ----------

def title_fields(t: str, warn: list[str]) -> tuple[str | None, str | None]:
    ticker, name = rl.parse_title(t)
    if not ticker:
        warn.append('title_unparsed')
    badge = re.search(r'<span class="ticker-badge">([^<]+)</span>', t)
    badge_ticker = badge.group(1).strip().split(':')[-1].strip() if badge else None
    if badge_ticker and ticker and badge_ticker != ticker:
        warn.append(f'ticker_badge_mismatch:{badge_ticker}')
    return ticker or badge_ticker, name


def meta_field(t: str, label: str) -> str | None:
    """The value after '<label>:' in the header meta line. Variant A: <span>LABEL:</span> VALUE</span>;
    variant B: <span>LABEL:</span> VALUE &nbsp;.&nbsp; <span>NEXT:</span>."""
    m = re.search(label + r':</span>\s*(.*?)(?:</span>|&nbsp;|<span)', t, re.S)
    if not m:
        return None
    return rl.strip_tags(m.group(1)).strip(' ··-') or None


def industry_fields(t: str, warn: list[str]) -> tuple[str | None, str | None]:
    """(sector, industry) from the meta line: variant A carries 'Sector / Industry', variant B the industry alone."""
    v = meta_field(t, 'Industry')
    if not v:
        warn.append('industry_missing')
        return None, None
    parts = [p.strip() for p in v.split('/', 1)]
    return (parts[0], parts[1]) if len(parts) > 1 else (None, parts[0])


def change_pct(t: str) -> float | None:
    ch = (re.search(r'class="price-change"[^>]*>\s*([^<]+)', t)
          or re.search(r'class="chg[ "][^>]*>\s*([^<]+)', t))
    if not ch:
        return None
    cm = re.search(r'([+\-−]?\s*\$?[\d,]+\.\d+)\s*\(([+\-−]?\s*[\d.]+)%\)', rl.strip_tags(ch.group(1)))
    return rl.to_number(cm.group(2).replace(' ', '')) if cm else None


def as_of_date(t: str, warn: list[str]) -> str | None:
    """The report's as-of date, YYYY-MM-DD, from its first "as of" statement; a range ('August 19–20, 2026')
    gives its first day and a warning."""
    as_of, was_range = rl.as_of(t)
    if was_range:
        warn.append('as_of_was_a_date_range')
    if not as_of:
        warn.append('as_of_missing')
    return as_of


def chart_fields(t: str, price: float | None, warn: list[str]) -> tuple[int | None, bool]:
    """(points, chart_ok) for the main price chart."""
    labels, prices = rl.chart_series(t)
    if labels is None or prices is None:
        warn.append('chart_arrays_missing')
        return None, False
    ends_at_price = bool(price is not None and prices
                         and abs(prices[-1] - price) <= max(rl.PRICE_ROUNDED_ABS, price * rl.PRICE_ROUNDED_REL))
    if len(labels) != len(prices):
        warn.append('chart_array_length_mismatch')
    if not ends_at_price and price:
        warn.append(f'chart_end_price_mismatch:{prices[-1] if prices else None}_vs_{price}')
    return len(prices), ends_at_price and len(prices) == len(labels)


def editions(t: str, as_of: str | None, price: float | None, warn: list[str]) -> tuple[list[list], str | None]:
    """([as_of, price, note] per published edition, newest last; the delta box's state or None). The prior
    edition is read back out of the report's own "what changed" box, so the box and the manifest cannot
    disagree — there is no separate state file."""
    box = re.search(r'<section class="tg-d tg-d--(?P<state>price|print|fix)"'
                    r'[^>]*data-prior-as-of="(?P<pd>[\d-]+)"'
                    r'[^>]*data-prior-price="(?P<pp>[\d.]+)"', t)
    if not box:
        return [[as_of, price, 'initial publication']], None
    if as_of and box.group('pd') >= as_of:
        warn.append('delta_box_prior_edition_not_earlier')
    return ([[box.group('pd'), rl.to_number(box.group('pp')), 'previous edition'], [as_of, price, 'refreshed']],
            box.group('state'))


def structure_ok(t: str, path: str, warn: list[str]) -> bool:
    """reportlib's structure problems go into warn; a legacy site nav is recorded but does not make the page unsound."""
    problems = rl.structure_problems(rl.structure_counts(t), path)
    warn.extend(problems)
    return not any(p != 'has_legacy_sitenav' for p in problems)


def card_fields(card: rl.IndexCard | None) -> dict[str, str | bool | None]:
    """The record fields the index card supplies (the card's industry label is canonical); None, and ndx False,
    for a report with no card."""
    if card is None:
        return {'sector_key': None, 'industry': None, 'sp500_added': None, 'ndx': False, 'dow30_added': None,
                'global_exchange': None}
    ix = card['indices']
    return {'sector_key': card['card_sector_key'], 'industry': card['card_industry'], 'sp500_added': ix['sp500_added'],
            'ndx': bool(ix['nasdaq100']), 'dow30_added': ix['dow30_added'], 'global_exchange': ix['global_exchange']}


def card_checks(card: rl.IndexCard | None, ticker: str | None, warn: list[str]) -> None:
    if card is None:
        warn.append('not_carded_on_index')
    elif ticker and card['ticker'] != ticker:
        warn.append(f"card_ticker_mismatch:{card['ticker']}")


def key_metrics(metrics: dict[str, rl.Metric]) -> dict[str, float | str]:
    """The KEY_METRICS the page has: the number when the cell is one, else its text."""
    out: dict[str, float | str] = {}
    for label, key in KEY_METRICS.items():
        if label in metrics:
            number = metrics[label]['number']
            out[key] = number if number is not None else metrics[label]['text']
    return out


def extract(path: str, cards: dict[str, rl.IndexCard], full_metrics: bool = False) -> rl.ReportRecord:
    """One report page -> its manifest record."""
    t = rl.read_text(path)
    slug = os.path.basename(path).replace('_analysis.html', '')
    warn: list[str] = []
    ticker, name = title_fields(t, warn)
    _sector, industry = industry_fields(t, warn)   # the card's industry label is canonical; the page's is kept raw
    price = rl.header_price(t)
    if price is None:
        warn.append('price_missing')
    as_of = as_of_date(t, warn)
    points, chart_ok = chart_fields(t, price, warn)
    w52 = rl.range_52w(t)
    if w52 and price is not None and not (w52[0] <= price <= w52[1]):
        warn.append('price_outside_52w_range')
    metrics = extract_metrics(t)
    if len(metrics) < MIN_METRICS:
        warn.append(f'few_metrics:{len(metrics)}')
    eds, delta_state = editions(t, as_of, price, warn)
    struct_ok = structure_ok(t, path, warn)
    sha, size = blob_sha(path)
    card = cards.get(slug)
    card_checks(card, ticker, warn)
    cf = card_fields(card)

    rec: dict[str, object] = {
        'ticker': ticker, 'slug': slug, 'name': name,
        'sector_key': cf['sector_key'], 'industry': cf['industry'], 'industry_raw': industry,
        'exchange': meta_field(t, 'Exchange'),
        'sp500_added': cf['sp500_added'], 'ndx': cf['ndx'],
        'dow30_added': cf['dow30_added'], 'global_exchange': cf['global_exchange'],
        'as_of': as_of, 'price': price, 'change_pct': change_pct(t), 'market_cap': meta_field(t, r'Mkt Cap'),
        'w52': w52, 'chart_points': points, 'chart_ok': chart_ok,
        'metrics_count': len(metrics), 'bytes': size, 'blob_sha': sha, 'structure_ok': struct_ok,
        'editions': eds, 'delta_state': delta_state, 'warnings': warn or None,
    }
    rec.update(key_metrics(metrics))
    if full_metrics:
        rec['metrics'] = metrics
    # drop nulls: a missing key means "not extracted", which the warnings explain; the keys are ReportRecord's
    return cast(rl.ReportRecord, {k: v for k, v in rec.items() if v is not None and v != []})


# ---------- the files ----------

def write_json(path: str, obj: Mapping[str, object]) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write('\n')
    return os.path.getsize(path)


def reconciliation(reports: list[rl.ReportRecord], cards: dict[str, rl.IndexCard]) -> dict[str, object]:
    carded, filed = set(cards), {r['slug'] for r in reports}
    return {
        'report_files': len(filed),
        'index_cards': len(carded),
        'uncarded': sorted(filed - carded),
        'orphan_cards': sorted(carded - filed),
        'structure_failures': sorted(r['slug'] for r in reports if not r.get('structure_ok')),
        'chart_failures': sorted(r['slug'] for r in reports if not r.get('chart_ok')),
        'reports_with_warnings': {r['slug']: r['warnings'] for r in reports if r.get('warnings')},
    }


def print_coverage(reports: list[rl.ReportRecord], full_metrics: bool) -> None:
    fields = ['ticker', 'name', 'exchange', 'sector_key', 'industry', 'industry_raw', 'as_of', 'price',
              'change_pct', 'market_cap', 'w52', 'chart_points', 'eps_ttm', 'pe_forward', 'yield_pct']
    for f in fields:
        c = sum(1 for r in reports if r.get(f) not in (None, [], {}))
        print(f'  {f:22s} {c:3d}/{len(reports)}' + ('' if c == len(reports) else '   <-- gaps'), file=sys.stderr)
    counts = sorted(r['metrics_count'] for r in reports)
    print(f'  metrics rows           {sum(counts):,} total, median {counts[len(counts) // 2]}'
          + ('' if full_metrics else '  (full table omitted; --full-metrics to include)'), file=sys.stderr)
    warned = [r for r in reports if r.get('warnings')]
    print(f'  reports with warnings  {len(warned)}', file=sys.stderr)
    for w, c in Counter(w.split(':')[0] for r in warned for w in r['warnings']).most_common():
        print(f'     {w:34s} {c}', file=sys.stderr)


def by_sector(reports: list[rl.ReportRecord]) -> dict[str, list[rl.ReportRecord]]:
    """Records grouped by sector key, reports without one under 'unclassified'.

    Sharded by sector. A single 208 KB file cannot be published through the GitHub connector (one
    push_files call must carry the whole file, ~113k tokens of minified JSON), and sharding is the better
    shape anyway: a consumer that wants one sector fetches ~18 KB, not the lot."""
    groups: dict[str, list[rl.ReportRecord]] = {}
    for r in reports:
        groups.setdefault(r.get('sector_key') or 'unclassified', []).append(r)
    return groups


def manifest_doc(reports: list[rl.ReportRecord], cards: dict[str, rl.IndexCard],
                 sectors: dict[str, list[rl.ReportRecord]]) -> rl.Manifest:
    """The top-level file: answers "what is stale?" and "does the site reconcile?" in one fetch."""
    return {
        'schema_version': SCHEMA_VERSION,
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': f'extracted from the published report HTML; generated by {GENERATOR}, never hand-edited',
        'count': len(reports),
        'reconciliation': reconciliation(reports, cards),
        'index_fields': ['ticker', 'slug', 'sector_key', 'as_of', 'price'],
        'index': [[r.get('ticker'), r['slug'], r.get('sector_key'), r.get('as_of'), r.get('price')] for r in reports],
        'shards': {k: f'data/reports/{k}.json' for k in sorted(sectors)},
        'shard_counts': {k: len(v) for k, v in sorted(sectors.items())},
    }


def write_shards(shard_dir: str, sectors: dict[str, list[rl.ReportRecord]], repo: str) -> None:
    """One file per sector, then remove any shard this build did not write: it belongs to an older build
    and, left in place, duplicates records."""
    for key, rs in sorted(sectors.items()):
        # deliberately no generated_at: a shard should change only when its content changes
        sn = write_json(os.path.join(shard_dir, key + '.json'),
                        {'schema_version': SCHEMA_VERSION, 'sector_key': key, 'count': len(rs), 'reports': rs})
        print(f'  data/reports/{key}.json  {len(rs):3d} reports  {sn:7,} bytes', file=sys.stderr)
    for stale in sorted(set(glob.glob(os.path.join(shard_dir, '*.json'))) -
                        {os.path.join(shard_dir, k + '.json') for k in sectors}):
        os.remove(stale)
        print(f'  removed stale shard {os.path.relpath(stale, repo)}', file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Build the report manifest from the published report pages.')
    ap.add_argument('repo', nargs='?', default=rl.ROOT, help='repo root (default: the repo this script is in)')
    ap.add_argument('-o', dest='out', help='top-level output file (default: <repo>/data/reports.json)')
    ap.add_argument('--full-metrics', action='store_true', help='include every report\'s full metrics table')
    args = ap.parse_args(argv)
    out_path = args.out or os.path.join(args.repo, 'data', 'reports.json')

    cards = rl.parse_index_cards(args.repo)
    files = sorted(glob.glob(os.path.join(args.repo, rl.STOCK_REPORTS)))
    reports = [extract(f, cards, args.full_metrics) for f in files]
    reports.sort(key=lambda r: r.get('ticker') or r['slug'])
    sectors = by_sector(reports)

    n = write_json(out_path, manifest_doc(reports, cards, sectors))
    print(f'wrote {out_path}  ({len(reports)} reports indexed, {n:,} bytes)', file=sys.stderr)
    write_shards(os.path.join(os.path.dirname(out_path), 'reports'), sectors, args.repo)
    print_coverage(reports, args.full_metrics)
    return 0


if __name__ == '__main__':
    sys.exit(main())
