// One real preview from the engine, asked by the page itself the way a visitor
// does, then shown on screen. For changes to the engine or its prompts: the
// other tests only use the sample report, so they cannot see what the model
// now writes. Costs about 0.025 $ per run (docs/motore.md), so it is not in
// check.sh: run it by hand on the preview #81 after updating it.
// Run: NODE_PATH=/opt/node22/lib/node_modules node tests/engine.js https://deploy-preview-81--oneciak.netlify.app/
const { chromium } = require('playwright');
const BASE = process.argv[2];
if (!BASE) { console.log('manca l\'indirizzo: node tests/engine.js https://deploy-preview-81--oneciak.netlify.app/'); process.exit(1); }
if (/^https:\/\/(www\.)?oneciak\.com/.test(BASE)) { console.log('non sul sito vero: ogni prova spende e conta nei limiti dei visitatori'); process.exit(1); }
// the form filled in like a visitor: text typed, each list on its first real choice
const fill = () => {
  const set = (id, v) => { document.getElementById(id).value = v; };
  set('title', 'Salt Season'); set('logline', 'A young salt worker in Trapani has one summer to prove the family salt pans can survive before her father sells them to a resort developer.');
  set('country', 'Italy'); set('language', 'Italian'); set('runtime', '95');
  document.querySelectorAll('#sec-form select').forEach(s => { if (!s.value) { const o = [...s.options].find(o => o.value && o.value !== 'Other'); if (o) s.value = o.value; } });
  set('genre1', 'Drama'); set('format', 'Feature Film');
  return getProject();
};
const AREAS = ['creative', 'financial', 'market', 'festival', 'distribution'];
let pass = 0, fail = 0;
const T = (name, ok, info) => { ok ? pass++ : fail++; console.log((ok ? 'ok   ' : 'NO   ') + name + (info ? ' | ' + info : '')); };
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 860 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(BASE, { timeout: 45000 });
  const project = await p.evaluate(fill); console.log('progetto: ' + JSON.stringify(project)); const t0 = Date.now();
  const r = await p.evaluate(async pr => { try { return await callFullAPI(pr); } catch (e) { return { error: e.message }; } }, project);
  const secs = Math.round((Date.now() - t0) / 1000);
  T('il motore risponde', !r.error, r.error || secs + ' secondi');
  if (r.error) { await b.close(); process.exit(1); }
  const out = require('path').join(process.env.OUT || require('os').tmpdir(), 'engine.json'); require('fs').writeFileSync(out, JSON.stringify(r, null, 1)); console.log('risposta intera: ' + out);
  T('report utilizzabile (isUsableReport)', await p.evaluate(x => isUsableReport(x), r));
  for (const a of AREAS) {
    const s = r[a + '_score'];
    T(a + ': voto da 1 a 10', typeof s === 'number' && s >= 1 && s <= 10, String(s));
    T(a + ': testi', ['verdict', 'detail', 'tip'].every(k => typeof r[a + '_' + k] === 'string' && r[a + '_' + k].trim()), ['verdict', 'detail', 'tip'].filter(k => !r[a + '_' + k]).join(' ') || '');
  }
  const mean = Math.round(AREAS.map(a => r[a + '_score']).reduce((x, y) => x + y, 0) / 5 * 10) / 10;
  T('voto finale = media delle 5 aree', r.overall_score === mean, r.overall_score + ' e ' + mean);
  T('riassunto e prossimo passo', !!(r.overall_summary && r.next_step));
  T('niente overall_label (tolta dai prompt il 25 nov 2026)', !('overall_label' in r));
  // grounding.js keeps a film or festival only with a page its search returned, and moves it to source
  for (const k of ['one_comp', 'one_festival']) T(k + ': assente o con fonte controllata', !r[k] || (/^https?:\/\//.test(r[k].source || '') && !!r[k].checked), r[k] ? (r[k].title || r[k].name) + ' ' + (r[k].source || 'SENZA FONTE') : 'assente');
  await p.evaluate(x => { lastResult = x; showOnly('sec-results'); renderFree(x, 'Salt Season'); }, r); await p.waitForTimeout(1200);
  const text = await p.evaluate(() => document.getElementById('sec-results').innerText);
  T('si vede senza errori nella pagina', !errs.length, errs.join(' ').slice(0, 120));
  T('nessun trattino lungo a schermo', !/[—–]/.test(text));
  console.log('\nPROVE PASSATE ' + pass + ' | FALLITE ' + fail);
  console.log('voti: ' + AREAS.map(a => a + ' ' + r[a + '_score']).join(', ') + ' | finale ' + r.overall_score);
  await b.close(); process.exitCode = fail ? 1 : 0;
})();
