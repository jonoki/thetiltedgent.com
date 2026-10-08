"""The unattended earnings refresh run: take the due reports from the refresh queue, have the builder and then an
independent checker refresh each one (headless Claude Code, the project agents ttg-report-builder and
ttg-report-checker), re-run the gates here, commit what passes to the review branch and push it. Nothing reaches
main: Oki merges the branch.   Run: py -3 tools/auto_refresh.py [--dry-run] [--only SLUG ...]

--assets is the monthly numbers-only refresh of the ETF, crypto and bond & cash reports (Oki, 8 Oct 2026): every
report under reports/etf, reports/crypto and reports/fixed whose banner as-of is ASSET_MIN_AGE_DAYS old or more, same
agents, gates, branch and commit-or-revert, brief claude/briefs/REFRESH_ASSETS.md; summary tasks/queue/runs/<date>-assets.md.

Works in its own git worktree (.claude/worktrees/auto-refresh of the main checkout, branch claude/auto-refresh).
Writes a summary to tasks/queue/runs/<date>.md there (git-excluded), each agent's JSON result beside it, and the
checkers' PITFALLS lines to tasks/queue/pitfalls_pending.md for the next retro. One run at a time: a run that starts
while another holds the run lock waits for it (run_lock)."""
import argparse
import concurrent.futures
import contextlib
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from typing import IO, TypedDict

import reportlib as rl
import repodata as rd

BRANCH = 'claude/auto-refresh'
WORKTREE = os.path.join('.claude', 'worktrees', 'auto-refresh')   # under the main checkout; .claude/ is git-ignored
T2_CAP = 0           # T2 refreshes started per run, 0 = no cap; every due T1 always runs (Oki, 8 Oct 2026: no T2 cap)
JOBS = 4             # builder/checker pairs run at once; more when there is a backlog (jobs_for)
MAX_JOBS = 8         # Oki, 8 Oct 2026: "can do more in parallel if required"
MAX_ATTEMPTS = 2     # per report and print; after that it waits in the summary for a person
AGENT_TIMEOUT_S = 90 * 60
MAX_TURNS = '300'
# What an unattended builder or checker may do. Anything else is denied (dontAsk), and the denial is logged.
# No git: the runner alone commits. No deletes.
ALLOWED_TOOLS = ['Read', 'Write', 'Edit', 'Glob', 'Grep', 'WebSearch', 'WebFetch',
                 'Bash(py -3 *)', 'Bash(python *)', 'Bash(node *)', 'Bash(curl *)', 'Bash(cd *)', 'Bash(ls *)',
                 'Bash(cat *)', 'Bash(head *)', 'Bash(tail *)', 'Bash(grep *)', 'Bash(sed -n *)', 'Bash(wc *)',
                 'Bash(mkdir *)', 'Bash(date *)', 'Bash(echo *)', 'Bash(sort *)', 'Bash(diff *)', 'Bash(wc *)',
                 'Bash(find *)']
# A chained command (a && b, a; b, X=… b) is denied when any part is off the list: 11 such denials on 2 Oct 2026.
ONE_COMMAND = ('Run one command per Bash call: no &&, ; or variable assignments (a chained command is refused in '
               'this unattended run); use absolute paths instead of cd.')
TIER_ORDER = {'overdue': 0, 'due': 1}
# The session is started as the agent itself, so it also reads the user's global CLAUDE.md; say which parts apply.
UNATTENDED = ('You are running as an unattended scheduled job, not an interactive session: the plan-and-wait step, '
              'vault writes, lessons.md upkeep and the four-line close in CLAUDE.md do not apply. Do your one task and '
              'return your result in the format your agent file specifies.')
# --assets (Oki, 8 Oct 2026): monthly, first Monday 17:30. 28 days is the shortest gap between two first Mondays, and
# a refresh's as-of is never after its run date, so every report refreshed at one run is due again at the next.
ASSET_MIN_AGE_DAYS = 28
ASSET_BRIEF = 'claude/briefs/REFRESH_ASSETS.md'
FAMILY_NAME = {'etf': 'ETF', 'crypto': 'crypto', 'fixed': 'bond & cash'}   # one per repodata.ASSET_FAMILIES folder
AUDITED_FAMILIES = ('etf', 'crypto')   # chart_audit.py covers these; bond pages chart yields (checked by the agents)
# The daily, weekly and monthly runs share one worktree; a run that finds the lock held waits for it, up to this long.
LOCK_WAIT_S = 12 * 3600
LOCK_POLL_S = 60


class Outcome(TypedDict):
    slug: str
    ticker: str
    tier: str               # T1 / T2, or the family (etf / crypto / fixed) in an asset run
    verdict: str            # committed / reverted / failed; unchanged (asset run: the builder found no newer data)
    detail: str
    cost_usd: float
    usage: list[dict]       # per agent: calls, tokens read (input + cache), cache reads, output — usage_of()
    denials: list[str]
    pitfalls: list[str]
    data_layer: str         # off / used / failed: … (--data-layer)


class DataLayer(TypedDict):
    """What the pre-pass of tools/refresh_data.py left for the agents (--data-layer)."""
    facts: str              # path of facts.json
    stale: str              # path of stale_hits.txt
    summary: str            # the pre-pass's output: what it wrote, what it left to the builder, warnings


# ---- choosing the work ----

def select(items: list[dict], attempts: dict[str, dict[str, int]], t2_cap: int = T2_CAP,
           only: list[str] | None = None, tiers: tuple[str, ...] = ('T1', 'T2')) -> list[dict]:
    """Due and overdue reports of the given tiers: every T1, then T2 oldest first up to the cap; a report that has
    used up its attempts on this print is left for a person. (Schedule, Oki 2 Oct 2026: T1 daily at 06:30, T2
    weekly on Monday at 17:30, before the weekly usage reset.)"""
    due = [i for i in items if i['status'] in TIER_ORDER and i['tier'] in tiers and (not only or i['slug'] in only)
           and attempts.get(i['slug'], {}).get(i['release'], 0) < MAX_ATTEMPTS]
    due.sort(key=lambda i: (i['tier'], TIER_ORDER[i['status']], i['release'], i['ticker']))
    t1 = [i for i in due if i['tier'] == 'T1']
    t2 = [i for i in due if i['tier'] == 'T2']
    return t1 + (t2[:t2_cap] if t2_cap else t2)


