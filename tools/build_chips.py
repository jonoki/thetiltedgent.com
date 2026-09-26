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

import reportlib as rl

OUT_CHIPS = os.path.join(rl.ROOT, 'assets', 'chips')
OUT_CARDS = os.path.join(rl.ROOT, 'assets', 'cards')
CHIP_SIZE = 1080                 # chip SVG viewBox, square
CARD_W, CARD_H = 750, 1050       # poker card, 2.5 x 3.5 in
LATTICE_STEP = 34                # card-back diagonal lattice spacing

GS = CMAP = UPM = None           # the loaded font's glyph set, character map and units per em (see load_font)


def load_font(path):
    global GS, CMAP, UPM
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        sys.exit('build_chips.py needs fontTools: py -3 -m pip install fonttools')
    font = TTFont(path)
    GS, CMAP, UPM = font.getGlyphSet(), font.getBestCmap(), font['head'].unitsPerEm


def text_path(s, size, x, y, anchor='middle', spacing=0):
    """Return SVG <path>s for string s in Cinzel 700, baseline at y, sized in px."""
    from fontTools.pens.svgPathPen import SVGPathPen
    scale = size / UPM; parts = []; adv = 0
    glyphs = [CMAP.get(ord(c)) for c in s]
    widths = [GS[g].width if g else 0 for g in glyphs]
    total = sum(w * scale for w in widths) + spacing * (len(s) - 1)
    x0 = x - total / 2 if anchor == 'middle' else (x - total if anchor == 'end' else x)
    for g, w in zip(glyphs, widths):
        if g:
            pen = SVGPathPen(GS); GS[g].draw(pen); d = pen.getCommands()
            if d: parts.append('<path transform="translate(%.2f %.2f) scale(%.5f %.5f)" d="%s"/>' % (x0 + adv, y, scale, -scale, d))
        adv += w * scale + spacing
    return ''.join(parts)


def read_mark(path):
    """(the <defs> block, the monogram's paths) from the source chip mark."""
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    defs = src[src.index('<defs>'):src.index('</defs>') + 7]
    mono_start = src.index('<g transform="translate(540 540) scale(0.8772) translate(-685.5 -688.0)">')
    mono = src[mono_start:src.index('</g>', mono_start) + 4]
    return defs, mono[mono.index('>') + 1:-4]   # the paths only


def spots(a, b):
    """The eight edge spots: arcs at r=470, alternating colours a and b."""
    out = ''
    for i in range(8):
        th0 = math.radians(i * 45 - 7.5); th1 = math.radians(i * 45 + 7.5)
        x0, y0 = 540 + 470 * math.sin(th0), 540 - 470 * math.cos(th0); x1, y1 = 540 + 470 * math.sin(th1), 540 - 470 * math.cos(th1)
        out += '<path d="M %.2f %.2f A 470 470 0 0 1 %.2f %.2f" fill="none" stroke-width="104" stroke-linecap="round" stroke="%s"/>\n' % (x0, y0, x1, y1, a if i % 2 == 0 else b)
    return out


CHIPS = [  # value, inlay gradient (centre, mid, edge), rim/body field (chip colour, darker toward the edge), edge-spot colours, value text colour
    (1,   ('#FBF6EA', '#F1E6CF', '#D9CDB0'), ('#F4EBD6', '#E6D9BC', '#C9BB9A'), ('#0B0913', '#C21E38'), '#7A1122'),
    (5,   ('#D8334A', '#B71E36', '#8A1428'), ('#C42239', '#8F1A2B', '#5C0F1B'), ('#F1E6CF', '#0B0913'), '#F1E6CF'),
    (25,  ('#2F9862', '#1F7A4D', '#145233'), ('#237A4E', '#175A38', '#0D3A24'), ('#F1E6CF', '#C21E38'), '#F1E6CF'),
    (100, ('#2A2434', '#161120', '#08060E'), ('#1E1830', '#0E0B16', '#06050B'), ('#F1E6CF', '#C21E38'), '#FFD57A'),
    (500, ('#7A4CCB', '#5A339E', '#3B2170'), ('#5E38A8', '#452A80', '#2A1750'), ('#F1E6CF', '#D9A85C'), '#FFD57A'),
]


