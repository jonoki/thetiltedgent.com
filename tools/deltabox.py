#!/usr/bin/env python3
"""Insert the "what changed since the last edition" box into refreshed reports.

Only reports with a genuine prior edition get a box. Every figure below is
taken from the report's own prose or from claude/REFRESH_POLICY.md — nothing is
newly researched here, it is existing analysis given a consistent structure.

Three states, because the refresh run found three genuinely different outcomes:
  price  — the multiple moved, the business did not (5 of the 7)
  print  — the company reported; numbers are new
  fix    — this edition corrects something the previous one got wrong
"""
import re, sys, datetime, os

ANCHOR_RE = re.compile(r'<!-- =+ 01 COMPANY OVERVIEW')   # the '=' run length varies by era

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

# prior_date, prior_price, as_of, price, state, claim, body paragraphs, verified line
R = {
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
}


def box(slug, rec):
    pd, pp, ad, cp, state, claim, paras, check = rec
    d0 = datetime.date(*map(int, pd.split('-')))
    d1 = datetime.date(*map(int, ad.split('-')))
    days = (d1 - d0).days
    pct = (cp / pp - 1) * 100
    cls = 'up' if pct >= 0 else 'dn'
    fmt = lambda d: d.strftime('%-d %b %Y')
    body = '\n  '.join(f'<p>{p}</p>' for p in paras)
    return f"""<!-- ============ WHAT CHANGED SINCE THE LAST EDITION ============ -->
<section class="tg-d tg-d--{state}" data-prior-as-of="{pd}" data-prior-price="{pp}" data-as-of="{ad}" data-price="{cp}">
  <div class="tg-d-top">
    <span class="tg-d-tag">{TAGS[state]}</span>
    <span class="tg-d-when">{fmt(d0)} &rarr; {fmt(d1)} &middot; {days} days</span>
  </div>
  <p class="tg-d-claim">{claim}</p>
  <div class="tg-d-move">
    <div class="tg-d-px">${pp:,.2f}<span>PREVIOUS EDITION</span></div>
    <div class="tg-d-arw">&rarr;</div>
    <div class="tg-d-px">${cp:,.2f}<span>THIS EDITION</span></div>
    <div class="tg-d-pct {cls}">{pct:+.1f}%</div>
  </div>
  {body}
  <p class="tg-d-check">{check}</p>
</section>

"""


def main():
    root = sys.argv[1]
    for slug, rec in R.items():
        p = os.path.join(root, 'reports', f'{slug}_analysis.html')
        t = open(p, encoding='utf-8').read()
        if 'class="tg-d ' in t:
            print(f'  {slug}: already has a box, skipping')
            continue
        am = ANCHOR_RE.search(t)
        assert am, f'{slug}: section-01 anchor not found'
        assert '</style>' in t, f'{slug}: no style block'
        # CSS once, before the last </style>
        i = t.rindex('</style>')
        t = t[:i] + CSS + t[i:]
        # box immediately above section 01
        j = ANCHOR_RE.search(t).start()
        t = t[:j] + box(slug, rec) + t[j:]
        open(p, 'w', encoding='utf-8').write(t)
        print(f'  {slug}: box inserted ({rec[4]})')


if __name__ == '__main__':
    main()
