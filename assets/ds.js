/* Shared UI helpers: theme, URL state, share/copy, toast, SVG charts, formatting. No dependencies. */
(function(){
  var d=document, root=d.documentElement, KEY='theme';
  // Theme: saved choice > OS preference. Applied early by inline snippet in <head>; here we wire the toggle.
  function setTheme(t){ root.setAttribute('data-theme',t); try{localStorage.setItem(KEY,t);}catch(e){} var b=d.getElementById('themeBtn'); if(b) b.setAttribute('aria-label', t==='dark'?'Switch to light mode':'Switch to dark mode'); }
  var money0=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0});
  var money2=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2});
  var UI = window.UI = {
    $: function(id){ return d.getElementById(id); },
    money: function(n,whole){ if(n===null||n===undefined||!isFinite(n)) return '—'; return (whole?money0:money2).format(n); },
    signed: function(n,whole){ return (n>0?'+':'')+UI.money(n,whole); },
    num: function(id){ var el=d.getElementById(id); if(!el) return 0; var v=parseFloat(String(el.value).replace(/[,$\s]/g,'')); return isFinite(v)?v:0; },
    cls: function(n){ return n>=0?'pos':'neg'; },
    esc: function(s){ return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); },
    icon: function(name){ return '<svg class="icon" aria-hidden="true"><use href="#i-'+name+'"/></svg>'; },
    toast: function(msg){ var t=d.getElementById('toast'); if(!t){t=d.createElement('div');t.id='toast';t.className='toast';t.setAttribute('role','status');d.body.appendChild(t);} t.textContent=msg; t.classList.add('show'); clearTimeout(t._h); t._h=setTimeout(function(){t.classList.remove('show');},2200); },
    copy: function(text,msg){ function ok(){UI.toast(msg||'Copied');} if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(text).then(ok,fallback);} else fallback();
      function fallback(){ var ta=d.createElement('textarea'); ta.value=text; ta.style.position='fixed'; ta.style.opacity='0'; d.body.appendChild(ta); ta.select(); try{d.execCommand('copy'); ok();}catch(e){UI.toast('Copy failed: select and copy manually');} d.body.removeChild(ta);} },
    // URL state: every element with [data-state] is saved to ?id=value
    readState: function(){ var p=new URLSearchParams(location.search), n=0; d.querySelectorAll('[data-state]').forEach(function(el){ if(el.dataset.def==null) el.dataset.def=el.value; if(p.has(el.id)){ el.value=p.get(el.id); n++; } }); return {params:p,count:n}; },
    stateURL: function(extra){ var p=new URLSearchParams(); d.querySelectorAll('[data-state]').forEach(function(el){ var dv=el.dataset.def!=null?el.dataset.def:el.defaultValue; if(el.value!==dv && !(el.tagName==='SELECT' && el.dataset.def==null && el.selectedOptions[0] && el.selectedOptions[0].defaultSelected)) p.set(el.id,el.value); }); if(extra) Object.keys(extra).forEach(function(k){ if(extra[k]!==''&&extra[k]!=null) p.set(k,extra[k]); }); var q=p.toString(); return location.origin+location.pathname+(q?'?'+q:'')+location.hash.replace(/#.*/,''); },
    share: function(url,title,text){ if(navigator.share){ navigator.share({title:title,text:text,url:url}).catch(function(){}); } else UI.copy(url,'Link copied'); },
    // segmented controls: <div class="seg" data-for="hiddenInputId"><button data-v="x">
    segs: function(onchange){ d.querySelectorAll('.seg[data-for]').forEach(function(seg){ var inp=d.getElementById(seg.dataset.for);
      function sync(){ seg.querySelectorAll('button').forEach(function(b){ b.setAttribute('aria-pressed', String(b.dataset.v===inp.value)); }); }
      seg.addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; inp.value=b.dataset.v; sync(); inp.dispatchEvent(new Event('change',{bubbles:true})); if(onchange) onchange(); });
      inp.addEventListener('sync',sync); sync(); }); },
    syncSegs: function(){ d.querySelectorAll('.seg[data-for]').forEach(function(seg){ var inp=d.getElementById(seg.dataset.for); inp.dispatchEvent(new Event('sync')); }); },
    // Minimal SVG charts
    bars: function(items,opt){ // items: [{label,value,color?}]
      opt=opt||{}; var W=560,H=opt.h||220,P={l:56,r:12,t:14,b:34}, n=items.length; if(!n) return '';
      var vals=items.map(function(i){return i.value;}), mx=Math.max(0,Math.max.apply(null,vals)), mn=Math.min(0,Math.min.apply(null,vals)); if(mx===mn) mx=mn+1;
      var y=function(v){return P.t+(mx-v)/(mx-mn)*(H-P.t-P.b);}, bw=(W-P.l-P.r)/n, s='<svg class="chart" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+UI.esc(opt.label||'Bar chart')+'">';
      UI.ticks(mn,mx).forEach(function(t){ s+='<line class="grid" x1="'+P.l+'" x2="'+(W-P.r)+'" y1="'+y(t)+'" y2="'+y(t)+'"/><text x="'+(P.l-6)+'" y="'+(y(t)+4)+'" text-anchor="end">'+(opt.fmt||UI.short)(t)+'</text>'; });
      items.forEach(function(it,i){ var x=P.l+i*bw+bw*0.18, w=bw*0.64, y0=y(0), y1=y(it.value), c=it.color||(it.value>=0?'var(--good)':'var(--bad)');
        s+='<rect x="'+x+'" y="'+Math.min(y0,y1)+'" width="'+w+'" height="'+Math.max(1,Math.abs(y1-y0))+'" rx="6" fill="'+c+'"><title>'+UI.esc(it.label)+': '+(opt.fmt||UI.short)(it.value)+'</title></rect>';
        s+='<text x="'+(x+w/2)+'" y="'+(H-P.b+16)+'" text-anchor="middle">'+UI.esc(it.label)+'</text>'; });
      return s+'<line x1="'+P.l+'" x2="'+(W-P.r)+'" y1="'+y(0)+'" y2="'+y(0)+'" stroke="var(--muted)"/></svg>'; },
    lines: function(series,opt){ // series: [{name,color,points:[[x,y]]}], opt.marks: [{x,label}]
      opt=opt||{}; var W=560,H=opt.h||240,P={l:56,r:14,t:14,b:34}, xs=[],ys=[];
      series.forEach(function(s){ s.points.forEach(function(p){xs.push(p[0]);ys.push(p[1]);}); });
      var x0=Math.min.apply(null,xs),x1=Math.max.apply(null,xs),y0=Math.min(0,Math.min.apply(null,ys)),y1=Math.max.apply(null,ys); if(y1===y0) y1=y0+1;
      var X=function(v){return P.l+(v-x0)/(x1-x0||1)*(W-P.l-P.r);}, Y=function(v){return P.t+(y1-v)/(y1-y0)*(H-P.t-P.b);};
      var s='<svg class="chart" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+UI.esc(opt.label||'Line chart')+'">';
      UI.ticks(y0,y1).forEach(function(t){ s+='<line class="grid" x1="'+P.l+'" x2="'+(W-P.r)+'" y1="'+Y(t)+'" y2="'+Y(t)+'"/><text x="'+(P.l-6)+'" y="'+(Y(t)+4)+'" text-anchor="end">'+UI.short(t)+'</text>'; });
      UI.ticks(x0,x1).forEach(function(t){ s+='<text x="'+X(t)+'" y="'+(H-P.b+18)+'" text-anchor="middle">'+UI.short(t)+'</text>'; });
      (opt.marks||[]).forEach(function(m){ s+='<line x1="'+X(m.x)+'" x2="'+X(m.x)+'" y1="'+P.t+'" y2="'+(H-P.b)+'" stroke="var(--muted)" stroke-dasharray="4 4"/><text x="'+(X(m.x)+4)+'" y="'+(P.t+12)+'">'+UI.esc(m.label)+'</text>'; });
      series.forEach(function(sr){ s+='<polyline fill="none" stroke="'+sr.color+'" stroke-width="3" stroke-linejoin="round" points="'+sr.points.map(function(p){return X(p[0]).toFixed(1)+','+Y(p[1]).toFixed(1);}).join(' ')+'"><title>'+UI.esc(sr.name)+'</title></polyline>'; });
      if (opt.dot) s+='<circle cx="'+X(opt.dot[0])+'" cy="'+Y(opt.dot[1])+'" r="5" fill="var(--ink)"/>';
      return s+'</svg>'; },
    ticks: function(a,b){ var span=b-a, step=Math.pow(10,Math.floor(Math.log10(span||1))); if(span/step>8) step*=2; if(span/step>8) step*=2.5; if(span/step<3) step/=2; var out=[]; for(var v=Math.ceil(a/step)*step; v<=b+1e-9; v+=step) out.push(Math.round(v*100)/100); return out; },
    short: function(v){ var a=Math.abs(v), s=v<0?'-':''; return s+'$'+(a>=1e6?(a/1e6).toFixed(1)+'M':a>=1e3?(a/1e3).toFixed(a>=1e4?0:1)+'k':Math.round(a)); },
    debounce: function(fn,ms){ var h; return function(){ clearTimeout(h); h=setTimeout(fn,ms||60); }; }
  };
  d.addEventListener('click',function(e){ if(e.target.closest('#themeBtn')) setTheme(root.getAttribute('data-theme')==='dark'?'light':'dark'); });

  // ---- v4 shared components ----
  // Preset chips: <div class="presets" data-target="inputId"><button data-v="25">$25</button>…</div> sets the input and fires input
  d.addEventListener('click',function(e){ var b=e.target.closest('.presets button'); if(!b) return; var box=b.parentNode, inp=d.getElementById(box.dataset.target); if(!inp) return;
    inp.value=b.dataset.v; inp.dispatchEvent(new Event('input',{bubbles:true})); UI.syncPresets(); });
  UI.syncPresets=function(){ d.querySelectorAll('.presets').forEach(function(box){ var inp=d.getElementById(box.dataset.target); if(!inp) return; box.querySelectorAll('button').forEach(function(b){ b.setAttribute('aria-pressed',String(b.dataset.v===String(inp.value))); }); }); };
  d.addEventListener('input',function(e){ if(e.target.id) UI.syncPresets(); });
  // Stepper: <div class="stepper"><button data-step="-1">−</button><input …><button data-step="1">+</button></div>
  d.addEventListener('click',function(e){ var b=e.target.closest('.stepper button'); if(!b) return; var inp=b.parentNode.querySelector('input'); var v=(+inp.value||0)+(+b.dataset.step)*(+inp.step||1);
    if(inp.min!=='') v=Math.max(+inp.min,v); if(inp.max!=='') v=Math.min(+inp.max,v); inp.value=v; inp.dispatchEvent(new Event('input',{bubbles:true})); });
  // Range + number pairs: <input type=range data-mirror="id">
  d.addEventListener('input',function(e){ var r=e.target; if(r.dataset&&r.dataset.mirror){ var t=d.getElementById(r.dataset.mirror); t.value=r.value; t.dispatchEvent(new Event('input',{bubbles:true})); }
    d.querySelectorAll('input[data-mirror="'+r.id+'"]').forEach(function(x){ if(x!==r) x.value=r.value; }); });
  // Print / save as PDF
  d.addEventListener('click',function(e){ if(e.target.closest('[data-print]')) window.print(); });
  // Tiny localStorage store
  UI.store={ get:function(k,def){ try{ var v=JSON.parse(localStorage.getItem(k)); return v==null?def:v; }catch(e){ return def; } }, set:function(k,v){ try{ localStorage.setItem(k,JSON.stringify(v)); }catch(e){} } };
  UI.root=function(){ return d.documentElement.getAttribute('data-root')||''; };
  if(d.readyState!=='loading') UI.syncPresets(); else d.addEventListener('DOMContentLoaded',UI.syncPresets);
})();
/* Feedback: thumbs + "what should we add?" + optional email. Opens a prefilled GitHub issue (public, labelled "feedback")
   on this site's repo, or an email to the owner. Nothing is sent until the visitor submits it in GitHub or their mail app. */
