// Material library, shader patches (height fog/mist, box-projected probes, RGBM lightmaps) and shared uniforms.
import * as THREE from 'three';
import { FOG, LIGHTMAP_INTENSITY } from './config.js';
import { KZS } from './vendor/kzshader.js';
import { makeKzMaterial, addFlow } from './kzlib.js';

// ---- shared uniforms (same objects referenced by every patched program) ----
export const KZ = {
  kzFogColor: { value: new THREE.Color().setRGB(...FOG.color, THREE.LinearSRGBColorSpace) },
  kzFogDensity: { value: FOG.density },
  kzMistColor: { value: new THREE.Color().setRGB(...FOG.mistColor, THREE.LinearSRGBColorSpace) },
  kzMistDensity: { value: FOG.mistDensity },
  kzMistHeight: { value: FOG.mistHeight },
  kzWaterCount: { value: 0 },
  kzWaterRect: { value: Array.from({ length: FOG.maxWaters }, () => new THREE.Vector4()) }, // minX, minZ, maxX, maxZ (three)
  kzWaterY: { value: new Float32Array(FOG.maxWaters) },
  kzWaterMist: { value: new Float32Array(FOG.maxWaters) },
  kzFogOn: { value: 1 },
  kzProbeAMin: { value: new THREE.Vector3(-1e4, -1e4, -1e4) },
  kzProbeAMax: { value: new THREE.Vector3(1e4, 1e4, 1e4) },
  kzProbeACenter: { value: new THREE.Vector3() },
  kzProbeBMin: { value: new THREE.Vector3(-1e4, -1e4, -1e4) },
  kzProbeBMax: { value: new THREE.Vector3(1e4, 1e4, 1e4) },
  kzProbeBCenter: { value: new THREE.Vector3() },
  kzProbeBlend: { value: 0 },
  kzEnvB: { value: null },
  kzProbeIntensity: { value: 1 },
  kzTime: { value: 0 },
};
KZS.time = KZ.kzTime; // the material kit's animation clock is the runtime clock

const N = FOG.maxWaters;
export const FOG_PARS = /* glsl */ `
uniform vec3 kzFogColor; uniform float kzFogDensity; uniform vec3 kzMistColor; uniform float kzMistDensity; uniform float kzMistHeight;
uniform int kzWaterCount; uniform vec4 kzWaterRect[${N}]; uniform float kzWaterY[${N}]; uniform float kzWaterMist[${N}]; uniform float kzFogOn;
varying vec3 kzWorldPos;
float kzInRect(vec2 p, vec4 r) {
  vec2 a = smoothstep(r.xy - 0.75, r.xy + 0.75, p) * (1.0 - smoothstep(r.zw - 0.75, r.zw + 0.75, p));
  return a.x * a.y;
}
// returns vec4(fog colour * amount, amount): base exponential haze + analytic exponential mist layer above each water
vec4 kzFogTerms(vec3 wp) {
  vec3 ro = cameraPosition;
  float dist = length(wp - ro);
  float base = 1.0 - exp(-kzFogDensity * dist);
  float od = 0.0;
  float H = kzMistHeight;
  for (int i = 0; i < ${N}; i++) {
    if (i >= kzWaterCount) break;
    // water: mist where the ray starts or ends over it; fx patches (negative amount): only where the ray ends
    float m = kzWaterMist[i];
    float w = m < 0.0 ? kzInRect(wp.xz, kzWaterRect[i]) : 0.5 * (kzInRect(wp.xz, kzWaterRect[i]) + kzInRect(ro.xz, kzWaterRect[i]));
    if (w <= 0.0) continue;
    float y0 = kzWaterY[i];
    float ya = max(ro.y - y0, 0.0), yb = max(wp.y - y0, 0.0), dy = yb - ya;
    float f = abs(dy) < 1e-3 ? exp(-ya / H) : H * (exp(-ya / H) - exp(-yb / H)) / dy;
    od += abs(m) * w * (m < 0.0 ? min(dist, 4.0) : dist) * f; // a patch holds at most ~4 m of the ray
  }
  float mist = 1.0 - exp(-kzMistDensity * od);
  vec3 c = kzFogColor * base;
  float a = base;
  c = c * (1.0 - mist) + kzMistColor * mist;
  a = a + mist - a * mist;
  return vec4(c, a) * kzFogOn;
}
`;
export const WORLDPOS_VERT_PARS = 'varying vec3 kzWorldPos;\n';
export const WORLDPOS_VERT = /* glsl */ `
  {
    vec4 kzwp = vec4(transformed, 1.0);
    #ifdef USE_BATCHING
      kzwp = batchingMatrix * kzwp;
    #endif
    #ifdef USE_INSTANCING
      kzwp = instanceMatrix * kzwp;
    #endif
    kzWorldPos = (modelMatrix * kzwp).xyz;
  }
`;

