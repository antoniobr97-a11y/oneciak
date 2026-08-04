const { getStore } = require('@netlify/blobs');

const KEY = 'reports_generated';

// Best-effort, real usage counter — swallows its own errors so a blob
// store hiccup never fails the caller's actual response.
async function incrementUsageCount() {
  try {
    const store = getStore('site-stats');
    const current = await store.get(KEY, { type: 'json' });
    const count = (current && current.count) || 0;
    await store.setJSON(KEY, { count: count + 1 });
  } catch (e) { /* non-critical, ignore */ }
}

async function getUsageCount() {
  try {
    const store = getStore('site-stats');
    const current = await store.get(KEY, { type: 'json' });
    return (current && current.count) || 0;
  } catch (e) { return 0; }
}

module.exports = { incrementUsageCount, getUsageCount };
