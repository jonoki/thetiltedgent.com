// The glossaries: search box and section chips. Without this script every term shows (the controls are hidden).
(function(){
  var q=document.getElementById('q'), count=document.getElementById('count'), none=document.getElementById('none');
  var chips=[].slice.call(document.querySelectorAll('.chip')), groups=[].slice.call(document.querySelectorAll('.grp'));
  var terms=[].slice.call(document.querySelectorAll('.term')), az=document.getElementById('a-z'), bar=document.querySelector('.azbar');
  var group='';
  var hay=terms.map(function(t){ return t.getAttribute('data-s')+' '+t.textContent.toLowerCase(); });
  function apply(){
    var words=q.value.toLowerCase().trim().split(/\s+/).filter(Boolean), shown=0;
    terms.forEach(function(t,i){
      var ok=(!group||t.getAttribute('data-g')===group)&&words.every(function(w){return hay[i].indexOf(w)>-1;});
      t.hidden=!ok; if(ok) shown++;
    });
    groups.forEach(function(g){ g.hidden=!g.querySelector('.term:not([hidden])'); });
    var filtered=!!(group||words.length);
    az.hidden=filtered; bar.hidden=filtered; none.hidden=shown>0;
    count.textContent=filtered?'Showing '+shown+' of '+terms.length+' terms':'';
  }
  function setGroup(g){
    group=g;
    chips.forEach(function(c){ var on=c.getAttribute('data-g')===g; c.classList.toggle('active',on); c.setAttribute('aria-pressed',on?'true':'false'); });
    apply();
  }
  chips.forEach(function(c){ c.addEventListener('click',function(){ setGroup(c.getAttribute('data-g')); }); });
  setGroup('');
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
  addEventListener('hashchange',function(){
    var t=document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if(t&&t.classList.contains('term')&&t.hidden){ q.value=''; setGroup(''); t.scrollIntoView(); }
  });
})();
