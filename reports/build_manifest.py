#!/usr/bin/env python3
"""Scan the report tear-sheets into data/reports.json — the machine-readable state
the refresh queue runs on.

Run from the repo root:  python3 reports/build_manifest.py
Options:  --no-git   skip the git lookup for first-published dates (much faster)
          --check    exit 1 if any report's as-of date is unknown (for CI)

Where each field comes from, and why it matters:

  asof      The date the analysis is frozen at. Read from <meta name="tg:asof"> when the
            report declares it, otherwise parsed out of the "Static data as of ..." banner
            prose. `asof_source` records which, because a parsed date is a guess about
            someone's sentence and a declared one is a fact. Run reports/backfill_meta.py
            to turn parsed into declared.

  published First commit that added the file, from git. Together with `asof` this is the
            whole refresh history a report carries: published == asof means it has never
            been refreshed; asof > published means it has.

  indices   From reports/index.html, the generated landing page — the only place S&P 500 /
            NDX / Dow membership and the ISO addition dates live. Sector and industry
            come from the same cards.

The stale rule this feeds is one comparison: a report is stale iff the company has
reported since `asof`. Everything else here is prioritisation or provenance.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "reports")
OUT = os.path.join(ROOT, "data", "reports.json")

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"])}
MONTHS.update({"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
               "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12})

# "Static data as of August 10, 2026", "as of the September 1, 2026 close", "as of Sep 2, 2026 ("
BANNER = re.compile(
    r"static\s+data\s+as\s+of[^<]{0,80}?"
    r"(january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)\.?\s+(\d{1,2}),?\s+(\d{4})",
    re.I)
META = re.compile(r'<meta\s+name=["\']tg:([a-z-]+)["\']\s+content=["\']([^"\']*)["\']', re.I)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def parse_banner_date(src: str) -> str | None:
    m = BANNER.search(src)
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    try:
        return date(int(m.group(3)), mon, int(m.group(2))).isoformat()
    except ValueError:          # e.g. "February 30"
        return None


def parse_cards(index_src: str) -> dict[str, dict]:
    """One record per card on the reports landing page, keyed by ticker."""
    cards: dict[str, dict] = {}
    sector = None
    # walk the file so each card inherits the sector group it sits in
    for chunk in re.finditer(r'<section class="sgroup"[^>]*data-s="([^"]*)"|<a class="rep"([^>]*)>(.*?)</a>',
                             index_src, re.S):
        if chunk.group(1):
            sector = chunk.group(1)
            continue
        attrs, body = chunk.group(2), chunk.group(3)

        def attr(name: str) -> str | None:
            m = re.search(name + r'="([^"]*)"', attrs)
            return m.group(1) if m else None

        tick = re.search(r'<span class="tick">([^<]*)</span>', body)
        name = re.search(r"<h3>(.*?)</h3>", body, re.S)
        sect = re.search(r'<span class="sect">([^<]*)</span>', body)
        if not tick:
            continue
        indices = {}
        if attr("data-sp"):
            indices["SP500"] = attr("data-sp")
        if "data-ndx" in attrs:
            indices["NDX"] = None       # Nasdaq publishes no per-company addition date
        if attr("data-dow"):
            indices["DOW"] = attr("data-dow")
        cards[html.unescape(tick.group(1)).strip().upper()] = {
            "name": html.unescape(name.group(1)).strip() if name else None,
            "industry": html.unescape(sect.group(1)).strip().title() if sect else None,
            "sector": sector,
            "indices": indices,
            "href": attr("href"),
        }
    return cards


def first_commit_dates(paths: list[str]) -> dict[str, str]:
    """First commit that added each file. Empty dict if git is unavailable or shallow."""
    out: dict[str, str] = {}
    try:
        shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT,
                                 capture_output=True, text=True, timeout=20)
        if shallow.stdout.strip() == "true":
            print("  ! shallow clone — no published dates. `git fetch --unshallow` for them.",
                  file=sys.stderr)
            return out
        for rel in paths:
            r = subprocess.run(
                ["git", "log", "--diff-filter=A", "--follow", "--format=%ad", "--date=short", "--", rel],
                cwd=ROOT, capture_output=True, text=True, timeout=30)
            lines = [x for x in r.stdout.splitlines() if x.strip()]
            if lines:
                out[rel] = lines[-1]
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  ! git lookup skipped: {type(exc).__name__}", file=sys.stderr)
    return out


def build(use_git: bool = True) -> dict:
    files = sorted(f for f in os.listdir(REPORTS) if f.endswith("_analysis.html"))
    cards = parse_cards(read(os.path.join(REPORTS, "index.html")))
    published = first_commit_dates([f"reports/{f}" for f in files]) if use_git else {}
    norm_index = {re.sub(r"[^A-Z0-9]", "", t): t for t in cards}

    reports, counts = [], {"declared": 0, "parsed": 0, "unknown": 0}
    for fname in files:
        src = read(os.path.join(REPORTS, fname))
        meta = {k.lower(): v for k, v in META.findall(src)}
        ticker = (meta.get("ticker") or fname[:-len("_analysis.html")]).upper()

        if meta.get("asof"):
            asof, source = meta["asof"], "declared"
        else:
            asof = parse_banner_date(src)
            source = "parsed" if asof else "unknown"
        counts[source] += 1

        # Card tickers carry punctuation the filenames drop (BRK.B -> brkb), so fall back to
        # the same normalisation reports/index.js uses for search.
        card = cards.get(ticker) or cards.get(norm_index.get(re.sub(r"[^A-Z0-9]", "", ticker), ""), {})
        pub = published.get(f"reports/{fname}")
        reports.append({
            "ticker": ticker,
            "name": card.get("name"),
            "file": fname,
            "asof": asof,
            "asof_source": source,
            "published": pub,
            "refreshed": (bool(pub and asof and asof > pub)) if (pub and asof) else None,
            "covers_end": meta.get("covers-end"),
            "covers_label": meta.get("covers-label"),
            "indices": card.get("indices", {}),
            "sector": card.get("sector"),
            "industry": card.get("industry"),
            "on_index_page": bool(card),
        })

    listed = {re.sub(r"[^A-Z0-9]", "", t) for t in cards}
    have = {re.sub(r"[^A-Z0-9]", "", r["ticker"]) for r in reports}
    return {
        "generated_at": date.today().isoformat(),
        "generator": "reports/build_manifest.py",
        "count": len(reports),
        "asof_sources": counts,
        "warnings": {
            "missing_from_index_page": sorted(have - listed),
            "carded_but_no_file": sorted(listed - have),
            "no_asof": sorted(r["ticker"] for r in reports if not r["asof"]),
        },
        "reports": reports,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-git", action="store_true", help="skip first-published dates")
    ap.add_argument("--check", action="store_true", help="exit 1 if any as-of date is unknown")
    args = ap.parse_args()

    manifest = build(use_git=not args.no_git)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    c = manifest["asof_sources"]
    print(f"{manifest['count']} reports -> data/reports.json")
    print(f"  as-of: {c['declared']} declared, {c['parsed']} parsed, {c['unknown']} unknown")
    for key, vals in manifest["warnings"].items():
        if vals:
            print(f"  ! {key}: {', '.join(vals[:12])}{' …' if len(vals) > 12 else ''}")
    if args.check and c["unknown"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
