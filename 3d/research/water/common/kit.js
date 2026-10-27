// Shared helpers for the Kazan-yu water prototypes.
// three.js is the pinned copy the runtime uses (web/node_modules/three, r186 / 0.186.1).
// Everything here is procedural: no external textures are loaded.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
export { mergeVertices };

export const params = new URLSearchParams(location.search);

// ---------------------------------------------------------------- GLSL chunks
export const GLSL_COMMON = /* glsl */`
uniform float uTime;
uniform vec3  uFogColor;
uniform vec4  uFog;        // x: layer base y, y: layer density, z: layer height scale H, w: distance density
uniform vec4  uFogGrad;    // z0, z1, base drop over that z range
uniform sampler2D tNoise;  // R fbm, G worley F1, B worley lace (F2-F1), A fbm2  (all tileable)

uniform sampler3D tNoise3; // 64^3 tileable: R fbm, G fbm (offset), B turbulence |n|, A worley F1
uniform sampler2D tScene;  // High tier: opaque scene colour (rgb) + view depth (a), half res
uniform vec2  uSceneInv;   // 1 / full-res target size (for gl_FragCoord -> uv)
uniform float uSceneOn;    // 1 when tScene is valid for this pass
uniform vec3  uCamFwd;     // main camera forward (for view depth of a fragment)
uniform vec4  uLPos[8];    // lights for lit particles / sheets: xyz, radius-ish falloff scale
uniform vec4  uLCol[8];    // rgb * intensity
uniform vec3  uAmb;        // ambient for lit particles (teal bounce from the water)

float hash11(float p){ p = fract(p*.1031); p *= p+33.33; p *= p+p; return fract(p); }
vec2  hash21(float p){ vec3 p3 = fract(vec3(p)*vec3(.1031,.1030,.0973)); p3 += dot(p3,p3.yzx+33.33); return fract((p3.xx+p3.yz)*p3.zy); }
vec3  hash31(float p){ vec3 p3 = fract(vec3(p)*vec3(.1031,.1030,.0973)); p3 += dot(p3,p3.yzx+33.33); return fract((p3.xxy+p3.yzz)*p3.zyx); }

// Analytic height fog: a dense layer that hugs the water (0..0.5 m) plus thin distance haze.
// Integrated along the view ray (I. Quilez, "better fog"), with one noise tap so it drifts.
float fogAmount(vec3 wpos){
  vec3 ro = cameraPosition;
  float dist = length(wpos - ro);
  // layer base can slope along z (rivers that drop): base = uFog.x + uFogGrad.z*clamp((z-z0)/(z1-z0))
  float baseA = uFog.x + uFogGrad.z*clamp((ro.z-uFogGrad.x)/(uFogGrad.y-uFogGrad.x), 0.0, 1.0);
  float baseB = uFog.x + uFogGrad.z*clamp((wpos.z-uFogGrad.x)/(uFogGrad.y-uFogGrad.x), 0.0, 1.0);
  // density a*exp(-max(h,0)/H): exact integral for a straight ray with both ends clamped to the layer floor
  float H = uFog.z;
  float yA = max(ro.y - baseA, 0.0), yB = max(wpos.y - baseB, 0.0);
  float dy = yB - yA;
  float eA = exp(-yA/H), eB = exp(-yB/H);
  float layer = uFog.y*dist*(abs(dy) < 1e-3 ? eA : H*(eA - eB)/dy);
  float drift = texture(tNoise, wpos.xz*0.045 + vec2(uTime*0.011, uTime*0.006)).r;
  layer *= 0.35 + 1.3*drift;
  return clamp(1.0 - exp(-(layer + dist*uFog.w)), 0.0, 1.0);
}
// ---- scene-texture helpers (refraction, depth-softened particles, thickness)
float viewDepth(vec3 wpos){ return dot(wpos - cameraPosition, uCamFwd); }
// light scattered by droplets / mist at p towards the eye: Henyey-Greenstein forward lobe + isotropic part
vec3 litScatter(vec3 p, vec3 V, float g, float iso){
  vec3 s = uAmb;
  for (int i = 0; i < 8; i++){
    vec3 L = uLPos[i].xyz - p; float d2 = dot(L, L) + 0.3; vec3 Ld = L*inversesqrt(d2);
    float c = dot(-Ld, -V);                  // angle between light->particle and particle->eye directions
    float hg = (1.0 - g*g)/pow(1.0 + g*g - 2.0*g*c, 1.5);
    s += uLCol[i].rgb*mix(hg, 1.0, iso)/(d2*uLPos[i].w + 1.0);
  }
  return s;
}
float noise3(vec3 p){ return texture(tNoise3, p).r; }

vec3 applyFog(vec3 col, vec3 wpos){ return mix(col, uFogColor, fogAmount(wpos)); }
// premultiplied-alpha variant for blended surfaces
vec4 applyFogPM(vec4 c, vec3 wpos){ float f = fogAmount(wpos); return vec4(mix(c.rgb, uFogColor*c.a, f), c.a); }
`;

