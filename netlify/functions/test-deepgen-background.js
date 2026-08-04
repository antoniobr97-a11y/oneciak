const { connectLambda, getStore } = require('@netlify/blobs');
const { callAnthropic, extractJSON } = require('./_util/anthropic');
const { allFullPrompts } = require('./_util/reportPrompts');

const FULL_MODEL = 'claude-haiku-4-5-20251001';
const FULL_MAX_TOKENS = 8000;
const TEST_KEY = 'qk7-diag-3f0c9b';

// TEMPORARY diagnostic function — exercises the exact production code path
// (allFullPrompts + callAnthropic + extractJSON at the real 8000-token
// budget) without touching Stripe or Resend, to verify the deepened
// prompts complete successfully and in reasonable time. Removed after use.
exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Not Allowed' };
  const body = JSON.parse(event.body || '{}');
  if (body.key !== TEST_KEY) return { statusCode: 403, body: 'Forbidden' };

  connectLambda(event);
  const store = getStore('test-deepgen');
  const runId = 'latest';
  await store.setJSON(runId, { status: 'started', startedAt: Date.now() });

  const anthropicKey = (process.env.ANTHROPIC_API_KEY || '').trim();
  const project = {
    title: 'Diagnostic Test Project', logline: 'A test logline for verifying deep report generation.',
    genre: 'Drama', format: 'Feature Film', budget: '€500K', audience: 'General / Mainstream',
    distrib: 'Festival circuit only', country: 'Italy', experience: 'First film', extra: ''
  };

  try {
    const prompts = allFullPrompts(project);
    const callStarted = Date.now();
    const results = await Promise.all(prompts.map(p => callAnthropic(anthropicKey, p, FULL_MODEL, FULL_MAX_TOKENS)));
    const callDurationMs = Date.now() - callStarted;
    const failed = results.find(r => r.status !== 200);
    if (failed) throw new Error('Anthropic API error: ' + JSON.stringify(failed.body));

    const perCallStopReasons = results.map(r => r.body.stop_reason);
    const perCallOutputTokens = results.map(r => r.body.usage && r.body.usage.output_tokens);

    const merged = {};
    let parseErrors = [];
    results.forEach((r, i) => {
      try { Object.assign(merged, extractJSON(r.body.content && r.body.content[0] ? r.body.content[0].text : '')); }
      catch (e) { parseErrors.push('prompt ' + i + ': ' + e.message); }
    });

    const expectedFields = ['overall_score', 'score_benchmark', 'creative_score', 'financial_score', 'talent_leverage', 'tax_incentive', 'market_score', 'festival_score', 'distribution_score', 'roadmap', 'revenue_projection'];
    const missingFields = expectedFields.filter(f => !(f in merged));

    const summary = {
      status: 'finished', finishedAt: Date.now(),
      callDurationMs, perCallStopReasons, perCallOutputTokens,
      parseErrors, missingFields,
      mergedFieldCount: Object.keys(merged).length,
      mergedSizeBytes: JSON.stringify(merged).length
    };
    await store.setJSON(runId, summary);
    return { statusCode: 200, body: JSON.stringify(summary) };
  } catch (err) {
    const summary = { status: 'error', finishedAt: Date.now(), error: err.message };
    await store.setJSON(runId, summary);
    return { statusCode: 500, body: JSON.stringify(summary) };
  }
};