(function(){ var d=document, repo=d.documentElement.getAttribute('data-repo'), MAIL='mathtools@mail.grokbot.com'; if(!repo) return;
  function init(){ if(d.getElementById('fbBtn')) return;
    var b=d.createElement('button'); b.type='button'; b.id='fbBtn'; b.className='fb-btn'; b.innerHTML='<span aria-hidden="true">💬</span>Feedback'; d.body.appendChild(b);
    var dl=d.createElement('dialog'); dl.className='fb'; dl.setAttribute('aria-labelledby','fbH');
    dl.innerHTML='<form method="dialog" id="fbForm"><h2 id="fbH">Was this useful?</h2><div class="fb-thumbs" role="group" aria-label="Was this useful?"><button type="button" data-r="yes" aria-pressed="false">👍 Yes</button><button type="button" data-r="no" aria-pressed="false">👎 Not really</button></div>'+
      '<label for="fbText">What is missing or wrong?</label><textarea id="fbText" rows="3" maxlength="1500" placeholder="e.g. add SGC crossover pricing"></textarea>'+
      '<label for="fbEmail" style="margin-top:8px;display:block">Your email <span class="hint" style="display:inline">(optional, only if you want a reply)</span></label><input id="fbEmail" type="email" autocomplete="email" placeholder="you@example.com">'+
      '<p class="fb-url">Page: <span id="fbUrl"></span></p>'+
      '<div class="actions"><button type="button" class="btn sm" id="fbGh">Send via GitHub</button><button type="button" class="btn ghost sm" id="fbMail">Send by email</button><button type="submit" class="btn ghost sm" value="cancel">Close</button></div>'+
      '<p class="hint" style="margin-top:8px">GitHub issues are public and need a free GitHub login; your email is never put in a GitHub issue. No GitHub? Use “Send by email”.</p></form>';
    d.body.appendChild(dl); var rate='';
    function msg(){ var t=d.getElementById('fbText').value.trim(); return {t:t, title:'[feedback] '+(rate==='yes'?'👍 ':rate==='no'?'👎 ':'')+(t.slice(0,60)||d.title.split('|')[0].trim()),
      body:'**Page:** '+location.href+'\n**Useful:** '+(rate||'not answered')+'\n\n**What is missing or wrong?**\n'+(t||'(nothing written)')+'\n\n---\nSent from the feedback form.'}; }
    b.addEventListener('click',function(){ d.getElementById('fbUrl').textContent=location.href; if(dl.showModal) dl.showModal(); else dl.setAttribute('open',''); });
    dl.addEventListener('click',function(e){ var r=e.target.closest('[data-r]'); if(r){ rate=r.dataset.r; dl.querySelectorAll('[data-r]').forEach(function(x){ x.setAttribute('aria-pressed',String(x===r)); }); } });
    d.getElementById('fbGh').addEventListener('click',function(){ var m=msg(); window.open('https://github.com/Matt5516/'+repo+'/issues/new?template=feedback.md&labels=feedback&title='+encodeURIComponent(m.title)+'&body='+encodeURIComponent(m.body),'_blank','noopener'); dl.close&&dl.close(); });
    d.getElementById('fbMail').addEventListener('click',function(){ var m=msg(), e=d.getElementById('fbEmail').value.trim(); location.href='mailto:'+MAIL+'?subject='+encodeURIComponent(m.title)+'&body='+encodeURIComponent(m.body+(e?'\nReply to: '+e:'')); dl.close&&dl.close(); });
  }
  if(d.readyState==='loading') d.addEventListener('DOMContentLoaded',init); else init();
})();
/* v5: share bar, result image, embed mode */
(function(){ var d=document, w=window;
  var q=new URLSearchParams(location.search), inFrame=false; try{inFrame=w.self!==w.top;}catch(e){inFrame=true;}
  var embed=q.get('embed')==='1';
  if(embed) d.documentElement.classList.add('embed');
  function cleanUrl(){ var u=new URL(location.href); u.searchParams.delete('embed'); return u.toString(); }
  function resultEl(){ return d.querySelector('main .sticky [aria-live]')||d.querySelector('main [aria-live]'); }
  function lines(){ var el=resultEl(); if(!el) return []; var L=(el.innerText||'').split('\n').map(function(s){return s.trim();}).filter(function(s){return s&&s.length<90;}); var o=[]; L.forEach(function(s){ if(o.length&&/^[-+−$€£\d]/.test(s)&&!/[:\d]$/.test(o[o.length-1])) o[o.length-1]+=': '+s; else o.push(s); }); return o.slice(0,7); }
  function wrap(ctx,t,max){ var out=[],cur=''; t.split(' ').forEach(function(wd){ var x=cur?cur+' '+wd:wd; if(ctx.measureText(x).width>max&&cur){out.push(cur);cur=wd;} else cur=x; }); if(cur) out.push(cur); return out; }
  function image(){ var cs=getComputedStyle(d.documentElement), b1=cs.getPropertyValue('--brand').trim()||'#333', b2=cs.getPropertyValue('--brand-2').trim()||b1;
    var cv=d.createElement('canvas'); cv.width=1200; cv.height=630; var x=cv.getContext('2d'); var g=x.createLinearGradient(0,0,1200,630); g.addColorStop(0,b1); g.addColorStop(1,b2); x.fillStyle=g; x.fillRect(0,0,1200,630);
    x.fillStyle='rgba(255,255,255,.96)'; x.beginPath(); if(x.roundRect) x.roundRect(48,48,1104,534,28); else x.rect(48,48,1104,534); x.fill();
    var site=(d.querySelector('meta[property="og:site_name"]')||{}).content||d.title.split('|').pop().trim(), h1=(d.querySelector('h1')||{}).textContent||d.title;
    x.fillStyle=b1; x.font='700 30px system-ui,sans-serif'; x.fillText(site,96,116);
    x.fillStyle='#111'; x.font='800 46px system-ui,sans-serif'; var y=180; wrap(x,h1,1000).slice(0,2).forEach(function(l){x.fillText(l,96,y); y+=56;});
    x.font='500 30px system-ui,sans-serif'; x.fillStyle='#333'; var L=lines(); if(!L.length) L=['Free, no signup. Try your own numbers.'];
    L.forEach(function(l){ if(y>500) return; wrap(x,l,1000).slice(0,1).forEach(function(s){x.fillText(s,96,y+10); y+=44;}); });
    x.fillStyle='#555'; x.font='600 24px system-ui,sans-serif'; x.fillText(cleanUrl().replace(/^https?:\/\//,'').split('?')[0],96,552);
    cv.toBlob(function(bl){ if(!bl){ UI.toast('Could not make the image'); return; } var f; try{ f=new File([bl],'result.png',{type:'image/png'}); }catch(e){}
      if(f&&navigator.canShare&&navigator.canShare({files:[f]})){ navigator.share({files:[f],title:h1,url:cleanUrl()}).catch(function(){}); return; }
      var a=d.createElement('a'); a.href=URL.createObjectURL(bl); a.download=(site+'-result.png').replace(/\s+/g,'-').toLowerCase(); d.body.appendChild(a); a.click(); setTimeout(function(){URL.revokeObjectURL(a.href); a.remove();},500); UI.toast('Image saved'); },'image/png'); }
  function init(){
    if(embed){ var c=d.createElement('a'); c.className='embed-credit'; c.href=cleanUrl(); c.target='_blank'; c.rel='noopener'; var nm=(d.querySelector('meta[property="og:site_name"]')||{}).content||'the full site';
      c.textContent='Open on '+nm+' ↗'; d.body.appendChild(c); d.querySelectorAll('main a[href]').forEach(function(a){ if(!a.target && !/^#/.test(a.getAttribute('href'))) a.target='_blank'; }); }
    d.addEventListener('click',function(e){ var el=e.target.closest&&e.target.closest('[data-share]'); if(!el) return; var k=el.getAttribute('data-share'), u=cleanUrl(), box=el.closest('.share-embed'), title=box?box.getAttribute('data-share-title'):d.title;
      if(k==='copy'){ UI.share?UI.share(u,title,title):UI.copy(u,'Link copied'); }
      else if(k==='img'){ image(); }
      else if(k==='embed'){ var ta=box&&box.querySelector('textarea'); if(ta) UI.copy(ta.value,'Embed code copied'); }
      else { var eu=encodeURIComponent(u), href=el.getAttribute('href'); el.setAttribute('href', href.replace(/(url=|u=|body=)[^&]*/, '$1'+eu)); } });
  }
  if(d.readyState==='loading') d.addEventListener('DOMContentLoaded',init); else init();
})();