def jobs_for(n: int, asked: int | None = None) -> int:
    """Pairs to run at once: what was asked for, else JOBS, rising to MAX_JOBS when more than 2 x JOBS reports are due."""
    if asked:
        return asked
    return max(1, min(n, MAX_JOBS if n > 2 * JOBS else JOBS))


def asset_items(repo: str, today: datetime.date) -> list[dict]:
    """Every ETF, crypto and bond & cash report under repo: slug ('etf/voo', the form chart_audit and the report path
    take), family, ticker, banner as-of and its age in days on today (None when the banner cannot be read), and
    'release', the attempts key: the run's month, so a report out of attempts is tried again the next month."""
    items = []
    for fam in rd.ASSET_FAMILIES:
        for p in sorted(glob.glob(rd.report_path('*', fam, repo=repo))):
            t = rl.read_text(p)
            as_of, _ = rl.as_of(t)
            tick, _name = rl.parse_title(t)
            slug = f'{fam}/{rd.slug_of(p)}'
            items.append({'slug': slug, 'family': fam, 'ticker': tick or rd.slug_of(p).upper(), 'tier': fam,
                          'as_of': as_of, 'run_date': today.isoformat(), 'release': today.strftime('%Y-%m'),
                          'age_days': (today - datetime.date.fromisoformat(as_of)).days if as_of else None})
    return items


def select_assets(items: list[dict], attempts: dict[str, dict[str, int]], min_age: int = ASSET_MIN_AGE_DAYS,
                  only: list[str] | None = None, families: tuple[str, ...] = rd.ASSET_FAMILIES) -> list[dict]:
    """The asset reports due: banner as-of min_age days old or more, in the given families, oldest first; a report
    that has used up its attempts this month waits for a person. only takes 'etf/voo' or 'voo'."""
    due = [i for i in items if i['family'] in families and i['age_days'] is not None and i['age_days'] >= min_age
           and (not only or i['slug'] in only or i['slug'].split('/')[1] in only)
           and attempts.get(i['slug'], {}).get(i['release'], 0) < MAX_ATTEMPTS]
    due.sort(key=lambda i: (i['as_of'], rd.ASSET_FAMILIES.index(i['family']), i['slug']))
    return due


def file_key(slug: str) -> str:
    """A slug as a file or folder name: 'etf/voo' -> 'etf_voo'; a stock slug is unchanged."""
    return slug.replace('/', '_')


def builder_prompt(i: dict, wt: str, data: DataLayer | None = None) -> str:
    surprise = ('' if i['eps'] is None else
                f"Nasdaq calendar: EPS {i['eps']} vs consensus {i['eps_forecast']} (surprise {i['surprise_pct']}%) - "
                'calendar data, re-confirm on the company release. ')
    move = '' if i['first_move_pct'] is None else f"First-session move per the queue: {i['first_move_pct']:+.2f}%. "
    why = (f"The queue tiers it {i['tier']} ({', '.join(i['triggers'])})." if i['triggers'] else
           f"The queue tiers it {i['tier']}; decide T1 vs T2 honestly per REFRESH.md TASK B (guidance, news).")
    return (f"Earnings refresh of ONE report: {i['ticker']}, slug `{i['slug']}`, file reports/{i['slug']}_analysis.html "
            f"(current as-of {i['as_of']}). This is an unattended run: no person will answer questions, so stop "
            f"and report anything that blocks you instead of guessing. {UNATTENDED}\n\n"
            f"WORKING REPO (overrides the REPO line in the briefs): {wt}. Read and edit files only under it; run "
            "tools from it.\n\nSpec: read claude/PITFALL_RULES.md, then claude/briefs/REFRESH.md and "
            "claude/briefs/BUILD.md, and follow them exactly.\n\n"
            f"Print: released {i['release']} ({i['timing']} per Nasdaq; confirm the time yourself), fiscal quarter "
            f"{i['fiscal_quarter']}. {surprise}{move}{why} The T+2 close ({i['t2']}) has settled; use the most "
            "recent settled close with an Adj. Close row as the new as-of.\n\n"
            "Privacy: never put personal data (names, emails) in any request or User-Agent; read sec.gov with "
            f"WebFetch only. No git commands. {ONE_COMMAND} Temp files only in $TEMP/ttgref_{i['slug']}/. Run "
            f"`py -3 tools/chart_audit.py {i['slug']}` and `py -3 tools/verify.py reports/{i['slug']}_analysis.html` "
            "and report both outputs verbatim. Return in the format your agent file specifies, including the "
            "REFRESH.md return lines and the flag list." + (data_layer_brief(data) if data else ''))


def data_layer_brief(data: DataLayer) -> str:
    """The builder's part of the data layer: what is already on the page and what is left to do."""
    return ("\n\nDATA LAYER (tools/refresh_data.py has already run): the structured numbers are already updated from "
            f"{data['facts']} — the header price and change, the banner date, the chart (month-ends and the as-of "
            "close, chart_audit-clean), the 52-week range, and the trailing P/E and dividend yield where the page "
            "allowed. Don't refetch prices or recompute them; use facts.json for every price-derived number in prose "
            "(returns, SPY/QQQ comparisons, RSI and moving averages, distance from the 52-week high and low, short "
            "interest with its settlement date, EPS against Nasdaq consensus); fix every line listed in "
            f"{data['stale']} (old price, old chart values, old range, P/E, yield or as-of date still in the prose), "
            "leaving only those about that date on purpose. The chart is trimmed to the five-year window (61 points; "
            "the events re-indexed, any that fell off listed in facts.json fields.chart.trim): take the window "
            "return, its start month and value from fields.return_chart, and rewrite prose that still starts the "
            "window at the dropped month. Existing chart points that were off Yahoo's month-end were replaced: "
            "facts.json fixed_points lists each (month, old, new, source). Rule A: sweep the prose, timeline, events "
            "labels and cards for every old value (they are in stale_hits.txt) and fix each month-end use; when "
            "fixed_points is not empty, the delta box is `tg-d--fix` and says the chart was corrected (how many "
            "month-end closes, against Yahoo). Update the EPS (TTM) cell from the release: a post-pass "
            "recomputes P/E and the yield from the page's final cells. Fields the pre-pass left to you and its "
            f"warnings:\n<<<\n{data['summary'][:3000]}\n>>>")


