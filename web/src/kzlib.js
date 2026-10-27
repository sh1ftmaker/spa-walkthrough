// Library materials for Blender parts: manifest material { type: 'kz', id (kz_id), params (the 7 kz settings), kit, maps, lib }.
// Kit materials (3d/materials.json kzTech + plates) go through kzShade (vendor/kzshader.js, configured by KZM[id]);
// the rest use the library texture set: kzShade mode 0 (plain tiling, handles the RG-normal + height packing),
// emissive map from <set>_emis, alpha cards as plain MeshStandardMaterial with alphaTest.
// lava_molten (and anything with a _kz_flow attribute) scrolls along its flow direction.
import * as THREE from 'three';
import { kzShade } from './vendor/kzshader.js';
import { KZM } from './vendor/kzmaterials.js';

const FLOW_SPEED = { lava_molten: 0.05, lava_flow: 0.03, waterfall: 0.6 }; // metres of UV0 per second

const PAPER = new Set(['lantern_paper', 'lantern_andon', 'lantern_andon_plain', 'washi_backlit']);

export function settingsOf(d, gain = 1) {
  const p = d.params ?? {};
  return {
    tint: (p.tint ?? [1, 1, 1]).map((x) => x * gain), wetness: p.wetness ?? 0, wear: p.wear ?? 0,
    roughness_offset: p.roughness_offset ?? 0, normal_strength: p.normal_strength ?? 1,
    emissive_level: p.emissive_level ?? 1,
  };
}

/**
 * Builds the material (already patchMaterial'd by the caller: fog, probes, lightmap decode).
 * tex(id, colorSpace) returns the manifest texture. Returns { mat, kit: bool }.
 */
