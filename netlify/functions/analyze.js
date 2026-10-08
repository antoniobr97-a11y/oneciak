const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { callAnthropic, extractJSON } = require('./_util/anthropic');
const { incrementUsageCount } = require('./_util/stats');
const { sanitizeProject } = require('./_util/project');
const { allFreePrompts } = require('./_util/freePrompts');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';
const FREE_MODEL = 'claude-haiku-4-5-20251001';
const FREE_MAX_TOKENS = 3200;

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

    // Free quick preview only (the full report is start-full-report.js).
    // Takes the project fields and builds the prompts here: accepting prompt
    // text from the browser would let anyone use our key for anything.
    const project = sanitizeProject(body.project);
    if (!project) {
      const stale = Array.isArray(body.prompts) || typeof body.prompt === 'string';
      return { statusCode: 400, headers, body: JSON.stringify({ error: stale ? 'OneCiak was just updated. Please reload the page and try again.' : 'Invalid request.' }) };
    }
    const results = await Promise.all(allFreePrompts(project).map(p => callAnthropic(apiKey, p, FREE_MODEL, FREE_MAX_TOKENS)));
    const failed = results.find(r => r.status !== 200);
    if (failed) {
      console.error('analyze: Anthropic error', failed.status, failed.body && failed.body.error && failed.body.error.message);
      const busy = failed.status === 429 || failed.status === 529;
      return { statusCode: busy ? 503 : 502, headers, body: JSON.stringify({ error: busy ? 'The analysis service is busy right now. Please try again in a minute.' : 'The analysis service had a problem. Please try again.' }) };
    }
    let merged;
    try {
      merged = {};
      results.forEach(r => { Object.assign(merged, extractJSON(r.body.content && r.body.content[0] ? r.body.content[0].text : '')); });
    } catch (e) {
      return { statusCode: 502, headers, body: JSON.stringify({ error: 'Could not parse AI response. Please try again.' }) };
    }
    await incrementUsageCount();
    return { statusCode: 200, headers, body: JSON.stringify({ merged }) };
  } catch(err) {
    console.error('analyze:', err);
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'Something went wrong. Please try again.' }) };
  }
};
