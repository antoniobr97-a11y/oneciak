// Every project field that reaches a prompt or an email goes through here.
// Limits are generous for real use (the form enforces the same maxlength)
// and stop anyone posting megabytes of text to run up the AI bill or put
// arbitrary copy into an email subject.
const LIMITS = {
  title: 120,
  logline: 600,
  genre: 80,
  format: 60,
  budget: 40,
  audience: 80,
  distrib: 80,
  country: 80,
  language: 60,
  experience: 80,
  stage: 60,
  producer: 60,
  runtime: 4,
  shown: 60,
  extra: 1500
};

function clean(value, max) {
  return String(value == null ? '' : value)
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '')
    .replace(/\s*[\r\n]+\s*/g, ' ')
    .trim()
    .slice(0, max);
}

// Country and language as names: "italy" -> "Italy", "english/ arabic" ->
// "English / Arabic" (a lowercase country in the report header, Antonio,
// 26 Nov 2026). Words typed with capitals stay as typed. Same in index.html.
function properName(s) {
  if (s === 'Not specified') return s;                       // the form's own default, compared elsewhere
  return String(s).replace(/\s*\/\s*/g, ' / ').replace(/\s*,\s*/g, ', ').replace(/\s+/g, ' ').trim()
    .replace(/[^\s\/,()-]+/g, function (w, i) {
      if (w !== w.toLowerCase()) return w;                     // typed with capitals: kept (USA, McAllen)
      if (i > 0 && /^(of|and|the|da|di|del|della|de|e|y)$/.test(w)) return w;
      var m = /^([dl]')(.+)$/.exec(w);                          // d'ivoire -> d'Ivoire
      if (m) return m[1] + m[2].charAt(0).toUpperCase() + m[2].slice(1);
      return w.charAt(0).toUpperCase() + w.slice(1);
    });
}

// Returns a fresh object holding only the known fields, or null when the
// project has no title.
function sanitizeProject(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const p = {};
  Object.keys(LIMITS).forEach(function (k) { p[k] = clean(raw[k], LIMITS[k]); });
  if (!p.title) return null;
  ['country', 'language'].forEach(function (k) { p[k] = properName(p[k]); });
  ['country', 'language', 'experience', 'stage', 'producer', 'runtime', 'shown'].forEach(function (k) { if (!p[k]) p[k] = 'Not specified'; });
  return p;
}

module.exports = { sanitizeProject, properName };
