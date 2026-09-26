"""Shared knowledge of the report library: where the repo is, how a published report page is read, and
how the manifest's data files are loaded. Imported by the scripts in tools/; not run on its own.

Everything that reads a report page reads it through here, so a change to the report markup (a new
title format, a renamed price class) is made once rather than in four scripts that drift apart.
"""
import glob
import html as htmllib
import json
import os
import re
from typing import TypedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repo root, from this file's place in tools/

ASSET_FAMILIES = ('etf', 'crypto', 'fixed')   # reports/<family>/: ETFs, crypto, bonds and cash
STOCK_REPORTS = os.path.join('reports', '*_analysis.html')
ASSET_REPORTS = [os.path.join('reports', fam, '*_analysis.html') for fam in ASSET_FAMILIES]

# The header price must equal the chart's last point, to the cent: the rule every build and refresh is held to.
PRICE_EXACT = 0.006
# A looser reconciliation for the manifest: chart series are often rounded (1 dp, or whole dollars on a
# four-figure price), so a stored series is only flagged when it misses by more than 5 cents and 0.1%.
PRICE_ROUNDED_ABS, PRICE_ROUNDED_REL = 0.05, 0.001

_FULL_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December']
MONTHS = {m: i + 1 for i, m in enumerate(_FULL_MONTHS)}
MONTHS.update({m[:3]: i + 1 for i, m in enumerate(_FULL_MONTHS)})   # 'Aug 12, 2026'
MONTHS['Sept'] = 9

_DASHES = str.maketrans({'\u2212': '-', '\u2013': '-', '\u2014': '-'})   # minus sign, en dash, em dash


# ---------- files, text and numbers ----------

def report_path(slug: str, family: str | None = None, repo: str = ROOT) -> str:
    """reports/<slug>_analysis.html, or reports/<family>/<slug>_analysis.html for an ETF, crypto or bond report."""
    return os.path.join(repo, 'reports', *([family] if family else []), f'{slug}_analysis.html')


def read_text(path: str) -> str:
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def normalize_dashes(s: str) -> str:
    """Minus sign, en dash and em dash -> '-', so a number typed with any of them reads as negative."""
    return s.translate(_DASHES)


def strip_tags(s: str) -> str:
    """Markup removed and entities decoded: the text a reader sees in a cell or span."""
    return htmllib.unescape(re.sub(r'<[^>]+>', '', s)).strip()


def to_number(s: str | None) -> float | None:
    """A whole string read as one number: '1,234.5', '$12.30', '4.1%', '−3.2' -> float; anything else -> None."""
    if s is None:
        return None
    s = normalize_dashes(s.replace(',', '').replace('$', '').replace('%', '').strip())
    try:
        return float(s)
    except ValueError:
        return None


def first_number(s: str | int | float | None) -> float | None:
    """The first number in a text cell: '12.4x (vs 18x)' -> 12.4. None for n/m, n/a or no number.
    Brackets or a leading minus make it negative: '($1.2B)' -> -1.2. Numbers pass through as floats."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = normalize_dashes(s)
    if re.search(r'\bn/?m\b|\bn/?a\b|not meaningful', s, re.I):
        return None
    m = re.search(r'(\(?)(-?)\$?\s*(\d[\d,]*\.?\d*)', s)
    if not m:
        return None
    v = float(m.group(3).replace(',', ''))
    return -v if (m.group(1) or m.group(2)) else v


def iso_date(text: str | None) -> str | None:
    """'September 10, 2026' -> '2026-09-10'; None when it is not a date in that form."""
    if not text:
        return None
    m = re.match(r'([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})', text.strip())
    if not m or m.group(1) not in MONTHS:
        return None
    return f'{int(m.group(3)):04d}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}'


# ---------- what a report page says ----------

def parse_title(t: str) -> tuple[str | None, str | None]:
    """(ticker, name) from the <title>: 'AAPL — Apple Inc. | Stock Analysis' or 'Apple Inc. (AAPL) — …'.
    Either part is None when the title is in neither form."""
    m = re.search(r'<title>\s*([A-Z][A-Z0-9.\-]*)\s*[\u2014\u2013\-]\s*(.*?)\s*(?:\|[^<]*)?</title>', t, re.S)
    if m:
        return m.group(1), htmllib.unescape(m.group(2))
    m = re.search(r'<title>\s*(.*?)\s*\(([A-Z][A-Z0-9.\-]*)\)\s*[\u2014\u2013\-]\s*.*?</title>', t, re.S)
    if m:
        return m.group(2), htmllib.unescape(m.group(1))
    return None, None


def header_price(t: str) -> float | None:
    """The price in the report header ($ and commas removed), or None."""
    m = (re.search(r'class="price-current"[^>]*>\s*\$?([\d,]+\.\d+)', t)
         or re.search(r'class="price[ "][^>]*>\s*\$?([\d,]+\.\d+)', t)
         or re.search(r'class="price-now[ "][^>]*>\s*\$?([\d,]+\.\d+)', t))
    return to_number(m.group(1)) if m else None


_ROW = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
_CELL = re.compile(r'<(t[dh])[^>]*>(.*?)</t[dh]>', re.S)


def table_rows(t: str) -> list[tuple[str, str]]:
    """(label, value) text of every table row in t whose second cell is a <td>, in page order. The label is
    the first cell (<td> or <th>); header rows (all <th>) are skipped. Cells are read with tags stripped,
    because metrics labels are often split into tooltip spans ("<span>EPS</span> (<span>TTM</span>)"), and
    whitespace is collapsed. The one reader of report tables: manifest.py, verify.py and style_tags.py use it."""
    rows = []
    for row in _ROW.findall(t):
        cells = _CELL.findall(row)
        if len(cells) >= 2 and cells[1][0] == 'td':
            rows.append(tuple(re.sub(r'\s+', ' ', strip_tags(body)) for _, body in cells[:2]))
    return rows


def row_value(rows: list[tuple[str, str]], label: str, flags: int = 0) -> str | None:
    """The value of the first row whose label matches the regex label (re.match), else None."""
    return next((value for lab, value in rows if re.match(label, lab, flags)), None)


def _js_arrays(t: str, name: str) -> list[str]:
    """The body of every `const|let|var <name> = [...]` in the page's scripts."""
    return [m.group(1) for m in re.finditer(r'(?:const|let|var)\s+' + name + r'\s*=\s*\[(.*?)\]\s*;', t, re.S)]


