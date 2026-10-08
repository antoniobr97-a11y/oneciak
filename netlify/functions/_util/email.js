const https = require('https');

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function scoreLabel(s) {
  const n = Number(s || 0);
  return n >= 7 ? 'Strong' : n >= 5 ? 'Moderate' : 'Weak';
}

const MONO = "'SFMono-Regular',Menlo,Consolas,monospace";

function monoLabel(text, color) {
  return '<p style="margin:0 0 8px;font-family:' + MONO + ';font-size:10.5px;letter-spacing:0.08em;text-transform:uppercase;color:' + color + '">' + esc(text) + '</p>';
}

// Label + rows with a colored left rule, same as the flags on the site. Nothing if the list is empty.
function ruledList(label, items, color) {
  items = (items || []).filter(Boolean);
  if (!items.length) return '';
  let html = '<div style="margin-top:16px">' + monoLabel(label, color);
  items.forEach(t => { html += '<p style="margin:0 0 8px;padding:2px 0 2px 12px;border-left:2px solid ' + color + ';font-size:13px;line-height:1.55;color:#161616">' + esc(t) + '</p>'; });
  return html + '</div>';
}

function section(title, score, verdict, detail, flags, strengths, tips, plan, extra) {
  let html = '<tr><td style="padding:28px 0;border-top:1px solid #e4ded6">';
  html += '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px"><tr>';
  html += '<td style="font-size:18px;font-weight:700;color:#141210;letter-spacing:-0.01em">' + esc(title) + '</td>';
  if (score !== null && score !== undefined) {
    html += '<td align="right" style="font-size:13px;color:#5c5852;white-space:nowrap"><b style="font-size:17px;color:#141210">' + esc(score) + '</b>/10 &middot; ' + scoreLabel(score) + '</td>';
  }
  html += '</tr></table>';
  if (verdict) html += '<p style="margin:0 0 8px;font-size:14px;color:#161616;font-weight:600">' + esc(verdict) + '</p>';
  if (detail) html += '<p style="margin:0 0 12px;font-size:13px;line-height:1.7;color:#3d3935">' + esc(detail) + '</p>';
  html += ruledList('Red flags', flags, '#b13225');
  html += ruledList('Strengths', strengths, '#0f7a3d');
  if (tips && tips.length) {
    html += '<div style="margin-top:16px">' + monoLabel('Recommendations', '#5c5852');
    tips.forEach(t => {
      if (!t) return;
      const txt = typeof t === 'string' ? t : (t.advice || '');
      html += '<p style="margin:6px 0 0;font-size:13px;color:#161616">• ' + esc(txt) + '</p>';
      if (typeof t === 'object' && t.links && t.links.length) {
        t.links.forEach(l => {
          if (!l) return;
          html += l.url
            ? '<p style="margin:2px 0 0 14px;font-size:12px"><a href="' + esc(l.url) + '" style="color:#141210">' + esc(l.label) + ' →</a></p>'
            : '<p style="margin:2px 0 0 14px;font-size:12px;color:#5c5852">' + esc(l.label) + '</p>';
        });
      }
    });
    html += '</div>';
  }
  if (plan && plan.length) {
    html += '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Action Plan</span>';
    const tags = ['30 days', '60 days', '90 days'];
    plan.forEach((a, i) => { html += '<p style="margin:4px 0 0;font-size:13px;color:#161616"><b>' + (tags[i] || '') + ':</b> ' + esc(String(a || '').replace(/^(30|60|90)\s*days?:?\s*/i, '')) + '</p>'; });
    html += '</div>';
  }
  if (extra) html += extra;
  html += '</td></tr>';
  return html;
}

function fundingSourcesHtml(sources) {
  if (!sources || !sources.length) return '';
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Funding Sources</span>';
  sources.forEach(f => { if (!f) return; h += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(f.name) + '</b> (' + esc(f.type) + ') — ' + esc(f.amount) + '<br><span style="font-size:12px;color:#5c5852">Deadline: ' + esc(f.deadline) + ' · ' + esc(f.eligibility) + '</span></p>'; });
  h += '</div>';
  return h;
}

