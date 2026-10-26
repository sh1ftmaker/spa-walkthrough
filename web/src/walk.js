// First-person walker: capsule vs a separate walk/collision mesh (three-mesh-bvh), step-up, gravity,
// fixed-timestep physics with render interpolation and eye smoothing on steps.
import * as THREE from 'three';
import { MeshBVH } from 'three-mesh-bvh';
import { EYE_HEIGHT, CAPSULE_RADIUS, CAPSULE_TOP, STEP_HEIGHT, GRAVITY, WALK_SPEED, RUN_SPEED, PHYSICS_HZ } from './config.js';

const _v = new THREE.Vector3(), _v2 = new THREE.Vector3(), _tri = new THREE.Vector3(), _cap = new THREE.Vector3();
const _seg = new THREE.Line3(), _box = new THREE.Box3(), _ray = new THREE.Ray(), _n = new THREE.Vector3();

export class Walker {
  constructor() {
    this.feet = new THREE.Vector3();
    this.prevFeet = new THREE.Vector3();
    this.vel = new THREE.Vector3();
    this.vy = 0;
    this.grounded = false;
    this.yaw = 0; this.pitch = 0;
    this.eyeOffset = 0; this.eyeA = 0; this.eyeY = 0; this.prevEyeY = 0;
    this.input = { x: 0, y: 0, run: false, active: false };
    this.bvh = null; this.zoneAttr = null; this.zoneNames = [];
    this.groundZone = null; this.groundY = null;
    this.lastSafe = new THREE.Vector3();
    this.acc = 0;
    this.fixed = false; // camera driven externally (setCamera)
    this.autopilot = null;
    this.speedScale = 1;
  }

