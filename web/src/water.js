// Water surfaces (two-pass: multiplicative transmittance, then additive reflection + in-scatter) and planar reflections.
import * as THREE from 'three';
import { KZ, FOG_PARS } from './materials.js';

function cubeUVDefines(tex) {
  const h = tex.image.height;
  const maxMip = Math.log2(h) - 2;
  return {
    ENVMAP_TYPE_CUBE_UV: '',
    CUBEUV_TEXEL_WIDTH: 1.0 / (3 * Math.max(Math.pow(2, maxMip), 7 * 16)),
    CUBEUV_TEXEL_HEIGHT: 1.0 / h,
    CUBEUV_MAX_MIP: `${maxMip}.0`,
  };
}

const VERT = /* glsl */ `
varying vec3 kzWorldPos;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  kzWorldPos = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}`;
const FRAG = /* glsl */ `
uniform sampler2D tNormal; uniform float uTime; uniform vec2 uFlow;
uniform vec3 uSigma; uniform float uDepth; uniform vec3 uScatter; uniform float uNormalStrength;
uniform sampler2D tReflect; uniform mat4 uReflMatrix; uniform float uHasPlanar;
uniform sampler2D envMap; uniform float uEnvIntensity; uniform float uF0; uniform float uReflGain;
#include <common>
#include <cube_uv_reflection_fragment>
void main() {
  vec2 uv = kzWorldPos.xz * 0.16;
  vec2 f = uFlow * uTime;
  vec3 n1 = texture2D(tNormal, uv + f + vec2(uTime * 0.011, uTime * 0.007)).xyz * 2.0 - 1.0;
  vec3 n2 = texture2D(tNormal, uv * 2.6 + f * 1.4 - vec2(uTime * 0.016, -uTime * 0.010)).xyz * 2.0 - 1.0;
  vec2 d = (n1.xy + n2.xy) * uNormalStrength;
  vec3 N = normalize(vec3(d.x, 1.0, d.y));
  vec3 V = normalize(cameraPosition - kzWorldPos);
  float above = step(0.0, cameraPosition.y - kzWorldPos.y);
  float cosT = clamp(abs(dot(N, V)), 0.0, 1.0);
  float F = mix(0.0, uF0 + (1.0 - uF0) * pow(1.0 - cosT, 5.0), above);
  vec3 refl;
  if (uHasPlanar > 0.5) {
    vec4 p = uReflMatrix * vec4(kzWorldPos, 1.0);
    vec2 ruv = p.xy / p.w + d * 0.08;
    refl = texture2D(tReflect, ruv).rgb;
  } else {
    vec3 R = reflect(-V, N);
    refl = textureCubeUV(envMap, R, 0.06).rgb * uEnvIntensity;
  }
  float path = uDepth / max(abs(V.y), 0.12);
  vec3 T = exp(-uSigma * path);
  vec3 M = T * (1.0 - F);
  vec3 A = refl * F * uReflGain + uScatter * (1.0 - T) * (1.0 - F);
  vec4 fogT = kzFogTerms(kzWorldPos);
#if KZ_PASS == 0
  gl_FragColor = vec4(mix(M, vec3(1.0), fogT.a), 1.0);
#else
  gl_FragColor = vec4(A * (1.0 - fogT.a), 1.0);
#endif
}`;

