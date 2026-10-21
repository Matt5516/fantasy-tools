#!/usr/bin/env python3
"""Generate DynastyMath data pages (weekly start/sit, dynasty rankings, pick values, player value pages,
injury report, trending adds), the guides hub and sitemap.xml from data/players.json.
Uses scripts/shell.json (page template written by the main build). Runs daily in GitHub Actions after refresh-data.mjs."""
import json, html, pathlib, re, datetime, shutil, math, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import blog as BLOG
E = html.escape
ROOT = pathlib.Path(__file__).resolve().parent.parent
S = json.loads((ROOT / 'scripts' / 'shell.json').read_text())
D = json.loads((ROOT / 'data' / 'players.json').read_text())
URL = S['url']; NAME = S['name']
gen = D.get('generated', '')[:10] or S['updated']
try: genh = datetime.date.fromisoformat(gen).strftime('%B %-d, %Y')
except Exception: genh = gen
WEEK, SEASON = D.get('week'), D.get('season')
POSC = {'QB': '#be123c', 'RB': '#047857', 'WR': '#1d4ed8', 'TE': '#b45309', 'PICK': '#6d28d9'}
def slugify(s): return re.sub('[^a-z0-9]+', '-', s.lower()).strip('-')
def tag(pos): return f'<span class="pos-tag" style="background:{POSC.get(pos,"#475569")}">{pos}</span>'
players = [p for p in D['players']]
valued = sorted([p for p in players if p.get('v1')], key=lambda p: -p['v1'])
pr = {}
for pos in ['QB', 'RB', 'WR', 'TE']:
    for i, p in enumerate([q for q in valued if q['pos'] == pos]): pr[p['id']] = i + 1
sf_sorted = sorted(valued, key=lambda p: -(p.get('v2') or p['v1']))
sf_rank = {p['id']: i + 1 for i, p in enumerate(sf_sorted)}; one_rank = {p['id']: i + 1 for i, p in enumerate(valued)}
# ---- daily value history (data/history.json: {"days": {date: {player id: [1QB, SF]}}}); one snapshot appended per build day ----
HIST_F = ROOT / 'data' / 'history.json'
try: HIST = json.loads(HIST_F.read_text()).get('days', {}) if HIST_F.exists() else {}
except Exception: HIST = {}
_snap = {p['id']: [p['v1'], p.get('v2') or p['v1']] for p in players if p.get('v1') and p.get('cs')}
if _snap and re.fullmatch(r'\d{4}-\d{2}-\d{2}', gen):
    HIST[gen] = _snap
    HIST = {d: HIST[d] for d in sorted(HIST)[-400:]}
    HIST_F.write_text(json.dumps({'days': HIST}, separators=(',', ':')))
def hist_base():
    """Oldest snapshot within the last 7 days (else the newest older one): the baseline for 'change since' columns."""
    ds = sorted(d for d in HIST if d < gen)
    if not ds: return None
    lo = (datetime.date.fromisoformat(gen) - datetime.timedelta(days=7)).isoformat()
    return next((d for d in ds if d >= lo), ds[-1])
BASE_D = hist_base() if re.fullmatch(r'\d{4}-\d{2}-\d{2}', gen) else None
def fmt_d(d): return datetime.date.fromisoformat(d).strftime('%b %-d')
def vchg(p):
    """(delta, pct) of the 1QB composite value since the baseline snapshot, or None."""
    b = (HIST.get(BASE_D) or {}).get(p['id']) if BASE_D else None
    if not b or not p.get('v1'): return None
    return p['v1'] - b[0], round((p['v1'] - b[0]) / b[0] * 100, 1)
PAGES = []
TOOLS = S.get('tools', []); LM = S.get('linkmap', {})
LINK_RE = re.compile(r'href="((?:\.\./)*|\./)?(\?[^"#]*)?#(tool|cobra|market|trade|league|rankings)"')
def fix_links(t):  # old one-page anchors -> tool pages (same mapping as _build/build.py)
    return LINK_RE.sub(lambda m: f'href="{m.group(1) or ""}{LM[m.group(3)]}/{m.group(2) or ""}"' if m.group(3) in LM and (m.group(1) or m.group(2)) else m.group(0), t)

def write(slug, section, nav, title, desc, h1, lede, answer, body, cta=('Open the trade calculator', ''), cta_text='Check any trade with players and picks.', ld_extra=None, featured=False, changefreq='daily'):
    url = URL + slug + '/'
    crumbs = [{"@type": "ListItem", "position": 1, "name": NAME, "item": URL}, {"@type": "ListItem", "position": 2, "name": "Guides", "item": URL + "guides/"}, {"@type": "ListItem", "position": 3, "name": nav, "item": url}]
    g = [{"@type": "Article", "headline": re.sub('<[^>]+>', '', h1)[:110], "description": desc, "url": url, "mainEntityOfPage": url, "dateModified": gen, "datePublished": S['updated'],
          "author": S['org'], "publisher": S['org'], "image": URL + 'og.png', "inLanguage": "en-US"}, {"@type": "BreadcrumbList", "itemListElement": crumbs}] + (ld_extra or [])
    ld = json.dumps({"@context": "https://schema.org", "@graph": g}, ensure_ascii=False).replace('</', '<\\/')
    t = S['template']
    for k, v in [('__LD__', ld), ('__TITLE__', E(title)), ('__DESC__', E(desc)), ('__H1__', h1), ('__LEDE__', lede), ('__ANSWER__', answer), ('__BODY__', body),
                 ('__SECTION__', E(section)), ('__NAV__', E(nav)), ('__UPDH__', genh), ('__UPD__', gen), ('__CTAL__', E(cta[0])), ('__CTAQ__', cta[1]), ('__CTAA__', 'tool' if re.search(r'start|sit', cta[0], re.I) else 'trade'), ('__CTAT__', E(cta_text)), ('__SLUG__', slug)]:
        t = t.replace(k, v)
    d = ROOT / slug; d.mkdir(exist_ok=True); (d / 'index.html').write_text(fix_links(t)); (d / '.generated').write_text('')
    PAGES.append(dict(slug=slug, section=section, nav=nav, desc=desc, featured=featured, changefreq=changefreq))

def table(rows, sf=False, n=None, show_val=True):
    out = '<div class="table-scroll"><table><thead><tr><th scope="col">#</th><th scope="col">Player</th><th scope="col">Pos rank</th><th scope="col">Age</th><th scope="col">PPR PPG</th><th scope="col">' + ('Superflex value' if sf else '1QB value') + '</th></tr></thead><tbody>'
    for i, p in enumerate(rows[:n] if n else rows):
        v = (p.get('v2') or p['v1']) if sf else p['v1']
        link = f'<a href="../dynasty-value-{slugify(p["n"])}/">{E(p["n"])}</a>' if p['id'] in PLAYER_PAGES else E(p['n'])
        out += f'<tr><td>{i+1}</td><td>{tag(p["pos"])} {link} <span class="hint" style="display:inline">{p.get("team") or "FA"}</span></td><td>{p["pos"]}{pr.get(p["id"],"")}</td><td>{p.get("age") or "—"}</td><td>{(p.get("ppg") or {}).get("ppr","—")}</td><td><b>{v:,}</b></td></tr>'
    return out + '</tbody></table></div>'

def itemlist(rows, name):
    return {"@type": "ItemList", "name": name, "itemListOrder": "https://schema.org/ItemListOrderDescending", "numberOfItems": len(rows),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": p['n']} for i, p in enumerate(rows)]}

SRCS = D.get('sources') or {}
SRCN = {'dp': ('DynastyProcess', 'https://github.com/dynastyprocess/data'), 'sl': ('Sleeper', 'https://sleeper.com'), 'ffc': ('Fantasy Football Calculator', 'https://fantasyfootballcalculator.com'), 'prod': ('nflverse', 'https://github.com/nflverse/nflverse-data')}
used = [k for k in ('dp', 'sl', 'ffc', 'prod') if (SRCS.get(k) or {}).get('ok')]
SRC = (f'<p class="hint">Composite values from ' + ', '.join(f'<a href="{SRCN[k][1]}" rel="noopener">{SRCN[k][0]}</a> ({round(SRCS[k]["weight"]*100)}%)' for k in used)
       + (' (weights re-normalised over the sources available today)' if len(used) < 4 else '') + f'; expert values from DynastyProcess open data (GPL-3.0); nflverse data CC BY 4.0, changed by us into per-game production ranks. Projections: Sleeper public API. Updated {genh}. <a href="../how-our-values-work/">How the composite works</a>. Values are a starting point, not a guarantee.</p>')
CON = {'strong': ('good', 'Sources agree'), 'mixed': ('', 'Some disagreement'), 'split': ('warn', 'Sources disagree'), 'single': ('', 'One source')}
def con_badge(p):
    c = CON.get(p.get('con') or 'single'); sig = p.get('sig')
    return f'<span class="badge {c[0]}">{c[1]}</span>' + (f' <span class="badge {"good" if sig=="buy" else "warn"}">{"Buy: market below experts" if sig=="buy" else "Sell: market above experts"}</span>' if sig else '')
def breakdown(p):
    cs = p.get('cs') or {}
    rows = ''.join(f'<tr><td style="text-align:left">{SRCN[k][0]}{" ADP" if k in ("sl","ffc") else " experts" if k=="dp" else " production"}</td><td>{round((SRCS.get(k) or {}).get("weight",0)*100)}%</td><td>{cs[k]:,}</td></tr>' for k in ('dp', 'sl', 'ffc', 'prod') if k in cs)
    return (f'<h2>Value by source</h2><p>{con_badge(p)} Spread between sources: {p["sp"]}%.</p>' if p.get('sp') is not None else '<h2>Value by source</h2>') + f'<div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Source</th><th scope="col">Weight</th><th scope="col">1QB value</th></tr></thead><tbody>{rows}<tr><th scope="row" style="text-align:left">Composite</th><td></td><td><strong>{p["v1"]:,}</strong></td></tr></tbody></table></div><p class="hint">A big spread means experts, drafters and production disagree. When the draft market values a player well below the experts, that is a possible buy; well above, a possible sell.</p>'
N_VALUE_PAGES = 200  # below ~#200 values fall under ~230 and the pages get thin
PLAYER_PAGES = {p['id'] for p in valued[:N_VALUE_PAGES]}
def vslug(p): return f'dynasty-value-{slugify(p["n"])}'
def fmtn(v): return '—' if v is None else (f'{v:,}' if isinstance(v, int) else str(v))
def ppg_of(p, f='ppr'): return (p.get('ppg') or {}).get(f)
def jround(x): return int(math.floor(x + 0.5))  # JS Math.round
# ---- mirror of assets/calc.js (sideValue / trade / balance) so comparison pages agree with the trade calculator ----
DEPTH = [1, 0.75, 0.55, 0.4, 0.3, 0.25]
def side_value(vals): return jround(sum(v * (DEPTH[i] if i < len(DEPTH) else 0.2) for i, v in enumerate(sorted(vals, reverse=True))))
def trade_calc(av, bv):
    a, b = side_value(av), side_value(bv); gap = (a - b) / max(a, b, 1)
    return dict(a=a, b=b, gap=gap, pct=jround(gap * 1000) / 10, fair=abs(gap) <= 0.05)
def balance_adds(low_vals, target_vals, pool, key, exclude):
    a, b = side_value(low_vals), side_value(target_vals); target = max(a, b); out = []
    for q in pool:
        if q['id'] in exclude: continue
        nv = side_value(low_vals + [q.get(key) or q['v1']])
        if target * 0.95 <= nv <= target * 1.08: out.append((abs(nv - target), q['id'], q))
    return [x[2] for x in sorted(out, key=lambda x: (x[0], x[1]))[:3]]
def faq_ld(qas):
    return {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qas]}
def faq_html(qas, title='Frequently asked questions'):
    return f'<h2>{title}</h2>' + ''.join(f'<h3>{E(q)}</h3><p>{E(a)}</p>' for q, a in qas)
def fit(opts, lo, hi):
    for o in opts:
        if lo <= len(o) <= hi: return o
    return opts[-1][:hi]

# ---- weekly start/sit structures (needed for cross-links) ----
def ssrows(pos_list, n):
    return sorted([p for p in players if p.get('proj') and p['pos'] in pos_list and not (p.get('inj') in ('Out', 'IR', 'PUP', 'Sus'))], key=lambda p: -p['proj']['ppr'])[:n]
