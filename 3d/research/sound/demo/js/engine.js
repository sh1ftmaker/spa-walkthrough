// Kazan-yu soundscape engine (prototype). Plain Web Audio, no libraries. Works on an AudioContext (live) or an
// OfflineAudioContext (renders/benchmarks): the caller drives update() at ~20 Hz with the listener pose.
//
// Model:
//  * Spaces from the layout are grouped into acoustic ROOMS (space + its `open_to` partners). Rooms connect through
//    PORTALS (doorways, stair mouths, the falls shaft). Each update a Dijkstra over portals gives, for every emitter
//    outside the listener's room, the path length, the summed portal loss and the first portal on the path. The
//    emitter is then heard FROM that portal's direction, attenuated and low-passed per hop: cheap occlusion with
//    no raycasts (the idea behind Wwise Spatial Audio rooms & portals).
//  * Emitters: point, line (nearest point on a polyline: rivers, spill lips, lava windows), area (nearest point on a
//    polygon, inside = enveloping). Beds: non-spatial per-space loops crossfaded by the listener's space.
//  * Voice virtualisation: every emitter gets an audibility score each update; only the loudest max_voices become
//    real (AudioBufferSource -> gain -> lowpass -> panner + diffuse + reverb sends); the rest cost nothing.
//  * One reverb (ConvolverNode, generated IR) per preset, only the listener's room preset is fed; crossfades on room change.
import * as G from './geom.js';
import { impulse, rng, dbToLin } from './dsp.js';

const EPS_DB = -60;
// Finite linear ramps (they end, so Chrome returns to its fast k-rate path); skip tiny changes.
function ramp(param, v, t, dur) {
  const cur = param.value; if (Math.abs(cur - v) < 1e-4 + 0.01 * Math.abs(v)) return;
  param.cancelScheduledValues(t); param.setValueAtTime(cur, t); param.linearRampToValueAtTime(v, t + dur);
}
function setIfChanged(param, v, rel) { if (Math.abs(param.value - v) > rel * Math.abs(v) + 1e-6) param.value = v; }
const smooth = 0.06; // AudioParam time constant (s)

export class SoundEngine {
  constructor(ctx, layout, blocks, bank, opts = {}) {
    this.ctx = ctx; this.layout = layout; this.blocks = blocks; this.bank = bank;
    this.opts = Object.assign({ maxVoices: blocks.rules?.max_voices || 14, panning: 'equalpower', mode: 'headphones', quiet: false, demoGeyser: true, seed: 7, reverb: true }, opts);
    this.R = rng(this.opts.seed);
    this.listener = { x: 0, y: 0, z: 0, heading: 0, level: 'ground' };
    this.voices = new Map(); this.beds = new Map(); this.shotsActive = 0; this.stat = { updates: 0, updMs: 0, oneshots: 0 };
    this.buffers = {}; this.shotBuffers = {};
    this.startTime = ctx.currentTime;
  }

