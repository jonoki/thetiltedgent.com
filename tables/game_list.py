"""The Tables pages' game list: one Game record per game on the grade board, the family pages that are not on
the board, and the family tab strips. Per-page prose that is not in the source page (the board one-liner, the
simulator intro or the note saying why there is none, the card link label, a callout) lives here;
tables/build_tables.py builds from it."""
from typing import NamedTuple

DEFAULT_BETS_PER_SESSION = 500   # bets in each simulated session unless a game sets its own
SLOTS_NO_SIM_NOTE = '''
    <div class="simsec" id="sim">
      <div class="kicker">Feel the edge</div>
      <h3 class="simhead">No simulator for slots &mdash; <em>and that's the point</em>.</h3>
      <div class="slotnote"><b>Slot outcome distributions are not published.</b> Every other game on this site has a simulator because its odds are knowable: the deck, the dice and the wheel are public, and the paytable is printed on the felt or the glass. A slot machine's return and hit frequency are set by the casino from a menu the manufacturer provides, are not displayed anywhere, and vary wildly from one machine to the next &mdash; two identical cabinets can be set years apart in expected cost. Any simulation would be a guess dressed up as a chart, which is exactly the trick the machine itself is playing. <b>What we do know is enough:</b> reported holds run from roughly 2&ndash;4% in high-limit rooms to 10&ndash;15% on penny games and bar tops, at 500&ndash;900 spins an hour. At those numbers a slot is the worst bet in the building by a wide margin, and no amount of simulating changes that. If you want to see what a fast, high-edge game does to a bankroll, run the <a href="craps.html#bet=any-seven&amp;unit=2&amp;n=1200" style="color:var(--cyan-neon)">any-seven bet on the craps page</a> at $2 for 1,200 bets &mdash; that's a penny slot on a good day.</div>
    </div>'''

CRAPS_TABLE_CALLOUT = '''    <div class="callout" style="margin-top:22px;border-left-color:var(--cyan);background:rgba(31,203,227,.05);"><b>Practice table.</b> The <a href="craps-table.html" style="color:var(--cyan-neon)">Craps Table</a> is a full layout with fair dice and play money: put chips anywhere on the felt and see what each bet pays, its true odds and its exact house edge before you roll, with a session recap that separates the house edge from luck. &rarr;</div>'''
BACCARAT_TABLE_CALLOUT = '''    <div class="callout" style="margin-top:22px;border-left-color:var(--cyan);background:rgba(31,203,227,.05);"><b>Practice table.</b> The <a href="baccarat-table.html" style="color:var(--cyan-neon)">Baccarat Table</a> deals a real eight-deck shoe by the drawing rules, with play money: put chips on Banker, Player, Tie or the pairs and see each bet&rsquo;s exact house edge and what your bets are worth before the cards come out, with a session recap that separates the house edge from luck. &rarr;</div>'''
TCP_TABLE_CALLOUT = '''    <div class="callout" style="margin-top:22px;border-left-color:var(--cyan);background:rgba(31,203,227,.05);"><b>Practice table.</b> The <a href="three-card-poker-table.html" style="color:var(--cyan-neon)">Three Card Poker Table</a> deals real hands with play money: bet the Ante and Pair Plus, see your three cards, and get the exact value of playing and of folding against every hand the dealer could hold, with a session recap that separates the house edge, your decisions and luck. &rarr;</div>'''
BLACKJACK_TRAINER_CALLOUT = '''    <div class="callout" style="margin-top:22px;border-left-color:var(--cyan);background:rgba(31,203,227,.05);"><b>Practice room.</b> The <a href="blackjack-trainer.html" style="color:var(--cyan-neon)">Blackjack Trainer</a> is a simulated table for learning the chart and then the count: choose decks and rules, seat other players, set the deal speed, get every decision graded, and check your running count against the real one. &rarr;</div>'''


class Game(NamedTuple):
    """A game on the grade board and its page: the <section id> in the source, page slug, title, meta description,
    grade (CSS class, label), the board card's one-liner and link label, and its simulator: the intro sentence and
    bets per session, or (sim_intro None) the no_sim_note shown instead. callout goes above the advantage-play box."""
    id: str
    slug: str
    title: str
    desc: str
    grade: tuple[str, str]
    oneline: str
    sim_intro: str | None
    bets_per_session: int = DEFAULT_BETS_PER_SESSION
    more: str = 'ANALYSIS + SIMULATOR'
    callout: str = ''
    no_sim_note: str = ''


