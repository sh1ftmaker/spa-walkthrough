// Kazan-yu mist: main-thread side. Owns one simulation zone (worker or main thread), the two RGBA8 field
// textures it interpolates between, the uniforms, and the GLSL that turns the field into a lit height-fog
// layer (Low: analytic per-ray integral with two field taps; High: few-slice raymarch).
//
//   const zone = new MistZone({...}); zone.start('low', 'worker');
//   material.uniforms = { ...zone.uniforms, ... };  fragment: MIST_GLSL + `col = mistApply(col, wpos);`
//   each frame: zone.setMovers([...]); zone.update(performance.now());
import * as THREE from 'three';
import { MistSim, PACK_VMAX } from './mist-worker.js';

export const MAX_LIGHTS = 6;

// ------------------------------------------------------------------ geometry helpers
// layout / Blender (x east, y north, z up) -> three (X = x, Y = z, Z = -y), optionally re-centred
export const layoutToWorld = (x, y, z = 0, o = [0, 0, 0]) => [x - o[0], z - o[2], -(y - o[1])];
export function pointInPoly(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
export function distToPolyline(x, z, pts) {
  let best = 1e9;
  for (let i = 0; i + 1 < pts.length; i++) {
    const [ax, az] = pts[i], [bx, bz] = pts[i + 1];
    const dx = bx - ax, dz = bz - az; const L = dx * dx + dz * dz;
    const t = L > 0 ? Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / L)) : 0;
    best = Math.min(best, Math.hypot(x - ax - t * dx, z - az - t * dz));
  }
  return best;
}

