// Kazan-yu mist: a cheap 2D Navier-Stokes ("stable fluids") solver for the low mist layer over water.
//
// One file, two roles:
//   * imported as an ES module, it exports MistSim (used directly for the "worker off / main thread" mode);
//   * started as a module Worker (new Worker(url, {type:'module'})), it runs MistSim at a fixed rate and
//     posts a packed RGBA8 field (density, heat, velocity) back with a transferable ArrayBuffer.
//
// Solver (Stam 1999 "Stable Fluids", Stam 2003 "Real-Time Fluid Dynamics for Games",
// Harris 2004 GPU Gems ch. 38, Mueller "Ten Minute Physics" #17):
//   MAC (staggered) grid, solid mask s (0 solid, 1 fluid / open), Gauss-Seidel with over-relaxation (SOR)
//   for incompressibility (with optional divergence sources: steam expansion, waterfall down-draft),
//   semi-Lagrangian advection of velocity, density and heat, vorticity confinement (Fedkiw/Stam/Jensen 2001
//   as in GPU Gems 38.5.1), a gravity-current "slump" force (dense cold mist spreads out and pools),
//   relaxation to a prescribed wind field (portal drafts), point/disc jets (inflow, spray), timed bursts
//   (geysers, fumaroles) and moving disc obstacles (guests wading through: they push the mist aside and
//   shed a wake).
//
// Grid convention: cell (i, j), i along world X, j along world Z (three.js world, metres). The packed output
// is row-major with j as the row, so the texture maps uv = ((X - minX) / W, (Z - minZ) / D).

export const PACK_VMAX = 3.0; // m/s mapped to the full byte range in the B/A (velocity) channels

export class MistSim {
  // cfg: { nx, ny, h, minX, minZ, solid: Uint8Array(nx*ny) 1 = rock, temp: Float32Array(nx*ny) water °C or 0,
  //        open: { xmin, xmax, ymin, ymax } booleans (domain edges that are open to the rest of the cave),
  //        params: see DEFAULTS }
  constructor(cfg) {
    this.cfg = cfg;
    const nx = cfg.nx, ny = cfg.ny;
    this.nx = nx; this.ny = ny; this.h = cfg.h;
    this.minX = cfg.minX ?? 0; this.minZ = cfg.minZ ?? 0;
    const NX = nx + 2, NY = ny + 2; this.NX = NX; this.NY = NY;
    const n = NX * NY; this.n = n;
    const F = () => new Float32Array(n);
    this.u = F(); this.v = F(); this.nu = F(); this.nv = F();
    this.d = F(); this.nd = F(); this.T = F(); this.nT = F();
    this.s = F(); this.s0 = F();
    this.srcD = F(); this.srcT = F(); this.dry = F(); this.div = F();
    this.windU = F(); this.windV = F();
    this.curl = F();
    this.p = Object.assign({}, MistSim.DEFAULTS, cfg.params || {});
    this.jets = []; this.events = []; this.movers = []; this.vort = [];
    this.time = 0; this.steps = 0; this._rnd = 0x9e3779b9 ^ (cfg.seed ?? 7);
    this.setGeometry(cfg.solid, cfg.temp, cfg.open || {});
  }

