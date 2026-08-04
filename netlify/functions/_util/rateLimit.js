const { getStore } = require('@netlify/blobs');

function getClientIp(event) {
  const nf = event.headers && (event.headers['x-nf-client-connection-ip'] || event.headers['X-Nf-Client-Connection-Ip']);
  if (nf) return nf;
  const fwd = event.headers && (event.headers['x-forwarded-for'] || event.headers['X-Forwarded-For']);
  if (fwd) return fwd.split(',')[0].trim();
  return 'unknown';
}

// Fixed-window counter per IP, persisted in Netlify Blobs so it survives
// across function invocations/cold starts (in-memory counters would not).
async function checkRateLimit(event, { name, limit, windowMinutes }) {
  const ip = getClientIp(event);
  const bucket = Math.floor(Date.now() / (windowMinutes * 60 * 1000));
  const key = name + ':' + ip + ':' + bucket;
  const store = getStore('rate-limits');
  let current;
  try { current = await store.get(key, { type: 'json' }); } catch (e) { current = null; }
  const count = (current && current.count) || 0;
  if (count >= limit) return { allowed: false, ip };
  try { await store.setJSON(key, { count: count + 1 }); } catch (e) { /* fail open on store errors */ }
  return { allowed: true, ip };
}

module.exports = { checkRateLimit, getClientIp };
