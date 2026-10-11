// Report tooltips (Oki, 10 Oct 2026). reports/view.html calls tgTips(doc) once a report has loaded in its frame: each
// label listed in data/report_labels.json gets a dotted underline and a tooltip on hover, tap or keyboard focus, with
// a link to the finance glossary when the entry names a term. The report files are never changed, and a label that
// isn't found, or markup that isn't expected, is simply skipped. tools/glossary.py checks the data file.
(function(){
  var labels=null, queue=[];
  fetch('/data/report_labels.json').then(function(r){return r.ok?r.json():null;}).then(function(d){
    labels=(d&&d.labels)||[]; queue.forEach(run); queue=[];
  }).catch(function(){ labels=[]; queue=[]; });

  window.tgTips=function(doc){ if(labels) run(doc); else queue.push(doc); };

  var CSS='.tg-tipl{text-decoration:underline dotted rgba(217,168,92,.75);text-underline-offset:3px;cursor:help;}'+
    '.tg-tipl:focus-visible{outline:2px solid #1FCBE3;outline-offset:2px;border-radius:2px;}'+
    '.tg-tip{position:absolute;z-index:2147483000;box-sizing:border-box;max-width:300px;margin:0;padding:10px 12px;'+
    'background:#120E1C;color:#F1E6CF;border:1px solid #2C2440;border-left:3px solid #D9A85C;border-radius:8px;'+
    'box-shadow:0 12px 30px -10px rgba(0,0,0,.7);font:400 13.5px/1.5 "DM Sans",system-ui,Arial,sans-serif;'+
    'letter-spacing:0;text-transform:none;text-align:left;white-space:normal;}'+
    '.tg-tip[hidden]{display:none;}.tg-tip a{display:inline-block;margin-top:6px;color:#1FCBE3;font-size:13px;text-decoration:none;}'+
    '.tg-tip a:hover{color:#6FF2FF;text-decoration:underline;}';

  function norm(s){ return s.replace(/\s+/g,' ').replace(/^[^A-Za-z0-9~]+/,'').replace(/:\s*$/,'').trim().toLowerCase(); }
  function hit(t,text){
    var w=t.label.toLowerCase(), m=t.match||'exact';
    return text===w || (m==='prefix'&&text.indexOf(w)===0) || (m==='contains'&&text.indexOf(w)>-1);
  }
  // a prefix match ("Static data as of August 12, 2026 — …") underlines only the label's own words
  function wrap(doc,el,label){
    var walk=doc.createTreeWalker(el,4), n, lo=label.toLowerCase();
    while((n=walk.nextNode())){
      var i=n.nodeValue.toLowerCase().indexOf(lo);
      if(i<0) continue;
      var mid=n.splitText(i); mid.splitText(label.length);
      var s=doc.createElement('span'); mid.parentNode.replaceChild(s,mid); s.appendChild(mid);
      return s;
    }
    return el;
  }

  function run(doc){
    try{
      if(!labels.length||!doc||!doc.body||doc.body.getAttribute('data-tg-tips')) return;
      doc.body.setAttribute('data-tg-tips','1');
      var st=doc.createElement('style'); st.textContent=CSS; doc.head.appendChild(st);
      // candidates: the elements that directly hold text, short enough to be a label
      var seen=[], walk=doc.createTreeWalker(doc.body,4), n;
      while((n=walk.nextNode())){
        var p=n.parentNode;
        if(!p||!n.nodeValue.trim()||/^(SCRIPT|STYLE|NOSCRIPT)$/.test(p.nodeName)||p.tgSeen) continue;
        p.tgSeen=1; seen.push(p);
      }
      var found=[];
      seen.forEach(function(el){
        var raw=el.textContent; if(raw.length>400) return;
        var text=norm(raw);
        for(var k=0;k<labels.length;k++){
          var t=labels[k];
          if(t.in && !(el.matches(t.in)||el.closest(t.in))) continue;
          if(hit(t,text)){ found.push([t.match==='prefix'?wrap(doc,el,t.label):el,t]); break; }
        }
      });
      if(found.length) attach(doc,found);
    }catch(e){}
  }

  function attach(doc,found){
    var win=doc.defaultView, tip=doc.createElement('div'), cur=null, shownAt=0, hideT=0, uid=0;
    tip.className='tg-tip'; tip.id='tg-tip'; tip.setAttribute('role','tooltip'); tip.hidden=true;
    doc.body.appendChild(tip);
    function show(el,t){
      clearTimeout(hideT);
      if(cur&&cur!==el) cur.setAttribute('aria-expanded','false');
      cur=el; shownAt=Date.now(); el.setAttribute('aria-expanded','true');
      tip.textContent=t.tip;
      if(t.term){
        var a=doc.createElement('a'); a.href='/learn/table-talk/finance.html#'+t.term; a.target='_top';
        a.textContent='More in the glossary →'; tip.appendChild(doc.createElement('br')); tip.appendChild(a);
      }
      tip.hidden=false;
      var r=el.getBoundingClientRect(), w=tip.offsetWidth, h=tip.offsetHeight, vw=win.innerWidth, vh=win.innerHeight;
      var left=Math.max(8,Math.min(r.left,vw-w-8)), top=r.bottom+8;
      if(top+h>vh-8 && r.top-h-8>8) top=r.top-h-8;
      tip.style.left=(left+win.scrollX)+'px'; tip.style.top=(top+win.scrollY)+'px';
    }
    function hide(){ if(cur) cur.setAttribute('aria-expanded','false'); cur=null; tip.hidden=true; }
    function later(){ clearTimeout(hideT); hideT=setTimeout(hide,180); }
    found.forEach(function(f){
      var el=f[0], t=f[1];
      if(el.classList.contains('tg-tipl')) return;
      el.classList.add('tg-tipl'); el.tabIndex=0; el.setAttribute('role','button');
      el.setAttribute('aria-expanded','false'); el.setAttribute('aria-describedby','tg-tip');
      el.setAttribute('data-tg-tip',++uid);
      el.addEventListener('mouseenter',function(){show(el,t);});
      el.addEventListener('mouseleave',later);
      el.addEventListener('focus',function(){show(el,t);});
      el.addEventListener('blur',function(ev){ if(!tip.contains(ev.relatedTarget)) later(); });
      // a tap fires mouseenter just before click: keep it open; a second tap closes it
      el.addEventListener('click',function(ev){
        ev.stopPropagation();
        if(cur===el && Date.now()-shownAt>400) hide(); else show(el,t);
      });
      el.addEventListener('keydown',function(ev){ if(ev.key==='Enter'||ev.key===' '){ ev.preventDefault(); cur===el?hide():show(el,t); } });
    });
    tip.addEventListener('mouseenter',function(){clearTimeout(hideT);});
    tip.addEventListener('mouseleave',later);
    tip.addEventListener('click',function(ev){ev.stopPropagation();});
    doc.addEventListener('click',hide);
    doc.addEventListener('keydown',function(ev){ if(ev.key==='Escape') hide(); });
    // scrolling closes it, except the scroll that focusing or tapping a label causes as it opens
    doc.addEventListener('scroll',function(){ if(cur && Date.now()-shownAt>300) hide(); },true);
    win.addEventListener('resize',hide);
  }
})();
