// Kazan-yu shader material kit (three.js r186, WebGLRenderer / WebGL2, onBeforeCompile).
//
// kzShade(material, cfg) patches a MeshStandardMaterial (already patched or not by web/src/materials.js
// patchMaterial) so that albedo / roughness / metal / AO / normal / emissive come from this kit:
//   (a) anti-tiling: hex-tiling after Mikkelsen 2022 (JCGT 11(2)) with per-tile rotation, scale and
//       offset jitter, height-weighted blending and correct rotation of the normal derivatives;
//       Low tier: Quilez "technique 3" (two virtual patterns chosen by a low-frequency index);
//       boards: per-board shuffle for planks (1 tap, gradients from continuous coordinates).
//       "patch" sources (the non-seamless Codex plates) are only read in a disc around the centre.
//   (b) macro variation: ALU 3D value noise at 2 scales (brightness, hue, roughness, wet patches)
//       plus vertical run-off streaks on walls.
//   (c) distance-faded micro detail (1 extra normal/height tap, branch-skipped beyond fade).
//   (d) world-space biplanar (Quilez) for cave rock, with hex/iq3 inside each projection and normals
//       through the surface-gradient framework (Mikkelsen 2020), so no UVs or seams are needed.
//   (e) wetness: porosity darkening + mirror films in hollows / wet-mask pockets + a world wet plane
//       (water proximity) + streaks; films also flatten the micro normals.
//   (f) procedural variants: basalt, obsidian, black sand, lava crust, glacier ice, rimstone, caustics.
// All honour the 7 shared settings: tint, wetness, wear, roughness_offset, scale, normal_strength,
// emissive_level (formulas follow 3d/materials.json -> kz_core.formulas).
//
// Usage:
//   import { kzShade, KZS } from './kzshader.js';
//   kzShade(mat, { mode: 2, tier: 'high', proj: 'uv', maps: { base, nh }, tileM: [2, 2], ... });
//   KZS.time.value = seconds;  // shared animation clock (lava, caustics)
import * as THREE from 'three';

export const KZS = { time: { value: 0 } };

export const MODES = { plain: 0, antitile: 1, rich: 2, procedural: 3 };
export const PROCS = { basalt: 1, obsidian: 2, sand: 3, lava: 4, ice: 5, rimstone: 6, caustics: 7 };

// ----------------------------------------------------------------------------------------------
// GLSL
// ----------------------------------------------------------------------------------------------
const VERT_PARS = /* glsl */ `
varying vec2 kzUv;
varying vec3 kzWN;
`;
const VERT_MAIN = /* glsl */ `
  kzUv = uv;
  {
    vec3 kzon = objectNormal;
    #ifdef USE_INSTANCING
      kzon = mat3(instanceMatrix) * kzon;
    #endif
    kzWN = normalize(mat3(modelMatrix) * kzon);
  }
`;
const WORLDPOS_VERT = /* glsl */ `
  {
    vec4 kzwp = vec4(transformed, 1.0);
    #ifdef USE_INSTANCING
      kzwp = instanceMatrix * kzwp;
    #endif
    kzWorldPos = (modelMatrix * kzwp).xyz;
  }
`;

