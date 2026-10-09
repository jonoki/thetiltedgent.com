"""Section 04's index column in the stock reports (the "S&P 500" or "Nasdaq-100" column of the metrics table),
computed from the library's own reports of the index members and never typed (Oki, 8 Oct 2026).

usage:  py -3 tools/index_stats.py [slug ...]            write the column and its fine print (default: every stock report)
        py -3 tools/index_stats.py --check [slug ...]    change nothing; exit 1 when any page differs from what it
                                                         would write
        py -3 tools/index_stats.py --dry-run [slug ...]  change nothing; print the index figures and every edit
        py -3 tools/index_stats.py --stats DATE          print both indexes' figures on DATE (YYYY-MM-DD) and stop

Universe, shares and closes are index_rank.py's: the cards on reports/index.html (data-sp = S&P 500, data-ndx =
Nasdaq-100), one card per company (a dual-class company's card carries the whole company's market cap), shares_i =
Mkt Cap / header price from member i's own report, and Yahoo's daily close on or before a date, put back on the
report's share basis. Every member's figures come from its own latest report in the library, whatever its date.

Which index: the one the page's column header names (S&P 500 or Nasdaq-100). The header is normalised to
"S&P 500" or "Nasdaq-100". A non-US report whose metrics table compares with its home index (Nikkei 225, DAX,
FTSE 100, Hang Seng ...: HOME_INDEX) gets the S&P 500 column instead, computed the same way, so every report
compares with the same benchmark (Oki, 9 Oct 2026). Its old sentences about the home-index column are not
rewritten by this tool (they were removed by hand that day): a sentence in Section 04's notes or the disclaimer
that names a home index next to the word "column" is listed as LEFT.

For a page with banner date D and each member i of its index:
  cap_i(D) = shares_i x close_i(D)                     market cap on the page's date
  M_i      = member i's Mkt Cap on its own as-of        the base of every flow below (USD)
  E_i      = M_i / PE_i              (trailing P/E row, when positive)
           = M_i x EPS_i / price_i   (EPS (TTM) row, when the P/E row is n/m, missing or negative: a loss counts)
  F_i      = M_i / FPE_i             (Forward P/E row, positive only)
  Div_i    = y_i x M_i               (Dividend Yield row; a row reading None, n/a or "—" counts as 0%)
  Rev_i    = E_i / NPM_i             (Net Profit Margin row; NPM and E of the same sign)
  Prior_i  = Rev_i / (1 + g_i)       (Revenue Growth row: its first figure, on the member report's own basis)
  Eq_i     = E_i / ROE_i             (ROE row; ROE and E of the same sign, so negative equity is left out)
  Debt_i   = DE_i x Eq_i             (Debt-to-Equity row; banks, insurers other than brokers, capital-markets,
                                      credit-services and asset-management members are left out: their debt is
                                      their funding, and their reports state D/E on different bases)
  Each sum below runs over the members that have the inputs it needs:
  Trailing P/E   = sum cap_i(D) / sum E_i               (aggregate earnings, losses included: the index provider's
                                                         method; a negative total shows "—")
  Forward P/E    = sum cap_i(D) / sum F_i
  Dividend yield = sum Div_i / sum cap_i(D)             (aggregate dividends / aggregate cap on D)
  Net margin     = sum E_i / sum Rev_i
  Gross margin   = sum (GM_i x Rev_i) / sum Rev_i       (members that report a gross margin; banks and insurers
                                                         show n/m and are left out)
  Revenue growth = sum Rev_i / sum Prior_i - 1
  ROE            = sum E_i / sum Eq_i
  Debt-to-equity = sum Debt_i / sum Eq_i
  Beta           = S&P 500: 1.00, its definition (betas are measured against it), except where the company's beta
                   is not measured against the S&P 500: "—" on a row whose label or Context names another index (the
                   Nikkei 225, the SMI ...), and on a home-market listing (6857.T, ALV.DE ...) unless the row says
                   it is against the S&P 500, SPY or the US market. Nasdaq-100: "—". The
                   cap-weighted mean of the members' own betas, sum cap_i(D) x beta_i / sum cap_i(D), is printed
                   by --stats and --dry-run but not shown: for the S&P 500 it comes to 1.18-1.21, not 1.00, because
                   each beta is measured over its own past five years, when today's largest (and most volatile)
                   members weighed far less, so today's weights overstate the index's beta.
Coverage: a figure shows only when the members it uses are worth at least COVERAGE of the index's cap on D;
otherwise the cell reads "—". Every other row (PEG, ROIC, current ratio, short interest, EPS, FCF ...) reads "—":
it has no aggregate the members' reports support (PEG and ROIC need growth rates and invested capital the reports
do not state; the current ratio needs current liabilities; short interest is stated on mixed bases).
A member's cell counts only when it starts with its number: a cell marked n/m, n/a, n/v or est. is not used.
Cells are written in the company column's format (decimals, x or %, a + on growth) and carry no colour.

Fine print: one methods sentence (METHODS) per page, in its disclaimer, placed after the first sentence the tool
rewrote, else after index_rank's market-cap ranks sentence, else at the end of the disclaimer's last paragraph before
the legal notice; a later run only brings its index and date up to date. Sentences in the disclaimer and in Section
04 (outside the table) that described the old column (estimates, SPY/QQQ proxies, "—" cells, sourced index P/Es)
are rewritten clause by clause: a clause about the index column alone goes; "Industry Avg and S&P 500 columns are
..." keeps the industry half ("The figures in the Industry Avg column are ...", so verbs and pronouns still agree).
What the tool cannot rewrite safely is printed as LEFT, never forced: fix those by hand. The detection is a
heuristic, so a LEFT line can be a sentence that only mentions SPY or the index for something else (a Section 07
return); --check does not fail on LEFT lines.
"""
import os
import re
import sys
from typing import Mapping, NamedTuple

import chart_audit as ca
import index_rank as ir
import refresh_data as rf
import reportlib as rl
import repodata as rd

