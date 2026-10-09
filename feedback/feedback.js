/* The Tilted Gent — the feedback form (feedback/index.html): report a bug, request a report, or report an error in one.
   It posts to Formspree (https://formspree.io/f/<FORM_ID>), which emails each submission to the site's inbox.
   Free plan: 50 submissions a month; 20 posts a minute per form, after which Formspree answers 429.
   Query parameters (the site's entry points): ?type=bug|request|error, ?page=<path> (bug; the footer's Feedback link,
   filled by assets/site.js), ?r=<slug> (error; the report viewer's "Spotted an error?" link, e.g. aapl or etf/voo). */
(function(){
  'use strict';
  // The Formspree form ID: the part after /f/ in the form's endpoint. While it is empty the form stays disabled,
  // the page says "Feedback opens soon", and nothing is fetched or sent.
  var FORM_ID = '';

  var form = document.getElementById('fb-form');
  if(!form) return;
  var on = /^[A-Za-z0-9]+$/.test(FORM_ID);
  var endpoint = 'https://formspree.io/f/' + FORM_ID;
  var $ = function(id){ return document.getElementById(id); };
  var all = $('fb-fields'), send = $('fb-send'), errBox = $('fb-error'), done = $('fb-done');
  var radios = form.querySelectorAll('input[name="type"]');
  var groups = form.querySelectorAll('fieldset.grp');
  var details = $('fb-details');

  // what the shared "details" box asks for, per type
  var COPY = {
    '':      ['Details', 'Pick one of the three above first.', 'Add a line or two here.'],
    bug:     ['What happened?', 'What you did, what you expected, and what you got instead.', 'Tell us what happened.'],
    request: ['Tell us a bit more', 'Where it trades, or what you’d like to know about it.', 'Add a line or two about it.'],
    error:   ['What’s wrong?', 'The number or fact, and where in the report you saw it.', 'Tell us what’s wrong.']
  };

  function type(){
    for(var i = 0; i < radios.length; i++) if(radios[i].checked) return radios[i].value;
    return '';
  }

  // show the chosen type's fields; a hidden group is disabled, so the browser neither checks nor sends it
  function show(t){
    Array.prototype.forEach.call(groups, function(g){
      var mine = g.getAttribute('data-for') === t;
      g.hidden = !mine;
      g.disabled = !mine;
    });
    var c = COPY[t] || COPY[''];
    $('fb-details-label').textContent = c[0];
    $('fb-details-hint').textContent = c[1];
    details.setAttribute('data-msg', c[2]);
    if(t) clearErr($('fb-type-err'), null);
  }

  Array.prototype.forEach.call(radios, function(r){
    r.addEventListener('change', function(){ show(type()); });
  });

  // ---- pre-fills from the query string ----
  var q = new URLSearchParams(location.search);
  var qt = (q.get('type') || '').toLowerCase();
  Array.prototype.forEach.call(radios, function(r){ r.checked = r.value === qt; });
  show(type());

  var page = (q.get('page') || '').trim();
  if(page) $('fb-page').value = page.slice(0, 300);
  $('fb-browser').value = (navigator.userAgent || '').slice(0, 400);

  // ?r=aapl (a stock report) or ?r=etf/voo (a family report), the same shapes reports/view.html accepts
  var slug = (q.get('r') || '').toLowerCase();
  var sm = /^(?:(etf|crypto|fixed|indicators)\/)?([a-z0-9]{1,9})$/.exec(slug);
  var ticker = '';   // what the subject line names
  var prefill = '';  // the report box's pre-filled text; editing it away from this drops the slug
  if(sm){
    ticker = sm[2].toUpperCase();
    prefill = ticker;
    $('fb-report').value = prefill;
    $('fb-slug').value = slug;
    // a stock report: show the company's name from the manifest (data/reports.json, then its sector file).
    // Only when the form is on: while it is off the page makes no network calls at all.
    if(on && !sm[1]) lookup(sm[2]);
  }
  $('fb-report').addEventListener('input', function(){
    $('fb-slug').value = this.value.trim() === prefill && sm ? slug : '';
  });

  function lookup(s){
    fetch('/data/reports.json').then(function(r){ return r.ok ? r.json() : null; }).then(function(d){
      var row = d && d.index && d.index.filter(function(x){ return x[1] === s; })[0];
      if(!row) return null;
      ticker = row[0];
      setReport(ticker);
      return fetch('/data/reports/' + encodeURIComponent(row[2]) + '.json').then(function(r){ return r.ok ? r.json() : null; })
        .then(function(sh){
          var rep = sh && sh.reports && sh.reports.filter(function(x){ return x.slug === s; })[0];
          // a few global names carry their page title's tail ("Meituan (MEITUAN) — Stock Analysis"): drop it
          var name = rep && rep.name ? String(rep.name).replace(/\s*\([^)]*\)\s*[—–-]\s*Stock Analysis\s*$/, '').trim() : '';
          if(name) setReport(name + ' (' + ticker + ')');
        });
    }).catch(function(){});   // the ticker stays; nothing else depends on the name
  }
  function setReport(text){
    var box = $('fb-report');
    if(box.value !== prefill) return;   // the reader has typed over it
    prefill = text;
    box.value = text;
  }

  // ---- validation ----
  function setErr(el, msg){
    var box = $(el.id + '-err');
    el.setAttribute('aria-invalid', 'true');
    if(box){ box.textContent = msg; box.hidden = false; }
  }
  function clearErr(box, el){
    if(el) el.removeAttribute('aria-invalid');
    if(box){ box.textContent = ''; box.hidden = true; }
  }
  // the fields the browser would send: not disabled, not inside a disabled group
  function live(el){ return !el.disabled && !el.closest('fieldset[disabled]'); }

  function problem(el){
    var v = el.value.trim();
    if(el.required && !v) return el.getAttribute('data-msg') || 'Fill this in.';
    if(el.maxLength > 0 && el.value.length > el.maxLength) return 'Keep it under ' + el.maxLength.toLocaleString('en-US') + ' characters.';
    if(el.type === 'email' && v && (el.validity.typeMismatch || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v))) return 'That doesn’t look like an email address.';
    return '';
  }

  function validate(){
    var first = null;
    if(!type()){
      var tb = $('fb-type-err');
      tb.textContent = 'Pick one of the three.';
      tb.hidden = false;
      first = radios[0];
    }
    Array.prototype.forEach.call(form.querySelectorAll('input[type=text],input[type=email],textarea'), function(el){
      if(!live(el)) return;
      var msg = problem(el);
      if(msg){ setErr(el, msg); if(!first) first = el; }
      else clearErr($(el.id + '-err'), el);
    });
    if(first) first.focus();
    return !first;
  }
  // a fixed field clears its message as soon as it is right
  form.addEventListener('input', function(e){
    var el = e.target;
    if(el.getAttribute && el.getAttribute('aria-invalid') === 'true' && !problem(el)) clearErr($(el.id + '-err'), el);
  });

  function subject(){
    var t = type();
    if(t === 'error'){
      var named = $('fb-slug').value ? ticker : $('fb-report').value.trim();
      return 'Error report: ' + named.slice(0, 80);
    }
    if(t === 'request') return 'Report request: ' + $('fb-company').value.trim().slice(0, 80);
    var p = $('fb-page').value.trim();
    return p ? 'Bug: ' + p.slice(0, 100) : 'Bug report';
  }

  // ---- sending ----
  function showErrors(lead, list){
    errBox.innerHTML = '';
    var p = document.createElement('p');
    p.textContent = lead;
    errBox.appendChild(p);
    if(list && list.length){
      var ul = document.createElement('ul');
      list.forEach(function(m){ var li = document.createElement('li'); li.textContent = m; ul.appendChild(li); });
      errBox.appendChild(ul);
    }
    errBox.hidden = false;
  }
  function busy(b){
    send.disabled = b;
    send.textContent = b ? 'Sending…' : 'Send';
    form.setAttribute('aria-busy', b ? 'true' : 'false');
  }

  form.addEventListener('submit', function(e){
    e.preventDefault();
    if(!on || send.disabled) return;
    errBox.hidden = true;
    if(!validate()) return;
    $('fb-subject').value = subject();
    busy(true);
    fetch(endpoint, {method: 'POST', body: new FormData(form), headers: {'Accept': 'application/json'}})
      .then(function(r){
        if(r.ok){ finish(); return; }
        if(r.status === 429){
          showErrors('Too many messages through this form just now. Wait a minute, then send it again.');
          return;
        }
        return r.json().catch(function(){ return null; }).then(function(d){
          var msgs = d && Array.isArray(d.errors) ? d.errors.map(function(x){ return x && x.message; }).filter(Boolean) : [];
          showErrors(msgs.length ? 'That didn’t go through:' : 'That didn’t go through (error ' + r.status + '). Try again in a minute.', msgs);
        });
      })
      .catch(function(){
        showErrors('That didn’t go through: we couldn’t reach the form. Check your connection and try again.');
      })
      .then(function(){ if(!done.hidden) return; busy(false); });
  });

  function finish(){
    form.hidden = true;
    done.hidden = false;
    $('fb-done-h').focus();
  }
  $('fb-again').addEventListener('click', function(){
    form.reset();
    Array.prototype.forEach.call(radios, function(r){ r.checked = false; });
    show('');
    busy(false);
    errBox.hidden = true;
    done.hidden = true;
    form.hidden = false;
    $('fb-browser').value = (navigator.userAgent || '').slice(0, 400);
    radios[0].focus();
  });

  // ---- on or off ----
  if(on){
    all.disabled = false;
  } else {
    $('fb-off').hidden = false;
    send.textContent = 'Opens soon';
  }
})();
