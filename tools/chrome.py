#!/usr/bin/env python3
"""Write the one site nav and footer into every site page, and make sure each page loads the shared
assets/site.css and assets/site.js. Report documents (reports/**/*_analysis.html) are never touched.

Run from the repo root:   py -3 tools/chrome.py            (then: py -3 tables/build_tables.py)
The Tables game pages are generated: this script updates their source (tables/_source/casino-games-source.html)
and the builder copies the nav and footer from there.

Each page keeps its own fine print: the <p> inside its old footer that starts with a <b>…fine print…</b>
label is carried into the new footer unchanged."""
import os
import re
import sys

import repodata as rd

LINKS = [  # (key, label, href) — root-relative so the same markup works at any depth
    ('learn', 'Learn', '/#learn'),
    ('tables', 'The Tables', '/tables/casino-games.html'),
    ('degens', 'Le Degens', '/#degens'),
    ('tools', 'The Toolbox', '/#tools'),
    ('reports', 'Reports', '/reports/'),
    ('about', 'The Gent', '/#about'),
]
CTA = ('Take a Seat', '/#learn')

# The shared wiring every page carries; tables/build_tables.py copies these three from the Tables source.
JS_CLASS = "<script>document.documentElement.classList.add('js');</script>"   # the menu starts closed
SITE_CSS = '<link rel="stylesheet" href="/assets/site.css">'
SITE_JS = '<script src="/assets/site.js" defer></script>'

PAGES = [  # (path, active nav key or None, has a footer)
    ('index.html', None, True),
    ('brand.html', None, True),
    ('reports/index.html', 'reports', True),
    ('reports/view.html', 'reports', False),   # the report fills the screen; no footer
    ('tables/_source/casino-games-source.html', 'tables', True),
    ('tables/blackjack-trainer.html', 'tables', True),
    ('tables/craps-table.html', 'tables', True),
]

SITE_FINE = ("<b>The fine print (we read it, so should you):</b> Everything on this site is education and entertainment, "
             "not financial advice, investment advice, or an inducement to gamble. I'm a CFA charterholder, not <i>your</i> advisor. "
             "Markets can take your money; casinos are designed to. If gambling stops being fun, that's the game telling you "
             "something — help exists and taking it is the +EV play.")


def nav(active: str | None) -> str:
    links = '\n'.join(
        f'      <a href="{href}"' + (' aria-current="page"' if key == active else '') + f'>{label}</a>'
        for key, label, href in LINKS)
    return f'''<nav class="site" aria-label="Site">
  <div class="wrap navrow">
    <a class="navbrand" href="/">
      <img src="/assets/ttg-mark-neon.svg" alt="" width="46" height="46">
      <span class="navword">THE <span class="tilt">TILTED</span> GENT</span>
    </a>
    <button class="navtoggle" type="button" aria-label="Menu" aria-expanded="false" aria-controls="navmenu"><span class="bars"></span></button>
    <div class="navlinks" id="navmenu">
{links}
      <a class="cta" href="{CTA[1]}">{CTA[0]}</a>
    </div>
  </div>
</nav>'''


def footer(fine: str) -> str:
    links = ' '.join(f'<a href="{href}">{label}</a>' for _, label, href in LINKS)
    return f'''<footer class="site">
  <div class="wrap foot">
    <div>
      <a class="footbrand" href="/">
        <img src="/assets/ttg-mark-neon.svg" alt="" width="40" height="40">
        <span class="navword">THE <span class="tilt">TILTED</span> GENT</span>
      </a>
      <p>Markets, odds and risk. Est. Halifax, Nova Scotia.</p>
      <p class="footlinks">{links}</p>
      <p class="motto">THE HOUSE ALWAYS WINS. LEARN TO BE THE HOUSE.</p>
    </div>
    <div class="fine">
      <p>{fine}</p>
    </div>
  </div>
</footer>'''


def old_fine(block: str) -> str:
    """The page's own fine-print paragraph from its old footer, else the site's."""
    for p in re.findall(r'<p[^>]*>(.*?)</p>', block, re.S):
        if re.match(r'\s*<b[^>]*>[^<]*fine print', p, re.I):
            return re.sub(r'<b style="[^"]*">', '<b>', p.strip())
    return SITE_FINE


def insert_once(t: str, anchor: str, text: str, path: str, after: bool = False) -> str:
    """t with text put just before (or after) the first anchor; ValueError naming the page when there is none."""
    i = t.find(anchor)
    if i < 0:
        raise ValueError(f'{path}: no {anchor} to put {text.strip()[:40]} next to')
    at = i + len(anchor) if after else i
    return t[:at] + text + t[at:]


def write_chrome(path: str, active: str | None, has_footer: bool, repo: str = rd.ROOT) -> bool:
    """Put the current nav (and footer) into one page and make sure it loads site.css and site.js.
    Returns True when the page changed; raises ValueError, naming the page and what is missing, when there is
    no nav or footer to replace or nowhere to put the shared wiring."""
    full = os.path.join(repo, path)
    with open(full, encoding='utf-8', newline='') as fh:
        t = fh.read()
    before = t
    m = re.search(r'<nav\b[^>]*>.*?</nav>', t, re.S)
    if not m:
        raise ValueError(f'{path}: no <nav> found')
    t = t[:m.start()] + nav(active) + t[m.end():]
    if has_footer:
        m = re.search(r'<footer\b[^>]*>.*?</footer>', t, re.S)
        if not m:
            raise ValueError(f'{path}: no <footer> found')
        t = t[:m.start()] + footer(old_fine(m.group(0))) + t[m.end():]
    if JS_CLASS not in t:
        t = insert_once(t, '<meta charset="UTF-8">', '\n' + JS_CLASS, path, after=True)
    if SITE_CSS not in t:
        first_css = re.search(r'<link rel="stylesheet"|<style>', t)
        t = insert_once(t, first_css.group(0) if first_css else '</head>', SITE_CSS + '\n', path)
    if SITE_JS not in t:
        t = insert_once(t, '</body>', SITE_JS + '\n', path)
    if t == before:
        return False
    with open(full, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(t)
    return True


def main() -> int | str:
    """0 when every page is written, else the problem (the page had no nav or footer to replace)."""
    for path, active, has_footer in PAGES:
        try:
            print('updated' if write_chrome(path, active, has_footer) else 'unchanged', path)
        except ValueError as e:
            return str(e)
    return 0


if __name__ == '__main__':
    sys.exit(main())
