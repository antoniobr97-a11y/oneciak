// Facts checked by hand on the primary source, for cases where the web
// pages the model finds are out of date. Example: on 2026-10-22 the DGCA
// summary page of the Italian tax credit still showed the old 25-40% rates,
// while the decree in force sets 30% for independent producers (arts. 12-14
// and 28 of the consolidated text read on 2026-10-23). Each entry
// says where it was checked and when; re-check them when the law changes.

const FACTS = [
  {
    countries: /\b(italy|italia|italian)\b/i,
    tax_incentive: {
      region: 'Italy (national production tax credit, art. 15 of law 220/2016)',
      estimate: '30% of the eligible production cost for independent producers, for feature films and for short films; capped at 4,000,000 euro per cinema work',
      note: 'Claimed by an Italian independent production company (not by an individual) through the Ministry of Culture\'s DGCA. For a fiction feature over 52 minutes the producer must prove at least 40% of the financing and hold a binding theatrical distribution deal (for budgets up to 3.5 million euro: at least 90,000 euro of promotion and 300 screenings in 30 cinemas within six weeks); otherwise the film needs a DGCA selective grant or Council of Europe or EU support plus a minimum cinema release or, under 1.5 million euro, selection at an eligible international festival plus a broadcaster or platform deal. A festival-only release does not qualify on its own. The preliminary request can be filed no earlier than 60 days before shooting starts. Short films follow separate rules. Rules as amended by the interministerial decree MiC-MEF of 6 July 2026, n. 281.',
      source: 'https://cinema.cultura.gov.it/wp-content/uploads/2026/10/20260618_Consolidato_TC-art.-15_Modifica-2026_rev-19-ottobre.pdf',
      checked: '2026-10-22'
    },
    prompt: 'VERIFIED FACT (checked by hand on the official decree; use it and never contradict it): the Italian production tax credit for independent producers is 30% of the eligible production cost for both feature films and short films, capped at 4,000,000 euro per cinema work, under the interministerial decree MiC-MEF of 6 July 2026, n. 281; it is claimed by an Italian independent production company, not by an individual. For a fiction feature over 52 minutes it also requires at least 40% of the financing proven and a binding theatrical distribution deal, or else a DGCA selective grant or Council of Europe or EU support plus a minimum cinema release (or, under 1.5 million euro, an eligible international festival plus a broadcaster or platform deal): a festival-only release does not qualify. Pages that still say 25% to 40% are out of date.'
  }
];

function factsFor(project) {
  const where = String((project && project.country) || '');
  return FACTS.filter(f => f.countries.test(where));
}

// Extra lines for the financial prompt.
function promptFacts(project) {
  return factsFor(project).map(f => f.prompt).join('\n');
}

// Replaces what the model wrote with the hand-checked version, and fixes
// any funding-source row about the same incentive.
function applyFacts(report, project) {
  factsFor(project).forEach(f => {
    if (!f.tax_incentive) return;
    report.tax_incentive = Object.assign({}, f.tax_incentive);
    (report.financial_sources || []).forEach(item => {
      if (/tax credit|credito d.?imposta/i.test(String(item.name || ''))) {
        item.amount = f.tax_incentive.estimate;
        item.source = item.url = f.tax_incentive.source;
        item.checked = f.tax_incentive.checked;
      }
    });
  });
}

module.exports = { promptFacts, applyFacts, factsFor };
