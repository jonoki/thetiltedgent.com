#!/usr/bin/env python3
"""TTG chip set + card back, as SVG masters (1080-square chips, 750x1050 card) with all text converted to outlines.
Writes assets/chips/ttg-chip-<value>.svg and assets/cards/ttg-card-back.svg.

usage:  py -3 tools/build_chips.py --font <cinzel-latin-700-normal.woff> --mark <ttg-chip.svg>

Neither input is in the repo: the font is Cinzel 700 (the @fontsource/cinzel package ships the .woff), and the
mark is ttg-chip.svg, the Instagram chip artwork the monogram and rim geometry are taken from. Needs fontTools
(`py -3 -m pip install fonttools`), which nothing else in the repo uses.
"""
import argparse
import math
import os
import re
import sys
from typing import NamedTuple

import repodata as rd

OUT_CHIPS = os.path.join(rd.ROOT, 'assets', 'chips')
OUT_CARDS = os.path.join(rd.ROOT, 'assets', 'cards')
CHIP_SIZE = 1080                 # chip SVG viewBox, square
CARD_W, CARD_H = 750, 1050       # poker card, 2.5 x 3.5 in
LATTICE_STEP = 34                # card-back diagonal lattice spacing
MONOGRAM_GROUP = '<g transform="translate(540 540) scale(0.8772) translate(-685.5 -688.0)">'   # in the source mark


class Font:
    """The Cinzel font the text is drawn in: its glyph set, character map and units per em."""

    def __init__(self, path: str) -> None:
        """Raises ImportError when fontTools is not installed."""
        from fontTools.ttLib import TTFont   # imported here: only this script needs fontTools
        font = TTFont(path)
        self.glyphs, self.cmap, self.upm = font.getGlyphSet(), font.getBestCmap(), font['head'].unitsPerEm

    def text_path(self, s: str, size: float, x: float, y: float, anchor: str = 'middle', spacing: float = 0) -> str:
        """SVG <path>s for string s, baseline at y, sized in px; anchor is 'start', 'middle' or 'end'."""
        from fontTools.pens.svgPathPen import SVGPathPen   # see __init__
        scale = size / self.upm
        names = [self.cmap.get(ord(c)) for c in s]
        widths = [self.glyphs[g].width if g else 0 for g in names]
        total = sum(w * scale for w in widths) + spacing * (len(s) - 1)
        x0 = x - total / 2 if anchor == 'middle' else (x - total if anchor == 'end' else x)
        parts, adv = [], 0.0
        for g, w in zip(names, widths):
            if g:
                pen = SVGPathPen(self.glyphs)
                self.glyphs[g].draw(pen)
                d = pen.getCommands()
                if d:
                    parts.append(f'<path transform="translate({x0 + adv:.2f} {y:.2f}) scale({scale:.5f} {-scale:.5f})" d="{d}"/>')
            adv += w * scale + spacing
        return ''.join(parts)


def cut(src: str, start: str, end: str, what: str, from_: int = 0) -> tuple[str, int]:
    """(src from start through end, where it begins); ValueError naming the part of the mark when either is missing."""
    i = src.find(start, from_)
    j = src.find(end, i) if i >= 0 else -1
    if j < 0:
        raise ValueError(f'the chip mark has no {what} ({start!r} ... {end!r})')
    return src[i:j + len(end)], i


def read_mark(path: str) -> tuple[str, str]:
    """(the <defs> block, the monogram's paths) from the source chip mark."""
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    defs, _ = cut(src, '<defs>', '</defs>', '<defs> block')
    mono, _ = cut(src, MONOGRAM_GROUP, '</g>', 'monogram group')
    return defs, mono[len(MONOGRAM_GROUP):-len('</g>')]   # the paths only


def spots(a: str, b: str) -> str:
    """The eight edge spots: arcs at r=470, alternating colours a and b."""
    out = ''
    for i in range(8):
        th0, th1 = math.radians(i * 45 - 7.5), math.radians(i * 45 + 7.5)
        x0, y0 = 540 + 470 * math.sin(th0), 540 - 470 * math.cos(th0)
        x1, y1 = 540 + 470 * math.sin(th1), 540 - 470 * math.cos(th1)
        colour = a if i % 2 == 0 else b
        out += (f'<path d="M {x0:.2f} {y0:.2f} A 470 470 0 0 1 {x1:.2f} {y1:.2f}" fill="none" stroke-width="104" '
                f'stroke-linecap="round" stroke="{colour}"/>\n')
    return out


