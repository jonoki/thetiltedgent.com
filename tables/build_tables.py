#!/usr/bin/env python3
"""Split tables/casino-games.html into one page per game + an index, with the variance simulator.
Run from the repo root: python3 tables/build_tables.py
Source of truth for the prose is tables/_source/casino-games-source.html (the original single page)."""
import re, os, html

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, '_source', 'casino-games-source.html')
src = open(SRC, encoding='utf-8').read()

GAMES = [  # id, slug, title, short name, og description
    ('blackjack', 'blackjack', 'Blackjack', 'Blackjack: the only game where the house shows you its hand — rules, house edge on every bet, 6:5 vs 3:2, card counting, and a variance simulator.'),
    ('video-poker', 'video-poker', 'Video Poker', 'Video Poker: the slot machine that tells you the truth — paytables, returns, strategy, advantage play, and a variance simulator.'),
    ('craps', 'craps', 'Craps', 'Craps: two great bets and forty terrible ones — house edge on every bet, best and worst bets, dice control, and a variance simulator.'),
    ('baccarat', 'baccarat', 'Baccarat', 'Baccarat: coin-flipping in a tuxedo — Banker vs Player vs Tie, side bets, edge sorting, and a variance simulator.'),
    ('ultimate-texas-holdem', 'ultimate-texas-holdem', "Ultimate Texas Hold'em", "Ultimate Texas Hold'em: poker's costume, the house's rules — raise strategy, Trips paytables, hole-carding, and a variance simulator."),
    ('three-card-poker', 'three-card-poker', 'Three Card Poker', 'Three Card Poker: one decision, one trap — Q-6-4, Pair Plus paytables, and a variance simulator.'),
    ('roulette', 'roulette', 'Roulette', 'Roulette: pick the wheel, not the bet — single, double and triple zero, la partage, wheel bias, and a variance simulator.'),
    ('slots', 'slots', 'Slots', 'Slots: the only game where the price is a secret — reported holds by denomination, the design tricks, and why there is no simulator.'),
]
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

def between(s, a, b, start=0):
    i = s.index(a, start); j = s.index(b, i) + len(b)
    return s[i:j], i, j

# ---------- pieces of the source ----------
css, _, _ = between(src, '<style>', '</style>')
css = css[len('<style>'):-len('</style>')]
nav, _, _ = between(src, '<!-- ================= NAV ================= -->', '</nav>')
footer, _, _ = between(src, '<!-- ================= FOOTER ================= -->', '</footer>')
navscript, _, _ = between(src, '<script>\n/* Mobile nav toggle.', '</script>')
hero, _, _ = between(src, '<!-- ================= HERO ================= -->', '</div>\n</div>\n')
board, _, _ = between(src, '<!-- ================= GRADE BOARD ================= -->', '</section>')
method, _, _ = between(src, '<!-- ================= METHOD ================= -->', '</section>')
outro, _, _ = between(src, '<!-- ================= OUTRO ================= -->', '</section>')
sections = {}
for gid, *_ in GAMES:
    sec, _, _ = between(src, '<section class="game" id="%s">' % gid, '</section>')
    sections[gid] = sec

