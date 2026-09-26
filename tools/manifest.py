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
METRIC_ROW = re.compile(r'<tr>\s*<t[dh][^>]*>(?P<label>.*?)</t[dh]>\s*<td[^>]*>(?P<value>.*?)</td>', re.S)
MIN_METRICS = 5


def blob_sha(path):
    """Git's blob id for the file (what `git hash-object` prints) and its size. SHA-1 here is git's object
    naming, not a security control."""
    with open(path, 'rb') as fh:
        b = fh.read()
    return hashlib.sha1(b'blob %d\0' % len(b) + b, usedforsecurity=False).hexdigest(), len(b)


def extract_metrics(t):
    """The metrics table as a label -> {text, number} map.

    Deliberately generic: REIT reports carry P/FFO where others carry P/E, banks carry NIM and CET1.
    Capturing the table as-is keeps those without the manifest needing to know every sector's
    substitutions in advance. Only <tbody> rows are read, so the header row's cells cannot bleed into
    the first label ("MetricTICKERIndustry Avg...Trailing P/E").
    """
    metrics = {}
    for body in re.findall(r'<tbody[^>]*>(.*?)</tbody>', t, re.S) or [t]:
        for m in METRIC_ROW.finditer(body):
            label, value = rl.strip_tags(m.group('label')), rl.strip_tags(m.group('value'))
            if not label or not value or '\n' in label or len(label) > 60 or label in metrics:
                continue
            metrics[label] = {'text': value, 'number': rl.to_number(value)}
    return metrics


# ---------- one field group at a time; each returns its values and adds to warn ----------

def title_fields(t, warn):
    ticker, name = rl.parse_title(t)
    if not ticker:
        warn.append('title_unparsed')
    badge = re.search(r'<span class="ticker-badge">([^<]+)</span>', t)
    badge_ticker = badge.group(1).strip().split(':')[-1].strip() if badge else None
    if badge_ticker and ticker and badge_ticker != ticker:
        warn.append(f'ticker_badge_mismatch:{badge_ticker}')
    return ticker or badge_ticker, name


def meta_field(t, label):
    """The value after '<label>:' in the header meta line. Variant A: <span>LABEL:</span> VALUE</span>;
    variant B: <span>LABEL:</span> VALUE &nbsp;.&nbsp; <span>NEXT:</span>."""
    m = re.search(label + r':</span>\s*(.*?)(?:</span>|&nbsp;|<span)', t, re.S)
    if not m:
        return None
    return rl.strip_tags(m.group(1)).strip(' ··-') or None


def industry_fields(t, warn):
    """(sector, industry) from the meta line: variant A carries 'Sector / Industry', variant B the industry alone."""
    v = meta_field(t, 'Industry')
    if not v:
        warn.append('industry_missing')
        return None, None
    parts = [p.strip() for p in v.split('/', 1)]
    return (parts[0], parts[1]) if len(parts) > 1 else (None, parts[0])


def change_pct(t):
    ch = (re.search(r'class="price-change"[^>]*>\s*([^<]+)', t)
          or re.search(r'class="chg[ "][^>]*>\s*([^<]+)', t))
    if not ch:
        return None
    cm = re.search(r'([+\-−]?\s*\$?[\d,]+\.\d+)\s*\(([+\-−]?\s*[\d.]+)%\)', rl.strip_tags(ch.group(1)))
    return rl.to_number(cm.group(2).replace(' ', '')) if cm else None


def as_of_date(t, warn):
    day = r'(?:the\s+)?(?:[A-Za-z]+day,?\s+)?'
    dm = (re.search(r'Static data as of ' + day + r'([A-Za-z]+ \d+, \d{4})', t)
          or re.search(r'Data as of ' + day + r'([A-Za-z]+ \d+, \d{4})', t)
          or re.search(r'as of ' + day + r'([A-Za-z]+ \d+, \d{4})\s*(?:close|market close|\(market close\))', t)
          or re.search(r'Static data as of ([A-Za-z]+ \d+)[–\-—]\d+, (\d{4})', t))
    if dm and dm.lastindex and dm.lastindex > 1:      # 'August 19-20, 2026': the later day's year, first day
        text = f'{dm.group(1)}, {dm.group(2)}'
        warn.append('as_of_was_a_date_range')
    else:
        text = dm.group(1) if dm else None
    as_of = rl.iso_date(text)
    if not as_of:
        warn.append('as_of_missing')
    return as_of


def chart_fields(t, price, warn):
    """(points, chart_ok) for the main price chart."""
    labels, prices = rl.chart_series(t)
    if labels is None:
        warn.append('chart_arrays_missing')
        return None, False
    ends_at_price = bool(price is not None and prices
                         and abs(prices[-1] - price) <= max(rl.PRICE_ROUNDED_ABS, price * rl.PRICE_ROUNDED_REL))
    if len(labels) != len(prices):
        warn.append('chart_array_length_mismatch')
    if not ends_at_price and price:
        warn.append(f'chart_end_price_mismatch:{prices[-1] if prices else None}_vs_{price}')
    return len(prices), ends_at_price and len(prices) == len(labels)


def editions(t, as_of, price, warn):
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


def structure_ok(t, warn):
    s = rl.structure_counts(t)
    if not all(s[k] == 1 for k in rl.SKELETON):
        warn.append('document_skeleton_incomplete')
    if s['canvas'] != 2:
        warn.append(f"canvas_count:{s['canvas']}")
    if s['sitenav']:
        warn.append('has_legacy_sitenav')
    return not any(w.startswith(('document_skeleton', 'canvas_count')) for w in warn)


