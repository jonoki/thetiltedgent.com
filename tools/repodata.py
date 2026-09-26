"""Where the report library's files are: the repo root, report paths, the index page's cards and the manifest's
data files, with the record types they hold. Imported by the scripts in tools/; not run on its own.
How a report page itself is read is tools/reportlib.py."""
import glob
import html as htmllib
import json
import os
import re
from typing import TypedDict

import reportlib as rl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repo root, from this file's place in tools/

ASSET_FAMILIES = ('etf', 'crypto', 'fixed')   # reports/<family>/: ETFs, crypto, bonds and cash
STOCK_REPORTS = os.path.join('reports', '*_analysis.html')
ASSET_REPORTS = [os.path.join('reports', fam, '*_analysis.html') for fam in ASSET_FAMILIES]


def report_path(slug: str, family: str | None = None, repo: str = ROOT) -> str:
    """reports/<slug>_analysis.html, or reports/<family>/<slug>_analysis.html for an ETF, crypto or bond report."""
    return os.path.join(repo, 'reports', *([family] if family else []), f'{slug}_analysis.html')


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
    w52: list[float]                # [low, high]
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
    fin_table: dict[str, str]       # FIN_TABLE_ROWS cells of the .fin-table, as text (style_tags' inputs)
    metrics: dict[str, rl.Metric]    # only with --full-metrics


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


def parse_index_cards(repo: str = ROOT) -> dict[str, IndexCard]:
    """Per report slug on reports/index.html: ticker, name, industry, sector group and index membership."""
    t = rl.read_text(os.path.join(repo, 'reports', 'index.html'))   # FileNotFoundError, like the other loaders
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
    out: dict[str, IndexCard] = {}
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
