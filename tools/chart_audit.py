"""Audit report 5-year monthly charts against Yahoo monthly closes. Read-only on the repo.

usage: py -3 tools/chart_audit.py [slug ...]      (no args = whole library)
Flags any chart point >3% from Yahoo's split-adjusted month-end close AND from its dividend-adjusted
close, and lists series that are dividend-adjusted but never say so. The last point (the as-of close)
is verify.py's job. Yahoo JSON is cached under $TEMP/ttg_chart_audit/yh (delete to refetch)."""
import re, json, os, sys, time, glob, datetime, urllib.request, ssl
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
S = os.path.join(os.environ.get('TEMP') or os.environ.get('TMPDIR') or '/tmp', 'ttg_chart_audit')
C = os.path.join(S, 'yh'); os.makedirs(C, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MON = {m: i+1 for i, m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split())}
YSYM = {'brkb': 'BRK-B', 'bfb': 'BF-B'}

def arr(t, name):
    m = re.search(r'const\s+' + name + r'\s*=\s*\[(.*?)\]', t, re.S)
    return m.group(1) if m else None

def parse_label(s):
    s = s.strip().strip('\'"`').strip()
    m = re.match(r'([A-Za-z]{3})[a-z]*[\s\'’\-]*(\d{2,4})', s)
    if m and m.group(1).lower() in MON:
        y = int(m.group(2)); y = y + 2000 if y < 100 else y
        return (y, MON[m.group(1).lower()])
    m = re.match(r'(\d{4})-(\d{2})', s)
    if m: return (int(m.group(1)), int(m.group(2)))
    return None

def yahoo(slug, tick):
    p = os.path.join(C, slug + '.json')
    if not os.path.exists(p):
        sym = YSYM.get(slug, tick.replace('.', '-'))
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=6y&interval=1mo"
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30).read()
            open(p, 'wb').write(r); time.sleep(0.3)
        except Exception as e:
            return None, str(e)
    j = json.load(open(p, encoding='utf-8'))
    res = (j.get('chart') or {}).get('result')
    if not res: return None, 'no result'
    res = res[0]; ts = res.get('timestamp') or []
    cl = res['indicators']['quote'][0].get('close') or []
    ac = ((res['indicators'].get('adjclose') or [{}])[0].get('adjclose')) or [None]*len(cl)
    out = {}
    for t_, c, a in zip(ts, cl, ac):
        if c is None: continue
        d = datetime.datetime.fromtimestamp(t_ + (res['meta'].get('gmtoffset') or 0), datetime.UTC)
        out[(d.year, d.month)] = (c, a)
    return out, None

d = json.load(open(os.path.join(R, 'data', 'reports.json'), encoding='utf-8'))
only = set(sys.argv[1:])
rows = []
for tick, slug, sec, asof, px in d['index']:
    if only and slug not in only: continue
    t = open(os.path.join(R, 'reports', slug + '_analysis.html'), encoding='utf-8').read()
    L, P = arr(t, 'labels'), arr(t, 'prices')
    if not L or not P: rows.append({'slug': slug, 'err': 'arrays'}); continue
    labels = [x for x in re.findall(r'["\'`]([^"\'`]*)["\'`]', L)]
    prices = [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', P)]
    yh, err = yahoo(slug, tick)
    if yh is None: rows.append({'slug': slug, 'err': 'yahoo ' + err}); continue
    asof_ym = tuple(int(x) for x in asof.split('-')[:2]) if asof else None
    bad = []; n = 0; adjok = 0
    for lab, pr in zip(labels[:-1], prices[:-1]):   # last point is the as-of close, checked by verify.py
        ym = parse_label(lab)
        if not ym or ym not in yh or (asof_ym and ym >= asof_ym): continue
        n += 1
        c, a = yh[ym]
        dev = (pr - c) / c
        if abs(dev) > 0.03:
            if a and abs((pr - a) / a) <= 0.03: adjok += 1
            else: bad.append((lab, pr, round(c, 2), round(dev * 100, 1)))
    lab_adj = bool(re.search(r'(?i)dividend[- ]adjusted|adjusted (close|price)', t))
    rows.append({'slug': slug, 'tick': tick, 'asof': asof, 'checked': n, 'bad': bad, 'adj_pts': adjok, 'adj_labelled': lab_adj})
json.dump(rows, open(os.path.join(S, 'chart_audit.json'), 'w'), indent=0)
errs = [r for r in rows if 'err' in r]
flag = [r for r in rows if r.get('bad')]
unparsed = [r for r in rows if 'err' not in r and r['checked'] < 30]
adj_unl = [r for r in rows if r.get('adj_pts', 0) >= 10 and not r.get('adj_labelled')]
print('reports', len(rows), '| errors', len(errs), '| WRONG points >3% vs both close and adjclose:', len(flag), '| dividend-adjusted but unlabelled:', len(adj_unl), '| <30 comparable', len(unparsed))
print('ADJ-UNLABELLED', [r['slug'] for r in adj_unl])
for r in sorted(flag, key=lambda r: -len(r['bad']))[:60]:
    worst = max(r['bad'], key=lambda b: abs(b[3]))
    print(f"{r['slug']:6} as-of {r['asof']} bad {len(r['bad']):2}/{r['checked']:2}  worst {worst}")
print('ERR', [(r['slug'], r['err']) for r in errs][:20])
print('LOWCOUNT', [(r['slug'], r['checked']) for r in unparsed][:40])
