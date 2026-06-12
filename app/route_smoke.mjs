// LifeCast Cockpit pre-deploy gate: render every route in a DOM shim.
// Usage: node app/route_smoke.mjs <payload.json>   (payload = /api/content, may include "ai")
// Asserts every routed function is defined, then renders all routes non-empty.
import { readFileSync } from 'fs';
const payload = JSON.parse(readFileSync(process.argv[2] || '/tmp/content_test.json', 'utf8'));
const html = readFileSync(new URL('./static/index.html', import.meta.url), 'utf8');
const js = html.match(/<script>([\s\S]*)<\/script>/)[1];
const defined = new Set([...js.matchAll(/(?:async )?function (\w+)\(/g)].map(m => m[1]));
const needed = ['landing','pocPage','personasPage','termsPage','filePage','governancePage','governanceShowcase',
  'blockPage','flowPage','cardPage','personaPage','loadRunControl','triggerRun','askOverseer','loadGov','shell','route','aiPage'];
const missing = needed.filter(f => !defined.has(f));
if (missing.length) { console.error('MISSING FUNCTIONS:', missing); process.exit(1); }
let rootEl = { innerHTML: '' };
globalThis.window = { addEventListener(){} };
globalThis.document = { getElementById: id => id === 'root' ? rootEl : { innerHTML: '', value: '', textContent: '' } };
globalThis.fetch = async url => ({ ok: true, json: async () => {
  const u = String(url);
  if (u.includes('governance')) return { runs: [], inventory: [], error: null, scope: 's' };
  if (u.includes('file/')) return { title:'t', note:'n', name:'f', modified:'m', size_kb:1, columns:['A'], rows:[['1']], keys:[], volume_url:'u' };
  if (u.includes('runcontrol')) return { job: null, gate: null };
  return payload; } });
globalThis.confirm = () => false; globalThis.setTimeout = () => {};
globalThis.location = { hash: '' };
(0, eval)(js + '\n;globalThis.__route = route;');
await new Promise(r => setImmediate(r)); // page init sets DATA
const routes = ['#/','#/destination','#/ai','#/flow/model-point-feed','#/flow/model-point-feed/oldnew',
  '#/flow/model-point-feed/manage','#/block/assumptions','#/block/scenarios','#/block/modelling',
  '#/block/results','#/block/roadmap','#/governance','#/governance/record','#/terms','#/poc',
  '#/personas','#/p/actuary','#/file/mpf'];
let fails = 0;
for (const h of routes) {
  location.hash = h; rootEl.innerHTML = '';
  try {
    const r = globalThis.__route(); if (r?.then) await r; await new Promise(res => setImmediate(res));
    const r2 = globalThis.__route(); if (r2?.then) await r2; await new Promise(res => setImmediate(res));
    if (rootEl.innerHTML.length < 500) throw new Error('only ' + rootEl.innerHTML.length + ' chars');
    console.log('OK  ', h);
  } catch (e) { fails++; console.log('FAIL', h, '->', e.message); }
}
process.exit(fails ? 1 : 0);
