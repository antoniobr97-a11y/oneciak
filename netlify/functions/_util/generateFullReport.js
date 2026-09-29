const { callAnthropic, extractJSON } = require('./anthropic');
const { allFullPrompts } = require('./reportPrompts');
const { buildReportEmailHtml, sendReportEmail } = require('./email');
const { incrementUsageCount } = require('./stats');
const { verifyReportLinks } = require('./linkCheck');

const FULL_MODEL = 'claude-haiku-4-5-20251001';
const FULL_MAX_TOKENS = 9500; // background function isn't bound by a sync response-time ceiling, so the deeper prompts get real room; raised alongside reportPrompts.js's expanded fields to keep headroom against truncated/malformed JSON
const PROCESSING_STALE_MS = 8 * 60 * 1000; // generation can legitimately take a few minutes; give it plenty of room before a retry is treated as abandoned
const PROMPT_ATTEMPTS = 3; // each of the 6 parallel prompts gets its own retries — an occasional malformed-JSON response from the model shouldn't fail the whole report
const OVERALL_ATTEMPTS = 2; // a second full pass in case something broader (Resend, a transient network error) fails

async function callAndParseWithRetry(apiKey, prompt, model, maxTokens) {
  let lastErr;
  for (let i = 0; i < PROMPT_ATTEMPTS; i++) {
    const result = await callAnthropic(apiKey, prompt, model, maxTokens);
    if (result.status !== 200) {
      lastErr = new Error('Anthropic API error: ' + (result.body.error && result.body.error.message));
      continue;
    }
    try {
      return extractJSON(result.body.content && result.body.content[0] ? result.body.content[0].text : '');
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr;
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
      const parsedResults = await Promise.all(prompts.map(p => callAndParseWithRetry(anthropicKey, p, FULL_MODEL, FULL_MAX_TOKENS)));
      const merged = {};
      parsedResults.forEach(r => Object.assign(merged, r));

      // AI-generated URLs (funds, festivals, sales agents, platforms) can be
      // plausible hallucinations — strip any that don't actually resolve
      // before the report ever reaches screen, PDF, or email.
      await verifyReportLinks(merged);

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
