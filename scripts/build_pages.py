#!/usr/bin/env python3
"""Generate DynastyMath data pages (weekly start/sit, dynasty rankings, pick values, player value pages,
injury report, trending adds), the guides hub and sitemap.xml from data/players.json.
Uses scripts/shell.json (page template written by the main build). Runs daily in GitHub Actions after refresh-data.mjs."""
import json, html, pathlib, re, datetime, shutil
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
PLAYER_PAGES = {p['id'] for p in valued[:150]}

# ---- dynasty rankings ----
write('dynasty-rankings', 'Dynasty rankings', f'Dynasty rankings {SEASON}', f'Dynasty Rankings {SEASON} (1QB): Top 150 Trade Values, Updated Daily',
      f'Top 150 dynasty fantasy football rankings for 1QB leagues with trade values, ages and points per game. Updated {genh}.',
      f'Dynasty rankings {SEASON} (1QB)', 'The top 150 players by open dynasty trade value for single-QB leagues, refreshed every day.',
      f'The top dynasty asset in 1QB leagues right now is <strong>{E(valued[0]["n"])}</strong> ({valued[0]["pos"]}, {valued[0].get("team") or "FA"}), followed by {E(valued[1]["n"])} and {E(valued[2]["n"])}. Rankings are by DynastyProcess value, updated {genh}.',
      table(valued, n=150) + SRC + '<p>Superflex league? See <a href="../dynasty-rankings-superflex/">superflex rankings</a>. By position: <a href="../dynasty-qb-rankings/">QB</a> · <a href="../dynasty-rb-rankings/">RB</a> · <a href="../dynasty-wr-rankings/">WR</a> · <a href="../dynasty-te-rankings/">TE</a>.</p>',
      ld_extra=[itemlist(valued[:150], 'Dynasty rankings 1QB')], featured=True)
write('dynasty-rankings-superflex', 'Dynasty rankings', f'Superflex rankings {SEASON}', f'Superflex Dynasty Rankings {SEASON}: Top 150 SF Values',
      f'Top 150 superflex dynasty rankings with SF trade values, ages and PPG, updated {genh}. Quarterbacks move way up in 2QB formats.',
      f'Superflex dynasty rankings {SEASON}', 'Top 150 by superflex (2QB) dynasty value, refreshed daily.',
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
      'Dynasty rookie draft pick values', 'Future picks valued on the same scale as players, so you can trade picks for players with confidence.',
      (f'A {E(picks[0]["n"])} is worth about {picks[0]["v1"]:,} in 1QB ({(picks[0].get("v2") or picks[0]["v1"]):,} superflex), similar to {E(eq[0][1]["n"])}.' if picks else 'Pick values load with the next data refresh.'),
      '<div class="table-scroll"><table><thead><tr><th scope="col">Pick</th><th scope="col">1QB value</th><th scope="col">SF value</th><th scope="col">Similar player (1QB)</th></tr></thead><tbody>' + ''.join(f'<tr><td>{tag("PICK")} {E(pk["n"])}</td><td>{pk["v1"]:,}</td><td>{(pk.get("v2") or pk["v1"]):,}</td><td>{E(n["n"])} ({n["pos"]})</td></tr>' for pk, n in eq) + '</tbody></table></div>' + SRC + '<p>Add picks to either side in the <a href="../#trade">trade calculator</a>.</p>', featured=True)
chart_rows = valued[:60]
write('dynasty-trade-value-chart', 'Dynasty rankings', 'Trade value chart', f'Dynasty Trade Value Chart {SEASON} (Updated Daily): 1QB & Superflex',
      f'Dynasty fantasy football trade value chart with 1QB and superflex values for the top players and picks, updated {genh}.',
      f'Dynasty trade value chart {SEASON}', 'Players and picks on one scale. Add up each side to see who wins a trade, or use the calculator, which also discounts 2-for-1 deals.',
      f'Use the chart by adding up the values on each side of a trade. Within about 5% is a fair trade. Packages of several smaller pieces are worth less than the sum, so the <a href="../#trade">calculator</a> discounts extra pieces.',
      '<div class="table-scroll"><table><thead><tr><th scope="col">Player / pick</th><th scope="col">1QB</th><th scope="col">SF</th></tr></thead><tbody>' + ''.join(f'<tr><td>{tag(p["pos"])} {E(p["n"])}</td><td>{p["v1"]:,}</td><td>{(p.get("v2") or p["v1"]):,}</td></tr>' for p in sorted(chart_rows + picks[:12], key=lambda p: -p['v1'])) + '</tbody></table></div>' + SRC, featured=True)
