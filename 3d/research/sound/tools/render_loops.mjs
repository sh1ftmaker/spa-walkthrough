// Bake the whole procedural bank in Node and write every loop / one-shot as 16-bit WAV for analysis.
// node 3d/research/sound/tools/render_loops.mjs [sampleRate] [outDir]
import { bakeAll } from '../demo/js/bank.js';
import { writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const sr = Number(process.argv[2] || 48000);
const out = process.argv[3] || join(here, '..', '..', '..', '..', '.scratch', 'sound', 'bank');
mkdirSync(out, { recursive: true });

export function wav(chs, sr) {
  const n = chs[0].length, c = chs.length, buf = Buffer.alloc(44 + n * c * 2);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * c * 2, 4); buf.write('WAVEfmt ', 8); buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20); buf.writeUInt16LE(c, 22); buf.writeUInt32LE(sr, 24); buf.writeUInt32LE(sr * c * 2, 28);
  buf.writeUInt16LE(c * 2, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(n * c * 2, 40);
  let o = 44, clipped = 0;
  for (let i = 0; i < n; i++) for (let k = 0; k < c; k++) { let v = chs[k][i]; if (v > 1 || v < -1) clipped++; v = Math.max(-1, Math.min(1, v)); buf.writeInt16LE(Math.round(v * 32767), o); o += 2; }
  return { buf, clipped };
}

if (process.argv[1] && process.argv[1].endsWith("render_loops.mjs")) {
const t0 = Date.now();
const bank = await bakeAll(sr, () => {}, async () => {});
const total = Date.now() - t0;
const report = { sr, total_ms: total, decoded_MB: +(bank.meta.bytes / 1e6).toFixed(1), ms: bank.meta.ms, files: {} };
for (const [name, l] of Object.entries(bank.loops)) { const { buf, clipped } = wav(l.chs, l.sr); writeFileSync(join(out, `loop_${name}.wav`), buf); report.files[`loop_${name}`] = { ch: l.chs.length, sr: l.sr, secs: +(l.chs[0].length / l.sr).toFixed(2), clipped }; }
for (const [name, vs] of Object.entries(bank.shots)) vs.forEach((v, i) => { const chs = v.chs; const { buf, clipped } = wav(chs, v.sr); writeFileSync(join(out, `shot_${name}_${i}.wav`), buf); report.files[`shot_${name}_${i}`] = { ch: chs.length, sr: v.sr, secs: +(chs[0].length / v.sr).toFixed(2), clipped }; });
writeFileSync(join(out, 'bake_report.json'), JSON.stringify(report, null, 1));
console.log(JSON.stringify({ total_ms: total, decoded_MB: report.decoded_MB, ms: bank.meta.ms }, null, 1));
}
