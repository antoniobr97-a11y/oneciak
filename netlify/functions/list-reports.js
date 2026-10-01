const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const signedToken = require('./_util/signedToken');
const { normalizeEmail, listReportsForEmail } = require('./_util/userReports');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';

exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };

  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'list-reports', limit: 60, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many requests. Please try again in a while.' }) };

    let body;
    try { body = JSON.parse(event.body || '{}'); } catch (e) { return { statusCode: 400, headers, body: JSON.stringify({ error: 'Invalid request body.' }) }; }

    const email = normalizeEmail(body.email);
    const sessionToken = body.session_token;
    if (!email || !sessionToken || !signedToken.verify(sessionToken, email, 'REPORT_TOKEN_SECRET')) {
      return { statusCode: 403, headers, body: JSON.stringify({ error: 'Your session has expired. Please sign in again.' }) };
    }

    const reports = await listReportsForEmail(email);
    return { statusCode: 200, headers, body: JSON.stringify({ ok: true, reports: reports }) };
  } catch (err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
  }
};
