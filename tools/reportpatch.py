"""Targeted, count-checked writers for the structured fields of a report page: the mirror of reportlib's readers.
Imported by tools/refresh_data.py; not run on its own.

Each writer takes the page text and returns the new text. It changes one field, on the template's own markup, and
nothing else; it raises PatchError, naming the page and the field, unless the markup it needs is there exactly once
(a writer that matched twice, or guessed, would change the wrong number silently). Prose is never touched:
refresh_data.py lists the prose that still carries an old value (stale_hits.txt) for the builder.

Fields: header price (set_header_price), the day's change (set_header_change), the "Static data as of" banner and its
copies (set_banner_date), the chart's labels and prices arrays (set_chart_series) and its events when the oldest
points are dropped (shift_events), the metrics-table 52-week range
(set_range_52w) and any metrics-table value cell (set_fin_row, set_fin_number). Chart labels are read and written
with point_label / format_label, which know the library's label styles ('Sep 21', 'Sep \\'21', 'Sep 2021',
'Oct 1 26', 'Sep 10 \\'26', 'Sep 21, 2026', '18 Sep 26', 'Sep 26*').
"""
import datetime
import re
from typing import Callable, Literal, NamedTuple, Sequence, TypeVar

import reportlib as rl


class PatchError(ValueError):
    """A writer could not find its markup exactly once; nothing was changed."""

    def __init__(self, page: str, field: str, why: str) -> None:
        super().__init__(f'{page or "page"}: {field}: {why}')
        self.page, self.field, self.why = page, field, why


MON3 = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
FULL_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
               'November', 'December']
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MINUS = '\u2212'   # the library's minus sign


# ---------- numbers ----------

_NUMBER = re.compile(r'\d[\d,]*(?:\.\d+)?')


def format_like(old: str, value: float) -> str:
    """value written the way the number old was: the same decimals, and thousands commas when old has them or is
    under 1,000 (a four-figure number written without commas stays without)."""
    dec = len(old.split('.')[1]) if '.' in old else 0
    plain = old.replace(',', '')
    comma = ',' in old or float(plain) < 1000
    return f'{value:,.{dec}f}' if comma else f'{value:.{dec}f}'


def money(value: float, like: str = '') -> str:
    """A price to the cent, no $: 12345.6 -> '12,345.60', or '12345.60' when the number it replaces (like) is a
    four-figure price written without commas."""
    plain = like.replace(',', '')
    if like and ',' not in like and rl.to_number(plain) is not None and float(plain) >= 1000:
        return f'{value:.2f}'
    return f'{value:,.2f}'


def _once(pattern: re.Pattern[str], t: str, page: str, field: str) -> re.Match[str]:
    found = list(pattern.finditer(t))
    if len(found) != 1:
        raise PatchError(page, field, f'expected the markup exactly once, found it {len(found)} times')
    return found[0]


def _splice(t: str, start: int, end: int, new: str) -> str:
    return t[:start] + new + t[end:]


# ---------- header ----------

# reportlib.header_price's patterns, in its order: the first class present is the header price
_HEADER_PRICE = [re.compile(p + r'(\$?)([\d,]+\.\d+)') for p in
                 (r'class="price-current"[^>]*>\s*', r'class="price[ "][^>]*>\s*', r'class="price-now[ "][^>]*>\s*')]


def set_header_price(t: str, price: float, page: str = '') -> str:
    """The header price (the one reportlib.header_price reads), to the cent."""
    for pat in _HEADER_PRICE:
        if pat.search(t):
            m = _once(pat, t, page, 'header price')
            return _splice(t, m.start(2), m.end(2), money(price, m.group(2)))
    raise PatchError(page, 'header price', 'no price-current / price / price-now element')


_CHANGE = re.compile(r'<(div|span) class="((?:price-change|price-chg|chg)(?: [^"]*)?)"([^>]*)>(.*?)</\1>', re.S)
_DOLLAR = re.compile(r'([+\u2212\-]|&minus;)?\$([\d,]+\.\d+)')
_PCT = re.compile(r'\(([+\u2212\-]|&minus;)?(\d+(?:\.\d+)?)%\)')
_COLOR = re.compile(r'color:\s*var\(--(?:green|red|text-muted)\)')


