#!/usr/bin/env python3
"""Pre-publish harness: structure, chart arrays, final price == header price, P/E arithmetic, 52-wk range."""
import re, sys, json, glob, os

def num(s):
    return float(s.replace(',', ''))

def check(path):
    t = open(path, encoding='utf-8').read()
    out = {}
    out['doctype'] = t.count('<!DOCTYPE'); out['html'] = len(re.findall(r'<html[\s>]', t)); out['head'] = len(re.findall(r'<head[\s>]', t))
    out['body'] = len(re.findall(r'<body[\s>]', t)); out['/body'] = t.count('</body>'); out['/html'] = t.count('</html>')
    out['canvas'] = t.count('<canvas')
    out['style_open'] = len(re.findall(r'<style[\s>]', t)); out['style_close'] = t.count('</style>')   # CAT shipped with no </style> and rendered blank for five weeks
    out['lines'] = t.count('\n')
    # header price
    m = re.search(r'class="price-current"[^>]*>\s*\$?([\d,]+\.\d+)', t)
    price = num(m.group(1)) if m else None
    out['price'] = price
    # arrays: find labels & prices arrays in script
    lab = re.search(r'(?:const|let|var)\s+labels\s*=\s*\[(.*?)\];', t, re.S)
    pr = re.search(r'(?:const|let|var)\s+prices\s*=\s*\[(.*?)\];', t, re.S)
    if lab and pr:
        # split on commas rather than scanning for number-ish runs: a character
        # class containing ',' swallows a whole array as one token when the
        # source has no space after the commas (this silently passed COST/LLY)
        labels = re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', lab.group(1))
        prices = []
        for part in pr.group(1).split(','):
            part = part.strip()
            if part:
                try:
                    prices.append(num(part))
                except ValueError:
                    pass
        out['n_labels'] = len(labels); out['n_prices'] = len(prices)
        out['last_price'] = prices[-1] if prices else None
        out['price_match'] = (price is not None and prices and abs(prices[-1] - price) < 0.006)
    else:
        out['n_labels'] = out['n_prices'] = None; out['price_match'] = False
    # P/E arithmetic
    pe = re.search(r'Trailing\s*<span[^>]*>P/E</span>.*?<td[^>]*>\s*([\d.]+)', t, re.S) or re.search(r'Trailing P/E.*?<td[^>]*>\s*(?:<[^>]+>\s*)*([\d.]+)', t, re.S)   # value may sit inside a <span>
    # anchor on the row's label cell first: the loose pattern fires on "TTM EPS" in the P/E row's context text
    # and then reads the next row's value (VMC read its Forward P/E as EPS)
    eps = re.search(r'>\s*EPS\s*\(TTM\)\s*(?:</span>)?\s*</td>\s*<td[^>]*>\s*\$?(-?[\d.]+)', t) \
        or re.search(r'EPS.*?TTM.*?<td[^>]*>\s*\$?(-?[\d.]+)', t, re.S)
    if pe and eps and price:
        try:
            out['pe_stated'] = float(pe.group(1)); out['pe_calc'] = round(price / float(eps.group(1)), 2)
        except Exception:
            pass
    # 52-week range
    r = re.search(r'52-Week Range.*?\$?([\d,]+\.\d+)\s*(?:[–\-—]|&ndash;|&mdash;)\s*\$?([\d,]+\.\d+)', t, re.S)
    if r and price:
        lo, hi = num(r.group(1)), num(r.group(2)); out['range_ok'] = lo <= price <= hi; out['range'] = (lo, hi)
    date = re.search(r'Static data as of ([A-Za-z]+ \d+, \d{4})', t)
    out['date'] = date.group(1) if date else None
    out['sitenav'] = t.count('tg-sitenav')
    ok = all(out[k] == 1 for k in ['doctype', 'html', 'head', 'body', '/body', '/html']) and out['canvas'] == 2 and out['style_open'] == out['style_close'] \
        and out['price_match'] and out['n_labels'] == out['n_prices'] and out['sitenav'] == 0 and out.get('range_ok', True)
    out['OK'] = ok
    return out

if __name__ == '__main__':
    files = sys.argv[1:] or sorted(glob.glob('/home/claude/work/reports/*_analysis.html'))
    for f in files:
        o = check(f)
        flag = 'PASS' if o['OK'] else 'FAIL'
        print(f"{flag} {os.path.basename(f):22s} price={o['price']} last={o.get('last_price')} n={o['n_labels']}/{o['n_prices']} "
              f"skel={o['doctype']}{o['html']}{o['head']}{o['body']}{o['/body']}{o['/html']} canvas={o['canvas']} lines={o['lines']} "
              f"pe={o.get('pe_stated')}/{o.get('pe_calc')} range={o.get('range_ok')} date={o['date']}")
