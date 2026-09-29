const { getStore } = require('@netlify/blobs');

// Anonymous, cookie-free funnel counters — no IP, no user id, no per-visitor
// identifier is ever stored, only aggregate counts per event name per day.
// That's what keeps this exempt from a GDPR cookie/consent banner.
const EVENTS = ['landing', 'form_start', 'analysis_completed', 'full_report_requested', 'full_report_delivered'];

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

// Best-effort, same read-then-write pattern as _util/stats.js's usage
// counter: swallows its own errors so a blob store hiccup never fails the
// caller's actual response, and accepts rare undercounting under concurrent
// hits as a fine tradeoff for an aggregate dashboard number.
async function recordEvent(name) {
  if (EVENTS.indexOf(name) === -1) return;
  try {
    const store = getStore('analytics');
    const totalKey = 'total:' + name;
    const dayKey = 'day:' + todayKey() + ':' + name;
    const [totalCur, dayCur] = await Promise.all([store.get(totalKey), store.get(dayKey)]);
    await Promise.all([
      store.set(totalKey, String((parseInt(totalCur, 10) || 0) + 1)),
      store.set(dayKey, String((parseInt(dayCur, 10) || 0) + 1))
    ]);
  } catch (e) { /* non-critical, ignore */ }
}

async function getSummary(days) {
  const store = getStore('analytics');
  const totals = {};
  for (const e of EVENTS) {
    totals[e] = parseInt(await store.get('total:' + e), 10) || 0;
  }
  const daily = [];
  const now = new Date();
  const n = days || 14;
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    const row = { date: key };
    for (const e of EVENTS) {
      row[e] = parseInt(await store.get('day:' + key + ':' + e), 10) || 0;
    }
    daily.push(row);
  }
  return { totals, daily, events: EVENTS };
}

module.exports = { recordEvent, getSummary, EVENTS };
