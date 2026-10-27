#!/usr/bin/env node
// Screenshot the walkaround through an existing (GPU) browser over CDP.
//   node tools/shot.mjs --cdp 9311 --url http://127.0.0.1:5173/ --out ../3d/renders/web/arrival \
//        [--place g_arrival | --pos x,y,z --target x,y,z] [--fov 70] [--sizes 9:16,16:9] [--long 1600]
//        [--device phone|desktop] [--tier low|high] [--query "debug=1&labels=0"] [--mode dollhouse] [--wait-all]
// Positions are layout coordinates (x east, y north, z up). Writes <out>-9x16.jpg / <out>-16x9.jpg (or <out>-phone.jpg)
// and prints __kz.info() for every capture as JSON.
import { chromium } from 'playwright-core';
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const TMP = resolve(dirname(fileURLToPath(import.meta.url)), '../../.scratch/web/tmp');
mkdirSync(TMP, { recursive: true });

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  if (!argv[i].startsWith('--')) continue;
  const k = argv[i].slice(2), v = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
  opt[k] = v;
}
if (!opt.out || !opt.url) { console.error('usage: shot.mjs --url <app url> --out <path prefix> [--cdp 9311] ...'); process.exit(2); }
const port = Number(opt.cdp ?? 9311);
if (port === 9222) { console.error('refusing CDP 9222 (shared browser)'); process.exit(2); }
const long = Number(opt.long ?? 1600);
const vec = (s) => (s ? String(s).split(',').map(Number) : null);

function buildUrl(extra = {}) {
  const u = new URL(opt.url);
  if (opt.tier) u.searchParams.set('tier', opt.tier);
  if (opt.place) u.searchParams.set('place', opt.place);
  for (const [k, v] of new URLSearchParams(opt.query ?? '')) u.searchParams.set(k, v);
  for (const [k, v] of Object.entries(extra)) u.searchParams.set(k, v);
  if (!u.searchParams.has('hint')) u.searchParams.set('hint', '0');
  return u.href;
}

const shots = [];
if (opt.device === 'phone') shots.push({ tag: 'phone', viewport: { width: 390, height: 844 }, dpr: 3, mobile: true });
else if (opt.device === 'desktop') shots.push({ tag: 'desktop', viewport: { width: 1600, height: 900 }, dpr: 1, mobile: false });
else for (const s of String(opt.sizes ?? '9:16,16:9').split(',')) {
  const [a, b] = s.split(':').map(Number);
  const portrait = b > a;
  // CSS viewport ~ phone/desktop sized; DPR chosen so the long edge is `long` px
  const css = portrait ? { width: 405, height: Math.round((405 * b) / a) } : { width: 1280, height: Math.round((1280 * b) / a) };
  shots.push({ tag: `${a}x${b}`, viewport: css, dpr: long / Math.max(css.width, css.height), mobile: portrait });
}

const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
const results = [];
try {
  for (const s of shots) {
    const ctx = await browser.newContext({ viewport: s.viewport, deviceScaleFactor: s.dpr, isMobile: s.mobile, hasTouch: s.mobile,
      ...(s.mobile && opt.device === 'phone' ? { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1' } : {}) });
    const page = await ctx.newPage();
    const logs = [];
    page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') logs.push(`${m.type()}: ${m.text()}`); });
    page.on('pageerror', (e) => logs.push(`pageerror: ${e.message}`));
    page.on('response', (r) => { if (r.status() >= 400) logs.push(`HTTP ${r.status()} ${r.url()}`); });
    await page.goto(buildUrl(), { waitUntil: 'load' });
    await page.waitForFunction(() => window.__kz && window.__kz.ready, null, { timeout: 30000 });
    const ok = await page.evaluate(() => window.__kz.ready.then(() => true, (e) => String(e?.message ?? e)));
    if (ok !== true) throw new Error(`app failed: ${ok}\n${logs.join('\n')}`);
    if (opt['wait-all']) await page.waitForFunction(() => window.__kz.allLoadedMs != null, null, { timeout: 60000 });
    if (opt.mode) await page.evaluate((m) => window.__kz.mode(m), opt.mode);
    if (opt.pos) await page.evaluate(([p, t, f]) => window.__kz.setCamera(p, t, f), [vec(opt.pos), vec(opt.target), opt.fov ? Number(opt.fov) : null]);
    else if (opt.fov) await page.evaluate((f) => window.__kz.setFov(f), Number(opt.fov));
    await page.evaluate((n) => window.__kz.frames(n), Number(opt.frames ?? 20));
    if (opt.settle) await page.waitForTimeout(Number(opt.settle));
    const info = await page.evaluate(() => window.__kz.info());
    const tmp = resolve(TMP, `kzshot-${process.pid}-${s.tag}.png`);
    await page.screenshot({ path: tmp, type: 'png' });
    const out = resolve(`${opt.out}-${s.tag}.jpg`);
    mkdirSync(dirname(out), { recursive: true });
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', tmp, '-vf', `scale='if(gt(iw,ih),min(${long},iw),-2)':'if(gt(iw,ih),-2,min(${long},ih))'`, '-q:v', '3', out]);
    rmSync(tmp, { force: true });
    results.push({ file: out, tag: s.tag, viewport: s.viewport, dpr: s.dpr, info: { fps: info.fps, ms: info.ms, drawCalls: info.drawCalls, triangles: info.triangles, textures: info.textures, textureMB: info.textureMB, programs: info.programs, tier: info.tier, gpu: info.gpu, pos: info.pos, heading: info.heading, space: info.space, zone: info.zone, interactiveMs: info.interactiveMs }, logs });
    await ctx.close();
  }
} finally {
  await browser.close();
}
console.log(JSON.stringify(results, null, 1));
