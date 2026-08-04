const https = require('https');
const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { verify: verifyReportToken } = require('./_util/reportToken');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';
const FREE_MODEL = 'claude-haiku-4-5-20251001';
const FREE_MAX_TOKENS = 2000;
const FULL_MODEL = 'claude-haiku-4-5-20251001';
const FULL_MAX_TOKENS = 4000;
const MAX_PROMPT_LENGTH = 12000;

exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };
  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'analyze', limit: 10, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many requests. Please try again in a while.' }) };

    const body = JSON.parse(event.body || '{}');
    const prompt = body.prompt;
    if (!prompt || typeof prompt !== 'string' || prompt.length > MAX_PROMPT_LENGTH) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'Invalid request.' }) };
    }

    // The expensive model/full-length response is only granted when a valid
    // payment token (minted by verify-payment after a confirmed Stripe charge)
    // is presented. Anything else — including a client claiming tier "full"
    // without a token — silently falls back to the cheap free-tier model, so
    // this endpoint can't be used to run up the paid model's bill for free.
    const isPaid = body.tier === 'full' && verifyReportToken(body.token, body.session_id);
    const model = isPaid ? FULL_MODEL : FREE_MODEL;
    const maxTokens = isPaid ? FULL_MAX_TOKENS : FREE_MAX_TOKENS;

    const apiKey = (process.env.ANTHROPIC_API_KEY || '').trim();
    if (!apiKey) return { statusCode: 500, headers, body: JSON.stringify({ error: 'No API key' }) };
    const payload = JSON.stringify({ model, max_tokens: maxTokens, messages: [{ role: 'user', content: prompt }] });
    const data = await new Promise((resolve, reject) => {
      const req = https.request({ hostname: 'api.anthropic.com', path: '/v1/messages', method: 'POST', headers: { 'Content-Type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'Content-Length': Buffer.byteLength(payload) } }, (res) => {
        let d = '';
        res.on('data', c => d += c);
        res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(d) }));
      });
      req.on('error', reject);
      req.write(payload);
      req.end();
    });
    if (data.status !== 200) return { statusCode: data.status, headers, body: JSON.stringify({ error: data.body.error && data.body.error.message ? data.body.error.message : 'API error' }) };
    return { statusCode: 200, headers, body: JSON.stringify(data.body) };
  } catch(err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
  }
};