def ss_tier(i, n): return 'Must start' if i < (n // 5) else ('Start' if i < (n * 2 // 5) else ('Flex / matchup' if i < (n * 3 // 5) else 'Sit (deep leagues only)'))
SSN = {'QB': 32, 'RB': 50, 'WR': 60, 'TE': 30}      # list length of the start-sit-<pos> pages (tier rule uses this n)
SSLIM = {'QB': 36, 'RB': 60, 'WR': 72, 'TE': 30}    # players who get their own start-or-sit page
SS = {}; SSPOS = set()
if WEEK:
    for pos in SSN:
        if ssrows([pos], 1): SSPOS.add(pos)
        allr = ssrows([pos], 10 ** 6)
        for i, q in enumerate(allr[:SSLIM[pos]]):
            SS[q['id']] = dict(rank=i + 1, of=len(allr), tier=ss_tier(i, SSN[pos]), slug='start-or-sit-' + slugify(q['n']), p=q)
def ss_link(p, pre='../'):
    return f'<a href="{pre}{SS[p["id"]]["slug"]}/">{E(p["n"])}</a>' if p['id'] in SS else E(p['n'])
# ---- comparison pairs: each top-60 player vs the next two at his position (higher value first, each pair once) ----
CMPS = []; _seen = set()
_bypos = {pos: [q for q in valued if q['pos'] == pos] for pos in ('QB', 'RB', 'WR', 'TE')}
for a in valued[:60]:
    lst = _bypos.get(a['pos'], []); i = lst.index(a)
    for b in lst[i + 1:i + 3]:
        key = frozenset((a['id'], b['id']))
        if key in _seen or a['id'] not in PLAYER_PAGES or b['id'] not in PLAYER_PAGES: continue
        _seen.add(key); CMPS.append((a, b))
def cslug(a, b): return f'{slugify(a["n"])}-vs-{slugify(b["n"])}-dynasty'
CMP_BY = {}
for a, b in CMPS:
    CMP_BY.setdefault(a['id'], []).append((cslug(a, b), b)); CMP_BY.setdefault(b['id'], []).append((cslug(a, b), a))

# ---- dynasty rankings ----
write('dynasty-rankings', 'Dynasty rankings', f'Dynasty rankings {SEASON}', f'Dynasty Rankings {SEASON} (1QB): Top 150 Trade Values, Updated Daily',
      f'Top 150 dynasty fantasy football rankings for 1QB leagues with trade values, ages and points per game. Updated {genh}.',
      f'Dynasty rankings {SEASON} (1QB)', 'The 150 most valuable dynasty players for single-QB leagues, with fresh values every day.',
      f'The top dynasty asset in 1QB leagues is <strong>{E(valued[0]["n"])}</strong> ({valued[0]["pos"]}, {valued[0].get("team") or "FA"}), followed by {E(valued[1]["n"])} and {E(valued[2]["n"])}. Values as of {genh}.',
      table(valued, n=150) + SRC + '<p>Trade targets: <a href="../dynasty-buy-low-sell-high/">buy-low/sell-high</a> · <a href="../dynasty-value-risers-fallers/">risers and fallers</a> · <a href="../dynasty-rookie-rankings/">rookie rankings</a>. Superflex league? See <a href="../dynasty-rankings-superflex/">superflex rankings</a>. By position: <a href="../dynasty-qb-rankings/">QB</a> · <a href="../dynasty-rb-rankings/">RB</a> · <a href="../dynasty-wr-rankings/">WR</a> · <a href="../dynasty-te-rankings/">TE</a>.</p>',
      ld_extra=[itemlist(valued[:150], 'Dynasty rankings 1QB')], featured=True)
write('dynasty-rankings-superflex', 'Dynasty rankings', f'Superflex rankings {SEASON}', f'Superflex Dynasty Rankings {SEASON}: Top 150 SF Values',
      f'Top 150 superflex dynasty rankings with SF trade values, ages and PPG, updated {genh}. Quarterbacks move way up in 2QB formats.',
      f'Superflex dynasty rankings {SEASON}', 'The top 150 by superflex (2QB) dynasty value, fresh every day.',
      f'In superflex, <strong>{E(sf_sorted[0]["n"])}</strong> is the top dynasty asset, and {sum(1 for p in sf_sorted[:24] if p["pos"]=="QB")} of the top 24 are quarterbacks, versus {sum(1 for p in valued[:24] if p["pos"]=="QB")} in 1QB.',
      table(sf_sorted, sf=True, n=150) + SRC + '<p>Set the trade calculator to superflex: <a href="../?sf=1#trade">open SF trade calculator</a>.</p>', cta=('Superflex trade calculator', '?sf=1'),
      ld_extra=[itemlist(sf_sorted[:150], 'Dynasty rankings superflex')], featured=True)
for pos, full in [('QB', 'quarterback'), ('RB', 'running back'), ('WR', 'wide receiver'), ('TE', 'tight end')]:
    rows = [p for p in valued if p['pos'] == pos]
    avg_age = round(sum(p.get('age') or 0 for p in rows[:12]) / 12, 1)
    write(f'dynasty-{pos.lower()}-rankings', 'Dynasty rankings', f'Dynasty {pos} rankings', f'Dynasty {pos} Rankings {SEASON}: Top {min(60,len(rows))} {full.title()}s by Trade Value',
          f'Dynasty {full} rankings for {SEASON} with 1QB and superflex values, ages and PPG. Updated {genh}.',
          f'Dynasty {pos} rankings {SEASON}', f'Every {full} ranked by open dynasty value.',
          f'The top dynasty {full} is <strong>{E(rows[0]["n"])}</strong> ({rows[0].get("team") or "FA"}, age {rows[0].get("age") or "—"}). The top 12 {pos}s average {avg_age} years old.',
          table(rows, n=60) + SRC + ('<p>TE premium league? The <a href="../?tep=1#trade">trade calculator</a> adds 15% to tight ends.</p>' if pos == 'TE' else ''),
          ld_extra=[itemlist(rows[:60], f'Dynasty {pos} rankings')])
picks = sorted(D.get('picks', []), key=lambda p: -p['v1'])
yrs = sorted({p['n'][:4] for p in picks}); PY = (yrs[0] + '–' + yrs[-1]) if yrs else ''
eq = []
for pk in picks:
    near = min(valued, key=lambda p: abs(p['v1'] - pk['v1']))
    eq.append((pk, near))
write('rookie-draft-pick-values', 'Dynasty rankings', 'Rookie pick values', f'Dynasty Rookie Pick Values {PY}: 1sts, 2nds & Comps',
      f'What dynasty rookie draft picks are worth in trades, in 1QB and superflex, with a comparable player for each pick. Updated {genh}.',
      'Dynasty rookie draft pick values', 'Picks valued on the same scale as players, so you know what a pick buys.',
      (f'A {E(picks[0]["n"])} is worth about {picks[0]["v1"]:,} in 1QB ({(picks[0].get("v2") or picks[0]["v1"]):,} superflex), similar to {E(eq[0][1]["n"])}.' if picks else 'Pick values are on the way.'),
      '<div class="table-scroll"><table><thead><tr><th scope="col">Pick</th><th scope="col">1QB value</th><th scope="col">SF value</th><th scope="col">Similar player (1QB)</th></tr></thead><tbody>' + ''.join(f'<tr><td>{tag("PICK")} {E(pk["n"])}</td><td>{pk["v1"]:,}</td><td>{(pk.get("v2") or pk["v1"]):,}</td><td>{E(n["n"])} ({n["pos"]})</td></tr>' for pk, n in eq) + '</tbody></table></div>' + SRC + '<p>Add picks to either side in the <a href="../#trade">trade calculator</a>. Current rookies and what they are worth: <a href="../dynasty-rookie-rankings/">dynasty rookie rankings</a>.</p>', featured=True)
chart_rows = valued[:60]
write('dynasty-trade-value-chart', 'Dynasty rankings', 'Trade value chart', f'Dynasty Trade Value Chart {SEASON} (Updated Daily): 1QB & Superflex',
      f'Dynasty fantasy football trade value chart with 1QB and superflex values for the top players and picks, updated {genh}.',
      f'Dynasty trade value chart {SEASON}', 'Players and picks on one scale. Add up each side to see who wins, or let the calculator do it and discount the 2-for-1s.',
      f'Use the chart by adding up the values on each side of a trade. Within about 5% is a fair trade. Packages of several smaller pieces are worth less than the sum, so the <a href="../#trade">calculator</a> discounts extra pieces.',
      '<div class="table-scroll"><table><thead><tr><th scope="col">Player / pick</th><th scope="col">1QB</th><th scope="col">SF</th></tr></thead><tbody>' + ''.join(f'<tr><td>{tag(p["pos"])} {E(p["n"])}</td><td>{p["v1"]:,}</td><td>{(p.get("v2") or p["v1"]):,}</td></tr>' for p in sorted(chart_rows + picks[:12], key=lambda p: -p['v1'])) + '</tbody></table></div>' + SRC, featured=True)
# ---- weekly start/sit ----
if WEEK:
    for key, pos_list, n, lab in [('qb', ['QB'], 32, 'QB'), ('rb', ['RB'], 50, 'RB'), ('wr', ['WR'], 60, 'WR'), ('te', ['TE'], 30, 'TE'), ('flex', ['RB', 'WR', 'TE'], 100, 'Flex')]:
        rows = ssrows(pos_list, n)
        if not rows: continue
        tiers = lambda i: ss_tier(i, n)
        body = '<div class="table-scroll"><table><thead><tr><th scope="col">#</th><th scope="col">Player</th><th scope="col">Proj (PPR)</th><th scope="col">Half</th><th scope="col">PPG</th><th scope="col">Status</th><th scope="col">Call</th></tr></thead><tbody>' + ''.join(
            f'<tr><td>{i+1}</td><td>{tag(p["pos"])} {ss_link(p)} <span class="hint" style="display:inline">{p.get("team") or ""}</span></td><td><b>{p["proj"]["ppr"]}</b></td><td>{p["proj"].get("half","—")}</td><td>{(p.get("ppg") or {}).get("ppr","—")}</td><td>{E(p.get("inj") or "Active")}</td><td>{tiers(i)}</td></tr>' for i, p in enumerate(rows)) + '</tbody></table></div>'
        write(f'start-sit-{key}', 'Weekly start/sit', f'Week {WEEK} {lab} start/sit', f'Week {WEEK} {lab} Start/Sit Rankings ({SEASON}): Who to Start at {lab}',
              f'Week {WEEK} fantasy football {lab} rankings with PPR projections, injury status and start/sit calls. Updated {genh}.',
              f'Week {WEEK} {lab} start/sit rankings', f'Every {lab} ranked by Week {WEEK} PPR projection, with injury status and a plain start/sit call.',
              f'Top Week {WEEK} {lab} plays: <strong>{E(rows[0]["n"])}</strong> ({rows[0]["proj"]["ppr"]} projected PPR), {E(rows[1]["n"])} and {E(rows[2]["n"])}. Players ruled out are excluded.',
              body + f'<p class="hint">Projections from Sleeper’s public API, updated {genh}. Injury statuses change late in the week; check before kickoff.</p><p>Deciding between two players? Use the <a href="../#tool">start/sit tool</a>. Season-long view: <a href="../' + ('rest-of-season-rankings' if key == 'flex' else f'rest-of-season-{key}-rankings') + '/">rest of season rankings</a>. Other positions: ' + ' · '.join(f'<a href="../start-sit-{k}/">{l}</a>' for k, l in [('qb', 'QB'), ('rb', 'RB'), ('wr', 'WR'), ('te', 'TE'), ('flex', 'Flex')] if k != key) + '</p>',
              cta=('Compare two players', ''), cta_text='Who should I start? Compare up to 4 players.', featured=key in ('flex', 'rb'), ld_extra=[itemlist(rows, f'Week {WEEK} {lab} rankings')])
# ---- weekly cheat sheet (targets "week N start sit" searches); older week URLs redirect here ----
OLDWEEKS = []
if WEEK:
    secs = ''
    for key, pos_list, n, lab in [('qb', ['QB'], 12, 'QB'), ('rb', ['RB'], 24, 'RB'), ('wr', ['WR'], 30, 'WR'), ('te', ['TE'], 12, 'TE')]:
        rows = ssrows(pos_list, n)
        if not rows: continue
        q = len(rows) // 3
        secs += f'<h2>Week {WEEK} {lab}: start, flex, sit</h2><div class="table-scroll"><table><thead><tr><th scope="col">Must start</th><th scope="col">Start / flex</th><th scope="col">Sit in shallow leagues</th></tr></thead><tbody><tr>' + ''.join('<td>' + '<br>'.join(f'{E(p["n"])} <span class="hint" style="display:inline">{p["proj"]["ppr"]}</span>' for p in grp) + '</td>' for grp in (rows[:q], rows[q:2*q], rows[2*q:])) + f'</tr></tbody></table></div><p><a href="../start-sit-{key}/">Full Week {WEEK} {lab} rankings</a></p>'
    top = ssrows(['QB', 'RB', 'WR', 'TE'], 3)
    if top:
        write(f'week-{WEEK}-start-sit', 'Weekly start/sit', f'Week {WEEK} start/sit cheat sheet', f'Week {WEEK} Start/Sit Cheat Sheet ({SEASON}): Who to Start in Fantasy',
              f'Week {WEEK} fantasy football start/sit cheat sheet for QB, RB, WR and TE: must-starts, flex plays and sits from PPR projections. Updated {genh}.',
              f'Week {WEEK} start/sit cheat sheet', f'Every position on one page, sorted by Week {WEEK} PPR projection. Numbers are projected PPR points.',
              f'Highest Week {WEEK} projections: <strong>{E(top[0]["n"])}</strong> ({top[0]["proj"]["ppr"]}), {E(top[1]["n"])} and {E(top[2]["n"])}. Players ruled out are left off.',
              secs + f'<p class="hint">Projections from Sleeper’s public API, updated {genh}. Check injury news before kickoff (<a href="../injury-report/">injury report</a>). Stuck between two guys? <a href="../start-sit/">Compare them in the start/sit tool</a>.</p>',
              cta=('Compare two players', ''), cta_text='Who should I start? Compare up to 4 players.', featured=True)
        for w in range(1, WEEK):
            d = ROOT / f'week-{w}-start-sit'; d.mkdir(exist_ok=True); OLDWEEKS.append(d.name)
            (d / 'index.html').write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Week {w} start/sit has moved to Week {WEEK}</title><meta name="robots" content="noindex,follow"><link rel="canonical" href="{URL}week-{WEEK}-start-sit/"><meta http-equiv="refresh" content="0; url=../week-{WEEK}-start-sit/"></head><body><p><a href="../week-{WEEK}-start-sit/">Week {WEEK} start/sit cheat sheet</a></p></body></html>')
            (d / '.generated').write_text('')
inj = [p for p in players if p.get('inj') and p.get('v1')]
inj.sort(key=lambda p: -p['v1'])
if inj:
    write('injury-report', 'Weekly start/sit', f'Week {WEEK} injury report', f'Fantasy Football Injury Report Week {WEEK} ({SEASON})',
          f'Week {WEEK} fantasy football injury report: current status for fantasy-relevant players, sorted by dynasty value. Updated {genh}.',
          f'Week {WEEK} fantasy injury report', 'Who is hurt, most valuable players first.',
          f'{len(inj)} fantasy-relevant players carry an injury designation as of {genh}, including {", ".join(E(p["n"])+" ("+E(p["inj"])+")" for p in inj[:3])}.',
          '<div class="table-scroll"><table><thead><tr><th scope="col">Player</th><th scope="col">Team</th><th scope="col">Status</th><th scope="col">PPR PPG</th></tr></thead><tbody>' + ''.join(f'<tr><td>{tag(p["pos"])} {E(p["n"])}</td><td>{p.get("team") or "FA"}</td><td>{E(p["inj"])}</td><td>{(p.get("ppg") or {}).get("ppr","—")}</td></tr>' for p in inj[:80]) + '</tbody></table></div><p class="hint">Source: Sleeper. Statuses change fast, so check before kickoff.</p>',
          cta=('Check a start/sit', ''))
def adds24(p): return p.get('t24') or p.get('trend') or 0  # t24 = Sleeper trending adds, 24h lookback
tr = sorted([p for p in players if adds24(p) > 0], key=lambda p: -adds24(p))[:40]
if tr:
    write('waiver-wire-trending', 'Weekly start/sit', 'Trending waiver adds', f'Week {WEEK} Waiver Wire: Most Added Players in Fantasy Football ({SEASON})',
          f'The most-added players on Sleeper over the last 24 hours, with position, team and PPG. Updated {genh}.',
          f'Week {WEEK} waiver wire: trending adds', 'Who fantasy managers are adding right now, from Sleeper’s trending data.',
          f'The most-added player is <strong>{E(tr[0]["n"])}</strong> ({tr[0]["pos"]}, {tr[0].get("team") or "FA"}), added in {adds24(tr[0]):,} Sleeper leagues in the last 24 hours.',
          '<div class="table-scroll"><table><thead><tr><th scope="col">#</th><th scope="col">Player</th><th scope="col">Adds (24h)</th><th scope="col">PPR PPG</th></tr></thead><tbody>' + ''.join(f'<tr><td>{i+1}</td><td>{tag(p["pos"])} {E(p["n"])} <span class="hint" style="display:inline">{p.get("team") or "FA"}</span></td><td>{adds24(p):,}</td><td>{(p.get("ppg") or {}).get("ppr","—")}</td></tr>' for i, p in enumerate(tr)) + '</tbody></table></div>' + f'<p>Looking for pickups grouped by position with Week {WEEK} projections? See the <a href="../week-{WEEK}-waiver-wire/">Week {WEEK} waiver wire</a>.</p>')

# ---- weekly waiver wire (targets "week N waiver wire"; built only from Sleeper trending adds + Sleeper projections + our values) ----
FIRST_WAIVER_WEEK = 7   # first week this page family was published; older weeks redirect to the current one
WAIVER_SLUG = f'week-{WEEK}-waiver-wire' if WEEK else None
WV = []
if WEEK:
    WPOS = [('QB', 'Quarterbacks', 8), ('RB', 'Running backs', 14), ('WR', 'Wide receivers', 14), ('TE', 'Tight ends', 10)]
    allproj = {pos: ssrows([pos], 10 ** 6) for pos, _, _ in WPOS}
    def w_rank(p):
        lst = allproj[p['pos']]
        for i, q in enumerate(lst):
            if q['id'] == p['id']: return i + 1, len(lst)
        return None, len(lst)
    def pace(p):
        t24, t72 = p.get('t24'), p.get('t72')
        if not t24 or not t72: return None
        r = t24 / (t72 / 3)   # today's adds vs the average day of the last three
        return ('Rising', r) if r >= 1.25 else (('Cooling', r) if r <= 0.75 else ('Steady', r))
    def w_note(p):
        bits = []; pj = p.get('proj'); rk, of = w_rank(p)
        if pj and rk and not p.get('inj') in ('Out', 'IR', 'PUP', 'Sus'): bits.append(f'Projected {pj["ppr"]} PPR in Week {WEEK}, {p["pos"]}{rk} of {of} projected {p["pos"]}s')
        elif p.get('inj') in ('Out', 'IR', 'PUP', 'Sus'): bits.append(f'Listed {p["inj"]}, so no Week {WEEK} start call')
        else: bits.append(f'No Week {WEEK} projection on Sleeper (bye, inactive or no role yet)')
        if p.get('inj') and p['inj'] not in ('Out', 'IR', 'PUP', 'Sus'): bits.append(f'status {p["inj"]}')
        g, l3, l3g = ppg_of(p), (p.get('l3') or {}).get('ppr'), (p.get('l3') or {}).get('g', 3)
        if g is not None and p.get('gp'): bits.append(f'{g} PPR/game over {p["gp"]} game' + ('' if p['gp'] == 1 else 's') + (f', {l3} over the last {l3g}' if l3 is not None and l3g > 1 else ''))
        elif p.get('exp') == 0: bits.append('rookie with no games on the board yet')
        if (p.get('v1') or 0) >= 100: bits.append(f'dynasty value {p["v1"]:,} ({p["pos"]}{pr[p["id"]]})' if p['id'] in pr else f'dynasty value {p["v1"]:,}')
        return '; '.join(bits) + '.'
    wsec = ''; wtop = {}
    for pos, lab, n in WPOS:
        rows = sorted([p for p in players if p['pos'] == pos and (p.get('t24') or 0) > 0], key=lambda p: -p['t24'])[:n]
        if not rows: continue
        wtop[pos] = rows; WV.extend(rows)
        def wname(p):
            if p['id'] in SS: return f'<a href="../{SS[p["id"]]["slug"]}/">{E(p["n"])}</a>'
            if p['id'] in PLAYER_PAGES: return f'<a href="../{vslug(p)}/">{E(p["n"])}</a>'
            return E(p['n'])
        def wrow(p):
            pc = pace(p); pj = p.get('proj'); p3 = p.get('p3') or {}
            t72s = '{:,} · {}'.format(p['t72'], pc[0]) if pc else '—'
            return (f'<tr><td style="text-align:left">{wname(p)} <span class="hint" style="display:inline">{E(p.get("team") or "FA")}</span></td><td>{p["t24"]:,}</td>'
                    f'<td>{t72s}</td><td><b>{pj["ppr"] if pj else "—"}</b></td><td>{p3["ppr"] if p3.get("n") else "—"}</td><td style="text-align:left">{E(w_note(p))}</td></tr>')
        wsec += (f'<h2>Week {WEEK} waiver wire: {lab.lower()}</h2><div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Player</th><th scope="col">Adds (24h)</th><th scope="col">Adds (72h) · pace</th><th scope="col">Wk {WEEK} proj (PPR)</th><th scope="col">Next 3 wks (PPR)</th><th scope="col" style="text-align:left">What the data says</th></tr></thead><tbody>'
                 + ''.join(wrow(p) for p in rows) + '</tbody></table></div>')
    wall = sorted(WV, key=lambda p: -p['t24'])
    if wall:
        t3 = wall[:3]
        def best(pos): return wtop[pos][0] if pos in wtop else None
        ans = (f'The most-added fantasy players heading into Week {WEEK} are <strong>{E(t3[0]["n"])}</strong> ({t3[0]["pos"]}, {E(t3[0].get("team") or "FA")}; {t3[0]["t24"]:,} adds in 24 hours), '
               f'{E(t3[1]["n"])} ({t3[1]["pos"]}) and {E(t3[2]["n"])} ({t3[2]["pos"]}). Counts are Sleeper leagues that added the player in the last 24 hours, as of {genh}.')
        faqs = [(f'Who is the most added player on the Week {WEEK} waiver wire?', f'{t3[0]["n"]} ({t3[0]["pos"]}, {t3[0].get("team") or "FA"}) leads Sleeper trending adds with {t3[0]["t24"]:,} adds in the last 24 hours as of {genh}.')]
        for pos, lab, _ in WPOS:
            b = best(pos)
            if b: faqs.append((f'Who is the top trending {pos} on the Week {WEEK} waiver wire?', f'By Sleeper adds in the last 24 hours, {b["n"]} ({b.get("team") or "FA"}) is the top trending {pos} with {b["t24"]:,} adds' + (f' and a Week {WEEK} projection of {b["proj"]["ppr"]} PPR points.' if b.get('proj') else f'; Sleeper has no Week {WEEK} projection for him.')))
        faqs.append((f'Where do the Week {WEEK} waiver wire numbers come from?', 'Add counts are Sleeper’s public trending-adds data (24-hour and 72-hour windows) and projections are Sleeper’s public weekly projections. This isn’t an injury report or a beat-writer take, so check the news before you spend a claim or FAAB.'))
        faqs.append(('When do waiver claims run?', 'Waiver timing is a league setting (many Sleeper leagues process claims early Wednesday morning). Check your league’s waiver settings for the exact day and time and whether it uses FAAB or priority.'))
        body = (f'<p>Trending adds show where the crowd is moving, not who is free in <em>your</em> league or who will produce. The pace column compares the last 24 hours of adds with the average day of the last 72 hours: <strong>Rising</strong> means today’s adds are at least 25% above that average, <strong>Cooling</strong> at least 25% below. '
                f'“Next 3 wks” adds Sleeper’s projections for Weeks {WEEK} to {WEEK + 2}; bye weeks and weeks without a projection count as nothing, so a short total can just mean a bye. Quarterbacks, running backs, wide receivers and tight ends only (no kickers or defenses).</p>'
                + wsec +
                f'<h2>How to use this list</h2><ul><li>Filter to players actually available in your league, then compare them with your bench in the <a href="../start-sit/">start/sit tool</a>.</li>'
                f'<li>A high add count with no Week {WEEK} projection often means a stash or a handcuff, not a starter. Check the <a href="../injury-report/">injury report</a> first.</li>'
                f'<li>Thinking long term? Dynasty value is shown where there is one; the <a href="../trade-analyzer/">trade analyzer</a> prices players and picks together.</li>'
                f'<li>Playing for the whole season? See the <a href="../rest-of-season-rankings/">rest of season rankings</a>.</li>'
                f'<li>Want the full list, or who your league hasn’t rostered? See <a href="../waiver-wire-trending/">trending adds</a> and the <a href="../waiver-wire/">waiver wire tool</a>.</li></ul>'
                f'<p>Related: <a href="../week-{WEEK}-start-sit/"><strong>Week {WEEK} start/sit cheat sheet</strong></a> · <a href="../start-sit-flex/">Week {WEEK} flex rankings</a> · <a href="../start-or-sit-players/">start or sit by player</a>.</p>'
                f'<p class="hint">Data from Sleeper as of {genh}. Counts and projections move fast. This is data, not betting advice.</p>'
                + faq_html(faqs))
        write(WAIVER_SLUG, 'Weekly start/sit', f'Week {WEEK} waiver wire', f'Week {WEEK} Waiver Wire Pickups (Fantasy Football {SEASON})',
              f'Week {WEEK} fantasy football waiver wire pickups by position: Sleeper trending adds, Week {WEEK} projections and next-3-week outlook. Updated {genh}.',
              f'Week {WEEK} waiver wire pickups', f'Trending adds by position, with projections and a quick note on each player.', ans, body,
              cta=('Compare two players', ''), cta_text='Found a pickup? Compare him with your starter.', featured=True, ld_extra=[faq_ld(faqs), itemlist(wall[:40], f'Week {WEEK} waiver wire trending adds')])
        for w in range(FIRST_WAIVER_WEEK, WEEK):
            d = ROOT / f'week-{w}-waiver-wire'; d.mkdir(exist_ok=True); OLDWEEKS.append(d.name)
            (d / 'index.html').write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Week {w} waiver wire has moved to Week {WEEK}</title><meta name="robots" content="noindex,follow"><link rel="canonical" href="{URL}{WAIVER_SLUG}/"><meta http-equiv="refresh" content="0; url=../{WAIVER_SLUG}/"></head><body><p><a href="../{WAIVER_SLUG}/">Week {WEEK} waiver wire</a></p></body></html>')
            (d / '.generated').write_text('')
# ---- rest-of-season (ROS) rankings: Sleeper's projections for the next three weeks + actual production (redraft, PPR) ----
def plink(p, pre='../'):
    if p['id'] in SS: return f'<a href="{pre}{SS[p["id"]]["slug"]}/">{E(p["n"])}</a>'
    if p['id'] in PLAYER_PAGES: return f'<a href="{pre}{vslug(p)}/">{E(p["n"])}</a>'
    return E(p['n'])
ROS_OUT = ('Out', 'IR', 'PUP', 'Sus')
def ros_parts(p):
    j = p.get('p3') or {}
    return (j['ppr'] / j['n'] if j.get('n') else None), (p.get('l3') or {}).get('ppr'), ppg_of(p)
def ros_score(p):
    """40% average projected PPR over the next (up to) 3 weeks, 30% last-3-games PPG, 30% season PPG; re-weighted over what exists. None = not ranked."""
    a, l3, g = ros_parts(p)
    if a is None or g is None or p.get('inj') in ROS_OUT: return None
    parts = [(0.4, a), (0.3, l3), (0.3, g)]; w = sum(x for x, v in parts if v is not None)
    return round(sum(x * v for x, v in parts if v is not None) / w, 1)
ROS_BY = {}; ROS_PR = {}
if WEEK:
    for pos in ('QB', 'RB', 'WR', 'TE'):
        lst = sorted([(ros_score(p), p) for p in players if p['pos'] == pos and ros_score(p) is not None], key=lambda t: (-t[0], t[1]['n']))
        ROS_BY[pos] = lst
        for i, (s, p) in enumerate(lst): ROS_PR[p['id']] = i + 1
ROS_LIM = {'QB': 24, 'RB': 40, 'WR': 48, 'TE': 20}
def ros_table(items):
    out = f'<div class="table-scroll"><table><thead><tr><th scope="col">#</th><th scope="col" style="text-align:left">Player</th><th scope="col">Pos rank</th><th scope="col">Wk {WEEK} proj</th><th scope="col">Next 3 wks avg</th><th scope="col">Last 3 games</th><th scope="col">Season PPG</th><th scope="col">ROS score</th><th scope="col">Status</th></tr></thead><tbody>'
    for i, (s, p) in enumerate(items):
        a, l3, g = ros_parts(p); pj = (p.get('proj') or {}).get('ppr')
        out += f'<tr><td>{i+1}</td><td style="text-align:left">{tag(p["pos"])} {plink(p)} <span class="hint" style="display:inline">{E(p.get("team") or "FA")}</span></td><td>{p["pos"]}{ROS_PR[p["id"]]}</td><td>{fmtn(pj)}</td><td>{round(a, 1)}</td><td>{fmtn(l3)}</td><td>{fmtn(g)}</td><td><b>{s}</b></td><td>{E(p.get("inj") or "Active")}</td></tr>'
    return out + '</tbody></table></div>'
ROS_METHOD = (f'<h2>How the rest-of-season score works</h2><p>The ROS score is a PPR points-per-game number: <strong>40%</strong> the average of Sleeper’s projections for Weeks {WEEK} to {WEEK + 2} (weeks with no projection, such as a bye, are skipped rather than counted as zero), <strong>30%</strong> the average of the last three games (nflverse), and <strong>30%</strong> season points per game. '
              'Players listed Out, IR, PUP or suspended are left off. It is a short-horizon, production-and-projection ranking: it does <em>not</em> use strength of schedule, depth-chart news or playoff schedules, and a player needs at least one game this season to be ranked.</p>')
def ros_faq(pos, lab, rows):
    t = rows[0]
    qas = [(f'Who is the top rest of season {lab} in {SEASON}?', f'By our ROS score, {t[1]["n"]} ({t[1].get("team") or "FA"}) is the top {pos} at {t[0]} PPR points per game, followed by {rows[1][1]["n"]} ({rows[1][0]}) and {rows[2][1]["n"]} ({rows[2][0]}), as of {genh}.'),
           ('How are these rest of season rankings calculated?', f'The score blends Sleeper’s projections for the next three weeks (40%), the last three games (30%) and season points per game (30%) in PPR. Players who are Out, on IR or suspended are excluded. Strength of schedule is not included.'),
           ('Are the ROS rankings for PPR, half PPR or standard?', 'They use full PPR points. For half PPR or standard, the order near the top barely changes, but pass-catching backs and slot receivers slip a little; the weekly start/sit pages list half-PPR projections too.'),
           ('How often do the rest of season rankings update?', f'Every day. The data on this page is as of {genh} and the projections look at Weeks {WEEK} to {WEEK + 2}.')]
    return qas
if WEEK and all(ROS_BY.get(k) and len(ROS_BY[k]) >= 5 for k in ('QB', 'RB', 'WR', 'TE')):
    ROS_LINKS = ' · '.join(f'<a href="../rest-of-season-{k.lower()}-rankings/">ROS {k} rankings</a>' for k in ('QB', 'RB', 'WR', 'TE'))
    for pos, lab in [('QB', 'quarterback'), ('RB', 'running back'), ('WR', 'wide receiver'), ('TE', 'tight end')]:
        rows = ROS_BY[pos][:ROS_LIM[pos]]; faqs = ros_faq(pos, lab, rows)
        write(f'rest-of-season-{pos.lower()}-rankings', 'Rest of season', f'ROS {pos} rankings', f'Rest of Season {pos} Rankings ({SEASON}): Fantasy {lab.title()}s, Week {WEEK}',
              f'Rest of season fantasy football {pos} rankings for Week {WEEK} on: Sleeper projections, last 3 games and season PPG blended into one PPR score. Updated {genh}.',
              f'Rest of season {pos} rankings (Week {WEEK})', f'The top {len(rows)} {lab}s for the rest of the {SEASON} fantasy season, ranked by projections and production.',
              f'The top rest-of-season {pos} is <strong>{E(rows[0][1]["n"])}</strong> ({E(rows[0][1].get("team") or "FA")}) at {rows[0][0]} PPR points per game, ahead of {E(rows[1][1]["n"])} ({rows[1][0]}) and {E(rows[2][1]["n"])} ({rows[2][0]}). As of {genh}.',
              ros_table(rows) + ROS_METHOD + f'<p class="hint">Projections: Sleeper public API. Production: nflverse (CC BY 4.0). Updated {genh}. Not betting or fantasy advice; injuries and roles change fast.</p>' + faq_html(faqs)
              + f'<p>Other positions: <a href="../rest-of-season-rankings/">all positions</a> · ' + ' · '.join(f'<a href="../rest-of-season-{k.lower()}-rankings/">{k}</a>' for k in ('QB', 'RB', 'WR', 'TE') if k != pos) + f'. Starting someone this week? See the <a href="../start-sit-{pos.lower()}/">Week {WEEK} {pos} start/sit rankings</a>, the <a href="../week-{WEEK}-waiver-wire/">Week {WEEK} waiver wire</a> or <a href="../dynasty-{pos.lower()}-rankings/">dynasty {pos} rankings</a>.</p>',
              cta=('Compare two players', ''), cta_text='Stuck between two players? Compare up to 4.', ld_extra=[faq_ld(faqs), itemlist([p for s, p in rows], f'Rest of season {pos} rankings')], featured=pos in ('RB', 'WR'))
    flex = sorted([t for k in ('RB', 'WR', 'TE') for t in ROS_BY[k]], key=lambda t: (-t[0], t[1]['n']))[:80]
    faqs = [(f'Who is the top rest of season player in fantasy football {SEASON}?', f'Among running backs, wide receivers and tight ends, {flex[0][1]["n"]} ({flex[0][1]["pos"]}, {flex[0][1].get("team") or "FA"}) has the highest ROS score at {flex[0][0]} PPR points per game, then {flex[1][1]["n"]} ({flex[1][0]}) and {flex[2][1]["n"]} ({flex[2][0]}), as of {genh}.'),
            ('Why are quarterbacks not in the overall list?', 'Quarterbacks score more raw points than other positions but you start only one (or two in superflex), so ranking them on the same scale as RB, WR and TE would mislead. Use the QB page for the position-only order.')] + ros_faq('RB', 'running back', ROS_BY['RB'])[1:]
    write('rest-of-season-rankings', 'Rest of season', 'Rest of season rankings', f'Rest of Season Fantasy Football Rankings ({SEASON}): Week {WEEK} On',
          f'Rest of season fantasy football rankings for Week {WEEK} on: top RB, WR and TE by ROS score, with QB, RB, WR and TE pages. Updated {genh}.',
          f'Rest of season fantasy rankings (Week {WEEK})', 'Top running backs, wide receivers and tight ends for the rest of the season, from projections and production, refreshed daily.',
          f'The top rest-of-season fantasy player (RB/WR/TE, PPR) is <strong>{E(flex[0][1]["n"])}</strong> at {flex[0][0]} points per game, then {E(flex[1][1]["n"])} ({flex[1][0]}) and {E(flex[2][1]["n"])} ({flex[2][0]}). Quarterbacks have their own page. As of {genh}.',
          ros_table(flex) + ROS_METHOD + f'<p>By position: {ROS_LINKS}. Week {WEEK} specifics: <a href="../week-{WEEK}-start-sit/">start/sit cheat sheet</a> and <a href="../week-{WEEK}-waiver-wire/">waiver wire</a>. Dynasty league? See <a href="../dynasty-rankings/">dynasty rankings</a> and <a href="../dynasty-buy-low-sell-high/">buy-low/sell-high targets</a>.</p><p class="hint">Projections: Sleeper public API. Production: nflverse (CC BY 4.0). Updated {genh}.</p>' + faq_html(faqs),
          cta=('Compare two players', ''), cta_text='Stuck between two players? Compare up to 4.', ld_extra=[faq_ld(faqs), itemlist([p for s, p in flex], 'Rest of season rankings (RB, WR, TE)')], featured=True)

# ---- weekly position rankings (targets "week N rb rankings", "week N flex rankings", "week N kicker rankings", "week N defense streamers") ----
# Rolls with the same WEEK as week-N-start-sit; older weeks become redirect stubs. Data: Sleeper weekly projections (data/players.json: players, kd, opp).
import rankings as RK
FIRST_RANK_WEEK = 7
RK_KEYS = ['qb', 'rb', 'wr', 'te', 'flex', 'kicker', 'defense']
OPP = D.get('opp') or None
KD = D.get('kd') or []
RK_SLUGS = {}
def _rk_pool(key):
    if key == 'kicker': return [k for k in KD if k['pos'] == 'K']
    if key == 'defense': return [k for k in KD if k['pos'] == 'DEF']
    return [p for p in players if p['pos'] in (('RB', 'WR', 'TE') if key == 'flex' else (key.upper(),))]
RK_N = {'qb': 24, 'rb': 40, 'wr': 50, 'te': 24, 'flex': 60, 'kicker': 24, 'defense': 32}
RK_NAME = {'qb': ('QB', 'quarterbacks'), 'rb': ('RB', 'running backs'), 'wr': ('WR', 'wide receivers'), 'te': ('TE', 'tight ends'), 'flex': ('Flex', 'flex plays (RB, WR and TE)'), 'kicker': ('Kicker', 'kickers'), 'defense': ('Defense', 'team defenses')}
RK_ROS = {'qb': 'rest-of-season-qb-rankings', 'rb': 'rest-of-season-rb-rankings', 'wr': 'rest-of-season-wr-rankings', 'te': 'rest-of-season-te-rankings', 'flex': 'rest-of-season-rankings'}
def _rk_title(key):
    return {'flex': f'Week {WEEK} Flex Rankings (PPR) {SEASON}: Best RB, WR, TE Plays', 'kicker': f'Week {WEEK} Kicker Rankings {SEASON}: Fantasy Football K Projections',
            'defense': f'Week {WEEK} Defense Rankings {SEASON}: D/ST Streamers and Projections'}.get(key, f'Week {WEEK} {RK_NAME[key][0]} Rankings (PPR) {SEASON}: Fantasy Football Projections')
BYE_TEAMS = sorted({p['team'] for p in players if p.get('team')} - set(OPP)) if OPP else []
def rk_block(pre, current=None):
    """Links to this week's position rankings (home, start/sit, ROS, guides and the rankings pages themselves)."""
    return ' · '.join(f'<a href="{pre}{RK_SLUGS[k]}/">{RK_NAME[k][0]}</a>' for k in RK_KEYS if k in RK_SLUGS and k != current)
if WEEK:
    for key in RK_KEYS:
        lab, longlab = RK_NAME[key]; kd_page = key in ('kicker', 'defense')
        rows = RK.rank_rows(_rk_pool(key))[:RK_N[key]]
        if len(rows) < (8 if kd_page else 12): continue
        slug = f'week-{WEEK}-{key}-rankings'; RK_SLUGS[key] = slug
        vals = [p['proj']['ppr'] for p in rows]; brk = RK.tier_breaks(vals); tn = RK.tier_numbers(len(rows), brk); groups = RK.tier_groups(len(rows), brk)
        word = {'qb': 'QBs', 'rb': 'RBs', 'wr': 'WRs', 'te': 'TEs', 'flex': 'flex plays', 'kicker': 'kickers', 'defense': 'defenses'}[key]
        def nm(p): return ss_link(p) if (not kd_page and p['id'] in SS) else E(p['n'])
        head = '<th scope="col">#</th><th scope="col" style="text-align:left">Player</th>' + ('<th scope="col">Pos</th>' if key == 'flex' else '') + '<th scope="col">Team</th>' + ('<th scope="col">Opp</th>' if OPP else '')
        if key == 'defense': head += '<th scope="col">Proj pts</th><th scope="col">Pts allowed</th><th scope="col">Sacks</th><th scope="col">Takeaways</th>'
        elif key == 'kicker': head += '<th scope="col">Proj pts</th><th scope="col">FG made</th><th scope="col">XP made</th>'
        else: head += '<th scope="col">PPR</th><th scope="col">Half</th><th scope="col">Std</th>'
        head += '<th scope="col">Tier</th>'
        trs = ''
        for i, p in enumerate(rows):
            pj = p['proj']; x = p.get('x') or {}
            cells = f'<td>{i+1}</td><td style="text-align:left">{nm(p)}</td>' + (f'<td>{tag(p["pos"])}</td>' if key == 'flex' else '') + f'<td>{E(p.get("team") or "FA")}</td>' + (f'<td>{E(RK.opp_label(OPP, p.get("team")))}</td>' if OPP else '')
            if key == 'defense': cells += f'<td><b>{RK.fmt_pts(pj["ppr"])}</b></td><td>{RK.fmt_pts(x.get("pa"))}</td><td>{RK.fmt_pts(x.get("sk"))}</td><td>{RK.fmt_pts(x.get("to"))}</td>'
            elif key == 'kicker': cells += f'<td><b>{RK.fmt_pts(pj["ppr"])}</b></td><td>{RK.fmt_pts(x.get("fgm"))}</td><td>{RK.fmt_pts(x.get("xpm"))}</td>'
            else: cells += f'<td><b>{RK.fmt_pts(pj["ppr"])}</b></td><td>{RK.fmt_pts(pj.get("half"))}</td><td>{RK.fmt_pts(pj.get("std"))}</td>'
            trs += f'<tr>{cells}<td>{tn[i]}</td></tr>'
        table_html = f'<div class="table-scroll"><table><thead><tr>{head}</tr></thead><tbody>{trs}</tbody></table></div>'
        tier_li = ''
        for t, (a, b) in enumerate(groups):
            shown = ', '.join(nm(p) for p in rows[a:min(b, a + 8)]) + (f' and {b - a - 8} more' if b - a > 8 else '')
            rng = RK.fmt_pts(vals[a]) if b - a == 1 else f'{RK.fmt_pts(vals[a])} to {RK.fmt_pts(vals[b - 1])}'
            tier_li += f'<li><strong>Tier {t + 1}</strong> ({rng}): {shown}</li>'
        top3 = rows[:3]; t1 = rows[0]
        ans = f'Top 3 {word} in Week {WEEK}: <strong>{E(t1["n"])}</strong> ({RK.fmt_pts(vals[0])} projected points), {E(rows[1]["n"])} ({RK.fmt_pts(vals[1])}) and {E(rows[2]["n"])} ({RK.fmt_pts(vals[2])}).'
        if key == 'defense':
            soft = min(rows, key=lambda p: ((p.get('x') or {}).get('pa', 99), p['n'])); ans += f' Lowest projected points allowed: {E(soft["n"])} ({RK.fmt_pts(soft["x"]["pa"])}).'
        elif not kd_page: ans += ' Points are PPR; half-PPR and standard are in the table.'
        qas = [(f'Who are the top {word} in Week {WEEK}?', f'{RK.top_names(top3)} are the top three {word} in Week {WEEK}, projected for {", ".join(RK.fmt_pts(v) for v in vals[:3])} points in that order (as of {genh}).')]
        if kd_page:
            qas.append((f'How are Week {WEEK} {word} ranked?', 'By projected fantasy points in Sleeper’s standard weekly projections. ' + ('Defense points come from projected sacks, takeaways and points allowed.' if key == 'defense' else 'Kicker points come from projected field goals and extra points.') + ' Scoring for K and D/ST is the same in PPR, half-PPR and standard.'))
        else:
            pj0 = t1['proj']; qas.append((f'How many points is {t1["n"]} projected for in Week {WEEK}?', f'{RK.fmt_pts(pj0["ppr"])} in PPR, {RK.fmt_pts(pj0.get("half"))} in half PPR and {RK.fmt_pts(pj0.get("std"))} in standard' + (f', {RK.opp_words(RK.opp_label(OPP, t1.get("team")))}' if OPP and t1.get('team') else '') + '.'))
            qas.append((f'Are these Week {WEEK} {lab} rankings for PPR?', 'The order is by PPR projection. Half-PPR and standard projections sit next to it; pass-catchers move down a little in those formats and the top of the list barely changes.'))
        if key == 'defense':
            qas.append((f'Who is the best streaming defense in Week {WEEK}?', f'On projected points allowed, {soft["n"]} ({RK.opp_words(RK.opp_label(OPP, soft.get("team")))}) has the softest projection at {RK.fmt_pts(soft["x"]["pa"])} points allowed, and it ranks #{rows.index(soft) + 1} of {len(rows)} defenses on total projected points. Check which defenses are free in your league first.'))
        if BYE_TEAMS: qas.append((f'Which teams are on a bye in Week {WEEK}?', f'{", ".join(BYE_TEAMS)} {"is" if len(BYE_TEAMS) == 1 else "are"} on a bye in Week {WEEK}, so their players are not ranked.'))
        qas.append((f'When do the Week {WEEK} {lab} rankings update?', f'Every day, and again on Tuesday when the next week opens. Injury statuses change late in the week, so check before kickoff. Data as of {genh}.'))
        others = rk_block('../', key)
        links = [f'<a href="../start-sit/">start/sit tool</a>', f'<a href="../week-{WEEK}-start-sit/">Week {WEEK} start/sit cheat sheet</a>']
        if (ROOT / WAIVER_SLUG).exists(): links.append(f'<a href="../{WAIVER_SLUG}/">Week {WEEK} waiver wire</a>')
        if key in RK_ROS: links.append(f'<a href="../{RK_ROS[key]}/">rest of season {lab if key != "flex" else "RB, WR and TE"} rankings</a>')
        if key in SSPOS: links.append(f'<a href="../start-sit-{key}/">Week {WEEK} {lab} start/sit rankings</a>')
        links.append('<a href="../start-or-sit-players/">start or sit by player</a>')
        body = (f'<h2>Week {WEEK} {lab} tiers</h2><ul>{tier_li}</ul><p class="hint">Tiers break at the big drops in projected points.</p>'
                f'<h2>Week {WEEK} {lab} rankings</h2>{table_html}'
                + (f'<p class="hint">Byes: {", ".join(BYE_TEAMS)}. Opp: @ means away.</p>' if BYE_TEAMS else '')
                + f'<p class="hint">Projections from Sleeper’s public API, updated {genh}. Players ruled out are left off; injury statuses change late in the week. Data, not betting advice.</p>'
                + faq_html(qas)
                + f'<h2>More Week {WEEK} tools</h2><p>Deciding between two players? Use the ' + ' · '.join(links) + f'.</p><p>Other positions: {others}.</p>')
        write(slug, 'Weekly rankings', f'Week {WEEK} {lab} rankings', _rk_title(key),
              fit([f'Week {WEEK} {lab} rankings: projected points' + ('' if kd_page else ' in PPR, half PPR and standard') + f', opponent and tiers for every {({'flex': 'flex play', 'kicker': 'kicker', 'defense': 'defense'}).get(key, lab)}. Updated {genh}.', f'Week {WEEK} {lab} rankings with projected points, opponent and tiers. Updated {genh}.'], 70, 155),
              f'Week {WEEK} {lab} rankings', f'{len(rows)} {longlab} ranked by projected points, with matchups and tiers.', ans, body,
              cta=('Compare two players', ''), cta_text='Who should I start? Compare up to 4 players.', featured=key in ('rb', 'flex'), ld_extra=[faq_ld(qas), itemlist(rows, f'Week {WEEK} {lab} rankings')])
    if RK_SLUGS:
        for w in range(FIRST_RANK_WEEK, WEEK):
            for k in RK_KEYS:
                if k not in RK_SLUGS: continue
                sl = f'week-{w}-{k}-rankings'; d = ROOT / sl; d.mkdir(exist_ok=True); OLDWEEKS.append(sl)
                (d / 'index.html').write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Week {w} {RK_NAME[k][0]} rankings have moved to Week {WEEK}</title><meta name="robots" content="noindex,follow"><link rel="canonical" href="{URL}{RK_SLUGS[k]}/"><meta http-equiv="refresh" content="0; url=../{RK_SLUGS[k]}/"></head><body><p><a href="../{RK_SLUGS[k]}/">Week {WEEK} {RK_NAME[k][0]} rankings</a></p></body></html>')
                (d / '.generated').write_text('')

# ---- dynasty buy-low / sell-high: expert consensus vs the draft market, plus movers from the daily value history ----
def mkt_val(p):
    m = [x for x in ((p.get('cs') or {}).get('sl'), (p.get('cs') or {}).get('ffc')) if x is not None]
    return round(sum(m) / len(m)) if m else None
def vlink(p, pre='../'): return f'<a href="{pre}{vslug(p)}/">{E(p["n"])}</a>' if p['id'] in PLAYER_PAGES else E(p['n'])
def chg_cell(p):
    c = vchg(p)
    if not c: return '—'
    return f'{c[0]:+,} ({c[1]:+.1f}%)'
buys_all = sorted([p for p in valued if p.get('sig') == 'buy'], key=lambda p: -p['v1']); sells_all = sorted([p for p in valued if p.get('sig') == 'sell'], key=lambda p: -p['v1'])
def sig_table(rows):
    out = '<div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Player</th><th scope="col">Age</th><th scope="col">Experts</th><th scope="col">Draft market</th><th scope="col">Market vs experts</th><th scope="col">Composite (1QB)</th>' + (f'<th scope="col">Since {fmt_d(BASE_D)}</th>' if BASE_D else '') + '<th scope="col">PPR PPG</th><th scope="col">Status</th></tr></thead><tbody>'
    for p in rows:
        dp, mk = (p.get('cs') or {}).get('dp'), mkt_val(p)
        out += f'<tr><td style="text-align:left">{tag(p["pos"])} {vlink(p)} <span class="hint" style="display:inline">{E(p.get("team") or "FA")}</span></td><td>{p.get("age") or "—"}</td><td>{fmtn(dp)}</td><td>{fmtn(mk)}</td><td>{round((mk - dp) / dp * 100):+d}%</td><td><b>{p["v1"]:,}</b></td>' + (f'<td>{chg_cell(p)}</td>' if BASE_D else '') + f'<td>{fmtn(ppg_of(p))}</td><td>{E(p.get("inj") or "Active")}</td></tr>'
    return out + '</tbody></table></div>'
if buys_all and sells_all:
    buys, sells = buys_all[:15], sells_all[:15]
    swaps = []
    for s in sells[:8]:
        cand = sorted([b for b in buys_all if trade_calc([s['v1']], [b['v1']])['fair']], key=lambda b: abs(b['v1'] - s['v1']))[:2]
        if cand: swaps.append((s, cand))
    swap_html = ''
    if swaps:
        swap_html = '<h2>Sell-high for buy-low swaps that are fair on paper</h2><p>Straight swaps inside the 5% fair range (1QB values). On paper only: your roster needs, your scoring and the other manager’s view still matter.</p><div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Sell (market above experts)</th><th scope="col" style="text-align:left">Buy (market below experts)</th><th scope="col">Values</th><th scope="col">Gap</th></tr></thead><tbody>' + ''.join(
            f'<tr><td style="text-align:left">{tag(s["pos"])} {vlink(s)}</td><td style="text-align:left">{tag(b["pos"])} {vlink(b)}</td><td>{s["v1"]:,} vs {b["v1"]:,}</td><td>{abs(trade_calc([s["v1"]], [b["v1"]])["pct"])}%</td></tr>' for s, cs_ in swaps for b in cs_) + '</tbody></table></div>'
    nb, ns = len(buys_all), len(sells_all)
    faqs = [('What is a dynasty buy-low or sell-high target?', 'A buy-low is a player the draft market prices well below what the experts say he’s worth. A sell-high is the reverse. “Market” is Sleeper (and Fantasy Football Calculator when available) dynasty ADP, “experts” is the DynastyProcess consensus, and a flag needs a gap of at least 35% with a composite value of 1,000 or more.'),
            (f'Which dynasty players are the best buy-low targets right now?', f'By composite value, the top flagged buys as of {genh} are ' + ', '.join(f'{b["n"]} ({b["v1"]:,})' for b in buys[:5]) + '.'),
            (f'Which dynasty players are the best sell-high candidates right now?', f'By composite value, the top flagged sells as of {genh} are ' + ', '.join(f'{s["n"]} ({s["v1"]:,})' for s in sells[:5]) + '.'),
            ('Does a buy or sell flag mean I should make the trade?', 'No. It’s a nudge to look closer. The market can be right and the experts wrong, and the flag ignores age, role, injuries and your own roster and scoring.'),
            ('When is the fantasy trade deadline?', 'It is a league setting chosen by your commissioner, so check your league’s rules; many leagues close trades in the middle of the season. These tables refresh daily, so re-check before your deadline.')]
    write('dynasty-buy-low-sell-high', 'Dynasty movers', 'Dynasty buy-low/sell-high', f'Dynasty Buy Low & Sell High Trade Targets ({SEASON}): Updated Daily',
          f'Dynasty buy-low and sell-high trade targets from the gap between expert rankings and the draft market, plus value changes. Updated {genh}.',
          f'Dynasty buy-low and sell-high trade targets ({SEASON})', 'Where the draft market and the experts disagree most, ranked by trade value, fresh every morning.',
          f'{nb} players are flagged as possible buys and {ns} as possible sells as of {genh}. The most valuable buy is <strong>{E(buys[0]["n"])}</strong> ({buys[0]["v1"]:,}) and the most valuable sell is <strong>{E(sells[0]["n"])}</strong> ({sells[0]["v1"]:,}).',
          f'<h2>Buy low: market below the experts</h2>{sig_table(buys)}<h2>Sell high: market above the experts</h2>{sig_table(sells)}{swap_html}'
          + '<h2>How to read this</h2><ul><li><strong>Experts</strong> is the DynastyProcess expert-consensus value; <strong>Draft market</strong> is dynasty ADP (real drafts) converted to the same 0–10,000 scale by positional rank. See <a href="../how-our-values-work/">how our values work</a>.</li><li><strong>Market vs experts</strong> is the gap; the flag needs 35% or more.</li>'
          + (f'<li><strong>Since {fmt_d(BASE_D)}</strong> is the change in value since {fmt_d(BASE_D)} (see <a href="../dynasty-value-risers-fallers/">risers and fallers</a>).</li>' if BASE_D else '')
          + '<li>Price any deal in the <a href="../trade-analyzer/">dynasty trade analyzer</a>, which discounts 2-for-1 packages.</li></ul>' + SRC + faq_html(faqs),
          ld_extra=[faq_ld(faqs)], featured=True)
if BASE_D:
    mv = [(p, *vchg(p)) for p in valued if vchg(p) and max(p['v1'], HIST[BASE_D][p['id']][0]) >= 1000]
    if len(mv) >= 20:
        up = sorted(mv, key=lambda t: -t[1])[:15]; dn = sorted(mv, key=lambda t: t[1])[:15]
        def mv_table(rows):
            return '<div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Player</th><th scope="col">Age</th><th scope="col">' + f'{fmt_d(BASE_D)}' + '</th><th scope="col">Now</th><th scope="col">Change</th><th scope="col">%</th><th scope="col">Pos rank now</th></tr></thead><tbody>' + ''.join(
                f'<tr><td style="text-align:left">{tag(p["pos"])} {vlink(p)} <span class="hint" style="display:inline">{E(p.get("team") or "FA")}</span></td><td>{p.get("age") or "—"}</td><td>{HIST[BASE_D][p["id"]][0]:,}</td><td><b>{p["v1"]:,}</b></td><td>{d:+,}</td><td>{pc:+.1f}%</td><td>{p["pos"]}{pr.get(p["id"], "—")}</td></tr>' for p, d, pc in rows) + '</tbody></table></div>'
        bypos = ''
        for pos in ('QB', 'RB', 'WR', 'TE'):
            xs = [t for t in mv if t[0]['pos'] == pos]
            if xs:
                u, f = max(xs, key=lambda t: t[1]), min(xs, key=lambda t: t[1])
                bypos += f'<tr><th scope="row" style="text-align:left">{pos}</th><td style="text-align:left">{vlink(u[0])} ({u[1]:+,})</td><td style="text-align:left">{vlink(f[0])} ({f[1]:+,})</td></tr>'
        days = (datetime.date.fromisoformat(gen) - datetime.date.fromisoformat(BASE_D)).days
        big = sum(1 for t in mv if abs(t[2]) >= 10)
        faqs = [('Who gained the most dynasty value this week?', f'Since {fmt_d(BASE_D)}, the biggest 1QB composite value gains were ' + ', '.join(f'{p["n"]} ({d:+,})' for p, d, pc in up[:4]) + f', as of {genh}.'),
                ('Who lost the most dynasty value this week?', f'Since {fmt_d(BASE_D)}, the biggest losses were ' + ', '.join(f'{p["n"]} ({d:+,})' for p, d, pc in dn[:4]) + f', as of {genh}.'),
                ('Why did a player’s dynasty value change?', 'The composite blends expert consensus (updated weekly), dynasty ADP from Sleeper (changes daily) and nflverse production (changes after each game). The page shows how far a number moved, not why. News, role changes and injuries are the usual drivers.'),
                ('How far back does the comparison go?', f'It compares today with {fmt_d(BASE_D)} ({days} day{"s" if days != 1 else ""} ago). Once a full week of history exists, the baseline stays seven days back.')]
        write('dynasty-value-risers-fallers', 'Dynasty movers', 'Dynasty risers & fallers', f'Dynasty Value Risers & Fallers ({SEASON}): Biggest Movers',
              f'Dynasty value risers and fallers over the last {days} days with the biggest gains and drops in 1QB trade value. Updated {genh}.',
              f'Dynasty value risers and fallers ({SEASON})', f'Who gained and lost the most trade value since {fmt_d(BASE_D)}.',
              f'Since {fmt_d(BASE_D)}, <strong>{E(up[0][0]["n"])}</strong> gained the most 1QB dynasty value ({up[0][1]:+,}, now {up[0][0]["v1"]:,}) and <strong>{E(dn[0][0]["n"])}</strong> lost the most ({dn[0][1]:+,}, now {dn[0][0]["v1"]:,}). {big} players with a value of 1,000 or more moved 10% or more.',
              f'<h2>Biggest risers</h2>{mv_table(up)}<h2>Biggest fallers</h2>{mv_table(dn)}<h2>Biggest mover at each position</h2><div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Position</th><th scope="col" style="text-align:left">Riser</th><th scope="col" style="text-align:left">Faller</th></tr></thead><tbody>{bypos}</tbody></table></div>'
              + f'<p class="hint">Only players with a composite value of 1,000 or more at either date are compared. Values are on a 0–10,000 scale; changes are in value points. Expert consensus updates about weekly while ADP moves daily, so some moves are one input catching up. Compared with {fmt_d(BASE_D)}.</p><p>Looking for trade targets? See <a href="../dynasty-buy-low-sell-high/">dynasty buy-low and sell-high targets</a>, the <a href="../dynasty-trade-value-chart/">trade value chart</a> and <a href="../dynasty-rookie-rankings/">dynasty rookie rankings</a>.</p>' + SRC + faq_html(faqs),
              ld_extra=[faq_ld(faqs)], featured=True)

# ---- dynasty rookie rankings: the current rookie class by composite value, plus next year's pick values ----
rooks = [p for p in valued if p.get('exp') == 0]
if len(rooks) >= 10:
    top_r = rooks[:40]
    def rk_table(rows):
        out = '<div class="table-scroll"><table><thead><tr><th scope="col">#</th><th scope="col" style="text-align:left">Player</th><th scope="col">Pos rank (all)</th><th scope="col">Age</th><th scope="col">1QB</th><th scope="col">SF</th>' + (f'<th scope="col">Since {fmt_d(BASE_D)}</th>' if BASE_D else '') + '<th scope="col">Games</th><th scope="col">PPR PPG</th><th scope="col">Status</th></tr></thead><tbody>'
        for i, p in enumerate(rows):
            out += f'<tr><td>{i+1}</td><td style="text-align:left">{tag(p["pos"])} {plink(p)} <span class="hint" style="display:inline">{E(p.get("team") or "FA")}</span></td><td>{p["pos"]}{pr.get(p["id"], "—")}</td><td>{p.get("age") or "—"}</td><td><b>{p["v1"]:,}</b></td><td>{(p.get("v2") or p["v1"]):,}</td>' + (f'<td>{chg_cell(p)}</td>' if BASE_D else '') + f'<td>{p.get("gp") or 0}</td><td>{fmtn(ppg_of(p))}</td><td>{E(p.get("inj") or "Active")}</td></tr>'
        return out + '</tbody></table></div>'
    nxt = [pk for pk in picks if pk['n'][:4] == str(int(SEASON) + 1)] if picks else []
    pick_html = ('<h2>What next year’s rookie picks are worth</h2><p>Draft picks sit on the same scale as players, so you can see what a pick costs against a current rookie.</p><div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Pick</th><th scope="col">1QB value</th><th scope="col">SF value</th><th scope="col" style="text-align:left">Closest rookie (1QB)</th></tr></thead><tbody>' + ''.join(
        f'<tr><td style="text-align:left">{tag("PICK")} {E(pk["n"])}</td><td>{pk["v1"]:,}</td><td>{(pk.get("v2") or pk["v1"]):,}</td><td style="text-align:left">{vlink(n)}</td></tr>' for pk in nxt for n in [min(rooks, key=lambda q: abs(q['v1'] - pk['v1']))]) + '</tbody></table></div><p><a href="../rookie-draft-pick-values/">All rookie pick values</a>.</p>') if nxt else ''
    posb = ''.join(f'<li>{pos}: ' + ', '.join(f'{vlink(q)} ({q["v1"]:,})' for q in [r for r in rooks if r['pos'] == pos][:3]) + '</li>' for pos in ('QB', 'RB', 'WR', 'TE') if [r for r in rooks if r['pos'] == pos])
    faqs = [(f'Who is the top {SEASON} rookie in dynasty right now?', f'{rooks[0]["n"]} ({rooks[0]["pos"]}, {rooks[0].get("team") or "FA"}) has the highest composite dynasty value among {SEASON} rookies at {rooks[0]["v1"]:,} in 1QB leagues and {(rooks[0].get("v2") or rooks[0]["v1"]):,} in superflex, followed by {rooks[1]["n"]} ({rooks[1]["v1"]:,}) and {rooks[2]["n"]} ({rooks[2]["v1"]:,}), as of {genh}.'),
            ('How are these dynasty rookie rankings made?', 'By dynasty value (expert consensus, Sleeper and Fantasy Football Calculator ADP, and nflverse production), first-year players only. Pre-draft grades and college scouting aren’t in the number.'),
            ('Is there a 2027 rookie class ranking?', f'Not yet. That class has no pro data to value. The market price of {int(SEASON) + 1} rookie picks is below, and that is how most dynasty leagues trade the class.'),
            ('Can I use this for a startup or rookie draft?', 'Yes. The rookie draft board tool uses the same values and lets you tick players off as they are drafted.')]
    write('dynasty-rookie-rankings', 'Dynasty rankings', f'Dynasty rookie rankings {SEASON}', f'Dynasty Rookie Rankings {SEASON}: Class Values & Production',
          f'Dynasty rookie rankings for the {SEASON} class by trade value in 1QB and superflex, with games, PPG and value changes. Updated {genh}.',
          f'Dynasty rookie rankings {SEASON}', f'Every first-year player ranked by composite dynasty value, with this season’s production.',
          f'The top {SEASON} rookie in dynasty is <strong>{E(rooks[0]["n"])}</strong> ({rooks[0]["pos"]}, {E(rooks[0].get("team") or "FA")}, value {rooks[0]["v1"]:,}), then {E(rooks[1]["n"])} ({rooks[1]["v1"]:,}) and {E(rooks[2]["n"])} ({rooks[2]["v1"]:,}). {len(rooks)} rookies carry a value, as of {genh}.',
          rk_table(top_r) + f'<h2>Top rookies by position</h2><ul>{posb}</ul>' + pick_html + '<p>Drafting? Use the <a href="../rookie-draft-board/">rookie draft board</a>. Trading? Price it in the <a href="../trade-analyzer/">dynasty trade analyzer</a>. See also <a href="../dynasty-value-risers-fallers/">value risers and fallers</a>.</p>' + SRC + faq_html(faqs),
          ld_extra=[faq_ld(faqs), itemlist(top_r, f'Dynasty rookie rankings {SEASON}')], featured=True)

# ---- player value pages (top 250) ----
SSPOS_LABEL = {'QB': 'QB', 'RB': 'RB', 'WR': 'WR', 'TE': 'TE'}
def source_line(p):
    c = CON.get(p.get('con') or 'single')[1]
    return f'{c}' + (f' (spread {p["sp"]}%)' if p.get('sp') is not None else '')
def sig_sentence(p):
    sig = p.get('sig')
    if sig == 'buy': return 'The data flags a possible buy: the draft markets (Sleeper and Fantasy Football Calculator ADP) value him at least 35% below the expert consensus. That is a prompt to look closer, not advice.'
    if sig == 'sell': return 'The data flags a possible sell: the draft markets (Sleeper and Fantasy Football Calculator ADP) value him at least 35% above the expert consensus. That is a prompt to look closer, not advice.'
    return 'The data shows no buy or sell flag: the draft markets are not far enough from the expert consensus (under 35%) to flag him either way.'
for p in valued[:N_VALUE_PAGES]:
    v1, v2 = p['v1'], p.get('v2') or p['v1']
    comps = sorted([q for q in valued if q['id'] != p['id']], key=lambda q: (abs(q['v1'] - v1), q['id']))[:6]
    pk = min(picks, key=lambda q: abs(q['v1'] - v1)) if picks else None
    if pk and abs(pk['v1'] - v1) > 0.2 * v1: pk = None  # only mention a pick when it is genuinely comparable
    nm = E(p['n']); pos = p['pos']
    fair = [q for q in comps if trade_calc([v1], [q['v1']])['fair']]
    ppr = ppg_of(p)
    qas = [(f'What is {p["n"]}\'s dynasty value?', f'As of {genh}, {p["n"]} has a composite dynasty value of {v1:,} in 1QB leagues (#{one_rank[p["id"]]} overall) and {v2:,} in superflex (#{sf_rank[p["id"]]} overall). He is {pos}{pr.get(p["id"])} by value at his position.'),
           (f'Is {p["n"]} a buy or sell in dynasty?', f'Source agreement: {source_line(p)}. ' + sig_sentence(p))]
    if fair: qas.append((f'Who is a fair trade for {p["n"]}?', f'By the same rule as our trade calculator (within about 5%), straight-up trades for ' + ', '.join(f'{q["n"]} ({q["v1"]:,})' for q in fair[:3]) + f' are fair against {p["n"]} ({v1:,}) in 1QB leagues.' + (f' A {pk["n"]} pick is also in the same range.' if pk else '')))
    else: qas.append((f'Who is a fair trade for {p["n"]}?', f'No other player is within about 5% of {p["n"]}\'s {v1:,} in 1QB, so a fair deal is usually a package. The closest single values are ' + ', '.join(f'{q["n"]} ({q["v1"]:,})' for q in comps[:3]) + '. The calculator discounts extra pieces, so a package needs to add up to more than the sum.'))
    gp = p.get('gp')
    qas.append((f'How old is {p["n"]} and what is his PPG?', (f'{p["n"]} is {p["age"]} years old' if p.get('age') else f'His age is not listed') + f', plays {pos} for {p.get("team") or "no team (free agent)"}' + (f' and averages {ppr} PPR points per game in {SEASON}' + (f' over {gp} games.' if gp else '.') if ppr is not None else f' and has no {SEASON} points per game on record yet.')))
    posname = {'QB': 'quarterback', 'RB': 'running back', 'WR': 'wide receiver', 'TE': 'tight end'}.get(pos, pos)
    ss_bits = ''
    if p['id'] in SS: ss_bits += f'<li><a href="../{SS[p["id"]]["slug"]}/">Should I start {nm} this week?</a> (Week {WEEK} call and projection)</li>'
    if WEEK and pos in SSPOS: ss_bits += f'<li><a href="../start-sit-{pos.lower()}/">Week {WEEK} {pos} start/sit rankings</a></li>'
    cmp_bits = ''.join(f'<li><a href="../{s}/">{nm} vs {E(o["n"])} dynasty</a></li>' for s, o in CMP_BY.get(p['id'], []))
    more = f'<h2>Related pages</h2><ul>{cmp_bits}{ss_bits}<li><a href="../dynasty-{pos.lower()}-rankings/">Dynasty {pos} rankings</a></li><li><a href="../dynasty-player-values/">All player dynasty values</a></li></ul>'
    write(vslug(p), 'Player values', f'{p["n"]} dynasty value', f'{p["n"]} Dynasty Value {SEASON}: Rank & Trade Comps',
          f'{p["n"]} dynasty value today: #{one_rank[p["id"]]} overall in 1QB, #{sf_rank[p["id"]]} in superflex, {pos}{pr.get(p["id"])}. Comparable players and picks. Updated {genh}.',
          f'{nm} dynasty trade value', f'{pos}, {E(p.get("team") or "free agent")}{", age "+str(p["age"]) if p.get("age") else ""}.',
          f'{nm} is the <strong>#{one_rank[p["id"]]}</strong> dynasty asset in 1QB leagues (value {v1:,}) and <strong>#{sf_rank[p["id"]]}</strong> in superflex (value {v2:,}), and the {pos}{pr.get(p["id"])} at his position, as of {genh}.' + (f' That is roughly the value of a {E(pk["n"])}.' if pk else ''),
          f'''<div class="stats s3"><div class="stat"><div class="k">1QB value</div><div class="v">{v1:,}</div></div><div class="stat"><div class="k">Superflex value</div><div class="v">{v2:,}</div></div><div class="stat"><div class="k">Position rank</div><div class="v">{pos}{pr.get(p["id"])}</div></div><div class="stat"><div class="k">Age</div><div class="v">{p.get("age") or "—"}</div></div><div class="stat"><div class="k">PPR PPG ({SEASON})</div><div class="v">{fmtn(ppr)}</div></div><div class="stat"><div class="k">Status</div><div class="v">{E(p.get("inj") or "Active")}</div></div></div>
{breakdown(p)}
<h2>Players with similar value</h2><p>The closest {len(comps)} players by 1QB value (within about 5% counts as a fair straight-up trade):</p>{table(comps, n=6)}
<p><a class="btn" href="../?a={p["id"]}&b={comps[0]["id"]}#trade">Compare {nm} vs {E(comps[0]["n"])}</a></p>
{faq_html(qas)}
{more}{SRC}''',
          cta=(f'Trade calculator with {p["n"].split(" ")[-1]}', f'?a={p["id"]}'), changefreq='daily', ld_extra=[faq_ld(qas)])

# ---- "X vs Y dynasty" comparison pages ----
def age_line(a, b):
    if not a.get('age') or not b.get('age'): return ''
    d = abs(a['age'] - b['age'])
    if d == 0: return f'Both are {a["age"]} years old.'
    y, o = (a, b) if a['age'] < b['age'] else (b, a)
    return f'{y["n"]} is {d} year{"s" if d != 1 else ""} younger ({y["age"]} vs {o["age"]}).'
def ppg_line(a, b):
    x, y = ppg_of(a), ppg_of(b)
    if x is None or y is None: return ''
    if x == y: return f'Both average {x} PPR points per game in {SEASON}.'
    h, l = (a, b) if x > y else (b, a)
    return f'{h["n"]} is scoring more in {SEASON}: {ppg_of(h)} vs {ppg_of(l)} PPR points per game.'
for a, b in CMPS:
    slug = cslug(a, b); na, nb = E(a['n']), E(b['n']); pos = a['pos']
    a2, b2 = a.get('v2') or a['v1'], b.get('v2') or b['v1']
    t1 = trade_calc([a['v1']], [b['v1']]); t2 = trade_calc([a2], [b2])
    def verdict(t, hi_name, lo_name):
        if t['fair']: return f'a fair trade (the gap is {abs(t["pct"])}%, within the 5% fair range)'
        return f'not even: {hi_name} is valued {abs(t["pct"])}% above {lo_name}, so a straight swap favors the side getting {hi_name}'
    adds = balance_adds([b['v1']], [a['v1']], valued[:N_VALUE_PAGES], 'v1', {a['id'], b['id']}) if not t1['fair'] else []
    ans = (f'In 1QB dynasty, {na} is valued at <strong>{a["v1"]:,}</strong> and {nb} at <strong>{b["v1"]:,}</strong>: straight up that is <strong>{"a fair trade" if t1["fair"] else "not even"}</strong> ' +
           (f'({abs(t1["pct"])}% gap, within the 5% fair range).' if t1['fair'] else f'({abs(t1["pct"])}% gap, favoring the side that gets {na}).') + f' Superflex values are {a2:,} and {b2:,}.')
    def row(label, x, y): return f'<tr><th scope="row" style="text-align:left">{label}</th><td>{x}</td><td>{y}</td></tr>'
    srcrows = ''.join(row(f'{SRCN[k][0]} value', fmtn((a.get('cs') or {}).get(k)), fmtn((b.get('cs') or {}).get(k))) for k in ('dp', 'sl', 'ffc', 'prod') if k in (a.get('cs') or {}) or k in (b.get('cs') or {}))
    table_html = f'''<div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left"></th><th scope="col"><a href="../{vslug(a)}/">{na}</a></th><th scope="col"><a href="../{vslug(b)}/">{nb}</a></th></tr></thead><tbody>
{row("Team", a.get("team") or "FA", b.get("team") or "FA")}{row("Age", fmtn(a.get("age")), fmtn(b.get("age")))}{row(f"{pos} rank by value", f"{pos}{pr.get(a['id'])}", f"{pos}{pr.get(b['id'])}")}{row("1QB value", f"<b>{a['v1']:,}</b>", f"<b>{b['v1']:,}</b>")}{row("Superflex value", f"<b>{a2:,}</b>", f"<b>{b2:,}</b>")}{row("Overall rank (1QB / SF)", f"#{one_rank[a['id']]} / #{sf_rank[a['id']]}", f"#{one_rank[b['id']]} / #{sf_rank[b['id']]}")}{row(f"PPR PPG ({SEASON})", fmtn(ppg_of(a)), fmtn(ppg_of(b)))}{row("Injury status", E(a.get("inj") or "Active"), E(b.get("inj") or "Active"))}{row("Source agreement", E(source_line(a)), E(source_line(b)))}{srcrows}</tbody></table></div>'''
    adds_html = (f'<p>To even it up, the side getting {nb} could add a piece such as ' + ', '.join(f'<a href="../{vslug(q)}/">{E(q["n"])}</a> ({q["v1"]:,})' for q in adds) + ' (checked with the calculator’s 2-for-1 discount).</p>') if adds else ''
    sigs = ''.join(f'<li>{E(x["n"])}: {"possible buy (market below experts)" if x.get("sig")=="buy" else "possible sell (market above experts)"}</li>' for x in (a, b) if x.get('sig'))
    qas = [(f'Who is worth more in dynasty, {a["n"]} or {b["n"]}?', f'{a["n"]} is valued higher in 1QB leagues, by {abs(a["v1"]-b["v1"]):,} points ({a["v1"]:,} vs {b["v1"]:,}) as of {genh}.' + (f' In superflex it is {a2:,} vs {b2:,}.' )),
           (f'Is {a["n"]} for {b["n"]} a fair dynasty trade?', f'In 1QB leagues, a straight swap is {verdict(t1, a["n"], b["n"])}. In superflex it is {verdict(t2, a["n"] if a2 >= b2 else b["n"], b["n"] if a2 >= b2 else a["n"])}.'),
           (f'Who is younger, {a["n"]} or {b["n"]}, and who scores more?', ' '.join(x for x in (age_line(a, b), ppg_line(a, b)) if x) or 'Age or points-per-game data is not available for one of these players yet.')]
    sa, sb = SS.get(a['id']), SS.get(b['id'])
    ss_html = ''.join(f'<li><a href="../{x["slug"]}/">Should I start {E(x["p"]["n"])} this week?</a></li>' for x in (sa, sb) if x)
    title = fit([f'{a["n"]} vs {b["n"]} Dynasty Value {SEASON}: Who Wins?', f'{a["n"]} vs {b["n"]}: Dynasty Trade Value', f'{a["n"]} vs {b["n"]} Dynasty'], 20, 65)
    desc = fit([f'{a["n"]} vs {b["n"]} dynasty: 1QB values {a["v1"]:,} vs {b["v1"]:,}, superflex, age, PPG and a fair-trade verdict. Updated {genh}.', f'{a["n"]} vs {b["n"]} dynasty values, ages, PPG and a fair-trade verdict. Updated {genh}.'], 70, 155)
    write(slug, 'Player comparisons', f'{a["n"]} vs {b["n"]}', title, desc, f'{na} vs {nb} dynasty', f'Two {pos}s with close dynasty trade values, side by side.', ans,
          f'''{table_html}
<h2>Fair-trade verdict</h2>
<div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Format</th><th scope="col">{na}</th><th scope="col">{nb}</th><th scope="col">Gap</th><th scope="col">Verdict</th></tr></thead><tbody>
<tr><th scope="row" style="text-align:left">1QB</th><td>{t1["a"]:,}</td><td>{t1["b"]:,}</td><td>{abs(t1["pct"])}%</td><td>{"Fair trade" if t1["fair"] else "Favors " + (na if t1["gap"] > 0 else nb)}</td></tr>
<tr><th scope="row" style="text-align:left">Superflex</th><td>{t2["a"]:,}</td><td>{t2["b"]:,}</td><td>{abs(t2["pct"])}%</td><td>{"Fair trade" if t2["fair"] else "Favors " + (na if t2["gap"] > 0 else nb)}</td></tr></tbody></table></div>
<p class="hint">Same rule as the <a href="../?a={a["id"]}&b={b["id"]}#trade">trade calculator</a>: gap = (larger − smaller) ÷ larger; within 5% is fair. Favors means the side receiving that player gets the better value.</p>{adds_html}
{('<h2>Buy/sell flags</h2><ul>' + sigs + '</ul>') if sigs else ''}
<p>{E(age_line(a, b))} {E(ppg_line(a, b))}</p>
{faq_html(qas)}
<h2>More</h2><ul><li><a href="../{vslug(a)}/">{na} dynasty value</a></li><li><a href="../{vslug(b)}/">{nb} dynasty value</a></li><li><a href="../dynasty-{pos.lower()}-rankings/">Dynasty {pos} rankings</a></li><li><a href="../dynasty-player-comparisons/">All dynasty player comparisons</a></li>{ss_html}</ul>
<p><a class="btn" href="../?a={a["id"]}&b={b["id"]}#trade">Open {na} vs {nb} in the trade calculator</a></p>{SRC}''',
          cta=(f'Trade calculator: {a["n"].split(" ")[-1]} vs {b["n"].split(" ")[-1]}', f'?a={a["id"]}&b={b["id"]}'), cta_text='Add picks or more players to either side.', ld_extra=[faq_ld(qas)])

# ---- "Should I start X" this-week pages ----
INJ_MULT = {'Out': 0, 'IR': 0, 'PUP': 0, 'Sus': 0, 'Doubtful': 0.25, 'Questionable': 0.85}
CALL_TXT = {'Must start': 'a must start', 'Start': 'a start', 'Flex / matchup': 'a flex or matchup play', 'Sit (deep leagues only)': 'a sit in all but deep leagues'}
SSPAGES = []
for pid, info in SS.items():
    p = info['p']; pos = p['pos']; nm = E(p['n']); pj = p['proj']; rank, of, tier = info['rank'], info['of'], info['tier']
    inj = p.get('inj'); st = inj or 'Active'
    l3 = p.get('l3') or {}; ppr = ppg_of(p)
    # start score: same blend as calc.js startScore (50% projection, 25% last 3, 25% season PPG, x injury factor)
    parts = [(0.5, pj.get('ppr')), (0.25, l3.get('ppr')), (0.25, ppr)]
    w = sum(x for x, v in parts if v is not None); base = sum(x * v for x, v in parts if v is not None) / w
    score = jround(base * INJ_MULT.get(inj, 1) * 10) / 10
    near = [q for q in ssrows([pos], 10 ** 6)][max(0, rank - 3):rank + 2]
    near_rows = ''.join(f'<tr><td>{ssrows([pos], 10**6).index(q)+1}</td><td>{ss_link(q)}</td><td>{q["proj"]["ppr"]}</td><td>{E(q.get("inj") or "Active")}</td></tr>' for q in near)
    inj_txt = f' He is listed as {inj}, so check status before kickoff.' if inj else ' He has no injury designation.'
    qas = [(f'Should I start {p["n"]} in Week {WEEK}?', f'The data puts {p["n"]} at {pos}{rank} of {of} projected {pos}s this week ({pj["ppr"]} PPR points projected), which the {pos} start/sit page labels "{tier}".' + inj_txt),
           (f'What is {p["n"]}\'s Week {WEEK} projection?', f'{pj["ppr"]} points in PPR, {pj.get("half","—")} in half PPR and {pj.get("std","—")} in standard, from Sleeper\'s public projections as of {genh}.'),
           (f'How is {p["n"]} scoring this season?', (f'He averages {ppr} PPR points per game' + (f' over {p["gp"]} games' if p.get('gp') else '') + (f' and {l3["ppr"]} over his last {l3.get("g",3)}' if l3.get('ppr') is not None else '') + '.') if ppr is not None else f'He has no {SEASON} points-per-game yet.')]
    if pid in PLAYER_PAGES: qas.append((f'What is {p["n"]}\'s dynasty value?', f'His composite dynasty value is {p["v1"]:,} in 1QB leagues (#{one_rank[pid]} overall) and {(p.get("v2") or p["v1"]):,} in superflex. See his dynasty value page for the breakdown.'))
    title = fit([f'Should I Start {p["n"]}? Week {WEEK} Start/Sit ({SEASON})', f'Should I Start {p["n"]}? Week {WEEK} Start/Sit', f'Start or Sit {p["n"]}? Week {WEEK}'], 20, 65)
    cmpl = ''.join(f'<li><a href="../{s}/">{nm} vs {E(o["n"])} dynasty</a></li>' for s, o in CMP_BY.get(pid, []))
    SSPAGES.append((p, info))
    write(info['slug'], 'Start or sit', f'Start or sit {p["n"]}', title,
          fit([f'Week {WEEK} start/sit for {p["n"]}: {pj["ppr"]} projected PPR points, {pos}{rank} this week, injury status and a plain call. Updated {genh}.', f'{p["n"]} Week {WEEK} start/sit: {pj["ppr"]} projected PPR points, {pos}{rank}, injury status. Updated {genh}.'], 70, 155),
          f'Should I start {nm} in Week {WEEK}?', f'{pos}, {E(p.get("team") or "FA")}. Week {WEEK} projection, ranking and call.',
          f'Week {WEEK} call on {nm}: <strong>{tier.lower()}</strong>. <strong>{pj["ppr"]}</strong> projected PPR points, {pos}{rank} of {of} projected {pos}s, status {E(st)}.',
          f'''<div class="stats s3"><div class="stat"><div class="k">Proj (PPR)</div><div class="v">{pj["ppr"]}</div></div><div class="stat"><div class="k">Rank this week</div><div class="v">{pos}{rank}</div></div><div class="stat"><div class="k">Call</div><div class="v">{E(tier)}</div></div><div class="stat"><div class="k">Status</div><div class="v">{E(st)}</div></div><div class="stat"><div class="k">PPR PPG ({SEASON})</div><div class="v">{fmtn(ppr)}</div></div><div class="stat"><div class="k">Start score</div><div class="v">{score}</div></div></div>
<h2>How the call works</h2>
<div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Input</th><th scope="col">Value</th><th scope="col">Weight</th></tr></thead><tbody>
<tr><th scope="row" style="text-align:left">Week {WEEK} projection (PPR)</th><td>{pj["ppr"]}</td><td>50%</td></tr>
<tr><th scope="row" style="text-align:left">Last 3 games (PPR)</th><td>{fmtn(l3.get("ppr"))}</td><td>25%</td></tr>
<tr><th scope="row" style="text-align:left">Season PPG (PPR)</th><td>{fmtn(ppr)}</td><td>25%</td></tr>
<tr><th scope="row" style="text-align:left">Injury factor ({E(st)})</th><td>×{INJ_MULT.get(inj, 1)}</td><td></td></tr>
<tr><th scope="row" style="text-align:left">Start score</th><td><b>{score}</b></td><td></td></tr></tbody></table></div>
<p>The call uses the same tier rule as the <a href="../start-sit-{pos.lower()}/">Week {WEEK} {pos} start/sit rankings</a>: players are ranked by projection, and the top fifth of the list is a must start, then start, then flex/matchup, then sit in all but deep leagues. At {pos}{rank} that makes {nm} {CALL_TXT[tier]}. Players ruled out are left out of the ranking.</p>
<h2>{pos}s ranked near {nm}</h2><div class="table-scroll"><table><thead><tr><th scope="col">Rank</th><th scope="col">Player</th><th scope="col">Proj (PPR)</th><th scope="col">Status</th></tr></thead><tbody>{near_rows}</tbody></table></div>
{faq_html(qas)}
<p class="hint">This is data, not betting advice or a guarantee. Projections come from Sleeper’s public API and can change before kickoff; injury statuses change late in the week.</p>
<h2>Related pages</h2><ul>{('<li><a href="../' + vslug(p) + '/">' + nm + ' dynasty value</a></li>') if pid in PLAYER_PAGES else ''}{cmpl}<li><a href="../week-{WEEK}-start-sit/">Week {WEEK} start/sit cheat sheet</a></li><li><a href="../start-or-sit-players/">All start-or-sit player pages</a></li><li><a href="../injury-report/">Injury report</a></li></ul>
<p class="hint">Projections from Sleeper’s public API; production from nflverse (CC BY 4.0). Updated {genh}. <a href="../how-our-values-work/">How the start score works</a>.</p>''',
          cta=('Compare two players', ''), cta_text='Who should I start? Compare up to 4 players.', ld_extra=[faq_ld(qas)])

# ---- stable URLs: players without a call this week (bye, ruled out, no projection) keep their start-or-sit page ----
# (top-150 skill players, plus any start-or-sit page generated before, so links and search results never hit a 404)
SSOFF = []
if WEEK:
    _by_slug = {'start-or-sit-' + slugify(q['n']): q for q in players if q['pos'] in SSN}
    _prev = {d.name for d in ROOT.iterdir() if d.is_dir() and d.name.startswith('start-or-sit-') and d.name != 'start-or-sit-players' and (d / '.generated').exists()}
    _cand = {('start-or-sit-' + slugify(q['n'])): q for q in valued[:150] if q['pos'] in SSN}
    _cand.update({sl: _by_slug[sl] for sl in _prev if sl in _by_slug})
    _done = {i['slug'] for i in SS.values()}
    for slug, p in sorted(_cand.items()):
        if slug in _done or p['id'] in SS: continue
        nm = E(p['n']); pos = p['pos']; inj = p.get('inj'); pj = p.get('proj') or {}
        if inj in ('Out', 'IR', 'PUP', 'Sus'):
            why = f'he is listed as {inj}'; call = 'Do not start him'
        elif not pj:
            why = f'Sleeper has no Week {WEEK} projection for him (usually a bye week, an inactive player or a backup)'; call = 'Leave him on your bench unless news changes'
        else:
            why = f'his Week {WEEK} projection ({pj.get("ppr")} PPR) is outside the top {SSLIM[pos]} {pos}s'; call = 'He is a sit in most leagues'
        ppr = ppg_of(p)
        qas = [(f'Should I start {p["n"]} in Week {WEEK}?', f'{call}: {why}. Check the injury report before kickoff, since statuses change late in the week.'),
               (f'How is {p["n"]} scoring this season?', f'He averages {ppr} PPR points per game' + (f' over {p["gp"]} games.' if p.get('gp') else '.') if ppr is not None else f'We have no {SEASON} scoring data for him yet.')]
        if p['id'] in PLAYER_PAGES: qas.append((f'What is {p["n"]}\'s dynasty value?', f'{p["v1"]:,} in 1QB leagues (#{one_rank[p["id"]]} overall) and {(p.get("v2") or p["v1"]):,} in superflex, as of {genh}.'))
        SSOFF.append(slug)
        write(slug, 'Start or sit', f'Start or sit {p["n"]}', fit([f'Should I Start {p["n"]}? Week {WEEK} Start/Sit ({SEASON})', f'Should I Start {p["n"]}? Week {WEEK}', f'Start or Sit {p["n"]}?'], 20, 65),
              fit([f'Should you start {p["n"]} in Week {WEEK}? {call}: {why[:60]}. Status, season PPG and who to start instead. Updated {genh}.', f'Week {WEEK} start/sit for {p["n"]}: {call.lower()}. Status and who to start instead. Updated {genh}.'], 70, 155),
              f'Should I start {nm} in Week {WEEK}?', f'{pos}, {E(p.get("team") or "FA")}. No start call this week.',
              f'<strong>{E(call)}</strong> in Week {WEEK}: {E(why)}.',
              f'''<div class="stats s3"><div class="stat"><div class="k">Status</div><div class="v">{E(inj or "Active")}</div></div><div class="stat"><div class="k">Week {WEEK} projection</div><div class="v">{fmtn(pj.get("ppr"))}</div></div><div class="stat"><div class="k">PPR PPG ({SEASON})</div><div class="v">{fmtn(ppr)}</div></div></div>
<h2>Who to start instead</h2><p>The top projected {pos}s this week are on the <a href="../start-sit-{pos.lower()}/">Week {WEEK} {pos} start/sit rankings</a>; for a quick look at every position see the <a href="../week-{WEEK}-start-sit/">Week {WEEK} cheat sheet</a>, or compare two players in the <a href="../start-sit/">start/sit tool</a>.</p>
{faq_html(qas)}
<p class="hint">This is data, not betting advice or a guarantee. Projections and injury statuses come from Sleeper’s public API, updated {genh}, and can change before kickoff.</p>
<h2>Related pages</h2><ul>{('<li><a href="../' + vslug(p) + '/">' + nm + ' dynasty value</a></li>') if p['id'] in PLAYER_PAGES else ''}<li><a href="../injury-report/">Injury report</a></li><li><a href="../start-or-sit-players/">All start-or-sit player pages</a></li></ul>''',
              cta=('Compare two players', ''), cta_text='Who should I start? Compare up to 4 players.', ld_extra=[faq_ld(qas)])

# ---- family hubs ----
rows_html = lambda ps: '<div class="table-scroll"><table><thead><tr><th scope="col">#</th><th scope="col">Player</th><th scope="col">Pos</th><th scope="col">Age</th><th scope="col">1QB</th><th scope="col">SF</th></tr></thead><tbody>' + ''.join(f'<tr><td>{one_rank[p["id"]]}</td><td><a href="../{vslug(p)}/">{E(p["n"])}</a> <span class="hint" style="display:inline">{p.get("team") or "FA"}</span></td><td>{tag(p["pos"])}</td><td>{p.get("age") or "—"}</td><td>{p["v1"]:,}</td><td>{(p.get("v2") or p["v1"]):,}</td></tr>' for p in ps) + '</tbody></table></div>'
write('dynasty-player-values', 'Dynasty rankings', 'Player dynasty values (top 250)', f'Dynasty Player Values {SEASON}: Top {N_VALUE_PAGES} Trade Values',
      f'Dynasty trade value pages for the top {N_VALUE_PAGES} players: 1QB and superflex values, ages and positional rank. Updated {genh}.',
      f'Dynasty player values {SEASON}', f'One page per player for the top {N_VALUE_PAGES} by open dynasty value, each with comparable trades.',
      f'The top {N_VALUE_PAGES} dynasty players run from <strong>{E(valued[0]["n"])}</strong> ({valued[0]["v1"]:,}) down to {E(valued[N_VALUE_PAGES-1]["n"])} ({valued[N_VALUE_PAGES-1]["v1"]:,}) in 1QB value, as of {genh}.',
      rows_html(valued[:N_VALUE_PAGES]) + SRC + '<p>Related: <a href="../dynasty-player-comparisons/">player vs player comparisons</a>, <a href="../dynasty-trade-value-chart/">trade value chart</a>' + (', <a href="../start-or-sit-players/">start or sit this week</a>' if SS else '') + '.</p>', ld_extra=[itemlist(valued[:N_VALUE_PAGES], 'Dynasty player values')])
if CMPS:
    cb = ''
    for pos in ('QB', 'RB', 'WR', 'TE'):
        ps = [(a, b) for a, b in CMPS if a['pos'] == pos]
        if ps: cb += f'<h2>{pos} comparisons</h2><div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Comparison</th><th scope="col">1QB values</th><th scope="col">Verdict</th></tr></thead><tbody>' + ''.join(f'<tr><td style="text-align:left"><a href="../{cslug(a, b)}/">{E(a["n"])} vs {E(b["n"])}</a></td><td>{a["v1"]:,} / {b["v1"]:,}</td><td>{"Fair" if trade_calc([a["v1"]], [b["v1"]])["fair"] else "Favors " + E(a["n"])}</td></tr>' for a, b in ps) + '</tbody></table></div>'
    write('dynasty-player-comparisons', 'Dynasty rankings', 'Player vs player dynasty', f'Dynasty Player Comparisons {SEASON}: X vs Y Trade Values',
          f'{len(CMPS)} "X vs Y" dynasty comparisons of close players at the same position, with values, ages, PPG and fair-trade verdicts. Updated {genh}.',
          f'Dynasty player comparisons {SEASON}', 'Each top player against the next two at his position, with a trade verdict from the calculator’s rule.',
          f'{len(CMPS)} close pairs are compared, and <strong>{sum(1 for a, b in CMPS if trade_calc([a["v1"]], [b["v1"]])["fair"])}</strong> of them are fair straight-up trades (within 5%) in 1QB leagues as of {genh}.',
          cb + SRC + '<p>All player values: <a href="../dynasty-player-values/">top 250</a>. Compare any two players in the <a href="../#trade">trade calculator</a>.</p>', featured=True)
if SSPAGES:
    sb = ''
    for pos in ('QB', 'RB', 'WR', 'TE'):
        ps = [(p, i) for p, i in SSPAGES if p['pos'] == pos]
        if ps: sb += f'<h2>{pos}: Week {WEEK} start or sit</h2><div class="table-scroll"><table><thead><tr><th scope="col">Rank</th><th scope="col" style="text-align:left">Player</th><th scope="col">Proj (PPR)</th><th scope="col">Status</th><th scope="col">Call</th></tr></thead><tbody>' + ''.join(f'<tr><td>{i["rank"]}</td><td style="text-align:left"><a href="../{i["slug"]}/">{E(p["n"])}</a> <span class="hint" style="display:inline">{p.get("team") or "FA"}</span></td><td>{p["proj"]["ppr"]}</td><td>{E(p.get("inj") or "Active")}</td><td>{i["tier"]}</td></tr>' for p, i in sorted(ps, key=lambda x: x[1]['rank'])) + '</tbody></table></div>'
    top = max(SSPAGES, key=lambda x: x[0]['proj']['ppr'])[0]
    write('start-or-sit-players', 'Weekly start/sit', 'Start or sit: player pages', f'Should I Start...? Week {WEEK} Start or Sit by Player ({SEASON})',
          f'Week {WEEK} start or sit pages for {len(SSPAGES)} QBs, RBs, WRs and TEs with PPR projections, injury status and a plain call. Updated {genh}.',
          f'Week {WEEK} start or sit: every player', 'Pick a player to see this week’s projection, positional rank, injury status and call.',
          f'{len(SSPAGES)} players have a Week {WEEK} start-or-sit page; the highest projection is <strong>{E(top["n"])}</strong> at {top["proj"]["ppr"]} PPR points. Data, not betting advice.',
          sb + f'<p class="hint">Projections from Sleeper’s public API, updated {genh}. Players ruled out and players without a projection (bye or inactive) have no page. Also see the <a href="../week-{WEEK}-start-sit/">Week {WEEK} cheat sheet</a>.</p>', cta=('Compare two players', ''), cta_text='Who should I start? Compare up to 4 players.', featured=True)
# ---- blog (content/blog/*.md -> blog/) ----
ARTS = BLOG.build(ROOT, S, gen, genh)
# ---- hub ----
statics = S['statics']; allp = statics + PAGES
order = S['sections'] + [s for s in ['Dynasty rankings', 'Dynasty movers', 'Rest of season', 'Weekly rankings', 'Weekly start/sit', 'Player values', 'Player comparisons', 'Start or sit'] if s not in S['sections']]
body = ''
for sec in order:
    ps = [p for p in allp if p['section'] == sec]
    if not ps: continue
    if sec in ('Player comparisons', 'Start or sit'):
        hub_slug, lab = ('dynasty-player-comparisons', 'Dynasty player comparisons ("X vs Y")') if sec == 'Player comparisons' else ('start-or-sit-players', f'Week {WEEK} start or sit by player')
        body += f'<h2>{E(sec)}</h2><div class="guide-grid"><a class="gcard" href="../{hub_slug}/"><b>{lab}</b><span>{len(ps)} pages: see the full list.</span></a></div>'
    elif sec == 'Player values':
        body += f'<h2>{E(sec)}</h2><p class="hint">Top {N_VALUE_PAGES} players by dynasty value (<a href="../dynasty-player-values/">table view</a>).</p><ul class="cols">' + ''.join(f'<li><a href="../{p["slug"]}/">{E(p["nav"].replace(" dynasty value",""))}</a></li>' for p in ps) + '</ul>'
    else:
        body += f'<h2>{E(sec)}</h2><div class="guide-grid">' + ''.join(f'<a class="gcard" href="../{p["slug"]}/"><b>{E(p["nav"])}</b><span>{E(p["desc"][:120])}</span></a>' for p in ps) + '</div>'
if ARTS: body = f'<h2>Latest articles</h2>{BLOG.cards(ARTS, "../", 6)}<p><a href="../blog/">All articles →</a></p>' + body
PAGES_BEFORE = len(PAGES)
write('guides', 'Guides', 'All guides', f'All guides | {NAME}', f'Every {NAME} page: weekly start/sit rankings, dynasty rankings, trade value chart, pick values, player values and guides.',
      f'{NAME} guides & rankings', 'Rankings, trade values and start/sit calls, fresh every day.', f'{len(allp)} pages. Values as of {genh}.', body, changefreq='daily')
PAGES.pop()
# ---- sitemap: statics + generated + guides + glossary ----
ent = [('', '1.0', 'daily')] + [(t + '/', '0.9', 'daily') for t in TOOLS] + [(p['slug'] + '/', '0.7' if p.get('featured') else '0.6', p.get('changefreq', 'monthly')) for p in statics] + [(p['slug'] + '/', '0.7' if p.get('featured') else '0.5', p['changefreq']) for p in PAGES] + ([('blog/', '0.7', 'daily')] + [(f'blog/{a["slug"]}/', '0.6', 'monthly') for a in ARTS] if ARTS else []) + [('guides/', '0.5', 'daily'), ('glossary/', '0.4', 'monthly')] + [(f, '0.3', 'yearly') for f in ('privacy.html', 'terms.html', 'about.html', 'contact.html')]
LMS = S.get('lastmod', {}); DATA = {p['slug'] + '/' for p in PAGES} | {'', 'guides/', 'blog/'}  # static pages keep their real last-changed date (from the main build)
ALM = {f'blog/{a["slug"]}/': (a.get('updated') or a['date']) for a in ARTS}
(ROOT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'  <url><loc>{URL}{s}</loc><lastmod>{ALM[s] if s in ALM else (gen if s in DATA else LMS.get(s, gen))}</lastmod><changefreq>{cf}</changefreq><priority>{p}</priority></url>\n' for s, p, cf in ent) + '</urlset>\n')
# ---- llms.txt: append the data-page families (idempotent: replaces the previous block) ----
_lf = ROOT / 'llms.txt'
if _lf.exists():
    _base = re.sub(r'\n## Data pages \(updated daily\).*', '', _lf.read_text(), flags=re.S).rstrip('\n')
    _fam = [('dynasty-rankings', 'Dynasty rankings 1QB'), ('dynasty-rankings-superflex', 'Superflex rankings'), ('dynasty-trade-value-chart', 'Trade value chart'), ('rookie-draft-pick-values', 'Rookie pick values'),
            ('dynasty-player-values', 'Every player value page'), ('dynasty-player-comparisons', 'Player vs player comparisons'), ('start-or-sit-players', 'Start or sit by player (this week)'), (f'week-{WEEK}-start-sit', f'Week {WEEK} start/sit cheat sheet')] + [(RK_SLUGS[k], f'Week {WEEK} {RK_NAME[k][0]} rankings') for k in RK_KEYS if k in RK_SLUGS] + [('injury-report', 'Injury report'), ('waiver-wire-trending', 'Trending waiver adds'), ('rest-of-season-rankings', 'Rest of season rankings'), ('dynasty-buy-low-sell-high', 'Dynasty buy-low/sell-high targets'), ('dynasty-value-risers-fallers', 'Dynasty value risers and fallers'), ('dynasty-rookie-rankings', 'Dynasty rookie rankings'), (f'week-{WEEK}-waiver-wire', f'Week {WEEK} waiver wire pickups')]
    _have = {p['slug'] for p in PAGES}
    _txt = f'\n\n## Data pages (updated daily)\nData as of {genh}. Each player has a dynasty value page at {URL}dynasty-value-<player-name>/ and, in season, a start-or-sit page at {URL}start-or-sit-<player-name>/.\n' + ''.join(f'- [{n}]({URL}{sl}/)\n' for sl, n in _fam if sl in _have)
    _txt += '\n### Top player value pages\n' + ''.join(f'- [{q["n"]} dynasty value]({URL}{vslug(q)}/): #{one_rank[q["id"]]} 1QB, {q["v1"]:,}\n' for q in valued[:50])
    if ARTS: _txt += '\n## Blog (data-driven articles by DynastyMath Staff)\n' + f'- [Blog index]({URL}blog/) · [RSS feed]({URL}blog/feed.xml)\n' + ''.join(f'- [{a["title"]}]({URL}blog/{a["slug"]}/): {a["description"]} (published {a["date"]}, numbers as of {a.get("data_as_of") or a["date"]})\n' for a in ARTS)
    _lf.write_text(_base + _txt)
