const https = require('https');
const http = require('http');

// Keeps a real-world claim in the report only when it is backed by a page
// the web search tool actually returned while that section was written.
// Two checks:
// 1. the item's `source_url` must be one of the URLs the search returned in
//    that same request (a URL the model remembers or invents never matches),
//    otherwise the item is dropped: its very existence is the claim (a
//    festival, fund, film or company the reader is told to rely on);
// 2. every number in its dates and figures (deadline, amount, budget...)
//    must appear on that page, fetched here; otherwise that field is
//    cleared and the reader is sent to the official page instead.

function normalizeUrl(u) {
  try {
    const x = new URL(String(u).trim());
    const host = x.hostname.toLowerCase().replace(/^www\./, '');
    const path = x.pathname.replace(/\/+$/, '');
    return host + path + (x.search || '');
  } catch (e) {
    return null;
  }
}

function sourcedSet(searchUrls) {
  const set = new Set();
  (searchUrls || []).forEach(u => { const n = normalizeUrl(u); if (n) set.add(n); });
  return set;
}

function isSourced(url, set) {
  const n = url && normalizeUrl(url);
  return !!(n && set.has(n));
}

// List field -> fields that are a single figure or date (cleared when its
// numbers are not on the source page) and prose fields (where only the
// sentences whose numbers are not on the page are removed).
const LISTS = {
  financial_sources: { figures: ['amount', 'deadline'], prose: ['eligibility'] },
  market_comps: { figures: ['budget'], prose: ['result'] },
  cautionary_comps: { figures: ['budget'], prose: ['what_went_wrong'] },
  festival_calendar: { figures: ['deadline'], prose: ['fit'] },
  lab_and_market_opportunities: { figures: [], prose: ['fit'] },
  distribution_platforms: { figures: [], prose: ['reason'] },
  sales_agents: { figures: [], prose: ['focus', 'why'] }
};

const FETCH_TIMEOUT_MS = 6000;
const MAX_PAGE_BYTES = 2 * 1024 * 1024;
const MAX_REDIRECTS = 3;

function fetchPage(url, redirects) {
  return new Promise((resolve) => {
    let lib;
    try { lib = new URL(url).protocol === 'http:' ? http : https; } catch (e) { return resolve(null); }
    const req = lib.get(url, { timeout: FETCH_TIMEOUT_MS, headers: { 'User-Agent': 'Mozilla/5.0 (compatible; OneCiak source check; +https://oneciak.com)', 'Accept': 'text/html,application/xhtml+xml,application/pdf;q=0.5,*/*;q=0.1' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location && (redirects || 0) < MAX_REDIRECTS) {
        res.resume();
        let next;
        try { next = new URL(res.headers.location, url).toString(); } catch (e) { return resolve(null); }
        return resolve(fetchPage(next, (redirects || 0) + 1));
      }
      if (res.statusCode !== 200) { res.resume(); return resolve(null); }
      const chunks = [];
      let size = 0;
      res.on('data', c => { size += c.length; if (size > MAX_PAGE_BYTES) { req.destroy(); } else chunks.push(c); });
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
      res.on('error', () => resolve(null));
    });
    req.on('timeout', () => { req.destroy(); resolve(null); });
    req.on('error', () => resolve(null));
  });
}

// Page text with tags removed and digit groups joined ("500,000", "500 000"
// and "500.000" all become "500000"), so figures can be looked up as written.
function pageNumbers(html) {
  const text = String(html)
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;|&#160;/g, ' ');
  return ' ' + text.replace(/(\d)[,.   ](?=\d{3}\b)/g, '$1') + ' ';
}

function numbersIn(value) {
  const s = String(value == null ? '' : value).replace(/(\d)[,.   ](?=\d{3}\b)/g, '$1');
  return (s.match(/\d+(?:\.\d+)?/g) || []);
}

function numbersOnPage(value, pageText) {
  const nums = numbersIn(value);
  return nums.every(n => new RegExp('(^|[^0-9])' + n.replace('.', '\\.') + '([^0-9]|$)').test(pageText));
}

// Drops the sentences of `text` that state a number the page does not
// contain; sentences without numbers are kept as they are.
// Sentences end at . ! ? followed by whitespace, so "$2.6 million" or
// "U.S." never split a sentence (a fact-check on 2026-10-22 caught the old
// splitter turning "$2.6 million" into "6 million").
function sentencesOf(text) {
  return text.split(/(?<=[.!?])\s+/).filter(Boolean);
}

