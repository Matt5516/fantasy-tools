#!/usr/bin/env python3
"""One-off: seed data/history.json (daily composite values) from the git history of data/players.json.
build_pages.py keeps appending one snapshot per day after this; run this only to (re)create the seed.
Only snapshots from the composite-value era (players have a 'cs' breakdown) are used, one per calendar date (the last of that date)."""
import json, subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
log = subprocess.check_output(['git', 'log', '--reverse', '--format=%h', '--', 'data/players.json'], cwd=ROOT, text=True).split()
days = {}
for c in log:
    try: D = json.loads(subprocess.check_output(['git', 'show', f'{c}:data/players.json'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL))
    except Exception: continue
    vals = {p['id']: [p['v1'], p.get('v2') or p['v1']] for p in D.get('players', []) if p.get('v1') and p.get('cs')}
    if len(vals) < 100: continue
    days[D['generated'][:10]] = vals
(ROOT / 'data' / 'history.json').write_text(json.dumps({'days': days}, separators=(',', ':')))
print('seeded', sorted(days))
