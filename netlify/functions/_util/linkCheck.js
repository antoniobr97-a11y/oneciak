const dns = require('dns');
const https = require('https');
const http = require('http');

const DNS_TIMEOUT_MS = 3000;
const HTTP_TIMEOUT_MS = 4000;
const MAX_CONCURRENT = 8;

function resolvesToADomain(hostname) {
  return new Promise((resolve) => {
    let settled = false;
    const timer = setTimeout(() => { if (!settled) { settled = true; resolve(false); } }, DNS_TIMEOUT_MS);
    dns.lookup(hostname, (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(!err);
    });
  });
}

// Returns false only on a confirmed 404 from a server that actually responded;
// any timeout, connection error, or non-404 status (including 403/405 — many
// sites reject HEAD or bot-like requests without the link itself being wrong)
// resolves true, so a real but blocked link is never mistaken for a broken one.
function httpRespondsNotFound(url) {
  return new Promise((resolve) => {
    let settled = false;
    let lib;
    try { lib = new URL(url).protocol === 'https:' ? https : http; } catch (e) { return resolve(false); }
    const req = lib.request(url, { method: 'HEAD', timeout: HTTP_TIMEOUT_MS }, (res) => {
      if (settled) return;
      settled = true;
      resolve(res.statusCode === 404);
      res.resume();
    });
    req.on('timeout', () => { if (!settled) { settled = true; req.destroy(); resolve(false); } });
    req.on('error', () => { if (!settled) { settled = true; resolve(false); } });
    req.end();
  });
}

// AI-generated URLs (fund/festival/sales-agent/platform pages) can be
// plausible-looking hallucinations. Strips a URL only on strong evidence it
// doesn't exist — an unresolvable domain, or a real server returning a
// confirmed 404 — and otherwise fails open, since a wrongly-removed real
// resource is worse than an occasional unverified one slipping through.
async function verifyUrl(url) {
  if (!url || typeof url !== 'string') return false;
  let hostname;
  try { hostname = new URL(url).hostname; } catch (e) { return false; }
  const domainExists = await resolvesToADomain(hostname);
  if (!domainExists) return false;
  const notFound = await httpRespondsNotFound(url);
  return !notFound;
}

// Walks the merged report object and strips any .url field that fails
// verification, so a broken link never reaches the report as a dead button.
async function verifyReportLinks(merged) {
  const holders = [];
  (function collect(obj) {
    if (Array.isArray(obj)) { obj.forEach(collect); return; }
    if (obj && typeof obj === 'object') {
      if (typeof obj.url === 'string' && obj.url) holders.push(obj);
      Object.values(obj).forEach(collect);
    }
  })(merged);

  let idx = 0;
  async function worker() {
    while (idx < holders.length) {
      const holder = holders[idx++];
      const ok = await verifyUrl(holder.url).catch(() => false);
      if (!ok) delete holder.url;
    }
  }
  await Promise.all(Array.from({ length: Math.min(MAX_CONCURRENT, holders.length) || 1 }, worker));
  return merged;
}

module.exports = { verifyReportLinks };
