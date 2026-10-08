const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const signedToken = require('./_util/signedToken');
const { normalizeEmail } = require('./_util/userReports');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';
// The session token that keeps "My Reports" unlocked across visits, mirroring
// the report-link token's own lifetime — once logged in, no need to click
// another email link for 90 days.
const SESSION_TTL_MS = 90 * 24 * 60 * 60 * 1000;

// Exchanges a short-lived magic-link token (proves "this email received our
// link") for a long-lived session token (proves "this browser is logged in
// as this email") — the client stores the session token and never has to
// send the original magic-link token again.
exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };

  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'verify-login', limit: 30, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many requests. Please try again in a while.' }) };

    let body;
    try { body = JSON.parse(event.body || '{}'); } catch (e) { return { statusCode: 400, headers, body: JSON.stringify({ error: 'Invalid request body.' }) }; }

    const email = normalizeEmail(body.email);
    const loginToken = body.login_token;
    if (!email || !loginToken || !signedToken.verify(loginToken, email, 'REPORT_TOKEN_SECRET')) {
      return { statusCode: 403, headers, body: JSON.stringify({ error: 'This sign-in link is invalid or has expired. Please request a new one.' }) };
    }

    const sessionToken = signedToken.sign(email, SESSION_TTL_MS, 'REPORT_TOKEN_SECRET');
    return { statusCode: 200, headers, body: JSON.stringify({ ok: true, session_token: sessionToken }) };
  } catch (err) {
    console.error('verify-login:', err);
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'Something went wrong. Please try again.' }) };
  }
};
