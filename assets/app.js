(function(){
  'use strict';
  var $=UI.$, D=null, BY={}, ALLITEMS=[], POSC={QB:'#be123c',RB:'#047857',WR:'#1d4ed8',TE:'#b45309',PICK:'#7c3aed'};
  var sel={ss:[],a:[],b:[]};
  function v(id,d){ var e=$(id); return e?e.value:d; }
  function opt(){ return {superflex:v('sf','0')==='1', tePremium:v('tep','0')==='1'}; }
  function val(p){ return p.pos==='PICK' ? Math.round((v('sf','0')==='1'?p.v2:p.v1)||0) : FFCalc.dynastyValue(p,opt()); }
  function label(p){ return p.pos==='PICK'?p.n:p.n+' · '+p.pos+' '+p.team; }
  function tag(p){ return '<span class="pos-tag" style="background:'+(POSC[p.pos]||'#64748b')+'">'+p.pos+'</span>'; }
  function norm(s){ return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]/g,''); }
  // ---------- Autocomplete combobox ----------
  function combo(inputId,listId,key,pool,max,onchange){
    var inp=$(inputId), list=$(listId), items=[], active=-1;
    function close(){ list.hidden=true; inp.setAttribute('aria-expanded','false'); inp.removeAttribute('aria-activedescendant'); active=-1; }
    function render(){
      var q=norm(inp.value.trim()); if(!q){ close(); return; }
      items=pool().filter(function(p){ return p._s.indexOf(q)>=0 && sel[key].indexOf(p.id)<0; }).slice(0,8);
      if(!items.length){ list.innerHTML='<li role="option" aria-disabled="true">No matches</li>'; list.hidden=false; inp.setAttribute('aria-expanded','true'); return; }
      list.innerHTML=items.map(function(p,i){ return '<li role="option" id="'+listId+'-'+i+'" data-i="'+i+'" aria-selected="'+(i===active)+'"><span>'+UI.esc(p.n)+'</span><span class="hint" style="margin:0">'+(p.pos==='PICK'?'Pick':p.pos+' · '+(p.team||''))+'</span></li>'; }).join('');
      list.hidden=false; inp.setAttribute('aria-expanded','true');
    }
    function choose(i){ var p=items[i]; if(!p) return; if(sel[key].length>=max){ UI.toast('Up to '+max+' here'); return; } sel[key].push(p.id); inp.value=''; close(); onchange(); inp.focus(); }
    inp.addEventListener('input',function(){ active=-1; render(); });
    inp.addEventListener('keydown',function(e){
      if(list.hidden && e.key==='ArrowDown'){ render(); }
      if(e.key==='ArrowDown'||e.key==='ArrowUp'){ e.preventDefault(); if(!items.length) return; active=(active+(e.key==='ArrowDown'?1:-1)+items.length)%items.length; render(); inp.setAttribute('aria-activedescendant',listId+'-'+active); }
      else if(e.key==='Enter'){ e.preventDefault(); choose(active<0?0:active); }
      else if(e.key==='Escape'){ close(); }
    });
    list.addEventListener('mousedown',function(e){ var li=e.target.closest('li[data-i]'); if(li){ e.preventDefault(); choose(+li.dataset.i); } });
    inp.addEventListener('blur',function(){ setTimeout(close,120); });
    inp.disabled=false;
  }
  function chips(boxId,key,onchange,showVal){
    $(boxId).innerHTML=sel[key].map(function(id){ var p=BY[id]; if(!p) return ''; return '<div class="pchip">'+tag(p)+'<span><strong>'+UI.esc(p.n)+'</strong>'+(p.team?' <span class="hint" style="display:inline">'+p.team+(p.inj?' · '+p.inj:'')+'</span>':'')+'</span>'+(showVal?'<span class="badge" style="margin-left:auto">'+val(p).toLocaleString()+'</span>':'')+'<button type="button" class="x" data-key="'+key+'" data-id="'+UI.esc(id)+'" aria-label="Remove '+UI.esc(p.n)+'">×</button></div>'; }).join('');
  }
  document.addEventListener('click',function(e){ var x=e.target.closest('.pchip .x'); if(!x) return; var k=x.dataset.key; sel[k]=sel[k].filter(function(id){return id!==x.dataset.id;}); renderAll(); });
  // ---------- Start / sit ----------
  var ssText='', trText='';
  function startSit(){ if(!$('ssOut')) return;
    chips('ssChips','ss',renderAll,false);
    var out=$('ssOut'), fmt=$('fmt').value, ps=sel.ss.map(function(id){return BY[id];}).filter(Boolean);
    if(ps.length<2){ out.innerHTML='<div class="empty">'+UI.icon('users')+'<p><strong>Add at least two players</strong><br>Search above, e.g. two running backs you\'re torn between.</p></div>'; ssText=''; return; }
    var r=FFCalc.startSit(ps,fmt), top=r[0], gap=r[1]?top.s.score-r[1].s.score:0;
    var conf=gap>=4?'High':gap>=1.5?'Medium':'Low';
    var h='<h2>'+UI.icon('trophy')+'Start/sit call</h2><div class="verdict good"><span class="vicon">'+UI.icon('check')+'</span><div><strong class="big">Start '+UI.esc(top.p.n)+'</strong><span>'+conf+' confidence: '+gap.toFixed(1)+' point edge in '+({ppr:'PPR',half:'Half PPR',std:'standard'})[fmt]+' scoring.</span></div></div>';
    var mx=Math.max.apply(null,r.map(function(x){return x.s.score;}))||1;
    h+='<div style="margin-top:14px">'+r.map(function(x,i){ var p=x.p; return '<div style="margin:10px 0"><div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><span>'+tag(p)+' <strong>'+UI.esc(p.n)+'</strong> <span class="hint" style="display:inline">'+p.team+'</span></span><span class="badge '+(i===0?'good':'')+'">'+(i===0?'START':'SIT')+' · '+x.s.score+'</span></div><div class="bar" style="margin-top:6px"><i style="width:'+Math.max(2,x.s.score/mx*100)+'%"></i></div>'+
      '<div class="hint">Projection '+(p.proj?p.proj[fmt]:'—')+' · last 3 games '+(p.l3?p.l3[fmt]:'—')+' · season PPG '+(p.ppg?p.ppg[fmt]:'—')+(p.gp?' ('+p.gp+' games)':'')+(x.s.spread!=null&&x.s.spread>=6?' · <strong>sources disagree by '+x.s.spread+' pts</strong>':'')+(p.trend?' · trending +'+p.trend.toLocaleString()+' adds':'')+(x.s.note?' · '+UI.esc(x.s.note):'')+'</div></div>'; }).join('')+'</div>';
    h+='<div class="actions"><button type="button" class="btn sm" data-share="ss">'+UI.icon('share')+'Share</button><button type="button" class="btn ghost sm" data-copy="ss">'+UI.icon('copy')+'Copy</button></div>';
    out.innerHTML=h;
    ssText='Start/sit (Week '+D.week+', '+fmt.toUpperCase()+'): START '+top.p.n+' ('+top.s.score+'). '+r.slice(1).map(function(x){return 'Sit '+x.p.n+' ('+x.s.score+')';}).join(', ')+'.';
  }
  var SRCN={dp:'Experts (DynastyProcess)',sl:'Sleeper ADP',ffc:'FFC ADP',prod:'Production (nflverse)'}, CON={strong:['good','Sources agree'],mixed:['','Some disagreement'],split:['warn','Sources disagree'],single:['','One source']};
  function conBadge(p){ if(!p.con) return ''; var c=CON[p.con]; return '<span class="badge '+c[0]+'" title="Spread between sources: '+(p.sp==null?'n/a':p.sp+'%')+'">'+c[1]+'</span>'+(p.sig?' <span class="badge '+(p.sig==='buy'?'good':'warn')+'">'+(p.sig==='buy'?'Buy: market below experts':'Sell: market above experts')+'</span>':''); }
  UI.conBadge=conBadge;
  function breakdown(list){ var keys=['dp','sl','ffc','prod'].filter(function(k){ return list.some(function(p){ return p.cs&&p.cs[k]!=null; }); }); if(!keys.length) return '';
    return '<details class="adv" style="margin-top:14px"><summary>Where the values come from</summary><div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Player</th>'+keys.map(function(k){return '<th scope="col">'+SRCN[k]+'</th>';}).join('')+'<th scope="col">Composite</th><th scope="col">Consensus</th></tr></thead><tbody>'+
      list.filter(function(p){return p.pos!=='PICK';}).map(function(p){ return '<tr><td style="text-align:left">'+UI.esc(p.n)+'</td>'+keys.map(function(k){ return '<td>'+(p.cs&&p.cs[k]!=null?p.cs[k].toLocaleString():'—')+'</td>'; }).join('')+'<td><strong>'+(p.v1||0).toLocaleString()+'</strong></td><td>'+conBadge(p)+'</td></tr>'; }).join('')+
      '</tbody></table></div><p class="hint">1QB scale. Each source is converted to the same 0–10,000 scale by positional rank, then blended (experts 40%, Sleeper ADP 30%, FFC ADP 15%, production 15%, re-weighted when a source is missing). Picks use DynastyProcess only. <a href="'+UI.root()+'how-our-values-work/">Methodology</a></p></details>'; }
  // ---------- Trade ----------
  function trade(){ if(!$('trOut')) return;
    chips('aChips','a',renderAll,true); chips('bChips','b',renderAll,true);
    var out=$('trOut'), A=sel.a.map(function(id){return BY[id];}).filter(Boolean), B=sel.b.map(function(id){return BY[id];}).filter(Boolean);
    if(!A.length||!B.length){ out.innerHTML='<div class="empty">'+UI.icon('swap')+'<p><strong>Add at least one player or pick to each side</strong><br>Example: a 2027 1st for a young receiver.</p></div>'; trText=''; return; }
    var va=A.map(val), vb=B.map(val), r=FFCalc.trade(va,vb), fair=r.verdict==='Fair trade';
    var share=r.a/(r.a+r.b||1)*100;
    var h='<h2>'+UI.icon('swap')+'Trade verdict</h2><div class="verdict '+(fair?'good':'warn')+'"><span class="vicon">'+UI.icon(fair?'check':'alert')+'</span><div><strong class="big">'+(fair?'Fair trade':(r.a>r.b?'You overpay':'You win this trade'))+'</strong><span>'+(fair?'The sides are within 5%.':(r.a>r.b?'The other side wins by ':'You come out ahead by ')+Math.abs(r.gapPct)+'%.')+'</span></div></div>';
    h+='<div class="stats">'+'<div class="stat"><div class="k">You give</div><div class="v">'+r.a.toLocaleString()+'</div></div><div class="stat"><div class="k">You get</div><div class="v">'+r.b.toLocaleString()+'</div></div></div>';
    h+='<div class="bar" style="height:14px" role="img" aria-label="You give '+Math.round(share)+'% of total value"><i style="width:'+share+'%"></i></div><div class="legend" style="justify-content:space-between;margin-top:4px"><span>You give '+Math.round(share)+'%</span><span>You get '+Math.round(100-share)+'%</span></div>';
    var bal=FFCalc.balance(va,vb,ALLITEMS.map(function(p){return {p:p,v:val(p)};}).filter(function(x){return x.v>200;}),Object.assign({},...sel.a.concat(sel.b).map(function(id){var o={};o[id]=1;return o;})));
    if(bal.side){ h+='<h3 style="margin-top:16px">To balance it, '+(bal.side==='A'?'you':'the other side')+' could add</h3>'+(bal.list.length?bal.list.map(function(x){return '<div class="pchip">'+tag(x.p)+'<span><strong>'+UI.esc(x.p.n)+'</strong> <span class="hint" style="display:inline">'+(x.p.team||'')+'</span></span><span class="badge" style="margin-left:auto">'+x.v.toLocaleString()+'</span><button type="button" class="btn ghost sm" data-add="'+bal.side.toLowerCase()+'" data-id="'+UI.esc(x.p.id)+'">Add</button></div>';}).join(''):'<p class="hint">No single player closes the gap. Try adding a pick or a second piece.</p>'); }
    h+=breakdown(A.concat(B));
    h+='<div class="actions"><button type="button" class="btn sm" data-share="tr">'+UI.icon('share')+'Share trade</button><button type="button" class="btn ghost sm" data-copy="tr">'+UI.icon('copy')+'Copy</button></div>';
    out.innerHTML=h;
    trText='Dynasty trade ('+(opt().superflex?'SF':'1QB')+(opt().tePremium?', TEP':'')+'): I give '+A.map(function(p){return p.n;}).join(' + ')+' ('+r.a.toLocaleString()+') for '+B.map(function(p){return p.n;}).join(' + ')+' ('+r.b.toLocaleString()+'): '+(fair?'fair':(r.a>r.b?'I overpay by ':'I win by ')+Math.abs(r.gapPct)+'%')+'.';
  }
  document.addEventListener('click',function(e){ var b=e.target.closest('[data-add]'); if(!b) return; sel[b.dataset.add].push(b.dataset.id); renderAll(); });
  // ---------- Rankings ----------
  var rkLimit=40, rkTimer=0;
  function rankings(){ if(!$('rkBody')) return; clearTimeout(rkTimer); rkTimer=setTimeout(rankingsNow, rkLimit===40&&!rkDone?250:0); }
  var rkDone=false; function rankingsNow(){ rkDone=true;
    var pos=$('rkPos').value, q=norm($('rkFind').value||''), rows=ALLITEMS.filter(function(p){ return (!pos||p.pos===pos) && (!q||p._s.indexOf(q)>=0); }).map(function(p){return {p:p,v:val(p)};}).filter(function(x){return x.v>0;}).sort(function(a,b){return b.v-a.v;}).slice(0,200); var total=rows.length; rows=rows.slice(0,rkLimit); $('rkMore').hidden=total<=rkLimit;
    $('rkBody').innerHTML=rows.length?rows.map(function(x,i){ var p=x.p; return '<tr><td>'+(i+1)+'</td><td>'+tag(p)+' '+UI.esc(p.n)+(p.team?' <span class="hint" style="display:inline">'+p.team+'</span>':'')+'</td><td>'+(p.age||'—')+'</td><td>'+(p.ppg?p.ppg.ppr:'—')+'</td><td><strong>'+x.v.toLocaleString()+'</strong></td></tr>'; }).join(''):'<tr><td colspan="5"><div class="empty">No players match.</div></td></tr>';
    $('rkNote').textContent='Top '+rows.length+' by '+(opt().superflex?'superflex':'1QB')+(opt().tePremium?' + TE premium':'')+' value. PPG is PPR points per game this season.';
  }
  // ---------- Sleeper league import ----------
  var SLOTS={QB:['QB'],RB:['RB'],WR:['WR'],TE:['TE'],FLEX:['RB','WR','TE'],SUPER_FLEX:['QB','RB','WR','TE'],REC_FLEX:['WR','TE'],WRRB_FLEX:['WR','RB']};
  function api(path){ return fetch('https://api.sleeper.app/v1'+path).then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); }); }
  var lgState={user:null,leagues:[]};
  function loadLeagues(){
    var u=$('sleeperUser').value.trim(); if(!u){ $('lgPick').innerHTML='<div class="alert">'+UI.icon('info')+'<div>Enter your Sleeper username.</div></div>'; return; }
    $('lgBtn').disabled=true; $('lgPick').innerHTML='<p class="hint">Loading…</p>';
    api('/user/'+encodeURIComponent(u)).then(function(user){ if(!user||!user.user_id) throw new Error('nouser'); lgState.user=user; return api('/user/'+user.user_id+'/leagues/nfl/'+D.season); })
    .then(function(ls){ lgState.leagues=ls||[]; if(!ls||!ls.length){ $('lgPick').innerHTML='<div class="alert">'+UI.icon('info')+'<div>No '+D.season+' NFL leagues found for that user.</div></div>'; return; }
      $('lgPick').innerHTML='<label for="lgSel">League</label><select id="lgSel">'+ls.map(function(l){return '<option value="'+l.league_id+'">'+UI.esc(l.name)+'</option>';}).join('')+'</select>';
      $('lgSel').addEventListener('change',loadRoster); loadRoster(); })
    .catch(function(e){ $('lgPick').innerHTML='<div class="alert err">'+UI.icon('alert')+'<div>'+(e.message==='nouser'?'We couldn\'t find that Sleeper username. Check the spelling.':'Sleeper didn\'t respond. Try again in a moment.')+'</div></div>'; })
    .finally(function(){ $('lgBtn').disabled=false; });
  }
  function bestLineup(players,positions,fmt){
    var sc=players.map(function(p){return {p:p,s:FFCalc.startScore(p,fmt)};}).sort(function(a,b){return b.s.score-a.s.score;});
    var slots=(positions||[]).filter(function(s){return SLOTS[s];}).sort(function(a,b){return SLOTS[a].length-SLOTS[b].length;});
    var used={}, lineup=slots.map(function(s){ var pick=sc.filter(function(x){return !used[x.p.id] && SLOTS[s].indexOf(x.p.pos)>=0;})[0]; if(pick) used[pick.p.id]=1; return {slot:s,x:pick}; });
    var order=['QB','RB','WR','TE','WRRB_FLEX','REC_FLEX','FLEX','SUPER_FLEX']; lineup.sort(function(a,b){return order.indexOf(a.slot)-order.indexOf(b.slot);});
    return {lineup:lineup,total:lineup.reduce(function(t,l){return t+(l.x?l.x.s.score:0);},0),bench:sc.filter(function(x){return !used[x.p.id];})};
  }
  UI.bestLineup=bestLineup;
  function loadRoster(){
    var id=$('lgSel').value, lg=lgState.leagues.filter(function(l){return l.league_id===id;})[0], out=$('lgOut');
    out.innerHTML='<p class="hint">Loading league…</p>';
    Promise.all([api('/league/'+id+'/rosters'),api('/league/'+id+'/users').catch(function(){return [];})]).then(function(res){
      var rs=res[0]||[], users={}; (res[1]||[]).forEach(function(u){ users[u.user_id]=(u.metadata&&u.metadata.team_name)||u.display_name; });
      var mine=rs.filter(function(r){ return r.owner_id===lgState.user.user_id || (r.co_owners||[]).indexOf(lgState.user.user_id)>=0; })[0];
      var sc=lg.scoring_settings||{}, fmt=sc.rec>=1?'ppr':sc.rec>=0.5?'half':'std', sf=(lg.roster_positions||[]).indexOf('SUPER_FLEX')>=0, tep=(sc.bonus_rec_te||0)>0;
      var o={superflex:sf,tePremium:tep}, dv=function(p){ return FFCalc.dynastyValue(p,o); };
      var teams=rs.map(function(r){ var ps=(r.players||[]).map(function(pid){return BY[pid];}).filter(Boolean), L=bestLineup(ps,lg.roster_positions,fmt);
        return {r:r,name:users[r.owner_id]||('Team '+r.roster_id),mine:r===mine,L:L,dyn:ps.reduce(function(t,p){return t+dv(p);},0),w:(r.settings||{}).wins||0,l:(r.settings||{}).losses||0}; });
      var rostered={}; rs.forEach(function(r){ (r.players||[]).forEach(function(pid){ rostered[pid]=1; }); });
      var h='<h2>'+UI.icon('trophy')+UI.esc(lg.name)+'</h2>';
      var lineupHtml='', row=function(slot,x){ return '<tr><td>'+slot.replace('SUPER_FLEX','SF').replace('WRRB_FLEX','W/R').replace('REC_FLEX','W/T')+'</td><td style="text-align:left">'+(x?tag(x.p)+' '+UI.esc(x.p.n)+(x.s.note?' <span class="badge warn">'+UI.esc(x.p.inj||'bye')+'</span>':''):'<span class="hint">empty</span>')+'</td><td>'+(x?x.s.score:'—')+'</td></tr>'; };
      var me=teams.filter(function(t){return t.mine;})[0];
      if(me){ lineupHtml='<div class="verdict good"><span class="vicon">'+UI.icon('check')+'</span><div><strong class="big">Optimal lineup: '+me.L.total.toFixed(1)+' pts</strong><span>Week '+D.week+', '+({ppr:'PPR',half:'Half PPR',std:'standard'})[fmt]+' scoring. Kickers and defenses aren\'t scored.</span></div></div>'+
        '<div class="table-scroll" style="margin-top:12px"><table><thead><tr><th scope="col">Slot</th><th scope="col" style="text-align:left">Player</th><th scope="col">Score</th></tr></thead><tbody>'+me.L.lineup.map(function(l){return row(l.slot,l.x);}).join('')+'</tbody></table></div>'+
        '<h3 style="margin-top:14px">Bench</h3><div class="table-scroll"><table><tbody>'+me.L.bench.map(function(x){return row('BN',x);}).join('')+'</tbody></table></div>'; }
      else lineupHtml='<div class="alert">'+UI.icon('info')+'<div>No roster for you in this league. Power rankings and waivers still work.</div></div>';
      // power rankings: 60% this week's lineup strength, 40% dynasty value (each scaled to the league max)
      var mxL=Math.max.apply(null,teams.map(function(t){return t.L.total;}))||1, mxD=Math.max.apply(null,teams.map(function(t){return t.dyn;}))||1;
      teams.forEach(function(t){ t.pow=Math.round((0.6*t.L.total/mxL+0.4*t.dyn/mxD)*100); }); teams.sort(function(a,b){return b.pow-a.pow;});
      var prHtml='<div class="table-scroll"><table><thead><tr><th scope="col">#</th><th scope="col" style="text-align:left">Team</th><th scope="col">Record</th><th scope="col">Lineup pts</th><th scope="col">Dynasty value</th><th scope="col">Power</th></tr></thead><tbody>'+teams.map(function(t,i){ return '<tr'+(t.mine?' style="font-weight:700"':'')+'><td>'+(i+1)+'</td><td style="text-align:left">'+UI.esc(t.name)+(t.mine?' (you)':'')+'</td><td>'+t.w+'-'+t.l+'</td><td>'+t.L.total.toFixed(1)+'</td><td>'+Math.round(t.dyn).toLocaleString()+'</td><td><strong>'+t.pow+'</strong></td></tr>'; }).join('')+'</tbody></table></div><p class="hint">Power = 60% this week\'s best-lineup points + 40% total dynasty value, each scaled to the top team.</p>';
      // waiver helper: unrostered players, by start score this week and adds trend
      var worst={}; if(me) me.L.lineup.forEach(function(l){ if(l.x&&(!worst[l.x.p.pos]||l.x.s.score<worst[l.x.p.pos])) worst[l.x.p.pos]=l.x.s.score; });
      var fa=D.players.filter(function(p){return !rostered[p.id]&&p.team;}).map(function(p){return {p:p,s:FFCalc.startScore(p,fmt),v:dv(p)};}).sort(function(a,b){return (b.s.score+b.v/1000)-(a.s.score+a.v/1000);}).slice(0,15);
      var waHtml='<div class="table-scroll"><table><thead><tr><th scope="col" style="text-align:left">Free agent</th><th scope="col">Start score</th><th scope="col">Dynasty value</th><th scope="col">Adds (24h)</th><th scope="col">Upgrade?</th></tr></thead><tbody>'+fa.map(function(x){ var up=worst[x.p.pos]!=null&&x.s.score>worst[x.p.pos]; return '<tr><td style="text-align:left">'+tag(x.p)+' '+UI.esc(x.p.n)+' <span class="hint" style="display:inline">'+(x.p.team||'')+'</span></td><td>'+x.s.score+'</td><td>'+x.v.toLocaleString()+'</td><td>'+(x.p.trend?'+'+x.p.trend.toLocaleString():'—')+'</td><td>'+(up?'<span class="badge good">Beats a starter</span>':'')+'</td></tr>'; }).join('')+'</tbody></table></div><p class="hint">Players on no roster in this league, best first. “Beats a starter” = higher start score than your weakest starter at that position.</p>';
      var tabs=[['lineup','My lineup',lineupHtml],['power','Power rankings',prHtml],['waiver','Waiver helper',waHtml]], first=document.documentElement.getAttribute('data-panel')||'lineup';
      tabs.sort(function(a,b){ return (b[0]===first)-(a[0]===first); });
      h+=tabs.map(function(t){ return '<details class="adv lg-panel"'+(t[0]===tabs[0][0]?' open':'')+' id="lg-'+t[0]+'"><summary>'+t[1]+'</summary>'+t[2]+'</details>'; }).join('');
      out.innerHTML=h;
    }).catch(function(){ out.innerHTML='<div class="alert err">'+UI.icon('alert')+'<div>Couldn\'t load this league from Sleeper. Try again.</div></div>'; });
  }
  if($('lgForm')) $('lgForm').addEventListener('submit',loadLeagues);
  // ---------- Glue ----------
  if($('rkMore')) $('rkMore').addEventListener('click',function(){ rkLimit+=60; rankingsNow(); });
  function renderAll(){ startSit(); trade(); rankings(); history.replaceState(null,'',UI.stateURL($('ssOut')?{ss:sel.ss.join(',')}:$('trOut')?{a:sel.a.join(','),b:sel.b.join(',')}:{})); }
  document.addEventListener('click',function(e){ var s=e.target.closest('[data-share]'), c=e.target.closest('[data-copy]');
    var t=function(k){return k==='ss'?ssText:trText;};
    if(s) UI.share(location.href,'DynastyMath',t(s.dataset.share)); if(c) UI.copy(t(c.dataset.copy)+' '+location.href,'Copied'); });
  if($('rkPos')){ $('rkPos').addEventListener('change',rankings); $('rkFind').addEventListener('input',UI.debounce(rankings,80)); }
  var st=UI.readState(); UI.segs(renderAll); UI.syncSegs();
  fetch(UI.root()+'data/players.json').then(function(r){ if(!r.ok) throw new Error(); return r.json(); }).then(function(d){
    D=d; d.players.forEach(function(p){ p._s=norm(p.n+' '+(p.team||'')); BY[p.id]=p; });
    (d.picks||[]).forEach(function(p){ p._s=norm(p.n+' pick'); BY[p.id]=p; });
    ALLITEMS=d.players.concat(d.picks||[]);
    if($('dpDate')) $('dpDate').textContent=d.valuesDate||'—'; if($('dataDate')) $('dataDate').textContent=new Date(d.generated).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
    var ssPool=function(){return d.players;}, all=function(){return ALLITEMS;};
    if($('ssSearch')) combo('ssSearch','ssList','ss',ssPool,4,renderAll); if($('aSearch')){ combo('aSearch','aList','a',all,6,renderAll); combo('bSearch','bList','b',all,6,renderAll); }
    window.FFDATA=d; window.FFDETAIL={d:d,val:val,tag:tag}; document.dispatchEvent(new CustomEvent('ffdata',{detail:window.FFDETAIL}));
    var P=st.params, ids=function(k){ return (P.get(k)||'').split(',').filter(function(id){return BY[id];}); };
    if(P.has('ss')||P.has('a')||P.has('b')){ sel.ss=ids('ss'); sel.a=ids('a'); sel.b=ids('b'); }
    else { // sensible defaults: two healthy RBs with projections; a 1st-round pick vs a young WR
      var rb=d.players.filter(function(p){return p.pos==='RB'&&p.proj&&!p.inj;}).slice(2,4); sel.ss=rb.map(function(p){return p.id;});
      var wr=d.players.filter(function(p){return p.pos==='WR'&&p.v1;}).sort(function(a,b){return b.v1-a.v1;})[8], pk=(d.picks||[])[0];
      if(wr&&pk){ sel.a=[wr.id]; sel.b=[pk.id]; } }
    if(P.has('sleeperUser')&&$('lgForm')) loadLeagues();
    renderAll();
  }).catch(function(){ ['ssOut','trOut','dbOut'].forEach(function(id){ if($(id)) $(id).innerHTML='<div class="alert err">'+UI.icon('alert')+'<div>Player data didn\'t load. Check your connection and refresh.</div></div>'; }); });
})();
