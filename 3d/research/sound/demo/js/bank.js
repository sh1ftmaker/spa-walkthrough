// The sound bank: every asset the soundscape uses, all procedural (self-made, no third-party audio).
// Loops are baked once at load time (seamless, mono unless stereo is needed); one-shots are baked as a few
// seeded variants and randomised at play time (pitch/gain/position). Same list is used by Node tools.
import * as D from './dsp.js';

// secs = loop length. Keep loops 8-16 s: long enough that the repetition is not obvious under movement,
// short enough to keep decoded memory small (one 12 s mono loop at 48 kHz = 2.3 MB of float32).
export const LOOPS = {
  // Round 2: big water is a calibrated noise bank (rush / thunder), bubbles are accents only.
  river:     { rate: 32000, secs: 14, make: (sr) => D.rush(sr, 14, 201, { template: 'rapids', detail: -13 }) },
  falls:     { rate: 32000, secs: 14, make: (sr) => D.thunder(sr, 14, 211, { impacts: 9 }) },
  river2:    { rate: 32000, secs: 13, make: (sr) => D.rush(sr, 13, 202, { template: 'rapids', detail: -13 }) },   // second, uncorrelated take
  falls2:    { rate: 32000, secs: 13, make: (sr) => D.thunder(sr, 13, 212, { impacts: 12 }) },
  falls_mid: { rate: 32000, secs: 12, make: (sr) => D.rush(sr, 12, 205, { template: 'falls', detail: -11 }) },
  inflow:    { rate: 32000, secs: 12, make: (sr) => D.rush(sr, 12, 207, { template: 'falls', detail: -8, tilt: 0.6 }) },
  sheet:     { rate: 32000, secs: 10, make: (sr) => D.sheet2(sr, 10, 251) },
  curtain:   { rate: 32000, secs: 10, make: (sr) => D.sheet2(sr, 10, 253, 1.0) },
  cascade:   { rate: 32000, secs: 12, make: (sr) => D.cascade2(sr, 12, 261) },
  stream:    { rate: 32000, secs: 12, make: (sr) => D.stream2(sr, 12, 241) },
  spray:     { rate: 32000, secs: 8,  make: (sr) => D.spray(sr, 8, 221) },
  rumble:    { rate: 8000,  secs: 14, make: (sr) => D.rockRumble(sr, 14, 231) },
  surf:      { rate: 24000, secs: 32, make: (sr) => D.surf2(sr, 32, 271, { period: 9 }) },
  // close-range accents (bubble models)
  boil:      { rate: 32000, secs: 12, make: (sr) => D.brook(sr, 12, 11) },
  rill:      { rate: 32000, secs: 10, make: (sr) => D.rill(sr, 10, 21, { rate: 22 }) },
  basin:     { rate: 32000, secs: 9,  make: (sr) => D.rill(sr, 9, 23, { rate: 70, pitch: 1.4 }) },
  lapping:   { rate: 24000, secs: 12, make: (sr) => D.lapping(sr, 12, 71) },
  // air, fire, people, earth
  wind:      { rate: 24000, secs: 20, make: (sr) => D.wind(sr, 20, 81, { strength: 1, whistle: 0.35 }) },
  steam:     { rate: 32000, secs: 10, make: (sr) => D.steam(sr, 10, 91) },
  lava:      { rate: 8000,  secs: 14, make: (sr) => D.lava(sr, 14, 111) },
  sizzle:    { rate: 32000, secs: 8,  make: (sr) => D.sizzle(sr, 8, 121) },
  murmur:    { rate: 16000, secs: 14, make: (sr) => D.murmur(sr, 14, 131) },
  heartbeat: { rate: 8000,  secs: 16.36, make: (sr) => D.heartbeat(sr, 16.36, 141, { bpm: 22 }) }, // 6 beats at 22 bpm
  roomtone:  { rate: 8000,  secs: 10, make: (sr) => D.roomtone(sr, 10, 161) },
};
export const ONESHOTS = {
  drip:   { rate: 48000, n: 10, make: (sr, s) => D.drip(sr, s) },
  plop:   { rate: 48000, n: 4,  make: (sr, s) => D.plop(sr, s) },
  bell:   { rate: 24000, n: 2,  make: (sr, s) => D.bell(sr, s, { f0: 620 }) },
  furin:  { rate: 32000, n: 4,  make: (sr, s) => D.furin(sr, s, { f0: [1380, 1520, 1660, 1460][s % 4] }) },
  clink:  { rate: 48000, n: 8,  make: (sr, s) => D.clink(sr, s) },
  blorp:  { rate: 8000, n: 5,  make: (sr, s) => D.blorp(sr, s) },
  geyser_big:   { rate: 32000, n: 1, make: (sr, s) => D.geyser(sr, 151 + s, { big: true }) },
  geyser_small: { rate: 32000, n: 3, make: (sr, s) => D.geyser(sr, 160 + s, { big: false }) },
};

