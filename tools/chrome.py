#!/usr/bin/env python3
"""Write the one site nav and footer into every site page, and make sure each page loads the shared
assets/site.css and assets/site.js. Report documents (reports/**/*_analysis.html) are never touched.

Run from the repo root:   py -3 tools/chrome.py
The Tables game pages are generated: this script updates their source (tables/_source/casino-games-source.html)
and then runs tables/build_tables.py, which copies the nav and footer from there, so the two cannot drift.

Each page keeps its own fine print: the <p> inside its old footer that starts with a <b>…fine print…</b>
label is carried into the new footer unchanged."""
import os
import re
import subprocess
import sys
from typing import NamedTuple

import reportlib as rl
import repodata as rd

class NavLink(NamedTuple):
    """A top-level link; badge is a short chip after the label (e.g. 'Soon')."""
    key: str
    label: str
    href: str
    badge: str = ''


class NavMenu(NamedTuple):
    """A top-level section that opens a panel of links, in headed groups of (label, href)."""
    key: str
    label: str
    groups: list[tuple[str, list[tuple[str, str]]]]


# The site nav (Oki, 30 Sep 2026): Learn and Le Degens stay, marked Soon; Reports and The Tables open panels, and
# every trainer sits under The Tables. The Toolbox stays a homepage section, linked from the footer. The two glossaries
# (Oki, 5 Oct 2026): finance under Reports, poker & gambling under The Tables.
# Hrefs are root-relative so the same markup works at any depth. Games follow the board's order (best grade first).
NAV: list[NavLink | NavMenu] = [
    NavLink('learn', 'Learn', '/#learn', 'Soon'),
    NavMenu('reports', 'Reports', [('Reports', [
        ('Stocks', '/reports/'), ('ETFs', '/reports/?f=etf'), ('Crypto', '/reports/?f=crypto'),
        ('Bonds &amp; cash', '/reports/?f=fixed'), ('Glossary', '/glossary/finance.html')])]),
    NavMenu('tables', 'The Tables', [
        ('Games, graded', [
            ('All games: the grades', '/tables/casino-games.html'), ('Blackjack', '/tables/blackjack.html'),
            ('Blackjack Variants', '/tables/blackjack-variants.html'), ('Video Poker', '/tables/video-poker.html'),
            ('Craps', '/tables/craps.html'), ('Baccarat', '/tables/baccarat.html'),
            ('Ultimate Texas Hold&rsquo;em', '/tables/ultimate-texas-holdem.html'),
            ('Three Card Poker', '/tables/three-card-poker.html'), ('Roulette', '/tables/roulette.html'),
            ('Slots', '/tables/slots.html')]),
        ('Trainers', [('Blackjack Trainer', '/tables/blackjack-trainer.html'),
                      ('Craps Table', '/tables/craps-table.html')]),
        ('Glossary', [('Poker &amp; gambling terms', '/glossary/poker.html')])]),
    NavLink('degens', 'Le Degens', '/#degens', 'Soon'),
    NavLink('about', 'The Gent', '/#about'),
]
FOOT_LINKS = [('Learn', '/#learn'), ('Reports', '/reports/'), ('The Tables', '/tables/casino-games.html'),
              ('Le Degens', '/#degens'), ('The Toolbox', '/#tools'), ('The Gent', '/#about')]
CTA = ('Take a Seat', '/#learn')

# The shared wiring every page carries; tables/build_tables.py copies these three from the Tables source.
JS_CLASS = "<script>document.documentElement.classList.add('js');</script>"   # the menu starts closed
# Bump ASSET_V whenever site.css or site.js changes: Pages caches for ten minutes, and new nav markup with the old
# stylesheet shows an unstyled menu. write_chrome replaces any older stamp.
ASSET_V = '20261005'
SITE_CSS = f'<link rel="stylesheet" href="/assets/site.css?v={ASSET_V}">'
SITE_JS = f'<script src="/assets/site.js?v={ASSET_V}" defer></script>'
OLD_SITE_CSS = re.compile(r'<link rel="stylesheet" href="/assets/site\.css(?:\?v=[^"]*)?">')
OLD_SITE_JS = re.compile(r'<script src="/assets/site\.js(?:\?v=[^"]*)?" defer></script>')

