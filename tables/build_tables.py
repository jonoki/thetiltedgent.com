#!/usr/bin/env python3
"""Build the Tables pages from their one source: tables/_source/casino-games-source.html.

Run from the repo root:   py -3 tables/build_tables.py        (after py -3 tools/chrome.py when the nav changed)
Writes tables/tables.css, one page per game (GAMES), the family pages (FAMILY_PAGES) and the index,
tables/casino-games.html. The prose lives only in the source; never edit the built pages by hand.
tools/chrome.py writes the nav and footer into the source, and every page copies them from there.
"""
import html
import os
from typing import NamedTuple

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, '_source', 'casino-games-source.html')


class Game(NamedTuple):
    """A game on the grade board: its <section id> in the source, page slug, title and meta description."""
    id: str
    slug: str
    title: str
    desc: str


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
    Game('blackjack', 'blackjack', 'Blackjack', 'Blackjack: the only game where the house shows you its hand — rules, house edge on every bet, 6:5 vs 3:2, card counting, and a variance simulator.'),
    Game('video-poker', 'video-poker', 'Video Poker', 'Video Poker: the slot machine that tells you the truth — paytables, returns, strategy, advantage play, and a variance simulator.'),
    Game('craps', 'craps', 'Craps', 'Craps: two great bets and forty terrible ones — house edge on every bet, best and worst bets, dice control, and a variance simulator.'),
    Game('baccarat', 'baccarat', 'Baccarat', 'Baccarat: coin-flipping in a tuxedo — Banker vs Player vs Tie, side bets, edge sorting, and a variance simulator.'),
    Game('ultimate-texas-holdem', 'ultimate-texas-holdem', "Ultimate Texas Hold'em", "Ultimate Texas Hold'em: poker's costume, the house's rules — raise strategy, Trips paytables, hole-carding, and a variance simulator."),
    Game('three-card-poker', 'three-card-poker', 'Three Card Poker', 'Three Card Poker: one decision, one trap — Q-6-4, Pair Plus paytables, and a variance simulator.'),
    Game('roulette', 'roulette', 'Roulette', 'Roulette: pick the wheel, not the bet — single, double and triple zero, la partage, wheel bias, and a variance simulator.'),
    Game('slots', 'slots', 'Slots', 'Slots: the only game where the price is a secret — reported holds by denomination, the design tricks, and why there is no simulator.'),
]
FAMILY_PAGES = [
    FamilyPage('blackjack-variants', 'blackjack-variants', 'Blackjack Variants', 'Free Bet Blackjack, Blackjack Switch, Spanish 21, Double Exposure and Super Fun 21: what each gives, what each takes back, the house edge with the right chart, and a variance simulator.', 'blackjack-variants', 'blackjack', 'video-poker'),
]
FAMILY = {'blackjack': [('blackjack.html', 'Blackjack'), ('blackjack-variants.html', 'Variants'), ('blackjack-trainer.html', 'Trainer')]}
GRADES = {'blackjack': ('a', 'A'), 'video-poker': ('a', 'A&minus;'), 'craps': ('b', 'B+'), 'baccarat': ('b', 'B'),
          'ultimate-texas-holdem': ('b', 'B&minus;'), 'three-card-poker': ('c', 'C+'), 'roulette': ('c', 'C&minus;'), 'slots': ('d', 'D')}
ONELINE = {
    'blackjack': 'The best game on the floor, <i>if</i> you find a 3:2 table and play the chart.',
    'video-poker': "A slot machine that publishes its odds. Read the paytable or don't sit.",
    'craps': 'Two great bets surrounded by forty terrible ones. Loudest fun per dollar in the building.',
    'baccarat': "Zero decisions, low edge, fast. The house's favourite game for a reason.",
    'ultimate-texas-holdem': "Poker's costume, house's rules. Fun, strategic, and priced fairly if you raise 4x when you should.",
    'three-card-poker': 'One decision (Q-6-4), one trap (Pair Plus), one pleasant hour.',
    'roulette': 'Elegant, slow, and every bet on the felt costs the same — pick the wheel, not the bet.',
    'slots': "The only game where the price is a secret. That's the tell.",
}
SIM_INTRO = {
    'blackjack': "Play a thousand sessions of basic strategy and watch how long the half-percent edge stays invisible — then switch the table to 6:5 and watch it stop hiding.",
    'video-poker': "The same 500 hands on a 9/6 machine and an 8/5 machine, side by side, is the most persuasive argument on this page. Try both.",
    'craps': "Pass line with full odds, then any seven, at the same unit and the same number of bets. That's the whole craps lesson in two runs.",
    'baccarat': "Banker at 1.06% looks like nothing per hand. Run 700 hands — a long evening at the big table — and see what nothing adds up to.",
    'ultimate-texas-holdem': "The variance here is the story: 4x raises make the swings enormous even though the edge on the money is only half a percent.",
    'three-card-poker': "Ante & Play versus Pair Plus on the 6-3-1 table, same unit, same hands. One of these is a game and one is a donation.",
    'roulette': "Same bet, three wheels. Run even money on single zero, double zero and triple zero and watch the median line steepen.",
}
SIM_SESSIONS = {'baccarat': 700}   # default bets per simulated session is 500
AP_MARKER = '    <div class="ap">'    # the advantage-play box; the simulator goes just above it
NAVSCRIPT = '<script src="/assets/site.js" defer></script>'   # shared menu script; tools/chrome.py writes the nav