class Chip(NamedTuple):
    """One chip: its value, inlay gradient and rim/body field (centre, mid, edge; darker toward the edge),
    edge-spot colours and value text colour."""
    value: int
    disc: tuple[str, str, str]
    body: tuple[str, str, str]
    spots: tuple[str, str]
    text: str


CHIPS = [
    Chip(1,   ('#FBF6EA', '#F1E6CF', '#D9CDB0'), ('#F4EBD6', '#E6D9BC', '#C9BB9A'), ('#0B0913', '#C21E38'), '#7A1122'),
    Chip(5,   ('#D8334A', '#B71E36', '#8A1428'), ('#C42239', '#8F1A2B', '#5C0F1B'), ('#F1E6CF', '#0B0913'), '#F1E6CF'),
    Chip(25,  ('#2F9862', '#1F7A4D', '#145233'), ('#237A4E', '#175A38', '#0D3A24'), ('#F1E6CF', '#C21E38'), '#F1E6CF'),
    Chip(100, ('#2A2434', '#161120', '#08060E'), ('#1E1830', '#0E0B16', '#06050B'), ('#F1E6CF', '#C21E38'), '#FFD57A'),
    Chip(500, ('#7A4CCB', '#5A339E', '#3B2170'), ('#5E38A8', '#452A80', '#2A1750'), ('#F1E6CF', '#D9A85C'), '#FFD57A'),
]


def gradient(gid: str, cx: str, cy: str, r: str, mid: str, colours: tuple[str, str, str]) -> str:
    c0, c1, c2 = colours
    return (f'<radialGradient id="{gid}" cx="{cx}" cy="{cy}" r="{r}"><stop offset="0" stop-color="{c0}"/>'
            f'<stop offset="{mid}" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></radialGradient>')


def chip_svg(font: Font, defs: str, monogram: str, chip: Chip) -> str:
    """One chip: the mark's defs with this chip's body and inlay gradients, its spots, value and the monogram."""
    d = re.sub(r'<radialGradient id="body".*?</radialGradient>',
               lambda _: gradient('body', '38%', '30%', '78%', '0.55', chip.body), defs, flags=re.S)
    d = re.sub(r'<radialGradient id="disc".*?</radialGradient>',
               lambda _: gradient('disc', '42%', '34%', '72%', '0.62', chip.disc), d, flags=re.S)
    label = f'${chip.value:,}'
    val = font.text_path(label, 150 if chip.value < 100 else 132, 540, 792, 'middle', 4)
    tiny = font.text_path('THE TILTED GENT', 26, 540, 268, 'middle', 6)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHIP_SIZE} {CHIP_SIZE}" width="{CHIP_SIZE}" height="{CHIP_SIZE}" role="img" aria-label="The Tilted Gent {label} chip">
<title>The Tilted Gent — {label} chip</title>
{d}
<g clip-path="url(#chipClip)">
  <circle cx="540" cy="540" r="540" fill="url(#body)"/>
{spots(*chip.spots)}  <circle cx="540" cy="540" r="540" fill="url(#sheen)"/>
  <circle cx="540" cy="540" r="398" fill="none" stroke="url(#gold)" stroke-width="15"/>
  <circle cx="540" cy="540" r="374" fill="none" stroke="#D9A85C" stroke-width="3.5" opacity="0.55"/>
  <circle cx="540" cy="540" r="368" fill="#0A0305"/>
  <circle cx="540" cy="540" r="363" fill="url(#disc)"/>
  <circle cx="540" cy="540" r="368" fill="url(#sheen)"/>
  <g fill="#D9A85C" opacity="0.85">{tiny}</g>
  <g transform="translate(540 500) scale(0.56) translate(-685.5 -688.0)">
{monogram}
  </g>
  <line x1="420" y1="676" x2="660" y2="676" stroke="#D9A85C" stroke-width="3" opacity="0.6"/>
  <g fill="{chip.text}">{val}</g>
  <circle cx="540" cy="540" r="540" fill="url(#vig)"/>