def checker_prompt(i: dict, wt: str, builder_result: str, post: str | None = None) -> str:
    return (f"Independent check of ONE refreshed report: reports/{i['slug']}_analysis.html ({i['ticker']}), "
            f"{i['tier']} earnings refresh (previous as-of {i['as_of']}). This is an unattended run: no person will "
            f"answer questions; fix what you can prove, cut what you cannot source, and list the rest. {UNATTENDED}\n\n"
            f"WORKING REPO (overrides the REPO line in the briefs): {wt}. Edit only that report. No git commands. {ONE_COMMAND} "
            f"Temp files only in $TEMP/ttgchk_{i['slug']}/.\n\nSpec: claude/PITFALL_RULES.md first, then "
            "claude/briefs/CHECK.md (which points to REFRESH.md and BUILD.md). Never trust the builder's "
            "\"verified\": re-confirm on pages you fetch yourself. House rules: nothing dated after the banner "
            "date; no user-facing doubt caveats (source it or remove the sentence cleanly); quotes verbatim or "
            "marked as paraphrase.\n\nThe builder's return, including its flag list:\n<<<\n"
            f"{builder_result[:15000]}\n>>>\n\nPrivacy: never put personal data in any request or User-Agent; "
            f"sec.gov via WebFetch only. At the end run `py -3 tools/chart_audit.py {i['slug']}` and "
            f"`py -3 tools/verify.py reports/{i['slug']}_analysis.html`, report both verbatim, give a VERDICT line "
            "(PUBLISH or HOLD with the reason) and a PITFALLS: line, in your agent file's return format."
            + ('' if post is None else
               "\n\nDATA LAYER: the header, banner date, chart, 52-week range and price-derived numbers in "
               "facts.json were machine-fetched and are gated after you (tools/refresh_data.py --post --check): "
               "spot-check two of them, then spend your checking on what the builder wrote (release figures, "
               "quotes, analysts, causes, carried-over facts). Chart points the pre-pass corrected are listed in "
               "facts.json fixed_points (month, old, new, source): confirm no old value survives in the prose, "
               "timeline, events labels or cards (rule A) and that the delta box is `tg-d--fix` and mentions the "
               "chart correction when that list is not empty. The post-pass output (it re-synced P/E and the "
               f"yield to the page's final cells; fix any MISMATCH it lists):\n<<<\n{post[:3000]}\n>>>"))


def asset_checks(i: dict) -> str:
    """The checks an asset builder or checker runs and reports verbatim: chart_audit for ETF and crypto pages, the
    official daily file for bond pages, verify.py, node --check."""
    chart = (f"`py -3 tools/chart_audit.py {i['slug']}`" if i['family'] in AUDITED_FAMILIES else
             'the comparison of every appended or changed chart point with the official daily file')
    return (f"Run {chart}, `py -3 tools/verify.py reports/{i['slug']}_analysis.html` and `node --check` on each "
            "extracted inline script, and report the outputs verbatim.")


def asset_builder_prompt(i: dict, wt: str) -> str:
    """The builder's prompt for the monthly numbers-only refresh of one ETF, crypto or bond & cash report."""
    return (f"Monthly numbers-only refresh of ONE {FAMILY_NAME[i['family']]} report: {i['ticker']}, file "
            f"reports/{i['slug']}_analysis.html (current as-of {i['as_of']}, {i['age_days']} days old). This is an "
            "unattended run: no person will answer questions, so stop and report anything that blocks you instead "
            f"of guessing. {UNATTENDED}\n\n"
            f"WORKING REPO (overrides the REPO line in the briefs): {wt}. Read and edit files only under it; run "
            f"tools from it.\n\nSpec: read claude/PITFALL_RULES.md, then {ASSET_BRIEF}, and follow it exactly (it says "
            "which parts of BUILD_ASSETS.md, BUILD.md and REFRESH.md apply).\n\n"
            f"Run date {i['run_date']}: the new as-of is the last settled close (ETF, crypto) or the latest official "
            f"daily value (bond & cash) on or before it, per {ASSET_BRIEF} Step 2. If there is nothing newer than "
            f"{i['as_of']}, change nothing and return NO CHANGE.\n\n"
            "Privacy: never put personal data (names, emails) in any request or User-Agent; read sec.gov with "
            f"WebFetch only. No git commands. {ONE_COMMAND} Temp files only in $TEMP/ttgref_{file_key(i['slug'])}/. "
            f"{asset_checks(i)} Return in the format {ASSET_BRIEF} gives, including the flag list.")


def asset_checker_prompt(i: dict, wt: str, builder_result: str) -> str:
    """The independent checker's prompt for one refreshed asset report, with the builder's return."""
    return (f"Independent check of ONE refreshed report: reports/{i['slug']}_analysis.html ({i['ticker']}, "
            f"{FAMILY_NAME[i['family']]}), monthly numbers-only refresh (previous as-of {i['as_of']}, run date "
            f"{i['run_date']}). This is an unattended run: no person will answer questions; fix what you can prove, "
            f"cut what you cannot source, and list the rest. {UNATTENDED}\n\n"
            f"WORKING REPO (overrides the REPO line in the briefs): {wt}. Edit only that report. No git commands. "
            f"{ONE_COMMAND} Temp files only in $TEMP/ttgchk_{file_key(i['slug'])}/.\n\nSpec: claude/PITFALL_RULES.md "
            f"first, then the \"Checker\" section of {ASSET_BRIEF} (the report must satisfy the whole brief). Never "
            "trust the builder's \"verified\": re-confirm on pages you fetch yourself. House rules: nothing dated "
            "after the banner date; no user-facing doubt caveats (source it or remove the sentence cleanly).\n\n"
            f"The builder's return, including its flag list:\n<<<\n{builder_result[:15000]}\n>>>\n\nPrivacy: never "
            f"put personal data in any request or User-Agent; sec.gov via WebFetch only. At the end: {asset_checks(i)} "
            "Give a VERDICT line (PUBLISH or HOLD with the reason) and a PITFALLS: line, in your agent file's return "
            "format.")