  // ---------- setup ----------
  init() {
    const ctx = this.ctx;
    const mk = (chs, sr) => { const b = ctx.createBuffer(chs.length, chs[0].length, sr); chs.forEach((c, i) => b.copyToChannel(c, i)); return b; };
    for (const [k, l] of Object.entries(this.bank.loops)) this.buffers[k] = l.buffer || (l.buffer = mk(l.chs, l.sr));
    for (const [k, vs] of Object.entries(this.bank.shots)) this.shotBuffers[k] = vs.map((v) => v.buffer || (v.buffer = mk(v.chs, v.sr)));
    this._buildGraph(); this._buildRooms(); this._buildEmitters(); this._buildPortalGraph();
    return this;
  }
  _buildGraph() {
    const ctx = this.ctx;
    this.master = ctx.createGain(); this.master.gain.value = dbToLin(-7);
    this.speakerHP = ctx.createBiquadFilter(); this.speakerHP.type = 'highpass'; this.speakerHP.frequency.value = 20;
    this.speakerPK = ctx.createBiquadFilter(); this.speakerPK.type = 'peaking'; this.speakerPK.frequency.value = 2800; this.speakerPK.Q.value = 0.8; this.speakerPK.gain.value = 0;
    this.comp = ctx.createDynamicsCompressor(); Object.assign(this.comp, {}); this.comp.threshold.value = -20; this.comp.knee.value = 12; this.comp.ratio.value = 2.5; this.comp.attack.value = 0.02; this.comp.release.value = 0.3;
    this.limiter = ctx.createDynamicsCompressor(); this.limiter.threshold.value = -4.5; this.limiter.knee.value = 0; this.limiter.ratio.value = 20; this.limiter.attack.value = 0.002; this.limiter.release.value = 0.1;
    // Safety clipper after the limiter: linear to -3 dBFS, then a tanh knee that never exceeds -1.2 dBFS, 4x oversampled
    // (the DynamicsCompressor limiter alone let the loudest walk reach -0.6 dBTP).
    this.clip = ctx.createWaveShaper(); const cn = 2049, cv = new Float32Array(cn), th = 0.708, ceil = 0.871;
    for (let i = 0; i < cn; i++) { const x = (i / (cn - 1)) * 2 - 1, a = Math.abs(x); cv[i] = Math.sign(x) * (a <= th ? a : th + (ceil - th) * Math.tanh((a - th) / (ceil - th))); }
    this.clip.curve = cv; this.clip.oversample = '4x';
    this.master.connect(this.speakerHP).connect(this.speakerPK).connect(this.comp).connect(this.limiter).connect(this.clip).connect(ctx.destination);
    this.dry = ctx.createGain(); this.dry.connect(this.master);
    this.bedBus = ctx.createGain(); this.bedBus.connect(this.master);
    // (no shared diffuse bus: wide sources carry their own uncorrelated second read, see _applyVoice)
    this.send = ctx.createGain(); this.reverbs = {};
    this.setMode(this.opts.mode);
  }
  setMode(mode) {
    this.opts.mode = mode; const t = this.ctx.currentTime, sp = mode === 'speaker';
    this.speakerHP.frequency.value = sp ? 160 : 28; this.speakerPK.gain.value = sp ? 4 : 0;
    this.comp.threshold.value = sp ? -30 : -20; this.comp.ratio.value = sp ? 4 : 2.5;
    ramp(this.master.gain, dbToLin(sp ? -1 : -7), t, 0.1);
  }
  setPanning(model) { this.opts.panning = model; for (const v of this.voices.values()) v.pan.panningModel = model; }
  setQuiet(q) { this.opts.quiet = q; }

  _reverb(preset) {
    if (!this.opts.reverb) return null;
    if (this.reverbs[preset]) return this.reverbs[preset];
    const p = this.blocks.reverb_presets[preset]; const ctx = this.ctx; const sr = ctx.sampleRate;
    const chs = impulse(sr, { rt: p.rt, rtHigh: p.rtHigh, predelay: p.predelay, size: p.size, seed: 171 + preset.length });
    const b = ctx.createBuffer(2, chs[0].length, sr); chs.forEach((c, i) => b.copyToChannel(c, i));
    const conv = ctx.createConvolver(); conv.normalize = true; conv.buffer = b;
    const wet = ctx.createGain(); wet.gain.value = 0; conv.connect(wet).connect(this.master);
    const r = { preset, conv, wet, connected: false, idle: 0, irSecs: chs[0].length / sr };
    this.reverbs[preset] = r; return r;
  }

