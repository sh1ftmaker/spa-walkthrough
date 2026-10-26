// Place list (teleport sheet) and on-screen labels that fade with distance and are occlusion-tested against the walk mesh.
import * as THREE from 'three';
import { l2t } from './coords.js';

const LEVEL_ORDER = ['summit', 'cliff', 'ground', 'b1', 'b2', 'b3', 'b4'];
export const LEVEL_NAMES = { summit: 'Summit', cliff: 'Cliff suites', ground: 'Ground', b1: 'B1 Thermal', b2: 'B2 River', b3: 'B3 Aqua Cavern', b4: 'B4 Magma' };

export function placeName(p) { return p.kind === 'attraction' ? p.name.replace(/^\d\d\s+/, '') : p.name; }

export function buildPlaceSheet(places, onPick) {
  const body = document.createElement('div');
  const attractions = places.filter((p) => p.kind === 'attraction').sort((a, b) => a.number - b.number);
  if (attractions.length) {
    const h = document.createElement('div'); h.className = 'kz-group'; h.textContent = 'The ten attractions'; body.appendChild(h);
    for (const p of attractions) body.appendChild(item(p, String(p.number), onPick));
  }
  for (const lv of LEVEL_ORDER) {
    const list = places.filter((p) => p.level === lv && p.kind !== 'attraction');
    if (!list.length) continue;
    const h = document.createElement('div'); h.className = 'kz-group'; h.textContent = LEVEL_NAMES[lv] ?? lv; body.appendChild(h);
    for (const p of list) body.appendChild(item(p, null, onPick));
  }
  const rest = places.filter((p) => !LEVEL_ORDER.includes(p.level) && p.kind !== 'attraction');
  for (const p of rest) body.appendChild(item(p, null, onPick));
  return body;
}
function item(p, n, onPick) {
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'kz-item'; b.dataset.place = p.id;
  const s = document.createElement('span'); s.className = n ? 'n' : 'n dot'; s.textContent = n ?? '·';
  const t = document.createElement('span'); t.textContent = placeName(p);
  b.append(s, t);
  b.addEventListener('click', () => onPick(p.id));
  return b;
}

export class Labels {
  constructor(container, places, walker) {
    this.el = container; this.walker = walker;
    this.items = places.filter((p) => p.label).map((p) => {
      const d = document.createElement('div');
      d.className = 'kz-label' + (p.kind === 'attraction' ? ' attr' : '');
      if (p.kind === 'attraction') { const n = document.createElement('span'); n.className = 'n'; n.textContent = p.number; d.appendChild(n); }
      d.appendChild(document.createTextNode(p.label.text));
      container.appendChild(d);
      return { p, el: d, pos: l2t(p.label.pos), visible: false, occluded: false, opacity: 0, checked: 0 };
    });
    this.max = 4; this.maxDist = 45; this.enabled = true; this.rr = 0;
    this._v = new THREE.Vector3(); this._d = new THREE.Vector3();
  }
  update(camera, visibleZones) {
    const W = innerWidth, H = innerHeight;
    const cam = camera.position;
    const zones = new Set(visibleZones);
    const cand = [];
    for (const it of this.items) {
      it.want = 0;
      if (!this.enabled || !zones.has(it.p.zone)) continue;
      const d = it.pos.distanceTo(cam);
      if (d > this.maxDist || d < 1.2) continue;
      this._v.copy(it.pos).project(camera);
      if (this._v.z > 1 || Math.abs(this._v.x) > 1.05 || Math.abs(this._v.y) > 1.05) continue;
      cand.push({ it, d, sx: (this._v.x * 0.5 + 0.5) * W, sy: (-this._v.y * 0.5 + 0.5) * H });
    }
    cand.sort((a, b) => (a.it.p.kind === 'attraction' ? -8 : 0) + a.d - ((b.it.p.kind === 'attraction' ? -8 : 0) + b.d));
    // occlusion: re-test a couple per frame (round-robin)
    for (let k = 0; k < Math.min(3, cand.length); k++) {
      const c = cand[(this.rr++) % cand.length];
      this._d.subVectors(c.it.pos, cam);
      const len = this._d.length();
      const hit = this.walker.raycast(cam, this._d.normalize(), len - 0.3);
      c.it.occluded = !!hit;
    }
    const placed = [];
    for (const c of cand) {
      if (placed.length >= this.max) break;
      if (c.it.occluded) continue;
      if (placed.some((p) => Math.abs(p.sx - c.sx) < 120 && Math.abs(p.sy - c.sy) < 28)) continue;
      placed.push(c);
      const fade = Math.min(1, (this.maxDist - c.d) / (this.maxDist * 0.4));
      c.it.want = Math.max(0, fade);
      c.it.el.style.transform = `translate(${c.sx.toFixed(1)}px, ${c.sy.toFixed(1)}px) translate(-50%, -100%)`;
    }
    for (const it of this.items) {
      const o = it.want.toFixed(2);
      if (it.el.style.opacity !== o) it.el.style.opacity = o;
    }
  }
  hideAll() { for (const it of this.items) it.el.style.opacity = '0'; }
}
