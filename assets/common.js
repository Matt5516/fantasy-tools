/* Shared helpers (no dependencies) */
(function(){
  var fmt = new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2});
  window.Site = {
    money: function(n){ return isFinite(n) ? fmt.format(n) : '—'; },
    num: function(id){ var el=document.getElementById(id); var v=parseFloat(el && el.value); return isFinite(v)?v:0; },
    cls: function(n){ return n>=0?'pos':'neg'; },
    esc: function(s){ return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
  };
  // Email signup placeholder: no provider wired up yet. Replace the form action with beehiiv/other embed later.
  document.addEventListener('submit', function(e){
    var f = e.target;
    if (f.matches && f.matches('form[data-signup-placeholder]')) {
      e.preventDefault();
      var msg = f.parentNode.querySelector('.signup-msg');
      if (msg) msg.textContent = 'Thanks! Email signup is not connected yet. Check back soon.';
    }
  });
})();
