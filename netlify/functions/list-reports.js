const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const signedToken = require('./_util/signedToken');
const { normalizeEmail, listReportsForEmail } = require('./_util/userReports');
const { sign: signReportToken } = require('./_util/reportToken');

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

    const stored = await listReportsForEmail(email);
    const siteBase = (process.env.URL || process.env.SITE_URL || 'https://oneciak.com').replace(/\/$/, '');
    // Mint a fresh token for every report on every visit instead of reusing
    // whatever was stored — this is what makes a logged-in visit to "My
    // Reports" never go stale, regardless of how old the report itself is.
    const reports = stored.map(function (r) {
      var viewUrl = r.sessionId
        ? siteBase + '/?report_id=' + encodeURIComponent(r.sessionId) + '&report_token=' + encodeURIComponent(signReportToken(r.sessionId))
        : r.viewUrl; // best-effort fallback for any legacy entry recorded before this field existed
      return { title: r.title, viewUrl: viewUrl, createdAt: r.createdAt };
    }).filter(function (r) { return !!r.viewUrl; });

    return { statusCode: 200, headers, body: JSON.stringify({ ok: true, reports: reports }) };
  } catch (err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
  }
};
