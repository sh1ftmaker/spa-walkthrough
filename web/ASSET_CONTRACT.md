# Kazan-yu web asset contract (v1.2)

This is the interface between the Blender export pipeline and the three.js walkaround in `web/`.
v1.1 (2026-10-27) adds the Blender side; v1.2 (same day, look-dev round 2) is in §16. v1.1 (`tools/export/`) and the mixed manifests; every v1 file still loads unchanged
(`"contract": 1` stays). The additions are listed in §15.
Anything that follows it loads without code changes. The graybox stand-in
(`tools/build-standin.mjs`, generated from `3d/layout.json`) is built through the same contract and is the reference
implementation of the exporter side.

## 1. Stack and versions

| Package | Version | Why |
|---|---|---|
| three | 0.186.1 (r186) | WebGL2 renderer, `AgXToneMapping`, KTX2Loader with UASTC HDR (needs r170+; BC6H / ASTC-HDR / RGBA16F fallback), `GLTFLoader` + meshopt. Released 2026-09-24, so it has been out for weeks. |
| three-mesh-bvh | 0.9.16 | capsule collision and raycasts against the walk mesh |
| vite | 7.3.7 | dev server + build (`base: './'`, so every URL is relative) |
| @gltf-transform/core/functions/extensions | 4.5.1 | stand-in GLB writer (weld, quantize, meshopt) |
| meshoptimizer | 1.3.0 | meshopt encoder for the stand-in builder (the decoder ships with three) |
| ktx2-encoder | 0.6.0 | Basis Universal WASM encoder (UASTC LDR, ETC1S, UASTC HDR) for the stand-in builder |
| polygon-clipping | 0.15.7 | stand-in builder only (stair holes, water cut-outs) |
| playwright-core | 1.56.1 | `tools/shot.mjs` and `tools/flythrough.mjs` (CDP only, no bundled browsers) |

All versions are exact in `package.json`. The Basis transcoder (`basis_transcoder.js/.wasm`) is copied from
`three/examples/jsm/libs/basis` into `public/libs/basis/` by `tools/copy-libs.mjs` and ships in `dist/`. Nothing loads from a CDN.

## 2. Coordinates and units

* Metres everywhere.
* Layout / Blender space: x east, y north, z up. **All JSON files use this space**: places, labels, probes, water, spaces.
* three / glTF space: `X = x, Y = z, Z = -y` (Y up). Export GLBs with the Blender glTF exporter's default **+Y Up**, which does exactly this.
* Headings in JSON are degrees clockwise from north (0 = +y, 90 = +x). In three, `rotation.y = -heading` (order `YXZ`).
* Code helpers: `src/coords.js` (`l2t`, `t2l`, `headingToYaw`).

## 3. Files

```
assets/
  manifests/low.json, manifests/high.json   fixed names, fetched with cache: no-cache
  parts/<sha16>.glb                         render parts and walk meshes, content-addressed
  tex/<sha16>.ktx2                          KTX2 textures, content-addressed
  data/places.json                          fixed name (the lead's exporter overwrites it)
  data/<sha16>.json                         spaces, placements, other JSON, content-addressed
```

`<sha16>` is the first 16 hex characters of the SHA-256 of the file bytes. Content-addressed files never change, so they
can be cached forever. Only the manifests and `places.json` change in place. All URIs in a manifest are relative to `assets/`.

**Failure policy:** each batch of loads runs in parallel. If anything fails (HTTP status, network error, bad JSON,
bad KTX2 or GLB), the app shows a red panel listing **every** failed URL with its status and reason, logs the same list
to the console, and rejects `__kz.ready`. Nothing fails silently.

## 4. Manifest (`manifests/<tier>.json`)