def _labels(body: str) -> list[str]:
    """Quoted strings in an array body, unescaped; allows 'Sep \\'21', "Oct '21" and `Nov 21`."""
    out = []
    for dq, sq, bq in re.findall(r'"((?:\\.|[^"\\])*)"|\'((?:\\.|[^\'\\])*)\'|`([^`]*)`', body):
        out.append((dq or sq or bq).replace("\\'", "'").replace('\\"', '"'))
    return out


def _numbers(body: str) -> list[float]:
    """Numbers in an array body, split on commas (a character class containing ',' would swallow a
    whole array written without spaces as one token). Entries that are not numbers are dropped."""
    vals = (to_number(part.strip()) for part in body.split(',') if part.strip())
    return [v for v in vals if v is not None]


def chart_series(t: str) -> tuple[list[str], list[float]] | tuple[None, None]:
    """(labels, prices) of the main price chart, or (None, None) when the page defines no arrays.
    A page may define more than one series; the main one is the first labels/prices pair of equal length,
    else the first of each."""
    label_arrays = [_labels(b) for b in _js_arrays(t, 'labels')]
    price_arrays = [_numbers(b) for b in _js_arrays(t, 'prices')]
    if not label_arrays or not price_arrays:
        return None, None
    return next(((la, pa) for la in label_arrays for pa in price_arrays if len(la) == len(pa)),
                (label_arrays[0], price_arrays[0]))


_DASH = r'(?:&ndash;|&mdash;|&#8211;|&#x2013;|[\u2013\-\u2014])'


def range_52w(t: str) -> list[float | None] | None:
    """[low, high] from the metrics-table 52-week row (else the first '52-week range $x – $y' in the page)."""
    m = (re.search(r'52-Week Range[^<]*</t[dh]>\s*<td[^>]*>\s*\$?([\d,]+\.\d+)\s*' + _DASH + r'\s*\$?([\d,]+\.\d+)', t, re.S)
         or re.search(r'52[- ]Week Range.{0,120}?\$([\d,]+\.\d+)\s*' + _DASH + r'\s*\$([\d,]+\.\d+)', t, re.S))
    return [to_number(m.group(1)), to_number(m.group(2))] if m else None


class StructureCounts(TypedDict):
    """How many of each skeleton element a page has (structure_counts)."""
    doctype: int
    html: int
    head: int
    head_close: int
    body: int
    body_close: int
    html_close: int
    style_open: int
    style_close: int
    canvas: int
    lines: int
    sitenav: int


def structure_counts(t: str) -> StructureCounts:
    """How many of each skeleton element the page has; a sound page has exactly one of each tag pair."""
    return {
        'doctype': t.count('<!DOCTYPE'),
        'html': len(re.findall(r'<html[\s>]', t)),
        'head': len(re.findall(r'<head[\s>]', t)),
        'head_close': t.count('</head>'),
        'body': len(re.findall(r'<body[\s>]', t)),
        'body_close': t.count('</body>'),
        'html_close': t.count('</html>'),
        'style_open': len(re.findall(r'<style[\s>]', t)),
        'style_close': t.count('</style>'),
        'canvas': t.count('<canvas'),
        'lines': t.count('\n'),
        'sitenav': t.count('tg-sitenav'),
    }


SKELETON = ('doctype', 'html', 'head', 'head_close', 'body', 'body_close', 'html_close')


def expected_canvases(path: str) -> int:
    """The price chart and one other; bond and cash reports (reports/fixed/) add the yield curve."""
    return 3 if os.path.basename(os.path.dirname(os.path.abspath(path))) == 'fixed' else 2


