const { getStore } = require('@netlify/blobs');

// Caps how many past reports are kept per email, so the blob can't grow
// unbounded for a very frequent user — oldest entries drop off first.
const MAX_REPORTS_PER_EMAIL = 200;

function normalizeEmail(email) {
  return String(email || '').trim().toLowerCase();
}

// Same read-modify-write pattern as benchmarkStats.js: one small JSON blob
// per email, keyed by the normalized address, holding just enough to link
// back to each report — never the report content itself.
async function recordReportForEmail(email, entry) {
  const normalized = normalizeEmail(email);
  if (!normalized || !entry || !entry.viewUrl) return;
  const store = getStore('user-reports');
  let existing = [];
  try {
    const rec = await store.get(normalized, { type: 'json' });
    existing = (rec && Array.isArray(rec.reports)) ? rec.reports : [];
  } catch (e) { /* no record yet */ }
  const updated = existing.concat([{
    title: entry.title || 'Untitled project',
    viewUrl: entry.viewUrl,
    createdAt: entry.createdAt || Date.now()
  }]).slice(-MAX_REPORTS_PER_EMAIL);
  try { await store.setJSON(normalized, { reports: updated }); } catch (e) { /* never block report delivery over this */ }
}

async function listReportsForEmail(email) {
  const normalized = normalizeEmail(email);
  if (!normalized) return [];
  const store = getStore('user-reports');
  try {
    const rec = await store.get(normalized, { type: 'json' });
    const reports = (rec && Array.isArray(rec.reports)) ? rec.reports : [];
    return reports.slice().sort(function (a, b) { return b.createdAt - a.createdAt; });
  } catch (e) {
    return [];
  }
}

module.exports = { recordReportForEmail, listReportsForEmail, normalizeEmail };
