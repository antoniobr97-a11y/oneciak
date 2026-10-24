// Free quick-preview prompts. Built here on the server from the project
// fields, never accepted from the browser: otherwise /analyze would forward
// any text to the model on our key.

const { SCORING, stageLines, stageRules } = require('./reportPrompts');

const FREE_PREAMBLE = 'You are a film market consultant. Write in clear English, no markdown. Be honest and specific: a filmmaker needs real information, not generic advice. Every sentence must add new, specific information: never restate a verdict field inside its paired detail field, and never pad with generic filler ("this is important", "it is worth noting").\n\nHONESTY RULES (strict): never invent a film, festival, fund, company, statistic, date, deadline, amount or percentage. In this quick preview do not state any deadline, budget, box-office figure, fund amount, rebate percentage or statistic at all: the full report researches those with sources. Name real organisations only when you are certain they exist.\n\n'+SCORING+'\n\nRespond ONLY with valid JSON, no text outside the JSON.';

function freeCurrentDateLine() {
  var today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
  return 'Today\'s date is '+today+'. Only recommend festival editions, fund deadlines and other time-bound opportunities that have not yet closed as of this date — if the current year\'s edition has already happened or its deadline has passed, recommend the next upcoming edition instead and say so.';
}

function freeProjectContext(p) {
  var ctx = freeCurrentDateLine()+'\n\n'+stageRules()+'\n\nProject: Title="'+p.title+'", Logline="'+p.logline+'", Genre="'+p.genre+'", Format="'+p.format+'", Budget="'+p.budget+'", Audience="'+p.audience+'", Distribution="'+p.distrib+'", Country="'+p.country+'", Language="'+p.language+'", Experience="'+p.experience+'", '+stageLines(p)+', Notes="'+(p.extra||'None')+'"';
  if (p.budget === 'Not sure yet') {
    ctx += '\n\nThe filmmaker has not set a budget yet. Before giving any financial assessment, recommend a realistic budget range for a project with this genre, format and scope, and use that range as the basis for every other budget-dependent field in your response.';
  }
  return ctx;
}

// The one prompt of the preview that names real things (a comparable film,
// a festival): it may run two web searches, and analyze.js keeps each only
// when its source_url is one of the pages those searches returned.
function freePromptA(p) {
  return FREE_PREAMBLE+'\n\nRESEARCH: you have a web_search tool and may use it twice: once to confirm one real comparable film (same format as this project, an independent production of similar scale, never a series for a film or a studio release for a low-budget project), once to find the official page of one festival that fits (the festival\'s own site, not a listing site). Set each source_url to the exact URL of the search result that supports it, copied exactly from the search results. Copy any premiere requirement in the source\'s own words.\n\n'+freeProjectContext(p)+'\n\nCover ONLY: overall assessment, one comparable film, one festival fit, and the creative package (narrative, logline, pitch). NOTHING about budget, market, distribution.\n\nRespond with exactly this JSON:\n{\n"overall_label":"3-5 words",\n"overall_summary":"2 honest sentences about this project market position",\n"biggest_risk":"one specific sentence",\n"biggest_opportunity":"one specific sentence",\n"next_step":"the single most important concrete action this week",\n"logline_verdict":"one sentence: does the logline work as a pitch tool",\n"one_comp":{"title":"one real comparable film","year":"year","result":"why it is comparable and where it premiered or was released, without budget or box-office figures","lesson":"one concrete lesson","source_url":"exact search result URL"},\n"one_festival":{"name":"one realistic festival to target","tier":"A/B/C","why":"why it fits, including any premiere requirement that matters","rule_quote":"the premiere or eligibility rule that matters most for this project, copied character for character from the festival page (it is checked against the page), or null","source_url":"exact search result URL"},\n"creative_score":6,\n"creative_verdict":"one sentence — a sharp headline judgment, not a preview of creative_detail","creative_detail":"2-3 sentences","creative_tip":"one concrete suggestion","creative_flag":"one specific red flag","creative_strength":"one specific strength"\n}';
}

function freePromptB(p) {
  return FREE_PREAMBLE+'\n\n'+freeProjectContext(p)+'\n\nCover ONLY: the financial plan (budget realism, funding) and market & audience (demand, trends). NOTHING about creative, festivals, distribution.\n\nRespond with exactly this JSON:\n{\n"financial_score":5,\n"financial_verdict":"one sentence — a sharp headline judgment, not a preview of financial_detail","financial_detail":"2-3 sentences","financial_tip":"one concrete suggestion","financial_flag":"one specific red flag","financial_strength":"one specific strength",\n"market_score":5,\n"market_verdict":"one sentence — a sharp headline judgment, not a preview of market_detail","market_detail":"2-3 sentences","market_tip":"one concrete suggestion","market_flag":"one specific red flag","market_strength":"one specific strength"\n}';
}

function freePromptC(p) {
  return FREE_PREAMBLE+'\n\n'+freeProjectContext(p)+'\n\nCover ONLY: festival strategy (circuit, timing) and distribution & revenue (platforms, projections). NOTHING about creative, budget, market.\n\nRespond with exactly this JSON:\n{\n"festival_score":5,\n"festival_verdict":"one sentence — a sharp headline judgment, not a preview of festival_detail","festival_detail":"2-3 sentences","festival_tip":"one concrete suggestion","festival_flag":"one specific red flag","festival_strength":"one specific strength",\n"distribution_score":5,\n"distribution_verdict":"one sentence — a sharp headline judgment, not a preview of distribution_detail","distribution_detail":"2-3 sentences","distribution_tip":"one concrete suggestion","distribution_flag":"one specific red flag","distribution_strength":"one specific strength"\n}';
}

const PREVIEW_SEARCHES = 2;

function allFreePrompts(p) {
  return [
    { prompt: freePromptA(p), maxSearches: PREVIEW_SEARCHES },
    { prompt: freePromptB(p) },
    { prompt: freePromptC(p) }
  ];
}

module.exports = { allFreePrompts };
