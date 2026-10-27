#!/usr/bin/env node
// Gallery data check for `npm run build` (prebuild). The data itself needs Blender and is written by
//   .venv/bin/python tools/export/export_gallery.py      (repo root; see that file)
// into public/gallery/. This step only verifies it: index.json + materials.json parse, and every file they reference
// (parts/*.glb, tex/*.ktx2, img/*.jpg) exists. Missing data is a warning (gallery.html then shows its error panel);
// a broken reference fails the build.
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const G = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'gallery');
const idx = join(G, 'data', 'index.json'), mats = join(G, 'data', 'materials.json');
if (!existsSync(idx) || !existsSync(mats)) {
  console.warn('build-gallery: no public/gallery/data (run tools/export/export_gallery.py); gallery.html will show an error');
  process.exit(0);
}
const refs = new Set();
const walk = (x) => {
  if (typeof x === 'string') { if (/^(parts|tex|img)\/[0-9a-f]{16}\.(glb|ktx2|jpg)$/.test(x)) refs.add(x); return; }
  if (Array.isArray(x)) x.forEach(walk); else if (x && typeof x === 'object') Object.values(x).forEach(walk);
};
const I = JSON.parse(readFileSync(idx, 'utf8'));
walk(I); walk(JSON.parse(readFileSync(mats, 'utf8')));
let bytes = 0;
const missing = [];
for (const r of refs) { const f = join(G, r); if (existsSync(f)) bytes += statSync(f).size; else missing.push(r); }
if (missing.length) {
  console.error(`build-gallery: ${missing.length} referenced files missing:\n  ${missing.slice(0, 20).join('\n  ')}`);
  process.exit(1);
}
console.log(`build-gallery: ${I.assets.length} models, ${refs.size} files, ${(bytes / 1048576).toFixed(1)} MB`);
