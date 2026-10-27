// Screenshot / stats / bench / clip helper for the mist prototypes. Uses the lead's GPU browser on CDP 9310
// (new tab only, closed afterwards).
//   node shot.mjs shot  <url> <out.jpg> <WxH> [waitMs]
//   node shot.mjs stats <url> <WxH> [waitMs]             -> prints __stats() JSON (+ console errors)
//   node shot.mjs bench <url> <WxH> [waitMs]             -> GPU ms/frame with mist on/off at 1600x900 and 3840x2160
//   node shot.mjs clip  <url> <out.webm> <WxH> <seconds> [waitMs]
//   node shot.mjs eval  <url> <WxH> <js> [waitMs]
import { createRequire } from 'module';
import fs from 'fs';
const require = createRequire('/home/agent-tom/Desktop/volcanospa/tools/package.json');
const { chromium } = require('playwright-core');
const [mode, url, a, b, c, d] = process.argv.slice(2);
const browser = await chromium.connectOverCDP('http://127.0.0.1:9310');
const ctx = browser.contexts()[0] ?? await browser.newContext();
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page); await cdp.send('Network.enable'); await cdp.send('Network.setCacheDisabled', { cacheDisabled: true }); // always load files as on disk
if (process.env.THROTTLE) await cdp.send('Emulation.setCPUThrottlingRate', { rate: Number(process.env.THROTTLE) }); // phone-CPU estimate
const logs = [];
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') logs.push(`[${m.type()}] ${m.text()}`); });
page.on('pageerror', e => logs.push('[pageerror] ' + e.message));
try {
  const size = (mode === 'shot' || mode === 'clip' || mode === 'frames') ? b : a;
  const [w, h] = (size ?? '1600x900').split('x').map(Number);
  await page.setViewportSize({ width: w, height: h });
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__app && window.__stats && window.__stats().ready, null, { timeout: 60000 }).catch(async e => { logs.push('[timeout] ' + JSON.stringify(await page.evaluate(() => ({ app: !!window.__app, st: window.__stats?.() })).catch(() => 'eval failed'))); throw e; });
  if (mode === 'shot') {
    await page.waitForTimeout(Number(c ?? 3000));
    fs.writeFileSync(a, await page.screenshot({ type: 'jpeg', quality: 90 }));
    console.log(JSON.stringify(await page.evaluate(() => window.__stats())));
  } else if (mode === 'stats') {
    await page.waitForTimeout(Number(b ?? 5000));
    console.log(JSON.stringify(await page.evaluate(() => window.__stats())));
  } else if (mode === 'eval') {
    await page.waitForTimeout(Number(c ?? 3000));
    console.log(JSON.stringify(await page.evaluate(b)));
  } else if (mode === 'bench') {
    await page.waitForTimeout(Number(b ?? 4000));
    const st = await page.evaluate(() => window.__stats());
    const r1 = await page.evaluate(() => window.__app.bench({ w: 1600, h: 900, n: 60 }));
    const r4 = [];
    for (let k = 0; k < 3; k++) r4.push(await page.evaluate(() => window.__app.bench({ w: 3840, h: 2160, n: 40 })));
    r4.sort((x, y) => x.mist - y.mist);
    console.log(JSON.stringify({ live: st, b1600: r1, b4k: r4[1] }));
  } else if (mode === 'frames') {
    // frame-locked clip: frames <url> <out.mp4> <WxH> <seconds> [warmup s]   (url must have &offline&mode=main)
    const secs = Number(c ?? 7), warm = Number(d ?? 0); const dir = a.replace(/\.mp4$/, '_frames');
    fs.mkdirSync(dir, { recursive: true });
    for (let k = 0; k < Math.round(warm * 30); k++) await page.evaluate(() => { window.__app.offlineFrame(1 / 30); return 0; });
    const n = Math.round(secs * 30);
    for (let k = 0; k < n; k++) {
      const url = await page.evaluate(() => window.__app.offlineFrame(1 / 30, 0.92));
      fs.writeFileSync(`${dir}/f${String(k).padStart(4, '0')}.jpg`, Buffer.from(url.split(',')[1], 'base64'));
    }
    console.log(JSON.stringify({ frames: n, dir, stats: await page.evaluate(() => window.__stats()) }));
  } else if (mode === 'clip') {
    await page.waitForTimeout(Number(d ?? 3000));
    const secs = Number(c ?? 7);
    const b64 = await page.evaluate(async (secs) => {
      const cv = document.querySelector('canvas'); const st = cv.captureStream(30);
      const rec = new MediaRecorder(st, { mimeType: 'video/webm;codecs=vp9', videoBitsPerSecond: 18e6 });
      const chunks = []; rec.ondataavailable = e => chunks.push(e.data);
      const done = new Promise(r => rec.onstop = r); rec.start(); await new Promise(r => setTimeout(r, secs * 1000)); rec.stop(); await done;
      const buf = await new Blob(chunks).arrayBuffer(); let s = ''; const u = new Uint8Array(buf);
      for (let i = 0; i < u.length; i += 32768) s += String.fromCharCode.apply(null, u.subarray(i, i + 32768));
      return btoa(s);
    }, secs);
    fs.writeFileSync(a, Buffer.from(b64, 'base64'));
    console.log(JSON.stringify(await page.evaluate(() => window.__stats())));
  }
} finally {
  if (logs.length) console.log(logs.slice(0, 20).map(l => l.length > 800 ? l.split('\n').filter(x => /ERROR|error|pageerror|^>/.test(x)).slice(0, 12).join('\n') : l).join('\n'));
  await page.close();
  await browser.close();
}
