// Every function of the site, on a phone (iPhone 13) and a computer (1280px):
// menu and its questions, disclaimer, empty form (7 red fields), My Reports,
// the sample report (Read more, each of the 5 areas, the blocks inside an
// area, each step of "Your path", copy email, glossary, every item of the
// index), PDF, Report a problem, roadmap (49 jobs, ticks kept, every drop-down), 404.
// Run: NODE_PATH=/opt/node22/lib/node_modules node tests/functions.js [base url]
// Base url: a local server on the repo (default http://localhost:8143/) or https://oneciak.com/.
const { chromium, devices } = require('playwright'); const fs=require('fs');
// Opens a page, trying again up to 3 times: the live site sometimes takes more
// than 30s to answer one request (seen 24 and 25 Nov 2026), and a network
// hiccup must not read as a broken site.
async function open(p, url) { for (let i = 1; ; i++) { try { return await p.goto(url, { timeout: 45000 }); } catch (e) { if (i >= 3) throw e; await p.waitForTimeout(3000 * i); } } }
const BASE=process.argv[2]||'http://localhost:8143/'; const OUT=(process.env.OUT||require('os').tmpdir())+'/';
let ok=0, ko=[];
const T=(name,cond,info='')=>{ if(cond) ok++; else ko.push(name+(info?' ('+info+')':'')); };
const barsBottom=p=>p.evaluate(()=>{ let m=0; for (const s of ['#sec-results .r-header','#areaNav']) { const e=document.querySelector(s); if(!e) continue; const cs=getComputedStyle(e); if(cs.opacity==='0'||cs.display==='none') continue; const r=e.getBoundingClientRect(); if(s==='#areaNav'&&innerWidth>=1100) continue; if(r.bottom>0&&r.top<200) m=Math.max(m,r.bottom);} return m; });
const visibleUnderBars=async(p,sel,idx=0)=>{ const bb=await barsBottom(p); const t=await p.evaluate(([s,i])=>{const e=document.querySelectorAll(s)[i]; return e?e.getBoundingClientRect().top:null;},[sel,idx]); return {ok: t!==null && t>=bb-1 && t<innerHeightSafe(p), t, bb}; };
function innerHeightSafe(){ return 2000; }
(async()=>{ const b=await chromium.launch();
for (const dev of ['tel','pc']) {
 const ctx=await b.newContext(dev==='tel'?{...devices['iPhone 13'],acceptDownloads:true}:{viewport:{width:1280,height:900},acceptDownloads:true});
 await ctx.grantPermissions(['clipboard-read','clipboard-write'],{origin:new URL(BASE).origin}).catch(()=>{});
 const p=await ctx.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(e.message));
 const tap=async loc=>{ if(dev==='tel') await loc.tap(); else await loc.click(); };
 const W=ms=>p.waitForTimeout(ms);
 // HOME + MENU
 await open(p, BASE); await W(700);
 await tap(p.locator('#hamburgerBtn')); await W(500);
 T(dev+' menu si apre', await p.evaluate(()=>getComputedStyle(document.getElementById('menuOverlay')).visibility!=='hidden' && document.getElementById('menuOverlay').getBoundingClientRect().height>200));
 const faq=p.locator('.menu-faq-item > summary'); const nf=await faq.count();
 for (let i=0;i<nf;i++){ await tap(faq.nth(i)); await W(300); T(dev+' menu domanda '+(i+1)+' si apre', await p.evaluate(i=>document.querySelectorAll('.menu-faq-item')[i].open,i)); await tap(faq.nth(i)); await W(250); T(dev+' menu domanda '+(i+1)+' si chiude', await p.evaluate(i=>!document.querySelectorAll('.menu-faq-item')[i].open,i)); }
 await tap(p.locator('.menu-close')); await W(400);
 T(dev+' menu si chiude', await p.evaluate(()=>!document.getElementById('menuOverlay').classList.contains('open') && !document.getElementById('menuOverlay').classList.contains('is-open')));
 // disclaimer
 await tap(p.locator('#sec-landing .l-btn')); await W(300);
 T(dev+' senza casella: avviso', await p.evaluate(()=>getComputedStyle(document.getElementById('termsError')).display!=='none'));
 // FORM
 await p.evaluate(()=>{document.getElementById('termsCheck').checked=true;}); await tap(p.locator('#sec-landing .l-btn')); await W(700);
 T(dev+' modulo si apre', await p.evaluate(()=>document.getElementById('sec-form').getBoundingClientRect().height>300 && getComputedStyle(document.getElementById('sec-form')).display!=='none'));
 const sub=p.locator('#sec-form .btn-primary').first(); await sub.scrollIntoViewIfNeeded(); await tap(sub); await W(900);
 const red=await p.evaluate(()=>document.querySelectorAll('#sec-form .is-invalid').length); T(dev+' modulo vuoto: 7 caselle rosse', red===7, 'rosse '+red);
 T(dev+' modulo vuoto: messaggio', await p.evaluate(()=>/fields are missing/.test(document.getElementById('sec-form').innerText)));
 const pn=await p.evaluate(()=>{ const c=document.getElementById('country'), l=document.getElementById('language'), o=[c.value,l.value]; c.value='italy'; l.value='english/ arabic'; const r=getProject(); c.value=o[0]; l.value=o[1]; return r.country+' | '+r.language; }); T(dev+' paese e lingua con la maiuscola', pn==='Italy | English / Arabic', pn);
 // MY REPORTS
 await open(p, BASE); await W(500); await p.evaluate(()=>openMyReports()); await W(500);
 T(dev+' My Reports si apre con la casella email', await p.evaluate(()=>!!document.querySelector('#sec-myreports input[type=email]') && document.querySelector('#sec-myreports input[type=email]').offsetParent!==null));
 // REPORT (the sample card's bars must have the report's colours)
 await open(p, BASE); await W(500);
 const cardBars=await p.evaluate(()=>[...document.querySelectorAll('.l-sheet-row .l-bar i')].map(i=>getComputedStyle(i).backgroundColor));
 const cardNum=await p.evaluate(()=>getComputedStyle(document.querySelector('.l-sheet-score .n')).fontSize);
 await tap(p.locator('.l-sheet')); await W(1300);
 const repBars=await p.evaluate(()=>[...document.querySelectorAll('#accordionMenu .acc-bar i')].map(i=>getComputedStyle(i).backgroundColor));
 T(dev+' barre della scheda come quelle del report', JSON.stringify(cardBars)===JSON.stringify(repBars), JSON.stringify(cardBars)+' vs '+JSON.stringify(repBars));
 const repNum=await p.evaluate(()=>getComputedStyle(document.querySelector('#overallScore .overall-num')).fontSize); T(dev+' voto della scheda grande come quello del report', cardNum===repNum, cardNum+' vs '+repNum);
 T(dev+' scheda Northbound apre il report', await p.evaluate(()=>document.getElementById('resultTitle').textContent.trim()==='Northbound'));
 if (dev==='tel') { const more=p.locator('#heroMore'); if(await more.count()){ await tap(more); await W(300); T(dev+' Read more apre il riassunto', await p.evaluate(()=>document.getElementById('resultSubtitle').classList.contains('is-open'))); } else T(dev+' Read more presente',false); }
 // areas: tap each, in order and back
 const trig=p.locator('#accordionMenu .accordion-trigger');
 for (const i of [0,1,2,3,4,2,0]) { await trig.nth(i).scrollIntoViewIfNeeded(); await W(200); await tap(trig.nth(i)); await W(1300);
  const st=await p.evaluate(i=>[...document.querySelectorAll('#accordionMenu .accordion-body')].map((b,k)=>b.classList.contains('open')?k:null).filter(x=>x!==null),i);
  T(dev+' area '+(i+1)+' si apre da sola', st.length===1&&st[0]===i, JSON.stringify(st));
  const bb=await barsBottom(p); const t=await p.evaluate(i=>document.getElementById('acc-trigger-'+i).getBoundingClientRect().top,i);
  T(dev+' area '+(i+1)+' titolo visibile sotto le barre', t>=bb-1 && t<400, 'titolo '+Math.round(t)+' barre '+Math.round(bb)); }
 await tap(trig.nth(0)); await W(800); T(dev+' area 1 si richiude', await p.evaluate(()=>!document.getElementById('acc-body-0').classList.contains('open')));
 // blocks inside an area
 await tap(trig.nth(1)); await W(1200);
 const inner=p.locator('#acc-body-1 details.rblock > summary'); const ni=await inner.count();
 for (let k=0;k<ni;k++){ await inner.nth(k).scrollIntoViewIfNeeded(); await tap(inner.nth(k)); await W(900); const o=await p.evaluate(()=>[...document.querySelectorAll('#acc-body-1 details.rblock')].map((d,k)=>d.open?k:null).filter(x=>x!==null)); T(dev+' area 2 blocco '+(k+1)+' si apre da solo',o.length===1&&o[0]===k,JSON.stringify(o)); }
 T(dev+' area 2 ha blocchi interni', ni>0, 'blocchi '+ni);
 await tap(trig.nth(1)); await W(600);
 // path steps
 const steps=p.locator('#accordionMenu details.path-step > summary'); const ns=await steps.count();
 for (let j=0;j<ns;j++){ await steps.nth(j).scrollIntoViewIfNeeded(); await W(200); await tap(steps.nth(j)); await W(1300);
  const o=await p.evaluate(()=>[...document.querySelectorAll('details.path-step')].map((d,k)=>d.open?k:null).filter(x=>x!==null)); T(dev+' passo '+(j+1)+' si apre da solo',o.length===1&&o[0]===j,JSON.stringify(o));
  const bb=await barsBottom(p); const t=await p.evaluate(j=>document.querySelectorAll('details.path-step > summary')[j].getBoundingClientRect().top,j); T(dev+' passo '+(j+1)+' titolo visibile',t>=bb-1&&t<400,'titolo '+Math.round(t)+' barre '+Math.round(bb));
  const full=await p.evaluate(j=>{const l=document.querySelectorAll('details.path-step')[j].querySelector('.path-line'); return !l || (getComputedStyle(l).display!=='none' && l.scrollHeight<=l.clientHeight+1);},j); T(dev+' passo '+(j+1)+' frase intera da aperto',full);
  if (j===1) { const cb=p.locator('details.path-step').nth(1).locator('.copy-btn').first(); if (await cb.count()){ await cb.scrollIntoViewIfNeeded(); await tap(cb); await W(300); const txt=await cb.textContent(); T(dev+' copia email', /Copied|Select/.test(txt), txt); } else T(dev+' bottone copia email presente', false); }
  // inner blocks of this step one at a time
 }
 T(dev+' Your path ha 5 passi', ns===5, 'passi '+ns);
 await tap(steps.nth(ns-1)); await W(500);
 // glossary
 const g=p.locator('.gl-term').first(); if (await g.count()){ const area=await p.evaluate(()=>{const t=document.querySelector('.gl-term'); const d=t.closest('details'); const a=t.closest('.accordion-body'); return d? 'd' : a? a.id : '';}); 
  await p.evaluate(()=>{const t=document.querySelector('.gl-term'); const a=t.closest('.accordion-body'); if(a&&!a.classList.contains('open')) toggleAccordion(Number(a.id.replace('acc-body-',''))); const d=t.closest('details'); if(d) d.open=true;}); await W(1200);
  await g.scrollIntoViewIfNeeded(); await tap(g); await W(400);
  const pop=await p.evaluate(()=>{const e=document.querySelector('.gl-pop'); if(!e||getComputedStyle(e).display==='none') return null; const r=e.getBoundingClientRect(); return {l:r.left,r:r.right,t:r.top,b:r.bottom,w:innerWidth,h:innerHeight};});
  T(dev+' glossario: la nuvoletta si apre dentro lo schermo', pop && pop.l>=0 && pop.r<=pop.w && pop.t>=0 && pop.b<=pop.h, JSON.stringify(pop));
  await p.keyboard.press('Escape'); await W(300); T(dev+' glossario: Esc la chiude', await p.evaluate(()=>{const e=document.querySelector('.gl-pop'); return !e||getComputedStyle(e).display==='none'||!e.isConnected||e.hidden||getComputedStyle(e).opacity==='0';}));
 } else T(dev+' glossario presente',false);
 // Sections index: every item
 await p.evaluate(()=>scrollTo(0,0)); await W(300);
 const items=await p.evaluate(()=>document.querySelectorAll('#areaNav .an-item').length);
 for (let k=0;k<items;k++){
  if (dev==='tel') { await p.evaluate(()=>{const a=document.querySelector('#accordionMenu .r-areas-h'); scrollTo(0,a.getBoundingClientRect().top+scrollY+300);}); await W(600); await tap(p.locator('#areaNav .an-top')); await W(400); }
  else { await p.evaluate(()=>{const a=document.querySelector('#accordionMenu .r-areas-h'); scrollTo(0,a.getBoundingClientRect().top+scrollY-50);}); await W(500); }
  const it=p.locator('#areaNav .an-item').nth(k); const label=(await it.textContent()).trim();
  await tap(it); await W(1500);
  const r=await p.evaluate(k=>{const b=document.querySelectorAll('#areaNav .an-item')[k]; let el, open;
    if (b.classList.contains('an-step')) { const j=+b.dataset.j; const d=document.querySelectorAll('details.path-step')[j]; el=d.querySelector('summary'); open=d.open; } else { const i=+b.dataset.i; el=document.getElementById('acc-trigger-'+i); open=document.getElementById('acc-body-'+i).classList.contains('open'); }
    return {t:el.getBoundingClientRect().top, open};},k);
  const bb=await barsBottom(p); T(dev+' indice "'+label+'" porta alla voce aperta', r.open && r.t>=bb-1 && r.t<400, 'titolo '+Math.round(r.t)+' barre '+Math.round(bb)+' aperta '+r.open);
 }
 T(dev+' indice ha 10 voci (5 aree + 5 passi)', items===10, 'voci '+items);
 // the report's side column moves exactly like the form's side steps (computer)
 if (dev==='pc') {
  const look=sel=>p.evaluate(sel=>{const e=document.querySelector(sel); if(!e) return null; const c=getComputedStyle(e); return [c.fontSize,c.color,c.paddingTop,c.paddingLeft,c.borderBottomWidth,c.boxShadow].join(' | ');},sel);
  await p.evaluate(()=>{const a=document.querySelector('.r-areas-h'); scrollTo(0,a.getBoundingClientRect().top+scrollY+150);}); await W(900);
  const repOn=await look('#areaNav .an-item.on'), repOff=await look('#areaNav .an-item:not(.on)');
  await p.evaluate(()=>{const a=document.getElementById('acc-trigger-4'); scrollTo(0,a.getBoundingClientRect().top+scrollY-250);});
  const fr=[]; for(let k=0;k<8;k++){ fr.push(await p.evaluate(()=>parseFloat(getComputedStyle([...document.querySelectorAll('#areaNav .an-item')][4]).paddingLeft))); await W(45); }
  T(dev+' colonna del report: lo scivolamento è animato', fr.some(v=>v>0.5&&v<11.5), fr.map(v=>v.toFixed(1)).join(' '));
  const f2=await ctx.newPage(); await open(f2, BASE); await f2.evaluate(()=>{document.getElementById('termsCheck').checked=true;onStartClick();}); await f2.waitForTimeout(700);
  const formOn=await f2.evaluate(()=>{const e=document.querySelector('#formSteps li.on'); const c=getComputedStyle(e); return [c.fontSize,c.color,c.paddingTop,c.paddingLeft,c.borderBottomWidth,c.boxShadow].join(' | ');});
  const formOff=await f2.evaluate(()=>{const e=document.querySelector('#formSteps li:not(.on)'); const c=getComputedStyle(e); return [c.fontSize,c.color,c.paddingTop,c.paddingLeft,c.borderBottomWidth,c.boxShadow].join(' | ');});
  await f2.close();
  T(dev+' colonna del report uguale ai passi del modulo', repOn===formOn && repOff===formOff, repOn+' vs '+formOn);
 }
 // the report title fills its column, also with "Reduce motion" on (25 Nov 2026:
 // a 0.01ms transition on every property left it at 108px instead of 166px)
 if (dev==='pc') for (const rm of ['no-preference','reduce']) {
  const c3=await b.newContext({viewport:{width:1280,height:800},reducedMotion:rm}); const q=await c3.newPage(); await open(q, BASE); await q.waitForTimeout(300); await q.evaluate(()=>showSampleReport()); await q.waitForTimeout(1500);
  const r=await q.evaluate(()=>{const t=document.getElementById('resultTitle'); const g=document.createRange(); g.selectNodeContents(t); return [Math.round(g.getBoundingClientRect().width), t.parentNode.clientWidth];});
  T(dev+' titolo del report largo quanto la colonna ('+rm+')', r[0]>=r[1]*0.95 && r[0]<=r[1]+1, r[0]+' su '+r[1]); await c3.close();
 }
 // every main button the size of the home's start button (Antonio, 26 Nov 2026)
 { const q=await ctx.newPage(); await open(q, BASE); const sz=[];
  const m=async(sel)=>sz.push(await q.evaluate(s=>{const e=document.querySelector(s); if(!e||!e.offsetParent) return s+' non visibile'; const b=e.getBoundingClientRect(); return Math.round(b.width)+'x'+Math.round(b.height)+' '+getComputedStyle(e).fontSize;},sel));
  await m('#sec-landing .l-btn');
  await q.evaluate(()=>{document.getElementById('termsCheck').checked=true; onStartClick();}); await q.waitForTimeout(600); await m('#sec-form .btn-primary');
  await q.evaluate(()=>showSampleReport()); await q.waitForTimeout(800); await q.evaluate(()=>{isSampleReport=false; renderFree(JSON.parse(JSON.stringify(lastResult)), lastProject.title); document.getElementById('againBtn').style.display='';}); await q.waitForTimeout(500);
  await m('#upgradeSection .btn-unlock'); await m('#againBtn');
  const leads=await q.evaluate(()=>[...document.querySelectorAll('.exec-card .exec-lead')].map(e=>getComputedStyle(e).color)); const txt=await q.evaluate(()=>getComputedStyle(document.querySelector('.exec-box-text')).color);
  T(dev+' rischio, opportunità e prossimo passo nel colore del testo', leads.length===3 && leads.every(c=>c===txt), leads.join(' | ')+' testo '+txt);
  await q.evaluate(()=>openMyReports()); await q.waitForTimeout(400); await m('#loginSubmitBtn');
  T(dev+' bottoni principali tutti uguali a quello della home', sz.every(x=>x===sz[0]), sz.join(' | ')); await q.close(); }
 // the loading title on one line on a computer, also with a long film name (Antonio, 26 Nov 2026)
 if (dev==='pc') { const c4=await b.newContext({viewport:{width:1280,height:720}}); const q4=await c4.newPage(); await open(q4, BASE);
  await q4.evaluate(()=>{ showOnly('sec-loading'); setLoadingTitle('Reading \u201CThe Last Shift at Saint Agnes\u201D'); }); await q4.waitForTimeout(500);
  const lt=await q4.evaluate(()=>{const t=document.getElementById('loadingTitle'); const r=document.createRange(); r.selectNodeContents(t); return [r.getClientRects().length, getComputedStyle(t).fontSize];});
  T(dev+' titolo del caricamento su una riga', lt[0]===1, lt[0]+' righe a '+lt[1]); await c4.close(); }
 // the report's side column fits short laptop screens without a scroll bar
 if (dev==='pc') for (const [w,h] of [[1366,657],[1280,600],[1440,700]]) {
  const c2=await b.newContext({viewport:{width:w,height:h}}); const q=await c2.newPage(); await open(q, BASE); await q.evaluate(()=>showSampleReport()); await q.waitForTimeout(900);
  await q.evaluate(()=>{const a=document.querySelector('.r-areas-h'); scrollTo(0,a.getBoundingClientRect().top+scrollY+400);}); await q.waitForTimeout(700);
  const r=await q.evaluate(()=>{const n=document.getElementById('areaNav'); return [n.scrollHeight, n.clientHeight];});
  T(dev+' colonna del report intera su schermo '+w+'x'+h, r[0]<=r[1]+1, 'alta '+r[0]+' spazio '+r[1]);
  await q.evaluate(()=>scrollTo(0,document.body.scrollHeight)); await q.waitForTimeout(500);
  const ov=await q.evaluate(()=>{const n=document.getElementById('areaNav').getBoundingClientRect(), f=document.querySelector('#sec-results .r-foot').getBoundingClientRect(); return [Math.round(n.bottom), Math.round(f.top)];});
  T(dev+' colonna del report sopra il piè di pagina '+w+'x'+h, ov[0]<=ov[1], 'colonna finisce a '+ov[0]+', piè di pagina da '+ov[1]); await c2.close();
 }
 // PDF
 await p.evaluate(()=>scrollTo(0,document.body.scrollHeight)); await W(400);
 try { const [dl]=await Promise.all([p.waitForEvent('download',{timeout:30000}), tap(p.locator('.pdf-row button').first())]); const f=OUT+dev+'_report.pdf'; await dl.saveAs(f); const sz=fs.statSync(f).size; T(dev+' PDF si scarica',sz>100000,sz+' byte'); } catch(e){ T(dev+' PDF si scarica',false,e.message.slice(0,60)); }
 // "Report a problem", on a real full report only (the sample has no report to report against)
 { const q=await ctx.newPage(); await open(q, BASE); await q.evaluate(()=>showSampleReport()); await q.waitForTimeout(900);
  T(dev+' esempio: niente Report a problem', await q.evaluate(()=>document.getElementById('helpBtn').hidden));
  await q.evaluate(()=>{ isSampleReport=false; renderFull(lastResult, lastProject.title); }); await q.waitForTimeout(900);
  await q.evaluate(()=>document.querySelector('.pdf-card').scrollIntoView({block:'center'})); await q.waitForTimeout(400);
  await tap(q.locator('#helpBtn')); await q.waitForTimeout(300);
  T(dev+' Report a problem apre il modulo', await q.evaluate(()=>!document.getElementById('issuePanel').hidden && document.getElementById('helpBtn').getAttribute('aria-expanded')==='true'));
  await tap(q.locator('#helpBtn')); await q.waitForTimeout(300);
  T(dev+' Report a problem si richiude', await q.evaluate(()=>document.getElementById('issuePanel').hidden));
  await q.close(); }
 T(dev+' nessun errore JS', errs.length===0, errs.join(' | ').slice(0,200));
 // ROADMAP
 const r2=await ctx.newPage(); const e2=[]; r2.on('pageerror',e=>e2.push(e.message)); await open(r2, BASE+'roadmap/'); await r2.waitForTimeout(600);
 const cbx=r2.locator('input[type=checkbox]'); const nc=await cbx.count(); T(dev+' roadmap 49 lavori', nc===49, nc);
 await cbx.nth(0).check(); await r2.reload(); await r2.waitForTimeout(500); T(dev+' roadmap la spunta resta dopo ricarica', await cbx.nth(0).isChecked()); await cbx.nth(0).uncheck();
 const det=r2.locator('details > summary'); const nd=await det.count(); let dok=0; for(let i=0;i<nd;i++){ await det.nth(i).scrollIntoViewIfNeeded(); await (dev==='tel'?det.nth(i).tap():det.nth(i).click()); await r2.waitForTimeout(250); if(await r2.evaluate(i=>document.querySelectorAll('details')[i].open,i)) dok++; }
 T(dev+' roadmap tendine si aprono', dok===nd, dok+'/'+nd); T(dev+' roadmap nessun errore JS', e2.length===0, e2.join('|'));
 // 404, privacy, terms links
 const r3=await ctx.newPage(); const res=await open(r3, BASE+'pagina-che-non-esiste'); T(dev+' 404 mostra la pagina', (await r3.content()).includes('<h1'));
 await ctx.close();
}
console.log('PROVE PASSATE',ok,'| FALLITE',ko.length); ko.forEach(k=>console.log('  NO:',k)); process.exitCode=ko.length?1:0;
await b.close();})();
