// Render the preview soundscapes with the real engine in the lead's GPU browser (CDP 9310), one new tab, closed after.
// node 3d/research/sound/tools/render_previews.mjs [render|bench|all] [scenario ...]
import { createRequire } from 'node:module';
import { writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..', '..', '..');
const require = createRequire(join(root, 'tools', 'package.json'));
const { chromium } = require('playwright-core');

const mode = process.argv[2] || 'all';
const only = process.argv.slice(3);
const outDir = join(here, '..', 'previews');
mkdirSync(outDir, { recursive: true });
const results = { when: new Date().toISOString(), renders: [], bench: [] };

const browser = await chromium.connectOverCDP('http://127.0.0.1:9310');
const ctx = browser.contexts()[0] ?? await browser.newContext();
const page = await ctx.newPage();
{ const cdp = await ctx.newCDPSession(page); await cdp.send('Network.setCacheDisabled', { cacheDisabled: true }); } // always load the current files
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.type(), m.text()); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
try {
  await page.goto('http://127.0.0.1:8742/3d/research/sound/demo/preview.html', { waitUntil: 'load' });
  await page.waitForFunction('window.KZ_READY === true', null, { timeout: 30000 });
  results.ua = await page.evaluate('navigator.userAgent');
  results.bake = await page.evaluate('KZ.bake(48000)');
  console.log('bake', JSON.stringify({ ms: Math.round(results.bake.ms), MB: results.bake.MB.toFixed(1) }));
  const names = only.length ? only : await page.evaluate("(async () => Object.keys((await import('./js/scenarios.js')).SCENARIOS))()");
  if (mode === 'render' || mode === 'all') {
    for (const n of names) {
      const r = await page.evaluate(`KZ.render(${JSON.stringify(n)})`);
      writeFileSync(join(outDir, `${n}.wav`), Buffer.from(r.b64, 'base64'));
      delete r.b64; results.renders.push(r);
      console.log('render', n, Math.round(r.wallMs), 'ms wall; update', Math.round(r.updateMs), 'ms; clip>1', r.clipOver1, JSON.stringify(r.stats));
    }
  }
  if (mode === 'bench' || mode === 'all') {
    const cases = [
      ['p4_kawagiri', 15, {}], ['p4_kawagiri', 15, { panning: 'HRTF' }], ['p4_kawagiri', 15, { reverb: false }],
      ['p6_wave_grotto', 12, {}], ['p6_wave_grotto', 12, { panning: 'HRTF' }],
      ['p5_thunder_curtain', 13, {}], ['p2_mist_corridor', 7, {}], ['p3_obsidian_mirror', 15, {}], ['p8_magma_heartbeat', 22, {}],
      ['p7_geyser', 2, { fire: 'geyser_big' }], ['p4_kawagiri', 15, { maxVoices: 24 }], ['p4_kawagiri', 15, { maxVoices: 24, panning: 'HRTF' }],
    ];
    for (const [n, t, extra] of cases) {
      const runs = [];
      for (let i = 0; i < 3; i++) runs.push(await page.evaluate(`KZ.bench(${JSON.stringify(n)}, ${t}, 10, ${JSON.stringify(extra)})`));
      runs.sort((a, b) => a.wallMs - b.wallMs); const r = runs[1]; r.extra = extra; r.runsMs = runs.map((q) => Math.round(q.wallMs));
      results.bench.push(r);
      console.log('bench', n, JSON.stringify(extra), r.loadPct.toFixed(2) + '% of realtime (median of 3)', 'voices', r.stats.realVoices, 'conv', r.stats.convolvers);
    }
  }
} finally {
  await page.close();
  await browser.close(); // disconnects only; the shared browser keeps running
}
writeFileSync(join(here, '..', 'previews', 'render_results.json'), JSON.stringify(results, null, 1));
