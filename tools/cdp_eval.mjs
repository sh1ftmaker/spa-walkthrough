// node tools/cdp_eval.mjs <port> <url> <js-expression> [screenshot.png] [WxH]
import { chromium } from 'playwright-core';
const [port, url, expr, shot, size] = process.argv.slice(2);
const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
const ctx = browser.contexts()[0] ?? await browser.newContext();
const page = await ctx.newPage();
if (size) { const [w, h] = size.split('x').map(Number); await page.setViewportSize({ width: w, height: h }); }
await page.goto(url, { waitUntil: 'load' });
const out = await page.evaluate(expr);
console.log(typeof out === 'string' ? out : JSON.stringify(out, null, 1));
if (shot) await page.screenshot({ path: shot });
await page.close();
await browser.close();
