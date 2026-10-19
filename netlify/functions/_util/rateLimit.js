const crypto = require('crypto');
const { getStore } = require('@netlify/blobs');

function getClientIp(event) {
  const nf = event.headers && (event.headers['x-nf-client-connection-ip'] || event.headers['X-Nf-Client-Connection-Ip']);
  if (nf) return nf;
  const fwd = event.headers && (event.headers['x-forwarded-for'] || event.headers['X-Forwarded-For']);
  if (fwd) return fwd.split(',')[0].trim();
  return 'unknown';
}

// IPs and email addresses are never stored in clear: only a keyed one-way
// hash (HMAC with a server secret), so the stored keys can't be turned back
// into an address. Falls back to a plain SHA-256 if the secret is missing.
function pseudonymize(value) {
  const secret = process.env.REPORT_TOKEN_SECRET || '';
  const h = secret ? crypto.createHmac('sha256', secret) : crypto.createHash('sha256');
  return h.update(String(value)).digest('hex').slice(0, 32);
}

// Keys are "name:hash:bucket:windowMinutes", so a key alone says when it
// expires: (bucket + 1) * windowMinutes. Keys in any other format come from
// the old version, which stored raw IPs, and count as expired.
function isExpired(key, now) {
  const parts = key.split(':');
  if (parts.length !== 4) return true;
  const bucket = Number(parts[2]), win = Number(parts[3]);
  if (!isFinite(bucket) || !isFinite(win) || win <= 0) return true;
  return now >= (bucket + 1) * win * 60 * 1000;
}

// Deletes expired counters (and every legacy raw-IP key). Runs on a small
// share of requests so no request pays for it often; capped per run.
const CLEANUP_PROBABILITY = 0.02;
const CLEANUP_MAX_DELETES = 500;
async function cleanupExpired(store) {
  const now = Date.now();
  let deleted = 0;
  for await (const page of store.list({ paginate: true })) {
    for (const blob of page.blobs) {
      if (deleted >= CLEANUP_MAX_DELETES) return deleted;
      if (isExpired(blob.key, now)) {
        try { await store.delete(blob.key); deleted++; } catch (e) { /* try again next time */ }
      }
    }
  }
  return deleted;
}

// Fixed-window counter, persisted in Netlify Blobs so it survives across
// function invocations/cold starts (in-memory counters would not).
async function bump(id, { name, limit, windowMinutes }) {
  const bucket = Math.floor(Date.now() / (windowMinutes * 60 * 1000));
  const key = name + ':' + id + ':' + bucket + ':' + windowMinutes;
  const store = getStore('rate-limits');
  if (Math.random() < CLEANUP_PROBABILITY) {
    try { await cleanupExpired(store); } catch (e) { /* never block a request over cleanup */ }
  }
  let current;
  try { current = await store.get(key, { type: 'json' }); } catch (e) { current = null; }
  const count = (current && current.count) || 0;
  if (count >= limit) return false;
  try { await store.setJSON(key, { count: count + 1 }); } catch (e) { /* fail open on store errors */ }
  return true;
}

// Per client IP (stored only as a keyed hash).
async function checkRateLimit(event, opts) {
  const ip = getClientIp(event);
  return { allowed: await bump(pseudonymize(ip), opts), ip };
}

// Per arbitrary value, e.g. a recipient address (stored only as a keyed hash).
async function checkKeyLimit(value, opts) {
  return bump(pseudonymize(value), opts);
}

module.exports = { checkRateLimit, checkKeyLimit, getClientIp, cleanupExpired, isExpired };