COVERAGE = 0.80             # share of the index's cap on D the contributing members must cover
PE_EPS_TOLERANCE = 0.25     # flag a member whose P/E and price / EPS disagree by more than this
THIN_MARGIN = 0.01          # flag a member whose net margin is under 1%: Rev_i = E_i / NPM_i is sensitive there
HEADERS = {'sp500': 'S&amp;P 500', 'ndx': 'Nasdaq-100'}
# a non-US report's home index, in a column header or a beta row (its metrics table gets the S&P 500 column)
HOME_INDEX = re.compile(r'Nikkei|TOPIX|\bDAX\b|\bCAC\b|FTSE|\bSMI\b|Swiss Market Index|Hang Seng|\bHSI\b|KOSPI|'
                        r'KOSDAQ|IBEX|\bAEX\b|\bOMX|CSI 300|\bASX\b|Australia Large Cap|TAIEX|Ibovespa|BEL ?20|'
                        r'\bSTI\b|Straits Times|\bOBX\b|(?i:nifty)|(?i:sensex)|\bTSX\b|\bTASI\b|(?i:euro ?stoxx)')

# The metrics rows, by key: the label patterns for both the members' own rows and the rows this tool fills.
ROWS: dict[str, str] = {
    'pe': r'(?i)^(?:Trailing P/E|P/E \(Trailing\))',
    'fpe': r'(?i)^Forward P/E',
    'dy': r'(?i)^Dividend Yield',
    'npm': r'(?i)^Net (?:Profit )?Margin',
    'gm': r'(?i)^Gross Margin(?!\s*/)',
    'g': r'(?i)^Revenue Growth',
    'roe': r'(?i)^ROE\b',
    'de': r'(?i)^Debt[- ]to[- ]Equity',
    'beta': r'(?i)^Beta\b',
}
EPS_ROW = r'(?i)^EPS \(TTM'
PERCENT = {'dy', 'npm', 'gm', 'g', 'roe'}
MULTIPLE = {'pe', 'fpe'}
# industries whose debt is their funding (Debt-to-Equity left out of the aggregate)
LENDER = re.compile(r'^(?:BANKS|INSURANCE - (?!BROKERS)|CAPITAL MARKETS|CREDIT SERVICES|ASSET MANAGEMENT)')

# A member's cell counts only when it starts with its number; these marks mean the page itself does not stand by it.
NOT_A_FIGURE = re.compile(r'(?i)\bn/?[amv]\b|not meaningful|\bNM\b|\best\b|estimate')
LEAD = re.compile(r'^\s*[~≈]?\s*([+\-−–]?)\s*\$?\s*(\d[\d,]*(?:\.(\d+))?)\s*([x×%])?')
NO_DIVIDEND = re.compile(r'(?i)^\s*(?:none|nil|no dividend|n/a|[—–-]\s*$|—\s*\()')


class Figures(NamedTuple):
    """One member's metrics as fractions (percent rows / 100) or multiples, None where its report has none."""
    pe: float | None
    fpe: float | None
    dy: float | None
    npm: float | None
    gm: float | None
    g: float | None
    roe: float | None
    de: float | None
    beta: float | None
    eps: float | None


class Flows(NamedTuple):
    """One member's aggregate inputs in dollars on its own as-of (None: not available)."""
    e: float | None
    f: float | None
    div: float | None
    rev: float | None
    gp: float | None
    prior: float | None
    eq: float | None
    debt: float | None
    beta: float | None


class Stat(NamedTuple):
    value: float | None         # None: below coverage, or no meaningful aggregate
    coverage: float             # share of the index's cap on D that contributed
    used: int
    left_out: int
    raw: float | None           # the computed figure before the beta convention or the coverage rule


class StatsError(Exception):
    """A page the tool cannot read or write the way it expects."""


# ---------- the members' figures ----------

def cell_figure(text: str | None, key: str) -> float | None:
    """A member's metrics cell as a number (percent rows as fractions). None unless the cell starts with its number
    and carries no n/m, n/a, n/v or est. mark. A Dividend Yield cell reading None, n/a or a dash is 0."""
    if text is None:
        return None
    if key == 'dy' and NO_DIVIDEND.search(text):
        return 0.0
    if NOT_A_FIGURE.search(text):
        return None
    m = LEAD.match(text)
    if not m:
        return None
    v = float(m.group(2).replace(',', ''))
    v = -v if m.group(1) in ('-', '−', '–') else v
    return v / 100 if key in PERCENT else v


def metrics_table(t: str) -> tuple[int, int] | None:
    """(start, end) of the page's metrics table: the first .fin-table whose fourth header names the S&P 500, the
    Nasdaq-100 or (on a metrics table) a home index. None when it has none."""
    for m in re.finditer(r'<table class="fin-table"[^>]*>.*?</table>', t, re.S):
        if header_index(m.group(0)):
            return m.start(), m.end()
    return None


def header_cells(table: str) -> list[tuple[int, int, str]]:
    """(start, end, inner html) of each <th> in the table's first row, offsets within table."""
    first = re.search(r'<tr[^>]*>(.*?)</tr>', table, re.S)
    if not first:
        return []
    return [(first.start(1) + m.start(), first.start(1) + m.end(), m.group(2))
            for m in re.finditer(r'(<th\b[^>]*>)(.*?)</th>', first.group(1), re.S)]


def header_index(table: str) -> str | None:
    """'sp500' or 'ndx' when the table's fourth header names that index; 'sp500' when it names a home index and the
    table is a metrics table (it has a Trailing P/E or EPS (TTM) row); else None."""
    th = header_cells(table)
    if len(th) < 4:
        return None
    text = rl.strip_tags(th[3][2])
    if re.search(r'S&P 500', text):
        return 'sp500'
    if re.search(r'(?i)nasdaq[- ]100', text):
        return 'ndx'
    if home_header(table):
        return 'sp500'
    return None


def home_header(table: str) -> bool:
    """True when the table's fourth header names a home index (not the S&P 500 or the Nasdaq-100) and the table
    is the metrics table."""
    th = header_cells(table)
    if len(th) < 4:
        return False
    text = rl.strip_tags(th[3][2])
    if re.search(r'S&P 500|(?i:nasdaq[- ]100)', text) or not HOME_INDEX.search(text):
        return False
    return any(re.match(ROWS['pe'], lab) or re.match(EPS_ROW, lab) for lab, _ in rl.table_rows(table))


