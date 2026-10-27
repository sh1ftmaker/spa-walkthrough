# Kazan-yu web asset contract (v1)

This is the interface between the Blender export pipeline and the three.js walkaround in `web/`.
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
