const Stripe = require('stripe');
exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Method Not Allowed' };
  try {
    const stripe = Stripe(process.env.STRIPE_SECRET_KEY);
    const { project } = JSON.parse(event.body);
    const session = await stripe.checkout.sessions.create({
      payment_method_types: ['card'],
      line_items: [{ price_data: { currency: 'eur', product_data: { name: 'OneCiak — Full Report', description: `Analisi completa per "${project.title}"` }, unit_amount: 2900 }, quantity: 1 }],
      mode: 'payment',
      success_url: `${process.env.SITE_URL}/?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${process.env.SITE_URL}/`,
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
    return { statusCode: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify({ url: session.url }) };
  } catch (err) {
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
  }
};