# ---- weekly start/sit ----
def ssrows(pos_list, n):
    rows = sorted([p for p in players if p.get('proj') and p['pos'] in pos_list and not (p.get('inj') in ('Out', 'IR', 'PUP', 'Sus'))], key=lambda p: -p['proj']['ppr'])[:n]
    return rows
if WEEK:
    for key, pos_list, n, lab in [('qb', ['QB'], 32, 'QB'), ('rb', ['RB'], 50, 'RB'), ('wr', ['WR'], 60, 'WR'), ('te', ['TE'], 30, 'TE'), ('flex', ['RB', 'WR', 'TE'], 100, 'Flex')]:
        rows = ssrows(pos_list, n)
        if not rows: continue
        tiers = lambda i: 'Must start' if i < (n // 5) else ('Start' if i < (n * 2 // 5) else ('Flex / matchup' if i < (n * 3 // 5) else 'Sit (deep leagues only)'))
        body = '<div class="table-scroll"><table><thead><tr><th scope="col">#</th><th scope="col">Player</th><th scope="col">Proj (PPR)</th><th scope="col">Half</th><th scope="col">PPG so far</th><th scope="col">Status</th><th scope="col">Call</th></tr></thead><tbody>' + ''.join(
            f'<tr><td>{i+1}</td><td>{tag(p["pos"])} {E(p["n"])} <span class="hint" style="display:inline">{p.get("team") or ""}</span></td><td><b>{p["proj"]["ppr"]}</b></td><td>{p["proj"].get("half","—")}</td><td>{(p.get("ppg") or {}).get("ppr","—")}</td><td>{E(p.get("inj") or "Active")}</td><td>{tiers(i)}</td></tr>' for i, p in enumerate(rows)) + '</tbody></table></div>'
        write(f'start-sit-{key}', 'Weekly start/sit', f'Week {WEEK} {lab} start/sit', f'Week {WEEK} {lab} Start/Sit Rankings ({SEASON}): Who to Start at {lab}',
              f'Week {WEEK} fantasy football {lab} rankings with PPR projections, injury status and start/sit calls. Updated {genh}.',
              f'Week {WEEK} {lab} start/sit rankings', f'Every {lab} ranked by Week {WEEK} PPR projection, with injury status and a plain start/sit call.',
              f'Top Week {WEEK} {lab} plays: <strong>{E(rows[0]["n"])}</strong> ({rows[0]["proj"]["ppr"]} projected PPR), {E(rows[1]["n"])} and {E(rows[2]["n"])}. Players ruled out are excluded.',
              body + f'<p class="hint">Projections from Sleeper’s public API, updated {genh}. Injury statuses change late in the week; check before kickoff.</p><p>Deciding between two players? Use the <a href="../#tool">start/sit tool</a>. Other positions: ' + ' · '.join(f'<a href="../start-sit-{k}/">{l}</a>' for k, l in [('qb', 'QB'), ('rb', 'RB'), ('wr', 'WR'), ('te', 'TE'), ('flex', 'Flex')] if k != key) + '</p>',
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
          f'Week {WEEK} fantasy injury report', 'Current injury designations for fantasy-relevant players, most valuable first.',
          f'{len(inj)} fantasy-relevant players carry an injury designation as of {genh}, including {", ".join(E(p["n"])+" ("+E(p["inj"])+")" for p in inj[:3])}.',
          '<div class="table-scroll"><table><thead><tr><th scope="col">Player</th><th scope="col">Team</th><th scope="col">Status</th><th scope="col">PPR PPG</th></tr></thead><tbody>' + ''.join(f'<tr><td>{tag(p["pos"])} {E(p["n"])}</td><td>{p.get("team") or "FA"}</td><td>{E(p["inj"])}</td><td>{(p.get("ppg") or {}).get("ppr","—")}</td></tr>' for p in inj[:80]) + '</tbody></table></div><p class="hint">Source: Sleeper public API. Statuses can change after this page updates.</p>',
          cta=('Check a start/sit', ''))
tr = sorted([p for p in players if (p.get('trend') or 0) > 0], key=lambda p: -p['trend'])[:40]
if tr:
    write('waiver-wire-trending', 'Weekly start/sit', 'Trending waiver adds', f'Week {WEEK} Waiver Wire: Most Added Players in Fantasy Football ({SEASON})',
          f'The most-added players on Sleeper over the last 24 hours, with position, team and PPG. Updated {genh}.',
          f'Week {WEEK} waiver wire: trending adds', 'Who fantasy managers are adding right now, from Sleeper’s public trending data.',
          f'The most-added player right now is <strong>{E(tr[0]["n"])}</strong> ({tr[0]["pos"]}, {tr[0].get("team") or "FA"}), added in {tr[0]["trend"]:,} Sleeper leagues in the last day.',
          '<div class="table-scroll"><table><thead><tr><th scope="col">#</th><th scope="col">Player</th><th scope="col">Adds (24h)</th><th scope="col">PPR PPG</th></tr></thead><tbody>' + ''.join(f'<tr><td>{i+1}</td><td>{tag(p["pos"])} {E(p["n"])} <span class="hint" style="display:inline">{p.get("team") or "FA"}</span></td><td>{p["trend"]:,}</td><td>{(p.get("ppg") or {}).get("ppr","—")}</td></tr>' for i, p in enumerate(tr)) + '</tbody></table></div>')
# ---- player value pages ----
for p in valued[:150]:
    v1, v2 = p['v1'], p.get('v2') or p['v1']
    comps = sorted([q for q in valued if q['id'] != p['id']], key=lambda q: abs(q['v1'] - v1))[:6]
    pk = min(picks, key=lambda q: abs(q['v1'] - v1)) if picks else None
    if pk and abs(pk['v1'] - v1) > 0.2 * v1: pk = None  # only mention a pick when it is genuinely comparable
    nm = E(p['n'])
    write(f'dynasty-value-{slugify(p["n"])}', 'Player values', f'{p["n"]} dynasty value', f'{p["n"]} Dynasty Value {SEASON}: Rank & Trade Comps',
          f'{p["n"]} dynasty value today: #{one_rank[p["id"]]} overall in 1QB, #{sf_rank[p["id"]]} in superflex, {p["pos"]}{pr.get(p["id"])}. Comparable players and picks. Updated {genh}.',
          f'{nm} dynasty trade value', f'{p["pos"]}, {E(p.get("team") or "free agent")}{", age "+str(p["age"]) if p.get("age") else ""}.',
          f'{nm} is the <strong>#{one_rank[p["id"]]}</strong> dynasty asset in 1QB leagues (value {v1:,}) and <strong>#{sf_rank[p["id"]]}</strong> in superflex (value {v2:,}), and the {p["pos"]}{pr.get(p["id"])} at his position, as of {genh}.' + (f' That is roughly the value of a {E(pk["n"])}.' if pk else ''),
          f'''<div class="stats s3"><div class="stat"><div class="k">1QB value</div><div class="v">{v1:,}</div></div><div class="stat"><div class="k">Superflex value</div><div class="v">{v2:,}</div></div><div class="stat"><div class="k">Position rank</div><div class="v">{p["pos"]}{pr.get(p["id"])}</div></div><div class="stat"><div class="k">Age</div><div class="v">{p.get("age") or "—"}</div></div><div class="stat"><div class="k">PPR PPG ({SEASON})</div><div class="v">{(p.get("ppg") or {}).get("ppr","—")}</div></div><div class="stat"><div class="k">Status</div><div class="v">{E(p.get("inj") or "Active")}</div></div></div>
{breakdown(p)}
<h2>Players with similar value</h2><p>Straight-up trades for any of these are roughly fair in 1QB:</p>{table(comps, n=6)}
<p><a class="btn" href="../?a={p["id"]}&b={comps[0]["id"]}#trade">Compare {nm} vs {E(comps[0]["n"])}</a></p>{SRC}''',
          cta=(f'Trade calculator with {p["n"].split(" ")[-1]}', f'?a={p["id"]}'), changefreq='daily')
# ---- hub ----
statics = S['statics']; allp = statics + PAGES
order = S['sections'] + [s for s in ['Dynasty rankings', 'Weekly start/sit', 'Player values'] if s not in S['sections']]
body = ''
for sec in order:
    ps = [p for p in allp if p['section'] == sec]
    if not ps: continue
    if sec == 'Player values':
        body += f'<h2>{E(sec)}</h2><p class="hint">Top 150 players by dynasty value.</p><ul class="cols">' + ''.join(f'<li><a href="../{p["slug"]}/">{E(p["nav"].replace(" dynasty value",""))}</a></li>' for p in ps) + '</ul>'
    else:
        body += f'<h2>{E(sec)}</h2><div class="guide-grid">' + ''.join(f'<a class="gcard" href="../{p["slug"]}/"><b>{E(p["nav"])}</b><span>{E(p["desc"][:120])}</span></a>' for p in ps) + '</div>'
PAGES_BEFORE = len(PAGES)
write('guides', 'Guides', 'All guides', f'All guides | {NAME}', f'Every {NAME} page: weekly start/sit rankings, dynasty rankings, trade value chart, pick values, player values and guides.',
      f'{NAME} guides & rankings', 'Rankings refresh daily from open data.', f'{len(allp)} pages, updated {genh}.', body, changefreq='daily')
PAGES.pop()
# ---- sitemap: statics + generated + guides + glossary ----
ent = [('', '1.0', 'daily')] + [(t + '/', '0.9', 'daily') for t in TOOLS] + [(p['slug'] + '/', '0.7' if p.get('featured') else '0.6', p.get('changefreq', 'monthly')) for p in statics] + [(p['slug'] + '/', '0.7' if p.get('featured') else '0.5', p['changefreq']) for p in PAGES] + [('guides/', '0.5', 'daily'), ('glossary/', '0.4', 'monthly')] + [(f, '0.3', 'yearly') for f in ('privacy.html', 'terms.html', 'about.html', 'contact.html')]
(ROOT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'  <url><loc>{URL}{s}</loc><lastmod>{gen}</lastmod><changefreq>{cf}</changefreq><priority>{p}</priority></url>\n' for s, p, cf in ent) + '</urlset>\n')
# remove stale generated folders (e.g. a player who dropped out of the top 150)
keep = {p['slug'] for p in allp} | {'guides', 'glossary'} | set(TOOLS) | set(OLDWEEKS)
for d in ROOT.iterdir():
    if d.is_dir() and (d / '.generated').exists() and d.name not in keep: shutil.rmtree(d)