function comparablesHtml(comps) {
  if (!comps || !comps.length) return '';
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Comparable Films</span>';
  comps.forEach(c => { if (!c) return; h += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(c.title) + '</b> (' + esc(c.year) + ') — Budget: ' + esc(c.budget) + ' — ' + esc(c.result) + '<br><span style="font-size:12px;color:#5c5852">' + esc(c.lesson) + '</span></p>'; });
  h += '</div>';
  return h;
}

function platformsHtml(platforms) {
  if (!platforms || !platforms.length) return '';
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Platform Priority</span>';
  platforms.forEach(pl => { if (!pl) return; h += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(pl.priority) + ':</b> ' + esc(pl.name) + '<br><span style="font-size:12px;color:#5c5852">' + esc(pl.reason) + '</span></p>'; });
  h += '</div>';
  return h;
}

function pitchAssessmentHtml(pa) {
  if (!pa) return '';
  let h = '<div style="margin-top:10px">';
  if (pa.thirty_second_pitch) {
    h += '<span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">30-Second Pitch</span>' +
      '<p style="margin:6px 0 12px;font-size:13px;color:#161616;font-style:italic;line-height:1.6">"' + esc(pa.thirty_second_pitch) + '"</p>';
  }
  if (pa.logline_improved) {
    h += '<span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Logline Assessment' + (pa.logline_score ? ' — ' + esc(pa.logline_score) + '/10' : '') + '</span>';
    if (pa.logline_issues) h += '<p style="margin:6px 0 0;font-size:13px;color:#5c5852;line-height:1.6">' + esc(pa.logline_issues) + '</p>';
    h += '<p style="margin:4px 0 12px;font-size:13px;color:#0f7a3d;font-weight:700;line-height:1.6">Improved: ' + esc(pa.logline_improved) + '</p>';
  }
  if (pa.pitch_deck_checklist && pa.pitch_deck_checklist.length) {
    h += '<span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Pitch Deck Checklist</span>';
    pa.pitch_deck_checklist.forEach(item => { if (item) h += '<p style="margin:4px 0 0;font-size:13px;color:#161616">☐ ' + esc(item) + '</p>'; });
  }
  h += '</div>';
  return h;
}

function marketingStrategyHtml(ms) {
  if (!ms) return '';
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Marketing Strategy</span>';
  if (ms.overview) h += '<p style="margin:6px 0 10px;font-size:13px;color:#161616;line-height:1.6">' + esc(ms.overview) + '</p>';
  if (ms.pre_release && ms.pre_release.length) {
    ms.pre_release.forEach(a => { if (a) h += '<p style="margin:2px 0 0;font-size:13px;color:#5c5852">• ' + esc(a) + '</p>'; });
  }
  if (ms.social_strategy) h += '<p style="margin:6px 0 0;font-size:12px;color:#5c5852"><b style="color:#161616">Social:</b> ' + esc(ms.social_strategy) + '</p>';
  if (ms.community) h += '<p style="margin:4px 0 0;font-size:12px;color:#5c5852"><b style="color:#161616">Community:</b> ' + esc(ms.community) + '</p>';
  if (ms.press) h += '<p style="margin:4px 0 0;font-size:12px;color:#5c5852"><b style="color:#161616">Press:</b> ' + esc(ms.press) + '</p>';
  if (ms.budget_estimate) h += '<p style="margin:4px 0 0;font-size:12px;color:#5c5852"><b style="color:#161616">Marketing Budget:</b> ' + esc(ms.budget_estimate) + '</p>';
  h += '</div>';
  return h;
}

function labeledTextHtml(label, text) {
  if (!text) return '';
  return '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">' + esc(label) + '</span><p style="margin:6px 0 0;font-size:13px;color:#161616;line-height:1.6">' + esc(text) + '</p></div>';
}

