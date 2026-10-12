"""Key terms on the lesson pages (Oki, 12 Oct 2026).

Each lesson lists its 3-5 key terms in data/lesson_terms.json as [glossary id, phrase as it appears in the text].
This tool, for every lesson:
  - highlights the phrase where it first appears in the lesson's running text (not in headings, the contents list,
    links other than glossary links, or the interactive widget) with a tooltip: the first sentence of the term's
    definition in data/glossary_finance.json. A glossary link already on that phrase is replaced by the highlight.
  - writes a "Terms in this lesson" list after the contents: a sidebar on wide screens, a collapsed box on phones,
    each term linking to its full Table Talk entry.
Rerunning is safe: it removes its own markup first.

    py -3 tools/lesson_terms.py           rewrite the lesson pages
    py -3 tools/lesson_terms.py --check   exit 1 if any page is out of date or a phrase isn't found (run_checks)
"""
from __future__ import annotations

import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LESSONS = os.path.join(ROOT, 'learn', 'lessons')
TERMS = os.path.join(ROOT, 'data', 'lesson_terms.json')
GLOSSARY = os.path.join(ROOT, 'data', 'glossary_finance.json')
GLOSS_URL = '/learn/table-talk/finance.html'
MAX_TERMS = 5

START = '<!-- lesson-terms: written by tools/lesson_terms.py from data/lesson_terms.json; edit those, not this -->'
END = '<!-- /lesson-terms -->'
BLOCK_RE = re.compile(r'\n?' + re.escape(START) + r'.*?' + re.escape(END), re.S)
TERM_RE = re.compile(r'<span class="term" tabindex="0">(.*?)<span class="tip" role="tooltip">[^<]*</span></span>', re.S)
TOC_END = '</ol></nav>'
SKIP_TAGS = {'h1', 'h2', 'h3', 'nav', 'aside', 'details', 'script', 'style', 'svg', 'label', 'select', 'option', 'button',
             'figure', 'table'}
SKIP_CLASSES = {'widget', 'formula', 'next', 'callout', 'toc', 'term', 'tip'}
VOID = {'br', 'img', 'input', 'hr', 'meta', 'link', 'wbr'}


def first_sentence(text: str) -> str:
    m = re.search(r'^(.+?[.!?])(\s|$)', text)
    return (m.group(1) if m else text).strip()


def strip_own(page: str) -> str:
    page = BLOCK_RE.sub('', page)
    return TERM_RE.sub(r'\1', page)


def find(page: str, start: int, stop: int, phrase: str):
    """First place `phrase` appears in eligible running text between start and stop: (text_start, text_end, anchor)
    where anchor is the (start, end) of a glossary link wrapping it, or None."""
    pat = re.compile(r'(?<![\w-])' + re.escape(html.escape(phrase, quote=False)) + r'(?![\w-])', re.I)
    stack: list[tuple[str, str, int]] = []          # (tag, class, start offset)
    for tok in re.finditer(r'<[^>]+>|[^<]+', page[start:stop]):
        s, raw = start + tok.start(), tok.group(0)
        if raw.startswith('<'):
            m = re.match(r'</?\s*([a-zA-Z0-9]+)', raw)
            if not m or raw.startswith('<!'):
                continue
            tag = m.group(1).lower()
            if raw.startswith('</'):
                while stack and stack[-1][0] != tag:
                    stack.pop()
                if stack:
                    stack.pop()
            elif tag not in VOID and not raw.endswith('/>'):
                cls = re.search(r'class="([^"]*)"', raw)
                stack.append((tag, cls.group(1) if cls else '', s))
            continue
        if any(t in SKIP_TAGS or set(c.split()) & SKIP_CLASSES for t, c, _ in stack):
            continue
        anchors = [(t, c, o) for t, c, o in stack if t == 'a']
        if anchors and not all('g' in c.split() and GLOSS_URL in page[o:page.index('>', o)] for t, c, o in anchors):
            continue
        m = pat.search(raw)
        if not m:
            continue
        anchor = None
        if anchors:
            o = anchors[-1][2]
            anchor = (o, page.index('</a>', o) + 4)
        return s + m.start(), s + m.end(), anchor
    return None