def set_header_change(t: str, change: float, pct: float, page: str = '',
                      dates: tuple[str, str] | None = None) -> str:
    """The day's change under the header price: '+$0.53 (+2.16%)' and its colour (green up, red down, through the
    element's style or its up/down, pos/neg class). dates=(old ISO date, new ISO date) also moves a 'Sep 18, 2026
    close' stamp inside the element. An element with more than one dollar amount or percentage (a prose variant) is
    left to the builder: PatchError."""
    m = _once(_CHANGE, t, page, 'price change')
    tag, cls, attrs, inner = m.group(1), m.group(2), m.group(3), m.group(4)
    dollars, pcts = list(_DOLLAR.finditer(inner)), list(_PCT.finditer(inner))
    if len(dollars) != 1 or len(pcts) != 1:
        raise PatchError(page, 'price change', f'{len(dollars)} dollar amounts and {len(pcts)} percentages in the '
                         'element (expected one of each)')
    if change and 'unchanged' in inner:
        raise PatchError(page, 'price change', 'the element says "unchanged"')
    minus = '&minus;' if '&minus;' in inner else ('-' if re.search(r'-\$', inner) else MINUS)
    sign = '+' if change > 0 else (minus if change < 0 else '')
    d, p = dollars[0], pcts[0]
    # replace the later match first so the earlier one's offsets stay valid
    parts = sorted([(d.start(), d.end(), f'{sign}${money(abs(change))}'),
                    (p.start(), p.end(), f'({sign}{format_like(p.group(2), abs(pct))}%)')], reverse=True)
    for s, e, new in parts:
        inner = _splice(inner, s, e, new)
    up = change > 0
    inner = inner.replace('\u25bc' if up else '\u25b2', '\u25b2' if up else '\u25bc') if change else inner
    if dates:
        inner = replace_dates(inner, dates[0], dates[1])
    tokens = cls.split()
    swap = {'up': 'down', 'down': 'up', 'pos': 'neg', 'neg': 'pos'}
    want = {'up', 'pos'} if up else {'down', 'neg'}
    tokens = [tok if tok not in swap or tok in want or not change else swap[tok] for tok in tokens]
    colour = 'green' if change > 0 else ('red' if change < 0 else 'text-muted')
    if _COLOR.search(attrs):
        attrs = _COLOR.sub(f'color:var(--{colour})', attrs)
    elif tokens == ['price-change'] and change > 0:   # the stylesheet's default is red
        attrs += ' style="color:var(--green);"'
    return _splice(t, m.start(), m.end(), f'<{tag} class="{" ".join(tokens)}"{attrs}>{inner}</{tag}>')


# ---------- dates ----------

_MONTH_RE = '|'.join(FULL_MONTHS + ['Sept'] + MON3)
_WDAY_RE = '|'.join(WEEKDAYS)


def _date_pattern(iso: str) -> re.Pattern[str]:
    """'2026-09-18' -> 'September 18, 2026' / 'Sep 18, 2026' / 'Sept. 18, 2026', any case."""
    d = datetime.date.fromisoformat(iso)
    names = [FULL_MONTHS[d.month - 1], MON3[d.month - 1]] + (['Sept'] if d.month == 9 else [])
    return re.compile(r'\b(' + '|'.join(names) + r')(\.?) ' + str(d.day) + r', ' + str(d.year) + r'\b', re.I)


def render_date(iso: str, like: str, full_if_may: bool = False) -> str:
    """The date written like the month token like: full or abbreviated, and upper case when like is. 'May' is both;
    full_if_may decides it."""
    d = datetime.date.fromisoformat(iso)
    full = len(like.rstrip('.')) > 4 or like.lower() in ('june', 'july') or (like.lower() == 'may' and full_if_may)
    name = FULL_MONTHS[d.month - 1] if full else MON3[d.month - 1]
    text = f'{name} {d.day}, {d.year}'
    return text.upper() if like.isupper() and len(like) > 1 else text


def replace_dates(s: str, old_iso: str, new_iso: str) -> str:
    """Every 'Month D, YYYY' form of old_iso in s rewritten as new_iso in the same style."""
    return _date_pattern(old_iso).sub(lambda m: render_date(new_iso, m.group(1)), s)