// ------------------------------------------------------------------ GLSL
export const MIST_GLSL = /* glsl */`
uniform sampler2D tMistA; uniform sampler2D tMistB; uniform float uMistBlend;
uniform vec4 uMistRect;     // minX, minZ, maxX, maxZ (world)
uniform vec4 uMistShape;    // water y, base layer height H0, max height Hmax (hot / spray), extinction at d = 1 (1/m)
uniform vec4 uMistLook;     // detail amount, detail scale (1/m), flow-noise period (s), haze density (1/m)
uniform vec4 uMistLPos[${MAX_LIGHTS}]; uniform vec4 uMistLCol[${MAX_LIGHTS}];
uniform vec3 uMistAmb; uniform vec3 uMistGlow; uniform vec3 uMistHaze;
uniform sampler2D tMistNoise; uniform sampler3D tMistNoise3; uniform float uMistTime; uniform float uMistOn;
uniform float uMistDebug;

vec4 mistField(vec2 xz){
  vec2 uv = (xz - uMistRect.xy)/(uMistRect.zw - uMistRect.xy);
  vec4 m = mix(texture(tMistA, uv), texture(tMistB, uv), uMistBlend);
  m.x *= m.x;                                          // density was sqrt-encoded
  m.zw = (m.zw*(255.0/127.5) - 1.0)*${PACK_VMAX.toFixed(1)}; // m/s
  return m;
}
// Two-phase flow noise (Vlachos 2010): noise advected by the sim velocity, reset every half period with
// a triangle cross-fade, so detail far finer than the grid moves with the flow at the display rate.
float mistFlowNoise(vec2 xz, vec2 vel, float taps){
  float P = uMistLook.z; float ph = uMistTime/P;
  float f0 = fract(ph), f1 = fract(ph + 0.5);
  float w0 = 1.0 - abs(2.0*f0 - 1.0);
  vec2 s = xz*uMistLook.y;
  vec2 o0 = vel*(f0*P)*uMistLook.y, o1 = vel*(f1*P)*uMistLook.y;
  float n0 = texture(tMistNoise, s - o0).r, n1 = texture(tMistNoise, s - o1 + vec2(0.37, 0.61)).r;
  if (taps > 1.5){
    n0 = n0*0.62 + 0.38*texture(tMistNoise, s*2.7 - o0*2.7 + vec2(0.13, 0.71)).a;
    n1 = n1*0.62 + 0.38*texture(tMistNoise, s*2.7 - o1*2.7 + vec2(0.53, 0.29)).a;
  }
  return mix(n1, n0, w0);
}
// in-scattered light at p towards the eye (rd = view ray direction, camera -> p)
#ifndef MIST_NL
#define MIST_NL ${MAX_LIGHTS}
#endif
vec3 mistLight(vec3 p, vec3 rd, float heat){
  float h = max(p.y - uMistShape.x, 0.0);
  vec3 c = uMistAmb + uMistGlow*exp(-h*2.2);           // teal light coming up off the water
  for (int i = 0; i < MIST_NL; i++){                    // Low: the first 3 lights only (put the important ones first)
    vec3 L = uMistLPos[i].xyz - p; float d2 = dot(L, L) + 0.04;
    float cs = dot(L*inversesqrt(d2), rd);
    float hg = 0.1875/pow(1.5625 - 1.5*cs, 1.5);         // Henyey-Greenstein g = 0.6, normalised so cs = 0 gives ~0.1
    c += uMistLCol[i].rgb*(0.35 + 2.2*hg)/(1.0 + d2*uMistLPos[i].w);
  }
  return c*(1.0 + 0.25*heat);
}
// segment camera -> wp clipped to the mist slab; returns (t0, t1) in [0, 1] of the segment
vec2 mistClip(vec3 ro, vec3 rd, float ytop){
  vec3 bmin = vec3(uMistRect.x, uMistShape.x - 0.02, uMistRect.y), bmax = vec3(uMistRect.z, ytop, uMistRect.w);
  vec3 inv = 1.0/(rd + vec3(1e-6));
  vec3 a = (bmin - ro)*inv, b = (bmax - ro)*inv;
  vec3 lo = min(a, b), hi = max(a, b);
  return vec2(max(max(lo.x, lo.y), max(lo.z, 0.0)), min(min(hi.x, hi.y), min(hi.z, 1.0)));
}
// exact optical depth of exp(-h/Hs) along a straight piece from height ha to hb, length len
float mistExpInt(float ha, float hb, float Hs, float len){
  float dh = hb - ha; float ea = exp(-max(ha, 0.0)/Hs), eb = exp(-max(hb, 0.0)/Hs);
  return len*(abs(dh) < 1e-3 ? ea : Hs*(ea - eb)/dh);
}
// coverage from noise: thin mist breaks into wisps and holes, thick mist stays mostly solid
float mistDetail(float d, float n){
#ifdef MIST_HIGH
  float k = uMistLook.x;
#else
  float k = uMistLook.x*0.45;   // one tap per half-ray reads as a texture on a sheet: keep the contrast low
#endif
  float c = clamp((n - 0.5)*3.2 + 0.5 + 0.7*(d - 0.3), 0.0, 1.0); return d*mix(1.0, c*c*(3.0 - 2.0*c)*1.9, k); }

// returns (premultiplied in-scatter, alpha)
vec4 mistTerms(vec3 wp){
  if (uMistOn < 0.5) return vec4(0.0);
  vec3 ro = cameraPosition; vec3 seg = wp - ro; float len = length(seg); vec3 rd = seg/max(len, 1e-4);
  vec4 haze = vec4(uMistHaze, 1.0)*(1.0 - exp(-uMistLook.w*len));
  float ytop = uMistShape.x + uMistShape.z*1.45;
  vec2 tt = mistClip(ro, seg, ytop);
  if (tt.y <= tt.x) return haze;
  vec3 col = vec3(0.0); float T = 1.0;
#ifdef MIST_HIGH
  // few-slice raymarch (High): field x flow detail x 3D-noise-perturbed vertical profile, lit per slice
  // slice count follows the in-layer path length (grazing rays are long), 3..MIST_SLICES
  float segLen = (tt.y - tt.x)*len; int NS = int(clamp(ceil(segLen/0.3), 3.0, float(MIST_SLICES))); float ds = segLen/float(NS);
  float jit = 0.4 + 0.2*fract(52.9829189*fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
  for (int k = 0; k < MIST_SLICES; k++){
    if (k >= NS) break;
    float t = tt.x + (float(k) + jit)/float(NS)*(tt.y - tt.x);
    vec3 p = ro + seg*t;
    vec4 m = mistField(p.xz);
    if (m.x < 0.003) continue;
    float h = p.y - uMistShape.x;
    float Hl = mix(uMistShape.y, uMistShape.z, clamp(m.y, 0.0, 1.0));
    // billowy top: a coarse flow-advected height field, so the layer's silhouette has lumps and gaps
    float fs = inversesqrt(max(Hl/0.6, 1.0));   // taller layers get bigger, rounder billows
    float fl = mistFlowNoise(p.xz, m.zw, 2.0);
    float big = texture(tMistNoise, p.xz*uMistLook.y*0.35*fs - m.zw*0.05 + vec2(uMistTime*0.006, 0.0)).r;
    // detail level follows the slice spacing: long steps cannot resolve billows, so they get a flatter layer
    // (otherwise the top boundary aliases into hair-like spikes on grazing rays)
    float lod = clamp(1.25 - ds*0.9, 0.15, 1.0);
    float top = Hl*(0.35 + 1.4*big*big*(0.85 + 0.3*fl*lod));   // coarse billows always; the fine noise only where resolved
    // wisps: 3D noise rising slowly through the layer
    vec4 n3 = texture(tMistNoise3, vec3(p.xz*0.3*fs, h*0.45*fs - uMistTime*0.05));
    float prof = (1.0 - smoothstep(top*0.35, top, h))*(0.55 + 0.45*exp(-h/(0.6*Hl)));
    float dd = mistDetail(m.x, mix(0.5, fl*0.55 + n3.r*0.45, lod))*prof*mix(1.0, 0.5 + n3.g, lod);
    float sig = uMistShape.w*dd;
    float a = 1.0 - exp(-sig*ds);
    col += T*a*mistLight(p, rd, m.y);
    T *= 1.0 - a;
    if (T < 0.02) break;
  }
#else
  // analytic (Low): split the in-slab piece in two, one field tap per half, and integrate a vertical profile
  // (1 - h/Ht)^3 exactly along each straight half: it has a soft top (no exp tail climbing the walls) and a
  // closed-form integral, so it costs the same as the old exponential
  // the split and the taps sit at fixed distances from where the ray enters the layer (not at fractions of
  // the segment), so neighbouring pixels on a bumpy wall share their taps and the result stays smooth
  float segL = (tt.y - tt.x)*len; float sSplit = min(segL*0.5, 2.5);
  float tSplit = tt.x + sSplit/len;
  for (int k = 0; k < 2; k++){
    float ta = k == 0 ? tt.x : tSplit, tb = k == 0 ? tSplit : tt.y;
    float tm = k == 0 ? tt.x + 0.5*sSplit/len : tSplit + 0.5*min(segL - sSplit, 7.0)/len;
    vec3 pa = ro + seg*ta, pb = ro + seg*tb, pm = ro + seg*tm;
    vec4 m = mistField(pm.xz);
    float fn = mistFlowNoise(pm.xz, m.zw, 1.0);
    float Ht = 1.25*mix(uMistShape.y, uMistShape.z, clamp(m.y, 0.0, 1.0));   // smooth top: noise on the top streaks walls
    float ua = clamp((pa.y - uMistShape.x)/Ht, 0.0, 1.0), ub = clamp((pb.y - uMistShape.x)/Ht, 0.0, 1.0);
    float du = (pb.y - pa.y)/Ht; float seglen = (tb - ta)*len;
    float I = abs(du) < 1e-4 ? seglen*pow(1.0 - ua, 3.0) : seglen*(pow(1.0 - ua, 4.0) - pow(1.0 - ub, 4.0))/(4.0*du);
    float dd = mistDetail(m.x, fn);
    float tau = uMistShape.w*1.3*dd*I;
    float a = 1.0 - exp(-tau);
    // light the piece at its densest point (a quarter of the way up the layer, clamped into the segment)
    vec3 pl = pm; pl.y = clamp(uMistShape.x + 0.25*Ht, min(pa.y, pb.y), max(pa.y, pb.y));
    col += T*a*mistLight(pl, rd, m.y);
    T *= 1.0 - a;
  }
#endif
  // haze sits behind/around the layer: composite it under the mist
  col += T*haze.rgb; float A = 1.0 - T*(1.0 - haze.a);
  return vec4(col, A);
}
vec3 mistApply(vec3 c, vec3 wp){ vec4 m = mistTerms(wp); return c*(1.0 - m.a) + m.rgb; }
// premultiplied blended surfaces (curtains, spray): the opaque surface behind already carries the mist of the
// whole ray, so a blended surface only fades out by the mist in front of it (adding in-scatter again doubles it)
vec4 mistApplyPM(vec4 c, vec3 wp){ vec4 m = mistTerms(wp); return c*(1.0 - m.a); }
`;

