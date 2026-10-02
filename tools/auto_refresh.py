"""The unattended earnings refresh run: take the due reports from the refresh queue, have the builder and then an
independent checker refresh each one (headless Claude Code, the project agents ttg-report-builder and
ttg-report-checker), re-run the gates here, commit what passes to the review branch and push it. Nothing reaches
main: Oki merges the branch.   Run: py -3 tools/auto_refresh.py [--dry-run] [--only SLUG ...]

Works in its own git worktree (.claude/worktrees/auto-refresh of the main checkout, branch claude/auto-refresh).
Writes a summary to tasks/queue/runs/<date>.md there (git-excluded), each agent's JSON result beside it, and the
checkers' PITFALLS lines to tasks/queue/pitfalls_pending.md for the next retro."""
import concurrent.futures
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from typing import TypedDict

import repodata as rd

BRANCH = 'claude/auto-refresh'
WORKTREE = os.path.join('.claude', 'worktrees', 'auto-refresh')   # under the main checkout; .claude/ is git-ignored
T2_CAP = 8           # T2 refreshes started per run; every due T1 always runs (Oki, 30 Sep 2026: "T1 + capped T2")
JOBS = 4             # builder/checker pairs run at once
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


class Outcome(TypedDict):
    slug: str
    ticker: str
    tier: str
    verdict: str            # committed / reverted / failed
    detail: str
    cost_usd: float
    denials: list[str]
    pitfalls: list[str]


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
    return t1 + [i for i in due if i['tier'] == 'T2'][:t2_cap]


def builder_prompt(i: dict, wt: str) -> str:
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
            "tools from it.\n\nSpec: read claude/REPORT_PITFALLS.md, then claude/briefs/REFRESH.md and "
            "claude/briefs/BUILD.md, and follow them exactly.\n\n"
            f"Print: released {i['release']} ({i['timing']} per Nasdaq; confirm the time yourself), fiscal quarter "
            f"{i['fiscal_quarter']}. {surprise}{move}{why} The T+2 close ({i['t2']}) has settled; use the most "
            "recent settled close with an Adj. Close row as the new as-of.\n\n"
            "Privacy: never put personal data (names, emails) in any request or User-Agent; read sec.gov with "
            f"WebFetch only. No git commands. {ONE_COMMAND} Temp files only in $TEMP/ttgref_{i['slug']}/. Run "
            f"`py -3 tools/chart_audit.py {i['slug']}` and `py -3 tools/verify.py reports/{i['slug']}_analysis.html` "
            "and report both outputs verbatim. Return in the format your agent file specifies, including the "
            "REFRESH.md return lines and the flag list.")


def checker_prompt(i: dict, wt: str, builder_result: str) -> str:
    return (f"Independent check of ONE refreshed report: reports/{i['slug']}_analysis.html ({i['ticker']}), "
            f"{i['tier']} earnings refresh (previous as-of {i['as_of']}). This is an unattended run: no person will "
            f"answer questions; fix what you can prove, cut what you cannot source, and list the rest. {UNATTENDED}\n\n"
            f"WORKING REPO (overrides the REPO line in the briefs): {wt}. Edit only that report. No git commands. {ONE_COMMAND} "
            f"Temp files only in $TEMP/ttgchk_{i['slug']}/.\n\nSpec: claude/REPORT_PITFALLS.md first, then "
            "claude/briefs/CHECK.md (which points to REFRESH.md and BUILD.md). Never trust the builder's "
            "\"verified\": re-confirm on pages you fetch yourself. House rules: nothing dated after the banner "
            "date; no user-facing doubt caveats (source it or remove the sentence cleanly); quotes verbatim or "
            "marked as paraphrase.\n\nThe builder's return, including its flag list:\n<<<\n"
            f"{builder_result[:15000]}\n>>>\n\nPrivacy: never put personal data in any request or User-Agent; "
            f"sec.gov via WebFetch only. At the end run `py -3 tools/chart_audit.py {i['slug']}` and "
            f"`py -3 tools/verify.py reports/{i['slug']}_analysis.html`, report both verbatim, give a VERDICT line "
            "(PUBLISH or HOLD with the reason) and a PITFALLS: line, in your agent file's return format.")


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


