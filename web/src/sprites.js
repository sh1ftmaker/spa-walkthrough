// Glowworm points (additive round sprites with a slow twinkle) and their silk threads (faint additive lines).
// Point attributes (glTF COLOR_0, normalized): r = brightness, g = twinkle phase, b = sprite radius / 0.05 m, a = rate / 0.4 Hz.
import * as THREE from 'three';
import { KZ, FOG_PARS } from './materials.js';

export const SPRITES = {
  kzPxScale: { value: 500 },   // drawing-buffer pixels per unit of (size / distance): H / (2 tan(fov / 2))
  kzSpriteGain: { value: 7.0 }, // linear HDR at full brightness (AgX keeps the cyan)
};

const VERT = /* glsl */ `
attribute vec4 color;
uniform float kzPxScale; uniform float kzTime;
varying vec3 kzWorldPos; varying float vB;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  kzWorldPos = wp.xyz;
  vec4 mv = viewMatrix * wp;
  gl_Position = projectionMatrix * mv;
  float r = color.b * 0.05;
  float px = 2.0 * r * kzPxScale / max(-mv.z, 0.05);
  float tw = 0.6 + 0.4 * sin(6.2831853 * (kzTime * color.a * 0.4 + color.g));
  // keep sub-pixel points visible at 1.6 px, dimmed in proportion to their true footprint
  vB = color.r * tw * clamp(px / 1.6, 0.3, 1.0);
  gl_PointSize = clamp(px, 1.6, 10.0);
}`;
const FRAG = /* glsl */ `
uniform vec3 uColor; uniform float kzSpriteGain;
varying float vB;
void main() {
  vec2 q = gl_PointCoord * 2.0 - 1.0;
  float d2 = dot(q, q);
  if (d2 > 1.0) discard;
  float a = exp(-d2 * 3.0);
  vec4 f = kzFogTerms(kzWorldPos);
  gl_FragColor = vec4(uColor * kzSpriteGain * vB * a * (1.0 - f.a), 1.0);
}`;
const LVERT = /* glsl */ `
attribute vec4 color;
varying vec3 kzWorldPos; varying float vB;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  kzWorldPos = wp.xyz; vB = color.r;
  gl_Position = projectionMatrix * viewMatrix * wp;
}`;
const LFRAG = /* glsl */ `
uniform vec3 uColor; uniform float kzSpriteGain;
varying float vB;
void main() {
  vec4 f = kzFogTerms(kzWorldPos);
  gl_FragColor = vec4(uColor * kzSpriteGain * 0.03 * vB * (1.0 - f.a), 1.0);
}`;

export function spriteMaterial(color, lines = false) {
  const uniforms = { ...KZ, ...SPRITES, uColor: { value: new THREE.Color().setRGB(...(color ?? [0, 0.48, 1]), THREE.LinearSRGBColorSpace) } };
  return new THREE.ShaderMaterial({
    name: lines ? 'glowworm_threads' : 'glowworm_points', uniforms,
    vertexShader: lines ? LVERT : VERT, fragmentShader: FOG_PARS + (lines ? LFRAG : FRAG),
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false,
  });
}
