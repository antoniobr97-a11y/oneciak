const https = require('https');

function postMessages(apiKey, body) {
  const payload = JSON.stringify(body);
  return new Promise((resolve, reject) => {
    const req = https.request({ hostname: 'api.anthropic.com', path: '/v1/messages', method: 'POST', headers: { 'Content-Type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'Content-Length': Buffer.byteLength(payload) } }, (res) => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => { try { resolve({ status: res.statusCode, body: JSON.parse(d) }); } catch(e) { reject(e); } });
    });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

// Every URL the web search tool actually returned in this response. A fact
// is only treated as sourced when it cites one of these: a URL the model
// merely remembers (or invents) never counts.
function collectSearchUrls(content, into) {
  (content || []).forEach(block => {
    if (block && block.type === 'web_search_tool_result' && Array.isArray(block.content)) {
      block.content.forEach(r => { if (r && r.url) into.add(r.url); });
    }
  });
}

// The answer is the text written after the last search result. Selected by
// block type, never by position: newer models put thinking blocks first,
// and citations split one answer into several text blocks.
function answerText(content) {
  const blocks = content || [];
  let start = 0;
  blocks.forEach((b, i) => { if (b && (b.type === 'web_search_tool_result' || b.type === 'server_tool_use')) start = i + 1; });
  return blocks.slice(start).filter(b => b && b.type === 'text').map(b => b.text).join('');
}

const MAX_CONTINUATIONS = 4;

// One prompt in, one answer out. With `webSearch` the model can search the
// web (Anthropic runs the searches server side); long searches can pause the
// turn, which is resumed by sending the paused message back unchanged.
async function callClaude({ apiKey, prompt, model, maxTokens, effort, webSearch }) {
  const body = { model, max_tokens: maxTokens, messages: [{ role: 'user', content: prompt }] };
  if (effort) body.output_config = { effort };
  if (webSearch) {
    const tool = { type: 'web_search_20250305', name: 'web_search', max_uses: webSearch.maxUses || 5 };
    if (webSearch.blockedDomains && webSearch.blockedDomains.length) tool.blocked_domains = webSearch.blockedDomains;
    body.tools = [tool];
  }
  const searchUrls = new Set();
  let searches = 0;
  let paused = [];
  for (let i = 0; i <= MAX_CONTINUATIONS; i++) {
    const res = await postMessages(apiKey, body);
    if (res.status !== 200) {
      return { ok: false, status: res.status, error: (res.body && res.body.error && res.body.error.message) || 'API error' };
    }
    const content = res.body.content || [];
    collectSearchUrls(content, searchUrls);
    const used = res.body.usage && res.body.usage.server_tool_use && res.body.usage.server_tool_use.web_search_requests;
    if (used) searches += used;
    if (res.body.stop_reason === 'pause_turn') {
      paused = paused.concat(content);
      body.messages = [{ role: 'user', content: prompt }, { role: 'assistant', content: paused }];
      continue;
    }
    if (res.body.stop_reason === 'refusal') return { ok: false, status: 200, error: 'refusal' };
    return { ok: true, text: answerText(content), searchUrls, searches, stopReason: res.body.stop_reason, usage: res.body.usage };
  }
  return { ok: false, status: 200, error: 'Search did not finish' };
}

function extractJSON(text) {
  const cleaned = (text || '').replace(/```json/gi, '').replace(/```/g, '').trim();
  const a = cleaned.indexOf('{'), b = cleaned.lastIndexOf('}');
  const raw = (a !== -1 && b !== -1) ? cleaned.substring(a, b + 1) : cleaned;
  return JSON.parse(raw);
}

module.exports = { callClaude, extractJSON, answerText, collectSearchUrls };
