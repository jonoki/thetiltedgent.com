#!/usr/bin/env python3
"""Build the Tables pages from their one source: tables/_source/casino-games-source.html.

Run from the repo root:   py -3 tables/build_tables.py        (after py -3 tools/chrome.py when the nav changed)
Writes tables/tables.css (the source page's CSS + tables/_source/split-pages.css), one page per game (GAMES),
the family pages (FAMILY_PAGES) and the index, tables/casino-games.html. The prose lives only in the source;
never edit the built pages by hand. tools/chrome.py writes the nav, the footer and the shared site.css / site.js
wiring into the source, and every page copies them from there.
"""
import html
import os
import sys
from typing import NamedTuple

TABLES = os.path.dirname(os.path.abspath(__file__))   # the tables/ folder: source in, pages out
SRC = os.path.join(TABLES, '_source', 'casino-games-source.html')
SPLIT_CSS = os.path.join(TABLES, '_source', 'split-pages.css')   # game cards, page nav and simulator styles

AP_MARKER = '    <div class="ap">'    # the advantage-play box; the simulator goes just above it
DEFAULT_SESSIONS = 500   # bets per simulated session unless a game sets its own
BLACKJACK_TRAINER_CALLOUT = '''    <div class="callout" style="margin-top:22px;border-left-color:var(--cyan);background:rgba(31,203,227,.05);"><b>Practice room.</b> The <a href="blackjack-trainer.html" style="color:var(--cyan-neon)">Blackjack Trainer</a> is a simulated table for learning the chart and then the count: choose decks and rules, seat other players, set the deal speed, get every decision graded, and check your running count against the real one. &rarr;</div>'''


class Game(NamedTuple):
    """A game on the grade board and its page: the <section id> in the source, page slug, title, meta description,
    grade (CSS class, label), the board card's one-liner and link label, and its simulator: the intro sentence
    (None: no simulator, the page explains why) and bets per session. callout goes above the advantage-play box."""
    id: str
    slug: str
    title: str
    desc: str
    grade: tuple[str, str]
    oneline: str
    sim_intro: str | None
    sessions: int = DEFAULT_SESSIONS
    more: str = 'ANALYSIS + SIMULATOR'
    callout: str = ''


class FamilyPage(NamedTuple):
    """A page in a game's family that is not on the grade board, with its simulator game and page neighbours."""
    id: str
    slug: str
    title: str
    desc: str
    sim_game: str
    prev: str
    next: str


