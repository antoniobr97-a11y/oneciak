const https = require('https');

function callAnthropic(apiKey, prompt, model, maxTokens) {
  const payload = JSON.stringify({ model, max_tokens: maxTokens, messages: [{ role: 'user', content: prompt }] });
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

function extractJSON(text) {
  const cleaned = (text || '').replace(/```json/gi, '').replace(/```/g, '').trim();
  const a = cleaned.indexOf('{'), b = cleaned.lastIndexOf('}');
  const raw = (a !== -1 && b !== -1) ? cleaned.substring(a, b + 1) : cleaned;
  return JSON.parse(raw);
}

module.exports = { callAnthropic, extractJSON };