def member_rows(t: str) -> list[tuple[str, str]]:
    """(label, company cell) of the page's metrics rows: its metrics table, else every .fin-table, else the page."""
    span = metrics_table(t)
    if span:
        return rl.table_rows(t[span[0]:span[1]])
    tables = re.findall(r'<table class="fin-table"[^>]*>.*?</table>', t, re.S)
    return rl.table_rows(''.join(tables) if tables else t)


def member_figures(t: str) -> Figures:
    rows = member_rows(t)
    vals = {k: cell_figure(rl.row_value(rows, pat), k) for k, pat in ROWS.items()}
    eps = rl.row_value(rows, EPS_ROW)
    m = LEAD.match(eps) if eps and not NOT_A_FIGURE.search(eps) else None
    e = (-1 if m.group(1) in ('-', '−', '–') else 1) * float(m.group(2).replace(',', '')) if m else None
    return Figures(vals['pe'], vals['fpe'], vals['dy'], vals['npm'], vals['gm'], vals['g'], vals['roe'], vals['de'],
                   vals['beta'], e)


def same_sign(a: float, b: float) -> bool:
    return (a > 0 and b > 0) or (a < 0 and b < 0)


def flows(m: ir.Member, f: Figures, lender: bool) -> Flows:
    """A member's dollar inputs, from its figures and its own Mkt Cap (the module docstring's formulas)."""
    e = m.mcap / f.pe if f.pe and f.pe > 0 else (m.mcap * f.eps / m.price if f.eps is not None else None)
    fwd = m.mcap / f.fpe if f.fpe and f.fpe > 0 else None
    div = f.dy * m.mcap if f.dy is not None else None
    rev = e / f.npm if e and f.npm and same_sign(e, f.npm) else None
    gp = f.gm * rev if rev and f.gm is not None else None
    prior = rev / (1 + f.g) if rev and f.g is not None and f.g > -1 else None
    eq = e / f.roe if e and f.roe and same_sign(e, f.roe) else None
    debt = f.de * eq if eq and f.de is not None and not lender else None
    return Flows(e, fwd, div, rev, gp, prior, eq, debt, f.beta)


def member_flags(m: ir.Member, f: Figures) -> list[str]:
    """What looks wrong in a member's own figures."""
    out = []
    if f.pe and f.pe > 0 and f.eps and f.eps > 0 and abs((m.price / f.eps) / f.pe - 1) > PE_EPS_TOLERANCE:
        out.append(f'{m.slug}: Trailing P/E {f.pe} vs price / EPS {m.price / f.eps:.1f}')
    if f.npm is not None and 0 < abs(f.npm) < THIN_MARGIN:
        out.append(f'{m.slug}: net margin {f.npm * 100:.2f}% (revenue = earnings / margin is sensitive)')
    if f.pe is None and f.eps is None:
        out.append(f'{m.slug}: no usable Trailing P/E or EPS (TTM): left out of P/E, margins, growth, ROE, D/E')
    return out


# ---------- the aggregates ----------

def aggregate(key: str, caps: Mapping[str, float], fl: Mapping[str, Flows]) -> Stat:
    """One row's figure for an index on a date: caps = every member's cap on D, fl = their flows."""
    total = sum(caps.values())

    def over(need: tuple[str, ...]) -> list[str]:
        return [s for s in caps if all(getattr(fl[s], n) is not None for n in need)]

    def ratio(num: float, den: float) -> float | None:
        return num / den if den > 0 else None

    need = {'pe': ('e',), 'fpe': ('f',), 'dy': ('div',), 'npm': ('e', 'rev'), 'gm': ('gp',), 'g': ('prior',),
            'roe': ('e', 'eq'), 'de': ('debt',), 'beta': ('beta',)}[key]
    used = over(need)
    cov = sum(caps[s] for s in used) / total if total else 0.0
    v: float | None
    if not used:
        v = None
    elif key == 'pe':
        v = ratio(sum(caps[s] for s in used), sum(fl[s].e or 0.0 for s in used))
    elif key == 'fpe':
        v = ratio(sum(caps[s] for s in used), sum(fl[s].f or 0.0 for s in used))
    elif key == 'dy':
        v = ratio(sum(fl[s].div or 0.0 for s in used), sum(caps[s] for s in used))
    elif key == 'npm':
        v = ratio(sum(fl[s].e or 0.0 for s in used), sum(fl[s].rev or 0.0 for s in used))
    elif key == 'gm':
        v = ratio(sum(fl[s].gp or 0.0 for s in used), sum(fl[s].rev or 0.0 for s in used))
    elif key == 'g':
        r = ratio(sum(fl[s].rev or 0.0 for s in used), sum(fl[s].prior or 0.0 for s in used))
        v = r - 1 if r is not None else None
    elif key == 'roe':
        v = ratio(sum(fl[s].e or 0.0 for s in used), sum(fl[s].eq or 0.0 for s in used))
    elif key == 'de':
        v = ratio(sum(fl[s].debt or 0.0 for s in used), sum(fl[s].eq or 0.0 for s in used))
    else:
        v = ratio(sum(caps[s] * (fl[s].beta or 0.0) for s in used), sum(caps[s] for s in used))
    return Stat(v if cov >= COVERAGE else None, cov, len(used), len(caps) - len(used), v)


def index_stats(index: str, caps: Mapping[str, float], fl: Mapping[str, Flows]) -> dict[str, Stat]:
    """Every row's figure for one index on one date. Beta: the S&P 500's is 1.00 by definition (betas are measured
    against it); the Nasdaq-100's reads "—" (the module docstring says why). The computed means stay in raw."""
    out = {k: aggregate(k, caps, fl) for k in ROWS}
    b = out['beta']
    out['beta'] = b._replace(value=1.0 if index == 'sp500' and b.value is not None else None)
    return out


# ---------- the cells ----------

class Format(NamedTuple):
    decimals: int
    suffix: str                 # '', 'x', '×' or '%'
    plus: bool                  # a + on a positive figure
    minus: str                  # the minus sign the page uses


