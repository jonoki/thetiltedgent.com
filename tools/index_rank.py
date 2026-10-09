"""Market-cap ranks in the stock reports' headers, computed and never typed: each report's rank among the S&P 500 and
the Nasdaq-100 members on its own banner (as-of) date (Oki, 8 Oct 2026).

usage:  py -3 tools/index_rank.py [slug ...]            write the rank rows (default: every stock report)
        py -3 tools/index_rank.py --check [slug ...]    change nothing; exit 1 when any page's row differs from what
                                                        it would write
        py -3 tools/index_rank.py --dry-run [slug ...]  change nothing; print every row and fine-print edit it would make

Universe: the cards on reports/index.html; data-sp = S&P 500, data-ndx = Nasdaq-100. There is one card per company, so a
company with two listed share classes (Alphabet GOOGL/GOOG, Fox FOXA/FOX, News Corp NWSA/NWS, Berkshire BRK.B/BRK.A)
ranks once, at its whole market cap: its report states the company's total and its shares below are counted in units
of the carded class.
Shares: market cap / header price, both as the member's own report states them at its own as-of.
Close on date D: Yahoo's daily close (split-adjusted, not dividend-adjusted), the last one on or before D, times the
splits Yahoo booked after the member's as-of (Yahoo back-adjusts every close for them; the report's share count is
on its as-of basis). Market cap on D = shares x that close.
Rank on D: 1 + the number of the index's members with a larger market cap on D.
The row: "Mkt Cap Ranking:" then "S&P 500: #N" and/or "Nasdaq-100: #N", first pill in the page's accent pill style, the
second dim; a page in neither index has no row; a member page without one gets it under the ticker line.
Fine print (the page's disclaimer): sentences and list items about the old ranks (companiesmarketcap.com, estimated
US and exchange ranks) become NEW_CLAUSE with the banner date, or are removed on a page in neither index. What does
not match a known shape is listed, never forced.
Flags, printed: implied shares more than 5% from the page's own Shares Outstanding row; a header price more than 1%
from Yahoo's close on the as-of. A member without a usable market cap, price or Yahoo series stops the run before
anything is written: every rank in its index would be in doubt.
Yahoo JSON is cached under <temp>/ttg_index_rank; a cached series that does not reach the latest date needed is
fetched again.
"""
import datetime
import html as htmllib
import json
import os
import re
import sys
import tempfile
from typing import Mapping, NamedTuple

import chart_audit as ca
import refresh_data as rf
import reportlib as rl
import repodata as rd

WORK = os.path.join(tempfile.gettempdir(), 'ttg_index_rank')
SHARES_TOLERANCE = 0.05     # implied shares vs the page's Shares Outstanding row
PRICE_TOLERANCE = 0.01      # header price vs Yahoo's close on the as-of (split basis aligned)
FETCH_LEAD_DAYS = 10        # fetch from this many days before the earliest date needed (a holiday-proof margin)
INDEXES = (('sp500', 'S&amp;P 500'), ('ndx', 'Nasdaq-100'))
NEW_CLAUSE = 'Market-cap ranks: our calculation on {date} — shares × closing price for every index member'
NEW_RE = re.compile(r'[Mm]arket-cap ranks: our calculation on ([A-Z][a-z]+ \d{1,2}, \d{4}) — shares × closing '
                    r'price for every index member')

# The row a member page without one gets (the markup General Mills carried until 29 Sep 2026).
DEFAULT_OPEN = '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px;">'
DEFAULT_LABEL = ('<span style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:var(--accent);'
                 'letter-spacing:0.5px;">Mkt Cap Ranking:</span>')
DEFAULT_ACCENT = ('<span style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:var(--accent);'
                  'background:var(--accent-dim);padding:3px 10px;border-radius:4px;">')


class Member(NamedTuple):
    slug: str
    symbol: str                 # Yahoo
    as_of: str                  # YYYY-MM-DD
    price: float
    mcap: float                 # dollars
    shares: float               # mcap / price
    stated_shares: float | None
    sp500: bool
    ndx: bool


class RankError(Exception):
    """A page the tool cannot read or write the way it expects."""


# ---------- the members and their market caps ----------

def parse_shares(text: str | None) -> float | None:
    """'2.45B', '596.00M', '12.1 billion', '1,234,567,890' -> a share count; None when the cell is not one, or is a
    bare number too small to be a count ('191.61', millions by the page's convention, which the cell does not say)."""
    if not text:
        return None
    m = re.search(r'([\d,]+(?:\.\d+)?)\s*(B|M|K|bn|billion|million|thousand)?\b', text, re.I)
    if not m:
        return None
    unit = {'b': 1e9, 'bn': 1e9, 'billion': 1e9, 'm': 1e6, 'million': 1e6, 'k': 1e3, 'thousand': 1e3}
    n = float(m.group(1).replace(',', '')) * unit.get((m.group(2) or '').lower(), 1.0)
    return n if m.group(2) or n >= 1e6 else None


