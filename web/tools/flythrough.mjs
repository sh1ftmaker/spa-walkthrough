#!/usr/bin/env node
// Walk a list of waypoints at eye height (real walk physics: stairs, collision) and record it as an MP4.
//   node tools/flythrough.mjs --cdp 9311 --url http://127.0.0.1:5173/ --route tools/routes/ground-to-b1.json \
//        --out ../3d/renders/web/ground-to-b1.mp4 [--size 1280x720] [--fps 30] [--speed 1.6] [--tier low|high] [--query labels=0]
// Route JSON: { "start": "<place id>", "points": [[x, y, zEye], ...] }  (layout coords; z is eye height = floor + 1.6)
// or a bare array of points (then --start <place id> is required). Frames come from CDP Page.startScreencast and are
// re-timed to a constant frame rate with ffmpeg (concat demuxer with per-frame durations).
import { chromium } from 'playwright-core';
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  if (!argv[i].startsWith('--')) continue;
  const k = argv[i].slice(2), v = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
  opt[k] = v;
}
if (!opt.route || !opt.out || !opt.url) { console.error('usage: flythrough.mjs --url <app> --route <route.json> --out <file.mp4> [--cdp 9311]'); process.exit(2); }
const port = Number(opt.cdp ?? 9311);
if (port === 9222) { console.error('refusing CDP 9222 (shared browser)'); process.exit(2); }
const [W, H] = String(opt.size ?? '1280x720').split('x').map(Number);
const FPS = Number(opt.fps ?? 30);
const routeDoc = JSON.parse(readFileSync(opt.route, 'utf8'));
const points = Array.isArray(routeDoc) ? routeDoc : routeDoc.points;
const start = opt.start ?? routeDoc.start;
if (!start) { console.error('route needs a start place (route.start or --start)'); process.exit(2); }

const here = dirname(fileURLToPath(import.meta.url));
const work = resolve(here, `../../.scratch/web/fly-${process.pid}`);
mkdirSync(work, { recursive: true });

const u = new URL(opt.url);
u.searchParams.set('place', start); u.searchParams.set('hint', '0');
if (opt.tier) u.searchParams.set('tier', opt.tier);
for (const [k, v] of new URLSearchParams(opt.query ?? '')) u.searchParams.set(k, v);

const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
const frames = [];
let summary;
try {
  await page.goto(u.href, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__kz && window.__kz.ready, null, { timeout: 30000 });
  const ok = await page.evaluate(() => window.__kz.ready.then(() => true, (e) => String(e?.message ?? e)));
  if (ok !== true) throw new Error(`app failed: ${ok}`);
  await page.waitForFunction(() => window.__kz.allLoadedMs != null, null, { timeout: 120000 });
  await page.evaluate(() => window.__kz.frames(30));
  const cdp = await ctx.newCDPSession(page);
  cdp.on('Page.screencastFrame', async (f) => {
    frames.push({ t: f.metadata.timestamp, data: f.data });
    try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch { /* closed */ }
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 88, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  const t0 = Date.now();
  const res = await page.evaluate(async ({ points, speed }) => {
    const kz = window.__kz;
    const stats = { fpsMin: 999, drawMax: 0, triMax: 0 };
    let done = false, skipped = null;
    kz.walkPath(points, { speed }).then((s) => { done = true; skipped = s; });
    while (!done) {
      await kz.frames(10);
      const i = kz.info();
      stats.fpsMin = Math.min(stats.fpsMin, i.fps); stats.drawMax = Math.max(stats.drawMax, i.drawCalls); stats.triMax = Math.max(stats.triMax, i.triangles);
    }
    await kz.frames(30);
    return { skipped, stats, end: kz.info() };
  }, { points, speed: Number(opt.speed ?? 1.6) });
  await cdp.send('Page.stopScreencast');
  summary = { seconds: (Date.now() - t0) / 1000, frames: frames.length, skippedWaypoints: res.skipped, ...res.stats, end: { pos: res.end.pos, space: res.end.space, zone: res.end.zone, tier: res.end.tier } };
} finally {
  await ctx.close();
  await browser.close();
}
if (frames.length < 2) throw new Error('no frames captured');
// write frames + concat list with real durations
const lines = ['ffconcat version 1.0'];
frames.forEach((f, i) => {
  const name = `f${String(i).padStart(6, '0')}.jpg`;
  writeFileSync(join(work, name), Buffer.from(f.data, 'base64'));
  const dur = i + 1 < frames.length ? Math.max(0.001, frames[i + 1].t - f.t) : 1 / FPS;
  lines.push(`file ${name}`, `duration ${dur.toFixed(4)}`);
});
lines.push(`file f${String(frames.length - 1).padStart(6, '0')}.jpg`);
writeFileSync(join(work, 'list.ffconcat'), lines.join('\n'));
const out = resolve(opt.out);
mkdirSync(dirname(out), { recursive: true });
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', join(work, 'list.ffconcat'),
  '-vf', `fps=${FPS},scale=${W - (W % 2)}:${H - (H % 2)}`, '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out]);
rmSync(work, { recursive: true, force: true });
console.log(JSON.stringify({ out, ...summary }, null, 1));
