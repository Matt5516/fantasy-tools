(function(root){
  var INJ = {Out:0, IR:0, PUP:0, Sus:0, Doubtful:0.25, Questionable:0.85};
  function r1(n){return Math.round(n*10)/10;}
  // Start/sit score: 70% this week's projection + 30% season points per game, discounted by injury status.
  function startScore(p, fmt){
    var proj = p.proj ? p.proj[fmt] : null, ppg = p.ppg ? p.ppg[fmt] : null;
    var base = proj!=null && ppg!=null ? 0.7*proj + 0.3*ppg : (proj!=null ? proj : null);
    var mult = p.inj && INJ.hasOwnProperty(p.inj) ? INJ[p.inj] : 1;
    if (base===null) return {score:0, base:null, mult:mult, note:'No projection this week (bye or inactive).'};
    return {score:r1(base*mult), base:r1(base), mult:mult, note: mult<1 ? 'Injury status: '+p.inj+' (×'+mult+')' : ''};
  }
  function startSit(players, fmt){
    return players.map(function(p){ var s=startScore(p,fmt); return {p:p, s:s}; })
      .sort(function(a,b){return b.s.score-a.s.score;});
  }
  // Dynasty value 0-10000 from dynasty ADP with an age curve; superflex boosts QBs.
  var PEAK = {QB:32, RB:25, WR:28, TE:29}, DECAY = {QB:0.05, RB:0.10, WR:0.07, TE:0.07};
  function dynastyValue(p, opt){
    opt = opt||{};
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
  var api={startScore:startScore,startSit:startSit,dynastyValue:dynastyValue,sideValue:sideValue,trade:trade};
  if (typeof module!=='undefined'&&module.exports) module.exports=api; else root.FFCalc=api;
})(this);