  static DEFAULTS = {
    iters: 16,          // SOR sweeps per step
    omega: 1.9,         // over-relaxation (Mueller uses 1.9)
    vort: 6.0,          // vorticity confinement epsilon (m/s^2 scale)
    slump: 0.35,        // gravity-current force: m^2/s^2 per unit density (c = sqrt(slump*d))
    drag: 0.25,         // 1/s relaxation of velocity toward the wind field
    srcScale: 0.5,      // density / s at a source of strength 1 (strength from water temperature)
    heatScale: 0.6,     // heat / s at strength 1
    decay: 0.06,        // 1/s density loss everywhere (mixing into cave air)
    dryDecay: 0.45,     // extra 1/s over dry rock (mist evaporates off water)
    rise: 0.5,          // extra 1/s loss proportional to heat (plume carries mist up out of the layer)
    heatDecay: 0.35,    // 1/s heat relaxation to ambient
    airT: 28, airRH: 0.9, // cave air for the evaporation model
    dMax: 1.6,
    srcNoise: 0.8,      // 0..1: how much a drifting noise breaks the evaporation into patches / thermals
    srcNoiseScale: 0.7, // 1/m
    vorticles: 10,      // live swirl injectors (Ghost of Tsushima's "vorticles", here forcing the grid)
    vortR: [0.5, 1.3],  // radius range, m
    vortV: 0.35,        // peak tangential speed, m/s
    vortLife: [2.5, 6], // s
    wakeMix: 1.6,       // 1/s per m/s of walking speed: legs stir the layer into the clear air above it
    wakeVort: 0.35,     // m/s swirl of the alternating eddies shed behind a walker
    divBalance: false,  // subtract the mean divergence source (rooms without an open edge)
  };

  // Saturation vapour pressure (Magnus formula, hPa). Visible mist forms where the warm saturated boundary
  // layer over the water mixes with cooler cave air; we take the excess vapour pressure as the source strength.
  static evap(waterC, airC = 28, rh = 0.9) {
    const es = (t) => 6.112 * Math.exp((17.67 * t) / (t + 243.5));
    return Math.max(0, es(waterC) - rh * es(airC)) / 60; // ~0.3 at 34 °C, 1.0 at 45 °C, 3.6 at 65 °C
  }

