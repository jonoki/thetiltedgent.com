/* The Tilted Gent — shared site script: the mobile menu. Without JS the menu is a plain stacked list. */
(function(){
  var nav = document.querySelector('nav.site');
  var btn = nav && nav.querySelector('.navtoggle');
  if(!btn) return;
  function set(open){
    nav.classList.toggle('open', open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  btn.addEventListener('click', function(){ set(!nav.classList.contains('open')); });
  Array.prototype.forEach.call(nav.querySelectorAll('.navlinks a'), function(a){
    a.addEventListener('click', function(){ set(false); });
  });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && nav.classList.contains('open')){ set(false); btn.focus(); }
  });
})();