def read_member(slug: str, card: rd.IndexCard, repo: str) -> Member:
    """One index member's numbers from its own report. RankError when a number is missing."""
    path = rd.report_path(slug, repo=repo)
    if not os.path.exists(path):
        raise RankError(f'{slug}: no page {os.path.relpath(path, repo)}')
    t = rl.read_text(path)
    ticker = rl.parse_title(t)[0] or card['ticker']
    as_of, price, mcap = rl.as_of(t)[0], rl.header_price(t), rf.header_mcap(t)
    if not (as_of and price and mcap):
        raise RankError(f'{slug}: as-of {as_of}, header price {price}, Mkt Cap {mcap and mcap[0]}: one is unreadable')
    stated = parse_shares(rl.row_value(rl.table_rows(t), r'(?i)shares outstanding'))
    return Member(slug, ca.yahoo_symbol(slug, ticker), as_of, price, mcap[1], mcap[1] / price, stated,
                  bool(card['indices']['sp500_added']), card['indices']['ndx'])


def index_members(repo: str) -> tuple[dict[str, Member], list[str]]:
    """Every S&P 500 and Nasdaq-100 member card's numbers, and the errors of the ones that could not be read."""
    out, errs = {}, []
    for slug, card in rd.parse_index_cards(repo).items():
        if card['indices']['sp500_added'] or card['indices']['ndx']:
            try:
                out[slug] = read_member(slug, card, repo)
            except RankError as e:
                errs.append(str(e))
    return out, errs


# ---------- Yahoo daily closes ----------

def cache_path(symbol: str) -> str:
    os.makedirs(WORK, exist_ok=True)
    return os.path.join(WORK, f'{symbol}.d1.json')