# ---------- extra CSS for the split pages ----------
extra_css = r'''
  /* ===== SPLIT PAGES: game cards on the index, page nav, simulator ===== */
  .gamegrid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:28px;}
  @media(max-width:980px){.gamegrid{grid-template-columns:repeat(2,1fr);}}
  @media(max-width:520px){.gamegrid{grid-template-columns:1fr;}}
  a.gcard{display:flex;flex-direction:column;gap:10px;background:var(--card);border:1px solid var(--gold-line-soft);border-radius:14px;padding:22px;transition:border-color .15s, box-shadow .2s;}
  a.gcard:hover{border-color:var(--gold-line);box-shadow:0 0 30px rgba(255,201,94,.08);}
  a.gcard .top{display:flex;align-items:center;justify-content:space-between;gap:10px;}
  a.gcard h3{font-family:'Cinzel',Georgia,serif;font-size:18px;font-weight:600;letter-spacing:.5px;}
  a.gcard p{color:var(--dim);font-size:14px;line-height:1.6;flex:1;}
  a.gcard .more{font-family:'JetBrains Mono',monospace;font-size:11.5px;letter-spacing:2.5px;color:var(--cyan);}
  a.gcard:hover .more{color:var(--cyan-neon);}
  .crumbs{font-family:'JetBrains Mono',monospace;font-size:11.5px;letter-spacing:2px;text-transform:uppercase;color:var(--dim2);padding:22px 0 0;}
  .crumbs a{color:var(--gold);} .crumbs a:hover{color:var(--gold-hi);}
  .crumbs span{margin:0 8px;color:var(--dim2);}
  .game.first{border-top:0;padding-top:34px;}
  .pagenav{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 0 60px;}
  @media(max-width:600px){.pagenav{grid-template-columns:1fr;}}
  .pagenav a{display:block;background:var(--card);border:1px solid var(--gold-line-soft);border-radius:12px;padding:18px 20px;transition:border-color .15s;}
  .pagenav a:hover{border-color:var(--gold-line);}
  .pagenav a.next{text-align:right;}
  .pagenav .k{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2.5px;color:var(--cyan);text-transform:uppercase;margin-bottom:6px;}
  .pagenav .t{font-family:'Cinzel',Georgia,serif;font-size:17px;font-weight:600;}
  .allgames{text-align:center;padding:0 0 56px;}
  /* simulator */
  .simsec{margin-top:34px;border:1px solid var(--gold-line);border-radius:14px;padding:26px 26px 22px;background:linear-gradient(180deg,rgba(217,168,92,.05),rgba(6,5,11,0));}
  @media(max-width:600px){.simsec{padding:20px 16px 16px;}}
  .simsec .kicker{font-size:11.5px;letter-spacing:4px;}
  .simsec h3.simhead{font-family:'Cinzel',Georgia,serif;font-size:clamp(20px,2.4vw,27px);font-weight:600;margin:10px 0 8px;}
  .simsec h3.simhead em{font-style:normal;color:var(--pink-neon);text-shadow:var(--glow-pink);}
  .simsec p.simsub{color:var(--dim);font-size:15px;max-width:760px;margin-bottom:18px;}
  .simsec p.simsub b{color:var(--cream);font-weight:500;}
  .simform{display:flex;flex-wrap:wrap;gap:12px 16px;align-items:flex-end;}
  .simfield{display:flex;flex-direction:column;gap:6px;min-width:0;}
  .simfield .k{font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:2.5px;text-transform:uppercase;color:var(--gold);}
  .simfield select,.simfield input{background:var(--bg2);color:var(--cream);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font:500 14px 'DM Sans',Arial,sans-serif;min-width:0;}
  .simfield select{max-width:100%;width:min(100%,420px);}
  .simfield input{width:120px;font-family:'JetBrains Mono',monospace;}
  .simfield select:focus,.simfield input:focus{outline:2px solid var(--cyan);outline-offset:2px;border-color:var(--cyan);}
  .simhours{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--dim);letter-spacing:.5px;}
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
  .st .k{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--dim);margin-bottom:6px;}
  .st .v{font-family:'JetBrains Mono',monospace;font-size:19px;font-weight:500;color:var(--cream);line-height:1.25;overflow-wrap:anywhere;}
  .st.up .v{color:var(--green);} .st.dn .v{color:var(--red-neon);}
  .st .s{font-size:12px;color:var(--dim2);margin-top:6px;line-height:1.5;}
  .simchart{margin-top:16px;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--card);}
  .simchart canvas{display:block;width:100%;height:340px;}
  @media(max-width:600px){.simchart canvas{height:260px;}}
  .simlegend{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:10px;font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:.5px;color:var(--dim);}
  .simlegend span{display:inline-flex;align-items:center;gap:7px;}
  .simlegend i{display:inline-block;width:18px;height:3px;border-radius:2px;}
  .l-med{background:var(--gold);} .l-ev{background:repeating-linear-gradient(90deg,var(--gold-hi) 0 5px,transparent 5px 8px);height:2px !important;}
  .l-70{background:rgba(31,203,227,.42);height:10px !important;} .l-95{background:rgba(31,203,227,.20);height:10px !important;} .l-smp{background:rgba(163,153,166,.5);height:1px !important;}
  .simfoot{margin-top:14px;font-size:12.5px;color:var(--dim2);line-height:1.65;}
  .simnojs{padding:16px;border:1px dashed var(--line);border-radius:10px;color:var(--dim);font-size:14px;}
  html.js .simnojs{display:none;}
  .slotnote{border:1px solid rgba(224,56,79,.45);background:rgba(224,56,79,.06);border-radius:12px;padding:20px 22px;margin-top:14px;color:var(--dim);font-size:15px;line-height:1.7;}
  .slotnote b{color:var(--cream);font-weight:500;}
'''
open(os.path.join(ROOT, 'tables.css'), 'w', encoding='utf-8').write(css.strip('\n') + '\n' + extra_css)

