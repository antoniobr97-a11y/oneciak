// Area scores as the report uses them: numbers from 1 to 10, one decimal.
// The prompts' JSON examples carry no number (a number there anchored every
// score near it), so a model may answer "7" or "7/10": both read as 7.
// Anything else is dropped rather than guessed.
const AREAS = ['creative_score', 'financial_score', 'market_score', 'festival_score', 'distribution_score'];

function toScore(v) {
  const n = typeof v === 'number' ? v : parseFloat(String(v == null ? '' : v).replace(',', '.'));
  return isFinite(n) && n >= 1 && n <= 10 ? Math.round(n * 10) / 10 : null;
}

function normalizeScores(r) {
  AREAS.forEach(k => { if (k in r) { const s = toScore(r[k]); if (s == null) delete r[k]; else r[k] = s; } });
  if (r.pitch_assessment && 'logline_score' in r.pitch_assessment) {
    const s = toScore(r.pitch_assessment.logline_score);
    if (s == null) delete r.pitch_assessment.logline_score; else r.pitch_assessment.logline_score = s;
  }
}

// The overall score is the average of the five area scores, so it can never
// contradict them.
function overallFromAreas(r) {
  const vals = AREAS.map(k => r[k]).filter(v => typeof v === 'number');
  if (!vals.length) return null;
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 10) / 10;
}

module.exports = { normalizeScores, overallFromAreas };