export function makeKzMaterial(name, d, tex, tier, side, prepare) {
  const k = KZM[d.id];
  const lib = d.lib ?? {};
  const p = d.params ?? {};
  const alpha = lib.alphaTest != null;
  const mat = new THREE.MeshStandardMaterial({ name, color: 0xffffff, roughness: 1, metalness: 0, side: alpha || lib.doubleSided ? THREE.DoubleSide : side });
  const scale = lib.uv_mode === 'object' ? 1 : (p.scale || lib.tiling || 1);
  const aspect = lib.aspect || 1;
  const t = (id, cs) => (id ? tex(id, cs) : null);
  // emission from the library emissive map (kit materials add their own on top through KZM[id].emissive)
  const emisLevel = p.emissive_level ?? 1;
  // kit materials with their own emission (KZM[id].emissive: lava, lava_flow, glacier_ice) skip the library emissive map
  if (d.maps?.emis && lib.emissive && emisLevel > 0 && !(k?.emissive && k.tech !== 'keep' && d.kit?.base)) {
    const e = t(d.maps.emis, THREE.SRGBColorSpace).clone();
    e.repeat.set(1 / scale, aspect / scale);
    e.wrapS = e.wrapT = THREE.RepeatWrapping;
    mat.emissiveMap = e;
    // paper emitters also pass the light of the lamp inside (Cycles renders that as translucency; the web cannot):
    // measured against the Cycles concept renders, the lantern pools came out ~0.7 stops short without this
    const backlit = PAPER.has(d.id) ? 1.6 : 1;
    const tint = p.tint ?? [1, 1, 1], s = lib.emissive.strength * emisLevel * lib.emissive.map_scale * backlit;
    mat.emissive.setRGB(tint[0] * s * lib.emissive.color[0], tint[1] * s * lib.emissive.color[1], tint[2] * s * lib.emissive.color[2], THREE.LinearSRGBColorSpace);
    mat.emissiveIntensity = 1;
  }
  mat.envMapIntensity = lib.envMapIntensity ?? 1;
  if (lib.transparent) { // glass / lava glass: no transmission on the web, a thin alpha pane over the scene
    mat.transparent = true; mat.depthWrite = false; mat.opacity = d.id === 'lava_glass' ? 0.12 : 0.2; mat.envMapIntensity = 0.3; // clear panes: the lava field must read through them
    mat.defines = { ...(mat.defines ?? {}), KZ_NO_DIRECT: '' }; // panes: no pool lights at all (the lava-window light sits 0.6 m in front of the glass and blew it white)
  }
  if (alpha) {
    // alpha cards: plain three material (the kit has no alpha path)
    const b = t(d.maps.base, THREE.SRGBColorSpace).clone();
    b.repeat.set(1 / scale, aspect / scale); b.wrapS = b.wrapT = THREE.RepeatWrapping;
    mat.map = b; mat.alphaTest = lib.alphaTest;
    const tint = p.tint ?? [1, 1, 1];
    mat.color.setRGB(tint[0], tint[1], tint[2], THREE.LinearSRGBColorSpace);
    mat.roughness = 0.8;
    prepare(mat);
    return { mat, kit: false };
  }
  let cfg;
  if (k && k.tech !== 'keep' && d.kit?.base) {
    const ratio = (p.scale ?? 1) / (lib.tiling ?? p.scale ?? 1);
    const m = k.plateM * ratio;
    cfg = {
      ...k, mode: k.tech === 'hybrid' || k.tech === 'procedural' ? 3 : 2, tier,
      hybrid: k.tech === 'hybrid', patch: true, aspect: 1, tileM: [m, m],
      maps: { base: t(d.kit.base, THREE.SRGBColorSpace), nh: t(d.kit.nh, THREE.NoColorSpace) },
      maps2: d.kit.base2 ? { base: t(d.kit.base2, THREE.SRGBColorSpace), nh: t(d.kit.nh2, THREE.NoColorSpace) } : null,
      noiseTex: d.kit.noise ? t(d.kit.noise, THREE.NoColorSpace) : null,
      porosity: lib.porosity ?? k.porosity, worn: { color: lib.worn?.color ?? [0.05, 0.05, 0.05], rough: lib.worn?.rough ?? 0.45 },
      settings: { ...settingsOf(d, k.tech === 'procedural' && k.proc ? 1 : k.gain ?? 1), scale: m },
    };
  } else if (d.maps?.base) {
    cfg = {
      mode: 0, tier, proj: 'uv', proc: null, patch: false,
      maps: { base: t(d.maps.base, THREE.SRGBColorSpace), nh: t(d.maps.nh, THREE.NoColorSpace), orm: t(d.maps.orm, THREE.NoColorSpace) },
      tileM: [scale, scale / aspect], aspect, macro: { amount: 0 },
      porosity: lib.porosity ?? 0.5, worn: { color: lib.worn?.color ?? [0.05, 0.05, 0.05], rough: lib.worn?.rough ?? 0.45 },
      rough: [0.7, 0.1], metal: 0,
      settings: { ...settingsOf(d), scale },
    };
    if (d.maps.emis) cfg.settings.emissive_level = 0; // emission comes from the emissive map above
  } else {
    prepare(mat);
    return { mat, kit: false };
  }
  prepare(mat);
  for (const key of Object.keys(cfg)) if (cfg[key] === undefined) delete cfg[key];
  kzShade(mat, cfg);
  return { mat, kit: true };
}

// UV scroll along the per-vertex flow (_kz_flow, unit UV-space direction) or along -v for lava without one.
export function addFlow(mat, id, hasFlowAttr, timeUniform) {
  const speed = FLOW_SPEED[id];
  if (!speed) return;
  const prev = mat.onBeforeCompile, prevKey = mat.customProgramCacheKey?.bind(mat) ?? (() => '');
  mat.onBeforeCompile = (shader, r) => {
    prev?.call(mat, shader, r);
    shader.uniforms.kzTime = timeUniform;
    let vs = shader.vertexShader;
    const decl = `uniform float kzTime;\n${hasFlowAttr ? 'attribute vec2 _kz_flow;\n' : ''}`;
    vs = decl + vs;
    const off = `(${hasFlowAttr ? '_kz_flow' : 'vec2(0.0, -1.0)'} * kzTime * ${speed.toFixed(4)})`;
    if (vs.includes('kzUv = uv;')) vs = vs.replace('kzUv = uv;', `kzUv = uv - ${off};`);
    vs = vs.replace('#include <uv_vertex>', `#include <uv_vertex>\n#ifdef USE_EMISSIVEMAP\n\tvEmissiveMapUv -= ( emissiveMapTransform * vec3( ${off}, 0.0 ) ).xy;\n#endif\n#ifdef USE_MAP\n\tvMapUv -= ( mapTransform * vec3( ${off}, 0.0 ) ).xy;\n#endif`);
    shader.vertexShader = vs;
  };
  mat.customProgramCacheKey = () => `${prevKey()}|flow${hasFlowAttr ? 1 : 0}`;
}