  _buildRooms() {
    const L = this.layout; this.spaces = {}; for (const s of L.spaces) { s.area = s.area_m2 || G.polyArea(s.footprint); this.spaces[s.id] = s; }
    const parent = {}; const find = (a) => (parent[a] === a ? a : (parent[a] = find(parent[a])));
    for (const id of Object.keys(this.spaces)) parent[id] = id;
    for (const c of L.connections) parent[c.id] = c.id;
    for (const [id, b] of Object.entries(this.blocks.spaces)) for (const o of b.open_to || []) if (parent[o] && parent[id]) parent[find(o)] = find(id);
    this.roomOf = (sid) => find(sid);
    this.rooms = {}; for (const id of Object.keys(parent)) { const r = find(id); (this.rooms[r] = this.rooms[r] || []).push(id); }
  }
  _ref(space, ref) { // resolve a geometry reference to { pts:[[x,y],...], poly?:[[x,y]...] }
    const s = this.spaces[space];
    if (ref === 'hero') return { pts: [s.hero.at.slice(0, 2)] };
    if (ref === 'spine') return { pts: (s.spine || []).map((p) => p.slice(0, 2)) };
    if (ref.startsWith('water:')) {
      const ids = ref.slice(6).split(','); const out = { pts: [], multi: [] };
      for (const id of ids) {
        const w = s.water.find((q) => q.id === id); if (!w) { console.warn('missing water', space, id); continue; }
        if (w.footprint) out.poly = w.footprint;
        const p = w.path || w.lip || (w.at ? [w.at] : null);
        if (p) { out.multi.push(p); out.pts.push(...p); }
        if (!p && w.footprint) out.pts.push(G.centroid(w.footprint));
      }
      return out;
    }
    if (ref.startsWith('anchored:')) { const a = s.anchored.find((q) => q.id === ref.slice(9)); if (!a) { console.warn('missing anchored', space, ref); return { pts: [] }; } return { pts: [a.at.slice(0, 2)] }; }
    if (ref.startsWith('anchored_asset:')) return { pts: s.anchored.filter((q) => q.asset === ref.slice(15)).map((q) => q.at.slice(0, 2)) };
    if (ref.startsWith('emitter:')) { const e = this.emitters.find((q) => q.space === space && q.id === ref.slice(8)); return { pts: e.pts }; }
    return { pts: [] };
  }
  _buildEmitters() {
    this.emitters = []; this.oneshots = []; let k = 0;
    for (const [sid, b] of Object.entries(this.blocks.spaces)) {
      if (!this.spaces[sid]) continue;
      for (const e of b.emitters || []) {
        const g = e.from ? this._ref(sid, e.from) : { pts: e.points || (e.at ? [e.at] : []), poly: e.polygon };
        const base = { ...e, space: sid, room: this.roomOf(sid), level: this.spaces[sid].level, z: e.z ?? this.spaces[sid].floor_z + 1, tags: e.tags || [] };
        if (e.shape === 'point' && g.pts.length > 1) { // one emitter per instance (pods, vents, trickles)
          g.pts.forEach((p, i) => this.emitters.push({ ...base, id: `${e.id}_${i}`, shape: 'point', pts: [p], key: k++ }));
        } else if (e.shape === 'area') {
          const poly = g.poly || e.polygon; if (!poly) { console.warn('area emitter without polygon', sid, e.id); continue; }
          this.emitters.push({ ...base, pts: g.pts.length ? g.pts : [G.centroid(poly)], poly, key: k++ });
        } else if (!g.pts.length) { console.warn('emitter without geometry (skipped)', sid, e.id); continue;
        } else {
          let pts = g.pts; if (e.closed && pts.length > 2) pts = [...pts, pts[0]];
          this.emitters.push({ ...base, pts, key: k++ });
        }
      }
    }
    for (const [sid, b] of Object.entries(this.blocks.spaces)) {
      if (!this.spaces[sid]) continue;
      for (const o of b.oneshots || []) {
        let pts = null, poly = null, around = null;
        if (o.along) pts = this._ref(sid, o.along).pts;
        else if (o.area) { const g = this._ref(sid, o.area); poly = g.poly; }
        else if (o.around) around = this._ref(sid, o.around).pts[0];
        else if (o.points) pts = this._ref(sid, o.points).pts;
        else if (o.from) pts = this._ref(sid, o.from).pts;
        else if (o.at) pts = [o.at];
        this.oneshots.push({ ...o, space: sid, room: this.roomOf(sid), level: this.spaces[sid].level, pts, poly, around, mode: o.along ? 'along' : poly ? 'area' : around ? 'around' : 'points', next: this.ctx.currentTime + this._interval(o) * this.R(), lastTrig: -1e9, tags: o.tags || [] });
      }
    }
  }
  _interval(o) { const [a, b] = o.every_s || [10, 20]; return a + (b - a) * this.R(); }

  _buildPortalGraph() {
    const ov = this.blocks.portal_overrides || {};
    this.portals = this.layout.portals.map((p) => {
      const ra = this.roomOf(p.a), rb = this.roomOf(p.b);
      const o = ov[p.id] || {};
      const lossDb = o.loss_db ?? (2 + Math.max(0, 10 * Math.log10(6 / Math.max(1, p.width))));
      return { ...p, ra, rb, pos: [p.at[0], p.at[1], (p.at[2] ?? 0) + 1.5], loss: lossDb, lp: o.lp ?? 0.5 };
    }).filter((p) => p.ra !== p.rb);
    this.portalsByRoom = {};
    for (const p of this.portals) for (const r of [p.ra, p.rb]) (this.portalsByRoom[r] = this.portalsByRoom[r] || []).push(p);
  }