def data_layer_cmd(slug: str, out: str, post: bool = False, check: bool = False) -> list[str]:
    """tools/refresh_data.py: the pre-pass (as-of auto, written into the page, chart trimmed to the default window and
    wrong existing points fixed) or the post-pass."""
    if post:
        return [sys.executable, 'tools/refresh_data.py', slug, '--post', '--out', out] + (['--check'] if check else [])
    return [sys.executable, 'tools/refresh_data.py', slug, '--as-of', 'auto', '--out', out, '--write', '--fix-points']


def pitfall_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if 'PITFALLS:' in ln]


def built_tier(text: str, queued: str) -> str:
    """The tier the builder decided (it may raise T2 to T1 on guidance or news), else the queue's."""
    m = re.search(r'Tier\W{0,6}(T[12])\b', text)
    return m.group(1) if m else queued


def verdict_hold(text: str) -> bool:
    return bool(re.search(r'VERDICT\W{0,4}HOLD', text, re.I))


# ---- running things ----

def run(cmd: list[str], cwd: str, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                          timeout=timeout, stdin=subprocess.DEVNULL)


def git(wt: str, *args: str) -> str:
    p = run(['git', *args], wt)
    if p.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def claude(agent: str, prompt: str, wt: str, log: str, model: str | None = None) -> dict:
    """One headless agent session; its JSON result (or an error record) is also written to log."""
    exe = shutil.which('claude') or 'claude'
    # --strict-mcp-config with no --mcp-config: no MCP servers (Gmail, Drive, Playwright …); the agents use none of
    # them and their tool listings cost ~2.4k tokens on every call (measured 30 Sep 2026). Not --bare: it drops the login.
    cmd = [exe, '-p', '--agent', agent, '--permission-mode', 'dontAsk', '--permission-prompts', 'none',
           '--strict-mcp-config', '--max-turns', MAX_TURNS, '--output-format', 'json',
           *(['--model', model] if model else []),   # else the agent file's model (Opus)
           '--allowedTools', *ALLOWED_TOOLS, '--', prompt]
    try:
        p = run(cmd, wt, AGENT_TIMEOUT_S)
        out = p.stdout
        res = json.loads(out[out.index('{'):]) if '{' in out else {'is_error': True, 'result': out + p.stderr}
    except (subprocess.TimeoutExpired, ValueError) as e:
        res = {'is_error': True, 'result': f'{type(e).__name__}: {e}'}
    with open(log, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, indent=1)
    return res


def gates(wt: str, slug: str, facts_out: str | None = None, family: str | None = None) -> tuple[bool, str]:
    """Our own re-run of the publish gates; the agents' reports of them are not trusted. With the data layer, the
    page must also still match facts.json (refresh_data.py --post --check). An asset report (family set, slug
    'etf/voo') also needs every inline script to pass node --check and exactly one delta box; chart_audit runs for
    ETF and crypto pages only (bond pages chart yields, which it does not cover)."""
    path = os.path.join(wt, 'reports', f'{slug}_analysis.html')
    v = run([sys.executable, 'tools/verify.py', f'reports/{slug}_analysis.html'], wt, 600)
    ok = v.returncode == 0 and v.stdout.startswith('PASS')
    if family is None or family in AUDITED_FAMILIES:
        a = run([sys.executable, 'tools/chart_audit.py', slug], wt, 600)
        audit = (a.stdout.splitlines() or [''])[0]
        wrong = re.search(r'WRONG points[^:]*: (\d+)', audit)
        ok = ok and wrong is not None and wrong.group(1) == '0' and ' errors 0 ' in audit
    else:
        audit = 'chart_audit n/a (bond yields)'
    with open(path, 'rb') as fh:
        raw = fh.read()
    crlf = raw.count(b'\r\n')
    extra = ''
    if family is not None:
        node = node_check(raw.decode('utf-8', errors='replace'))
        boxes = len(re.findall(r'<section class="tg-d[ "]', raw.decode('utf-8', errors='replace')))
        ok = ok and node is None and boxes == 1
        extra = f" | node --check {node or 'ok'} | delta boxes {boxes}"
    facts = ''
    if facts_out:
        f = run(data_layer_cmd(slug, facts_out, post=True, check=True), wt, 600)
        ok = ok and f.returncode == 0
        facts = ' | facts ' + ('ok' if f.returncode == 0 else 'MISMATCH: ' + ' / '.join(
            ln.strip() for ln in f.stdout.splitlines() if 'MISMATCH' in ln)[:500])
    return ok and not crlf, f"{v.stdout.strip()} | {audit}{extra}{facts}" + (f' | {crlf} CRLF' if crlf else '')


def node_check(page: str) -> str | None:
    """None when every inline script of the page parses under `node --check`, else what failed (including node
    missing). Scripts with a src, and JSON-LD, are skipped."""
    bodies = re.findall(r'<script(?![^>]*\bsrc=)(?![^>]*application/ld\+json)[^>]*>(.*?)</script>', page, re.S | re.I)
    with tempfile.TemporaryDirectory() as tmp:
        for n, body in enumerate(bodies):
            js = os.path.join(tmp, f'script{n}.js')
            rl.write_text(js, body)
            try:
                p = run(['node', '--check', js], tmp, 120)
            except OSError as e:
                return f'FAIL: node not runnable ({e})'
            if p.returncode:   # node ends its report with its version line; the error is the line naming it
                err = [ln for ln in p.stderr.splitlines() if 'Error' in ln] or p.stderr.strip().splitlines() or ['?']
                return f'FAIL: script {n}: {err[0].strip()[:200]}'
    return None


