#!/usr/bin/env python3
"""Fact helpers for writing blog articles from DynastyMath's own data (data/players.json + data/history.json).

CLI (prints plain-text facts to quote; every number in an article must come from here or from the generated pages):
  python3 scripts/blog_facts.py sig                 # buy/sell flags (experts vs draft market), top 16 each
  python3 scripts/blog_facts.py rook                # 2026 rookies (exp == 0) by value
  python3 scripts/blog_facts.py movers [N]          # biggest risers/fallers since the baseline snapshot
  python3 scripts/blog_facts.py waiver              # Sleeper trending adds (24h/72h) with projections
  python3 scripts/blog_facts.py ros [POS]           # rest-of-season scores (same formula as build_pages.py)
  python3 scripts/blog_facts.py picks               # draft pick values
  python3 scripts/blog_facts.py player "Name" ...   # one line per player
As a module (from scripts/): `from blog_facts import *` gives V, P, N(name), vl(p), chg(p), chgs(p), gap(p), mk(p), ppg(p), l3(p), fair(a, b), GEN, BASE_D, ...
Field names: n pos team age exp inj(Out/IR/Questionable/..) gp ppg{ppr,half,std} proj{ppr,half,std} l3{ppr,g} p3{ppr,n,next} t24 t72 (trending adds)
v1 (1QB composite) v2 (superflex) cs{dp,sl,ffc,prod} sp (source spread %) con sig(buy|sell|null); picks: n v1 v2."""
import json, re, sys, pathlib, datetime
ROOT = pathlib.Path(__file__).resolve().parent.parent
D = json.loads((ROOT / 'data' / 'players.json').read_text()); H = json.loads((ROOT / 'data' / 'history.json').read_text())['days']
GEN = D['generated'][:10]; WEEK = D['week']; SEASON = D['season']
P = D['players']; V = sorted([p for p in P if p.get('v1')], key=lambda p: -p['v1'])
ONE = {p['id']: i + 1 for i, p in enumerate(V)}
PR = {}
for _pos in ('QB', 'RB', 'WR', 'TE'):
    for _i, _p in enumerate([q for q in V if q['pos'] == _pos]): PR[_p['id']] = _i + 1
def _base():
    ds = sorted(d for d in H if d < GEN)
    lo = (datetime.date.fromisoformat(GEN) - datetime.timedelta(days=7)).isoformat()
    return next((d for d in ds if d >= lo), ds[-1] if ds else None)
BASE_D = _base(); BASE = H.get(BASE_D, {})
def slugify(s): return re.sub('[^a-z0-9]+', '-', s.lower()).strip('-')
def N(name):
    m = [p for p in P if p['n'] == name]
    if len(m) != 1: raise KeyError(f'{name!r}: {len(m)} matches')
    return m[0]
def vl(p): return f'[{p["n"]}](/dynasty-value-{slugify(p["n"])}/)'          # markdown link to the player's value page (written root-relative)
def chg(p):
    b = BASE.get(p['id'])
    if not b or not p.get('v1'): return None
    return p['v1'] - b[0], round((p['v1'] - b[0]) / b[0] * 100, 1)
def chgs(p):
    c = chg(p); return '—' if not c else f'{c[0]:+,} ({c[1]:+.1f}%)'
def mk(p):
    m = [x for x in ((p.get('cs') or {}).get('sl'), (p.get('cs') or {}).get('ffc')) if x is not None]; return round(sum(m) / len(m)) if m else None
def gap(p): return round((mk(p) - p['cs']['dp']) / p['cs']['dp'] * 100)       # draft market vs experts, %
def ppg(p): return (p.get('ppg') or {}).get('ppr')
def l3(p): return (p.get('l3') or {}).get('ppr')
DEPTH = [1, 0.75, 0.55, 0.4, 0.3, 0.25]
def sv(vals): return int(sum(v * DEPTH[i] for i, v in enumerate(sorted(vals, reverse=True))) + 0.5)
def fair(a, b):
    """Same rule as the trade calculator: (side A total, side B total, gap %, within 5%)."""
    x, y = sv(a), sv(b); g = (x - y) / max(x, y, 1); return x, y, round(g * 1000) / 10, abs(g) <= 0.05
def ros_score(p):
    j = p.get('p3') or {}; a = j['ppr'] / j['n'] if j.get('n') else None; g = ppg(p)
    if a is None or g is None or p.get('inj') in ('Out', 'IR', 'PUP', 'Sus'): return None
    parts = [(0.4, a), (0.3, l3(p)), (0.3, g)]; w = sum(x for x, v in parts if v is not None)
    return round(sum(x * v for x, v in parts if v is not None) / w, 1)
def line(p):
    c = chg(p)
    return (f"{p['n']:22} {p['pos']}{PR.get(p['id'], '-')} #{ONE.get(p['id'], '-')} {p['team']} age{p['age']} exp{p['exp']} inj={p['inj']} gp={p['gp']} ppg={ppg(p)} l3={l3(p)} proj={(p.get('proj') or {}).get('ppr')}"
            f" v1={p.get('v1')} v2={p.get('v2')} cs={p.get('cs')} sp={p.get('sp')} sig={p.get('sig')} chg={c} t24={p.get('t24')} t72={p.get('t72')}")
if __name__ == '__main__':
    a = sys.argv[1:] or ['help']
    print(f'# data generated {D["generated"]}, week {WEEK}, baseline snapshot {BASE_D}, history days {sorted(H)}')
    if a[0] == 'sig':
        for s in ('buy', 'sell'):
            print('==', s)
            for p in [q for q in V if q['sig'] == s][:16]: print(line(p), f'gap={gap(p)}%')
    elif a[0] == 'rook':
        for p in [q for q in V if q['exp'] == 0][:25]: print(line(p))
    elif a[0] == 'movers':
        n = int(a[1]) if len(a) > 1 else 12
        mv = sorted([(chg(p)[0], p) for p in V if chg(p) and max(p['v1'], BASE[p['id']][0]) >= 1000], key=lambda t: t[0])
        print('== fallers'); [print(line(p)) for d, p in mv[:n]]
        print('== risers'); [print(line(p)) for d, p in mv[::-1][:n]]
    elif a[0] == 'waiver':
        for p in sorted([q for q in P if (q.get('t24') or 0) > 0], key=lambda q: -q['t24'])[:25]: print(line(p), f"p3={p.get('p3')}")
    elif a[0] == 'ros':
        pos = a[1] if len(a) > 1 else None
        for s, p in sorted([(ros_score(q), q) for q in P if ros_score(q) is not None and (not pos or q['pos'] == pos)], key=lambda t: -t[0])[:30]: print(s, line(p))
    elif a[0] == 'picks':
        for p in D['picks']: print(p['n'], p['v1'], p['v2'])
    elif a[0] == 'player':
        for n in a[1:]: print(line(N(n)))
    else: print(__doc__)
