// Screenshot / bench / clip helper for the water prototypes (uses the lead's GPU browser on CDP 9310, new tabs only).
// node shot.mjs shot  <url> <out.jpg> <WxH> [waitMs]
// node shot.mjs bench <url> [WxH]
// node shot.mjs clip  <url> <out.webm> <WxH> <seconds>
import { createRequire } from 'module';
import fs from 'fs';
const require = createRequire('/home/agent-tom/Desktop/volcanospa/tools/package.json');
const { chromium } = require('playwright-core');
const [mode, url, a, b, c] = process.argv.slice(2);
const browser = await chromium.connectOverCDP('http://127.0.0.1:9310');
const ctx = browser.contexts()[0] ?? await browser.newContext();
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page); await cdp.send('Network.enable'); await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });   // always load the files as they are on disk
const logs = [];
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') logs.push(`[${m.type()}] ${m.text()}`); });
page.on('pageerror', e => logs.push('[pageerror] ' + e.message));
try {
  const size = (mode === 'bench' ? a : b) ?? '1600x900';
  const [w, h] = size.split('x').map(Number);
  await page.setViewportSize({ width: w, height: h });
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__app || window.__ready, null, { timeout: 60000 });
  if (mode === 'shot') {
    await page.waitForTimeout(Number(c ?? 2500));
    const buf = await page.screenshot({ type: 'jpeg', quality: 88 });
    fs.writeFileSync(a, buf);
    console.log(JSON.stringify(await page.evaluate(() => window.__stats ? window.__stats() : document.getElementById('stats')?.textContent)));
  } else if (mode === 'bench') {
    await page.waitForTimeout(3000);
    const st = await page.evaluate(() => window.__stats());
    const r = await page.evaluate(() => window.__app.bench({ w: 1600, h: 900, n: 60 }));
    const r4k = await page.evaluate(() => window.__app.bench({ w: 3840, h: 2160, n: 30, groups: false }));
    console.log(JSON.stringify({ live: st, b1600: r, b4k: r4k.total }));
  } else if (mode === 'bench4k') {
    await page.waitForTimeout(3000);
    const runs = [];
    for (let k = 0; k < 3; k++) runs.push(await page.evaluate(() => window.__app.bench({ w: 3840, h: 2160, n: 60 })));
    const med = {}; for (const key of Object.keys(runs[0])) { const v = runs.map(r => r[key]); med[key] = typeof v[0] === 'number' ? v.sort((x, y) => x - y)[1] : v[0]; }
    console.log(JSON.stringify(med));
  } else if (mode === 'clip') {
    await page.waitForTimeout(2500);
    const secs = Number(c ?? 6);
    const b64 = await page.evaluate(async (secs) => {
      const cv = document.querySelector('canvas'); const st = cv.captureStream(60);
      const rec = new MediaRecorder(st, { mimeType: 'video/webm;codecs=vp9', videoBitsPerSecond: 16e6 });
      const chunks = []; rec.ondataavailable = e => chunks.push(e.data);
      const done = new Promise(r => rec.onstop = r); rec.start(); await new Promise(r => setTimeout(r, secs * 1000)); rec.stop(); await done;
      const buf = await new Blob(chunks).arrayBuffer(); let s = ''; const u = new Uint8Array(buf);
      for (let i = 0; i < u.length; i += 32768) s += String.fromCharCode.apply(null, u.subarray(i, i + 32768));
      return btoa(s);
    }, secs);
    fs.writeFileSync(a, Buffer.from(b64, 'base64'));
  }
} finally {
  if (logs.length) console.log(logs.slice(0, 30).map(l => l.length > 600 ? l.split("\n").filter(x => /ERROR|Shader Error|pageerror|^>/.test(x)).join("\n") : l).join("\n"));
  await page.close();
  await browser.close();
}
