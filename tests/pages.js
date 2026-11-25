// Every page x 8 screens (262, 320, 393, 430, 1280, 1600 wide; 1366x657 and
// 1280x600, short laptops, added 25 Nov 2026) x light, dark and no
// preference: home, menu, form (empty and in red), My Reports, the sample
// report with everything open, roadmap, privacy, terms, 404. Looks for page
// errors, failed requests, a page wider than the screen, blue text in
// buttons (iPhone Safari default), long dashes and half-pixel font sizes.
// Run: NODE_PATH=/opt/node22/lib/node_modules node tests/pages.js [base url]
const { chromium } = require('playwright');
// Opens a page, trying again up to 3 times: the live site sometimes takes more
// than 30s to answer one request (seen 24 and 25 Nov 2026), and a network
// hiccup must not read as a broken site.
async function open(p, url) { for (let i = 1; ; i++) { try { return await p.goto(url, { timeout: 45000 }); } catch (e) { if (i >= 3) throw e; await p.waitForTimeout(3000 * i); } } }
const BASE=process.argv[2]||'http://localhost:8143/';
(async()=>{ const b=await chromium.launch(); let issues=[], n=0;
for (const [w,hh] of [[262,860],[320,860],[393,860],[430,860],[1280,860],[1600,860],[1366,657],[1280,600]]) for (const sc of ['light','dark','no-preference']) {
 const ctx=await b.newContext({viewport:{width:w,height:hh},colorScheme:sc,hasTouch:w<500}); const p=await ctx.newPage(); const errs=[], fails=[];
 p.on('pageerror',e=>errs.push(e.message)); p.on('requestfailed',r=>{ if(!/analytics|track/.test(r.url())) fails.push(r.url().slice(0,80)); }); p.on('response',r=>{ if(r.status()>=400 && !r.url().includes('nope') && !r.url().includes('/.netlify/')) fails.push(r.status()+' '+r.url().slice(0,80)); });
 await p.addInitScript(()=>{document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent=':where(button){color:rgb(0,122,255)}';document.head.prepend(s);});});
 const chk=async(view)=>{ n++; const r=await p.evaluate(()=>{const over=document.documentElement.scrollWidth>window.innerWidth+1; const blue=[...document.querySelectorAll('button, button *')].filter(e=>e.offsetParent&&[...e.childNodes].some(t=>t.nodeType===3&&t.textContent.trim())&&getComputedStyle(e).color==='rgb(0, 122, 255)').map(e=>e.textContent.trim().slice(0,20)); const dash=document.body.innerText.includes('—'); const half=[...document.querySelectorAll('body *')].filter(e=>e.offsetParent&&[...e.childNodes].some(t=>t.nodeType===3&&t.textContent.trim())).map(e=>getComputedStyle(e).fontSize).filter(f=>/\.5px$/.test(f)); return {over,blue,dash,half:[...new Set(half)]};}); if(r.over||r.blue.length||r.dash||r.half.length) issues.push(`${w}x${hh} ${sc} ${view}: ${JSON.stringify(r)}`); };
 await open(p, BASE); await p.waitForTimeout(500); await chk('home');
 await p.evaluate(()=>{openMenu(); document.querySelectorAll('.menu-faq-item').forEach(d=>d.open=true);}); await p.waitForTimeout(300); await chk('menu'); await p.evaluate(()=>closeMenu());
 await p.evaluate(()=>{document.getElementById('termsCheck').checked=true; onStartClick();}); await p.waitForTimeout(600); await chk('modulo');
 await p.evaluate(()=>{const b=document.querySelector('#sec-form .btn-primary'); b&&b.click();}); await p.waitForTimeout(500); await chk('modulo rosso');
 await p.evaluate(()=>openMyReports()); await p.waitForTimeout(400); await chk('my reports');
 await p.evaluate(()=>{ showOnly('sec-loading'); startFullReportTimer(); }); await p.waitForTimeout(300); await chk('caricamento');
 await open(p, BASE); await p.evaluate(()=>showSampleReport()); await p.waitForTimeout(800);
 await p.evaluate(()=>{document.querySelectorAll('#sec-results details').forEach(d=>d.open=true); for(let i=0;i<5;i++){const b=document.getElementById('acc-body-'+i); b&&b.classList.add('open');}}); await p.waitForTimeout(300); await chk('report tutto aperto');
 for (const u of ['roadmap/','privacy.html','terms.html','nope']) { await open(p, BASE+u); await p.waitForTimeout(400); await p.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true)); await chk(u); }
 if (errs.length) issues.push(`${w}x${hh} ${sc}: errori JS ${errs}`); if (fails.length) issues.push(`${w}x${hh} ${sc}: richieste fallite ${[...new Set(fails)].join(', ')}`); await ctx.close(); }
console.log('viste controllate',n,'| problemi',issues.length); issues.slice(0,30).forEach(i=>console.log(i)); process.exitCode=issues.length?1:0; await b.close();})();