  setGeometry(solid, temp, open) {
    const { nx, ny, NX, NY, s, srcD, srcT, dry } = this;
    s.fill(0);
    for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx; i++) {
      const c = (j - 1) * nx + (i - 1), k = j * NX + i;
      const rock = solid ? solid[c] : 0;
      s[k] = rock ? 0 : 1;
      const tw = temp ? temp[c] : 0;
      const e = tw > 0 ? MistSim.evap(tw, this.p.airT, this.p.airRH) : 0;
      srcD[k] = e; srcT[k] = tw > 0 ? Math.max(0, (tw - this.p.airT) / 20) : 0;
      dry[k] = tw > 0 || rock ? 0 : 1;
    }
    // open edges: border cells count as fluid (p = 0 Dirichlet), so air can leave / enter there
    if (open.xmin) for (let j = 1; j <= ny; j++) if (s[j * NX + 1]) s[j * NX] = 1;
    if (open.xmax) for (let j = 1; j <= ny; j++) if (s[j * NX + nx]) s[j * NX + nx + 1] = 1;
    if (open.ymin) for (let i = 1; i <= nx; i++) if (s[NX + i]) s[i] = 1;
    if (open.ymax) for (let i = 1; i <= nx; i++) if (s[ny * NX + i]) s[(ny + 1) * NX + i] = 1;
    this.s0.set(s);
  }

  // uniform wind (a draft through the zone) plus optional per-cell field (fn(x, z) -> [u, v]) in world m/s
  setWind(fnOrVec) {
    const { nx, ny, NX, h, windU, windV } = this;
    for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx; i++) {
      const x = this.minX + (i - 0.5) * h, z = this.minZ + (j - 0.5) * h; const k = j * NX + i;
      const w = typeof fnOrVec === 'function' ? fnOrVec(x, z) : fnOrVec;
      windU[k] = w ? w[0] : 0; windV[k] = w ? w[1] : 0;
    }
  }
  // jets: [{x, z, r, vx, vz, dens, heat, div}] (world units; div in 1/s = expansion rate)
  setJets(jets) { this.jets = jets || []; }
  // movers: [{x, z, vx, vz, r}] guests wading through
  setMovers(m) { this.movers = m || []; }
  _wake(m, idx, dt) {
    const { d, s0, NX, nx, ny, h, p } = this; const sp = Math.hypot(m.vx, m.vz); if (sp < 0.15) return;
    const ux = m.vx / sp, uz = m.vz / sp; const r = m.r ?? 0.3;
    // mixing disc trailing the body
    const cx = m.x - ux * r * 1.2, cz = m.z - uz * r * 1.2; const [gx, gy] = this._gridOf(cx, cz); const R = r * 2.2 / h, R2 = R * R;
    const k0 = Math.exp(-p.wakeMix * sp * dt);
    const i0 = Math.max(1, Math.floor(gx - R)), i1 = Math.min(nx, Math.ceil(gx + R)), j0 = Math.max(1, Math.floor(gy - R)), j1 = Math.min(ny, Math.ceil(gy + R));
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
      const dx = i + 0.5 - gx, dy = j + 0.5 - gy, q = (dx * dx + dy * dy) / R2; if (q > 1) continue;
      const k = j * NX + i; if (s0[k]) d[k] *= 1 - (1 - k0) * (1 - q);
    }
    // shed alternating eddies every ~0.45 m walked (a Karman street at walking Reynolds numbers)
    const st = this._wakeState ??= []; const w = st[idx] ??= { dist: 0, sign: 1 };
    w.dist += sp * dt;
    if (w.dist > 0.45) {
      w.dist = 0; w.sign = -w.sign;
      const ox = m.x - ux * r * 1.5 - uz * r * 0.9 * w.sign, oz = m.z - uz * r * 1.5 + ux * r * 0.9 * w.sign; const [vx, vy] = this._gridOf(ox, oz);
      this.vort.push({ gx: vx, gy: vy, r: (r * 1.8) / h, w: w.sign * p.wakeVort * Math.min(1.5, sp), t0: this.time, life: 2.5, wake: true });
    }
  }
  // timed burst: {x, z, r, dur, dens, heat, div, vx?, vz?}
  addEvent(e) { this.events.push(Object.assign({ t0: this.time }, e)); }

  // ---------------------------------------------------------------- one step
  step(dt) {
    const p = this.p;
    this.time += dt; this.steps++; this._dt = dt;
    this._obstacles(true);
    this._forces(dt);
    this._project(p.iters, p.omega, dt);
    this._extrapolate();
    this._advectVel(dt);
    this._advectScalars(dt);
    this._sources(dt);
    this._obstacles(false);
  }

  _gridOf(x, z) { return [(x - this.minX) / this.h + 1, (z - this.minZ) / this.h + 1]; } // to cell units incl. border

  _obstacles(on) {
    const { s, s0, u, v, d, NX, nx, ny, h } = this;
    if (!on) { s.set(s0); return; }
    this.movers.forEach((m, i) => this._wake(m, i, this._dt ?? 1 / 30));
    for (const m of this.movers) {
      const [gx, gy] = this._gridOf(m.x, m.z); const r = (m.r ?? 0.3) / h; const r2 = r * r;
      const i0 = Math.max(1, Math.floor(gx - r - 1)), i1 = Math.min(nx, Math.ceil(gx + r + 1));
      const j0 = Math.max(1, Math.floor(gy - r - 1)), j1 = Math.min(ny, Math.ceil(gy + r + 1));
      for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
        const dx = i + 0.5 - gx, dy = j + 0.5 - gy; // cell centre is at i + 0.5 in border-inclusive units
        if (dx * dx + dy * dy > r2) continue;
        const k = j * NX + i; if (!s0[k]) continue;
        s[k] = 0;
        // the body's faces move with it: projection pushes the surrounding mist aside, advection leaves a wake
        u[k] = m.vx; u[k + 1] = m.vx; v[k] = m.vz; v[k + NX] = m.vz;
        d[k] *= 0.85; // a body displaces the mist it stands in
      }
    }
  }

  _forces(dt) {
    const { u, v, d, s, NX, nx, ny, h, windU, windV, curl, div, p } = this;
    const relax = 1 - Math.exp(-p.drag * dt);
    const sl = p.slump * dt / h;
    div.fill(0);
    // gravity-current slump + drag toward the draft field
    for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx + 1; i++) {
      const k = j * NX + i;
      if (s[k] && s[k - 1]) {
        u[k] -= sl * (d[k] - d[k - 1]);
        u[k] += (0.5 * (windU[k] + windU[k - 1]) - u[k]) * relax;
      }
    }
    for (let j = 1; j <= ny + 1; j++) for (let i = 1; i <= nx; i++) {
      const k = j * NX + i;
      if (s[k] && s[k - NX]) {
        v[k] -= sl * (d[k] - d[k - NX]);
        v[k] += (0.5 * (windV[k] + windV[k - NX]) - v[k]) * relax;
      }
    }
    // vorticity confinement: f = eps * h * (N x w), N = grad|w| / |grad|w||
    if (p.vort > 0) {
      for (let j = 2; j < ny; j++) for (let i = 2; i < nx; i++) {
        const k = j * NX + i;
        const vr = 0.5 * (v[k + 1] + v[k + 1 + NX]), vl = 0.5 * (v[k - 1] + v[k - 1 + NX]);
        const ut = 0.5 * (u[k + NX] + u[k + NX + 1]), ub = 0.5 * (u[k - NX] + u[k - NX + 1]);
        curl[k] = ((vr - vl) - (ut - ub)) / (2 * h);
      }
      const e = p.vort * h * dt;
      for (let j = 3; j < ny - 1; j++) for (let i = 3; i < nx - 1; i++) {
        const k = j * NX + i; if (!s[k]) continue;
        const w = curl[k];
        let gx = Math.abs(curl[k + 1]) - Math.abs(curl[k - 1]);
        let gy = Math.abs(curl[k + NX]) - Math.abs(curl[k - NX]);
        const len = Math.hypot(gx, gy) + 1e-5; gx /= len; gy /= len;
        const fx = e * gy * w, fy = -e * gx * w;
        if (s[k - 1]) u[k] += 0.5 * fx; if (s[k + 1]) u[k + 1] += 0.5 * fx;
        if (s[k - NX]) v[k] += 0.5 * fy; if (s[k + NX]) v[k + NX] += 0.5 * fy;
      }
    }
    // jets and bursts: relax velocity toward the jet, add density / heat / expansion
    const apply = (x, z, r, vx, vz, dens, heat, dv, w) => {
      const [gx, gy] = this._gridOf(x, z); const R = Math.max(r / h, 0.75); const R2 = R * R;
      const i0 = Math.max(1, Math.floor(gx - R)), i1 = Math.min(nx, Math.ceil(gx + R));
      const j0 = Math.max(1, Math.floor(gy - R)), j1 = Math.min(ny, Math.ceil(gy + R));
      for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
        const dx = i + 0.5 - gx, dy = j + 0.5 - gy; const q = (dx * dx + dy * dy) / R2; if (q > 1) continue;
        const k = j * NX + i; if (!s[k]) continue;
        const f = (1 - q) * (1 - q) * w;
        if (vx || vz) {
          const a = Math.min(1, 4 * dt * f);
          if (s[k - 1]) u[k] += (vx - u[k]) * a; if (s[k + 1]) u[k + 1] += (vx - u[k + 1]) * a;
          if (s[k - NX]) v[k] += (vz - v[k]) * a; if (s[k + NX]) v[k + NX] += (vz - v[k + NX]) * a;
        }
        if (dens) this.d[k] += dens * f * dt;
        if (heat) this.T[k] += heat * f * dt;
        if (dv) div[k] += dv * f;
      }
    };
    // vorticles: short-lived swirls spawned over the water, drifting with the flow
    const vp = p.vorticles | 0;
    let live = 0; for (const o of this.vort) if (!o.wake) live++;
    while (live++ < vp && this.srcCells?.length) {
      const k = this.srcCells[(this._rand() * this.srcCells.length) | 0];
      const i = k % NX, j = (k / NX) | 0;
      this.vort.push({ gx: i + 0.5, gy: j + 0.5, r: (p.vortR[0] + this._rand() * (p.vortR[1] - p.vortR[0])) / h,
        w: (this._rand() < 0.5 ? -1 : 1) * p.vortV * (0.5 + 0.5 * this._rand()), t0: this.time, life: p.vortLife[0] + this._rand() * (p.vortLife[1] - p.vortLife[0]) });
    }
    this.vort = this.vort.filter(o => this.time - o.t0 < o.life);
    for (const o of this.vort) {
      const a = (this.time - o.t0) / o.life, env = Math.sin(Math.PI * a); const R = o.r, R2 = R * R;
      const ci = o.gx | 0, cj = o.gy | 0; const kc = cj * NX + ci;
      if (kc > 0 && kc < this.n) { o.gx += 0.5 * (u[kc] + u[kc + 1]) * dt / h; o.gy += 0.5 * (v[kc] + v[kc + NX]) * dt / h; }
      const i0 = Math.max(1, Math.floor(o.gx - R)), i1 = Math.min(nx, Math.ceil(o.gx + R));
      const j0 = Math.max(1, Math.floor(o.gy - R)), j1 = Math.min(ny, Math.ceil(o.gy + R));
      const g = Math.min(1, 3 * dt);
      for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
        const k = j * NX + i; if (!s[k]) continue;
        // u face at (i, j + .5), v face at (i + .5, j): tangential target speed w * r/R * (1 - r^2/R^2)^2 * 2
        let dx = i - o.gx, dy = j + 0.5 - o.gy, q = (dx * dx + dy * dy) / R2;
        if (q < 1 && s[k - 1]) { const sp = o.w * env * 2.6 * Math.sqrt(q) * (1 - q) * (1 - q) / (Math.sqrt(q) + 1e-3) / R; u[k] += (-dy * sp - u[k]) * g * (1 - q); }
        dx = i + 0.5 - o.gx; dy = j - o.gy; q = (dx * dx + dy * dy) / R2;
        if (q < 1 && s[k - NX]) { const sp = o.w * env * 2.6 * Math.sqrt(q) * (1 - q) * (1 - q) / (Math.sqrt(q) + 1e-3) / R; v[k] += (dx * sp - v[k]) * g * (1 - q); }
      }
    }
    for (const jt of this.jets) apply(jt.x, jt.z, jt.r, jt.vx || 0, jt.vz || 0, jt.dens || 0, jt.heat || 0, jt.div || 0, 1);
    this.events = this.events.filter(e => this.time - e.t0 < e.dur);
    for (const e of this.events) {
      const a = (this.time - e.t0) / e.dur; const env = Math.sin(Math.PI * Math.min(1, a * 1.6)) * (1 - a * 0.5); // fast rise, slow tail
      apply(e.x, e.z, e.r, (e.vx || 0) * env, (e.vz || 0) * env, (e.dens || 0) * env, (e.heat || 0) * env, (e.div || 0) * env, 1);
    }
    // closed rooms: air that a jet or burst pushes into the layer leaves it upward everywhere else
    // (keeps the pressure solve compatible: total divergence over the fluid = 0)
    if (p.divBalance) {
      let sum = 0, cnt = 0;
      for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx; i++) { const k = j * NX + i; if (s[k]) { sum += div[k]; cnt++; } }
      if (cnt && sum !== 0) { const m = sum / cnt; for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx; i++) { const k = j * NX + i; if (s[k]) div[k] -= m; } }
    }
  }

  // Gauss-Seidel / SOR on the MAC divergence (Mueller TMP #17), with a divergence source term (1/s).
  // Red-black ordering so the sweep has no directional bias (plain lexicographic GS drifts the mist).
  _project(iters, omega, dt) {
    const { u, v, s, NX, nx, ny, h, div } = this;
    for (let it = 0; it < iters; it++) {
      for (let parity = 0; parity < 2; parity++) {
        for (let j = 1; j <= ny; j++) {
          let i = 1 + ((j + parity) & 1);
          for (; i <= nx; i += 2) {
            const k = j * NX + i;
            if (s[k] === 0) continue;
            const sx0 = s[k - 1], sx1 = s[k + 1], sy0 = s[k - NX], sy1 = s[k + NX];
            const sum = sx0 + sx1 + sy0 + sy1;
            if (sum === 0) continue;
            const dv = u[k + 1] - u[k] + v[k + NX] - v[k] - div[k] * h;
            const q = -dv / sum * omega;
            u[k] -= sx0 * q; u[k + 1] += sx1 * q; v[k] -= sy0 * q; v[k + NX] += sy1 * q;
          }
        }
      }
    }
  }

  // scalar values inside solids = mean of fluid neighbours (walls are no-flux, and the renderer samples
  // bilinearly right up to the rock, so there is no dark seam along walls)
  _extrapolate() {
    const { d, T, s, NX, nx, ny } = this;
    for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx; i++) {
      const k = j * NX + i; if (s[k]) continue;
      let w = 0, sd = 0, st = 0;
      if (s[k - 1]) { w++; sd += d[k - 1]; st += T[k - 1]; } if (s[k + 1]) { w++; sd += d[k + 1]; st += T[k + 1]; }
      if (s[k - NX]) { w++; sd += d[k - NX]; st += T[k - NX]; } if (s[k + NX]) { w++; sd += d[k + NX]; st += T[k + NX]; }
      if (w) { d[k] = sd / w; T[k] = st / w; } else { d[k] *= 0.9; T[k] *= 0.9; }
    }
    // open border cells hold clean ambient air
    for (let i = 0; i < NX; i++) { d[i] = 0; d[(this.NY - 1) * NX + i] = 0; T[i] = 0; T[(this.NY - 1) * NX + i] = 0; }
    for (let j = 0; j < this.NY; j++) { d[j * NX] = 0; d[j * NX + NX - 1] = 0; T[j * NX] = 0; T[j * NX + NX - 1] = 0; }
  }

  // bilinear sample of a field at (x, y) in cell units; field sample (i, j) sits at (i + ox, j + oy)
  _sample(f, x, y, ox, oy) {
    const NX = this.NX, NY = this.NY;
    x -= ox; y -= oy;
    if (x < 0) x = 0; else if (x > NX - 1.001) x = NX - 1.001;
    if (y < 0) y = 0; else if (y > NY - 1.001) y = NY - 1.001;
    const i = x | 0, j = y | 0, tx = x - i, ty = y - j, k = j * NX + i;
    return (f[k] * (1 - tx) + f[k + 1] * tx) * (1 - ty) + (f[k + NX] * (1 - tx) + f[k + NX + 1] * tx) * ty;
  }

  _advectVel(dt) {
    const { u, v, nu, nv, s, NX, nx, ny, h } = this;
    const c = dt / h;
    nu.set(u); nv.set(v);
    for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx + 1; i++) {
      const k = j * NX + i;
      // u face (i, j) sits at (i, j + 0.5)
      if (s[k] && s[k - 1]) {
        const uu = u[k];
        const vv = 0.25 * (v[k] + v[k - 1] + v[k + NX] + v[k + NX - 1]);
        nu[k] = this._sample(u, i - uu * c, j + 0.5 - vv * c, 0, 0.5);
      }
    }
    for (let j = 1; j <= ny + 1; j++) for (let i = 1; i <= nx; i++) {
      const k = j * NX + i;
      // v face (i, j) sits at (i + 0.5, j)
      if (s[k] && s[k - NX]) {
        const vv = v[k];
        const uu = 0.25 * (u[k] + u[k + 1] + u[k - NX] + u[k - NX + 1]);
        nv[k] = this._sample(v, i + 0.5 - uu * c, j - vv * c, 0.5, 0);
      }
    }
    this.u = nu; this.nu = u; this.v = nv; this.nv = v;
  }

  _advectScalars(dt) {
    const { u, v, d, T, nd, nT, s, NX, nx, ny, h } = this;
    const c = dt / h;
    nd.set(d); nT.set(T);
    for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx; i++) {
      const k = j * NX + i; if (!s[k]) continue;
      const uu = 0.5 * (u[k] + u[k + 1]), vv = 0.5 * (v[k] + v[k + NX]);
      const x = i + 0.5 - uu * c, y = j + 0.5 - vv * c;
      nd[k] = this._sample(d, x, y, 0.5, 0.5);
      nT[k] = this._sample(T, x, y, 0.5, 0.5);
    }
    this.d = nd; this.nd = d; this.T = nT; this.nT = T;
  }

  _rand() { let t = (this._rnd += 0x6D2B79F5); t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }
  static _h(a, b) { let n = Math.imul(a, 374761393) + Math.imul(b, 668265263) | 0; n = Math.imul(n ^ (n >>> 13), 1274126177); return ((n ^ (n >>> 16)) >>> 0) / 4294967296; }
  // cheap smooth value noise in [0, 1] (2D lattice + time as a second, moving lattice)
  static _vn(x, y) {
    const xi = Math.floor(x), yi = Math.floor(y), fx = x - xi, fy = y - yi;
    const ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
    const H = MistSim._h; const a = H(xi, yi), b = H(xi + 1, yi), c = H(xi, yi + 1), e = H(xi + 1, yi + 1);
    return (a + (b - a) * ux) * (1 - uy) + (c + (e - c) * ux) * uy;
  }
  _sources(dt) {
    const { d, T, s, srcD, srcT, dry, NX, nx, ny, p, h } = this;
    const sd = p.srcScale * dt, sh = p.heatScale * dt;
    const kT = Math.exp(-p.heatDecay * dt);
    const nA = p.srcNoise, f = p.srcNoiseScale * h, tm = this.time;
    const refresh = (this.steps & 3) === 1 || !this.srcMul; const mul = this.srcMul ??= new Float32Array(this.n);
    if (!this.srcCells) { this.srcCells = []; for (let k = 0; k < this.n; k++) if (srcD[k] > 0 && s[k]) this.srcCells.push(k); }
    for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx; i++) {
      const k = j * NX + i; if (!s[k]) continue;
      let src = srcD[k];
      if (src > 0 && nA > 0) {
        // patchy, drifting evaporation: two value-noise octaves moving in different directions
        // (refreshed every 4th step: it changes over seconds, and this keeps it ~5% of the step)
        if (refresh) {
          const n1 = MistSim._vn(i * f + tm * 0.11, j * f - tm * 0.07), n2 = MistSim._vn(i * f * 2.3 - tm * 0.19 + 17.3, j * f * 2.3 + tm * 0.13 + 5.1);
          mul[k] = (1 - nA) + nA * 2.4 * Math.max(0, n1 * 0.7 + n2 * 0.5 - 0.35);
        }
        src *= mul[k];
      }
      let dd = d[k] + src * sd * Math.max(0, 1 - d[k] / p.dMax);
      const t = T[k] * kT + srcT[k] * sh;
      dd *= Math.exp(-(p.decay + p.dryDecay * dry[k] + p.rise * t) * dt);
      d[k] = dd > p.dMax ? p.dMax : dd; T[k] = t > 1.5 ? 1.5 : t;
    }
  }

  // ---------------------------------------------------------------- output
  // RGBA8 per interior cell: R density (0..1, sqrt-encoded for precision in thin mist), G heat (0..1),
  // B/A cell-centre velocity (±PACK_VMAX m/s).
  pack(out) {
    const { d, T, u, v, NX, nx, ny } = this;
    const kv = 127.5 / PACK_VMAX;
    let o = 0;
    for (let j = 1; j <= ny; j++) for (let i = 1; i <= nx; i++) {
      const k = j * NX + i;
      const dd = d[k] < 0 ? 0 : d[k] > 1 ? 1 : d[k];
      out[o] = Math.sqrt(dd) * 255 + 0.5;
      // heat sets the layer height in the renderer: a 3x3 blur keeps plume tops round instead of grid-sharp
      const t = (4 * T[k] + T[k - 1] + T[k + 1] + T[k - NX] + T[k + NX] + 0.5 * (T[k - NX - 1] + T[k - NX + 1] + T[k + NX - 1] + T[k + NX + 1])) / 10;
      out[o + 1] = (t < 0 ? 0 : t > 1 ? 1 : t) * 255 + 0.5;
      const uc = 0.5 * (u[k] + u[k + 1]) * kv + 127.5, vc = 0.5 * (v[k] + v[k + NX]) * kv + 127.5;
      out[o + 2] = uc < 0 ? 0 : uc > 255 ? 255 : uc; out[o + 3] = vc < 0 ? 0 : vc > 255 ? 255 : vc;
      o += 4;
    }
    return out;
  }
  bytes() { return this.n * 4 * 17 + this.nx * this.ny * 4; } // 17 float fields + one packed frame
}

