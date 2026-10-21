#!/usr/bin/env node
// Refreshes data/players.json from the free, public Sleeper API (no key needed).
// Run: node scripts/refresh-data.mjs   (Node 18+). Schedule via .github/workflows/refresh.yml.
// Sleeper asks for < 1000 calls/min and that /players/nfl be pulled at most once per day.
// Note: /players/nfl and /players/nfl/trending are documented (https://docs.sleeper.com).
// /stats and /projections are public but undocumented; the script degrades gracefully if they fail.
import { writeFile, readFile } from 'node:fs/promises';
import { WEIGHTS, SOURCE_INFO, buildCurves, positionalRanks, composite, ageFactor, lastN } from './composite.mjs';
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
const season = state.season, stateWeek = Math.max(1, state.week || 1), stype = state.season_type === 'post' ? 'post' : 'regular';
// Target week = the week people are searching for. Sleeper flips its week on Tuesday, but "week N+1 waiver wire" and start/sit demand
// starts Monday (after Sunday's games), so on Mondays (UTC) we look one week ahead, and never behind the calendar
// (week 2 starts the Tuesday after season_start_date's week; the flip can lag the daily run). Falls back to Sleeper's week if
// the next week has no projections yet.
function calendarWeek() {
  const s = state.season_start_date ? new Date(state.season_start_date + 'T00:00:00Z') : null; if (!s || isNaN(s)) return 1;
  const tue = new Date(s); tue.setUTCDate(tue.getUTCDate() - ((tue.getUTCDay() + 5) % 7)); // Tuesday on or before the start date
  return 1 + Math.max(0, Math.floor((Date.now() - tue.getTime()) / (7 * 864e5)));
}
let week = stateWeek;
if (stype === 'regular') week = Math.min(18, Math.max(stateWeek, calendarWeek(), stateWeek + (new Date().getUTCDay() === 1 ? 1 : 0)));
// DynastyProcess open dynasty values (GPL-3.0, https://github.com/dynastyprocess/data). Attribution shown on the site.
const DP = 'https://raw.githubusercontent.com/dynastyprocess/data/master/files/';
async function csv(name) {
  try { const r = await fetch(DP + name); if (!r.ok) throw new Error(name + ' ' + r.status); return parseCSV(await r.text()); }
  catch (e) { console.warn('WARN', e.message); return null; }
}
function parseCSV(t) {
  const rows = []; let row = [], f = '', q = false;
  for (let i = 0; i < t.length; i++) { const c = t[i];
    if (q) { if (c === '"' && t[i + 1] === '"') { f += '"'; i++; } else if (c === '"') q = false; else f += c; }
    else if (c === '"') q = true; else if (c === ',') { row.push(f); f = ''; } else if (c === '\n') { row.push(f); rows.push(row); row = []; f = ''; } else if (c !== '\r') f += c; }
  if (f || row.length) { row.push(f); rows.push(row); }
  const [h, ...rest] = rows; return rest.filter(r => r.length === h.length).map(r => Object.fromEntries(h.map((k, i) => [k, r[i]])));
}
const STATE_SEASON = (await (await fetch('https://api.sleeper.app/v1/state/nfl')).json()).season;
const [dpValues, dpIds] = await Promise.all([csv('values.csv'), csv('db_playerids.csv')]);
const status = {}; // per-source health, published in players.json and on the methodology page
const fpToSleeper = new Map((dpIds || []).filter(r => r.fantasypros_id && r.sleeper_id && r.sleeper_id !== 'NA').map(r => [r.fantasypros_id, r.sleeper_id]));
const dpBySleeper = new Map(), picks = [];
for (const v of dpValues || []) {
  const v1 = +v.value_1qb, v2 = +v.value_2qb;
  if (v.pos === 'PICK') { const yr = parseInt(v.player, 10); if (yr && yr <= +STATE_SEASON) continue; picks.push({ id: 'pick:' + v.player, n: v.player, pos: 'PICK', v1, v2 }); continue; }
  const sid = fpToSleeper.get(v.fp_id); if (sid) dpBySleeper.set(sid, { v1, v2 });
}
// Fantasy Football Calculator dynasty ADP (free REST API, attribution requested). Empty early in a season -> skipped.
async function ffcAdp() {
  try { const r = await fetch(`https://fantasyfootballcalculator.com/api/v1/adp/dynasty?teams=12&year=${STATE_SEASON}`); if (!r.ok) throw new Error('FFC ' + r.status);
    const j = await r.json(); const ps = j.players || []; if (ps.length < 50) throw new Error(`FFC dynasty ADP has only ${ps.length} players (${j.meta?.total_drafts ?? 0} drafts)`); return ps; }
  catch (e) { console.warn('WARN', e.message); status.ffc = { ok: false, note: e.message }; return null; }
}
// nflverse weekly player stats (CC BY 4.0) for production and last-3-games form.
async function nflverseWeekly() {
  try { const r = await fetch(`https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_${STATE_SEASON}.csv`); if (!r.ok) throw new Error('nflverse ' + r.status);
    return parseCSV(await r.text()); }
  catch (e) { console.warn('WARN', e.message); status.prod = { ok: false, note: e.message }; return null; }
}
const [ffc, nfv] = await Promise.all([ffcAdp(), nflverseWeekly()]);
if (week > stateWeek) { const probe = await get(`/projections/nfl/${stype}/${season}/${week}`, true); if (Object.values(probe || {}).filter(j => j && j.pts_ppr > 5).length < 100) { console.warn(`WARN week ${week} projections not published; using Sleeper's week ${stateWeek}`); week = stateWeek; } }
const [players, stats, proj, projPrev, trend, trend24, trend72, projN1, projN2] = await Promise.all([
  get('/players/nfl'),
  get(`/stats/nfl/${stype}/${season}`, true),
  get(`/projections/nfl/${stype}/${season}/${week}`, true),
  week > 1 ? get(`/projections/nfl/${stype}/${season}/${week - 1}`, true) : null,
  get('/players/nfl/trending/add?lookback_hours=48&limit=50', true),
  get('/players/nfl/trending/add?lookback_hours=24&limit=200', true),
  get('/players/nfl/trending/add?lookback_hours=72&limit=200', true),
  week < 18 ? get(`/projections/nfl/${stype}/${season}/${week + 1}`, true) : null,
  week < 17 ? get(`/projections/nfl/${stype}/${season}/${week + 2}`, true) : null
]);
// Kickers and team defenses for the weekly position rankings (not dynasty assets, so they stay out of `players`).
const kd = [];
for (const [id, p] of Object.entries(players)) {
  if (!p || !p.team || !(p.position === 'DEF' || (p.position === 'K' && p.active))) continue;
  const j = proj?.[id]; if (!j || !(j.pts_ppr > 0)) continue;
  const row = { id, n: p.position === 'DEF' ? `${p.first_name} ${p.last_name}` : (p.full_name || `${p.first_name} ${p.last_name}`), pos: p.position, team: p.team, inj: p.injury_status || null, proj: { ppr: r1(j.pts_ppr), half: r1(j.pts_half_ppr ?? j.pts_ppr), std: r1(j.pts_std ?? j.pts_ppr) } };
  row.x = p.position === 'DEF' ? { pa: r1(j.pts_allow || 0), sk: r1(j.sack || 0), to: r1((j.int || 0) + (j.fum_rec || 0)) } : { fgm: r1(j.fgm || 0), xpm: r1(j.xpm || 0) };
  kd.push(row);
}
kd.sort((a, b) => b.proj.ppr - a.proj.ppr);
// This week's opponent for each team (Sleeper schedule endpoint, undocumented). "@" = away. Teams missing from the map are on a bye.
let opp = null;
try {
  const r = await fetch(`https://api.sleeper.app/schedule/nfl/${stype}/${season}`, { headers: { 'User-Agent': 'fantasy-tools-static-refresh' } });
  if (!r.ok) throw new Error('schedule -> HTTP ' + r.status);
  const games = (await r.json()).filter(g => g.week === week && g.home && g.away);
  if (games.length) { opp = {}; for (const g of games) { opp[g.home] = g.away; opp[g.away] = '@' + g.home; } }
} catch (e) { console.warn('WARN', e.message); }
const t24 = new Map((trend24 || []).map(t => [t.player_id, t.count])), t72 = new Map((trend72 || []).map(t => [t.player_id, t.count]));
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
  if (t24.get(id)) { row.t24 = t24.get(id); row.t72 = t72.get(id) || null; }
  // Sleeper's own projections for this week and the next two (undocumented endpoint). Sum shown on the waiver page; weeks without a projection (bye) add nothing.
  const fut = [j, projN1?.[id], projN2?.[id]].map(x => (x && x.pts_ppr > 0 ? x.pts_ppr : null));
  if (row.t24 || fut.some(v => v != null)) row.p3 = { ppr: r1(fut.reduce((a, v) => a + (v || 0), 0)), n: fut.filter(v => v != null).length, next: projN1?.[id]?.pts_ppr > 0 ? r1(projN1[id].pts_ppr) : null };
  const dv = dpBySleeper.get(id); if (dv) { row._dp = dv; }
  // keep the file small: drop deep-bench players with no signal
  if (row.rank > 600 && !row.ppg && !row.proj && !row.dadp && !row.v1 && !row.t24) continue;
  out.push(row);
}
out.sort((a, b) => a.rank - b.rank);
// ---------- composite dynasty values ----------
const norm = x => (x || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\b(jr|sr|ii|iii|iv|v)\b/g, '').replace(/[^a-z]/g, '');
const posOf = new Map(out.map(p => [p.id, p.pos])), byName = new Map(out.map(p => [norm(p.n) + '|' + p.pos, p.id]));
const src = {};
const dpScores = new Map(out.filter(p => p._dp && p._dp.v1 > 0).map(p => [p.id, { pos: p.pos, s: p._dp.v1 }]));
if (dpScores.size) { src.dp = positionalRanks(dpScores); status.dp = { ok: true, count: dpScores.size }; } else status.dp = { ok: false, note: 'DynastyProcess values unavailable' };
const slScores = new Map(out.filter(p => p.dadp).map(p => [p.id, { pos: p.pos, s: p.dadp }]));
if (slScores.size >= 50) { src.sl = positionalRanks(slScores, false); status.sl = { ok: true, count: slScores.size }; } else status.sl = { ok: false, note: `Sleeper dynasty ADP has ${slScores.size} players` };
if (ffc) { const m = new Map(); for (const f of ffc) { const id = byName.get(norm(f.name) + '|' + f.position); if (id) m.set(id, { pos: f.position, s: f.adp }); }
  if (m.size >= 50) { src.ffc = positionalRanks(m, false); status.ffc = { ok: true, count: m.size }; } else status.ffc = { ok: false, note: `matched only ${m.size} FFC players` }; }
