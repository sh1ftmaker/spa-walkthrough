// Kazan-yu procedural sound library: pure DSP, no Web Audio, no DOM.
// Every generator returns Float32Array channel data at the given sample rate, so the same code runs in the
// browser (baked into AudioBuffers at load time) and in Node (offline previews and seam analysis).
// All randomness is seeded: the same seed gives the same sound everywhere.
//
// Physical models and their sources (see ../../README.md for the full citations):
//  - bubble(): Minnaert resonance f0 = (1/2πr)·sqrt(3γp0/ρ) ≈ 3.26/r Hz, damped sine with van den Doel's
//    rising-pitch term f(t) = f0(1 + σt), σ = ξ·d (van den Doel 2005, ACM TAP 2(4); as restated by Moss et al. 2009).
//    Radius picked from a power law r^-α (Pumphrey & Elmore α≈2.9 rain; Deane & Stokes α 1.5-3.3 breaking waves).
//  - wind(): band-passed noise driven by one gust envelope, plus a Strouhal whistle (Farnell, Designing Sound, "Wind").
//  - fire/crackle, steam: shaped noise bursts (Farnell, "Fire").
//  - bells/chimes: modal synthesis, sums of exponentially decaying partials with beating pairs.

export const TAU = Math.PI * 2;

export function rng(seed = 1) {
  let a = seed >>> 0;
  return function () { // mulberry32
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export const dbToLin = (db) => Math.pow(10, db / 20);
export const linToDb = (g) => 20 * Math.log10(Math.max(g, 1e-12));
const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);

// ---------- noise ----------
export function white(n, R) { const o = new Float32Array(n); for (let i = 0; i < n; i++) o[i] = R() * 2 - 1; return o; }
export function pink(n, R) { // Paul Kellet's refined filter
  const o = new Float32Array(n); let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
  for (let i = 0; i < n; i++) {
    const w = R() * 2 - 1;
    b0 = 0.99886 * b0 + w * 0.0555179; b1 = 0.99332 * b1 + w * 0.0750759; b2 = 0.969 * b2 + w * 0.153852;
    b3 = 0.8665 * b3 + w * 0.3104856; b4 = 0.55 * b4 + w * 0.5329522; b5 = -0.7616 * b5 - w * 0.016898;
    o[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11; b6 = w * 0.115926;
  }
  return o;
}
export function brown(n, R) { const o = new Float32Array(n); let y = 0; for (let i = 0; i < n; i++) { y = (y + 0.02 * (R() * 2 - 1)) * 0.998; o[i] = y * 3.5; } return o; }

// ---------- filters ----------
// TPT state-variable filter (Zavalishin). cutoff may be a number or a Float32Array (per-sample).
export function svf(x, sr, cutoff, q = 0.707, mode = 'lp') {
  const o = new Float32Array(x.length); let ic1 = 0, ic2 = 0; const k = 1 / q;
  const per = typeof cutoff !== 'number';
  let g = Math.tan(Math.PI * clamp(per ? cutoff[0] : cutoff, 10, sr * 0.45) / sr);
  let a1 = 1 / (1 + g * (g + k)), a2 = g * a1, a3 = g * a2;
  for (let i = 0; i < x.length; i++) {
    if (per && (i & 15) === 0) {
      g = Math.tan(Math.PI * clamp(cutoff[i], 10, sr * 0.45) / sr); a1 = 1 / (1 + g * (g + k)); a2 = g * a1; a3 = g * a2;
    }
    const v3 = x[i] - ic2, v1 = a1 * ic1 + a2 * v3, v2 = ic2 + a2 * ic1 + a3 * v3;
    ic1 = 2 * v1 - ic1; ic2 = 2 * v2 - ic2;
    o[i] = mode === 'lp' ? v2 : mode === 'bp' ? v1 : mode === 'hp' ? x[i] - k * v1 - v2 : x[i] - k * v1; // 'notch'
  }
  return o;
}
export const lp = (x, sr, f, q) => svf(x, sr, f, q, 'lp');
export const hp = (x, sr, f, q) => svf(x, sr, f, q, 'hp');
export const bp = (x, sr, f, q) => svf(x, sr, f, q, 'bp');
// RBJ biquad shelf/peak (static)
export function biquad(x, sr, type, f, gainDb = 0, q = 0.707) {
  const A = Math.pow(10, gainDb / 40), w = TAU * f / sr, c = Math.cos(w), s = Math.sin(w), al = s / (2 * q);
  let b0, b1, b2, a0, a1, a2;
  if (type === 'peak') { b0 = 1 + al * A; b1 = -2 * c; b2 = 1 - al * A; a0 = 1 + al / A; a1 = -2 * c; a2 = 1 - al / A; }
  else if (type === 'lowshelf') { const r = 2 * Math.sqrt(A) * al; b0 = A * ((A + 1) - (A - 1) * c + r); b1 = 2 * A * ((A - 1) - (A + 1) * c); b2 = A * ((A + 1) - (A - 1) * c - r); a0 = (A + 1) + (A - 1) * c + r; a1 = -2 * ((A - 1) + (A + 1) * c); a2 = (A + 1) + (A - 1) * c - r; }
  else { const r = 2 * Math.sqrt(A) * al; b0 = A * ((A + 1) + (A - 1) * c + r); b1 = -2 * A * ((A - 1) + (A + 1) * c); b2 = A * ((A + 1) + (A - 1) * c - r); a0 = (A + 1) - (A - 1) * c + r; a1 = 2 * ((A - 1) - (A + 1) * c); a2 = (A + 1) - (A - 1) * c - r; }
  const o = new Float32Array(x.length); let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < x.length; i++) { const y = (b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2) / a0; x2 = x1; x1 = x[i]; y2 = y1; y1 = y; o[i] = y; }
  return o;
}
export function onepoleLP(x, sr, f) { const o = new Float32Array(x.length); const a = Math.exp(-TAU * f / sr); let y = 0; for (let i = 0; i < x.length; i++) { y = (1 - a) * x[i] + a * y; o[i] = y; } return o; }

// ---------- envelopes / control ----------
// Smooth random control signal in [0,1]: cosine-interpolated random points every 1/rate s, periodic over n.
export function smoothRandom(n, sr, rate, R, lo = 0, hi = 1) {
  const step = Math.max(1, Math.round(sr / rate)); const pts = Math.ceil(n / step);
  const v = new Float32Array(pts + 1); for (let i = 0; i < pts; i++) v[i] = lo + (hi - lo) * R(); v[pts] = v[0];
  const o = new Float32Array(n);
  for (let i = 0; i < n; i++) { const p = i / step, k = Math.floor(p), f = p - k; const m = (1 - Math.cos(Math.PI * f)) / 2; o[i] = v[k] * (1 - m) + v[Math.min(k + 1, pts)] * m; }
  return o;
}
export function mul(a, b) { for (let i = 0; i < a.length; i++) a[i] *= typeof b === 'number' ? b : b[i]; return a; }
export function add(a, b, g = 1) { for (let i = 0; i < a.length && i < b.length; i++) a[i] += b[i] * g; return a; }
export function mixInto(dst, src, at, g = 1) { const n = Math.min(src.length, dst.length - at); for (let i = 0; i < n; i++) dst[at + i] += src[i] * g; }
export function rms(x) { let s = 0; for (let i = 0; i < x.length; i++) s += x[i] * x[i]; return Math.sqrt(s / Math.max(1, x.length)); }
export function peak(x) { let m = 0; for (let i = 0; i < x.length; i++) { const a = Math.abs(x[i]); if (a > m) m = a; } return m; }
export function normRms(chs, db) { let s = 0, n = 0; for (const c of chs) { for (let i = 0; i < c.length; i++) s += c[i] * c[i]; n += c.length; } const g = dbToLin(db) / Math.sqrt(s / n + 1e-20); for (const c of chs) mul(c, g); return chs; }
export function normPeak(chs, db) { let m = 0; for (const c of chs) m = Math.max(m, peak(c)); const g = dbToLin(db) / (m + 1e-12); for (const c of chs) mul(c, g); return chs; }
export function softClip(x, drive = 1) { for (let i = 0; i < x.length; i++) x[i] = Math.tanh(x[i] * drive) / Math.tanh(drive); return x; }

// Make a buffer loop seamlessly: generate (len + xf) samples, then fold the tail onto the head with an
// equal-power crossfade (uncorrelated textures keep constant energy through the fade).
export function foldLoop(x, xf) {
  const n = x.length - xf; const o = x.slice(0, n);
  for (let i = 0; i < xf; i++) { const t = (i + 0.5) / xf; o[i] = x[i] * Math.sin(t * Math.PI / 2) + x[n + i] * Math.cos(t * Math.PI / 2); }
  return o;
}
function fadeEdges(x, sr, inS = 0.002, outS = 0.01) { const a = Math.max(1, Math.round(inS * sr)), b = Math.max(1, Math.round(outS * sr)); for (let i = 0; i < a && i < x.length; i++) x[i] *= i / a; for (let i = 0; i < b && i < x.length; i++) x[x.length - 1 - i] *= i / b; return x; }

// ---------- bubbles (Minnaert / van den Doel) ----------
export const minnaertHz = (rMeters) => 3.26 / rMeters;
// Decay rate d (1/s) for a bubble of resonance f0, van den Doel's fit d = 0.043 f0 + 0.0014 f0^1.5.
export const bubbleDecay = (f0) => 0.043 * f0 + 0.0014 * Math.pow(f0, 1.5);
// Add one bubble into out at sample index at. xi controls the pitch rise (0.1 for free-rising bubbles,
// larger for drop-impact bubbles that chirp upward, the "plink").
export function bubble(out, at, sr, f0, amp, xi = 0.1, maxDur = 0.6, floorDb = -60) {
  const d = bubbleDecay(f0), sigma = xi * d;
  const dur = Math.min(maxDur, (-floorDb / 8.686) / d); const n = Math.min(Math.ceil(dur * sr), out.length - at);
  const att = Math.max(2, Math.round(0.0004 * sr)); const k = Math.exp(-d / sr); const w0 = TAU * f0 / sr, dw = w0 * sigma / sr;
  let ph = 0, env = amp, w = w0;
  for (let i = 0; i < n; i++) {
    ph += w; w += dw; env *= k;
    out[at + i] += Math.sin(ph) * (i < att ? env * i / att : env);
  }
}
// Power-law radius sampler r^-alpha between rmin and rmax (metres), inverse-CDF.
export function radiusSampler(rmin, rmax, alpha, R) {
  const e = 1 - alpha;
  return () => { const u = R(); return Math.pow(Math.pow(rmin, e) + u * (Math.pow(rmax, e) - Math.pow(rmin, e)), 1 / e); };
}
// A cloud of bubbles. rate may be a number (per second) or a Float32Array rate envelope (per sample, per second).
export function bubbleCloud(n, sr, R, { rate = 100, rmin = 0.001, rmax = 0.01, alpha = 2.5, ampExp = 1.0, xi = 0.1, xiJit = 0.05, gain = 1 }) {
  const out = new Float32Array(n); const pick = radiusSampler(rmin, rmax, alpha, R);
  const per = typeof rate !== 'number'; let i = 0;
  while (i < n) {
    const rr = per ? Math.max(0.5, rate[i]) : rate;
    i += Math.max(1, Math.round(-Math.log(1 - R()) / rr * sr)); if (i >= n) break;
    const r = pick(); const f0 = minnaertHz(r); if (f0 > 16000) continue;
    const amp = gain * Math.pow(r / rmax, ampExp) * (0.4 + 0.6 * R());
    bubble(out, i, sr, f0, amp, xi + xiJit * (R() * 2 - 1), 0.25, -45);
  }
  return out;
}

// ---------- water textures ----------
function loopWrap(fn, sr, secs, xf = 1.0) { const n = Math.round(secs * sr), x = Math.round(xf * sr); const chs = fn(n + x); return chs.map((c) => foldLoop(c, x)); }

// Babbling stream / brook (arrival hall stream, lobby rills): clustered mid-size bubbles + soft wash.
export function brook(sr, secs, seed = 11, { busy = 1.0, bright = 1.0 } = {}) {
  const R = rng(seed);
  return loopWrap((n) => {
    const gurgle = smoothRandom(n, sr, 3.0, R, 0.15, 1.0); const rate = new Float32Array(n);
    for (let i = 0; i < n; i++) rate[i] = 380 * busy * Math.pow(gurgle[i], 2.0);
    const b = bubbleCloud(n, sr, R, { rate, rmin: 0.0008 / bright, rmax: 0.009, alpha: 2.3, ampExp: 0.5, xi: 0.12, gain: 0.5 });
    const spray = hp(white(n, R), sr, 3500); for (let i = 0; i < n; i++) spray[i] *= gurgle[i] * gurgle[i]; add(b, spray, 0.035);
    const wash = bp(pink(n, R), sr, 1100 * bright, 0.5); mul(wash, smoothRandom(n, sr, 1.2, R, 0.5, 1));
    add(b, wash, 0.10);
    return normRms([hp(b, sr, 120)], -20);
  }, sr, secs);
}
// Tinkling rill / wall trickle / basin spout: sparse, small, bright bubbles with drop-impact chirps.
export function rill(sr, secs, seed = 21, { rate = 40, pitch = 1.0 } = {}) {
  const R = rng(seed);
  return loopWrap((n) => {
    const env = smoothRandom(n, sr, 1.5, R, 0.4, 1.0); const rr = new Float32Array(n); for (let i = 0; i < n; i++) rr[i] = rate * env[i];
    const b = bubbleCloud(n, sr, R, { rate: rr, rmin: 0.0007 / pitch, rmax: 0.0045 / pitch, alpha: 2.0, ampExp: 0.3, xi: 0.25, xiJit: 0.15, gain: 0.6 });
    const fizz = bubbleCloud(n, sr, R, { rate: rate * 6, rmin: 0.0004, rmax: 0.0012, alpha: 2.5, ampExp: 0.5, xi: 0.1, gain: 0.08 });
    add(b, fizz); add(b, hp(pink(n, R), sr, 3000), 0.012);
    return normRms([hp(b, sr, 200)], -22);
  }, sr, secs);
}
// Fast river: rushing broadband body + dense low gurgle. The rush is noise (turbulence and countless
// unresolved bubbles), the gurgle keeps it from sounding like wind.
export function river(sr, secs, seed = 31, { size = 1.0 } = {}) {
  const R = rng(seed);
  return loopWrap((n) => {
    const body = add(lp(brown(n, R), sr, 500 * size), bp(pink(n, R), sr, 900, 0.4), 0.9);
    mul(body, smoothRandom(n, sr, 0.7, R, 0.75, 1.0));
    const hiss = mul(hp(white(n, R), sr, 2500), smoothRandom(n, sr, 2, R, 0.4, 0.8));
    const gurg = bubbleCloud(n, sr, R, { rate: 900, rmin: 0.002, rmax: 0.02, alpha: 2.0, ampExp: 0.8, xi: 0.1, gain: 0.25 });
    const out = add(add(body, hiss, 0.32), gurg, 0.6);
    add(out, bubbleCloud(n, sr, R, { rate: 1600, rmin: 0.0007, rmax: 0.003, alpha: 2.4, ampExp: 0.6, xi: 0.15, gain: 0.12 }));
    return normRms([hp(out, sr, 60)], -18);
  }, sr, secs);
}
// Big waterfall roar (Thunder Curtain, river inflow): massive broadband noise with fast impact flutter.
export function falls(sr, secs, seed = 41, { weight = 1.0 } = {}) {
  const R = rng(seed);
  return loopWrap((n) => {
    const chs = [0].map(() => {
      const lo = lp(brown(n, R), sr, 260 * weight); const mid = bp(pink(n, R), sr, 700, 0.35); const hi = hp(pink(n, R), sr, 1800);
      const flutter = smoothRandom(n, sr, 18, R, 0.7, 1.0);
      const o = new Float32Array(n); for (let i = 0; i < n; i++) o[i] = (lo[i] * 0.6 * weight + mid[i] * 1.0 + hi[i] * 0.9) * flutter[i];
      add(o, bubbleCloud(n, sr, R, { rate: 350, rmin: 0.004, rmax: 0.015, alpha: 1.8, ampExp: 1.0, gain: 0.25 }));
      return hp(o, sr, 45);
    });
    return normRms(chs, -17);
  }, sr, secs);
}
// Water curtain / thin sheet into a trough (Kawagiri pods, Mist Steps, spill lips): hiss + dense droplets.
export function curtain(sr, secs, seed = 51, { height = 1.0 } = {}) {
  const R = rng(seed);
  return loopWrap((n) => {
    const hiss = bp(pink(n, R), sr, 2600 * Math.sqrt(height), 0.6); mul(hiss, smoothRandom(n, sr, 6, R, 0.7, 1));
    const drops = bubbleCloud(n, sr, R, { rate: 1800 * height, rmin: 0.0006, rmax: 0.004, alpha: 2.4, ampExp: 0.7, xi: 0.18, gain: 0.35 });
    const o = add(hiss, drops, 1.0); add(o, lp(pink(n, R), sr, 400), 0.15 * height);
    return normRms([hp(o, sr, 150)], -20);
  }, sr, secs);
}
// Rimstone / Mist Steps cascade: many small spills, between brook and curtain, stereo spread.
export function cascade(sr, secs, seed = 61) {
  const R = rng(seed);
  return loopWrap((n) => {
    const chs = [0].map(() => {
      const a = bubbleCloud(n, sr, R, { rate: mulEnv(n, sr, R, 500, 2.5), rmin: 0.0009, rmax: 0.007, alpha: 2.3, ampExp: 0.6, xi: 0.15, gain: 0.45 });
      add(a, bp(pink(n, R), sr, 1800, 0.5), 0.12); return hp(a, sr, 150);
    });
    return normRms(chs, -20);
  }, sr, secs);
}
function mulEnv(n, sr, R, base, rate) { const e = smoothRandom(n, sr, rate, R, 0.35, 1); for (let i = 0; i < n; i++) e[i] *= base; return e; }

// Lazy river: slow, wide, gentle laps and the odd bloop.
export function lapping(sr, secs, seed = 71) {
  const R = rng(seed);
  return loopWrap((n) => {
    const swell = smoothRandom(n, sr, 0.6, R, 0, 1); const rr = new Float32Array(n); for (let i = 0; i < n; i++) rr[i] = 4 + 60 * Math.pow(swell[i], 3);
    const b = bubbleCloud(n, sr, R, { rate: rr, rmin: 0.003, rmax: 0.02, alpha: 1.8, ampExp: 0.7, xi: 0.08, gain: 0.5 });
    const slap = mul(bp(pink(n, R), sr, 500, 0.8), swell); add(b, slap, 0.15);
    return normRms([hp(b, sr, 60)], -22);
  }, sr, secs);
}

// ---------- air ----------
// Wind with gusts. Returns { chs:[L,R], gust: Float32Array (decimated control at 100 Hz) }.
export function wind(sr, secs, seed = 81, { strength = 1.0, whistle = 0.5 } = {}) {
  const R = rng(seed); const n = Math.round(secs * sr), x = Math.round(1.5 * sr), N = n + x;
  const g1 = smoothRandom(N, sr, 0.18, R, 0, 1), g2 = smoothRandom(N, sr, 0.9, R, 0, 1);
  const gust = new Float32Array(N); for (let i = 0; i < N; i++) gust[i] = clamp(0.15 + 0.6 * g1[i] * g1[i] + 0.25 * g2[i] * g1[i], 0, 1);
  const chs = [0, 1].map((c) => {
    const cut = new Float32Array(N); for (let i = 0; i < N; i++) cut[i] = 250 + 900 * gust[i];
    const body = bp(pink(N, R), sr, cut, 0.9); const low = lp(brown(N, R), sr, 120);
    const wcut = new Float32Array(N); const wf = 700 + 260 * c; for (let i = 0; i < N; i++) wcut[i] = wf * (0.8 + 0.6 * gust[i]);
    const wh = bp(white(N, R), sr, wcut, 25);
    const o = new Float32Array(N);
    for (let i = 0; i < N; i++) { const g = gust[i]; o[i] = body[i] * (0.25 + 1.6 * g * g) * strength + low[i] * 0.25 * g + wh[i] * whistle * 2.5 * Math.pow(Math.max(0, g - 0.45) / 0.55, 2); }
    return foldLoop(o, x);
  });
  normRms(chs, -21);
  const gl = foldLoop(gust, x); const dec = Math.round(sr / 100); const gd = new Float32Array(Math.floor(gl.length / dec)); for (let i = 0; i < gd.length; i++) gd[i] = gl[i * dec];
  return { chs, gust: gd };
}
// Steam / fumarole vent: jet hiss with breathing surges and a low chuff.
export function steam(sr, secs, seed = 91, { surge = 1.0 } = {}) {
  const R = rng(seed);
  return loopWrap((n) => {
    const breath = smoothRandom(n, sr, 0.35, R, 0.25, 1);
    const jet = mul(add(hp(white(n, R), sr, 2000), bp(white(n, R), sr, 4200, 2.5), 0.6), breath);
    const chuff = mul(lp(brown(n, R), sr, 180), breath); add(jet, chuff, 0.25 * surge);
    return normRms([jet], -22);
  }, sr, secs);
}

// ---------- sea ----------
// Surf on a black-sand beach inside a sea cave. period from layout waves.period_s. Stereo.
export function surf(sr, secs, seed = 101, { period = 9 } = {}) {
  const R = rng(seed); const n = Math.round(secs * sr), x = Math.round(2 * sr), N = n + x;
  const L = new Float32Array(N), Rr = new Float32Array(N);
  const waves = Math.ceil(N / (period * sr)) + 1;
  for (let w = 0; w < waves; w++) {
    const t0 = Math.round((w * period + (R() - 0.5) * 1.2) * sr); const size = 0.6 + 0.4 * R(); const pan = R() * 0.6 - 0.3;
    const len = Math.round(8.5 * sr); const env = new Float32Array(len), bri = new Float32Array(len);
    for (let i = 0; i < len; i++) {
      const t = i / sr; // swell 0-1.8 s, break at ~1.8 s, wash to 5 s, backwash hiss to 8 s
      const swell = t < 1.8 ? Math.pow(t / 1.8, 2) * 0.35 : 0;
      const crash = t >= 1.6 ? Math.min(1, (t - 1.6) / 0.35) * Math.exp(-Math.max(0, t - 1.95) / 0.9) : 0;
      const wash = t >= 2.0 ? Math.exp(-(t - 2.0) / 2.2) * 0.45 : 0;
      env[i] = (swell + crash + wash) * size * (i > len - sr ? (len - i) / sr : 1);
      bri[i] = 300 + 3500 * (crash * 0.8 + wash * 0.6) + 400 * swell;
    }
    for (const [ch, g] of [[L, 1 - pan], [Rr, 1 + pan]]) {
      const nz = svf(pink(len, R), sr, bri, 0.6, 'lp'); mul(nz, env);
      const fizz = bubbleCloud(len, sr, R, { rate: 1200, rmin: 0.0005, rmax: 0.003, alpha: 2.5, ampExp: 0.6, gain: 0.25 });
      for (let i = 0; i < len; i++) { const t = i / sr; fizz[i] *= (t > 2.2 ? Math.exp(-(t - 2.2) / 1.4) * size : 0) * (i > len - sr ? (len - i) / sr : 1); }
      add(nz, fizz); mixInto(ch, nz, Math.max(0, t0), g);
    }
  }
  const low = lp(brown(N, R), sr, 90); add(L, low, 0.1); add(Rr, low, 0.1);
  const chs = [foldLoop(hp(L, sr, 50), x), foldLoop(hp(Rr, sr, 50), x)];
  return normRms(chs, -21);
}

// ---------- fire and earth ----------
// Roiling lava heard through thick glass: low churn, slow heave, muffled crust ticks.
export function lava(sr, secs, seed = 111) {
  const R = rng(seed);
  return loopWrap((n) => {
    const heave = smoothRandom(n, sr, 0.12, R, 0.5, 1), churn = smoothRandom(n, sr, 1.3, R, 0.6, 1);
    const o = lp(brown(n, R), sr, 140); for (let i = 0; i < n; i++) o[i] *= heave[i] * churn[i];
    add(o, mul(bp(pink(n, R), sr, 220, 1.0), heave), 0.7);
    const ticks = new Float32Array(n); let i = 0; while (i < n) { i += Math.round(-Math.log(1 - R()) / 3 * sr); if (i >= n) break; const a = 0.2 + 0.8 * R(); for (let k = 0; k < 40 && i + k < n; k++) ticks[i + k] += a * (R() * 2 - 1) * Math.exp(-k / 8); }
    add(o, lp(ticks, sr, 900), 0.15);
    return normRms([hp(o, sr, 35)], -20);
  }, sr, secs);
}
// One viscous lava bubble bursting behind glass ("blorp"): a slow, low Minnaert-like bloop plus a soft thump.
export function blorp(sr, seed = 1) {
  const R = rng(seed); const n = Math.round(1.6 * sr); const o = new Float32Array(n);
  const f0 = 45 + 70 * R(); let ph = 0;
  for (let i = 0; i < n; i++) { const t = i / sr; const f = f0 * (1 + 0.5 * t); ph += TAU * f / sr; o[i] = Math.sin(ph) * Math.exp(-t * 6.5) * Math.min(1, t * 60); }
  const th = lp(white(n, R), sr, 200); for (let i = 0; i < n; i++) th[i] *= Math.exp(-i / sr * 12); add(o, th, 0.6);
  return normPeak([lp(o, sr, 500)], -3);
}
// Kitchen fryer / wok sizzle and grill crackle (Farnell-style crackle: Poisson clicks into band-pass).
export function sizzle(sr, secs, seed = 121) {
  const R = rng(seed);
  return loopWrap((n) => {
    const cr = new Float32Array(n); let i = 0; while (i < n) { i += 1 + Math.round(-Math.log(1 - R()) / 450 * sr); if (i < n) cr[i] = (R() * 2 - 1) * Math.pow(R(), 2); }
    const o = bp(cr, sr, 4500, 0.8); add(o, mul(hp(white(n, R), sr, 3000), smoothRandom(n, sr, 0.5, R, 0.4, 1)), 0.05);
    return normRms([o], -24);
  }, sr, secs);
}

// ---------- people ----------
// Distant restaurant murmur: N synthetic talkers (glottal pulse -> two moving formants, syllable rhythm,
// speech/pause turns). Honest note: up close it is recognisably synthetic; it is meant for 15 m+ and reverb.
export function murmur(sr, secs, seed = 131, { voices = 22 } = {}) {
  const R = rng(seed);
  const VOW = [[730, 1090], [270, 2290], [300, 870], [530, 1840], [570, 840], [440, 1020], [660, 1720]];
  return loopWrap((n) => {
    const chs = [new Float32Array(n), new Float32Array(n)];
    for (let v = 0; v < voices; v++) {
      const f0b = (R() < 0.5 ? 105 : 195) * (0.85 + 0.3 * R()); const pan = R();
      const src = new Float32Array(n), f1 = new Float32Array(n), f2 = new Float32Array(n), amp = new Float32Array(n);
      let ph = 0, syl = 0, sylLen = 1, talk = R() < 0.6, turn = Math.round((0.5 + 2.5 * R()) * sr), a = 0, tgt = 0, vi = 0, vj = 1;
      for (let i = 0; i < n; i++) {
        if (--turn <= 0) { talk = !talk; turn = Math.round((talk ? 0.8 + 2.8 * R() : 0.4 + 2.2 * R()) * sr); }
        if (--syl <= 0) { sylLen = Math.round((0.13 + 0.14 * R()) * sr); syl = sylLen; vi = vj; vj = Math.floor(R() * VOW.length); tgt = talk ? 0.4 + 0.6 * R() : 0; }
        const p = 1 - syl / sylLen; const se = Math.sin(Math.PI * p); a += (tgt * se - a) * 0.004;
        const into = Math.sin(TAU * i / sr * 0.7 + v) * 0.08; const f0 = f0b * (1 + into + 0.04 * se);
        ph += f0 / sr; if (ph >= 1) ph -= 1; src[i] = (ph < 0.12 ? 1 - ph / 0.06 : -0.15) + (R() - 0.5) * 0.1;
        f1[i] = VOW[vi][0] + (VOW[vj][0] - VOW[vi][0]) * p; f2[i] = VOW[vi][1] + (VOW[vj][1] - VOW[vi][1]) * p; amp[i] = a;
      }
      const s = add(bp(src, sr, f1, 6), bp(src, sr, f2, 8), 0.6); mul(s, amp);
      add(chs[0], s, 1 - pan * 0.7); add(chs[1], s, 0.3 + pan * 0.7);
    }
    return normRms(chs.map((c) => lp(hp(c, sr, 120), sr, 3200)), -22);
  }, sr, secs);
}
// Ceramic bowl / cup clink: 3-4 inharmonic partials, short.
export function clink(sr, seed = 1) {
  const R = rng(seed); const n = Math.round(0.6 * sr); const o = new Float32Array(n);
  const f0 = 1800 + 2600 * R(); const ratios = [1, 1.58 + 0.1 * R(), 2.6 + 0.2 * R(), 4.1 + 0.3 * R()];
  ratios.forEach((r, k) => { const f = f0 * r, d = 9 + 9 * k + 10 * R(), a = 1 / (1 + k); for (let i = 0; i < n; i++) o[i] += a * Math.sin(TAU * f * i / sr) * Math.exp(-d * i / sr); });
  for (let i = 0; i < 30; i++) o[i] += (R() * 2 - 1) * 0.3 * (1 - i / 30);
  return normPeak([fadeEdges(o, sr, 0.0005, 0.05)], -3);
}

// ---------- drips, plops ----------
// A drop falling into still water: tiny impact click, then a strongly up-chirping bubble (the "plink").
export function drip(sr, seed = 1, { size = 1.0 } = {}) {
  const R = rng(seed); const n = Math.round(0.35 * sr); const o = new Float32Array(n);
  for (let i = 0; i < 24; i++) o[i] += (R() * 2 - 1) * 0.15 * (1 - i / 24);
  const r = (0.0018 + 0.0028 * R()) * size; bubble(o, Math.round(0.002 * sr), sr, minnaertHz(r), 1.0, 0.15 + 0.2 * R(), 0.3);
  return normPeak([fadeEdges(o, sr)], -3);
}
export function plop(sr, seed = 1) { // koi surfacing / small splash
  const R = rng(seed); const n = Math.round(0.5 * sr); const o = new Float32Array(n);
  const sp = hp(white(n, R), sr, 1500); for (let i = 0; i < n; i++) sp[i] *= Math.exp(-i / sr * 30); add(o, sp, 0.25);
  bubble(o, Math.round(0.004 * sr), sr, minnaertHz(0.006 + 0.006 * R()), 1, 0.15, 0.4);
  for (let k = 0; k < 5; k++) bubble(o, Math.round((0.02 + 0.12 * R()) * sr), sr, minnaertHz(0.001 + 0.003 * R()), 0.25, 0.3, 0.2);
  return normPeak([fadeEdges(o, sr)], -3);
}

// ---------- bells ----------
function modal(sr, secs, partials, R, strike = 0.15) {
  const n = Math.round(secs * sr); const o = new Float32Array(n);
  for (const [f, a, t60, beat] of partials) {
    const d = 6.91 / t60; const fb = beat || 0;
    for (let i = 0; i < n; i++) { const t = i / sr; const e = Math.exp(-d * t); o[i] += a * e * (Math.sin(TAU * f * t) + (fb ? 0.7 * Math.sin(TAU * (f + fb) * t + 1.3) : 0)); }
  }
  const nz = hp(white(Math.round(0.01 * sr), R), sr, 2000); for (let i = 0; i < nz.length; i++) o[i] += strike * nz[i] * (1 - i / nz.length);
  return fadeEdges(o, sr, 0.0003, 0.2);
}
// Small bronze junction bell (rin-like): low hum-ish fundamental with beating pairs, long ring.
export function bell(sr, seed = 1, { f0 = 620 } = {}) {
  const R = rng(seed); const ratios = [[1, 1, 9, 0.6], [2.71, 0.55, 5, 1.1], [5.18, 0.32, 2.8, 1.9], [8.3, 0.18, 1.5, 2.7], [12.1, 0.09, 0.8, 0]];
  const p = ratios.map(([r, a, t, b]) => [f0 * r * (1 + (R() - 0.5) * 0.004), a * (0.9 + 0.2 * R()), t, b]);
  return normPeak([modal(sr, 6.5, p, R, 0.12)], -3);
}
// Furin (Nambu iron wind bell): bright, inharmonic, long tail; struck by the clapper in gusts.
export function furin(sr, seed = 1, { f0 = 1450 } = {}) {
  const R = rng(seed); const ff = f0 * (0.97 + 0.06 * R());
  const p = [[ff, 1, 3.2, 0.9], [ff * 2.32, 0.5, 2.0, 1.6], [ff * 4.08, 0.25, 1.1, 0], [ff * 6.3, 0.12, 0.5, 0]];
  return normPeak([modal(sr, 3.2, p, R, 0.3)], -3);
}

// ---------- the heartbeat ----------
// "Low-frequency microphones in the magma chamber play the mountain's own rumble, slowed down."
// Built as a seismic rumble then time-stretched 4x by resampling (pitch drops two octaves), plus a slow
// double-pulse. Harmonics at 2x/3x from soft saturation let phone speakers (which stop near 150 Hz) hint at it.
export function heartbeat(sr, secs, seed = 141, { bpm = 22 } = {}) {
  const R = rng(seed);
  return loopWrap((n) => {
    const m = Math.ceil(n / 4) + 8; const raw = lp(brown(m, R), sr, 240); mul(raw, smoothRandom(m, sr, 2.5, R, 0.4, 1));
    const slow = new Float32Array(n); for (let i = 0; i < n; i++) { const p = i / 4, k = Math.floor(p), f = p - k; slow[i] = raw[k] * (1 - f) + raw[k + 1] * f; }
    const beat = new Float32Array(n); const per = 60 / bpm;
    for (let i = 0; i < n; i++) { const t = (i / sr) % per; const pulse = (u, w) => (u > 0 && u < w ? Math.sin(Math.PI * u / w) : 0); const ph = TAU * 34 * i / sr; beat[i] = (pulse(t, 0.55) + 0.6 * pulse(t - 0.75, 0.6)) * (Math.sin(ph) + 0.55 * Math.sin(2 * ph) + 0.4 * Math.sin(3 * ph) + 0.3 * Math.sin(4 * ph) + 0.18 * Math.sin(5 * ph)); }
    const o = add(mul(slow, 0.9), beat, 0.9); softClip(o, 2.2);
    return normRms([lp(hp(o, sr, 18), sr, 400)], -18);
  }, sr, secs);
}
// Geyser eruption one-shot: pre-gurgle, whoosh, sustained jet, fall-back splatter (~1.7 s for a 14 m plume), steam tail.
export function geyser(sr, seed = 151, { big = true } = {}) {
  const R = rng(seed); const T = big ? 16 : 3.5; const n = Math.round(T * sr);
  const pre = big ? 2.5 : 0.4, jet = big ? 7 : 1.2; const fb = Math.sqrt(2 * (big ? 14 : 2) / 9.81);
  const env = new Float32Array(n), cut = new Float32Array(n), fall = new Float32Array(n), gurg = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const t = i / sr; const on = t - pre;
    gurg[i] = t < pre ? Math.pow(t / pre, 2) : on < 0.8 ? 1 - on / 0.8 : 0;
    env[i] = on < 0 ? 0 : on < 0.35 ? on / 0.35 : on < jet ? 1 - 0.25 * (on - 0.35) / jet : 0.75 * Math.exp(-(on - jet) / 1.6);
    cut[i] = 400 + 5000 * env[i];
    const f = on - fb; fall[i] = f < 0 ? 0 : f < jet ? Math.min(1, f / 0.5) : Math.exp(-(f - jet) / 1.2);
  }
  const rr = new Float32Array(n); for (let i = 0; i < n; i++) rr[i] = 5 + 120 * gurg[i];
  const o = bubbleCloud(n, sr, R, { rate: rr, rmin: 0.004, rmax: 0.03, alpha: 1.6, ampExp: 1, xi: 0.1, gain: 0.6 });
  const roar = mul(svf(pink(n, R), sr, cut, 0.5, 'lp'), env); add(o, roar, big ? 1.4 : 0.9);
  add(o, mul(lp(brown(n, R), sr, 120), env), big ? 0.7 : 0.2);
  const spl = bubbleCloud(n, sr, R, { rate: 2500, rmin: 0.0006, rmax: 0.004, alpha: 2.3, ampExp: 0.6, xi: 0.2, gain: 0.3 }); mul(spl, fall); add(o, spl, big ? 1 : 0.5);
  add(o, mul(hp(white(n, R), sr, 3000), fall), 0.05);
  return normPeak([fadeEdges(hp(o, sr, 30), sr, 0.01, 0.5)], -1.5);
}