  // ---------- listener ----------
  setListener(pose) {
    Object.assign(this.listener, pose);
    const sp = this.spaceAt(this.listener.x, this.listener.y, this.listener.level);
    this.listener.space = sp?.id || null;
    if (sp && pose.z === undefined) this.listener.z = sp.floor_z + 1.6;
  }
  spaceAt(x, y, level) {
    let best = null;
    for (const s of Object.values(this.spaces)) {
      if (s.level !== level) continue;
      if (G.pointInPoly([x, y], s.footprint) && (!best || s.area < best.area)) best = s;
    }
    if (best) return best;
    let bd = Infinity; // outside every footprint (in rock / off-map): snap to nearest space on the level
    for (const s of Object.values(this.spaces)) { if (s.level !== level) continue; const q = G.nearestOnPolygon([x, y], s.footprint); const d = Math.hypot(q[0] - x, q[1] - y); if (d < bd) { bd = d; best = s; } }
    return best;
  }

  _dijkstra() {
    const L = this.listener; const lp = [L.x, L.y, L.z]; const room = this.roomOf(L.space);
    const best = new Map(); // portal id -> {cost, dist, loss, hops, first, lp}
    const open = [];
    for (const p of this.portalsByRoom[room] || []) {
      // Doorway blend: within 5 m of a portal its loss and muffling fade in with distance, so walking through a
      // door is a glide, not a step (the other room is "in front of you" before you are inside it).
      const d = G.dist3(lp, p.pos); const u = Math.min(1, d / 5); const loss = p.loss * u, lpf = 1 - (1 - p.lp) * u;
      const rec = { cost: d + 2 * loss, dist: d, loss, hops: u < 1 ? 0.5 : 1, first: p, lpf, room: p.ra === room ? p.rb : p.ra };
      best.set(p.id, rec); open.push(p);
    }
    while (open.length) {
      open.sort((a, b) => best.get(a.id).cost - best.get(b.id).cost); const p = open.shift(); const rp = best.get(p.id);
      for (const q of this.portalsByRoom[rp.room] || []) {
        if (q === p) continue; const d = G.dist3(p.pos, q.pos); const cost = rp.cost + d + 2 * q.loss;
        const cur = best.get(q.id);
        if (!cur || cost < cur.cost - 1e-6) { best.set(q.id, { cost, dist: rp.dist + d, loss: rp.loss + q.loss, hops: rp.hops + 1, first: rp.first, lpf: rp.lpf * q.lp, room: q.ra === rp.room ? q.rb : q.ra }); if (!open.includes(q)) open.push(q); }
      }
    }
    this.paths = best; this.listenerRoom = room;
  }
  // Acoustic route from the listener to the emitter. Returns {gain, pos (apparent), dist, lp, spread}
  _route(e, ptFn) {
    const L = this.listener, lp = [L.x, L.y, L.z];
    let out = null;
    if (e.room === this.listenerRoom) {
      const q = ptFn(lp); const pos = [q[0], q[1], e.z]; const d = q.inside ? Math.abs(L.z - e.z) : G.dist3(lp, pos);
      out = { dist: d, loss: 0, hops: 0, pos, lpf: 1, inside: q.inside };
    } else {
      for (const p of this.portalsByRoom[e.room] || []) {
        const rec = this.paths.get(p.id); if (!rec || rec.room !== e.room) continue;
        const q = ptFn(p.pos); const pos = [q[0], q[1], e.z]; const d = rec.dist + G.dist3(p.pos, pos);
        const cost = rec.cost + G.dist3(p.pos, pos);
        if (!out || cost < out.cost) out = { cost, dist: d, loss: rec.loss, hops: rec.hops, pos: rec.first.pos, lpf: rec.lpf, inside: false };
      }
    }
    const ref = e.ref_m || 2, roll = e.rolloff ?? (e.shape === 'point' || !e.shape ? 1 : 0.75);
    const g = (d) => Math.pow(ref / Math.max(d, ref), roll);
    let gain = out ? dbToLin(e.gain_db || 0) * g(out.dist) * dbToLin(-out.loss) : 0;
    let lpHz = out ? Math.min(e.lp_hz || 20000, 20000 * out.lpf, 16000 / (1 + out.dist / 35)) : 200; // air + distance: big water goes dull with distance
    if (e.leak_db !== undefined) { // structure-borne / through-rock path for the very loud things
      const q = ptFn(lp); const d = G.dist3(lp, [q[0], q[1], e.z]); const gl = dbToLin((e.gain_db || 0) + e.leak_db) * g(d);
      if (gl > gain) { gain = gl; lpHz = e.leak_lp_hz || 300; out = { dist: d, pos: [q[0], q[1], e.z], inside: false, hops: 9 }; }
    }
    if (!out) return null;
    let spread = out.inside ? 0.85 : (out.hops === 0 && e.spread_m ? Math.max(0, 1 - out.dist / e.spread_m) * 0.85 : 0); if (this.opts.diffuse === false) spread = 0;
    return { gain, pos: out.pos, dist: out.dist, lpHz, spread, hops: out.hops };
  }
  _pointFn(e) {
    if (e.poly && (e.shape === 'area')) return (p) => { const q = G.nearestOnPolygon(p, e.poly); return { 0: q[0], 1: q[1], inside: q[2] }; };
    if (e.pts.length > 1) return (p) => { const q = G.nearestOnPolyline(p, e.pts); return { 0: q[0], 1: q[1], inside: false }; };
    return () => ({ 0: e.pts[0][0], 1: e.pts[0][1], inside: false });
  }

