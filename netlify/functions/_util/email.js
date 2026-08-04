const https = require('https');

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function scoreLabel(s) {
  const n = Number(s || 0);
  return n >= 7 ? 'Strong' : n >= 5 ? 'Moderate' : 'Weak';
}

function section(title, score, verdict, detail, flags, strengths, tips, plan, extra) {
  let html = '<tr><td style="padding:28px 0;border-top:1px solid #e5e5e5">';
  html += '<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px">';
  html += '<span style="font-size:16px;font-weight:700;color:#000">' + esc(title) + '</span>';
  if (score !== null && score !== undefined) {
    html += '<span style="font-size:13px;font-weight:700;color:#000;border:1px solid #000;border-radius:999px;padding:2px 10px">' + esc(score) + '/10 · ' + scoreLabel(score) + '</span>';
  }
  html += '</div>';
  if (verdict) html += '<p style="margin:0 0 8px;font-size:14px;color:#161616;font-weight:600">' + esc(verdict) + '</p>';
  if (detail) html += '<p style="margin:0 0 12px;font-size:13px;line-height:1.7;color:#444">' + esc(detail) + '</p>';
  (flags || []).forEach(f => { html += '<p style="margin:0 0 4px;font-size:13px;color:#c5382a">⚑ ' + esc(f) + '</p>'; });
  (strengths || []).forEach(s => { html += '<p style="margin:0 0 4px;font-size:13px;color:#0f7a3d">✓ ' + esc(s) + '</p>'; });
  if (tips && tips.length) {
    html += '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">Recommendations</span>';
    tips.forEach(t => {
      if (!t) return;
      const txt = typeof t === 'string' ? t : (t.advice || '');
      html += '<p style="margin:6px 0 0;font-size:13px;color:#161616">• ' + esc(txt) + '</p>';
      if (typeof t === 'object' && t.links && t.links.length) {
        t.links.forEach(l => { if (l) html += '<p style="margin:2px 0 0 14px;font-size:12px"><a href="' + esc(l.url) + '" style="color:#000">' + esc(l.label) + ' →</a></p>'; });
      }
    });
    html += '</div>';
  }
  if (plan && plan.length) {
    html += '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">Action Plan</span>';
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
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">Funding Sources</span>';
  sources.forEach(f => { if (!f) return; h += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(f.name) + '</b> (' + esc(f.type) + ') — ' + esc(f.amount) + '<br><span style="font-size:12px;color:#6f6f6f">Deadline: ' + esc(f.deadline) + ' · ' + esc(f.eligibility) + '</span></p>'; });
  h += '</div>';
  return h;
}

function comparablesHtml(comps) {
  if (!comps || !comps.length) return '';
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">Comparable Films</span>';
  comps.forEach(c => { if (!c) return; h += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(c.title) + '</b> (' + esc(c.year) + ') — Budget: ' + esc(c.budget) + ' — ' + esc(c.result) + '<br><span style="font-size:12px;color:#6f6f6f">' + esc(c.lesson) + '</span></p>'; });
  h += '</div>';
  return h;
}

function platformsHtml(platforms) {
  if (!platforms || !platforms.length) return '';
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">Platform Priority</span>';
  platforms.forEach(pl => { if (!pl) return; h += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(pl.priority) + ':</b> ' + esc(pl.name) + '<br><span style="font-size:12px;color:#6f6f6f">' + esc(pl.reason) + '</span></p>'; });
  h += '</div>';
  return h;
}

function pitchAssessmentHtml(pa) {
  if (!pa) return '';
  let h = '<div style="margin-top:10px">';
  if (pa.thirty_second_pitch) {
    h += '<span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">30-Second Pitch</span>' +
      '<p style="margin:6px 0 12px;font-size:13px;color:#161616;font-style:italic;line-height:1.6">"' + esc(pa.thirty_second_pitch) + '"</p>';
  }
  if (pa.logline_improved) {
    h += '<span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">Logline Assessment' + (pa.logline_score ? ' — ' + esc(pa.logline_score) + '/10' : '') + '</span>';
    if (pa.logline_issues) h += '<p style="margin:6px 0 0;font-size:13px;color:#6f6f6f;line-height:1.6">' + esc(pa.logline_issues) + '</p>';
    h += '<p style="margin:4px 0 12px;font-size:13px;color:#0f7a3d;font-weight:700;line-height:1.6">Improved: ' + esc(pa.logline_improved) + '</p>';
  }
  if (pa.pitch_deck_checklist && pa.pitch_deck_checklist.length) {
    h += '<span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">Pitch Deck Checklist</span>';
    pa.pitch_deck_checklist.forEach(item => { if (item) h += '<p style="margin:4px 0 0;font-size:13px;color:#161616">☐ ' + esc(item) + '</p>'; });
  }
  h += '</div>';
  return h;
}

function marketingStrategyHtml(ms) {
  if (!ms) return '';
  let h = '<div style="margin-top:10px"><span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">Marketing Strategy</span>';
  if (ms.overview) h += '<p style="margin:6px 0 10px;font-size:13px;color:#161616;line-height:1.6">' + esc(ms.overview) + '</p>';
  if (ms.pre_release && ms.pre_release.length) {
    ms.pre_release.forEach(a => { if (a) h += '<p style="margin:2px 0 0;font-size:13px;color:#6f6f6f">• ' + esc(a) + '</p>'; });
  }
  if (ms.social_strategy) h += '<p style="margin:6px 0 0;font-size:12px;color:#6f6f6f"><b style="color:#161616">Social:</b> ' + esc(ms.social_strategy) + '</p>';
  if (ms.community) h += '<p style="margin:4px 0 0;font-size:12px;color:#6f6f6f"><b style="color:#161616">Community:</b> ' + esc(ms.community) + '</p>';
  if (ms.press) h += '<p style="margin:4px 0 0;font-size:12px;color:#6f6f6f"><b style="color:#161616">Press:</b> ' + esc(ms.press) + '</p>';
  h += '</div>';
  return h;
}

function talentAndTaxHtml(talentLeverage, taxIncentive) {
  if (!talentLeverage && !(taxIncentive && taxIncentive.estimate)) return '';
  let h = '<div style="margin-top:10px">';
  if (talentLeverage) {
    h += '<span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">Talent Leverage</span>' +
      '<p style="margin:6px 0 12px;font-size:13px;color:#161616;line-height:1.6">' + esc(talentLeverage) + '</p>';
  }
  if (taxIncentive && taxIncentive.estimate) {
    h += '<span style="font-size:11px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:#6f6f6f">Tax Incentive' + (taxIncentive.region ? ' — ' + esc(taxIncentive.region) : '') + '</span>' +
      '<p style="margin:6px 0 0;font-size:13px;font-weight:700;color:#0f7a3d">' + esc(taxIncentive.estimate) + '</p>' +
      (taxIncentive.note ? '<p style="margin:2px 0 0;font-size:12px;color:#6f6f6f">' + esc(taxIncentive.note) + '</p>' : '');
  }
  h += '</div>';
  return h;
}

function buildReportEmailHtml(project, r, sessionId) {
  const title = project.title || 'Your project';
  const score = Number(r.overall_score || 5).toFixed(1);
  const viewUrl = sessionId ? 'https://oneciak.com/?session_id=' + encodeURIComponent(sessionId) : 'https://oneciak.com';

  const financialExtra = fundingSourcesHtml(r.financial_sources) + talentAndTaxHtml(r.talent_leverage, r.tax_incentive);
  let body = '';
  body += section('Creative Package', r.creative_score, r.creative_verdict, r.creative_detail, r.creative_flags, r.creative_strengths, r.creative_tips, null, pitchAssessmentHtml(r.pitch_assessment));
  body += section('Financial Plan', r.financial_score, r.financial_verdict, r.financial_detail, r.financial_flags, r.financial_strengths, r.financial_tips, r.financial_action_plan, financialExtra);
  body += section('Market & Audience', r.market_score, r.market_verdict, r.market_detail, r.market_flags, r.market_strengths, r.market_tips, null, comparablesHtml(r.market_comps) + marketingStrategyHtml(r.marketing_strategy));
  body += section('Festival Strategy', r.festival_score, r.festival_verdict, r.festival_detail, r.festival_flags, r.festival_strengths, r.festival_tips, r.festival_action_plan);
  body += section('Distribution & Revenue', r.distribution_score, r.distribution_verdict, r.distribution_detail, r.distribution_flags, r.distribution_strengths, r.distribution_tips, r.distribution_action_plan, platformsHtml(r.distribution_platforms));

  if (r.roadmap && r.roadmap.length) {
    let rm = '<tr><td style="padding:28px 0;border-top:1px solid #e5e5e5"><span style="font-size:16px;font-weight:700;color:#000">Roadmap</span>';
    r.roadmap.forEach((s, i) => { if (!s) return; rm += '<p style="margin:10px 0 0;font-size:13px;color:#161616"><b>' + (i + 1) + '. ' + esc(s.phase) + ':</b> ' + esc(s.action) + '</p>'; });
    rm += '</td></tr>';
    body += rm;
  }

  if (r.international_markets && r.international_markets.length) {
    let im = '<tr><td style="padding:28px 0;border-top:1px solid #e5e5e5"><span style="font-size:16px;font-weight:700;color:#000">International Markets</span>';
    r.international_markets.forEach(m => { if (!m) return; im += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(m.country) + ':</b> ' + esc(m.reason) + '</p>'; });
    im += '</td></tr>';
    body += im;
  }

  if (r.festival_calendar && r.festival_calendar.length) {
    let fc = '<tr><td style="padding:28px 0;border-top:1px solid #e5e5e5"><span style="font-size:16px;font-weight:700;color:#000">Festival Calendar</span>';
    r.festival_calendar.forEach(f => { if (!f) return; fc += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(f.festival) + '</b> (Tier ' + esc(f.tier) + ') — ' + esc(f.deadline) + '<br><span style="font-size:12px;color:#6f6f6f">' + esc(f.fit) + '</span></p>'; });
    fc += '</td></tr>';
    body += fc;
  }

  if (r.sales_agents && r.sales_agents.length) {
    let sa = '<tr><td style="padding:28px 0;border-top:1px solid #e5e5e5"><span style="font-size:16px;font-weight:700;color:#000">Sales Agents</span>';
    r.sales_agents.forEach(a => { if (!a) return; sa += '<p style="margin:8px 0 0;font-size:13px;color:#161616"><b>' + esc(a.name) + '</b>' + (a.focus ? ' <span style="font-size:11px;color:#6f6f6f;text-transform:uppercase;letter-spacing:0.05em">' + esc(a.focus) + '</span>' : '') + '<br><span style="font-size:12px;color:#6f6f6f">' + esc(a.why) + '</span></p>'; });
    sa += '</td></tr>';
    body += sa;
  }

  if (r.risk_assessment && ((r.risk_assessment.top_risks && r.risk_assessment.top_risks.length) || (r.risk_assessment.mitigation && r.risk_assessment.mitigation.length))) {
    let ra = '<tr><td style="padding:28px 0;border-top:1px solid #e5e5e5"><span style="font-size:16px;font-weight:700;color:#000">Risk Assessment</span>';
    (r.risk_assessment.top_risks || []).forEach(risk => { if (risk) ra += '<p style="margin:8px 0 0;font-size:13px;color:#c5382a">⚑ ' + esc(risk) + '</p>'; });
    (r.risk_assessment.mitigation || []).forEach(m => { if (m) ra += '<p style="margin:8px 0 0;font-size:13px;color:#0f7a3d">✓ ' + esc(m) + '</p>'; });
    ra += '</td></tr>';
    body += ra;
  }

  if (r.revenue_projection) {
    const rp = r.revenue_projection;
    let rv = '<tr><td style="padding:28px 0;border-top:1px solid #e5e5e5"><span style="font-size:16px;font-weight:700;color:#000">Revenue Projection</span>';
    [['Theatrical', rp.theatrical], ['Streaming (SVOD)', rp.streaming_svod], ['VOD / AVOD', rp.vod_avod], ['TV Rights', rp.tv_rights], ['International', rp.international]]
      .forEach(([label, v]) => { if (v) rv += '<p style="margin:8px 0 0;font-size:13px;color:#161616;display:flex;justify-content:space-between"><span>' + esc(label) + '</span><span style="color:#6f6f6f">' + esc(v) + '</span></p>'; });
    if (rp.total_realistic) rv += '<p style="margin:12px 0 0;font-size:14px;font-weight:700;color:#000">Total realistic: ' + esc(rp.total_realistic) + '</p>';
    if (rp.breakeven_note) rv += '<p style="margin:6px 0 0;font-size:13px;color:#444">' + esc(rp.breakeven_note) + '</p>';
    rv += '</td></tr>';
    body += rv;
  }

  return '<!doctype html><html><body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif">' +
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:32px 0">' +
    '<tr><td align="center">' +
    '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:18px;overflow:hidden;max-width:600px;width:100%">' +
    '<tr><td style="padding:32px 32px 0;text-align:center"><span style="font-size:14px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#6f6f6f">OneCiak — Film Market Intelligence</span></td></tr>' +
    '<tr><td style="padding:16px 32px 24px;text-align:center">' +
    '<div style="font-size:22px;font-weight:700;color:#000;margin-bottom:8px">"' + esc(title) + '"</div>' +
    '<div style="display:inline-block;border:1px solid #000;border-radius:999px;padding:6px 18px;font-size:15px;font-weight:700;color:#000">Score ' + esc(score) + '/10</div>' +
    (r.overall_label ? '<p style="margin:8px 0 0;font-size:13px;font-weight:600;color:#161616">' + esc(r.overall_label) + '</p>' : '') +
    (r.score_benchmark ? '<p style="margin:10px 0 0;font-size:12.5px;color:#6f6f6f;line-height:1.5">' + esc(r.score_benchmark) + '</p>' : '') +
    '<p style="margin:14px 0 0;font-size:14px;line-height:1.7;color:#444">' + esc(r.executive_summary || r.overall_summary || '') + '</p>' +
    (r.biggest_risk ? '<p style="margin:14px 0 0;padding:10px 14px;background:#fdf1ef;border-radius:10px;text-align:left;font-size:12.5px;color:#c5382a"><b>Main Risk:</b> ' + esc(r.biggest_risk) + '</p>' : '') +
    (r.biggest_opportunity ? '<p style="margin:8px 0 0;padding:10px 14px;background:#eef8f1;border-radius:10px;text-align:left;font-size:12.5px;color:#0f7a3d"><b>Main Opportunity:</b> ' + esc(r.biggest_opportunity) + '</p>' : '') +
    '</td></tr>' +
    '<tr><td style="padding:0 32px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + body + '</table></td></tr>' +
    '<tr><td style="padding:24px 32px 32px;text-align:center;border-top:1px solid #e5e5e5">' +
    '<a href="' + esc(viewUrl) + '" style="display:inline-block;background:#000;color:#fff;text-decoration:none;font-size:14px;font-weight:600;border-radius:999px;padding:12px 28px">View on oneciak.com →</a>' +
    '<p style="margin:20px 0 0;font-size:11px;line-height:1.6;color:#a3a3a3">Analysis generated by AI for informational purposes only. Not professional, legal or financial advice. OneCiak assumes no liability. Results are estimates and do not guarantee any outcome.</p>' +
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
