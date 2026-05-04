const https = require(‘https’);

exports.handler = async (event) => {
if (event.httpMethod !== ‘POST’) {
return { statusCode: 405, body: ‘Method Not Allowed’ };
}

try {
const { prompt } = JSON.parse(event.body);
const apiKey = (process.env.ANTHROPIC_API_KEY || ‘’).trim();

```
if (!apiKey) {
  return {
    statusCode: 500,
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    body: JSON.stringify({ error: 'API key not configured' })
  };
}

const body = JSON.stringify({
  model: 'claude-opus-4-5',
  max_tokens: 8000,
  messages: [{ role: 'user', content: prompt }]
});

const result = await new Promise((resolve, reject) => {
  const options = {
    hostname: 'api.anthropic.com',
    path: '/v1/messages',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'Content-Length': Buffer.byteLength(body)
    }
  };

  const req = https.request(options, (res) => {
    let data = '';
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      try {
        resolve({ status: res.statusCode, body: JSON.parse(data) });
      } catch(e) {
        reject(new Error('Invalid response from Anthropic'));
      }
    });
  });

  req.on('error', reject);
  req.setTimeout(55000, () => { req.destroy(new Error('Request timeout')); });
  req.write(body);
  req.end();
});

if (result.status !== 200) {
  const errMsg = (result.body.error && result.body.error.message) ? result.body.error.message : JSON.stringify(result.body);
  return {
    statusCode: result.status,
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    body: JSON.stringify({ error: errMsg })
  };
}

return {
  statusCode: 200,
  headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
  body: JSON.stringify(result.body)
};
```

} catch (err) {
return {
statusCode: 500,
headers: { ‘Content-Type’: ‘application/json’, ‘Access-Control-Allow-Origin’: ‘*’ },
body: JSON.stringify({ error: err.message })
};
}
};