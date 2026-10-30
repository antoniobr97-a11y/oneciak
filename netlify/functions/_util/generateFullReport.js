const { callClaude, extractJSON } = require('./anthropic');
const { groundReport } = require('./grounding');
const { applyFacts } = require('./verifiedFacts');
const { allFullPrompts } = require('./reportPrompts');
const { buildReportEmailHtml, sendReportEmail } = require('./email');
const { incrementUsageCount } = require('./stats');
const { verifyReportLinks } = require('./linkCheck');
const { recordAndBenchmark } = require('./benchmarkStats');
const { recordReportForEmail } = require('./userReports');

const FULL_MODEL = 'claude-haiku-5-5';
const FULL_MAX_TOKENS = 32000; // 16000 was not always enough: on 2026-10-28 and -30 a section stopped mid-JSON ("Unexpected end of JSON input") and the whole report failed; Haiku 5.5 allows up to 128K and only the tokens used are billed // room for adaptive thinking plus the JSON (thinking counts toward max_tokens, and Haiku 5.5's tokenizer counts ~30% more tokens than Haiku 4.5's)
const PROCESSING_STALE_MS = 8 * 60 * 1000; // generation can legitimately take a few minutes; give it plenty of room before a retry is treated as abandoned
const PROMPT_ATTEMPTS = 3; // each of the 6 parallel prompts gets its own retries — an occasional malformed-JSON response from the model shouldn't fail the whole report
const RETRY_DELAY_MS = 6000;
const OVERALL_ATTEMPTS = 2; // a second full pass in case something broader (Resend, a transient network error) fails

// Returns the parsed section plus the URLs its web searches returned, which
// grounding.js needs to tell sourced facts from remembered ones.
async function callAndParseWithRetry(apiKey, section) {
  let lastErr;
  for (let i = 0; i < PROMPT_ATTEMPTS; i++) {
    const result = await callClaude({
      apiKey, model: FULL_MODEL, maxTokens: FULL_MAX_TOKENS, prompt: section.prompt,
      webSearch: section.maxSearches ? { maxUses: section.maxSearches } : null
    });
    if (!result.ok) {
      lastErr = new Error('Anthropic API error: ' + result.error);
      // Overload and rate-limit errors clear in seconds; retrying at once
      // (as before) can burn every attempt inside the same busy moment.
      if (i < PROMPT_ATTEMPTS - 1) await new Promise(r => setTimeout(r, RETRY_DELAY_MS * (i + 1)));
      continue;
    }
    try {
      return { data: extractJSON(result.text), searchUrls: Array.from(result.searchUrls), searches: result.searches, usage: result.usage };
    } catch (e) {
      lastErr = new Error(e.message + ' (section ' + section.key + ', stop ' + result.stopReason + ')');
      console.error('generateFullReport: section', section.key, 'unparsable, stop_reason', result.stopReason, 'chars', (result.text || '').length);
    }
  }
  throw lastErr;
}

// The overall score is the average of the five area scores, so it can never
// contradict them (it used to be a separate guess from a different prompt).
function overallFromAreas(r) {
  const keys = ['creative_score', 'financial_score', 'market_score', 'festival_score', 'distribution_score'];
  const vals = keys.map(k => Number(r[k])).filter(v => isFinite(v) && v >= 1 && v <= 10);
  if (!vals.length) return null;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 10) / 10;
}

// Core used to generate and deliver a full report, kept separate from
// generate-report-background.js so the retry/reliability behavior has a
// single home. Always runs inside a Background Function — callers are not
// bound by a sync response-time ceiling, so all retry logic has to live in
// here rather than relying on the caller to redeliver on failure.
//
// `key` is the blob store key the report is persisted under and the id
// embedded in the emailed "View on oneciak.com" link. `viewUrl`, if given,
// overrides the default `?session_id=<key>` link (used by the free-tier
// path, which authenticates that link with its own signed token instead).
async function generateAndDeliverFullReport({ store, key, project, email, anthropicKey, resendKey, fromEmail, subjectPrefix, viewUrl }) {
  const prompts = allFullPrompts(project);
  let lastErr;
  for (let attempt = 1; attempt <= OVERALL_ATTEMPTS; attempt++) {
    try {
      const parsedResults = await Promise.all(prompts.map(section => callAndParseWithRetry(anthropicKey, section)));
      const merged = {};
      const searchUrlsByField = {};
      parsedResults.forEach(r => {
        Object.assign(merged, r.data);
        Object.keys(r.data).forEach(k => { searchUrlsByField[k] = r.searchUrls; });
      });
      merged.overall_score = overallFromAreas(merged);

      // Every festival, fund, film, sales agent and platform must come from
      // a page found by this report's own searches, and every date or figure
      // must appear on that page; anything else is removed, not shown.
      const today = new Date().toISOString().slice(0, 10);
      const grounding = await groundReport(merged, searchUrlsByField, today);
      merged.sources_checked = today;
      applyFacts(merged, project);
      console.log('report', key, 'searches', parsedResults.reduce((a, r) => a + (r.searches || 0), 0),
        'grounding', JSON.stringify(grounding),
        'tokens', JSON.stringify(parsedResults.map(r => r.usage && [r.usage.input_tokens, r.usage.output_tokens])));

      // AI-generated URLs (funds, festivals, sales agents, platforms) can be
      // plausible hallucinations — strip any that don't actually resolve
      // before the report ever reaches screen, PDF, or email.
      await verifyReportLinks(merged);

      // Replace the AI's generic score_benchmark guess with a factual one
      // computed from our own accumulated, anonymized report data, once
      // there's enough of it to say something real — this is the one field
      // a generic chatbot can never produce, since it has no access to data
      // from every other project run through OneCiak.
      try {
        const realBenchmark = await recordAndBenchmark(project, merged.overall_score);
        if (realBenchmark) merged.score_benchmark = realBenchmark;
      } catch (e) { /* benchmarking must never block report delivery */ }

      const html = buildReportEmailHtml(project, merged, key, viewUrl);
      const emailResult = await sendReportEmail({
        apiKey: resendKey,
        from: fromEmail,
        to: email,
        subject: subjectPrefix + ' "' + project.title + '"',
        html
      });

      // Resend's message id, so a delivery complaint can be cross-referenced
      // against the Resend dashboard's logs (accepted-by-API is not the same
      // as delivered-to-inbox — that's tracked on Resend's side, not ours).
      await store.setJSON(key, { status: 'sent', sentAt: Date.now(), report: merged, project, resendId: emailResult && emailResult.id, emailTo: email });
      await incrementUsageCount();

      // Lets this report show up under "My Reports" for this email later,
      // without needing to keep the original link — the whole point of
      // logging in being an alternative to "I lost the email". Storing the
      // session id (not a pre-built link) lets list-reports.js mint a fresh,
      // never-expired link on every visit instead of inheriting the emailed
      // link's 90-day lifetime.
      try { await recordReportForEmail(email, { title: project.title, sessionId: key, createdAt: Date.now() }); } catch (e) { /* never block report delivery over this */ }

      return { ok: true };
    } catch (err) {
      lastErr = err;
      console.error('generateAndDeliverFullReport: attempt ' + attempt + ' failed for', key, err.message);
    }
  }
  try { await store.setJSON(key, { status: 'failed', error: lastErr.message, at: Date.now() }); } catch (e) { /* fail open */ }
  return { ok: false, error: lastErr };
}

module.exports = { generateAndDeliverFullReport, PROCESSING_STALE_MS };
