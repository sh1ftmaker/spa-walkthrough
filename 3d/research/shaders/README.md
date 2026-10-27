# Kazan-yu shader kit: anti-tiling, macro variation and runtime material shaders

Research and prototype for the owner's request: tile materials far more effectively, and make most
materials runtime shaders instead of plain texture materials. three.js r186, WebGLRenderer, WebGL2,
`onBeforeCompile` on top of the runtime's own patch (`web/src/materials.js`). Lighting is baked
irradiance only, so all of this sits in albedo / roughness / normal and does not touch the bake.

- Kit: `kzshader.js` (GLSL + `kzShade(material, cfg)`), per-material table: `kzmaterials.js`
- Demo: `demo/index.html` → https://terminal.sels.tech/lp/8742/3d/research/shaders/demo/index.html
  (query: `scene=cave|corridor|swatch&wall=<id>&floor=<id>&mode=0..3&tier=low|high&source=auto|lib|plate`)
- Texture prep: `tools/prep_textures.py` (plates → PBR sets), renders/benchmarks: `tools/kzshot.mjs`
- Renders: `3d/renders/shaders/` (before/after pairs 1600 px, swatch sheets, phone 390×844 shots,
  `corridor_walk_4modes.mp4`)

## 1. What works best, per family (short version)

| family | best technique | why |
|---|---|---|
| Cave rock (basalt_wet / basalt_dry) | **hybrid**: Codex plate, hex-tiled inside a world-space biplanar projection, second plate height-blended at 6–7 m, ALU macro (brightness / hue / wet patches / run-off streaks), distance-faded detail, + procedural fracture-facet chips and vesicles near the camera (High) | Plate gives the photographic richness the library sets lack; hex + rotation kills the repeat; biplanar needs no UVs on cave meshes; facets give crisp chips at 0.5–3 m |
| Obsidian | **hybrid**: plate colour/veins, relief replaced by flat 3D-Voronoi facets (constant gradient per cell) | Reflections break into long clean planes with ridges, which is what the review asked for |
| Lava (crust field, flow) | **hybrid**: hex-tiled crust plate, its glowing seams as emissive, modulated by macro (hot vs cooled regions) and a flowing "breathing" noise | Plate seams look far better than my procedural cells; the modulation adds life for ~0 cost |
| Black sand, ash clay, paving, iron, bronze, washi | **anti-tiled texture** (hex + macro + detail), plate source | Repetition gone, richness from the plate; sand gets procedural ripples + roughness glints in mode 3 |
| Hinoki, lacquer | **board shuffle**: each board picks one of the plate's N boards, random offset/flip, staggered end joints, ±11 % per-board tint | 1 tap per map; planks must not be hex-blended |
| Tatami, noren, bamboo, rope | **plain + macro** | Regular weaves/poles: repetition is correct, anti-tiling would ghost the weave |
| Rimstone, glacier ice | **anti-tiled plate**; procedural variants exist but are not good enough yet | see open problems |
| Pool floors | anti-tiled paving + **kzCaustic** (ALU, animated) | replaces the caustics decal texture |
| Water, glass, lights | keep (owned by the water research / object UVs) | |

Honest verdict on the renders (`*__before.jpg` vs `*__after.jpg`):
- Big walls (`basalt_wall_wide`, `lava_wall`, `basalt_dry_corridor`) no longer show a repeat. Today's
  bark-like 2 m motif (basalt) and the 1 m lava blob grid are gone.
- At eye height (`basalt_wall_eye`, `phone_cave_390x844__after`) the rock reads as rock; today's
  basalt reads as cork/bark.
- Still fake: lava at 40 m is uniformly busy (it needs flow-scale structure from geometry or a flow
  map, not more texture); hex-tiled paving creates "ghost" joints where two flagstones blend; ice
  looks blobby when hex-blended; procedural rimstone sides read as wood figure.

## 2. Research (primary sources read)