// fragment-only helpers (gl_FragCoord): include after GLSL_COMMON in fragment shaders
export const GLSL_FRAG = /* glsl */`
vec2  screenUv(){ return gl_FragCoord.xy*uSceneInv; }
// opaque depth behind this fragment minus the fragment depth (metres along the view axis); huge when unknown
float sceneGap(vec3 wpos){ if (uSceneOn < 0.5) return 1e4; return texture(tScene, screenUv()).a - viewDepth(wpos); }
float softFade(vec3 wpos, float soft){ return clamp(sceneGap(wpos)/soft, 0.0, 1.0); }
vec3  sceneColor(vec2 offs){ return texture(tScene, clamp(screenUv() + offs, vec2(0.001), vec2(0.999))).rgb; }
float sceneDepthAt(vec2 offs){ return texture(tScene, clamp(screenUv() + offs, vec2(0.001), vec2(0.999))).a; }
`;

// ---------------------------------------------------------------- procedural texture bake (GPU, once)
const BAKE_VS = `precision highp float; in vec3 position; out vec2 vUv; void main(){ vUv = position.xy*0.5+0.5; gl_Position = vec4(position.xy,0.,1.); }`;
const BAKE_NOISE_FS = /* glsl */`
precision highp float;
in vec2 vUv; out vec4 o;
vec2 g2(vec2 p){ p = vec2(dot(p,vec2(127.1,311.7)), dot(p,vec2(269.5,183.3))); return -1.+2.*fract(sin(p)*43758.5453); }
float gnoise(vec2 p, float P){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f*f*f*(f*(f*6.-15.)+10.);
  float a = dot(g2(mod(i,P)), f), b = dot(g2(mod(i+vec2(1,0),P)), f-vec2(1,0));
  float c = dot(g2(mod(i+vec2(0,1),P)), f-vec2(0,1)), d = dot(g2(mod(i+vec2(1,1),P)), f-vec2(1,1));
  return mix(mix(a,b,u.x), mix(c,d,u.x), u.y);
}
float fbm(vec2 uv, float P, int oct){ float s=0., a=.5, n=0.; for(int k=0;k<8;k++){ if(k>=oct) break; s += a*gnoise(uv*P, P); n+=a; P*=2.; a*=.5; uv=uv; } return s/n; }
vec2 h2(vec2 p){ return fract(sin(vec2(dot(p,vec2(127.1,311.7)),dot(p,vec2(269.5,183.3))))*43758.5453); }
vec2 worley(vec2 uv, float P){
  vec2 p = uv*P; vec2 i = floor(p), f = fract(p); float F1=8., F2=8.;
  for(int y=-1;y<=1;y++) for(int x=-1;x<=1;x++){
    vec2 o2 = vec2(x,y); vec2 r = o2 + h2(mod(i+o2,P)) - f; float d = dot(r,r);
    if(d<F1){F2=F1;F1=d;} else if(d<F2){F2=d;}
  }
  return sqrt(vec2(F1,F2));
}
void main(){
  float n1 = fbm(vUv, 4., 7)*0.5+0.5;
  vec2  w  = worley(vUv, 10.);
  float lace = clamp((w.y-w.x)*2.2, 0., 1.);          // thin bright cell borders -> foam lace
  vec2  w2 = worley(vUv + 0.13*vec2(fbm(vUv,4.,4),fbm(vUv+.5,4.,4)), 16.);
  float lace2 = clamp((w2.y-w2.x)*2.6, 0., 1.);
  float n2 = fbm(vUv+vec2(.37,.71), 8., 6)*0.5+0.5;
  o = vec4(n1, w.x, min(lace, lace2*1.2+0.15), n2);
}`;
// Height field for the ripple normal map: anisotropic-free sum of fbm + worley bumps, tileable.
const BAKE_HEIGHT_FS = /* glsl */`
precision highp float;
in vec2 vUv; out vec4 o; uniform sampler2D tN;
void main(){ vec4 n = texture(tN, vUv); float h = n.r*0.55 + n.a*0.35 + (1.-n.g)*0.25; o = vec4(h,h,h,1.); }`;
const BAKE_NORMAL_FS = /* glsl */`
precision highp float;
in vec2 vUv; out vec4 o; uniform sampler2D tH; uniform float uStrength; uniform vec2 uTexel;
void main(){
  float hl = texture(tH, vUv-vec2(uTexel.x,0)).r, hr = texture(tH, vUv+vec2(uTexel.x,0)).r;
  float hd = texture(tH, vUv-vec2(0,uTexel.y)).r, hu = texture(tH, vUv+vec2(0,uTexel.y)).r;
  vec3 n = normalize(vec3((hl-hr)*uStrength, (hd-hu)*uStrength, 1.));
  o = vec4(n.xy*0.5+0.5, texture(tH,vUv).r, 1.);
}`;
// Soft, lumpy puff for steam / mist sprites (alpha in A).
const BAKE_PUFF_FS = /* glsl */`
precision highp float;
in vec2 vUv; out vec4 o; uniform sampler2D tN;
void main(){
  vec2 p = vUv*2.-1.; float r = length(p);
  float n = texture(tN, vUv*0.5+vec2(.21,.37)).r*0.6 + texture(tN, vUv*1.3).a*0.4;
  float a = smoothstep(1.0, 0.15, r + (n-0.5)*0.7);
  a *= a;
  o = vec4(vec3(0.85+0.15*n), a);
}`;