def structure_problems(counts: StructureCounts, path: str) -> list[str]:
    """What is wrong with a page's skeleton, as manifest warning codes; empty for a sound page. The one
    definition of a sound report: verify.py gates on it and manifest.py records it. A missing </head> (EXPD)
    or </style> (CAT, blank for five weeks) is caught here."""
    problems = []
    if not all(counts[k] == 1 for k in SKELETON):
        problems.append('document_skeleton_incomplete')
    if counts['style_open'] != counts['style_close']:
        problems.append('style_unbalanced')
    if counts['canvas'] != expected_canvases(path):
        problems.append(f"canvas_count:{counts['canvas']}")
    if counts['sitenav']:
        problems.append('has_legacy_sitenav')
    return problems


# ---------- the index page and the manifest's data files ----------

class IndexMembership(TypedDict):
    sp500_added: str | None      # 'YYYY-MM-DD' the name joined the S&P 500, when it is a member
    nasdaq100: bool
    dow30_added: str | None
    global_exchange: str | None  # home exchange of a non-US-index name


class ReportRecord(TypedDict, total=False):
    """One report in the manifest (data/reports/<sector>.json). A key is absent when it was not extracted;
    the record's warnings say why. Key metrics are numbers when the page cell is a plain number, else its text."""
    ticker: str
    slug: str
    name: str
    sector_key: str
    industry: str
    industry_raw: str
    exchange: str
    sp500_added: str
    ndx: bool
    dow30_added: str
    global_exchange: str
    as_of: str                      # YYYY-MM-DD
    price: float
    change_pct: float
    market_cap: str
    w52: list[float | None]         # [low, high]
    chart_points: int
    chart_ok: bool
    metrics_count: int
    bytes: int
    blob_sha: str
    structure_ok: bool
    editions: list[list]            # [as_of, price, note] per published edition, newest last
    delta_state: str
    warnings: list[str]
    pe_trailing: float | str
    pe_forward: float | str
    peg: float | str
    eps_ttm: float | str
    yield_pct: float | str
    beta: float | str
    shares_out: float | str
    fcf: float | str
    metrics: dict[str, dict]        # only with --full-metrics


class Manifest(TypedDict):
    """data/reports.json."""
    schema_version: int
    generated_at: str
    source: str
    count: int
    reconciliation: dict[str, object]
    index_fields: list[str]
    index: list[list]               # [ticker, slug, sector_key, as_of, price]
    shards: dict[str, str]          # sector key -> path of its shard
    shard_counts: dict[str, int]


class IndexCard(TypedDict):
    ticker: str
    card_name: str
    card_industry: str
    card_sector_key: str | None  # the sector group the card sits in
    indices: IndexMembership


def parse_index_cards(repo: str = ROOT) -> dict[str, 'IndexCard']:
    """Per report slug on reports/index.html: ticker, name, industry, sector group and index membership."""
    p = os.path.join(repo, 'reports', 'index.html')
    if not os.path.exists(p):
        return {}
    t = read_text(p)
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
    out = {}
    for m in card_re.finditer(t):
        a = m.group('attrs')
        sp = re.search(r'data-sp="([\d-]+)"', a)
        dow = re.search(r'data-dow="([\d-]+)"', a)
        gl = re.search(r'data-gl="([A-Z ]+)"', a)   # global (non-US-index) names carry their home exchange
        out[m.group('slug')] = {
            'ticker': m.group('tick'),
            'card_name': htmllib.unescape(m.group('name')),
            'card_industry': htmllib.unescape(m.group('ind')),
            'card_sector_key': sector_of.get(m.group('slug')),
            'indices': {
                'sp500_added': sp.group(1) if sp else None,
                'nasdaq100': 'data-ndx' in a,
                'dow30_added': dow.group(1) if dow else None,
                'global_exchange': gl.group(1) if gl else None,
            },
        }
    return out


def load_manifest(repo: str = ROOT) -> Manifest:
    """data/reports.json, the manifest's top-level file."""
    with open(os.path.join(repo, 'data', 'reports.json'), encoding='utf-8') as fh:
        return json.load(fh)


def load_report_records(repo: str = ROOT) -> dict[str, ReportRecord]:
    """Every manifest record, slug -> record, from the shards the manifest lists (not every file in the
    folder, so a shard left over from an older build cannot add stale or duplicate records)."""
    recs = {}
    for rel in load_manifest(repo)['shards'].values():
        with open(os.path.join(repo, rel), encoding='utf-8') as fh:
            for r in json.load(fh)['reports']:
                recs[r['slug']] = r
    return recs


def report_paths(repo: str = ROOT, assets: bool = False) -> list[str]:
    """Sorted paths of the stock reports (and the ETF, crypto and bond reports when assets=True)."""
    pats = [STOCK_REPORTS] + (ASSET_REPORTS if assets else [])
    return sorted(p for pat in pats for p in glob.glob(os.path.join(repo, pat)))
