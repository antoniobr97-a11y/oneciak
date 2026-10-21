const { connectLambda } = require('@netlify/blobs');
const { checkRateLimit } = require('./_util/rateLimit');
const { callClaude, extractJSON } = require('./_util/anthropic');
const { isSourced, sourcedSet } = require('./_util/grounding');
const { incrementUsageCount } = require('./_util/stats');
const { sanitizeProject } = require('./_util/project');
const { allFreePrompts } = require('./_util/freePrompts');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';
const FREE_MODEL = 'claude-haiku-5-5';
const FREE_MAX_TOKENS = 8000; // room for thinking plus the JSON; low effort keeps the preview fast
const FREE_EFFORT = 'low';

// A comparable film or festival is shown only when the model cites a page
// its own search returned in this request; otherwise it is left out.
function keepIfSourced(obj, set) {
  if (!obj || typeof obj !== 'object' || !isSourced(obj.source_url, set)) return null;
  const out = Object.assign({}, obj, { source: obj.source_url, url: obj.source_url, checked: new Date().toISOString().slice(0, 10) });
  delete out.source_url;
  return out;
}

function overallFromAreas(r) {
  const vals = ['creative_score', 'financial_score', 'market_score', 'festival_score', 'distribution_score']
    .map(k => Number(r[k])).filter(v => isFinite(v) && v >= 1 && v <= 10);
  if (!vals.length) return null;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 10) / 10;
}

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
    const results = await Promise.all(allFreePrompts(project).map(p => callClaude({
      apiKey, model: FREE_MODEL, maxTokens: FREE_MAX_TOKENS, effort: FREE_EFFORT, prompt: p.prompt,
      webSearch: p.maxSearches ? { maxUses: p.maxSearches } : null
    })));
    const failed = results.find(r => !r.ok);
    if (failed) {
      console.error('analyze: Anthropic error', failed.status, failed.error);
      const busy = failed.status === 429 || failed.status === 529;
      return { statusCode: busy ? 503 : 502, headers, body: JSON.stringify({ error: busy ? 'The analysis service is busy right now. Please try again in a minute.' : 'The analysis service had a problem. Please try again.' }) };
    }
    let merged;
    try {
      merged = {};
      results.forEach(r => { Object.assign(merged, extractJSON(r.text)); });
    } catch (e) {
      return { statusCode: 502, headers, body: JSON.stringify({ error: 'Could not parse AI response. Please try again.' }) };
    }
    const set = sourcedSet(results[0].searchUrls);
    merged.one_comp = keepIfSourced(merged.one_comp, set);
    merged.one_festival = keepIfSourced(merged.one_festival, set);
    merged.overall_score = overallFromAreas(merged);
    console.log('analyze: searches', results[0].searches, 'comp', !!merged.one_comp, 'festival', !!merged.one_festival);
    await incrementUsageCount();
    return { statusCode: 200, headers, body: JSON.stringify({ merged }) };
  } catch(err) {
    console.error('analyze:', err);
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'Something went wrong. Please try again.' }) };
  }
};
