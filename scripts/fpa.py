"""Fantasy points allowed by position, from nflverse weekly player stats (PPR).
load() returns {'season', 'weeks', 'teams': {TEAM: {'QB': [avg, games], ...}}} and caches it in data/fantasy-points-allowed.json.
If the download fails the last cached data is used; None if there is none."""
import csv, io, json, pathlib, urllib.request
from collections import defaultdict
ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / 'data' / 'fantasy-points-allowed.json'
URLS = ['https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{s}.csv',
        'https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats_{s}.csv']
POS = ('QB', 'RB', 'WR', 'TE')

def compute(text, season):
    pts = defaultdict(float)   # (team, week, pos) -> PPR points allowed
    games = defaultdict(set)   # team -> weeks played
    for r in csv.DictReader(io.StringIO(text)):
        if (r.get('season_type') or 'REG') != 'REG' or r.get('position') not in POS: continue
        opp = r.get('opponent_team'); wk = r.get('week')
        if not opp or not wk: continue
        try: pts[(opp, int(wk), r['position'])] += float(r.get('fantasy_points_ppr') or 0)
        except ValueError: continue
        games[opp].add(int(wk))
    teams = {}
    for t, wks in games.items():
        teams[t] = {p: [round(sum(pts[(t, w, p)] for w in wks) / len(wks), 1), len(wks)] for p in POS}
    weeks = max((w for ws in games.values() for w in ws), default=0)
    return {'season': season, 'weeks': weeks, 'teams': teams}

def load(season):
    for u in URLS:
        try:
            with urllib.request.urlopen(urllib.request.Request(u.format(s=season), headers={'User-Agent': 'dynastymath-build'}), timeout=60) as f:
                d = compute(f.read().decode('utf-8'), season)
            if len(d['teams']) >= 28 and d['weeks'] >= 1:
                CACHE.write_text(json.dumps(d, separators=(',', ':')))
                return d
        except Exception as e:
            print(f'fantasy points allowed: download failed ({e})')
    try:
        d = json.loads(CACHE.read_text())
        return d if d.get('season') == season and d.get('teams') else None
    except Exception:
        return None
