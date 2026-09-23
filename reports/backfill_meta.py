#!/usr/bin/env python3
"""Give every report tear-sheet a machine-readable identity in its <head>.

Run from the repo root:
    python3 reports/backfill_meta.py            # dry run — says what it would change
    python3 reports/backfill_meta.py --apply    # write the files

Adds two tags immediately after </title>:

    <meta name="tg:ticker" content="AAPL">
    <meta name="tg:asof" content="2026-08-10">

That is the whole change: two invisible lines per file, nothing else touched. No class
is added and no element is restructured, so the reports look and behave exactly as they
do now — and the in-flight as-of hero work (.tg-note / .tg-asof-live) is free to land
however it likes without colliding with this.

Why <meta> rather than attributes on the banner: the banner is presentation and is being
redesigned; the as-of date is document metadata. Putting state on an element someone is
restyling is how it gets lost.

The as-of date comes from the same parser build_manifest.py uses — the "Static data as
of ..." banner prose. A file whose date cannot be parsed is skipped and named, never
guessed at. Existing tg:asof tags are left alone unless --force, so a hand-corrected
date survives a re-run.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_manifest import META, REPORTS, parse_banner_date, read  # noqa: E402

TITLE_END = re.compile(r"</title>", re.I)


def tags_for(ticker: str, asof: str) -> str:
    return (f'\n<meta name="tg:ticker" content="{ticker}">'
            f'\n<meta name="tg:asof" content="{asof}">')


def strip_existing(src: str) -> str:
    return re.sub(r'\n?<meta\s+name=["\']tg:(?:ticker|asof)["\'][^>]*>', "", src, flags=re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the files (default: dry run)")
    ap.add_argument("--force", action="store_true", help="overwrite tags that are already there")
    args = ap.parse_args()

    added, skipped, rewritten, failed = [], [], [], []

    for fname in sorted(f for f in os.listdir(REPORTS) if f.endswith("_analysis.html")):
        path = os.path.join(REPORTS, fname)
        src = read(path)
        ticker = fname[: -len("_analysis.html")].upper()
        existing = {k.lower(): v for k, v in META.findall(src)}

        if "asof" in existing and not args.force:
            skipped.append(ticker)
            continue

        asof = parse_banner_date(src)
        if not asof:
            failed.append(ticker)
            continue

        m = TITLE_END.search(src)
        if not m:
            failed.append(ticker + " (no <title>)")
            continue

        base = strip_existing(src) if existing else src
        m = TITLE_END.search(base)
        out = base[: m.end()] + tags_for(ticker, asof) + base[m.end():]

        if out == src:
            skipped.append(ticker)
            continue
        (rewritten if existing else added).append(ticker)
        if args.apply:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(out)

    verb = "wrote" if args.apply else "would write"
    print(f"{verb}: {len(added)} added, {len(rewritten)} updated, "
          f"{len(skipped)} already tagged, {len(failed)} skipped")
    if failed:
        print("  ! no as-of date found: " + ", ".join(failed))
    if not args.apply:
        print("  (dry run — pass --apply to write)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