GAMES = [
    Game('blackjack', 'blackjack', 'Blackjack',
         'Blackjack: the only game where the house shows you its hand — rules, house edge on every bet, 6:5 vs 3:2, card counting, and a variance simulator.',
         ('a', 'A'), 'The best game on the floor, <i>if</i> you find a 3:2 table and play the chart.',
         "Play a thousand sessions of basic strategy and watch how long the half-percent edge stays invisible — then switch the table to 6:5 and watch it stop hiding.",
         more='ANALYSIS · VARIANTS · TRAINER', callout=BLACKJACK_TRAINER_CALLOUT),
    Game('video-poker', 'video-poker', 'Video Poker',
         'Video Poker: the slot machine that tells you the truth — paytables, returns, strategy, advantage play, and a variance simulator.',
         ('a', 'A&minus;'), "A slot machine that publishes its odds. Read the paytable or don't sit.",
         "The same 500 hands on a 9/6 machine and an 8/5 machine, side by side, is the most persuasive argument on this page. Try both."),
    Game('craps', 'craps', 'Craps',
         'Craps: two great bets and forty terrible ones — house edge on every bet, best and worst bets, dice control, and a variance simulator.',
         ('b', 'B+'), 'Two great bets surrounded by forty terrible ones. Loudest fun per dollar in the building.',
         "Pass line with full odds, then any seven, at the same unit and the same number of bets. That's the whole craps lesson in two runs."),
    Game('baccarat', 'baccarat', 'Baccarat',
         'Baccarat: coin-flipping in a tuxedo — Banker vs Player vs Tie, side bets, edge sorting, and a variance simulator.',
         ('b', 'B'), "Zero decisions, low edge, fast. The house's favourite game for a reason.",
         "Banker at 1.06% looks like nothing per hand. Run 700 hands — a long evening at the big table — and see what nothing adds up to.",
         sessions=700),
    Game('ultimate-texas-holdem', 'ultimate-texas-holdem', "Ultimate Texas Hold'em",
         "Ultimate Texas Hold'em: poker's costume, the house's rules — raise strategy, Trips paytables, hole-carding, and a variance simulator.",
         ('b', 'B&minus;'), "Poker's costume, house's rules. Fun, strategic, and priced fairly if you raise 4x when you should.",
         "The variance here is the story: 4x raises make the swings enormous even though the edge on the money is only half a percent."),
    Game('three-card-poker', 'three-card-poker', 'Three Card Poker',
         'Three Card Poker: one decision, one trap — Q-6-4, Pair Plus paytables, and a variance simulator.',
         ('c', 'C+'), 'One decision (Q-6-4), one trap (Pair Plus), one pleasant hour.',
         "Ante & Play versus Pair Plus on the 6-3-1 table, same unit, same hands. One of these is a game and one is a donation."),
    Game('roulette', 'roulette', 'Roulette',
         'Roulette: pick the wheel, not the bet — single, double and triple zero, la partage, wheel bias, and a variance simulator.',
         ('c', 'C&minus;'), 'Elegant, slow, and every bet on the felt costs the same — pick the wheel, not the bet.',
         "Same bet, three wheels. Run even money on single zero, double zero and triple zero and watch the median line steepen."),
    Game('slots', 'slots', 'Slots',
         'Slots: the only game where the price is a secret — reported holds by denomination, the design tricks, and why there is no simulator.',
         ('d', 'D'), "The only game where the price is a secret. That's the tell.",
         None, more='READ THE ANALYSIS'),
]
FAMILY_PAGES = [
    FamilyPage('blackjack-variants', 'blackjack-variants', 'Blackjack Variants', 'Free Bet Blackjack, Blackjack Switch, Spanish 21, Double Exposure and Super Fun 21: what each gives, what each takes back, the house edge with the right chart, and a variance simulator.', 'blackjack-variants', 'blackjack', 'video-poker'),
]
FAMILY = {'blackjack': [('blackjack.html', 'Blackjack'), ('blackjack-variants.html', 'Variants'), ('blackjack-trainer.html', 'Trainer')]}


def between(s: str, a: str, b: str, start: int = 0) -> tuple[str, int, int]:
    """(s from the first a to the end of the following b, its start, its end); ValueError naming the marker when absent."""
    i = s.find(a, start)
    if i < 0:
        raise ValueError(f'marker not found in the source: {a!r}')
    j = s.find(b, i)
    if j < 0:
        raise ValueError(f'no {b!r} after {a!r} in the source')
    return s[i:j + len(b)], i, j + len(b)


def replace_once(s: str, old: str, new: str) -> str:
    """s with its one occurrence of old replaced; ValueError when old is not there exactly once, so an edit to the
    source prose cannot silently switch a patch off."""
    n = s.count(old)
    if n != 1:
        raise ValueError(f'expected one {old[:70]!r} in the source, found {n}')
    return s.replace(old, new, 1)


# ---------- the simulator section and its scripts ----------