const FRAG_PARS = /* glsl */ `
// ===================== KZ shader kit =====================
varying vec2 kzUv;
varying vec3 kzWN;
uniform sampler2D kz_base, kz_nh, kz_orm, kz_base2, kz_nh2;
uniform vec2 kz_tileM;        // metres per repeat (u, v)
uniform float kz_hexK;        // hex cells per repeat
uniform float kz_rot;         // rotation jitter (fraction of +-pi)
uniform float kz_scaleJit;    // per-tile scale jitter (+-)
uniform float kz_jit;         // patch-centre jitter (patch sources)
uniform float kz_gainK;       // Gain3 exponent k = log(1-r)/log(0.5)
uniform float kz_hexBeta;     // height influence on hex weights (Mikkelsen beta)
uniform vec3 kz_tint;
uniform float kz_wetness, kz_wear, kz_roughOff, kz_normalStr, kz_emisLevel;
uniform vec2 kz_rough;        // roughness: dry, wet pocket (2-texture sets)
uniform float kz_metal, kz_aoAmt, kz_porosity;
uniform vec3 kz_wornColor;
uniform float kz_wornRough;
uniform vec3 kz_macro;        // amount, size1 (m), size2 (m)
uniform vec3 kz_macroHue;     // multiplier at full "cool" hue
uniform float kz_streak;      // vertical streak amount
uniform vec4 kz_detail;       // amount, repeat (m), fade start (m), fade end (m)
uniform vec4 kz_wetPlane;     // xyz normal, w offset: wet where dot(n,p)+w < kz_wetBand
uniform float kz_wetBand;
uniform vec3 kz_emisColor;
uniform float kz_emisFromBase;
uniform vec2 kz_layer;        // layer-2 amount, layer noise size (m)
uniform vec4 kz_board;        // boards per plate (N), board width (m), board margin, end-joint darkening
uniform vec4 kz_procA, kz_procB;
uniform vec3 kz_albedoA, kz_albedoB;
uniform float kz_time;
uniform float kz_caustics;    // caustics strength (any mode >= 2)
uniform sampler2D kz_noiseTex; // 256 px tileable RGBA noise (Low-tier macro): R,G,B fbm, A vertical streaks

#define KZ_SAT(x) clamp(x, 0.0, 1.0)

// ---- hashes (Hoskins "hash without sine", stable in highp) ----
float kzHash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
vec2 kzHash22(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973)); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.xx + p3.yz) * p3.zy); }
float kzHash13(vec3 p3) { p3 = fract(p3 * 0.1031); p3 += dot(p3, p3.zyx + 31.32); return fract((p3.x + p3.y) * p3.z); }
vec3 kzHash33(vec3 p3) { p3 = fract(p3 * vec3(0.1031, 0.1030, 0.0973)); p3 += dot(p3, p3.yxz + 33.33); return fract((p3.xxy + p3.yxx) * p3.zyx); }

// ---- value noise with analytic derivatives (Quilez) ----
vec3 kzNoised2(vec2 x) {
  vec2 i = floor(x), f = fract(x);
  vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  vec2 du = 30.0 * f * f * (f * (f - 2.0) + 1.0);
  float a = kzHash12(i), b = kzHash12(i + vec2(1, 0)), c = kzHash12(i + vec2(0, 1)), d = kzHash12(i + vec2(1, 1));
  return vec3(a + (b - a) * u.x + (c - a) * u.y + (a - b - c + d) * u.x * u.y,
              du * (vec2(b - a, c - a) + (a - b - c + d) * u.yx));
}
vec4 kzNoised3(vec3 x) {
  vec3 i = floor(x), f = fract(x);
  vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  vec3 du = 30.0 * f * f * (f * (f - 2.0) + 1.0);
  float a = kzHash13(i), b = kzHash13(i + vec3(1, 0, 0)), c = kzHash13(i + vec3(0, 1, 0)), d = kzHash13(i + vec3(1, 1, 0));
  float e = kzHash13(i + vec3(0, 0, 1)), f1 = kzHash13(i + vec3(1, 0, 1)), g = kzHash13(i + vec3(0, 1, 1)), h = kzHash13(i + vec3(1, 1, 1));
  float k1 = b - a, k2 = c - a, k3 = e - a, k4 = a - b - c + d, k5 = a - c - e + g, k6 = a - b - e + f1, k7 = -a + b + c - d + e - f1 - g + h;
  return vec4(a + k1 * u.x + k2 * u.y + k3 * u.z + k4 * u.x * u.y + k5 * u.y * u.z + k6 * u.z * u.x + k7 * u.x * u.y * u.z,
              du * vec3(k1 + k4 * u.y + k6 * u.z + k7 * u.y * u.z,
                        k2 + k5 * u.z + k4 * u.x + k7 * u.z * u.x,
                        k3 + k6 * u.x + k5 * u.y + k7 * u.x * u.y));
}
const mat3 kzM3 = mat3(0.00, 0.80, 0.60, -0.80, 0.36, -0.48, -0.60, -0.48, 0.64);
const mat3 kzM3i = mat3(0.00, -0.80, -0.60, 0.80, 0.36, -0.48, 0.60, -0.48, 0.64);
// fbm in [0,1] with gradient wrt p
vec4 kzFbm3(vec3 p, int oct) {
  float a = 0.5, tot = 0.0; vec4 s = vec4(0.0); mat3 m = mat3(1.0);
  for (int i = 0; i < 6; i++) {
    if (i >= oct) break;
    vec4 n = kzNoised3(p);
    s.x += a * n.x; s.yzw += a * (m * n.yzw); tot += a;
    a *= 0.5; p = kzM3 * p * 2.02; m = 2.02 * kzM3i * m;
  }
  return s / tot;
}
const mat2 kzM2 = mat2(0.8, 0.6, -0.6, 0.8);
vec3 kzFbm2(vec2 p, int oct) {
  float a = 0.5, tot = 0.0; vec3 s = vec3(0.0); mat2 m = mat2(1.0);
  for (int i = 0; i < 6; i++) {
    if (i >= oct) break;
    vec3 n = kzNoised2(p);
    s.x += a * n.x; s.yz += a * (m * n.yz); tot += a;
    a *= 0.5; p = kzM2 * p * 2.03; m = 2.03 * transpose(kzM2) * m;
  }
  return s / tot;
}
// cellular: x F1, y F2 (cell units), z hash of nearest cell; rel = p - nearest feature point
vec3 kzVoronoi2(vec2 x, out vec2 rel, out vec2 cid) {
  vec2 n = floor(x), f = fract(x); float F1 = 8.0, F2 = 8.0; rel = vec2(0.0); cid = n;
  for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
    vec2 g = vec2(float(i), float(j)); vec2 r = g + kzHash22(n + g) - f; float d = dot(r, r);
    if (d < F1) { F2 = F1; F1 = d; rel = -r; cid = n + g; } else if (d < F2) { F2 = d; }
  }
  return vec3(sqrt(F1), sqrt(F2), kzHash12(cid));
}
vec3 kzVoronoi3(vec3 x, out vec3 rel, out vec3 cid) {
  vec3 n = floor(x), f = fract(x); float F1 = 8.0, F2 = 8.0; rel = vec3(0.0); cid = n;
  for (int k = -1; k <= 1; k++) for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
    vec3 g = vec3(float(i), float(j), float(k)); vec3 r = g + kzHash33(n + g) - f; float d = dot(r, r);
    if (d < F1) { F2 = F1; F1 = d; rel = -r; cid = n + g; } else if (d < F2) { F2 = d; }
  }
  return vec3(sqrt(F1), sqrt(F2), kzHash13(cid));
}

// surface gradient of a scalar h(x) from screen-space derivatives (Mikkelsen 2010 / three perturbNormalArb)
vec3 kzScreenGrad(vec3 wp, vec3 N, float h) {
  vec3 dpdx = dFdx(wp), dpdy = dFdy(wp);
  vec3 r1 = cross(dpdy, N), r2 = cross(N, dpdx);
  float det = dot(dpdx, r1);
  vec3 g = (dFdx(h) * r1 + dFdy(h) * r2) * sign(det);
  return g / max(abs(det), 1e-12);
}

// ---- texture taps ----
struct KzTex { vec4 base; vec4 nh; vec4 orm; vec2 d; };
#ifdef KZ_GRAD
  #define KZ_T(s, uv, dx, dy) textureGrad(s, uv, dx, dy)
#else
  #define KZ_T(s, uv, dx, dy) texture(s, uv)
#endif
vec2 kzDeriv(vec2 rg) {           // Mikkelsen 2022 listing 9: tangent normal -> height derivative
  vec3 m = vec3(rg * 2.0 - 1.0, 0.0);
  m.z = sqrt(max(1.0 - dot(m.xy, m.xy), 0.0));
  return -m.xy / max(m.z, (1.0 / 128.0) * max(abs(m.x), abs(m.y)));
}
KzTex kzFetch(sampler2D tb, sampler2D tn, vec2 st, vec2 dx, vec2 dy) {
  KzTex o;
  o.base = KZ_T(tb, st, dx, dy);
  o.nh = KZ_T(tn, st, dx, dy);
  #ifdef KZ_ORM
    o.orm = KZ_T(kz_orm, st, dx, dy);
  #else
    o.orm = vec4(1.0, 0.0, 0.0, o.nh.b);
  #endif
  o.d = kzDeriv(o.nh.rg);
  return o;
}
KzTex kzMix3(KzTex a, KzTex b, KzTex c, vec3 W) {
  KzTex o;
  o.base = a.base * W.x + b.base * W.y + c.base * W.z;
  o.nh = a.nh * W.x + b.nh * W.y + c.nh * W.z;
  o.orm = a.orm * W.x + b.orm * W.y + c.orm * W.z;
  o.d = a.d * W.x + b.d * W.y + c.d * W.z;
  return o;
}
KzTex kzMix2(KzTex a, KzTex b, float t) {
  KzTex o;
  o.base = mix(a.base, b.base, t); o.nh = mix(a.nh, b.nh, t); o.orm = mix(a.orm, b.orm, t); o.d = mix(a.d, b.d, t);
  return o;
}

// ---- plain ----
KzTex kzPlain(sampler2D tb, sampler2D tn, vec2 t, vec2 dx, vec2 dy) { return kzFetch(tb, tn, t, dx, dy); }

// ---- hex tiling (Mikkelsen 2022 listings 1, 3-5, 8; Heitz & Neyret 2018 triangle grid) ----
void kzTriGrid(vec2 st, out vec3 w, out vec2 v1, out vec2 v2, out vec2 v3) {
  st *= 3.46410162;                                        // 2 sqrt(3)
  vec2 sk = vec2(st.x - 0.57735027 * st.y, 1.15470054 * st.y);
  vec2 b = floor(sk);
  vec3 t = vec3(fract(sk), 0.0); t.z = 1.0 - t.x - t.y;
  float s = step(0.0, -t.z), s2 = 2.0 * s - 1.0;
  w = vec3(-t.z * s2, s - t.y * s2, s - t.x * s2);
  v1 = b + vec2(s, s); v2 = b + vec2(s, 1.0 - s); v3 = b + vec2(1.0 - s, s);
}
// per-vertex transform: st_i = R (s - cen) * sc / k + o ; returns R*sc (the Jacobian dst/dt)
mat2 kzHexVert(vec2 v, vec2 s, out vec2 st) {
  vec2 cen = vec2(v.x + 0.5 * v.y, 0.8660254 * v.y) * 0.28867513;
  vec2 h = kzHash22(v + 17.0);
  float h2 = kzHash12(v * 1.7 + 3.1);
  float a = (h2 - 0.5) * 6.2831853 * kz_rot;
  float c = cos(a), si = sin(a);
  float sc = 1.0 + (h.x - 0.5) * kz_scaleJit;
  mat2 J = mat2(c, si, -si, c) * sc;
  #ifdef KZ_PATCH
    vec2 o = 0.5 + (h - 0.5) * kz_jit;                    // stay inside the plate centre disc
  #else
    vec2 o = h;
  #endif
  st = J * (s - cen) / kz_hexK + o;
  return J;
}
vec3 kzGain3(vec3 x) {
  #ifdef KZ_GAIN
    vec3 s = 2.0 * step(0.5, x);
    vec3 m = 2.0 * (1.0 - s);
    vec3 r = 0.5 * s + 0.25 * m * pow(max(vec3(0.0), s + x * m), vec3(kz_gainK));
    return r / (r.x + r.y + r.z);
  #else
    return x;
  #endif
}
KzTex kzHex(sampler2D tb, sampler2D tn, vec2 t, vec2 dx, vec2 dy) {
  vec2 s = t * kz_hexK;
  vec3 w; vec2 v1, v2, v3;
  kzTriGrid(s, w, v1, v2, v3);
  vec2 st1, st2, st3;
  mat2 J1 = kzHexVert(v1, s, st1), J2 = kzHexVert(v2, s, st2), J3 = kzHexVert(v3, s, st3);
  KzTex a = kzFetch(tb, tn, st1, J1 * dx, J1 * dy);
  KzTex b = kzFetch(tb, tn, st2, J2 * dx, J2 * dy);
  KzTex c = kzFetch(tb, tn, st3, J3 * dx, J3 * dy);
  // derivative wrt t: (dst/dt)^T d   (rotate the normals back with their tile)
  a.d = transpose(J1) * a.d; b.d = transpose(J2) * b.d; c.d = transpose(J3) * c.d;
  vec3 H = vec3(a.nh.b, b.nh.b, c.nh.b);
  vec3 Dw = mix(vec3(1.0), H, kz_hexBeta);
  vec3 w2 = w * w; vec3 w7 = w2 * w2 * w2 * w;                // gamma = 7
  vec3 W = Dw * w7; W /= (W.x + W.y + W.z);
  W = kzGain3(W);
  return kzMix3(a, b, c, W);
}

// ---- Quilez technique 3: two virtual patterns chosen by a low-frequency index (Low tier) ----
KzTex kzIq3(sampler2D tb, sampler2D tn, vec2 t, vec2 dx, vec2 dy) {
  float k = kzNoised2(t * 1.3 + 0.37).x;
  float idx = k * 8.0; float i = floor(idx), f = fract(idx);
  vec2 oa = kzHash22(vec2(i, 3.0)), ob = kzHash22(vec2(i + 1.0, 3.0));
  float qa = floor(kzHash12(vec2(i, 9.0)) * 4.0) * 1.5707963 * step(0.01, kz_rot);
  float qb = floor(kzHash12(vec2(i + 1.0, 9.0)) * 4.0) * 1.5707963 * step(0.01, kz_rot);
  mat2 Ra = mat2(cos(qa), sin(qa), -sin(qa), cos(qa)), Rb = mat2(cos(qb), sin(qb), -sin(qb), cos(qb));
  KzTex a = kzFetch(tb, tn, Ra * t + oa, Ra * dx, Ra * dy);
  KzTex b = kzFetch(tb, tn, Rb * t + ob, Rb * dx, Rb * dy);
  a.d = transpose(Ra) * a.d; b.d = transpose(Rb) * b.d;
  float bl = smoothstep(0.2, 0.8, f + (b.nh.b - a.nh.b) * 0.6);
  return kzMix2(a, b, bl);
}

// ---- boards: per-board shuffle of plank strips (u = along the board, v = across) ----
KzTex kzBoards(sampler2D tb, sampler2D tn, vec2 uvm, vec2 dxm, vec2 dym, out float joint, out float boardRnd) {
  float N = kz_board.x, W = kz_board.y, mg = kz_board.z;
  float j = floor(uvm.y / W); float a = fract(uvm.y / W);
  vec2 hj = kzHash22(vec2(j, 5.0));
  float along = uvm.x / kz_tileM.y + hj.x * 7.0;              // plate lengths along the board
  float seg = floor(along); float fa = fract(along);
  vec2 hs = kzHash22(vec2(j, seg) + 11.0);
  float b = floor(hs.x * N);
  float fl = step(0.5, hs.y);
  float across = mix(a, 1.0 - a, fl);
  // plate: boards run along v; board b occupies u in [b/N, (b+1)/N]
  vec2 st = vec2((b + mg + across * (1.0 - 2.0 * mg)) / N, along);
  float sx = (1.0 - 2.0 * mg) / (N * W), sy = 1.0 / kz_tileM.y;
  vec2 gx = vec2(dxm.y * sx * (1.0 - 2.0 * fl), dxm.x * sy), gy = vec2(dym.y * sx * (1.0 - 2.0 * fl), dym.x * sy);
  KzTex o = kzFetch(tb, tn, st, gx, gy);
  // derivative wrt plate (u_p, v_p) -> wrt (u_m, v_m) in plate units: swap axes, flip
  o.d = vec2(o.d.y, o.d.x * (1.0 - 2.0 * fl));
  float fw = fwidth(fa) + 1e-4;
  joint = 1.0 - smoothstep(0.0, 0.004 / kz_tileM.y + fw, min(fa, 1.0 - fa));
  boardRnd = hs.x;
  return o;
}

// ---- source selection ----
KzTex kzSample(sampler2D tb, sampler2D tn, vec2 t, vec2 dx, vec2 dy) {
  #if KZ_SAMPLER == 1
    return kzHex(tb, tn, t, dx, dy);
  #elif KZ_SAMPLER == 2
    return kzIq3(tb, tn, t, dx, dy);
  #else
    return kzPlain(tb, tn, t, dx, dy);
  #endif
}

// ---- macro variation: ALU 3D value noise, 2 octaves at two sizes ----
vec4 kzMacro(vec3 wp, vec3 N) {
#ifdef KZ_MACRO_TEX
  // Low tier: 2 fetches of a tiny tileable noise texture in the dominant-axis plane (cheaper than ALU noise)
  vec3 an = abs(N);
  vec2 pc = an.y > max(an.x, an.z) ? wp.xz : (an.x > an.z ? wp.zy : wp.xy);
  vec4 A = texture(kz_noiseTex, pc / (kz_macro.y * 4.0));
  vec4 B = texture(kz_noiseTex, kzM2 * pc / (kz_macro.z * 4.0) + 0.31);
  float st = 0.0;
  #if KZ_MODE >= 2
    st = smoothstep(0.2, 0.8, texture(kz_noiseTex, pc / vec2(10.0, 24.0) + 0.6).a) * smoothstep(0.35, 0.65, A.b) * (1.0 - smoothstep(0.4, 0.8, an.y));
  #endif
  return vec4(0.6 * A.r + 0.4 * A.g, B.r, 0.5 * A.r + 0.5 * B.g, st * kz_streak);
#else
  float a = kzNoised3(wp / kz_macro.y + 3.1).x;
  float b = kzNoised3(wp / kz_macro.z + 11.7).x;
  float c = kzNoised3(wp / (kz_macro.y * 0.37) + 5.3).x;
  float bright = 0.6 * a + 0.4 * c;
  float hue = b;
  float wetp = 0.5 * a + 0.5 * kzNoised3(wp / (kz_macro.y * 0.6) - 7.1).x;
  // run-off streaks: narrow horizontally, long vertically, only on steep faces
  float st = 0.0;
  #if KZ_MODE >= 2
    vec3 q = wp * vec3(1.0 / 0.09, 1.0 / 1.6, 1.0 / 0.09);
    float s1 = kzNoised3(q).x;
    st = smoothstep(0.62, 0.85, s1) * smoothstep(0.35, 0.7, kzNoised3(wp / 2.5 + 1.3).x) * (1.0 - smoothstep(0.4, 0.8, abs(N.y)));
  #endif
  return vec4(bright, hue, wetp, st * kz_streak);
#endif
}

// ---- tangent frame (three getTangentFrame) in world space ----
mat2x3 kzTB(vec3 wp, vec3 N, vec2 uv) {
  vec3 q0 = dFdx(wp), q1 = dFdy(wp);
  vec2 st0 = dFdx(uv), st1 = dFdy(uv);
  vec3 q1p = cross(q1, N), q0p = cross(N, q0);
  vec3 T = q1p * st0.x + q0p * st1.x;
  vec3 B = q1p * st0.y + q0p * st1.y;
  float det = max(dot(T, T), dot(B, B));
  float sc = (det == 0.0) ? 0.0 : inversesqrt(det);
  return mat2x3(T * sc, B * sc);
}

struct KzSurf { vec3 albedo; float rough; float metal; float ao; vec3 emis; vec3 nW; float h; float film; };

// ---- procedural sources: fill albedo / rough / h / film / world gradient / emissive ----
struct KzProc { vec3 albedo; float rough; float h; float film; vec3 g; vec3 emis; float ao; float metal; };
KzProc kzProcInit() { KzProc p; p.albedo = kz_albedoA; p.rough = kz_rough.x; p.h = 0.5; p.film = 0.0; p.g = vec3(0.0); p.emis = vec3(0.0); p.ao = 1.0; p.metal = kz_metal; return p; }

vec3 kzBlackbody(float t) {       // 0..1 normalised temperature -> linear emission
  t = KZ_SAT(t);
  vec3 c = mix(vec3(0.9, 0.07, 0.005), vec3(1.0, 0.33, 0.04), smoothstep(0.15, 0.55, t));
  c = mix(c, vec3(1.0, 0.75, 0.38), smoothstep(0.6, 1.0, t));
  return c * t * t * (1.0 + 3.0 * t);
}

#if KZ_PROC == 1
// basalt: domain-warped fbm relief, sparse fractures, vesicles, grain + feldspar flecks
KzProc kzProcBasalt(vec3 wp, vec3 N, float fw) {
  KzProc o = kzProcInit();
  float f0 = kz_procA.x;                                 // 1 / relief size
  vec3 p = wp * f0;
  vec3 warp = vec3(kzNoised3(p * 0.45).x, kzNoised3(p * 0.45 + 5.2).x, kzNoised3(p * 0.45 + 9.7).x) - 0.5;
  vec3 q = p + warp * 1.2;
  vec4 f = kzFbm3(q, KZ_TIER > 0 ? 5 : 3);
  float amp = kz_procA.y;                                // metres
  o.h = f.x;
  o.g = f.yzw * f0 * amp;
  float crack = 0.0, hole = 0.0, fleck = 0.0, chip = 0.5;
  {
    // conchoidal fracture facets / chips 8-30 cm: constant gradient per 3D cell -> crisp ridges, no outline
    vec3 rel, cid;
    vec3 v = kzVoronoi3(wp / kz_procA.z + warp * 0.6, rel, cid);
    vec3 tilt = (kzHash33(cid + 7.0) * 2.0 - 1.0);
    float ff = 1.0 - smoothstep(kz_procA.z * 0.15, kz_procA.z * 0.6, fw);
    o.g += tilt * kz_procA.w * ff;
    chip = v.z;
    // sparse fractures: only where a low-frequency mask allows, a shadowed groove (no albedo outline)
    float e = v.y - v.x;
    float mask = smoothstep(0.62, 0.78, kzNoised3(wp * 0.35 + 4.0).x);
    crack = (1.0 - smoothstep(0.0, 0.05 + fw / kz_procA.z, e)) * mask;
  }
  #if KZ_TIER > 0
  if (fw < 0.006) {                                       // vesicles 2-15 mm, near only
    vec3 rel, cid;
    vec3 v = kzVoronoi3(wp * 45.0, rel, cid);
    float r = mix(0.12, 0.42, kzHash13(cid + 3.0)) * step(0.55, v.z);
    hole = (1.0 - smoothstep(r * 0.7, r, v.x)) * (1.0 - smoothstep(0.002, 0.006, fw));
    fleck = step(0.985, kzHash13(cid + 9.0)) * (1.0 - smoothstep(0.75, 0.25, v.x)) * (1.0 - smoothstep(0.0015, 0.004, fw));
  }
  #endif
  float grain = kzNoised3(wp * 60.0).x;
  float gfade = 1.0 - smoothstep(0.003, 0.012, fw);
  vec3 alb = kz_albedoA * (0.45 + 1.1 * smoothstep(0.2, 0.8, f.x)) * (1.0 + (grain - 0.5) * 0.4 * gfade) * (0.9 + 0.2 * chip);
  alb = mix(alb, kz_albedoB, fleck);
  alb *= 1.0 - 0.6 * hole;
  alb *= 1.0 - 0.15 * crack;
  o.albedo = alb;
  float hd = -crack * 0.015 - hole * 0.004;               // metres, screen-space gradient
  o.g += kzScreenGrad(wp, N, hd);
  o.ao = (1.0 - 0.5 * crack) * (1.0 - 0.5 * hole) * mix(0.75, 1.0, smoothstep(0.25, 0.6, f.x));
  o.rough = kz_rough.x + (f.x - 0.5) * 0.2;
  o.film = KZ_SAT((0.5 - f.x) * 1.6 + crack * 0.8 + hole);
  return o;
}
#endif

#if KZ_PROC == 2
// obsidian: flat conchoidal facets (constant gradient per 3D cell), crisp ridges, ripple arcs
KzProc kzProcObsidian(vec3 wp, vec3 N, float fw) {
  KzProc o = kzProcInit();
  float cs = kz_procA.x;                                  // facet size (m)
  vec3 rel, cid;
  vec3 v = kzVoronoi3(wp / cs, rel, cid);
  vec3 tilt = (kzHash33(cid + 7.0) * 2.0 - 1.0) * kz_procA.y;
  o.g = tilt;
  float e = v.y - v.x;
  float ridge = 1.0 - smoothstep(0.0, 0.035 + fw / cs * 1.5, e);
  // concentric ripple arcs around an off-cell origin, only on some facets
  float r = length(rel) * cs;
  float on = step(0.45, kzHash13(cid + 1.0));
  float lam = kz_procA.z;                                 // ripple spacing (m)
  float rf = (1.0 - smoothstep(lam * 0.4, lam * 1.2, fw)) * on;
  vec3 dir = rel / max(length(rel), 1e-4);
  o.g += dir * cos(r * 6.2831853 / lam) * (6.2831853 / lam) * 0.00035 * rf * smoothstep(0.0, 0.3, v.x);
  o.albedo = mix(kz_albedoA, kz_albedoB, ridge * 0.6 + 0.15 * kzHash13(cid));
  o.rough = mix(kz_rough.x, kz_rough.y, ridge);
  o.h = 1.0 - ridge;
  o.ao = 1.0 - 0.3 * ridge;
  return o;
}
#endif

#if KZ_PROC == 3
// black sand: wind/wave ripples, glints set in roughness, sparse pebbles
KzProc kzProcSand(vec3 wp, vec3 N, float fw) {
  KzProc o = kzProcInit();
  vec2 x = wp.xz;
  vec3 w = kzFbm2(x * 0.35, 3);
  vec3 w2 = kzFbm2(x * 0.9 + 7.0, 2);
  float lam = kz_procA.x;                                 // ripple wavelength (m)
  float rf = 1.0 - smoothstep(lam * 0.06, lam * 0.22, fw);
  float amask = smoothstep(0.3, 0.8, kzNoised2(x * 0.12 + 4.0).x);
  // two ripple trains at different angles, blended by a patch mask, warped by fbm
  float ang = (w.x - 0.5) * 1.6 + 0.4;
  vec2 dir = vec2(cos(ang), sin(ang)), dir2 = vec2(cos(ang + 0.9), sin(ang + 0.9));
  float ph = dot(x, dir) / lam + w.x * 6.0 + w2.x * 1.5;
  float ph2 = dot(x, dir2) / (lam * 1.35) + w.x * 4.0;
  float pm = smoothstep(0.35, 0.65, kzNoised2(x * 0.25 + 9.0).x);
  float amp = kz_procA.y * amask * rf;                     // metres
  float s1 = sin(ph * 6.2831853), s2 = sin(ph2 * 6.2831853);
  float s = mix(s1, s2, pm);
  float hr = s * amp * (0.75 + 0.5 * w2.x);
  vec2 g2 = mix(cos(ph * 6.2831853) * 6.2831853 / lam * dir, cos(ph2 * 6.2831853) * 6.2831853 / (lam * 1.35) * dir2, pm) * amp * (0.75 + 0.5 * w2.x);
  o.g = vec3(g2.x, 0.0, g2.y);
  // pebbles
  vec2 rel, cid;
  vec3 v = kzVoronoi2(x / 0.06, rel, cid);
  float pr = mix(0.12, 0.42, pow(kzHash12(cid + 2.0), 2.0)) * step(0.93, v.z);
  float peb = 1.0 - smoothstep(pr * 0.6, pr, v.x);
  float pd = sqrt(KZ_SAT(1.0 - (v.x * v.x) / (pr * pr + 1e-4)));
  float hp = peb * pd * 0.01;
  o.g += kzScreenGrad(wp, N, hp);
  // grains + glints (footprint faded)
  vec2 gc = floor(x / 0.0025);
  float gh = kzHash12(gc);
  float gfade = 1.0 - smoothstep(0.0012, 0.004, fw);
  float glint = step(0.991, gh) * gfade;
  vec3 alb = kz_albedoA * (0.85 + 0.3 * kzNoised2(x * 1.7).x) * (1.0 + (gh - 0.5) * 0.6 * gfade);
  alb = mix(alb, kz_albedoB * (0.5 + 0.6 * kzHash12(cid)), peb * 0.6);
  o.albedo = alb;
  o.rough = mix(kz_rough.x, 0.07, glint);
  o.rough = mix(o.rough, kz_rough.x - 0.12, (1.0 - gfade) * 0.5);    // far: glint density as lower roughness
  o.h = 0.5 + hr / max(kz_procA.y, 1e-4) * 0.5 + peb * 0.3;
  o.film = KZ_SAT((0.5 - s * 0.5) * 0.7 * amask);
  return o;
}
#endif

#if KZ_PROC == 4
// lava crust: drifting crust plates, glowing seams, cooling cracks, flicker
KzProc kzProcLava(vec2 x, vec3 wp, vec3 N, float fw) {
  KzProc o = kzProcInit();
  float cs = kz_procA.x;
  vec2 flow = kz_procB.xy * kz_time;
  vec2 p = (x + flow) / cs;
  vec3 w = kzFbm2(p * 0.5 + kz_time * 0.02, 2);
  p += (w.x - 0.5) * 0.9;
  vec2 rel, cid;
  vec3 v = kzVoronoi2(p, rel, cid);
  float e = v.y - v.x;
  float seamW = kz_procA.y;
  float seam = (1.0 - smoothstep(0.0, seamW + fw / cs, e)) * 0.8 + 0.2 * exp(-e / (seamW * 3.0 + fw / cs));
  vec2 rel2, cid2;
  vec3 v2 = kzVoronoi2(p * 3.3 + 7.0, rel2, cid2);
  float e2 = v2.y - v2.x;
  float crack = exp(-e2 / (seamW * 0.6 + fw / cs * 3.3)) * smoothstep(0.15, 0.6, v.x);
  float flick = 0.8 + 0.2 * sin(kz_time * (0.6 + v.z) + v.z * 40.0);
  // seams vary along their length: hot rivers in a few, cooling (dim) in most
  float hotN = kzNoised2(p * 0.7 + kz_time * 0.05).x;
  float seamHot = smoothstep(0.25, 0.75, hotN);
  float temp = seam * flick * mix(0.35, 1.0, seamHot) + crack * 0.35 * seamHot + 0.05 * w.x;
  o.emis = kzBlackbody(temp) * kz_procA.z;
  float plate = smoothstep(0.0, 0.18, e);
  vec3 b = kzFbm2(p * 2.0 + v.z * 13.0, 3);
  o.albedo = kz_albedoA * (0.6 + 0.8 * b.x) * plate + kz_albedoB * (1.0 - plate) * 0.3;
  float hm = (plate * 0.03 + b.x * 0.012) * cs;
  o.g = kzScreenGrad(wp, N, hm);
  o.h = plate * 0.7 + b.x * 0.3;
  o.rough = mix(0.45, kz_rough.x, plate);
  o.ao = mix(0.6, 1.0, plate);
  return o;
}
#endif

#if KZ_PROC == 5
// glacier ice: 3 parallax layers of cracks and bubbles in a deep-blue body, fake under-glow
KzProc kzProcIce(vec3 wp, vec3 N, float fw, vec2 pc, vec3 ea, vec3 eb) {
  KzProc o = kzProcInit();
  vec3 V = normalize(cameraPosition - wp);
  float ndv = max(dot(V, N), 0.2);
  vec2 vt = vec2(dot(V, ea), dot(V, eb)) / ndv;
  float acc = 0.0, bub = 0.0;
  for (int i = 0; i < 3; i++) {
    float d = kz_procA.x * (0.35 + float(i) * float(i) * 0.9 + float(i) * 0.6);
    float cs = kz_procA.y * (1.0 + float(i) * 0.7);
    vec2 q = (pc - vt * d) / cs + float(i) * 17.3;
    vec2 rel, cid;
    vec3 v = kzVoronoi2(q, rel, cid);
    float e = v.y - v.x;
    float cmask = smoothstep(0.45, 0.7, kzNoised2(q * 0.35 + 3.0).x);
    float crack = (1.0 - smoothstep(0.0, 0.03 + fw / cs * 2.0, e)) * cmask * 0.6;
    float br = mix(0.03, 0.09, kzHash12(cid + 4.0)) * step(0.82, kzHash12(cid + 8.0));
    float bubble = 1.0 - smoothstep(br * 0.6, br, length(rel - (kzHash22(cid) - 0.5) * 0.5));
    float att = exp(-d * kz_procA.z);
    acc += (crack * 0.7) * att * (1.0 - acc);
    bub += bubble * att * (1.0 - bub);
  }
  vec3 s = kzFbm2(pc * 1.3, 3);
  o.g = (ea * s.y + eb * s.z) * 0.02;
  o.albedo = mix(kz_albedoA * (0.8 + 0.4 * s.x), kz_albedoB, KZ_SAT(acc + bub * 0.6));
  o.emis = kz_emisColor * (1.0 - acc) * (0.6 + 0.4 * s.x);
  o.rough = mix(kz_rough.x, kz_rough.y, acc);
  o.h = 0.5 + 0.5 * s.x;
  return o;
}
#endif

#if KZ_PROC == 6
// rimstone: gours (scalloped rim terraces with water pockets) on tops, flowstone flutes on sides
KzProc kzProcRimstone(vec3 wp, vec3 N, float fw) {
  KzProc o = kzProcInit();
  float up = smoothstep(0.45, 0.8, N.y);
  float hTop = 0.0, hSide = 0.0, rim = 0.0, pool = 0.0, flute = 0.0;
  vec3 colTop = kz_albedoA, colSide = kz_albedoA;
  if (up > 0.01) {
    vec3 n = kzFbm2(wp.xz / kz_procA.x, 4);
    float q = n.x * kz_procA.y + wp.y * 0.0;
    float fr = fract(q);
    rim = smoothstep(0.80, 0.96, fr) * (1.0 - smoothstep(0.96, 1.0, fr));
    pool = 1.0 - smoothstep(0.05, 0.6, fr);
    hTop = (floor(q) + smoothstep(0.7, 1.0, fr)) * 0.012 + rim * 0.006;
    colTop = mix(kz_albedoA * 0.82, kz_albedoA * 1.08, rim);
  }
  if (up < 0.99) {
    vec3 T = normalize(cross(vec3(0.0, 1.0, 0.0), N) + 1e-5);
    float sx = dot(wp, T);
    vec3 m = kzFbm2(vec2(sx * 1.5, wp.y * 0.15), 2);
    float ph = sx / kz_procA.z + m.x * 0.8;
    flute = pow(0.5 + 0.5 * sin(ph * 6.2831853), 1.5);
    // bulbous drips: short rounded lobes hanging from the flutes
    float dr = smoothstep(0.6, 0.85, kzNoised2(vec2(floor(ph) * 3.1, wp.y * 2.5 + floor(ph) * 1.7)).x) * flute;
    hSide = (flute * 0.006 + dr * 0.004) * (1.0 - smoothstep(kz_procA.z * 0.2, kz_procA.z * 0.8, fw));
    float band = smoothstep(0.55, 0.8, kzNoised2(vec2(sx * 0.4, wp.y * 2.5)).x);
    colSide = mix(kz_albedoA * (0.85 + 0.25 * flute), kz_albedoB, band * 0.7);
  }
  float h = mix(hSide, hTop, up);
  o.g = kzScreenGrad(wp, N, h);
  vec3 grain = vec3(kzNoised3(wp * 25.0).x);
  o.albedo = mix(colSide, colTop, up) * (0.9 + 0.2 * grain.x);
  o.albedo = mix(o.albedo, o.albedo * vec3(0.72, 0.86, 0.86), pool * up * 0.8);   // teal-grey wet pockets
  o.film = KZ_SAT(mix((1.0 - flute) * 0.6, pool + rim * 0.5, up));
  o.h = mix(flute, 1.0 - pool, up);
  o.rough = kz_rough.x;
  o.ao = mix(0.85 + 0.15 * flute, 1.0 - 0.25 * pool, up);
  return o;
}
#endif


#if defined(KZ_HYBRID) && KZ_HYBRID == 1
// hybrid basalt overlay on the plate: fracture-facet chips, sparse grooves, vesicles (near), glinty film
void kzOverlayBasalt(vec3 wp, vec3 N, float fw, float dist, inout vec3 g, inout vec3 albedo, inout float film, inout float ao, inout float rough) {
  float ff = 1.0 - smoothstep(kz_procA.z * 0.12, kz_procA.z * 0.5, fw);
  if (ff <= 0.001) return;
  vec3 rel, cid;
  vec3 v = kzVoronoi3(wp / kz_procA.z, rel, cid);
  g += (kzHash33(cid + 7.0) * 2.0 - 1.0) * kz_procA.w * ff;
  albedo *= 1.0 + (v.z - 0.5) * 0.25 * ff;
  rough += (kzHash13(cid + 2.0) - 0.5) * 0.25 * ff;     // some chips glossier than others
  #if KZ_TIER > 0
  if (fw < 0.005) {
    vec3 rel2, cid2;
    vec3 vv = kzVoronoi3(wp * 45.0, rel2, cid2);
    float r = mix(0.12, 0.42, kzHash13(cid2 + 3.0)) * step(0.6, vv.z);
    float hole = (1.0 - smoothstep(r * 0.7, r, vv.x)) * (1.0 - smoothstep(0.002, 0.005, fw));
    albedo *= 1.0 - 0.55 * hole; ao *= 1.0 - 0.4 * hole; film = max(film, hole);
    g += kzScreenGrad(wp, N, -hole * 0.003);
  }
  #endif
}
#endif
#if defined(KZ_HYBRID) && KZ_HYBRID == 3
// hybrid sand overlay: warped ripple trains + roughness glints on the plate
void kzOverlaySand(vec3 wp, vec3 N, float fw, inout vec3 g, inout vec3 albedo, inout float film, inout float rough) {
  vec2 x = wp.xz;
  vec3 w = kzFbm2(x * 0.35, 2);
  float lam = kz_procA.x;
  float rf = 1.0 - smoothstep(lam * 0.06, lam * 0.22, fw);
  float amask = smoothstep(0.3, 0.8, kzNoised2(x * 0.12 + 4.0).x) * rf;
  float ang = (w.x - 0.5) * 1.6 + 0.4;
  vec2 dir = vec2(cos(ang), sin(ang));
  float ph = dot(x, dir) / lam + w.x * 6.0;
  float c = cos(ph * 6.2831853);
  vec2 g2 = c * 6.2831853 / lam * dir * kz_procA.y * amask;
  g += vec3(g2.x, 0.0, g2.y);
  film = max(film, (0.5 - 0.5 * sin(ph * 6.2831853)) * 0.6 * amask);
  vec2 gc = floor(x / 0.0025);
  float gfade = 1.0 - smoothstep(0.0012, 0.004, fw);
  rough = mix(rough, 0.07, step(0.992, kzHash12(gc)) * gfade);
  rough -= 0.1 * (1.0 - gfade);
}
#endif

// water caustics: two drifting cellular layers, bright edges (min of the two)
float kzCaustic(vec2 x, float t) {
  vec2 rel, cid;
  vec2 p = x * 2.2;
  vec3 w = kzFbm2(p * 0.4 + t * 0.07, 2);
  vec3 a = kzVoronoi2(p + vec2(t * 0.11, t * 0.07) + w.x * 0.7, rel, cid);
  vec3 b = kzVoronoi2(p * 1.37 - vec2(t * 0.09, -t * 0.05) + w.x * 0.6 + 3.1, rel, cid);
  float ca = exp(-(a.y - a.x) * 9.0), cb = exp(-(b.y - b.x) * 9.0);
  return pow(min(ca + 0.25, cb + 0.25) - 0.25, 1.5) * 1.6 + 0.1 * (ca + cb);
}

KzSurf kzSurface() {
  KzSurf S;
  vec3 wp = kzWorldPos;
  vec3 N = normalize(kzWN);
  #ifdef DOUBLE_SIDED
    N *= gl_FrontFacing ? 1.0 : -1.0;
  #endif
  float dist = length(wp - cameraPosition);
  float fw = length(fwidth(wp));                          // metres per pixel
  #if KZ_MODE >= 2
    vec4 M = kzMacro(wp, N);
    float mAmt = kz_macro.x;
  #else
    vec4 M = vec4(0.5, 0.5, 0.5, 0.0);
    float mAmt = 0.0;
  #endif

  vec3 albedo; float rough, metal, ao, h, film; vec3 g; vec3 emis = vec3(0.0);
  float layerT = 0.0;

  #if KZ_MODE == 3 && KZ_PROC > 0
    KzProc P;
    #if KZ_PROC == 1
      P = kzProcBasalt(wp, N, fw);
    #elif KZ_PROC == 2
      P = kzProcObsidian(wp, N, fw);
    #elif KZ_PROC == 3
      P = kzProcSand(wp, N, fw);
    #elif KZ_PROC == 4
      #if KZ_PROJ == 0
        P = kzProcLava(kzUv, wp, N, fw);
      #else
        P = kzProcLava(wp.xz, wp, N, fw);
      #endif
    #elif KZ_PROC == 5
      {
        vec3 an = abs(N);
        vec3 ea = an.x > an.z && an.x > an.y ? vec3(0, 0, 1) : (an.y > an.z ? vec3(1, 0, 0) : vec3(1, 0, 0));
        vec3 eb = an.y > max(an.x, an.z) ? vec3(0, 0, 1) : vec3(0, 1, 0);
        P = kzProcIce(wp, N, fw, vec2(dot(wp, ea), dot(wp, eb)), ea, eb);
      }
    #elif KZ_PROC == 6
      P = kzProcRimstone(wp, N, fw);
    #else
      P = kzProcInit();
    #endif
    albedo = P.albedo * kz_tint; rough = P.rough; metal = P.metal; ao = P.ao; h = P.h; film = P.film;
    g = P.g; emis = P.emis * kz_tint * kz_emisLevel;
  #else
    // ------------------- texture path -------------------
    KzTex T;
    float joint = 0.0, boardRnd = 0.5;
    #if KZ_PROJ == 0
      vec2 uvm = kzUv;
      vec2 t = uvm / kz_tileM;
      vec2 tdx = dFdx(t), tdy = dFdy(t);
      #if defined(KZ_BOARDS) && KZ_MODE >= 1
        T = kzBoards(kz_base, kz_nh, uvm, dFdx(uvm), dFdy(uvm), joint, boardRnd);
      #else
        T = kzSample(kz_base, kz_nh, t, tdx, tdy);
      #endif
      #if defined(KZ_LAYER2) && KZ_MODE >= 2
        layerT = smoothstep(0.35, 0.65, kzNoised3(wp / kz_layer.y + 2.7).x * 0.8 + 0.1 + (T.nh.b - 0.5) * 0.5) * kz_layer.x;
        if (layerT > 0.001) {
          KzTex T2 = kzSample(kz_base2, kz_nh2, t * 0.93 + 0.21, tdx * 0.93, tdy * 0.93);
          // height blend: the higher of the two layers wins inside the transition band
          layerT = smoothstep(-0.12, 0.12, (T2.nh.b - T.nh.b) * 0.5 + layerT - 0.5);
          T = kzMix2(T, T2, layerT);
        }
      #endif
      mat2x3 TB = kzTB(wp, N, t);
      g = TB[0] * T.d.x + TB[1] * T.d.y;
      vec2 tDet = t;
      mat2x3 TBd = TB;
    #else
      // ------------- biplanar world projection (Quilez) -------------
      vec3 an = abs(N);
      // major (ma) and median (me) axes; projections: X -> (z, y), Y -> (x, z), Z -> (x, y)
      int ma = (an.x > an.y && an.x > an.z) ? 0 : (an.y > an.z ? 1 : 2);
      int mi = (an.x < an.y && an.x < an.z) ? 0 : (an.y < an.z ? 1 : 2);
      int me = 3 - mi - ma;
      #if KZ_PROJ == 2
        ma = 1; me = 1;
      #endif
      vec3 e0a = ma == 0 ? vec3(0, 0, 1) : vec3(1, 0, 0);
      vec3 e0b = ma == 1 ? vec3(0, 0, 1) : vec3(0, 1, 0);
      vec3 e1a = me == 0 ? vec3(0, 0, 1) : vec3(1, 0, 0);
      vec3 e1b = me == 1 ? vec3(0, 0, 1) : vec3(0, 1, 0);
      vec3 pdx = dFdx(wp), pdy = dFdy(wp);
      vec2 tiv = 1.0 / kz_tileM;
      vec2 t0 = vec2(dot(wp, e0a), dot(wp, e0b)) * tiv;
      vec2 t1 = vec2(dot(wp, e1a), dot(wp, e1b)) * tiv + 0.37;
      vec2 t0dx = vec2(dot(pdx, e0a), dot(pdx, e0b)) * tiv, t0dy = vec2(dot(pdy, e0a), dot(pdy, e0b)) * tiv;
      KzTex A = kzSample(kz_base, kz_nh, t0, t0dx, t0dy);
      #if defined(KZ_LAYER2) && KZ_MODE >= 2
        // layer 2 on the major projection only (the median projection keeps layer 1)
        layerT = smoothstep(0.35, 0.65, kzNoised3(wp / kz_layer.y + 2.7).x * 0.8 + 0.1 + (A.nh.b - 0.5) * 0.5) * kz_layer.x;
        if (layerT > 0.001) {
          KzTex A2 = kzSample(kz_base2, kz_nh2, t0 * 0.93 + 0.21, t0dx * 0.93, t0dy * 0.93);
          layerT = smoothstep(-0.12, 0.12, (A2.nh.b - A.nh.b) * 0.5 + layerT - 0.5);
          A = kzMix2(A, A2, layerT);
        }
      #endif
      vec2 w = vec2(an[ma], an[me]);
      w = KZ_SAT((w - 0.5773) / (1.0 - 0.5773));
      w = pow(w, vec2(1.0));
      KzTex Bt = A;
      if (w.y > 0.001 && me != ma) {
        Bt = kzSample(kz_base, kz_nh, t1, vec2(dot(pdx, e1a), dot(pdx, e1b)) * tiv, vec2(dot(pdy, e1a), dot(pdy, e1b)) * tiv);
      } else { w.y = 0.0; }
      // height-aware projection blend
      w *= mix(vec2(1.0), vec2(A.nh.b, Bt.nh.b) + 0.25, 0.7);
      float wb = w.y / max(w.x + w.y, 1e-5);
      wb = smoothstep(0.25, 0.75, wb);
      vec3 gA = (e0a * A.d.x + e0b * A.d.y) * tiv.x;
      vec3 gB = (e1a * Bt.d.x + e1b * Bt.d.y) * tiv.x;
      T = kzMix2(A, Bt, wb);
      g = mix(gA, gB, wb) * kz_tileM.x;                     // slope as encoded in the normal map
      vec2 tDet = t0;
      mat2x3 TBd = mat2x3(e0a, e0b);
    #endif

    #if KZ_MODE == 0 && defined(KZ_ORM)
      albedo = T.base.rgb * kz_tint;
      ao = T.orm.r; rough = T.orm.g; metal = T.orm.b; h = T.orm.a;
      film = T.nh.a;
    #else
      albedo = T.base.rgb * kz_tint;
      h = T.nh.b;
      film = T.nh.a;
      #ifdef KZ_ORM
        ao = T.orm.r; rough = T.orm.g; metal = T.orm.b;
      #else
        ao = mix(1.0, smoothstep(0.0, 0.55, h) * 0.5 + 0.5, kz_aoAmt);
        rough = mix(kz_rough.x, kz_rough.y, film);
        metal = kz_metal;
      #endif
    #endif
    #ifdef KZ_BOARDS
      albedo *= (1.0 + (boardRnd - 0.5) * 0.22) * (1.0 - 0.7 * joint);
      ao *= 1.0 - 0.5 * joint;
    #endif
    if (kz_emisFromBase > 0.0) {
      float hot = smoothstep(0.08, 0.35, T.base.r - T.base.b * 1.4) * smoothstep(0.05, 0.4, T.base.r);
      emis = T.base.rgb * T.base.rgb * hot * kz_emisFromBase * kz_emisLevel * kz_tint;
      albedo *= 1.0 - 0.8 * hot;
    }
    emis += kz_emisColor * kz_emisLevel * kz_tint * (kz_emisFromBase > 0.0 ? 0.0 : 1.0);

    // ------------- distance-faded micro detail (1 tap) -------------
    #if KZ_MODE >= 2
      float dfade = (1.0 - smoothstep(kz_detail.z, kz_detail.w, dist)) * kz_detail.x;
      if (dfade > 0.002) {
        float ds = kz_tileM.x / kz_detail.y;
        mat2 Rd = mat2(0.8253, 0.5646, -0.5646, 0.8253);
        vec2 td = Rd * tDet * ds + 0.5;
        vec4 nd = texture(kz_nh, td);
        vec2 dd = transpose(Rd) * kzDeriv(nd.rg) * ds;
        g += (TBd[0] * dd.x + TBd[1] * dd.y) * dfade * 0.35;
        albedo *= 1.0 + (nd.b - 0.5) * 0.45 * dfade;
        film = mix(film, max(film, nd.a), dfade * 0.5);
      }
    #endif
    #if defined(KZ_HYBRID) && KZ_HYBRID == 1
      kzOverlayBasalt(wp, N, fw, dist, g, albedo, film, ao, rough);
    #elif defined(KZ_HYBRID) && KZ_HYBRID == 3
      kzOverlaySand(wp, N, fw, g, albedo, film, rough);
    #elif defined(KZ_HYBRID) && KZ_HYBRID == 2
      {
        // hybrid obsidian: plate colour/veins, but the relief is replaced by flat 3D-Voronoi facets
        vec3 rel, cid;
        vec3 v = kzVoronoi3(wp / kz_procA.x, rel, cid);
        float e = v.y - v.x;
        float ridge = 1.0 - smoothstep(0.0, 0.035 + fw / kz_procA.x * 1.5, e);
        g = (kzHash33(cid + 7.0) * 2.0 - 1.0) * kz_procA.y + g * 0.15;
        rough = mix(kz_rough.x, kz_rough.y, max(ridge, film * 0.5));
        albedo *= 1.0 + ridge * 0.2;
        film = 0.0;
      }
    #elif defined(KZ_HYBRID) && KZ_HYBRID == 4
      // hybrid lava: plate crust + animated "breathing" of the plate's glowing seams (flowing noise)
      emis *= 0.25 + 1.5 * smoothstep(0.3, 0.7, M.x);                 // hot and cooled regions at macro scale
      emis *= 0.45 + 1.1 * smoothstep(0.2, 0.8, kzNoised2(uvm * 0.9 - kz_procB.xy * kz_time * 4.0 + vec2(0.0, kz_time * 0.03)).x);
    #endif
  #endif

  // ------------- macro variation -------------
  #if KZ_MODE >= 2
    albedo *= 1.0 + (M.x - 0.5) * 0.9 * mAmt;
    albedo *= mix(vec3(1.0), kz_macroHue, KZ_SAT((M.y - 0.5) * 2.2) * mAmt);
    albedo *= mix(vec3(1.0), vec3(1.0) / max(kz_macroHue, vec3(0.5)), KZ_SAT((0.5 - M.y) * 2.2) * mAmt * 0.5);
    albedo *= 1.0 - 0.3 * M.w;
    rough -= (M.z - 0.5) * 0.25 * mAmt;
  #endif

  // ------------- wear (shared setting) -------------
  float wear_m = KZ_SAT((h + 1.2 * kz_wear - 1.0) * 4.0) * step(0.001, kz_wear);
  albedo = mix(albedo, kz_wornColor * kz_tint * (0.7 + 0.6 * h), wear_m);
  rough = mix(rough, kz_wornRough, wear_m);

  // ------------- wetness (shared setting + water proximity + macro patches + streaks) -------------
  float plane = dot(kz_wetPlane.xyz, wp) + kz_wetPlane.w;
  float wetNear = kz_wetBand > 0.0 ? 1.0 - smoothstep(0.0, kz_wetBand, plane) : 0.0;
  float wet = KZ_SAT(kz_wetness + wetNear + ((M.z - 0.5) * 0.9 * mAmt + M.w * 0.8) * step(0.01, kz_wetness + wetNear));
  film = KZ_SAT(film * 1.2 + (0.5 - h) * 0.8 + (M.z - 0.5) * 0.6 * mAmt + M.w * 0.5 + wetNear * 0.4);
  albedo *= 1.0 - kz_porosity * 0.55 * wet * (0.6 + 0.4 * film);
  rough = mix(rough, min(rough, mix(0.32, 0.04, film)), KZ_SAT(1.4 * wet));
  rough += kz_roughOff;

  // ------------- caustics (pool floors) -------------
  #if KZ_MODE >= 2
    if (kz_caustics > 0.0) emis += kz_caustics * vec3(0.55, 0.95, 0.9) * kzCaustic(wp.xz, kz_time) * albedo * 6.0;
  #endif

  // ------------- normal: surface gradient, water films flatten micro relief -------------
  float nstr = kz_normalStr * (1.0 - 0.55 * wet * film);
  g *= nstr;
  vec3 sg = g - N * dot(N, g);
  vec3 nW = normalize(N - sg);

  // ------------- specular anti-aliasing (Kaplanyan/Tokuyoshi kernel on the perturbed normal) -------------
  vec3 ndx = dFdx(nW), ndy = dFdy(nW);
  float variance = 0.25 * (dot(ndx, ndx) + dot(ndy, ndy));
  float r2 = rough * rough;
  rough = sqrt(KZ_SAT(r2 + min(2.0 * variance, 0.18)));

  S.albedo = max(albedo, vec3(0.0));
  S.rough = clamp(rough, 0.03, 1.0);
  S.metal = KZ_SAT(metal);
  S.ao = KZ_SAT(ao);
  S.emis = emis;
  S.nW = nW;
  S.h = h;
  S.film = film;
  return S;
}
// =================== end KZ shader kit ===================
`;

