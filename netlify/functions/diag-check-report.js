const { connectLambda, getStore } = require('@netlify/blobs');

const TEST_KEY = 'qk7-diag-3f0c9b';

// TEMPORARY diagnostic endpoint — remove after use. Inspects a stored report
// record and the email sender config (non-secret) to debug why an email
// might not have arrived despite the report generating successfully.
exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Not Allowed' };
  let body;
  try { body = JSON.parse(event.body || '{}'); } catch (e) { return { statusCode: 400, body: 'Invalid body' }; }
  if (body.key !== TEST_KEY) return { statusCode: 403, body: 'Forbidden' };

  connectLambda(event);
  const store = getStore('webhook-reports');

  const out = {
    REPORT_FROM_EMAIL_configured: !!process.env.REPORT_FROM_EMAIL,
    REPORT_FROM_EMAIL_value: process.env.REPORT_FROM_EMAIL || '(fallback: OneCiak <onboarding@resend.dev>)',
    RESEND_API_KEY_configured: !!process.env.RESEND_API_KEY,
    RESEND_API_KEY_length: (process.env.RESEND_API_KEY || '').length
  };

  if (body.id) {
    try {
      const record = await store.get(body.id, { type: 'json' });
      out.record = record ? { status: record.status, startedAt: record.startedAt, sentAt: record.sentAt, error: record.error, hasReport: !!record.report, resendId: record.resendId, emailTo: record.emailTo } : null;
    } catch (e) {
      out.recordError = e.message;
    }
  }

  if (body.list) {
    try {
      const listing = await store.list({ prefix: 'free_' });
      out.recentFreeReports = (listing.blobs || []).slice(-15).map(b => b.key);
    } catch (e) {
      out.listError = e.message;
    }
  }

  return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(out, null, 2) };
};
