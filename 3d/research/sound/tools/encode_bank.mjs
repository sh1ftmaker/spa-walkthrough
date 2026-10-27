// Pre-render the procedural bank offline and encode it for the web: Ogg Opus (primary) + AAC .m4a (fallback).
// Loops get a wrapped pad (pad s of the loop's end before it, pad s of its start after it) so codec priming can
// never cause a click at the loop point. Writes demo/assets/{loop_*,shot_*}.{opus,m4a} + manifest.json.
// node 3d/research/sound/tools/encode_bank.mjs
import { bakeAll } from '../demo/js/bank.js';
import { wav } from './render_loops.mjs';
import { writeFileSync, mkdirSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..', '..', '..', '..');
const tmp = join(root, '.scratch', 'sound', 'enc'); const out = join(here, '..', 'demo', 'assets');
mkdirSync(tmp, { recursive: true }); mkdirSync(out, { recursive: true });
const PAD = 0.25;
const bank = await bakeAll(48000, () => {}, async () => {});
const man = { pad_s: PAD, loops: {}, shots: {}, bytes: { opus: 0, m4a: 0 } };
const enc = (name, chs, sr) => {
  const w = join(tmp, name + '.wav'); writeFileSync(w, wav(chs, sr).buf);
  const st = chs.length > 1; const ob = st ? '64k' : '40k', ab = st ? '96k' : '64k';
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', w, '-c:a', 'libopus', '-b:a', ob, '-application', 'audio', join(out, name + '.opus')]);
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', w, '-c:a', 'aac', '-b:a', ab, '-movflags', '+faststart', join(out, name + '.m4a')]);
  man.bytes.opus += statSync(join(out, name + '.opus')).size; man.bytes.m4a += statSync(join(out, name + '.m4a')).size;
};
for (const [name, l] of Object.entries(bank.loops)) {
  const n = l.chs[0].length, p = Math.round(PAD * l.sr);
  const padded = l.chs.map((c) => { const o = new Float32Array(n + 2 * p); o.set(c.subarray(n - p), 0); o.set(c, p); o.set(c.subarray(0, p), n + p); return o; });
  enc('loop_' + name, padded, l.sr);
  man.loops[name] = { sr: l.sr, n, ch: l.chs.length, pad: p, ...(l.gust ? { gust: Array.from(l.gust, (v) => +v.toFixed(3)) } : {}) };
}
// Round 3: CC0 anchor loops prepared by tools/make_anchors.py (.scratch/sound/anchors/anchor_*.wav, already seamless).
import { readdirSync, readFileSync, existsSync } from 'node:fs';
const adir = join(root, '.scratch', 'sound', 'anchors');
if (existsSync(adir)) for (const f of readdirSync(adir).filter((q) => /^anchor_.*\.wav$/.test(q))) {
  const b = readFileSync(join(adir, f)); const sr = b.readUInt32LE(24); const n = b.readUInt32LE(40) / 2; const c = new Float32Array(n);
  for (let i = 0; i < n; i++) c[i] = b.readInt16LE(44 + 2 * i) / 32768;
  const p = Math.round(PAD * sr); const o = new Float32Array(n + 2 * p); o.set(c.subarray(n - p), 0); o.set(c, p); o.set(c.subarray(0, p), n + p);
  const name = f.slice(0, -4); const w = join(tmp, name + '.wav'); writeFileSync(w, wav([o], sr).buf);
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', w, '-c:a', 'libopus', '-b:a', '32k', '-application', 'audio', join(out, 'loop_' + name + '.opus')]);
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', w, '-c:a', 'aac', '-b:a', '48k', '-movflags', '+faststart', join(out, 'loop_' + name + '.m4a')]);
  const ob = statSync(join(out, 'loop_' + name + '.opus')).size, mb = statSync(join(out, 'loop_' + name + '.m4a')).size; man.bytes.opus += ob; man.bytes.m4a += mb;
  man.loops[name] = { sr, n, ch: 1, pad: p, anchor: true, opus_bytes: ob, m4a_bytes: mb };
  console.log('anchor', name, (n / sr).toFixed(1) + ' s', (ob / 1000).toFixed(0) + ' KB opus', (mb / 1000).toFixed(0) + ' KB m4a');
}
for (const [name, vs] of Object.entries(bank.shots)) { man.shots[name] = vs.map((v, i) => { enc(`shot_${name}_${i}`, v.chs, v.sr); return { sr: v.sr, n: v.chs[0].length }; }); }
writeFileSync(join(out, 'manifest.json'), JSON.stringify(man));
console.log('opus total', (man.bytes.opus / 1e6).toFixed(2), 'MB; m4a total', (man.bytes.m4a / 1e6).toFixed(2), 'MB');
