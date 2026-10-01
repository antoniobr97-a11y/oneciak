const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { sendReportEmail } = require('./_util/email');
const signedToken = require('./_util/signedToken');
const { normalizeEmail } = require('./_util/userReports');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const LOGIN_LINK_TTL_MS = 20 * 60 * 1000; // long enough to find and click the email, short enough to limit replay risk

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// "My Reports" login: no password, no separate account secret to manage —
// just a time-limited link emailed to the address itself, reusing the same
// signed-token mechanism and the same email-sending path already used to
// deliver reports (no new infrastructure, no new env var to configure).
exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };

  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'request-login', limit: 5, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many requests. Please try again in a while.' }) };

    let body;
    try { body = JSON.parse(event.body || '{}'); } catch (e) { return { statusCode: 400, headers, body: JSON.stringify({ error: 'Invalid request body.' }) }; }

    const email = normalizeEmail(body.email);
    if (!email || !EMAIL_RE.test(email)) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'Please enter a valid email address.' }) };
    }

    const resendKey = (process.env.RESEND_API_KEY || '').trim();
    if (!resendKey) {
      console.error('request-login: missing RESEND_API_KEY');
      return { statusCode: 500, headers, body: JSON.stringify({ error: 'Server misconfigured.' }) };
    }

    const loginToken = signedToken.sign(email, LOGIN_LINK_TTL_MS, 'REPORT_TOKEN_SECRET');
    const siteBase = (process.env.URL || process.env.SITE_URL || 'https://oneciak.com').replace(/\/$/, '');
    const loginUrl = siteBase + '/?login_token=' + encodeURIComponent(loginToken) + '&login_email=' + encodeURIComponent(email);

    const html = '<div style="font-family:sans-serif;font-size:15px;color:#111;line-height:1.6;max-width:480px;margin:0 auto;padding:24px">' +
      '<p style="font-weight:700;font-size:17px">Your OneCiak sign-in link</p>' +
      '<p>Click below to see every full report you\'ve requested with this email address. This link expires in 20 minutes.</p>' +
      '<p style="margin:24px 0"><a href="' + esc(loginUrl) + '" style="background:#000;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:600">View my reports →</a></p>' +
      '<p style="color:#6f6f6f;font-size:13px">If you didn\'t request this, you can safely ignore this email.</p>' +
      '</div>';

    try {
      await sendReportEmail({
        apiKey: resendKey,
        from: process.env.REPORT_FROM_EMAIL || 'OneCiak <onboarding@resend.dev>',
        to: email,
        subject: 'Your OneCiak sign-in link',
        html
      });
    } catch (e) {
      console.error('request-login: failed to send login email', e.message);
      return { statusCode: 500, headers, body: JSON.stringify({ error: 'Could not send the sign-in link right now. Please try again later.' }) };
    }

    return { statusCode: 200, headers, body: JSON.stringify({ ok: true }) };
  } catch (err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
  }
};