def cell_format(key: str, company: str | None, page_suffix: str) -> Format:
    """The company cell's number format, or the row's default when the cell does not start with a number."""
    m = LEAD.match(company) if company else None
    minus = '-' if company and re.match(r'^\s*[~≈]?\s*-', company) else '−'
    if m:
        dec = min(len(m.group(3) or ''), 2)
        suffix = '%' if key in PERCENT else (m.group(4) or '') if m.group(4) in ('x', '×') else ''
        return Format(dec, suffix, key == 'g' and bool(m.group(1)), minus)
    if key in PERCENT:
        return Format(1, '%', key == 'g', minus)
    if key in MULTIPLE:
        return Format(1, page_suffix, False, minus)
    return Format(2, '', False, minus)


def render(v: float, key: str, f: Format) -> str:
    x = v * 100 if key in PERCENT else v
    s = f'{abs(x):,.{f.decimals}f}'
    if x < 0 and float(s.replace(',', '')) != 0:
        s = f.minus + s
    elif f.plus:
        s = '+' + s
    return s + f.suffix


def multiple_suffix(rows: list[tuple[str, str]]) -> str:
    """The x or × the page writes after its P/E figures, '' when it writes none."""
    for lab, val in rows:
        if re.match(ROWS['pe'], lab) or re.match(ROWS['fpe'], lab):
            m = LEAD.match(val)
            if m and m.group(4) in ('x', '×'):
                return m.group(4)
    return ''


# a page row that names one period ("Revenue Growth (FY2025)", "ROE, reported (Q2 2026)") is not the aggregate's
PERIOD_ROW = re.compile(r'^(?!Forward).*\((?:FY|Q\d)|^ROE,')


def row_key(label: str) -> str | None:
    """The ROWS key a page row is filled from, or None (it reads "—")."""
    if PERIOD_ROW.search(label):
        return None
    return next((k for k, pat in ROWS.items() if re.match(pat, label)), None)


US_BASIS = re.compile(r'S&P 500|\bSPY\b|\bU\.?S\.? market\b')
# a home-market symbol in the page's <title> ("6857.T — ...", "ALV.DE — ..."): BRK.B and BF.B are not one
HOME_LISTING = re.compile(r'<title>\s*[0-9A-Z][0-9A-Z-]*\.(?:T|DE|PA|L|SW|HK|KS|KQ|NS|BO|MC|AS|ST|SS|SZ|AX|TW|TWO|SA|BR|'
                          r'SI|OL|MI|TO|V|CO|HE|IR|VI|LS|F|SR|JK|NZ|WA|BK|KL|MX|JO)\s+—')


def other_basis(label: str, context: str, home_listing: bool = False) -> bool:
    """True when a beta row is not measured against the S&P 500, so the S&P 500's own beta of 1.00 is not the
    comparable figure: its label or Context names another index, or the page's listing is a home-market line
    (6857.T, ALV.DE ...) and the row does not say it is measured against the S&P 500 (data sites measure such a
    line's beta on their own basis)."""
    if HOME_INDEX.search(label) or HOME_INDEX.search(context):
        return True
    return home_listing and not (US_BASIS.search(label) or US_BASIS.search(context))


def neutral(td: str) -> str:
    """A cell's opening tag without a green, red or amber colour."""
    return re.sub(r'\s*color:\s*var\(--(?:green|red|amber)\);?', '', td).replace(' style=""', '')


def write_column(t: str, stats: Mapping[str, Stat]) -> tuple[str, dict[str, int], str]:
    """(the page with its metrics table's index column written, cells written per row key ('—' for a dash),
    the index key). StatsError when the table is not there."""
    span = metrics_table(t)
    if not span:
        raise StatsError('no metrics table with an S&P 500 or Nasdaq-100 column')
    table = t[span[0]:span[1]]
    index = header_index(table)
    assert index
    th = header_cells(table)[3]
    open_tag = re.match(r'<th\b[^>]*>', table[th[0]:th[1]])
    assert open_tag
    table = table[:th[0]] + open_tag.group(0) + HEADERS[index] + '</th>' + table[th[1]:]
    rows = rl.table_rows(table)
    suffix = multiple_suffix(rows)
    counts: dict[str, int] = {}
    out, pos = [], 0
    for rm in re.finditer(r'<tr\b[^>]*>(.*?)</tr>', table, re.S):
        cells = list(re.finditer(r'(<td\b[^>]*>)(.*?)</td>', rm.group(1), re.S))
        if len(cells) < 4:
            continue
        label = re.sub(r'\s+', ' ', rl.strip_tags(cells[0].group(2)))
        key = row_key(label)
        if key == 'beta' and other_basis(label, rl.strip_tags(cells[-1].group(2)) if len(cells) > 4 else '',
                                         bool(HOME_LISTING.search(t))):
            key = None
        st = stats.get(key) if key else None
        if key and st is not None and st.value is not None:
            text = render(st.value, key, cell_format(key, rl.strip_tags(cells[1].group(2)), suffix))
            counts[key] = counts.get(key, 0) + 1
        else:
            text = '—'
            counts['—'] = counts.get('—', 0) + 1
        c = cells[3]
        a, b = rm.start(1) + c.start(), rm.start(1) + c.end()
        out.append(table[pos:a] + neutral(c.group(1)) + text + '</td>')
        pos = b
    out.append(table[pos:])
    return t[:span[0]] + ''.join(out) + t[span[1]:], counts, index


# ---------- the fine print ----------
#
# Read block by block, sentence by sentence and clause by clause (index_rank's protect / sentences machinery: inline
# tags stand in as one private-use character each while a block is edited).

PH = ir.PH
METHODS = ('{name} column in Section 04: our aggregate of each index member\'s latest report in this library, weighted '
           'by market cap on {date}, shown where members worth at least 80% of the index report the figure (formulas '
           'in the finance glossary).')
METHODS_RE = re.compile(r'(S&(?:amp;)?P 500|Nasdaq-100) column in Section 04: our aggregate of each index member\'s '
                        r'latest report in this library, weighted by market cap on ([A-Z][a-z]+ \d{1,2}, \d{4}), shown '
                        r'where members worth at least 80% of the index report the figure \(formulas in the finance '
                        r'glossary\)\.')