export function createWaterMeshes(geometry, info, normalTex, env) {
  const depth = Math.max(0.2, info.z - info.bed_z);
  const sig = info.absorption ?? [0.75, 0.16, 0.12];
  const common = {
    tNormal: { value: normalTex },
    uTime: KZ.kzTime,
    uFlow: { value: new THREE.Vector2(info.flow ? 0.02 : 0, info.flow ? 0.012 : 0) },
    uSigma: { value: new THREE.Vector3(...sig) },
    uDepth: { value: depth },
    uScatter: { value: new THREE.Vector3(...(info.scatter ?? [0.006, 0.03, 0.028])) },
    uNormalStrength: { value: info.normal_strength ?? (info.id === 'w_mirror' ? 0.06 : 0.22) },
    uF0: { value: info.f0 ?? 0.02 },
    uReflGain: { value: info.reflect_gain ?? 1 },
    tReflect: { value: null },
    uReflMatrix: { value: new THREE.Matrix4() },
    uHasPlanar: { value: 0 },
    envMap: { value: env },
    uEnvIntensity: { value: 1 },
  };
  const mk = (pass) => {
    const m = new THREE.ShaderMaterial({
      name: `water_${info.id}_${pass ? 'add' : 'mul'}`,
      uniforms: { ...KZ, ...common },
      vertexShader: VERT,
      fragmentShader: FOG_PARS.replace('varying vec3 kzWorldPos;', 'varying vec3 kzWorldPos;') + FRAG,
      defines: { KZ_PASS: pass, ...cubeUVDefines(env) },
      transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false,
      blending: THREE.CustomBlending, blendEquation: THREE.AddEquation,
      blendSrc: pass ? THREE.OneFactor : THREE.ZeroFactor,
      blendDst: pass ? THREE.OneFactor : THREE.SrcColorFactor,
    });
    return m;
  };
  const mul = new THREE.Mesh(geometry, mk(0));
  const add = new THREE.Mesh(geometry, mk(1));
  mul.renderOrder = 10; add.renderOrder = 11;
  mul.userData.kzWater = add.userData.kzWater = info.id;
  const g = new THREE.Group();
  g.name = `water_${info.id}`;
  g.add(mul, add);
  g.userData.kzWater = info;
  g.userData.uniforms = common;
  geometry.computeBoundingBox();
  return g;
}

// Horizontal planar reflection (oblique near plane, after three's Reflector).
export class PlanarReflection {
  constructor(scale) {
    this.scale = scale;
    this.rt = new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, samples: 0, depthBuffer: true });
    this.rt.texture.name = 'planar_reflection';
    this.camera = new THREE.PerspectiveCamera();
    this.textureMatrix = new THREE.Matrix4();
    this.water = null;
  }
  setSize(w, h) {
    const W = Math.max(4, Math.round(w * this.scale)), H = Math.max(4, Math.round(h * this.scale));
    if (this.rt.width !== W || this.rt.height !== H) this.rt.setSize(W, H);
  }
  render(renderer, scene, camera, y, hide) {
    const cam = this.camera;
    const cp = new THREE.Vector3().setFromMatrixPosition(camera.matrixWorld);
    if (cp.y <= y + 0.02) return false;
    const normal = new THREE.Vector3(0, 1, 0);
    const plane = new THREE.Vector3(cp.x, y, cp.z);
    const view = new THREE.Vector3().subVectors(plane, cp).reflect(normal).negate().add(plane);
    const rot = new THREE.Matrix4().extractRotation(camera.matrixWorld);
    const look = new THREE.Vector3(0, 0, -1).applyMatrix4(rot).add(cp);
    const target = new THREE.Vector3().subVectors(plane, look).reflect(normal).negate().add(plane);
    cam.position.copy(view);
    cam.up.set(0, 1, 0).applyMatrix4(rot).reflect(normal);
    cam.lookAt(target);
    cam.near = camera.near; cam.far = camera.far;
    cam.updateMatrixWorld();
    cam.projectionMatrix.copy(camera.projectionMatrix);
    this.textureMatrix.set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
    this.textureMatrix.multiply(cam.projectionMatrix).multiply(cam.matrixWorldInverse);
    // oblique clip plane
    const p = new THREE.Plane().setFromNormalAndCoplanarPoint(normal, plane).applyMatrix4(cam.matrixWorldInverse);
    const clip = new THREE.Vector4(p.normal.x, p.normal.y, p.normal.z, p.constant);
    const e = cam.projectionMatrix.elements, q = new THREE.Vector4();
    q.x = (Math.sign(clip.x) + e[8]) / e[0];
    q.y = (Math.sign(clip.y) + e[9]) / e[5];
    q.z = -1.0;
    q.w = (1.0 + e[10]) / e[14];
    clip.multiplyScalar(2.0 / clip.dot(q));
    e[2] = clip.x; e[6] = clip.y; e[10] = clip.z + 1.0 - 0.003; e[14] = clip.w;
    cam.projectionMatrixInverse.copy(cam.projectionMatrix).invert();
    const vis = hide.map((o) => o.visible);
    hide.forEach((o) => (o.visible = false));
    const prev = renderer.getRenderTarget();
    renderer.setRenderTarget(this.rt);
    renderer.clear();
    renderer.render(scene, cam);
    renderer.setRenderTarget(prev);
    hide.forEach((o, i) => (o.visible = vis[i]));
    return true;
  }
}
