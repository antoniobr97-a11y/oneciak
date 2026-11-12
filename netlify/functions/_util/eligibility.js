// WHO CAN APPLY. A fund, lab or festival whose own words shut out this
// project (its country, format, running time or the director's number of
// features) is removed: the report must never send a filmmaker to a call
// they cannot enter (La Résidence of Cannes, "for young non-French
// filmmakers", was offered to a French project on 2026-11-10).
// Only exclusions written in the text are acted on; when the text does not
// say, the item stays and the reader is pointed to the official page.

// name and adjective of each country, lower case; aliases map typed input.
const COUNTRIES = {
  italy: ['italy', 'italian'], france: ['france', 'french'], germany: ['germany', 'german'],
  spain: ['spain', 'spanish'], portugal: ['portugal', 'portuguese'], 'united kingdom': ['united kingdom', 'british'],
  ireland: ['ireland', 'irish'], 'united states': ['united states', 'american'], canada: ['canada', 'canadian'],
  mexico: ['mexico', 'mexican'], brazil: ['brazil', 'brazilian'], argentina: ['argentina', 'argentine'],
  chile: ['chile', 'chilean'], colombia: ['colombia', 'colombian'], belgium: ['belgium', 'belgian'],
  netherlands: ['netherlands', 'dutch'], switzerland: ['switzerland', 'swiss'], austria: ['austria', 'austrian'],
  denmark: ['denmark', 'danish'], sweden: ['sweden', 'swedish'], norway: ['norway', 'norwegian'],
  finland: ['finland', 'finnish'], iceland: ['iceland', 'icelandic'], poland: ['poland', 'polish'],
  'czech republic': ['czech republic', 'czech'], hungary: ['hungary', 'hungarian'], romania: ['romania', 'romanian'],
  greece: ['greece', 'greek'], croatia: ['croatia', 'croatian'], serbia: ['serbia', 'serbian'],
  slovenia: ['slovenia', 'slovenian'], turkey: ['turkey', 'turkish'], israel: ['israel', 'israeli'],
  egypt: ['egypt', 'egyptian'], morocco: ['morocco', 'moroccan'], tunisia: ['tunisia', 'tunisian'],
  'south africa': ['south africa', 'south african'], nigeria: ['nigeria', 'nigerian'], kenya: ['kenya', 'kenyan'],
  india: ['india', 'indian'], china: ['china', 'chinese'], japan: ['japan', 'japanese'],
  'south korea': ['south korea', 'korean'], australia: ['australia', 'australian'], 'new zealand': ['new zealand'],
  luxembourg: ['luxembourg'], estonia: ['estonia', 'estonian'], latvia: ['latvia', 'latvian'], lithuania: ['lithuania', 'lithuanian'],
};
const ALIASES = { usa: 'united states', us: 'united states', 'u.s.': 'united states', 'u.s.a.': 'united states', america: 'united states',
  'united states of america': 'united states', uk: 'united kingdom', 'u.k.': 'united kingdom', 'great britain': 'united kingdom',
  britain: 'united kingdom', england: 'united kingdom', scotland: 'united kingdom', wales: 'united kingdom',
  italia: 'italy', 'españa': 'spain', espana: 'spain', deutschland: 'germany', korea: 'south korea', czechia: 'czech republic',
  holland: 'netherlands', 'the netherlands': 'netherlands' };