Q = r'(?:"|“|”|&quot;|&ldquo;|&rdquo;|' + PH + r')?'
IDX = r'(?:S&(?:amp;)?P 500|S&(?:amp;)?P|NASDAQ-100|Nasdaq-100|NASDAQ 100|Nasdaq 100|NASDAQ|index)'
# one word of a column's name ("Industry Avg", "Travel Services Avg"): not a determiner, preposition or verb
WORD = (r'(?!(?:and|the|in|of|every|each|all|any|cells?|figures|values|averages|columns|for|from|to|with|are|is|was|'
        r'were|marked|by|on|both|entire|this|includes?|like|including|no|most)\b)[^\s,:.()"“”/—–⚠*¹²³†‡≈'
        + PH[1:-1] + r']+')
# "Industry Avg and S&P 500 columns", "industry/index averages": the industry half kept
PAIR = re.compile(r'(?<![^\s(“"*⚠¹²³†‡' + PH[1:-1] + r'])(?P<det>(?:(?:[Tt]he|[Aa]ll|[Bb]oth) )?(?:entire )?)'
                  r'(?P<a>' + Q + WORD + r'(?: ' + WORD + r'){0,5}' + Q + r'(?: \([^()]*\))?' + Q + r')'
                  r'(?: and |/)' + Q + r'(?:the )?(?:S&(?:amp;)?P 500|NASDAQ-100|Nasdaq-100|NASDAQ 100|'
                  r'index(?:-average|-benchmark)?)(?: \(est\.\))?' + Q +
                  r'(?P<kind> (?:(?:benchmark|comparison|comparator|[Aa]verage|aggregate|metric|benchmark average|'
                  r'benchmark column|comparison column) )?)'
                  r'(?P<noun>columns|averages|benchmarks|aggregates|composites|figures|values|metrics|cells|ratios)\b')
PLURAL_END = re.compile(r'(?:ratios|averages|figures|values|benchmarks|composites|multiples|aggregates|metrics)'
                        + Q + r'$')
# a heading before a clause's subject ("Specifically: ", "Estimates: ")
HEADING = re.compile(r'^[^:;]{1,60}:' + PH + r'?\s+$')
# the verb that makes the pair a clause's subject
VERB_AFTER = re.compile(r'^[^;]*?\b(?:are|were|read|show|remain|use|carry|have|come)\b')
RESPECTIVELY = re.compile(r' and the ' + IDX + r',? respectively')
LEADING = re.compile(r'^(?:[\s*⚠¹²³†‡—–]|≈est\.|' + PH + r')*')
WHERE = r'(?: (?:in|of) (?:Section 04|the (?:financial )?metrics table|the table)| \(Section 04\))?'
# a whole clause that names the old index column and nothing else
ITEM_ONLY = re.compile(r'^(?P<head>[^:;]{0,40}:' + PH + r'? )?(?:the |The |all |All |every |Every )?' + Q +
                       r'(?:the )?' + IDX + r'(?: \(est\.\))?' + Q + r'(?: benchmark| comparison)? (?:column|figures|'
                       r'values|cells)' + WHERE + r'(?: \([^()]*\))?$')
# a clause whose subject is the index column (or its source): what only_column may remove whole
ONLY_START = re.compile(r'^(?:[*⚠¹²³†‡\s]*)(?:Note:? )?(?:[Ww]here |[Aa]ll |[Ss]everal |[Oo]ther |[Tt]he |[Ii]ts )?'
                        r'(?:a |an |the )?(?:entire )?["“]?(?:S&P 500|S&P\b|NASDAQ-100|Nasdaq-100|NASDAQ\b|SPY\b|QQQ\b|'
                        r'VOO\b|[Ii]ndex\b|[Bb]enchmark\b)')
# a mention of the index column: the index by name near a column word, or "index" + a column word
COLUMN_TALK = re.compile(r'(?i)(?:S&P 500|NASDAQ[- ]100|\bSPY\b|\bQQQ\b|\bVOO\b)[^.;]{0,80}?'
                         r'\b(?:columns?|benchmarks?|averages?|composites?|aggregates?|comparison (?:figures|values|'
                         r'statistics|data)|statistics|proxy|proxies|proxied|P/E|cells?|metrics|values|figures)\b|'
                         r'\b(?:columns?|averages?|benchmark|comparisons?|cells)\b[^.;]{0,60}?(?:S&P 500|NASDAQ[- ]100)|'
                         r'(?<!published )(?<!live )(?<!sector )(?<!full-industry )(?<!broad )(?<!a )\bindex[- ]'
                         r'(?:columns?|averages?|benchmarks?|aggregates?|comparisons?|cells?|figures|metrics|values|'
                         r'ratios|P/E|yield)\b|\bindustry(?: and |/)index\b|\bindex column')
ELSEWHERE = re.compile(r'(?i)Section 0[1235-9]|five-year|5-year|relative[- ](?:return|performance)|price return|'
                       r'total return|daily closes|monthly closes|month-end|\bchart|index addition|add(?:ition)? date|'
                       r'date added|member since|List of S&P|market-cap ranks?|\branks?\b|\bmember(?:ship)?\b|'
                       r'benchmark returns|\breturns?\b')
# what the old column was said to be: estimates, proxies, blanks, a dated or sourced figure
OLD_CLAIM = re.compile(r'(?i)estimat|approx|\best\b|screener|prox(?:y|ies|ied)|\bSPY\b|\bQQQ\b|\bVOO\b|—|blank|'
                       r'composite|aggregate|directional|refreshed|carried|orientation|context only|deliberately|'
                       r'published|\bn/[avd]\b|\bvia\b|\bsourced\b|taken from|P/E (?:of )?\(?\d|yield \(?\d|throughout|'
                       r'labell?ed|marked|asterisk|reference|indicative|rough|omitted|removed|not shown|\bn/a\b|'
                       r'multpl|FactSet|GuruFocus|InvestSnips|Trading ?Economics|ChartRow|cross-check|definitional|'
                       r'by (?:definition|construction)|edition|\bfrom\b|\buses?\b|reported figures|only where')
