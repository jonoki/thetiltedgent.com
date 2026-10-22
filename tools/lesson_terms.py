"""Concepts on the lesson pages (Oki, 12 Oct 2026).

data/lesson_terms.json gives each lesson
  - ctx: the context words that pick a term's sense and switch on context-only match phrases (e.g. "futures"),
    written to <main data-ctx="...">; the concept tooltips themselves are added site-wide by assets/site.js from
    data/terms.json (tools/glossary.py), so this tool writes no tooltip markup;
  - concepts: 3-8 finance glossary ids, the lesson's core concepts, listed in a "Concepts in this lesson" sidebar on
    wide screens and a collapsed box under the contents on phones, each with its short definition and a link to
    its full Table Talk entry.
Rerunning is safe: it replaces its own block and removes the inline markup of the earlier, per-lesson version.

    py -3 tools/lesson_terms.py           rewrite the lesson pages
    py -3 tools/lesson_terms.py --check   exit 1 if any page is out of date or the data is wrong (run_checks)
"""
from __future__ import annotations

import html
import json
import os
import re
import sys

import glossary

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LESSONS = os.path.join(ROOT, 'learn', 'lessons')
TERMS = os.path.join(ROOT, 'data', 'lesson_terms.json')
GLOSSARY = os.path.join(ROOT, 'data', 'glossary_finance.json')
GLOSS_URL = '/learn/table-talk/finance.html'
MIN_CONCEPTS, MAX_CONCEPTS = 3, 8

START = '<!-- lesson-terms: written by tools/lesson_terms.py from data/lesson_terms.json; edit those, not this -->'
END = '<!-- /lesson-terms -->'
BLOCK_RE = re.compile(r'\n?' + re.escape(START) + r'.*?' + re.escape(END), re.S)
OLD_SPAN_RE = re.compile(r'<span class="term" tabindex="0">(.*?)<span class="tip" role="tooltip">[^<]*</span></span>', re.S)
MAIN_RE = re.compile(r'<main class="wrap lesson"(?: data-ctx="[^"]*")?>')
TOC_END = '</ol></nav>'


def build(page: str, slug: str, spec: dict, gloss: dict) -> tuple[str, list[str]]:
    errors = []
    page = OLD_SPAN_RE.sub(r'\1', BLOCK_RE.sub('', page))
    ids = spec.get('concepts', [])
    if not MIN_CONCEPTS <= len(ids) <= MAX_CONCEPTS:
        errors.append(f'{slug}: {len(ids)} concepts, needs {MIN_CONCEPTS}-{MAX_CONCEPTS}')
    errors += [f'{slug}: unknown glossary id {i!r}' for i in ids if i not in gloss]
    bad_ctx = [c for c in spec.get('ctx', '').split() if c not in glossary.CTX_LABEL]
    errors += [f'{slug}: unknown ctx {c!r}' for c in bad_ctx]
    if TOC_END not in page or not MAIN_RE.search(page):
        return page, errors + [f'{slug}: no <main class="wrap lesson"> or contents list']
    ctx = spec.get('ctx', '').strip()
    page = MAIN_RE.sub(f'<main class="wrap lesson"{f" data-ctx=\"{ctx}\"" if ctx else ""}>', page, count=1)
    rows = ''.join(f'<dt><a href="{GLOSS_URL}#{i}">{html.escape(gloss[i]["term"], quote=False)}</a></dt>'
                   f'<dd>{html.escape(glossary.short(gloss[i]), quote=False)}</dd>' for i in ids if i in gloss)
    more = f'<a class="more" href="{GLOSS_URL}">Every term in Table Talk</a>'
    block = (f'\n{START}\n<aside class="terms" aria-labelledby="terms-h"><b id="terms-h">Concepts in this lesson</b><dl>{rows}</dl>{more}</aside>\n'
             f'<details class="terms-m"><summary>Concepts in this lesson</summary><dl>{rows}</dl>{more}</details>\n{END}')
    i = page.index(TOC_END) + len(TOC_END)
    return page[:i] + block + page[i:], errors


def main(check: bool) -> int:
    spec = json.load(open(TERMS, encoding='utf-8'))
    gloss = {t['id']: t for t in json.load(open(GLOSSARY, encoding='utf-8'))['terms']}
    errors, stale = [], []
    for slug, item in spec['lessons'].items():
        path = os.path.join(LESSONS, slug + '.html')
        page = open(path, encoding='utf-8', newline='').read()
        out, errs = build(page, slug, item, gloss)
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