```jsonc
{
  "contract": 1, "tier": "low", "source": "standin|blender", "generated": "ISO time",
  "color": { "toneMapping": "AgX", "exposureStops": 0, "lightMapIntensity": 3.14159 },
  "start": { "place": "g_gate" },
  "textures": { "<id>": { "uri": "tex/<sha16>.ktx2", "colorSpace": "srgb|linear", "width": 512, "height": 512, "codec": "etc1s|uastc|uastc-hdr" } },
  "materials": {
    "<name>": { "type": "standard", "baseColorTexture": "<texture id>|null", "normalTexture": "<id>?", "ormTexture": "<id>?",
                "color": [1,1,1], "roughness": 0.7, "metalness": 0, "emissive": [r,g,b]|null, "emissiveIntensity": 0,
                "lightmap": true },
    "water": { "type": "water", "normalTexture": "water_normal" }
  },
  "zones": [{
    "id": "b1", "name": "B1 Thermal",
    "neighbors": ["b2", "c_spiral_stair"],      // visible together; loaded before the player may enter
    "preload": ["b3"],                           // extra links (lift); loaded in the background
    "spaces": ["b1_lobby", "..."],
    "bounds": [minx, miny, maxx, maxy],          // layout xy
    "parts": [{ "uri": "parts/<sha16>.glb", "bytes": 170448, "tris": 5872 }],
    "walk": { "uri": "parts/<sha16>.glb", "bytes": 15372, "tris": 4172 },
    "lightmaps": [{ "id": "lm_b1", "uri": "tex/<sha16>.ktx2", "encoding": "rgbm|hdr", "range": 16, "gamma": 2,
                    "intensity": 3.14159, "width": 512, "height": 256, "uv": 1 }],
    "probes": [{ "id": "probe_b1_lobby", "space": "b1_lobby", "center": [x,y,z], "box_min": [x,y,z], "box_max": [x,y,z],
                 "cubemap": "tex/<sha16>.ktx2|null", "intensity": 0.6 }],
    "placements": []                              // reserved: instanced props, data/<sha16>.json
  }],
  "water": [{ "id": "w_mirror", "kind": "still|flow|sea", "zone": "b1", "z": -20.05, "bed_z": -21.25,
              "bounds": [minx, miny, maxx, maxy], "planar": true, "mist": 1, "absorption": [0.75, 0.16, 0.12], "flow": 0 }],
  "places": "data/places.json",
  "spaces": "data/<sha16>.json",
  "budget": { "drawCalls": 150, "triangles": 500000, "textureMB": 250 }
}
```

### 4.1 Zones and loading

* At start the app loads the start place's zone plus its `neighbors`, then lets the player move. After that it
  background-loads every other zone, one at a time. The Low budget fits everything, so the whole site ends up resident.
* Visible set while walking: the current zone (from the walk-mesh triangle under the player) plus its `neighbors`.
  Visibility is only toggled on zones that are already loaded.
* If a neighbour is not loaded yet, the mist thickens until it is (`KZ.kzFogDensity` eases to 0.25/m).
  Teleporting into an unloaded zone waits for that zone and its neighbours.
* Unloading is not implemented yet (not needed at the current size).

## 5. GLB parts

* glTF 2.0 binary, **`EXT_meshopt_compression`** + **`KHR_mesh_quantization`** (positions 16-bit, normals 10-bit,
  UVs in [0,1] 14-bit; tiling UVs outside [0,1] stay float). Indexed triangles. No embedded images.
* Every mesh node carries `extras.kz` (Blender: custom properties on the object, exported with "Include > Custom Properties"):
  | key | meaning |
  |---|---|
  | `role` | `floor`, `wall`, `ceiling`, `stair`, `rail`, `basin`, `lantern`, `water`, `prop`, ... (`ceiling` is hidden in dollhouse view) |
  | `material` | key into `manifest.materials`. The glTF material is a placeholder; the runtime replaces it with the library material. |
  | `lightmap` | id of a lightmap in the same zone; omit for unbaked meshes |
  | `water` | for `role: water`: id in `manifest.water` |
* UV0 holds the tiling material UVs, in metres / tile size. UV1 holds the lightmap UVs (non-overlapping, packed into the
  atlas named by `lightmap`). glTF UV convention: v = 0 is the top row of the image (KTX2 is not flipped).
* Water surfaces are separate meshes (`role: water`). They need positions only and are drawn with the water shader.
* Several parts per zone are fine. Keep each part under about 2 MB and group meshes by material, because draw calls cost
  about one per material per part.

## 6. Textures (KTX2 / Basis Universal)

