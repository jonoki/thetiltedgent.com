/* As-of bar: appends "last close + drift since the note" to a report's static banner.
 *
 * Contract: the page carries
 *   <div class="tg-asof" data-ticker="TSLA" data-note-price="348.95"> ...static half... </div>
 * and this script adds the live half from ../data/quotes.json.
 *
 * Rules this file exists to enforce:
 *   - Fail closed. Any missing, malformed or unusable data leaves the static banner untouched.
 *   - Never show a number without the date it belongs to.
 *   - Fetch once on load. No polling, no animation, no ticking.
 *   - While the feed is flagged "placeholder", mark the figure SAMPLE so it cannot be
 *     mistaken for a real quote.
 */
(function () {
  'use strict';

  var MONTHS = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];

  /* Format YYYY-MM-DD by hand. new Date('2026-09-04') parses as UTC midnight and can
     render as the 3rd west of Greenwich, so never round-trip these through Date. */
  function formatDay(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
    if (!m) return null;
    var month = parseInt(m[2], 10);
    if (month < 1 || month > 12) return null;
    return parseInt(m[3], 10) + ' ' + MONTHS[month - 1] + ' ' + m[1];
  }

  function money(n) {
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  var bar = document.querySelector('.tg-asof[data-ticker]');
  if (!bar || typeof window.fetch !== 'function') return;

  var ticker = (bar.getAttribute('data-ticker') || '').toUpperCase();
  var notePrice = parseFloat(bar.getAttribute('data-note-price'));
  if (!ticker || !isFinite(notePrice) || notePrice <= 0) return;

  fetch('../data/quotes.json', { cache: 'no-cache' })
    .then(function (res) {
      if (!res.ok) throw new Error('quotes ' + res.status);
      return res.json();
    })
    .then(function (feed) {
      var quote = feed && feed.quotes && feed.quotes[ticker];
      if (!quote) return;

      var close = parseFloat(quote.close);
      var day = formatDay(quote.asof);
      if (!isFinite(close) || close <= 0 || !day) return;  // no number without its date

      var pct = (close - notePrice) / notePrice * 100;
      var rounded = Math.abs(pct) < 0.05 ? 0 : pct;
      var dir = rounded > 0 ? 'up' : (rounded < 0 ? 'dn' : 'flat');
      var label = rounded === 0
        ? 'unchanged since'
        : (rounded > 0 ? '▲ +' : '▼ −') + Math.abs(pct).toFixed(1) + '% since';

      var live = el('div', 'tg-asof-live');
      live.appendChild(el('span', 'lbl', 'LAST CLOSE'));
      live.appendChild(el('span', 'px', money(close)));
      live.appendChild(el('span', 'drift ' + dir, label));
      live.appendChild(el('span', 'when', day));
      if (feed.source === 'placeholder') {
        live.appendChild(el('span', 'sample', 'SAMPLE'));
      }
      bar.appendChild(live);
    })
    .catch(function () {
      /* Offline, 404, bad JSON, blocked: leave the static banner exactly as authored. */
    });
})();