EXTRA_CSS = r'''
  /* ===== SPLIT PAGES: game cards on the index, page nav, simulator ===== */
  .gamegrid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:28px;}
  @media(max-width:980px){.gamegrid{grid-template-columns:repeat(2,1fr);}}
  @media(max-width:520px){.gamegrid{grid-template-columns:1fr;}}
  a.gcard{display:flex;flex-direction:column;gap:10px;background:var(--card);border:1px solid var(--gold-line-soft);border-radius:14px;padding:22px;transition:border-color .15s, box-shadow .2s;}
  a.gcard:hover{border-color:var(--gold-line);box-shadow:0 0 30px rgba(255,201,94,.08);}
  a.gcard .top{display:flex;align-items:center;justify-content:space-between;gap:10px;}
  a.gcard h3{font-family:'Cinzel',Georgia,serif;font-size:18px;font-weight:600;letter-spacing:.5px;}
  a.gcard p{color:var(--dim);font-size:14px;line-height:1.6;flex:1;}
  a.gcard .more{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:2.5px;color:var(--cyan);}
  a.gcard:hover .more{color:var(--cyan-neon);}
  .famtabs{display:flex;flex-wrap:wrap;gap:8px;padding:18px 0 0;}
  .famtabs a{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:2.5px;text-transform:uppercase;color:var(--dim);border:1px solid var(--line);border-radius:6px;padding:8px 14px;transition:color .15s,border-color .15s;}
  .famtabs a:hover{color:var(--cyan-neon);border-color:var(--cyan);}
  .famtabs a.on{color:var(--gold);border-color:var(--gold);}
  .crumbs{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--dim2);padding:22px 0 0;}
  .crumbs a{color:var(--gold);} .crumbs a:hover{color:var(--gold-hi);}
  .crumbs span{margin:0 8px;color:var(--dim2);}
  .game.first{border-top:0;padding-top:34px;}
  .pagenav{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 0 60px;}
  @media(max-width:600px){.pagenav{grid-template-columns:1fr;}}
  .pagenav a{display:block;background:var(--card);border:1px solid var(--gold-line-soft);border-radius:12px;padding:18px 20px;transition:border-color .15s;}
  .pagenav a:hover{border-color:var(--gold-line);}
  .pagenav a.next{text-align:right;}
  .pagenav .k{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:2.5px;color:var(--cyan);text-transform:uppercase;margin-bottom:6px;}
  .pagenav .t{font-family:'Cinzel',Georgia,serif;font-size:17px;font-weight:600;}
  .allgames{text-align:center;padding:0 0 56px;}
  /* simulator */
  .simsec{margin-top:34px;border:1px solid var(--gold-line);border-radius:14px;padding:26px 26px 22px;background:linear-gradient(180deg,rgba(217,168,92,.05),rgba(6,5,11,0));}
  @media(max-width:600px){.simsec{padding:20px 16px 16px;}}
  .simsec .kicker{font-size:12px;letter-spacing:4px;}
  .simsec h3.simhead{font-family:'Cinzel',Georgia,serif;font-size:clamp(20px,2.4vw,27px);font-weight:600;margin:10px 0 8px;}
  .simsec h3.simhead em{font-style:normal;color:var(--pink-neon);text-shadow:var(--glow-pink);}
  .simsec p.simsub{color:var(--dim);font-size:15px;max-width:760px;margin-bottom:18px;}
  .simsec p.simsub b{color:var(--cream);font-weight:500;}
  .simform{display:flex;flex-wrap:wrap;gap:12px 16px;align-items:flex-end;}
  .simfield{display:flex;flex-direction:column;gap:6px;min-width:0;}
  .simfield .k{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:2.5px;text-transform:uppercase;color:var(--gold);}
  .simfield select,.simfield input{background:var(--bg2);color:var(--cream);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font:500 14px 'DM Sans',Arial,sans-serif;min-width:0;}
  .simfield select{max-width:100%;width:min(100%,420px);}
  .simfield input{width:120px;font-family:'JetBrains Mono',monospace;}
  .simfield select:focus,.simfield input:focus{outline:2px solid var(--cyan);outline-offset:2px;border-color:var(--cyan);}
  .simhours{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--dim);letter-spacing:.5px;}
  .simbtns{display:flex;gap:10px;flex-wrap:wrap;}
  .simrun{background:var(--gold);color:#140B0C;border:0;border-radius:7px;padding:12px 20px;font:700 14px 'DM Sans',Arial,sans-serif;letter-spacing:.4px;cursor:pointer;box-shadow:var(--glow-gold);}
  .simrun:hover{background:var(--gold-hi);}
  .simroll{background:transparent;color:var(--cyan-neon);border:1px solid var(--cyan);border-radius:7px;padding:12px 16px;font:700 14px 'DM Sans',Arial,sans-serif;cursor:pointer;box-shadow:var(--glow-cyan);}
  .simroll:hover{background:rgba(31,203,227,.10);}
  .simmeta{margin:16px 0 14px;font-size:13.5px;color:var(--dim);line-height:1.7;}
  .simmeta b{color:var(--cream);font-weight:500;} .simmeta .dim{color:var(--dim2);}
  .simstats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;}
  @media(max-width:980px){.simstats{grid-template-columns:repeat(2,1fr);}}
  @media(max-width:460px){.simstats{grid-template-columns:1fr;}}
  .st{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-width:0;}
  .st .k{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--dim);margin-bottom:6px;}
  .st .v{font-family:'JetBrains Mono',monospace;font-size:19px;font-weight:500;color:var(--cream);line-height:1.25;overflow-wrap:anywhere;}
  .st.up .v{color:var(--green);} .st.dn .v{color:var(--red-neon);}
  .st .s{font-size:12px;color:var(--dim2);margin-top:6px;line-height:1.5;}
  .simchart{margin-top:16px;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--card);}
  .simchart canvas{display:block;width:100%;height:340px;}
  @media(max-width:600px){.simchart canvas{height:260px;}}
  .simlegend{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:10px;font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.5px;color:var(--dim);}
  .simlegend span{display:inline-flex;align-items:center;gap:7px;}
  .simlegend i{display:inline-block;width:18px;height:3px;border-radius:2px;}
  .l-med{background:var(--gold);} .l-ev{background:repeating-linear-gradient(90deg,var(--gold-hi) 0 5px,transparent 5px 8px);height:2px !important;}
  .l-70{background:rgba(31,203,227,.42);height:10px !important;} .l-95{background:rgba(31,203,227,.20);height:10px !important;} .l-smp{background:rgba(163,153,166,.5);height:1px !important;} .l-best{background:var(--green);} .l-worst{background:var(--red-neon);}
  .simfoot{margin-top:14px;font-size:12.5px;color:var(--dim2);line-height:1.65;}
  .simstory{margin:0 0 10px;font-size:14.5px;color:var(--dim);line-height:1.7;} .simstory b{color:var(--cream);font-weight:500;} .simstory b.up{color:var(--green);} .simstory b.dn{color:var(--red-neon);}
  .simnojs{padding:16px;border:1px dashed var(--line);border-radius:10px;color:var(--dim);font-size:14px;}
  html.js .simnojs{display:none;}
  .slotnote{border:1px solid rgba(224,56,79,.45);background:rgba(224,56,79,.06);border-radius:12px;padding:20px 22px;margin-top:14px;color:var(--dim);font-size:15px;line-height:1.7;}
  .slotnote b{color:var(--cream);font-weight:500;}
'''


