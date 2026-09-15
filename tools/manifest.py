#!/usr/bin/env python3
"""Build data/reports.json — the machine-readable manifest of every live report.

Extracts from the report HTML itself rather than re-researching, so the manifest
can never disagree with what is actually published. Anything that cannot be
parsed is recorded as null with a warning; nothing is guessed.

Usage:  python3 manifest.py <repo-root> [-o data/reports.json]
"""
import re, json, glob, os, sys, hashlib, html as htmllib
from datetime import datetime, timezone

SCHEMA_VERSION = 1

# Metrics a client-side live-price recompute needs: everything price-derived on
# the page can be rebuilt from a live quote plus these static values.
KEY_METRICS = {
    'Trailing P/E': 'pe_trailing', 'Forward P/E': 'pe_forward', 'PEG Ratio': 'peg',
    'EPS (TTM)': 'eps_ttm', 'Dividend Yield': 'yield_pct', 'Beta': 'beta',
    'Shares Outstanding': 'shares_out', 'Free Cash Flow': 'fcf',
}
FULL_METRICS = '--full-metrics' in sys.argv

_FULL = ['January', 'February', 'March', 'April', 'May', 'June',
         'July', 'August', 'September', 'October', 'November', 'December']
MONTHS = {m: i + 1 for i, m in enumerate(_FULL)}
MONTHS.update({m[:3]: i + 1 for i, m in enumerate(_FULL)})   # 'Aug 12, 2026'
MONTHS['Sept'] = 9


def blob_sha(path):
    b = open(path, 'rb').read()
    return hashlib.sha1(b'blob %d\0' % len(b) + b).hexdigest(), len(b)


def num(s):
    if s is None:
        return None
    s = s.replace(',', '').replace('$', '').replace('%', '').strip()
    s = s.replace('−', '-').replace('–', '-').replace('—', '-')
    try:
        return float(s)
    except ValueError:
        return None


def iso_date(text):
    """'September 10, 2026' -> '2026-09-10'."""
    if not text:
        return None
    m = re.match(r'([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})', text.strip())
    if not m or m.group(1) not in MONTHS:
        return None
    return f'{int(m.group(3)):04d}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}'


def strip_tags(s):
    s = re.sub(r'<[^>]+>', '', s)
    return htmllib.unescape(s).strip()


def parse_index_cards(repo):
    """Index membership + the canonical industry label, from reports/index.html."""
    p = os.path.join(repo, 'reports', 'index.html')
    if not os.path.exists(p):
        return {}
    t = open(p, encoding='utf-8').read()
    out = {}
    # which sgroup each card sits in -> the canonical sector
    sector_of = {}
    for g in re.finditer(r'<section class="sgroup" data-s="([a-z]+)">(.*?)</section>', t, re.S):
        for sl in re.findall(r'href="view\.html\?r=([a-z0-9.\-]+)"', g.group(2)):
            sector_of[sl] = g.group(1)
    card_re = re.compile(
        r'<a class="rep"(?P<attrs>[^>]*?)href="view\.html\?r=(?P<slug>[a-z0-9.\-]+)">'
        r'<span class="tick">(?P<tick>[^<]+)</span>'
        r'<h3>(?P<name>.*?)</h3>'
        r'<span class="sect">(?P<ind>[^<]*)</span>'
        r'<span class="ixrow">(?P<ix>.*?)</span></a>')
    for m in card_re.finditer(t):
        a = m.group('attrs')
        sp = re.search(r'data-sp="([\d-]+)"', a)
        dow = re.search(r'data-dow="([\d-]+)"', a)
        out[m.group('slug')] = {
            'ticker': m.group('tick'),
            'card_name': htmllib.unescape(m.group('name')),
            'card_industry': htmllib.unescape(m.group('ind')),
            'card_sector_key': sector_of.get(m.group('slug')),
            'indices': {
                'sp500_added': sp.group(1) if sp else None,
                'nasdaq100': 'data-ndx' in a,
                'dow30_added': dow.group(1) if dow else None,
            },
        }
    return out


