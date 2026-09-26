// ---- report families: Stocks · ETFs · Crypto · Bonds & cash, one tab each; ?f= keeps the open tab in the URL
(function(){
  var tabs=[].slice.call(document.querySelectorAll('.fam')), panels=[].slice.call(document.querySelectorAll('.fampanel'));
  if(!tabs.length) return;
  var KEYS=tabs.map(function(t){return t.getAttribute('data-fam');});
  window.TTG_FAM='stocks';
  function show(f, push){
    if(KEYS.indexOf(f)<0) f='stocks';
    window.TTG_FAM=f;
    panels.forEach(function(p){p.hidden=p.id!=='fam-'+f;});
    tabs.forEach(function(t){
      var on=t.getAttribute('data-fam')===f;
      t.setAttribute('aria-selected',on?'true':'false'); t.tabIndex=on?0:-1;
    });
    if(push){
      var p=new URLSearchParams(location.search);
      if(f==='stocks') p.delete('f'); else { p=new URLSearchParams(); p.set('f',f); }
      var qs=p.toString();
      try{history.replaceState(null,'',location.pathname+(qs?'?'+qs:''));}catch(e){}
    }
  }
  tabs.forEach(function(t,i){
    t.addEventListener('click',function(e){e.preventDefault(); show(t.getAttribute('data-fam'),true);});
    t.addEventListener('keydown',function(e){
      var d=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0; if(!d) return;
      e.preventDefault(); var n=tabs[(i+d+tabs.length)%tabs.length]; n.focus(); show(n.getAttribute('data-fam'),true);
    });
  });
  show(new URLSearchParams(location.search).get('f')||'stocks',false);
})();

