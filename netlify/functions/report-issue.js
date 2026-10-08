const { connectLambda, getStore } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { verify: verifyReportToken } = require('./_util/reportToken');
const { sendReportEmail } = require('./_util/email');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';
const MAX_MESSAGE_LEN = 2000;

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Lets a filmmaker flag something wrong in their own report (a dead link, a
// stale date, anything else) straight from the page — this is the "if we get
// it wrong, we fix it fast" promise that a generic AI chatbot can't make,
// since there's no one on the other end to tell. Gated by the same
// long-lived report token as get-report.js, so only someone who actually
// holds a link to that report can flag it.
exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };

  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'report-issue', limit: 10, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many requests. Please try again in a while.' }) };

    let body;
    try { body = JSON.parse(event.body || '{}'); } catch (e) { return { statusCode: 400, headers, body: JSON.stringify({ error: 'Invalid request body.' }) }; }

    const { session_id, token, category, message } = body;
    if (!session_id || !verifyReportToken(token, session_id)) {
      return { statusCode: 403, headers, body: JSON.stringify({ error: 'Invalid or expired report link.' }) };
    }
    const cleanCategory = String(category || '').slice(0, 100);
    const trimmedMessage = String(message || '').trim().slice(0, MAX_MESSAGE_LEN);
    if (!trimmedMessage) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'Please describe the issue.' }) };
    }

    const resendKey = (process.env.RESEND_API_KEY || '').trim();
    if (!resendKey) {
      console.error('report-issue: missing RESEND_API_KEY');
      return { statusCode: 500, headers, body: JSON.stringify({ error: 'Server misconfigured.' }) };
    }

    const store = getStore('webhook-reports');
    let record = null;
    try { record = await store.get(session_id, { type: 'json' }); } catch (e) { /* fail open — still forward the report even without project context */ }
    const projectTitle = (record && record.project && record.project.title) || 'Unknown project';
    const reportedBy = (record && record.emailTo) || 'unknown';
    const siteBase = (process.env.URL || process.env.SITE_URL || 'https://oneciak.com').replace(/\/$/, '');
    const viewUrl = siteBase + '/?report_id=' + encodeURIComponent(session_id) + '&report_token=' + encodeURIComponent(token);

    const html = '<div style="font-family:sans-serif;font-size:14px;color:#111;line-height:1.6">' +
      '<p><strong>Report issue flagged on OneCiak</strong></p>' +
      '<p><strong>Project:</strong> ' + esc(projectTitle) + '<br>' +
      '<strong>Submitted by:</strong> ' + esc(reportedBy) + '<br>' +
      '<strong>Category:</strong> ' + esc(cleanCategory || 'Not specified') + '<br>' +
      '<strong>Session:</strong> ' + esc(session_id) + '</p>' +
      '<p><strong>Message:</strong><br>' + esc(trimmedMessage).replace(/\n/g, '<br>') + '</p>' +
      '<p><a href="' + esc(viewUrl) + '">Open this report</a></p>' +
      '</div>';

    try {
      await sendReportEmail({
        apiKey: resendKey,
        from: process.env.REPORT_FROM_EMAIL || 'OneCiak <onboarding@resend.dev>',
        to: process.env.ISSUE_REPORT_EMAIL || 'info@oneciak.com',
        subject: 'Report issue: "' + projectTitle + '"',
        html
      });
    } catch (e) {
      console.error('report-issue: failed to send notification email', e.message);
      return { statusCode: 500, headers, body: JSON.stringify({ error: 'Could not send your report right now. Please try again later.' }) };
    }

    return { statusCode: 200, headers, body: JSON.stringify({ ok: true }) };
  } catch (err) {
    console.error('report-issue:', err);
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'Something went wrong. Please try again.' }) };
  }
};
