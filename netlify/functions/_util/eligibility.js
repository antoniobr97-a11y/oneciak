// WHO CAN APPLY. A fund, lab or festival whose own words shut out this
// project's country is removed: the report must never send a filmmaker to a
// call they cannot enter (La Résidence of Cannes, "for young non-French
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

module.exports = { countryOf, excludes, COUNTRIES };