  // walk geometries: [{zone, geometry (world-space positions)}]
  setWorld(parts) {
    const zoneNames = [];
    let count = 0;
    for (const p of parts) count += p.geometry.index ? p.geometry.index.count : p.geometry.attributes.position.count;
    const pos = new Float32Array(count * 3), zone = new Uint8Array(count);
    let o = 0;
    for (const p of parts) {
      let zi = zoneNames.indexOf(p.zone);
      if (zi < 0) { zi = zoneNames.length; zoneNames.push(p.zone); }
      const g = p.geometry.index ? p.geometry.toNonIndexed() : p.geometry;
      const a = g.attributes.position;
      for (let i = 0; i < a.count; i++) { pos[o * 3] = a.getX(i); pos[o * 3 + 1] = a.getY(i); pos[o * 3 + 2] = a.getZ(i); zone[o] = zi; o++; }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('kzZone', new THREE.BufferAttribute(zone, 1));
    const t = performance.now();
    this.bvh = new MeshBVH(geo, { targetLeafSize: 8 });
    this.buildMs = performance.now() - t;
    this.geometry = geo;
    this.zoneAttr = geo.attributes.kzZone;
    this.zoneNames = zoneNames;
    this.triCount = count / 3;
  }

  raycast(origin, dir, far) {
    if (!this.bvh) return null;
    _ray.origin.copy(origin); _ray.direction.copy(dir);
    return this.bvh.raycastFirst(_ray, THREE.DoubleSide, 0, far);
  }

  // highest walkable surface under (x, z) at or below yTop, within depth
  probeGround(x, z, yTop, depth) {
    let best = null;
    const r = CAPSULE_RADIUS * 0.7;
    const offs = [[0, 0], [r, 0], [-r, 0], [0, r], [0, -r]];
    for (const [dx, dz] of offs) {
      _v.set(x + dx, yTop, z + dz);
      const hit = this.raycast(_v, _v2.set(0, -1, 0), depth);
      if (hit && hit.face && Math.abs(hit.face.normal.y) > 0.5 && (!best || hit.point.y > best.y)) {
        best = { y: hit.point.y, zone: this.zoneNames[this.zoneAttr.getX(hit.face.a)] };
      }
    }
    return best;
  }

  place(feet, { snap = true } = {}) {
    this.feet.copy(feet);
    if (snap && this.bvh) {
      const g = this.probeGround(feet.x, feet.z, feet.y + 1.0, 4.0);
      if (g) { this.feet.y = g.y; this.groundZone = g.zone; this.groundY = g.y; }
    }
    this.prevFeet.copy(this.feet);
    this.vel.set(0, 0, 0); this.vy = 0; this.eyeOffset = 0; this.grounded = true;
    this.eyeA = this.eyeY = this.prevEyeY = this.feet.y;
    this.lastSafe.copy(this.feet);
    this.fixed = false;
  }

  collide() {
    const r = CAPSULE_RADIUS;
    _seg.start.set(this.feet.x, this.feet.y + STEP_HEIGHT + r, this.feet.z);
    _seg.end.set(this.feet.x, this.feet.y + CAPSULE_TOP - r, this.feet.z);
    const sx = _seg.start.x, sz = _seg.start.z;
    for (let it = 0; it < 3; it++) {
      _box.makeEmpty(); _box.expandByPoint(_seg.start); _box.expandByPoint(_seg.end);
      _box.min.addScalar(-r); _box.max.addScalar(r);
      let moved = false;
      this.bvh.shapecast({
        intersectsBounds: (b) => b.intersectsBox(_box),
        intersectsTriangle: (tri) => {
          const d = tri.closestPointToSegment(_seg, _tri, _cap);
          if (d < r) {
            const depth = r - d;
            if (d > 1e-5) _n.subVectors(_cap, _tri).divideScalar(d); else tri.getNormal(_n);
            _n.y = 0;
            const l = _n.length();
            if (l < 1e-4) return;
            _n.divideScalar(l);
            _seg.start.addScaledVector(_n, depth); _seg.end.addScaledVector(_n, depth);
            moved = true;
          }
        },
      });
      if (!moved) break;
    }
    this.feet.x += _seg.start.x - sx;
    this.feet.z += _seg.start.z - sz;
  }

  update(dt) {
    if (!this.bvh || this.fixed) return;
    this.acc = Math.min(this.acc + dt, 0.25);
    const h = 1 / PHYSICS_HZ;
    while (this.acc >= h) {
      this.prevFeet.copy(this.feet);
      this.step(h);
      this.acc -= h;
    }
  }

  step(dt) {
    let ix = this.input.x, iy = this.input.y, speed = this.input.run ? RUN_SPEED : WALK_SPEED;
    const ap = this.autopilot;
    if (ap) {
      const tgt = ap.points[ap.i];
      const dx = tgt.x - this.feet.x, dz = tgt.z - this.feet.z, dist = Math.hypot(dx, dz);
      ap.t += dt;
      if (dist < ap.reach || ap.t > ap.timeout) {
        if (ap.t > ap.timeout) ap.skipped.push(ap.i);
        ap.i++; ap.t = 0;
        if (ap.i >= ap.points.length) { const done = ap.resolve; this.autopilot = null; done(ap.skipped); return; }
      }
      const want = Math.atan2(-dx, -dz);
      let d = want - this.yaw; d = Math.atan2(Math.sin(d), Math.cos(d));
      this.yaw += d * Math.min(1, dt * ap.turnRate);
      const dy = (tgt.y ?? this.feet.y) - this.feet.y;
      const wantPitch = Math.max(-0.45, Math.min(0.3, Math.atan2(dy, Math.max(dist, 2)) * 0.8));
      this.pitch += (wantPitch - this.pitch) * Math.min(1, dt * 2);
      ix = 0; iy = Math.min(1, dist / 0.8 + 0.3) * (Math.abs(d) > 1.2 ? 0.2 : 1); speed = ap.speed;
    }
    const mag = Math.hypot(ix, iy);
    if (mag > 1) { ix /= mag; iy /= mag; }
    speed *= this.speedScale;
    const s = Math.sin(this.yaw), c = Math.cos(this.yaw);
    const tx = (-s * iy + c * ix) * speed, tz = (-c * iy - s * ix) * speed;
    const k = 1 - Math.exp(-dt * (mag > 0.01 ? 9 : 12));
    this.vel.x += (tx - this.vel.x) * k; this.vel.z += (tz - this.vel.z) * k;
    this.feet.x += this.vel.x * dt; this.feet.z += this.vel.z * dt;
    this.collide();
    const y0 = this.feet.y;
    const g = this.probeGround(this.feet.x, this.feet.z, this.feet.y + STEP_HEIGHT + 0.02, STEP_HEIGHT + 0.02 + Math.max(0.4, -this.vy * dt + 0.05));
    if (g && this.grounded && g.y >= this.feet.y - 0.36) {
      this.feet.y = g.y; this.vy = 0;
    } else {
      this.vy -= GRAVITY * dt;
      this.feet.y += this.vy * dt;
      if (g && this.feet.y <= g.y) { this.feet.y = g.y; this.vy = 0; }
    }
    this.grounded = !!g && Math.abs(this.feet.y - g.y) < 1e-3;
    if (g) { this.groundZone = g.zone; this.groundY = g.y; }
    void y0;
    // two-pole low-pass on the eye height: steps become a smooth glide, falls/teleports snap
    this.prevEyeY = this.eyeY;
    if (Math.abs(this.feet.y - this.eyeY) > 0.6) { this.eyeA = this.eyeY = this.prevEyeY = this.feet.y; }
    else {
      const k = 1 - Math.exp(-dt * 11);
      this.eyeA += (this.feet.y - this.eyeA) * k;
      this.eyeY += (this.eyeA - this.eyeY) * k;
    }
    this.eyeOffset = this.eyeY - this.feet.y;
    if (this.grounded) this.lastSafe.copy(this.feet);
    if (this.feet.y < this.lastSafe.y - 60) { this.feet.copy(this.lastSafe); this.prevFeet.copy(this.feet); this.vy = 0; }
  }

  // interpolated eye position for rendering
  eye(out) {
    const a = this.fixed ? 1 : this.acc * PHYSICS_HZ;
    const t = Math.min(1, a);
    out.lerpVectors(this.prevFeet, this.feet, t);
    out.y = (this.fixed ? this.feet.y : this.prevEyeY + (this.eyeY - this.prevEyeY) * t) + EYE_HEIGHT;
    return out;
  }

  walkPath(points, { speed = 1.6, reach = 0.7, timeout = 25, turnRate = 3.5 } = {}) {
    return new Promise((resolve) => {
      this.fixed = false;
      this.autopilot = { points, i: 0, t: 0, speed, reach, timeout, turnRate, resolve, skipped: [] };
    });
  }
}
