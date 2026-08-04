const Stripe = require('stripe');
const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { sign: signReportToken } = require('./_util/reportToken');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';

exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };
  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'verify-payment', limit: 30, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many requests. Please try again in a while.' }) };

    const stripe = Stripe(process.env.STRIPE_SECRET_KEY);
    const { session_id } = JSON.parse(event.body || '{}');
    if (!session_id) return { statusCode: 400, headers, body: JSON.stringify({ error: 'Missing session_id' }) };
    const session = await stripe.checkout.sessions.retrieve(session_id);
    if (session.payment_status !== 'paid') return { statusCode: 402, headers, body: JSON.stringify({ error: 'Not paid' }) };
    const reportToken = signReportToken(session_id);
    return { statusCode: 200, headers, body: JSON.stringify({ paid: true, project: session.metadata, session_id, reportToken }) };
  } catch(err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
  }
};
