// Shared shell for the mist prototypes: renderer, HUD (main-thread fps/ms AND worker step ms), Low/High and
// worker/main toggles, procedural noise, stand-in materials, first-person walk controls and a GPU bench.
// three.js is the pinned runtime copy (web/node_modules/three, r186) through the page's import map.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
import { MIST_GLSL } from './mist.js';

export const params = new URLSearchParams(location.search);

// ------------------------------------------------------------------ noise
const VS = `precision highp float; in vec3 position; out vec2 vUv; void main(){ vUv = position.xy*0.5+0.5; gl_Position = vec4(position.xy,0.,1.); }`;
const NOISE_FS = /* glsl */`
precision highp float; in vec2 vUv; out vec4 o; uniform float uZ; uniform float u3;
vec3 g3(vec3 p){ p = vec3(dot(p,vec3(127.1,311.7,74.7)), dot(p,vec3(269.5,183.3,246.1)), dot(p,vec3(113.5,271.9,124.6))); return -1.0 + 2.0*fract(sin(p)*43758.5453); }
float gn(vec3 p, vec3 P){
  vec3 i = floor(p), f = fract(p); vec3 u = f*f*f*(f*(f*6.-15.)+10.);
  #define G(o) dot(g3(mod(i+o,P)), f-o)
  return mix(mix(mix(G(vec3(0,0,0)),G(vec3(1,0,0)),u.x), mix(G(vec3(0,1,0)),G(vec3(1,1,0)),u.x), u.y),
             mix(mix(G(vec3(0,0,1)),G(vec3(1,0,1)),u.x), mix(G(vec3(0,1,1)),G(vec3(1,1,1)),u.x), u.y), u.z);
}
vec3 h3(vec3 p){ return fract(sin(vec3(dot(p,vec3(127.1,311.7,74.7)), dot(p,vec3(269.5,183.3,246.1)), dot(p,vec3(113.5,271.9,124.6))))*43758.5453); }
float worley(vec3 p, vec3 P){ vec3 i = floor(p), f = fract(p); float F = 8.0;
  for (int z=-1;z<=1;z++) for (int y=-1;y<=1;y++) for (int x=-1;x<=1;x++){ vec3 o3 = vec3(x,y,z); if (u3 < 0.5 && z != 0) continue; vec3 r = o3 + h3(mod(i+o3,P)) - f; F = min(F, dot(r,r)); }
  return sqrt(F); }
float fbm(vec3 p, float P0, int oct){ float a = 0.0, amp = 0.5, n = 0.0, P = P0; for (int k = 0; k < 6; k++){ if (k >= oct) break; vec3 PP = u3 > 0.5 ? vec3(P) : vec3(P, P, 1e4); a += amp*gn(p*vec3(P, P, u3 > 0.5 ? P : 1.0), PP); n += amp; amp *= 0.5; P *= 2.0; } return a/n*0.5 + 0.5; }
void main(){
  vec3 p = vec3(vUv, u3 > 0.5 ? uZ : 0.0);
  // billowy: 1 - worley blended into fbm gives puffy cauliflower-free cells for the mist detail
  float wo = worley(p*vec3(6.0, 6.0, u3 > 0.5 ? 6.0 : 1.0), vec3(6.0, 6.0, u3 > 0.5 ? 6.0 : 1e4));
  float f1 = fbm(p, 4.0, 5), f2 = fbm(p + 0.37, 8.0, 4);
  float billow = clamp(f1*0.75 + (1.0 - wo)*0.45 - 0.12, 0.0, 1.0);
  o = vec4(billow, f1, wo, f2);
}`;
export function bakeNoise(renderer) {
  const mat = new THREE.RawShaderMaterial({ glslVersion: THREE.GLSL3, vertexShader: VS, fragmentShader: NOISE_FS, uniforms: { uZ: { value: 0 }, u3: { value: 0 } }, depthTest: false, depthWrite: false });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat); const cam = new THREE.Camera();
  const rt2 = new THREE.WebGLRenderTarget(256, 256, { wrapS: THREE.RepeatWrapping, wrapT: THREE.RepeatWrapping, minFilter: THREE.LinearMipmapLinearFilter, magFilter: THREE.LinearFilter, generateMipmaps: true, depthBuffer: false });
  renderer.setRenderTarget(rt2); renderer.render(quad, cam);
  const N = 32;
  const rt3 = new THREE.WebGL3DRenderTarget(N, N, N, { depthBuffer: false });
  const t3 = rt3.texture; t3.wrapS = t3.wrapT = t3.wrapR = THREE.RepeatWrapping; t3.minFilter = t3.magFilter = THREE.LinearFilter; t3.generateMipmaps = false;
  mat.uniforms.u3.value = 1;
  for (let z = 0; z < N; z++) { mat.uniforms.uZ.value = (z + 0.5) / N; renderer.setRenderTarget(rt3, z); renderer.render(quad, cam); }
  renderer.setRenderTarget(null); mat.dispose(); quad.geometry.dispose();
  return { n2: rt2.texture, n3: t3, bytes: 256 * 256 * 4 * 4 / 3 + N * N * N * 4 };
}

