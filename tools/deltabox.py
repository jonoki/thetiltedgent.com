#!/usr/bin/env python3
"""Insert the "what changed since the last edition" box into refreshed reports.

Only reports with a genuine prior edition get a box. Every figure below is
taken from the report's own prose or from claude/REFRESH_POLICY.md — nothing is
newly researched here, it is existing analysis given a consistent structure.

Three states, because the refresh run found three genuinely different outcomes:
  price  — the multiple moved, the business did not (5 of the 7)
  print  — the company reported; numbers are new
  fix    — this edition corrects something the previous one got wrong

usage:  py -3 tools/deltabox.py [repo-root]

The records below are the September 2026 refresh editions this script was written for; every one of those
reports has its box, so a run now skips them all. Later refreshes write their own box (claude/briefs/REFRESH.md,
which takes the box CSS from CSS below). The script only ever adds a box where none exists; it never rewrites one.
"""
import datetime
import os
import re
import sys
from typing import NamedTuple

import reportlib as rl


class Edition(NamedTuple):
    """One refreshed report's box: the previous and current editions, the box state (TAGS) and its text."""
    prior_date: str      # YYYY-MM-DD
    prior_price: float
    as_of: str           # YYYY-MM-DD
    price: float
    state: str           # 'price' | 'print' | 'fix'
    claim: str
    paras: list          # body paragraphs (HTML)
    check: str           # the closing "re-verified / not re-verified" line (HTML)


ANCHOR_RE = re.compile(r'<!-- =+ 01 (COMPANY )?OVERVIEW')   # the '=' run length and title vary by era

CSS = """
/* ---- what changed since the last edition ---- */
.tg-d{container-type:inline-size;background:var(--surface);border:1px solid var(--border);
  border-left:3px solid var(--green);border-radius:8px;padding:18px 20px;margin:26px 0 6px}
.tg-d--print{border-left-color:var(--blue)}
.tg-d--fix{border-left-color:var(--amber)}
.tg-d-top{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 12px;margin-bottom:10px}
.tg-d-tag{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1.3px;
  text-transform:uppercase;color:var(--green);background:var(--green-dim);padding:3px 9px;
  border-radius:4px;white-space:nowrap}
.tg-d--print .tg-d-tag{color:var(--blue);background:var(--blue-dim)}
.tg-d--fix .tg-d-tag{color:var(--amber);background:var(--amber-dim)}
.tg-d-when{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text-dim)}
.tg-d-claim{font-size:17px;font-weight:600;color:var(--text);margin:0 0 13px;line-height:1.35}
.tg-d-move{display:flex;flex-wrap:wrap;align-items:flex-end;gap:6px 14px;padding:11px 0;
  border-top:1px solid var(--border);border-bottom:1px solid var(--border);margin-bottom:13px}
.tg-d-px{font-family:'JetBrains Mono',monospace;font-size:15px;color:var(--text);line-height:1.2}
.tg-d-px span{display:block;font-family:'DM Sans',sans-serif;font-size:10px;color:var(--text-dim);
  letter-spacing:.4px;margin-top:3px}
.tg-d-arw{color:var(--text-dim);font-size:15px;align-self:center}
.tg-d-pct{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:15px;margin-left:auto}
.tg-d-pct.up{color:var(--green)}
.tg-d-pct.dn{color:var(--red)}
.tg-d p{font-size:13.5px;line-height:1.62;color:var(--text-muted);margin:0 0 10px}
.tg-d-check{font-size:12.5px;line-height:1.55;color:var(--text-dim);margin:0;padding-top:3px;
  border-top:1px dashed var(--border);margin-top:12px;padding-top:11px}
.tg-d-check b{color:var(--text-muted);font-weight:600}
/* the stat row stacks on its own width, not the viewport: these pages render
   standalone and inside the view.html iframe, where the two differ */
@container (max-width:420px){
  .tg-d-pct{margin-left:0;width:100%;padding-top:4px}
  .tg-d{padding:16px 15px}
  .tg-d-claim{font-size:15.5px}
}
"""

TAGS = {'price': 'Since the last edition',
        'print': 'Updated at the print',
        'fix': 'Corrected in this edition'}