_BANNER = re.compile(r'(static data as of (?:the )?)(?:(' + _WDAY_RE + r'),? )?(' + _MONTH_RE + r')(\.?) (\d{1,2}), (\d{4})'
                     r'(\s*\((?:' + _WDAY_RE + r')\b)?', re.I)


def set_banner_date(t: str, old_iso: str, new_iso: str, page: str = '') -> tuple[str, int]:
    """The "Static data as of <date>" banner (the statement reportlib.as_of reads: the first one) and every copy of
    it carrying the same date (the chart headings' "STATIC DATA AS OF AUG 18, 2026"), each in its own style, with
    the weekday beside it ("(Friday settled close") recomputed. Returns (text, copies changed besides the banner).
    PatchError when the banner is missing, gives a range, or does not carry old_iso."""
    first = re.search(r'static data as of', t, re.I)
    found = list(_BANNER.finditer(t))
    if not first or not found or found[0].start() != first.start() or not t[first.start():].startswith('Static'):
        raise PatchError(page, 'banner date', 'no "Static data as of <Month D, YYYY>" banner (a date range?)')
    new = datetime.date.fromisoformat(new_iso)
    wday = WEEKDAYS[new.weekday()]

    def same_case(word: str, like: str) -> str:
        return word.upper() if like.isupper() else word

    hits = 0
    out, pos = [], 0
    for i, m in enumerate(found):
        mon = m.group(3)
        month = rl.MONTHS.get(mon.capitalize()) or rl.MONTHS.get(mon[:3].capitalize())
        if not month or datetime.date(int(m.group(6)), month, int(m.group(5))).isoformat() != old_iso:
            if i == 0:
                raise PatchError(page, 'banner date', f'the banner is not dated {old_iso}')
            continue
        text = m.group(1) + (same_case(wday, m.group(2)) + ', ' if m.group(2) else '') + render_date(new_iso, mon, i == 0)
        if m.group(7):
            text += re.sub(_WDAY_RE, same_case(wday, m.group(7).strip(' (')), m.group(7), flags=re.I)
        out.append(t[pos:m.start()] + text)
        pos = m.end()
        hits += 1
    return ''.join(out) + t[pos:], hits - 1


# ---------- chart labels ----------

LabelKind = Literal['month', 'mon-day', 'day-mon']


class LabelStyle(NamedTuple):
    kind: LabelKind
    sep: str          # between month (or day) and year: ' ', " '", "'", '-', ', '
    year_digits: int  # 2 or 4
    suffix: str       # '*' on a part-month point, ' (debut)' …


class PointLabel(NamedTuple):
    year: int
    month: int
    day: int | None
    style: LabelStyle


_LABEL_MONTH = re.compile(r"^(?P<mon>[A-Z][a-z]{2})(?P<sep>\s*'|\s+|-)(?P<yr>\d{4}|\d{2})(?P<suf>\*?)$")
_LABEL_MON_DAY = re.compile(r"^(?P<mon>[A-Z][a-z]{2}) (?P<d>\d{1,2})(?P<sep>,? '?|,? )(?P<yr>\d{4}|\d{2})(?P<suf>.*)$")
_LABEL_DAY_MON = re.compile(r"^(?P<d>\d{1,2}) (?P<mon>[A-Z][a-z]{2})(?P<sep> '?)(?P<yr>\d{4}|\d{2})(?P<suf>.*)$")
_MON_INDEX = {m: i + 1 for i, m in enumerate(MON3)}


def point_label(s: str) -> PointLabel | None:
    """A chart label read as (year, month, day or None, style): 'Sep 21' and "Sep '21" are a month,
    'Oct 1 26', "Sep 10 '26", 'Sep 21, 2026' and '18 Sep 26' a day. None for anything else."""
    s = s.strip()
    forms: tuple[tuple[LabelKind, re.Pattern[str]], ...] = (
        ('month', _LABEL_MONTH), ('mon-day', _LABEL_MON_DAY), ('day-mon', _LABEL_DAY_MON))
    for kind, pat in forms:
        m = pat.match(s)
        if m and m.group('mon') in _MON_INDEX:
            yr = m.group('yr')
            year = int(yr) + (2000 if len(yr) == 2 else 0)
            day = int(m.group('d')) if kind != 'month' else None
            style = LabelStyle(kind, m.group('sep'), len(yr), m.group('suf'))
            return PointLabel(year, _MON_INDEX[m.group('mon')], day, style)
    return None