function countryOf(typed) {
  const t = String(typed || '').toLowerCase().replace(/\s+/g, ' ').trim();
  if (!t || t === 'not specified') return null;
  // "Italy / France" or "Italy, co-production with France": the first one is the production country.
  const first = t.split(/[\/,;(]| and | with /)[0].trim();
  const k = ALIASES[first] || first;
  return COUNTRIES[k] ? k : null;
}

function words(list) { return '(?:' + list.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')'; }
const PEOPLE = '(?:nationals?|citizens?|residents?|filmmakers?|directors?|producers?|applicants?|candidates?|projects?|companies|productions?|films?)';
const NOT_ELIGIBLE = '(?:are not eligible|is not eligible|are excluded|is excluded|cannot apply|can not apply|may not apply|are not accepted|is not accepted)';
const RESTRICT = new RegExp('(?:only|exclusively|restricted to|limited to|reserved for|must be|must have|must hold|must reside|must live|must be based|must be registered|must be established)[^.;]{0,120}', 'g');
const WHO = /citizen|national|resident|resid|based|registered|established|domicil|passport|filmmaker|director|producer|compan|applicant|candidate/;
const NOT_WHO = /premiere|release|language|subtitl|spoken|shot|filmed|shooting|produced|co-?produc|set in|story/;
const OPEN_WIDE = /\b(?:any country|all countries|worldwide|international|regardless of|any nationality|all nationalities|or other|abroad|europe|european|eu\b|member states?|eea|latin america|africa|asia|nordic|balkan|middle east|arab|francophone|commonwealth)/;

// True when the text shuts out the given country (a key of COUNTRIES).
function excludes(text, country) {
  if (!text || !COUNTRIES[country]) return false;
  const t = ' ' + String(text).toLowerCase().replace(/[‐-―−]/g, '-').replace(/\s+/g, ' ') + ' ';
  const own = COUNTRIES[country];
  const W = words(own);
  if (new RegExp('\\bnon-? ?' + W + '\\b').test(t)) return true;
  if (new RegExp('\\b(?:except(?:ing)?|excluding|other than|outside(?: of)?|not (?:be )?(?:from|in|based in|resident in|residing in|residents? (?:or citizens? )?of|citizens? (?:or residents? )?of)) (?:the )?' + W + '\\b').test(t)) return true;
  if (new RegExp('\\b' + W + ' ' + PEOPLE + '(?: (?:and|or) ' + PEOPLE + ')? ' + NOT_ELIGIBLE).test(t)) return true;
  // "must be residents of Italy", "open only to Spanish directors": a named
  // country list that leaves this one out. Unknown or wide areas are not judged.
  let m;
  RESTRICT.lastIndex = 0;
  while ((m = RESTRICT.exec(t))) {
    const span = m[0];
    // Only rules about who the applicant is: a premiere, language or
    // shooting rule names a country without shutting anyone out.
    if (/\bnot\b/.test(span) || OPEN_WIDE.test(span) || NOT_WHO.test(span) || !WHO.test(span)) continue;
    const named = Object.keys(COUNTRIES).filter(k => new RegExp('\\b' + words(COUNTRIES[k]) + '\\b').test(span));
    if (named.length && !named.includes(country)) return true;
  }
  return false;
}

// Format, running time and feature experience. Only a sentence that limits
// what may enter counts ("is for first and second features", "must be at
// least 60 minutes long"); a rule about a premiere, a release or money does
// not, and nothing with "not" in it is guessed at.
const LIMIT = /(?:\bonly\b|exclusively|restricted to|limited to|reserved for|dedicated to|open to|(?:is|are) for|must be|must have|must run|must last|must exceed|must not exceed)[^.;]{0,120}/g;
const NOT_WORK = /premiere|screen|release|shown|online|broadcast|distribut|cost|budget|financ|fund|euro|eur\b|usd|\$|€|£|percent|%|language|subtitl|deliver/;
const FEATURE = /\b(?:feature|full-length|long-?metra|lungometragg)/;
const SHORT = /\b(?:short|shorts|cortometragg|court-?m[ée]trage)/;
const ORDINAL = /\b(first|second|third|debut)(?:[- ]time)?\b((?:\s*(?:,|and|or|&|\/)\s*(?:the\s+)?(?:first|second|third|debut))*)\s+(?:(?:feature|full-length|fiction|narrative)[- ]?)*(?:features?|films?|works?|directors?|filmmakers?)\b/g;
const ORD = { first: 1, debut: 1, second: 2, third: 3 };

function facts(p) {
  p = p || {};
  const format = /short/i.test(p.format || '') ? 'short' : /feature/i.test(p.format || '') ? 'feature' : null;
  const min = parseInt(p.runtime, 10);
  const runtime = min > 0 && min < 1000 ? min : null;
  const e = String(p.experience || '');
  // "First film": nothing made yet, not even a short.
  const noWork = /^first film/i.test(e);
  // which feature this project is, for the director: debut, 2nd or 3rd, 4th on
  const nth = format !== 'feature' ? null
    : /first film|short films|tv|advertising/i.test(e) ? [1]
    : /1.2 feature/i.test(e) ? [2, 3]
    : /3\+/.test(e) ? [4] : null;
  return { format, runtime, nth, noWork };
}

// The running time a clause asks for: { min, max } in minutes, or null.
function minutesRule(span) {
  const n = '(\\d{1,3})\\s?(?:min\\b|mins\\b|minutes)';
  let m;
  if ((m = span.match(new RegExp('(?:not exceed|not be longer than|not last more than|up to|under|less than|no longer than|no more than|maximum(?: of)?|max\\.?|shorter than|within) ' + n)))) return { max: +m[1] - (/under|less than|shorter than/.test(m[0]) ? 1 : 0) };
  if ((m = span.match(new RegExp(n + ' or (?:less|shorter|under)')))) return { max: +m[1] };
  if ((m = span.match(new RegExp('(?:exceed|over|longer than|more than) ' + n)))) return { min: +m[1] + 1 };
  if ((m = span.match(new RegExp('(?:at least|minimum(?: of)?|min\\.) ' + n)))) return { min: +m[1] };
  if ((m = span.match(new RegExp(n + ' or (?:more|longer|over)')))) return { min: +m[1] };
  return null;
}

// True when the text shuts out this project by format, running time or the
// director's experience. Unknown project facts are never judged.
function excludesWork(text, project) {
  if (!text) return false;
  const f = facts(project);
  if (!f.format && !f.runtime && !f.nth && !f.noWork) return false;
  const t = ' ' + String(text).toLowerCase().replace(/[‐-―−]/g, '-').replace(/\s+/g, ' ') + ' ';
  if (f.nth && f.nth[0] === 1 && /\b(?:first|debut) (?:feature|full-length)[a-z -]{0,20} (?:are|is) not (?:eligible|accepted)/.test(t)) return true;
  let m;
  LIMIT.lastIndex = 0;
  while ((m = LIMIT.exec(t))) {
    // one rule at a time: "is for first and second features and programs
    // world premieres" is a limit plus a remark; the remark is left out.
    const parts = m[0].split(/, (?:but|so|while|whereas) |,? (?:and|but) (?!(?:the )?(?:first|second|third|debut)\b)/);
    let span = parts[0];
    for (let i = 1; i < parts.length && !NOT_WORK.test(parts[i]); i++) span += ' and ' + parts[i];
    LIMIT.lastIndex = m.index + 1;
    if (/\bnot\b/.test(span.replace(/^must not exceed/, '')) || NOT_WORK.test(span)) continue;
    // "Short films must be under 40 minutes": the clause's subject says which format it is about.
    const subject = t.slice(0, m.index).split(/[.;,]/).pop();
    const aboutShort = SHORT.test(subject) && !FEATURE.test(subject);
    const aboutFeature = FEATURE.test(subject) && !SHORT.test(subject);
    if ((aboutShort && f.format === 'feature') || (aboutFeature && f.format === 'short')) continue;
    const isFeature = FEATURE.test(span), isShort = SHORT.test(span);
    const pastWork = /must have (?:directed|made|written|produced|completed)/.test(span);
    if (!pastWork && f.format === 'short' && isFeature && !isShort) return true;
    if (!pastWork && f.format === 'feature' && isShort && !isFeature) return true;
    const mins = f.runtime && minutesRule(span);
    if (mins && ((mins.min && f.runtime < mins.min) || (mins.max && f.runtime > mins.max))) return true;
    // A rule that asks for work already made ("must have directed at least
    // one short film", "the filmmaker's previous short film(s) ... must have
    // been selected") shuts out a first film.
    if (f.noWork && (/must have (?:directed|made|completed|produced) (?:at least )?(?:one|a|an|two|three|1|2|3)\b[a-z -]{0,30}\b(?:films?|shorts?|features?|works?)/.test(span) ||
      (/^must (?:have|be)/.test(span) && /\bprevious (?:short )?(?:films?|works?|shorts?)|\bprevious\b[a-z ()-]{0,30}\b(?:films?|works?)/.test(subject)))) return true;
    if (f.nth && /must have (?:directed|made|written|produced) (?:at least )?(?:one|a|an|two|three|1|2|3)\b[a-z -]{0,30}\b(?:feature|full-length)/.test(span) && f.nth[0] === 1) return true;
    if (f.nth) {
      const allowed = [];
      let o;
      ORDINAL.lastIndex = 0;
      while ((o = ORDINAL.exec(span))) (o[0].match(/first|second|third|debut/g) || []).forEach(w => allowed.push(ORD[w]));
      if (allowed.length && (isFeature || /director|filmmaker/.test(span)) && !f.nth.some(n => allowed.includes(n))) return true;
    }
  }
  return false;
}

module.exports = { countryOf, excludes, excludesWork };
