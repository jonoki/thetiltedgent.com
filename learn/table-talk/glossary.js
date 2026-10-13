// The glossaries: search box and tag chips over one A-Z list. Without this script every term shows (the controls are
// hidden). ?tag=<id> opens the page filtered to one topic; a tag on an entry filters too.
(function(){
  var q=document.getElementById('q'), count=document.getElementById('count'), none=document.getElementById('none');
  var chips=[].slice.call(document.querySelectorAll('.chip')), groups=[].slice.call(document.querySelectorAll('.grp'));
  var terms=[].slice.call(document.querySelectorAll('.term')), bar=document.querySelector('.azbar');
  var known={}; chips.forEach(function(c){ known[c.getAttribute('data-t')]=c.textContent.replace(/\s*\d+$/,''); });
  var tag='';
  var hay=terms.map(function(t){ return t.getAttribute('data-s')+' '+t.textContent.toLowerCase(); });
  var tagsOf=terms.map(function(t){ return ' '+t.getAttribute('data-t')+' '; });
  function apply(){
    var words=q.value.toLowerCase().trim().split(/\s+/).filter(Boolean), shown=0;
    terms.forEach(function(t,i){
      var ok=(!tag||tagsOf[i].indexOf(' '+tag+' ')>-1)&&words.every(function(w){return hay[i].indexOf(w)>-1;});
      t.hidden=!ok; if(ok) shown++;
    });
    groups.forEach(function(g){ g.hidden=!g.querySelector('.term:not([hidden])'); });
    // the A-Z bar jumps only to letters with something showing
    [].forEach.call(bar.querySelectorAll('a'),function(a){
      var g=document.getElementById(a.getAttribute('href').slice(1)); a.classList.toggle('off',!!(g&&g.hidden));
    });
    var filtered=!!(tag||words.length);
    none.hidden=shown>0;
    count.textContent=filtered?'Showing '+shown+' of '+terms.length+' terms'+(tag?' tagged '+known[tag]:''):'';
  }
  function setTag(g,push){
    tag=known.hasOwnProperty(g)?g:'';
    chips.forEach(function(c){ var on=c.getAttribute('data-t')===tag; c.classList.toggle('active',on); c.setAttribute('aria-pressed',on?'true':'false'); });
    if(push!==false){
      try{ var u=new URL(location.href); if(tag) u.searchParams.set('tag',tag); else u.searchParams.delete('tag'); history.replaceState(null,'',u); }catch(e){}
    }
    apply();
  }
  chips.forEach(function(c){ c.addEventListener('click',function(){ setTag(c.getAttribute('data-t')); }); });
  // a tag on an entry filters the page in place
  document.addEventListener('click',function(e){
    var a=e.target.closest&&e.target.closest('.term a.tag'); if(!a) return;
    e.preventDefault(); setTag(a.getAttribute('data-t')); scrollTo(0,0);
  });
  var start=''; try{ start=new URL(location.href).searchParams.get('tag')||''; }catch(e){}
  setTag(start,false);
  q.addEventListener('input',apply);
  // a link to a retired entry (tools/glossary.py RETIRED) goes to its successor, or says where it is explained now
  var moved={}; try{ moved=JSON.parse(document.getElementById('moved').textContent); }catch(e){}
  function forward(){
    var mv=moved[decodeURIComponent(location.hash.slice(1))];
    if(!mv) return;
    if(mv.to){ location.replace('#'+mv.to); return; }
    count.textContent=mv.note; scrollTo(0,0);
  }
  forward();
  addEventListener('hashchange',forward);
  // the browser jumps to #term before the web fonts reflow the columns; jump again once they are in, unless the
  // reader has scrolled since
  if(location.hash&&document.fonts){
    var y0=scrollY;
    document.fonts.ready.then(function(){
      var t=document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if(t&&Math.abs(scrollY-y0)<2) t.scrollIntoView();
    });
  }
  // a link to a hidden term clears the filters that hide it
  function reveal(){
    var t=document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if(t&&(t.hidden||(t.parentNode.closest('.grp')||{}).hidden)){ q.value=''; setTag(''); t.scrollIntoView(); }
  }
  addEventListener('hashchange',reveal);
  if(location.hash) reveal();
})();