def chip_svg(defs, monogram, v, disc, body, spot, txtc):
    d = re.sub(r'<radialGradient id="body".*?</radialGradient>', '<radialGradient id="body" cx="38%%" cy="30%%" r="78%%"><stop offset="0" stop-color="%s"/><stop offset="0.55" stop-color="%s"/><stop offset="1" stop-color="%s"/></radialGradient>' % body, defs, flags=re.S)
    d = re.sub(r'<radialGradient id="disc".*?</radialGradient>', '<radialGradient id="disc" cx="42%%" cy="34%%" r="72%%"><stop offset="0" stop-color="%s"/><stop offset="0.62" stop-color="%s"/><stop offset="1" stop-color="%s"/></radialGradient>' % disc, d, flags=re.S)
    label = '$' + ('{:,}'.format(v))
    val = text_path(label, 150 if v < 100 else 132, 540, 792, 'middle', 4)
    tiny = text_path('THE TILTED GENT', 26, 540, 268, 'middle', 6)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CHIP_SIZE} {CHIP_SIZE}" width="{CHIP_SIZE}" height="{CHIP_SIZE}" role="img" aria-label="The Tilted Gent {label} chip">
<title>The Tilted Gent — {label} chip</title>
{d}
<g clip-path="url(#chipClip)">
  <circle cx="540" cy="540" r="540" fill="url(#body)"/>
{spots(*spot)}  <circle cx="540" cy="540" r="540" fill="url(#sheen)"/>
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
  <g fill="{txtc}">{val}</g>
  <circle cx="540" cy="540" r="540" fill="url(#vig)"/>
</g>
</svg>
'''


def card_back_svg(defs, monogram):
    lattice = ''.join('<line x1="%d" y1="0" x2="%d" y2="%d" stroke="#D9A85C" stroke-opacity="0.22" stroke-width="2"/>' % (x, x + CARD_H, CARD_H)
                      for x in range(-CARD_H, CARD_W, LATTICE_STEP))
    lattice += ''.join('<line x1="%d" y1="0" x2="%d" y2="%d" stroke="#D9A85C" stroke-opacity="0.22" stroke-width="2"/>' % (x, x - CARD_H, CARD_H)
                       for x in range(0, CARD_W + CARD_H, LATTICE_STEP))
    gold_defs = defs[defs.index('<linearGradient id="gold"'):defs.index('</linearGradient>') + 17]
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
    {lattice}
    <ellipse cx="375" cy="470" rx="250" ry="290" fill="#06050B" opacity="0.72"/>
    <ellipse cx="375" cy="470" rx="250" ry="290" fill="none" stroke="url(#gold)" stroke-width="5"/>
    <ellipse cx="375" cy="470" rx="236" ry="276" fill="none" stroke="#D9A85C" stroke-width="1.5" opacity="0.6"/>
  </g>
  <g transform="translate(375 470) scale(0.60) translate(-685.5 -688.0)">
{monogram}
  </g>
  <g fill="#D9A85C">{text_path('THE TILTED GENT', 34, 375, 830, 'middle', 7)}</g>
  <g fill="#D9A85C" opacity="0.7">{text_path('MARKETS · ODDS · RISK', 20, 375, 872, 'middle', 5)}</g>
</g>
</svg>
'''


def write(path, text):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Build the TTG chip and card-back SVG masters.')
    ap.add_argument('--font', required=True, help='Cinzel 700 font file (cinzel-latin-700-normal.woff)')
    ap.add_argument('--mark', required=True, help='the source chip mark, ttg-chip.svg')
    args = ap.parse_args(argv)
    for p in (args.font, args.mark):
        if not os.path.exists(p):
            sys.exit(f'not found: {p}')
    load_font(args.font)
    defs, monogram = read_mark(args.mark)
    for v, disc, body, spot, txtc in CHIPS:
        write(os.path.join(OUT_CHIPS, 'ttg-chip-%d.svg' % v), chip_svg(defs, monogram, v, disc, body, spot, txtc))
    write(os.path.join(OUT_CARDS, 'ttg-card-back.svg'), card_back_svg(defs, monogram))
    print('chips + card back written')


if __name__ == '__main__':
    main()