function bakePass(renderer, fs, size, uniforms = {}, mips = true) {
  const rt = new THREE.WebGLRenderTarget(size, size, {
    type: THREE.UnsignedByteType, format: THREE.RGBAFormat,
    wrapS: THREE.RepeatWrapping, wrapT: THREE.RepeatWrapping,
    minFilter: mips ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter, magFilter: THREE.LinearFilter,
    generateMipmaps: mips, depthBuffer: false,
  });
  rt.texture.anisotropy = 4;
  const mat = new THREE.RawShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: BAKE_VS, fragmentShader: fs, uniforms, depthTest: false, depthWrite: false });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
  const cam = new THREE.Camera();
  const prev = renderer.getRenderTarget();
  renderer.setRenderTarget(rt); renderer.render(quad, cam); renderer.setRenderTarget(prev);
  mat.dispose(); quad.geometry.dispose();
  return rt;
}

const BAKE3_FS = /* glsl */`
precision highp float; precision highp sampler3D;
in vec2 vUv; out vec4 o; uniform float uZ;
vec3 g3(vec3 p){ p = vec3(dot(p,vec3(127.1,311.7,74.7)), dot(p,vec3(269.5,183.3,246.1)), dot(p,vec3(113.5,271.9,124.6))); return -1.0 + 2.0*fract(sin(p)*43758.5453); }
float gn(vec3 p, float P){
  vec3 i = floor(p), f = fract(p); vec3 u = f*f*f*(f*(f*6.-15.)+10.);
  float n000 = dot(g3(mod(i,P)), f), n100 = dot(g3(mod(i+vec3(1,0,0),P)), f-vec3(1,0,0));
  float n010 = dot(g3(mod(i+vec3(0,1,0),P)), f-vec3(0,1,0)), n110 = dot(g3(mod(i+vec3(1,1,0),P)), f-vec3(1,1,0));
  float n001 = dot(g3(mod(i+vec3(0,0,1),P)), f-vec3(0,0,1)), n101 = dot(g3(mod(i+vec3(1,0,1),P)), f-vec3(1,0,1));
  float n011 = dot(g3(mod(i+vec3(0,1,1),P)), f-vec3(0,1,1)), n111 = dot(g3(mod(i+vec3(1,1,1),P)), f-vec3(1,1,1));
  return mix(mix(mix(n000,n100,u.x), mix(n010,n110,u.x), u.y), mix(mix(n001,n101,u.x), mix(n011,n111,u.x), u.y), u.z);
}
vec3 h3(vec3 p){ return fract(sin(vec3(dot(p,vec3(127.1,311.7,74.7)), dot(p,vec3(269.5,183.3,246.1)), dot(p,vec3(113.5,271.9,124.6))))*43758.5453); }
float worley(vec3 p, float P){ vec3 i = floor(p), f = fract(p); float F = 8.0;
  for (int z=-1;z<=1;z++) for (int y=-1;y<=1;y++) for (int x=-1;x<=1;x++){ vec3 o3 = vec3(x,y,z); vec3 r = o3 + h3(mod(i+o3,P)) - f; F = min(F, dot(r,r)); }
  return sqrt(F); }
void main(){
  vec3 p = vec3(vUv, uZ);
  float a = 0.0, b = 0.0, t = 0.0, amp = 0.5, P = 4.0, nrm = 0.0;
  for (int k = 0; k < 4; k++){ a += amp*gn(p*P, P); b += amp*gn(p*P + 17.0, P); t += amp*abs(gn(p*P + 31.0, P)); nrm += amp; amp *= 0.5; P *= 2.0; }
  o = vec4(a/nrm*0.5 + 0.5, b/nrm*0.5 + 0.5, t/nrm*1.6, worley(p*8.0, 8.0));
}`;
export function bakeNoise3(renderer, N = 64) {
  const rt = new THREE.WebGL3DRenderTarget(N, N, N, { type: THREE.UnsignedByteType, format: THREE.RGBAFormat, depthBuffer: false });
  const t = rt.texture; t.wrapS = t.wrapT = t.wrapR = THREE.RepeatWrapping; t.minFilter = t.magFilter = THREE.LinearFilter; t.generateMipmaps = false;
  const mat = new THREE.RawShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: BAKE_VS, fragmentShader: BAKE3_FS, uniforms: { uZ: { value: 0 } }, depthTest: false, depthWrite: false });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat); const cam = new THREE.Camera();
  for (let z = 0; z < N; z++) { mat.uniforms.uZ.value = (z + 0.5) / N; renderer.setRenderTarget(rt, z); renderer.render(quad, cam); }
  renderer.setRenderTarget(null); mat.dispose(); quad.geometry.dispose();
  return t;
}

export function bakeTextures(renderer) {
  const noise = bakePass(renderer, BAKE_NOISE_FS, 512);
  const height = bakePass(renderer, BAKE_HEIGHT_FS, 512, { tN: { value: noise.texture } }, false);
  const normal = bakePass(renderer, BAKE_NORMAL_FS, 512, { tH: { value: height.texture }, uStrength: { value: 6.0 }, uTexel: { value: new THREE.Vector2(1 / 512, 1 / 512) } });
  const puff = bakePass(renderer, BAKE_PUFF_FS, 128, { tN: { value: noise.texture } });
  puff.texture.wrapS = puff.texture.wrapT = THREE.ClampToEdgeWrapping;
  height.dispose();
  return { noise: noise.texture, normal: normal.texture, puff: puff.texture, bytes: (512 * 512 * 4 * 2 * 4 / 3) + 128 * 128 * 4 * 4 / 3 };
}