// ------------------------------------------------------------------ zone
export class MistZone {
  // opts: { rect: [minX, minZ, maxX, maxZ], y, H0, Hmax, sigma, tiers: { low: {h, hz, iters}, high: {...} },
  //         solid(x, z) -> bool, temp(x, z) -> water °C (0 = dry), open: {xmin, xmax, ymin, ymax},
  //         params, wind: [u, v] | (x, z) -> [u, v], jets: [...], prewarm (s), look: {...}, lights: [...] }
  constructor(opts) {
    this.o = opts;
    const r = opts.rect;
    this.uniforms = {
      tMistA: { value: null }, tMistB: { value: null }, uMistBlend: { value: 0 },
      uMistRect: { value: new THREE.Vector4(r[0], r[1], r[2], r[3]) },
      uMistShape: { value: new THREE.Vector4(opts.y, opts.H0 ?? 0.4, opts.Hmax ?? 1.0, opts.sigma ?? 2.5) },
      uMistLook: { value: new THREE.Vector4(opts.look?.detail ?? 0.75, opts.look?.scale ?? 0.32, opts.look?.period ?? 2.2, opts.look?.haze ?? 0.012) },
      uMistLPos: { value: Array.from({ length: MAX_LIGHTS }, () => new THREE.Vector4(0, -999, 0, 1)) },
      uMistLCol: { value: Array.from({ length: MAX_LIGHTS }, () => new THREE.Vector4(0, 0, 0, 0)) },
      uMistAmb: { value: new THREE.Vector3(...(opts.amb ?? [0.02, 0.022, 0.024])) },
      uMistGlow: { value: new THREE.Vector3(...(opts.glow ?? [0.01, 0.06, 0.055])) },
      uMistHaze: { value: new THREE.Vector3(...(opts.haze ?? [0.012, 0.011, 0.01])) },
      tMistNoise: { value: null }, tMistNoise3: { value: null }, uMistTime: { value: 0 }, uMistOn: { value: 1 }, uMistDebug: { value: 0 },
    };
    // runtime: pass a stable uniform object (e.g. the KZ block every patched material already references);
    // the zone then writes into those objects instead of its own, so materials compiled earlier keep working
    if (opts.uniforms) {
      for (const [k, v] of Object.entries(this.uniforms)) { if (opts.uniforms[k]) opts.uniforms[k].value = v.value; else opts.uniforms[k] = v; }
      this.uniforms = opts.uniforms;
    }
    if (opts.lights) this.setLights(opts.lights);
    this.mode = null; this.tier = null; this.worker = null; this.sim = null;
    this.movers = []; this.jets = opts.jets ?? [];
    this.stat = { stepMs: 0, stepP95: 0, packMs: 0, mainMs: 0, mainMsAvg: 0, frames: 0, fpsSim: 0, prewarmMs: 0, simBytes: 0, texBytes: 0, cells: 0, fluid: 0 };
    this._mainHist = []; this._recv = []; this._acc = 0; this._last = 0;
  }
  setLights(lights) {
    lights.slice(0, MAX_LIGHTS).forEach((l, i) => {
      this.uniforms.uMistLPos.value[i].set(l.pos[0], l.pos[1], l.pos[2], l.falloff ?? 1);
      this.uniforms.uMistLCol.value[i].set(l.color[0] * l.i, l.color[1] * l.i, l.color[2] * l.i, 0);
    });
  }
  setNoise(tex2d, tex3d) { this.uniforms.tMistNoise.value = tex2d; this.uniforms.tMistNoise3.value = tex3d; }

