// The design rules of CLAUDE.md on every view, phone and computer, 3 schemes:
// fonts (only Geist and Carlito), :active on every clickable (text links,
// form labels and inputs are listed but are not buttons), button corners
// (10px), uppercase labels, contrast of text on flat backgrounds (4.5:1, 3:1
// for big titles). Run: NODE_PATH=/opt/node22/lib/node_modules node tests/rules.js [url]
// On a local python server the 404 page is python's own (Times New Roman).
const { chromium, devices } = require('playwright');
const BASE=process.argv[2]||'http://localhost:8143/';
(async()=>{ const b=await chromium.launch(); const found={};
const add=(k,v)=>{ (found[k]=found[k]||new Set()).add(v); };
for (const [dev,opt] of [['tel',{...devices['iPhone 13']}],['pc',{viewport:{width:1280,height:900}}]]) for (const sc of ['light','dark','no-preference']) {
 const ctx=await b.newContext({...opt,colorScheme:sc}); const p=await ctx.newPage(); const cdp=await ctx.newCDPSession(p);
 await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
 const views=[['home',async()=>{await p.goto(BASE);}],['menu',async()=>{await p.goto(BASE); await p.evaluate(()=>{openMenu();document.querySelectorAll('.menu-faq-item').forEach(d=>d.open=true);});}],
  ['modulo',async()=>{await p.goto(BASE); await p.evaluate(()=>{document.getElementById('termsCheck').checked=true;onStartClick();});}],
  ['myreports',async()=>{await p.goto(BASE); await p.evaluate(()=>openMyReports());}],
  ['report',async()=>{await p.goto(BASE); await p.evaluate(()=>{showSampleReport();}); await p.waitForTimeout(700); await p.evaluate(()=>{document.querySelectorAll('#sec-results details').forEach(d=>d.open=true); for(let i=0;i<5;i++){const x=document.getElementById('acc-body-'+i); x&&x.classList.add('open');}});}],
  ['roadmap',async()=>{await p.goto(BASE+'roadmap/'); await p.evaluate(()=>document.querySelectorAll('details').forEach(d=>d.open=true));}],
  ['privacy',async()=>{await p.goto(BASE+'privacy.html');}],['terms',async()=>{await p.goto(BASE+'terms.html');}],['404',async()=>{await p.goto(BASE+'nope');}]];
 for (const [v,go] of views) { await go(); await p.waitForTimeout(600);
  const r=await p.evaluate(()=>{ const out={fonts:[],corners:[],upper:[],contrast:[],clickables:[]};
   const lum=c=>{const m=c.match(/[\d.]+/g).map(Number); const f=x=>{x/=255;return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4)}; return [0.2126*f(m[0])+0.7152*f(m[1])+0.0722*f(m[2]), m[3]===undefined?1:m[3]];};
   const bgOf=e=>{ while(e){ const cs=getComputedStyle(e); if(cs.backgroundImage!=='none') return null; const c=cs.backgroundColor; const a=c.match(/[\d.]+/g).map(Number); if(a.length<4||a[3]>=0.99) return c; if(a[3]>0.05) return null; e=e.parentElement; } return 'rgb(255,255,255)'; };
   document.querySelectorAll('body *').forEach((e,idx)=>{ if(!e.getClientRects().length) return; const cs=getComputedStyle(e); if(cs.visibility==='hidden'||parseFloat(cs.opacity)===0) return;
    const txt=[...e.childNodes].some(t=>t.nodeType===3&&t.textContent.trim());
    if(txt){ out.fonts.push(cs.fontFamily.split(',')[0].replace(/"/g,'')); if(cs.textTransform==='uppercase') out.upper.push((e.className||e.tagName)+': '+e.textContent.trim().slice(0,30));
     const bg=bgOf(e); if(bg){ const [l1,a1]=lum(cs.color); const [l2]=lum(bg); if(a1>=0.99){ const ratio=(Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05); const big=parseFloat(cs.fontSize)>=24||(parseFloat(cs.fontSize)>=18.6&&+cs.fontWeight>=700); if(ratio<(big?3:4.5)) out.contrast.push((e.className||e.tagName)+' "'+e.textContent.trim().slice(0,25)+'" '+ratio.toFixed(2)); } } }
    if(e.matches('button, a, summary, [role=button], label[for], input[type=checkbox]')){ e.setAttribute('data-ck', idx); out.clickables.push(idx);
     if(e.matches('button')&&!e.matches('.l-sheet')&&(cs.borderStyle!=='none'&&parseFloat(cs.borderWidth)>0 || !/rgba\(0, 0, 0, 0\)|transparent/.test(cs.backgroundColor))){ const r=cs.borderRadius; if(r!=='10px') out.corners.push((e.className||e.tagName)+' "'+e.textContent.trim().slice(0,20)+'" '+r); } }
   });
   return out; });
  r.fonts.forEach(f=>add('font '+f,v)); r.corners.forEach(c=>add('angoli non 10px',v+': '+c)); r.upper.forEach(u=>add('maiuscolo',v+': '+u)); r.contrast.forEach(c=>add('contrasto basso ('+sc+')',dev+' '+v+': '+c));
  // :active check through CDP on each clickable
  if (sc==='dark') { const doc=await cdp.send('DOM.getDocument',{depth:-1}); for (const idx of r.clickables) { const q=await cdp.send('DOM.querySelector',{nodeId:doc.root.nodeId,selector:`[data-ck="${idx}"]`}).catch(()=>null); if(!q||!q.nodeId) continue;
    const before=await p.evaluate(i=>{const e=document.querySelector(`[data-ck="${i}"]`); return getComputedStyle(e).transform;},idx);
    await cdp.send('CSS.forcePseudoState',{nodeId:q.nodeId,forcedPseudoClasses:['active']});
    await p.waitForTimeout(250); // let the 160ms press transition finish
    const after=await p.evaluate(i=>{const e=document.querySelector(`[data-ck="${i}"]`); const cs=getComputedStyle(e); return [cs.transform, (e.className||e.tagName)+' "'+(e.textContent||'').trim().slice(0,25)+'"'];},idx);
    await cdp.send('CSS.forcePseudoState',{nodeId:q.nodeId,forcedPseudoClasses:[]});
    if(after[0]===before) add('senza :active',dev+' '+v+': '+after[1]); } }
 }
 await ctx.close(); }
for (const k of Object.keys(found)) { console.log('== '+k+' ('+found[k].size+')'); [...found[k]].slice(0,400).forEach(x=>console.log('   '+x)); }
await b.close();})();