// ----------------------------------------------------------------------------------------------
// JS side
// ----------------------------------------------------------------------------------------------
const WHITE = new THREE.DataTexture(new Uint8Array([255, 255, 255, 255]), 1, 1); WHITE.needsUpdate = true;
const FLAT = new THREE.DataTexture(new Uint8Array([128, 128, 128, 128]), 1, 1); FLAT.needsUpdate = true;

function gainK(r) { return Math.log(1 - r) / Math.log(0.5); }

/**
 * cfg:
 *  mode 0..3, tier 'low'|'high', proj 'uv'|'biplanar'|'floor', proc name|null
 *  maps {base, nh, orm?}, maps2 {base, nh}? (layer 2), patch bool, boards {n, widthM, margin}?
 *  tileM [u, v] metres per repeat, hexK, rot, scaleJit, jit, gainR, hexBeta
 *  rough [dry, wetPocket], metal, aoAmt, porosity, worn {color, rough}
 *  macro {amount, size1, size2, hue:[r,g,b], streak}, detail {amount, repeatM, fade:[a,b]}
 *  wetPlane [nx,ny,nz,w], wetBand, emissive {color, fromBase}, layer {amount, sizeM}
 *  procA, procB, albedoA, albedoB, caustics
 *  settings {tint, wetness, wear, roughness_offset, scale, normal_strength, emissive_level}
 *  grad bool (textureGrad; default true)
 */