class FamilyPage(NamedTuple):
    """A page in a game's family that is not on the grade board: its simulator game and intro, and page neighbours."""
    id: str
    slug: str
    title: str
    desc: str
    sim_game: str
    prev: str
    next: str
    sim_intro: str


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
         "Pass line with full odds, then any seven, at the same unit and the same number of bets. That's the whole craps lesson in two runs.", more='ANALYSIS · SIMULATOR · TABLE', callout=CRAPS_TABLE_CALLOUT),
    Game('baccarat', 'baccarat', 'Baccarat',
         'Baccarat: coin-flipping in a tuxedo — Banker vs Player vs Tie, side bets, edge sorting, and a variance simulator.',
         ('b', 'B'), "Zero decisions, low edge, fast. The house's favourite game for a reason.",
         "Banker at 1.06% looks like nothing per hand. Run 700 hands — a long evening at the big table — and see what nothing adds up to.",
         bets_per_session=700, more='ANALYSIS · SIMULATOR · TABLE', callout=BACCARAT_TABLE_CALLOUT),
    Game('ultimate-texas-holdem', 'ultimate-texas-holdem', "Ultimate Texas Hold'em",
         "Ultimate Texas Hold'em: poker's costume, the house's rules — raise strategy, Trips paytables, hole-carding, and a variance simulator.",
         ('b', 'B&minus;'), "Poker's costume, house's rules. Fun, strategic, and priced fairly if you raise 4x when you should.",
         "The variance here is the story: 4x raises make the swings enormous even though the edge on the money is only half a percent."),
    Game('three-card-poker', 'three-card-poker', 'Three Card Poker',
         'Three Card Poker: one decision, one trap — Q-6-4, Pair Plus paytables, and a variance simulator.',
         ('c', 'C+'), 'One decision (Q-6-4), one trap (Pair Plus), one pleasant hour.',
         "Ante & Play versus Pair Plus on the 6-3-1 table, same unit, same hands. One of these is a game and one is a donation.",
         more='ANALYSIS · SIMULATOR · TABLE', callout=TCP_TABLE_CALLOUT),
    Game('roulette', 'roulette', 'Roulette',
         'Roulette: pick the wheel, not the bet — single, double and triple zero, la partage, wheel bias, and a variance simulator.',
         ('c', 'C&minus;'), 'Elegant, slow, and every bet on the felt costs the same — pick the wheel, not the bet.',
         "Same bet, three wheels. Run even money on single zero, double zero and triple zero and watch the median line steepen."),
    Game('slots', 'slots', 'Slots',
         'Slots: the only game where the price is a secret — reported holds by denomination, the design tricks, and why there is no simulator.',
         ('d', 'D'), "The only game where the price is a secret. That's the tell.",
         None, more='READ THE ANALYSIS', no_sim_note=SLOTS_NO_SIM_NOTE),
]
FAMILY_PAGES = [
    FamilyPage('blackjack-variants', 'blackjack-variants', 'Blackjack Variants', 'Free Bet Blackjack, Blackjack Switch, Spanish 21, Double Exposure and Super Fun 21: what each gives, what each takes back, the house edge with the right chart, and a variance simulator.', 'blackjack-variants', 'blackjack', 'video-poker',
               "Pick a variant and a rule set. The simulator plays <b>1,000 sessions</b> from a result shape calibrated to the published house edge (these are labelled approximate &mdash; the variants don't have the clean combinatorics of a single bet). Try Spanish 21 against Super Fun 21 at the same unit: same cards, a percentage point apart."),
]
FAMILY_TABS = {'blackjack': [('blackjack.html', 'Blackjack'), ('blackjack-variants.html', 'Variants'), ('blackjack-trainer.html', 'Trainer')],
               'craps': [('craps.html', 'Craps'), ('craps-table.html', 'Table')],
               'baccarat': [('baccarat.html', 'Baccarat'), ('baccarat-table.html', 'Table')],
               'three-card-poker': [('three-card-poker.html', 'Three Card Poker'), ('three-card-poker-table.html', 'Table')]}
