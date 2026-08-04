const Stripe = require('stripe');
const { connectLambda, getStore } = require('@netlify/blobs');
const { callAnthropic, extractJSON } = require('./_util/anthropic');
const { allFullPrompts } = require('./_util/reportPrompts');
const { buildReportEmailHtml, sendReportEmail } = require('./_util/email');

const FULL_MODEL = 'claude-haiku-4-5-20251001';
const FULL_MAX_TOKENS = 8000; // background function isn't bound by a sync response-time ceiling, so the deeper prompts get real room
const PROCESSING_STALE_MS = 8 * 60 * 1000; // generation can now legitimately take a few minutes; give it plenty of room before a retry is treated as abandoned

// Netlify Background Function (note the -background suffix): Netlify acks
// this immediately with a 202 and lets it keep running for up to 15
// minutes, instead of the ~30s ceiling a normal function is bound by. Fired
// by Stripe's checkout.session.completed webhook. This is the SOLE source
// of truth for the full report — the client polls get-report.js and shows
// exactly what got generated here, so screen and email are always
// identical, and generation is independent of whatever happens in the
// customer's browser afterward.
exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Not Allowed' };

  const webhookSecret = (process.env.STRIPE_WEBHOOK_SECRET || '').trim();
  const stripeKey = (process.env.STRIPE_SECRET_KEY || '').trim();
  const resendKey = (process.env.RESEND_API_KEY || '').trim();
  const anthropicKey = (process.env.ANTHROPIC_API_KEY || '').trim();
  if (!webhookSecret || !stripeKey || !resendKey || !anthropicKey) {
    console.error('stripe-webhook-background: missing required env vars');
    return { statusCode: 500, body: 'Server misconfigured' };
  }

  const stripe = Stripe(stripeKey);
  const sig = event.headers['stripe-signature'] || event.headers['Stripe-Signature'];
  const rawBody = event.isBase64Encoded ? Buffer.from(event.body || '', 'base64') : (event.body || '');

  let stripeEvent;
  try {
    stripeEvent = stripe.webhooks.constructEvent(rawBody, sig, webhookSecret);
  } catch (err) {
    console.error('stripe-webhook-background: signature verification failed', err.message);
    return { statusCode: 400, body: 'Invalid signature' };
  }

  if (stripeEvent.type !== 'checkout.session.completed') {
    return { statusCode: 200, body: 'Ignored' };
  }

  const session = stripeEvent.data.object;
  if (session.payment_status !== 'paid') {
    return { statusCode: 200, body: 'Not paid yet' };
  }

  const email = (session.customer_details && session.customer_details.email) || session.customer_email;
  const m = session.metadata || {};
  const project = {
    title: m.title || '', logline: m.logline || '', genre: m.genre || '',
    format: m.format || '', budget: m.budget || '', audience: m.audience || '',
    distrib: m.distrib || '', country: m.country || 'Not specified',
    experience: m.experience || 'Not specified', extra: m.extra || ''
  };

  if (!email || !project.title) {
    console.error('stripe-webhook-background: session missing email or project metadata', session.id);
    return { statusCode: 200, body: 'Missing data, skipped' };
  }

  connectLambda(event);
  const store = getStore('webhook-reports');
  const key = session.id;

  try {
    const existing = await store.get(key, { type: 'json' });
    if (existing && existing.status === 'sent') return { statusCode: 200, body: 'Already sent' };
    if (existing && existing.status === 'processing' && (Date.now() - existing.startedAt) < PROCESSING_STALE_MS) {
      return { statusCode: 200, body: 'Already processing' };
    }
  } catch (e) { /* no record yet, proceed */ }

  try {
    await store.setJSON(key, { status: 'processing', startedAt: Date.now() });
  } catch (e) { /* fail open — proceed even if we can't record state */ }

  try {
    const prompts = allFullPrompts(project);
    const results = await Promise.all(prompts.map(p => callAnthropic(anthropicKey, p, FULL_MODEL, FULL_MAX_TOKENS)));
    const failed = results.find(r => r.status !== 200);
    if (failed) throw new Error('Anthropic API error: ' + (failed.body.error && failed.body.error.message));

    const merged = {};
    results.forEach(r => Object.assign(merged, extractJSON(r.body.content && r.body.content[0] ? r.body.content[0].text : '')));

    const html = buildReportEmailHtml(project, merged, session.id);
    await sendReportEmail({
      apiKey: resendKey,
      from: process.env.REPORT_FROM_EMAIL || 'OneCiak <onboarding@resend.dev>',
      to: email,
      subject: 'Your OneCiak Full Report — "' + project.title + '"',
      html
    });

    await store.setJSON(key, { status: 'sent', sentAt: Date.now(), report: merged, project });
    return { statusCode: 200, body: 'OK' };
  } catch (err) {
    console.error('stripe-webhook-background: generation/email failed for session', session.id, err.message);
    try { await store.setJSON(key, { status: 'failed', error: err.message, at: Date.now() }); } catch (e) {}
    return { statusCode: 500, body: 'Failed, will retry' };
  }
};