const PROBE_PARS = /* glsl */ `
uniform vec3 kzProbeAMin; uniform vec3 kzProbeAMax; uniform vec3 kzProbeACenter;
uniform vec3 kzProbeBMin; uniform vec3 kzProbeBMax; uniform vec3 kzProbeBCenter;
uniform float kzProbeBlend; uniform sampler2D kzEnvB; uniform float kzProbeIntensity;
// parallax-corrected (box-projected) lookup direction; falls back to the raw direction outside the box
vec3 kzBoxProject(vec3 d, vec3 p, vec3 bmin, vec3 bmax, vec3 c) {
  vec3 ins = step(bmin, p) * step(p, bmax);
  if (ins.x * ins.y * ins.z < 0.5) return d;
  vec3 t1 = (bmax - p) / d, t2 = (bmin - p) / d;
  vec3 tf = max(t1, t2);
  float t = min(min(tf.x, tf.y), tf.z);
  return normalize(p + d * t - c);
}
`;

function patchedEnvChunk() {
  const src = THREE.ShaderChunk.envmap_physical_pars_fragment;
  const needle = 'vec4 envMapColor = textureCubeUV( envMap, envMapRotation * reflectVec, roughness );';
  const i = src.indexOf(needle);
  if (i < 0) throw new Error('three envmap chunk changed: probe patch needle not found');
  const rep = `vec3 kzDA = kzBoxProject( reflectVec, kzWorldPos, kzProbeAMin, kzProbeAMax, kzProbeACenter );
			vec3 kzDB = kzBoxProject( reflectVec, kzWorldPos, kzProbeBMin, kzProbeBMax, kzProbeBCenter );
			vec4 envMapColor = mix( textureCubeUV( envMap, envMapRotation * kzDA, roughness ), textureCubeUV( kzEnvB, envMapRotation * kzDB, roughness ), kzProbeBlend ) * kzProbeIntensity;`;
  return src.slice(0, i) + rep + src.slice(i + needle.length);
}
function patchedLightsMapsChunk(rgbm) {
  let src = THREE.ShaderChunk.lights_fragment_maps;
  const lmNeedle = 'vec3 lightMapIrradiance = lightMapTexel.rgb * lightMapIntensity;';
  if (!src.includes(lmNeedle)) throw new Error('three lights_fragment_maps changed: lightmap needle not found');
  if (rgbm) src = src.replace(lmNeedle, 'vec3 lightMapIrradiance = KZ_RGBM_RANGE * pow( lightMapTexel.rgb * lightMapTexel.a, vec3( KZ_RGBM_GAMMA ) ) * lightMapIntensity;');
  // baked lightmaps already contain the diffuse indirect light: drop probe irradiance where a lightmap exists
  const irr = 'iblIrradiance += getIBLIrradiance( geometryNormal );';
  if (!src.includes(irr)) throw new Error('three lights_fragment_maps changed: irradiance needle not found');
  src = src.replace(irr, '#ifndef USE_LIGHTMAP\n\t\t\t' + irr + '\n\t\t\t#endif');
  return src;
}
let ENV_CHUNK = null;
const SPEC_ONLY = /* glsl */ `
#if defined( USE_LIGHTMAP ) || defined( KZ_SPEC_ONLY )
void RE_Direct_KzSpec( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
  float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
  // the pool lights are points standing in for lamps of some size: widen the lobe (no pin-point sparkle on wet rock)
  PhysicalMaterial m = material;
  m.roughness = max( m.roughness, 0.15 );
  reflectedLight.directSpecular += dotNL * directLight.color * BRDF_GGX( directLight.direction, geometryViewDir, geometryNormal, m ) * m.multiScatteringCompensation;
}
#endif
`;
const GREY = (() => { try { const v = new URLSearchParams(location.search).get('albedo'); return v == null ? null : Number(v); } catch { return null; } })();

