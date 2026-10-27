// Kazan-yu walkaround runtime.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { TIERS, BLOOM, BLENDER_EXPOSURE_STOPS, EYE_HEIGHT, FOG } from './config.js';
import { detectTier, frameProbe, saveTier, savedTier, gpuString } from './tier.js';
import { Assets, AssetError, showFailures } from './assets.js';
import { KZ, makeStubEnvironment } from './materials.js';
import { PlanarReflection } from './water.js';
import { World } from './world.js';
import { Walker } from './walk.js';
import { Input } from './input.js';
import { Labels, buildPlaceSheet, LEVEL_NAMES, placeName } from './places.js';
import { Dollhouse } from './dollhouse.js';
import { SPRITES } from './sprites.js';
import { l2t, t2l, headingToYaw, yawToHeading } from './coords.js';

const Q = new URLSearchParams(location.search);
const DEBUG = Q.get('debug') === '1';
const $ = (id) => document.getElementById(id);
const loadText = (t, f) => { $('kz-load-text').textContent = t; if (f != null) $('kz-load-fill').style.width = `${Math.round(f * 100)}%`; };

let readyResolve, readyReject;
const ready = new Promise((res, rej) => { readyResolve = res; readyReject = rej; });
ready.catch(() => {});
const frameWaiters = [];
const nextFrames = (n = 1) => new Promise((r) => frameWaiters.push({ n, r }));
const kz = { ready, info: () => ({ state: 'loading' }), frames: nextFrames };
kz.teleport = async (...a) => { await ready; return kz.teleport(...a); };
kz.setCamera = async (...a) => { await ready; return kz.setCamera(...a); };
window.__kz = kz;

window.addEventListener('error', (e) => { if (!$('kz-error').hidden) return; showFailures([{ url: e.filename ?? '', status: 'JS', detail: e.message }], 'Script error'); });

main().catch((e) => {
  console.error(e);
  if (e instanceof AssetError) showFailures(e.failures);
  else showFailures([{ url: '', status: 'ERR', detail: e.stack ?? String(e) }], 'Startup failed');
  loadText('Failed to start');
  readyReject(e);
});