# slug -> the fields of an Edition, in order (built into EDITIONS below)
_RECORDS = {
 'adbe': ('2026-08-17', 254.04, '2026-09-01', 286.08, 'price',
   'The price moved. Nothing else did.',
   ["Adobe has not reported since the previous edition. The rally tracked a broad enterprise-software "
    "and AI re-rating — ServiceNow and Salesforce moved comparably — that accelerated after Nvidia's "
    "August 26 earnings beat eased fears that AI would erode software spending. The stock touched "
    "$292.79 on August 31 before settling."],
   "Re-verified: no earnings report (Q3 FY2026 is still ahead, on September 10), no guidance update, "
   "no new AI-ARR disclosure, no announced change to Creative Cloud pricing. "
   "<b>Every fundamental figure below is unchanged from the August 17 edition; only the price-derived ones moved.</b>"),

 'now': ('2026-08-17', 117.70, '2026-09-01', 142.90, 'price',
   'The price moved. Nothing else did.',
   ["No new operating results were published between the two editions. This was software multiple "
    "expansion, and the cleanest evidence is from the sell side itself: a BofA analyst raised his "
    "price target over the window while stating explicitly that his estimates were unchanged. "
    "The stock closed at $147.99 on August 31, a 25.7% monthly gain, before a −3.44% session on "
    "September 1."],
   "Re-verified: no earnings report, no guidance update, no new disclosure. "
   "<b>Every fundamental figure below is unchanged from the August 17 edition; only the price-derived ones moved.</b>"),

 'stx': ('2026-08-17', 994.79, '2026-09-01', 816.64, 'price',
   'The price fell 17.9%. Seagate did nothing to cause it.',
   ["The decline was a sector-wide memory and storage de-rating, not a company event — contemporaneous "
    "coverage said explicitly that there was no memory-specific bad news. What changed is what "
    "investors will pay for the same earnings stream: 15.2× sales instead of 18.5×, 22.8× forward "
    "earnings instead of 27.8×."],
   "Re-verified: the demand picture, the HAMR position and the two-player structure in Sections 02, 03 "
   "and 06 were last set by the July 28 print and nothing since has touched them. "
   "<b>Only the price-derived figures moved.</b>"),

 'amat': ('2026-08-13', 548.15, '2026-09-01', 441.85, 'print',
   'New numbers from the Q3 FY2026 print. The direction is unchanged.',
   ["Applied reported Q3 FY2026 on August 13 — the same day as the previous edition — and beat on every "
    "line: revenue of $9.115B, +25% year on year, with EPS +41%. Those figures are now in the report. "
    "The share price then fell 19.4% over the window with no adverse fundamental news, alongside "
    "KLA −16%, Seagate −17%, SanDisk −12%: a semicap de-rating, not an Applied problem."],
   "Updated at this edition: the income-statement figures and the year-to-date performance. "
   "<b>Not re-verified, and still carrying their mid-August vintage:</b> the Industry Avg and "
   "NASDAQ-100 comparison columns, and the peer market caps for ASML and Lam."),

 'crm': ('2026-08-24', 209.06, '2026-09-01', 258.11, 'print',
   'The business changed. This edition is substantially rewritten.',
   ["Salesforce reported Q2 FY2027 on August 26: revenue +10.8%, cRPO of $33.5B (+14% in constant "
    "currency), Agentforce ARR above $1.5B, and raised guidance — alongside an announced Anthropic "
    "“Claudeforce” partnership. The stock rose 22.6% in a single session. Sections 02 through 06 "
    "were rewritten against the new numbers rather than adjusted."],
   "Superseded at this edition: the prior $209.06 price basis, the pre-print revenue and cRPO figures, "
   "and the segment framing — Salesforce no longer reports the five legacy clouds, and the report now "
   "follows its Agentforce Apps vs Data 360 split."),

 'gev': ('2026-08-12', 1039.90, '2026-09-01', 898.53, 'fix',
   'The price fell 13.6% on nothing — and this edition fixes a number the last one got wrong.',
   ["<b>The correction:</b> the previous edition carried a <em>modelled</em> FY2025 Electrification "
    "revenue figure that understated the reported number by roughly $540M. It has been replaced with "
    "the $9,642M actually reported in the 4Q25 release on SEC EDGAR. That error came from the August 12 "
    "cohort, which was researched with search constrained and several investor-relations domains blocked.",
    "The price move itself was multiple compression with no company news. Worth noting because it is "
    "commonly misread: short interest <em>fell</em> over the window, from 3.8% to 2.98% — so this was "
    "long liquidation, not a short campaign."],
   "Corrected: FY2025 Electrification segment revenue, now from the reported filing rather than a model. "
   "<b>Re-verified as unchanged:</b> capacity factors, guidance and signed PPAs — nothing broke operationally."),

 'klac': ('2026-08-12', 208.25, '2026-09-01', 170.89, 'fix',
   'The price fell 17.9% on a sector de-rating — and this edition replaces modelled segment data with reported figures.',
   ["<b>The correction:</b> the previous edition's segment splits were modelled. They have been replaced "
    "with the figures reported in the FY2026 10-K, which also moved two numbers the analysis leans on: "
    "China is 30% of FY2026 revenue and services 23%. Like GEV, this report came from the August 12 "
    "cohort, researched with search constrained and IR domains blocked.",
    "The price decline was a semicap de-rating triggered by Applied Materials' August 13 print, not by "
    "anything KLA disclosed."],
   "Corrected: the Section 02 segment revenue splits, the China revenue share and the services share, "
   "all now from the 10-K. <b>Re-verified as unchanged:</b> the process-control moat and the competitive structure."),

 # ---- 16 Sep 2026 batch ----
 'nvda': ('2026-08-24', 208.48, '2026-09-15', 212.17, 'print',
   'NVIDIA reported Q2 FY2027 on August 26 — and the stock round-tripped the beat, closing September 15 just 1.8% above the prior edition.',
   ["<b>Q2 FY2027</b> (quarter ended July 26): revenue $96.2B (+106% YoY, +18% QoQ); Data Center $89.0B (+117%); "
    "Edge Computing $7.2B (+27%); gross margin 75.0% on both bases; GAAP EPS $2.46, non-GAAP $2.22; $26.0B "
    "returned to shareholders with about $99B of repurchase authorization remaining. <b>Q3 guidance</b> is "
    "$108.0B ±2% with gross margin 74.0% ±50bp — the first guided step-down — and assumes zero China data-center "
    "compute revenue. The release now discloses the GAAP-over-non-GAAP gap as gains on equity securities "
    "($7.8B in Q2, $15.9B in Q1), replacing the previous edition's inference.",
    "Shares rose 8.7% to $227.98 on August 27, closed August at $220.78, and drifted to $212.17 by September 15. "
    "Trailing P/E 26.8x, forward 17.6x, PEG 0.34; consensus target $327.65 with post-print raises as high as $515."],
   "Updated at this edition: header, chart (the Aug 26 point is now the true month-end close), sections 01, 02, 04 "
   "including One-Off Items, 05, 06, 07 and 08. <b>Not re-verified:</b> the Vanguard holding line, the customer-"
   "concentration percentages from the January 2026 10-K, hyperscaler capex figures, all \"est.\" comparison columns, "
   "and the China policy narrative. The Q3 FY2027 earnings date was not on any NVIDIA page fetched."),

 'hd': ('2026-08-03', 340.02, '2026-09-15', 305.48, 'print',
   'Home Depot beat and reaffirmed on August 18 — and the stock has fallen about 10% since, back to within 6% of its May low.',
   ["<b>Q2 FY2026</b> (reported August 18): sales $47.9B (+5.7%), comparable sales +1.7% (US +1.3%), comparable "
    "transactions −1.0%, average ticket +2.8%, net earnings $4.8B, diluted EPS $4.79 (adjusted $4.92 vs $4.68); "
    "operating margin 14.3%. FY2026 guidance reaffirmed: sales +2.5–4.5%, comps flat to +2%, adjusted EPS flat to "
    "+4% from $14.69. A $2.33 dividend was declared August 20 — the 158th consecutive quarterly payment. CEO Ted "
    "Decker began a temporary medical leave on August 12; Ann-Marie Campbell and Richard McPhail share interim "
    "oversight and Greg Brenneman chairs the board.",
    "<em>The valuation reset:</em> trailing P/E 24.2x → 21.4x, forward 22.2x → 19.7x, yield 2.74% → 3.05%, "
    "D/E 4.59 → 3.80. Consensus is still Buy (36 analysts, 21 buy / 15 hold / 0 sell) with the average target up to "
    "$377.19 — now 23.5% above the price. The five-year chart is now built from real month-end closes rather than "
    "the previous edition's reconstructed series."],
   "Updated at this edition: header, banner, chart series and warnings, sections 01 through 08, industry commentary "
   "and sourcing. <b>Not re-verified:</b> the July 30 realignment details, the June 23 Wolfe downgrade, the "
   "Oppenheimer attribution of the $310 low target, the July litigation item, institutional ownership, the Section 02 "
   "segment allocation and all \"est.\" comparison figures. The Q3 earnings date (November 17) is MarketBeat's estimate, "
   "not company-confirmed."),

 'unh': ('2026-08-03', 416.83, '2026-09-15', 375.93, 'price',
   'UNH fell 9.8% between editions on no new company news — the multiple compressed, the business did not move.',
   ["Trailing P/E 26.7x → 24.2x, forward 19.5x → 17.5x, PEG 1.53 → 1.21, yield 2.23% → 2.47%, market cap $378.5B → "
    "$337.4B. The 52-week range is now $255.97–$461.62 as the August 2025 lows rolled out of the window. Consensus "
    "target is unchanged at $475.23 (27 analysts, 16 buy / 7 hold / 4 sell), so the implied upside widened from +14% to "
    "+26% purely on price; Zacks (September 14) and Erste (August 27) moved to Hold, while Wells Fargo ($526) and "
    "Bernstein ($512) added targets in September — all as listed on MarketBeat and TipRanks.",
    "<em>Company news since August 3:</em> the Q3 2026 report date is confirmed for October 13 (IR events page, "
    "announced September 15), replacing the previous \"~Oct 14 est.\"; a dividend authorization on August 12; no "
    "guidance change and no DOJ or CMS release on the company's newsroom. The five-year chart is now built from real "
    "month-end closes, which changes the shape of the 2025–26 drawdown materially — Section 07 was rewritten to match."],
   "Updated at this edition: header, banner, chart, sections 01, 04, 05, 06, 07 and 08, industry commentary and "
   "disclaimer; the embedded site nav was removed. <b>Not re-verified:</b> the Q2 segment figures (unchanged since the "
   "July 16 print), the industry and S&P comparison columns, and the five-year index-return comparisons. Note: "
   "StockAnalysis's history table shows the August 3 close as $415.36, not the $416.83 the previous edition printed; "
   "the prior-edition price above is the figure that was published."),
}