const weekly = new Map(); // sleeper id -> [{week, ppr, half, std}]
if (nfv) { const g2s = new Map((dpIds || []).filter(r => r.gsis_id && r.gsis_id !== 'NA' && r.sleeper_id && r.sleeper_id !== 'NA').map(r => [r.gsis_id, r.sleeper_id]));
  for (const r of nfv) { const id = g2s.get(r.player_id); if (!id || !posOf.has(id) || r.season_type !== 'REG') continue; const ppr = +r.fantasy_points_ppr || 0, std = +r.fantasy_points || 0;
    (weekly.get(id) || weekly.set(id, []).get(id)).push({ week: +r.week, ppr, std, half: (ppr + std) / 2 }); }
  const prodScores = new Map(); for (const [id, rows] of weekly) { if (rows.length < 3) continue; const p = out.find(x => x.id === id);
    prodScores.set(id, { pos: p.pos, s: rows.reduce((t, x) => t + x.ppr, 0) / rows.length * ageFactor(p.pos, p.age) }); }
  if (prodScores.size >= 50) { src.prod = positionalRanks(prodScores); status.prod = { ok: true, count: prodScores.size }; } else status.prod = { ok: false, note: `only ${prodScores.size} players with 3+ games` }; }
// Value curves: DynastyProcess positional curves (fallback curve if it is down)
const dpRows = out.filter(p => p._dp).map(p => ({ pos: p.pos, v1: p._dp.v1, v2: p._dp.v2 }));
const comp = composite(src, posOf, buildCurves(dpRows, 'v1'), buildCurves(dpRows, 'v2'));
for (const p of out) { const c = comp.get(p.id); delete p._dp;
  // only publish a composite when an expert or market source has the player (production alone isn't a dynasty value)
  if (c && (c.cs.dp != null || c.cs.sl != null || c.cs.ffc != null)) Object.assign(p, { v1: c.v1, v2: c.v2, cs: c.cs, sp: c.sp, con: c.con, sig: c.sig });
  const l3 = weekly.has(p.id) ? lastN(weekly.get(p.id), 3) : null; if (l3) p.l3 = l3; }