def between(s: str, a: str, b: str, start: int = 0) -> tuple[str, int, int]:
    """(s from the first a to the end of the following b, its start, its end); ValueError when absent."""
    i = s.index(a, start)
    j = s.index(b, i) + len(b)
    return s[i:j], i, j


def head(title: str, desc: str, url: str, extra: str = '') -> str:
    t = html.escape(title, quote=False)
    d = html.escape(desc, quote=True)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>document.documentElement.classList.add('js');</script>
<title>{t} — The Tilted Gent</title>
<link rel="icon" type="image/svg+xml" href="../assets/ttg-favicon.svg">
<link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="../assets/apple-touch-icon.png">
<meta name="description" content="{d}">
<meta name="theme-color" content="#06050B">
<meta name="color-scheme" content="dark">
<meta property="og:type" content="article">
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
<link rel="stylesheet" href="/assets/site.css">
<link rel="stylesheet" href="tables.css">
{extra}</head>
<body>

'''


# ---------- the simulator section and its scripts ----------

SLOTS_NOTE = '''
    <div class="simsec" id="sim">
      <div class="kicker">Feel the edge</div>
      <h3 class="simhead">No simulator for slots &mdash; <em>and that's the point</em>.</h3>
      <div class="slotnote"><b>Slot outcome distributions are not published.</b> Every other game on this site has a simulator because its odds are knowable: the deck, the dice and the wheel are public, and the paytable is printed on the felt or the glass. A slot machine's return and hit frequency are set by the casino from a menu the manufacturer provides, are not displayed anywhere, and vary wildly from one machine to the next &mdash; two identical cabinets can be set years apart in expected cost. Any simulation would be a guess dressed up as a chart, which is exactly the trick the machine itself is playing. <b>What we do know is enough:</b> reported holds run from roughly 2&ndash;4% in high-limit rooms to 10&ndash;15% on penny games and bar tops, at 500&ndash;900 spins an hour. At those numbers a slot is the worst bet in the building by a wide margin, and no amount of simulating changes that. If you want to see what a fast, high-edge game does to a bankroll, run the <a href="craps.html#bet=any-seven&amp;unit=2&amp;n=1200" style="color:var(--cyan-neon)">any-seven bet on the craps page</a> at $2 for 1,200 bets &mdash; that's a penny slot on a good day.</div>
    </div>'''


def sim_section(em: str, sub: str, nojs: str) -> str:
    return f'''
    <div class="simsec" id="sim">
      <div class="kicker">Feel the edge</div>
      <h3 class="simhead">Run a session <em>{em}</em>.</h3>
      <p class="simsub">{sub}</p>
      <div id="simmount"><div class="simnojs">{nojs}</div></div>
    </div>'''


def game_sim(gid: str) -> str:
    if gid == 'slots':
        return SLOTS_NOTE
    return sim_section('before you sit down',
                       "Pick a bet, a unit and a number of bets. The simulator plays <b>1,000 sessions from the bet's actual outcome table</b> &mdash; not a normal approximation &mdash; and shows the spread, the drawdowns, and how long it takes before the house edge stops hiding behind luck. " + SIM_INTRO[gid],
                       'The simulator needs JavaScript. The house edge on every bet is in the table above; the simulator only shows what it feels like.')


def variant_sim() -> str:
    return sim_section('at each variant',
                       "Pick a variant and a rule set. The simulator plays <b>1,000 sessions</b> from a result shape calibrated to the published house edge (these are labelled approximate &mdash; the variants don't have the clean combinatorics of a single bet). Try Spanish 21 against Super Fun 21 at the same unit: same cards, a percentage point apart.",
                       'The simulator needs JavaScript. The house edge on every variant is in the table above.')


def sim_scripts(game: str) -> str:
    return f'''
