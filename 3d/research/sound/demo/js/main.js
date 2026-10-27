// Kazan-yu sound walk: UI, unlock, map, live update loop.
import { SoundEngine } from './engine.js';
import { bakeAll, loadEncoded, addAnchors } from './bank.js';
import { SCENARIOS, ROUTE } from './scenarios.js';
import * as G from './geom.js';

const $ = (id) => document.getElementById(id);
const LEVELS = [['summit', 'Summit +120'], ['ground', 'Ground 0 m'], ['b1', 'B1 −20'], ['b2', 'B2 −40'], ['b3', 'B3 −70'], ['b4', 'B4 −100']];
const START = { summit: [76, 66, 90], ground: [30, 55, 90], b1: [86, 76, 300], b2: [70, 70, 0], b3: [86, 66, 180], b4: [88, 73, 230] };
const params = new URLSearchParams(location.search);
let ctx, eng, bank, layout, blocks, level = 'ground';
const L = { x: 30, y: 55, heading: 90 };
let walking = null, flashes = [], benchTxt = '—', bankInfo = '—';

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const COLORS = () => ({ teal: css('--teal'), lava: css('--lava'), amber: css('--amber'), bell: css('--bell'), dim: css('--dim'), line: css('--line'), fg: css('--fg'), panel: css('--panel'), accent: css('--accent') });
const assetColor = (a, C) => (['lava', 'blorp', 'heartbeat'].includes(a) ? C.lava : ['murmur', 'sizzle', 'clink', 'steam', 'wind', 'furin'].includes(a) ? C.amber : C.teal);

async function boot() {
  [layout, blocks] = await Promise.all([fetch('./data/layout_extract.json').then((r) => r.json()), fetch('./data/audio_blocks.json').then((r) => r.json())]);
  const tabs = $('tabs');
  for (const [id, name] of LEVELS) { const b = document.createElement('button'); b.textContent = name; b.dataset.level = id; b.onclick = () => { stopWalk(); setLevel(id, true); }; tabs.appendChild(b); }
  setLevel('ground', true); draw();
  $('go').onclick = start;
}

async function start() {
  const go = $('go'); go.disabled = true; go.textContent = 'Starting…';
  // 1. Unlock inside the gesture. iOS: 'playback' audio session so the silent switch does not mute us (Safari 16.4+).
  try { if (navigator.audioSession) navigator.audioSession.type = 'playback'; } catch (_) {}
  ctx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: 'playback' });
  const s = ctx.createBufferSource(); s.buffer = ctx.createBuffer(1, 1, ctx.sampleRate); s.connect(ctx.destination); s.start();
  await ctx.resume();
  // 2. Sound bank: pre-rendered Opus loops (small download) when available, else bake procedurally on the device.
  const t0 = performance.now(); const prog = (f, name) => { $('prog').firstChild.style.width = (f * 100).toFixed(0) + '%'; $('progtxt').textContent = `preparing ${name}…`; };
  const want = params.get('bank') || 'encoded';
  if (want !== 'bake') { try { bank = await loadEncoded(ctx, './assets/', prog); bankInfo = `pre-rendered ${bank.meta.format}, ${(bank.meta.downloadBytes / 1e6).toFixed(2)} MB download`; } catch (e) { console.warn('encoded bank unavailable, baking', e); bank = null; } }
  if (!bank) { bank = await bakeAll(ctx.sampleRate, prog); await addAnchors(ctx, bank, './assets/'); bankInfo = 'baked on this device + CC0 anchors'; }
  const ms = performance.now() - t0; bankInfo += ` · ${(ms / 1000).toFixed(1)} s · ${(bank.meta.bytes / 1e6).toFixed(1)} MB decoded`;
  eng = new SoundEngine(ctx, layout, blocks, bank, { demoGeyser: true }).init();
  eng.onFire = (o, p) => { if (o.level === level) flashes.push({ x: p[0], y: p[1], t: performance.now(), asset: o.asset }); };
  eng.setListener({ ...L, level }); eng.update();
  $('start').remove();
  setInterval(tick, 50); requestAnimationFrame(frame); setInterval(renderStats, 250);
  document.addEventListener('visibilitychange', () => { if (document.hidden) ctx.suspend(); else ctx.resume(); });
  ctx.onstatechange = () => { if (ctx.state === 'interrupted' || ctx.state === 'suspended') showResume(); };
  wire();
}
function showResume() {
  if (document.hidden || $('resume')) return;
  const d = document.createElement('div'); d.id = 'start'; d.innerHTML = '<div class="card"><button id="resume">Tap to resume sound</button></div>'; document.body.appendChild(d);
  $('resume').onclick = async () => { await ctx.resume(); d.remove(); };
}

