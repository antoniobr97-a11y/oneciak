const { connectLambda, getStore } = require('@netlify/blobs');

const TEST_KEY = 'qk7-diag-3f0c9b';

// TEMPORARY diagnostic function — reads back the webhook-reports blob for
// a session_id, but ONLY for ids under the reserved "cs_test_diag_" test
// prefix, so it can never expose a real customer's report. Removed after use.
exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Not Allowed' };
  const body = JSON.parse(event.body || '{}');
  if (body.key !== TEST_KEY) return { statusCode: 403, body: 'Forbidden' };
  const sessionId = body.session_id || '';
  if (!sessionId.startsWith('cs_test_diag_')) return { statusCode: 400, body: 'session_id must use the reserved test prefix' };

  connectLambda(event);
  const store = getStore('webhook-reports');
  let record;
  try { record = await store.get(sessionId, { type: 'json' }); } catch (e) { record = null; }
  return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(record || { status: 'none' }) };
};
