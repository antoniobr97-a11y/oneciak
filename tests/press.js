// Press feedback of every button, link-button, icon and row, phone and computer:
// buttons 0.97, rows and cards 0.99, all 160ms on --ease (Antonio, 24 Nov 2026:
// "che abbiano tutte la stessa animazione quando clicchi i tasti"). Words in a
// sentence (glossary, citations) are listed as "testo" and not scaled.
// Run: NODE_PATH=/opt/node22/lib/node_modules node tests/press.js [url]
const { chromium, devices } = require('playwright');
const BASE=process.argv[2]||'http://localhost:8143/';
(async()=>{ const b=await chromium.launch(); const rows={};
for (const [dev,opt] of [['tel',{...devices['iPhone 13']}],['pc',{viewport:{width:1280,height:900}}]]) {
 const ctx=await b.newContext(opt); const p=await ctx.newPage(); const cdp=await ctx.newCDPSession(p); await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
 const views=[['home',async()=>{await p.goto(BASE);}],['menu',async()=>{await p.goto(BASE); await p.evaluate(()=>openMenu());}],
  ['modulo',async()=>{await p.goto(BASE); await p.evaluate(()=>{document.getElementById('termsCheck').checked=true;onStartClick();});}],
  ['myreports',async()=>{await p.goto(BASE); await p.evaluate(()=>openMyReports());}],
  ['report',async()=>{await p.goto(BASE); await p.evaluate(()=>showSampleReport()); await p.waitForTimeout(700); await p.evaluate(()=>{document.querySelectorAll('#sec-results details').forEach(d=>d.open=true); for(let i=0;i<5;i++){const x=document.getElementById('acc-body-'+i); x&&x.classList.add('open');} document.getElementById('areaNav').classList.add('is-on','is-open');});}],
  ['roadmap',async()=>{await p.goto(BASE+'roadmap/');}],['privacy',async()=>{await p.goto(BASE+'privacy.html');}]];
 for (const [v,go] of views) { await go(); await p.waitForTimeout(1500);
  const list=await p.evaluate(()=>{ const out=[]; document.querySelectorAll('button, a, summary, [role=button]').forEach((e,i)=>{ if(!e.getClientRects().length) return; const cs=getComputedStyle(e); if(cs.display==='inline'&&e.tagName==='A') return; e.setAttribute('data-pk',i); out.push(i); }); return out; });
  const doc=await cdp.send('DOM.getDocument',{depth:-1});
  for (const i of list) { const q=await cdp.send('DOM.querySelector',{nodeId:doc.root.nodeId,selector:`[data-pk="${i}"]`}).catch(()=>null); if(!q||!q.nodeId) continue;
   await cdp.send('CSS.forcePseudoState',{nodeId:q.nodeId,forcedPseudoClasses:['active']}); await p.waitForTimeout(350);
   const r=await p.evaluate(i=>{const e=document.querySelector(`[data-pk="${i}"]`); const cs=getComputedStyle(e); const m=cs.transform.match(/matrix\(([^,]+)/); const props=cs.transitionProperty.split(',').map(s=>s.trim()); const k=props.findIndex(x=>x==='transform'||x==='all'); const dur=k>=0?cs.transitionDuration.split(',')[k].trim():'nessuna'; const ease=k>=0?cs.transitionTimingFunction.split(/,(?![^(]*\))/)[k].trim():'-';
     const cls=(typeof e.className==='string'&&e.className?'.'+e.className.trim().split(/\s+/)[0]:e.tagName.toLowerCase()); return {cls, txt:(e.textContent||'').trim().replace(/\s+/g,' ').slice(0,22), scale:m?(+m[1]).toFixed(2):'1.00', dur, ease:ease.replace('cubic-bezier(0.23, 1, 0.32, 1)','--ease')};},i);
   await cdp.send('CSS.forcePseudoState',{nodeId:q.nodeId,forcedPseudoClasses:[]});
   const key=r.cls+' | scala '+r.scale+' | '+r.dur+' '+r.ease; (rows[key]=rows[key]||new Set()).add(v+':'+r.txt); }
 }
 await ctx.close(); }
let bad=0; Object.keys(rows).sort().forEach(k=>{ const okRule=/scala 0\.9[79] \| 0\.16s --ease/.test(k); const words=/^\.gl-term|^a \| scala 1\.00/.test(k); if(!okRule&&!words) bad++; console.log((okRule?'ok   ':words?'testo':'NO   ')+' '+k.padEnd(66),[...rows[k]].slice(0,3).join(' ; ')); });
console.log(bad?('DIVERSI: '+bad):'TUTTI UGUALI (0.97 bottoni, 0.99 righe, 160ms --ease)'); process.exitCode=bad?1:0;
await b.close();})();
