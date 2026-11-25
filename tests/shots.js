// A sheet of photos, before and after, of every view on a phone and a
// computer, to look at with your own eyes: the programs cannot tell whether
// something looks right, only whether it changed. Views that changed are
// listed and put first. Writes OUT/foto-prima-dopo.png and .html.
// Run: OUT=dir NODE_PATH=/opt/node22/lib/node_modules node tests/shots.js https://oneciak.com/ http://localhost:8143/
const { chromium, devices } = require('playwright'); const fs = require('fs'); const path = require('path');
// Opens a page, trying again up to 3 times: the live site sometimes takes more
// than 30s to answer one request (seen 24 and 25 Nov 2026), and a network
// hiccup must not read as a broken site.
async function open(p, url) { for (let i = 1; ; i++) { try { return await p.goto(url, { timeout: 45000 }); } catch (e) { if (i >= 3) throw e; await p.waitForTimeout(3000 * i); } } }
const [A, B] = [process.argv[2] || 'https://oneciak.com/', process.argv[3] || 'http://localhost:8143/'];
const OUT = process.env.OUT || require('os').tmpdir(); fs.mkdirSync(OUT, { recursive: true });
const report = async p => { await p.evaluate(() => showSampleReport()); await p.waitForTimeout(1200); };
const at = sel => async p => { await report(p); await p.evaluate(s => { const e = document.querySelector(s); scrollTo(0, e.getBoundingClientRect().top + scrollY - 120); }, sel); await p.waitForTimeout(900); };
const views = {
  home: async p => {},
  menu: async p => { await p.evaluate(() => openMenu()); await p.waitForTimeout(500); },
  modulo: async p => { await p.evaluate(() => { document.getElementById('termsCheck').checked = true; onStartClick(); }); await p.waitForTimeout(700); },
  'report apertura': report,
  'report aree': at('#accordionMenu .r-areas-h'),
  'report your path': at('#accordionMenu .r-path'),
  'my reports': async p => { await p.evaluate(() => openMyReports()); await p.waitForTimeout(500); },
  roadmap: async p => { await open(p, p.url() + 'roadmap/'); await p.waitForTimeout(800); },
  privacy: async p => { await open(p, p.url() + 'privacy.html'); await p.waitForTimeout(500); }
};
(async () => {
  const b = await chromium.launch(); const rows = [];
  for (const [dev, opt] of [['telefono', { ...devices['iPhone 13'], deviceScaleFactor: 1 }], ['computer', { viewport: { width: 1280, height: 800 } }]]) {
    for (const [name, go] of Object.entries(views)) {
      const pics = [];
      for (const base of [A, B]) {
        const ctx = await b.newContext({ ...opt, colorScheme: 'dark', reducedMotion: 'reduce' }); const p = await ctx.newPage();
        await open(p, base); await p.waitForTimeout(1500); await go(p); await p.waitForTimeout(400);
        pics.push(await p.screenshot()); await ctx.close();
      }
      const same = Buffer.compare(pics[0], pics[1]) === 0;
      const f = n => `${dev}-${name.replace(/ /g, '_')}-${n}.png`;
      fs.writeFileSync(path.join(OUT, f('prima')), pics[0]); fs.writeFileSync(path.join(OUT, f('dopo')), pics[1]);
      rows.push({ dev, name, same, a: f('prima'), b: f('dopo') });
    }
  }
  rows.sort((x, y) => x.same - y.same);
  const html = `<!doctype html><meta charset="utf-8"><style>body{font:15px Carlito,Arial,sans-serif;background:#fff;color:#111;margin:16px}h2{font-size:18px;margin:24px 0 8px}.r{display:flex;gap:16px;align-items:flex-start}.r div{flex:1;min-width:0}img{width:100%;border:1px solid #ccc}.t img{max-width:300px}</style>` +
    rows.map(r => `<h2>${r.dev}, ${r.name}: ${r.same ? 'uguale' : 'CAMBIATA'}</h2><div class="r ${r.dev === 'telefono' ? 't' : ''}"><div>prima (${A})<br><img src="${r.a}"></div><div>dopo (${B})<br><img src="${r.b}"></div></div>`).join('');
  fs.writeFileSync(path.join(OUT, 'foto-prima-dopo.html'), html);
  const p = await b.newPage({ viewport: { width: 1300, height: 900 } }); await open(p, 'file://' + path.join(OUT, 'foto-prima-dopo.html')); await p.waitForTimeout(800);
  await p.screenshot({ path: path.join(OUT, 'foto-prima-dopo.png'), fullPage: true });
  const changed = rows.filter(r => !r.same);
  console.log(changed.length ? 'VISTE CAMBIATE (da guardare): ' + changed.map(r => r.dev + ' ' + r.name).join(', ') : 'NESSUNA VISTA CAMBIATA');
  console.log('Foto: ' + path.join(OUT, 'foto-prima-dopo.png'));
  await b.close();
})();