METRIC_ROW = re.compile(
    r'<tr>\s*<t[dh][^>]*>(?P<label>.*?)</t[dh]>\s*<td[^>]*>(?P<value>.*?)</td>', re.S)


def extract_metrics(t):
    """The metrics table as a label -> {text, number} map.

    Deliberately generic: REIT reports carry P/FFO where others carry P/E, banks
    carry NIM and CET1. Capturing the table as-is keeps those without the
    manifest needing to know every sector's substitutions in advance.
    """
    metrics = {}
    # scan tbody only — otherwise the <thead> row's cells bleed into the first
    # label ("MetricTICKERIndustry Avg...Trailing P/E")
    bodies = re.findall(r'<tbody[^>]*>(.*?)</tbody>', t, re.S) or [t]
    for body in bodies:
        for m in METRIC_ROW.finditer(body):
            label = strip_tags(m.group('label'))
            value = strip_tags(m.group('value'))
            if not label or not value or '\n' in label or len(label) > 60:
                continue
            if label in metrics:
                continue
            metrics[label] = {'text': value, 'number': num(value)}
    return metrics


def extract(path, repo, cards):
    t = open(path, encoding='utf-8').read()
    slug = os.path.basename(path).replace('_analysis.html', '')
    warn = []

    m = re.search(r'<title>\s*([A-Z.\-]+)\s*[—\-]\s*(.*?)\s*\|\s*(?:Stock Analysis|Comprehensive Analysis)\s*</title>', t)
    ticker = m.group(1) if m else None
    name = htmllib.unescape(m.group(2)) if m else None
    if not m:
        m2 = re.search(r'<title>\s*(.*?)\s*\(([A-Z.\-]+)\)\s*[\u2014\-]\s*.*?</title>', t)
        if m2:
            name, ticker = htmllib.unescape(m2.group(1)), m2.group(2)
        else:
            warn.append('title_unparsed')

    badge = re.search(r'<span class="ticker-badge">([^<]+)</span>', t)
    if badge:
        bt = badge.group(1).strip()
        badge_ticker = bt.split(':')[-1].strip() if ':' in bt else bt
    else:
        badge_ticker = None
    if badge_ticker and ticker and badge_ticker != ticker:
        warn.append(f'ticker_badge_mismatch:{badge_ticker}')
    if not ticker and badge_ticker:
        ticker = badge_ticker

    def meta_field(label):
        # variant A: <span ...>LABEL:</span> VALUE</span>
        # variant B: ... <span ...>LABEL:</span> VALUE &nbsp;.&nbsp; <span ...>NEXT:</span>
        m = re.search(label + r':</span>\s*(.*?)(?:</span>|&nbsp;|<span)', t, re.S)
        if not m:
            return None
        v = htmllib.unescape(strip_tags(m.group(1))).strip(' \u00b7·-')
        return v or None

    ex_v = meta_field('Exchange')
    ind_v = meta_field('Industry')
    cap_v = meta_field(r'Mkt Cap')

    sector = industry = None
    if ind_v:
        # variant A carries 'Sector / Industry'; variant B carries the industry alone
        parts = [p.strip() for p in ind_v.split('/', 1)]
        if len(parts) > 1:
            sector, industry = parts[0], parts[1]
        else:
            industry = parts[0]
    else:
        warn.append('industry_missing')

    pm = (re.search(r'class="price-current"[^>]*>\s*\$?([\d,]+\.\d+)', t)
          or re.search(r'class="price[ "][^>]*>\s*\$?([\d,]+\.\d+)', t)
          or re.search(r'class="price-now[ "][^>]*>\s*\$?([\d,]+\.\d+)', t))
    price = num(pm.group(1)) if pm else None
    if price is None:
        warn.append('price_missing')

    ch = (re.search(r'class="price-change"[^>]*>\s*([^<]+)', t)
          or re.search(r'class="chg[ "][^>]*>\s*([^<]+)', t))
    change_text = strip_tags(ch.group(1)) if ch else None
    change = change_pct = None
    if change_text:
        cm = re.search(r'([+\-−]?\s*\$?[\d,]+\.\d+)\s*\(([+\-−]?\s*[\d.]+)%\)', change_text)
        if cm:
            change = num(cm.group(1).replace(' ', ''))
            change_pct = num(cm.group(2).replace(' ', ''))

    dm = (re.search(r'Static data as of (?:the\s+)?(?:[A-Za-z]+day,?\s+)?([A-Za-z]+ \d+, \d{4})', t)
          or re.search(r'Data as of (?:the\s+)?(?:[A-Za-z]+day,?\s+)?([A-Za-z]+ \d+, \d{4})', t)
          or re.search(r'as of (?:the\s+)?(?:[A-Za-z]+day,?\s+)?([A-Za-z]+ \d+, \d{4})\s*(?:close|market close|\(market close\))', t)
          or re.search(r'Static data as of ([A-Za-z]+ \d+)[\u2013\-\u2014]\d+, (\d{4})', t))
    if dm and dm.lastindex and dm.lastindex > 1:      # 'August 19-20, 2026'
        as_of_text = f'{dm.group(1)}, {dm.group(2)}'
        warn.append('as_of_was_a_date_range')
    else:
        as_of_text = dm.group(1) if dm else None
    as_of = iso_date(as_of_text)
    if not as_of:
        warn.append('as_of_missing')

    def arrays(name, kind):
        """Every `<name> = [...]` in the file, parsed element-wise.

        Split on commas rather than scanning for number-ish runs: a character
        class containing ',' swallows a whole comma-separated array as one
        token when the source has no spaces after the commas.
        """
        out = []
        for m in re.finditer(r'(?:const|let|var)\s+' + name + r'\s*=\s*\[(.*?)\]\s*;', t, re.S):
            body = m.group(1)
            if kind == 'str':
                # allow escaped quotes inside a label, e.g.  'Sep \'21'
                out.append([a or b for a, b in re.findall(
                    r'"((?:\\.|[^"\\])*)"|\'((?:\\.|[^\'\\])*)\'', body)])
            else:
                vals = []
                for part in body.split(','):
                    part = part.strip()
                    if part:
                        vals.append(num(part))
                out.append([v for v in vals if v is not None])
        return out

    label_arrays = arrays('labels', 'str')
    price_arrays = arrays('prices', 'num')
    chart = None
    if label_arrays and price_arrays:
        # a report may define more than one series; take the first labels/prices
        # pair of equal length, which is the main monthly price chart
        pair = next(((la, pa) for la in label_arrays for pa in price_arrays
                     if len(la) == len(pa)), (label_arrays[0], price_arrays[0]))
        labels, prices = pair
        chart = {
            'points': len(prices),
            'labels_count': len(labels),
            'first_label': labels[0] if labels else None,
            'last_label': labels[-1] if labels else None,
            'last_value': prices[-1] if prices else None,
            # chart series are frequently rounded (1dp, or whole dollars on a
            # four-figure price), so compare proportionally rather than exactly
            'matches_header_price': (price is not None and bool(prices)
                                     and abs(prices[-1] - price) <= max(0.05, price * 0.001)),
        }
        if len(labels) != len(prices):
            warn.append('chart_array_length_mismatch')
        if not chart['matches_header_price'] and price:
            warn.append(f'chart_end_price_mismatch:{prices[-1]}_vs_{price}')
    else:
        warn.append('chart_arrays_missing')

    # the separator may be a literal dash or an HTML entity, and the row must be
    # the metrics-table row rather than any later mention in prose
    DASH = r'(?:&ndash;|&mdash;|&#8211;|&#x2013;|[–\-—])'
    rng = (re.search(r'52-Week Range[^<]*</t[dh]>\s*<td[^>]*>\s*\$?([\d,]+\.\d+)\s*' + DASH + r'\s*\$?([\d,]+\.\d+)', t, re.S)
           or re.search(r'52[- ]Week Range.{0,120}?\$([\d,]+\.\d+)\s*' + DASH + r'\s*\$([\d,]+\.\d+)', t, re.S))
    range_52w = [num(rng.group(1)), num(rng.group(2))] if rng else None
    if range_52w and price is not None and not (range_52w[0] <= price <= range_52w[1]):
        warn.append('price_outside_52w_range')

    metrics = extract_metrics(t)
    if len(metrics) < 5:
        warn.append(f'few_metrics:{len(metrics)}')

    struct = {
        'doctype': t.count('<!DOCTYPE'),
        'html': len(re.findall(r'<html[\s>]', t)),
        'head': len(re.findall(r'<head[\s>]', t)),
        'body': len(re.findall(r'<body[\s>]', t)),
        'body_close': t.count('</body>'),
        'html_close': t.count('</html>'),
        'canvas': t.count('<canvas'),
        'lines': t.count('\n'),
        'sitenav': t.count('tg-sitenav'),
    }
    if not all(struct[k] == 1 for k in ('doctype', 'html', 'head', 'body', 'body_close', 'html_close')):
        warn.append('document_skeleton_incomplete')
    if struct['canvas'] != 2:
        warn.append(f"canvas_count:{struct['canvas']}")
    if struct['sitenav']:
        warn.append('has_legacy_sitenav')

    sha, size = blob_sha(path)
    card = cards.get(slug, {})
    if not card:
        warn.append('not_carded_on_index')
    if card and ticker and card.get('ticker') != ticker:
        warn.append(f"card_ticker_mismatch:{card.get('ticker')}")

    km = {}
    for label, key in KEY_METRICS.items():
        if label in metrics:
            v = metrics[label]
            km[key] = v['number'] if v['number'] is not None else v['text']

    rec = {
        'ticker': ticker,
        'slug': slug,
        'name': name,
        'sector_key': card.get('card_sector_key'),
        'industry': card.get('card_industry'),
        'industry_raw': industry,
        'exchange': ex_v,
        'sp500_added': card.get('indices', {}).get('sp500_added'),
        'ndx': bool(card.get('indices', {}).get('nasdaq100')),
        'dow30_added': card.get('indices', {}).get('dow30_added'),
        'as_of': as_of,
        'price': price,
        'change_pct': change_pct,
        'market_cap': cap_v,
        'w52': range_52w,
        'chart_points': chart['points'] if chart else None,
        'chart_ok': bool(chart and chart['matches_header_price']
                         and chart['points'] == chart['labels_count']),
        'metrics_count': len(metrics),
        'bytes': size,
        'blob_sha': sha,
        'structure_ok': not any(w.startswith(('document_skeleton', 'canvas_count')) for w in warn),
        # prior editions, so a "what changed since last time" box has something
        # to diff against without re-reading old HTML: [as_of, price, note]
        'editions': [[as_of, price, 'initial publication']],
        'warnings': warn or None,
    }
    rec.update(km)
    if FULL_METRICS:
        rec['metrics'] = metrics
    # drop nulls: a missing key means "not extracted", which the warnings explain
    return {k: v for k, v in rec.items() if v is not None and v != []}


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else '.'
    out_path = os.path.join(repo, 'data', 'reports.json')
    if '-o' in sys.argv:
        out_path = sys.argv[sys.argv.index('-o') + 1]

    cards = parse_index_cards(repo)
    files = sorted(glob.glob(os.path.join(repo, 'reports', '*_analysis.html')))
    reports = [extract(f, repo, cards) for f in files]
    reports.sort(key=lambda r: (r['ticker'] or r['slug']))

    carded = set(cards)
    filed = {r['slug'] for r in reports}

    if not FULL_METRICS:
        for r in reports:
            r.pop('metrics', None)

    # Sharded by sector. A single 208 KB file cannot be published through the
    # GitHub connector (one push_files call must carry the whole file, and that
    # is ~113k tokens of minified JSON), and sharding is the better shape
    # anyway: a consumer that wants one sector fetches ~18 KB, not the lot.
    by_sector = {}
    for r in reports:
        by_sector.setdefault(r.get('sector_key') or 'unclassified', []).append(r)

    # The top-level file carries everything needed to answer "what is stale?"
    # and "does the site reconcile?" in one fetch, without pulling any shard.
    index = [[r['ticker'], r['slug'], r.get('sector_key'), r['as_of'], r['price']]
             for r in reports]

    doc = {
        'schema_version': SCHEMA_VERSION,
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': 'extracted from the published report HTML; generated by idx/manifest.py, never hand-edited',
        'count': len(reports),
        'reconciliation': {
            'report_files': len(filed),
            'index_cards': len(carded),
            'uncarded': sorted(filed - carded),
            'orphan_cards': sorted(carded - filed),
            'structure_failures': sorted(r['slug'] for r in reports if not r.get('structure_ok')),
            'chart_failures': sorted(r['slug'] for r in reports if not r.get('chart_ok')),
            'reports_with_warnings': {r['slug']: r['warnings'] for r in reports if r.get('warnings')},
        },
        'index_fields': ['ticker', 'slug', 'sector_key', 'as_of', 'price'],
        'index': index,
        'shards': {k: f'data/reports/{k}.json' for k in sorted(by_sector)},
        'shard_counts': {k: len(v) for k, v in sorted(by_sector.items())},
    }

    def write(path, obj):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(obj, fh, ensure_ascii=False, sort_keys=False,
                      separators=(',', ':'), indent=None)
            fh.write('\n')
        return os.path.getsize(path)

    n = write(out_path, doc)
    print(f'wrote {out_path}  ({len(reports)} reports indexed, {n:,} bytes)', file=sys.stderr)
    shard_dir = os.path.join(os.path.dirname(out_path), 'reports')
    for key, rs in sorted(by_sector.items()):
        sn = write(os.path.join(shard_dir, key + '.json'), {
            'schema_version': SCHEMA_VERSION,
            'generated_at': doc['generated_at'],
            'sector_key': key,
            'count': len(rs),
            'reports': rs,
        })
        print(f'  data/reports/{key}.json  {len(rs):3d} reports  {sn:7,} bytes', file=sys.stderr)

    # coverage report
    fields = ['ticker', 'name', 'exchange', 'sector_key', 'industry', 'industry_raw',
              'as_of', 'price', 'change_pct', 'market_cap', 'w52', 'chart_points',
              'eps_ttm', 'pe_forward', 'yield_pct']
    for f in fields:
        c = sum(1 for r in reports if r.get(f) not in (None, [], {}))
        print(f'  {f:22s} {c:3d}/{len(reports)}' + ('' if c == len(reports) else '   <-- gaps'), file=sys.stderr)
    counts = sorted(r['metrics_count'] for r in reports)
    print(f'  metrics rows           {sum(counts):,} total, median {counts[len(counts)//2]}'
          + ('' if FULL_METRICS else '  (full table omitted; --full-metrics to include)'), file=sys.stderr)
    warned = [r for r in reports if r.get('warnings')]
    print(f'  reports with warnings  {len(warned)}', file=sys.stderr)
    from collections import Counter
    for w, c in Counter(w.split(':')[0] for r in warned for w in r.get('warnings') or []).most_common():
        print(f'     {w:34s} {c}', file=sys.stderr)


if __name__ == '__main__':
    main()
