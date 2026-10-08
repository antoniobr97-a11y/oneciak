const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { sendReportEmail } = require('./_util/email');
const signedToken = require('./_util/signedToken');
const { normalizeEmail } = require('./_util/userReports');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const LOGIN_LINK_TTL_MS = 20 * 60 * 1000; // long enough to find and click the email, short enough to limit replay risk

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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

    // Same look as the report email and the site: night header, warm paper body.
    const FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif";
    const html = '<!doctype html><html><head><meta name="color-scheme" content="light only"></head><body style="margin:0;padding:0;background:#f4f1ec;font-family:' + FONT + '">' +
      '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f1ec;padding:28px 0"><tr><td align="center">' +
      '<table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;border-radius:14px;overflow:hidden;background:#fbf9f6">' +
      '<tr><td bgcolor="#140d10" background="https://oneciak.com/email-header.jpg" style="background:#140d10 url(https://oneciak.com/email-header.jpg) center top / cover no-repeat;padding:24px 28px 26px">' +
        '<div style="font-size:15px;font-weight:700;color:#f2ede6">OneCiak</div>' +
        '<div style="margin-top:26px;font-size:24px;line-height:1.15;font-weight:700;color:#f2ede6;letter-spacing:-0.02em">Your sign-in link</div>' +
      '</td></tr>' +
      '<tr><td style="padding:24px 28px 28px;font-size:15px;line-height:1.6;color:#161616">' +
        '<p style="margin:0">Click below to see every full report you\'ve requested with this email address. This link expires in 20 minutes.</p>' +
        '<p style="margin:22px 0 0"><a href="' + esc(loginUrl) + '" style="display:inline-block;background:#140d10;color:#f2ede6;padding:13px 22px;border-radius:10px;text-decoration:none;font-weight:600;font-size:14px">View my reports</a></p>' +
        '<p style="margin:22px 0 0;color:#5c5852;font-size:13px">If you didn\'t request this, you can safely ignore this email.</p>' +
      '</td></tr></table></td></tr></table></body></html>';

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
    console.error('request-login:', err);
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'Something went wrong. Please try again.' }) };
  }
};