NO_SIM_NOTE = '''
    <div class="simsec" id="sim">
      <div class="kicker">Feel the edge</div>
      <h3 class="simhead">No simulator for slots &mdash; <em>and that's the point</em>.</h3>
      <div class="slotnote"><b>Slot outcome distributions are not published.</b> Every other game on this site has a simulator because its odds are knowable: the deck, the dice and the wheel are public, and the paytable is printed on the felt or the glass. A slot machine's return and hit frequency are set by the casino from a menu the manufacturer provides, are not displayed anywhere, and vary wildly from one machine to the next &mdash; two identical cabinets can be set years apart in expected cost. Any simulation would be a guess dressed up as a chart, which is exactly the trick the machine itself is playing. <b>What we do know is enough:</b> reported holds run from roughly 2&ndash;4% in high-limit rooms to 10&ndash;15% on penny games and bar tops, at 500&ndash;900 spins an hour. At those numbers a slot is the worst bet in the building by a wide margin, and no amount of simulating changes that. If you want to see what a fast, high-edge game does to a bankroll, run the <a href="craps.html#bet=any-seven&amp;unit=2&amp;n=1200" style="color:var(--cyan-neon)">any-seven bet on the craps page</a> at $2 for 1,200 bets &mdash; that's a penny slot on a good day.</div>
    </div>'''   # the one game without a simulator (sim_intro None) is slots


def sim_section(em: str, sub: str, nojs: str) -> str:
    return f'''
    <div class="simsec" id="sim">
      <div class="kicker">Feel the edge</div>
      <h3 class="simhead">Run a session <em>{em}</em>.</h3>
      <p class="simsub">{sub}</p>
      <div id="simmount"><div class="simnojs">{nojs}</div></div>
    </div>'''


def game_sim(g: Game) -> str:
    """The game page's simulator section (with the game's callout after it), or the note saying why there is none."""
    if g.sim_intro is None:
        return NO_SIM_NOTE
    sim = sim_section('before you sit down',
                      "Pick a bet, a unit and a number of bets. The simulator plays <b>1,000 sessions from the bet's actual outcome table</b> &mdash; not a normal approximation &mdash; and shows the spread, the drawdowns, and how long it takes before the house edge stops hiding behind luck. " + g.sim_intro,
                      'The simulator needs JavaScript. The house edge on every bet is in the table above; the simulator only shows what it feels like.')
    return sim + ('\n' + g.callout if g.callout else '')


def variant_sim() -> str:
    return sim_section('at each variant',
                       "Pick a variant and a rule set. The simulator plays <b>1,000 sessions</b> from a result shape calibrated to the published house edge (these are labelled approximate &mdash; the variants don't have the clean combinatorics of a single bet). Try Spanish 21 against Super Fun 21 at the same unit: same cards, a percentage point apart.",
                       'The simulator needs JavaScript. The house edge on every variant is in the table above.')


def sim_scripts(game: str, sessions: int) -> str:
    return f'''
<script src="sim/games.js"></script>
<script src="sim/ttg-sim.js"></script>
<script>TTGSim.mount('#simmount', {{game: '{game}', n: {sessions}}});</script>'''


# ---------- page parts ----------

def page_links(prev: Game | None, nxt: Game | None) -> str:
    """Previous / next page cards, then the link back to the board. prev and nxt are Games or None."""
    a = (f'<a class="prev" href="{prev.slug}.html"><div class="k">&larr; Previous</div><div class="t">{prev.title}</div></a>'
         if prev else '<span></span>')
    if nxt:
        a += f'<a class="next" href="{nxt.slug}.html"><div class="k">Next &rarr;</div><div class="t">{nxt.title}</div></a>'
    return (f'<div class="wrap pagenav">{a}</div><div class="wrap allgames">'
            '<a class="btn ghost" href="casino-games.html#board">&larr; All eight games, graded</a></div>')


def family_tabs(slug: str) -> str:
    for tabs in FAMILY.values():
        if any(h == slug + '.html' for h, _ in tabs):
            here = slug + '.html'
            links = ''.join(f'<a href="{h}"' + (' class="on"' if h == here else '') + f'>{t}</a>' for h, t in tabs)
            return '<div class="wrap famtabs">' + links + '</div>'
    return ''


def crumbs(*trail: str | tuple[str, str]) -> str:
    """Home / The Tables / … / the current page (its title, escaped); trail items before it are (href, text)."""
    *links, here = trail
    parts = ['<a href="../">Home</a>', '<a href="casino-games.html">The Tables</a>']
    parts += [f'<a href="{h}">{t}</a>' for h, t in links] + [html.escape(here, quote=False)]
    return '<div class="wrap crumbs">' + '<span>/</span>'.join(parts) + '</div>'