function wire() {
  $('walk').onclick = () => (walking ? stopWalk() : startWalk());
  $('quiet').onclick = (e) => { eng.setQuiet(!eng.opts.quiet); e.target.classList.toggle('on', eng.opts.quiet); };
  $('mode').onclick = (e) => { const m = eng.opts.mode === 'headphones' ? 'speaker' : 'headphones'; eng.setMode(m); e.target.textContent = 'Output: ' + (m === 'speaker' ? 'phone speaker' : 'headphones'); e.target.classList.toggle('on', m === 'speaker'); };
  $('pan').onclick = (e) => { const m = eng.opts.panning === 'HRTF' ? 'equalpower' : 'HRTF'; eng.setPanning(m); e.target.textContent = 'Panning: ' + (m === 'HRTF' ? 'HRTF' : 'equal-power'); e.target.classList.toggle('on', m === 'HRTF'); };
  $('turnL').onclick = () => { L.heading = (L.heading + 315) % 360; };
  $('turnR').onclick = () => { L.heading = (L.heading + 45) % 360; };
  $('geyser').onclick = () => { if (level !== 'b3') { stopWalk(); setLevel('b3'); L.x = 101; L.y = 42; L.heading = 90; } eng.fireById('geyser_big'); };
  $('bell').onclick = () => { if (level !== 'b1') { stopWalk(); setLevel('b1'); L.x = 72; L.y = 74.5; L.heading = 320; } eng.fireById('junction_bell'); };
  $('bench').onclick = bench;
}

// Render 4 s of the current scene offline and time it: DSP load as a share of one real-time core on THIS device.
async function bench() {
  const b = $('bench'); b.disabled = true; b.textContent = 'Measuring…';
  const sr = ctx.sampleRate, secs = 4; const out = {};
  for (const pan of ['equalpower', 'HRTF']) {
    const oc = new OfflineAudioContext(2, secs * sr, sr);
    const e2 = new SoundEngine(oc, layout, blocks, bank, { panning: pan, quiet: eng.opts.quiet, mode: eng.opts.mode }).init();
    e2.setListener({ ...L, level }); e2.update();
    const t0 = performance.now(); await oc.startRendering(); out[pan] = ((performance.now() - t0) / (secs * 1000)) * 100;
    out.voices = e2.stats().realVoices;
  }
  benchTxt = `${out.equalpower.toFixed(1)}% (HRTF ${out.HRTF.toFixed(1)}%) · ${out.voices} voices`;
  b.disabled = false; b.textContent = 'Measure DSP cost';
}

// ---------- map ----------
let view = null;
function setLevel(id, resetPos) {
  level = id; for (const b of $('tabs').children) b.classList.toggle('on', b.dataset.level === id);
  const sp = layout.spaces.filter((s) => s.level === id); let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const s of sp) for (const [x, y] of s.footprint) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  const pad = 4; x0 -= pad; y0 -= pad; x1 += pad; y1 += pad;
  const c = $('map'); const W = c.width; const narrow = c.getBoundingClientRect().width < 600;
  const H = Math.round(W * (y1 - y0) / (x1 - x0)); c.height = narrow ? 1050 : Math.min(Math.max(H, 420), 900);
  box = { x0, y0, x1, y1, narrow }; fitView();
  if (resetPos) { const p = START[id]; L.x = p[0]; L.y = p[1]; L.heading = p[2]; }
  fitView();
}
// Phones: show a 70 m window that follows the listener (re-centred when a drag ends), so the map stays touchable.
let box = null;
function fitView() {
  const c = $('map'); let { x0, y0, x1, y1, narrow } = box;
  if (narrow) {
    const w = Math.min(x1 - x0, 70), h = w * c.height / c.width; const cx = Math.min(Math.max(L.x, x0 + w / 2), x1 - w / 2), cy = Math.min(Math.max(L.y, y0 + h / 2), y1 - h / 2);
    x0 = (x1 - x0 <= w) ? x0 : cx - w / 2; x1 = x0 + w; y0 = cy - h / 2; y1 = y0 + h;
  }
  const s = Math.min(c.width / (x1 - x0), c.height / (y1 - y0));
  view = { x0, y0, x1, y1, s, ox: (c.width - (x1 - x0) * s) / 2, oy: (c.height - (y1 - y0) * s) / 2 };
}
let dragging = false;

