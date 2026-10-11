// Lessons: the interactive widgets. Without this script each page's text and tables still teach everything; the
// widgets are hidden and a short note says what they do.
//   #fut-sim  futures: a position marked to market over five days, with margin calls (futures.html)
//   #opt-sim  options: profit at expiry and value today for a call, put or simple strategy (options.html)
(function(){
  var NS='http://www.w3.org/2000/svg';
  function $(root,sel){ return root.querySelector(sel); }
  function num(el,def){ var v=parseFloat(el.value); return isFinite(v)?v:def; }
  function money(x,dp){
    var s=Math.abs(x).toLocaleString('en-US',{minimumFractionDigits:dp||0,maximumFractionDigits:dp||0});
    return (x<0?'−$':'$')+s;
  }
  function signed(x,dp){ return (x>0?'+':'')+money(x,dp); }
  function el(tag,attrs,parent){
    var e=document.createElementNS(NS,tag);
    for(var k in attrs) e.setAttribute(k,attrs[k]);
    if(parent) parent.appendChild(e);
    return e;
  }
  function css(v){ return getComputedStyle(document.documentElement).getPropertyValue(v).trim()||'#999'; }
  // draw at the chart's real width so its 12px labels stay 12px on a phone; height scales with it
  function size(svg,ratio,minH){
    var W=Math.max(300,Math.round(svg.getBoundingClientRect().width)||640), H=Math.max(minH,Math.round(W*ratio));
    svg.setAttribute('viewBox','0 0 '+W+' '+H); svg.style.height=H+'px';
    return [W,H];
  }
  // round axis ticks (1, 2 or 5 × a power of ten) covering lo..hi
  function ticks(lo,hi,n){
    var raw=(hi-lo)/n, p=Math.pow(10,Math.floor(Math.log(raw)/Math.LN10)), m=raw/p;
    var step=(m<1.5?1:m<3?2:m<7?5:10)*p, out=[];
    for(var v=Math.ceil(lo/step)*step;v<=hi+1e-9;v+=step) out.push(Math.abs(v)<step/1e6?0:v);
    return out;
  }
  var redraw=[];
  addEventListener('resize',function(){ clearTimeout(redraw.t); redraw.t=setTimeout(function(){ redraw.forEach(function(f){f();}); },150); });

  // ---------- futures: marked to market ----------
  function futures(root){
    var f={side:$(root,'[name=side]'),mult:$(root,'[name=mult]'),qty:$(root,'[name=qty]'),entry:$(root,'[name=entry]'),
           init:$(root,'[name=init]'),maint:$(root,'[name=maint]')};
    var days=[].slice.call(root.querySelectorAll('.days input'));
    var svg=$(root,'svg.chart'), rows=$(root,'tbody'), out=$(root,'.out');
    function run(){
      var dir=f.side.value==='short'?-1:1, mult=num(f.mult,50), qty=Math.max(1,Math.round(num(f.qty,1)));
      var entry=num(f.entry,6000), init=num(f.init,22000)*qty, maint=Math.min(num(f.maint,20000)*qty,init);
      var bal=init, prev=entry, added=0, path=[{d:0,bal:bal}], html='';
      days.forEach(function(inp,i){
        var px=num(inp,prev), chg=dir*(px-prev)*mult*qty, call=0;
        bal+=chg;
        if(bal<maint){ call=init-bal; }
        html+='<tr><td>Day '+(i+1)+'</td><td class="num">'+px.toLocaleString('en-US')+'</td><td class="num '+(chg>=0?'up':'down')+'">'+
              signed(chg)+'</td><td class="num">'+money(bal)+'</td><td>'+(call?'<span class="down">Margin call: add '+money(call)+'</span>':'—')+'</td></tr>';
        path.push({d:i+1,bal:bal});
        bal+=call; added+=call; prev=px;
        if(call) path.push({d:i+1,bal:bal,topup:true});
      });
      rows.innerHTML=html;
      var pnl=dir*(prev-entry)*mult*qty;
      out.innerHTML='<span>Gain or loss: <b class="'+(pnl>=0?'up':'down')+'">'+signed(pnl)+'</b></span>'+
        '<span>Cash added by margin calls: <b>'+money(added)+'</b></span>'+
        '<span>Contract value at entry: <b>'+money(entry*mult*qty)+'</b></span>'+
        '<span>Return: <b class="'+(pnl>=0?'up':'down')+'">'+(pnl>=0?'+':'')+(100*pnl/(entry*mult*qty)).toFixed(1)+'%</b> on the contract&rsquo;s value, '+
        '<b class="'+(pnl>=0?'up':'down')+'">'+(pnl>=0?'+':'')+(100*pnl/(init+added)).toFixed(1)+'%</b> on the cash you put up</span>';
      draw(path,init,maint);
    }
    function draw(path,init,maint){
      while(svg.firstChild) svg.removeChild(svg.firstChild);
      var wh=size(svg,0.375,200), W=wh[0], H=wh[1], L=70, R=26, T=14, B=30;
      var vals=path.map(function(p){return p.bal;}).concat([maint,init]);
      var lo=Math.min.apply(null,vals), hi=Math.max.apply(null,vals), pad=(hi-lo)*0.12||1000; lo-=pad; hi+=pad;
      var x=function(d){return L+(W-L-R)*d/5;}, y=function(v){return T+(H-T-B)*(hi-v)/(hi-lo);};
      ticks(lo,hi,4).forEach(function(v){
        el('line',{x1:L,x2:W-R,y1:y(v),y2:y(v),stroke:css('--line'),'stroke-width':1},svg);
        el('text',{x:L-8,y:y(v)+4,'text-anchor':'end'},svg).textContent=money(v); });
      for(var d=0;d<=5;d++) el('text',{x:x(d),y:H-8,'text-anchor':'middle'},svg).textContent=d?(W<480?'D'+d:'Day '+d):(W<480?'0':'Start');
      el('line',{x1:L,x2:W-R,y1:y(maint),y2:y(maint),stroke:css('--red'),'stroke-width':1.5,'stroke-dasharray':'6 5'},svg);
      var dpath=path.map(function(p,i){return (i?'L':'M')+x(p.d).toFixed(1)+' '+y(p.bal).toFixed(1);}).join(' ');
      el('path',{d:dpath,fill:'none',stroke:css('--gold'),'stroke-width':2.5,'stroke-linejoin':'round'},svg);
      path.forEach(function(p){ el('circle',{cx:x(p.d),cy:y(p.bal),r:p.topup?4:3.5,fill:p.topup?css('--red'):css('--gold-hi')},svg); });
      svg.setAttribute('aria-label','Account balance over five days, starting at '+money(init)+', with the maintenance level at '+money(maint)+'.');
    }
    root.addEventListener('input',run); root.addEventListener('change',run); redraw.push(run);
    run();
  }

  // ---------- options: Black-Scholes and payoffs ----------
  function ncdf(x){ // Abramowitz–Stegun 7.1.26 via erf, accurate to ~1e-7
    var t=1/(1+0.3275911*Math.abs(x)/Math.SQRT2), a=[0.254829592,-0.284496736,1.421413741,-1.453152027,1.061405429];
    var erf=1-(((((a[4]*t+a[3])*t)+a[2])*t+a[1])*t+a[0])*t*Math.exp(-x*x/2);
    return x>=0?0.5*(1+erf):0.5*(1-erf);
  }
  function bs(kind,S,K,T,r,v){
    if(T<=0||v<=0) return Math.max(kind==='call'?S-K:K-S,0);
    var d1=(Math.log(S/K)+(r+v*v/2)*T)/(v*Math.sqrt(T)), d2=d1-v*Math.sqrt(T);
    return kind==='call'?S*ncdf(d1)-K*Math.exp(-r*T)*ncdf(d2):K*Math.exp(-r*T)*ncdf(-d2)-S*ncdf(-d1);
  }
  var STRATS={
    'long-call':     {name:'Long call',      legs:function(K,K2){return [['call',K,1]];}},
    'long-put':      {name:'Long put',       legs:function(K,K2){return [['put',K,1]];}},
    'short-call':    {name:'Short call',     legs:function(K,K2){return [['call',K,-1]];}},
    'short-put':     {name:'Short put',      legs:function(K,K2){return [['put',K,-1]];}},
    'covered-call':  {name:'Covered call',   legs:function(K,K2){return [['stock',0,1],['call',K,-1]];}},
    'protective-put':{name:'Protective put', legs:function(K,K2){return [['stock',0,1],['put',K,1]];}},
    'bull-spread':   {name:'Bull call spread',legs:function(K,K2){return [['call',K,1],['call',K2,-1]];}, two:true},
    'straddle':      {name:'Long straddle',  legs:function(K,K2){return [['call',K,1],['put',K,1]];}}
  };
  function options(root){
    var f={strat:$(root,'[name=strat]'),S:$(root,'[name=spot]'),K:$(root,'[name=k1]'),K2:$(root,'[name=k2]'),
           vol:$(root,'[name=vol]'),days:$(root,'[name=days]'),rate:$(root,'[name=rate]')};
    var k2wrap=$(root,'.k2'), svg=$(root,'svg.chart'), out=$(root,'.out'), volv=$(root,'.volv'), daysv=$(root,'.daysv');
    function run(){
      var st=STRATS[f.strat.value]||STRATS['long-call'];
      var S0=Math.max(1,num(f.S,100)), K=Math.max(1,num(f.K,100)), K2=Math.max(K+1,num(f.K2,110));
      var v=Math.max(0.01,num(f.vol,25)/100), T=Math.max(0,num(f.days,90))/365, r=num(f.rate,4)/100;
      k2wrap.hidden=!st.two; volv.textContent=Math.round(v*100)+'%'; daysv.textContent=Math.round(T*365)+' days';
      var legs=st.legs(K,K2).map(function(l){
        return {kind:l[0],K:l[1],q:l[2],prem:l[0]==='stock'?S0:bs(l[0],S0,l[1],T,r,v)};
      });
      function atExpiry(S){ return legs.reduce(function(s,l){
        var pay=l.kind==='stock'?S:Math.max(l.kind==='call'?S-l.K:l.K-S,0); return s+l.q*(pay-l.prem); },0); }
      function today(S){ return legs.reduce(function(s,l){
        var val=l.kind==='stock'?S:bs(l.kind,S,l.K,T,r,v); return s+l.q*(val-l.prem); },0); }
      var lo=S0*0.6, hi=S0*1.4, n=160, pts=[], i, S;
      for(i=0;i<=n;i++){ S=lo+(hi-lo)*i/n; pts.push([S,atExpiry(S),today(S)]); }
      // breakevens, max gain and loss on a wide grid; "unlimited" when the payoff still slopes at the far end
      var be=[], wide=[], prevS=null, prevP=null;
      for(i=0;i<=3000;i++){ S=S0*3*i/3000; var p=atExpiry(S); wide.push(p);
        if(prevS!==null && (prevP<0)!==(p<0) && p!==prevP) be.push(prevS+(S-prevS)*(-prevP)/(p-prevP));
        prevS=S; prevP=p; }
      var top=Math.max.apply(null,wide), bot=Math.min.apply(null,wide), slope=atExpiry(S0*3+1)-atExpiry(S0*3);
      var maxG=slope>1e-9?'Unlimited':money(top*100), maxL=slope<-1e-9?'Unlimited':money(bot*100);
      var net=legs.reduce(function(s,l){return s+(l.kind==='stock'?0:l.q*l.prem);},0);
      out.innerHTML='<span>'+(net>=0?'Premium paid':'Premium received')+' per contract (100 shares): <b>'+money(Math.abs(net)*100)+'</b></span>'+
        '<span>Breakeven at expiry: <b>'+(be.length?be.map(function(b){return '$'+b.toFixed(2);}).join(' and '):'none')+'</b></span>'+
        '<span>Best case: <b class="up">'+(maxG==='Unlimited'?maxG:'+'+maxG)+'</b></span>'+
        '<span>Worst case: <b class="down">'+maxL+'</b></span>';
      draw(pts,S0,legs);
      svg.setAttribute('aria-label',st.name+': profit or loss per share against the stock price at expiry, from $'+lo.toFixed(0)+' to $'+hi.toFixed(0)+'.');
    }
    function draw(pts,S0,legs){
      while(svg.firstChild) svg.removeChild(svg.firstChild);
      var wh=size(svg,0.44,220), W=wh[0], H=wh[1], L=50, R=18, T=14, B=30;
      var ys=[];pts.forEach(function(p){ys.push(p[1],p[2]);});
      var lo=Math.min.apply(null,ys.concat([0])), hi=Math.max.apply(null,ys.concat([0])), pad=(hi-lo)*0.1||1; lo-=pad; hi+=pad;
      var x0=pts[0][0], x1=pts[pts.length-1][0];
      var x=function(s){return L+(W-L-R)*(s-x0)/(x1-x0);}, y=function(v){return T+(H-T-B)*(hi-v)/(hi-lo);};
      ticks(lo,hi,4).forEach(function(gv){
        el('line',{x1:L,x2:W-R,y1:y(gv),y2:y(gv),stroke:css('--line'),'stroke-width':1},svg);
        el('text',{x:L-8,y:y(gv)+4,'text-anchor':'end'},svg).textContent=(gv<0?'−$':'$')+Math.abs(gv).toFixed(0); });
      ticks(x0,x1,W<480?3:5).forEach(function(sv){ el('text',{x:x(sv),y:H-8,'text-anchor':'middle'},svg).textContent='$'+sv.toFixed(0); });
      // shade profit green and loss red at expiry
      var up='M'+x(x0)+' '+y(0), dn='M'+x(x0)+' '+y(0);
      pts.forEach(function(p){ up+=' L'+x(p[0]).toFixed(1)+' '+y(Math.max(p[1],0)).toFixed(1); dn+=' L'+x(p[0]).toFixed(1)+' '+y(Math.min(p[1],0)).toFixed(1); });
      up+=' L'+x(x1)+' '+y(0)+' Z'; dn+=' L'+x(x1)+' '+y(0)+' Z';
      el('path',{d:up,fill:css('--green'),'fill-opacity':0.16},svg);
      el('path',{d:dn,fill:css('--red'),'fill-opacity':0.16},svg);
      el('line',{x1:L,x2:W-R,y1:y(0),y2:y(0),stroke:css('--dim2'),'stroke-width':1.2},svg);
      el('line',{x1:x(S0),x2:x(S0),y1:T,y2:H-B,stroke:css('--dim2'),'stroke-width':1,'stroke-dasharray':'3 4'},svg);
      el('text',{x:x(S0)+4,y:T+12},svg).textContent='today $'+S0.toFixed(0);
      var line=function(k){return pts.map(function(p,i){return (i?'L':'M')+x(p[0]).toFixed(1)+' '+y(p[k]).toFixed(1);}).join(' ');};
      el('path',{d:line(2),fill:'none',stroke:css('--cream'),'stroke-width':1.6,'stroke-dasharray':'6 5','stroke-opacity':0.85},svg);
      el('path',{d:line(1),fill:'none',stroke:css('--gold'),'stroke-width':2.6,'stroke-linejoin':'round'},svg);
    }
    root.addEventListener('input',run); root.addEventListener('change',run); redraw.push(run);
    run();
  }

  var fs=document.getElementById('fut-sim'); if(fs) futures(fs);
  var os=document.getElementById('opt-sim'); if(os) options(os);
})();
