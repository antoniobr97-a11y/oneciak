// Every movement of the site, compared between two versions (Antonio, 24 Nov
// 2026: the one-press change silently took the slide away from the report's
// side column and no test saw it). For each element on each view it records
// how it moves: which properties change smoothly (transition), how long, on
// which curve, and its entrance animation. Then it lists every element whose
// movement differs between version A (usually the live site) and version B
// (usually the local server with the change). Every difference must be one
// you meant to make.
// Run: NODE_PATH=/opt/node22/lib/node_modules node tests/motion.js https://oneciak.com/ http://localhost:8143/
const { chromium } = require('playwright');
const [A, B] = [process.argv[2] || 'https://oneciak.com/', process.argv[3] || 'http://localhost:8143/'];
const views = {
  home: async p => {},
  menu: async p => { await p.evaluate(() => openMenu()); },
  modulo: async p => { await p.evaluate(() => { document.getElementById('termsCheck').checked = true; onStartClick(); }); },
  myreports: async p => { await p.evaluate(() => openMyReports()); },
  report: async p => { await p.evaluate(() => showSampleReport()); await p.waitForTimeout(800);
    await p.evaluate(() => { document.querySelectorAll('#sec-results details').forEach(d => d.open = true); for (let i = 0; i < 5; i++) { const x = document.getElementById('acc-body-' + i); x && x.classList.add('open'); } }); }
};
async function signature(browser, base, dev, view) {
  const ctx = await browser.newContext(dev === 'tel' ? { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true } : { viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage(); await p.goto(base); await p.waitForTimeout(600); await views[view](p); await p.waitForTimeout(700);
  const out = await p.evaluate(() => {
    const m = {};
    document.querySelectorAll('body *').forEach(e => {
      if (!e.getClientRects().length) return;
      const cs = getComputedStyle(e);
      const props = cs.transitionProperty.split(',').map(s => s.trim());
      const durs = cs.transitionDuration.split(',').map(s => s.trim());
      const eases = cs.transitionTimingFunction.split(/,(?![^(]*\))/).map(s => s.trim().replace('cubic-bezier(0.23, 1, 0.32, 1)', '--ease'));
      const tr = props.map((pr, i) => durs[i % durs.length] === '0s' ? null : pr + ' ' + durs[i % durs.length] + ' ' + eases[i % eases.length]).filter(Boolean).sort().join(', ');
      const an = cs.animationName !== 'none' ? cs.animationName + ' ' + cs.animationDuration + ' ' + cs.animationFillMode : '';
      if (!tr && !an) return;
      const cls = typeof e.className === 'string' ? e.className.trim().split(/\s+/).filter(c => !/^(on|open|is-[\w-]+|in-view|reveal-observed)$/.test(c)).sort().join('.') : '';
      let anc = e.parentElement, path = ''; for (let k = 0; k < 2 && anc; k++, anc = anc.parentElement) path = (anc.id ? '#' + anc.id : (typeof anc.className === 'string' && anc.className ? '.' + anc.className.trim().split(/\s+/)[0] : anc.tagName.toLowerCase())) + ' > ' + path;
      const key = path + e.tagName.toLowerCase() + (cls ? '.' + cls : '');
      m[key] = 'transizione: ' + (tr || 'nessuna') + (an ? ' | entrata: ' + an : '');
    });
    return m;
  });
  await ctx.close(); return out;
}
(async () => {
  const browser = await chromium.launch(); let diffs = 0, lost = 0;
  for (const dev of ['tel', 'pc']) for (const view of Object.keys(views)) {
    const [a, b] = await Promise.all([signature(browser, A, dev, view), signature(browser, B, dev, view)]);
    for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) {
      if (a[k] === b[k]) continue; diffs++;
      // "background" and "background-color" move the same way; any other
      // property that used to move smoothly and now jumps is flagged.
      const props = x => new Set(((x || '').split('|')[0].match(/[a-z-]+(?= [\d.]+m?s)/g) || []).map(q => q === 'background' ? 'background-color' : q));
      const gone = [...props(a[k])].filter(q => !props(b[k]).has(q) && a[k] && b[k]);
      if (gone.length) { lost++; console.log('PERSO ' + gone.join(', ')); }
      console.log(`${dev} ${view}  ${k}\n   prima: ${a[k] || '(non c\'era)'}\n   dopo:  ${b[k] || '(non c\'è più)'}`);
    }
  }
  console.log(diffs ? `MOVIMENTI DIVERSI: ${diffs} (ognuno deve essere voluto)` : 'NESSUN MOVIMENTO CAMBIATO'); console.log(lost ? `MOVIMENTI PERSI: ${lost} (una cosa che prima si muoveva e ora salta)` : 'NESSUN MOVIMENTO PERSO'); process.exitCode = lost ? 1 : 0;
  await browser.close();
})();