const toPx = (x, y) => [view.ox + (x - view.x0) * view.s, view.oy + (view.y1 - y) * view.s];
const toM = (px, py) => [(px - view.ox) / view.s + view.x0, view.y1 - (py - view.oy) / view.s];

function draw() {
  const c = $('map'), g = c.getContext('2d'), C = COLORS(); g.clearRect(0, 0, c.width, c.height); const k = box?.narrow ? 2.2 : 1;
  const here = eng?.listener.space;
  for (const s of layout.spaces.filter((q) => q.level === level)) {
    g.beginPath(); s.footprint.forEach(([x, y], i) => { const [px, py] = toPx(x, y); i ? g.lineTo(px, py) : g.moveTo(px, py); }); g.closePath();
    g.fillStyle = s.id === here ? C.accent + '22' : C.line + '55'; g.fill(); g.strokeStyle = s.id === here ? C.accent : C.line; g.lineWidth = s.id === here ? 2 : 1; g.stroke();
    for (const w of s.water || []) {
      g.strokeStyle = C.teal + '66'; g.fillStyle = C.teal + '22';
      if (w.footprint) { g.beginPath(); w.footprint.forEach(([x, y], i) => { const [px, py] = toPx(x, y); i ? g.lineTo(px, py) : g.moveTo(px, py); }); g.closePath(); g.fill(); }
      const p = w.path || w.lip; if (p && p.length > 1) { g.beginPath(); p.forEach(([x, y], i) => { const [px, py] = toPx(x, y); i ? g.lineTo(px, py) : g.moveTo(px, py); }); g.lineWidth = Math.max(1.5, (w.width || 1) * view.s * 0.6); g.stroke(); }
    }
  }
  g.font = `${Math.round(12 * k)}px system-ui`; g.fillStyle = C.dim;
  for (const s of layout.spaces.filter((q) => q.level === level)) if (s.area > 250) { const [cx, cy] = G.centroid(s.footprint); const [px, py] = toPx(cx, cy); const n = s.name.replace(/^\d+ /, ''); g.fillText(n.length > 22 ? n.slice(0, 21) + '…' : n, px - 40 * k, py); }
  if (eng) {
    const real = new Set([...eng.voices.keys()]);
    for (const e of eng.emitters.filter((q) => q.level === level)) {
      const on = real.has(e.key); const col = on ? assetColor(e.asset, C) : C.dim; const db = on ? 20 * Math.log10(e.route?.gain + 1e-9) : -80;
      g.globalAlpha = on ? 1 : 0.45; g.strokeStyle = col; g.fillStyle = col;
      if (e.pts.length > 1 && e.shape !== 'area') { g.beginPath(); e.pts.forEach(([x, y], i) => { const [px, py] = toPx(x, y); i ? g.lineTo(px, py) : g.moveTo(px, py); }); g.lineWidth = k * (on ? 3 : 1.5); g.setLineDash(on ? [] : [4, 4]); g.stroke(); g.setLineDash([]); }
      else { const pp = e.pts[0] || G.centroid(e.poly); const [px, py] = toPx(pp[0], pp[1]); g.beginPath(); g.arc(px, py, k * (on ? 4 + Math.max(0, (db + 50) / 6) : 3), 0, 7); on ? g.fill() : g.stroke(); }
      if (on && e.route && e.route.hops === 0 && e.pts.length > 1) { const [ax, ay] = toPx(e.route.pos[0], e.route.pos[1]); g.beginPath(); g.arc(ax, ay, 3, 0, 7); g.fill(); }
    }
    g.globalAlpha = 1;
    const tnow = performance.now(); flashes = flashes.filter((f) => tnow - f.t < 1400);
    for (const f of flashes) { const a = (tnow - f.t) / 1400; const [px, py] = toPx(f.x, f.y); g.strokeStyle = C.bell; g.globalAlpha = 1 - a; g.beginPath(); g.arc(px, py, k * (4 + a * (f.asset.startsWith('geyser') ? 60 : 22)), 0, 7); g.lineWidth = 2 * k; g.stroke(); }
    g.globalAlpha = 1;
  }
  // listener
  const [lx, ly] = toPx(L.x, L.y); const h = L.heading * Math.PI / 180;
  g.save(); g.translate(lx, ly); g.rotate(h); g.scale(k, k); g.fillStyle = C.fg; g.beginPath(); g.moveTo(0, -14); g.lineTo(8, 8); g.lineTo(0, 3); g.lineTo(-8, 8); g.closePath(); g.fill();
  g.strokeStyle = C.fg + '55'; g.beginPath(); g.arc(0, 0, 20, 0, 7); g.stroke(); g.restore();
}

