/* The Tilted Gent — shared site script: the mobile menu and the nav's section panels. Without JS the menu is a
   plain stacked list and the sections still open and close (they are native <details>). */
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

/* Concept tooltips, site-wide (Oki, 12 Oct 2026). data/terms.json, written by tools/glossary.py from the Table Talk
   glossaries, lists each term's short definition and the phrases that call it up. The first time a phrase appears in
   a page's running text it gets a dotted underline and the definition on hover, focus or tap; glossary links get the
   same tooltip and stay links. A page picks the right sense of a word with data-ctx="futures options" on <main>;
   poker terms apply on The Tables and inside the lessons' "At the table" boxes. Table Talk itself is left alone.
   reports/view.html calls window.tgTerms(doc, true) on each report. */
(function(){
  var DATA = null, waiting = [];
  function load(cb){
    if(DATA) return cb(DATA);
    waiting.push(cb);
    if(waiting.length > 1) return;
    // revalidated on each load, so a glossary edit shows at once
    fetch('/data/terms.json', {cache: 'no-cache'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(d){
      DATA = d; var w = waiting; waiting = []; if(d) w.forEach(function(f){ f(d); });
    }).catch(function(){});
  }
  var SKIP = 'h1,h2,h3,h4,h5,h6,a,button,input,select,textarea,label,option,script,style,svg,code,pre,nav,header,footer,' +
             'table,summary,aside,details,.ticker,.widget,.formula,.tt,.toc,.next,.callout,.legend,.out,.tg-tipl,.tg-tip,[data-no-terms]';
  // escape for a RegExp; a straight apostrophe in a phrase also matches the pages' curly one
  function esc(s){ return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/'/g, "['\u2019]"); }
  function place(t){
    var tip = t.querySelector('.tt-tip'); if(!tip) return;
    var w = t.ownerDocument.documentElement.clientWidth;
    tip.style.left = '0px'; tip.classList.remove('below');
    var shown = tip.style.display; tip.style.display = 'block';   // measure even if it isn't showing yet
    var r = tip.getBoundingClientRect(), want = Math.max(12, Math.min(r.left, w - 12 - r.width));
    tip.style.left = (want - r.left) + 'px';
    if(r.top < 84) tip.classList.add('below');
    tip.style.display = shown;
  }
  function wire(doc){
    if(doc.__ttWired) return; doc.__ttWired = true;
    function find(e){ return e.target && e.target.closest ? e.target.closest('.tt') : null; }
    doc.addEventListener('mouseover', function(e){ var t = find(e); if(t) place(t); });
    doc.addEventListener('focusin', function(e){ var t = find(e); if(t) place(t); });
    doc.addEventListener('click', function(e){
      var t = find(e);
      Array.prototype.forEach.call(doc.querySelectorAll('.tt.open'), function(o){ if(o !== t) o.classList.remove('open'); });
      if(t && t.tagName !== 'A'){ t.classList.toggle('open'); if(t.classList.contains('open')) place(t); }
    });
    doc.addEventListener('keydown', function(e){
      if(e.key === 'Escape') Array.prototype.forEach.call(doc.querySelectorAll('.tt.open'), function(o){ o.classList.remove('open'); });
    });
  }
  function tipFor(d, key, ctx){
    var t = d.terms[key]; if(!t) return null;
    var s = t[1], senses = t[2] || {};
    for(var i = 0; i < ctx.length; i++) if(senses[ctx[i]]){ s = senses[ctx[i]]; break; }
    return [t[0], s];
  }
  function tipNode(doc, text){
    var tip = doc.createElement('span'); tip.className = 'tt-tip'; tip.setAttribute('role', 'tooltip');
    var b = doc.createElement('b'); b.textContent = text[0]; tip.appendChild(b); tip.appendChild(doc.createTextNode(text[1]));
    return tip;
  }
  function run(doc, isReport){
    var path = (doc.defaultView || window).location.pathname;
    if(!isReport && /^\/learn\/table-talk\//.test(path)) return;
    if(/^\/tables\/(.*-table|blackjack-trainer)\.html$/.test(path)) return;   // the trainers: the game board is no place for tooltips
    var root = isReport ? doc.body : (doc.querySelector('main') || doc.body);   // pages without <main>: the body (nav, header and footer are skipped)
    if(!root) return;
    load(function(d){
      var tables = /^\/tables\//.test(path);
      var ctx = (root.getAttribute('data-ctx') || '').split(/\s+/).filter(Boolean);
      if(tables) ctx.push('tables');
      if(/^\/tables\/(ultimate-texas-holdem|three-card-poker|video-poker)/.test(path)) ctx.push('poker');   // the poker-game pages
      var used = {};
      Array.prototype.forEach.call(root.querySelectorAll('.tt[data-tt]'), function(t){ used[t.getAttribute('data-tt')] = 1; });
      // glossary links: same tooltip, still a link
      Array.prototype.forEach.call(root.querySelectorAll('a[href*="/learn/table-talk/"]:not(.tt)'), function(a){
        var m = a.getAttribute('href').match(/table-talk\/(finance|poker)\.html#([a-z0-9-]+)/);
        if(!m || (a.parentElement && a.parentElement.closest(SKIP))) return;
        var key = (m[1] === 'poker' ? 'p:' : 'f:') + m[2], text = tipFor(d, key, ctx);
        if(!text || used[key]) return;
        used[key] = 1; a.classList.add('tt'); a.setAttribute('data-tt', key); a.appendChild(tipNode(doc, text));
      });
      // two matchers: the page's own contexts, and, for the "At the table" boxes, the poker contexts as well
      function matcher(cx, pokerFirst){
        var by = {}, phrases = [];
        d.match.forEach(function(m){
          var p = m[0].toLowerCase();
          if(m[2] && cx.indexOf(m[2]) < 0) return;
          if(!by[p]){ by[p] = []; phrases.push(m[0]); }
          by[p].push(m);
        });
        Object.keys(by).forEach(function(p){   // poker first at the casino and in the boxes, finance first elsewhere
          by[p].sort(function(a, b){ return ((a[1].charAt(0) === 'p') === pokerFirst ? 0 : 1) - ((b[1].charAt(0) === 'p') === pokerFirst ? 0 : 1); });
        });
        phrases.sort(function(a, b){ return b.length - a.length; });
        return phrases.length ? {by: by, re: new RegExp('(?<![\\w-])(' + phrases.map(esc).join('|') + ')(?![\\w-])', 'gi')} : null;
      }
      var pageM = matcher(ctx, tables), lensM = matcher(ctx.concat(['poker', 'tables']), true);
      var walker = doc.createTreeWalker(root, 4, null), nodes = [], n;
      while((n = walker.nextNode())) if(n.nodeValue.trim() && !(n.parentElement && n.parentElement.closest(SKIP))) nodes.push(n);
      nodes.forEach(function(node){
        var lens = !!(node.parentElement && node.parentElement.closest('.lens')), M = lens ? lensM : pageM;
        if(!M) return;
        var re = M.re, by = M.by, text = node.nodeValue, m, cut = 0, frag = null;
        re.lastIndex = 0;
        while((m = re.exec(text))){
          var cands = by[m[1].toLowerCase()] || [], pick = null;
          for(var i = 0; i < cands.length && !pick; i++){
            var c = cands[i], poker = c[1].charAt(0) === 'p';
            if(used[c[1]]) continue;
            if(poker ? (tables || lens) : !tables) pick = c;   // The Tables use the poker glossary only
          }
          if(!pick) continue;
          var label = tipFor(d, pick[1], ctx); if(!label) continue;
          used[pick[1]] = 1;
          frag = frag || doc.createDocumentFragment();
          frag.appendChild(doc.createTextNode(text.slice(cut, m.index)));
          var span = doc.createElement('span'); span.className = 'tt'; span.tabIndex = 0; span.setAttribute('data-tt', pick[1]);
          span.appendChild(doc.createTextNode(m[1])); span.appendChild(tipNode(doc, label));
          frag.appendChild(span); cut = m.index + m[1].length;
        }
        if(frag){ frag.appendChild(doc.createTextNode(text.slice(cut))); node.parentNode.replaceChild(frag, node); }
      });
      wire(doc);
    });
  }
  window.tgTerms = function(doc, isReport){
    doc = doc || document;
    if(isReport && !doc.querySelector('link[data-tt-css]')){
      var l = doc.createElement('link'); l.rel = 'stylesheet'; l.href = '/assets/terms.css?v=20261012'; l.setAttribute('data-tt-css', '');
      doc.head.appendChild(l);
    }
    run(doc, !!isReport);
  };
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function(){ window.tgTerms(document); });
  else window.tgTerms(document);
})();