| Use | Low | High | colour space |
|---|---|---|---|
| albedo | ETC1S, 512-1024 | UASTC LDR + zstd, 1024-2048 | sRGB (KTX2 sRGB transfer flag set) |
| normal | UASTC (normal-map preset) | same | linear |
| ORM (AO, rough, metal) | UASTC | same | linear |
| lightmap | **RGBM** in UASTC LDR | **UASTC HDR** (BC6H / ASTC-HDR / RGBA16F fallback) or RGBM | linear |
| probe cubemap | UASTC HDR or RGBA16F cube, 256 px faces | same | linear |

**RGBM** (linear 8-bit, no sRGB flag): `L = range * (rgb * a)^gamma`, with `range` 16 and `gamma` 2 from the
lightmap entry. Encoder: `e = (L / range)^(1/gamma)`, `a = ceil(max(e) * 255) / 255`, `rgb = e / a`.

**Lightmap units:** bake Cycles **Diffuse** with **Direct + Indirect** on and **Color off**, in linear HDR, then denoise.
The baked value E is the factor such that radiance = albedo * E. three's Lambert divides irradiance by PI, so the runtime
uses `lightMapIntensity = PI` (`manifest.color.lightMapIntensity`). Use the same exposure and units for every bake.
Materials that have a lightmap get no probe diffuse irradiance (that light is already in the bake). Probes only add the
specular reflection.

## 7. Reflection probes

* One per space, or more for big spaces. `center` is the capture point. `box_min` / `box_max` give the parallax box,
  normally the room's bounding box. All in layout coordinates.
* The cubemap is linear HDR at 256 px per face. The runtime prefilters it with `PMREMGenerator.fromCubemap`
  (GGX roughness levels) on load, so exported mips are not needed. All probes must use the same face size, so the shaders
  are shared and swapping probes never recompiles.
* Runtime: the two nearest probes (by distance to their boxes; inside a box counts as 0, and the smaller box wins)
  are blended. The lookup direction is box-projected (parallax-corrected) per probe. This is the `envmap_physical_pars_fragment`
  patch in `src/materials.js`. While `cubemap` is null, a generated stub environment is used (warm floor, dark vault, lantern band).

## 8. Walk mesh

* One GLB per zone (`zone.walk`), positions only, in the same space as the render parts.
* It contains everything the player stands on or bumps into: floors, stair treads (real risers of 0.20 m or less),
  landings, walls, railings, bridge decks, pool basins. **No ceilings.** Make it watertight enough that a 0.3 m capsule cannot slip through gaps.
* The player is a capsule (radius 0.30 m) from `feet + 0.20` to `feet + 1.75`. It collides horizontally. Vertical
  placement is a 5-ray ground probe that steps up as much as 0.20 m and snaps down as much as 0.36 m. Gravity applies otherwise.
  Eye height is 1.6 m above the walk surface, smoothed with a two-pole low-pass filter so stairs glide.
* Walkable surfaces need a normal with |n.y| > 0.5. Shallow water (0.25 m or less below the surrounding floor) can be
  walkable at the water surface. Deeper water needs a railing or curb in the walk mesh.

## 9. Places, labels, spaces