# ---------- shared head ----------
def head(title, desc, url, extra=''):
    t = html.escape(title, quote=False); d = html.escape(desc, quote=True)
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
<link rel="stylesheet" href="tables.css">
{extra}</head>
<body>

'''

SIM_INTRO = {
    'blackjack': "Play a thousand sessions of basic strategy and watch how long the half-percent edge stays invisible — then switch the table to 6:5 and watch it stop hiding.",
    'video-poker': "The same 500 hands on a 9/6 machine and an 8/5 machine, side by side, is the most persuasive argument on this page. Try both.",
    'craps': "Pass line with full odds, then any seven, at the same unit and the same number of bets. That's the whole craps lesson in two runs.",
    'baccarat': "Banker at 1.06% looks like nothing per hand. Run 700 hands — a long evening at the big table — and see what nothing adds up to.",
    'ultimate-texas-holdem': "The variance here is the story: 4x raises make the swings enormous even though the edge on the money is only half a percent.",
    'three-card-poker': "Ante & Play versus Pair Plus on the 6-3-1 table, same unit, same hands. One of these is a game and one is a donation.",
    'roulette': "Same bet, three wheels. Run even money on single zero, double zero and triple zero and watch the median line steepen.",
}

def sim_block(gid):
    if gid == 'slots':
        return '''
    <div class="simsec" id="sim">
      <div class="kicker">Feel the edge</div>
      <h3 class="simhead">No simulator for slots &mdash; <em>and that's the point</em>.</h3>
      <div class="slotnote"><b>Slot outcome distributions are not published.</b> Every other game on this site has a simulator because its odds are knowable: the deck, the dice and the wheel are public, and the paytable is printed on the felt or the glass. A slot machine's return and hit frequency are set by the casino from a menu the manufacturer provides, are not displayed anywhere, and vary wildly from one machine to the next &mdash; two identical cabinets can be set years apart in expected cost. Any simulation would be a guess dressed up as a chart, which is exactly the trick the machine itself is playing. <b>What we do know is enough:</b> reported holds run from roughly 2&ndash;4% in high-limit rooms to 10&ndash;15% on penny games and bar tops, at 500&ndash;900 spins an hour. At those numbers a slot is the worst bet in the building by a wide margin, and no amount of simulating changes that. If you want to see what a fast, high-edge game does to a bankroll, run the <a href="craps.html#bet=any-seven&amp;unit=2&amp;n=1200" style="color:var(--cyan-neon)">any-seven bet on the craps page</a> at $2 for 1,200 bets &mdash; that's a penny slot on a good day.</div>
    </div>'''
    return f'''
    <div class="simsec" id="sim">
      <div class="kicker">Feel the edge</div>
      <h3 class="simhead">Run a session <em>before you sit down</em>.</h3>
      <p class="simsub">Pick a bet, a unit and a number of bets. The simulator plays <b>1,000 sessions from the bet's actual outcome table</b> &mdash; not a normal approximation &mdash; and shows the spread, the drawdowns, and how long it takes before the house edge stops hiding behind luck. {SIM_INTRO[gid]}</p>
      <div id="simmount"><div class="simnojs">The simulator needs JavaScript. The house edge on every bet is in the table above; the simulator only shows what it feels like.</div></div>
    </div>'''

def page_nav(idx):
    prev = GAMES[idx - 1] if idx > 0 else None
    nxt = GAMES[idx + 1] if idx < len(GAMES) - 1 else None
    a = ''
    if prev: a += f'<a class="prev" href="{prev[1]}.html"><div class="k">&larr; Previous</div><div class="t">{prev[2]}</div></a>'
    else: a += '<span></span>'
    if nxt: a += f'<a class="next" href="{nxt[1]}.html"><div class="k">Next &rarr;</div><div class="t">{nxt[2]}</div></a>'
    return f'<div class="wrap pagenav">{a}</div><div class="wrap allgames"><a class="btn ghost" href="casino-games.html#board">&larr; All eight games, graded</a></div>'

def nav_for(current):
    n = nav.replace('<a href="casino-games.html">The Tables</a>', '<a href="casino-games.html" aria-current="page">The Tables</a>')
    return n

# ---------- game pages ----------
for i, (gid, slug, title, desc) in enumerate(GAMES):
    sec = sections[gid]
    sec = sec.replace('<section class="game" id="%s">' % gid, '<section class="game first" id="%s">' % gid, 1)
    # insert the simulator between the body grid and the advantage-play box
    marker = '    <div class="ap">'
    assert sec.count(marker) == 1, gid
    sec = sec.replace(marker, sim_block(gid) + '\n' + marker, 1)
    scripts = '' if gid == 'slots' else f'''
