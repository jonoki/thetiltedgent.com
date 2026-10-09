/* The Tilted Gent — shared site script: the mobile menu and the nav's section panels. Without JS the menu is a
   plain stacked list and the sections still open and close (they are native <details>). */
(function(){
  // the footer's Feedback link starts a bug report with this page filled in (tools/chrome.py FEEDBACK)
  var fb = document.querySelector('footer.site a[data-feedback]');
  if(fb && location.pathname.indexOf('/feedback/') !== 0)
    fb.href = '/feedback/?type=bug&page=' + encodeURIComponent(location.pathname + location.search);
})();
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
  // the sections that open a panel (<details>): one open at a time, closed by Esc or a click elsewhere
  var menus = nav.querySelectorAll('details.navmenu');
  function closeMenus(except){
    Array.prototype.forEach.call(menus, function(d){ if(d !== except) d.open = false; });
  }
  Array.prototype.forEach.call(menus, function(d){
    d.addEventListener('toggle', function(){ if(d.open) closeMenus(d); });
  });
  document.addEventListener('click', function(e){ if(!nav.contains(e.target)) closeMenus(null); });
  // mark this page in the panels (the server marks only the section)
  var here = location.pathname.replace(/index\.html$/, '') + location.search;
  Array.prototype.forEach.call(nav.querySelectorAll('.navgroup a'), function(a){
    if(a.pathname.replace(/index\.html$/, '') + a.search === here) a.setAttribute('aria-current', 'page');
  });
  document.addEventListener('keydown', function(e){
    if(e.key !== 'Escape') return;
    var open = nav.querySelector('details.navmenu[open]');
    if(open){ open.open = false; open.querySelector('summary').focus(); return; }
    if(nav.classList.contains('open')){ set(false); btn.focus(); }
  });
})();
