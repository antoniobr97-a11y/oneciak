const crypto = require('crypto');

// Binds the recipient and the project to a report id. start-full-report signs
// them; generate-report-background only runs when the signature matches, so a
// valid id/token can't be replayed with a different email or project.
function digest(id, email, project) {
  const secret = process.env.REPORT_TOKEN_SECRET || '';
  return crypto.createHmac('sha256', secret).update(String(id) + '\n' + String(email) + '\n' + JSON.stringify(project)).digest('hex');
}

function sign(id, email, project) {
  return digest(id, email, project);
}

function verify(sig, id, email, project) {
  if (!sig || !process.env.REPORT_TOKEN_SECRET) return false;
  const a = Buffer.from(String(sig), 'hex');
  const b = Buffer.from(digest(id, email, project), 'hex');
  return a.length === b.length && a.length > 0 && crypto.timingSafeEqual(a, b);
}

module.exports = { sign, verify };