// pointer drag
(() => {
  const c = $('map'); let down = false, last = null;
  const pos = (ev) => { const r = c.getBoundingClientRect(); return toM((ev.clientX - r.left) * c.width / r.width, (ev.clientY - r.top) * c.height / r.height); };
  c.addEventListener('pointerdown', (ev) => { down = true; dragging = true; stopWalk(); c.setPointerCapture(ev.pointerId); const p = pos(ev); last = p; L.x = p[0]; L.y = p[1]; });
  c.addEventListener('pointermove', (ev) => { if (!down) return; const p = pos(ev); const dx = p[0] - last[0], dy = p[1] - last[1]; if (Math.hypot(dx, dy) > 0.8) { L.heading = (Math.atan2(dx, dy) * 180 / Math.PI + 360) % 360; last = p; } L.x = p[0]; L.y = p[1]; });
  c.addEventListener('pointerup', () => { down = false; dragging = false; fitView(); });
  c.addEventListener('pointercancel', () => { down = false; dragging = false; fitView(); });
})();

// ---------- guided walk ----------
function startWalk() { walking = { i: 0, t0: performance.now() }; $('walk').classList.add('on'); $('walk').textContent = 'Stop walking'; }
function stopWalk() { if (!walking) return; walking = null; $('walk').classList.remove('on'); $('walk').textContent = 'Walk the route'; }
function walkStep() {
  const sc = SCENARIOS[ROUTE[walking.i]]; const t = (performance.now() - walking.t0) / 1000;
  if (t > sc.secs) { walking.i = (walking.i + 1) % ROUTE.length; walking.t0 = performance.now(); if (ROUTE[walking.i] === 'p7_geyser') eng.fireById('geyser_big'); return; }
  const k = sc.keys; let a = k[0], b = k[k.length - 1];
  for (let i = 0; i < k.length - 1; i++) if (t >= k[i].t && t <= k[i + 1].t) { a = k[i]; b = k[i + 1]; break; }
  const u = b.t > a.t ? Math.min(1, (t - a.t) / (b.t - a.t)) : 1; const lv = u < 0.5 ? a.level : b.level;
  if (lv !== level) setLevel(lv);
  L.x = a.x + (b.x - a.x) * u; L.y = a.y + (b.y - a.y) * u; const hd = ((b.heading - a.heading + 540) % 360) - 180; L.heading = (a.heading + hd * u + 360) % 360;
  $('where').dataset.scene = sc.title;
}

function tick() { if (walking) walkStep(); eng.setListener({ x: L.x, y: L.y, heading: L.heading, level }); eng.update(); }
function frame() { if (box?.narrow && !dragging) { const m = 0.18 * (view.x1 - view.x0); if (L.x < view.x0 + m || L.x > view.x1 - m || L.y < view.y0 + m || L.y > view.y1 - m) fitView(); } draw(); requestAnimationFrame(frame); }
function renderStats() {
  const s = eng.stats(); const sp = eng.spaces[s.space];
  $('where').textContent = (sp ? sp.name : '—') + (walking ? ' · ' + ($('where').dataset.scene || '') : '');
  const rows = [['space', sp?.name], ['reverb', `${s.reverb} (${blocks.reverb_presets[s.reverb]?.rt}s)`], ['voices', `${s.realVoices} real / ${s.audible} audible / ${s.emitters} emitters (max ${eng.opts.maxVoices})`],
    ['beds', s.beds], ['one-shots', `${s.oneshotsActive} playing · ${s.oneshotsTotal} fired`], ['convolvers', s.convolvers], ['update', `${s.updMs.toFixed(2)} ms / 50 ms tick`],
    ['DSP load', benchTxt], ['context', `${s.state} · ${s.sr} Hz · base ${(s.baseLatency * 1000 || 0).toFixed(0)} ms · out ${((s.outputLatency || 0) * 1000).toFixed(0)} ms`], ['bank', bankInfo], ['quiet hours', eng.opts.quiet ? 'on' : 'off']];
  $('stats').innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v ?? '—'}</dd>`).join('');
  $('voices').innerHTML = eng.voiceList().sort((a, b) => b.db - a.db).map((v) => `<li><span>${v.id}</span><span>${v.db} dB${v.hops ? ' · ' + (v.hops === 9 ? 'rock' : Math.ceil(v.hops) + ' portal' + (v.hops > 1 ? 's' : '')) : ''}</span></li>`).join('');
}

boot();
window.__kz = () => ({ eng, L, level, stats: eng?.stats(), bankInfo, benchTxt });