- **Heitz & Neyret 2018**, *High-Performance By-Example Noise using a Histogram-Preserving Blending
  Operator* (HPG 2018, PACMCGIT 1(2)), https://inria.hal.science/hal-01824773/file/HPN2018.pdf.
  Triangle grid, 3 random patches, variance-preserving blend `(G - mean)/sqrt(w1²+w2²+w3²) + mean`,
  exact only for Gaussian inputs, hence the Gaussianising histogram transform + inverse LUT. 0.11 ms at
  1080p on a GTX 980 for 256² input.
- **Deliot & Heitz 2019**, *Procedural Stochastic Textures by Tiling and Blending* (GPU Zen 2), Unity
  implementation https://github.com/UnityLabs/procedural-stochastic-texturing
  (`Editor/ProceduralTexture2D/SampleProceduralTexture2DNode.cs`: 3 `SampleGrad` taps, `rsqrt(w1²+w2²+w3²)`,
  `T⁻¹` LUT fetch per channel), blog https://unity.com/blog/engine-platform/procedural-stochastic-texturing-in-unity.
  Needs precomputed T / T⁻¹ textures per input, i.e. a pipeline change; and normals cannot be rotated.
- **Mikkelsen 2022**, *Practical Real-Time Hex-Tiling*, JCGT 11(2), https://jcgt.org/published/0011/03/05/
  (code https://github.com/mmikk/hextile-demo). No preprocessing: weights `w^γ` (γ = 7) times a
  per-sample metric δ (luminance for colour, slope `sqrt(|d|²/(1+|d|²))` for normals, β = 0.6),
  renormalised, then an S-curve gain (r ≈ 0.65–0.75) to keep contrast; per-tile **rotation**, with the
  normal blended as height **derivatives** and rotated back per tile (only possible without histogram
  preservation). `SampleGrad` because of the per-tile offsets. **This is what the kit uses** (listings
  1, 3–5, 8, 9 ported), with one change: δ is the material **height** (nh.b) for all maps, so base,
  normal and roughness switch tiles together (height blending), which hides transitions in crevices.
- **Quilez, texture repetition**, https://iquilezles.org/articles/texturerepetition/ : technique 1
  (per-tile offset/mirror, 4 taps), 2 (Voronoi bombing, 9 taps), **3 (2 virtual patterns chosen by a
  low-frequency index, 2 taps + 1 cheap lookup)**. The kit uses technique 3 as the **Low tier** sampler
  (index from 2D value noise, blend nudged by the height difference, optional 90° rotations).
- **Glanville 2004**, *Texture Bombing*, GPU Gems ch. 20,
  https://developer.nvidia.com/gpugems/gpugems/part-iii-materials/chapter-20-texture-bombing :
  cell-grid placement of sprites; the board shuffle and the pebble/vesicle features are cell-based in
  this spirit.
- **Quilez, biplanar mapping**, https://iquilezles.org/articles/biplanar/ : 2 projections (major +
  median axis), local support `clamp((n-0.5773)/(1-0.5773))`, `textureGrad` with projected position
  derivatives. Used for cave rock, with hex/iq3 inside each projection, and the projection blend made
  height-aware.
- **Mikkelsen 2020**, *Surface Gradient-Based Bump Mapping Framework* (JCGT 9(3)),
  https://jcgt.org/published/0009/03/04/ : blend everything as surface gradients, `n' = normalize(n - (g - n(n·g)))`;
  this is how the kit combines tangent-space maps, world-projected maps, ALU noise gradients and
  screen-space bumps in one normal.