def refresh_one(i: dict, wt: str, logs: str, lock: threading.Lock, data_layer: bool = False,
                models: dict[str, str | None] | None = None) -> Outcome:
    """Builder, then checker, then our gates, then commit or revert, for one report: an earnings refresh, or the
    monthly numbers refresh of an asset report when the item has a family (asset_items)."""
    models = models or {}
    slug = i['slug']
    family: str | None = i.get('family')
    key = file_key(slug)
    path = f'reports/{slug}_analysis.html'
    out: Outcome = {'slug': slug, 'ticker': i['ticker'], 'tier': i['tier'], 'verdict': 'failed', 'detail': '',
                    'cost_usd': 0.0, 'denials': [], 'pitfalls': [], 'usage': [], 'data_layer': 'off'}
    data: DataLayer | None = None
    facts_out = os.path.join(logs, key)
    if data_layer and not family:   # a failed pre-pass leaves the page untouched; the builder then does the numbers
        pre = run(data_layer_cmd(slug, facts_out), wt, 900)
        if pre.returncode == 0:
            data = {'facts': os.path.join(facts_out, 'facts.json'), 'stale': os.path.join(facts_out, 'stale_hits.txt'),
                    'summary': pre.stdout.strip()}
            out['data_layer'] = 'used'
        else:
            out['data_layer'] = 'failed: ' + (pre.stdout + pre.stderr).strip()[-300:]
    b = claude('ttg-report-builder', asset_builder_prompt(i, wt) if family else builder_prompt(i, wt, data), wt,
               os.path.join(logs, f'{key}.builder.json'), models.get('builder'))
    c: dict = {}
    if family and not b.get('is_error'):
        with lock:
            untouched = not git(wt, 'status', '--porcelain', '--', path).strip()
        if untouched:   # NO CHANGE: no newer data, so no checker either
            out['cost_usd'] = float(b.get('total_cost_usd') or 0)
            out['usage'].append(usage_of('builder', b))
            out['verdict'], out['detail'] = 'unchanged', 'builder changed nothing (no newer data?)'
            return out
    if not b.get('is_error'):
        post = None
        if data:
            p = run(data_layer_cmd(slug, facts_out, post=True), wt, 600)
            post = (p.stdout + p.stderr).strip()
        prompt = (asset_checker_prompt(i, wt, str(b.get('result', ''))) if family else
                  checker_prompt(i, wt, str(b.get('result', '')), post))
        c = claude('ttg-report-checker', prompt, wt, os.path.join(logs, f'{key}.checker.json'), models.get('checker'))
    for who, r in (('builder', b), ('checker', c)):
        out['cost_usd'] += float(r.get('total_cost_usd') or 0)
        if r:
            out['usage'].append(usage_of(who, r))
        out['denials'] += [json.dumps(d)[:200] for d in r.get('permission_denials') or []]
    out['pitfalls'] = pitfall_lines(str(c.get('result', '')))
    with lock:   # one git operation at a time; the agents only ever touch their own report
        changed = bool(git(wt, 'status', '--porcelain', '--', path).strip())
        if b.get('is_error') or c.get('is_error') or not c:
            out['detail'] = 'builder error' if b.get('is_error') else 'checker error'
        elif verdict_hold(str(c.get('result', ''))):
            out['detail'] = 'checker verdict HOLD'
        elif not changed:
            out['detail'] = 'no change to the report'
        else:
            ok, why = gates(wt, slug, facts_out if data else None, family)
            if ok:
                git(wt, 'add', '--', path)
                if family:
                    new_as_of = rl.as_of(rl.read_text(os.path.join(wt, path)))[0]
                    msg = (f"{i['ticker']} monthly numbers refresh ({FAMILY_NAME[family]}, as-of {i['as_of']} -> "
                           f"{new_as_of}), unattended: builder + independent checker, verify PASS, node --check ok"
                           + (', chart_audit 0 wrong' if family in AUDITED_FAMILIES else ''))
                else:
                    out['tier'] = built_tier(str(b.get('result', '')), i['tier'])
                    msg = (f"{i['ticker']} earnings refresh ({out['tier']}, print {i['release']}), "
                           "unattended: builder + independent checker, verify PASS, chart_audit 0 wrong")
                git(wt, 'commit', '-q', '-m', msg, '-m', 'Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>')
                out['verdict'], out['detail'] = 'committed', why
                return out
            out['detail'] = f'gates failed: {why}'
        if changed:   # leave nothing half-done in the tree: the summary and the logs keep the work
            shutil.copy(os.path.join(wt, path), os.path.join(logs, f'{key}_analysis.rejected.html'))
            git(wt, 'checkout', '--', path)
            out['verdict'] = 'reverted'
    return out


# ---- the worktree ----

def main_checkout() -> str:
    common = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], cwd=rd.ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    return os.path.dirname(common)


GENERATED = ('data/',)   # files the tools write; a conflict in them is healed by regenerating


def merge_base(wt: str, base: str) -> None:
    """Merge base into the review branch. A conflict only in generated data (both sides rebuilt data/card_tags.json,
    say) is healed: take base's copy and regenerate from the merged reports. Any other conflict aborts the merge so
    the worktree is never left half-merged (7-8 Oct 2026: a half-merge stopped two morning runs), then raises."""
    if run(['git', 'merge', '-q', '--no-edit', base], wt).returncode == 0:
        return
    conflicted = git(wt, 'diff', '--name-only', '--diff-filter=U').split()
    if not conflicted or not all(f.startswith(GENERATED) for f in conflicted):
        run(['git', 'merge', '--abort'], wt)
        raise RuntimeError(f'merging {base} conflicts outside generated data: {conflicted}; merge aborted, branch unchanged')
    git(wt, 'checkout', '--theirs', '--', *conflicted)
    for tool in ('manifest.py', 'style_tags.py', 'card_tags.py'):
        r = run([sys.executable, f'tools/{tool}'], wt)
        if r.returncode:
            run(['git', 'merge', '--abort'], wt)
            raise RuntimeError(f'regenerating after a data conflict: {tool} exit {r.returncode}; merge aborted')
    git(wt, 'add', '--', 'data')
    git(wt, 'commit', '-q', '-m', f'Merge {base}: generated data conflict ({", ".join(conflicted)}) healed by regenerating',
        '-m', 'Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>')