# true statements about which index the column uses, kept as they are
TRUE_INDEX = re.compile(r'(?i)\bjoined\b|constituent|\bmember of\b|(?:index|S&P 500|Nasdaq-100) member\b|home index|'
                        r'(?:benchmark|index)(?: index| column)? (?:is|=|:) (?:the )?' + Q + r'(?:S&P 500|NASDAQ-100|Nasdaq-100)' + Q + r'(?:\W*$|,)|'
                        r'\bas the (?:index )?benchmark\W*$')
OTHER_SUBJECT = re.compile(r'(?i)industry|peer|competitor|market[- ]share|addressable|\bTAM\b|segment|sector|'
                           r'revenue|earnings date|dividend total|bubbles|holdings|biograph|Section 0[1235-9]|rank|'
                           r'\breturns?\b|index levels?|price history')


def names_column(c: str) -> bool:
    """True when a clause (protected text) mentions the metrics table's index column, other than to say truly which
    index it is."""
    p = ir.plain(c)
    if METHODS_RE.search(c) or not COLUMN_TALK.search(p) or TRUE_INDEX.search(p.rstrip(' ;.')):
        return False
    return not (ELSEWHERE.search(p) and not re.search(r'(?i)Section 04|column|metrics table', p))


def talks_of_column(s: str) -> bool:
    """True when a sentence describes the index column the old way: a clause names it and the sentence makes a claim
    the new column no longer fits (estimates, proxies, blanks, sourced figures)."""
    return bool(OLD_CLAIM.search(ir.plain(METHODS_RE.sub('', s)))) and any(
        names_column(c) for c in ir.top_level_split(s))


def only_column(c: str) -> bool:
    """True when the clause is about the index column and nothing else: its subject is the column (or the index,
    or its proxy) and it names nothing else the page estimates."""
    p = ir.plain(c)
    return names_column(c) and bool(ONLY_START.match(p)) and len(p) < 300 and not OTHER_SUBJECT.search(p)


def industry_half(m: re.Match[str], subject: bool, lower: bool = False) -> str:
    """The pair's industry half: as a subject "The figures in the X column" (so the plural verb and any "they" still
    agree), else "the X column"; plural nouns other than columns stay plural."""
    det, a, kind, noun = m.group('det'), m.group('a'), m.group('kind'), m.group('noun')
    if (kind.strip() == 'aggregate' and noun != 'columns') or (
            kind.strip().lower() == 'average' and re.search(r'(?:[Aa]verage|Avg)' + Q + r'$', a)):
        kind = ' '
    if noun != 'columns':
        return f'{det}{a}' if PLURAL_END.search(a) else f'{det}{a}{kind}{noun}'
    if re.match(Q + r'Industry[- ]average\b', a) and not det.strip(' ').lower().startswith('the'):
        a = re.sub(r'Industry', 'industry', a, count=1)
    if subject:
        lead = 'All figures in the ' if 'entire' in det else 'The figures in the '
        lead = lead[0].lower() + lead[1:] if lower else lead
        t = re.match(r'(' + PH + r'*)(?:[Tt]he )?', a)          # its own "The" goes
        assert t
        if t.group(1) and len(re.findall(PH, a)) >= 2:          # a tag around the name alone: the words go before it
            return f'{lead}{t.group(1)}{a[t.end():]}{kind}column'
        return f'{t.group(1)}{lead}{a[t.end():]}{kind}column'     # a tag around the sentence: inside it
    return f'{"the " if not det or det.lower().startswith(("all", "both")) else det}{a}{kind}column'


def rewrite_pair(c: str) -> tuple[str, bool]:
    """A clause with each "<industry> and <index> columns" phrase made the industry column alone. (clause, changed)"""
    out, pos = '', 0
    for m in PAIR.finditer(c):
        before = c[:m.start()]
        lead = LEADING.match(before)
        assert lead
        rest = before[lead.end():]
        headed = bool(HEADING.match(rest))
        subject = bool(VERB_AFTER.match(c[m.end():])) and (
            not rest.strip() or headed or bool(re.fullmatch(r'[Tt]he ' + PH + r'+', rest)))
        pre = c[pos:m.start()]
        if subject and pos == 0 and rest.strip() and not headed:  # "The <strong>entire X and S&P 500 columns": the
            pre = before[:lead.end()] + before[lead.end() + 4:]   # subject's own "The" gives way to the new one
        if pre.endswith(', ') and m.group('noun') != 'columns' and not m.group('det'):
            pre = pre[:-2] + ' and '                              # "A, B and S&P 500 figures" -> "A and B figures"
        out += pre + industry_half(m, subject, headed)
        pos = m.end()
    out += c[pos:]
    out = RESPECTIVELY.sub('', out)
    return out, out != c


class Note(NamedTuple):
    rule: str
    old: str
    new: str


def rewrite_clauses(s: str, tags: list[str]) -> tuple[str | None, list[Note], bool]:
    """One sentence (protected text) that talks_of_column, with its old index-column wording rewritten. (the sentence
    or None when it goes, the edits, whether a clause about the index column alone was removed)."""
    parts = ir.top_level_split(s)
    kept: list[str] = []
    notes: list[Note] = []
    removed_only = False
    carry = ''
    for i, p in enumerate(parts):
        sep = '; ' if p.endswith('; ') else ''
        body = p[:len(p) - len(sep)]
        stop = body[len(body.rstrip('.')):] if not sep else ''
        core = body[:len(body) - len(stop)] if stop else body
        core = carry + core
        carry = ''
        if not names_column(core):
            kept.append(core + stop + sep)
            continue
        im = ITEM_ONLY.match(ir.plain(core).strip()) and ITEM_ONLY.match(core.strip())
        if im or (only_column(core) and not PAIR.search(core)):
            notes.append(Note('clause removed', core, ''))
            removed_only = True
            head = im.group('head') if im else None
            if head and i + 1 < len(parts):
                carry = head
            elif not sep and kept:                       # the last clause went: the one before it ends the sentence
                kept[-1] = kept[-1][:-2] + stop
            continue
        new, changed = rewrite_pair(core)
        if changed:
            notes.append(Note('pair rewritten', core, new))
        kept.append(new + stop + sep)
    if not kept:
        return None, notes, removed_only
    out = ''.join(kept)
    out = re.sub(r'^((?:' + PH + r'|\s)*)([a-z])', lambda m: m.group(1) + m.group(2).upper(), out, count=1)
    lost = ''.join(ch for ch in re.findall(PH, s) if ch not in out)
    if not ir.pairs_up(lost, tags):
        return s, [], False
    return out, notes, removed_only


