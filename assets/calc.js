(function(root){
  var INJ = {Out:0, IR:0, PUP:0, Sus:0, Doubtful:0.25, Questionable:0.85};
  function r1(n){return Math.round(n*10)/10;}
  // Start/sit score: weighted blend of independent signals, re-normalised over those available:
  // 50% this week's projection (Sleeper / RotoWire), 25% last 3 games (nflverse), 25% season points per game (Sleeper).
  // A projection is required (no projection = bye or inactive). Then discounted by injury status.
  var PW = {proj:0.5, l3:0.25, ppg:0.25};
  function startScore(p, fmt){
    var parts = {proj: p.proj ? p.proj[fmt] : null, l3: p.l3 ? p.l3[fmt] : null, ppg: p.ppg ? p.ppg[fmt] : null};
    var mult = p.inj && INJ.hasOwnProperty(p.inj) ? INJ[p.inj] : 1;
    if (parts.proj==null) return {score:0, base:null, mult:mult, parts:parts, spread:null, note:'No projection this week (bye or inactive).'};
    var w=0, t=0, vals=[]; for (var k in PW){ if (parts[k]!=null){ w+=PW[k]; t+=PW[k]*parts[k]; vals.push(parts[k]); } }
    var base=t/w, hi=Math.max.apply(null,vals), lo=Math.min.apply(null,vals), spread=vals.length>1?r1(hi-lo):null;
    return {score:r1(base*mult), base:r1(base), mult:mult, parts:parts, spread:spread, note: mult<1 ? 'Injury status: '+p.inj+' (×'+mult+')' : ''};
  }
  function startSit(players, fmt){
    return players.map(function(p){ var s=startScore(p,fmt); return {p:p, s:s}; })
      .sort(function(a,b){return b.s.score-a.s.score;});
  }
  // Dynasty value 0-10000 from dynasty ADP with an age curve; superflex boosts QBs.
  var PEAK = {QB:32, RB:25, WR:28, TE:29}, DECAY = {QB:0.05, RB:0.10, WR:0.07, TE:0.07};
  function dynastyValue(p, opt){
    opt = opt||{};
    if (p.v1){ // DynastyProcess open values (1QB / superflex)
      var dv = opt.superflex ? (p.v2||p.v1) : p.v1;
      if (opt.tePremium && p.pos==='TE') dv *= 1.15;
      return Math.round(dv);
    }
    var adp = p.dadp || Math.min(400, (p.rank||300)*1.2+20); // fallback when ADP missing
    var v = 10000*Math.exp(-0.0125*(adp-1));
    if (p.age) v *= Math.max(0.35, 1 - DECAY[p.pos]*Math.max(0, p.age-PEAK[p.pos]));
    if (opt.superflex && p.pos==='QB') v *= 1.35;
    if (opt.tePremium && p.pos==='TE') v *= 1.15;
    return Math.round(v);
  }
  // Trade side total: best asset counts fully, extra pieces are discounted (2-for-1s favor the consolidating side).
  var DEPTH = [1, 0.75, 0.55, 0.4, 0.3, 0.25];
  function sideValue(values){
    return Math.round(values.slice().sort(function(a,b){return b-a;}).reduce(function(t,v,i){return t+v*(DEPTH[i]||0.2);},0));
  }
  function trade(aValues, bValues){
    var a=sideValue(aValues), b=sideValue(bValues), max=Math.max(a,b,1), gap=(a-b)/max;
    var verdict = Math.abs(gap)<=0.05 ? 'Fair trade' : (gap>0 ? 'Side A wins' : 'Side B wins');
    return {a:a, b:b, gapPct:Math.round(gap*1000)/10, verdict:verdict};
  }
  // Players that would even up the trade if added to the side that's behind. pool: [{p, v}] already valued.
  function balance(aVals, bVals, pool, exclude){
    var a=sideValue(aVals), b=sideValue(bVals); if (Math.abs(a-b)/Math.max(a,b,1) <= 0.05) return {side:null, list:[]};
    var behind = a<b ? 'A' : 'B', mine = a<b ? aVals : bVals, target = Math.max(a,b);
    var list = pool.filter(function(x){return !exclude[x.p.id];}).map(function(x){ var nv=sideValue(mine.concat([x.v])); return {p:x.p, v:x.v, after:nv, miss:Math.abs(nv-target)}; })
      .filter(function(x){ return x.after >= target*0.95 && x.after <= target*1.08; }).sort(function(x,y){return x.miss-y.miss;}).slice(0,5);
    return {side:behind, gap:Math.abs(a-b), list:list};
  }
  var api={PW:PW,balance:balance,startScore:startScore,startSit:startSit,dynastyValue:dynastyValue,sideValue:sideValue,trade:trade};
  if (typeof module!=='undefined'&&module.exports) module.exports=api; else root.FFCalc=api;
})(this);