// ---------- room tone ----------
export function roomtone(sr, secs, seed = 161, { tone = 1.0 } = {}) {
  const R = rng(seed);
  return loopWrap((n) => normRms([add(lp(pink(n, R), sr, 300 * tone), lp(brown(n, R), sr, 60), 0.5)], -30), sr, secs);
}

// ---------- reverb impulse responses ----------
// Exponentially decaying stereo noise in two bands (rtLow below xover, rtHigh above), sparse early reflections,
// pre-delay. Length capped so phone convolvers stay cheap.
export function impulse(sr, { rt = 2, rtHigh = null, predelay = 0.01, early = 6, size = 20, cap = 4.5, seed = 171 } = {}) {
  const R = rng(seed); const len = Math.round(Math.min(cap, rt * 1.15 + predelay) * sr); const pd = Math.round(predelay * sr);
  const rh = rtHigh || rt * 0.6;
  return [0, 1].map((c) => {
    const lo = lp(white(len, R), sr, 1200), hi = hp(white(len, R), sr, 1200); const o = new Float32Array(len);
    for (let i = pd; i < len; i++) { const t = (i - pd) / sr; const fade = Math.min(1, t / 0.02); o[i] = (lo[i] * Math.exp(-6.91 * t / rt) + hi[i] * Math.exp(-6.91 * t / rh)) * fade; }
    for (let k = 0; k < early; k++) { const t = pd + Math.round((0.003 + R() * size / 343) * sr); if (t < len) o[t] += (R() < 0.5 ? -1 : 1) * (0.3 + 0.5 * R()) / (1 + k * 0.3); }
    for (let i = len - Math.round(0.05 * sr); i < len; i++) o[i] *= (len - i) / (0.05 * sr);
    return o;
  }); // normalised by the engine
}

