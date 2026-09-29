const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { callAnthropic, extractJSON } = require('./_util/anthropic');
const { incrementUsageCount } = require('./_util/stats');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';
const FREE_MODEL = 'claude-haiku-4-5-20251001';
const FREE_MAX_TOKENS = 3200;
const MAX_PROMPT_LENGTH = 12000;
const MAX_PARALLEL_PROMPTS = 6;

exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, headers, body: 'Not Allowed' };
  try {
    connectLambda(event);
    const rl = await checkRateLimit(event, { name: 'analyze', limit: 10, windowMinutes: 60 });
    if (!rl.allowed) return { statusCode: 429, headers, body: JSON.stringify({ error: 'Too many requests. Please try again in a while.' }) };

    let body;
    try { body = JSON.parse(event.body || '{}'); } catch (e) { return { statusCode: 400, headers, body: JSON.stringify({ error: 'Invalid request body.' }) }; }

    const apiKey = (process.env.ANTHROPIC_API_KEY || '').trim();
    if (!apiKey) return { statusCode: 500, headers, body: JSON.stringify({ error: 'No API key' }) };

    // Serves the free quick-preview tier only — the full report is generated
    // entirely server-side, see start-full-report.js.
    if (Array.isArray(body.prompts)) {
      const prompts = body.prompts;
      if (!prompts.length || prompts.length > MAX_PARALLEL_PROMPTS || prompts.some(p => typeof p !== 'string' || !p || p.length > MAX_PROMPT_LENGTH)) {
        return { statusCode: 400, headers, body: JSON.stringify({ error: 'Invalid request.' }) };
      }
      const results = await Promise.all(prompts.map(p => callAnthropic(apiKey, p, FREE_MODEL, FREE_MAX_TOKENS)));
      const failed = results.find(r => r.status !== 200);
      if (failed) return { statusCode: failed.status, headers, body: JSON.stringify({ error: failed.body.error && failed.body.error.message ? failed.body.error.message : 'API error' }) };
      let merged;
      try {
        merged = {};
        results.forEach(r => { Object.assign(merged, extractJSON(r.body.content && r.body.content[0] ? r.body.content[0].text : '')); });
      } catch (e) {
        return { statusCode: 502, headers, body: JSON.stringify({ error: 'Could not parse AI response. Please try again.' }) };
      }
      await incrementUsageCount();
      return { statusCode: 200, headers, body: JSON.stringify({ merged }) };
    }

    const prompt = body.prompt;
    if (!prompt || typeof prompt !== 'string' || prompt.length > MAX_PROMPT_LENGTH) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'Invalid request.' }) };
    }
    const result = await callAnthropic(apiKey, prompt, FREE_MODEL, FREE_MAX_TOKENS);
    if (result.status !== 200) return { statusCode: result.status, headers, body: JSON.stringify({ error: result.body.error && result.body.error.message ? result.body.error.message : 'API error' }) };
    return { statusCode: 200, headers, body: JSON.stringify(result.body) };
  } catch(err) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: err.message }) };
  }
};