export function kzShade(mat, cfg) {
  const c = { ...DEFAULTS, ...cfg };
  for (const k of ['macro', 'detail', 'worn', 'emissive', 'layer']) c[k] = { ...DEFAULTS[k], ...(cfg[k] || {}) };
  const st = { ...DEFAULTS.settings, ...(cfg.settings || {}) };
  const mode = c.mode;
  const high = c.tier !== 'low';
  const procId = c.proc ? PROCS[c.proc] : 0;
  const sampler = mode === 0 ? 0 : (high ? 1 : 2);
  const proj = { uv: 0, biplanar: 1, floor: 2 }[c.proj] ?? 0;
  const defines = {
    KZ_MODE: mode, KZ_TIER: high ? 1 : 0, KZ_SAMPLER: sampler, KZ_PROJ: proj,
    KZ_PROC: mode === 3 && !c.hybrid ? procId : 0,
  };
  // hybrid overlays: basalt/obsidian Voronoi overlays are High only (Low keeps the mode-2 texture look)
  if (mode === 3 && c.hybrid && procId && (high || procId === 3 || procId === 4)) defines.KZ_HYBRID = procId;
  if (!high && c.noiseTex) defines.KZ_MACRO_TEX = 1;
  if (c.maps?.orm) defines.KZ_ORM = 1;
  if (c.patch && mode >= 1) defines.KZ_PATCH = 1;
  if (c.gainR && c.gainR !== 0.5) defines.KZ_GAIN = 1;
  if (c.grad !== false) defines.KZ_GRAD = 1;
  if (c.boards && mode >= 1) defines.KZ_BOARDS = 1;
  if (c.maps2 && high && mode >= 2) defines.KZ_LAYER2 = 1;
  if (mat.side === THREE.DoubleSide) defines.DOUBLE_SIDED = 1;
  if (c.debug) defines.KZ_DEBUG = c.debug;
  // tile size from the shared "scale" setting (metres per repeat along u)
  const aspect = c.aspect ?? (c.tileM[0] / c.tileM[1]);
  const scale = st.scale ?? c.tileM[0];
  const U = {
    kz_base: { value: c.maps?.base ?? WHITE }, kz_nh: { value: c.maps?.nh ?? FLAT }, kz_orm: { value: c.maps?.orm ?? WHITE },
    kz_base2: { value: c.maps2?.base ?? WHITE }, kz_nh2: { value: c.maps2?.nh ?? FLAT },
    kz_tileM: { value: new THREE.Vector2(scale, scale / aspect) },
    kz_hexK: { value: c.hexK }, kz_rot: { value: c.rot }, kz_scaleJit: { value: c.scaleJit }, kz_jit: { value: c.jit },
    kz_gainK: { value: gainK(c.gainR || 0.5) }, kz_hexBeta: { value: c.hexBeta },
    kz_tint: { value: new THREE.Vector3(...st.tint) }, kz_wetness: { value: st.wetness }, kz_wear: { value: st.wear },
    kz_roughOff: { value: st.roughness_offset }, kz_normalStr: { value: st.normal_strength }, kz_emisLevel: { value: st.emissive_level },
    kz_rough: { value: new THREE.Vector2(...c.rough) }, kz_metal: { value: c.metal }, kz_aoAmt: { value: c.aoAmt }, kz_porosity: { value: c.porosity },
    kz_wornColor: { value: new THREE.Vector3(...c.worn.color) }, kz_wornRough: { value: c.worn.rough },
    kz_macro: { value: new THREE.Vector3(c.macro.amount, c.macro.size1, c.macro.size2) },
    kz_macroHue: { value: new THREE.Vector3(...c.macro.hue) }, kz_streak: { value: c.macro.streak },
    kz_detail: { value: new THREE.Vector4(c.detail.amount, c.detail.repeatM, c.detail.fade[0], c.detail.fade[1]) },
    kz_wetPlane: { value: new THREE.Vector4(...c.wetPlane) }, kz_wetBand: { value: c.wetBand },
    kz_emisColor: { value: new THREE.Vector3(...c.emissive.color) }, kz_emisFromBase: { value: c.emissive.fromBase },
    kz_layer: { value: new THREE.Vector2(c.layer.amount, c.layer.sizeM) },
    kz_board: { value: new THREE.Vector4(c.boards?.n ?? 1, c.boards?.widthM ?? 0.2, c.boards?.margin ?? 0.02, 0.7) },
    kz_procA: { value: new THREE.Vector4(...c.procA) }, kz_procB: { value: new THREE.Vector4(...c.procB) },
    kz_albedoA: { value: new THREE.Vector3(...c.albedoA) }, kz_albedoB: { value: new THREE.Vector3(...c.albedoB) },
    kz_time: KZS.time,
    kz_caustics: { value: c.caustics },
    kz_noiseTex: { value: c.noiseTex ?? WHITE },
  };
  for (const k of ['kz_base', 'kz_nh', 'kz_orm', 'kz_base2', 'kz_nh2']) {
    const t = U[k].value;
    // always repeat: patch taps stay inside the plate centre anyway, and detail / iq3 / plain taps
    // need the seamless copy to wrap
    if (t && t !== WHITE && t !== FLAT && t.wrapS !== THREE.RepeatWrapping) {
      t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.needsUpdate = true;
    }
  }
  const defStr = Object.entries(defines).map(([k, v]) => `#define ${k} ${v}`).join('\n') + '\n';
  const prevCompile = mat.onBeforeCompile;
  const prevKey = mat.customProgramCacheKey ? mat.customProgramCacheKey.bind(mat) : () => '';
  mat.onBeforeCompile = (shader, renderer) => {
    if (prevCompile && prevCompile !== THREE.Material.prototype.onBeforeCompile) prevCompile.call(mat, shader, renderer);
    Object.assign(shader.uniforms, U);
    let vs = shader.vertexShader;
    const hasWP = vs.includes('kzWorldPos');
    vs = VERT_PARS + (hasWP ? '' : 'varying vec3 kzWorldPos;\n') + vs;
    vs = vs.replace('#include <project_vertex>', '#include <project_vertex>\n' + VERT_MAIN + (hasWP ? '' : WORLDPOS_VERT));
    shader.vertexShader = vs;
    let fs = shader.fragmentShader;
    if (!fs.includes('varying vec3 kzWorldPos')) fs = 'varying vec3 kzWorldPos;\n' + fs;
    fs = defStr + fs;
    fs = fs.replace('#include <clipping_planes_pars_fragment>', '#include <clipping_planes_pars_fragment>\n' + FRAG_PARS);
    fs = rep(fs, '#include <map_fragment>', 'KzSurf kzS = kzSurface();\n\tdiffuseColor.rgb *= kzS.albedo;');
    fs = rep(fs, '#include <roughnessmap_fragment>', 'float roughnessFactor = kzS.rough;');
    fs = rep(fs, '#include <metalnessmap_fragment>', 'float metalnessFactor = kzS.metal;');
    fs = rep(fs, '#include <normal_fragment_maps>', 'normal = normalize( ( viewMatrix * vec4( kzS.nW, 0.0 ) ).xyz );');
    fs = rep(fs, '#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n\ttotalEmissiveRadiance += kzS.emis;');
    fs = rep(fs, '#include <aomap_fragment>', '#include <aomap_fragment>\n\treflectedLight.indirectDiffuse *= kzS.ao;\n\treflectedLight.indirectSpecular *= mix( 1.0, kzS.ao, 0.6 );');
    if (c.debug) fs = rep(fs, '#include <opaque_fragment>', `#if KZ_DEBUG == 1
      outgoingLight = kzS.albedo * 8.0;
    #elif KZ_DEBUG == 2
      outgoingLight = vec3(kzS.rough);
    #elif KZ_DEBUG == 3
      outgoingLight = kzS.nW * 0.5 + 0.5;
    #elif KZ_DEBUG == 4
      outgoingLight = reflectedLight.indirectSpecular;
    #elif KZ_DEBUG == 5
      outgoingLight = reflectedLight.indirectDiffuse;
    #endif
    #include <opaque_fragment>`);
    shader.fragmentShader = fs;
    mat.userData.kzShader = shader;
  };
  mat.customProgramCacheKey = () => prevKey() + '|kz|' + defStr;
  mat.userData.kz = { uniforms: U, defines, cfg: c };
  mat.needsUpdate = true;
  return mat;
}
function rep(s, a, b) {
  if (!s.includes(a)) throw new Error(`kzshader: three chunk "${a}" not found`);
  return s.replace(a, b);
}