def format_label(style: LabelStyle, year: int, month: int, day: int | None = None) -> str:
    """A label for (year, month[, day]) in style; a month style given a day writes the month only."""
    yr = f'{year % 100:02d}' if style.year_digits == 2 else str(year)
    mon = MON3[month - 1]
    if style.kind == 'mon-day' and day:
        return f'{mon} {day}{style.sep}{yr}{style.suffix}'
    if style.kind == 'day-mon' and day:
        return f'{day} {mon}{style.sep}{yr}{style.suffix}'
    return f'{mon}{style.sep}{yr}{style.suffix}'


# ---------- chart arrays ----------

LABELS_ARRAY = re.compile(r'((?:const|let|var)\s+labels\s*=\s*\[)(.*?)(\]\s*;)', re.S)
PRICES_ARRAY = re.compile(r'((?:const|let|var)\s+prices\s*=\s*\[)(.*?)(\]\s*;)', re.S)
_ANY_ARRAY = re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*\[(.*?)\]\s*;', re.S)
_STRING = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`[^`]*`')

T = TypeVar('T')


def _label_elements(body: str) -> list[tuple[int, int, str]]:
    """(start, end, value) of every quoted string in an array body, unescaped as reportlib reads them."""
    return [(m.start(), m.end(), rl._labels(m.group(0))[0]) for m in _STRING.finditer(body)]


def _price_elements(body: str, page: str) -> list[tuple[int, int, float]]:
    out = []
    for m in re.finditer(r'[^,]+', body):
        raw = m.group(0)
        if not raw.strip():
            continue
        v = rl.to_number(raw.strip())
        if v is None:
            raise PatchError(page, 'chart', f'a prices entry is not a number ({raw.strip()[:20]!r})')
        lead = len(raw) - len(raw.lstrip())
        out.append((m.start() + lead, m.start() + lead + len(raw.strip()), v))
    return out


def _rewrite(body: str, elems: Sequence[tuple[int, int, T]], new: Sequence[T], render: Callable[[T], str],
             same: Callable[[T, T], bool], drop: int = 0) -> str:
    """The array body with new values, element by element: the first `drop` elements are removed with the text up to
    the next one; each remaining old element pairs with the new value at its position and keeps its text (spacing,
    line breaks) when the value is the same, else is rewritten in place; old elements beyond the new values are
    removed, and new values beyond the old elements are appended with the array's own separator."""
    if not elems:
        lead = len(body) - len(body.lstrip())
        return body[:lead] + ','.join(render(v) for v in new) + body[lead:]
    seps = [body[elems[i][1]:elems[i + 1][0]] for i in range(len(elems) - 1)]
    flat = [s for s in seps if '\n' not in s]
    sep = flat[-1] if flat else ','
    kept = list(elems[drop:])
    n = min(len(kept), len(new))
    parts = [body[:elems[0][0]]]
    for j in range(n):
        s, e, v = kept[j]
        if j:
            parts.append(body[kept[j - 1][1]:s])
        parts.append(body[s:e] if same(v, new[j]) else render(new[j]))
    parts += [(sep if j else '') + render(new[j]) for j in range(n, len(new))]
    return ''.join(parts) + body[elems[-1][1]:]


def _quote(s: str, q: str) -> str:
    if q == '`':
        return f'`{s}`'
    return q + s.replace('\\', '\\\\').replace(q, '\\' + q) + q