(function(){
  var $=function(s,r){return (r||document).querySelector(s);},
      all=function(s,r){return [].slice.call((r||document).querySelectorAll(s));};
  var q=$('#q'), fInd=$('#find'), fIdx=$('#fidx'), fSort=$('#fsort'),
      clearBtn=$('#fclear'), countEl=$('#fcounttext'), annEl=$('#fann'),
      results=$('#results'), sectors=$('.sectors'), none=$('.noresult'),
      chips=all('.chip'), groups=all('.sgroup'), TOTAL=0;

  // one record per card; el stays a single node that we move between views
  var cards=all('#fam-stocks .rep').map(function(el){
    var t=$('.tick',el).textContent.trim();
    return {el:el, home:el.parentNode, t:t, tf:t.replace(/[^A-Z0-9]/g,''),
            n:$('h3',el).textContent.trim().toLowerCase(),
            i:$('.sect',el).textContent.trim(),
            sector:el.closest('.sgroup').getAttribute('data-s'),
            sp:el.getAttribute('data-sp'), ndx:el.hasAttribute('data-ndx'),
            dow:el.getAttribute('data-dow'), gl:el.getAttribute('data-gl')};
  });
  TOTAL=cards.length;
  cards.forEach(function(c){
    var d=[c.sp,c.dow].filter(Boolean).sort();
    c.since=d.length?d[0]:null;                 // earliest known index addition
    c.ts=c.since?Date.parse(c.since):null;
  });

  // ---- join year on each index badge, computed at view time: the year, or month and day when it is this year
  var NOW=new Date();
  function joinText(iso){
    var d=new Date(iso+'T00:00:00Z'); if(isNaN(d)) return '';
    if(d.getUTCFullYear()===NOW.getUTCFullYear())
      return d.toLocaleDateString('en-US',{month:'short',day:'numeric',timeZone:'UTC'});
    return String(d.getUTCFullYear());
  }
  all('#fam-stocks .rep').forEach(function(card){
    all('.ix',card).forEach(function(ix){
      var label=ix.querySelector('b').textContent,
          iso=label==='DOW'?card.getAttribute('data-dow'):label!=='NDX'?card.getAttribute('data-sp'):null,
          i=ix.querySelector('i');
      if(!iso||!i) return;
      i.textContent=' '+joinText(iso);
      ix.setAttribute('data-iso',iso);
    });
  });

  // ---- state
  var st={q:'',ind:'',idx:'',sort:'az',sector:'all'};
  function dirty(){return st.q||st.ind||st.idx||st.sort!=='az';}

  function matches(c){
    if(st.ind && c.i!==st.ind) return false;
    if(st.idx==='sp'  && !c.sp)  return false;
    if(st.idx==='ndx' && !c.ndx) return false;
    if(st.idx==='dow' && !c.dow) return false;
    if(st.idx==='gl'  && !c.gl)  return false;
    if(st.sector!=='all' && c.sector!==st.sector) return false;
    if(st.q){
      var s=st.q, sc=s.replace(/[^a-z0-9]/g,'');
      if(c.n.indexOf(s)<0 && (!sc || c.tf.toLowerCase().indexOf(sc)<0)) return false;
    }
    return true;
  }

  // when one index is selected, tenure means tenure IN THAT INDEX;
  // with no index filter it means the earliest major-index addition on record
  function keyTs(c){
    if(st.idx==='sp')  return c.sp ? Date.parse(c.sp) : null;
    if(st.idx==='dow') return c.dow ? Date.parse(c.dow) : null;
    if(st.idx==='ndx') return null;          // no published NDX addition dates
    if(st.idx==='gl')  return null;          // global names sit in no US index
    return c.ts;
  }
  function sorted(list){
    var arr=list.slice();
    if(st.sort==='az') arr.sort(function(a,b){return a.t<b.t?-1:a.t>b.t?1:0;});
    else{
      var dir=st.sort==='old'?1:-1;
      arr.sort(function(a,b){
        var x=keyTs(a), y=keyTs(b);
        if(x===null&&y===null) return a.t<b.t?-1:1;
        if(x===null) return 1;               // unknown dates always last
        if(y===null) return -1;
        return (x-y)*dir || (a.t<b.t?-1:1);
      });
    }
    return arr;
  }

  var flat=false;
  function setFlat(on,list){
    if(on){
      var frag=document.createDocumentFragment();
      list.forEach(function(c){frag.appendChild(c.el);});
      results.appendChild(frag);
      results.classList.add('on'); sectors.classList.add('off'); flat=true;
    }else if(flat){
      cards.forEach(function(c){c.home.appendChild(c.el);});
      results.classList.remove('on'); sectors.classList.remove('off'); flat=false;
    }
  }

  var annTimer;
  function announce(msg){
    clearTimeout(annTimer);
    annTimer=setTimeout(function(){annEl.textContent=msg;},350);
  }

  function apply(push){
    var hits=cards.filter(matches), n=hits.length;

    if(dirty()){
      setFlat(true,sorted(hits));
      cards.forEach(function(c){c.el.hidden=hits.indexOf(c)<0;});
      groups.forEach(function(g){g.hidden=true;});
    }else{
      setFlat(false);
      groups.forEach(function(g){
        var vis=0;
        all('.rep',g).forEach(function(el){
          var c=cards[cards.map(function(x){return x.el;}).indexOf(el)];
          var on=matches(c); el.hidden=!on; if(on) vis++;
        });
        var sc=$('.scount',g); if(sc) sc.textContent=vis;
        g.hidden = st.sector==='all' ? vis===0 : g.getAttribute('data-s')!==st.sector;
      });
    }

    none.hidden = n>0;
    if(n===0){
      none.textContent='No report matches that. Try a different ticker, industry or index.';
      countEl.textContent='';
    }else if(dirty()||st.sector!=='all'){
      countEl.innerHTML='Showing <b>'+n+'</b> of '+TOTAL+' reports';
    }else{
      countEl.innerHTML='<b>'+TOTAL+'</b> reports, grouped by sector';
    }
    if(n>0 && st.sort!=='az' && (st.idx==='ndx'||st.idx==='gl')){
      countEl.innerHTML+=' <span style="opacity:.7">&middot; '+(st.idx==='gl'?'Global names sit in no US index, so':'Nasdaq-100 addition dates aren\'t published, so')+' these are ordered A&ndash;Z</span>';
    }
    announce(n===0?'No reports match your filters.':n+' of '+TOTAL+' reports shown.');

    // sector chips act as live facets: each count is what you'd get if you clicked it
    var savedSector=st.sector;
    chips.forEach(function(ch){
      var key=ch.getAttribute('data-f'), badge=ch.querySelector('span');
      if(!badge) return;
      st.sector=key;
      var k=cards.filter(matches).length;
      badge.textContent=k;
      ch.classList.toggle('zero',k===0);
      st.sector=savedSector;
    });

    clearBtn.hidden = !(dirty() || st.sector!=='all');
    q.classList.toggle('on',!!st.q);
    fInd.parentNode.classList.toggle('on',!!st.ind);
    fIdx.parentNode.classList.toggle('on',!!st.idx);
    fSort.parentNode.classList.toggle('on',st.sort!=='az');
    chips.forEach(function(c){c.classList.toggle('active',c.getAttribute('data-f')===st.sector);});

    if(push!==false) writeUrl();
  }

  function writeUrl(){
    if(window.TTG_FAM && window.TTG_FAM!=='stocks') return;   // stock filters only live in the Stocks tab
    var p=[];
    if(st.q) p.push('q='+encodeURIComponent(st.q));
    if(st.ind) p.push('i='+encodeURIComponent(st.ind));
    if(st.idx) p.push('x='+st.idx);
    if(st.sort!=='az') p.push('sort='+st.sort);
    if(st.sector!=='all') p.push('s='+st.sector);
    try{history.replaceState(null,'',location.pathname+(p.length?'?'+p.join('&'):''));}catch(e){}
  }

  // ---- wiring
  var t;
  q.addEventListener('input',function(){
    clearTimeout(t);
    t=setTimeout(function(){st.q=q.value.trim().toLowerCase();apply();},120);
  });
  q.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&q.value){q.value='';st.q='';apply();}
  });
  fInd.addEventListener('change',function(){st.ind=fInd.value;apply();});
  fIdx.addEventListener('change',function(){st.idx=fIdx.value;apply();});
  fSort.addEventListener('change',function(){st.sort=fSort.value;apply();});
  chips.forEach(function(c){c.addEventListener('click',function(){st.sector=c.getAttribute('data-f');apply();});});
  clearBtn.addEventListener('click',function(){
    st={q:'',ind:'',idx:'',sort:'az',sector:'all'};
    q.value='';fInd.value='';fIdx.value='';fSort.value='az';
    apply();q.focus();
  });
  document.addEventListener('keydown',function(e){
    if(e.key==='/'&&document.activeElement!==q&&!/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)){
      e.preventDefault();q.focus();q.select();
    }
  });

  // ---- phones: each sector folds, so 544 cards open as eleven headings; a sector chip or a search still opens results
  var PHONE=window.matchMedia('(max-width:640px)');
  // the heading stays a heading; on phones a real <button> inside it does the folding
  groups.forEach(function(g){
    var h=$('.shead',g); if(!h) return;
    var id='sg-'+g.getAttribute('data-s'), plain=h.innerHTML, btn=null;
    $('.grid',g).id=id;
    g._set=function(open){
      if(PHONE.matches && !btn){
        h.innerHTML='<button type="button" class="shead-btn" aria-controls="'+id+'">'+plain+'</button>';
        btn=h.firstChild;
        btn.addEventListener('click',function(){ g._set(g.classList.contains('folded')); });
      }else if(!PHONE.matches && btn){ h.innerHTML=plain; btn=null; }
      g.classList.toggle('folded',PHONE.matches && !open);
      if(btn) btn.setAttribute('aria-expanded',open?'true':'false');
    };
  });
  function foldAll(){
    groups.forEach(function(g){ if(g._set) g._set(!PHONE.matches || st.sector!=='all'); });
  }
  if(PHONE.addEventListener) PHONE.addEventListener('change',foldAll);

  // ---- restore from the URL
  var p=new URLSearchParams(location.search);
  if(p.get('q')){q.value=p.get('q');st.q=q.value.trim().toLowerCase();}
  if(p.get('i')&&[].some.call(fInd.options,function(o){return o.value===p.get('i');})){fInd.value=p.get('i');st.ind=fInd.value;}
  if(['sp','ndx','dow','gl'].indexOf(p.get('x'))>-1){fIdx.value=p.get('x');st.idx=fIdx.value;}
  if(['old','new'].indexOf(p.get('sort'))>-1){fSort.value=p.get('sort');st.sort=fSort.value;}
  var s=p.get('s'); if(s&&$('.chip[data-f="'+s.replace(/[^a-z0-9]/g,'')+'"]')) st.sector=s;
  apply(false);
  foldAll();
  chips.forEach(function(c){c.addEventListener('click',foldAll);});
  clearBtn.addEventListener('click',foldAll);
})();

