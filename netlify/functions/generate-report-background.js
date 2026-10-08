const { connectLambda, getStore } = require('@netlify/blobs');
const { verify: verifyReportToken } = require('./_util/reportToken');
const payloadSig = require('./_util/payloadSig');
const { generateAndDeliverFullReport, PROCESSING_STALE_MS } = require('./_util/generateFullReport');

const SITE_BASE = (process.env.URL || process.env.SITE_URL || 'https://oneciak.com').replace(/\/$/, '');

// Netlify Background Function (note the -background suffix): acks the
// triggering request with 202 immediately and keeps running for up to 15
// minutes. Triggered directly by start-full-report.js (no payment involved)
// instead of a Stripe webhook. Since this endpoint is a public URL like any
// other Netlify function, anyone could otherwise POST arbitrary {id, project,
// email} at it directly, bypassing start-full-report's rate limit entirely —
// so a request is only honored if it carries a token that verifies against
// the id, which only start-full-report.js (holding REPORT_TOKEN_SECRET) can
// produce. This is the free-tier equivalent of Stripe's webhook signature.
exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Not Allowed' };

  const resendKey = (process.env.RESEND_API_KEY || '').trim();
  const anthropicKey = (process.env.ANTHROPIC_API_KEY || '').trim();
  if (!resendKey || !anthropicKey) {
    console.error('generate-report-background: missing required env vars');
    return { statusCode: 500, body: 'Server misconfigured' };
  }

  let payload;
  try { payload = JSON.parse(event.body || '{}'); } catch (e) { return { statusCode: 400, body: 'Invalid body' }; }

  const { id, token, project, email, sig } = payload;
  if (!id || !verifyReportToken(token, id)) {
    return { statusCode: 403, body: 'Invalid or expired token' };
  }
  if (!project || !project.title || !email) {
    return { statusCode: 400, body: 'Missing data' };
  }
  // The token alone only proves the id; this proves the email and project
  // are the ones start-full-report validated for that id.
  if (!payloadSig.verify(sig, id, email, project)) {
    return { statusCode: 403, body: 'Invalid payload signature' };
  }

  connectLambda(event);
  const store = getStore('webhook-reports');

  try {
    const existing = await store.get(id, { type: 'json' });
    if (existing && existing.status === 'sent') return { statusCode: 200, body: 'Already sent' };
    if (existing && existing.status === 'generating' && existing.startedAt && (Date.now() - existing.startedAt) < PROCESSING_STALE_MS) {
      return { statusCode: 200, body: 'Already processing' };
    }
  } catch (e) { /* no record yet, proceed */ }

  // Distinct from start-full-report's initial "processing" write — this marks that
  // generation has actually begun, so a duplicate trigger (e.g. a retried kick-off
  // request) can tell "queued" and "already running" apart.
  try { await store.setJSON(id, { status: 'generating', startedAt: Date.now() }); } catch (e) { /* fail open */ }

  const viewUrl = SITE_BASE + '/?report_id=' + encodeURIComponent(id) + '&report_token=' + encodeURIComponent(token);

  const result = await generateAndDeliverFullReport({
    store, key: id, project, email, anthropicKey, resendKey,
    fromEmail: process.env.REPORT_FROM_EMAIL || 'OneCiak <onboarding@resend.dev>',
    subjectPrefix: 'Your OneCiak Full Report —',
    viewUrl
  });

  if (!result.ok) return { statusCode: 500, body: 'Failed after retries' };
  return { statusCode: 200, body: 'OK' };
};