// ------------------------------------------------------------------ worker glue
const IS_WORKER = typeof WorkerGlobalScope !== 'undefined' && typeof self !== 'undefined' && self instanceof WorkerGlobalScope;
if (IS_WORKER) {
  let sim = null, hz = 30, timer = 0, nextAt = 0, seq = 0;
  const pool = []; let allocated = 0;
  const stepTimes = [];
  const tick = () => {
    if (!sim) return;
    const now = performance.now();
    const period = 1000 / hz;
    let n = 0;
    while (now >= nextAt && n < 2) { // fixed-rate; drop time rather than spiral if we fall behind
      const t0 = performance.now(); sim.step(1 / hz); stepTimes.push(performance.now() - t0);
      if (stepTimes.length > 60) stepTimes.shift();
      nextAt += period; n++;
    }
    if (now >= nextAt) nextAt = now + period;
    if (n) {
      let buf = pool.pop();
      if (!buf && allocated < 3) { buf = new ArrayBuffer(sim.nx * sim.ny * 4); allocated++; }
      if (buf) {
        const t0 = performance.now(); sim.pack(new Uint8Array(buf)); const packMs = performance.now() - t0;
        const avg = stepTimes.reduce((a, b) => a + b, 0) / stepTimes.length;
        const sorted = stepTimes.slice().sort((a, b) => a - b);
        self.postMessage({ type: 'frame', buf, seq: seq++, simTime: sim.time, stepMs: avg, stepP95: sorted[Math.floor(sorted.length * 0.95)] ?? avg, packMs, steps: sim.steps }, [buf]);
      }
    }
    timer = setTimeout(tick, Math.max(0, nextAt - performance.now()));
  };
  self.onmessage = (e) => {
    const m = e.data;
    if (m.type === 'init') {
      clearTimeout(timer); pool.length = 0; allocated = 0; stepTimes.length = 0;
      sim = new MistSim(m.cfg); hz = m.hz || 30;
      if (m.windU) { sim.windU.set(m.windU); sim.windV.set(m.windV); } if (m.jets) sim.setJets(m.jets);
      const t0 = performance.now();
      for (let k = 0; k < (m.prewarm || 0); k++) sim.step(1 / hz);
      self.postMessage({ type: 'ready', prewarmMs: performance.now() - t0, bytes: sim.bytes() });
      nextAt = performance.now(); tick();
    } else if (m.type === 'buf') { if (sim && m.buf.byteLength === sim.nx * sim.ny * 4) pool.push(m.buf); }
    else if (m.type === 'movers') sim?.setMovers(m.movers);
    else if (m.type === 'jets') sim?.setJets(m.jets);
    else if (m.type === 'event') sim?.addEvent(m.event);
    else if (m.type === 'params') { if (sim) Object.assign(sim.p, m.params); if (m.hz) hz = m.hz; }
    else if (m.type === 'windgrid') { if (sim) { sim.windU.set(m.u); sim.windV.set(m.v); } }
    else if (m.type === 'stop') { clearTimeout(timer); sim = null; }
  };
}