PAGES = [  # (path, active nav key or None, has a footer)
    ('index.html', None, True),
    ('brand.html', None, True),
    ('reports/index.html', 'reports', True),
    ('reports/view.html', 'reports', False),   # the report fills the screen; no footer
    ('tables/_source/casino-games-source.html', 'tables', True),
    ('tables/blackjack-trainer.html', 'tables', True),
    ('tables/craps-table.html', 'tables', True),
    ('glossary/finance.html', 'reports', True),   # written by tools/glossary.py
    ('glossary/poker.html', 'tables', True),
]

SITE_FINE = ("<b>The fine print (we read it, so should you):</b> Everything on this site is education and entertainment, "
             "not financial advice, investment advice, or an inducement to gamble. I'm a CFA charterholder, not <i>your</i> advisor. "
             "Markets can take your money; casinos are designed to. If gambling stops being fun, that's the game telling you "
             "something — help exists and taking it is the +EV play.")


def nav_item(item: NavLink | NavMenu, active: str | None) -> str:
    """One top-level entry. A section is a native disclosure (<details>): it opens without JS and needs no ARIA
    menu roles; site.js adds one-open-at-a-time, Esc, click-outside and the current page's mark."""
    if isinstance(item, NavLink):
        cur = ' aria-current="page"' if item.key == active else ''
        if not item.badge:
            return f'      <a href="{item.href}"{cur}>{item.label}</a>'
        return (f'      <a href="{item.href}"{cur} aria-label="{item.label} (coming {item.badge.lower()})">'
                f'{item.label} <span class="soon">{item.badge}</span></a>')
    groups = '\n'.join(
        f'          <div class="navgroup"><p class="navgh">{head}</p><ul>'
        + ''.join(f'<li><a href="{href}">{label}</a></li>' for label, href in links) + '</ul></div>'
        for head, links in item.groups)
    on = ' class="on"' if item.key == active else ''
    return (f'      <details class="navmenu" name="navmenu" data-menu="{item.key}"><summary{on}>{item.label}</summary>\n'
            f'        <div class="navpanel{" navwide" if len(item.groups) > 1 else ""}">\n{groups}\n        </div>\n'
            '      </details>')


def nav(active: str | None) -> str:
    links = '\n'.join(nav_item(item, active) for item in NAV)
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
    links = ' '.join(f'<a href="{href}">{label}</a>' for label, href in FOOT_LINKS)
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
            return p.strip()
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
    t = OLD_SITE_JS.sub(SITE_JS, OLD_SITE_CSS.sub(SITE_CSS, t))   # restamp the version on pages that have them
    if SITE_CSS not in t:
        first_css = re.search(r'<link rel="stylesheet"|<style>', t)
        t = insert_once(t, first_css.group(0) if first_css else '</head>', SITE_CSS + '\n', path)
    if SITE_JS not in t:
        t = insert_once(t, '</body>', SITE_JS + '\n', path)
    if t == before:
        return False
    rl.write_text(full, t)
    return True


def main(argv: list[str] | None = None) -> int | str:
    """0 when every page is written and the Tables pages rebuilt, else the problem (a page with no nav or footer
    to replace, a file that cannot be read or written, or the builder's own message)."""
    repo = rd.parser('Write the site nav and footer into every chrome page.').parse_args(argv).repo
    for path, active, has_footer in PAGES:
        try:
            print('updated' if write_chrome(path, active, has_footer, repo) else 'unchanged', path)
        except (ValueError, OSError) as e:
            return str(e)
    built = subprocess.run([sys.executable, os.path.join(repo, 'tables', 'build_tables.py')],
                           capture_output=True, text=True, encoding='utf-8')
    print(built.stdout.strip())
    return built.returncode and (built.stderr.strip() or f'tables/build_tables.py exited {built.returncode}')


if __name__ == '__main__':
    sys.exit(main())
