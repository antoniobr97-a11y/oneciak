const crypto = require('crypto');
const https = require('https');
const { connectLambda, getStore } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { sign: signReportToken } = require('./_util/reportToken');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';
const SITE_BASE = (process.env.URL || process.env.SITE_URL || 'https://oneciak.com').replace(/\/$/, '');
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Fires the generation background function and returns immediately — the
// Background Function itself acks with 202 right away, so this resolves
// almost instantly and never blocks the client on the actual generation.
function triggerBackground(payload) {
  return new Promise((resolve) => {
    try {
      const url = new URL(SITE_BASE + '/.netlify/functions/generate-report-background');
      const body = JSON.stringify(payload);
      const req = https.request({
        hostname: url.hostname, path: url.pathname, method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }
      }, (res) => { res.resume(); resolve(); });
      req.on('error', () => resolve()); // best-effort kick-off; get-report polling + PROCESSING_STALE_MS retry covers a dropped request
      req.write(body);
      req.end();
    } catch (e) { resolve(); }
  });
}

// The free-tier equivalent of create-checkout.js + the Stripe webhook: no
// payment involved, this just starts the same server-side generation
// directly. Full reports used to be gated behind a €29 Stripe charge, which
// also acted as a natural throttle — since that's gone, this is the only
// thing standing between the site and someone scripting unlimited paid-model
// generations, so the rate limit here is intentionally tighter than the old
// create-checkout limit.
exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };
  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'start-full-report', limit: 3, windowMinutes: 180 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many full reports requested from this connection recently. Please try again later.' }) };

    const { project, email } = JSON.parse(event.body || '{}');
    if (!project || !project.title || typeof project.title !== 'string') {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'Missing project data.' }) };
    }
    if (!email || typeof email !== 'string' || !EMAIL_RE.test(email) || email.length > 200) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'Please enter a valid email address.' }) };
    }

    const id = 'free_' + crypto.randomBytes(16).toString('hex');
    const token = signReportToken(id);

    const store = getStore('webhook-reports');
    try { await store.setJSON(id, { status: 'processing', startedAt: Date.now() }); } catch (e) { /* fail open */ }

    await triggerBackground({ id, token, project, email });

    return { statusCode: 200, headers, body: JSON.stringify({ id, token }) };
  } catch (err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
  }
};