async function main() {
  const t0 = performance.now();
  const canvas = $('kz-canvas');
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance', stencil: false }); }
  catch (e) {
    // some dual-GPU setups refuse an explicit power preference; retry with defaults
    console.warn('[kz] high-performance context refused, retrying with defaults:', e.message);
    renderer = new THREE.WebGLRenderer({ canvas, antialias: false, stencil: false });
  }
  const gl = renderer.getContext();
  if (!(gl instanceof WebGL2RenderingContext)) throw new Error('WebGL2 is required');
  renderer.toneMapping = THREE.AgXToneMapping;
  renderer.toneMappingExposure = 2 ** BLENDER_EXPOSURE_STOPS;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.info.autoReset = false;
  const gpu = gpuString(gl);

  const tierInfo = detectTier(gl);
  let tier = tierInfo.tier; // asset tier (manifest)
  let rt = { ...TIERS[tier] }; // runtime settings (may be downgraded by the frame probe)
  let runtimeTier = tier;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color().setRGB(...FOG.color, THREE.LinearSRGBColorSpace);
  const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.05, 1500);
  camera.rotation.order = 'YXZ';
  scene.add(camera);

  // composer: linear HDR target -> (bloom) -> AgX + sRGB
  const target = new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, samples: rt.msaa });
  const composer = new EffectComposer(renderer, target);
  const renderPass = new RenderPass(scene, camera);
  composer.addPass(renderPass);
  const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), BLOOM.strength, BLOOM.radius, BLOOM.threshold);
  bloom.enabled = rt.bloom && Q.get('bloom') !== '0';
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  let reflectors = [];
  const makeReflectors = () => {
    reflectors.forEach((r) => r.rt.dispose());
    reflectors = Array.from({ length: rt.planar }, () => new PlanarReflection(rt.planarScale));
  };
  makeReflectors();
  function resize() {
    const w = innerWidth, h = innerHeight, dpr = Math.min(devicePixelRatio || 1, rt.dprMax);
    renderer.setPixelRatio(dpr); renderer.setSize(w, h, false);
    composer.setPixelRatio(dpr); composer.setSize(w, h);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    dollhouse?.resize(w, h);
    for (const r of reflectors) r.setSize(w * dpr, h * dpr);
  }
  let dollhouse = null;
  resize();
  addEventListener('resize', resize);

  loadText('Loading manifest', 0.05);
  const assets = new Assets(renderer);
  const manifest = await assets.manifest(tier);
  if (manifest.color?.exposureStops != null) renderer.toneMappingExposure = 2 ** manifest.color.exposureStops;
  const env = makeStubEnvironment(renderer);
  KZ.kzEnvB.value = env;
  const [placesDoc, spacesDoc] = await assets.all([assets.json(manifest.places), assets.json(manifest.spaces)]);
  const places = placesDoc.places;
  const placeById = new Map(places.map((p) => [p.id, p]));
  const spaces = spacesDoc.spaces;
  loadText('Loading materials', 0.15);
  const world = new World(renderer, scene, assets, manifest, env, tier);
  await world.init();
  // fixed pool of live lights for kz_runtime lights (Blender places); constant count, so zone changes never recompile
  const lightPool = manifest.zones.some((z) => z.lights?.length) ? Array.from({ length: 6 }, () => { const l = new THREE.PointLight(0xffffff, 0, 0, 2); scene.add(l); return l; }) : [];

  const walker = new Walker();
  const startId = Q.get('place') && placeById.has(Q.get('place')) ? Q.get('place') : manifest.start?.place ?? places[0].id;
  const start = placeById.get(startId);
  const startZone = start.zone ?? world.zoneOfSpace(start.id);
  const first = [startZone, ...world.zones.get(startZone).def.neighbors];
  let loadedCount = 0;
  world.onZoneLoaded = () => { loadedCount++; loadText(`Loading zones ${loadedCount}/${world.zones.size}`, 0.2 + 0.7 * (loadedCount / first.length)); };
  await assets.all(first.map((id) => world.load(id)));
  walker.setWorld(world.walkParts());
  let bvhDirty = false;
  world.onZoneLoaded = () => { bvhDirty = true; };

  // ---------- state ----------
  let mode = 'walk';
  let currentSpace = null, currentZone = startZone;
  const input = new Input(canvas, walker, { onUserMove: () => releaseFixed() });
  const labels = new Labels($('kz-labels'), places, walker);
  labels.max = rt.labelMax;
  if (Q.get('labels') === '0') labels.enabled = false;
  if (Q.get('fog') === '0') KZ.kzFogOn.value = 0;

  function spaceAt(feetL) {
    let best = null;
    for (const s of spaces) {
      if (feetL[2] < s.floor_z - 0.8 || (s.ceiling_z != null ? feetL[2] > s.ceiling_z : feetL[2] > s.floor_z + 6)) continue;
      if (!pointInRing(feetL, s.footprint)) continue;
      if (!best || Math.abs(s.floor_z - feetL[2]) < Math.abs(best.floor_z - feetL[2]) || (s.kind !== 'envelope' && best.kind === 'envelope')) best = s;
    }
    return best;
  }
  function zoneForPoint(pL) {
    const tp = l2t(pL);
    const g = walker.probeGround(tp.x, tp.z, tp.y + 0.5, 6);
    if (g) return g.zone;
    const s = spaceAt(pL);
    if (s) return s.zone;
    let best = null, bd = Infinity;
    for (const z of world.zones.values()) {
      const b = z.def.bounds;
      const d = Math.hypot(Math.max(b[0] - pL[0], 0, pL[0] - b[2]), Math.max(b[1] - pL[1], 0, pL[1] - b[3]));
      if (d < bd) { bd = d; best = z.def.id; }
    }
    return best;
  }
  async function ensureZones(zoneId) {
    const ids = [zoneId, ...world.zones.get(zoneId).def.neighbors];
    const missing = ids.filter((id) => world.zones.get(id).state !== 'ready');
    if (missing.length) {
      KZ.kzFogDensity.value = 0.6; // hold in thick mist while loading
      await assets.all(missing.map((id) => world.load(id)));
      walker.setWorld(world.walkParts()); bvhDirty = false;
    }
  }
  async function teleport(id) {
    const p = placeById.get(id);
    if (!p) throw new Error(`unknown place ${id}`);
    if (mode !== 'walk') setMode('walk');
    const zid = p.zone ?? world.zoneOfSpace(p.id);
    await ensureZones(zid);
    const eye = l2t(p.pos);
    walker.place(new THREE.Vector3(eye.x, eye.y - EYE_HEIGHT, eye.z));
    walker.yaw = headingToYaw(p.yaw_deg ?? 0); walker.pitch = ((p.pitch_deg ?? 0) * Math.PI) / 180;
    currentZone = walker.groundZone ?? zid;
    closeSheet();
    await nextFrames(2);
    return kz.info();
  }
  let fixedZone = null;
  async function setCamera(pos, tgt, fovDeg) {
    if (mode !== 'walk') setMode('walk');
    const zid = zoneForPoint(pos);
    await ensureZones(zid);
    walker.fixed = true; walker.autopilot = null;
    fixedZone = zid;
    camera.position.copy(l2t(pos));
    if (tgt) camera.lookAt(l2t(tgt));
    if (fovDeg) { camera.fov = fovDeg; camera.updateProjectionMatrix(); }
    const e = new THREE.Euler().setFromQuaternion(camera.quaternion, 'YXZ');
    walker.yaw = e.y; walker.pitch = e.x;
    walker.feet.copy(camera.position); walker.feet.y -= EYE_HEIGHT; walker.prevFeet.copy(walker.feet);
    await nextFrames(3);
    return kz.info();
  }
  function releaseFixed() {
    if (!walker.fixed) return;
    walker.place(walker.feet.clone().setY(walker.feet.y + 0.5));
    fixedZone = null;
  }

  // ---------- UI ----------
  const sheet = $('kz-sheet');
  function openSheet(title, body) { $('kz-sheet-title').textContent = title; $('kz-sheet-body').replaceChildren(body); sheet.hidden = false; input.enabled = false; document.exitPointerLock?.(); }
  function closeSheet() { sheet.hidden = true; input.enabled = mode === 'walk'; }
  $('kz-sheet-close').addEventListener('click', closeSheet);
  $('kz-btn-places').addEventListener('click', () => (sheet.hidden ? openSheet('Places', buildPlaceSheet(places, (id) => teleport(id))) : closeSheet()));
  $('kz-btn-settings').addEventListener('click', () => openSheet('Settings', settingsBody()));
  $('kz-btn-mode').addEventListener('click', () => setMode(mode === 'walk' ? 'dollhouse' : 'walk'));
  function settingsBody() {
    const d = document.createElement('div');
    const cur = savedTier();
    const row = document.createElement('div'); row.className = 'kz-row';
    for (const t of ['auto', 'low', 'high']) {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = t === 'auto' ? 'Auto' : t === 'low' ? 'Low' : 'High';
      if ((Q.get('tier') ?? cur) === t) b.classList.add('on');
      b.addEventListener('click', () => { saveTier(t); const u = new URL(location.href); u.searchParams.delete('tier'); location.href = u.href; });
      row.appendChild(b);
    }
    const g = document.createElement('div'); g.className = 'kz-group'; g.textContent = 'Quality';
    const lab = document.createElement('div'); lab.className = 'kz-row';
    const lb = document.createElement('button'); lb.type = 'button'; lb.textContent = labels.enabled ? 'Labels on' : 'Labels off'; lb.classList.toggle('on', labels.enabled);
    lb.addEventListener('click', () => { labels.enabled = !labels.enabled; lb.textContent = labels.enabled ? 'Labels on' : 'Labels off'; lb.classList.toggle('on', labels.enabled); if (!labels.enabled) labels.hideAll(); });
    lab.appendChild(lb);
    const hb = document.createElement('button'); hb.type = 'button'; hb.textContent = 'Debug HUD'; hb.classList.toggle('on', !$('kz-hud').hidden);
    hb.addEventListener('click', () => { $('kz-hud').hidden = !$('kz-hud').hidden; hb.classList.toggle('on', !$('kz-hud').hidden); });
    lab.appendChild(hb);
    const g2 = document.createElement('div'); g2.className = 'kz-group'; g2.textContent = 'View';
    const note = document.createElement('div'); note.className = 'kz-note';
    note.textContent = `Now: ${runtimeTier}${runtimeTier !== tier ? ` (assets ${tier})` : ''} · ${tierInfo.reason}${probeMs ? ` · ${probeMs.toFixed(1)} ms/frame` : ''}\n${gpu}`;
    // the model gallery (gallery.html, same site): every generator model, the material library, the slice places
    const g3 = document.createElement('div'); g3.className = 'kz-group'; g3.textContent = 'Explore';
    const ex = document.createElement('div'); ex.className = 'kz-row';
    const ga = document.createElement('a'); ga.className = 'kz-link'; ga.href = './gallery.html'; ga.textContent = 'Models & materials gallery';
    ex.appendChild(ga);
    d.append(g3, ex, g, row, g2, lab, note);
    return d;
  }
  function setMode(m) {
    mode = m;
    $('kz-btn-mode').textContent = m === 'walk' ? 'Dollhouse' : 'Walk';
    $('kz-btn-mode').classList.toggle('on', m === 'dollhouse');
    if (m === 'dollhouse') {
      document.exitPointerLock?.();
      input.enabled = false; labels.hideAll();
      KZ.kzFogOn.value = 0;
      const lv = spaces.find((s) => s.id === currentSpace)?.level ?? places.find((p) => p.zone === currentZone)?.level ?? 'ground';
      dollhouse.enter(lv);
    } else {
      dollhouse.exit();
      input.enabled = sheet.hidden;
      KZ.kzFogOn.value = Q.get('fog') === '0' ? 0 : 1;
    }
  }
  dollhouse = new Dollhouse(canvas, world, places, { onPick: (id) => teleport(id) });
  dollhouse.resize(innerWidth, innerHeight);
  dollhouse.renderer = renderer;

  // hint
  const hint = $('kz-hint');
  if (Q.get('hint') !== '0') {
    const touch = matchMedia('(pointer: coarse)').matches || navigator.maxTouchPoints > 0;
    hint.textContent = touch ? 'Left thumb to walk · drag right side to look' : 'Click to look around · WASD to walk · Shift to run';
    hint.hidden = false;
    setTimeout(() => (hint.style.opacity = '0'), 7000);
  }

  // ---------- HUD ----------
  const hud = $('kz-hud');
  hud.hidden = !DEBUG;
  let fps = 60, msAvg = 16, frameCount = 0, lastHud = 0, probeMs = null, lastInfo = {};
  function textureMB() {
    let b = assets.textureBytes;
    const px = renderer.domElement.width * renderer.domElement.height;
    b += px * 8 * 2 * (rt.msaa ? 1 + rt.msaa : 1); // composer targets (+ MSAA storage)
    if (rt.bloom) b += px * 8 * 0.7;
    for (const r of reflectors) b += r.rt.width * r.rt.height * 8;
    b += env.image.width * env.image.height * 8;
    return b / 1048576;
  }

  // ---------- frame ----------
  const clock = new THREE.Clock();
  const eye = new THREE.Vector3(), camDir = new THREE.Vector3();
  const frustum = new THREE.Frustum(), pm = new THREE.Matrix4(), tmpBox = new THREE.Box3();
  let probe = null;
  let lastFrameT = performance.now();

  function choosePlanar() {
    const cam = camera.position;
    pm.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    frustum.setFromProjectionMatrix(pm);
    const cands = [];
    for (const w of world.waterObjs) {
      const info = w.userData.kzWater;
      w.userData.uniforms.uHasPlanar.value = 0;
      if (!info.planar || !w.parent?.visible || cam.y < info.z) continue;
      tmpBox.copy(w.children[0].geometry.boundingBox);
      const d = tmpBox.distanceToPoint(cam);
      if (d > 70 || !frustum.intersectsBox(tmpBox)) continue;
      cands.push({ w, d });
    }
    cands.sort((a, b) => a.d - b.d);
    return cands.slice(0, reflectors.length).map((c) => c.w);
  }

  renderer.setAnimationLoop(() => {
    const now = performance.now();
    const dt = Math.min(clock.getDelta(), 0.1);
    renderer.info.reset();
    if (bvhDirty && mode === 'walk') { walker.setWorld(world.walkParts()); bvhDirty = false; }
    input.update();
    let visible;
    if (mode === 'walk') {
      walker.update(dt);
      if (!walker.fixed) {
        walker.eye(eye);
        camera.position.copy(eye);
        camera.rotation.set(walker.pitch, walker.yaw, 0, 'YXZ');
        if (camera.fov !== 70 && !kz._fovLocked) { camera.fov = 70; camera.updateProjectionMatrix(); }
      }
      const feetL = t2l(walker.fixed ? camera.position.clone().setY(camera.position.y - EYE_HEIGHT) : walker.feet);
      const s = spaceAt(feetL);
      currentSpace = s?.id ?? null;
      currentZone = walker.fixed ? fixedZone ?? currentZone : walker.groundZone ?? s?.zone ?? currentZone;
      visible = [currentZone, ...(world.zones.get(currentZone)?.def.neighbors ?? [])];
      world.setVisible(visible);
      // thicken the mist while a neighbouring zone is still loading
      const target = world.neighborsReady(currentZone) ? FOG.density : 0.25;
      KZ.kzFogDensity.value += (target - KZ.kzFogDensity.value) * Math.min(1, dt * 2);
      camera.updateMatrixWorld();
      world.updateUniforms(camera.position, now / 1000);
      world.update(dt);
      world.assignLights(lightPool, camera.position, camera.getWorldDirection(camDir));
      SPRITES.kzPxScale.value = renderer.domElement.height / (2 * Math.tan((camera.fov * Math.PI) / 360));
      // planar reflections
      const ws = choosePlanar();
      ws.forEach((w, i) => {
        const r = reflectors[i];
        // Low: the mirror pass draws only the water's own zone (it doubled the corridor's draw calls otherwise)
        const own = w.userData.zone;
        const hide = rt.planarOwnZone ? [...world.waterObjs, ...[...world.zones.values()].filter((z) => z.group && z.def.id !== own).map((z) => z.group)] : world.waterObjs;
        if (r.render(renderer, scene, camera, w.userData.kzWater.z, hide)) {
          const u = w.userData.uniforms;
          u.tReflect.value = r.rt.texture; u.uReflMatrix.value.copy(r.textureMatrix); u.uHasPlanar.value = 1;
        }
      });
      renderPass.camera = camera;
      composer.render(dt);
      labels.update(camera, world.visibleIds ?? []);
    } else {
      dollhouse.update();
      dollhouse.camera.updateMatrixWorld();
      world.updateUniforms(dollhouse.camera.position, now / 1000);
      for (const w of world.waterObjs) w.userData.uniforms.uHasPlanar.value = 0;
      renderPass.camera = dollhouse.camera;
      composer.render(dt);
      visible = world.visibleIds ?? [];
    }
    // stats
    const ft = now - lastFrameT; lastFrameT = now;
    fps += (1000 / Math.max(1, ft) - fps) * 0.05; msAvg += (ft - msAvg) * 0.05;
    frameCount++;
    if (probe) probe.tick(now);
    const inf = renderer.info;
    const feetL = t2l(walker.feet);
    lastInfo = {
      state: 'ready', mode, assetTier: tier, tier: runtimeTier, tierReason: tierInfo.reason, gpu, facts: tierInfo.facts,
      fps: +fps.toFixed(1), ms: +msAvg.toFixed(2), probeMs, drawCalls: inf.render.calls, triangles: inf.render.triangles,
      textures: inf.memory.textures, geometries: inf.memory.geometries, programs: inf.programs?.length ?? 0, textureMB: +textureMB().toFixed(1),
      pos: (walker.fixed ? t2l(camera.position) : t2l(eye)).map((v) => +v.toFixed(3)), feet: feetL.map((v) => +v.toFixed(3)),
      heading: +yawToHeading(walker.yaw).toFixed(1), pitch: +((walker.pitch * 180) / Math.PI).toFixed(1), fov: camera.fov,
      space: currentSpace, zone: currentZone, visibleZones: world.visibleIds ?? [], loadedZones: world.loadedIds(), zonesTotal: world.zones.size,
      walkTris: walker.triCount, liveLights: lightPool.filter((l) => l.intensity > 0).length, mixers: world.mixers.length, sprites: world.sprites.length, bvhMs: +(walker.buildMs ?? 0).toFixed(1), planar: reflectors.filter((r) => r).length,
      probeA: world.probeA, probeB: world.probeB, blend: +KZ.kzProbeBlend.value.toFixed(2),
      viewport: [innerWidth, innerHeight], dpr: renderer.getPixelRatio(), bytesLoaded: assets.bytes, interactiveMs: kz.interactiveMs ?? null,
    };
    if (!hud.hidden && now - lastHud > 250) {
      lastHud = now;
      const i = lastInfo;
      hud.textContent = `${i.fps.toFixed(0)} fps  ${i.ms.toFixed(1)} ms  tier ${i.tier}${i.tier !== i.assetTier ? `/${i.assetTier}` : ''} (${i.tierReason})\n` +
        `draws ${i.drawCalls}  tris ${(i.triangles / 1000).toFixed(1)}k  tex ${i.textures} (${i.textureMB} MB)  progs ${i.programs}\n` +
        `pos ${i.pos.map((v) => v.toFixed(2)).join(', ')}  hdg ${i.heading}\n` +
        `space ${i.space ?? '-'}  zone ${i.zone}  vis ${i.visibleZones.length}  loaded ${i.loadedZones.length}/${i.zonesTotal}\n` +
        `probe ${i.probeA ?? '-'} / ${i.probeB ?? '-'} ${i.blend}  planar ${reflectors.length}@${rt.planarScale}  dpr ${i.dpr}\n${gpu}`;
    }
    // where
    const sp = spaces.find((s) => s.id === currentSpace);
    const lvl = sp ? LEVEL_NAMES[sp.level] ?? sp.level : world.zones.get(currentZone)?.def.name ?? '';
    if ($('kz-where-level').textContent !== lvl) $('kz-where-level').textContent = lvl;
    const nm = sp ? placeName(placeById.get(sp.id) ?? sp) : world.zones.get(currentZone)?.def.name ?? '';
    if ($('kz-where-space').textContent !== nm) $('kz-where-space').textContent = nm;
    for (let k = frameWaiters.length - 1; k >= 0; k--) if (--frameWaiters[k].n <= 0) { frameWaiters[k].r(); frameWaiters.splice(k, 1); }
    void visible;
  });

  // ---------- go ----------
  await teleport(startId);
  setMode('walk');
  $('kz-loading').classList.add('done');
  kz.interactiveMs = Math.round(performance.now() - t0);
  console.info(`[kz] interactive in ${kz.interactiveMs} ms, tier ${tier} (${tierInfo.reason}), ${gpu}`);
  Object.assign(kz, {
    info: () => ({ ...lastInfo, renderer: { ...renderer.info.render }, memory: { ...renderer.info.memory } }),
    teleport, setCamera,
    places: () => places.map((p) => ({ id: p.id, name: p.name, level: p.level, kind: p.kind })),
    mode: (m) => { if (m) setMode(m); return mode; },
    walkPath: async (pts, opts) => { releaseFixed(); const v = pts.map((p) => l2t(p)); v.forEach((q) => (q.y -= EYE_HEIGHT)); return walker.walkPath(v, opts); },
    setFov: (f) => { kz._fovLocked = !!f; if (f) { camera.fov = f; camera.updateProjectionMatrix(); } },
    renderer, scene, camera, world, walker, THREE,
  });
  readyResolve(kz.info());
  if (!tierInfo.locked && tier === 'high') probe = frameProbe(45);
  // background-load everything else (Low budget fits it all), one zone at a time
  for (const z of world.zones.values()) {
    if (z.state === 'idle') { try { await world.load(z.def.id); } catch (e) { if (e instanceof AssetError) showFailures(assets.failures); } }
  }
  kz.allLoadedMs = Math.round(performance.now() - t0);
  console.info(`[kz] all ${world.zones.size} zones loaded in ${kz.allLoadedMs} ms, ${(assets.bytes / 1048576).toFixed(1)} MB`);
  if (probe) {
    probeMs = await probe.done;
    if (probeMs > 21 && runtimeTier === 'high') {
      runtimeTier = 'low'; rt = { ...TIERS.low };
      bloom.enabled = false; labels.max = rt.labelMax; makeReflectors(); resize();
      console.info(`[kz] frame probe ${probeMs.toFixed(1)} ms -> runtime tier low`);
    }
    probe = null;
  }
}

function pointInRing(p, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi + 1e-30) + xi) inside = !inside;
  }
  return inside;
}
