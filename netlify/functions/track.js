const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { recordEvent, EVENTS } = require('./_util/analytics');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';

// Fire-and-forget funnel beacon called from the client at a handful of fixed
// points (landing, form start, analysis completed, full report requested,
// full report delivered) — see EVENTS in _util/analytics.js. Anonymous and
// aggregate only: no identifier is ever stored per visitor.
exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };
  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'track', limit: 60, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 204, headers, body: '' }; // silently drop, never surface an error for a beacon

    const body = JSON.parse(event.body || '{}');
    if (EVENTS.indexOf(body.event) === -1) return { statusCode: 204, headers, body: '' };
    await recordEvent(body.event);
    return { statusCode: 204, headers, body: '' };
  } catch (err) {
    return { statusCode: 204, headers, body: '' }; // a tracking beacon must never surface an error to the client
  }
};
