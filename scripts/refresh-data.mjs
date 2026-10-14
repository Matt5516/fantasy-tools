#!/usr/bin/env node
// Refreshes data/players.json from the free, public Sleeper API (no key needed).
// Run: node scripts/refresh-data.mjs   (Node 18+). Schedule via .github/workflows/refresh.yml.
// Sleeper asks for < 1000 calls/min and that /players/nfl be pulled at most once per day.
// Note: /players/nfl and /players/nfl/trending are documented (https://docs.sleeper.com).
// /stats and /projections are public but undocumented; the script degrades gracefully if they fail.
import { writeFile } from 'node:fs/promises';
const BASE = 'https://api.sleeper.app/v1';
const POS = new Set(['QB', 'RB', 'WR', 'TE']);
async function get(path, optional = false) {
  try {
    const r = await fetch(BASE + path, { headers: { 'User-Agent': 'fantasy-tools-static-refresh' } });
    if (!r.ok) throw new Error(path + ' -> HTTP ' + r.status);
    return await r.json();
  } catch (e) { if (optional) { console.warn('WARN', e.message); return null; } throw e; }
}
const r1 = n => Math.round(n * 10) / 10;
const state = await get('/state/nfl');
const season = state.season, week = Math.max(1, state.week || 1), stype = state.season_type === 'post' ? 'post' : 'regular';
const [players, stats, proj, projPrev, trend] = await Promise.all([
  get('/players/nfl'),
  get(`/stats/nfl/${stype}/${season}`, true),
  get(`/projections/nfl/${stype}/${season}/${week}`, true),
  week > 1 ? get(`/projections/nfl/${stype}/${season}/${week - 1}`, true) : null,
  get('/players/nfl/trending/add?lookback_hours=48&limit=50', true)
]);
const trending = new Map((trend || []).map(t => [t.player_id, t.count]));
const out = [];
for (const [id, p] of Object.entries(players)) {
  if (!p || !POS.has(p.position) || !p.active || !p.team) continue;
  const s = stats?.[id] || {}, j = proj?.[id] || {}, jp = projPrev?.[id] || {};
  const gp = s.gp || 0;
  const adp = x => (x && x < 999 ? x : null);
  const dadp = adp(j.adp_dd_ppr) ?? adp(jp.adp_dd_ppr); // dynasty ADP; previous week covers bye weeks
  const row = {
    id, n: p.full_name || `${p.first_name} ${p.last_name}`, pos: p.position, team: p.team,
    age: p.age ?? null, exp: p.years_exp ?? null, inj: p.injury_status || null, rank: p.search_rank ?? 9999,
    gp, ppg: gp ? { ppr: r1((s.pts_ppr || 0) / gp), half: r1((s.pts_half_ppr || 0) / gp), std: r1((s.pts_std || 0) / gp) } : null,
    proj: j.pts_ppr != null ? { ppr: r1(j.pts_ppr), half: r1(j.pts_half_ppr ?? j.pts_ppr), std: r1(j.pts_std ?? j.pts_ppr) } : null,
    dadp, trend: trending.get(id) || 0
  };
  // keep the file small: drop deep-bench players with no signal
  if (row.rank > 600 && !row.ppg && !row.proj && !row.dadp) continue;
  out.push(row);
}
out.sort((a, b) => a.rank - b.rank);
const data = { generated: new Date().toISOString(), season, week, seasonType: stype, source: 'Sleeper public API (api.sleeper.app)', players: out };
await writeFile(new URL('../data/players.json', import.meta.url), JSON.stringify(data));
console.log(`Wrote ${out.length} players for ${season} week ${week} (stats: ${!!stats}, projections: ${!!proj}).`);