// ---------------------------------------------------------------- "baked" rock material
// Stands in for a lightmapped surface: albedo * baked irradiance (vertex colour) + height fog.
export function rockMaterial(shared, opts = {}) {
  return new THREE.ShaderMaterial({
    uniforms: { ...shared, uTint: { value: new THREE.Color(opts.tint ?? 0x2a2624) }, uWet: { value: opts.wet ?? 0.0 }, uScale: { value: opts.scale ?? 0.6 } },
    vertexShader: /* glsl */`
      attribute vec3 color; varying vec3 vCol; varying vec3 vW; varying vec3 vN;
      void main(){ vec4 w = modelMatrix*vec4(position,1.); vW = w.xyz; vCol = color; vN = normalize(mat3(modelMatrix)*normal); gl_Position = projectionMatrix*viewMatrix*w; }`,
    fragmentShader: GLSL_COMMON + /* glsl */`
      uniform vec3 uTint; uniform float uWet; uniform float uScale; varying vec3 vCol; varying vec3 vW; varying vec3 vN;
      void main(){
        vec3 an = abs(vN);
        vec2 uv = an.y > max(an.x,an.z) ? vW.xz : (an.x > an.z ? vW.zy : vW.xy);
        vec4 n = texture(tNoise, uv*uScale*0.25);
        float grain = texture(tNoise, uv*uScale*1.7).a;
        vec3 alb = uTint * (0.55 + 0.9*n.r) * (0.8+0.4*grain);
        vec3 col = alb * vCol;
        // wet sheen: a cheap glint so the basalt reads wet near water
        vec3 v = normalize(cameraPosition - vW);
        float sheen = pow(1.0 - max(dot(v, normalize(vN)), 0.0), 4.0) * uWet;
        col += sheen * vCol * 0.6;
        col = applyFog(col, vW);
        gl_FragColor = vec4(col, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
}

// Bake a fake lightmap into vertex colours: ambient + point lights with distance falloff + AO-ish term.
export function bakeVertexLight(geo, lights, ambient = new THREE.Color(0.02, 0.025, 0.03), aoFn = null) {
  geo.computeVertexNormals();
  const pos = geo.attributes.position, nor = geo.attributes.normal;
  const col = new Float32Array(pos.count * 3);
  const p = new THREE.Vector3(), n = new THREE.Vector3(), L = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    p.fromBufferAttribute(pos, i); n.fromBufferAttribute(nor, i);
    let r = ambient.r, g = ambient.g, b = ambient.b;
    for (const l of lights) {
      L.copy(l.pos).sub(p); const d2 = Math.max(L.lengthSq(), 0.25); L.normalize();
      const ndl = l.wrap ? Math.max((n.dot(L) + l.wrap) / (1 + l.wrap), 0) : Math.max(n.dot(L), 0);
      const f = ndl * l.intensity / d2;
      r += l.color.r * f; g += l.color.g * f; b += l.color.b * f;
    }
    const ao = aoFn ? aoFn(p, n) : 1;
    col[i * 3] = r * ao; col[i * 3 + 1] = g * ao; col[i * 3 + 2] = b * ao;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return geo;
}

// Value noise for CPU-side displacement of rock meshes.
export function makeNoise3(seed = 1) {
  const perm = new Uint8Array(512); const rnd = mulberry(seed);
  const p = [...Array(256).keys()]; for (let i = 255; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [p[i], p[j]] = [p[j], p[i]]; }
  for (let i = 0; i < 512; i++) perm[i] = p[i & 255];
  const val = new Float32Array(256); for (let i = 0; i < 256; i++) val[i] = rnd() * 2 - 1;
  const lerp = (a, b, t) => a + (b - a) * t, fade = t => t * t * (3 - 2 * t);
  const n3 = (x, y, z) => {
    const X = Math.floor(x), Y = Math.floor(y), Z = Math.floor(z); const fx = fade(x - X), fy = fade(y - Y), fz = fade(z - Z);
    const h = (i, j, k) => val[perm[(perm[(perm[(X + i) & 255] + Y + j) & 255] + Z + k) & 255]];
    return lerp(lerp(lerp(h(0, 0, 0), h(1, 0, 0), fx), lerp(h(0, 1, 0), h(1, 1, 0), fx), fy), lerp(lerp(h(0, 0, 1), h(1, 0, 1), fx), lerp(h(0, 1, 1), h(1, 1, 1), fx), fy), fz);
  };
  return (x, y, z, oct = 4) => { let s = 0, a = 0.5, f = 1; for (let o = 0; o < oct; o++) { s += a * n3(x * f, y * f, z * f); a *= 0.5; f *= 2.03; } return s; };
}
export function mulberry(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

// Displace every vertex along its normal by fbm: turns primitives into lumpy basalt.
export function lumpify(geo, amp, freq, seed = 3, oct = 4) {
  const nz = makeNoise3(seed);
  geo.deleteAttribute('uv'); geo.deleteAttribute('normal'); geo = mergeVertices(geo); geo.computeVertexNormals();
  const pos = geo.attributes.position, nor = geo.attributes.normal;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    const d = nz(x * freq, y * freq, z * freq, oct) * amp;
    pos.setXYZ(i, x + nor.getX(i) * d, y + nor.getY(i) * d, z + nor.getZ(i) * d);
  }
  geo.computeVertexNormals();
  return geo;
}

// ---------------------------------------------------------------- app shell: renderer, HUD, tiers, bench
export function createApp({ title, cams, onTier, fog }) {
  const canvas = document.createElement('canvas'); document.body.appendChild(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: params.has('shot') });
  renderer.toneMapping = THREE.AgXToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.info.autoReset = false;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, 1, 0.05, 400);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;

  const tex = bakeTextures(renderer);
  const shared = {
    uTime: { value: 0 },
    uFogColor: { value: new THREE.Color(fog?.color ?? 0x8fb3b6) },
    uFog: { value: new THREE.Vector4(...(fog?.v ?? [0, 0.6, 0.35, 0.004])) },
    uFogGrad: { value: new THREE.Vector4(...(fog?.grad ?? [0, 1, 0, 0])) },
    tNoise: { value: tex.noise },
    tNoise3: { value: bakeNoise3(renderer) },
    tScene: { value: null }, uSceneInv: { value: new THREE.Vector2(1, 1) }, uSceneOn: { value: 0 }, uCamFwd: { value: new THREE.Vector3(0, 0, -1) },
    uLPos: { value: Array.from({ length: 8 }, () => new THREE.Vector4(0, -999, 0, 1)) },
    uLCol: { value: Array.from({ length: 8 }, () => new THREE.Vector4(0, 0, 0, 0)) },
    uAmb: { value: new THREE.Vector3(0.01, 0.02, 0.02) },
  };
  tex.bytes += 64 * 64 * 64 * 4;
  const dummy = new THREE.DataTexture(new Uint16Array(4), 1, 1, THREE.RGBAFormat, THREE.HalfFloatType); dummy.needsUpdate = true; shared.tScene.value = dummy;

  const state = {
    low: params.get('tier') === 'low', paused: params.has('freeze'), t: parseFloat(params.get('t') ?? '0'),
    camIndex: parseInt(params.get('cam') ?? '0', 10),
  };

  // HUD
  const hud = document.createElement('div'); hud.id = 'hud';
  hud.innerHTML = `<div class="ttl">${title}</div><div id="stats">…</div>
    <div class="row"><button id="bTier"></button><button id="bCam">camera</button><button id="bPause">pause</button><button id="bBench">bench</button></div>
    <div id="bench"></div>`;
  document.body.appendChild(hud);
  const style = document.createElement('style');
  style.textContent = `html,body{margin:0;height:100%;background:#05080a;overflow:hidden;font:12px/1.35 ui-monospace,Menlo,monospace;color:#d8eeee}
  canvas{display:block;width:100vw;height:100vh;touch-action:none}
  #hud{position:fixed;left:8px;top:8px;background:rgba(4,10,12,.62);padding:7px 9px;border-radius:8px;max-width:min(92vw,360px);backdrop-filter:blur(4px)}
  #hud .ttl{font-weight:700;color:#7fe6dc;margin-bottom:2px}
  #hud .row{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}
  #hud button{font:inherit;background:#123236;color:#d8eeee;border:1px solid #2f6a6c;border-radius:5px;padding:4px 8px}
  #hud button.on{background:#7a3d12;border-color:#d07a2e}
  #bench{white-space:pre;color:#ffd9a8;margin-top:4px}
  body.clean #hud{display:none}`;
  document.head.appendChild(style);
  if (params.has('clean')) document.body.classList.add('clean');
  const $ = id => hud.querySelector('#' + id);

  const setTier = low => {
    state.low = low;
    $('bTier').textContent = low ? 'Low tier: ON' : 'Low tier: off';
    $('bTier').classList.toggle('on', low);
    resize();
    onTier?.(low);
  };
  const setCam = i => {
    state.camIndex = (i + cams.length) % cams.length; const c = cams[state.camIndex];
    camera.position.set(...c.pos); controls.target.set(...c.target); camera.fov = c.fov ?? 55; camera.updateProjectionMatrix(); controls.update();
  };
  $('bTier').onclick = () => setTier(!state.low);
  $('bCam').onclick = () => setCam(state.camIndex + 1);
  $('bPause').onclick = () => { state.paused = !state.paused; $('bPause').classList.toggle('on', state.paused); };

  function resize() {
    const dpr = Math.min(window.devicePixelRatio, 2) * (state.low ? 0.75 : 1);
    renderer.setPixelRatio(dpr);
    renderer.setSize(window.innerWidth, window.innerHeight, false);
    camera.aspect = window.innerWidth / window.innerHeight; camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);

  // frame stats
  const ft = []; let last = performance.now(); let statsAt = 0; let frameCalls = 0, frameTris = 0;
  const app = {
    THREE, renderer, scene, camera, controls, shared, tex, state, params,
    update: null,            // (t, dt) => void, set by page
    preRender: null,         // () => void : extra passes (sims, reflections) counted in stats
    groups: {},              // name -> Object3D[] for the bench
    extraTexBytes: 0,
    start() {
      setTier(state.low); setCam(state.camIndex);
      for (const g of (params.get('hide') ?? '').split(',').filter(Boolean)) (app.groups[g] ?? []).forEach(o => o.visible = false);
      if (params.has('pos')) { camera.position.set(...params.get('pos').split(',').map(Number)); controls.target.set(...params.get('tgt').split(',').map(Number)); controls.update(); }
      requestAnimationFrame(loop);
    },
  };

  // ---- render pipeline
  // Low tier (direct): one pass to the screen, transparent effects use analytic fades.
  // High tier (scene texture): opaque layer 0 -> HDR target A (+depth), A -> half-res B (colour + linear view depth),
  // effects on layer 1 render into A sampling B (refraction, soft particles, thickness), A -> screen with AgX.
  const pipe = { w: 0, h: 0, A: null, B: null };
  const quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const copyMat = new THREE.ShaderMaterial({
    uniforms: { tColor: { value: null }, tDepth: { value: null }, uNear: { value: 0.05 }, uFar: { value: 400 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `#include <packing>
      uniform sampler2D tColor; uniform sampler2D tDepth; uniform float uNear; uniform float uFar; varying vec2 vUv;
      void main(){ float d = texture2D(tDepth, vUv).x; float vz = -perspectiveDepthToViewZ(d, uNear, uFar);
        gl_FragColor = vec4(texture2D(tColor, vUv).rgb, d >= 1.0 ? 1e4 : vz); }`,
    depthTest: false, depthWrite: false, toneMapped: false,
  });
  const outMat = new THREE.ShaderMaterial({
    uniforms: { tColor: { value: null } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `uniform sampler2D tColor; varying vec2 vUv; void main(){ gl_FragColor = vec4(texture2D(tColor, vUv).rgb, 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,
    depthTest: false, depthWrite: false,
  });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), copyMat); quad.frustumCulled = false;
  const quadScene = new THREE.Scene(); quadScene.add(quad);
  function ensurePipe(w, h) {
    if (pipe.w === w && pipe.h === h) return;
    pipe.A?.dispose(); pipe.B?.dispose(); pipe.w = w; pipe.h = h;
    pipe.A = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples: 0, depthBuffer: true });
    pipe.A.depthTexture = new THREE.DepthTexture(w, h); pipe.A.depthTexture.type = THREE.FloatType;
    pipe.B = new THREE.WebGLRenderTarget(Math.max(1, w >> 1), Math.max(1, h >> 1), { type: THREE.HalfFloatType, depthBuffer: false, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter });
  }
  const fwd = new THREE.Vector3();
  function renderPipeline(target) {
    camera.getWorldDirection(fwd); shared.uCamFwd.value.copy(fwd);
    app.preRender?.();
    const useScene = !state.low && app.sceneTexture;
    const size = target ? new THREE.Vector2(target.width, target.height) : renderer.getDrawingBufferSize(new THREE.Vector2());
    if (!useScene) {
      shared.uSceneOn.value = 0; camera.layers.enable(0); camera.layers.enable(1); camera.layers.enable(2);
      if (!app.sceneTexture) { renderer.setRenderTarget(target); renderer.render(scene, camera); return; }
      // Low tier: still one HDR pass + AgX at the end (no copy, no refraction). Tone-mapping each blended layer
      // separately lifts every faint mist particle and blows the result out, so blending must happen in linear HDR.
      ensurePipe(size.x, size.y);
      renderer.setRenderTarget(pipe.A); renderer.clear(); renderer.render(scene, camera);
      outMat.uniforms.tColor.value = pipe.A.texture; quad.material = outMat;
      renderer.setRenderTarget(target); renderer.render(quadScene, quadCam);
      return;
    }
    ensurePipe(size.x, size.y);
    shared.uSceneOn.value = 0;
    camera.layers.set(0);
    renderer.setRenderTarget(pipe.A); renderer.clear(); renderer.render(scene, camera);
    copyMat.uniforms.tColor.value = pipe.A.texture; copyMat.uniforms.tDepth.value = pipe.A.depthTexture;
    copyMat.uniforms.uNear.value = camera.near; copyMat.uniforms.uFar.value = camera.far;
    quad.material = copyMat; renderer.setRenderTarget(pipe.B); renderer.render(quadScene, quadCam);
    shared.tScene.value = pipe.B.texture; shared.uSceneInv.value.set(1 / size.x, 1 / size.y); shared.uSceneOn.value = 1;
    camera.layers.set(1); camera.layers.enable(2);
    const ac = renderer.autoClear; renderer.autoClear = false;
    const bg = scene.background; scene.background = null;
    renderer.setRenderTarget(pipe.A); renderer.render(scene, camera);
    renderer.autoClear = ac; scene.background = bg;
    shared.uSceneOn.value = 0;
    outMat.uniforms.tColor.value = pipe.A.texture; quad.material = outMat;
    renderer.setRenderTarget(target); renderer.render(quadScene, quadCam);
    camera.layers.enable(0); camera.layers.enable(1); camera.layers.enable(2);
  }
  app.renderPipeline = renderPipeline;
  // mark a mesh as a blended effect (layer 1): drawn after the scene-texture copy on High
  app.fx = (...meshes) => { for (const m of meshes) { m.layers.set(1); } camera.layers.enable(1); };
  // effects that should also show up in planar reflections (the reflection camera sees layers 0 and 2)
  app.fxReflected = (...meshes) => { for (const m of meshes) { m.layers.set(2); } camera.layers.enable(2); };
  // set the shared light list used by litScatter()
  app.setLights = (lights, amb) => {
    lights.slice(0, 8).forEach((l, i) => { shared.uLPos.value[i].set(l.pos.x, l.pos.y, l.pos.z, l.falloff ?? 1); shared.uLCol.value[i].set(l.color.r * l.i, l.color.g * l.i, l.color.b * l.i, 0); });
    if (amb) shared.uAmb.value.set(amb.r, amb.g, amb.b);
  };

  function renderFrame() {
    renderer.info.reset();
    renderPipeline(null);
    frameCalls = renderer.info.render.calls; frameTris = renderer.info.render.triangles;
  }

  function loop(now) {
    requestAnimationFrame(loop);
    const dt = Math.min((now - last) / 1000, 0.1); last = now;
    ft.push(dt * 1000); if (ft.length > 90) ft.shift();
    if (!state.paused) state.t += dt;
    shared.uTime.value = state.t;
    controls.update();
    app.update?.(state.t, state.paused ? 0 : dt);
    renderFrame();
    if (now - statsAt > 400) {
      statsAt = now;
      const avg = ft.reduce((a, b) => a + b, 0) / ft.length; const worst = Math.max(...ft);
      const w = renderer.domElement.width, h = renderer.domElement.height;
      $('stats').textContent = `${(1000 / avg).toFixed(0)} fps  ${avg.toFixed(2)} ms (worst ${worst.toFixed(1)})\n`
        + `calls ${frameCalls}  tris ${(frameTris / 1000).toFixed(1)}k  ${w}×${h}\n`
        + `tex ≈ ${((tex.bytes + app.extraTexBytes) / 1048576).toFixed(1)} MB  t=${state.t.toFixed(1)}s`;
      $('stats').style.whiteSpace = 'pre';
    }
  }

  // GPU bench without timer queries (EXT_disjoint_timer_query is not exposed here):
  // render N frames back-to-back into an offscreen target, then force a sync with a 1-pixel readPixels.
  // Reports ms per frame at a fixed resolution; isolates a group by hiding the others.
  app.bench = async function ({ w = 1600, h = 900, n = 40, groups = true } = {}) {
    const rt = new THREE.WebGLRenderTarget(w, h, { samples: 0, type: THREE.UnsignedByteType });
    const px = new Uint8Array(4);
    const prevPR = renderer.getPixelRatio(); const prevSize = renderer.getSize(new THREE.Vector2());
    const aspect = camera.aspect; camera.aspect = w / h; camera.updateProjectionMatrix();
    const sync = () => renderer.readRenderTargetPixels(rt, 0, 0, 1, 1, px);
    const run = () => {
      for (let i = 0; i < 3; i++) renderPipeline(rt); sync();
      const t0 = performance.now();
      for (let i = 0; i < n; i++) { shared.uTime.value += 1 / 60; app.update?.(shared.uTime.value, 1 / 60); renderPipeline(rt); }
      sync();
      return (performance.now() - t0) / n;
    };
    const res = { resolution: `${w}x${h}`, tier: state.low ? 'low' : 'high', pipeline: !app.sceneTexture ? 'direct' : (state.low ? 'hdr-single-pass' : 'scene-texture') };
    res.total = run();
    if (groups) {
      const all = Object.entries(app.groups);
      const saved = new Map(); all.forEach(([, objs]) => objs.forEach(o => saved.set(o, o.visible)));
      for (const [name, objs] of all) { objs.forEach(o => o.visible = false); res['without_' + name] = run(); objs.forEach(o => o.visible = saved.get(o)); }
      all.forEach(([name, objs]) => objs.forEach(o => o.visible = false));
      const savedPre = app.preRender; app.preRender = null; res.empty = run(); app.preRender = savedPre;
      all.forEach(([, objs]) => objs.forEach(o => o.visible = saved.get(o)));
      for (const [name] of all) res['cost_' + name] = Math.max(0, res.total - res['without_' + name]);
    }
    renderer.setRenderTarget(null); rt.dispose();
    camera.aspect = aspect; camera.updateProjectionMatrix(); renderer.setPixelRatio(prevPR); renderer.setSize(prevSize.x, prevSize.y, false);
    for (const k in res) if (typeof res[k] === 'number') res[k] = +res[k].toFixed(3);
    return res;
  };
  $('bBench').onclick = async () => {
    $('bench').textContent = 'running…';
    await new Promise(r => setTimeout(r, 50));
    const r = await app.bench();
    $('bench').textContent = Object.entries(r).map(([k, v]) => `${k}: ${v}`).join('\n');
  };
  window.__app = app;
  window.__stats = () => ({ calls: frameCalls, tris: frameTris, fpsMs: ft.reduce((a, b) => a + b, 0) / ft.length, texMB: (tex.bytes + app.extraTexBytes) / 1048576, w: renderer.domElement.width, h: renderer.domElement.height });
  return app;
}

// Instanced camera-facing quads for particles. Attribute aSeed per instance; motion is computed
// entirely in the vertex shader from (seed, time) so the CPU never touches the buffers.
export function instancedQuads(count) {
  const g = new THREE.InstancedBufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(new Float32Array([-0.5, -0.5, 0, 0.5, -0.5, 0, 0.5, 0.5, 0, -0.5, 0.5, 0]), 3));
  g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]), 2));
  g.setIndex([0, 1, 2, 0, 2, 3]);
  const seeds = new Float32Array(count); for (let i = 0; i < count; i++) seeds[i] = i;
  g.setAttribute('aSeed', new THREE.InstancedBufferAttribute(seeds, 1));
  g.instanceCount = count; g.userData.max = count;
  g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e4);
  return g;
}

export const BILLBOARD_GLSL = /* glsl */`
// camera-aligned quad corner offset in world space
vec3 billboard(vec2 corner, float size){
  vec3 right = vec3(viewMatrix[0][0], viewMatrix[1][0], viewMatrix[2][0]);
  vec3 up    = vec3(viewMatrix[0][1], viewMatrix[1][1], viewMatrix[2][1]);
  return (right*corner.x + up*corner.y)*size;
}
// streak quad: stretched along a world velocity, as seen from the camera
vec3 streak(vec2 corner, vec3 center, vec3 vel, float width, float len){
  vec3 toCam = normalize(cameraPosition - center);
  float vl = length(vel); vec3 dir = vl > 1e-4 ? vel/vl : vec3(0.0, 1.0, 0.0);
  vec3 side = cross(dir, toCam); float sl = length(side);
  side = sl > 1e-4 ? side/sl : vec3(1.0, 0.0, 0.0);
  return side*corner.x*width + dir*corner.y*len;
}
`;

// One-time reflection probe (stand-in for the baked Cycles cubemap in the real pipeline).
export function bakeProbe(renderer, scene, pos, size = 128, hide = []) {
  const rt = new THREE.WebGLCubeRenderTarget(size, { type: THREE.HalfFloatType, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter });
  const cc = new THREE.CubeCamera(0.1, 300, rt); cc.position.copy(pos);
  const vis = hide.map(o => o.visible); hide.forEach(o => o.visible = false);
  const tm = renderer.toneMapping; renderer.toneMapping = THREE.NoToneMapping;
  cc.update(renderer, scene);
  renderer.toneMapping = tm;
  hide.forEach((o, i) => o.visible = vis[i]);
  return rt.texture;
}

// Ping-pong GPU simulation on a small float texture. fs gets: tPrev, uTexel, uRes (+ your uniforms), writes `o`.
// Steps are fixed-size (call step() at a fixed rate); state persists between frames.
export function createSim(renderer, { w, h, fs, uniforms = {}, filter = THREE.LinearFilter, init = null }) {
  const opts = { type: THREE.HalfFloatType, format: THREE.RGBAFormat, minFilter: filter, magFilter: filter, depthBuffer: false, wrapS: THREE.ClampToEdgeWrapping, wrapT: THREE.ClampToEdgeWrapping };
  const rts = [new THREE.WebGLRenderTarget(w, h, opts), new THREE.WebGLRenderTarget(w, h, opts)];
  const mat = new THREE.RawShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { tPrev: { value: null }, uTexel: { value: new THREE.Vector2(1 / w, 1 / h) }, uRes: { value: new THREE.Vector2(w, h) }, ...uniforms },
    vertexShader: `precision highp float; in vec3 position; out vec2 vUv; void main(){ vUv = position.xy*0.5+0.5; gl_Position = vec4(position.xy,0.,1.); }`,
    fragmentShader: `precision highp float; precision highp sampler3D;\n` + fs, depthTest: false, depthWrite: false,
  });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat); const cam = new THREE.Camera();
  const sim = {
    w, h, mat, uniforms: mat.uniforms, bytes: w * h * 8 * 2,
    get texture() { return rts[0].texture; },
    step() { mat.uniforms.tPrev.value = rts[0].texture; const prev = renderer.getRenderTarget(); renderer.setRenderTarget(rts[1]); renderer.render(quad, cam); renderer.setRenderTarget(prev); rts.reverse(); },
    clear() { const prev = renderer.getRenderTarget(); for (const r of rts) { renderer.setRenderTarget(r); renderer.clear(); } renderer.setRenderTarget(prev); },
    dispose() { rts.forEach(r => r.dispose()); mat.dispose(); },
  };
  sim.clear();
  return sim;
}

// Fixed-rate stepper: call tick(dt) each frame, it runs fn() at `hz` (max `maxSteps` per frame).
export function fixedStep(hz, fn, maxSteps = 3) {
  let acc = 0; return dt => { acc += dt; let n = 0; while (acc >= 1 / hz && n < maxSteps) { fn(); acc -= 1 / hz; n++; } if (n === maxSteps) acc = 0; return n; };
}
