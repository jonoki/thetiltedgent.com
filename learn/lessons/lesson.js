// Lessons: the interactive widgets. Without this script each page's text and tables still teach everything; the
// widgets are hidden and a short note says what they do.
//   #fut-sim  futures: a position marked to market over five days, with margin calls (futures.html)
//   #opt-sim  options: profit at expiry and value today for a call, put or simple strategy (options.html)
//   #stk-sim  stocks: $10,000 with and without dividends reinvested           #bond-sim  bonds: price against yield
//   #cash-sim cash: interest against inflation, in today's dollars            #etf-sim   ETFs: what fees cost over time
//   #mf-sim   mutual funds: an active fund's fees and load against an index    #reit-sim  REITs: cap rate and share value
//   #pref-sim preferred shares: price against yield, with the call price      #cry-sim   crypto: $1,000 in BTC, ETH, S&P 500
//   The last one reads data/crypto.json, written from our own reports by tools/lesson_data.py.
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
  // profit at expiry (gold, green/red shading) and value today (dashed) against the stock price; pts = [S, expiry, today]
  function payoff(svg,pts,S0){
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
      payoff(svg,pts,S0);
      svg.setAttribute('aria-label',st.name+': profit or loss per share against the stock price at expiry, from $'+lo.toFixed(0)+' to $'+hi.toFixed(0)+'.');
    }
    root.addEventListener('input',run); root.addEventListener('change',run); redraw.push(run);
    run();
  }

  // ---------- a shared line chart for the other lessons ----------
  // spec: {x:[numbers], series:[{v:[numbers], color, dash, w}], yfmt, xfmt, xticks:[{x,label}]|null, refs:[{y,color,dash}],
  //        mark:{x,y}, ratio, minH, label}
  function line(svg,spec){
    while(svg.firstChild) svg.removeChild(svg.firstChild);
    var wh=size(svg,spec.ratio||0.42,spec.minH||210), W=wh[0], H=wh[1], L=spec.left||64, R=16, T=14, B=30;
    var ys=[]; spec.series.forEach(function(s){ s.v.forEach(function(v){ if(isFinite(v)) ys.push(v); }); });
    (spec.refs||[]).forEach(function(r){ ys.push(r.y); });
    var lo=spec.ymin!=null?spec.ymin:Math.min.apply(null,ys), hi=Math.max.apply(null,ys), pad=(hi-lo)*0.08||1;
    if(spec.ymin==null) lo-=pad; hi+=pad;
    var x0=spec.x[0], x1=spec.x[spec.x.length-1];
    var x=function(v){return L+(W-L-R)*(v-x0)/((x1-x0)||1);}, y=function(v){return T+(H-T-B)*(hi-v)/((hi-lo)||1);};
    ticks(lo,hi,4).forEach(function(v){
      el('line',{x1:L,x2:W-R,y1:y(v),y2:y(v),stroke:css('--line'),'stroke-width':1},svg);
      el('text',{x:L-8,y:y(v)+4,'text-anchor':'end'},svg).textContent=spec.yfmt(v); });
    (spec.xticks||ticks(x0,x1,W<480?3:5).map(function(v){return {x:v,label:spec.xfmt(v)};})).forEach(function(t){
      el('text',{x:x(t.x),y:H-8,'text-anchor':'middle'},svg).textContent=t.label; });
    (spec.refs||[]).forEach(function(r){
      el('line',{x1:L,x2:W-R,y1:y(r.y),y2:y(r.y),stroke:r.color||css('--dim2'),'stroke-width':1.3,'stroke-dasharray':r.dash||'5 5'},svg); });
    spec.series.forEach(function(s){
      var d=''; s.v.forEach(function(v,i){ if(isFinite(v)) d+=(d?' L':'M')+x(spec.x[i]).toFixed(1)+' '+y(v).toFixed(1); });
      el('path',{d:d,fill:'none',stroke:s.color,'stroke-width':s.w||2.5,'stroke-dasharray':s.dash||'','stroke-linejoin':'round'},svg); });
    if(spec.mark){ el('line',{x1:x(spec.mark.x),x2:x(spec.mark.x),y1:T,y2:H-B,stroke:css('--dim2'),'stroke-width':1,'stroke-dasharray':'3 4'},svg);
      el('circle',{cx:x(spec.mark.x),cy:y(spec.mark.y),r:4.5,fill:css('--gold-hi')},svg); }
    svg.setAttribute('aria-label',spec.label||'Chart');
  }
  function years(n){ var a=[]; for(var i=0;i<=n;i++) a.push(i); return a; }
  function pct(v,dp){ return (v>=0?'':'−')+Math.abs(v).toFixed(dp==null?1:dp)+'%'; }
  function kfmt(v){ // $500, $1.5k, $75k, $1.2M: one decimal only where whole units would merge two ticks
    var a=Math.abs(v), s;
    if(a>=1e6) s=(a/1e6).toFixed(1).replace(/\.0$/,'')+'M';
    else if(a>=1e3) s=(a<1e4?(a/1e3).toFixed(1).replace(/\.0$/,''):Math.round(a/1e3))+'k';
    else s=String(Math.round(a));
    return (v<0?'−$':'$')+s;
  }
  function wire(root,run){ root.addEventListener('input',run); root.addEventListener('change',run); redraw.push(run); run(); }
  function vals(root){ var o={}; [].forEach.call(root.querySelectorAll('[name]'),function(e){ o[e.name]=e.type==='checkbox'?e.checked:parseFloat(e.value); }); return o; }
  function show(root,name,text){ var e=$(root,'.v-'+name); if(e) e.textContent=text; }

  // stocks: price growth alone, against price growth plus dividends reinvested (total return = growth + yield)
  function stocks(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out');
    wire(root,function(){
      var o=vals(root), g=(o.growth||0)/100, dy=(o.yield||0)/100, n=Math.max(1,Math.round(o.years||30)), p0=o.amount||10000;
      show(root,'years',n+' years');
      var xs=years(n), price=xs.map(function(t){return p0*Math.pow(1+g,t);}), tot=xs.map(function(t){return p0*Math.pow(1+g+dy,t);});
      var share=1-price[n]/tot[n];
      line(svg,{x:xs,series:[{v:tot,color:css('--gold')},{v:price,color:css('--cream'),dash:'6 5',w:1.8}],yfmt:kfmt,
        xfmt:function(v){return 'Yr '+Math.round(v);},ymin:0,label:'Growth of '+money(p0)+' over '+n+' years'});
      out.innerHTML='<span>Shares alone, dividends spent: <b>'+money(price[n])+'</b></span><span>Dividends reinvested: <b class="up">'+money(tot[n])+
        '</b></span><span>Part of that from reinvesting: <b>'+Math.round(share*100)+'%</b></span>';
    });
  }

  // bonds: price of a fixed-coupon bond across yields, with the duration estimate at the chosen yield
  function bondPrice(cpn,yrs,ytm){ var n=Math.max(1,Math.round(yrs*2)), c=1000*cpn/2, y=ytm/2, p=0;
    for(var k=1;k<=n;k++) p+=c/Math.pow(1+y,k); return p+1000/Math.pow(1+y,n); }
  function bonds(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out');
    wire(root,function(){
      var o=vals(root), cpn=(o.coupon||4)/100, yrs=Math.max(1,o.maturity||10), y0=(o.ytm||4)/100;
      show(root,'ytm',(y0*100).toFixed(1)+'%'); show(root,'maturity',Math.round(yrs)+' years');
      var xs=[],ps=[]; for(var i=0;i<=95;i++){ var y=0.005+i*0.001; xs.push(y*100); ps.push(bondPrice(cpn,yrs,y)); }
      var p0=bondPrice(cpn,yrs,y0), h=1e-5, md=-(bondPrice(cpn,yrs,y0+h)-bondPrice(cpn,yrs,y0-h))/(2*h)/p0;
      var tan=xs.map(function(yp){ return p0*(1-md*(yp/100-y0)); });
      var up=bondPrice(cpn,yrs,y0+0.01);
      line(svg,{x:xs,series:[{v:ps,color:css('--gold')},{v:tan,color:css('--cream'),dash:'6 5',w:1.4}],refs:[{y:1000}],
        yfmt:function(v){return '$'+Math.round(v);},xfmt:function(v){return v.toFixed(0)+'%';},mark:{x:y0*100,y:p0},
        label:'Price of a $1,000 bond against its yield'});
      out.innerHTML='<span>Price at '+(y0*100).toFixed(1)+'%: <b>'+money(p0,2)+'</b></span><span>Duration: <b>'+md.toFixed(2)+'</b></span>'+
        '<span>If yields rise 1 point: <b class="down">'+money(up,2)+'</b> ('+pct((up/p0-1)*100,1)+'; duration says '+pct(-md,1)+')</span>';
    });
  }

  // cash: a balance growing at the interest rate, and the same balance in today's dollars after inflation
  function cash(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out');
    wire(root,function(){
      var o=vals(root), r=(o.rate||0)/100, inf=(o.inflation||0)/100, n=Math.max(1,Math.round(o.years||10)), a=o.amount||10000;
      show(root,'years',n+' years');
      var xs=years(n), nom=xs.map(function(t){return a*Math.pow(1+r,t);}), real=xs.map(function(t){return nom[t]/Math.pow(1+inf,t);});
      var rr=(1+r)/(1+inf)-1;
      line(svg,{x:xs,series:[{v:nom,color:css('--gold')},{v:real,color:css('--cream'),dash:'6 5',w:1.8}],refs:[{y:a}],yfmt:kfmt,
        xfmt:function(v){return 'Yr '+Math.round(v);},label:'Balance and its buying power over '+n+' years'});
      out.innerHTML='<span>Balance: <b>'+money(nom[n])+'</b></span><span>In today&rsquo;s dollars: <b class="'+(real[n]>=a?'up':'down')+'">'+money(real[n])+
        '</b></span><span>Real return: <b class="'+(rr>=0?'up':'down')+'">'+pct(rr*100,2)+'</b> a year</span>';
    });
  }

  // ETFs: the same market return, less two different yearly fees
  function etf(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out');
    wire(root,function(){
      var o=vals(root), g=(o.ret||7)/100, fa=(o.feea||0)/100, fb=(o.feeb||0)/100, n=Math.max(1,Math.round(o.years||30)), a=o.amount||10000;
      show(root,'years',n+' years');
      var xs=years(n), A=xs.map(function(t){return a*Math.pow(1+g-fa,t);}), B=xs.map(function(t){return a*Math.pow(1+g-fb,t);});
      var gap=A[n]-B[n], gainA=A[n]-a;
      line(svg,{x:xs,series:[{v:A,color:css('--gold')},{v:B,color:css('--cream'),dash:'6 5',w:1.8}],yfmt:kfmt,ymin:0,
        xfmt:function(v){return 'Yr '+Math.round(v);},label:'Growth of '+money(a)+' at two fee levels'});
      out.innerHTML='<span>At '+(fa*100).toFixed(2)+'% a year: <b>'+money(A[n])+'</b></span><span>At '+(fb*100).toFixed(2)+'% a year: <b>'+money(B[n])+
        '</b></span><span>Difference: <b class="down">'+money(gap)+'</b>'+(gainA>0?' ('+Math.round(100*gap/gainA)+'% of the cheaper fund&rsquo;s gain)':'')+'</span>';
    });
  }

  // mutual funds: an index fund against an active fund with a front-end load, a higher fee and some skill
  function mfund(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out');
    wire(root,function(){
      var o=vals(root), g=(o.ret||7)/100, fi=(o.feei||0)/100, fa=(o.feea||0)/100, load=(o.load||0)/100, sk=(o.skill||0)/100,
          n=Math.max(1,Math.round(o.years||25)), a=o.amount||10000;
      show(root,'years',n+' years'); show(root,'skill',(sk>=0?'+':'')+(sk*100).toFixed(1)+'%');
      var xs=years(n), I=xs.map(function(t){return a*Math.pow(1+g-fi,t);}), A=xs.map(function(t){return a*(1-load)*Math.pow(1+g+sk-fa,t);});
      var lo=-0.1, hi=0.2, mid; for(var k=0;k<60;k++){ mid=(lo+hi)/2; if(a*(1-load)*Math.pow(1+g+mid-fa,n)<I[n]) lo=mid; else hi=mid; }
      line(svg,{x:xs,series:[{v:I,color:css('--gold')},{v:A,color:css('--cream'),dash:'6 5',w:1.8}],yfmt:kfmt,ymin:0,
        xfmt:function(v){return 'Yr '+Math.round(v);},label:'Index fund against active fund over '+n+' years'});
      out.innerHTML='<span>Index fund: <b>'+money(I[n])+'</b></span><span>Active fund: <b class="'+(A[n]>=I[n]?'up':'down')+'">'+money(A[n])+
        '</b></span><span>Skill needed just to tie: <b>'+(mid*100).toFixed(2)+'%</b> a year before fees</span>';
    });
  }

  // REITs: value per share of a leveraged property company as the cap rate changes
  function reit(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out');
    wire(root,function(){
      var o=vals(root), noi=(o.noi||1)*1e6, debt=(o.debt||0)*1e6, sh=Math.max(0.01,o.shares||1)*1e6, cap=(o.cap||5)/100;
      show(root,'cap',(cap*100).toFixed(2)+'%');
      function per(c){ return (noi/c-debt)/sh; }
      var xs=[],v=[]; for(var i=0;i<=70;i++){ var c=0.03+i*0.001; xs.push(c*100); v.push(per(c)); }
      var now=per(cap), next=per(cap+0.005);
      line(svg,{x:xs,series:[{v:v,color:css('--gold')}],refs:[{y:0,color:css('--red')}],yfmt:function(x){return (x<0?'−$':'$')+Math.abs(x).toFixed(0);},
        xfmt:function(x){return x.toFixed(0)+'%';},mark:{x:cap*100,y:now},label:'Equity value per share against the cap rate'});
      out.innerHTML='<span>Property value: <b>'+money(noi/cap)+'</b></span><span>Equity per share: <b>'+money(now,2)+'</b></span>'+
        '<span>If the cap rate rises half a point: <b class="down">'+money(next,2)+'</b> ('+pct((next/now-1)*100,0)+')</span>';
    });
  }

  // preferred shares: a perpetual dividend priced at the market's yield, and the cap a call price puts on it
  function pref(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out');
    wire(root,function(){
      var o=vals(root), d=o.div||1.5, call=o.call||25, y0=(o.yld||6)/100, callable=$(root,'[name=callable]').checked;
      show(root,'yld',(y0*100).toFixed(1)+'%');
      var xs=[],perp=[],cap=[]; for(var i=0;i<=90;i++){ var y=0.03+i*0.001; xs.push(y*100); perp.push(d/y); cap.push(Math.min(d/y,call)); }
      var p=callable?Math.min(d/y0,call):d/y0;
      var series=[{v:perp,color:callable?css('--cream'):css('--gold'),dash:callable?'6 5':'',w:callable?1.4:2.5}];
      if(callable) series.push({v:cap,color:css('--gold')});
      line(svg,{x:xs,series:series,refs:[{y:call}],yfmt:function(v){return '$'+Math.round(v);},xfmt:function(v){return v.toFixed(0)+'%';},
        mark:{x:y0*100,y:p},label:'Preferred share price against the market yield'});
      out.innerHTML='<span>Price at '+(y0*100).toFixed(1)+'%: <b>'+money(p,2)+'</b></span><span>Yield on that price: <b>'+(100*d/p).toFixed(2)+'%</b></span>'+
        (callable&&d/y0>call?'<span>Held near the call price: the issuer can redeem at <b>'+money(call,2)+'</b></span>':'');
    });
  }

  // crypto: $1,000 from a chosen month in bitcoin, ether and the S&P 500, from our reports' month-end closes
  function crypto(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out'), sel=$(root,'[name=start]'), note=$(root,'.asof');
    fetch('/learn/lessons/data/crypto.json?v=20261011').then(function(r){return r.ok?r.json():null;}).then(function(d){
      if(!d){ out.textContent='The price data did not load.'; return; }
      sel.innerHTML=d.labels.slice(0,-12).map(function(l,i){return '<option value="'+i+'">'+l.replace(/ (\d\d)$/,' 20$1')+'</option>';}).join('');
      note.textContent='Month-end closes from our reports: bitcoin and ether as of '+d.as_of.btc+'; the S&P 500 (VOO, dividends reinvested) as of '+d.as_of.voo+'.';
      var keys=['btc','eth','voo'], colors={btc:css('--gold'),eth:css('--pink-neon'),voo:css('--cream')};
      wire(root,function(){
        var s=Math.max(0,parseInt(sel.value,10)||0), lab=d.labels.slice(s), xs=lab.map(function(_,i){return i;}), res={};
        var series=keys.map(function(k){
          var v=d.series[k].slice(s), base=v[0], peak=v[0], dd=0;
          var path=v.map(function(p){ peak=Math.max(peak,p); dd=Math.min(dd,p/peak-1); return 1000*p/base; });
          res[k]={end:path[path.length-1],dd:dd};
          return {v:path,color:colors[k],dash:k==='voo'?'6 5':'',w:k==='voo'?1.8:2.4};
        });
        var step=Math.max(1,Math.ceil(lab.length/(svg.getBoundingClientRect().width<480?3:6)));
        var xt=[]; for(var i=0;i<lab.length;i+=step) xt.push({x:i,label:lab[i].replace(/ (\d\d)$/,' ’$1')});
        line(svg,{x:xs,series:series,refs:[{y:1000}],yfmt:kfmt,xticks:xt,label:'Value of $1,000 from '+lab[0]});
        out.innerHTML=keys.map(function(k){ return '<span>'+d.names[k].replace(/ \(.*/,'')+': <b class="'+(res[k].end>=1000?'up':'down')+'">'+money(res[k].end)+
          '</b>, worst fall <b class="down">'+pct(res[k].dd*100,0)+'</b></span>'; }).join('');
      });
    }).catch(function(){ out.textContent='The price data did not load.'; });
  }

  // ---------- financial statements ----------
  // a horizontal waterfall: rows {label, v, kind:'start'|'delta'|'total'}; deltas float from the running total
  function waterfall(svg,rows){
    while(svg.firstChild) svg.removeChild(svg.firstChild);
    var W=Math.max(300,Math.round(svg.getBoundingClientRect().width)||640), rowH=26, T=8, B=26, H=T+B+rows.length*rowH;
    svg.setAttribute('viewBox','0 0 '+W+' '+H); svg.style.height=H+'px';
    var L=Math.min(190,Math.round(W*0.38)), R=64, run=0, spans=[];
    rows.forEach(function(r){
      if(r.kind==='delta'){ spans.push([run,run+r.v]); run+=r.v; }
      else { run=r.v; spans.push([0,r.v]); }
    });
    var all=[0]; spans.forEach(function(s){all.push(s[0],s[1]);});
    var lo=Math.min.apply(null,all), hi=Math.max.apply(null,all); if(hi===lo) hi=lo+1;
    var x=function(v){return L+(W-L-R)*(v-lo)/(hi-lo);};
    el('line',{x1:x(0),x2:x(0),y1:T,y2:H-B,stroke:css('--dim2'),'stroke-width':1},svg);
    ticks(lo,hi,W<480?2:4).forEach(function(v){ el('text',{x:x(v),y:H-8,'text-anchor':'middle'},svg).textContent=kfmt(v); });
    rows.forEach(function(r,i){
      var y=T+i*rowH, s=spans[i], a=Math.min(s[0],s[1]), b=Math.max(s[0],s[1]);
      var col=r.kind==='delta'?(r.v>=0?css('--green'):css('--red')):css('--gold');
      el('rect',{x:x(a),y:y+5,width:Math.max(1.5,x(b)-x(a)),height:rowH-10,rx:2,fill:col,'fill-opacity':r.kind==='delta'?0.75:0.95},svg);
      var t=el('text',{x:L-8,y:y+rowH/2+4,'text-anchor':'end'},svg); t.textContent=r.label;
      if(r.kind!=='delta') t.setAttribute('style','fill:'+css('--cream'));
      el('text',{x:x(b)+6,y:y+rowH/2+4,'text-anchor':'start'},svg).textContent=(r.kind==='delta'&&r.v>0?'+':'')+kfmt(r.v);   // R keeps room for it
    });
  }

  // income statement: from revenue down to net income
  function income(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out');
    wire(root,function(){
      var o=vals(root), rev=o.revenue||0, cogs=rev*(o.cogspct||0)/100, gp=rev-cogs, opx=(o.wages||0)+(o.rent||0)+(o.other||0)+(o.dep||0);
      var oi=gp-opx, it=o.interest||0, pre=oi-it, tax=Math.max(0,pre)*(o.taxrate||0)/100, ni=pre-tax;
      show(root,'cogspct',(o.cogspct||0)+'%');
      waterfall(svg,[{label:'Revenue',v:rev,kind:'start'},{label:'Ingredients',v:-cogs,kind:'delta'},{label:'Gross profit',v:gp,kind:'total'},
        {label:'Wages',v:-(o.wages||0),kind:'delta'},{label:'Rent',v:-(o.rent||0),kind:'delta'},{label:'Other costs',v:-(o.other||0),kind:'delta'},
        {label:'Depreciation',v:-(o.dep||0),kind:'delta'},{label:'Operating income',v:oi,kind:'total'},{label:'Interest',v:-it,kind:'delta'},
        {label:'Tax',v:-tax,kind:'delta'},{label:'Net income',v:ni,kind:'total'}]);
      svg.setAttribute('aria-label','From revenue of '+money(rev)+' to net income of '+money(ni));
      function m(v){ return rev?pct(100*v/rev,1):'—'; }
      out.innerHTML='<span>Gross margin: <b>'+m(gp)+'</b></span><span>Operating margin: <b>'+m(oi)+'</b></span><span>Net margin: <b class="'+(ni>=0?'up':'down')+'">'+m(ni)+'</b></span>';
    });
  }

  // balance sheet: what it owns against what it owes; equity is whatever is left
  function balance(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out');
    wire(root,function(){
      var o=vals(root), A=[['Cash',o.cash||0,'--gold-hi'],['Receivables',o.ar||0,'--gold'],['Inventory',o.inv||0,'--gold-deep'],['Equipment',o.ppe||0,'--dim']];
      var Lb=[['Payables',o.ap||0,'--red-neon'],['Loan',o.loan||0,'--red']], ta=A.reduce(function(s,a){return s+a[1];},0), tl=Lb.reduce(function(s,a){return s+a[1];},0), eq=ta-tl;
      while(svg.firstChild) svg.removeChild(svg.firstChild);
      var wh=size(svg,0.5,240), W=wh[0], H=wh[1], T=14, B=34, top=Math.max(ta,tl,1), y=function(v){return T+(H-T-B)*(1-v/top);}, bw=Math.min(150,W*0.26);
      function stack(xc,items,label){ var base=0; items.forEach(function(it){ if(it[1]<=0) return;
          el('rect',{x:xc-bw/2,y:y(base+it[1]),width:bw,height:y(base)-y(base+it[1]),fill:css(it[2]),'fill-opacity':0.85,stroke:css('--bg'),'stroke-width':1},svg);
          if(y(base)-y(base+it[1])>16) el('text',{x:xc,y:(y(base)+y(base+it[1]))/2+4,'text-anchor':'middle',style:'fill:'+css('--bg')+';font-weight:700'},svg).textContent=it[0];
          base+=it[1]; });
        el('text',{x:xc,y:H-12,'text-anchor':'middle',style:'fill:'+css('--cream')},svg).textContent=label; }
      stack(W*0.3,A,'What it owns '+kfmt(ta));
      stack(W*0.7,Lb.concat(eq>0?[['Equity',eq,'--violet-neon']]:[]),'Owes + owners '+kfmt(Math.max(ta,tl)));
      svg.setAttribute('aria-label','Assets of '+money(ta)+' against liabilities of '+money(tl)+' and equity of '+money(eq));
      out.innerHTML='<span>Total assets: <b>'+money(ta)+'</b></span><span>Total liabilities: <b>'+money(tl)+'</b></span>'+
        '<span>Equity, what&rsquo;s left for the owners: <b class="'+(eq>=0?'up':'down')+'">'+money(eq)+'</b></span>'+
        (eq<0?'<span><b class="down">It owes more than it owns.</b></span>':'<span>Debt-to-equity: <b>'+(eq?((o.loan||0)/eq).toFixed(2):'—')+'</b></span>');
    });
  }

  // cash flow: from net income to the cash the business actually produced, then free cash flow
  function cashflow(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out');
    wire(root,function(){
      var o=vals(root), ni=o.ni||0, dep=o.dep||0, dar=o.dar||0, dinv=o.dinv||0, dap=o.dap||0, capex=o.capex||0;
      var cfo=ni+dep-dar-dinv+dap, fcf=cfo-capex;
      waterfall(svg,[{label:'Net income',v:ni,kind:'start'},{label:'+ Depreciation',v:dep,kind:'delta'},{label:'Receivables up',v:-dar,kind:'delta'},
        {label:'Inventory up',v:-dinv,kind:'delta'},{label:'Payables up',v:dap,kind:'delta'},{label:'Operating cash flow',v:cfo,kind:'total'},
        {label:'Capital spending',v:-capex,kind:'delta'},{label:'Free cash flow',v:fcf,kind:'total'}]);
      svg.setAttribute('aria-label','From net income of '+money(ni)+' to free cash flow of '+money(fcf));
      out.innerHTML='<span>Operating cash flow: <b>'+money(cfo)+'</b></span><span>Free cash flow: <b class="'+(fcf>=0?'up':'down')+'">'+money(fcf)+'</b></span>'+
        '<span>Cash per $1 of profit: <b>'+(ni?(cfo/ni).toFixed(2):'—')+'</b></span>';
    });
  }

  // how the three connect: post transactions and watch every statement move, and both checks hold
  var TX=[
    ['invest','Owners put in cash',function(s,a){s.cash+=a;s.paidin+=a;s.cf.fin+=a;}],
    ['borrow','Borrow from the bank',function(s,a){s.cash+=a;s.loan+=a;s.cf.fin+=a;}],
    ['oven','Buy an oven (cash)',function(s,a){s.cash-=a;s.ppe+=a;s.cf.inv-=a;}],
    ['stock','Buy ingredients on credit',function(s,a){s.inv+=a;s.ap+=a;}],
    ['sell','Sell pizzas for cash',function(s,a){var c=Math.min(s.inv,a*0.3);s.rev+=a;s.cogs+=c;s.inv-=c;s.cash+=a;s.cf.op+=a;}],
    ['cater','Cater an event, invoice later',function(s,a){var c=Math.min(s.inv,a*0.3);s.rev+=a;s.cogs+=c;s.inv-=c;s.ar+=a;}],
    ['collect','Collect an invoice',function(s,a){a=Math.min(a,s.ar);s.ar-=a;s.cash+=a;s.cf.op+=a;return a;}],
    ['paysup','Pay the supplier',function(s,a){a=Math.min(a,s.ap);s.ap-=a;s.cash-=a;s.cf.op-=a;return a;}],
    ['wages','Pay wages',function(s,a){s.opex+=a;s.cash-=a;s.cf.op-=a;}],
    ['dep','Record a year of depreciation',function(s,a){a=Math.min(a,s.ppe);s.dep+=a;s.ppe-=a;return a;}],
    ['div','Pay the owners a dividend',function(s,a){s.cash-=a;s.divs+=a;s.cf.fin-=a;}],
    ['repay','Repay part of the loan',function(s,a){a=Math.min(a,s.loan);s.loan-=a;s.cash-=a;s.cf.fin-=a;return a;}]
  ];
  function linked(root){
    var amt=$(root,'[name=amount]'), btns=$(root,'.txbtns'), log=$(root,'.txlog'), out=$(root,'.out'), st;
    function fresh(){ st={cash:0,ar:0,inv:0,ppe:0,ap:0,loan:0,paidin:0,divs:0,rev:0,cogs:0,opex:0,dep:0,cf:{op:0,inv:0,fin:0}}; log.innerHTML=''; }
    btns.innerHTML='<button type="button" class="seq">Post the opening sequence</button>'+
      TX.map(function(t){return '<button type="button" data-tx="'+t[0]+'">'+t[1]+'</button>';}).join('')+'<button type="button" class="reset">Start over</button>';
    var OPENING=[['invest',30000],['borrow',50000],['oven',60000],['stock',6000],['sell',10000],['cater',5000],['dep',12000]];
    function post(id,a){ var t=TX.filter(function(x){return x[0]===id;})[0]; if(!t||!a) return;
      var used=t[2](st,a); used=(typeof used==='number')?used:a; log.insertAdjacentHTML('afterbegin','<li>'+t[1]+': '+money(used)+'</li>'); }
    function row(k,v,cls){ return '<tr'+(cls?' class="'+cls+'"':'')+'><td>'+k+'</td><td class="num">'+money(v)+'</td></tr>'; }
    function render(){
      var s=st, ni=s.rev-s.cogs-s.opex-s.dep, re=ni-s.divs, ta=s.cash+s.ar+s.inv+s.ppe, tl=s.ap+s.loan, te=s.paidin+re;
      var cfo=s.cf.op, chg=s.cf.op+s.cf.inv+s.cf.fin;
      $(root,'.is tbody').innerHTML=row('Revenue',s.rev)+row('Cost of ingredients',-s.cogs)+row('Wages',-s.opex)+row('Depreciation',-s.dep)+row('Net income',ni,'tot');
      $(root,'.bs tbody').innerHTML=row('Cash',s.cash)+row('Receivables',s.ar)+row('Inventory',s.inv)+row('Equipment',s.ppe)+row('Total assets',ta,'tot')+
        row('Payables',s.ap)+row('Loan',s.loan)+row('Owners&rsquo; money in',s.paidin)+row('Retained earnings',re)+row('Liabilities + equity',tl+te,'tot');
      // operating cash shown the indirect way, the bridge from the cash flow lesson: the balances started at zero, so they are the changes
      $(root,'.cf tbody').innerHTML=row('Net income',ni)+row('+ Depreciation',s.dep)+row('&minus; Receivables up',-s.ar)+row('&minus; Inventory up',-s.inv)+
        row('+ Payables up',s.ap)+row('Operating',cfo,'tot')+row('Investing',s.cf.inv)+row('Financing',s.cf.fin)+row('Change in cash',chg,'tot');
      var okB=Math.abs(ta-tl-te)<0.005, okC=Math.abs(chg-s.cash)<0.005;
      out.innerHTML='<span>Assets = liabilities + equity: <b class="'+(okB?'up':'down')+'">'+(okB?'balances':'off')+'</b></span>'+
        '<span>Cash flow total = cash on the balance sheet: <b class="'+(okC?'up':'down')+'">'+(okC?'matches':'off')+'</b></span>'+
        '<span>Net income vs operating cash flow: <b>'+money(ni)+'</b> vs <b>'+money(cfo)+'</b></span>';
    }
    btns.addEventListener('click',function(e){
      var b=e.target.closest('button'); if(!b) return;
      if(b.classList.contains('reset')){ fresh(); render(); return; }
      if(b.classList.contains('seq')){ fresh(); OPENING.forEach(function(o){ post(o[0],o[1]); }); render(); return; }
      post(b.getAttribute('data-tx'),Math.max(0,parseFloat(amt.value)||0));
      render();
    });
    fresh(); render();
  }

  // ---------- options strategies: legs priced by Black-Scholes, with the position's Greeks ----------
  // a leg is [kind 'c'|'p', strike slot, quantity, 'back' for the calendar's longer-dated leg]
  var PRESETS={
    'bull-call':{s:[100,110],legs:[['c',0,1],['c',1,-1]]},       'bear-put':{s:[90,100],legs:[['p',1,1],['p',0,-1]]},
    'bull-put':{s:[90,100],legs:[['p',1,-1],['p',0,1]]},         'bear-call':{s:[100,110],legs:[['c',0,-1],['c',1,1]]},
    'long-straddle':{s:[100],legs:[['c',0,1],['p',0,1]]},         'short-straddle':{s:[100],legs:[['c',0,-1],['p',0,-1]]},
    'long-strangle':{s:[90,110],legs:[['p',0,1],['c',1,1]]},      'short-strangle':{s:[90,110],legs:[['p',0,-1],['c',1,-1]]},
    'butterfly':{s:[90,100,110],legs:[['c',0,1],['c',1,-2],['c',2,1]]},
    'iron-condor':{s:[85,95,105,115],legs:[['p',0,1],['p',1,-1],['c',2,-1],['c',3,1]]},
    'iron-butterfly':{s:[90,100,110],legs:[['p',0,1],['p',1,-1],['c',1,-1],['c',2,1]]},
    'collar':{s:[90,110],stock:1,legs:[['p',0,1],['c',1,-1]]},
    'calendar':{s:[100],legs:[['c',0,-1],['c',0,1,'back']]}
  };
  function greeks(kind,S,K,T,r,v){ // per share: delta, theta per day, vega per volatility point
    var sq=Math.sqrt(T), d1=(Math.log(S/K)+(r+v*v/2)*T)/(v*sq), d2=d1-v*sq, pdf=Math.exp(-d1*d1/2)/Math.sqrt(2*Math.PI);
    var th=-S*pdf*v/(2*sq)+(kind==='c'?-r*K*Math.exp(-r*T)*ncdf(d2):r*K*Math.exp(-r*T)*ncdf(-d2));
    return [kind==='c'?ncdf(d1):ncdf(d1)-1, th/365, S*pdf*sq/100];
  }
  function strategy(root){
    var svg=$(root,'svg.chart'), out=$(root,'.out'), sel=$(root,'[name=preset]'), bet=$(root,'.bet');
    var ks=[].slice.call(root.querySelectorAll('[name^=k]')), backWrap=$(root,'.back');
    function setDefaults(){ var p=PRESETS[sel.value]; ks.forEach(function(inp,i){ var on=i<p.s.length; inp.closest('label').hidden=!on; if(on) inp.value=p.s[i]; });
      backWrap.hidden=sel.value!=='calendar'; }
    sel.addEventListener('change',setDefaults); setDefaults();
    wire(root,function(){
      var p=PRESETS[sel.value], o=vals(root), S0=Math.max(1,o.spot||100), v=Math.max(0.01,(o.vol||25)/100), r=(o.rate||0)/100;
      var days=Math.max(1,Math.round(o.days||90)), gap=Math.max(1,Math.round(o.gap||60)), Tf=days/365, Tb=(days+gap)/365, K=p.s.map(function(_,i){return Math.max(1,ks[i]?parseFloat(ks[i].value)||p.s[i]:p.s[i]);});
      show(root,'vol',Math.round(v*100)+'%'); show(root,'days',days+' days'); show(root,'gap',gap+' more days');
      var legs=p.legs.map(function(l){ var T=l[3]==='back'?Tb:Tf, kind=l[0]==='c'?'call':'put'; return {kind:kind,k:l[0],K:K[l[1]],q:l[2],T:T,prem:bs(kind,S0,K[l[1]],T,r,v)}; });
      var stock=p.stock||0;
      function at(S,today){ return legs.reduce(function(s,l){ var left=today?l.T:l.T-Tf;
          return s+l.q*((left>1e-9?bs(l.kind,S,l.K,left,r,v):Math.max(l.kind==='call'?S-l.K:l.K-S,0))-l.prem); },0)+stock*(S-S0); }
      var lo=S0*0.6, hi=S0*1.4, pts=[], i, S;
      for(i=0;i<=160;i++){ S=lo+(hi-lo)*i/160; pts.push([S,at(S,false),at(S,true)]); }
      var be=[], wide=[], ps=null, pp=null;
      for(i=0;i<=3000;i++){ S=S0*3*i/3000; var pv=at(S,false); wide.push(pv);
        if(ps!==null&&(pp<0)!==(pv<0)&&pv!==pp) be.push(ps+(S-ps)*(-pp)/(pv-pp)); ps=S; pp=pv; }
      var slope=at(S0*3+1,false)-at(S0*3,false), top=Math.max.apply(null,wide), bot=Math.min.apply(null,wide);
      var net=legs.reduce(function(s,l){return s+l.q*l.prem;},0);
      var g=[0,0,0]; legs.forEach(function(l){ var x=greeks(l.k,S0,l.K,l.T,r,v); for(var j=0;j<3;j++) g[j]+=l.q*x[j]; }); g[0]+=stock;
      payoff(svg,pts,S0);
      svg.setAttribute('aria-label','Profit or loss per share at '+(sel.value==='calendar'?'the near expiry':'expiry')+', and today, against the stock price');
      out.innerHTML='<span>'+(net>=0?'Net cost':'Net credit')+' per contract: <b>'+money(Math.abs(net)*100)+'</b></span>'+
        '<span>Breakeven'+(be.length>1?'s':'')+': <b>'+(be.length?be.map(function(b){return '$'+b.toFixed(2);}).join(' and '):'none')+'</b></span>'+
        '<span>Best case: <b class="up">'+(slope>1e-9?'Unlimited':'+'+money(top*100))+'</b></span><span>Worst case: <b class="down">'+(slope<-1e-9?'Unlimited':money(bot*100))+'</b></span>';
      // per contract: a delta under 20 shares or a vega under $5 a point is too small to call a bet on it
      var d=Math.round(g[0]*100), dir=d>=20?'the stock rising':d<=-20?'the stock falling':'no particular direction';
      var vg=g[2]*100, mv=vg>=5?'the volatility priced into options rising':vg<=-5?'the volatility priced into options falling':'little exposure to volatility';
      bet.innerHTML='<span>Delta: <b>'+(d>=0?'+':'')+d+(Math.abs(d)===1?' share':' shares')+'</b></span><span>Theta: <b class="'+(g[1]>=0?'up':'down')+'">'+(g[1]>=0?'+':'')+money(g[1]*100,2)+'</b> a day</span>'+
        '<span>Vega: <b>'+(vg>=0?'+':'')+money(vg,2)+'</b> per volatility point</span><span>A bet on: <b>'+dir+'</b>; <b>'+mv+'</b>; time passing <b>'+(g[1]>=0?'helps':'hurts')+'</b>.</span>';
    });
  }

  var MODS={'strat-sim':strategy,'is-sim':income,'bs-sim':balance,'cf-sim':cashflow,'link-sim':linked,'fut-sim':futures,'opt-sim':options,'stk-sim':stocks,'bond-sim':bonds,'cash-sim':cash,'etf-sim':etf,'mf-sim':mfund,
            'reit-sim':reit,'pref-sim':pref,'cry-sim':crypto};
  for(var id in MODS){ var node=document.getElementById(id); if(node) MODS[id](node); }
})();
