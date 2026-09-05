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
            dow:el.getAttribute('data-dow')};
  });
  TOTAL=cards.length;
  cards.forEach(function(c){
    var d=[c.sp,c.dow].filter(Boolean).sort();
    c.since=d.length?d[0]:null;                 // earliest known index addition
    c.ts=c.since?Date.parse(c.since):null;
  });

  // ---- tenure text, computed at view time so it never goes stale
  var NOW=new Date();
  function tenure(iso){
    var d=new Date(iso+'T00:00:00Z'); if(isNaN(d)) return '';
    var m=(NOW.getUTCFullYear()-d.getUTCFullYear())*12+(NOW.getUTCMonth()-d.getUTCMonth());
    if(NOW.getUTCDate()<d.getUTCDate()) m--;
    if(m<1) return 'new';
    if(m<12) return m+'mo';
    return Math.floor(m/12)+'y';
  }
  function longDate(iso){
    var d=new Date(iso+'T00:00:00Z');
    return d.toLocaleDateString('en-CA',{year:'numeric',month:'long',day:'numeric',timeZone:'UTC'});
  }
  var IXNAME={'S&P 500':'S&P 500','DOW':'Dow 30'};
  all('.rep').forEach(function(card){
    all('.ix',card).forEach(function(ix){
      var label=ix.querySelector('b').textContent,
          iso=label==='DOW'?card.getAttribute('data-dow'):label!=='NDX'?card.getAttribute('data-sp'):null,
          i=ix.querySelector('i');
      if(!iso||!i) return;
      i.textContent=' '+tenure(iso);
      ix.setAttribute('title','Added to the '+(IXNAME[label]||label)+' on '+longDate(iso));
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
    if(n>0 && st.sort!=='az' && st.idx==='ndx'){
      countEl.innerHTML+=' <span style="opacity:.7">&middot; Nasdaq-100 addition dates aren\'t published, so these are ordered A&ndash;Z</span>';
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
  if(['sp','ndx','dow'].indexOf(p.get('x'))>-1){fIdx.value=p.get('x');st.idx=fIdx.value;}
  if(['old','new'].indexOf(p.get('sort'))>-1){fSort.value=p.get('sort');st.sort=fSort.value;}
  var s=p.get('s'); if(s&&$('.chip[data-f="'+s.replace(/[^a-z0-9]/g,'')+'"]')) st.sector=s;
  apply(false);
})();