  _buildCfg(tier) {
    const o = this.o, t = o.tiers[tier]; const [x0, z0, x1, z1] = o.rect;
    const nx = Math.round((x1 - x0) / t.h), ny = Math.round((z1 - z0) / t.h);
    const solid = new Uint8Array(nx * ny), temp = new Float32Array(nx * ny);
    let fluid = 0;
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const x = x0 + (i + 0.5) * t.h, z = z0 + (j + 0.5) * t.h;
      const sol = o.solid ? !!o.solid(x, z) : false; solid[j * nx + i] = sol ? 1 : 0; if (!sol) fluid++;
      temp[j * nx + i] = sol ? 0 : (o.temp ? o.temp(x, z) : 0);
    }
    this.stat.cells = nx * ny; this.stat.fluid = fluid;
    return { nx, ny, h: t.h, minX: x0, minZ: z0, solid, temp, open: o.open ?? {}, params: Object.assign({}, o.params ?? {}, { iters: t.iters }) };
  }
  _windGrid(cfg) {
    const { nx, ny, h, minX, minZ } = cfg; const NX = nx + 2, NY = ny + 2;
    const u = new Float32Array(NX * NY), v = new Float32Array(NX * NY); const w = this.o.wind;
    if (!w) return { u, v };
    for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx; i++) {
      const vec = typeof w === 'function' ? w(minX + (i - 0.5) * h, minZ + (j - 0.5) * h) : w;
      u[j * NX + i] = vec[0]; v[j * NX + i] = vec[1];
    }
    return { u, v };
  }
  _makeTex(nx, ny) {
    const t = new THREE.DataTexture(new Uint8Array(nx * ny * 4), nx, ny, THREE.RGBAFormat, THREE.UnsignedByteType);
    t.minFilter = t.magFilter = THREE.LinearFilter; t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping; t.generateMipmaps = false;
    const d = t.image.data; for (let k = 0; k < d.length; k += 4) { d[k + 2] = 128; d[k + 3] = 128; }
    t.needsUpdate = true; return t;
  }

  // (re)start: tier 'low' | 'high', mode 'worker' | 'main'
  start(tier, mode) {
    this.stop();
    this.tier = tier; this.mode = mode;
    const cfg = this._buildCfg(tier); this.cfg = cfg;
    const t = this.o.tiers[tier]; this.hz = t.hz; this.period = 1000 / t.hz;
    this.uniforms.tMistA.value?.dispose(); this.uniforms.tMistB.value?.dispose();
    this.texA = this._makeTex(cfg.nx, cfg.ny); this.texB = this._makeTex(cfg.nx, cfg.ny);
    this.uniforms.tMistA.value = this.texA; this.uniforms.tMistB.value = this.texB;
    this.stat.texBytes = cfg.nx * cfg.ny * 4 * 2;
    const wind = this._windGrid(cfg);
    const prewarm = Math.round((this.o.prewarm ?? 6) * t.hz);
    this._recvAt = this._clock ?? performance.now(); this._acc = 0; this._last = 0; this._recv.length = 0;
    this.ready = false;
    if (mode === 'worker') {
      // written inline in this exact form so Vite bundles the worker (vite.dev/guide/features#web-workers)
      const w = new Worker(new URL('./mist-worker.js', import.meta.url), { type: 'module' }); this.worker = w;
      w.onmessage = (e) => this._onMsg(e.data);
      w.onerror = (e) => { console.error('mist worker error', e.message ?? e); };
      w.postMessage({ type: 'init', cfg, hz: t.hz, jets: this.jets, prewarm, windU: wind.u, windV: wind.v }, [wind.u.buffer, wind.v.buffer]);
    } else {
      const sim = new MistSim(cfg); this.sim = sim; sim.windU.set(wind.u); sim.windV.set(wind.v); sim.setJets(this.jets);
      const t0 = performance.now(); for (let k = 0; k < prewarm; k++) sim.step(1 / t.hz);
      this.stat.prewarmMs = performance.now() - t0; this.stat.simBytes = sim.bytes();
      this._packBuf = new Uint8Array(cfg.nx * cfg.ny * 4); this._stepHist = [];
      sim.pack(this._packBuf); this.texA.image.data.set(this._packBuf); this.texB.image.data.set(this._packBuf); this.texA.needsUpdate = this.texB.needsUpdate = true;
      this.ready = true;
    }
  }
  stop() {
    if (this.worker) { this.worker.postMessage({ type: 'stop' }); this.worker.terminate(); this.worker = null; }
    this.sim = null;
  }
  _onMsg(m) {
    if (m.type === 'ready') { this.stat.prewarmMs = m.prewarmMs; this.stat.simBytes = m.bytes; this.ready = true; return; }
    if (m.type !== 'frame') return;
    const t0 = performance.now();
    this._ingest(new Uint8Array(m.buf));
    this.worker?.postMessage({ type: 'buf', buf: m.buf }, [m.buf]);
    this.stat.stepMs = m.stepMs; this.stat.stepP95 = m.stepP95; this.stat.packMs = m.packMs;
    this._msgMs = (this._msgMs ?? 0) + (performance.now() - t0);
  }
  // new field: B becomes A, the new frame goes into the old A texture which becomes B (one upload per frame)
  _ingest(bytes) {
    const old = this.texA; this.texA = this.texB; this.texB = old;
    old.image.data.set(bytes); old.needsUpdate = true;
    this.uniforms.tMistA.value = this.texA; this.uniforms.tMistB.value = this.texB;
    const now = this.mode === 'main' && this._clock !== undefined ? this._clock : performance.now(); this._recvAt = now; this.stat.frames++;
    this._recv.push(now); while (this._recv.length && now - this._recv[0] > 1000) this._recv.shift();
    this.stat.fpsSim = this._recv.length;
  }
  setMovers(m) { this.movers = m; if (this.worker) this.worker.postMessage({ type: 'movers', movers: m }); else this.sim?.setMovers(m); }
  setJets(j) { this.jets = j; if (this.worker) this.worker.postMessage({ type: 'jets', jets: j }); else this.sim?.setJets(j); }
  event(e) { if (this.worker) this.worker.postMessage({ type: 'event', event: e }); else this.sim?.addEvent(e); }
  setParams(p) { Object.assign(this.o.params ??= {}, p); if (this.worker) this.worker.postMessage({ type: 'params', params: p }); else if (this.sim) Object.assign(this.sim.p, p); }

  // call once per frame before rendering; returns ms of main-thread JS spent on the mist this frame
  update(now, simTime) {
    const t0 = performance.now(); this._clock = now;
    this.uniforms.uMistTime.value = simTime ?? now / 1000;
    if (this.mode === 'main' && this.sim) {
      const dt = this._last ? Math.min(now - this._last, 100) : 0; this._last = now; this._acc += dt;
      let n = 0;
      while (this._acc >= this.period && n < 2) {
        const s0 = performance.now(); this.sim.step(1 / this.hz); const sm = performance.now() - s0;
        this._stepHist.push(sm); if (this._stepHist.length > 60) this._stepHist.shift();
        this._acc -= this.period; n++;
      }
      if (this._acc >= this.period) this._acc = 0;
      if (n) {
        const s0 = performance.now(); this.sim.pack(this._packBuf); this.stat.packMs = performance.now() - s0;
        this._ingest(this._packBuf);
        const h = this._stepHist; this.stat.stepMs = h.reduce((a, b) => a + b, 0) / h.length;
        this.stat.stepP95 = h.slice().sort((a, b) => a - b)[Math.floor(h.length * 0.95)] ?? this.stat.stepMs;
      }
    }
    this.uniforms.uMistBlend.value = Math.min(1, (now - this._recvAt) / this.period);
    const ms = performance.now() - t0 + (this._msgMs ?? 0); this._msgMs = 0;
    this.stat.mainMs = ms; this._mainHist.push(ms); if (this._mainHist.length > 120) this._mainHist.shift();
    this.stat.mainMsAvg = this._mainHist.reduce((a, b) => a + b, 0) / this._mainHist.length;
    this.stat.mainMsMax = Math.max(...this._mainHist);
    return ms;
  }
}
