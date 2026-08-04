const { connectLambda, getStore } = require('@netlify/blobs');

const TEST_KEY = 'qk7-diag-3f0c9b';

// TEMPORARY diagnostic function — lists recent webhook-reports blob entries
// (status/error only, not full report content) to debug a real payment
// without needing manual log access. Removed after use.
exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Not Allowed' };
  const body = JSON.parse(event.body || '{}');
  if (body.key !== TEST_KEY) return { statusCode: 403, body: 'Forbidden' };

  connectLambda(event);
  const store = getStore('webhook-reports');
  const { blobs } = await store.list();

  const results = await Promise.all(blobs.map(async (b) => {
    let record;
    try { record = await store.get(b.key, { type: 'json' }); } catch (e) { record = { error: 'could not read' }; }
    return {
      session_id: b.key,
      status: record && record.status,
      error: record && record.error,
      startedAt: record && record.startedAt,
      sentAt: record && record.sentAt,
      at: record && record.at,
      hasReport: !!(record && record.report),
      projectTitle: record && record.project && record.project.title
    };
  }));

  results.sort((a, b) => (b.startedAt || b.sentAt || b.at || 0) - (a.startedAt || a.sentAt || a.at || 0));

  return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(results) };
};
