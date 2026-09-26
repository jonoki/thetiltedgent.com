"""The Tables pages' game list: one Game record per game on the grade board, the family pages that are not on
the board, and the family tab strips. Per-game prose that is not in the source page (the board one-liner, the
simulator intro, the card link label, a callout) lives here; tables/build_tables.py builds from it."""
from typing import NamedTuple

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