<script src="sim/games.js"></script>
<script src="sim/ttg-sim.js"></script>
<script>TTGSim.mount('#simmount', {{game: '{game}', n: {SIM_SESSIONS.get(game, 500)}}});</script>'''


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
            links = ''.join('<a href="%s"%s>%s</a>' % (h, ' class="on"' if h == slug + '.html' else '', t) for h, t in tabs)
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
    sec = section.replace('<section class="game" id="%s">' % gid, '<section class="game first" id="%s">' % gid, 1)
    if sec.count(AP_MARKER) != 1:
        raise ValueError(f'{gid}: expected exactly one advantage-play box in the source section')
    return sec.replace(AP_MARKER, sim + '\n' + AP_MARKER, 1)


class Site:
    """The pieces of the source every page is assembled from."""

    def __init__(self, src: str) -> None:
        css, _, _ = between(src, '<style>', '</style>')
        self.css = css[len('<style>'):-len('</style>')]
        self.nav = between(src, '<!-- ================= NAV ================= -->', '</nav>')[0]
        self.footer = between(src, '<!-- ================= FOOTER ================= -->', '</footer>')[0]
        self.hero = between(src, '<!-- ================= HERO ================= -->', '</div>\n</div>\n')[0]
        self.board = between(src, '<!-- ================= GRADE BOARD ================= -->', '</section>')[0]
        self.method = between(src, '<!-- ================= METHOD ================= -->', '</section>')[0]
        self.outro = between(src, '<!-- ================= OUTRO ================= -->', '</section>')[0]
        self.sections = {g.id: between(src, '<section class="game" id="%s">' % g.id, '</section>')[0]
                         for g in GAMES + FAMILY_PAGES}

    def body(self, crumb: str, tabs: str, sec: str, links: str, scripts: str) -> str:
        return (self.nav + '\n\n' + crumb + ('\n' + tabs if tabs else '') + '\n\n' + sec + '\n\n' + links + '\n\n'
                + self.footer + '\n\n' + NAVSCRIPT + scripts + '\n</body>\n</html>\n')


def write(name: str, text: str) -> None:
    with open(os.path.join(ROOT, name), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def game_page(site: Site, i: int, g: Game) -> None:
    sec = with_sim(site.sections[g.id], g.id, game_sim(g.id))
    if g.id == 'blackjack':
        sec = sec.replace(AP_MARKER, '''    <div class="callout" style="margin-top:22px;border-left-color:var(--cyan);background:rgba(31,203,227,.05);"><b>Practice room.</b> The <a href="blackjack-trainer.html" style="color:var(--cyan-neon)">Blackjack Trainer</a> is a simulated table for learning the chart and then the count: choose decks and rules, seat other players, set the deal speed, get every decision graded, and check your running count against the real one. &rarr;</div>