<script src="sim/games.js"></script>
<script src="sim/ttg-sim.js"></script>
<script>TTGSim.mount('#simmount', {{game: '{gid}', n: {'700' if gid == 'baccarat' else '500'}}});</script>'''
    crumbs = f'<div class="wrap crumbs"><a href="../">Home</a><span>/</span><a href="casino-games.html">The Tables</a><span>/</span>{html.escape(title, quote=False)}</div>'
    body = nav_for(gid) + '\n\n' + crumbs + '\n\n' + sec + '\n\n' + page_nav(i) + '\n\n' + footer + '\n\n' + navscript + scripts + '\n</body>\n</html>\n'
    out = head(title + ', graded', desc, slug + '.html') + body
    open(os.path.join(ROOT, slug + '.html'), 'w', encoding='utf-8').write(out)

# ---------- index ----------
board_i = board
for gid, slug, title, desc in GAMES:
    board_i = board_i.replace(f'href="#{gid}"', f'href="{slug}.html"')
hero_i = hero.replace('<span class="stat"><b>60+</b> BETS PRICED</span>', '<span class="stat"><b>60+</b> BETS PRICED</span>\n        <span class="stat"><b>7</b> VARIANCE SIMULATORS</span>')
hero_i = hero_i.replace("and where a disciplined player can flip the edge — legally. Then a grade, so you know what a night at each table is worth.",
                        "and where a disciplined player can flip the edge — legally. Each game has its own page with a <b>variance simulator</b> that plays a thousand sessions from the real odds, and a grade, so you know what a night at each table is worth.")
cards = ''
for gid, slug, title, desc in GAMES:
    gc, gl = GRADES[gid]
    cards += f'''      <a class="gcard" href="{slug}.html"><div class="top"><h3>{html.escape(title, quote=False)}</h3><span class="grade {gc} sm">{gl}</span></div><p>{ONELINE[gid]}</p><span class="more">{'READ THE ANALYSIS' if gid == 'slots' else 'ANALYSIS + SIMULATOR'} &rarr;</span></a>\n'''
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
index_body = nav + '\n\n' + hero_i + '\n' + board_i + '\n\n' + games_section + '\n' + method + '\n\n' + outro + '\n\n' + footer + '\n\n' + navscript + '\n</body>\n</html>\n'
index_head = head('Casino Games, Graded', 'Eight casino games, graded honestly: how each one plays, the house edge on every bet, the best and worst bets, the quirks, advantage play — and a variance simulator on every game page.', 'casino-games.html').replace('<title>Casino Games, Graded — The Tilted Gent</title>', '<title>Casino Games, Graded — The Tilted Gent</title>').replace('property="og:type" content="article"', 'property="og:type" content="website"')
open(os.path.join(ROOT, 'casino-games.html'), 'w', encoding='utf-8').write(index_head + index_body)
print('built', len(GAMES), 'game pages + index + tables.css')
