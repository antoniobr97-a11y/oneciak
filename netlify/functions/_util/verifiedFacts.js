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
  },
  {
    // Who can apply to the MiC selective grants, read on the 2026 call
    // (decreto direttoriale 15 May 2026 n. 1238, arts. 7, 14 and 22) on
    // 2026-10-28: writing is open to authors as individuals, development
    // and production only to Italian independent production companies.
    countries: /\b(italy|italia|italian)\b/i,
    selective: {
      source: 'https://cinema.cultura.gov.it/wp-content/uploads/dlm_uploads/2026/05/Anno-2026-Bando-per-la-concessione-di-contributi-selettivi-per-la-scrittura-lo-sviluppo-e-la-produzione-di-opere-cinematograf.pdf',
      checked: '2026-10-28',
      writing: 'Possono presentare richiesta di contributo, anche congiuntamente, a pena di inammissibilità, i cittadini maggiorenni',
      development: 'Le richieste di contributo possono essere presentate da: imprese indipendenti cinematografiche e audiovisive italiane, anche in forma associata',
      production: 'Le richieste di contributo possono essere presentate, a pena di inammissibilità, da: imprese indipendenti cinematografiche e audiovisive italiane, anche in forma associata'
    },
    prompt: 'VERIFIED FACT (checked by hand on the 2026 call of the Italian Ministry of Culture for selective grants, decreto direttoriale 15 May 2026 n. 1238): screenplay writing grants are requested by authors as individuals (adult EEA citizens, tax resident in Italy when paid, holding the rights), only for works longer than 52 minutes and written in Italian, and screenplays written with AI systems are excluded; development and production grants, including those for first and second works, are requested only by Italian independent production companies registered with ATECO code 59.1 that have produced at least one eligible work in the last five years (newly founded companies excepted). An individual without a company cannot apply for development or production.'
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
    if (f.selective) applySelective(report, f.selective);
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

// A MiC/DGCA selective grant row gets who can apply, with the call's own
// sentence as the quote and the call as its source. The call's own title
// names writing, development and production together, so that title is
// taken out first and the row is read from what is left: a row about the
// whole call says both rules.
const SELECTIVE_ID = /\b(MiC|DGCA|Ministry of Culture|Ministero della Cultura|Direzione generale Cinema|legge n\.? ?220|law 220|articolo 26|art\.? 26)\b/i;
const CALL_TITLE = /contributi selettivi per la scrittura,? lo sviluppo e la produzione di opere cinematografiche e audiovisive/ig;
function applySelective(report, sel) {
  (report.financial_sources || []).forEach(item => {
    const raw = String(item.name || '') + ' ' + String(item.eligibility || '') + ' ' + String(item.amount || '');
    if (!/selettiv|selective/i.test(raw) || !SELECTIVE_ID.test(raw)) return;
    // The row's own name says which line it is; its other text only when
    // the name (once the call title is out) does not.
    const WRITING = /scrittura|writing|screenplay|sceneggiat/i, COMPANY = /sviluppo|development|produzione|production|opere prime|first and second|first works|giovani autori|young authors/i;
    const name = String(item.name || '').replace(CALL_TITLE, ' ');
    const about = WRITING.test(name) || COMPANY.test(name) ? name : raw.replace(CALL_TITLE, ' ');
    const writing = WRITING.test(about), company = COMPANY.test(about);
    if (writing && !company) { item.applicant = 'Individual'; item.rule_quote = sel.writing; }
    else if (company && !writing) { item.applicant = 'Company'; item.rule_quote = /sviluppo|development/i.test(about) && !/produzione|production|opere prime|first and second/i.test(about) ? sel.development : sel.production; }
    else { item.applicant = 'Split'; item.rule_quote = sel.production; }
    item.source = item.url = sel.source;
    item.checked = sel.checked;
  });
}

module.exports = { promptFacts, applyFacts, factsFor };
