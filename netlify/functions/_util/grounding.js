const { countryOf, excludes, excludesWork } = require('./eligibility');
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
  market_comps: { figures: ['budget', 'year'], prose: ['result', 'match'] },
  cautionary_comps: { figures: ['budget', 'year'], prose: ['what_went_wrong', 'match'] },
  festival_calendar: { figures: ['deadline'], prose: ['fit'] },
  lab_and_market_opportunities: { figures: ['deadline'], prose: ['fit'] },
  distribution_platforms: { figures: [], prose: ['reason'] },
  sales_agents: { figures: [], prose: ['focus', 'why'] },
  producers: { figures: ['year'], prose: ['why'] }
};

// Lists whose items may carry a `rule_quote` (checked by checkQuote).
const QUOTED = ['financial_sources', 'festival_calendar', 'lab_and_market_opportunities'];

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
const AGGREGATORS = ['festagent.com', 'fundsforngos.org', 'vitrina.ai', 'scriptmatch.ai', 'asianfilmfestivals.com', 'indieshortsmag.com', 'mauxa.com', 'filmfreeway.com', 'festhome.com', 'withoutabox.com', 'shortfilmdepot.com', 'clickforfestivals.com', 'movibeta.com', 'caligari.com.ar', 'filmcane.com'];
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
function datesIn(text) {
  const s = String(text || '');
  const found = [];
  let m;
  const dmy = /\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?,?\s+(20\d\d)\b/gi;
  while ((m = dmy.exec(s))) { const mi = monthIndex(m[2]); if (mi >= 0) found.push({ t: Date.UTC(+m[3], mi, +m[1]), at: m.index }); }
  const mdy = /\b([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)\b/gi;
  while ((m = mdy.exec(s))) { const mi = monthIndex(m[1]); if (mi >= 0) found.push({ t: Date.UTC(+m[3], mi, +m[2]), at: m.index }); }
  const iso = /\b(20\d\d)-(\d{2})-(\d{2})\b/g;
  while ((m = iso.exec(s))) found.push({ t: Date.UTC(+m[1], +m[2] - 1, +m[3]), at: m.index });
  const dots = /\b(\d{1,2})[./](\d{1,2})[./](20\d\d)\b/g;
  while ((m = dots.exec(s))) found.push({ t: Date.UTC(+m[3], +m[2] - 1, +m[1]), at: m.index });
  return found;
}
// The date that closes a call. When the text says "open until", "deadline",
// "by" or the like, that date counts, not the later dates of the programme
// itself ("open until 30 September 2026 for the session of March to July
// 2027" closed in September 2026).
const CLOSE_WORDS = /\b(until|till|deadline|due|by|before|closes?|closing|ends?|entro|scadenza|jusqu'au|bis)\b[^.;]{0,25}$/i;
function closingDateIn(text) {
  const s = String(text || '');
  const found = datesIn(s);
  if (!found.length) return null;
  const marked = found.filter(d => CLOSE_WORDS.test(s.slice(Math.max(0, d.at - 30), d.at)));
  return Math.max.apply(null, (marked.length ? marked : found).map(d => d.t));
}
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
function dayMonthYear(t) { const d = new Date(t); return d.getUTCDate() + ' ' + MONTH_NAMES[d.getUTCMonth()] + ' ' + d.getUTCFullYear(); }
function markIfClosed(item, field, today) {
  const own = item[field] != null && String(item[field]).trim() !== '';
  // No deadline of its own: the rule quoted from the official page may still
  // date the call ("was open from 15 January to 13 April 2026").
  const last = closingDateIn(own ? item[field] : item.rule_quote);
  if (last === null || last >= Date.parse(today + 'T00:00:00Z')) return;
  item.closed = true;
  if (!own) { item[field] = 'Closed (' + dayMonthYear(last) + ')'; return; }
  // The model sometimes already wrote "closed": say it once.
  const v = String(item[field]).replace(/\b(?:(?:applications|submissions|entries|registrations|the call|call)\s+)?(?:(?:is|are|was|were|now|already|has|have)\s+)*(?:been\s+)?closed\b/gi, ' ')
    .replace(/\(\s*[;,:]?\s*\)/g, ' ').replace(/\(\s*[;,:]\s*/g, '(').replace(/\s*[;,:]\s*\)/g, ')')
    .replace(/\s*[;,]\s*[;,]\s*/g, '; ').replace(/\s+([;,])/g, '$1').replace(/\s{2,}/g, ' ')
    .replace(/^[\s,;:.-]+|[\s,;:-]+$/g, '').trim();
  item[field] = /^\(.*\)$/.test(v) ? 'Closed ' + v : /[()]/.test(v) ? 'Closed: ' + v : 'Closed (' + v + ')';
}

// A rule quoted to the reader (premiere requirement, who can apply) is
// shown only if it is on the source page word for word: a paraphrase of
// an eligibility rule is how a first-time filmmaker loses a premiere or
// applies to a fund they cannot get (fact-check of 2026-10-22). Case,
// spacing, curly quotes, dashes and HTML entities are ignored, nothing else.
const ENTITIES = { amp: '&', quot: '"', apos: "'", lt: '<', gt: '>', nbsp: ' ', rsquo: "'", lsquo: "'", rdquo: '"', ldquo: '"', ndash: '-', mdash: '-', hellip: '...', laquo: '"', raquo: '"' };
function plainText(s) {
  return String(s == null ? '' : s)
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x([0-9a-f]+);/gi, (m, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (m, d) => String.fromCodePoint(+d))
    .replace(/&([a-z]+);/gi, (m, n) => ENTITIES[n.toLowerCase()] || m);
}
function quoteKey(s) {
  return plainText(s)
    .replace(/[‘’‚′`]/g, "'")
    .replace(/[“”„«»″]/g, '"')
    .replace(/[‐-―−]/g, '-')
    .replace(/…/g, '...')
    .replace(/\s+/g, ' ')
    .toLowerCase()
    .trim();
}
function cleanQuote(q) {
  return quoteKey(q).replace(/^["']+|["']+$/g, '').replace(/^(\.\.\.)\s*|\s*(\.\.\.)$/g, '').replace(/[.;:,]$/, '').trim();
}
function quoteOnPage(quote, html) {
  if (typeof quote !== 'string' || !html) return false;
  const q = cleanQuote(quote);
  if (q.length < 15 || q.length > 400) return false;
  return quoteKey(html).includes(q);
}
// The core of a company name or film title, as it would appear in running
// text: legal suffixes, quotes and punctuation do not count.
const LEGAL = /\b(s\.?r\.?l\.?s?|s\.?p\.?a\.?|s\.?a\.?s?|ltd\.?|limited|llc|inc\.?|gmbh|ug|ag|ab|oy|as|aps|a\/s|bv|b\.v\.|nv|sarl|sl|s\.l\.|co\.?|corp\.?|pty|plc|kft|sp\. z o\.o\.|s\.r\.o\.)$/i;
function nameCore(s) {
  let n = quoteKey(s).replace(/[,;]+\s*$/, '');
  for (let i = 0; i < 2; i++) n = n.replace(LEGAL, '').replace(/[\s,]+$/, '');
  return n.replace(/["'.,:;!?()\[\]]/g, ' ').replace(/\s+/g, ' ').trim();
}
function textCore(html) {
  return ' ' + quoteKey(html).replace(/["'.,:;!?()\[\]]/g, ' ').replace(/\s+/g, ' ') + ' ';
}
function namesBoth(item, html) {
  const name = nameCore(item.name), film = nameCore(item.film);
  // A film "title" that is just the company name proves nothing.
  if (!html || name.length < 3 || film.length < 2 || name.includes(film) || film.includes(name)) return false;
  const text = textCore(html);
  return text.includes(' ' + name + ' ') && text.includes(' ' + film + ' ');
}
// A sales agent or platform is a name the reader will look up: it stays
// only if its own source page names it (pages that cannot be read are not
// judged). This removes descriptions passed off as names.
async function checkListed(item, pages) {
  const html = item.source ? await pages(item.source) : null;
  if (!html) return;
  const name = nameCore(String(item.name || '').split('(')[0]);
  if (name.length < 2 || !textCore(html).includes(' ' + name + ' ')) item.unconfirmed = true;
}
async function checkNamed(item, pages) {
  if (!namesBoth(item, item.source ? await pages(item.source) : null)) item.unconfirmed = true;
}
// The page the model cited often names the film but not the company (a
// review, a festival entry). Another page from the same searches that names
// both is the same proof; it becomes the source.
async function findNamingPage(item, urls, pages) {
  for (const url of urls) {
    if (url === item.source) continue;
    if (namesBoth(item, await pages(url))) {
      item.source = item.url = url;
      delete item.unconfirmed;
      return;
    }
  }
}

// How a producer takes projects (a form, an agent only, no unsolicited
// scripts) decides whether the reader writes at all. It is shown only as
// the company's own sentence, word for word, from a page found in the
// searches on the company's own site: its address holds a distinctive word
// of the name (vivofilm.it for Vivo Film). A festival's "submit your film"
// line, or a news page, is not the company's rule; nor is how its
// distribution arm takes finished films.
const GENERIC = /^(?:the|and|film|films|filmes|pictures|picture|productions?|produzioni|production|prod|studios?|media|entertainment|cinema|group|company|house|creative|arts?|works|international|italia|italy)$/;
function ownSite(url, name) {
  let host;
  try { host = new URL(url).hostname.toLowerCase().replace(/^www\./, ''); } catch (e) { return false; }
  const site = host.replace(/[^a-z0-9]/g, '');
  return nameCore(name).split(' ').some(w => w.length >= 3 && !GENERIC.test(w) && site.includes(w.replace(/[^a-z0-9]/g, '')));
}
async function checkApproach(item, pages, set) {
  const q = item.approach_quote, url = item.approach_url || item.source;
  item.approach_quote = item.approach_url = null;
  if (!q || !url || !isSourced(url, set) || !ownSite(url, item.name)) return;
  // A distribution page's "send us your finished short" is not how the
  // company takes a project to produce; a sentence cut at "contact:" has
  // lost the address it points to.
  if (/distribu|catalog/i.test(q + ' ' + url) || /:\s*$/.test(String(q).trim())) return;
  if (!quoteOnPage(q, await pages(url))) return;
  item.approach_quote = String(q).trim().replace(/^["“]+|["”]+$/g, '');
  item.approach_url = url;
}

async function checkQuote(item, pages) {
  if (item.rule_quote == null) return;
  const html = isAggregator(item.source) ? null : await pages(item.source);
  if (!quoteOnPage(item.rule_quote, html)) item.rule_quote = null;
  else item.rule_quote = String(item.rule_quote).trim().replace(/^["“]+|["”]+$/g, '');
}

// A comparable film is kept only if its own page says it is the project's
// genre (and a short, for a short): a famous film that only shares a theme
// is not a comparable. Pages that cannot be read are not judged.
const GENRE_WORDS = { drama: /\bdrama/, thriller: /\bthriller/, comedy: /\bcomed/, horror: /\bhorror/,
  'sci-fi': /\bsci-fi\b|\bscience[- ]fiction/, action: /\baction\b/, romance: /\bromanc|\bromantic/, animation: /\banimat/ };
async function checkComp(item, pages, project) {
  const wanted = String(project.genre || '').toLowerCase().split('/').map(g => GENRE_WORDS[g.trim()]).filter(Boolean);
  const short = /short/i.test(project.format || '');
  if (!wanted.length && !short) return;
  const html = isAggregator(item.source) ? null : await pages(item.source);
  if (!html) return;
  const text = quoteKey(html);
  if ((wanted.length && !wanted.some(re => re.test(text))) || (short && !/\bshort/.test(text))) item.offTopic = true;
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
function applicantOf(item) {
  if (!item.rule_quote) return null;
  const a = String(item.applicant || '').trim().toLowerCase();
  if (a === 'individual' || a === 'company' || a === 'either') return a[0].toUpperCase() + a.slice(1);
  return null;
}

async function groundReport(report, searchUrlsByField, today, fetcher, project) {
  stripMarkup(report);
  const cache = new Map();
  const pages = (url) => {
    if (!cache.has(url)) cache.set(url, (fetcher || fetchPage)(url));
    return cache.get(url);
  };
  const stats = { kept: 0, dropped: 0, figuresCleared: 0 };
  const checks = [];
  const quoted = new Map();

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
      if (QUOTED.includes(field)) { quoted.set(out, out.rule_quote); checks.push(checkQuote(out, pages)); }
      else delete out.rule_quote;
      if (field === 'sales_agents' || field === 'distribution_platforms') checks.push(checkListed(out, pages));
      if (project && (field === 'market_comps' || field === 'cautionary_comps')) checks.push(checkComp(out, pages, project));
      if (field === 'producers') checks.push(checkNamed(out, pages));
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

  ['sales_agents', 'distribution_platforms'].forEach(field => {
    if (!Array.isArray(report[field])) return;
    const before = report[field].length;
    report[field] = report[field].filter(a => !a.unconfirmed);
    stats.dropped += before - report[field].length;
    stats.kept -= before - report[field].length;
  });
  ['market_comps', 'cautionary_comps'].forEach(field => {
    if (!Array.isArray(report[field])) return;
    const before = report[field].length;
    report[field] = report[field].filter(c => !c.offTopic);
    stats.offTopic = (stats.offTopic || 0) + before - report[field].length;
    stats.kept -= before - report[field].length;
  });

  // A producer stays only if a page from its searches names it and the film it produced.
  if (Array.isArray(report.producers)) {
    const urls = Array.from(new Set((searchUrlsByField.producers || []).filter(u => /^https?:\/\//.test(u)))).slice(0, 25);
    const unconfirmed = report.producers.filter(p => p.unconfirmed);
    if (unconfirmed.length) await Promise.all(urls.map(pages)); // fetched once, in parallel
    for (const p of unconfirmed) await findNamingPage(p, urls, pages);
    const before = report.producers.length;
    report.producers = report.producers.filter(p => !p.unconfirmed);
    stats.dropped += before - report.producers.length;
    stats.kept -= before - report.producers.length;
    const set = sourcedSet(searchUrlsByField.producers);
    await Promise.all(report.producers.map(p => checkApproach(p, pages, set)));
  }

  // A fund, festival or lab whose words shut out this project (its country,
  // format, running time or the director's number of features) goes
  // (eligibility.js). The model's own quote counts even if it failed the
  // word-for-word check: removing a call never puts a false claim on screen.
  const country = countryOf(project && project.country);
  ['financial_sources', 'festival_calendar', 'lab_and_market_opportunities'].forEach(field => {
    if (!Array.isArray(report[field])) return;
    const before = report[field].length;
    report[field] = report[field].filter(item => ![quoted.get(item), item.rule_quote, item.eligibility, item.fit].some(t => (country && excludes(t, country)) || excludesWork(t, project)));
    stats.notEligible = (stats.notEligible || 0) + before - report[field].length;
    stats.kept -= before - report[field].length;
  });

  // "Who can apply" is shown only next to the source's own sentence
  // (rule_quote, checked word for word above); without it, it goes.
  (report.financial_sources || []).forEach(item => { item.applicant = applicantOf(item); });

  ['financial_sources', 'festival_calendar', 'lab_and_market_opportunities'].forEach(field => {
    (report[field] || []).forEach(item => markIfClosed(item, 'deadline', today));
  });

  const firstHand = Array.from(cache.keys()).filter(u => !isAggregator(u));
  const fetched = await Promise.all(firstHand.map(u => cache.get(u)));
  const allPages = fetched.filter(Boolean).map(pageNumbers).join(' ');
  // The filmmaker's own figures (budget, running time) are facts of the
  // project, not claims about the world: a sentence stating them stays.
  const own = project ? pageNumbers(Object.keys(project).map(k => project[k]).join(' . ')) : '';
  Object.keys(report).forEach(field => {
    if (field in LISTS || field === 'tax_incentive') return;
    if (!(searchUrlsByField[field] && searchUrlsByField[field].length)) return;
    report[field] = checkProse(report[field], (allPages + ' ' + own).trim() || null);
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
  const pages = fetcher || fetchPage;
  await checkFigures(out, { figures: [], prose }, pages);
  await checkQuote(out, pages);
  return out;
}

module.exports = { groundReport, groundOne, sourcedSet };
