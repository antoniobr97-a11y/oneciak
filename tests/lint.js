// Fast check of the source against the design rules of CLAUDE.md that a
// machine can check better than a person (seconds, no browser). Each finding
// names file and line. Exit code 1 if anything is found.
// Run: node tests/lint.js
const fs = require('fs'), path = require('path');
const root = path.join(__dirname, '..');
const files = ['index.html', '404.html', 'privacy.html', 'terms.html', 'roadmap/index.html', 'roadmap/roadmap.css', 'netlify/functions/_util/email.js'];
const OFF_SCALE = new Set(['10', '10.5', '11', '11.5', '12', '12.5', '13.5', '14.5', '15.5', '16.5', '17', '19', '21', '22']);
let found = 0;
const say = (f, n, msg, line) => { found++; console.log(`${f}:${n}  ${msg}\n    ${line.trim().slice(0, 140)}`); };

for (const f of files) {
  const src = fs.readFileSync(path.join(root, f), 'utf8');
  const lines = src.split('\n');
  // where CSS lives: whole .css files, <style> blocks in html, nothing in .js
  let inStyle = f.endsWith('.css'), inComment = false, media = [];  // media: stack of open @media conditions with their depth
  let depth = 0;
  lines.forEach((raw, i) => {
    const n = i + 1;
    if (/<style[^>]*>/.test(raw)) inStyle = true;
    // strip comments for the checks (CSS /* */, JS //, HTML <!-- -->)
    let line = raw;
    if (inComment) { const e = line.indexOf('*/'); if (e < 0) return; line = line.slice(e + 2); inComment = false; }
    line = line.replace(/\/\*.*?\*\//g, '').replace(/<!--.*?-->/g, '');
    const s = line.indexOf('/*'); if (s >= 0) { line = line.slice(0, s); inComment = true; }
    if (!inStyle) line = line.replace(/(^|[^:'"\\])\/\/.*$/, '$1');

    // 1. icons are drawn: no text arrows or crosses in what the page shows
    if (/[←→✕×✓]|&larr;|&rarr;|&times;/.test(line)) say(f, n, 'simbolo di testo al posto di un\'icona disegnata (.ic)', raw);
    // 1b. black and white only (Antonio, 26 Nov 2026): every colour a grey with R=G=B, anywhere in the file
    for (const m of line.matchAll(/(?<![\w&])(?:#|%23)([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![\w-])/g)) { const h = m[1].length === 3 ? m[1].replace(/./g, c => c + c) : m[1]; if (!(h.slice(0, 2) === h.slice(2, 4) && h.slice(2, 4) === h.slice(4, 6))) say(f, n, `colore non grigio (#${m[1]})`, raw); }
    for (const m of line.matchAll(/rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/g)) if (!(m[1] === m[2] && m[2] === m[3])) say(f, n, `colore non grigio (rgb ${m[1]} ${m[2]} ${m[3]})`, raw);
    for (const m of line.matchAll(/set(?:Text|Fill|Draw)Color\((\d+),\s*(\d+),\s*(\d+)\)/g)) if (!(m[1] === m[2] && m[2] === m[3])) say(f, n, 'colore non grigio nel PDF', raw);
    // 2. long dashes never reach the page
    if (/—|&mdash;/.test(line) && !/noDash|replace\(/.test(line)) say(f, n, 'trattino lungo', raw);
    if (inStyle) {
      // 3. no pills
      if (/border-radius:\s*(999|9999)px/.test(line)) say(f, n, 'bottone o etichetta a pillola (usare 10px)', raw);
      // 4. no transition: all, no scale(0)
      if (/transition:\s*all\b/.test(line)) say(f, n, 'transition: all', raw);
      if (/scale\(0\)/.test(line)) say(f, n, 'scale(0)', raw);
      // 5. one type scale, no half pixels
      for (const m of line.matchAll(/font-size:\s*([\d.]+)px/g)) if (OFF_SCALE.has(m[1])) say(f, n, `misura del carattere fuori scala (${m[1]}px)`, raw);
      // 6. hover only with a real mouse: track the @media blocks we are inside
      const mm = line.match(/@media([^{]*)\{/);
      if (mm) media.push({ cond: mm[1], depth });
      const hoverOk = media.some(x => /hover:\s*hover/.test(x.cond) && /pointer:\s*fine/.test(x.cond)) || /@media[^{]*hover:\s*hover[^{]*pointer:\s*fine/.test(line) || /@media\s*\(hover:hover\)\s*and\s*\(pointer:fine\)/.test(line);
      if (/:hover/.test(line) && !hoverOk) say(f, n, ':hover fuori da @media (hover: hover) and (pointer: fine)', raw);
      for (const ch of line) { if (ch === '{') depth++; else if (ch === '}') { depth--; while (media.length && depth <= media[media.length - 1].depth) media.pop(); } }
    }
    if (/<\/style>/.test(raw)) { inStyle = false; media = []; depth = 0; }
  });
}
console.log(found ? `REGOLE VIOLATE: ${found}` : 'CODICE A POSTO (simboli, trattini, pillole, transizioni, misure, hover)');
process.exitCode = found ? 1 : 0;