// ------------------------------------------------------------------ CPU noise / geometry helpers
export function mulberry(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
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
export function lumpify(geo, amp, freq, seed = 3, oct = 4) {
  const nz = makeNoise3(seed);
  geo = geo.index ? geo : geo; geo.deleteAttribute('uv'); geo.deleteAttribute('normal'); geo = mergeVertices(geo); geo.computeVertexNormals();
  const pos = geo.attributes.position, nor = geo.attributes.normal;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i); const d = nz(x * freq, y * freq, z * freq, oct) * amp;
    pos.setXYZ(i, x + nor.getX(i) * d, y + nor.getY(i) * d, z + nor.getZ(i) * d);
  }
  geo.computeVertexNormals(); return geo;
}
// fake lightmap in vertex colours: ambient + point lights (wrap diffuse, inverse square) * optional AO
export function bakeVertexLight(geo, lights, ambient = [0.012, 0.014, 0.016], aoFn = null) {
  geo.computeVertexNormals();
  const pos = geo.attributes.position, nor = geo.attributes.normal; const col = new Float32Array(pos.count * 3);
  const p = new THREE.Vector3(), n = new THREE.Vector3(), L = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    p.fromBufferAttribute(pos, i); n.fromBufferAttribute(nor, i);
    let r = ambient[0], g = ambient[1], b = ambient[2];
    for (const l of lights) {
      L.set(l.pos[0], l.pos[1], l.pos[2]).sub(p); const d2 = Math.max(L.lengthSq(), 0.05); L.normalize();
      const w = l.wrap ?? 0.3; const ndl = Math.max((n.dot(L) + w) / (1 + w), 0); const f = ndl * l.i / (d2 * (l.falloff ?? 1) + 0.2);
      r += l.color[0] * f; g += l.color[1] * f; b += l.color[2] * f;
    }
    const ao = aoFn ? aoFn(p, n) : 1; col[i * 3] = r * ao; col[i * 3 + 1] = g * ao; col[i * 3 + 2] = b * ao;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3)); return geo;
}

