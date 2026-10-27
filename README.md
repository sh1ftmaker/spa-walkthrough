# Kazan-yu 火山湯

A fictional luxury spa inside a dormant volcano. It is modelled in Blender, with lighting baked in Cycles, and ships as a three.js walkaround built to run on a phone.

- **Walkthrough:** https://sh1ftmaker.github.io/spa-walkthrough/
- **Model gallery and 3D browser:** https://sh1ftmaker.github.io/spa-walkthrough/gallery.html

## Where it stands

| | |
|---|---|
| Parametric models | 132 generators. Each has 4 LODs and seeded variants, and its own check sheet and canonical render. They were built one round each, and review rounds are still to come. |
| Materials | 59 library materials, shader-based with KTX2 textures, calibrated under a warm 2700 K key. |
| People | Guest and staff figures on a shared 24-bone rig, with 13 self-made animation clips. |
| Places | The vertical slice: arrival hall, mist corridor and Obsidian Mirror. Each is one coherent place model, baked and exported to the web. Every other space is still a stand-in built from the layout. |
| Web | The three.js runtime has lightmaps, probes, planar water reflection, fog and mist, glowworm sprites, and Low and High tiers. Low stays at or under 150 draw calls and about 400k triangles. |

## Layout

```
AGENT_PROMPT_3D.md, layout-spec.md   brief and spatial spec
lookbook/, images/, refs/gen/        concept paintings, dollhouse cutaways, reference sheets
3d/layout.json, 3d/spaces/*.json     metric layout and per-space design intent
3d/asset_list.csv, 3d/assets.json    master asset list and proxies (default sizes)
3d/decisions.md                      every decision and why
3d/PLACE_CONTRACT.md                 how a place model is structured for bake and export
3d/materials/                        material library (kzmaterials.js, kzshader.js, tex/*.ktx2)
3d/renders/                          canonical renders, LOD sheets, place renders, web captures
3d/checks/                           check results (generators, places, web)
tools/gen/                           generators: gen_<asset>.py + kzgeo_* helpers, genlib, GUIDE.md
tools/matlib/                        material library build, calibration, previews
tools/place/                         place-model build scripts
tools/export/                        bake (Cycles lightmaps, probes) and export (meshopt GLB, KTX2)
web/                                 the three.js walkaround and gallery (see web/ASSET_CONTRACT.md)
```

## Rebuilding

The .blend files, bakes and web asset packages are build outputs and aren't committed. To rebuild them you need Blender 5.2 (OptiX for baking) and Node 22.

```bash
# one model: build + LOD check sheet (writes 3d/assets/<asset>.blend)
blender -b -P tools/gen/render_lod_sheet.py -- <asset>
.venv/bin/python tools/gen/compose_lod_sheet.py <asset>

# one place model, then bake + export it for the web
blender -b -P tools/place/build_<space>.py
tools/export/run_chain.sh <space> both

# web: merges stand-in + exported places, builds dist/
cd web && npm ci && npm run build
```
