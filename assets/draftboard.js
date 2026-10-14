/* Rookie & startup draft board: ranked by dynasty value, tap to mark drafted (saved in this browser). */
(function(){ var $=UI.$, KEY='dm-drafted', done=UI.store.get(KEY,{});
  document.addEventListener('ffdata',function(e){ var d=e.detail.d, val=e.detail.val, tag=e.detail.tag;
    function run(){ var pool=$('dbPool').value, pos=$('dbPos').value, hide=$('dbHide').checked;
      var rows=d.players.filter(function(p){ return (pool==='all'||p.exp===0)&&(!pos||p.pos===pos); }).map(function(p){return {p:p,v:val(p)};}).filter(function(x){return x.v>0;}).sort(function(a,b){return b.v-a.v;}).slice(0,pool==='all'?250:120);
      var left=rows.filter(function(x){return !done[x.p.id];}), shown=hide?left:rows;
      var nx=left[0];
      $('dbOut').innerHTML=(nx?'<div class="verdict good"><span class="vicon">'+UI.icon('check')+'</span><div><strong class="big">Best available: '+UI.esc(nx.p.n)+'</strong><span>'+nx.p.pos+' · '+(nx.p.team||'FA')+' · value '+nx.v.toLocaleString()+'. '+(rows.length-left.length)+' drafted so far.</span></div></div>':'')+
        '<div class="table-scroll" style="margin-top:12px"><table><thead><tr><th scope="col">#</th><th scope="col" style="text-align:left">Player</th><th scope="col">Age</th><th scope="col">Value</th><th scope="col">Drafted</th></tr></thead><tbody>'+shown.map(function(x){ var p=x.p, i=rows.indexOf(x); return '<tr'+(done[p.id]?' style="opacity:.45;text-decoration:line-through"':'')+'><td>'+(i+1)+'</td><td style="text-align:left">'+tag(p)+' '+UI.esc(p.n)+' <span class="hint" style="display:inline">'+(p.team||'')+'</span></td><td>'+(p.age||'—')+'</td><td><strong>'+x.v.toLocaleString()+'</strong></td><td><input type="checkbox" data-db="'+UI.esc(p.id)+'"'+(done[p.id]?' checked':'')+' aria-label="Mark '+UI.esc(p.n)+' drafted"></td></tr>'; }).join('')+'</tbody></table></div>';
      history.replaceState(null,'',UI.stateURL()); }
    $('dbOut').addEventListener('change',function(e){ var c=e.target.closest('[data-db]'); if(!c) return; if(c.checked) done[c.dataset.db]=1; else delete done[c.dataset.db]; UI.store.set(KEY,done); run(); });
    ['dbPool','dbPos','dbHide'].forEach(function(id){ $(id).addEventListener('change',run); });
    $('dbReset').addEventListener('click',function(){ done={}; UI.store.set(KEY,done); run(); });
    if($('sf')) $('sf').addEventListener('change',run); run(); });
})();
