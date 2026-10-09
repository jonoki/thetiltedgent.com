"""Where the report library's files are: the repo root, report paths, the index page's cards and the manifest's
data files, with the record types they hold. Imported by the scripts in tools/; not run on its own.
How a report page itself is read is tools/reportlib.py."""
import argparse
import glob
import html as htmllib
import json
import os
import re
from typing import Literal, NotRequired, TypedDict

import reportlib as rl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repo root, from this file's place in tools/

ASSET_FAMILIES = ('etf', 'crypto', 'fixed')   # reports/<family>/: ETFs, crypto, bonds and cash
STOCK_REPORTS = os.path.join('reports', '*_analysis.html')
ASSET_REPORTS = [os.path.join('reports', fam, '*_analysis.html') for fam in ASSET_FAMILIES]

# Archived stock reports: the company stopped trading, so the page stays at its URL as a final edition (one line on its
# "Static data as of" banner says why) but leaves the library: no card on reports/index.html, not in the manifest, so
# never tagged, queued for a refresh or ranked. verify.py still checks the page. slug -> the banner line.
ARCHIVED: dict[str, str] = {
    'wbd': 'Acquired by Skydance Corporation on Oct 6, 2026; final edition.',   # Skydance 8-K, 6 Oct 2026 (Oki, 8 Oct)
}
# Renamed stock reports, old slug -> new: the old file is a redirect stub (not a report) and reports/view.html maps
# ?r=<old> to the new slug in its `moved` map; tools/tests/test_site.py keeps the two in step.
RENAMED: dict[str, str] = {
    'psky': 'skyd',   # Paramount Skydance (Nasdaq: PSKY) -> Skydance Corporation (NYSE: SKYD), 6 Oct 2026 (Oki, 8 Oct)
}


def parser(description: str) -> argparse.ArgumentParser:
    """The command line every tools/ script shares: its description and --repo (default: this repo)."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument('--repo', default=ROOT, help='repo root (default: the repo these scripts are in)')
    return ap


def slug_of(path: str) -> str:
    """reports/aapl_analysis.html -> 'aapl'."""
    return os.path.basename(path).removesuffix('_analysis.html')


def write_json(path: str, obj: object, indent: int | None = None) -> int:
    """Write a data file the way every generator does: UTF-8, LF, non-ASCII kept, compact unless indent is
    given, ending in a newline. Returns its size in bytes."""
    text = json.dumps(obj, ensure_ascii=False, indent=indent, separators=None if indent else (',', ':'))
    rl.write_text(path, text + '\n')
    return os.path.getsize(path)


def report_path(slug: str, family: str | None = None, repo: str = ROOT) -> str:
    """reports/<slug>_analysis.html, or reports/<family>/<slug>_analysis.html for an ETF, crypto or bond report."""
    return os.path.join(repo, 'reports', *([family] if family else []), f'{slug}_analysis.html')


class IndexMembership(TypedDict):
    sp500_added: str | None      # 'YYYY-MM-DD' the name joined the S&P 500, when it is a member
    ndx: bool                    # a Nasdaq-100 member (the card's data-ndx)
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
    editions: list[list[str | float | None]]   # [as_of, price, note] per published edition, newest last
    delta_state: Literal['price', 'print', 'fix']   # the "what changed" box's class (claude/briefs/REFRESH.md)
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
    index: list[list[str | float | None]]      # [ticker, slug, sector_key, as_of, price]; any but slug may be None
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
        gl = re.search(r'data-gl="([A-Z0-9 ]+)"', a)   # global (non-US-index) names carry their home exchange (B3)
        out[m.group('slug')] = {
            'ticker': m.group('tick'),
            'card_name': htmllib.unescape(m.group('name')),
            'card_industry': htmllib.unescape(m.group('ind')),
            'card_sector_key': sector_of.get(m.group('slug')),
            'indices': {
                'sp500_added': sp.group(1) if sp else None,
                'ndx': 'data-ndx' in a,
                'dow30_added': dow.group(1) if dow else None,
                'global_exchange': gl.group(1) if gl else None,
            },
        }
    if not out:
        raise ValueError('no report cards found in reports/index.html (has the card markup changed?)')
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


# One report's style-tag inputs, as data/style_tags.json stores them (written by style_tags.py, read by
# card_tags.py) (keys include 'yield', a keyword, hence the functional form). Each number sits next
# to the page text it was read from, under 'raw'; 'tags' is added once the thresholds are known.
TagInputs = TypedDict('TagInputs', {
    'slug': str, 'ticker': str | None, 'as_of': str | None, 'industry': str | None, 'sp500': bool,
    'raw': dict[str, str | float | None], 'price': float | None, 'w52_high': float | None, 'mcap': float | None,
    'fcf': float | None, 'eps': float | None, 'pe': float | None, 'yield': float | None, 'revg': float | None,
    'roic': float | None, 'de': float | None, 'beta': float | None, 'fcf_yield': float | None,
    'excluded': NotRequired[str], 'tags': NotRequired[list[dict[str, str]]],
})


def report_paths(repo: str = ROOT, assets: bool = False, archived: bool = False) -> list[str]:
    """Sorted paths of the stock reports in the library (and the ETF, crypto and bond reports when assets=True, the
    ARCHIVED stock reports when archived=True). A RENAMED slug's redirect stub is never one."""
    skip = set(RENAMED) | (set() if archived else set(ARCHIVED))
    stocks = [p for p in glob.glob(os.path.join(repo, STOCK_REPORTS)) if slug_of(p) not in skip]
    return sorted(stocks + [p for pat in (ASSET_REPORTS if assets else []) for p in glob.glob(os.path.join(repo, pat))])
