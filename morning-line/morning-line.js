/* The Morning Line: reads the Day Trading Aid's public pre-market brief and explains it for a reader who does not
   follow markets. Vanilla JS, no dependencies. Bump the ?v= on morning-line/index.html when this file changes.

   The feed (https://jonoki.github.io/ttg-brief/brief.json) is owned by the Day Trading Aid repo
   (src/daytradingaid/brief/public.py decides what it may carry); this page only reads it. It is rebuilt about every
   15 minutes on weekdays from 06:25 to 12:00 ET, plus one run at about 16:05 ET after the close. This page fetches it at load, again
   every five minutes while the tab is visible during the session (weekdays 06:00–17:30 ET), and every five minutes
   while it has not loaded at all.

   The page never shows an old brief as today's: lineState() compares the brief's trading day with today's date in
   New York and the brief's age with STALE_HOURS.

   Test hooks, on a local preview server only (localhost / 127.0.0.1; ignored on the live site):
     ?feed=<url>   read another brief file, e.g. a saved sample
     ?now=<ISO>    pretend the clock reads this time, e.g. ?now=2026-10-08T13:45:00Z */
(function(){
  'use strict';

  var FEED = 'https://jonoki.github.io/ttg-brief/brief.json';
  var FEED_PAGE = 'https://jonoki.github.io/ttg-brief/';
  var REPORTS = '/data/reports.json';             // ticker -> report slug, written by tools/manifest.py
  var REFRESH_MS = 5 * 60 * 1000;
  var STALE_HOURS = 20;
  var ET = 'America/New_York';
  var LAST_KEY = 'ttg-ml-last';                    // localStorage: the last brief's trading day and update time

  var local = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  var query = new URLSearchParams(location.search);
  if (local && query.get('feed')) FEED = query.get('feed');
  var skew = local && query.get('now') && !isNaN(Date.parse(query.get('now'))) ? Date.parse(query.get('now')) - Date.now() : 0;
  function now(){ return new Date(Date.now() + skew); }

  var $ = function(id){ return document.getElementById(id); };
  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
    });
  }
  function safeUrl(u){ return /^https?:\/\//i.test(String(u || '')) ? String(u) : null; }

  /* ---------- dates and times, always in New York time ---------- */
  function etParts(d){
    var o = {};
    new Intl.DateTimeFormat('en-US', {timeZone: ET, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23'}).formatToParts(d).forEach(function(p){ o[p.type] = p.value; });
    return {date: o.year + '-' + o.month + '-' + o.day, mins: (+o.hour % 24) * 60 + (+o.minute)};
  }
  function noonUtc(iso){ return new Date(iso + 'T12:00:00Z'); }   // a calendar date, safe from time-zone edges
  function dayLong(iso){ return noonUtc(iso).toLocaleDateString('en-US', {timeZone: 'UTC', weekday: 'long', month: 'long', day: 'numeric'}); }
  function weekday(iso){ return noonUtc(iso).toLocaleDateString('en-US', {timeZone: 'UTC', weekday: 'long'}); }
  function isWeekday(iso){ var d = noonUtc(iso).getUTCDay(); return d > 0 && d < 6; }
  function nextWeekday(iso){
    var d = noonUtc(iso);
    do { d.setUTCDate(d.getUTCDate() + 1); } while (d.getUTCDay() === 0 || d.getUTCDay() === 6);
    return d.toISOString().slice(0, 10);
  }
  function timeEt(isoTime){   // "8:30 a.m."
    return new Date(isoTime).toLocaleTimeString('en-US', {timeZone: ET, hour: 'numeric', minute: '2-digit'})
      .replace(/\s?AM$/, ' a.m.').replace(/\s?PM$/, ' p.m.');
  }
  function stampEt(isoTime, withDay){   // "4:05 p.m. ET" or "Thu, Oct 8, 4:05 p.m. ET"
    var day = withDay ? new Date(isoTime).toLocaleDateString('en-US', {timeZone: ET, weekday: 'short', month: 'short', day: 'numeric'}) + ', ' : '';
    return day + timeEt(isoTime) + ' ET';
  }
  function inSession(){   // weekdays 06:00–17:30 ET: when the brief can change
    var p = etParts(now());
    return isWeekday(p.date) && p.mins >= 6 * 60 && p.mins <= 17 * 60 + 30;
  }

  /* ---------- is this brief today's? ---------- */
  function lineState(b){
    var n = now(), p = etParts(n), day = b.meta.trading_day;
    var ageHours = (n - Date.parse(b.meta.generated_at_utc)) / 36e5;
    if (day >= p.date && ageHours <= STALE_HOURS){
      return b.meta.run === 'post-close' ? {kind: 'closed', next: nextWeekday(day)} : {kind: 'live'};
    }
    if (isWeekday(p.date) && p.mins < 6 * 60 + 25) return {kind: 'old', when: 'early'};
    if (isWeekday(p.date) && p.mins < 12 * 60) return {kind: 'old', when: 'late'};
    return {kind: 'old', when: 'next', next: nextWeekday(p.date)};
  }

  /* ---------- plain-English notes for the releases the calendar carries most often (first match wins). An
     unknown release falls back to the brief's own one-line description. ---------- */
  var IND = '/reports/view.html?r=indicators/';
  var RELEASES = [
    [/inflation expectations/i, 'What consumers expect prices to do over the coming year, from the University of Michigan’s survey. The Fed watches it because expected inflation can turn into the real thing.'],
    [/fomc.*minutes|minutes.*fomc/i, 'The written record of the Fed’s last interest-rate meeting, published three weeks after it. Markets read it for how the committee is leaning.'],
    [/speaks|speech|testif|remarks|press conference/i, 'A scheduled speech by a policymaker. Traders listen for hints about where interest rates go next.'],
    [/fomc|federal funds|fed interest rate|rate decision/i, 'The Federal Reserve’s interest-rate decision. Borrowing costs across the economy key off it, which makes it the biggest scheduled event on any calendar.', IND + 'fedtarget', 'the Fed’s rate'],
    [/core pce|pce price/i, 'The Fed’s preferred measure of inflation, from the government’s monthly report on what Americans earn and spend.', IND + 'corepce', 'core PCE inflation'],
    [/cpi|consumer price/i, 'The consumer price index: what a fixed basket of everyday goods and services costs compared with a month and a year earlier. It is the headline inflation number.', IND + 'cpi', 'CPI'],
    [/ppi|producer price/i, 'Producer prices: what businesses charge each other for goods and services. Rising costs here can reach shop shelves later.'],
    [/non-?farm|payrolls|employment change/i, 'The monthly jobs report: how many jobs US employers added. The Fed watches it closely, so a surprise either way moves markets.', IND + 'payrolls', 'payrolls'],
    [/unemployment rate/i, 'The share of people who want a job and can’t find one.', IND + 'unrate', 'the unemployment rate'],
    [/claims/i, 'How many people filed a new claim for unemployment benefits last week: the most up-to-date read on layoffs.'],
    [/jolts|job openings/i, 'How many jobs employers are trying to fill. Fewer openings mean a cooling job market.'],
    [/retail sales/i, 'How much shoppers spent in stores and online last month. Consumer spending is about two-thirds of the US economy.'],
    [/gdp/i, 'Gross domestic product: the value of everything the US economy produced. The broadest measure of growth.'],
    [/ism|pmi/i, 'A survey of purchasing managers. A reading above 50 means their side of the economy is growing; below 50, shrinking.'],
    [/sentiment|confidence/i, 'A survey of how confident consumers feel about their money and the economy.'],
    [/auction/i, 'The Treasury sells new government debt. Weak demand pushes up yields (the interest rate the bonds pay), which can weigh on stocks.', '/learn/table-talk/finance.html#treasury-auction', 'Treasury auctions'],
    [/housing starts|building permits|home sales/i, 'A read on the housing market, which moves with mortgage rates.'],
    [/durable goods/i, 'Orders for goods built to last, like machinery and aircraft: a read on business investment.']
  ];
  function releaseNote(e){
    for (var i = 0; i < RELEASES.length; i++){
      var r = RELEASES[i];
      if (r[0].test(e.name || '')) return {text: r[1], href: r[2], label: r[3]};
    }
    return e.explain && e.explain.what ? {text: e.explain.what} : null;
  }

  /* ---------- the blocks ---------- */
  function renderStatus(b, st, warn){
    var chip = {live: ['live', 'Live'], closed: ['closed', 'After the close'], old: ['old', weekday(b.meta.trading_day) + '’s line']}[st.kind];
    var sameDay = etParts(new Date(b.meta.generated_at_utc)).date === etParts(now()).date;
    $('ml-status').innerHTML = '<span class="chip ' + chip[0] + '">' + esc(chip[1]) + '</span>'
      + '<span>Brief for <b>' + esc(dayLong(b.meta.trading_day)) + '</b></span>'
      + '<span>Last updated <b class="mono">' + esc(stampEt(b.meta.generated_at_utc, !sameDay)) + '</b></span>'
      + (warn ? '<span class="warn">' + esc(warn) + '</span>' : '');
  }

  function renderNotice(b, st){
    var day = dayLong(b.meta.trading_day), html = '';
    if (st.kind === 'old'){
      var next = st.when === 'early' ? 'Today’s line posts from about 6:25 a.m. ET, before the open.'
        : st.when === 'late' ? 'Today’s line hasn’t posted yet. This page checks again every five minutes.'
        : 'The next one posts before ' + weekday(st.next) + '’s open.';
      html = '<div class="notice"><p class="nh">This is the brief for ' + esc(day) + '.</p><p>' + esc(next)
        + ' Everything below is as it stood when this brief was last updated.</p></div>';
    } else if (st.kind === 'closed'){
      html = '<div class="notice"><p class="nh">The market has closed for the day.</p><p>This is the brief as it stood after the 4 p.m. close. The next one posts before '
        + esc(weekday(st.next)) + '’s open.</p></div>';
    }
    $('ml-notice').innerHTML = html;
  }

  function renderMatters(b, st, heads){
    $('h-matters').textContent = st.kind === 'old' ? 'What mattered on ' + weekday(b.meta.trading_day) : 'What matters today';
    var sum = (b.news && b.news.summary) || {};
    var lines = sum.lines || [];
    // when the summariser fails the feed falls back to a digest of top headlines; say so instead of calling them AI lines
    var digest = (sum.warnings || []).some(function(w){ return /digest|no valid lines/i.test(String(w)); });
    if (!$('why-matters').dataset.ai) $('why-matters').dataset.ai = $('why-matters').textContent;
    $('why-matters').textContent = digest
      ? 'The written summary isn’t ready for this brief, so here are the morning’s top headlines instead. Each one links to its story.'
      : $('why-matters').dataset.ai;
    if (!lines.length){
      $('ml-matters').innerHTML = '<p class="empty">No summary in this brief' + (heads.length ? '; the headlines are below.' : '.') + '</p>';
      return;
    }
    var num = {};
    heads.forEach(function(h, i){ num[h.id] = i + 1; });
    $('ml-matters').innerHTML = '<ol class="lines">' + lines.map(function(line){
      var ids = (String(line).match(/\[[0-9a-f]{6,}\]/g) || []).map(function(x){ return x.slice(1, -1); });
      var text = String(line).replace(/\s*\[[0-9a-f]{6,}\]/g, '').trim();
      var cites = ids.filter(function(id){ return num[id]; }).map(function(id){
        var h = heads[num[id] - 1], url = safeUrl(h.link);
        return url ? '<a class="cite" href="' + esc(url) + '" target="_blank" rel="noopener" title="' + esc(h.title)
          + '" aria-label="Source ' + num[id] + ': ' + esc(h.title) + '">' + num[id] + '</a>' : '';
      }).join('');
      return '<li>' + esc(text) + (cites ? '<span class="cites">' + cites + '</span>' : '') + '</li>';
    }).join('') + '</ol>';
  }

  function renderCalendar(b){
    var events = (b.calendar && b.calendar.events) || [];
    if (!events.length){
      $('ml-calendar').innerHTML = '<p class="empty">No major US releases on the calendar for this brief.</p>';
      return;
    }
    var n = now(), html = '', day = null;
    events.forEach(function(e){
      if (e.date !== day){
        html += (day ? '</ul>' : '') + '<p class="day">' + esc(dayLong(e.date)) + '</p><ul class="evs">';
        day = e.date;
      }
      var past = e.time_utc && new Date(e.time_utc) < n;
      var imp = String(e.impact || '').toLowerCase();
      var impLabel = {high: 'High', medium: 'Medium', low: 'Low', holiday: 'Holiday'}[imp] || '';
      var nums = [['Consensus', e.consensus], ['Prior', e.prior], ['Actual', e.actual]].filter(function(x){ return x[1]; })
        .map(function(x){ return '<span>' + x[0] + ' <b>' + esc(x[1]) + '</b></span>'; }).join('');
      var note = releaseNote(e), what = '';
      if (note){
        what = '<details class="what"><summary>What is it?</summary><p>' + esc(note.text)
          + (note.href ? ' <a class="ext" href="' + esc(note.href) + '">More on ' + esc(note.label) + '</a>' : '') + '</p></details>';
      }
      html += '<li class="' + (past ? 'past' : '') + '"><div class="t">' + (e.time_utc ? esc(timeEt(e.time_utc)) : 'All day') + '</div><div>'
        + '<p class="n">' + (impLabel ? '<span class="imp ' + esc(imp) + '">' + impLabel + '</span>' : '') + esc(e.name) + '</p>'
        + (nums ? '<p class="nums">' + nums + '</p>' : '') + what + '</div></li>';
    });
    html += '</ul><p class="note">Times are Eastern. Impact is how much a release usually moves the market. Consensus is the forecast; prior is the last reading.</p>';
    $('ml-calendar').innerHTML = html;
  }

  var slugs = null;   // ticker -> report slug, once /data/reports.json has loaded
  function normTicker(t){ return String(t || '').toUpperCase().replace(/[\/\-]/g, '.'); }

  function renderEarnings(b, st){
    var E = b.earnings || {}, rows = [], seen = {};
    ['reported', 'today', 'tomorrow_pre'].forEach(function(k){
      (E[k] || []).forEach(function(r){
        var key = r.symbol + '|' + r.date;
        if (!r.symbol || seen[key]) return;
        seen[key] = true;
        rows.push(r);
      });
    });
    if (!rows.length){
      $('ml-earnings').innerHTML = '<p class="empty">No big-name earnings in this brief’s window.</p>';
      return;
    }
    var order = {pre: 0, post: 1};
    rows.sort(function(a, c){
      return String(a.date).localeCompare(String(c.date)) || ((order[a.timing] ?? 2) - (order[c.timing] ?? 2)) || String(a.symbol).localeCompare(String(c.symbol));
    });
    var html = '', group = null, linked = false;
    rows.forEach(function(r){
      var g = r.date + '|' + r.timing;
      if (g !== group){
        var when = r.timing === 'pre' ? 'before the open' : r.timing === 'post' ? 'after the close' : 'time not announced';
        html += (group ? '</ul>' : '') + '<p class="day">' + esc(dayLong(r.date)) + ' <span class="tag">&middot; ' + when + '</span></p><ul class="earn">';
        group = g;
      }
      var slug = slugs && slugs[normTicker(r.symbol)];
      linked = linked || !!slug;
      var tk = slug ? '<a class="tk" href="/reports/view.html?r=' + encodeURIComponent(slug) + '" title="Read our report on ' + esc(r.name || r.symbol) + '">' + esc(r.symbol) + '</a>'
        : '<span class="tk">' + esc(r.symbol) + '</span>';
      var status = r.reported ? '<span class="st done">Reported</span>' : st.kind === 'live' ? '<span class="st">Due</span>' : '';
      html += '<li>' + tk + '<span class="co">' + esc(r.name) + '</span>' + status + '</li>';
    });
    html += '</ul>' + (linked ? '<p class="note">A ticker in gold opens our report on the company.</p>' : '');
    $('ml-earnings').innerHTML = html;
  }

  var NAMES = {NQ: 'Nasdaq-100 futures', ES: 'S&P 500 futures'};
  var MONTHS = {F: 'January', G: 'February', H: 'March', J: 'April', K: 'May', M: 'June', N: 'July', Q: 'August', U: 'September', V: 'October', X: 'November', Z: 'December'};
  function contractName(code){   // ESZ26 -> December 2026 contract
    var m = /^[A-Z]{1,3}([FGHJKMNQUVXZ])(\d{2})$/.exec(String(code || ''));
    return m ? MONTHS[m[1]] + ' 20' + m[2] + ' contract' : '';
  }
  function px(v){ return v == null || isNaN(v) ? '—' : Number(v).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}); }
  function signed(v, digits){ return (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toLocaleString('en-US', {minimumFractionDigits: digits, maximumFractionDigits: digits}); }

  function renderLevels(b){
    var sets = (b.levels || []).slice().sort(function(a, c){ return (a.root === 'NQ' ? 0 : 1) - (c.root === 'NQ' ? 0 : 1); });
    if (!sets.length){
      $('ml-levels').innerHTML = '<p class="empty">No levels in this brief.</p>';
      return;
    }
    var td = b.meta.trading_day;
    $('ml-levels').innerHTML = sets.map(function(ls, i){
      var at = {};
      (ls.levels || []).forEach(function(l){ at[l.tag] = l.price; });
      var s = ls.stats || {}, last = ls.last_price, prior = s.prior_day;
      var chg = last != null && at.pdc != null ? last - at.pdc : null;
      var cls = chg == null ? 'flat' : chg > 0 ? 'up' : chg < 0 ? 'dn' : 'flat';
      var rows = function(head, list){
        var body = list.filter(function(x){ return x[1] != null; }).map(function(x){
          return '<tr><td>' + x[0] + '</td><td class="v">' + (x[2] || px(x[1])) + '</td></tr>';
        }).join('');
        return body ? '<tr><th colspan="2" scope="colgroup">' + esc(head) + '</th></tr>' + body : '';
      };
      var table = '';
      if (at.tdh != null || at.tdl != null) table += rows(weekday(td) + '’s regular session', [['High', at.tdh], ['Low', at.tdl], ['Close', at.tdc]]);
      if (prior) table += rows(weekday(prior) + '’s regular session', [['High', at.pdh], ['Low', at.pdl], ['Close', at.pdc]]);
      var onRange = s.overnight_range != null ? s.overnight_range : (at.onh != null && at.onl != null ? at.onh - at.onl : null);
      table += rows('Overnight, into ' + weekday(td) + '’s open', [['High', at.onh], ['Low', at.onl], ['Range, high to low', onRange, onRange == null ? '' : px(onRange) + ' pts']]);
      if (s.atr14 != null) table += rows('Typical day', [['Average daily range, last ' + (s.atr_days || 14) + ' sessions', s.atr14, px(s.atr14) + ' pts']]);
      var bars = ls.bars && ls.bars.length;
      return '<article class="fut"><h3>' + esc(NAMES[ls.root] || ls.root + ' futures') + '</h3>'
        + '<p class="sub">' + esc(ls.root) + (s.front_month ? ' &middot; ' + esc(contractName(s.front_month) || s.front_month) : '') + (ls.delayed ? ' &middot; delayed' : '') + '</p>'
        + '<p class="last"><span class="px">' + px(last) + '</span>'
        + (chg != null ? '<span class="chg ' + cls + '">' + signed(chg, 2) + ' (' + signed(chg / at.pdc * 100, 2) + '%)</span>' : '') + '</p>'
        + '<p class="asof">Last price' + (s.last_bar_utc ? ' at ' + esc(stampEt(s.last_bar_utc, etParts(new Date(s.last_bar_utc)).date !== etParts(now()).date)) : '')
        + (chg != null && prior ? '; change since ' + esc(weekday(prior)) + '’s 4 p.m. close' : '') + '.</p>'
        + (bars ? '<figure><canvas id="ml-chart-' + i + '" role="img" aria-label="' + esc(NAMES[ls.root] || ls.root) + ', 15-minute price candles with the levels in the table"></canvas>'
          + '<figcaption>15-minute candles: green closed higher, red lower. Shaded: the regular session. <span class="k"></span>last regular session’s high, low and close <span class="k on"></span>overnight high and low</figcaption></figure>' : '')
        + (table ? '<table class="lv"><tbody>' + table + '</tbody></table>' : '') + '</article>';
    }).join('')
      + '<p class="note">The regular session is 9:30 a.m. to 4 p.m. ET, while the stock exchanges are open; overnight is futures trading from 6 p.m. until the next morning’s open. '
      + 'Prices are in index points. The average daily range is how far the price has travelled from high to low on a typical day lately, overnight gaps included. '
      + 'Traders who want every level, from volume profile to VWAP, will find them on the <a href="' + FEED_PAGE + '">full brief</a>.</p>';
    sets.forEach(function(ls, i){ var cv = $('ml-chart-' + i); if (cv) charts.push({cv: cv, ls: ls}); });
    drawCharts();
  }

  /* ---------- the candle chart (canvas) ---------- */
  var charts = [];
  function cssVar(name){ return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function drawCharts(){ charts.forEach(function(c){ if (document.body.contains(c.cv)) drawChart(c.cv, c.ls); }); }

  function drawChart(cv, ls){
    var bars = ls.bars || [];
    var w = cv.clientWidth, h = cv.clientHeight, dpr = window.devicePixelRatio || 1;
    if (!w || !h || !bars.length) return;
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    var ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    var C = {gold: cssVar('--gold'), dim: cssVar('--dim'), dim2: cssVar('--dim2'), cream: cssVar('--cream'), line: cssVar('--line'),
             green: cssVar('--green'), red: cssVar('--red-neon'), card: cssVar('--card')};
    var font = '12px ' + (cssVar('--mono') || 'monospace');
    var at = {};
    (ls.levels || []).forEach(function(l){ at[l.tag] = l.price; });
    var marks = [['PDH', at.pdh, C.gold, true], ['PDL', at.pdl, C.gold, true], ['PDC', at.pdc, C.gold, true],
                 ['ONH', at.onh, C.dim, true], ['ONL', at.onl, C.dim, true], ['Last', ls.last_price, C.cream, false]]
      .filter(function(m){ return m[1] != null; });
    var label = function(m){ return m[0] + ' ' + px(m[1]).replace(/\.00$/, ''); };
    ctx.font = font;
    var padR = 12 + Math.max(60, Math.max.apply(null, marks.map(function(m){ return ctx.measureText(label(m)).width; })));
    var padL = 4, padT = 8, padB = 22, iw = w - padL - padR, ih = h - padT - padB;
    var lo = Infinity, hi = -Infinity;
    bars.forEach(function(b){ lo = Math.min(lo, b.l); hi = Math.max(hi, b.h); });
    marks.forEach(function(m){ lo = Math.min(lo, m[1]); hi = Math.max(hi, m[1]); });
    var pad = (hi - lo || 1) * 0.04; lo -= pad; hi += pad;
    var y = function(p){ return padT + (hi - p) / (hi - lo) * ih; };
    // bar slots; a closed-market gap (more than one candle apart) gets a two-slot break with a dotted line
    var pos = [0], breaks = [];
    for (var i = 1; i < bars.length; i++){
      var gap = (Date.parse(bars[i].t) - Date.parse(bars[i - 1].t)) / 60000 > 16;
      if (gap) breaks.push(pos[i - 1] + 1.5);
      pos.push(pos[i - 1] + (gap ? 3 : 1));
    }
    var slot = iw / (pos[pos.length - 1] + 1), cw = Math.max(1, Math.min(7, slot * 0.66));
    var x = function(k){ return padL + (k + 0.5) * slot; };
    // regular session shading, 09:30-16:00 ET
    ctx.fillStyle = 'rgba(217,168,92,.07)';
    var runStart = null, runDay = '', labels = [];
    bars.forEach(function(b, k){
      var p = etParts(new Date(b.t)), rth = p.mins >= 570 && p.mins < 960;
      if (rth && runStart === null){ runStart = k; runDay = p.date; }
      if (runStart !== null && (!rth || k === bars.length - 1)){
        var x0 = x(pos[runStart]) - slot / 2, x1 = x(pos[rth ? k : k - 1]) + slot / 2;
        ctx.fillRect(x0, padT, x1 - x0, ih);
        labels.push({x: x0, t: weekday(runDay).slice(0, 3) + ' 9:30'});
        runStart = null;
      }
    });
    ctx.strokeStyle = C.line; ctx.setLineDash([2, 3]); ctx.lineWidth = 1;
    breaks.forEach(function(bk){ var bx = padL + (bk + 0.5) * slot; ctx.beginPath(); ctx.moveTo(bx, padT); ctx.lineTo(bx, padT + ih); ctx.stroke(); });
    ctx.setLineDash([]);
    // candles
    bars.forEach(function(b, k){
      var col = b.c >= b.o ? C.green : C.red, cx = x(pos[k]);
      ctx.strokeStyle = col; ctx.fillStyle = col;
      ctx.beginPath(); ctx.moveTo(Math.round(cx) + 0.5, y(b.h)); ctx.lineTo(Math.round(cx) + 0.5, y(b.l)); ctx.stroke();
      var top = y(Math.max(b.o, b.c)), bot = y(Math.min(b.o, b.c));
      ctx.fillRect(cx - cw / 2, top, cw, Math.max(1, bot - top));
    });
    // level lines and their labels, pushed apart so none overlap
    ctx.font = font; ctx.textBaseline = 'middle';
    var placed = marks.map(function(m){ return {m: m, ly: y(m[1])}; }).sort(function(a, c){ return a.ly - c.ly; });
    for (var j = 1; j < placed.length; j++) if (placed[j].ly - placed[j - 1].ly < 14) placed[j].ly = placed[j - 1].ly + 14;
    var over = placed.length ? placed[placed.length - 1].ly - (padT + ih - 6) : 0;
    if (over > 0) placed.forEach(function(p){ p.ly -= over; });
    placed.forEach(function(p){
      var m = p.m, ly0 = y(m[1]);
      ctx.strokeStyle = m[2]; ctx.lineWidth = m[3] ? 1 : 1.5; ctx.setLineDash(m[3] ? [5, 3] : []);
      ctx.beginPath(); ctx.moveTo(padL, ly0); ctx.lineTo(padL + iw, ly0); ctx.stroke();
      ctx.setLineDash([]);
      if (Math.abs(p.ly - ly0) > 1){ ctx.beginPath(); ctx.moveTo(padL + iw, ly0); ctx.lineTo(padL + iw + 4, p.ly); ctx.stroke(); }
      ctx.fillStyle = m[2] === C.cream ? C.cream : m[2];
      ctx.fillText(label(m), padL + iw + 6, p.ly);
    });
    // time labels under the regular sessions
    ctx.fillStyle = C.dim2; ctx.textBaseline = 'alphabetic';
    var lastX = -1e9;
    labels.forEach(function(l){
      var tw = ctx.measureText(l.t).width;
      if (l.x - lastX >= tw + 12 && l.x + 2 + tw <= w){ ctx.fillText(l.t, l.x + 2, h - 6); lastX = l.x; }
    });
  }

  function renderHeadlines(heads){
    if (!heads.length){
      $('ml-headlines').innerHTML = '<li class="empty">No headlines in this brief.</li>';
      return;
    }
    var OUTLETS = {cnbc: 'CNBC', reuters: 'Reuters', marketwatch: 'MarketWatch', yahoo: 'Yahoo Finance', wsj: 'The Wall Street Journal', ft: 'Financial Times'};
    $('ml-headlines').innerHTML = heads.map(function(h, i){
      var title = String(h.title || ''), outlet = '';
      var m = /^(.*\S)\s+-\s+([^-]{2,60})$/.exec(title);   // Google News titles end " - Outlet"
      if (m && /^gnews/.test(h.source || '')){ title = m[1]; outlet = m[2].trim(); }
      if (!outlet) outlet = OUTLETS[String(h.source || '').split('_')[0]] || '';
      var url = safeUrl(h.link);
      if (!outlet && url) outlet = new URL(url).hostname.replace(/^www\./, '');
      var when = h.published_utc ? stampEt(h.published_utc, true) : '';
      return '<li id="hl-' + (i + 1) + '"><span class="no">' + (i + 1) + '</span><div>'
        + (url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(title) + '</a>' : esc(title))
        + '<span class="m">' + esc([outlet, when].filter(Boolean).join(' · ')) + '</span></div></li>';
    }).join('');
  }

  /* ---------- load, render, refresh ---------- */
  var brief = null, shownKind = null, refreshWarn = '';

  function render(){
    var b = brief, st = lineState(b), heads = (b.news && b.news.headlines) || [];
    shownKind = st.kind;
    charts = [];
    $('ml-body').hidden = false;   // before the blocks, so the charts can measure their width
    renderStatus(b, st, refreshWarn);
    renderNotice(b, st);
    renderMatters(b, st, heads);
    renderCalendar(b);
    renderEarnings(b, st);
    renderLevels(b);
    renderHeadlines(heads);
  }

  function renderFailed(){
    var lastSeen = null;
    try { lastSeen = JSON.parse(localStorage.getItem(LAST_KEY) || 'null'); } catch (e) {}
    $('ml-status').innerHTML = '<span class="chip none">Not posted yet</span>';
    $('ml-notice').innerHTML = '<div class="notice"><p class="nh">The line isn’t posted yet.</p>'
      + '<p>The brief posts on weekdays from about 6:25 a.m. ET and updates every 15 minutes until noon, with one more after the 4 p.m. close. This page checks again every five minutes.</p>'
      + (lastSeen && lastSeen.day && lastSeen.at ? '<p>The last line this browser loaded was the brief for <b>' + esc(dayLong(lastSeen.day)) + '</b>, updated ' + esc(stampEt(lastSeen.at, true)) + '.</p>' : '')
      + '<p>You can also read the brief as posted at <a href="' + FEED_PAGE + '">jonoki.github.io/ttg-brief</a>.</p></div>';
    $('ml-body').hidden = true;
  }

  function load(){
    lastTry = Date.now();
    return fetch(FEED, {cache: 'no-cache'})
      .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function(b){
        if (!b || !b.meta || !/^\d{4}-\d{2}-\d{2}$/.test(b.meta.trading_day || '') || isNaN(Date.parse(b.meta.generated_at_utc))) throw new Error('not a brief');
        brief = b; refreshWarn = '';
        try { localStorage.setItem(LAST_KEY, JSON.stringify({day: b.meta.trading_day, at: b.meta.generated_at_utc})); } catch (e) {}
        render();
      })
      .catch(function(){
        if (!brief) renderFailed();
        else { refreshWarn = 'Couldn’t refresh at ' + timeEt(now().toISOString()) + ' ET; showing the last update.'; renderStatus(brief, lineState(brief), refreshWarn); }
      });
  }

  var lastTry = 0;
  function tick(){
    var due = Date.now() - lastTry >= REFRESH_MS - 1000;
    if (document.visibilityState === 'visible' && due && (!brief || inSession())) { load(); return; }
    if (brief && lineState(brief).kind !== shownKind) render();   // the day rolled over while the tab sat open
  }

  fetch(REPORTS).then(function(r){ return r.ok ? r.json() : null; }).then(function(d){
    if (!d || !d.index) return;
    slugs = {};
    d.index.forEach(function(row){ slugs[normTicker(row[0])] = row[1]; });
    if (brief) renderEarnings(brief, lineState(brief));
  }).catch(function(){});

  load();
  setInterval(tick, 60 * 1000);
  document.addEventListener('visibilitychange', tick);
  var resizeTimer;
  window.addEventListener('resize', function(){ clearTimeout(resizeTimer); resizeTimer = setTimeout(drawCharts, 150); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(drawCharts);
})();