@contextlib.contextmanager
def run_lock(main: str, wait_s: int = LOCK_WAIT_S, poll_s: int = LOCK_POLL_S) -> Iterator[None]:
    """One run at a time on the review worktree (the daily T1, weekly T2 and monthly asset runs share it, and the
    first Monday has both a T2 and an asset run at 17:30): an OS lock on tasks/queue/run.lock in the main checkout.
    A run that finds it held waits, polling every poll_s, up to wait_s, then raises. The OS drops the lock when the
    process ends, so a crashed run never leaves it held."""
    path = os.path.join(main, 'tasks', 'queue', 'run.lock')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = open(path, 'a+')
    deadline = time.monotonic() + wait_s
    try:
        while not _try_lock(fh):
            if time.monotonic() >= deadline:
                raise RuntimeError(f'another auto_refresh run still holds {path} after {wait_s // 60} min of waiting')
            time.sleep(poll_s)
        try:
            yield
        finally:
            _unlock(fh)
    finally:
        fh.close()


if sys.platform == 'win32':
    import msvcrt

    def _try_lock(fh: IO[str]) -> bool:
        """Lock the first byte of fh without waiting; False when another handle holds it."""
        fh.seek(0)
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _unlock(fh: IO[str]) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _try_lock(fh: IO[str]) -> bool:
        """Lock fh without waiting; False when another open file holds it."""
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _unlock(fh: IO[str]) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def alert(main: str, text: str) -> None:
    """Make a failed run impossible to miss: tasks/queue/ALERT.txt (refresh_queue.py puts it at the top of today.md)
    and a Windows message to the logged-on user."""
    path = os.path.join(main, 'tasks', 'queue', 'ALERT.txt')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8', newline='\n') as fh:
        fh.write(f"{datetime.datetime.now().isoformat(timespec='minutes')} auto_refresh failed: {text}\n")
    if os.name == 'nt':
        subprocess.run(['msg', os.environ.get('USERNAME', '*'), '/TIME:0', f'TTG auto refresh failed: {text[:200]}'],
                       capture_output=True)


def prepare(main: str, base: str) -> str:
    """The review worktree, up to date with base, clean, with the private agent files copied in."""
    wt = os.path.join(main, WORKTREE)
    git(main, 'fetch', '-q', 'origin')
    if not os.path.isdir(wt):
        have = run(['git', 'rev-parse', '--verify', '-q', BRANCH], main).returncode == 0
        git(main, 'worktree', 'add', '-q', *([wt, BRANCH] if have else ['--no-track', '-b', BRANCH, wt, base]))
    if git(wt, 'status', '--porcelain', '--untracked-files=no').strip():
        raise RuntimeError(f'{wt} has uncommitted changes (a crashed run?); look before running again')
    if run(['git', 'merge-base', '--is-ancestor', base, 'HEAD'], wt).returncode:
        merge_base(wt, base)
    shutil.copytree(os.path.join(main, '.claude', 'agents'), os.path.join(wt, '.claude', 'agents'),
                    dirs_exist_ok=True)
    return wt


def usage_of(who: str, r: dict) -> dict:
    """What one headless session used, from its JSON result: model calls and tokens. Cost scales with calls ×
    context, so 'read' (input + cache writes + cache reads) is the number to watch; output includes thinking."""
    u = r.get('usage') or {}
    read = sum(int(u.get(k) or 0) for k in ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
    main = [m for m in (r.get('modelUsage') or {}) if 'haiku' not in m]   # Haiku is web fetch's page reader
    return {'agent': who, 'model': (main[0] if main else '?').replace('claude-', ''), 'calls': int(r.get('num_turns') or 0), 'read': read,
            'cache_read': int(u.get('cache_read_input_tokens') or 0), 'output': int(u.get('output_tokens') or 0)}


def mtok(n: float) -> str:
    return f'{n / 1e6:.1f}M'


def summary_md(day: str, outcomes: list[Outcome], waiting: list[dict], notes: list[str], assets: bool = False) -> str:
    """The run's summary (tasks/queue/runs/<run_id>.md): one line per report with its cost and usage, the reports due
    but not run, and the notes (family counts, rebuilt data, checks, push)."""
    head = f'# Asset refresh (monthly, numbers only) — {day}' if assets else f'# Auto refresh — {day}'
    lines = [head, '', f'Branch `{BRANCH}`; nothing is on main until Oki merges it.', '']
    for o in outcomes:
        lines.append(f"- **{o['ticker']}** {o['tier']} — {o['verdict']}: {o['detail']} · ~${o['cost_usd']:.2f} "
                     "(client-side estimate)" + (f" · {len(o['denials'])} tool denials" if o['denials'] else '')
                     + (f" · data layer {o['data_layer']}" if o.get('data_layer', 'off') != 'off' else ''))
        for u in o['usage']:
            lines.append(f"  - {u['agent']} ({u.get('model', '?')}): {u['calls']} calls ·{mtok(u['read'])} tokens read "
                         f"({mtok(u['cache_read'])} from cache) · {u['output']:,} out")
    if outcomes:   # the number to compare run to run (baseline 2 Oct 2026: 209 calls, 16.6M read per refresh)
        calls = sum(u['calls'] for o in outcomes for u in o['usage'])
        read = sum(u['read'] for o in outcomes for u in o['usage'])
        lines += ['', f"Per refresh: {calls / len(outcomes):.0f} calls · {mtok(read / len(outcomes))} tokens read"
                      + ('' if assets else ' (baseline 2 Oct 2026: 209 calls · 16.6M)')]
    if waiting and assets:
        lines += ['', f'Due but not run (out of attempts this month, or the banner as-of could not be read): {len(waiting)}',
                  *[f"- {i['ticker']} ({i['slug']}) as-of {i['as_of']}" for i in waiting]]
    elif waiting:
        lines += ['', f'Due but not run (on the other schedule, over the T2 cap, or out of attempts): {len(waiting)}',
                  *[f"- {i['ticker']} {i['tier']} released {i['release']} ({i['status']})" for i in waiting]]
    return '\n'.join(lines + [''] + notes) + '\n'


def run_id(day: str, tiers: tuple[str, ...] = ('T1', 'T2'), assets: bool = False) -> str:
    """The name of a run's summary (runs/<id>.md) and log folder: the date, then -assets for the monthly asset run, or
    the tiers when a run takes only some of them (Mondays run T1 and T2 separately)."""
    if assets:
        return f'{day}-assets'
    return day if set(tiers) >= {'T1', 'T2'} else day + '-' + '-'.join(tiers)


def load_attempts(qdir: str) -> dict[str, dict[str, int]]:
    """tasks/queue/attempts.json: slug -> {print date (stocks) or run month (assets): attempts so far}."""
    path = os.path.join(qdir, 'attempts.json')
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def run_all(work: list[dict], wt: str, qdir: str, rid: str, attempts: dict[str, dict[str, int]],
            args: argparse.Namespace) -> list[Outcome]:
    """Count an attempt for each report, then run the builder/checker pairs in parallel (jobs_for)."""
    logs = os.path.join(qdir, 'runs', rid)
    os.makedirs(logs, exist_ok=True)
    for i in work:
        attempts.setdefault(i['slug'], {})[i['release']] = attempts.get(i['slug'], {}).get(i['release'], 0) + 1
    rd.write_json(os.path.join(qdir, 'attempts.json'), attempts, indent=1)
    lock = threading.Lock()
    models = {'builder': args.builder_model, 'checker': args.checker_model}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs_for(len(work), args.jobs)) as ex:
        return list(ex.map(lambda i: refresh_one(i, wt, logs, lock, args.data_layer, models), work))