def with_sim(section: str, gid: str, sim: str) -> str:
    """The game's source section, opened as the page's first section, with the simulator above the
    advantage-play box."""
    sec = replace_once(section, f'<section class="game" id="{gid}">', f'<section class="game first" id="{gid}">')
    if sec.count(AP_MARKER) != 1:
        raise ValueError(f'{gid}: expected exactly one advantage-play box in the source section')
    return sec.replace(AP_MARKER, sim + '\n' + AP_MARKER, 1)


class Site:
    """The pieces of the source every page is assembled from, and the page shell around them."""

    def __init__(self, src: str) -> None:
        css, _, _ = between(src, '<style>', '</style>')
        self.css = css[len('<style>'):-len('</style>')]
        # the shared wiring tools/chrome.py puts into the source: the js class (menu starts closed), site.css, site.js
        self.js_class = between(src, "<script>document.documentElement.classList.add('js')", '</script>')[0]
        self.site_css = between(src, '<link rel="stylesheet" href="/assets/site.css"', '>')[0]
        self.site_js = between(src, '<script src="/assets/site.js"', '</script>')[0]
        self.nav = between(src, '<!-- ================= NAV ================= -->', '</nav>')[0]
        self.footer = between(src, '<!-- ================= FOOTER ================= -->', '</footer>')[0]
        self.hero = between(src, '<!-- ================= HERO ================= -->', '</div>\n</div>\n')[0]
        self.board = between(src, '<!-- ================= GRADE BOARD ================= -->', '</section>')[0]
        self.method = between(src, '<!-- ================= METHOD ================= -->', '</section>')[0]
        self.outro = between(src, '<!-- ================= OUTRO ================= -->', '</section>')[0]
        self.sections = {g.id: between(src, f'<section class="game" id="{g.id}">', '</section>')[0]
                         for g in GAMES + FAMILY_PAGES}

    def head(self, title: str, desc: str, url: str, og_type: str = 'article') -> str:
        t = html.escape(title, quote=False)
        d = html.escape(desc, quote=True)
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{self.js_class}
<title>{t} — The Tilted Gent</title>
<link rel="icon" type="image/svg+xml" href="../assets/ttg-favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="../assets/apple-touch-icon.png">
<meta name="description" content="{d}">
<meta name="theme-color" content="#06050B">
<meta name="color-scheme" content="dark">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="The Tilted Gent">
<meta property="og:title" content="{t} — The Tilted Gent">
<meta property="og:description" content="{d}">
<meta property="og:url" content="https://thetiltedgent.com/tables/{url}">
<meta property="og:image" content="https://thetiltedgent.com/assets/ttg-og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t} — The Tilted Gent">
<meta name="twitter:image" content="https://thetiltedgent.com/assets/ttg-og.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
{self.site_css}
<link rel="stylesheet" href="tables.css">
</head>
<body>