def extract(path, cards, full_metrics=False):
    """One report page -> its manifest record."""
    t = rl.read_text(path)
    slug = os.path.basename(path).replace('_analysis.html', '')
    warn = []
    ticker, name = title_fields(t, warn)
    sector, industry = industry_fields(t, warn)
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
    struct_ok = structure_ok(t, warn)
    sha, size = blob_sha(path)
    card = cards.get(slug, {})
    if not card:
        warn.append('not_carded_on_index')
    elif ticker and card.get('ticker') != ticker:
        warn.append(f"card_ticker_mismatch:{card.get('ticker')}")
    ix = card.get('indices', {})

    rec = {
        'ticker': ticker, 'slug': slug, 'name': name,
        'sector_key': card.get('card_sector_key'), 'industry': card.get('card_industry'), 'industry_raw': industry,
        'exchange': meta_field(t, 'Exchange'),
        'sp500_added': ix.get('sp500_added'), 'ndx': bool(ix.get('nasdaq100')),
        'dow30_added': ix.get('dow30_added'), 'global_exchange': ix.get('global_exchange'),
        'as_of': as_of, 'price': price, 'change_pct': change_pct(t), 'market_cap': meta_field(t, r'Mkt Cap'),
        'w52': w52, 'chart_points': points, 'chart_ok': chart_ok,
        'metrics_count': len(metrics), 'bytes': size, 'blob_sha': sha, 'structure_ok': struct_ok,
        'editions': eds, 'delta_state': delta_state, 'warnings': warn or None,
    }
    for label, key in KEY_METRICS.items():
        if label in metrics:
            v = metrics[label]
            rec[key] = v['number'] if v['number'] is not None else v['text']
    if full_metrics:
        rec['metrics'] = metrics
    # drop nulls: a missing key means "not extracted", which the warnings explain
    return {k: v for k, v in rec.items() if v is not None and v != []}


# ---------- the files ----------

def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(obj, fh, ensure_ascii=False, sort_keys=False, separators=(',', ':'), indent=None)
        fh.write('\n')
    return os.path.getsize(path)


def reconciliation(reports, cards):
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


def print_coverage(reports, full_metrics):
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


def main(argv=None):
    ap = argparse.ArgumentParser(description='Build the report manifest from the published report pages.')
    ap.add_argument('repo', nargs='?', default='.', help='repo root (default: current directory)')
    ap.add_argument('-o', dest='out', help='top-level output file (default: <repo>/data/reports.json)')
    ap.add_argument('--full-metrics', action='store_true', help='include every report\'s full metrics table')
    args = ap.parse_args(argv)
    repo = args.repo
    out_path = args.out or os.path.join(repo, 'data', 'reports.json')

    cards = rl.parse_index_cards(repo)
    files = sorted(glob.glob(os.path.join(repo, rl.STOCK_REPORTS)))
    reports = [extract(f, cards, args.full_metrics) for f in files]
    reports.sort(key=lambda r: r.get('ticker') or r['slug'])

    # Sharded by sector. A single 208 KB file cannot be published through the GitHub connector (one
    # push_files call must carry the whole file, ~113k tokens of minified JSON), and sharding is the better
    # shape anyway: a consumer that wants one sector fetches ~18 KB, not the lot.
    by_sector = {}
    for r in reports:
        by_sector.setdefault(r.get('sector_key') or 'unclassified', []).append(r)

    # The top-level file answers "what is stale?" and "does the site reconcile?" in one fetch.
    doc = {
        'schema_version': SCHEMA_VERSION,
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': f'extracted from the published report HTML; generated by {GENERATOR}, never hand-edited',
        'count': len(reports),
        'reconciliation': reconciliation(reports, cards),
        'index_fields': ['ticker', 'slug', 'sector_key', 'as_of', 'price'],
        'index': [[r.get('ticker'), r['slug'], r.get('sector_key'), r.get('as_of'), r.get('price')] for r in reports],
        'shards': {k: f'data/reports/{k}.json' for k in sorted(by_sector)},
        'shard_counts': {k: len(v) for k, v in sorted(by_sector.items())},
    }
    n = write_json(out_path, doc)
    print(f'wrote {out_path}  ({len(reports)} reports indexed, {n:,} bytes)', file=sys.stderr)

    shard_dir = os.path.join(os.path.dirname(out_path), 'reports')
    for key, rs in sorted(by_sector.items()):
        # deliberately no generated_at: a shard should change only when its content changes
        sn = write_json(os.path.join(shard_dir, key + '.json'),
                        {'schema_version': SCHEMA_VERSION, 'sector_key': key, 'count': len(rs), 'reports': rs})
        print(f'  data/reports/{key}.json  {len(rs):3d} reports  {sn:7,} bytes', file=sys.stderr)
    # a shard this build did not write belongs to an older build; left in place it duplicates records
    for stale in sorted(set(glob.glob(os.path.join(shard_dir, '*.json'))) -
                        {os.path.join(shard_dir, k + '.json') for k in by_sector}):
        os.remove(stale)
        print(f'  removed stale shard {os.path.relpath(stale, repo)}', file=sys.stderr)

    print_coverage(reports, args.full_metrics)


if __name__ == '__main__':
    main()