</g>
</svg>
'''


def lattice() -> str:
    """The card back's diagonal lattice: lines one way, then the other, LATTICE_STEP apart."""
    line = '<line x1="{}" y1="0" x2="{}" y2="{}" stroke="#D9A85C" stroke-opacity="0.22" stroke-width="2"/>'
    return (''.join(line.format(x, x + CARD_H, CARD_H) for x in range(-CARD_H, CARD_W, LATTICE_STEP))
            + ''.join(line.format(x, x - CARD_H, CARD_H) for x in range(0, CARD_W + CARD_H, LATTICE_STEP)))


def card_back_svg(font: Font, defs: str, monogram: str) -> str:
    gold_defs, _ = cut(defs, '<linearGradient id="gold"', '</linearGradient>', 'gold gradient')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {CARD_H}" width="{CARD_W}" height="{CARD_H}" role="img" aria-label="The Tilted Gent card back">
<title>The Tilted Gent — card back</title>
<defs>{gold_defs}
  <radialGradient id="field" cx="50%" cy="42%" r="75%"><stop offset="0" stop-color="#1C1330"/><stop offset="0.6" stop-color="#0E0A18"/><stop offset="1" stop-color="#06050B"/></radialGradient>
  <clipPath id="cardClip"><rect x="0" y="0" width="{CARD_W}" height="{CARD_H}" rx="38"/></clipPath>
  <clipPath id="innerClip"><rect x="52" y="52" width="646" height="946" rx="22"/></clipPath>
</defs>
<g clip-path="url(#cardClip)">
  <rect width="{CARD_W}" height="{CARD_H}" fill="#F1E6CF"/>
  <rect x="14" y="14" width="722" height="1022" rx="30" fill="#06050B"/>
  <rect x="26" y="26" width="698" height="998" rx="26" fill="none" stroke="url(#gold)" stroke-width="6"/>
  <rect x="40" y="40" width="670" height="970" rx="24" fill="none" stroke="#D9A85C" stroke-width="2" opacity="0.7"/>
  <g clip-path="url(#innerClip)">
    <rect x="52" y="52" width="646" height="946" fill="url(#field)"/>
    {lattice()}
    <ellipse cx="375" cy="470" rx="250" ry="290" fill="#06050B" opacity="0.72"/>
    <ellipse cx="375" cy="470" rx="250" ry="290" fill="none" stroke="url(#gold)" stroke-width="5"/>
    <ellipse cx="375" cy="470" rx="236" ry="276" fill="none" stroke="#D9A85C" stroke-width="1.5" opacity="0.6"/>
  </g>
  <g transform="translate(375 470) scale(0.60) translate(-685.5 -688.0)">
{monogram}
  </g>
  <g fill="#D9A85C">{font.text_path('THE TILTED GENT', 34, 375, 830, 'middle', 7)}</g>
  <g fill="#D9A85C" opacity="0.7">{font.text_path('MARKETS · ODDS · RISK', 20, 375, 872, 'middle', 5)}</g>
</g>
</svg>
'''


def write(path: str, text: str) -> None:
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def main(argv: list[str] | None = None) -> int | str:
    """0 when every master is written, else what stopped it (a missing input, fontTools, a malformed mark)."""
    ap = argparse.ArgumentParser(description='Build the TTG chip and card-back SVG masters.')
    ap.add_argument('--font', required=True, help='Cinzel 700 font file (cinzel-latin-700-normal.woff)')
    ap.add_argument('--mark', required=True, help='the source chip mark, ttg-chip.svg')
    args = ap.parse_args(argv)
    missing = [p for p in (args.font, args.mark) if not os.path.exists(p)]
    if missing:
        return f'not found: {", ".join(missing)}'
    try:
        font = Font(args.font)
    except ImportError:
        return 'build_chips.py needs fontTools: py -3 -m pip install fonttools'
    try:
        defs, monogram = read_mark(args.mark)
        back = card_back_svg(font, defs, monogram)
    except ValueError as e:
        return f'{args.mark}: {e}'
    for chip in CHIPS:
        write(os.path.join(OUT_CHIPS, f'ttg-chip-{chip.value}.svg'), chip_svg(font, defs, monogram, chip))
    write(os.path.join(OUT_CARDS, 'ttg-card-back.svg'), back)
    print('chips + card back written')
    return 0


if __name__ == '__main__':
    sys.exit(main())
