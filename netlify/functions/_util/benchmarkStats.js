const { getStore } = require('@netlify/blobs');

// Below this sample size a cohort's percentile would be statistically
// meaningless ("better than 100% of the 1 other project") — stay silent and
// let the AI's own generic estimate stand until there's real signal.
const MIN_SAMPLE = 15;

// Caps how many historical scores a cohort blob keeps, so it can't grow
// unbounded — recent scores are what matter for "similar projects now"
// anyway, and this keeps each blob small and cheap to read/write.
const MAX_SCORES_PER_COHORT = 2000;

function slugify(s) {
  return String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'unspecified';
}

function primaryGenre(genre) {
  return String(genre || '').split('/')[0].trim() || 'Unspecified';
}

async function readScores(store, key) {
  try {
    const rec = await store.get(key, { type: 'json' });
    return (rec && Array.isArray(rec.scores)) ? rec.scores : [];
  } catch (e) {
    return [];
  }
}

function percentile(historicalScores, value) {
  if (!historicalScores.length) return null;
  const below = historicalScores.filter(function (s) { return s < value; }).length;
  return Math.round((below / historicalScores.length) * 100);
}

// Records this report's overall score into three cohorts (genre+budget,
// genre-only, and global — most specific first) and returns a factual
// benchmark sentence built from real accumulated data, using the most
// specific cohort that already has enough samples. Returns null when no
// cohort has enough data yet; callers should keep the AI's own
// score_benchmark field in that case rather than showing nothing.
//
// No title, logline, email, or other identifying project detail is ever
// stored here — only genre, budget bracket, and the numeric score.
async function recordAndBenchmark(project, overallScore) {
  if (typeof overallScore !== 'number') return null;
  const store = getStore('benchmark-scores');
  const genre = primaryGenre(project && project.genre);
  const genreKey = slugify(genre);
  const budgetKey = slugify(project && project.budget);

  const cohorts = [
    { key: genreKey + '__' + budgetKey, label: genre + ' projects at a similar budget' },
    { key: genreKey, label: genre + ' projects' },
    { key: 'global', label: 'projects' }
  ];

  let benchmarkText = null;
  for (let i = 0; i < cohorts.length; i++) {
    const cohort = cohorts[i];
    const existing = await readScores(store, cohort.key);
    if (benchmarkText === null && existing.length >= MIN_SAMPLE) {
      const pct = percentile(existing, overallScore);
      benchmarkText = 'Based on ' + existing.length + ' ' + cohort.label + ' analyzed on OneCiak, this project scores higher than ' + pct + '% of them.';
    }
    try {
      const updated = existing.concat([overallScore]).slice(-MAX_SCORES_PER_COHORT);
      await store.setJSON(cohort.key, { scores: updated });
    } catch (e) { /* benchmarking is a bonus — never let a storage hiccup block report delivery */ }
  }
  return benchmarkText;
}

module.exports = { recordAndBenchmark, MIN_SAMPLE };
