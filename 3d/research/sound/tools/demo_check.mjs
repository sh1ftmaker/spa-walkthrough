// Smoke-test the live demo in the lead's GPU browser (CDP 9310): new tab, tap start, walk, measure, screenshot, close.
// node 3d/research/sound/tools/demo_check.mjs [bank=encoded|bake] [WxH] [shot.png]
import { createRequire } from 'node:module';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..', '..', '..');
const require = createRequire(join(root, 'tools', 'package.json'));
const { chromium } = require('playwright-core');
const [bankMode = 'encoded', size = '412x915', shot = ''] = process.argv.slice(2);
const [w, h] = size.split('x').map(Number);
const browser = await chromium.connectOverCDP('http://127.0.0.1:9310');
const ctx = browser.contexts()[0] ?? await browser.newContext();
const page = await ctx.newPage();
{ const cdp = await ctx.newCDPSession(page); await cdp.send('Network.setCacheDisabled', { cacheDisabled: true }); } // always load the current files
const errs = [];
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) errs.push(m.type() + ': ' + m.text()); });
page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
const out = {};
try {
  await page.setViewportSize({ width: w, height: h });
  await page.goto(`http://127.0.0.1:8742/3d/research/sound/demo/?bank=${bankMode}`, { waitUntil: 'load' });
  const t0 = Date.now();
  await page.click('#go');
  await page.waitForFunction('!document.getElementById("start")', null, { timeout: 120000 });
  out.startMs = Date.now() - t0;
  await page.waitForTimeout(1500);
  out.arrival = await page.evaluate('({s: window.__kz().stats, bank: window.__kz().bankInfo})');
  // walk the route a little, then jump to Kawagiri and measure there
  await page.click('#walk'); await page.waitForTimeout(6000); out.walking = await page.evaluate('window.__kz().stats'); await page.click('#walk');
  await page.click('button[data-level="b2"]');
  await page.evaluate(() => { const k = window.__kz(); k.L.x = 90; k.L.y = 84; k.L.heading = 90; });
  await page.waitForTimeout(2500);
  out.kawagiri = await page.evaluate('window.__kz().stats');
  await page.click('#bench'); await page.waitForFunction('window.__kz().benchTxt !== "—"', null, { timeout: 60000 });
  out.bench = await page.evaluate('window.__kz().benchTxt');
  // per-update cost over a stretch of real time
  out.updMs = await page.evaluate('window.__kz().stats.updMs');
  if (shot) await page.screenshot({ path: shot, fullPage: true });
} finally {
  out.errors = errs;
  console.log(JSON.stringify(out, null, 1));
  await page.close();
  await browser.close();
}