def claude(agent: str, prompt: str, wt: str, log: str) -> dict:
    """One headless agent session; its JSON result (or an error record) is also written to log."""
    exe = shutil.which('claude') or 'claude'
    cmd = [exe, '-p', '--agent', agent, '--permission-mode', 'dontAsk', '--permission-prompts', 'none',
           '--max-turns', MAX_TURNS, '--output-format', 'json', '--allowedTools', *ALLOWED_TOOLS, '--', prompt]
    try:
        p = run(cmd, wt, AGENT_TIMEOUT_S)
        out = p.stdout
        res = json.loads(out[out.index('{'):]) if '{' in out else {'is_error': True, 'result': out + p.stderr}
    except (subprocess.TimeoutExpired, ValueError) as e:
        res = {'is_error': True, 'result': f'{type(e).__name__}: {e}'}
    with open(log, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, indent=1)
    return res


def gates(wt: str, slug: str) -> tuple[bool, str]:
    """Our own re-run of the publish gates; the agents' reports of them are not trusted."""
    v = run([sys.executable, 'tools/verify.py', f'reports/{slug}_analysis.html'], wt, 600)
    a = run([sys.executable, 'tools/chart_audit.py', slug], wt, 600)
    audit = (a.stdout.splitlines() or [''])[0]
    wrong = re.search(r'WRONG points[^:]*: (\d+)', audit)
    ok = v.returncode == 0 and v.stdout.startswith('PASS') and wrong is not None and wrong.group(1) == '0' \
        and ' errors 0 ' in audit
    with open(os.path.join(wt, 'reports', f'{slug}_analysis.html'), 'rb') as fh:
        crlf = fh.read().count(b'\r\n')
    return ok and not crlf, f"{v.stdout.strip()} | {audit}" + (f' | {crlf} CRLF' if crlf else '')


def refresh_one(i: dict, wt: str, logs: str, lock: threading.Lock) -> Outcome:
    slug = i['slug']
    out: Outcome = {'slug': slug, 'ticker': i['ticker'], 'tier': i['tier'], 'verdict': 'failed', 'detail': '',
                    'cost_usd': 0.0, 'denials': [], 'pitfalls': []}
    b = claude('ttg-report-builder', builder_prompt(i, wt), wt, os.path.join(logs, f'{slug}.builder.json'))
    c: dict = {}
    if not b.get('is_error'):
        c = claude('ttg-report-checker', checker_prompt(i, wt, str(b.get('result', ''))), wt,
                   os.path.join(logs, f'{slug}.checker.json'))
    for r in (b, c):
        out['cost_usd'] += float(r.get('total_cost_usd') or 0)
        out['denials'] += [json.dumps(d)[:200] for d in r.get('permission_denials') or []]
    out['pitfalls'] = pitfall_lines(str(c.get('result', '')))
    path = f'reports/{slug}_analysis.html'
    with lock:   # one git operation at a time; the agents only ever touch their own report
        changed = bool(git(wt, 'status', '--porcelain', '--', path).strip())
        if b.get('is_error') or c.get('is_error') or not c:
            out['detail'] = 'builder error' if b.get('is_error') else 'checker error'
        elif verdict_hold(str(c.get('result', ''))):
            out['detail'] = 'checker verdict HOLD'
        elif not changed:
            out['detail'] = 'no change to the report'
        else:
            ok, why = gates(wt, slug)
            if ok:
                git(wt, 'add', '--', path)
                out['tier'] = built_tier(str(b.get('result', '')), i['tier'])
                git(wt, 'commit', '-q', '-m', f"{i['ticker']} earnings refresh ({out['tier']}, print {i['release']}), "
                    "unattended: builder + independent checker, verify PASS, chart_audit 0 wrong",
                    '-m', 'Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>')
                out['verdict'], out['detail'] = 'committed', why
                return out
            out['detail'] = f'gates failed: {why}'
        if changed:   # leave nothing half-done in the tree: the summary and the logs keep the work
            shutil.copy(os.path.join(wt, path), os.path.join(logs, f'{slug}_analysis.rejected.html'))
            git(wt, 'checkout', '--', path)
            out['verdict'] = 'reverted'
    return out


# ---- the worktree ----

def main_checkout() -> str:
    common = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], cwd=rd.ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    return os.path.dirname(common)


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
        git(wt, 'merge', '-q', '--no-edit', base)
    shutil.copytree(os.path.join(main, '.claude', 'agents'), os.path.join(wt, '.claude', 'agents'),
                    dirs_exist_ok=True)
    return wt