'''

    def page(self, main: str, scripts: str = '') -> str:
        """The body: nav, the page's own content, footer, the menu script and any page scripts."""
        return (self.nav + '\n\n' + main + '\n\n' + self.footer + '\n\n' + self.site_js + scripts
                + '\n</body>\n</html>\n')

    def game_body(self, crumb: str, tabs: str, sec: str, links: str, scripts: str) -> str:
        return self.page(crumb + ('\n' + tabs if tabs else '') + '\n\n' + sec + '\n\n' + links, scripts)


def write(name: str, text: str) -> None:
    with open(os.path.join(TABLES, name), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def game_page(site: Site, i: int, g: Game) -> None:
    sec = with_sim(site.sections[g.id], g.id, game_sim(g))
    links = page_links(GAMES[i - 1] if i > 0 else None, GAMES[i + 1] if i < len(GAMES) - 1 else None)
    scripts = sim_scripts(g.id, g.sessions) if g.sim_intro is not None else ''
    body = site.game_body(crumbs(g.title), family_tabs(g.slug), sec, links, scripts)
    write(g.slug + '.html', site.head(g.title + ', graded', g.desc, g.slug + '.html') + body)


def family_page(site: Site, p: FamilyPage) -> None:
    by_slug = {g.slug: g for g in GAMES}
    prev, nxt = by_slug[p.prev], by_slug[p.next]
    sec = with_sim(site.sections[p.id], p.id, variant_sim())
    body = site.game_body(crumbs((f'{prev.slug}.html', prev.title), p.title), family_tabs(p.slug), sec,
                          page_links(prev, nxt), sim_scripts(p.sim_game, DEFAULT_SESSIONS))
    write(p.slug + '.html', site.head(p.title + ', graded', p.desc, p.slug + '.html') + body)


def index_hero(hero: str) -> str:
    """The source hero with the simulator count and a sentence about the game pages added."""
    stat = '<span class="stat"><b>60+</b> BETS PRICED</span>'
    sims = sum(g.sim_intro is not None for g in GAMES)
    hero = replace_once(hero, stat, f'{stat}\n        <span class="stat"><b>{sims}</b> VARIANCE SIMULATORS</span>')
    return replace_once(hero, 'and where a disciplined player can flip the edge — legally. Then a grade, so you know what a night at each table is worth.',
                        'and where a disciplined player can flip the edge — legally. Each game has its own page with a <b>variance simulator</b> that plays a thousand sessions from the real odds, and a grade, so you know what a night at each table is worth.')


def games_section() -> str:
    """The index's grid of game cards."""
    cards = ''.join(
        f'''      <a class="gcard" href="{g.slug}.html"><div class="top"><h3>{html.escape(g.title, quote=False)}</h3><span class="grade {g.grade[0]} sm">{g.grade[1]}</span></div><p>{g.oneline}</p><span class="more">{g.more} &rarr;</span></a>\n'''
        for g in GAMES)
    return f'''<!-- ================= GAME PAGES ================= -->
<section id="games">
  <div class="wrap">
    <div class="kicker">The Games</div>
    <h2 class="sec">One page per game, <em>one simulator each</em>.</h2>
    <p class="secsub">Every page has the full analysis &mdash; how it plays, the house edge on every bet, best and worst bets, the quirks, advantage play and its legality &mdash; plus a simulator that runs a thousand sessions from the bet's real outcome table. Slots get an explanation of why there isn't one.</p>
    <div class="gamegrid">
{cards}    </div>
  </div>
</section>
'''


def index_page(site: Site) -> None:
    board = site.board
    for g in GAMES:   # the board's links jump to the game's section in the source; here they open its page
        board = replace_once(board, f'href="#{g.id}"', f'href="{g.slug}.html"')
    main = index_hero(site.hero) + '\n' + board + '\n\n' + games_section() + '\n' + site.method + '\n\n' + site.outro
    head = site.head('Casino Games, Graded', 'Eight casino games, graded honestly: how each one plays, the house edge on every bet, the best and worst bets, the quirks, advantage play — and a variance simulator on every game page.',
                     'casino-games.html', og_type='website')
    write('casino-games.html', head + site.page(main))


def main() -> int | str:
    """0 when every page is built, else the problem (a marker or a patched sentence missing from the source)."""
    with open(SRC, encoding='utf-8') as fh:
        src = fh.read()
    try:
        site = Site(src)
        with open(SPLIT_CSS, encoding='utf-8') as fh:
            write('tables.css', site.css.strip('\n') + '\n' + fh.read())
        for i, g in enumerate(GAMES):
            game_page(site, i, g)
        for p in FAMILY_PAGES:
            family_page(site, p)
        index_page(site)
    except ValueError as e:
        return f'tables/_source/casino-games-source.html: {e}'
    print('built', len(GAMES), 'game pages +', len(FAMILY_PAGES), 'family pages + index + tables.css')
    return 0


if __name__ == '__main__':
    sys.exit(main())
