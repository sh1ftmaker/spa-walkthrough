// Asset contract loader: manifests/<tier>.json -> textures, material library, zones (GLB parts, walk mesh, lightmaps, probes).
// Every fetch failure is collected and shown; nothing fails silently.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

export class AssetError extends Error {
  constructor(failures) {
    super(`${failures.length} asset(s) failed to load:\n` + failures.map((f) => `  ${f.status}  ${f.url}${f.detail ? `  (${f.detail})` : ''}`).join('\n'));
    this.failures = failures;
  }
}

export function showFailures(failures, title = 'Missing or broken assets') {
  const el = document.getElementById('kz-error');
  el.hidden = false;
  const lines = failures.map((f) => `${String(f.status).padEnd(5)} ${f.url}${f.detail ? `\n      ${f.detail}` : ''}`);
  el.innerHTML = `<b>${title} (${failures.length})</b>\n\n`;
  el.appendChild(document.createTextNode(lines.join('\n')));
  console.error(`[kz] ${title}:\n` + lines.join('\n'));
}

export class Assets {
  constructor(renderer) {
    this.root = new URL('assets/', document.baseURI);
    this.failures = [];
    this.bytes = 0;
    this.ktx2 = new KTX2Loader().setTranscoderPath(new URL('libs/basis/', document.baseURI).href).detectSupport(renderer);
    this.gltf = new GLTFLoader().setKTX2Loader(this.ktx2).setMeshoptDecoder(MeshoptDecoder);
    this.textureBytes = 0;
  }
  url(rel) { return new URL(rel, this.root).href; }

  async fetchBuf(rel, type = 'arrayBuffer') {
    const url = this.url(rel);
    let res;
    try { res = await fetch(url, { cache: rel.startsWith('manifests/') ? 'no-cache' : 'default' }); }
    catch (e) { throw this.fail(url, 'NET', e.message); }
    if (!res.ok) throw this.fail(url, res.status, res.statusText);
    const out = await res[type]();
    this.bytes += type === 'arrayBuffer' ? out.byteLength : out.length ?? 0;
    return out;
  }
  async json(rel) {
    const txt = await this.fetchBuf(rel, 'text');
    try { return JSON.parse(txt); } catch (e) { throw this.fail(this.url(rel), 'JSON', e.message); }
  }
  fail(url, status, detail) {
    const f = { url, status, detail };
    this.failures.push(f);
    return new AssetError([f]);
  }
  // run loaders in parallel; if any failed, throw one error listing all of them
  async all(promises) {
    const res = await Promise.allSettled(promises);
    const bad = res.filter((r) => r.status === 'rejected');
    if (bad.length) {
      const failures = bad.flatMap((r) => (r.reason instanceof AssetError ? r.reason.failures : [{ url: '?', status: 'ERR', detail: String(r.reason?.message ?? r.reason) }]));
      throw new AssetError(failures);
    }
    return res.map((r) => r.value);
  }

  async texture(rel) {
    const buf = await this.fetchBuf(rel);
    const url = this.url(rel);
    try {
      const tex = await new Promise((resolve, reject) => {
        this.ktx2.parse(buf, resolve, reject);
      });
      tex.name = rel;
      this.textureBytes += textureBytes(tex);
      return tex;
    } catch (e) {
      throw this.fail(url, 'KTX2', e.message ?? String(e));
    }
  }
  async glb(rel) {
    const buf = await this.fetchBuf(rel);
    try {
      return await new Promise((resolve, reject) => this.gltf.parse(buf, this.url(rel), resolve, reject));
    } catch (e) {
      throw this.fail(this.url(rel), 'GLB', e.message ?? String(e));
    }
  }

  async manifest(tier) {
    const m = await this.json(`manifests/${tier}.json`);
    if (m.contract !== 1) throw this.fail(this.url(`manifests/${tier}.json`), 'VER', `contract ${m.contract} not supported (expected 1)`);
    return m;
  }
  async libraryTextures(manifest) {
    const ids = Object.keys(manifest.textures);
    const texs = await this.all(ids.map((id) => this.texture(manifest.textures[id].uri)));
    return Object.fromEntries(ids.map((id, i) => [id, texs[i]]));
  }
  async zone(zm) {
    const [parts, walk, lightmaps] = await this.all([
      this.all(zm.parts.map((p) => this.glb(p.uri))),
      this.glb(zm.walk.uri),
      this.all((zm.lightmaps ?? []).map((l) => this.texture(l.uri))),
    ]);
    return { parts, walk, lightmaps };
  }
}

export function textureBytes(tex) {
  if (tex.isCompressedTexture || tex.mipmaps?.length) {
    let b = 0;
    for (const m of tex.mipmaps ?? []) b += m.data?.byteLength ?? 0;
    return b;
  }
  const img = tex.image;
  if (img?.width) return img.width * img.height * 4 * 1.33;
  return 0;
}