  // ---------- per-frame ----------
  update() {
    const t0 = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    const ctx = this.ctx, now = ctx.currentTime, L = this.listener;
    if (!L.space) return;
    this._dijkstra();
    const quiet = this.opts.quiet, qr = this.blocks.rules.quiet_hours;
    // score emitters
    const scored = [];
    for (const e of this.emitters) {
      if (quiet && e.tags.some((t) => qr.mute_tags.includes(t))) continue;
      const r = this._route(e, e._pf || (e._pf = this._pointFn(e))); if (!r) continue;
      if (quiet) for (const t of e.tags) if (qr.duck_tags[t]) r.gain *= dbToLin(qr.duck_tags[t]);
      if (r.gain < dbToLin(EPS_DB)) continue;
      e.route = r; scored.push(e);
    }
    scored.sort((a, b) => b.route.gain - a.route.gain);
    const keep = new Set(scored.slice(0, this.opts.maxVoices).map((e) => e.key));
    // hysteresis: keep an existing voice if it is within 3 dB of the cut
    const cut = scored[this.opts.maxVoices - 1]?.route.gain || 0;
    for (const e of scored.slice(this.opts.maxVoices)) if (this.voices.has(e.key) && e.route.gain > cut * 0.7) keep.add(e.key);
    this.audible = scored.length;
    for (const [key, v] of this.voices) if (!keep.has(key)) this._stopVoice(v);
    for (const e of scored) if (keep.has(e.key)) this._applyVoice(e, now);
    this._updateBeds(now); this._updateReverb(now); this._updateOneshots(now);
    const dt = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0;
    this.stat.updates++; this.stat.updMs = this.stat.updMs * 0.9 + dt * 0.1; this.stat.lastMs = dt;
  }
  _rel(pos) { // layout position -> listener-local audio coordinates (listener fixed at origin facing -Z)
    const L = this.listener, h = (L.heading || 0) * Math.PI / 180;
    const dx = pos[0] - L.x, dy = pos[1] - L.y, dz = (pos[2] ?? L.z) - L.z;
    const right = dx * Math.cos(h) - dy * Math.sin(h), fwd = dx * Math.sin(h) + dy * Math.cos(h);
    return [right, dz, -fwd];
  }
  _setPannerPos(pan, rel, t) {
    const n = Math.hypot(...rel) || 1; const s = 1 / n; const p = [rel[0] * s, rel[1] * s, rel[2] * s]; // unit vector: direction only
    // Plain .value writes, never automation: on Chrome an automated PannerNode position (or BiquadFilter frequency)
    // switches the node to its per-sample path for as long as the automation timeline is live (setTargetAtTime never ends).
    if (pan.positionX) { pan.positionX.value = p[0]; pan.positionY.value = p[1]; pan.positionZ.value = p[2]; }
    else pan.setPosition(p[0], p[1], p[2]);
  }
  _makePanner() {
    const pan = this.ctx.createPanner(); pan.panningModel = this.opts.panning; pan.distanceModel = 'linear'; pan.rolloffFactor = 0; pan.refDistance = 1; pan.maxDistance = 1e4;
    return pan;
  }
  _applyVoice(e, now) {
    let v = this.voices.get(e.key); const r = e.route;
    if (!v) {
      const ctx = this.ctx; const buf = this.buffers[e.asset]; if (!buf) return;
      const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true;
      const hr = rng(e.key * 7919 + 13); const rate = 0.96 + 0.08 * hr(); src.playbackRate.value = rate;
      const g = ctx.createGain(); g.gain.value = 0; const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.Q.value = 0.5; lp.frequency.value = r.lpHz;
      const pan = this._makePanner(); const pg = ctx.createGain(), dg = ctx.createGain(), sg = ctx.createGain(); dg.gain.value = 0; sg.gain.value = 0;
      const off = buf.duration * hr(); let src2 = null, merger = null, split = null;
      // "Wide" sources (spread or area): the enveloping part is a SECOND, uncorrelated read of the same loop (half a
      // loop apart) on the right channel, the first read on the left. No delays, so no comb filtering against the
      // dry path (round 1's delay decorrelator and a velvet-noise decorrelator both striped the spectrum).
      const wide = !!(e.spread_m || e.shape === 'area');
      if (wide && buf.numberOfChannels === 1) {
        src2 = ctx.createBufferSource(); src2.buffer = buf; src2.loop = true; src2.playbackRate.value = rate;
        merger = ctx.createChannelMerger(2); src.connect(merger, 0, 0); src2.connect(merger, 0, 1); merger.connect(g);
      } else src.connect(g);
      g.connect(lp);
      if (wide) { split = ctx.createChannelSplitter(2); lp.connect(split); split.connect(pg, 0); lp.connect(dg).connect(this.master); }
      else { lp.connect(pg); }
      pg.connect(pan).connect(this.dry); lp.connect(sg).connect(this.send);
      src.start(now, off); if (src2) src2.start(now, (off + buf.duration / 2) % buf.duration);
      v = { e, src, src2, merger, split, g, lp, pan, pg, dg, sg, born: now, t0: now, off, rate };
      this.voices.set(e.key, v);
    }
    const t = now; const fresh = v.born === now;
    // Smooth in JS (dB for gain, log-frequency for cutoff, vector for direction) so crossing a portal or a room
    // boundary glides over ~200 ms instead of stepping; the Web Audio params only ever get short ramps or .value.
    const k = fresh ? 1 : 0.3;
    const gDb = 20 * Math.log10(r.gain + 1e-9); v.gDb = v.gDb === undefined ? gDb : v.gDb + (gDb - v.gDb) * k;
    const lf = Math.log(r.lpHz); v.lf = v.lf === undefined ? lf : v.lf + (lf - v.lf) * k;
    const rel = this._rel(r.pos); const n = Math.hypot(...rel) || 1; const dir = rel.map((c) => c / n);
    v.dir = v.dir ? v.dir.map((c, i) => c + (dir[i] - c) * (fresh ? 1 : 0.35)) : dir;
    v.sp = v.sp === undefined ? r.spread : v.sp + (r.spread - v.sp) * k;
    ramp(v.g.gain, dbToLin(v.gDb), t, fresh ? 0.3 : 0.06);
    setIfChanged(v.lp.frequency, Math.exp(v.lf), 0.02);
    ramp(v.pg.gain, Math.sqrt(1 - v.sp), t, 0.06); ramp(v.dg.gain, Math.SQRT1_2 * Math.sqrt(v.sp), t, 0.06);
    setIfChanged(v.sg.gain, dbToLin(e.send_db ?? 0), 0.01);
    this._setPannerPos(v.pan, v.dir, t);
  }
  _stopVoice(v) {
    const t = this.ctx.currentTime; ramp(v.g.gain, 0, t, 0.4); try { v.src.stop(t + 0.45); if (v.src2) v.src2.stop(t + 0.45); } catch (_) {}
    v.src.onended = () => { [v.src, v.src2, v.merger, v.split, v.g, v.lp, v.pan, v.pg, v.dg, v.sg].forEach((n) => n && n.disconnect()); };
    this.voices.delete(v.e.key);
  }

