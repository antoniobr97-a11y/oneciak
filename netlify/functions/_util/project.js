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
  extra: 1500
};

function clean(value, max) {
  return String(value == null ? '' : value)
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '')
    .replace(/\s*[\r\n]+\s*/g, ' ')
    .trim()
    .slice(0, max);
}

// Returns a fresh object holding only the known fields, or null when the
// project has no title.
function sanitizeProject(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const p = {};
  Object.keys(LIMITS).forEach(function (k) { p[k] = clean(raw[k], LIMITS[k]); });
  if (!p.title) return null;
  ['country', 'language', 'experience'].forEach(function (k) { if (!p[k]) p[k] = 'Not specified'; });
  return p;
}

module.exports = { sanitizeProject, LIMITS };
