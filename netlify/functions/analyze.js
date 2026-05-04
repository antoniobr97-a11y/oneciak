const https = require('https');
exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Not Allowed' };
  try {
    const body = JSON.parse(event.body);
    const prompt = body.prompt;
    const apiKey = (process.env.ANTHROPIC_API_KEY || '').trim();
    if (!apiKey) return { statusCode: 500, headers: {'Content-Type':'application/json'}, body: JSON.stringify({error:'No API key'}) };
    const payload = JSON.stringify({ model: 'claude-opus-4-5', max_tokens: 8000, messages: [{ role: 'user', content: prompt }] });
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
    return { statusCode: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify(data.body) };
  } catch(err) {
    return { statusCode: 500, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ error: err.message }) };
  }
};
