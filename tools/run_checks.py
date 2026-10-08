#!/usr/bin/env python3
"""Every check on the build scripts and the Tables engines, in one command. Run it before pushing to main,
which deploys the site.

usage:  py -3 tools/run_checks.py

Runs, from the repo root:
  the tools unit tests         py -3 -m unittest discover -s tools/tests -t tools
  the Tables builder tests     py -3 -m unittest discover -s tables/checks -t tables  (incl. committed pages == build)
  the Tables engine checks     node tables/checks/{craps_engine_check,games_check,bj_engine_check,baccarat_engine_check,tcp_engine_check}.js
  the type check               py -3 -m mypy   (skipped, and said so, when mypy is not installed)
Exits 1 when any of them fails. The report-content gates (verify.py, chart_audit.py) are separate: they
check the published reports, not this code.
"""
import importlib.util
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_PYTHON = (3, 11)   # typing.NotRequired, datetime.UTC

CHECKS = [
    ('tools unit tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tools/tests', '-t', 'tools']),
    ('Tables builder tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tables/checks', '-t', 'tables']),
    ('craps engine', ['node', 'tables/checks/craps_engine_check.js']),
    ('simulator outcome tables', ['node', 'tables/checks/games_check.js']),
    ('blackjack engine', ['node', 'tables/checks/bj_engine_check.js']),
    ('baccarat engine', ['node', 'tables/checks/baccarat_engine_check.js']),
    ('three card poker engine', ['node', 'tables/checks/tcp_engine_check.js']),
    ('glossary pages', [sys.executable, 'tools/glossary.py', '--check']),
    ('type check', [sys.executable, '-m', 'mypy']),
]


def available(cmd: list[str]) -> str | None:
    """None when the check can run here, else why it cannot."""
    if cmd[0] == 'node' and not shutil.which('node'):
        return 'node is not installed'
    if cmd[1:3] == ['-m', 'mypy'] and importlib.util.find_spec('mypy') is None:
        return 'mypy is not installed (py -3 -m pip install mypy)'
    return None


def main() -> int:
    if sys.version_info < MIN_PYTHON:
        print(f'the scripts need Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or later; this is {sys.version.split()[0]}')
        return 1
    failed, skipped = [], []
    for name, cmd in CHECKS:
        why = available(cmd)
        if why:
            skipped.append(f'{name}: {why}')
            continue
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        out = (r.stdout + r.stderr).strip().splitlines()
        print(f"{'ok  ' if r.returncode == 0 else 'FAIL'} {name}: {out[-1] if out else ''}")
        if r.returncode:
            failed.append(name)
            print('\n'.join('     ' + line for line in out[-30:]))
    for s in skipped:
        print(f'SKIP {s}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