def summary_md(day: str, outcomes: list[Outcome], waiting: list[dict], notes: list[str]) -> str:
    lines = [f'# Auto refresh — {day}', '', f'Branch `{BRANCH}`; nothing is on main until Oki merges it.', '']
    for o in outcomes:
        lines.append(f"- **{o['ticker']}** {o['tier']} — {o['verdict']}: {o['detail']} · ~${o['cost_usd']:.2f} "
                     "(client-side estimate)" + (f" · {len(o['denials'])} tool denials" if o['denials'] else ''))
    if waiting:
        lines += ['', f'Due but not run (on the other schedule, over the T2 cap, or out of attempts): {len(waiting)}',
                  *[f"- {i['ticker']} {i['tier']} released {i['release']} ({i['status']})" for i in waiting]]
    return '\n'.join(lines + [''] + notes) + '\n'


def main(argv: list[str] | None = None) -> int:
    ap = rd.parser('Unattended earnings refreshes onto the review branch.')
    ap.add_argument('--base', default='origin/main', help='what the review branch builds on (default origin/main)')
    ap.add_argument('--t2-cap', type=int, default=T2_CAP)
    ap.add_argument('--jobs', type=int, default=JOBS)
    ap.add_argument('--only', nargs='*', help='limit the run to these slugs')
    ap.add_argument('--tiers', default='T1,T2', help='tiers to refresh, e.g. T1 (the daily run) or T2 (the weekly run)')
    ap.add_argument('--dry-run', action='store_true', help='show what would run; no agents, commits or push')
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[union-attr]
    day = datetime.date.today().isoformat()
    wt = prepare(main_checkout(), args.base)
    q = run([sys.executable, 'tools/refresh_queue.py', '--repo', wt], wt, 1800)
    print(q.stdout.strip())
    qdir = os.path.join(wt, 'tasks', 'queue')
    with open(os.path.join(qdir, 'queue.json'), encoding='utf-8') as fh:
        items = json.load(fh)['items']
    att_path = os.path.join(qdir, 'attempts.json')
    attempts: dict[str, dict[str, int]] = {}
    if os.path.exists(att_path):
        with open(att_path, encoding='utf-8') as fh:
            attempts = json.load(fh)
    tiers = tuple(t.strip().upper() for t in args.tiers.split(',') if t.strip())
    work = select(items, attempts, args.t2_cap, args.only, tiers)
    waiting = [i for i in items if i['status'] in TIER_ORDER and i not in work and (not args.only or i['slug'] in args.only)]
    print(f'run {day}: ' + (', '.join(f"{i['ticker']} {i['tier']}" for i in work) or 'nothing due'))
    if args.dry_run:
        for i in work[:1]:
            print('\n--- builder prompt ---\n' + builder_prompt(i, wt))
        return 0
    logs = os.path.join(qdir, 'runs', day)
    os.makedirs(logs, exist_ok=True)
    for i in work:
        attempts.setdefault(i['slug'], {})[i['release']] = attempts.get(i['slug'], {}).get(i['release'], 0) + 1
    rd.write_json(att_path, attempts, indent=1)
    lock = threading.Lock()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        outcomes = list(ex.map(lambda i: refresh_one(i, wt, logs, lock), work))
    notes = []
    if any(o['verdict'] == 'committed' for o in outcomes):
        for tool in ('manifest.py', 'style_tags.py', 'card_tags.py'):
            r = run([sys.executable, f'tools/{tool}'], wt)
            notes.append(f"- {tool}: exit {r.returncode}")
        git(wt, 'add', '--', 'data')
        if git(wt, 'status', '--porcelain', '--', 'data').strip():
            git(wt, 'commit', '-q', '-m', 'Manifest, style and card tags rebuilt after the unattended refreshes',
                '-m', 'Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>')
        checks = run([sys.executable, 'tools/run_checks.py'], wt, 1800)
        notes.append('- run_checks: ' + ' / '.join(ln for ln in checks.stdout.splitlines() if ln[:4] in ('ok  ', 'FAIL', 'SKIP')))
        push = run(['git', 'push', '-q', 'origin', BRANCH], wt)
        notes.append(f"- push {BRANCH}: {'ok' if push.returncode == 0 else push.stderr.strip()}")
    pend = [f"- {day} {o['ticker']}: {ln}" for o in outcomes for ln in o['pitfalls']]
    if pend:
        with open(os.path.join(qdir, 'pitfalls_pending.md'), 'a', encoding='utf-8', newline='\n') as fh:
            fh.write('\n'.join(pend) + '\n')
    text = summary_md(day, outcomes, waiting, notes)
    with open(os.path.join(qdir, 'runs', f'{day}.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    print(text)
    return 0 if all(o['verdict'] == 'committed' for o in outcomes) else 1


if __name__ == '__main__':
    sys.exit(main())
