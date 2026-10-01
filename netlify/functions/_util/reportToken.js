const signedToken = require('./signedToken');

// This token is embedded once in the "View on oneciak.com" email link and in
// the page URL for the lifetime of that report — the product promise is
// "we'll email it, and you can always come back here to view it", so it has
// to outlive a single sitting. 90 days comfortably covers that while still
// not being literally unbounded. (A much shorter TTL — 30 minutes — was
// inherited from an earlier Stripe-checkout-session design where the token
// only needed to survive a single payment flow; that no longer applies.)
const TOKEN_TTL_MS = 90 * 24 * 60 * 60 * 1000;

function sign(sessionId) {
  return signedToken.sign(sessionId, TOKEN_TTL_MS, 'REPORT_TOKEN_SECRET');
}

function verify(token, sessionId) {
  return signedToken.verify(token, sessionId, 'REPORT_TOKEN_SECRET');
}

module.exports = { sign, verify };