def set_chart_series(t: str, labels: Sequence[str], prices: Sequence[float], page: str = '', drop: int = 0) -> str:
    """The main chart's labels and prices arrays. The page must define each exactly once, and no other hard-coded
    array may run parallel to them (one page carries ma3/ma10/rsi arrays of the same length: extending the prices
    alone would put them out of step). New prices are written to the cent; unchanged entries keep their text.
    drop = how many of the page's oldest points the new series leaves out (the window trim; the events move with
    shift_events)."""
    if len(labels) != len(prices):
        raise PatchError(page, 'chart', f'{len(labels)} labels for {len(prices)} prices')
    ml = _once(LABELS_ARRAY, t, page, 'chart labels')
    mp = _once(PRICES_ARRAY, t, page, 'chart prices')
    lab_el = _label_elements(ml.group(2))
    pr_el = _price_elements(mp.group(2), page)
    for m in _ANY_ARRAY.finditer(t):
        if m.group(1) not in ('labels', 'prices') and '{' not in m.group(2) and \
                len([x for x in m.group(2).split(',') if x.strip()]) == len(pr_el):
            raise PatchError(page, 'chart', f'hard-coded array {m.group(1)!r} runs parallel to the prices')
    if drop and not 0 < drop < min(len(lab_el), len(pr_el)):
        raise PatchError(page, 'chart', f'cannot drop {drop} of {len(pr_el)} points')
    q = ml.group(2)[lab_el[0][0]] if lab_el else "'"
    new_l = _rewrite(ml.group(2), lab_el, list(labels), lambda s: _quote(s, q), lambda a, b: a == b, drop)
    new_p = _rewrite(mp.group(2), pr_el, [round(p, 2) for p in prices], lambda v: f'{v:.2f}',
                     lambda a, b: abs(a - b) < 1e-9, drop)
    edits = sorted([(ml.start(2), ml.end(2), new_l), (mp.start(2), mp.end(2), new_p)], reverse=True)
    for s, e, new in edits:
        t = _splice(t, s, e, new)
    got_l, got_p = rl.chart_series(t)
    if got_l != list(labels) or got_p is None or [round(p, 2) for p in got_p] != [round(p, 2) for p in prices]:
        raise PatchError(page, 'chart', 'the rewritten arrays do not read back as written')
    return t


# ---------- chart events (the annotated points, by index into the chart arrays) ----------

# The library's two forms (surveyed 2 Oct 2026): an array of objects with an `idx` field (`const events = [{ idx: 4,
# label: '…', color: '…' }, …]`, 541 pages) and an object keyed by index (`const events = {2: "…", …}` on DOW, HD, UNH;
# `const eventIdx = {2: "…", …}` on GWW). Everything else the pages do with events derives from these.
EVENTS_DEF = re.compile(r'(?:const|let|var)\s+(events|eventIdx)\s*=\s*([\[{])')
# a chart index written as a number outside the events (FISV: `if (i === 51) notes.push(…)`); 0 is harmless
_HARD_INDEX = re.compile(r'\b(?:i|idx|index|dataIndex)\s*[!=]==?\s*([1-9]\d*)\b')
_SCRIPT = re.compile(r'<script\b[^>]*>(.*?)</script>', re.S | re.I)


def _js_marks(s: str, start: int, end: int) -> list[tuple[int, str]]:
    """(position, char) of the brackets and commas of JavaScript source s[start:end], outside strings, template
    literals and comments."""
    out = []
    i = start
    while i < end:
        c = s[i]
        if c in '\'"`':
            j = i + 1
            while j < end and s[j] != c:
                j += 2 if s[j] == '\\' else 1
            i = j + 1
            continue
        if s.startswith('//', i):
            j = s.find('\n', i, end)
            i = end if j < 0 else j
            continue
        if s.startswith('/*', i):
            j = s.find('*/', i + 2, end)
            i = end if j < 0 else j + 2
            continue
        if c in '[]{}(),':
            out.append((i, c))
        i += 1
    return out


def _closing(s: str, open_pos: int) -> int:
    """The position of the bracket that closes the one at open_pos."""
    depth = 0
    for i, c in _js_marks(s, open_pos, len(s)):
        if c in '[{(':
            depth += 1
        elif c in ']})':
            depth -= 1
            if depth == 0:
                return i
    raise ValueError('unclosed bracket')


def _skip_blank(s: str, i: int, end: int) -> int:
    """The first position from i that is not whitespace or a comment."""
    while i < end:
        if s[i].isspace():
            i += 1
        elif s.startswith('//', i):
            j = s.find('\n', i, end)
            i = end if j < 0 else j
        elif s.startswith('/*', i):
            j = s.find('*/', i + 2, end)
            i = end if j < 0 else j + 2
        else:
            break
    return i


