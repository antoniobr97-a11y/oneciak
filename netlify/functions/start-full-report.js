const crypto = require('crypto');
const https = require('https');
const { connectLambda, getStore } = require('@netlify/blobs');
const { checkRateLimit, checkKeyLimit } = require('./_util/rateLimit');
const { sanitizeProject } = require('./_util/project');
const payloadSig = require('./_util/payloadSig');
const { sign: signReportToken } = require('./_util/reportToken');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';
const SITE_BASE = (process.env.URL || process.env.SITE_URL || 'https://oneciak.com').replace(/\/$/, '');

// On a Netlify deploy preview the generation must run on that same preview
// (process.env.URL always points at the live site, which runs the live
// code). Only the preview hostname pattern is trusted, never any Host header.
function functionsBase(event) {
  const host = event.headers && (event.headers.host || event.headers.Host);
  if (host && /^deploy-preview-\d+--oneciak\.netlify\.app$/.test(host)) return 'https://' + host;
  return SITE_BASE;
}
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Fires the generation background function and returns immediately — the
// Background Function itself acks with 202 right away, so this resolves
// almost instantly and never blocks the client on the actual generation.
function triggerBackground(payload, base) {
  return new Promise((resolve) => {
    try {
      const url = new URL(base + '/.netlify/functions/generate-report-background');
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
    const rl = await checkRateLimit(event, { name: process.env.CONTEXT === 'deploy-preview' ? 'start-full-report-preview' : 'start-full-report', limit: process.env.CONTEXT === 'deploy-preview' ? 12 : 3, windowMinutes: 180 }); // TEST BRANCH ONLY
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many full reports requested from this connection recently. Please try again later.' }) };

    let parsedBody;
    try { parsedBody = JSON.parse(event.body || '{}'); } catch (e) { return { statusCode: 400, headers, body: JSON.stringify({ error: 'Invalid request body.' }) }; }
    const project = sanitizeProject(parsedBody.project);
    if (!project) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'Missing project data.' }) };
    }
    const email = typeof parsedBody.email === 'string' ? parsedBody.email.trim() : '';
    if (!email || !EMAIL_RE.test(email) || email.length > 200) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'Please enter a valid email address.' }) };
    }
    // Per recipient as well as per IP: stops the site being used to send a
    // stream of reports to someone else's inbox from many connections.
    const perEmail = await checkKeyLimit(email.toLowerCase(), { name: 'full-report-email', limit: 5, windowMinutes: 24 * 60 });
    if (!perEmail) return { statusCode: 429, headers, body: JSON.stringify({ error: 'This email address has received the maximum number of reports for today. Please try again tomorrow.' }) };

    const id = 'free_' + crypto.randomBytes(16).toString('hex');
    const token = signReportToken(id);

    const store = getStore('webhook-reports');
    try { await store.setJSON(id, { status: 'processing', startedAt: Date.now() }); } catch (e) { /* fail open */ }

    await triggerBackground({ id, token, project, email, sig: payloadSig.sign(id, email, project) }, functionsBase(event));

    return { statusCode: 200, headers, body: JSON.stringify({ id, token }) };
  } catch (err) {
    console.error('start-full-report:', err);
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'Could not start the report. Please try again.' }) };
  }
};
