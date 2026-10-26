// Dollhouse: orbit over a cutaway of one level (ceilings hidden), tap a place pin to travel there.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { l2t } from './coords.js';
import { LEVEL_NAMES, placeName } from './places.js';

export class Dollhouse {
  constructor(canvas, world, places, { onPick, onLevel }) {
    this.world = world; this.places = places; this.onPick = onPick; this.onLevel = onLevel ?? (() => {});
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.5, 3000);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = Math.PI * 0.47;
    this.controls.enabled = false;
    this.active = false;
    this.level = null;
    this.pinsEl = document.getElementById('kz-pins');
    this.levelsEl = document.getElementById('kz-levels');
    this.pins = [];
    this._v = new THREE.Vector3();
    this.clip = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
    this.renderer = null;
  }
  levelsAvailable() {
    const order = ['summit', 'cliff', 'ground', 'b1', 'b2', 'b3', 'b4'];
    const have = new Set(this.places.map((p) => p.level));
    return order.filter((l) => have.has(l));
  }
  enter(level) {
    this.active = true; this.controls.enabled = true;
    this.levelsEl.hidden = false;
    this.levelsEl.replaceChildren(...this.levelsAvailable().map((l) => {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = LEVEL_NAMES[l] ?? l; b.dataset.level = l;
      b.addEventListener('click', () => this.show(l));
      return b;
    }));
    this.show(level ?? 'ground');
  }
  exit() {
    this.active = false; this.controls.enabled = false;
    this.levelsEl.hidden = true;
    this.pinsEl.replaceChildren(); this.pins = [];
    for (const m of this.world.ceilings) m.visible = true;
    if (this.renderer) this.renderer.clippingPlanes = [];
  }
  zonesFor(level) {
    const ids = new Set();
    for (const p of this.places) if (p.level === level) ids.add(p.zone);
    // stairs that touch those zones
    for (const z of this.world.zones.values()) if (z.def.id.startsWith('c_') && z.def.neighbors.some((n) => ids.has(n))) ids.add(z.def.id);
    return [...ids];
  }
  async show(level) {
    this.level = level;
    for (const b of this.levelsEl.children) b.classList.toggle('on', b.dataset.level === level);
    const ids = this.zonesFor(level);
    await Promise.all(ids.map((id) => this.world.load(id).catch(() => null)));
    if (!this.active || this.level !== level) return;
    this.world.setVisible(ids);
    for (const m of this.world.ceilings) m.visible = false;
    const lp = this.places.filter((p) => p.level === level);
    // frame the level: bounds of its places' zones (non-stair)
    const box = new THREE.Box3();
    for (const id of ids) {
      if (id.startsWith('c_')) continue;
      const b = this.world.zones.get(id).def.bounds;
      const floor = Math.min(...lp.map((p) => p.pos[2] - 1.6));
      box.expandByPoint(l2t([b[0], b[1], floor])); box.expandByPoint(l2t([b[2], b[3], floor + 6]));
    }
    const floorY = Math.min(...lp.map((p) => p.pos[2] - 1.6));
    this.clip.constant = floorY + 2.6; // cutaway: keep everything below floor + 2.6 m
    if (this.renderer) this.renderer.clippingPlanes = [this.clip];
    const c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3());
    const R = Math.max(s.x, s.z) * 0.75 + 20;
    this.controls.target.copy(c);
    this.camera.position.set(c.x + R * 0.35, c.y + R * 0.9, c.z + R * 0.75);
    this.controls.minDistance = 10; this.controls.maxDistance = R * 2.5;
    this.controls.update();
    this.pins = lp.map((p) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'kz-pin' + (p.kind === 'attraction' ? ' attr' : '');
      b.textContent = p.kind === 'attraction' ? `${p.number} ${placeName(p)}` : placeName(p);
      b.addEventListener('click', (e) => { e.stopPropagation(); this.onPick(p.id); });
      return { p, el: b, pos: l2t([p.pos[0], p.pos[1], p.pos[2] - 1.0]) };
    });
    this.pinsEl.replaceChildren(...this.pins.map((q) => q.el));
    this.onLevel(level, ids);
  }
  resize(w, h) { this.camera.aspect = w / h; this.camera.updateProjectionMatrix(); }
  update() {
    if (!this.active) return;
    this.controls.update();
    const W = innerWidth, H = innerHeight;
    for (const q of this.pins) {
      this._v.copy(q.pos).project(this.camera);
      const vis = this._v.z < 1 && Math.abs(this._v.x) < 1 && Math.abs(this._v.y) < 1;
      q.el.style.display = vis ? '' : 'none';
      if (vis) q.el.style.transform = `translate(${((this._v.x * 0.5 + 0.5) * W).toFixed(1)}px, ${((-this._v.y * 0.5 + 0.5) * H).toFixed(1)}px) translate(-50%, -50%)`;
    }
  }
}