// Patch any built-in material (Standard/Physical/Basic/Lambert...) with fog + probes (+ RGBM decode).
export function patchMaterial(mat, { rgbm = null } = {}) {
  if (mat.userData.kzPatched) return mat;
  mat.userData.kzPatched = true;
  ENV_CHUNK ??= patchedEnvChunk();
  const key = `kz6|${rgbm ? `rgbm${rgbm.range}_${rgbm.gamma}` : ''}`;
  mat.customProgramCacheKey = () => key;
  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, KZ);
    shader.vertexShader = WORLDPOS_VERT_PARS + shader.vertexShader.replace('#include <project_vertex>', '#include <project_vertex>\n' + WORLDPOS_VERT);
    let fs = shader.fragmentShader;
    fs = FOG_PARS + PROBE_PARS + fs;
    if (rgbm) fs = `#define KZ_RGBM_RANGE ${rgbm.range.toFixed(4)}\n#define KZ_RGBM_GAMMA ${rgbm.gamma.toFixed(4)}\n` + fs;
    fs = fs.replace('#include <envmap_physical_pars_fragment>', ENV_CHUNK);
    fs = fs.replace('#include <lights_fragment_maps>', patchedLightsMapsChunk(!!rgbm));
    // lightmapped surfaces already hold the diffuse of every baked light: the light pool adds only their specular there
    // (wet basalt, lacquer and water films read through lamp highlights); unbaked meshes get the full light
    fs = fs.replace('#include <lights_physical_pars_fragment>', '#include <lights_physical_pars_fragment>\n' + SPEC_ONLY);
    fs = fs.replace('#include <lights_fragment_begin>', '#ifdef KZ_NO_DIRECT\n#undef RE_Direct\n#elif defined( USE_LIGHTMAP ) || defined( KZ_SPEC_ONLY )\n#undef RE_Direct\n#define RE_Direct RE_Direct_KzSpec\n#endif\n#include <lights_fragment_begin>');
    // fog in linear HDR, before tone mapping
    fs = fs.replace('#include <tonemapping_fragment>', '{ vec4 kzF = kzFogTerms( kzWorldPos ); gl_FragColor.rgb = min( gl_FragColor.rgb, vec3( 4.0 ) ) * ( 1.0 - kzF.a ) + kzF.rgb; }\n#include <tonemapping_fragment>');
    shader.fragmentShader = fs;
  };
  return mat;
}

// ---- stub probe environment: warm floor, dark rock vault, a soft lantern band ----
export function makeStubEnvironment(renderer) {
  const scene = new THREE.Scene();
  const geo = new THREE.SphereGeometry(10, 48, 24);
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false,
    vertexShader: 'varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
    fragmentShader: `varying vec3 vD; void main(){
      float y = vD.y;
      vec3 floorC = vec3(0.10, 0.075, 0.055);
      vec3 vault = vec3(0.025, 0.022, 0.02);
      vec3 c = mix(floorC, vault, smoothstep(-0.25, 0.6, y));
      float band = exp(-pow((y - 0.18) / 0.07, 2.0));
      float lanterns = pow(max(0.0, sin(atan(vD.z, vD.x) * 6.0)), 24.0);
      c += vec3(1.0, 0.6, 0.3) * band * (0.08 + 1.6 * lanterns);
      c += vec3(0.05, 0.16, 0.15) * smoothstep(-0.2, -0.9, y);
      gl_FragColor = vec4(c, 1.0);
    }`,
  });
  scene.add(new THREE.Mesh(geo, mat));
  const pmrem = new THREE.PMREMGenerator(renderer);
  const rt = pmrem.fromScene(scene, 0, 0.1, 100, { size: 256 }); // same size as real probes -> shared shader defines
  pmrem.dispose(); geo.dispose(); mat.dispose();
  return rt.texture;
}

