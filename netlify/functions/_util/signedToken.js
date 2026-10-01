const crypto = require('crypto');

// Generic HMAC-signed, self-expiring token: "<subject-b64url>.<expires>.<mac>".
// Shared by reportToken.js (proves "this link is for report X") and the
// magic-link login flow (proves "this link was emailed to address X") so
// both reuse the same signing/verification logic instead of each
// reimplementing it.
//
// The subject is base64url-encoded before being embedded: session_ids never
// contain a literal ".", but an email address almost always does (the
// domain's dot), which would otherwise collide with the "." delimiter and
// silently break every token whose subject is an email.
function sign(subject, ttlMs, secretEnvVar) {
  const secret = process.env[secretEnvVar] || '';
  const expires = Date.now() + ttlMs;
  const encodedSubject = Buffer.from(String(subject)).toString('base64url');
  const payload = encodedSubject + '.' + expires;
  const mac = crypto.createHmac('sha256', secret).update(payload).digest('hex');
  return payload + '.' + mac;
}

function verify(token, subject, secretEnvVar) {
  const secret = process.env[secretEnvVar] || '';
  if (!token || !secret || !subject) return false;
  const parts = String(token).split('.');
  if (parts.length !== 3) return false;
  const [encodedSubject, expiresStr, mac] = parts;
  let tokSubject;
  try { tokSubject = Buffer.from(encodedSubject, 'base64url').toString('utf8'); } catch (e) { return false; }
  if (tokSubject !== String(subject)) return false;
  const expires = Number(expiresStr);
  if (!expires || Date.now() > expires) return false;
  const expected = crypto.createHmac('sha256', secret).update(encodedSubject + '.' + expiresStr).digest('hex');
  const a = Buffer.from(mac, 'hex');
  const b = Buffer.from(expected, 'hex');
  if (a.length !== b.length || a.length === 0) return false;
  return crypto.timingSafeEqual(a, b);
}

module.exports = { sign, verify };
