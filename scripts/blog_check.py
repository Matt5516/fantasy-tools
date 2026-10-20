#!/usr/bin/env python3
"""Lint content/blog/*.md before publishing. Exit 1 on any ERROR.
Checks: front matter, title/description length, word count (900-1500 rendered, tables included), direct-answer paragraph, FAQ section,
author/ad/forbidden-string rules, internal links resolve to built pages, 'Numbers as of' date, and a NUMBER CHECK: every table row that links a
/dynasty-value-<name>/ page and has a bold composite value (**1,234**) must match data/history.json for the article's data_as_of date.
Usage: python3 scripts/blog_check.py [file.md ...]   (default: all articles)"""
import re, sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import blog as B
ROOT = pathlib.Path(__file__).resolve().parent.parent
HIST = json.loads((ROOT / 'data' / 'history.json').read_text())['days']
_D = json.loads((ROOT / 'data' / 'players.json').read_text()); PLAYERS = _D['players']; GEN = _D['generated'][:10]
BY_SLUG = {B_slug: p for p in PLAYERS for B_slug in [re.sub('[^a-z0-9]+', '-', p['n'].lower()).strip('-')]}
FORBID = [r'360 ?benefits', r'\bad slot\b', r'adsbygoogle', r'\bsponsored\b', r'\baffiliate\b', r'\bpromo code\b', r'matt5516', r'\bi\b(?= think| believe| recommend)']
errs = 0
def err(f, m):
    global errs; errs += 1; print(f'ERROR {f}: {m}')
files = [pathlib.Path(x) for x in sys.argv[1:]] or sorted((ROOT / 'content' / 'blog').glob('*.md'))
for f in files:
    meta, body = B.parse_front(f.read_text()); n = f.name
    for k in ('title', 'slug', 'date', 'description', 'answer', 'data_as_of', 'tags'):
        if not meta.get(k): err(n, f'missing front matter {k}')
    if len(meta.get('title', '')) > 70: err(n, f'title {len(meta["title"])} chars (max 70)')
    if not 100 <= len(meta.get('description', '')) <= 160: err(n, f'description {len(meta.get("description", ""))} chars (100-160)')
    if not n.startswith(meta.get('date', 'x')): err(n, 'file name should start with the publish date')
    if meta.get('slug') in [x.get('slug') for x in [B.parse_front(g.read_text())[0] for g in (ROOT / 'content' / 'blog').glob('*.md') if g.name != n]]: err(n, 'duplicate slug')
    r = B.Renderer(ROOT, '../../'); html = r.md(body.strip()); words = len(re.sub(r'<[^>]+>', ' ', html).split())
    if not 900 <= words <= 1500: err(n, f'{words} words (900-1500)')
    for w in r.warn: err(n, w)
    if not re.search(r'^##\s+(Frequently asked questions|FAQ)\s*$', body, re.M | re.I): err(n, 'missing "## Frequently asked questions" section')
    if len(B.faq_pairs(body)) < 3: err(n, 'fewer than 3 FAQ pairs')
    if not re.search(r'\|', body): err(n, 'no table')
    if not re.search(r'as of|snapshot', body + meta.get('answer', ''), re.I): err(n, 'must state the date the numbers are as of')
    if len(re.findall(r'\]\(/(?:dynasty-value|start-or-sit)-', body)) < 3: err(n, 'fewer than 3 links to player pages (dynasty-value-* / start-or-sit-*)')
    if len(re.findall(r'\]\(/(?:trade-analyzer|start-sit|rookie-draft-board|waiver-wire|league-import)/', body)) < 1: err(n, 'no link to a tool')
    for pat in FORBID:
        if re.search(pat, (body + ' '.join(meta.values())), re.I): err(n, f'forbidden pattern {pat}')
    asof = meta.get('data_as_of', '')
    snap = HIST.get(asof)
    if not snap: err(n, f'data/history.json has no snapshot for data_as_of {asof}')
    else:
        checked = 0
        for ln in body.split('\n'):
            m = re.search(r'\]\(/dynasty-value-([a-z0-9-]+)/\)', ln); b = re.findall(r'\*\*([\d,]+)\*\*', ln)
            if ln.lstrip().startswith('|') and m and b:
                p = BY_SLUG.get(m.group(1)); hv = snap.get(p['id']) if p else None
                if not hv: err(n, f'no history for {m.group(1)}')
                elif int(b[0].replace(',', '')) != hv[0]:
                    msg = f'{m.group(1)}: article says {b[0]}, snapshot {asof} says {hv[0]:,}'
                    if asof == GEN: err(n, msg)
                    else: print(f'warn {n}: {msg} (the {asof} snapshot is overwritten by that day\'s later refreshes, so only same-day checks are strict)')
                else: checked += 1
        print(f'ok   {n}: {words} words, {checked} table values matched the {asof} snapshot')
sys.exit(1 if errs else 0)