// Bake everything. onProgress(doneFraction, name). Yields between assets so a page can paint progress.
export async function bakeAll(sr, onProgress = () => {}, yieldFn = () => new Promise((r) => setTimeout(r, 0))) {
  const loops = {}, shots = {}, meta = { ms: {}, samples: 0 };
  const names = [...Object.keys(LOOPS), ...Object.keys(ONESHOTS)]; let k = 0;
  for (const [name, def] of Object.entries(LOOPS)) {
    const r = Math.min(sr, def.rate || sr); const t0 = now(); const res = def.make(r); const chs = Array.isArray(res) ? res : res.chs;
    loops[name] = { chs, sr: r, gust: res.gust || null }; meta.ms[name] = now() - t0; meta.samples += chs.length * chs[0].length;
    onProgress(++k / names.length, name); await yieldFn();
  }
  for (const [name, def] of Object.entries(ONESHOTS)) {
    const r = Math.min(sr, def.rate || sr); const t0 = now(); shots[name] = [];
    for (let s = 0; s < def.n; s++) { const chs = def.make(r, s + 1); shots[name].push({ chs, sr: r }); meta.samples += chs.length * chs[0].length; }
    meta.ms[name] = now() - t0; onProgress(++k / names.length, name); await yieldFn();
  }
  meta.bytes = meta.samples * 4;
  return { loops, shots, meta };
}
const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

// Production path: load loops pre-rendered by tools/encode_bank.mjs (same generators, rendered offline) as Ogg Opus,
// falling back to AAC (.m4a) where Opus will not decode (iOS Safari before 18.4). Each loop file carries a wrapped
// pad at both ends, so whatever codec priming/padding the decoder leaves in, cutting n samples anywhere inside the
// pad still gives a seamless loop. decodeAudioData resamples to the context rate; low-band assets are decimated
// back to their bake rate to keep decoded memory down.
export async function loadEncoded(ctx, base, onProgress = () => {}, { only = null } = {}) {
  const man = await (await fetch(base + 'manifest.json')).json();
  if (only) { man.loops = Object.fromEntries(Object.entries(man.loops).filter(([k, m]) => only(k, m))); man.shots = {}; }
  let fmt = 'opus', down = 0; const out = { loops: {}, shots: {}, meta: { bytes: 0, format: '', downloadBytes: 0, ms: {} } };
  const dec = async (file) => {
    for (;;) {
      try { const r = await fetch(base + file + '.' + fmt); if (!r.ok) throw new Error(r.status); const ab = await r.arrayBuffer(); down += ab.byteLength; return await ctx.decodeAudioData(ab); }
      catch (e) { if (fmt === 'opus') { fmt = 'm4a'; continue; } throw e; }
    }
  };
  const shrink = (ab, sr, n, start) => { // slice n samples at `start` (asset-rate samples), resample to the asset rate
    const k = ab.sampleRate / sr; const b = ctx.createBuffer(ab.numberOfChannels, n, sr);
    for (let c = 0; c < ab.numberOfChannels; c++) {
      const src = ab.getChannelData(c), dst = new Float32Array(n);
      for (let i = 0; i < n; i++) { const p = (start + i) * k, j = Math.floor(p), f = p - j; dst[i] = (src[j] || 0) * (1 - f) + (src[j + 1] || 0) * f; }
      b.copyToChannel(dst, c);
    }
    out.meta.bytes += n * ab.numberOfChannels * 4; return b;
  };
  const names = [...Object.keys(man.loops), ...Object.keys(man.shots)]; let k = 0;
  for (const [name, m] of Object.entries(man.loops)) {
    const ab = await dec('loop_' + name);
    const expect = Math.round((m.n + 2 * m.pad) * ab.sampleRate / m.sr); const excess = Math.max(0, ab.length - expect);
    const front = Math.min(m.pad * 0.8, Math.round(excess * m.sr / ab.sampleRate)); // assume extra samples are leading priming
    out.loops[name] = { buffer: shrink(ab, m.sr, m.n, m.pad + front), sr: m.sr, gust: m.gust ? Float32Array.from(m.gust) : null };
    onProgress(++k / names.length, name);
  }
  for (const [name, list] of Object.entries(man.shots)) {
    out.shots[name] = [];
    for (let i = 0; i < list.length; i++) { const ab = await dec(`shot_${name}_${i}`); out.shots[name].push({ buffer: shrink(ab, list[i].sr, Math.min(list[i].n, Math.floor(ab.length * list[i].sr / ab.sampleRate)), 0), sr: list[i].sr }); }
    onProgress(++k / names.length, name);
  }
  out.meta.format = fmt === 'opus' ? 'Ogg Opus' : 'AAC'; out.meta.downloadBytes = down;
  return out;
}

// CC0 anchor recordings (round 3) only exist pre-rendered: load them into a baked bank too.
export async function addAnchors(ctx, bank, base) {
  try { const a = await loadEncoded(ctx, base, () => {}, { only: (k, m) => !!m.anchor }); Object.assign(bank.loops, a.loops); bank.meta.bytes += a.meta.bytes; bank.meta.anchorBytes = a.meta.downloadBytes; }
  catch (e) { console.warn('anchors unavailable', e); }
  return bank;
}