def _items(s: str, a: int, b: int) -> list[tuple[int, int]]:
    """(start, end) of each top-level comma-separated item of s[a:b], without the blank text around it."""
    cuts, depth = [a], 0
    for i, c in _js_marks(s, a, b):
        if c in '[{(':
            depth += 1
        elif c in ']})':
            depth -= 1
        elif c == ',' and depth == 0:
            cuts.append(i + 1)
    out = []
    for x, y in zip(cuts, cuts[1:] + [b + 1]):
        start, stop = _skip_blank(s, x, y - 1), y - 1
        while stop > start and s[stop - 1].isspace():
            stop -= 1
        if stop > start:
            out.append((start, stop))
    return out


_IDX = re.compile(r'\bidx\s*:\s*(\d+)')
_KEY = re.compile(r'(\d+)(\s*:)')
_TEXT = re.compile(r'"((?:\\.|[^"\\])*)"|\'((?:\\.|[^\'\\])*)\'|`([^`]*)`')


def _event_label(text: str, form: str, m: re.Match[str]) -> str:
    """An event's text: its label field (array form) or its value (keyed form); the whole item if neither reads."""
    if form == '[':
        lm = re.search(r'\blabel\s*:\s*', text)
        rest = text[lm.end():] if lm else ''
    else:
        rest = text[m.end():].lstrip()
    s = _TEXT.match(rest)
    return next(g for g in s.groups() if g is not None) if s else text


def shift_events(t: str, k: int, page: str = '') -> tuple[str, int, list[dict]]:
    """The chart events moved k points to the left, for a chart that lost its k oldest points: every index minus k;
    an event whose index falls below 0 is removed (with its separator). Returns (text, events kept, events removed as
    {'idx', 'label'}). A page without events is returned as it is. PatchError when the events are defined more than
    once, an item has no single index, or a script compares a chart index with a number outside the events (it would
    point at the wrong month)."""
    defs = list(EVENTS_DEF.finditer(t))
    if not defs or not k:
        return t, 0, []
    if len(defs) != 1:
        raise PatchError(page, 'events', f'{len(defs)} event definitions (expected one)')
    d = defs[0]
    open_pos = d.end() - 1
    try:
        close = _closing(t, open_pos)
    except ValueError as e:
        raise PatchError(page, 'events', str(e)) from e
    for sm in _SCRIPT.finditer(t):
        for h in _HARD_INDEX.finditer(sm.group(1)):
            pos = sm.start(1) + h.start()
            if not open_pos <= pos <= close:
                raise PatchError(page, 'events', f'a script compares a chart index with {h.group(1)} '
                                 f'({h.group(0)!r}) outside the events')
    form = d.group(2)
    items = _items(t, open_pos + 1, close)
    kept_text: list[str] = []
    kept_pos: list[int] = []
    dropped: list[dict] = []
    for n, (s, e) in enumerate(items):
        text = t[s:e]
        if form == '[':
            hits = list(_IDX.finditer(text)) if text.startswith('{') and text.endswith('}') else []
            if len(hits) != 1:
                raise PatchError(page, 'events', f'item {n} has {len(hits)} idx fields: {text[:60]!r}')
            m = hits[0]
        else:
            m = _KEY.match(text)
            if not m:
                raise PatchError(page, 'events', f'item {n} is not keyed by an index: {text[:60]!r}')
        old = int(m.group(1))
        if old - k < 0:
            dropped.append({'idx': old, 'label': _event_label(text, form, m)})
            continue
        kept_text.append(text[:m.start(1)] + str(old - k) + text[m.end(1):])
        kept_pos.append(n)
    if not items:
        return t, 0, []
    body: list[str] = [t[open_pos + 1:items[0][0]]]
    for j, (n, text) in enumerate(zip(kept_pos, kept_text)):
        body.append(text)
        if j < len(kept_pos) - 1:
            body.append(t[items[n][1]:items[n + 1][0]])
    body.append(t[items[-1][1]:close])
    return _splice(t, open_pos + 1, close, ''.join(body)), len(kept_text), dropped


# ---------- metrics table ----------

_ROW = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
_CELL = re.compile(r'<(t[dh])([^>]*)>(.*?)</t[dh]>', re.S)