def section04_scope(t: str) -> list[tuple[int, int]]:
    """The spans of Section 04 outside its metrics table (its intro and the notes under the table)."""
    m = re.search(r'<span class="num">04</span>', t)
    span = metrics_table(t)
    if not m or not span:
        return []
    start = t.rfind('<div class="section"', 0, m.start())
    if start < 0:
        return []
    end = ir.div_end(t, start)
    return [(start, span[0]), (span[1], end)] if start < span[0] < span[1] <= end else []


class Pass(NamedTuple):
    text: str
    notes: list[Note]
    anchor: int | None          # where the methods sentence goes (an offset in text), when a sentence asked for it
    rank_anchor: int | None     # just after the market-cap ranks sentence (index_rank's clause)
    methods: int                # methods sentences found (their name and date brought up to date)


def rewrite_zone(html: str, name: str, date: str) -> Pass:
    """One zone (a disclaimer, or Section 04 outside its table) with its old index-column sentences rewritten and any
    methods sentence brought up to date."""
    pieces = ir.BLOCK.split(html)
    notes: list[Note] = []
    anchor = rank_anchor = None
    methods = 0
    offset = 0
    for i in range(len(pieces)):
        seg = pieces[i]
        if i % 2 or not seg.strip():
            offset += len(seg)
            continue
        b = ir.protect(seg)
        out, pos = '', 0
        for x, y in ir.sentences(b.text, b.tags):
            sent = b.text[x:y]
            out += b.text[pos:x]
            pos = y
            mm = METHODS_RE.search(sent)
            if mm:
                methods += 1
                sent = sent[:mm.start(1)] + name + sent[mm.end(1):mm.start(2)] + date + sent[mm.end(2):]
                out += sent
                continue
            if not talks_of_column(sent):
                out += sent
                if ir.NEW_RE.search(ir.plain(sent)) and rank_anchor is None:
                    rank_anchor = offset + len(ir.restore(out.rstrip(), b.tags))
                continue
            new, ed, removed_only = rewrite_clauses(sent.rstrip(), b.tags)
            notes += [Note(n.rule, ir.restore(n.old, b.tags), ir.restore(n.new, b.tags)) for n in ed]
            if new is None:
                while pos < len(b.text) and b.text[pos] == ' ':
                    pos += 1
            else:
                out += new + sent[len(sent.rstrip()):]
            if ed and anchor is None:
                anchor = offset + len(ir.restore(out.rstrip(), b.tags))
        out += b.text[pos:]
        pieces[i] = ir.restore(out, b.tags)
        offset += len(pieces[i])
    return Pass(''.join(pieces), notes, anchor, rank_anchor, methods)


def fallback_anchor(html: str) -> int | None:
    """End of the disclaimer's last block (paragraph, or run of text between line breaks) that is neither the
    data-date line nor the legal notice."""
    best, offset = None, 0
    for i, seg in enumerate(ir.BLOCK.split(html)):
        p = rl.strip_tags(seg) if i % 2 == 0 else ''
        if p and not re.match(r'(?i)(?:⚠\s*)?(?:static )?data as of', p) and not re.search(
                r'(?i)educational|informational purposes|not investment advice|not a recommendation', p):
            best = offset + len(seg.rstrip())
        offset += len(seg)
    return best


# a home index named next to a column that is not the Context or industry column
COLUMN_WORD = r'(?<!Context )(?<![Ii]ndustry )(?<!Avg )\bcolumns?\b'
HOME_COLUMN = re.compile(r'(?:' + HOME_INDEX.pattern + r')[^.;]{0,60}?' + COLUMN_WORD + '|'
                         + COLUMN_WORD + r'[^.;]{0,60}?(?:' + HOME_INDEX.pattern + r')')


def old_sentences(html: str) -> list[str]:
    """Sentences of html that still describe the old index column (or a home-index column), as a reader sees them."""
    out = []
    for seg in ir.BLOCK.split(html)[::2]:
        b = ir.protect(seg)
        out += [' '.join(ir.plain(b.text[x:y]).split()) for x, y in ir.sentences(b.text, b.tags)
                if talks_of_column(b.text[x:y]) or HOME_COLUMN.search(ir.plain(b.text[x:y]))]
    return out


def rewrite_fine_print(t: str, index: str, date: str) -> tuple[str, list[Note], list[str]]:
    """(the page with Section 04's notes and its disclaimer rewritten and the methods sentence in place, the edits,
    the sentences that still describe the old column)."""
    name = HEADERS[index]
    notes: list[Note] = []
    for a, b in reversed(section04_scope(t)):
        p = rewrite_zone(t[a:b], name, date)
        t = t[:a] + p.text + t[b:]
        notes += p.notes
    scope = ir.fine_print_scope(t)
    if not scope:
        raise StatsError('no disclaimer for the methods sentence')
    a, b = scope
    p = rewrite_zone(t[a:b], name, date)
    body = p.text
    if not p.methods:
        at = p.anchor if p.anchor is not None else p.rank_anchor if p.rank_anchor is not None else fallback_anchor(body)
        if at is None:
            raise StatsError('no place in the disclaimer for the methods sentence')
        sentence = METHODS.format(name=name, date=date)
        if at and not re.match(r'[\s>]', body[at - 1]):
            body = body[:at] + ' ' + sentence + body[at:]
        else:
            body = body[:at] + sentence + ('' if re.match(r'[\s<]|$', body[at:at + 1]) else ' ') + body[at:]
        notes.append(Note('methods sentence added', '', sentence))
    t = t[:a] + body + t[b:]
    left = [s for x, y in section04_scope(t) for s in old_sentences(t[x:y])]
    sc = ir.fine_print_scope(t)
    if sc:
        left += old_sentences(t[sc[0]:sc[1]])
    return t, notes + p.notes, left


# ---------- the run ----------

class Library(NamedTuple):
    members: dict[str, ir.Member]
    flows: dict[str, Flows]
    series: dict[str, rf.Daily]
    flags: list[str]