  _updateBeds(now) {
    const b = this.blocks.spaces[this.listener.space] || {}; const want = {};
    for (const bd of b.beds || []) want[bd.asset] = dbToLin(bd.gain_db || 0);
    for (const [asset, g] of Object.entries(want)) {
      if (!this.beds.has(asset)) {
        const buf = this.buffers[asset]; if (!buf) continue; const src = this.ctx.createBufferSource(); src.buffer = buf; src.loop = true;
        const gn = this.ctx.createGain(); gn.gain.value = 0; src.connect(gn).connect(this.bedBus); const off = buf.duration * this.R(); src.start(now, off);
        this.beds.set(asset, { src, g: gn, zeroSince: null, t0: now, off, rate: 1 });
      }
    }
    for (const [asset, bd] of this.beds) {
      const g = want[asset] || 0; if (Math.abs((bd.target ?? -1) - g) > 1e-4) { ramp(bd.g.gain, g, now, 2.5); bd.target = g; }
      if (g === 0) { bd.zeroSince ??= now; if (now - bd.zeroSince > 6) { bd.src.stop(); bd.src.disconnect(); bd.g.disconnect(); this.beds.delete(asset); } } else bd.zeroSince = null;
    }
  }
  _updateReverb(now) {
    if (!this.opts.reverb) return;
    const preset = (this.blocks.spaces[this.listener.space] || {}).reverb || 'corridor';
    const cur = this._reverb(preset);
    if (!cur.connected) { this.send.connect(cur.conv); cur.connected = true; }
    for (const r of Object.values(this.reverbs)) {
      const target = r === cur ? dbToLin(this.blocks.reverb_presets[r.preset].wet_db) : 0;
      if (Math.abs((r.target ?? -1) - target) > 1e-4) { ramp(r.wet.gain, target, now, 1.5); r.target = target; }
      if (r !== cur && r.connected) { r.idle ||= now; if (now - r.idle > r.irSecs + 3) { this.send.disconnect(r.conv); r.connected = false; r.idle = 0; } } else r.idle = 0;
    }
    this.reverbPreset = preset;
  }
  _gustAt(now) { // gust envelope of the wind loop, as it plays; used to strike the furin in gusts
    const w = this.bank.loops.wind; if (!w?.gust) return 0.5;
    let src = [...this.voices.values()].find((v) => v.e.asset === 'wind') || this.beds.get('wind');
    const dur = w.gust.length / 100; const pos = src ? (src.off + (now - src.t0) * src.rate) % dur : (now - this.startTime) % dur;
    return w.gust[Math.floor(pos * 100) % w.gust.length];
  }
  _updateOneshots(now) {
    const L = this.listener, quiet = this.opts.quiet, look = 0.12, mute = this.blocks.rules.quiet_hours.mute_tags;
    for (const o of this.oneshots) {
      if (quiet && o.tags.some((t) => mute.includes(t))) { o.next = Math.max(o.next, now + 1); continue; }
      if (o.trigger === 'proximity') {
        const p = o.pts[0]; const d = Math.hypot(L.x - p[0], L.y - p[1]);
        if (L.space && this.spaces[L.space].level === o.level && d < o.radius_m && now - o.lastTrig > o.cooldown_s) { o.lastTrig = now; o.next = now + this._interval(o); this._fire(o, now + 0.05); continue; }
      }
      if (o.trigger === 'timer') {
        const per = this.opts.demoGeyser ? o.demo_period_s : o.period_s; if (o.nextT === undefined) o.nextT = this.startTime + (this.opts.firstGeyserAt ?? per * 0.25);
        if (now + look >= o.nextT) { this._fire(o, Math.max(now, o.nextT)); o.nextT += per; }
        continue;
      }
      if (o.trigger === 'gust') {
        const gst = this._gustAt(now); const rate = (o.rate_hz || 0.5) * Math.pow(Math.max(0, gst - 0.25) / 0.75, 2) * 3;
        if (this.R() < rate * 0.05) this._fire(o, now + 0.02 + 0.03 * this.R());
        continue;
      }
      if (now + look >= o.next) { const at = Math.max(now, o.next); o.next = at + this._interval(o); if (o.trigger === 'proximity' && now - o.lastTrig < o.cooldown_s) continue; this._fire(o, at); }
    }
  }
  fireById(id) { const o = this.oneshots.find((q) => q.id === id); if (o) this._fire(o, this.ctx.currentTime + 0.02); }
  _fire(o, when) {
    const R = this.R; let p;
    if (o.mode === 'area') p = G.randomInPoly(o.poly, R);
    else if (o.mode === 'around') { const a = R() * Math.PI * 2, r = Math.sqrt(R()) * o.radius_m; p = [o.around[0] + r * Math.cos(a), o.around[1] + r * Math.sin(a)]; }
    else if (o.mode === 'along' && o.pts.length > 1) p = G.pointAlong(o.pts, R());
    else p = o.pts[Math.floor(R() * o.pts.length)];
    if (!p) return;
    const e = { room: o.room, z: o.z ?? this.spaces[o.space].floor_z, gain_db: o.gain_db || 0, ref_m: o.ref_m || 2, leak_db: o.leak_db, shape: 'point' };
    const by = (this.stat.byId ||= {}); const rec = (by[o.id] ||= { fired: 0, quiet: 0, busy: 0 });
    const r = this._route(e, () => ({ 0: p[0], 1: p[1], inside: false })); if (!r || r.gain < dbToLin(o.trigger ? -50 : -42)) { rec.quiet++; return; }
    if (this.shotsActive >= 8 && !o.trigger) { rec.busy++; return; }
    rec.fired++; (rec.t ||= []).push(+when.toFixed(2)); rec.db = +(20 * Math.log10(r.gain)).toFixed(1);
    const bufs = this.shotBuffers[o.asset]; if (!bufs) return; const buf = bufs[Math.floor(R() * bufs.length)];
    const ctx = this.ctx, src = ctx.createBufferSource(); src.buffer = buf;
    if (o.pitch) src.playbackRate.value = o.pitch[0] + (o.pitch[1] - o.pitch[0]) * R();
    const g = ctx.createGain(); g.gain.value = r.gain * (0.7 + 0.3 * R()); const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = r.lpHz;
    const pan = this._makePanner(); pan.panningModel = 'equalpower'; this._setPannerPos(pan, this._rel(r.pos), when);
    const sg = ctx.createGain(); sg.gain.value = 1;
    src.connect(g).connect(lp).connect(pan).connect(this.dry); lp.connect(sg).connect(this.send);
    src.start(when); this.shotsActive++; this.stat.oneshots++; if (this.onFire) this.onFire(o, p);
    src.onended = () => { this.shotsActive--; [src, g, lp, pan, sg].forEach((n) => n.disconnect()); };
  }