(ROOT / 'data' / 'pages.json').write_text(json.dumps([{k: p[k] for k in ('slug', 'section', 'nav')} for p in PAGES]))
print(f'fantasy data pages: {len(PAGES)} generated + {len(statics)} static + guides/glossary; total URLs in sitemap {len(ent)}')
# ---- link this week's cheat sheet from the hub and start/sit pages (idempotent; refreshed daily) ----
if WEEK and (ROOT / f'week-{WEEK}-start-sit').exists():
    for rel, pre in [('index.html', ''), ('start-sit/index.html', '../'), ('waiver-wire/index.html', '../')]:
        f = ROOT / rel
        if not f.exists(): continue
        h = re.sub(r'<!--wk-->.*?<!--/wk-->', '', f.read_text(), flags=re.S)
        lk = f'<!--wk--><p class="hint" style="margin:10px 0 0"><a href="{pre}week-{WEEK}-start-sit/"><strong>Week {WEEK} start/sit cheat sheet</strong> (every position, one page) →</a></p><!--/wk-->'
        if rel == 'index.html': h = re.sub(r'(<p class="lede">.*?</p>)', lambda m: m.group(1) + lk, h, count=1, flags=re.S); f.write_text(h); continue
        h = h.replace('<main id="main"><div class="wrap">', f'<main id="main"><div class="wrap"><!--wk--><p class="hint" style="margin:10px 0 0"><a href="{pre}week-{WEEK}-start-sit/"><strong>Week {WEEK} start/sit cheat sheet</strong> (every position, one page) →</a></p><!--/wk-->', 1)
        f.write_text(h)
