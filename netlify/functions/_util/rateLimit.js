const crypto = require('crypto');
const { getStore } = require('@netlify/blobs');

function getClientIp(event) {
  const nf = event.headers && (event.headers['x-nf-client-connection-ip'] || event.headers['X-Nf-Client-Connection-Ip']);
  if (nf) return nf;
  const fwd = event.headers && (event.headers['x-forwarded-for'] || event.headers['X-Forwarded-For']);
  if (fwd) return fwd.split(',')[0].trim();
  return 'unknown';
}

// Fixed-window counter, persisted in Netlify Blobs so it survives across
// function invocations/cold starts (in-memory counters would not).
async function bump(id, { name, limit, windowMinutes }) {
  const bucket = Math.floor(Date.now() / (windowMinutes * 60 * 1000));
  const key = name + ':' + id + ':' + bucket;
  const store = getStore('rate-limits');
  let current;
  try { current = await store.get(key, { type: 'json' }); } catch (e) { current = null; }
  const count = (current && current.count) || 0;
  if (count >= limit) return false;
  try { await store.setJSON(key, { count: count + 1 }); } catch (e) { /* fail open on store errors */ }
  return true;
}

// Per client IP.
async function checkRateLimit(event, opts) {
  const ip = getClientIp(event);
  return { allowed: await bump(ip, opts), ip };
}

// Per arbitrary value, e.g. a recipient address. The value is hashed so the
// store never holds it in clear.
async function checkKeyLimit(value, opts) {
  const id = crypto.createHash('sha256').update(String(value)).digest('hex').slice(0, 32);
  return bump(id, opts);
}

module.exports = { checkRateLimit, checkKeyLimit, getClientIp };