def _fin_regions(t: str) -> list[tuple[int, int]]:
    """The spans of the .fin-table tables (reportlib.fin_table's scope), else the whole page (HD, UNH)."""
    spans = [(m.start(), m.end()) for m in re.finditer(r'<table class="fin-table"[^>]*>.*?</table>', t, re.S)]
    return spans or [(0, len(t))]


def fin_cells(t: str, label: str) -> list[tuple[int, int, str]]:
    """(start, end, inner HTML) of the value cell (the second, a <td>) of every metrics-table row whose label text
    matches the regex label (re.match, any case)."""
    out = []
    for a, b in _fin_regions(t):
        for row in _ROW.finditer(t, a, b):
            cells = list(_CELL.finditer(row.group(1)))
            if len(cells) < 2 or cells[1].group(1) != 'td':
                continue
            text = re.sub(r'\s+', ' ', rl.strip_tags(cells[0].group(3)))
            if re.match(label, text, re.I):
                base = row.start(1)
                out.append((base + cells[1].start(3), base + cells[1].end(3), cells[1].group(3)))
    return out


def fin_row_texts(t: str, label: str) -> list[str] | None:
    """The text of every cell of the one metrics-table row labelled label (re.match, any case); None when there is
    not exactly one such row."""
    hits = []
    for a, b in _fin_regions(t):
        for row in _ROW.finditer(t, a, b):
            cells = [re.sub(r'\s+', ' ', rl.strip_tags(c.group(3))) for c in _CELL.finditer(row.group(1))]
            if len(cells) >= 2 and re.match(label, cells[0], re.I):
                hits.append(cells)
    return hits[0] if len(hits) == 1 else None


def fin_cell(t: str, label: str, page: str = '') -> tuple[int, int, str]:
    """The one value cell of the row labelled label; PatchError when there is none or more than one."""
    cells = fin_cells(t, label)
    if len(cells) != 1:
        raise PatchError(page, f'row {label!r}', f'expected one metrics-table row, found {len(cells)}')
    return cells[0]


def set_fin_row(t: str, label: str, value_html: str, page: str = '') -> str:
    """The whole value cell of the row labelled label (its <td> attributes, e.g. a colour, are kept)."""
    s, e, _ = fin_cell(t, label, page)
    return _splice(t, s, e, value_html)


def _text_numbers(inner: str) -> list[re.Match[str]]:
    """Numbers in the text of a cell, not inside its tags or attributes (a tooltip's title can hold numbers)."""
    out: list[re.Match[str]] = []
    for tok in re.finditer(r'<[^>]*>|[^<]+', inner):
        if not tok.group(0).startswith('<'):
            out += _NUMBER.finditer(inner, tok.start(), tok.end())
    return out


def set_fin_number(t: str, label: str, value: float, page: str = '') -> str:
    """The first number in the value cell of the row labelled label, written like the number it replaces ('11.36'
    -> '11.04', '24.1x' -> '23.9x', '2.42%' -> '2.39%'). PatchError when the cell has no number (n/m, None)."""
    s, e, inner = fin_cell(t, label, page)
    nums = _text_numbers(inner)
    if not nums or re.search(r'\bn/?[ma]\b', rl.strip_tags(inner), re.I):
        raise PatchError(page, f'row {label!r}', f'no number in the cell ({rl.strip_tags(inner)[:20]!r})')
    n = nums[0]
    return _splice(t, s + n.start(), s + n.end(), format_like(n.group(0), value))


RANGE_LABEL = r'52[- ]Week Range'


def set_range_52w(t: str, low: float, high: float, page: str = '') -> str:
    """The metrics table's 52-week range cell: '$21.45 – $34.03' (the two prices, nothing else)."""
    s, e, inner = fin_cell(t, RANGE_LABEL, page)
    nums = [m for m in _text_numbers(inner) if '.' in m.group(0)]
    if len(nums) != 2:
        raise PatchError(page, '52-week range', f'{len(nums)} prices in the cell (expected 2)')
    for m, v in sorted(zip(nums, (low, high)), key=lambda x: -x[0].start()):
        inner = _splice(inner, m.start(), m.end(), money(v, m.group(0)))
    return _splice(t, s, e, inner)
