# Place model contract (Blender side, v1)

A **place model** is one coherent model for one space: its architecture, rock, terrain and water forms, built as one piece (decision 61), then dressed with the parametric assets. The exporter (`tools/export/`) turns place .blend files into the web contract (`web/ASSET_CONTRACT.md`). Anything that follows this contract bakes and exports without changes to the exporter.

## 1. Files

| What | Where |
|---|---|
| Build script (deterministic, rebuildable) | `tools/place/build_<space>.py`, run as `blender -b -P tools/place/build_<space>.py` |
| Place-specific helpers | `tools/place/kzplace_<space>.py`; shared helpers in `tools/place/kzplace_common.py` (lead-owned; propose additions) |
| Output | `3d/places/<space>.blend` |
| Renders | `3d/renders/places/<space>/canonical.jpg` + `views.jpg` |
| Checks | `3d/checks/places/<space>.json` |

## 2. Space and units

- World space is the **layout space**: metres, x east, y north, z up, with the same numbers as `3d/layout.json` and `3d/spaces/<space>.json`. There is no local offset, and object origins may be anywhere.
- Floors sit at the space's `floor_z`.
- **Portals** are the openings named in the space file (`portals[].at`, `width`, height). They must be open, at floor level, and at least the given width, so the neighbouring place or stand-in joins without a step.
- Build only inside your footprint, plus the rock or structure mass behind your walls (at most about 3 m beyond the footprint). Exception: a view-only backdrop behind glass (lava field, sea, sky) may extend as far as the view needs. A neighbour builds its own side of a shared portal. A shared hero such as a portal arch is built by the owner the brief names.

## 3. Collections (exact names)

| Collection | Contents |
|---|---|
| `kz_render` | Every visible static mesh: the shell and the realized dressing at LOD0. |
| `kz_lod` | Optional: LOD1–3 of dressing objects, each with `kz_lod_of` = the LOD0 object name and `kz_lod` = 1..3. Hidden in renders. |
| `kz_walk` | The walk mesh (contract §8). Positions only. Floors, treads with risers ≤ 0.20 m, walls, rails or curbs at deep water, pool basins. No ceilings. Watertight enough that a 0.3 m capsule can't slip through. Not rendered. |
| `kz_water` | Water surface meshes, one per layout water id. |
| `kz_lights` | Blender lights for the bake, in real units, with `kz_runtime` = true if the runtime needs the light live. Emissive meshes in `kz_render` also light the bake. |
| `kz_probes` | Empties `probe_<space>_<n>` at the capture point, with `kz_box_min` and `kz_box_max` (layout xyz). |
| `kz_fx` | Empties for runtime effects: `kz_fx` = steam, mist, drips, spray, glowworm, etc., plus params. |
| `kz_cameras` | Cameras `cam_entry`, `cam_reveal`, `cam_concept` from the space file (plus any you add). Lens is set from the fov. |
| `kz_anim` | Animated or skinned objects (figures, swaying noren, boats). Exported as separate parts, not baked into the static mesh. |

## 4. Object custom properties (render objects)

| Key | Meaning |
|---|---|
| `kz_role` | floor, wall, ceiling, stair, rail, basin, lantern, water, prop, rock, glass, emissive... (`ceiling` is hidden in dollhouse view) |
| `kz_material` | Library id with optional variant (`basalt_wet`, `hinoki:stained`), matching the assigned library material (`matlib.assign`). Shell objects take one material each. Dressing from `genlib.build` keeps its several slots (the exporter splits by slot; each slot's material must be a library material). |
| `kz_bake` | true (default) means it gets a lightmap. False for water, glass, emissive-only, animated, and tiny props under about 0.3 m (those use probes). |
| `kz_asset`, `kz_seed`, `kz_params` | On dressing objects built with `genlib.build(asset, lod, seed, **params)`. Keep them for re-dressing. |
| `kz_water` | On water meshes: the layout water id. Also set `kz_water_kind` (still / flow / sea), `kz_planar` (bool), `kz_absorption` [r, g, b] and `kz_flow` (speed in m/s; a flow vector or a JSON object with `speed_mps` is also accepted, as the places use). |

- **UVs:** UV0 holds tiling material UVs (generators already provide them). The exporter makes UV1 (the lightmap UVs), so leave it out.
- **Normals:** consistent, outward.

## 5. Budgets (whole place, LOD0, everything in view)

| | High | Low (exporter swaps dressing to LOD1–2 by distance) |
|---|---|---|
| Triangles | ≤ 250k for a hero place, ≤ 80k for a corridor | about half |
| Materials | ≤ 40 distinct library ids (generator parameter variants of one id count once; the exporter merges or atlases them) | |

The exporter merges objects by material per part. Fewer distinct material ids means fewer draw calls.

## 6. Lighting

- Light it as the concept is lit: practical lanterns, lava and glowworm glow, the hero as the brightest thing.
- Same exposure as the generator canonicals: AgX, exposure 0, warm 2700 K practicals.
- No sun or world light indoors. The world colour is near black (0.012, 0.014, 0.018).

## 7. Proof

- **Renders.** `canonical.jpg` is the concept camera, Cycles 128 samples, denoised, with the concept image(s) and the dollhouse strip beside it. `views.jpg` holds the entry and reveal views at 16:9 and 9:16, plus a top-down plan with the walk mesh tinted.
- **Checks** (`3d/checks/places/<space>.json`):
  - triangles and material count;
  - walk-mesh flood fill from every portal reaches every other portal and the hero viewpoint;
  - clearance of at least 2.1 m above the walk mesh along the spine;
  - portals open at floor_z;
  - no dressing floating or sunk by more than 2 cm (raycast at each object's base).
