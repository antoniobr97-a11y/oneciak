const { connectLambda, getStore } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { verify: verifyReportToken } = require('./_util/reportToken');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';

// Lets the client recover a report the stripe-webhook already generated
// server-side, instead of paying for a brand-new AI generation on every
// retry or return visit. Gated by the same paid-session token as analyze.js.
exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };
  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'get-report', limit: 30, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many requests. Please try again in a while.' }) };

    const { session_id, token } = JSON.parse(event.body || '{}');
    if (!session_id || !verifyReportToken(token, session_id)) {
      return { statusCode: 403, headers, body: JSON.stringify({ ready: false }) };
    }

    const store = getStore('webhook-reports');
    let record;
    try { record = await store.get(session_id, { type: 'json' }); } catch (e) { record = null; }

    if (record && record.status === 'sent' && record.report) {
      return { statusCode: 200, headers, body: JSON.stringify({ ready: true, report: record.report, project: record.project }) };
    }
    return { statusCode: 200, headers, body: JSON.stringify({ ready: false }) };
  } catch (err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
  }
};
