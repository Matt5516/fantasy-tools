// Composite dynasty values and start/sit inputs from several free, legally usable sources.
// Pure functions (no network) so they can be unit-tested. Used by refresh-data.mjs.
//
// Method: each source ranks players WITHIN A POSITION. A positional rank is converted to a value with the
// DynastyProcess positional value curve (1QB curve for 1QB values, superflex curve for SF), so every source
// lands on the same 0-10,000 scale and QB scarcity in superflex is handled the same way for every source.
// Composite = weighted average of the sources that have the player (weights re-normalised over those present).
export const WEIGHTS = { dp: 0.40, sl: 0.30, ffc: 0.15, prod: 0.15 };
export const SOURCE_INFO = {
  dp:   { name: 'DynastyProcess expert consensus', kind: 'Experts', url: 'https://github.com/dynastyprocess/data', license: 'GPL-3.0 (open data repository; values derived from FantasyPros expert consensus rankings)' },
  sl:   { name: 'Sleeper dynasty ADP', kind: 'Market (real dynasty drafts)', url: 'https://docs.sleeper.com', license: 'Sleeper public API (free, no key)' },
  ffc:  { name: 'Fantasy Football Calculator dynasty ADP', kind: 'Market (mock drafts)', url: 'https://fantasyfootballcalculator.com', license: 'Free ADP REST API for personal and commercial use, with attribution' },
  prod: { name: 'nflverse production (PPR points per game, age-adjusted)', kind: 'On-field production', url: 'https://github.com/nflverse/nflverse-data', license: 'CC BY 4.0' },
};
export const PROJ_WEIGHTS = { proj: 0.5, l3: 0.25, ppg: 0.25 };
const PEAK = { QB: 29, RB: 25, WR: 27, TE: 27 };

// curves[pos] = descending array of values (index = positional rank - 1)
export function curveValue(curve, rank, pos) {
  if (curve && curve.length) {
    if (rank <= curve.length) return curve[rank - 1];
    const last = curve[curve.length - 1]; return Math.max(1, Math.round(last * Math.pow(0.97, rank - curve.length)));
  }
  const top = { QB: 7000, RB: 8500, WR: 9000, TE: 6000 }[pos] || 6000; // fallback if DynastyProcess is down
  return Math.round(top * Math.exp(-0.06 * (rank - 1)));
}
export function buildCurves(dpRows, key) { // dpRows: [{pos, v1, v2}]
  const c = {}; for (const r of dpRows) { if (!(r[key] > 0)) continue; (c[r.pos] ||= []).push(r[key]); }
  for (const k in c) c[k].sort((a, b) => b - a); return c;
}
// scores: Map id -> {pos, s}; higherIsBetter=false for ADP. Returns Map id -> positional rank.
export function positionalRanks(scores, higherIsBetter = true) {
  const byPos = {}; for (const [id, x] of scores) (byPos[x.pos] ||= []).push([id, x.s]);
  const out = new Map();
  for (const pos in byPos) byPos[pos].sort((a, b) => higherIsBetter ? b[1] - a[1] : a[1] - b[1]).forEach(([id], i) => out.set(id, i + 1));
  return out;
}
export function ageFactor(pos, age) {
  if (!age || !PEAK[pos]) return 1;
  const d = PEAK[pos] - age; return Math.min(1.15, Math.max(0.5, 1 + (d > 0 ? 0.03 : 0.07) * d));
}
// sources: {key: Map id -> positional rank}; pos: Map id -> pos. Returns Map id -> {v1, v2, cs, sp, con, sig}
export function composite(sources, posOf, curves1, curves2, weights = WEIGHTS) {
  const ids = new Set(); for (const k in sources) for (const id of sources[k].keys()) ids.add(id);
  const out = new Map();
  for (const id of ids) {
    const pos = posOf.get(id); if (!pos) continue;
    let w = 0, s1 = 0, s2 = 0; const cs = {};
    for (const k in sources) { const r = sources[k].get(id); if (!r || !weights[k]) continue;
      const a = curveValue(curves1[pos], r, pos), b = curveValue(curves2[pos], r, pos);
      cs[k] = a; w += weights[k]; s1 += weights[k] * a; s2 += weights[k] * b; }
    if (!w) continue;
    const v1 = Math.round(s1 / w), v2 = Math.round(s2 / w), vals = Object.values(cs);
    const sp = vals.length > 1 ? Math.round((Math.max(...vals) - Math.min(...vals)) / Math.max(1, ...vals) * 100) : null; // % gap between highest and lowest source
    out.set(id, { v1, v2, cs, sp, con: consensus(sp, vals.length), sig: signal(cs, v1) });
  }
  return out;
}
export function consensus(sp, n) { if (n < 2 || sp == null) return 'single'; return sp < 35 ? "strong" : sp < 65 ? "mixed" : "split"; }
// market (ADP sources) vs experts: market much lower = buy candidate, much higher = sell candidate
export function signal(cs, v1) {
  const m = [cs.sl, cs.ffc].filter(x => x != null); if (cs.dp == null || !m.length || v1 < 1000) return null;
  const mk = m.reduce((a, b) => a + b, 0) / m.length, d = (mk - cs.dp) / cs.dp;
  return d <= -0.35 ? "buy" : d >= 0.35 ? "sell" : null;
}
// last-N-games points per game from nflverse weekly rows [{week, ppr, half, std}]
export function lastN(rows, n = 3) {
  const r = rows.slice().sort((a, b) => b.week - a.week).slice(0, n); if (!r.length) return null;
  const avg = k => Math.round(r.reduce((t, x) => t + x[k], 0) / r.length * 10) / 10;
  return { ppr: avg('ppr'), half: avg('half'), std: avg('std'), g: r.length };
}
