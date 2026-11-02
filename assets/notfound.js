// 404 rescue: send old or mistyped addresses to the closest real page.
(function(){
  var box=document.getElementById('nf-suggest'); if(!box) return;
  var root=document.documentElement.getAttribute('data-root')||'/';
  var seg=location.pathname.slice(root.length).replace(/\/+$/,'').split('/')[0].toLowerCase().replace(/\.html$/,'');
  if(!seg) return;
  fetch(root+'sitemap.xml').then(function(r){return r.text();}).then(function(x){
    var slugs=[],m,re=/<loc>https?:\/\/[^\/]+\/([^<]*?)\/?<\/loc>/g;
    while((m=re.exec(x))) if(m[1]&&m[1].indexOf('/')<0) slugs.push(m[1]);
    var go=function(s){location.replace(root+s+'/'+location.search+location.hash);};
    // Player pages that gained a suffix (Jr, Sr, II, III).
    var ext=slugs.filter(function(s){return s.indexOf(seg+'-')===0&&/-(jr|sr|ii|iii|iv)$/.test(s);});
    if(ext.length===1) return go(ext[0]);
    // Old weekly pages: send to this week's version.
    var w=seg.match(/^week-\d+-(.+)$/);
    if(w){var best=null,bn=-1;slugs.forEach(function(s){var k=s.match(/^week-(\d+)-(.+)$/);if(k&&k[2]===w[1]&&+k[1]>bn){bn=+k[1];best=s;}});if(best) return go(best);}
    // Otherwise suggest the closest pages by shared words.
    var stop={dynasty:1,value:1,start:1,or:1,sit:1,vs:1,week:1,rankings:1,jr:1,sr:1};
    var words=seg.split('-').filter(function(t){return t.length>1&&!stop[t];});
    if(!words.length) return;
    var scored=slugs.map(function(s){var p=s.split('-'),n=0;words.forEach(function(t){if(p.indexOf(t)>=0)n++;});if(n&&s.split('-').slice(0,2).join('-')===seg.split('-').slice(0,2).join('-'))n+=0.5;return [n,s];})
      .filter(function(a){return a[0]>0;}).sort(function(a,b){return b[0]-a[0]||a[1].length-b[1].length;}).slice(0,6);
    if(!scored.length) return;
    var nice=function(s){return s.replace(/-/g,' ').replace(/\b(\w)/g,function(c){return c.toUpperCase();}).replace(/\bVs\b/g,'vs').replace(/\bOr\b/g,'or');};
    box.innerHTML='<p>Looking for one of these?</p><ul>'+scored.map(function(a){return '<li><a href="'+root+a[1]+'/">'+nice(a[1])+'</a></li>';}).join('')+'</ul>';
  }).catch(function(){});
})();
