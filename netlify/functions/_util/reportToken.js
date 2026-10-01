const crypto = require('crypto');

// This token is embedded once in the "View on oneciak.com" email link and in
// the page URL for the lifetime of that report — the product promise is
// "we'll email it, and you can always come back here to view it", so it has
// to outlive a single sitting. 90 days comfortably covers that while still
// not being literally unbounded. (A much shorter TTL — 30 minutes — was
// inherited from an earlier Stripe-checkout-session design where the token
// only needed to survive a single payment flow; that no longer applies.)
const TOKEN_TTL_MS = 90 * 24 * 60 * 60 * 1000;

function sign(sessionId) {
  const secret = process.env.REPORT_TOKEN_SECRET || '';
  const expires = Date.now() + TOKEN_TTL_MS;
  const payload = sessionId + '.' + expires;
  const mac = crypto.createHmac('sha256', secret).update(payload).digest('hex');
  return payload + '.' + mac;
}

function verify(token, sessionId) {
  const secret = process.env.REPORT_TOKEN_SECRET || '';
  if (!token || !secret || !sessionId) return false;
  const parts = String(token).split('.');
  if (parts.length !== 3) return false;
  const [tokSessionId, expiresStr, mac] = parts;
  if (tokSessionId !== sessionId) return false;
  const expires = Number(expiresStr);
  if (!expires || Date.now() > expires) return false;
  const expected = crypto.createHmac('sha256', secret).update(tokSessionId + '.' + expiresStr).digest('hex');
  const a = Buffer.from(mac, 'hex');
  const b = Buffer.from(expected, 'hex');
  if (a.length !== b.length || a.length === 0) return false;
  return crypto.timingSafeEqual(a, b);
}

module.exports = { sign, verify };