function keepSupportedSentences(text, pageText) {
  if (typeof text !== 'string' || !numbersIn(text).length) return text;
  const kept = sentencesOf(text).filter(s => !numbersIn(s).length || (pageText && numbersOnPage(s, pageText)));
  return kept.join(' ').trim() || null;
}

// In free text, only the figures that read as facts are checked: amounts
// of money and calendar dates. Rules of thumb ("a 10% contingency", "30
// days") are advice, not claims about the world.
const MONTH = '(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)';
const FACTUAL = new RegExp(
  '(?:[$€£₦¥]|\\b(?:usd|eur|gbp|ngn|cad|aud|n)\\s?)\\d[\\d.,]*(?:\\s?(?:k|m|bn|million|billion|thousand))?' +
  '|\\d[\\d.,]*\\s?(?:k|m|bn|million|billion|thousand)?\\s?(?:euros?|dollars?|pounds?|naira)\\b' +
  '|\\b\\d{1,2}(?:st|nd|rd|th)?\\s+' + MONTH + '\\b(?:,?\\s+20\\d\\d)?|\\b' + MONTH + '\\.?\\s+\\d{1,2}\\b(?:,?\\s+20\\d\\d)?', 'gi');

function factualNumbers(text) {
  return (String(text).match(FACTUAL) || []).flatMap(numbersIn);
}

function keepFactualSentences(text, pageText) {
  if (typeof text !== 'string' || !factualNumbers(text).length) return text;
  const kept = sentencesOf(text).filter(s => {
    const nums = factualNumbers(s);
    return !nums.length || (pageText && nums.every(n => numbersOnPage(n, pageText)));
  });
  return kept.join(' ').trim() || null;
}

// Sites that copy festival and fund listings from elsewhere and are often
// out of date. They can show that something exists, but a deadline or
// amount taken only from them is not shown.
const AGGREGATORS = ['festagent.com', 'fundsforngos.org', 'vitrina.ai', 'scriptmatch.ai', 'asianfilmfestivals.com', 'indieshortsmag.com', 'mauxa.com', 'filmfreeway.com', 'festhome.com', 'withoutabox.com', 'shortfilmdepot.com', 'clickforfestivals.com', 'movibeta.com'];
function isAggregator(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return AGGREGATORS.some(d => host === d || host.endsWith('.' + d));
  } catch (e) { return false; }
}

