(function(){
  var $=function(s,r){return (r||document).querySelector(s);},
      all=function(s,r){return [].slice.call((r||document).querySelectorAll(s));};
  var q=$('#q'), fInd=$('#find'), fIdx=$('#fidx'), fSort=$('#fsort'),
      clearBtn=$('#fclear'), countEl=$('#fcounttext'), annEl=$('#fann'),
      results=$('#results'), sectors=$('.sectors'), none=$('.noresult'),
      chips=all('.chip'), groups=all('.sgroup'), TOTAL=0;

  // one record per card; el stays a single node that we move between views
  var cards=all('.rep').map(function(el){
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
  all('.rep').forEach(function(card){
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

  // ---- restore from the URL
  var p=new URLSearchParams(location.search);
  if(p.get('q')){q.value=p.get('q');st.q=q.value.trim().toLowerCase();}
  if(p.get('i')&&[].some.call(fInd.options,function(o){return o.value===p.get('i');})){fInd.value=p.get('i');st.ind=fInd.value;}
  if(['sp','ndx','dow','gl'].indexOf(p.get('x'))>-1){fIdx.value=p.get('x');st.idx=fIdx.value;}
  if(['old','new'].indexOf(p.get('sort'))>-1){fSort.value=p.get('sort');st.sort=fSort.value;}
  var s=p.get('s'); if(s&&$('.chip[data-f="'+s.replace(/[^a-z0-9]/g,'')+'"]')) st.sector=s;
  apply(false);
})();

// ---- card tags: families, tooltips and one-liners from ../data/card_tags.json (built by tools/card_tags.py)
(function(){
  var ICON={
    list:'<circle cx="12" cy="6.6" r="4.3"/><circle cx="6.6" cy="13.4" r="4.3"/><circle cx="17.4" cy="13.4" r="4.3"/><path d="M11 12h2l1.6 9.2H9.4z"/>',
    cash:'<path d="M12 1.8 20.2 12 12 22.2 3.8 12z"/>',
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
    if(c.ln){
      var sect=card.querySelector('.sect');
      if(sect) sect.insertAdjacentHTML('afterend','<p class="line">'+esc(c.ln)+'</p>');
    }
    var h='';
    if(c.ed && (NOW-Date.parse(c.ed[0]+'T00:00:00Z'))/864e5<=60)
      h+=tagHtml('new','Updated','Refreshed '+when(c.ed[0])+', replacing the edition of '+nice(c.ed[1])+' (then $'+(+c.ed[2]).toFixed(2)+'). The report opens with what changed.');
    var income=false;
    (c.st||[]).forEach(function(s){ if(s[0]==='Income') income=true; h+=tagHtml('style',s[0],s[1]); });
    if(c.dv===0) h+=tagHtml('cash','No dividend','Pays no dividend, so shareholders gain only if the share price rises.');
    else if(c.dv>0 && !income) h+=tagHtml('cash','Dividend','Pays a dividend of about $'+c.dv.toFixed(2)+' a year per $100 invested ('+c.dv.toFixed(2)+'% yield).');
    if(c.hq) h+=tagHtml('where',c.hq[0],'Head office: '+c.hq[1]+'. This tag is about home base only; many companies earn much of their money abroad.');
    if(h){
      var row=card.querySelector('.ixrow');
      (row||card.querySelector('.sect')).insertAdjacentHTML('afterend','<span class="tags">'+h+'</span>');
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
  document.addEventListener('click',function(e){
    var el=tagOf(e);
    if(el){e.preventDefault(); e.stopPropagation(); if(pinned===el) hide(); else {pinned=el; show(el);} return;}
    if(pinned) hide();
  },true);
  document.addEventListener('keydown',function(e){
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
