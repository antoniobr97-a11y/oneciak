const Stripe = require('stripe');
const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';

exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };
  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'create-checkout', limit: 15, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many requests. Please try again in a while.' }) };

    const stripe = Stripe(process.env.STRIPE_SECRET_KEY);
    const { project } = JSON.parse(event.body || '{}');
    const session = await stripe.checkout.sessions.create({
      payment_method_types: ['card'],
      line_items: [{ price_data: { currency: 'eur', product_data: { name: 'OneCiak — Full Report', description: 'Analisi completa per "' + (project.title||'') + '"' }, unit_amount: 2900 }, quantity: 1 }],
      mode: 'payment',
      success_url: 'https://oneciak.com/?session_id={CHECKOUT_SESSION_ID}',
      cancel_url: 'https://oneciak.com/',
      metadata: {
        title: (project.title||'').substring(0,200),
        logline: (project.logline||'').substring(0,400),
        genre: (project.genre||'').substring(0,100),
        format: (project.format||'').substring(0,100),
        budget: (project.budget||'').substring(0,100),
        audience: (project.audience||'').substring(0,100),
        distrib: (project.distrib||'').substring(0,100),
        country: (project.country||'').substring(0,100),
        experience: (project.experience||'').substring(0,100),
        extra: (project.extra||'').substring(0,200)
      }
    });
    return { statusCode: 200, headers, body: JSON.stringify({ url: session.url }) };
  } catch(err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
  }
};