# remove stale generated folders (e.g. a player who dropped out of the top 150)
keep = {p['slug'] for p in allp} | {'guides', 'glossary', 'blog'} | set(TOOLS) | set(OLDWEEKS)
for d in ROOT.iterdir():
    if d.is_dir() and (d / '.generated').exists() and d.name not in keep: shutil.rmtree(d)
(ROOT / 'data' / 'pages.json').write_text(json.dumps([{k: p[k] for k in ('slug', 'section', 'nav')} for p in PAGES]))
print(f'fantasy data pages: {len(PAGES)} generated + {len(statics)} static + guides/glossary; total URLs in sitemap {len(ent)}')
# ---- link this week's pages from the hub, start/sit and waiver pages (idempotent; refreshed daily) ----
if WEEK and (ROOT / f'week-{WEEK}-start-sit').exists():
    def _wk(pre):
        w = f'<a href="{pre}week-{WEEK}-waiver-wire/"><strong>Week {WEEK} waiver wire</strong> (trending adds by position) →</a>' if (ROOT / WAIVER_SLUG).exists() else ''
        ex = ' · '.join(f'<a href="{pre}{s}/">{l}</a>' for s, l in [('rest-of-season-rankings', 'Rest of season rankings'), ('dynasty-buy-low-sell-high', 'Dynasty buy-low/sell-high'), ('dynasty-rookie-rankings', 'Rookie rankings')] if (ROOT / s).exists())
        rk = f'<p class="hint" style="margin:6px 0 0"><strong>This week’s rankings:</strong> {rk_block(pre)}</p>' if RK_SLUGS else ''
        return f'<!--wk--><p class="hint" style="margin:10px 0 0"><a href="{pre}week-{WEEK}-start-sit/"><strong>Week {WEEK} start/sit cheat sheet</strong> (every position, one page) →</a>' + (' · ' + w if w else '') + '</p>' + rk + (f'<p class="hint" style="margin:6px 0 0">{ex}</p>' if ex else '') + '<!--/wk-->'
    for rel, pre in [('index.html', ''), ('start-sit/index.html', '../'), ('waiver-wire/index.html', '../'), ('waiver-wire-trending/index.html', '../'), ('trade-analyzer/index.html', '../'), ('guides/index.html', '../'), (f'week-{WEEK}-start-sit/index.html', '../'), (f'{WAIVER_SLUG}/index.html', '../')] + [(f'rest-of-season-{k}rankings/index.html', '../') for k in ('', 'qb-', 'rb-', 'wr-', 'te-')]:
        f = ROOT / rel
        if not f.exists(): continue
        h = re.sub(r'<!--wk-->.*?<!--/wk-->', '', f.read_text(), flags=re.S)
        if rel == 'index.html': h = re.sub(r'(<p class="lede">.*?</p>)', lambda m: m.group(1) + _wk(pre), h, count=1, flags=re.S); f.write_text(h); continue
        h = h.replace('<main id="main"><div class="wrap">', '<main id="main"><div class="wrap">' + _wk(pre), 1)
        f.write_text(h)
