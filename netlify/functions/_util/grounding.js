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

// List field -> the fields whose numbers must appear on the source page.
const LISTS = {
  financial_sources: ['amount', 'deadline'],
  market_comps: ['budget', 'result'],
  cautionary_comps: ['budget', 'what_went_wrong'],
  festival_calendar: ['deadline'],
  lab_and_market_opportunities: [],
  distribution_platforms: [],
  sales_agents: []
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

async function checkFigures(item, fields, pages) {
  const withNumbers = fields.filter(f => numbersIn(item[f]).length);
  if (!withNumbers.length) return;
  const html = await pages(item.source);
  withNumbers.forEach(f => {
    if (!html || !numbersOnPage(item[f], pageNumbers(html))) item[f] = null;
  });
}

// Mutates `report` in place. `searchUrlsByField` maps each field to the URLs
// returned by the search of the section that produced it.
async function groundReport(report, searchUrlsByField, today, fetcher) {
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
      const before = LISTS[field].filter(f => out[f] != null).length;
      checks.push(checkFigures(out, LISTS[field], pages).then(() => {
        stats.figuresCleared += before - LISTS[field].filter(f => out[f] != null).length;
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
      checks.push(checkFigures(ti, ['estimate'], pages));
    } else {
      ti.estimate = null;
      stats.dropped++;
    }
    delete ti.source_url;
  }

  await Promise.all(checks);
  return stats;
}

module.exports = { groundReport, normalizeUrl, isSourced, sourcedSet, numbersOnPage, pageNumbers, numbersIn, LISTS };