// ------------------------------------------------------------------ materials (all apply the mist layer)
const NOISE_U = `uniform sampler2D tNoise; uniform float uTime;`;
export function rockMaterial(app, { tint = [0.09, 0.08, 0.075], wet = 0.5, scale = 0.6 } = {}) {
  return app.mistMaterial({
    uniforms: { uTint: { value: new THREE.Vector3(...tint) }, uWet: { value: wet }, uScale: { value: scale } },
    vertexShader: `attribute vec3 color; varying vec3 vCol; varying vec3 vW; varying vec3 vN;
      void main(){ vec4 w = modelMatrix*vec4(position,1.); vW = w.xyz; vCol = color; vN = normalize(mat3(modelMatrix)*normal); gl_Position = projectionMatrix*viewMatrix*w; }`,
    fragmentShader: `${NOISE_U} uniform vec3 uTint; uniform float uWet; uniform float uScale; varying vec3 vCol; varying vec3 vW; varying vec3 vN;
      void main(){
        vec3 an = abs(vN); vec2 uv = an.y > max(an.x, an.z) ? vW.xz : (an.x > an.z ? vW.zy : vW.xy);
        vec4 n = texture(tNoise, uv*uScale*0.21); float g = texture(tNoise, uv*uScale*1.3).a;
        vec3 alb = uTint*(0.5 + 0.9*n.g)*(0.75 + 0.5*g);
        vec3 V = normalize(cameraPosition - vW); vec3 N = normalize(vN);
        float fr = pow(1.0 - max(dot(V, N), 0.0), 4.0);
        vec3 col = alb*vCol*1.25 + fr*uWet*vCol*0.45;
        col = mistApply(col, vW);
        gl_FragColor = vec4(col, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
}
export function emissiveMaterial(app, color, i = 1) {
  return app.mistMaterial({
    uniforms: { uCol: { value: new THREE.Vector3(color[0] * i, color[1] * i, color[2] * i) } },
    vertexShader: `varying vec3 vW; varying vec2 vUv; void main(){ vUv = uv; vec4 w = modelMatrix*vec4(position,1.); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }`,
    fragmentShader: `${NOISE_U} uniform vec3 uCol; varying vec3 vW; varying vec2 vUv;
      void main(){ vec2 g = abs(fract(vUv*vec2(3.0, 4.0)) - 0.5); float lat = smoothstep(0.43, 0.5, max(g.x, g.y));
        vec3 col = uCol*(1.0 - 0.93*lat); col = mistApply(col, vW); gl_FragColor = vec4(col, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
}
// Stand-in water (the water agent owns the real surface): dark mirror, lantern glints on a noisy normal,
// teal glow from the bed. Only here so the mist has something to sit on.
export function waterMaterial(app, { glow = [0.0, 0.05, 0.045], rough = 1.0 } = {}) {
  return app.mistMaterial({
    uniforms: { uGlow: { value: new THREE.Vector3(...glow) }, uRough: { value: rough } },
    vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }`,
    fragmentShader: `${NOISE_U} uniform vec3 uGlow; uniform float uRough; varying vec3 vW;
      void main(){
        vec2 p = vW.xz;
        float a = texture(tNoise, p*0.21 + vec2(uTime*0.013, uTime*0.008)).b, b = texture(tNoise, p*0.47 - vec2(uTime*0.017, -uTime*0.011)).b;
        float ax = texture(tNoise, p*0.21 + vec2(0.003, 0.0) + vec2(uTime*0.013, uTime*0.008)).b, bz = texture(tNoise, p*0.47 + vec2(0.0, 0.003) - vec2(uTime*0.017, -uTime*0.011)).b;
        vec3 N = normalize(vec3((a - ax)*1.2*uRough, 1.0, (b - bz)*1.2*uRough));
        vec3 V = normalize(cameraPosition - vW); vec3 R = reflect(-V, N);
        float F = 0.02 + 0.98*pow(1.0 - max(dot(N, V), 0.0), 5.0);
        vec3 refl = vec3(0.004, 0.005, 0.006);
        for (int i = 0; i < ${6}; i++){ vec3 L = uMistLPos[i].xyz - vW; float d = length(L); vec3 l = L/d;
          float sp = pow(max(dot(R, l), 0.0), 900.0)*60.0 + pow(max(dot(R, l), 0.0), 60.0)*1.2;
          refl += uMistLCol[i].rgb*sp/(1.0 + d*d*uMistLPos[i].w*0.4); }
        float caust = texture(tNoise, p*0.33 + N.xz*0.2 + uTime*0.01).b;
        vec3 bed = uGlow*(0.6 + 0.8*caust);
        vec3 col = bed*(1.0 - F) + refl*F*1.6;
        col = mistApply(col, vW);
        gl_FragColor = vec4(col, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
}

// ------------------------------------------------------------------ app shell
export function createApp({ title, cams, zone, walk = null }) {
  const canvas = document.createElement('canvas'); document.body.appendChild(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.toneMapping = THREE.AgXToneMapping; renderer.toneMappingExposure = parseFloat(params.get('exp') ?? '1.0');
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.info.autoReset = false;
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x020202);
  const camera = new THREE.PerspectiveCamera(60, 1, 0.05, 300);
  const controls = new OrbitControls(camera, canvas); controls.enableDamping = true;
  const noise = bakeNoise(renderer); zone.setNoise(noise.n2, noise.n3);
  const shared = { tNoise: { value: noise.n2 }, uTime: { value: 0 } };

  const state = {
    tier: params.get('tier') === 'high' ? 'high' : (params.get('tier') === 'low' ? 'low' : (/Android|iPhone|iPad|Mobile/i.test(navigator.userAgent) ? 'low' : 'high')),
    mode: params.get('mode') === 'main' ? 'main' : 'worker',
    t: parseFloat(params.get('t') ?? '0'), paused: false, camIndex: parseInt(params.get('cam') ?? '0', 10),
    walking: !!walk && params.get('walk') !== '0' && !params.has('cam'),
    mistOn: params.get('mist') !== '0',
  };
  const mats = [];
  const app = {
    THREE, renderer, scene, camera, controls, zone, state, shared, noise, params, update: null, groups: {},
    mistMaterial({ uniforms = {}, vertexShader, fragmentShader, ...rest }) {
      const m = new THREE.ShaderMaterial({ uniforms: { ...zone.uniforms, ...shared, ...uniforms }, vertexShader,
        fragmentShader: MIST_GLSL + fragmentShader, defines: {}, ...rest });
      mats.push(m); setDefines(m); return m;
    },
  };
  function setDefines(m) {
    if (state.tier === 'high') { m.defines.MIST_HIGH = ''; m.defines.MIST_SLICES = 14; delete m.defines.MIST_NL; } else { delete m.defines.MIST_HIGH; delete m.defines.MIST_SLICES; m.defines.MIST_NL = 3; }
    m.needsUpdate = true;
  }

  // HUD
  const hud = document.createElement('div'); hud.id = 'hud';
  hud.innerHTML = `<div class="ttl">${title}</div><div id="stats">…</div>
    <div class="row"><button id="bTier"></button><button id="bMode"></button><button id="bMist">mist</button>
    <button id="bCam">camera</button>${walk ? '<button id="bWalk">walk</button>' : ''}<button id="bBench">bench</button></div><div id="bench"></div>`;
  document.body.appendChild(hud);
  const style = document.createElement('style');
  style.textContent = `html,body{margin:0;height:100%;background:#020202;overflow:hidden;font:12px/1.35 ui-monospace,Menlo,monospace;color:#e6eeee}
  canvas{display:block;width:100vw;height:100vh;touch-action:none}
  #hud{position:fixed;left:8px;top:8px;background:rgba(6,10,12,.62);padding:7px 9px;border-radius:8px;max-width:min(94vw,380px);backdrop-filter:blur(4px)}
  #hud .ttl{font-weight:700;color:#ffd8a0;margin-bottom:2px} #stats{white-space:pre}
  #hud .row{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}
  #hud button{font:inherit;background:#1c2a2c;color:#e6eeee;border:1px solid #3d6466;border-radius:5px;padding:5px 8px}
  #hud button.on{background:#7a3d12;border-color:#d07a2e} #bench{white-space:pre;color:#ffd9a8;margin-top:4px}
  body.clean #hud{display:none}
  #hint{position:fixed;right:10px;bottom:10px;color:#cfd8d8;opacity:.7;font-size:11px;text-align:right} body.clean #hint{display:none}`;
  document.head.appendChild(style);
  if (params.has('clean')) document.body.classList.add('clean');
  const $ = id => hud.querySelector('#' + id);

  const label = () => {
    $('bTier').textContent = state.tier === 'high' ? 'High' : 'Low'; $('bTier').classList.toggle('on', state.tier === 'low');
    $('bMode').textContent = state.mode === 'worker' ? 'sim: worker' : 'sim: main thread'; $('bMode').classList.toggle('on', state.mode === 'main');
    $('bMist').classList.toggle('on', !state.mistOn);
    if (walk) $('bWalk').classList.toggle('on', state.walking);
  };
  const restartSim = () => { zone.start(state.tier, state.mode); app.onRestart?.(); };
  const setTier = t => { state.tier = t; mats.forEach(setDefines); resize(); restartSim(); label(); };
  $('bTier').onclick = () => setTier(state.tier === 'high' ? 'low' : 'high');
  $('bMode').onclick = () => { state.mode = state.mode === 'worker' ? 'main' : 'worker'; restartSim(); label(); };
  $('bMist').onclick = () => { state.mistOn = !state.mistOn; zone.uniforms.uMistOn.value = state.mistOn ? 1 : 0; label(); };
  const setCam = i => {
    state.camIndex = (i + cams.length) % cams.length; const c = cams[state.camIndex];
    camera.position.set(...c.pos); controls.target.set(...c.target); camera.fov = c.fov ?? 60; camera.updateProjectionMatrix(); controls.update();
  };
  $('bCam').onclick = () => { if (walk) { state.walking = false; label(); } setCam(state.camIndex + 1); };
  if (walk) $('bWalk').onclick = () => { state.walking = !state.walking; label(); };
  zone.uniforms.uMistOn.value = state.mistOn ? 1 : 0;

  function resize() {
    const dpr = Math.min(window.devicePixelRatio, 2) * (state.tier === 'low' ? 0.75 : 1);
    renderer.setPixelRatio(dpr); renderer.setSize(window.innerWidth, window.innerHeight, false);
    camera.aspect = window.innerWidth / window.innerHeight; camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);

  // ---- first-person walk (WASD / arrows + mouse drag; touch: left half moves, right half looks)
  const W = { yaw: walk?.yaw ?? 0, pitch: walk?.pitch ?? -0.12, pos: new THREE.Vector3(...(walk?.start ?? [0, 0, 0])), vel: new THREE.Vector3(), keys: {}, touchMove: null, touchLook: null };
  app.walker = W;
  if (walk) {
    addEventListener('keydown', e => { W.keys[e.code] = true; if (/Key[WASD]|Arrow/.test(e.code) && !state.walking) { state.walking = true; label(); } });
    addEventListener('keyup', e => { W.keys[e.code] = false; });
    let drag = null;
    canvas.addEventListener('pointerdown', e => {
      if (!state.walking) return;
      const left = e.pointerType === 'touch' && e.clientX < innerWidth * 0.5;
      drag = { id: e.pointerId, x: e.clientX, y: e.clientY, left, x0: e.clientX, y0: e.clientY };
      if (left) W.touchMove = { dx: 0, dy: 0 };
    });
    addEventListener('pointermove', e => {
      if (!drag || drag.id !== e.pointerId || !state.walking) return;
      if (drag.left) { W.touchMove = { dx: (e.clientX - drag.x0) / 60, dy: (e.clientY - drag.y0) / 60 }; }
      else { W.yaw -= (e.clientX - drag.x) * 0.004; W.pitch = Math.max(-1.2, Math.min(1.0, W.pitch - (e.clientY - drag.y) * 0.004)); }
      drag.x = e.clientX; drag.y = e.clientY;
    });
    addEventListener('pointerup', e => { if (drag && drag.id === e.pointerId) { if (drag.left) W.touchMove = null; drag = null; } });
    const hint = document.createElement('div'); hint.id = 'hint'; hint.textContent = 'WASD / arrows + drag to look · touch: left side walks, right side looks'; document.body.appendChild(hint);
  }
  function stepWalk(dt) {
    let f = 0, s = 0;
    if (W.keys.KeyW || W.keys.ArrowUp) f += 1; if (W.keys.KeyS || W.keys.ArrowDown) f -= 1;
    if (W.keys.KeyD) s += 1; if (W.keys.KeyA) s -= 1;
    if (W.keys.ArrowLeft) W.yaw += 1.6 * dt; if (W.keys.ArrowRight) W.yaw -= 1.6 * dt;
    if (W.touchMove) { f -= Math.max(-1, Math.min(1, W.touchMove.dy)); s += Math.max(-1, Math.min(1, W.touchMove.dx)); }
    const speed = (W.keys.ShiftLeft ? 2.6 : 1.3);
    const fx = -Math.sin(W.yaw), fz = -Math.cos(W.yaw);
    const tvx = (fx * f + Math.cos(W.yaw) * s) * speed, tvz = (fz * f - Math.sin(W.yaw) * s) * speed;
    const a = 1 - Math.exp(-8 * dt); W.vel.x += (tvx - W.vel.x) * a; W.vel.z += (tvz - W.vel.z) * a;
    const nx = W.pos.x + W.vel.x * dt, nz = W.pos.z + W.vel.z * dt;
    if (!walk.blocked(nx, W.pos.z)) W.pos.x = nx; else W.vel.x = 0;
    if (!walk.blocked(W.pos.x, nz)) W.pos.z = nz; else W.vel.z = 0;
    const bob = Math.sin(performance.now() / 1000 * 7.5) * 0.015 * Math.min(1, Math.hypot(W.vel.x, W.vel.z));
    camera.position.set(W.pos.x, (walk.floorY?.(W.pos.x, W.pos.z) ?? 0) + 1.6 + bob, W.pos.z);
    camera.rotation.set(W.pitch, W.yaw, 0, 'YXZ');
  }

  // ---- debug overlay (?field=1): the packed sim field, density in white, heat in red, as the worker sends it
  let fieldCv = null, fieldAt = 0;
  if (params.has('field')) { fieldCv = document.createElement('canvas'); fieldCv.style.cssText = 'position:fixed;right:8px;top:8px;image-rendering:pixelated;border:1px solid #3d6466;background:#000;max-width:46vw'; document.body.appendChild(fieldCv); }
  function drawField(now) {
    if (!fieldCv || now - fieldAt < 150 || !zone.cfg) return; fieldAt = now;
    const { nx, ny } = zone.cfg; const sc = Math.max(1, Math.floor(Math.min(700 / nx, 300 / ny)));
    if (fieldCv.width !== nx) { fieldCv.width = nx; fieldCv.height = ny; fieldCv.style.width = nx * sc + 'px'; fieldCv.style.height = ny * sc + 'px'; }
    const g = fieldCv.getContext('2d'); const img = g.createImageData(nx, ny); const src = zone.texB.image.data;
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { const a = (j * nx + i) * 4, b = ((ny - 1 - j) * nx + i) * 4; // flip so +Z is down... keep world X right, Z down
      const dd = src[a]; img.data[b] = Math.min(255, dd + src[a + 1] * 0.4); img.data[b + 1] = dd; img.data[b + 2] = dd; img.data[b + 3] = 255; }
    g.putImageData(img, 0, 0);
  }

  // ---- stats
  const ft = []; let last = performance.now(), statsAt = 0, calls = 0, tris = 0; const rms = [];
  function loop(now, fixedDt) {
    if (fixedDt === undefined) requestAnimationFrame(loop);
    const dt = fixedDt ?? Math.min((now - last) / 1000, 0.1); last = now;
    ft.push(dt * 1000); if (ft.length > 120) ft.shift();
    if (!state.paused) state.t += dt;
    shared.uTime.value = state.t;
    if (state.walking && walk) stepWalk(dt); else if (!params.has('follow')) { controls.enabled = true; controls.update(); }
    controls.enabled = !state.walking;
    const j0 = performance.now();
    app.update?.(state.t, dt);
    zone.update(now, state.t);
    renderer.info.reset(); renderer.render(scene, camera);
    rms.push(performance.now() - j0); if (rms.length > 120) rms.shift();
    drawField(now);
    calls = renderer.info.render.calls; tris = renderer.info.render.triangles;
    if (now - statsAt > 400) {
      statsAt = now;
      const avg = ft.reduce((a, b) => a + b, 0) / ft.length, worst = Math.max(...ft); const st = zone.stat; const c = zone.cfg;
      const js = rms.reduce((a, b) => a + b, 0) / rms.length;
      $('stats').textContent =
        `main  ${(1000 / avg).toFixed(0)} fps  ${avg.toFixed(2)} ms (worst ${worst.toFixed(1)})\n` +
        `      JS+submit ${js.toFixed(2)} ms · mist JS ${st.mainMsAvg.toFixed(3)} ms (max ${(st.mainMsMax ?? 0).toFixed(2)})\n` +
        `${state.mode === 'worker' ? 'worker' : 'main! '} step ${st.stepMs.toFixed(2)} ms (p95 ${st.stepP95.toFixed(2)}) @ ${st.fpsSim} Hz\n` +
        `grid  ${c ? c.nx + '×' + c.ny : '-'} @ ${c ? (c.h * 100).toFixed(0) : '-'} cm · ${st.fluid} fluid · ${zone.o.tiers[state.tier].iters} it\n` +
        `mem   sim ${(st.simBytes / 1048576).toFixed(2)} MB · tex ${((st.texBytes + noise.bytes) / 1048576).toFixed(2)} MB\n` +
        `gpu   ${calls} calls ${(tris / 1000).toFixed(0)}k tris ${renderer.domElement.width}×${renderer.domElement.height}`;
    }
  }

  // GPU bench (EXT_disjoint_timer_query is not exposed here): N frames into an offscreen target, then a 1 px
  // readPixels to sync. Reports ms/frame with the mist on and off (same pass, same shaders, uMistOn toggled).
  app.bench = async function ({ w = 1600, h = 900, n = 40 } = {}) {
    const rt = new THREE.WebGLRenderTarget(w, h, { type: THREE.UnsignedByteType }); const px = new Uint8Array(4);
    const aspect = camera.aspect; camera.aspect = w / h; camera.updateProjectionMatrix();
    const run = () => { renderer.setRenderTarget(rt); for (let i = 0; i < 3; i++) renderer.render(scene, camera); renderer.readRenderTargetPixels(rt, 0, 0, 1, 1, px);
      const t0 = performance.now(); for (let i = 0; i < n; i++) renderer.render(scene, camera); renderer.readRenderTargetPixels(rt, 0, 0, 1, 1, px); return (performance.now() - t0) / n; };
    const on = zone.uniforms.uMistOn.value;
    zone.uniforms.uMistOn.value = 1; const a = run(); zone.uniforms.uMistOn.value = 0; const b = run(); zone.uniforms.uMistOn.value = 1; const a2 = run();
    zone.uniforms.uMistOn.value = on; renderer.setRenderTarget(null); rt.dispose(); camera.aspect = aspect; camera.updateProjectionMatrix();
    const withMist = Math.min(a, a2);
    return { res: `${w}x${h}`, tier: state.tier, withMist: +withMist.toFixed(3), noMist: +b.toFixed(3), mist: +(withMist - b).toFixed(3) };
  };
  $('bBench').onclick = async () => { $('bench').textContent = 'running…'; await new Promise(r => setTimeout(r, 50)); const r = await app.bench(); $('bench').textContent = Object.entries(r).map(([k, v]) => `${k}: ${v}`).join('\n'); };

  app.start = () => {
    resize(); setCam(state.camIndex);
    if (params.has('pos')) { camera.position.set(...params.get('pos').split(',').map(Number)); controls.target.set(...params.get('tgt').split(',').map(Number)); controls.update(); }
    if (walk && params.has('wpos')) { const v = params.get('wpos').split(',').map(Number); W.pos.set(v[0], 0, v[1]); if (v.length > 2) W.yaw = v[2]; if (v.length > 3) W.pitch = v[3]; }
    restartSim(); label();
    if (params.has('offline')) {
      // frame-locked rendering for clips: the page only advances when asked, so GPU contention on the shared
      // machine cannot drop frames (use with mode=main so the solver steps on the same clock)
      let clock = 0;
      app.offlineFrame = (dt = 1 / 30, q = 0.9) => { clock += dt * 1000; loop(clock, dt); return renderer.domElement.toDataURL('image/jpeg', q); };
    } else requestAnimationFrame(loop);
  };
  window.__app = app;
  window.__stats = () => { const st = zone.stat; const avg = ft.reduce((a, b) => a + b, 0) / Math.max(1, ft.length);
    return { fps: 1000 / avg, frameMs: avg, worst: Math.max(...ft), jsMs: rms.reduce((a, b) => a + b, 0) / Math.max(1, rms.length), mistMainMs: st.mainMsAvg, mistMainMax: st.mainMsMax, stepMs: st.stepMs, stepP95: st.stepP95, simHz: st.fpsSim, grid: zone.cfg ? `${zone.cfg.nx}x${zone.cfg.ny}` : '', fluid: st.fluid, simMB: st.simBytes / 1048576, texMB: (st.texBytes + noise.bytes) / 1048576, calls, tris, tier: state.tier, mode: state.mode, ready: zone.ready, w: renderer.domElement.width, h: renderer.domElement.height }; };
  return app;
}

// a simple guest: capsule body + head, light yukata colour, walking along a polyline (world XZ) at speed
export function makeGuest(app, color = [0.75, 0.7, 0.62]) {
  const THREE_ = THREE; const g = new THREE_.Group();
  const mat = app.mistMaterial({
    uniforms: { uCol: { value: new THREE_.Vector3(...color) } },
    vertexShader: `varying vec3 vW; varying vec3 vN; void main(){ vec4 w = modelMatrix*vec4(position,1.); vW = w.xyz; vN = normalize(mat3(modelMatrix)*normal); gl_Position = projectionMatrix*viewMatrix*w; }`,
    fragmentShader: `${NOISE_U} uniform vec3 uCol; varying vec3 vW; varying vec3 vN;
      void main(){ vec3 N = normalize(vN); vec3 c = uMistAmb*2.0 + uMistGlow*max(-N.y, 0.0)*2.0;
        for (int i = 0; i < 6; i++){ vec3 L = uMistLPos[i].xyz - vW; float d2 = dot(L, L); c += uMistLCol[i].rgb*max(dot(N, L*inversesqrt(d2)) + 0.2, 0.0)/(1.0 + d2*uMistLPos[i].w); }
        vec3 col = uCol*c*0.6; col = mistApply(col, vW); gl_FragColor = vec4(col, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const body = new THREE_.Mesh(new THREE_.CapsuleGeometry(0.2, 1.05, 4, 12), mat); body.position.y = 0.75; body.scale.set(1, 1, 0.75);
  const robe = new THREE_.Mesh(new THREE_.CylinderGeometry(0.2, 0.3, 0.9, 14, 1, true), mat); robe.position.y = 0.55;
  const head = new THREE_.Mesh(new THREE_.SphereGeometry(0.12, 14, 10), mat); head.position.y = 1.55;
  g.add(body, robe, head); return g;
}