// ======================================================================================================
// Round 2: big moving water as a NOISE BANK, not a bubble cloud.
// Field recordings of waterfalls and rapids are broadband and noise-like (spectral flatness 0.70-0.79 in
// 400 Hz-4 kHz in the CC0 references measured in README section 11), fall 2-4.6 dB/octave above 1 kHz, and only
// fluctuate 1-3 dB per band at 20 ms. Big falls put as much energy below 250 Hz as above (the "thunder").
// So: octave bands of noise shaped to a measured template, each band slowly and independently modulated (so it is
// not static pink noise), a shared slow surge, granular noise "spray" grains for fine liquid texture, and low
// impacts for the pounding of a heavy fall. Bubbles survive only as a quiet texture layer.
// ======================================================================================================
export const OCT = [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];
// Octave-band templates (dB re total), fitted to the CC0 reference recordings (README section 11).
export const TEMPLATES = {
  rapids:   [-40, -25, -15, -9, -5.5, -5, -7, -10, -15, -24],   // fast river / rapids (Auxide_Audio, kyles, ThanksForTheInspiration)
  thunder:  [-11, -7.5, -6.5, -7, -9, -10.5, -12, -14, -17, -26], // big falls, heard close (A.Deathy, deleted_user_7146007)
  falls:    [-32, -20, -13, -9, -6, -6, -7.5, -9, -14, -23],     // medium falls (Fabrizio84, nsmusic)
  sheet:    [-38, -24, -15, -9, -6.5, -6, -7.5, -9, -13, -18],   // shallow sheets, spill lips, cascades (Breviceps)
  stream:   [-46, -34, -23, -14, -8, -5.5, -5.5, -8, -13, -22],  // shallow fast stream
  seacave:  [-12, -9, -10.5, -10, -9, -10, -13, -11, -16, -26],  // surf in a sea cave (Andy_Gardner)
  rock:     [-6, -4, -6, -14, -30, -50, -70, -90, -90, -90],     // the same water heard through rock
};
// Granular noise grains: short Hann-windowed band-passed noise, Poisson in time, log-normal amplitudes.
export function grains(n, sr, R, { rate = 600, lo = 1500, hi = 7000, msMin = 2, msMax = 10, spread = 1.0, gain = 1 } = {}) {
  const o = new Float32Array(n); let i = 0;
  while (i < n) {
    i += Math.max(1, Math.round(-Math.log(1 - R()) / rate * sr)); if (i >= n) break;
    const len = Math.max(4, Math.round((msMin + (msMax - msMin) * R()) * 0.001 * sr));
    const a = gain * Math.exp(spread * (R() * 2 - 1) * 1.2);
    for (let k = 0; k < len && i + k < n; k++) o[i + k] += a * (R() * 2 - 1) * 0.5 * (1 - Math.cos(TAU * k / len));
  }
  return lp(hp(o, sr, lo, 0.6), sr, Math.min(hi, sr * 0.45), 0.6);
}
// The core: octave-band noise bank shaped to a template. modDb = per-band modulation depth (dB), rates 0.4-3 Hz.
// Octave levels (dB re total) measured with a 4th-order band-pass per octave (two cascaded SVF band-passes).
export function octaveLevels(x, sr) {
  const tot = rms(x) + 1e-12;
  return OCT.map((fc) => (fc > sr * 0.42 ? null : linToDb(rms(bp(bp(x, sr, fc, 1.41), sr, fc, 1.41)) / tot)));
}
// extras(n) may return a Float32Array that is added before calibration (grains, impacts), so the FINAL spectrum
// matches the template. Three calibration passes adjust the band weights.
export function noiseBank(n, sr, R, template, { modDb = 1.5, lowModDb = 2.5, surgeDb = 1.2, tilt = 0, extras = null } = {}) {
  const surge = smoothRandom(n, sr, 0.15, R, -1, 1); const bands = [], w = [], tgt = [];
  OCT.forEach((fc, b) => {
    if (fc > sr * 0.42) return;
    const band = svf(white(n, R), sr, fc, 1.2, 'bp'); const r = rms(band) + 1e-12;
    const depth = fc < 250 ? lowModDb : modDb; const mod = smoothRandom(n, sr, 0.4 + 2.6 * R() * (fc > 1000 ? 1 : 0.5), R, -1, 1);
    for (let i = 0; i < n; i++) band[i] = band[i] / r * dbToLin(depth * mod[i] + surgeDb * surge[i]);
    bands.push({ b, band }); tgt.push(template[b] + tilt * Math.log2(fc / 1000)); w.push(dbToLin(template[b] + tilt * Math.log2(fc / 1000)));
  });
  const ex = extras ? extras(n) : null;
  const sum = () => { const o = new Float32Array(n); bands.forEach(({ band }, k) => { const g = w[k]; for (let i = 0; i < n; i++) o[i] += band[i] * g; }); if (ex) { const g = rms(o) * ex.rel / (rms(ex.sig) + 1e-12); add(o, ex.sig, g); } return o; };
  let o = sum();
  for (let it = 0; it < 3; it++) {
    const lv = octaveLevels(o, sr); const ref = Math.max(...tgt.map((t, k) => lv[bands[k].b] - t));
    bands.forEach(({ b }, k) => { w[k] *= dbToLin(0.85 * (tgt[k] - (lv[b] - ref))); });
    o = sum();
  }
  return o;
}
// Rushing water bed (rivers, rapids, inflow). detail = spray grains level (dB re bed), bubbles = optional glug layer.
export function rush(sr, secs, seed = 201, { template = 'rapids', detail = -14, bubbles = -60, tilt = 0, modDb = 2.2 } = {}) {
  const R = rng(seed);
  return loopWrap((n) => {
    const o = noiseBank(n, sr, R, TEMPLATES[template], { tilt, modDb, extras: (m) => ({ sig: grains(m, sr, R, { rate: 900, lo: 900, hi: Math.min(9000, sr * 0.4) }), rel: dbToLin(detail) }) });
    if (bubbles > -50) { const b = bubbleCloud(n, sr, R, { rate: 120, rmin: 0.002, rmax: 0.012, alpha: 2.2, ampExp: 0.6, xi: 0.1, gain: 1 }); add(o, b, dbToLin(bubbles) * rms(o) / (rms(b) + 1e-12)); }
    return normRms([hp(o, sr, 25)], -20);
  }, sr, secs);
}
// Heavy falls ("thunder"): thunder template + pounding low impacts + sub swell + spray.
export function thunder(sr, secs, seed = 211, { impacts = 9, detail = -16 } = {}) {
  const R = rng(seed);
  return loopWrap((n) => {
    const extras = (m) => {
      const im = new Float32Array(m); let i = 0;
      while (i < m) { i += Math.round(-Math.log(1 - R()) / impacts * sr); if (i >= m) break; const len = Math.round((0.04 + 0.08 * R()) * sr), a = Math.exp((R() - 0.5) * 1.4); for (let k = 0; k < len && i + k < m; k++) im[i + k] += a * (R() * 2 - 1) * Math.exp(-k / (len * 0.3)); }
      const imp = lp(lp(im, sr, 160), sr, 160); const g = grains(m, sr, R, { rate: 1400, lo: 1200, hi: Math.min(9000, sr * 0.4) });
      const s2 = add(mul(imp, 1 / (rms(imp) + 1e-12)), g, dbToLin(detail) / (rms(g) + 1e-12)); return { sig: s2, rel: 0.55 };
    };
    const o = noiseBank(n, sr, R, TEMPLATES.thunder, { modDb: 2.0, lowModDb: 3.0, surgeDb: 1.5, extras });
    return normRms([hp(o, sr, 22)], -18);
  }, sr, secs);
}
// Near-field spray: what you hear only within a few metres of falling water (droplet hiss and splashes).
export function spray(sr, secs, seed = 221) {
  const R = rng(seed);
  return loopWrap((n) => {
    const g = grains(n, sr, R, { rate: 2500, lo: 1500, hi: Math.min(12000, sr * 0.42), msMin: 1, msMax: 6 });
    add(g, mul(hp(white(n, R), sr, 3000), smoothRandom(n, sr, 3, R, 0.5, 1)), 0.15 * rms(g) / 0.3);
    add(g, bubbleCloud(n, sr, R, { rate: 600, rmin: 0.0005, rmax: 0.002, alpha: 2.5, ampExp: 0.5, xi: 0.2, gain: 0.05 }));
    return normRms([hp(g, sr, 600)], -22);
  }, sr, secs);
}
// The river and falls heard through tens of metres of basalt: only the rumble survives.
export function rockRumble(sr, secs, seed = 231) {
  const R = rng(seed);
  return loopWrap((n) => normRms([hp(noiseBank(n, sr, R, TEMPLATES.rock, { modDb: 2, lowModDb: 3.5, surgeDb: 2 }), sr, 20)], -20), sr, secs);
}
// Shallow fast stream (arrival hall): rush in a brighter template, a few bubbles as texture.
export const stream2 = (sr, secs, seed = 241) => rush(sr, secs, seed, { template: 'stream', detail: -10, bubbles: -16, modDb: 2.6 });
// Sheets, spill lips, curtains, cascades: sheet template with grains; cascade adds a quiet bubble layer.
export const sheet2 = (sr, secs, seed = 251, tilt = 0) => rush(sr, secs, seed, { template: 'sheet', detail: -9, tilt, modDb: 2.2 });
export const cascade2 = (sr, secs, seed = 261) => rush(sr, secs, seed, { template: 'sheet', detail: -11, bubbles: -18, modDb: 2.2 });
// Surf in the sea cave, round 2: the old wave envelope on top of a sea-cave noise bank (boom and wash).
export function surf2(sr, secs, seed = 271, { period = 9 } = {}) {
  const R = rng(seed); const n = Math.round(secs * sr), x = Math.round(2 * sr), N = n + x;
  const base = noiseBank(N, sr, R, TEMPLATES.seacave, { modDb: 2, lowModDb: 3, surgeDb: 2 });
  const env = new Float32Array(N), cut = new Float32Array(N);
  // Round 3: irregular sets. Intervals 0.65-1.45 x period, 20 % chance of a quick second wave 2-3.5 s behind,
  // sizes 0.5-1.15 and per-wave break sharpness, so no two waves arrive alike (round 2 was a near-metronome).
  const t0s = []; const sz = []; const atk = []; let tw = -1 - R() * 2;
  while (tw < N / sr + 8) { t0s.push(tw); sz.push(0.5 + 0.65 * R()); atk.push(0.25 + 0.35 * R()); if (R() < 0.2) { t0s.push(tw + 2 + 1.5 * R()); sz.push(0.35 + 0.4 * R()); atk.push(0.2 + 0.2 * R()); } tw += period * (0.65 + 0.8 * Math.pow(R(), 1.2)); }
  for (let i = 0; i < N; i++) {
    const t = i / sr; let e = 0.25;
    for (let w = 0; w < t0s.length; w++) { const u = t - t0s[w]; if (u > -1.6 && u < 7) e += sz[w] * (u < 0 ? 0.35 * Math.pow((u + 1.6) / 1.6, 2) : Math.min(1, u / atk[w]) * (0.9 * Math.exp(-u / 1.1) + 0.35 * Math.exp(-u / 3.2))); }
    env[i] = e; cut[i] = 500 + 6000 * Math.min(1, e);
  }
  const shaped = mul(svf(base, sr, cut, 0.6, 'lp'), env);
  const L = foldLoop(hp(shaped, sr, 30), x);
  const Rr = foldLoop(hp(mul(svf(noiseBank(N, sr, R, TEMPLATES.seacave, { modDb: 2, lowModDb: 3, surgeDb: 2 }), sr, cut, 0.6, 'lp'), env), sr, 30), x);
  return normRms([L, Rr], -20);
}