- **Macro variation / distance-blended detail**: UE landscape docs
  https://docs.unrealengine.com/udk/Three/LandscapeMaterials.html (detail→macro by view distance) and
  the common "macro variation" multiply (e.g. https://versluis.com/2023/05/how-to-use-macro-variations-for-unreal-engine-landscape-materials ).
- **Specular anti-aliasing**: Kaplanyan et al. 2016 / Tokuyoshi & Kaplanyan 2019 (kernel on normal
  derivatives, `α² += min(2σ², 0.18)`), implemented on the final perturbed normal.
- **Mobile cost**: Arm Mali offline compiler notes (trilinear ≈ 2× bilinear texture cycles; check the
  bound pipe before optimising ALU), https://developer.arm.com/community/arm-community-blogs/b/mobile-graphics-and-gaming-blog/posts/accelerating-shader-programs-with-mali-offline-compiler-7 ;
  https://learn.arm.com/learning-paths/mobile-graphics-and-gaming/ams/malioc/ .
- **three.js TSL / NodeMaterial**: node materials only run on `WebGPURenderer` (which has a WebGL2
  fallback backend); legacy WebGLRenderer node support was removed in r164
  (https://threejs.org/manual/en/webgpurenderer.html, https://discourse.threejs.org/t/r164-nodes-no-longer-working-with-webgl-webgl2/64909 ).
  The runtime is WebGLRenderer with chunk patches (fog, box-projected probes, RGBM lightmaps), so
  **stay on `onBeforeCompile` now**; a TSL port only makes sense together with a move to
  WebGPURenderer, and then fog/probes/lightmap must be ported too. The GLSL is written as small pure
  functions so it maps 1:1 to TSL `Fn()` later.

## 3. The kit (`kzshader.js`)

`kzShade(mat, cfg)` chains after `patchMaterial()` (it calls the previous `onBeforeCompile`, extends
`customProgramCacheKey`), adds two varyings (`kzUv`, `kzWN`; reuses `kzWorldPos` when present) and
replaces `map_fragment`, `roughnessmap_fragment`, `metalnessmap_fragment`, `normal_fragment_maps`,
appends to `emissivemap_fragment` and `aomap_fragment` (AO multiplies the lightmap's indirect diffuse,
60 % of it on indirect specular). Everything is driven by `#define`s, so each program only contains
what it uses.

| define | meaning |
|---|---|
| `KZ_MODE` 0..3 | plain / anti-tiled / + macro + detail (+ layer 2) / procedural or hybrid |
| `KZ_TIER` 0/1, `KZ_SAMPLER` | Low → iq technique 3 (2 taps per map), High → hex (3 taps per map) |
| `KZ_PROJ` 0/1/2 | UV metres / world biplanar / world floor (XZ) |
| `KZ_PATCH` | non-seamless plate: hex taps stay in a disc around the plate centre (no wrap seams) |
| `KZ_ORM` | 3-texture set (library); otherwise 2 textures: rough = mix(dry, wet-pocket, nh.a), ao from height |
| `KZ_BOARDS` | plank shuffle (hinoki, lacquer) |
| `KZ_LAYER2` | second plate height-blended by a 6–7 m noise (High; UV path, and the major projection of the biplanar path) |
| `KZ_PROC` / `KZ_HYBRID` | 1 basalt, 2 obsidian, 3 sand, 4 lava, 5 ice, 6 rimstone; hybrid = texture path + overlay |
| `KZ_MACRO_TEX` | Low: macro from 2–3 taps of a 256² noise texture instead of 3D ALU noise |
| `KZ_GRAD` | `textureGrad` (default). Off = implicit derivatives: artefacts only where the third hex weight is ~0 |
| `KZ_DEBUG` 1..5 | albedo / roughness / normal / indirect specular / indirect diffuse |

Shared settings: `tint`, `wetness`, `wear`, `roughness_offset`, `scale` (metres per repeat; for plates
it scales `plateM` by `params.scale / tiling_m_per_repeat`), `normal_strength`, `emissive_level`, with the
`kz_core.formulas` from `materials.json` (porosity darkening, film → mirror-wet 0.04 / damp 0.32, wear
toward WornColor/WornRough on high points). Additions: water films also flatten the micro normal
(`normal_strength *= 1 - 0.55·wet·film`); a world **wet plane** (`kz_wetPlane`, `kz_wetBand`) gives
water-proximity wetness without vertex colours; macro wet patches and vertical run-off streaks feed
`film`.

Plates (`tools/prep_textures.py`): the 24 Codex plates are cut from the sheets by gutter detection
(`.scratch/shaders/plates/*.png`), resized to 512², de-lit (divide by 40 px low-pass luminance^k),
glints soft-clipped out of albedo (knee relative to the median, they come back as low roughness),
stone plates desaturated to a cool neutral, height from a luminance band-pass, AO from cavity,
roughness from the glint mask, normals from height; then made seamless with an offset cross-fade (the
centre stays the original, which is the only part the hex patch sampler reads). Boards are first
regularised to N equal-width strips. Output: `demo/tex/pl/<name>_{base.jpg,nh.png,orm.png}` +
`plates.json` (mean albedo, std, roughness per plate). Library sets the demo compares against are a
512 px snapshot in `demo/tex/lib/` (taken 2026-10-27 00:4x UTC from `.scratch/matlib/tex`).

## 4. Recommendation table (all 29 library materials)

Taps = texture fetches per pixel, measured configuration of the demo. High = hex (3 taps per map).
Low = iq3 (2 per map). "2-tex" = base + nh (rough/AO derived), no ORM needed.

| material | technique | texture inputs | High taps / ALU | Low fallback (taps) | Blender side (bakes / previews only) |
|---|---|---|---|---|---|
| basalt_wet | hybrid, biplanar | plate `rock_wet_ore` 2.4 m + `basalt_columnar_wet` (layer 2) | 12 + 6 layer 2 + 1 detail = 19; ALU macro + 2× 3D Voronoi (facets, vesicles) | iq3 biplanar 8 + 3 macro tex, no overlay | box-projected plate + Noise macro in preview; bake with geometric normals |
| basalt_dry | hybrid, biplanar | `basalt_vesicular` 2.2 m + `rock_wet_ore` | as above | as above | as above |
| obsidian | hybrid, biplanar | `obsidian` 1.6 m | 12 + 1; 1× 3D Voronoi facets | iq3 biplanar (facets dropped) | plate, Box projection; probes matter more than albedo |
| rimstone | anti-tiled | `rimstone` 1.4 m (tops); sides: library `rimstone_side` | 6 + 1 | 4 + 3 | plate; keep the library's normal-based side blend |
| black_sand | hybrid, floor XZ | `black_sand` 1.6 m | 6 + 1; ripples + glints ALU | 4 + 3 + ripples | plate planar XZ |
| ash_clay | anti-tiled | `ash_clay` 2.4 m | 6 + 1 | 4 + 3 | plate |
| paving | anti-tiled, gain r = 0.8 | `paving_wet` 2.6 m | 6 + 1 | 4 + 3 | plate; real flagstones should come from layout geometry/decals |
| hinoki | board shuffle | `hinoki` (5 boards, 0.16 m × 1.8 m) | 2 (+1 detail) | 2 + 3 | per-board UV offset like today |
| lacquer_dark | board shuffle | `lacquer` (3 boards) | 2 + 1 | 2 + 3 | as hinoki |
| bamboo | keep + macro | library | 3 | 3 | unchanged |
| tatami | plain + macro | `tatami` 0.9 m | 2 + 1 | 2 + 3 | plate, plain repeat |
| washi | anti-tiled | `washi` 0.8 m | 6 + 1 | 4 + 3 | plate |
| washi_backlit | anti-tiled + emissive | `washi` | 6 + 1 | 4 + 3 | plate, emission unchanged |
| noren | plain + macro | `noren` (logo cropped out) 0.5 m | 2 + 1 | 2 + 3 | plate |
| rope | keep | library | 3 | 3 | unchanged |
| iron | anti-tiled | `iron` 0.9 m, metal 0.3 | 6 + 1 | 4 + 3 | plate |
| bronze | anti-tiled | `bronze` 0.9 m, metal 1 | 6 + 1 | 4 + 3 | plate |
| glacier_ice | anti-tiled (procedural parallax variant experimental) | `glacier_ice` 2 m | 12 + 1 biplanar | 8 + 3 | plate |
| lava_glass | keep (+ macro smudge later) | library | – | – | unchanged |
| water_still / water_river / water_sea / waterfall | keep (water research) | – | – | – | – |
| caustics_decal | procedural `kzCaustic` on the pool-floor material | none | 0 taps, 2× 2D Voronoi + fbm | same | none (emissive-like, not baked) |
| lava | hybrid | `lava_crust` 3 m, emissive from plate seams | 6 + 1; macro + flowing noise | 4 + 3 | plate + emission; bake lava as emitter as today |
| lava_flow | hybrid (faster flow) | `lava_crust` | 6 + 1 | 4 + 3 | as lava |
| neon_tube, lantern_paper, lantern_andon | keep | library, object UVs | – | – | unchanged |

Families with no plate (bamboo, rope, glass, water, lights) keep the library sets; the kit still
gives them macro and wetness if wanted.

## 5. Measured cost

Method: `KZDEMO.bench()`; this Chrome does not expose `EXT_disjoint_timer_query_webgl2`, so each frame
is followed by a 1-pixel `readPixels` (full GPU sync), 40 frames, best of 3 runs. 3840×2160 (8.3 Mpx),
material covering ~95 % of the screen, RTX 4090 via ANGLE/Vulkan. Mode 0 already includes the
runtime's fog, box-projected probe and lightmap path, plus the sync overhead (so the deltas are what
counts). Raw data: `.scratch/shaders/bench1.txt`, `bench2.txt`, `bench3.txt`.

| surface (full screen) | High m0 | m1 | m2 | m3 | Low m0 | m1 | m2 | m3 |
|---|---|---|---|---|---|---|---|---|
| basalt_wet wall (biplanar, hybrid, layer 2) | 0.50 | 0.56 | 0.98 | 1.45 | 0.46 | 0.51 | 0.59 | 0.59 |
| basalt_dry wall (biplanar, hybrid, layer 2) | 0.44 | – | 0.96 | 1.43 | 0.42 | – | 0.55 | 0.56 |
| obsidian wall (biplanar, hybrid) | 0.43 | 0.56 | 0.83 | 1.05 | 0.42 | 0.50 | 0.60 | 0.60 |
| lava wall (uv, hybrid) | 0.42 | 0.53 | 0.81 | 0.82 | 0.42 | 0.49 | 0.55 | 0.58 |
| ash_clay wall (uv) | 0.41 | 0.51 | 0.78 | 0.80 | – | – | – | – |
| black_sand floor (hybrid) | 0.47 | 0.64 | 0.89 | 1.07 | 0.49 | 0.57 | 0.62 | 0.67 |
| paving floor | 0.46 | 0.62 | 0.88 | 1.00 | 0.47 | 0.55 | 0.61 | 0.61 |
| hinoki floor (boards) | 0.46 | 0.56 | 0.83 | 0.94 | 0.45 | 0.53 | 0.59 | 0.59 |

(ms per frame at 8.3 Mpx; basalt rows re-measured after adding layer 2 to the biplanar path, `bench3.txt`). Findings:
- Anti-tiling itself is cheap: +0.05–0.17 ms at 8.3 Mpx (hex, 3 taps per map).
- The expensive part on High was the **ALU 3D macro noise** (+0.25 ms): switching Low to the 256²
  noise texture (`KZ_MACRO_TEX`, 2–3 taps) cut mode 2 from +0.30 to +0.06–0.13 ms. High could use it
  too (saves ~0.2 ms) at the price of soft dominant-axis seams in the macro on curved rock.
- 3D Voronoi overlays (basalt facets + vesicles) cost +0.45 ms; they are High only.

**Phone estimate** (honest, not measured on a phone): phone_ms ≈ Δdesktop_ms × (phone pixels covered /
8.3 Mpx) × R. Low renders 585×1266 (DPR 1.5) = 0.74 Mpx, ~70 % covered by kit materials = 0.52 Mpx. R
= throughput ratio RTX 4090 / phone GPU: ~25 for a 2023 flagship (Adreno 740 / Apple A16 class,
~3–3.5 FP32 TFLOPS vs 82.6), ~90 for a 2021 mid-range part (~1 TFLOPS); texture rate ratios are
lower (~13–40) so texture-bound parts fare better. Tile GPUs also pay ~2× for trilinear vs bilinear
and `textureGrad` can be slower than implicit LOD (Arm guidance), so treat this as ±2×.
- Low, mode 3 / hybrid, cave wall: Δ ≈ 0.13 ms → **0.2–0.8 ms** on the phone.
- Low, anti-tiled UV material (paving / hinoki): Δ ≈ 0.14 ms → **0.2–0.8 ms**.
- High, hybrid basalt (layer 2 + overlays): Δ ≈ 0.95 ms → 1.5–5.5 ms: **desktop / flagship only**, keep phones on Low.
The water research budgets 2.3–4.8 ms on Low; this kit adds well under 1 ms on Low.

## 6. Proposed integration patch for `web/src/materials.js` (not applied)

Copy `kzshader.js` and `kzmaterials.js` into `web/src/`, encode the plates as KTX2 like the library
(`3d/materials/tex/pl_<name>_{base,nh}.ktx2`, 512², base sRGB / nh linear) plus `kz_noise.ktx2`, and
let the manifest carry them as `kzBase` / `kzNh` / `kzBase2` / `kzNh2` texture ids. Then:

```diff
--- a/web/src/materials.js
+++ b/web/src/materials.js
@@
 import * as THREE from 'three';
 import { FOG, LIGHTMAP_INTENSITY } from './config.js';
+import { kzShade, KZS } from './kzshader.js';
+import { KZM } from './kzmaterials.js';
@@
   kzTime: { value: 0 },
 };
+// the kit's animation clock is the runtime clock
+KZS.time = KZ.kzTime;
@@
 export class MaterialLibrary {
-  constructor(manifest, textures, env) {
+  constructor(manifest, textures, env, tier = 'low') {
     this.def = manifest.materials;
     this.textures = textures; // id -> THREE.Texture
     this.env = env;
+    this.tier = tier;
     this.cache = new Map();
   }
@@
     if (this.env && !d.emissive) { m.envMap = this.env; m.envMapIntensity = 1; }
     patchMaterial(m, { rgbm: lightMap && lightMapInfo?.encoding === 'rgbm' ? { range: lightMapInfo.range, gamma: lightMapInfo.gamma } : null });
+    const k = KZM[d.kz_id ?? name];
+    if (k && k.tech !== 'keep' && d.kzBase) kzShade(m, this.kzConfig(d, k));
     this.cache.set(key, m);
     return m;
   }
+  kzConfig(d, k) {
+    const p = d.params ?? {}, c = d.constants ?? {};
+    const ratio = (p.scale ?? 1) / (d.tiling_m_per_repeat ?? p.scale ?? 1);
+    const t = (id, cs) => (id ? this.tex(id, cs) : null);
+    return {
+      ...k, mode: k.tech === 'hybrid' || k.tech === 'procedural' ? 3 : 2, tier: this.tier,
+      hybrid: k.tech === 'hybrid', patch: true, aspect: 1,
+      tileM: [k.plateM * ratio, k.plateM * ratio],
+      maps: { base: t(d.kzBase, THREE.SRGBColorSpace), nh: t(d.kzNh, THREE.NoColorSpace) },
+      maps2: d.kzBase2 ? { base: t(d.kzBase2, THREE.SRGBColorSpace), nh: t(d.kzNh2, THREE.NoColorSpace) } : null,
+      noiseTex: t(d.kzNoise ?? 'kz_noise', THREE.NoColorSpace),
+      porosity: c.Porosity ?? k.porosity, worn: { color: c.WornColor ?? [0.05, 0.05, 0.05], rough: c.WornRough ?? 0.45 },
+      settings: {
+        tint: (p.tint ?? [1, 1, 1]).map((x) => x * (k.gain ?? 1)), wetness: p.wetness ?? 0, wear: p.wear ?? 0,
+        roughness_offset: p.roughness_offset ?? 0, normal_strength: p.normal_strength ?? 1,
+        emissive_level: p.emissive_level ?? 1, scale: k.plateM * ratio,
+      },
+    };
+  }
```

and in `world.js`: `new MaterialLibrary(this.m, tex, this.env, tier)`; on a tier change clear
`lib.cache` and rebind (new defines → new programs). `kzShade` sets `map = null` behaviour
implicitly (albedo comes from the kit), so `d.baseColorTexture` is not needed for kit materials.
Per-asset variation (the 7 settings) keeps working: each variant is just different uniforms, and the
program cache key only depends on the defines, so variants share programs.

Notes for the runtime: drop `powerPreference: 'high-performance'` in the demo-like contexts (it fails
on this ANGLE/Vulkan Chrome; the water research found the same); `EXT_disjoint_timer_query_webgl2`
is not available, so on-device profiling needs the frame-time probe in `tier.js`.

## 7. Blender side

Albedo is not baked (Cycles bakes irradiance only, colour off), so Blender only needs the kit for
previews: plate Image Texture with Box projection (blend 0.2) on cave rock, a Noise Texture (scale
1/7 m) multiplied in as macro, and the same 7 settings in `KZ_Core`. For **bakes**, keep the normal
detail out of the bake (geometric normals only), because the runtime adds its own per-pixel normal
detail; baking the plate normal in would double it and would show the library's repeat in the
lightmap. If exact parity is wanted for previews, the hex TriangleGrid + per-vertex transform is
about 30 math nodes (a `KZ_Hex` group), but I do not think previews need it.

## 8. Open problems

- Lava at 40 m: no repeat but uniformly busy. Needs flow-scale structure (a baked flow map or
  geometry), then the plate seams can follow the flow.
- Paving: hex blends of discrete flagstones give ghost joints. Better: flagstones as layout geometry
  or a cell-ID texture (one stone per cell, random rotation per cell); the kit's board shuffle could be
  generalised to that.
- Glacier ice and rimstone procedural variants (parallax cracks, gours/flowstone) are not convincing
  yet; the plates are better. Sides of rimstone need the library's `rimstone_side` or the
  `sulfur_travertine` plate.
- The plates are 512² photos with baked lighting; de-lighting is approximate (some pinkish residue in
  `rock_wet_ore`). A Codex re-run asking for flat-lit, cross-polarised plates (no glints) at 1024²
  would raise the ceiling; the soft-clip already removes most glints.
- Macro on High is ALU 3D noise (world-seamless but +0.25 ms); Low uses the texture version, which
  can show soft seams where the dominant axis changes on curved rock.
- Layer 2 is only on the major biplanar projection; the minor projection shows layer 1 only.
- Specular richness depends on the probes containing the lanterns (the demo bakes one box-projected
  scene probe); with the stub probe wet rock reads as matte.

## 9. Rebuild / rerun

```bash
.venv/bin/python 3d/research/shaders/tools/prep_textures.py        # plates -> demo/tex/pl, lib snapshot, kz_noise.png
node 3d/research/shaders/tools/kzshot.mjs <job.json>              # renders / bench in the shared GPU browser (CDP 9310)
# jobs used: .scratch/shaders/jobs/{final,final_b,video,bench,bench2}.json
```