# ---- blog entry points on every page: nav + footer links, and a "Latest articles" block on the home page (idempotent) ----
if ARTS:
    NAV_RE = re.compile(r'(<a href="((?:\.\./)*|/)guides/" class="hide-sm">Guides</a>)(?!<a href="[^"]*blog/")')
    FOOT_RE = re.compile(r'(?<!>Blog</a></li>)(<li><a href="((?:\.\./)*|/)guides/">All guides →</a></li>)')
    for f in list(ROOT.glob('*.html')) + list(ROOT.glob('*/index.html')) + list(ROOT.glob('blog/*/index.html')):
        h = f.read_text(); o = h
        h = NAV_RE.sub(lambda m: m.group(1) + f'<a href="{m.group(2)}blog/" class="hide-sm">Blog</a>', h)
        h = FOOT_RE.sub(lambda m: f'<li><a href="{m.group(2)}blog/">Blog</a></li>' + m.group(1), h)
        h = re.sub(r'(<li><a href="[^"]*blog/">Blog</a></li>)+', lambda m: m.group(0)[:m.group(0).index('</li>') + 5], h)
        if f.name == 'index.html' and f.parent == ROOT:
            h = re.sub(r'<!--blog-->.*?<!--/blog-->', '', h, flags=re.S)
            h = re.sub(r'<link rel="alternate" type="application/rss\+xml"[^>]*>', '', h)
            h = h.replace('<link rel="alternate" type="text/plain"', f'<link rel="alternate" type="application/rss+xml" title="{NAME} blog" href="blog/feed.xml"><link rel="alternate" type="text/plain"', 1)
            blk = f'<!--blog--><section aria-labelledby="blh"><div class="sec-head"><h2 id="blh">Latest articles</h2><a href="blog/">All articles →</a></div>{BLOG.cards(ARTS, "", 3)}</section><!--/blog-->'
            h = h.replace('<section class="prose" id="how">', blk + '<section class="prose" id="how">', 1)
        if h != o: f.write_text(h)