''' + AP_MARKER, 1)
    links = page_links(GAMES[i - 1] if i > 0 else None, GAMES[i + 1] if i < len(GAMES) - 1 else None)
    scripts = '' if g.id == 'slots' else sim_scripts(g.id)
    body = site.body(crumbs(g.title), family_tabs(g.slug), sec, links, scripts)
    write(g.slug + '.html', head(g.title + ', graded', g.desc, g.slug + '.html') + body)


def family_page(site: Site, p: FamilyPage) -> None:
    by_slug = {g.slug: g for g in GAMES}
    prev, nxt = by_slug[p.prev], by_slug[p.next]
    sec = with_sim(site.sections[p.id], p.id, variant_sim())
    body = site.body(crumbs((f'{prev.slug}.html', prev.title), p.title), family_tabs(p.slug), sec,
                     page_links(prev, nxt), sim_scripts(p.sim_game))
    write(p.slug + '.html', head(p.title + ', graded', p.desc, p.slug + '.html') + body)


def index_page(site: Site) -> None:
    board = site.board
    for g in GAMES:
        board = board.replace(f'href="#{g.id}"', f'href="{g.slug}.html"')
    hero = site.hero.replace('<span class="stat"><b>60+</b> BETS PRICED</span>', '<span class="stat"><b>60+</b> BETS PRICED</span>\n        <span class="stat"><b>7</b> VARIANCE SIMULATORS</span>')
    hero = hero.replace("and where a disciplined player can flip the edge — legally. Then a grade, so you know what a night at each table is worth.",
                        "and where a disciplined player can flip the edge — legally. Each game has its own page with a <b>variance simulator</b> that plays a thousand sessions from the real odds, and a grade, so you know what a night at each table is worth.")
    cards = ''
    for g in GAMES:
        gc, gl = GRADES[g.id]
        more = 'READ THE ANALYSIS' if g.id == 'slots' else ('ANALYSIS · VARIANTS · TRAINER' if g.id == 'blackjack' else 'ANALYSIS + SIMULATOR')
        cards += f'''      <a class="gcard" href="{g.slug}.html"><div class="top"><h3>{html.escape(g.title, quote=False)}</h3><span class="grade {gc} sm">{gl}</span></div><p>{ONELINE[g.id]}</p><span class="more">{more} &rarr;</span></a>\n'''
    games_section = f'''<!-- ================= GAME PAGES ================= -->
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
    body = (site.nav + '\n\n' + hero + '\n' + board + '\n\n' + games_section + '\n' + site.method + '\n\n' + site.outro
            + '\n\n' + site.footer + '\n\n' + NAVSCRIPT + '\n</body>\n</html>\n')
    index_head = head('Casino Games, Graded', 'Eight casino games, graded honestly: how each one plays, the house edge on every bet, the best and worst bets, the quirks, advantage play — and a variance simulator on every game page.',
                      'casino-games.html').replace('property="og:type" content="article"', 'property="og:type" content="website"')
    write('casino-games.html', index_head + body)


def main() -> None:
    with open(SRC, encoding='utf-8') as fh:
        site = Site(fh.read())
    write('tables.css', site.css.strip('\n') + '\n' + EXTRA_CSS)
    for i, g in enumerate(GAMES):
        game_page(site, i, g)
    for p in FAMILY_PAGES:
        family_page(site, p)
    index_page(site)
    print('built', len(GAMES), 'game pages +', len(FAMILY_PAGES), 'family pages + index + tables.css')


if __name__ == '__main__':
    main()