for (const k of Object.keys(SOURCE_INFO)) status[k] = { ...SOURCE_INFO[k], weight: WEIGHTS[k], ...(status[k] || { ok: false, note: 'not fetched' }) };
// If every value source failed, keep yesterday's values rather than publishing nothing.
if (!out.some(p => p.v1)) { try { const prev = JSON.parse(await readFile(new URL('../data/players.json', import.meta.url), 'utf8')); const pm = new Map(prev.players.map(p => [p.id, p]));
  for (const p of out) { const o = pm.get(p.id); if (o && o.v1) Object.assign(p, { v1: o.v1, v2: o.v2, cs: o.cs, sp: o.sp, con: o.con, sig: o.sig }); } console.warn('WARN all value sources failed; kept previous values'); } catch (e) {} }
const data = { generated: new Date().toISOString(), season, week, stateWeek, seasonType: stype, source: 'Composite of DynastyProcess, Sleeper, Fantasy Football Calculator and nflverse; see sources', sources: status, weights: WEIGHTS, valuesDate: (dpValues && dpValues[0] && dpValues[0].scrape_date) || null, players: out, picks, kd, opp };
await writeFile(new URL('../data/players.json', import.meta.url), JSON.stringify(data));
console.log('Sources:', Object.entries(status).map(([k, v]) => `${k}=${v.ok ? 'ok(' + v.count + ')' : 'FAILED(' + v.note + ')'}`).join(' '));
console.log(`Wrote ${out.length} players, ${kd.length} K/DEF, ${opp ? Object.keys(opp).length : 0} team matchups, ${picks.length} picks, ${dpBySleeper.size} DP values for ${season} week ${week} (stats: ${!!stats}, projections: ${!!proj}).`);
