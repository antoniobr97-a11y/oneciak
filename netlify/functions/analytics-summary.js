const crypto = require('crypto');
const { connectLambda } = require('@netlify/blobs');
const { getSummary } = require('./_util/analytics');
const { checkRateLimit } = require('./_util/rateLimit');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';

function keyMatches(provided) {
  const expected = process.env.ADMIN_STATS_KEY || '';
  if (!expected || !provided) return false;
  const a = Buffer.from(String(provided));
  const b = Buffer.from(expected);
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'GET, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'GET') return { statusCode: 405, headers, body: 'Not Allowed' };
  try {
    connectLambda(event);
    // Rate-limited before the key check itself, so this can't be used to
    // brute-force ADMIN_STATS_KEY at any real speed.
    const rl = await checkRateLimit(event, { name: 'analytics-summary', limit: 20, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many requests. Please try again in a while.' }) };
    const params = event.queryStringParameters || {};
    if (!keyMatches(params.key)) return { statusCode: 403, headers, body: JSON.stringify({ error: 'Forbidden' }) };
    const days = Math.min(parseInt(params.days, 10) || 14, 90);
    const summary = await getSummary(days);
    return { statusCode: 200, headers, body: JSON.stringify(summary) };
  } catch (err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
  }
};
