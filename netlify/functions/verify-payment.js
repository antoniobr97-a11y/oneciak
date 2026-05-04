const Stripe = require('stripe');
exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Not Allowed' };
  try {
    const stripe = Stripe(process.env.STRIPE_SECRET_KEY);
    const { session_id } = JSON.parse(event.body);
    const session = await stripe.checkout.sessions.retrieve(session_id);
    if (session.payment_status !== 'paid') return { statusCode: 402, body: JSON.stringify({ error: 'Not paid' }) };
    return { statusCode: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify({ paid: true, project: session.metadata }) };
  } catch(err) {
    return { statusCode: 500, headers: {'Content-Type':'application/json'}, body: JSON.stringify({ error: err.message }) };
  }
};