`data/places.json` (the lead's exporter replaces it; for now it is derived from the layout):
```jsonc
{ "contract": 1, "coords": "layout", "places": [
  { "id": "b1_mirror", "name": "05 Obsidian Mirror Float Pool", "level": "b1", "zone": "b1",
    "kind": "attraction|place", "number": 5,
    "pos": [x, y, zEye],                 // eye position (floor + 1.6)
    "yaw_deg": 198.4, "pitch_deg": 0,
    "label": { "text": "Obsidian Mirror Float Pool", "pos": [x, y, z] } | null } ] }
```
* The place list groups attractions first (by number), then places by level. Labels: the nearest 4 (Low) or 8 (High) within 45 m,
  attractions first. They fade with distance, are occlusion-tested against the walk mesh, and are never placed on top of each other.
* `spaces` JSON: `[{ id, name, level, zone, kind, floor_z, ceiling_z, footprint: [[x,y],...] }]`. It is used for the
  "where am I" readout, for `__kz.info().space`, and for dollhouse levels.

## 10. Rendering

* WebGL2 only. Render into a half-float target, then (High) `UnrealBloomPass` (threshold 1.6 linear, strength 0.16,
  radius 0.35), then `OutputPass` (AgX + sRGB). Low uses 2x MSAA and High uses 4x MSAA on the HDR target.
* **Colour:** Blender View Transform **AgX**, Look **None**, Exposure **E** stops ⇔ three `AgXToneMapping`,
  `toneMappingExposure = 2^E` (`manifest.color.exposureStops`, default 0). Compare a Cycles render and `tools/shot.mjs`
  from the same camera (`__kz.setCamera`) in three zones.
* **Height fog / mist** is injected into every material by `onBeforeCompile` (see `src/materials.js`, before
  tone mapping, in linear HDR). It has two parts: a base exponential haze, plus an analytic exponential layer above each nearby water surface
  (scale height 0.3 m, so it is dense in the first 0-0.5 m). The water list comes from `manifest.water`, with the 8 nearest active.
* **Water:** two passes over the same mesh. (1) Multiplicative transmittance: `exp(-absorption * depth / |V.y|)`
  times `(1 - Fresnel)`, so red is absorbed and you see teal. (2) Additive: Fresnel times the reflection (planar texture if
  assigned, otherwise the probe environment) plus a small in-scatter term. Normal maps scroll. There is no self-glow; the teal
  comes from the baked light on the basin under the water.
* **Planar reflections:** horizontal, using an oblique-clipped mirror camera. The nearest planar-flagged visible waters get them:
  Low gets 1 at quarter resolution, High gets 2 at half resolution. The reflection is disturbed by the water normal.

## 11. Quality tiers

| | Low | High |
|---|---|---|
| detect | mobile UA, coarse pointer, weak GPU (Mali, Adreno 5xx and below, PowerVR, SwiftShader...) | desktop + strong GPU (RTX/GTX/RX/Apple M) or 8+ GB and 8+ cores |
| DPR | at most 1.5 | at most 2 |
| planar reflections | 1 at 0.25 resolution | 2 at 0.5 resolution |
| bloom | off | on |
| labels | 4 | 8 |
| textures | `manifests/low.json` | `manifests/high.json` |

Override with `?tier=low|high`, or in Settings (stored in `localStorage` `kz.tier`; Auto clears it). When the tier is
auto-detected as High, a 45-frame probe runs after start. If the median frame takes more than 21 ms, the runtime settings
drop to Low (the textures stay loaded).

## 12. Runtime API (`window.__kz`)

| | |
|---|---|
| `ready` | Promise. Resolves once the player can move (start zone and neighbours loaded, first frames drawn). Rejects with the failure list. |
| `info()` | `{fps, ms, drawCalls, triangles, textures, programs, textureMB, tier, assetTier, gpu, pos, feet (layout), heading, pitch, space, zone, visibleZones, loadedZones, interactiveMs, ...}` |
| `teleport(placeId)` | Promise, resolves after 2 frames |
| `setCamera(pos, target, fovDeg)` | layout coords. Freezes walk physics until user input. Resolves after the zones are loaded and 3 frames are drawn. |
| `walkPath(points, {speed})` | autopilot through eye-height waypoints (layout coords) with real physics; resolves with the skipped waypoint indices |
| `frames(n)`, `places()`, `mode('walk'|'dollhouse')`, `setFov(f)` | helpers |
| `allLoadedMs` | set once every zone is resident |

URL flags: `?debug=1` (HUD), `?tier=`, `?place=<id>`, `?labels=0`, `?fog=0`, `?hint=0`.

## 13. Tools

```
npm run dev                    # vite on 127.0.0.1:5173
npm run standin                # rebuild public/assets from ../3d/layout.json
npm run build                  # libs + stand-in + vite build -> dist/ (relative URLs; works at any sub-path)
node tools/shot.mjs --cdp 9311 --url http://127.0.0.1:5173/ --place b1_mirror --sizes 9:16,16:9 --out ../3d/renders/web/mirror
node tools/shot.mjs ... --pos x,y,z --target x,y,z --fov 60      # explicit camera, layout coords
node tools/shot.mjs ... --device phone                           # 390x844 @3x, touch, iPhone UA
node tools/make-route.mjs spiral_stair 0 -20 > tools/routes/ground-to-b1.json
node tools/flythrough.mjs --cdp 9311 --url http://127.0.0.1:5173/ --route tools/routes/ground-to-b1.json --out ../3d/renders/web/ground-to-b1.mp4
```
`shot.mjs` and `flythrough.mjs` only attach to an existing browser over CDP. They refuse port 9222.

## 14. Measured on the stand-in (2026-10-26, RTX 4090 via ANGLE/Vulkan; the phone figures use 390x844 @3x emulation)

| | Low | High |
|---|---|---|
| worst draw calls (every place, 4 headings, incl. planar pass) | 73 | 89 |
| worst draw calls walking the spiral stair | 74 | 125 |
| worst triangles | 110k | 158k |
| GPU texture estimate (textures + render targets) | 43 MB | 130 MB |
| asset bytes before interactive / all zones | 2.6 MB / 4.8 MB | about 5 MB / 8.7 MB |
| interactive, built `dist/`, 9 Mbit/s + 60 ms + 4x CPU throttle | 4.6 s from navigation (3.5 s app) | - |
| frame time, desktop | 16.7 ms (vsync-bound) | 16.7 ms (vsync-bound) |
| walk smoothness on stairs (frame-to-frame step change, p99) | 3 mm | 3 mm |

## 15. v1.1: Blender places and mixed manifests (2026-10-27)

### 15.1 Pipeline

```
3d/places/<space>.blend  (3d/PLACE_CONTRACT.md)
  -> tools/export/bake_place.py    blender -b <place> -P ... -- --tier low|high      -> 3d/bake/<space>/<tier>/
       evaluate kz_render (skip the kz_preview_modifier modifier), pull glowworm points/threads out, fold near-identical
       library variants of one kz_id (Low: <= 2 per id, High: <= 4); skip kz_role render_only, take kz_lod_render meshes, merge by material into parts; UV1 'kz_lm':
       smart project + average island scale + pack (margin ADD 4-6 px) into one atlas per place
       (Low target 6 cm/texel, High 2.5 cm, both capped at 2048 px, so big places get coarser); Cycles Diffuse bake, Direct + Indirect, Color off,
       OptiX, OIDN denoise (view-layer kz_bake = 1 only with --kz-bake: it made the hinoki deck bake ~60x too bright) -> lightmap_raw.exr, lightmap.exr, lightmap.f32;
       probes: Cycles equirect 1024 x 512 at each kz_probes empty (denoised) -> probe_*.exr / .f32; baked.blend, bake.json
  -> tools/export/export_place.py  blender -b -P ... -- --bake 3d/bake/<space>/<tier>   -> dump/ (+ runs pack_place.mjs)
  -> tools/export/pack_place.mjs   GLBs (meshopt + quantization), KTX2 lightmap / probes   -> pkg/place.json + pkg/files/
  -> web/tools/build-mixed.mjs     stand-in with --exclude-spaces + every package in 3d/bake -> public/assets
tools/export/run_chain.sh <space> [low|high|both]      bake + export in one go
tools/export/render_compare.py                          Cycles reference render for the §10 colour match
```
`npm run build` runs `build-mixed.mjs` (stand-in only when no package exists). Manifests then say `"source": "mixed"`
and list `places_blender`.

### 15.2 Zones

Each Blender place is its own zone `p_<space>` (`"source": "blender"`, `"base": <level zone>`). Its neighbours are its base
zone and the zones it has portals to (level zones, stair zones, other places); every one of those lists it back.
(Taking all of the base zone's neighbours put all three places in view on the spiral stair: 192 draws, 673k tris on Low.)
The stand-in leaves out the replaced spaces' floors, ceilings, walls, lanterns, probes and walk mesh, cuts their
footprints out of overlapping slabs and water at the same level, and keeps treating them as rooms for its neighbours'
walls (portals stay open). `mixed-report.json` records a walk-mesh seam check at every portal of every place.
New zone fields: `lights` (live lights, §15.6), `fx` (emitters, §15.7); `parts[].kind` = `sprites` | `anim` (with `clips`).

### 15.3 Materials (`"type": "kz"`)

```jsonc
"basalt_wet~8e53177b": { "type": "kz", "id": "basalt_wet", "params": { /* the 7 kz settings */ }, "lightmap": true,
  "kit": { "base": "lib:pl_dark_rock_02_base", "nh": "lib:pl_dark_rock_02_nh", "noise": "lib:kz_noise" },   // kit plates
  "maps": { "base": ..., "orm": ..., "nh": ..., "emis": ... },                                             // library set
  "lib": { "tiling", "aspect", "uv_mode", "tech", "porosity", "worn", "emissive", "alphaTest", "doubleSided", "envMapIntensity" } }
```
Keys are the Blender material names (`<kz_id>~<hash>` for thin variants), the same names the GLB primitives carry.
Textures `lib:<file>` are the library KTX2 files (`3d/materials/tex`), copied content-addressed. The runtime
(`src/kzlib.js`) builds kit materials with `kzShade` + `KZM[id]` (copied to `src/vendor/` by `tools/copy-libs.mjs`),
mode 3 for hybrid / procedural and 2 otherwise; other materials use kzShade mode 0 on the library set; alpha cards
(foliage) are plain MeshStandardMaterial with `alphaTest`; the library emissive map is added when the library material
emits (`emissive = tint x strength x emissive_level x map_scale`). Lightmapped materials ignore live lights
(`RE_Direct` is undefined when `USE_LIGHTMAP`), so baked lights are never counted twice.
`_glowworm` is `{ "type": "sprite" }`.

### 15.4 GLB additions

* `extras.kz.role`: also `glowworm` (POINTS, COLOR_0 = brightness, twinkle phase, radius / 0.05 m, rate / 0.4 Hz;
  `extras.kz.color` linear RGB) and `glowworm_threads` (LINES, COLOR_0.r = brightness). Drawn additively with fog.
* `_KZ_FLOW` (VEC2, normalized short): unit flow direction in UV0 space; `lava_molten`, `lava_flow`, `waterfall`
  scroll along it (or along -v without it) at 0.05 / 0.03 / 0.6 m/s.
* `extras.kz.role: anim`: one GLB per kz_anim object. Skinned figures carry their own clip (`kz_clip`, from
  `3d/assets/figure_anims.blend`, not force-sampled) and play it in a loop with a random start (AnimationMixer).
  Other kz_anim objects are exported in their static pose.
* Placeholder glTF materials may be double-sided; Blender parts render single-sided only for the roles floor, wall,
  ceiling, rock, basin and stair.

### 15.5 Lightmaps and probes

Lightmap entries add `texel_m` (measured density). High uses UASTC HDR; atlases are capped at 2048 px (the WASM encoder
takes at most ~12 Mpix). The atlas is baked as one joined object and split by material afterwards (Blender writes
the bake margin per object, so several objects sharing one image overwrote each other's texels). Probes from places are `"projection": "equirect"`: a UASTC HDR
2D texture, 1024 x 512, rows bottom-first (three's `equirectUv` with flipY false: u = 0.5 looks east, u grows
clockwise seen from above). The runtime uses `PMREMGenerator.fromEquirectangular`, which gives the same 256 px cube
size as the stub. Probes also carry `mean` (linear RGB mean radiance): the base haze and the mist colour follow it
(`FOG.hazeFromProbe` 0.25, `FOG.mistFromProbe` 1.5), so a dark room gets dark mist.

### 15.6 Live lights

`zone.lights`: `[{ name, type: point|spot, pos (layout), dir, color (linear), intensity, distance }]` from the
`kz_lights` objects with `kz_runtime` = true. Intensity is in three render units, `I = W / 4pi` (Cycles point-light
watts). The runtime keeps a fixed pool (Low 2, High 4) of PointLights and gives them to the nearest live lights of the
visible zones each frame, so the light count never changes and no program recompiles.

### 15.7 FX emitters and water

`zone.fx`: `[{ name, kind, pos (layout), params }]` from `kz_fx` empties (`kz_` prefixes stripped). `mist` / `steam` / `fog`
emitters join the mist list of §10 as square patches (`params.radius`, `params.density`). Water entries may add
`scatter` (in-scatter colour, scaled by the probe mean so dark pools stay black), `f0`, `normal_strength` and
`reflect_gain` (the Obsidian Mirror uses 0.12 / 0.025 / 1.25 and absorption [1.6, 1.1, 0.9] for a black, dead-still
mirror). Place water keeps `planar` only when its bounds cover >= 80 m2 (or it is the Mirror): a planar reflection re-renders
the scene, which doubled the draw calls for the small blossom basin in the arrival hall. Water in a place that authors `mist` emitters gets `mist` 0 (the emitters carry the authored mist). Water ids resolve per zone
first (`<zone>|<id>`), so a stand-in remnant and a place can share a layout water id.

### 15.8 Places data

For Blender spaces, `data/places.json` takes the zone `p_<space>` and the space file's `cam_entry` as the teleport pose;
the spaces JSON takes the new zone.

### 15.9 Measured on the vertical slice (2026-10-27, RTX 4090 via ANGLE/Vulkan; `3d/checks/web_slice.json`)

| | Low | High |
|---|---|---|
| worst draw calls, concept cameras (incl. planar pass) | 110 | 269 |
| worst triangles, concept cameras | 334k | 735k |
| flythrough arrival -> spiral stair -> corridor -> Mirror, worst draws / triangles | 141 / 403k | 296 / 742k |
| GPU texture estimate | 163 MB | 231 MB |
| place packages (GLB + lightmap + probes) | g_arrival 12.9 MB, b1_mirror 11.2 MB, b1_cor_mirror 6.5 MB | 12.3 / 10.9 / 9.7 MB |

Low planar reflections draw only the water's own zone (`TIERS.low.planarOwnZone`). High exceeds the Low budget on purpose.
Debug: `?albedo=0.18` replaces every library material with grey 0.18 (lighting check against
`tools/export/render_compare.py --albedo 0.18`).

## 16. v1.2: look-dev round 2 (2026-10-27)

Measured against Cycles at each place's concept camera (`3d/checks/web_slice.json` → `colour_match`): arrival and corridor
are within 0.3 stops in mean luminance on both tiers (bright pools 0.5-0.8 stops short); the Mirror is about 2.7 stops
short (see the note there).

* **Lights.** `zone.lights` now holds every place light: `baked: true` for the ones already in the lightmap, except baked
  *area* lights (as pool points they made hard, over-bright highlights; their soft reflections come through the probes).
  Watts → render units: point / spot `W / 4pi`, area `W / 2pi`. The pool has 6 PointLights on both tiers, ranked each
  frame by `intensity / (1 + distance)`, lights in front of the camera and runtime lights first.
  - Lightmapped materials take only the **specular** of the pool lights (`RE_Direct_KzSpec`, lobe widened to roughness
    >= 0.15 because the points stand in for lamps of some size). Unbaked meshes (figures, emissive props) take them fully.
  - Transparent materials (`KZ_NO_DIRECT`) take no pool light at all.
  - Every patched material clamps its linear output at 4.0 before fog and tone mapping (lamp highlights on wet floors
    otherwise bloomed the arrival hall by +1.3 stops).
* **Bloom** (High): strength 0.08, radius 0.3, threshold 2.5. `?bloom=0` turns it off.
* **Probes** now show the lamps (lights visible to camera and glossy rays), except area lights larger than 1 m (proxy panels).
* **Glass** (`transparent` library materials): opacity 0.12 (lava_glass) / 0.2, `envMapIntensity` 0.3, so the lava
  field reads through the window.
* **Paper emitters** (`lantern_paper`, `lantern_andon`, `lantern_andon_plain`, `washi_backlit`): emissive x 1.6 for the
  lamp light passing through the paper (Cycles translucency).
* **Mist.** The mist colour is the probe luminance x 1.5 in a cool neutral (`FOG.mistTint` [0.8, 0.93, 1.1]); fx mist
  patches (sent as negative amounts) count only where the ray *ends* in the patch, over at most 4 m of the ray (before, a
  camera standing in a rim patch misted the whole view). The Mirror water has `scatter` [0, 0, 0].
* **Lightmaps.** When one 2048 atlas would leave a place coarser than the tier's texel_max, `bake_place.py` splits it at
  floor + 3.5 m: walk-level surfaces get `lm_<space>` at the target density, the mass above `lm_<space>_upper` at half
  of it. Parts carry their own `extras.kz.lightmap`; zones list both. Margin 3 px. g_arrival Low walk level: 7.3 cm/texel.
* **Poses.** `data/places.json` takes each Blender place's *concept* camera (pos, heading and pitch from the target);
  the manifest starts at `g_arrival` when it is a Blender place.