def finish(wt: str, qdir: str, day: str, rid: str, outcomes: list[Outcome], waiting: list[dict], notes: list[str],
           assets: bool = False) -> str:
    """After the reports: rebuild the generated files (the asset cards too in an asset run) and commit them, run the
    checks, push the review branch; collect the checkers' PITFALLS lines; write the summary and return it."""
    if any(o['verdict'] == 'committed' for o in outcomes):
        tools = (('asset_cards.py',) if assets else ()) + ('manifest.py', 'style_tags.py', 'card_tags.py')
        for tool in tools:
            r = run([sys.executable, f'tools/{tool}'], wt)
            notes.append(f"- {tool}: exit {r.returncode}")
        paths = ['data'] + (['reports/index.html'] if assets else [])
        git(wt, 'add', '--', *paths)
        if git(wt, 'status', '--porcelain', '--', *paths).strip():
            what = 'Asset cards, manifest, style and card tags' if assets else 'Manifest, style and card tags'
            git(wt, 'commit', '-q', '-m', f'{what} rebuilt after the unattended refreshes',
                '-m', 'Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>')
        checks = run([sys.executable, 'tools/run_checks.py'], wt, 1800)
        notes.append('- run_checks: ' + ' / '.join(ln for ln in checks.stdout.splitlines() if ln[:4] in ('ok  ', 'FAIL', 'SKIP')))
        push = run(['git', 'push', '-q', 'origin', BRANCH], wt)
        notes.append(f"- push {BRANCH}: {'ok' if push.returncode == 0 else push.stderr.strip()}")
    pend = [f"- {day} {o['ticker']}: {ln}" for o in outcomes for ln in o['pitfalls']]
    if pend:
        with open(os.path.join(qdir, 'pitfalls_pending.md'), 'a', encoding='utf-8', newline='\n') as fh:
            fh.write('\n'.join(pend) + '\n')
    text = summary_md(day, outcomes, waiting, notes, assets)
    os.makedirs(os.path.join(qdir, 'runs'), exist_ok=True)
    with open(os.path.join(qdir, 'runs', f'{rid}.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return text


def main(argv: list[str] | None = None) -> int:
    ap = rd.parser('Unattended earnings refreshes onto the review branch.')
    ap.add_argument('--base', default='origin/main', help='what the review branch builds on (default origin/main)')
    ap.add_argument('--t2-cap', type=int, default=T2_CAP)
    ap.add_argument('--jobs', type=int, default=None, help=f'pairs at once (default {JOBS}, up to {MAX_JOBS} with a backlog)')
    ap.add_argument('--only', nargs='*', help='limit the run to these slugs (asset run: etf/voo or voo)')
    ap.add_argument('--tiers', default='T1,T2', help='tiers to refresh, e.g. T1 (the daily run) or T2 (the weekly run)')
    ap.add_argument('--builder-model', help="model for the builders, e.g. sonnet (default: the agent file's, Opus)")
    ap.add_argument('--checker-model', help="model for the checkers (default: the agent file's, Opus)")
    ap.add_argument('--dry-run', action='store_true', help='show what would run; no agents, commits or push')
    ap.add_argument('--data-layer', action='store_true', help='run tools/refresh_data.py before the builder (structured '
                    'numbers written from facts.json) and after it (--post), and gate on --post --check (opt-in)')
    ap.add_argument('--assets', action='store_true', help='the monthly numbers-only refresh of the ETF, crypto and bond '
                    f'& cash reports whose as-of is --min-age days old or more ({ASSET_BRIEF})')
    ap.add_argument('--families', default=','.join(rd.ASSET_FAMILIES), help='with --assets: the families to take')
    ap.add_argument('--min-age', type=int, default=ASSET_MIN_AGE_DAYS, help='with --assets: days since the as-of')
    ap.add_argument('--today', help='with --assets: the run date YYYY-MM-DD for the selection and the prompts '
                    '(default today); with --dry-run, to see what a later run would take')
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[union-attr]
    if args.assets:
        today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
        if args.dry_run:   # reads this checkout; prepares no worktree, takes no lock
            return assets_dry_run(args, today)
        with run_lock(main_checkout()):
            return run_assets(args, today)
    if args.dry_run:
        return run_stocks(args)
    with run_lock(main_checkout()):
        return run_stocks(args)


def run_stocks(args: argparse.Namespace) -> int:
    """The earnings refresh run: the due reports from the refresh queue."""
    day = datetime.date.today().isoformat()
    wt = prepare(main_checkout(), args.base)
    q = run([sys.executable, 'tools/refresh_queue.py', '--repo', wt], wt, 1800)
    print(q.stdout.strip())
    qdir = os.path.join(wt, 'tasks', 'queue')
    with open(os.path.join(qdir, 'queue.json'), encoding='utf-8') as fh:
        items = json.load(fh)['items']
    attempts = load_attempts(qdir)
    tiers = tuple(t.strip().upper() for t in args.tiers.split(',') if t.strip())
    work = select(items, attempts, args.t2_cap, args.only, tiers)
    waiting = [i for i in items if i['status'] in TIER_ORDER and i not in work and (not args.only or i['slug'] in args.only)]
    print(f'run {day}: ' + (', '.join(f"{i['ticker']} {i['tier']}" for i in work) or 'nothing due'))
    if args.dry_run:
        for i in work[:1]:
            demo: DataLayer = {'facts': '<run>/<slug>/facts.json', 'stale': '<run>/<slug>/stale_hits.txt',
                               'summary': '<the pre-pass output>'}
            print('\n--- builder prompt ---\n' + builder_prompt(i, wt, demo if args.data_layer else None))
        return 0
    rid = run_id(day, tiers)
    outcomes = run_all(work, wt, qdir, rid, attempts, args)
    print(finish(wt, qdir, day, rid, outcomes, waiting, []))
    return 0 if all(o['verdict'] == 'committed' for o in outcomes) else 1


def asset_selection(items: list[dict], attempts: dict[str, dict[str, int]], args: argparse.Namespace
                    ) -> tuple[list[dict], list[dict], list[str]]:
    """(the work, the reports due but not run, one count line per family) for an asset run."""
    families = tuple(f.strip() for f in args.families.split(',') if f.strip())
    unknown = set(families) - set(rd.ASSET_FAMILIES)
    if unknown:
        raise ValueError(f'unknown families {sorted(unknown)}; use {",".join(rd.ASSET_FAMILIES)}')
    work = select_assets(items, attempts, args.min_age, args.only, families)
    due_any = select_assets(items, {}, args.min_age, args.only, families)
    unread = [i for i in items if i['as_of'] is None and i['family'] in families]
    waiting = [i for i in due_any if i not in work] + unread
    counts = [f"- {f}: {sum(i['family'] == f for i in items)} reports · {sum(i['family'] == f for i in work)} to refresh"
              for f in families]
    return work, waiting, counts


def assets_dry_run(args: argparse.Namespace, today: datetime.date) -> int:
    """What an asset run on `today` would take, read from this checkout (--repo), and the first builder prompt (the
    oldest report's, marked as an example, when nothing is due)."""
    wt = os.path.join(main_checkout(), WORKTREE)
    items = asset_items(args.repo, today)
    work, waiting, counts = asset_selection(items, load_attempts(os.path.join(wt, 'tasks', 'queue')), args)
    print(f'asset run {today.isoformat()} (dry run, pages read from {args.repo}): {len(work)} of {len(items)} due '
          f'(as-of {args.min_age}+ days old)', *counts, sep='\n')
    for i in work:
        print(f"  {i['slug']:16} {i['ticker']:8} as-of {i['as_of']} ({i['age_days']} days)")
    for i in waiting:
        print(f"  waiting: {i['slug']} as-of {i['as_of']}")
    later = sorted(select_assets(items, {}, 0, args.only, tuple(f.strip() for f in args.families.split(','))),
                   key=lambda i: i['as_of'])
    later = [i for i in later if i['age_days'] < args.min_age]   # not due yet, soonest first
    if later:
        nxt = datetime.date.fromisoformat(later[0]['as_of']) + datetime.timedelta(days=args.min_age)
        print(f"next report to fall due: {later[0]['slug']} on {nxt.isoformat()}")
    for i in (work[:1] or later[:1]):
        print(f"\n--- builder prompt{'' if work else ' (example: not due on this date)'} ---\n" + asset_builder_prompt(i, wt))
    return 0


def run_assets(args: argparse.Namespace, today: datetime.date) -> int:
    """The monthly asset run: every due ETF, crypto and bond & cash report, then the asset cards and the generated
    data, the checks and the push; an ALERT when any report was not committed (the page then waits a month)."""
    day = today.isoformat()
    main = main_checkout()
    wt = prepare(main, args.base)
    qdir = os.path.join(wt, 'tasks', 'queue')
    attempts = load_attempts(qdir)
    items = asset_items(wt, today)
    work, waiting, counts = asset_selection(items, attempts, args)
    print(f'asset run {day}: ' + (', '.join(i['slug'] for i in work) or 'nothing due'))
    rid = run_id(day, assets=True)
    outcomes = run_all(work, wt, qdir, rid, attempts, args) if work else []
    print(finish(wt, qdir, day, rid, outcomes, waiting, counts, assets=True))
    bad = [o for o in outcomes if o['verdict'] not in ('committed', 'unchanged')]
    if bad or waiting:
        alert(main, f'asset refresh {day}: {len(bad)} of {len(outcomes)} not committed, {len(waiting)} due but not run; '
                    f'see tasks/queue/runs/{rid}.md in the auto-refresh worktree')
    return 0 if not bad else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:   # noqa: BLE001 - any failure of an unattended run must reach a person
        alert(main_checkout(), f'{type(e).__name__}: {e}')
        raise
