// Free quick-preview prompts. Built here on the server from the project
// fields, never accepted from the browser: otherwise /analyze would forward
// any text to the model on our key.

const FREE_PREAMBLE = 'You are a film market consultant. Write in clear English, no markdown. Be honest and specific — a filmmaker needs real information, not generic advice. Every sentence must add new, specific information: never restate a verdict field inside its paired detail field, and never pad with generic filler ("this is important", "it is worth noting"). Respond ONLY with valid JSON, no text outside the JSON.';

function freeCurrentDateLine() {
  var today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
  return 'Today\'s date is '+today+'. Only recommend festival editions, fund deadlines and other time-bound opportunities that have not yet closed as of this date — if the current year\'s edition has already happened or its deadline has passed, recommend the next upcoming edition instead and say so.';
}

function freeProjectContext(p) {
  var ctx = freeCurrentDateLine()+'\n\nProject: Title="'+p.title+'", Logline="'+p.logline+'", Genre="'+p.genre+'", Format="'+p.format+'", Budget="'+p.budget+'", Audience="'+p.audience+'", Distribution="'+p.distrib+'", Country="'+p.country+'", Language="'+p.language+'", Experience="'+p.experience+'", Notes="'+(p.extra||'None')+'"';
  if (p.budget === 'Not sure yet') {
    ctx += '\n\nThe filmmaker has not set a budget yet. Before giving any financial assessment, recommend a realistic budget range for a project with this genre, format and scope, and use that range as the basis for every other budget-dependent field in your response.';
  }
  return ctx;
}

function freePromptA(p) {
  return FREE_PREAMBLE+'\n\n'+freeProjectContext(p)+'\n\nCover ONLY: overall assessment, one comparable film, one festival fit, and the creative package (narrative, logline, pitch). NOTHING about budget, market, distribution.\n\nRespond with exactly this JSON:\n{\n"overall_score":7.5,\n"overall_label":"3-5 words",\n"overall_summary":"2 honest sentences about this project market position",\n"biggest_risk":"one specific sentence",\n"biggest_opportunity":"one specific sentence",\n"next_step":"the single most important concrete action this week",\n"logline_verdict":"one sentence: does the logline work as a pitch tool",\n"one_comp":{"title":"one real comparable film","year":"year","result":"what it achieved at this budget level","lesson":"one concrete lesson"},\n"one_festival":{"name":"one realistic festival to target","tier":"A/B/C","why":"why it fits","url":"https://real.submission.url"},\n"creative_score":7,\n"creative_verdict":"one sentence — a sharp headline judgment, not a preview of creative_detail","creative_detail":"2-3 sentences","creative_tip":"one concrete suggestion","creative_flag":"one specific red flag","creative_strength":"one specific strength"\n}';
}

function freePromptB(p) {
  return FREE_PREAMBLE+'\n\n'+freeProjectContext(p)+'\n\nCover ONLY: the financial plan (budget realism, funding) and market & audience (demand, trends). NOTHING about creative, festivals, distribution.\n\nRespond with exactly this JSON:\n{\n"financial_score":6,\n"financial_verdict":"one sentence — a sharp headline judgment, not a preview of financial_detail","financial_detail":"2-3 sentences","financial_tip":"one concrete suggestion","financial_flag":"one specific red flag","financial_strength":"one specific strength",\n"market_score":7,\n"market_verdict":"one sentence — a sharp headline judgment, not a preview of market_detail","market_detail":"2-3 sentences","market_tip":"one concrete suggestion","market_flag":"one specific red flag","market_strength":"one specific strength"\n}';
}

function freePromptC(p) {
  return FREE_PREAMBLE+'\n\n'+freeProjectContext(p)+'\n\nCover ONLY: festival strategy (circuit, timing) and distribution & revenue (platforms, projections). NOTHING about creative, budget, market.\n\nRespond with exactly this JSON:\n{\n"festival_score":8,\n"festival_verdict":"one sentence — a sharp headline judgment, not a preview of festival_detail","festival_detail":"2-3 sentences","festival_tip":"one concrete suggestion","festival_flag":"one specific red flag","festival_strength":"one specific strength",\n"distribution_score":5,\n"distribution_verdict":"one sentence — a sharp headline judgment, not a preview of distribution_detail","distribution_detail":"2-3 sentences","distribution_tip":"one concrete suggestion","distribution_flag":"one specific red flag","distribution_strength":"one specific strength"\n}';
}

function allFreePrompts(p) {
  return [freePromptA(p), freePromptB(p), freePromptC(p)];
}

module.exports = { allFreePrompts };