def build(page: str, slug: str, items: list, gloss: dict) -> tuple[str, list[str]]:
    errors = []
    page = strip_own(page)
    if TOC_END not in page:
        return page, [f'{slug}: no contents list ({TOC_END}) to put the terms after']
    if len(items) > MAX_TERMS:
        errors.append(f'{slug}: {len(items)} terms, over {MAX_TERMS}')
    stop = page.find('<div class="next">')
    stop = stop if stop > 0 else page.find('</main>')
    for gid, phrase in items:
        if gid not in gloss:
            errors.append(f'{slug}: unknown glossary id {gid!r}')
            continue
        hit = find(page, page.index(TOC_END), stop, phrase)
        if not hit:
            errors.append(f'{slug}: phrase {phrase!r} ({gid}) not found in running text')
            continue
        a, b, anchor = hit
        tip = html.escape(first_sentence(gloss[gid]['def']), quote=False)
        span = f'<span class="term" tabindex="0">{page[a:b]}<span class="tip" role="tooltip">{tip}</span></span>'
        if anchor:   # replace the glossary link with the highlight; the sidebar carries the link
            inner = page[anchor[0]:anchor[1]]
            inner = re.sub(r'^<a[^>]*>|</a>$', '', inner)
            off = a - (anchor[0] + len(re.match(r'<a[^>]*>', page[anchor[0]:]).group(0)))
            inner = inner[:off] + span + inner[off + (b - a):]
            page = page[:anchor[0]] + inner + page[anchor[1]:]
            stop += len(inner) - (anchor[1] - anchor[0])
        else:
            page = page[:a] + span + page[b:]
            stop += len(span) - (b - a)
    rows = ''.join(f'<dt><a href="{GLOSS_URL}#{gid}">{html.escape(gloss[gid]["term"], quote=False)}</a></dt>'
                   f'<dd>{html.escape(first_sentence(gloss[gid]["def"]), quote=False)}</dd>'
                   for gid, _ in items if gid in gloss)
    more = f'<a class="more" href="{GLOSS_URL}">Every term in Table Talk</a>'
    block = (f'\n{START}\n<aside class="terms" aria-labelledby="terms-h"><b id="terms-h">Terms in this lesson</b><dl>{rows}</dl>{more}</aside>\n'
             f'<details class="terms-m"><summary>Terms in this lesson</summary><dl>{rows}</dl>{more}</details>\n{END}')
    i = page.index(TOC_END) + len(TOC_END)
    return page[:i] + block + page[i:], errors


def main(check: bool) -> int:
    spec = json.load(open(TERMS, encoding='utf-8'))
    gloss = {t['id']: t for t in json.load(open(GLOSSARY, encoding='utf-8'))['terms']}
    errors, stale = [], []
    for slug, items in spec['lessons'].items():
        path = os.path.join(LESSONS, slug + '.html')
        page = open(path, encoding='utf-8', newline='').read()
        out, errs = build(page, slug, items, gloss)
        errors += errs
        if out != page:
            stale.append(slug)
            if not check:
                open(path, 'w', encoding='utf-8', newline='').write(out)
    for e in errors:
        print('ERROR', e)
    if check:
        for s in stale:
            print(f'out of date: learn/lessons/{s}.html (run py -3 tools/lesson_terms.py)')
        if not stale and not errors:
            print(f'{len(spec["lessons"])} lessons up to date')
        return 1 if errors or stale else 0
    print(f'{len(stale)} lessons rewritten, {len(spec["lessons"]) - len(stale)} unchanged')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main('--check' in sys.argv[1:]))