def load_library(repo: str, dates: list[str]) -> tuple[Library, list[str]]:
    """Every index member's figures and flows, and Yahoo closes reaching every date needed. (library, errors)."""
    members, errs = ir.index_members(repo)
    cards = rd.parse_index_cards(repo)
    fl, flags = {}, []
    for s, m in members.items():
        f = member_figures(rl.read_text(rd.report_path(s, repo=repo)))
        fl[s] = flows(m, f, bool(LENDER.match(cards[s]['card_industry'])))
        flags += member_flags(m, f)
    need = sorted(set(dates) | {m.as_of for m in members.values()})
    series: dict[str, rf.Daily] = {}
    for s, m in sorted(members.items()):
        try:
            series[s] = ir.daily_closes(m.symbol, need[0], need[-1])
        except ca.YahooError as e:
            errs.append(f'{s} ({m.symbol}): yahoo {e}')
    return Library(members, fl, series, sorted(flags)), errs


def stats_on(index: str, iso: str, lib: Library, memo: dict[tuple[str, str], dict[str, Stat]]) -> dict[str, Stat]:
    if (index, iso) not in memo:
        caps = ir.index_caps(index, iso, lib.members, lib.series)
        memo[(index, iso)] = index_stats(index, caps, lib.flows)
    return memo[(index, iso)]


def print_stats(index: str, iso: str, st: Mapping[str, Stat]) -> None:
    print(f'{HEADERS[index].replace("&amp;", "&")} on {iso}:')
    for k, s in st.items():
        raw = 'n/a' if s.raw is None else (f'{s.raw * 100:.2f}%' if k in PERCENT else f'{s.raw:.3f}')
        print(f'  {k:5} {raw:>9}  coverage {s.coverage * 100:5.1f}%  used {s.used:3}  left out {s.left_out:3}'
              f'{"" if s.value is not None else "  -> —"}')


def main(argv: list[str] | None = None) -> int | str:
    ap = rd.parser('Write Section 04\'s S&P 500 / Nasdaq-100 column of each stock report from the members\' reports.')
    ap.add_argument('slugs', nargs='*', help='report slugs (default: every stock report)')
    ap.add_argument('--check', action='store_true', help='change nothing; exit 1 when a page differs from what would '
                    'be written or still describes the old column')
    ap.add_argument('--dry-run', action='store_true', help='change nothing; print the figures and edits')
    ap.add_argument('--stats', metavar='DATE', help='print both indexes\' figures on DATE (YYYY-MM-DD) and stop')
    args = ap.parse_args(argv)
    repo = args.repo
    slugs = args.slugs or [rd.slug_of(p) for p in rd.report_paths(repo)]
    errs: list[str] = []
    pages: dict[str, tuple[str, str, str]] = {}
    skipped = []
    for slug in slugs:
        path = rd.report_path(slug, repo=repo)
        if not os.path.exists(path):
            errs.append(f'{slug}: no page')
            continue
        t = rl.read_text(path)
        if not metrics_table(t):
            skipped.append(slug)
            continue
        a = rl.as_of(t)[0]
        if not a:
            errs.append(f'{slug}: no as-of date')
            continue
        pages[slug] = (path, t, a)
    dates = sorted({a for _, _, a in pages.values()} | ({args.stats} if args.stats else set()))
    if not dates:
        return 'nothing to do'
    lib, lerrs = load_library(repo, dates)
    if lerrs:
        print('ERRORS (nothing written):')
        print('\n'.join('  ' + e for e in errs + lerrs))
        return 1
    memo: dict[tuple[str, str], dict[str, Stat]] = {}
    if args.stats:
        for index in HEADERS:
            print_stats(index, args.stats, stats_on(index, args.stats, lib, memo))
        return 0
    cells: dict[str, int] = {}
    rules: dict[str, int] = {}
    changed, left_pages, home = [], [], []
    for slug, (path, t, a) in sorted(pages.items()):
        try:
            span = metrics_table(t)
            assert span
            if home_header(t[span[0]:span[1]]):
                home.append(f'{slug} ({rl.strip_tags(header_cells(t[span[0]:span[1]])[3][2])})')
            index = header_index(t[span[0]:span[1]])
            assert index
            new, counts, _ = write_column(t, stats_on(index, a, lib, memo))
            new, notes, left = rewrite_fine_print(new, index, ir.long_date(a))
        except (StatsError, ir.RankError) as e:
            errs.append(f'{slug}: {e}')
            continue
        for k, v in counts.items():
            cells[k] = cells.get(k, 0) + v
        for n in notes:
            rules[n.rule] = rules.get(n.rule, 0) + 1
            if args.dry_run and n.rule != 'methods sentence added':
                print(f'  {slug}: {n.rule}: {n.old!r} -> {n.new!r}')
        if left:
            left_pages.append((slug, left))
        if new != t:
            changed.append(slug)
            if not (args.check or args.dry_run):
                rl.write_text(path, new)
    if args.dry_run:
        for d in sorted({(header_index(t[slice(*metrics_table(t) or (0, 0))]) or '', a) for _, t, a in pages.values()}):
            if d[0]:
                print_stats(d[0], d[1], memo[(d[0], d[1])])
    if errs:
        print('ERRORS:')
        print('\n'.join('  ' + e for e in errs))
    print(f'pages with an S&P 500 / Nasdaq-100 column: {len(pages)}; without one (left alone): {len(skipped)}')
    if home:
        print(f'home-index columns given the S&P 500: {len(home)}', ', '.join(home))
    print('cells:', ', '.join(f'{k} {v}' for k, v in sorted(cells.items())))
    print('fine print:', ', '.join(f'{k} {v}' for k, v in sorted(rules.items())))
    print('member flags:', len(lib.flags))
    print('\n'.join('  ' + f for f in lib.flags))
    verb = 'that differ from what would be written' if args.check else 'that would change' if args.dry_run else 'written'
    print(f'pages {verb}: {len(changed)}', changed[:40] if args.check else '')
    print(f'old index-column sentences left: {sum(len(x) for _, x in left_pages)} on {len(left_pages)} pages')
    for slug, left in left_pages:
        for s in left:
            print(f'  LEFT {slug}: {s[:300]}')
    if args.check:
        return 1 if changed or errs else 0
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
