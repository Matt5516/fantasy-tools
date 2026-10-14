(function(){
  var $=function(id){return document.getElementById(id);}, P=[], byName={};
  function label(p){return p.n+' ('+p.pos+', '+p.team+')';}
  function inputs(container, prefix, count, defaults){
    for (var i=0;i<count;i++){ var d=document.createElement('div');
      d.innerHTML='<label for="'+prefix+i+'">Player '+(i+1)+'</label><input id="'+prefix+i+'" list="playerList" autocomplete="off" placeholder="Start typing a name" value="'+(defaults[i]||'')+'">';
      container.appendChild(d); }
  }
  function pick(prefix,count){ var out=[]; for(var i=0;i<count;i++){ var v=$(prefix+i).value.trim(); if(byName[v]) out.push(byName[v]); } return out; }
  function ss(){
    var fmt=$('fmt').value, ps=pick('ss',4);
    if (ps.length<2){ $('ssOut').innerHTML='<p class="hint">Pick at least two players from the list.</p>'; return; }
    var r=FFCalc.startSit(ps,fmt), h='<div class="verdict good"><strong>Start '+Site.esc(r[0].p.n)+'.</strong></div><div class="table-scroll"><table><thead><tr><th>Player</th><th>Proj</th><th>PPG</th><th>Score</th><th>Call</th></tr></thead><tbody>';
    r.forEach(function(x,i){ h+='<tr><td>'+Site.esc(label(x.p))+(x.s.note?'<div class="hint">'+Site.esc(x.s.note)+'</div>':'')+'</td><td>'+(x.p.proj?x.p.proj[fmt]:'—')+'</td><td>'+(x.p.ppg?x.p.ppg[fmt]:'—')+'</td><td><strong>'+x.s.score+'</strong></td><td class="'+(i===0?'pos':'neg')+'">'+(i===0?'Start':'Sit')+'</td></tr>'; });
    $('ssOut').innerHTML=h+'</tbody></table></div>';
  }
  function tr(){
    var opt={superflex:$('sf').value==='1', tePremium:$('tep').value==='1'};
    var A=pick('ta',4), B=pick('tb',4);
    if (!A.length||!B.length){ $('tradeOut').innerHTML='<p class="hint">Add at least one player to each side.</p>'; return; }
    var va=A.map(function(p){return FFCalc.dynastyValue(p,opt);}), vb=B.map(function(p){return FFCalc.dynastyValue(p,opt);});
    var r=FFCalc.trade(va,vb);
    function list(ps,vs){return ps.map(function(p,i){return Site.esc(label(p))+': '+vs[i].toLocaleString();}).join('<br>');}
    $('tradeOut').innerHTML='<div class="verdict '+(r.verdict==='Fair trade'?'good':'warn')+'"><strong>'+r.verdict+'</strong> (A '+r.a.toLocaleString()+' vs B '+r.b.toLocaleString()+', gap '+Math.abs(r.gapPct)+'%)</div><div class="grid cols-2" style="margin-top:8px"><div class="hint">'+list(A,va)+'</div><div class="hint">'+list(B,vb)+'</div></div>';
  }
  inputs($('ssInputs'),'ss',4,[]); inputs($('sideA'),'ta',4,[]); inputs($('sideB'),'tb',4,[]);
  fetch('data/players.json').then(function(r){return r.json();}).then(function(d){
    P=d.players; var dl=$('playerList'), frag=document.createDocumentFragment();
    P.forEach(function(p){ byName[label(p)]=p; var o=document.createElement('option'); o.value=label(p); frag.appendChild(o); });
    dl.appendChild(frag);
    $('dataInfo').textContent=d.season+' season, week '+d.week+' (updated '+new Date(d.generated).toLocaleDateString()+')';
    // sensible demo defaults: top two RBs with projections, and a sample trade
    var rb=P.filter(function(p){return p.pos==='RB'&&p.proj;}).slice(0,2), wr=P.filter(function(p){return p.pos==='WR'&&p.dadp;});
    if (rb[1]){ $('ss0').value=label(rb[0]); $('ss1').value=label(rb[1]); }
    if (wr[2]){ $('ta0').value=label(wr[0]); $('tb0').value=label(wr[1]); }
    ss(); tr();
  }).catch(function(){ $('dataInfo').textContent='could not load player data.'; });
  document.querySelector('main').addEventListener('input',function(){ss();tr();});
  document.querySelector('main').addEventListener('change',function(){ss();tr();});
})();