// ---- library ----
export class MaterialLibrary {
  constructor(manifest, textures, env, tier = 'low') {
    this.tier = tier;
    this.def = manifest.materials;
    this.textures = textures; // id -> THREE.Texture
    this.env = env;
    this.cache = new Map();
  }
  get(name, { lightMap = null, lightMapInfo = null, side = THREE.FrontSide, flow = false } = {}) {
    const key = `${name}|${lightMapInfo?.id ?? ''}|${side}|${flow}`;
    let m = this.cache.get(key);
    if (m) return m;
    const d = this.def[name];
    if (!d) throw new Error(`material "${name}" is not in the manifest material library`);
    if (d.type === 'kz') {
      const rgbm = lightMap && lightMapInfo?.encoding === 'rgbm' ? { range: lightMapInfo.range, gamma: lightMapInfo.gamma } : null;
      const prepare = (mm) => {
        if (lightMap && d.lightmap !== false) { mm.lightMap = lightMap; mm.lightMap.channel = 1; mm.lightMapIntensity = lightMapInfo.intensity ?? LIGHTMAP_INTENSITY; }
        if (this.env) { mm.envMap = this.env; }
        patchMaterial(mm, { rgbm });
      };
      if (GREY != null) { // ?albedo=0.18: lighting check against a Cycles grey override (contract §10)
        m = new THREE.MeshStandardMaterial({ name, roughness: 1, metalness: 0, side });
        m.color.setRGB(GREY, GREY, GREY, THREE.LinearSRGBColorSpace); prepare(m);
      } else ({ mat: m } = makeKzMaterial(name, d, (id, cs) => this.tex(id, cs), this.tier, side, prepare));
      addFlow(m, d.id, flow, KZ.kzTime);
      m.userData.kzId = d.id;
      this.cache.set(key, m);
      return m;
    }
    m = new THREE.MeshStandardMaterial({
      name, color: new THREE.Color().setRGB(...(d.color ?? [1, 1, 1]), THREE.SRGBColorSpace),
      roughness: d.roughness ?? 0.8, metalness: d.metalness ?? 0, side,
    });
    if (d.baseColorTexture) m.map = this.tex(d.baseColorTexture, THREE.SRGBColorSpace);
    if (d.normalTexture) m.normalMap = this.tex(d.normalTexture, THREE.NoColorSpace);
    if (d.ormTexture) { const t = this.tex(d.ormTexture, THREE.NoColorSpace); m.aoMap = t; m.roughnessMap = t; m.metalnessMap = t; }
    if (d.emissive) { m.emissive.setRGB(...d.emissive, THREE.SRGBColorSpace); m.emissiveIntensity = d.emissiveIntensity ?? 1; }
    if (lightMap && d.lightmap !== false) {
      m.lightMap = lightMap;
      m.lightMap.channel = 1;
      m.lightMapIntensity = lightMapInfo.intensity ?? LIGHTMAP_INTENSITY;
    } else if (d.lightmap !== false && !d.emissive) {
      // unbaked surface: dim ambient stand-in so it is not black
      m.emissive.setRGB(0.02, 0.018, 0.016); m.emissiveIntensity = 1;
    }
    if (this.env && !d.emissive) { m.envMap = this.env; m.envMapIntensity = 1; }
    patchMaterial(m, { rgbm: lightMap && lightMapInfo?.encoding === 'rgbm' ? { range: lightMapInfo.range, gamma: lightMapInfo.gamma } : null });
    this.cache.set(key, m);
    return m;
  }
  tex(id, colorSpace) {
    const t = this.textures[id];
    if (!t) throw new Error(`texture "${id}" missing from manifest.textures`);
    t.colorSpace = colorSpace;
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.anisotropy = 4;
    return t;
  }
}