// ---- card tags: families, tooltips and one-liners from ../data/card_tags.json (built by tools/card_tags.py)
(function(){
  var ICON={
    list:'<circle cx="12" cy="6.6" r="4.3"/><circle cx="6.6" cy="13.4" r="4.3"/><circle cx="17.4" cy="13.4" r="4.3"/><path d="M11 12h2l1.6 9.2H9.4z"/>',
    cash:'<path d="M12 1.8 20.2 12 12 22.2 3.8 12z"/>',
    what:'<path d="M12 21.2S2.6 14.9 2.6 8.6A4.9 4.9 0 0 1 12 6.4a4.9 4.9 0 0 1 9.4 2.2c0 6.3-9.4 12.6-9.4 12.6z"/>',
    theme:'<path d="M12 1.8S2.8 8.6 2.8 13.9a4.6 4.6 0 0 0 8.1 3l-1.5 4.9h5.2l-1.5-4.9a4.6 4.6 0 0 0 8.1-3C21.2 8.6 12 1.8 12 1.8z"/>',
    who:'<path d="m12 2 2.95 6.3 6.9.8-5.1 4.75 1.35 6.85L12 17.3l-6.1 3.4 1.35-6.85-5.1-4.75 6.9-.8z"/>',
    where:'<path d="M12 2.6 1.8 11.4h2.9V21.4h5.6v-6.2h3.4v6.2h5.6V11.4h2.9L18.9 8.4V4.2h-2.6v1.9z"/>',
    'new':'<circle cx="12" cy="12" r="8.6" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="M12 7v5.4l3.6 2.2" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
    style:'<circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2.4" stroke-dasharray="3.2 2.6"/><circle cx="12" cy="12" r="5.2"/>'
  };
  function icon(f){return '<span class="s" aria-hidden="true"><svg viewBox="0 0 24 24" fill="currentColor">'+ICON[f]+'</svg></span>';}
  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');}
  function tagHtml(fam,label,tip){
    return '<span class="tg t fam-'+fam+'" tabindex="0" role="button" data-label="'+esc(label)+'" data-tip="'+esc(tip)+'" aria-label="'+esc(label+': '+tip)+'">'+icon(fam)+esc(label)+'</span>';
  }
  var NOW=new Date(), YEAR=NOW.getUTCFullYear();
  function yr(iso){return iso?+iso.slice(0,4):null;}
  function nice(iso){var d=new Date(iso+'T00:00:00Z');return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'});}
  function when(iso){ // "in 2001", or "on March 3" for this year
    var d=new Date(iso+'T00:00:00Z');
    return yr(iso)===YEAR ? 'on '+d.toLocaleDateString('en-US',{month:'long',day:'numeric',timeZone:'UTC'}) : 'in '+yr(iso);
  }
  var SP='In the S&P 500: about 500 of America’s largest companies, and the benchmark most people mean by “the market”. Index funds and many retirement plans simply own the whole list.',
      NDX='In the Nasdaq-100: the 100 biggest companies trading on the Nasdaq stock exchange, leaving out banks and other finance firms.',
      DOW='One of just 30 companies in the Dow Jones Industrial Average (“the Dow”), the oldest US stock-market average, running since 1896.';

  function decorate(card,c){
    c=c||{};
    // take the link off the card and lay it over the card instead ("stretched link"), with tags stacked above it:
    // a tap on a tag or on +N then never reaches the link, whatever else is listening for link clicks
    var href=card.getAttribute('href');
    if(href){
      var tk=(card.querySelector('.tick')||{}).textContent||'';
      var extra=(card.getAttribute('target')?' target="'+card.getAttribute('target')+'"':'')+(card.getAttribute('rel')?' rel="'+card.getAttribute('rel')+'"':'');
      card.removeAttribute('href'); card.removeAttribute('target'); card.removeAttribute('rel');
      card.insertAdjacentHTML('afterbegin','<a class="stretch" href="'+href+'"'+extra+' aria-label="Read the '+esc(tk.trim())+' report"></a>');
    }
    // index badges become club tags with a tooltip
    [].forEach.call(card.querySelectorAll('.ix'),function(ix){
      var b=ix.querySelector('b'), label=b.textContent, iso=ix.getAttribute('data-iso'), tip;
      if(label==='S&P 500'){
        tip=SP+(c.sp?' '+c.sp[1]:(iso?' Joined '+when(iso)+'.':''));
        if(c.sp){var i=ix.querySelector('i'); if(i) i.textContent=' '+c.sp[0];}
      }else if(label==='NDX') tip=NDX;
      else if(label==='DOW') tip=DOW+(iso?' Joined '+when(iso)+'.':'');
      else if(label==='GLOBAL') tip='In none of the three big US indexes. Its main listing is on '+((ix.querySelector('i')||{}).textContent||'').trim()+'; the report prices its New York shares in dollars.';
      if(!tip) return;
      ix.classList.add('t','fam-list'); ix.removeAttribute('title');
      ix.setAttribute('tabindex','0'); ix.setAttribute('role','button');
      ix.setAttribute('data-label',ix.textContent.trim()); ix.setAttribute('data-tip',tip);
      ix.setAttribute('aria-label',ix.textContent.trim()+': '+tip);
      ix.insertAdjacentHTML('afterbegin',icon('list'));
    });
    if(c.lg){
      var tk=card.querySelector('.tick');
      if(tk) tk.insertAdjacentHTML('afterend','<span class="logo" aria-hidden="true"><img alt="" loading="lazy" src="'+c.lg+'"></span>');
      card.classList.add('has-logo');
    }
    if(c.ln){
      var sect=card.querySelector('.sect');
      if(sect) sect.insertAdjacentHTML('afterend','<div class="play"><span class="play-k"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.2" y="5" width="10.5" height="14.5" rx="1.8" transform="rotate(-13 8.5 12.2)"/><rect x="10" y="3.6" width="10.5" height="14.5" rx="1.8" transform="rotate(11 15.2 10.8)" class="f"/></svg>Their hand</span><p class="line">'+esc(c.ln)+'</p></div>');
    }
    // collect tags by family, in priority order; index badges (clubs) are separate and always shown
    var fams={what:[],theme:[],who:[],'new':[],style:[],cash:[],where:[]}, ORDER=['what','theme','who','new','style','cash','where'];
    (c.hw||[]).forEach(function(x){ fams.what.push(tagHtml('what',x[0],x[1])); });
    (c.th||[]).forEach(function(x){ fams.theme.push(tagHtml('theme',x[0],x[1])); });
    (c.pp||[]).forEach(function(x){
      // "New CEO" expires two years after the start month the tag was built with
      if(x[0]==='New CEO' && x[2] && (NOW-Date.parse(x[2]+'-01T00:00:00Z'))/864e5>730) return;
      fams.who.push(tagHtml('who',x[0],x[1]));
    });
    if(c.ed && (NOW-Date.parse(c.ed[0]+'T00:00:00Z'))/864e5<=60)
      fams['new'].push(tagHtml('new','Updated','Refreshed '+when(c.ed[0])+', replacing the edition of '+nice(c.ed[1])+' (then $'+(+c.ed[2]).toFixed(2)+'). The report opens with what changed.'));
    var income=false;
    (c.st||[]).forEach(function(s){ if(s[0]==='Income') income=true; fams.style.push(tagHtml('style',s[0],s[1])); });
    if(c.dv===0) fams.cash.push(tagHtml('cash','No dividend','Pays no dividend, so shareholders gain only if the share price rises.'));
    else if(c.dv>0 && !income) fams.cash.push(tagHtml('cash','Dividend','Pays a dividend of about $'+c.dv.toFixed(2)+' a year per $100 invested ('+c.dv.toFixed(2)+'% yield).'));
    if(c.hq) fams.where.push(tagHtml('where',c.hq[0],'Head office: '+c.hq[1]+'. This tag is about home base only; many companies earn much of their money abroad.'));
    // pick up to MAX: one from each family in turn, then a second round, so the visible set spans families
    var MAX=6, picked={}, n=0, round=0, more=true;
    while(n<MAX && more){
      more=false;
      ORDER.forEach(function(f){ if(n<MAX && fams[f].length>round){ picked[f]=(picked[f]||0)+1; n++; } if(fams[f].length>round+1) more=true; });
      round++;
    }
    var shown='', hidden='', extra=0;
    ORDER.forEach(function(f){ fams[f].forEach(function(html,k){
      if(k<(picked[f]||0)) shown+=html; else { hidden+=html.replace('class="tg t','class="tg t x'); extra++; }
    }); });
    if(shown||hidden){
      var more_=extra?'<span class="tg-more" role="button" tabindex="0" aria-expanded="false" aria-label="Show '+extra+' more tags">+'+extra+'</span>':'';
      var row=card.querySelector('.ixrow');
      (row||card.querySelector('.sect')).insertAdjacentHTML('afterend','<span class="tags">'+shown+hidden+more_+'</span>');
    }
  }

  // one shared tooltip: hover, keyboard focus, or tap. Tags sit inside the card link, so a tap on a tag
  // opens its tooltip instead of following the link; a tap anywhere else on the card still opens the report.
  var tip=document.createElement('div'); tip.id='tip'; tip.setAttribute('role','tooltip'); tip.hidden=true;
  document.body.appendChild(tip);
  var cur=null, pinned=null;
  function show(el){
    cur=el;
    tip.style.setProperty('--tc',getComputedStyle(el).getPropertyValue('--c'));
    tip.innerHTML='<b>'+esc(el.getAttribute('data-label'))+'</b>'+esc(el.getAttribute('data-tip'));
    tip.hidden=false;
    var r=el.getBoundingClientRect(), t=tip.getBoundingClientRect();
    var x=Math.min(Math.max(16,r.left+r.width/2-t.width/2),innerWidth-t.width-16);
    var y=r.top-t.height-8; if(y<8) y=r.bottom+8;
    tip.style.left=x+'px'; tip.style.top=y+'px';
  }
  function hide(){tip.hidden=true; cur=null; pinned=null;}
  function tagOf(e){return e.target.closest && e.target.closest('.t[data-tip]');}
  document.addEventListener('mouseover',function(e){var el=tagOf(e); if(el&&!pinned) show(el);});
  document.addEventListener('mouseout',function(e){if(tagOf(e)&&!pinned){tip.hidden=true;cur=null;}});
  document.addEventListener('focusin',function(e){var el=tagOf(e); if(el) show(el);});
  document.addEventListener('focusout',function(e){if(tagOf(e)) hide();});
  function toggleMore(m){ var box=m.parentNode, on=!box.classList.contains('all');
    box.classList.toggle('all',on); m.setAttribute('aria-expanded',on); m.textContent=on?'less':'+'+box.querySelectorAll('.x').length; }
  document.addEventListener('click',function(e){
    var m=e.target.closest&&e.target.closest('.tg-more');
    if(m){e.preventDefault(); e.stopPropagation(); toggleMore(m); return;}
    var el=tagOf(e);
    if(el){e.preventDefault(); e.stopPropagation(); if(pinned===el) hide(); else {pinned=el; show(el);} return;}
    if(pinned) hide();
  },true);
  document.addEventListener('keydown',function(e){
    var m=e.target.closest&&e.target.closest('.tg-more');
    if(m&&(e.key==='Enter'||e.key===' ')){e.preventDefault(); toggleMore(m); return;}
    var el=tagOf(e);
    if(el&&(e.key==='Enter'||e.key===' ')){e.preventDefault(); if(pinned===el) hide(); else {pinned=el; show(el);}}
    else if(e.key==='Escape') hide();
  });
  addEventListener('scroll',function(){if(!tip.hidden&&cur) show(cur);},{passive:true});

  fetch('../data/card_tags.json').then(function(r){return r.ok?r.json():null;}).then(function(d){
    var cards=(d&&d.cards)||{};
    [].forEach.call(document.querySelectorAll('.rep'),function(card){
      var m=/r=([a-z0-9.\-]+)/.exec(card.getAttribute('href')||'');
      decorate(card,m?cards[m[1]]:null);
    });
  }).catch(function(){
    [].forEach.call(document.querySelectorAll('.rep'),function(card){decorate(card,null);});
  });
})();