def cached_daily(path: str, first: str, last: str) -> rf.Daily | None:
    """The cached series when it reads and covers first..last; None (it is fetched again) otherwise."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            daily = rf.parse_daily(json.load(fh))
    except (ValueError, ca.YahooError):
        return None
    if not daily.days or daily.days[0].date > first or daily.days[-1].date < last:
        return None
    return daily


def daily_closes(symbol: str, first: str, last: str) -> rf.Daily:
    """Yahoo daily bars covering first..last (ISO dates), from the cache or fetched. ca.YahooError when there are none."""
    path = cache_path(symbol)
    cached = cached_daily(path, first, last)
    if cached:
        return cached
    start = datetime.date.fromisoformat(first) - datetime.timedelta(days=FETCH_LEAD_DAYS)
    p1 = int(datetime.datetime(start.year, start.month, start.day, tzinfo=datetime.UTC).timestamp())
    ca.fetch_url(rf.YAHOO_DAILY.format(sym=symbol, p1=p1, p2=int(datetime.datetime.now(datetime.UTC).timestamp())), path)
    with open(path, encoding='utf-8') as fh:
        try:
            daily = rf.parse_daily(json.load(fh))
        except ValueError as e:
            raise ca.YahooError(f'unreadable daily series ({type(e).__name__})') from e
    if not daily.days or daily.days[-1].date < last:
        raise ca.YahooError(f'series ends {daily.days[-1].date if daily.days else "empty"}, before {last}')
    return daily


def close_on(daily: rf.Daily, iso: str) -> float | None:
    """The last close on or before iso, or None when the series starts after it."""
    day = rf.on_or_before(daily.days, iso)
    return day.close if day else None


def cap_on(m: Member, daily: rf.Daily, iso: str) -> float | None:
    """A member's market cap on iso: shares x Yahoo's close, back on the as-of share basis."""
    c = close_on(daily, iso)
    return m.shares * c * ca.splits_after(daily.splits, m.as_of) if c is not None else None


def rank_of(caps: Mapping[str, float], slug: str) -> int:
    """1 + the number of others with a larger market cap."""
    mine = caps[slug]
    return 1 + sum(1 for s, c in caps.items() if s != slug and c > mine)


def index_caps(key: str, iso: str, members: Mapping[str, Member], series: Mapping[str, rf.Daily]) -> dict[str, float]:
    """Every member of index key ('sp500', 'ndx') with its market cap on iso. RankError when a member has no close."""
    caps = {}
    for s, m in members.items():
        if getattr(m, key):
            cap = cap_on(m, series[s], iso)
            if cap is None:
                raise RankError(f'{s}: no Yahoo close on or before {iso}')
            caps[s] = cap
    return caps


def ranks_on(slug: str, iso: str, members: Mapping[str, Member], series: Mapping[str, rf.Daily],
             memo: dict[tuple[str, str], dict[str, float]] | None = None) -> dict[str, int]:
    """{'sp500': N, 'ndx': N} for the indexes slug belongs to, on date iso (memo keeps each index's caps per date)."""
    memo = {} if memo is None else memo
    out = {}
    for key, _ in INDEXES:
        if getattr(members[slug], key):
            if (key, iso) not in memo:
                memo[(key, iso)] = index_caps(key, iso, members, series)
            out[key] = rank_of(memo[(key, iso)], slug)
    return out


def member_flags(m: Member, daily: rf.Daily) -> list[str]:
    """What looks wrong with a member's inputs: implied vs stated shares, header price vs Yahoo's as-of close."""
    flags = []
    if m.stated_shares and abs(m.shares / m.stated_shares - 1) > SHARES_TOLERANCE:
        flags.append(f'{m.slug}: implied shares {m.shares / 1e6:,.1f}M (Mkt Cap / price) vs Shares Outstanding '
                     f'{m.stated_shares / 1e6:,.1f}M ({(m.shares / m.stated_shares - 1) * 100:+.1f}%)')
    c = close_on(daily, m.as_of)
    if c is not None:
        yc = c * ca.splits_after(daily.splits, m.as_of)
        if abs(yc / m.price - 1) > PRICE_TOLERANCE:
            flags.append(f'{m.slug}: header price {m.price} vs Yahoo close {yc:.2f} on {m.as_of}')
    return flags


# ---------- the row ----------

LABEL_SPAN = re.compile(r'<span\b[^>]*>\s*(?i:mkt cap ranking)[^<]*</span>')
SPAN = re.compile(r'<span\b[^>]*>.*?</span>', re.S)
SEPARATORS = ('·', '&middot;', '|', '•')
KEEP = re.compile(r'(?i)member since')    # an index-membership pill that sits in the rank row; kept after the ranks


class Row(NamedTuple):
    start: int                  # the start of the row's line (its indentation included)
    end: int                    # just past its '</div>' and the line break after it
    indent: str
    child_indent: str | None    # None: the row is written on one line
    open_tag: str
    label: str                  # the whole label span, text normalised
    accent: str                 # opening tag of the first pill
    dim: str                    # opening tag of the second
    sep: str | None             # a whole separator span, when the row had one between pills
    keep: list[str]             # whole spans kept after the ranks


def div_end(t: str, start: int) -> int:
    """The index just past the </div> that closes the <div at start (nested divs counted)."""
    depth = 0
    for m in re.finditer(r'<div\b|</div>', t[start:]):
        depth += 1 if m.group(0) == '<div' else -1
        if depth == 0:
            return start + m.end()
    raise RankError(f'unclosed <div at {start}')


def line_bounds(t: str, start: int, end: int) -> tuple[int, int, str]:
    """(line start, end past the line break, indentation) of the element start..end when it sits on lines of its own."""
    ls = t.rfind('\n', 0, start) + 1
    indent = t[ls:start]
    if indent.strip():
        ls, indent = start, ''
    e = end + 1 if t[end:end + 1] == '\n' else end
    return ls, e, indent


def text_of(span: str) -> str:
    return rl.strip_tags(span)


def dim_from(accent: str) -> str:
    """A dim pill's opening tag from an accent one."""
    return accent.replace('color:var(--accent);', 'color:var(--text-dim);').replace('background:var(--accent-dim)',
                                                                                    'background:var(--surface2)')


def find_row(t: str) -> Row | None:
    """The page's rank row, or None. RankError when the label sits somewhere the tool does not recognise."""
    m = LABEL_SPAN.search(t)
    if not m:
        return None
    start = t.rfind('<div', 0, m.start())
    end = div_end(t, start)
    if end < m.end():
        raise RankError('the rank label is not inside a row of its own')
    open_tag = t[start:t.index('>', start) + 1]
    inner = t[len(open_tag) + start:end - len('</div>')]
    if '<div' in inner:
        raise RankError('the rank row holds a nested <div>')
    ls, le, indent = line_bounds(t, start, end)
    spans = SPAN.findall(inner)
    label_tag = m.group(0)[:m.group(0).index('>') + 1]
    label_text = 'MKT CAP RANKING:' if text_of(m.group(0)).startswith('MKT') else 'Mkt Cap Ranking:'
    pills = [s for s in spans if text_of(s) not in SEPARATORS and not LABEL_SPAN.fullmatch(s)
             and ('background' in s[:s.index('>')] or 'pill' in s[:s.index('>')])]
    tags = [p[:p.index('>') + 1] for p in pills]
    accent = next((g for g in tags if 'color:var(--accent)' in g), tags[0] if tags else DEFAULT_ACCENT)
    dim = next((g for g in tags if 'var(--text-dim)' in g), dim_from(accent))
    seps = [s for s in spans if text_of(s) in SEPARATORS]
    lm = re.search(r'\n([ \t]*)<span', inner)
    return Row(ls, le, indent, lm.group(1) if lm else None, open_tag, label_tag + label_text + '</span>', accent, dim,
               seps[0] if seps else None, [p for p in pills if KEEP.search(text_of(p))])


def default_row(indent: str) -> Row:
    return Row(0, 0, indent, indent + '  ', DEFAULT_OPEN, DEFAULT_LABEL, DEFAULT_ACCENT, dim_from(DEFAULT_ACCENT), None, [])


def render_row(row: Row, ranks: Mapping[str, int]) -> str:
    """The row's markup, from its first line's indentation to its line break."""
    named = [(name, ranks[key]) for key, name in INDEXES if key in ranks]
    pills = [f'{row.dim if i else row.accent}{name}: #{n}</span>' for i, (name, n) in enumerate(named)]
    children = [row.label]
    for i, p in enumerate(pills):
        if i and row.sep:
            children.append(row.sep)
        children.append(p)
    children += row.keep
    if row.child_indent is None:
        body = ' '.join(children)
    else:
        body = ''.join('\n' + row.child_indent + c for c in children) + '\n' + row.indent
    return f'{row.indent}{row.open_tag}{body}</div>\n'


def ticker_block_end(t: str) -> tuple[int, str]:
    """(where a new row goes: the line after the ticker block, its indentation)."""
    m = re.search(r'<div class="ticker-block"', t)
    if not m:
        raise RankError('no ticker block to put the rank row under')
    _, le, indent = line_bounds(t, m.start(), div_end(t, m.start()))
    return le, indent


def write_row(t: str, ranks: Mapping[str, int]) -> tuple[str, str]:
    """(the page with its rank row written, what was done: 'replaced', 'inserted', 'removed', 'unchanged' or 'none')."""
    row = find_row(t)
    if not ranks:
        return (t[:row.start] + t[row.end:], 'removed') if row else (t, 'none')
    if row:
        new = t[:row.start] + render_row(row, ranks) + t[row.end:]
        return new, 'unchanged' if new == t else 'replaced'
    at, indent = ticker_block_end(t)
    return t[:at] + render_row(default_row(indent), ranks) + t[at:], 'inserted'


# ---------- the fine print ----------
#
# The disclaimer is read block by block (paragraphs, list items, line breaks). Inside a block every inline tag
# (<strong>, <a>, <em> …) stands in as one private-use character while the text is edited, so a sentence can run
# across them; a sentence is only rewritten when the tags it would lose pair up.

OLD = re.compile(r'(?i)companiesmarketcap|(?:market[- ]cap(?:itali[sz]ation)?|mkt[- ]cap)\s+rank|\brank(?:s|ing|ings)?\b'
                 r'[^.;]{0,40}\(est\.\)|\b(?:US|U\.S\.|NYSE|NASDAQ|exchange)\b[^.;]{0,30}\branks?\b')
RANK = re.compile(r'(?i)\brank')
MONTHS = 'january february march april may june july august september october november december'.split()
VOCAB = set("""
global us u.s u.s. us-listed nyse nasdaq nyse-only nasdaq-only nyse-specific nasdaq-specific exchange exchange-level
exchange-specific uk u.k netherlands
the a an and or both all three two its it this that these such
market-cap market cap mkt capitalisation capitalization market-capitalisation market-capitalization
rank ranks ranking rankings ranked pill pills badge badges header above in on at of from per via by for to
is are was were be been
marked labelled labeled flagged shown as estimate estimates estimated est est. (est.) approximate approximately
approximation approximations approx approx. indicative rough roughly order-of-magnitude directional
only sourced source derived our own author's author computed interpolated
companiesmarketcap.com companiesmarketcap stockanalysis.com stockanalysis
move moves change changes daily with prices price close
items covers includes include including
not verified n/v n/d
treat them should
mid-august mid-september late-august early-september edition snapshot
because no directly published figure list lists universes ranked carried forward when current measured used page
site intraday read day explicitly specifically notes gaps stated data cross-check secondary context date dated
early-august figures flags nasdaq-exchange
""".split()) | set(MONTHS) | {m[:3] for m in MONTHS} | {'sept'}
# "market cap" that does not start a rank phrase ("market cap and global ranking"): the source covers more than ranks
MCAP_NOT_RANK = re.compile(r'(?i)\b(?:market[- ]cap(?:itali[sz]ation)?|mkt[- ]cap)s?\b'
                           r'(?![- ](?:(?:global|us|u\.s\.|nyse|nasdaq)[ /,]+)*rank)')
TOKEN_SKIP = re.compile(r'^(?:[~≈]?#?~?[\d,.]+|[~≈]?#~?[\d,]+(?:[–-]\d+)?|\$[\d,.]+[a-z]*|[—–/&=+\-]|)$', re.I)
ABBR = re.compile(r'(?:\b(?:U\.S|U\.K|est|approx|Inc|No|vs|e\.g|i\.e|St|Co|Corp|Ltd|Jr|Mr|Ms|Dr|Jan|Feb|Mar|Apr|Jun|Jul|Aug'
                  r'|Sep|Sept|Oct|Nov|Dec)|(?:^|\s)[A-Z])$')     # a lone capital is an initial; '10-K.' ends a sentence
BLOCK = re.compile(r'(</?(?:p|div|li|ul|ol|br|td|tr|th|table|tbody|thead|footer|section|h\d)\b[^>]*>)')
PH = f'[{chr(0xE000)}-{chr(0xF8FF)}]'          # one inline tag, while a block is edited
# A rank item in a list: "the US and NYSE market-cap rank pills", "the U.S./NYSE market-cap rankings", "the NASDAQ
# market-cap rank (~#55)"
WHO = (r'(?:Global|global|U\.S\.|US|US-listed|NYSE|NASDAQ|Nasdaq|UK|Netherlands|Canada|China|exchange-level|exchange)'
       r'(?:-specific|-only|-exchange)?(?: \([~≈]?#[\d,]+\))?')
ITEM = re.compile(r'(?:all three |both |the )?(?:' + WHO + r'(?:, and |, | and |/| / ))*(?:' + WHO + r' )?'
                  r'(?:market[- ]cap(?:itali[sz]ation)?|mkt[- ]cap)[- ]rank(?:s|ings?)?(?: pills?| badges?)?'
                  r'(?: in the header)?(?: \((?:[~≈]?#[\d,]+|est\.|(?:global|US|NYSE|NASDAQ)(?:, (?:global|US|NYSE|NASDAQ))*)\))?')
# The old source as a list item: "CompaniesMarketCap (global market-cap rank)", "companiesmarketcap.com for the global rank"
SOURCE_ITEM = re.compile(r'(?i)' + PH + r'?(?:https?://)?(?:www\.)?companiesmarketcap(?:\.com)?(?:/[\w\-/]*)?' + PH + r'?'
                         r'(?: \((?P<paren>[^()]*)\)| for (?P<for>[^.;,()]*?\brank(?:s|ing|ings)?\b(?: \([^()]*\))?))'
                         r'(?=[.;]|, |$)')
LEADS = (': ', '— ', ' includes ', ' include ', ' including ', ' covers ', ' only ')


class Edit(NamedTuple):
    rule: str
    old: str
    new: str


class Block(NamedTuple):
    """A disclaimer block with its inline tags stood in by one character each (protect())."""
    text: str
    tags: list[str]


def protect(html: str) -> Block:
    tags: list[str] = []

    def one(m: re.Match[str]) -> str:
        tags.append(m.group(0))
        return chr(0xE000 + len(tags) - 1)
    return Block(re.sub(r'<[^>]+>', one, html), tags)


def restore(s: str, tags: list[str]) -> str:
    return re.sub(PH, lambda m: tags[ord(m.group(0)) - 0xE000], s)


def plain(s: str) -> str:
    """The words a reader sees: stand-ins gone, entities decoded."""
    return htmllib.unescape(re.sub(PH, '', s))


def pairs_up(chars: str, tags: list[str]) -> bool:
    """True when the tags stood in by chars open and close in pairs (so removing them all keeps the page sound)."""
    depth: dict[str, int] = {}
    for ch in chars:
        m = re.match(r'<(/?)(\w+)', tags[ord(ch) - 0xE000])
        if m:
            depth[m.group(2)] = depth.get(m.group(2), 0) + (-1 if m.group(1) else 1)
    return not any(depth.values())


def rank_only(s: str) -> bool:
    """True when the sentence (or clause) is about the old ranks and nothing else: it mentions a rank, every other
    word is one a rank note uses (VOCAB), a number, a #rank or a date, and any "market cap" in it starts a rank phrase."""
    s = plain(s)
    if not RANK.search(s) or NEW_RE.search(s) or MCAP_NOT_RANK.search(s):
        return False
    for tok in s.split():
        w = tok.strip('.,;:()[]"\'“”‘’*').lower()
        if w.endswith("'s"):
            w = w[:-2]
        if w not in VOCAB and not TOKEN_SKIP.match(w):
            return False
    return True


def sentences(s: str, tags: list[str] | None = None) -> list[tuple[int, int]]:
    """(start, end) of each sentence in a block: a stop is ., ! or ? followed by whitespace and a capital, a quote or
    a bracket, or by the block's end, unless the word before it is an abbreviation (U.S., est., Inc.). Closing tags
    right after a stop belong to the sentence they close."""
    out, start = [], 0
    for m in re.finditer(r'[.!?](?=(?:\s|' + PH + r')+[A-Z"(“' + PH[1:-1] + r']|(?:\s|' + PH + r')*$)', s):
        if m.end() <= start or (m.group(0) == '.' and ABBR.search(plain(s[start:m.start()])) and plain(s[m.end():]).strip()):
            continue
        end = m.end()
        while tags and end < len(s) and re.match(PH, s[end]) and tags[ord(s[end]) - 0xE000].startswith('</'):
            end += 1
        out.append((start, end))
        start = end
        while start < len(s) and s[start].isspace():
            start += 1
    if plain(s[start:]).strip():
        out.append((start, len(s)))
    return out


def new_clause(date: str, capital: bool) -> str:
    c = NEW_CLAUSE.format(date=date)
    return c if capital else c[0].lower() + c[1:]


def top_level_split(s: str, sep: str = '; ') -> list[str]:
    """s split on sep outside brackets, each part but the last keeping its separator at its end."""
    parts, depth, last, i = [], 0, 0, 0
    while i < len(s):
        depth += {'(': 1, ')': -1}.get(s[i], 0)
        if depth == 0 and s.startswith(sep, i):
            parts.append(s[last:i + len(sep)])
            last = i = i + len(sep)
            continue
        i += 1
    parts.append(s[last:])
    return parts


def in_brackets(s: str, i: int) -> bool:
    return s[:i].count('(') > s[:i].count(')')


def list_head(b: str) -> int:
    """Where the list at the end of b starts: just after its last lead (': ', '— ', '; ', 'including' …), or 0."""
    return max([b.rfind(x) + len(x) for x in LEADS + ('; ',) if b.rfind(x) >= 0] or [0])


# where a list stops: its sentence or clause ends, a relative clause starts, or its verb
LIST_END = re.compile(r'\.(?=\s|$)|;|\s*—|\s*$| (?:are|were)\b|, which\b')


def tidy(s: str, head: int) -> str:
    """A list from head that is down to two items loses its serial comma: 'B, and C' -> 'B and C'."""
    end = head + next((m.start() for m in LIST_END.finditer(s[head:]) if m.start() > 0), len(s) - head)
    seg = s[head:end]
    return s[:head] + seg.replace(', and ', ' and ') + s[end:] if seg.count(', ') == 1 and ', and ' in seg else s


def drop_item(s: str, m: re.Match[str]) -> str | None:
    """s with the list item at m removed and the list's punctuation repaired, or None when the shape is not one of the
    handled ones (the caller lists the sentence instead). Lists end 'B and C' or, with the serial comma, 'B, and C'.
    An item at the start of the sentence ('The NYSE market-cap rank, A and B are estimates') goes too."""
    out = _drop_item(s, m)
    if out is None:
        return None
    head = list_head(s[:m.start()])
    out = tidy(out, head)
    return out[0].upper() + out[1:] if m.start() == 0 and out else out


def _drop_item(s: str, m: re.Match[str]) -> str | None:
    before, after = s[:m.start()], s[m.end():]
    lead = before.endswith(LEADS) or not before
    items_before = before[list_head(before):].count(', ')      # list items ahead of this one
    if after.startswith(', and '):
        if lead:                                               # ': ITEM, and B' -> ': B'
            return before + after[len(', and '):]
        if before.endswith(', '):                              # 'A, ITEM, and B' -> 'A and B'; 'A, C, ITEM, and B' -> 'A, C, and B'
            return before[:-2] + ' and ' + after[len(', and '):] if items_before == 1 else before + after[2:]
        return None
    if after.startswith(', ') and (lead or before.endswith((', ', '; '))):
        return before + after[2:]                              # 'A, ITEM, B' -> 'A, B'
    if after.startswith(' and '):
        if lead:                                               # ': ITEM and B' -> ': B'
            if re.match(r' and [^.;]*? (?:are|were)\b', after):
                return None                                    # 'ITEM and B are …': B alone may need 'is'
            return before + after[len(' and '):]
        if before.endswith(', '):                              # 'A, C, ITEM and B' -> 'A, C and B'
            return before[:-2] + after
        return None
    if after.startswith('; ') and (lead or before.endswith('; ')):
        return before + after[2:]
    if not LIST_END.match(after):
        return None
    if before.endswith('; '):                                  # the last of a semicolon list
        return before[:-2] + after
    verb = not re.match(r'[.;]|\s*—|\s*$', after)              # '..., C and ITEM are estimates': the verb stays plural
    for conj in (', and ', ' and '):                           # the last of a list: '..., C and ITEM.'
        if before.endswith(conj):
            b = before[:-len(conj)]
            k = b.rfind(', ')
            head = list_head(b)
            if k < head:                                       # 'A and ITEM.' -> 'A.'
                return None if verb else b + after
            more = b[head:k].count(', ') > 0
            return b[:k] + (', and ' if more and conj == ', and ' else ' and ') + b[k + 2:] + after
    return None


def place(date: str | None, slot: list[bool], capital: bool) -> str | None:
    """The page's one NEW_CLAUSE when the slot is free (and marks it taken), else None."""
    if date is None or slot[0]:
        return None
    slot[0] = True
    return new_clause(date, capital)


def leftover(s: str) -> bool:
    """True when s still mentions the old ranks (this tool's own clause aside): a rank and an old-rank marker. A
    sentence that cites companiesmarketcap.com for something else (peer market caps) is not one."""
    rest = NEW_RE.sub('', plain(s))
    return bool(OLD.search(rest) and RANK.search(rest))


def rewrite_sentence(s: str, tags: list[str], date: str | None, slot: list[bool]) -> tuple[str | None, list[Edit]]:
    """One sentence (protected text) with its old-rank wording rewritten; None drops it. slot[0] turns True once the
    page's one NEW_CLAUSE is placed. date None: the page is in neither index, so old ranks are removed, never replaced.
    A sentence that would still mention the old ranks, or lose tags that do not pair up, is left as it was (and listed)."""
    taken = slot[0]
    new, edits = _rewrite_sentence(s, date, slot)
    lost = ''.join(c for c in re.findall(PH, s) if new is None or c not in new)
    if edits and ((new is not None and leftover(new)) or not pairs_up(lost, tags)):
        slot[0] = taken
        return s, []
    return new, [Edit(e.rule, restore(e.old, tags), e.new) for e in edits]


def _rewrite_sentence(s: str, date: str | None, slot: list[bool]) -> tuple[str | None, list[Edit]]:
    nm = NEW_RE.search(s)
    if nm:                                                     # this tool's own sentence: keep its date current
        if date is None:
            whole = NEW_RE.fullmatch(plain(s).strip().rstrip('.'))
            return (None, [Edit('own sentence removed', s, '')]) if whole else (s, [])
        slot[0] = True
        return s[:nm.start(1)] + date + s[nm.end(1):], []
    if rank_only(s):
        nc = place(date, slot, True)
        return (nc + '.', [Edit('sentence replaced', s, nc + '.')]) if nc else (None, [Edit('sentence removed', s, '')])
    edits: list[Edit] = []
    parts = top_level_split(s)
    if len(parts) > 1:                                         # '...; Global rank from companiesmarketcap.com; ...'
        kept: list[str] = []
        for i, p in enumerate(parts):
            sep = '; ' if p.endswith('; ') else ''
            body = p[:len(p) - len(sep)]
            stop = body[len(body.rstrip('.')):]
            heading = i == 0 and ':' in body and not RANK.search(body.split(':')[0])   # 'Estimated: A; B; C'
            if heading and sep and rank_only(body.split(':', 1)[1]) and not re.match(r'\s*\(1\)', body.split(':', 1)[1]):
                lead, nxt = body.split(':', 1)[0] + ': ', parts[i + 1]
                parts[i + 1] = lead + nxt                       # 'Flagged: RANKS; A; B' -> 'Flagged: A; B'
                edits.append(Edit('clause removed', body.split(':', 1)[1].strip(), ''))
                continue
            if heading or not rank_only(body.rstrip('.')):
                kept.append(p)
                continue
            nc = place(date, slot, i == 0)
            if nc:
                kept.append(nc + stop + sep)
                edits.append(Edit('clause replaced', body, nc))
                continue
            edits.append(Edit('clause removed', body, ''))
            if not sep and kept:                               # the last clause went: the one before it ends the sentence
                kept[-1] = kept[-1][:-2] + stop
        if not kept:
            return None, edits
        s = ''.join(kept)
        s = s[0].upper() + s[1:]
    for m in reversed(list(SOURCE_ITEM.finditer(s))):
        detail = m.group('paren') if m.group('paren') is not None else m.group('for')
        listed = m.start() == 0 or s[:m.start()].endswith(('; ', ', ', ': ', '— ', ' and '))   # a list item, not prose
        if in_brackets(s, m.start()) or not listed or not rank_only(detail):
            continue
        nc = place(date, slot, m.start() == 0)
        if nc:
            edits.append(Edit('source item replaced', m.group(0), nc))
            s = s[:m.start()] + nc + s[m.end():]
            continue
        dropped = drop_item(s, m)
        if dropped is not None:
            edits.append(Edit('source item removed', m.group(0), ''))
            s = dropped
    while True:
        im = next((m for m in ITEM.finditer(s) if not in_brackets(s, m.start())), None)
        dropped = drop_item(s, im) if im else None
        if im is None or dropped is None:
            break
        edits.append(Edit('list item removed', im.group(0), ''))
        s = dropped
    return s, edits


def fine_print_scope(t: str) -> tuple[int, int] | None:
    """(start, end) of the page's disclaimer: <div class="disclaimer">, <div class="disc"> or else <footer>."""
    m = re.search(r'<div class="(?:disclaimer|disc)\b[^"]*"', t)
    if m:
        return m.start(), div_end(t, m.start())
    m = re.search(r'<footer\b', t)
    e = t.find('</footer>', m.start()) if m else -1
    return (m.start(), e) if m and e > 0 else None


def old_mentions(html: str) -> list[str]:
    """The sentences of html that still mention the old ranks, as a reader sees them."""
    out = []
    for seg in BLOCK.split(html)[::2]:
        b = protect(seg)
        out += [' '.join(plain(b.text[x:y]).split()) for x, y in sentences(b.text, b.tags) if leftover(b.text[x:y])]
    return out


def rewrite_fine_print(t: str, date: str | None) -> tuple[str, list[Edit], list[str]]:
    """(the page with its disclaimer's old-rank wording rewritten, the edits, the old-rank sentences left as they
    were). date None: the page is in neither index."""
    scope = fine_print_scope(t)
    if not scope:
        return t, [], (['(no disclaimer found)'] if OLD.search(t) else [])
    s0, s1 = scope
    pieces = BLOCK.split(t[s0:s1])
    edits: list[Edit] = []
    slot = [False]
    after_item: tuple[int, int] | None = None     # (piece, offset) just after the last sentence a list item left
    for i in range(0, len(pieces), 2):
        seg = pieces[i]
        if not (OLD.search(seg) or NEW_RE.search(seg)):
            continue
        b = protect(seg)
        out, pos = '', 0
        for x, y in sentences(b.text, b.tags):
            sent = b.text[x:y]
            out += b.text[pos:x]
            pos = y
            if not (leftover(sent) or NEW_RE.search(plain(sent))) or not re.search(r'[.!?]' + PH + r'*\s*$', sent):
                out += sent
                continue
            new, ed = rewrite_sentence(sent.rstrip(), b.tags, date, slot)
            edits += ed
            if new is None:                                    # dropped, with the space after it
                while pos < len(b.text) and b.text[pos] == ' ':
                    pos += 1
                continue
            out += new + sent[len(sent.rstrip()):]
            if any(e.rule == 'list item removed' for e in ed):
                after_item = (i, len(restore(out.rstrip(), b.tags)))
        out += b.text[pos:]
        if b.text.strip() and not plain(out).strip():
            out = ''
        new_seg = restore(out if seg[-1:] == ' ' or not out.strip() else out.rstrip(' '), b.tags)
        if new_seg.strip() or not seg.strip():
            pieces[i] = new_seg
        elif i >= 2 and i + 1 < len(pieces) and re.match(r'<p\b', pieces[i - 1]) and pieces[i + 1] == '</p>':
            pieces[i - 1] = pieces[i] = pieces[i + 1] = ''       # a paragraph left empty goes, with its line
            if i + 2 < len(pieces):
                pieces[i + 2] = re.sub(r'^\n?[ \t]*', '', pieces[i + 2], count=1)
        else:
            pieces[i] = new_seg
    if after_item and not slot[0]:
        nc = place(date, slot, True)
        if nc:
            i, at = after_item
            pieces[i] = pieces[i][:at] + ' ' + nc + '.' + pieces[i][at:]
            edits.append(Edit('sentence added after a removed list item', '', nc + '.'))
    body = ''.join(pieces)
    return t[:s0] + body + t[s1:], edits, old_mentions(body)


# ---------- the run ----------

def long_date(iso: str) -> str:
    d = datetime.date.fromisoformat(iso)
    return f'{d:%B} {d.day}, {d.year}'


def main(argv: list[str] | None = None) -> int | str:
    ap = rd.parser('Write each stock report\'s S&P 500 / Nasdaq-100 market-cap rank on its banner date.')
    ap.add_argument('slugs', nargs='*', help='report slugs (default: every stock report)')
    ap.add_argument('--check', action='store_true', help='change nothing; exit 1 when a row differs from what would be written')
    ap.add_argument('--dry-run', action='store_true', help='change nothing; print the edits')
    ap.add_argument('--top', metavar='DATE', help='also print the S&P 500 top 15 on DATE (YYYY-MM-DD)')
    args = ap.parse_args(argv)
    repo = args.repo
    members, errs = index_members(repo)
    slugs = args.slugs or [rd.slug_of(p) for p in rd.report_paths(repo)]
    pages = {}
    for slug in slugs:
        path = rd.report_path(slug, repo=repo)
        if not os.path.exists(path):
            errs.append(f'{slug}: no page')
            continue
        t = rl.read_text(path)
        a = rl.as_of(t)[0]
        if slug in members and not a:
            errs.append(f'{slug}: no as-of date')
            continue
        pages[slug] = (path, t, a)
    # the dates every member's series must reach (--top is a sanity print: it takes each last close on or before its date)
    need = sorted({a for _, _, a in pages.values() if a} | {m.as_of for m in members.values()})
    if not need:
        return 'nothing to do'
    series: dict[str, rf.Daily] = {}
    for slug, m in sorted(members.items()):
        try:
            series[slug] = daily_closes(m.symbol, need[0], need[-1])
        except ca.YahooError as e:
            errs.append(f'{slug} ({m.symbol}): yahoo {e}')
    flags = [f for s, m in sorted(members.items()) if s in series for f in member_flags(m, series[s])]
    if errs:
        print('ERRORS (nothing written):')
        print('\n'.join('  ' + e for e in errs))
        return 1
    memo: dict[tuple[str, str], dict[str, float]] = {}
    if args.top:
        caps = index_caps('sp500', args.top, members, series)
        print(f'S&P 500 top 15 on {args.top} (our calculation):')
        for i, (s, c) in enumerate(sorted(caps.items(), key=lambda kv: -kv[1])[:15], 1):
            print(f'  {i:2} {s:6} ${c / 1e12:.3f}T')
    counts: dict[str, int] = {}
    rules: dict[str, int] = {}
    left_pages, row_diff, changed = [], [], []
    for slug, (path, t, a) in sorted(pages.items()):
        try:
            ranks = ranks_on(slug, a, members, series, memo) if slug in members and a else {}
            new, what = write_row(t, ranks)
        except RankError as e:
            errs.append(f'{slug}: {e}')
            continue
        counts[what] = counts.get(what, 0) + 1
        if new != t:
            row_diff.append(slug)
        if args.check:
            continue
        new, edits, left = rewrite_fine_print(new, long_date(a) if ranks and a else None)
        for e in edits:
            rules[e.rule] = rules.get(e.rule, 0) + 1
            if args.dry_run:
                print(f'  {slug}: {e.rule}: {e.old!r} -> {e.new!r}')
        if left:
            left_pages.append((slug, left))
        if new != t:
            changed.append(slug)
            if not args.dry_run:
                rl.write_text(path, new)
    if errs:
        print('ERRORS:')
        print('\n'.join('  ' + e for e in errs))
    print('rows:', ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    print(f'members: {len(members)} (S&P 500 {sum(m.sp500 for m in members.values())}, Nasdaq-100 '
          f'{sum(m.ndx for m in members.values())}); implied shares checked against a Shares Outstanding row on '
          f'{sum(1 for m in members.values() if m.stated_shares)}')
    print('flags:', len(flags))
    print('\n'.join('  ' + f for f in flags))
    if args.check:
        print(f'rows that differ from what would be written: {len(row_diff)}', row_diff[:40])
        return 1 if row_diff or errs else 0
    print('fine print:', ', '.join(f'{k} {v}' for k, v in sorted(rules.items())))
    print(f'pages {"that would change" if args.dry_run else "written"}: {len(changed)}')
    print(f'old-rank mentions left in the fine print: {sum(len(x) for _, x in left_pages)} on {len(left_pages)} pages')
    for slug, left in left_pages:
        for s in left:
            print(f'  LEFT {slug}: {s[:220]}')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