function labOpportunitiesHtml(labs) {
  if (!labs || !labs.length) return '';
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Labs &amp; Market Opportunities</span>';
  labs.forEach(l => { if (!l) return; h += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(l.name) + '</b><br><span style="font-size:12px;color:#5c5852">' + esc(l.fit) + '</span></p>'; });
  h += '</div>';
  return h;
}

function keyCrewHtml(crew) {
  if (!crew || !crew.length) return '';
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Key Crew Recommendations</span>';
  crew.forEach(c => { if (!c) return; h += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(c.role) + '</b><br><span style="font-size:13px;color:#161616">' + esc(c.profile) + '</span><br><span style="font-size:12px;color:#5c5852">' + esc(c.why) + '</span></p>'; });
  h += '</div>';
  return h;
}

function cautionaryCompsHtml(comps) {
  if (!comps || !comps.length) return '';
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Cautionary Comparables</span>';
  comps.forEach(c => { if (!c) return; h += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(c.title) + '</b> (' + esc(c.year) + ') — Budget: ' + esc(c.budget) + '<br><span style="font-size:12px;color:#b13225">' + esc(c.what_went_wrong) + '</span><br><span style="font-size:12px;color:#5c5852">' + esc(c.lesson) + '</span></p>'; });
  h += '</div>';
  return h;
}

function talentAndTaxHtml(talentLeverage, taxIncentive) {
  if (!talentLeverage && !(taxIncentive && taxIncentive.estimate)) return '';
  let h = '<div style="margin-top:10px">';
  if (talentLeverage) {
    h += '<span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Talent Leverage</span>' +
      '<p style="margin:6px 0 12px;font-size:13px;color:#161616;line-height:1.6">' + esc(talentLeverage) + '</p>';
  }
  if (taxIncentive && taxIncentive.estimate) {
    h += '<span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#5c5852">Tax Incentive' + (taxIncentive.region ? ' — ' + esc(taxIncentive.region) : '') + '</span>' +
      '<p style="margin:6px 0 0;font-size:13px;font-weight:700;color:#0f7a3d">' + esc(taxIncentive.estimate) + '</p>' +
      (taxIncentive.note ? '<p style="margin:2px 0 0;font-size:12px;color:#5c5852">' + esc(taxIncentive.note) + '</p>' : '');
  }
  h += '</div>';
  return h;
}