// A deadline that has already passed is marked closed instead of being
// presented as a target. Only unambiguous written dates are parsed.
const MONTHS_EN = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
const MONTHS_IT = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];
function monthIndex(word) {
  const w = word.toLowerCase().slice(0, 3);
  let i = MONTHS_EN.indexOf(w);
  if (i === -1) i = MONTHS_IT.indexOf(w);
  return i;
}
function lastDateIn(text) {
  const s = String(text || '');
  const found = [];
  let m;
  const dmy = /\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?,?\s+(20\d\d)\b/gi;
  while ((m = dmy.exec(s))) { const mi = monthIndex(m[2]); if (mi >= 0) found.push(Date.UTC(+m[3], mi, +m[1])); }
  const mdy = /\b([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)\b/gi;
  while ((m = mdy.exec(s))) { const mi = monthIndex(m[1]); if (mi >= 0) found.push(Date.UTC(+m[3], mi, +m[2])); }
  const iso = /\b(20\d\d)-(\d{2})-(\d{2})\b/g;
  while ((m = iso.exec(s))) found.push(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  const dots = /\b(\d{1,2})[./](\d{1,2})[./](20\d\d)\b/g;
  while ((m = dots.exec(s))) found.push(Date.UTC(+m[3], +m[2] - 1, +m[1]));
  return found.length ? Math.max.apply(null, found) : null;
}
function markIfClosed(item, field, today) {
  const last = lastDateIn(item[field]);
  if (last !== null && last < Date.parse(today + 'T00:00:00Z')) { item.closed = true; item[field] = 'Closed (' + item[field] + ')'; }
}

// Model citation markup that sometimes leaks into JSON strings.
function stripMarkup(value) {
  if (typeof value === 'string') return value.replace(/<\/?cite\b[^>]*>/gi, '').replace(/\(?cite index="[^"]*">?/gi, '').replace(/\s{2,}/g, ' ').trim();
  if (Array.isArray(value)) return value.map(stripMarkup);
  if (value && typeof value === 'object') { Object.keys(value).forEach(k => { value[k] = stripMarkup(value[k]); }); return value; }
  return value;
}

async function checkFigures(item, spec, pages) {
  const figures = spec.figures.filter(f => numbersIn(item[f]).length);
  const prose = spec.prose.filter(f => numbersIn(item[f]).length);
  if (!figures.length && !prose.length) return;
  const html = await pages(item.source);
  const text = html ? pageNumbers(html) : null;
  const secondHand = isAggregator(item.source);
  figures.forEach(f => { if (!text || secondHand || !numbersOnPage(item[f], text)) item[f] = null; });
  prose.forEach(f => { item[f] = keepSupportedSentences(item[f], secondHand ? null : text); });
}

// Free-text fields of the sections that did research: any sentence stating
// an amount or a date that none of the pages fetched for the report contain
// is removed. Arrays lose the entries that end up empty.
function checkProse(value, pageText) {
  if (typeof value === 'string') return keepFactualSentences(value, pageText);
  if (Array.isArray(value)) return value.map(v => checkProse(v, pageText)).filter(v => v != null && v !== '');
  if (value && typeof value === 'object') { Object.keys(value).forEach(k => { value[k] = checkProse(value[k], pageText); }); return value; }
  return value;
}

// Mutates `report` in place. `searchUrlsByField` maps each field to the URLs
// returned by the search of the section that produced it.
async function groundReport(report, searchUrlsByField, today, fetcher) {
  stripMarkup(report);
  const cache = new Map();
  const pages = (url) => {
    if (!cache.has(url)) cache.set(url, (fetcher || fetchPage)(url));
    return cache.get(url);
  };
  const stats = { kept: 0, dropped: 0, figuresCleared: 0 };
  const checks = [];

  Object.keys(LISTS).forEach(field => {
    if (!(field in report)) return;
    const set = sourcedSet(searchUrlsByField[field]);
    const items = Array.isArray(report[field]) ? report[field] : [];
    const kept = [];
    items.forEach(item => {
      if (!item || typeof item !== 'object') return;
      if (!isSourced(item.source_url, set)) { stats.dropped++; return; }
      const out = Object.assign({}, item, { source: item.source_url, url: item.source_url, checked: today });
      delete out.source_url;
      kept.push(out);
      const figs = LISTS[field].figures;
      const before = figs.filter(f => out[f] != null).length;
      checks.push(checkFigures(out, LISTS[field], pages).then(() => {
        stats.figuresCleared += before - figs.filter(f => out[f] != null).length;
      }));
    });
    report[field] = kept;
    stats.kept += kept.length;
  });

  // The tax incentive is a single object: without an official source (or if
  // its figures are not on that page) the rate goes, and the note still
  // points the reader to the administering authority.
  const ti = report.tax_incentive;
  if (ti && typeof ti === 'object') {
    const set = sourcedSet(searchUrlsByField.tax_incentive);
    if (isSourced(ti.source_url, set)) {
      ti.source = ti.source_url;
      ti.checked = today;
      stats.kept++;
      checks.push(checkFigures(ti, { figures: ['estimate'], prose: ['note'] }, pages));
    } else {
      ti.estimate = null;
      stats.dropped++;
    }
    delete ti.source_url;
  }

  await Promise.all(checks);

  ['financial_sources', 'festival_calendar'].forEach(field => {
    (report[field] || []).forEach(item => markIfClosed(item, 'deadline', today));
  });

  const firstHand = Array.from(cache.keys()).filter(u => !isAggregator(u));
  const fetched = await Promise.all(firstHand.map(u => cache.get(u)));
  const allPages = fetched.filter(Boolean).map(pageNumbers).join(' ');
  Object.keys(report).forEach(field => {
    if (field in LISTS || field === 'tax_incentive') return;
    if (!(searchUrlsByField[field] && searchUrlsByField[field].length)) return;
    report[field] = checkProse(report[field], allPages || null);
  });
  return stats;
}

// For the preview's single comparable film and festival: kept only with a
// searched source, and only the sentences whose numbers are on that page.
async function groundOne(obj, set, prose, today, fetcher) {
  if (!obj || typeof obj !== 'object' || !isSourced(obj.source_url, set)) return null;
  stripMarkup(obj);
  const out = Object.assign({}, obj, { source: obj.source_url, url: obj.source_url, checked: today });
  delete out.source_url;
  await checkFigures(out, { figures: [], prose }, fetcher || fetchPage);
  return out;
}

module.exports = { groundReport, groundOne, keepSupportedSentences, keepFactualSentences, factualNumbers, lastDateIn, isAggregator, stripMarkup, normalizeUrl, isSourced, sourcedSet, numbersOnPage, pageNumbers, numbersIn, LISTS };
