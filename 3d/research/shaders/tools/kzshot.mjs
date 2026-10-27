// Drive the shader demo in the lead's shared GPU browser (CDP 9310, one new tab, closed at the end).
// node 3d/research/shaders/tools/kzshot.mjs <job.json>
// job: { base: url, shots: [{ q: "scene=cave&...", vp: [w,h], set: {...}, out: "file.jpg", bench: n, frames: [...] , framesOut: "dir/%04d.jpg" }] }
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from '/home/agent-tom/Desktop/volcanospa/tools/node_modules/playwright-core/index.mjs';

const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const browser = await chromium.connectOverCDP('http://127.0.0.1:9310');
const ctx = browser.contexts()[0] ?? await browser.newContext();
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
const logs = [];
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') logs.push(m.type() + ': ' + m.text().slice(0, 4000)); });
page.on('pageerror', (e) => logs.push('pageerror: ' + e.message));
const results = [];
let curUrl = null, curVp = null, lastQ = '';
try {
  for (const s of job.shots) {
    const vp = s.vp || curVp || [1600, 900];
    if (!curVp || vp[0] !== curVp[0] || vp[1] !== curVp[1]) { await page.setViewportSize({ width: vp[0], height: vp[1] }); curVp = vp; }
    if (s.q != null) lastQ = s.q;
    const url = job.base + '?' + lastQ + '&clean=1';
    if (url !== curUrl) {
      await page.goto(url, { waitUntil: 'load' });
      try { await page.waitForFunction(() => window.KZDEMO?.ready === true, null, { timeout: job.timeout || 60000 }); }
      catch (e) { console.log('NOT READY', await page.evaluate(() => document.getElementById('err')?.textContent)); console.log([...new Set(logs)].slice(0, 20).join('\n')); throw e; }
      curUrl = url;
      await page.evaluate(() => window.KZDEMO.set({}));
    }
    const r = { out: s.out, tag: s.tag };
    if (s.set) r.set = await page.evaluate((o) => window.KZDEMO.set(o), s.set);
    if (s.bench) r.bench = await page.evaluate((n) => window.KZDEMO.bench(n), s.bench);
    if (s.out) {
      await page.waitForTimeout(250);
      fs.mkdirSync(path.dirname(s.out), { recursive: true });
      await page.screenshot({ scale: 'css', path: s.out, type: s.out.endsWith('.png') ? 'png' : 'jpeg', quality: s.out.endsWith('.png') ? undefined : 90 });
    }
    if (s.frames) {
      fs.mkdirSync(path.dirname(s.framesOut), { recursive: true });
      for (let i = 0; i < s.frames.length; i++) {
        const f = s.frames[i];
        await page.evaluate((f) => window.KZDEMO.pose(f.pos, f.look, f.time), f);
        await page.screenshot({ scale: 'css', path: s.framesOut.replace('%04d', String(i).padStart(4, '0')), type: 'jpeg', quality: 88 });
      }
    }
    results.push(r);
    console.log(JSON.stringify(r));
  }
} finally {
  await page.close();
  await browser.close();
}
if (logs.length) console.log('LOGS\n' + [...new Set(logs)].slice(0, 30).join('\n'));