function buildReportEmailHtml(project, r, sessionId, viewUrlOverride) {
  const title = project.title || 'Your project';
  const score = Number(r.overall_score || 5).toFixed(1);
  const viewUrl = viewUrlOverride || (sessionId ? 'https://oneciak.com/?session_id=' + encodeURIComponent(sessionId) : 'https://oneciak.com');

  const financialExtra = fundingSourcesHtml(r.financial_sources) + talentAndTaxHtml(r.talent_leverage, r.tax_incentive) + labeledTextHtml('Budget Breakdown Guidance', r.budget_breakdown_guidance);
  let body = '';
  body += section('Creative Package', r.creative_score, r.creative_verdict, r.creative_detail, r.creative_flags, r.creative_strengths, r.creative_tips, null, pitchAssessmentHtml(r.pitch_assessment) + labeledTextHtml('Attachment Strategy', r.attachment_strategy) + keyCrewHtml(r.key_crew_recommendations));
  body += section('Financial Plan', r.financial_score, r.financial_verdict, r.financial_detail, r.financial_flags, r.financial_strengths, r.financial_tips, r.financial_action_plan, financialExtra);
  body += section('Market & Audience', r.market_score, r.market_verdict, r.market_detail, r.market_flags, r.market_strengths, r.market_tips, null, comparablesHtml(r.market_comps) + marketingStrategyHtml(r.marketing_strategy) + labeledTextHtml('Target Audience Profile', r.target_audience_profile) + cautionaryCompsHtml(r.cautionary_comps));
  body += section('Festival Strategy', r.festival_score, r.festival_verdict, r.festival_detail, r.festival_flags, r.festival_strengths, r.festival_tips, r.festival_action_plan, labOpportunitiesHtml(r.lab_and_market_opportunities));
  body += section('Distribution & Revenue', r.distribution_score, r.distribution_verdict, r.distribution_detail, r.distribution_flags, r.distribution_strengths, r.distribution_tips, r.distribution_action_plan, platformsHtml(r.distribution_platforms) + labeledTextHtml('Self-Distribution Playbook', r.self_distribution_playbook));

  if (r.roadmap && r.roadmap.length) {
    let rm = '<tr><td style="padding:28px 0;border-top:1px solid #e4ded6"><span style="font-size:16px;font-weight:700;color:#141210">Roadmap</span>';
    r.roadmap.forEach((s, i) => { if (!s) return; rm += '<p style="margin:10px 0 0;font-size:13px;color:#161616"><b>' + (i + 1) + '. ' + esc(s.phase) + ':</b> ' + esc(s.action) + '</p>'; });
    rm += '</td></tr>';
    body += rm;
  }

  if (r.international_markets && r.international_markets.length) {
    let im = '<tr><td style="padding:28px 0;border-top:1px solid #e4ded6"><span style="font-size:16px;font-weight:700;color:#141210">International Markets</span>';
    r.international_markets.forEach(m => { if (!m) return; im += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(m.country) + ':</b> ' + esc(m.reason) + '</p>'; });
    im += '</td></tr>';
    body += im;
  }

  if (r.festival_calendar && r.festival_calendar.length) {
    let fc = '<tr><td style="padding:28px 0;border-top:1px solid #e4ded6"><span style="font-size:16px;font-weight:700;color:#141210">Festival Calendar</span>';
    r.festival_calendar.forEach(f => { if (!f) return; fc += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(f.festival) + '</b> (Tier ' + esc(f.tier) + ') — ' + esc(f.deadline) + '<br><span style="font-size:12px;color:#5c5852">' + esc(f.fit) + '</span></p>'; });
    fc += '</td></tr>';
    body += fc;
  }

  if (r.sales_agents && r.sales_agents.length) {
    let sa = '<tr><td style="padding:28px 0;border-top:1px solid #e4ded6"><span style="font-size:16px;font-weight:700;color:#141210">Sales Agents</span>';
    r.sales_agents.forEach(a => { if (!a) return; sa += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(a.name) + '</b>' + (a.focus ? ' <span style="font-size:11px;color:#5c5852;text-transform:uppercase;letter-spacing:0.05em">' + esc(a.focus) + '</span>' : '') + '<br><span style="font-size:12px;color:#5c5852">' + esc(a.why) + '</span></p>'; });
    sa += '</td></tr>';
    body += sa;
  }

  if (r.risk_assessment && ((r.risk_assessment.top_risks && r.risk_assessment.top_risks.length) || (r.risk_assessment.mitigation && r.risk_assessment.mitigation.length))) {
    let ra = '<tr><td style="padding:28px 0;border-top:1px solid #e4ded6"><span style="font-size:16px;font-weight:700;color:#141210">Risk Assessment</span>';
    ra += ruledList('Top risks', r.risk_assessment.top_risks, '#b13225');
    ra += ruledList('How to reduce them', r.risk_assessment.mitigation, '#0f7a3d');
    ra += '</td></tr>';
    body += ra;
  }

  if (r.awards_qualification_strategy) {
    body += '<tr><td style="padding:28px 0;border-top:1px solid #e4ded6"><span style="font-size:16px;font-weight:700;color:#141210">Awards Qualification Strategy</span>' +
      '<p style="margin:10px 0 0;font-size:13px;color:#161616;line-height:1.7">' + esc(r.awards_qualification_strategy) + '</p></td></tr>';
  }

  if (r.legal_and_rights_considerations) {
    body += '<tr><td style="padding:28px 0;border-top:1px solid #e4ded6"><span style="font-size:16px;font-weight:700;color:#141210">Legal &amp; Rights Considerations</span>' +
      '<p style="margin:10px 0 0;font-size:13px;color:#161616;line-height:1.7">' + esc(r.legal_and_rights_considerations) + '</p></td></tr>';
  }

  if (r.revenue_projection) {
    const rp = r.revenue_projection;
    let rv = '<tr><td style="padding:28px 0;border-top:1px solid #e4ded6"><span style="font-size:16px;font-weight:700;color:#141210">Revenue Projection</span>';
    [['Theatrical', rp.theatrical], ['Streaming (SVOD)', rp.streaming_svod], ['VOD / AVOD', rp.vod_avod], ['TV Rights', rp.tv_rights], ['International', rp.international]]
      .forEach(([label, v]) => { if (v) rv += '<p style="margin:8px 0 0;font-size:13px;color:#161616;display:flex;justify-content:space-between"><span>' + esc(label) + '</span><span style="color:#5c5852">' + esc(v) + '</span></p>'; });
    if (rp.total_realistic) rv += '<p style="margin:12px 0 0;font-size:14px;font-weight:700;color:#141210">Total realistic: ' + esc(rp.total_realistic) + '</p>';
    if (rp.breakeven_note) rv += '<p style="margin:6px 0 0;font-size:13px;color:#3d3935">' + esc(rp.breakeven_note) + '</p>';
    rv += '</td></tr>';
    body += rv;
  }

  if (r.business_plan_summary) {
    const bp = r.business_plan_summary;
    let bps = '<tr><td style="padding:28px 0;border-top:1px solid #e4ded6"><span style="font-size:16px;font-weight:700;color:#141210">Business Plan Summary</span>';
    if (bp.executive_summary) bps += '<p style="margin:10px 0 0;font-size:13px;color:#161616;line-height:1.7">' + esc(bp.executive_summary) + '</p>';
    if (bp.the_ask) bps += '<p style="margin:12px 0 0;padding:10px 14px;background:#efeae3;border-radius:10px;font-size:13px;color:#161616"><b>The Ask:</b> ' + esc(bp.the_ask) + '</p>';
    [['Market Opportunity', bp.market_opportunity], ['Competitive Advantage', bp.competitive_advantage], ['Use of Funds', bp.use_of_funds], ['Team & Experience', bp.team_and_experience]]
      .forEach(([label, v]) => { if (v) bps += '<p style="margin:12px 0 0;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#5c5852">' + esc(label) + '</p><p style="margin:4px 0 0;font-size:13px;color:#161616;line-height:1.6">' + esc(v) + '</p>'; });
    if (bp.key_milestones && bp.key_milestones.length) {
      bps += '<p style="margin:14px 0 0;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#5c5852">Key Milestones</p>';
      bp.key_milestones.forEach(m => { if (m) bps += '<p style="margin:6px 0 0;font-size:13px;color:#161616">• ' + esc(m) + '</p>'; });
    }
    if (bp.risk_summary) bps += '<p style="margin:14px 0 0;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#5c5852">Biggest Risk</p><p style="margin:4px 0 0;font-size:13px;color:#b13225">' + esc(bp.risk_summary) + '</p>';
    bps += '</td></tr>';
    body += bps;
  }

  // Same language as the site: a night header carrying the glow (a hosted
  // image, because Gmail strips SVG and Outlook ignores CSS gradients; the
  // night bgcolor is the fallback), then the report on warm paper.
  const FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif";
  return '<!doctype html><html><head><meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light"></head><body style="margin:0;padding:0;background:#f4f1ec;font-family:' + FONT + '">' +
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f1ec;padding:28px 0">' +
    '<tr><td align="center">' +
    '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:14px;overflow:hidden;background:#fbf9f6">' +
    '<tr><td bgcolor="#140d10" background="https://oneciak.com/email-header.jpg" style="background:#140d10 url(https://oneciak.com/email-header.jpg) center top / cover no-repeat;padding:28px 32px 30px">' +
      '<div style="font-size:15px;font-weight:700;color:#f2ede6;letter-spacing:-0.01em">OneCiak</div>' +
      '<div style="margin-top:30px;font-family:' + MONO + ';font-size:11px;letter-spacing:0.08em;text-transform:uppercase;color:#d6cec3">Full market report</div>' +
      '<div style="margin-top:8px;font-size:30px;line-height:1.1;font-weight:700;color:#f2ede6;letter-spacing:-0.02em">' + esc(title) + '</div>' +
      '<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:18px"><tr>' +
        '<td style="font-size:44px;line-height:1;font-weight:300;color:#f2ede6;letter-spacing:-0.03em;padding-right:12px">' + esc(score) + '<span style="font-size:17px;color:#d6cec3">/10</span></td>' +
        (r.overall_label ? '<td style="font-size:14px;font-weight:600;color:#f2ede6;vertical-align:bottom;padding-bottom:4px">' + esc(r.overall_label) + '</td>' : '') +
      '</tr></table>' +
    '</td></tr>' +
    '<tr><td style="padding:26px 32px 6px">' +
    (r.score_benchmark ? '<p style="margin:0 0 14px;font-size:12.5px;color:#5c5852;line-height:1.55">' + esc(r.score_benchmark) + '</p>' : '') +
    '<p style="margin:0;font-size:15px;line-height:1.7;color:#161616">' + esc(r.executive_summary || r.overall_summary || '') + '</p>' +
    (r.biggest_risk ? '<p style="margin:18px 0 0;padding:2px 0 2px 12px;border-left:2px solid #b13225;font-size:13px;line-height:1.55;color:#161616"><span style="font-family:' + MONO + ';font-size:10.5px;letter-spacing:0.08em;text-transform:uppercase;color:#b13225">Main risk</span><br>' + esc(r.biggest_risk) + '</p>' : '') +
    (r.biggest_opportunity ? '<p style="margin:12px 0 0;padding:2px 0 2px 12px;border-left:2px solid #0f7a3d;font-size:13px;line-height:1.55;color:#161616"><span style="font-family:' + MONO + ';font-size:10.5px;letter-spacing:0.08em;text-transform:uppercase;color:#0f7a3d">Main opportunity</span><br>' + esc(r.biggest_opportunity) + '</p>' : '') +
    '</td></tr>' +
    '<tr><td style="padding:0 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + body + '</table></td></tr>' +
    '<tr><td style="padding:26px 32px 30px;border-top:1px solid #e4ded6">' +
    '<a href="' + esc(viewUrl) + '" style="display:inline-block;background:#140d10;color:#f2ede6;text-decoration:none;font-size:14px;font-weight:600;border-radius:10px;padding:13px 22px">View on oneciak.com</a>' +
    '<p style="margin:22px 0 0;font-size:11px;line-height:1.6;color:#6b665f">Analysis generated by AI for informational purposes only. Not professional, legal or financial advice. OneCiak assumes no liability. Results are estimates and do not guarantee any outcome.</p>' +
    '</td></tr>' +
    '</table></td></tr></table></body></html>';
}

function sendReportEmail({ apiKey, from, to, subject, html }) {
  const payload = JSON.stringify({ from, to: [to], subject, html });
  return new Promise((resolve, reject) => {
    const req = https.request({ hostname: 'api.resend.com', path: '/emails', method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + apiKey, 'Content-Length': Buffer.byteLength(payload) } }, (res) => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => {
        let parsed = null;
        try { parsed = JSON.parse(d); } catch (e) {}
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(parsed);
        else reject(new Error('Resend error ' + res.statusCode + ': ' + d));
      });
    });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

module.exports = { buildReportEmailHtml, sendReportEmail };
