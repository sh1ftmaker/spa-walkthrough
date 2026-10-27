// GLB writing (meshopt + quantized) and content-addressed file output.
import { Document, NodeIO, Logger } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { weld, meshopt } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptDecoder } from 'meshoptimizer';
import { createHash } from 'node:crypto';
import { writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';

await MeshoptEncoder.ready;
await MeshoptDecoder.ready;
export const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  'meshopt.encoder': MeshoptEncoder,
  'meshopt.decoder': MeshoptDecoder,
});

export const sha16 = (buf) => createHash('sha256').update(buf).digest('hex').slice(0, 16);

// Write bytes to <root>/<dir>/<sha16>.<ext>; returns the relative uri.
export function writeAddressed(root, dir, ext, bytes) {
  const name = `${sha16(bytes)}.${ext}`;
  const rel = `${dir}/${name}`;
  const abs = join(root, rel);
  mkdirSync(dirname(abs), { recursive: true });
  if (!existsSync(abs)) writeFileSync(abs, bytes);
  return rel;
}

/**
 * meshes: [{ name, material: {name, color:[r,g,b], roughness, metalness, emissive:[r,g,b]}, attrs: {position, normal?, uv0?, uv1?, color?},
 *            custom?: { _NAME: { type: 'VEC2'|'VEC3'|'VEC4'|'SCALAR', array } }, mode?: 'triangles'|'points'|'lines', extras }]
 * Custom attributes (glTF names starting with "_") stay float32 (only standard attributes are quantized).
 */
export async function buildGLB(meshes, { generator = 'kazanyu-standin' } = {}) {
  const doc = new Document().setLogger(new Logger(Logger.Verbosity.ERROR));
  doc.getRoot().getAsset().generator = generator;
  const buf = doc.createBuffer();
  const scene = doc.createScene('kz');
  doc.getRoot().setDefaultScene(scene);
  const mats = new Map();
  for (const m of meshes) {
    if (!m.attrs.position.length) continue;
    let mat = null;
    if (m.material) {
      mat = mats.get(m.material.name);
      if (!mat) {
        const c = m.material.color ?? [0.5, 0.5, 0.5];
        mat = doc.createMaterial(m.material.name)
          .setBaseColorFactor([c[0], c[1], c[2], 1])
          .setRoughnessFactor(m.material.roughness ?? 0.8)
          .setMetallicFactor(m.material.metalness ?? 0)
          .setEmissiveFactor(m.material.emissive ?? [0, 0, 0])
          .setDoubleSided(true);
        mats.set(m.material.name, mat);
      }
    }
    const acc = (type, arr) => doc.createAccessor().setType(type).setArray(arr).setBuffer(buf);
    const prim = doc.createPrimitive().setAttribute('POSITION', acc('VEC3', m.attrs.position));
    if (m.attrs.normal) prim.setAttribute('NORMAL', acc('VEC3', m.attrs.normal));
    if (m.attrs.uv0) prim.setAttribute('TEXCOORD_0', acc('VEC2', m.attrs.uv0));
    if (m.attrs.uv1) prim.setAttribute('TEXCOORD_1', acc('VEC2', m.attrs.uv1));
    if (m.attrs.color) prim.setAttribute('COLOR_0', acc('VEC4', m.attrs.color));
    for (const [k, v] of Object.entries(m.custom ?? {})) prim.setAttribute(k, acc(v.type, v.array));
    if (m.mode === 'points') prim.setMode(0);
    else if (m.mode === 'lines') prim.setMode(1);
    if (mat) prim.setMaterial(mat);
    const mesh = doc.createMesh(m.name).addPrimitive(prim);
    const node = doc.createNode(m.name).setMesh(mesh).setExtras({ kz: m.extras ?? {} });
    scene.addChild(node);
  }
  await doc.transform(
    weld(),
    meshopt({ encoder: MeshoptEncoder, level: 'medium', quantizePosition: 16, quantizeTexcoord: 14, quantizeNormal: 10 }),
  );
  return io.writeBinary(doc);
}
export { weld, meshopt, MeshoptEncoder };
