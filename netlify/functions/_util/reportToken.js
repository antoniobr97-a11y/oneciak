const crypto = require('crypto');

const TOKEN_TTL_MS = 30 * 60 * 1000; // 30 minutes — enough to load the full report after payment

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
