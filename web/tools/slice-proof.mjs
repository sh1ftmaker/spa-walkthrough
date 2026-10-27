#!/usr/bin/env node
// Browser proof for the Blender places: each place's concept camera at 16:9 and 9:16 on both tiers, plus the phone
// preset (Low), through tools/shot.mjs. Writes the captures and logs __kz.info() per shot to a JSON report.
//   node tools/slice-proof.mjs --cdp 9311 --url http://127.0.0.1:5173/ --places g_arrival,b1_cor_mirror,b1_mirror \
//        --out ../3d/renders/web/slice --report ../3d/checks/web_slice.json [--cams concept,entry]
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) if (argv[i].startsWith('--')) opt[argv[i].slice(2)] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
const places = String(opt.places).split(',');
const cams = String(opt.cams ?? 'concept').split(',');
const out = resolve(opt.out), report = resolve(opt.report);
const manifest = JSON.parse(readFileSync(join(here, '../public/assets/manifests/low.json'), 'utf8'));
const doc = existsSync(report) ? JSON.parse(readFileSync(report, 'utf8')) : {};
doc.generated = new Date().toISOString();
doc.manifest = { source: manifest.source, generated: manifest.generated, places_blender: manifest.places_blender };
doc.budget = manifest.budget;
doc.shots = [];
const run = (args) => JSON.parse(execFileSync('node', [join(here, 'shot.mjs'), '--cdp', String(opt.cdp ?? 9311), '--url', opt.url, '--query', 'labels=0', ...args], { encoding: 'utf8', maxBuffer: 1 << 26 }));
for (const p of places) {
  const sf = JSON.parse(readFileSync(join(here, '../../3d/spaces', `${p}.json`), 'utf8'));
  for (const c of cams) {
    const cam = sf.cameras?.[c];
    if (!cam?.pos) continue;
    const cargs = ['--pos', cam.pos.join(','), '--target', cam.target.join(','), '--fov', String(cam.fov_v ?? 60), '--frames', '40'];
    for (const tier of ['low', 'high']) {
      const res = run([...cargs, '--tier', tier, '--sizes', '16:9,9:16', '--out', join(out, `${p}-${c}-${tier}`)]);
      for (const r of res) doc.shots.push({ place: p, cam: c, tier, ...r });
      console.log(`${p} ${c} ${tier}: ${res.map((r) => `${r.tag} ${r.info.drawCalls} draws ${Math.round(r.info.triangles / 1000)}k tris ${r.info.textureMB} MB ${r.info.ms} ms`).join(' | ')}`);
    }
    if (c === cams[0]) {
      const res = run([...cargs, '--tier', 'low', '--device', 'phone', '--out', join(out, `${p}-${c}`)]);
      for (const r of res) doc.shots.push({ place: p, cam: c, tier: 'low', ...r });
      console.log(`${p} ${c} phone: ${res[0].info.drawCalls} draws ${Math.round(res[0].info.triangles / 1000)}k tris`);
    }
  }
}
const lowShots = doc.shots.filter((s) => s.tier === 'low');
doc.summary = {
  shots: doc.shots.length,
  low_worst: { drawCalls: Math.max(...lowShots.map((s) => s.info.drawCalls)), triangles: Math.max(...lowShots.map((s) => s.info.triangles)), textureMB: Math.max(...lowShots.map((s) => s.info.textureMB)) },
  high_worst: { drawCalls: Math.max(...doc.shots.filter((s) => s.tier === 'high').map((s) => s.info.drawCalls)), triangles: Math.max(...doc.shots.filter((s) => s.tier === 'high').map((s) => s.info.triangles)) },
  errors: doc.shots.flatMap((s) => s.logs.filter((l) => /^error|pageerror|HTTP/.test(l) && !/WebGL context|selected attributes/.test(l))),
};
doc.summary.low_within_budget = doc.summary.low_worst.drawCalls <= 150 && doc.summary.low_worst.triangles <= 500000;
writeFileSync(report, JSON.stringify(doc, null, 1));
console.log(JSON.stringify(doc.summary));