  stats() {
    const ctx = this.ctx;
    return {
      space: this.listener.space, room: this.listenerRoom, reverb: this.reverbPreset,
      realVoices: this.voices.size, audible: this.audible || 0, emitters: this.emitters.length, beds: this.beds.size, oneshotsActive: this.shotsActive, oneshotsTotal: this.stat.oneshots,
      convolvers: Object.values(this.reverbs).filter((r) => r.connected).length,
      updMs: +this.stat.updMs.toFixed(3), byId: this.stat.byId, state: ctx.state, sr: ctx.sampleRate, baseLatency: ctx.baseLatency, outputLatency: ctx.outputLatency,
    };
  }
  voiceList() { return [...this.voices.values()].map((v) => ({ id: v.e.id, asset: v.e.asset, db: +(20 * Math.log10(v.e.route.gain + 1e-9)).toFixed(1), hops: v.e.route.hops, pos: v.e.route.pos, key: v.e.key })); }
}

// Drive an engine through a scripted walk in an OfflineAudioContext. keys: [{t, x, y, level, heading}] (linear interp).
export async function renderOffline(OfflineCtx, layout, blocks, bank, { secs = 25, sr = 48000, keys, opts = {}, events = [] }) {
  const ctx = new OfflineCtx(2, Math.round(secs * sr), sr);
  const eng = new SoundEngine(ctx, layout, blocks, bank, opts).init();
  const step = 0.05; let ms = 0;
  const pose = (t) => { let a = keys[0], b = keys[keys.length - 1]; for (let i = 0; i < keys.length - 1; i++) if (t >= keys[i].t && t <= keys[i + 1].t) { a = keys[i]; b = keys[i + 1]; break; } const u = b.t > a.t ? Math.min(1, Math.max(0, (t - a.t) / (b.t - a.t))) : 0; let hd = (b.heading - a.heading + 540) % 360 - 180; return { x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, heading: a.heading + hd * u, level: u < 0.5 ? a.level : b.level, z: undefined }; };
  eng.setListener(pose(0)); eng.update();
  for (let t = step; t < secs - 0.01; t += step) {
    ctx.suspend(+t.toFixed(4)).then(() => {
      const tt = ctx.currentTime; const p = pose(tt); delete p.z; eng.listener.z = undefined; eng.setListener(p);
      for (const ev of events) if (!ev.done && tt >= ev.t) { ev.done = true; if (ev.fire) eng.fireById(ev.fire); if (ev.quiet !== undefined) eng.setQuiet(ev.quiet); }
      const a = performance.now(); eng.update(); ms += performance.now() - a; ctx.resume();
    });
  }
  const t0 = performance.now(); const buf = await ctx.startRendering(); const wall = performance.now() - t0;
  return { buf, wallMs: wall, updateMs: ms, stats: eng.stats() };
}