export const DEFAULTS = {
  mode: 2, tier: 'high', proj: 'uv', proc: null, maps: null, maps2: null, patch: false, boards: null,
  tileM: [2, 2], hexK: 1.0, rot: 1.0, scaleJit: 0.25, jit: 0.25, gainR: 0.7, hexBeta: 0.6,
  rough: [0.7, 0.1], metal: 0, aoAmt: 0.6, porosity: 0.6, worn: { color: [0.05, 0.05, 0.055], rough: 0.45 },
  macro: { amount: 1.0, size1: 7.0, size2: 23.0, hue: [0.9, 1.0, 1.12], streak: 0.6 },
  detail: { amount: 1.0, repeatM: 0.3, fade: [2.5, 8.0] },
  wetPlane: [0, 1, 0, 0], wetBand: 0, emissive: { color: [0, 0, 0], fromBase: 0 }, layer: { amount: 0, sizeM: 6 },
  procA: [1, 0.1, 0.02, 0], procB: [0, 0, 0, 0], albedoA: [0.03, 0.03, 0.03], albedoB: [0.1, 0.1, 0.1], caustics: 0,
  settings: { tint: [1, 1, 1], wetness: 0, wear: 0, roughness_offset: 0, scale: null, normal_strength: 1, emissive_level: 1 },
};

// rough per-pixel cost model (used by the README table and the demo readout)
export function kzCost(cfg) {
  const c = { ...DEFAULTS, ...cfg };
  const high = c.tier !== 'low';
  const nTex = 2 + (c.maps?.orm ? 1 : 0);
  let taps = 0;
  const per = c.mode === 0 ? 1 : (c.boards ? 1 : (high ? 3 : 2));
  const proj = c.proj === 'biplanar' ? 2 : 1;
  if (c.mode === 3 && c.proc) taps = 0;
  else {
    taps = per * nTex * proj;
    if (c.mode >= 2) taps += 1 + (c.maps2 && high ? per * 2 : 0);
  }
  return { taps };
}