EDITIONS = {slug: Edition(*fields) for slug, fields in _RECORDS.items()}


def day(d):
    """'1 Sep 2026' (no leading zero, on every platform: Windows strftime has no %-d)."""
    return f'{d.day} {d:%b %Y}'


def box(e):
    d0, d1 = datetime.date.fromisoformat(e.prior_date), datetime.date.fromisoformat(e.as_of)
    pct = (e.price / e.prior_price - 1) * 100
    body = '\n  '.join(f'<p>{p}</p>' for p in e.paras)
    return f"""<!-- ============ WHAT CHANGED SINCE THE LAST EDITION ============ -->
<section class="tg-d tg-d--{e.state}" data-prior-as-of="{e.prior_date}" data-prior-price="{e.prior_price}" data-as-of="{e.as_of}" data-price="{e.price}">
  <div class="tg-d-top">
    <span class="tg-d-tag">{TAGS[e.state]}</span>
    <span class="tg-d-when">{day(d0)} &rarr; {day(d1)} &middot; {(d1 - d0).days} days</span>
  </div>
  <p class="tg-d-claim">{e.claim}</p>
  <div class="tg-d-move">
    <div class="tg-d-px">${e.prior_price:,.2f}<span>PREVIOUS EDITION</span></div>
    <div class="tg-d-arw">&rarr;</div>
    <div class="tg-d-px">${e.price:,.2f}<span>THIS EDITION</span></div>
    <div class="tg-d-pct {'up' if pct >= 0 else 'dn'}">{pct:+.1f}%</div>
  </div>
  {body}
  <p class="tg-d-check">{e.check}</p>
</section>

"""


def insert_box(path, e):
    """Add the box (and, once, its CSS) to one report. Returns False when it already has one."""
    t = rl.read_text(path)
    if 'class="tg-d ' in t:
        return False
    if not ANCHOR_RE.search(t):
        raise ValueError('section-01 anchor comment not found')
    if '</style>' not in t:
        raise ValueError('no </style> to add the box CSS before')
    i = t.rindex('</style>')                     # CSS once, before the last </style>
    t = t[:i] + CSS + t[i:]
    j = ANCHOR_RE.search(t).start()              # the box immediately above section 01
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(t[:j] + box(e) + t[j:])
    return True


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    root = args[0] if args else rl.ROOT
    for slug, e in EDITIONS.items():
        p = os.path.join(root, 'reports', f'{slug}_analysis.html')
        try:
            inserted = insert_box(p, e)
        except (OSError, ValueError) as err:
            sys.exit(f'{slug}: {err}')
        print(f'  {slug}: box inserted ({e.state})' if inserted else f'  {slug}: already has a box, skipping')


if __name__ == '__main__':
    main()
