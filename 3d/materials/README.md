# Kazan-yu material library (round 2)

32 materials in five categories: stone; wood, paper & cloth; metal, ice & glass; water; light
sources. They are built from 33 texture sets, including one shared macro texture.

Where to look:
- Contact sheet: `3d/renders/materials/sheet.jpg`
- Previews: `3d/renders/materials/<id>.jpg` (sphere and swatch, stepped pool, or dark room)
- Real-scale corner: `scale/<id>.jpg` (neutral surround) and `scale/<id>__context.jpg`
- Raking close-up: `close/<id>.jpg`
- 10 × 10 m repeat view: `repeat/<id>.jpg` and `repeat/<id>__vs_concept.jpg`
- Tiling checks: `tiles/<id>.jpg`
- Round 0 against round 2: `compare/<id>.jpg` (round-0 renders are kept in `r0/`)

Manifest: `3d/materials.json`.

## Rebuild

```bash
B=/home/agent-tom/.local/bin/blender
$B -b -P tools/matlib/build_library.py           # generators -> shipping PNGs (+ORM mips) -> library.blend + materials.json (~45 s)
python3 tools/matlib/encode_ktx2.py              # PNG -> 3d/materials/tex/*.ktx2, sizes into materials.json
$B -b -P tools/matlib/render_previews.py         # previews (calibrated rig, see kzrig.py)
$B -b -P tools/matlib/render_scale_previews.py   # scale/, close/, repeat/
python3 tools/matlib/tile_checks.py              # tiles/
python3 tools/matlib/compare.py                  # compare/, repeat/*__vs_concept
python3 tools/matlib/contact_sheet.py            # sheet.jpg
```

The files are in `tools/matlib/`:
- `library_defs.py`: material data and the procedural pattern generators
- `kzdsl.py`: the node DSL
- `kzimg.py`: PNG writing, normals, cavity AO and Toksvig mips
- `kzrig.py`: the preview rig
- `matlib.py`: the asset helper

## Shader-first (round 3): shader kit + CC0 scans

Most materials are now a **parametric shader** rather than a fixed texture set.
- **Web:** `kzShade(material, cfg)` from `3d/materials/kzshader.js`, configured per material by
  `KZM[id]` in `3d/materials/kzmaterials.js`. These are the canonical copies, generated from
  `3d/research/shaders/` by `tools/matlib/kzkit.py`. The kzshader copy carries one library patch:
  a large hot/cool mask, downhill flow bands and temperature-graded seams for lava.
- **Manifest:** each kit material in `materials.json` carries `kzTech`, `kzBase`/`kzNh` (and
  `kzBase2`/`kzNh2`), `kzNoise`, `plateM` and the full `kz` config. The library texture sets
  remain as the fallback.
- **Blender** (`library.blend`, `KZM_<id>`) mirrors kzShade:
  - hex-tiling: `KZ_HexGrid`, 3 taps, per-tile rotation, normals rotated back as height derivatives, w^7 × height weights
  - biplanar/triplanar world projection for cave rock, a floor projection for sand
  - plank shuffle
  - world macro noise (brightness, hue, wet patches, run-off streaks)
  - wet film
  - overlays: basalt chips, obsidian facets, lava seams as emission with large-scale masks
- **Normals** are built as a surface gradient. For the Cycles irradiance bake, set the view-layer
  property `kz_bake = 1`: every KZ material then uses geometric normals only, so normal detail
  stays out of the lightmap (kit README §7).

Texture inputs per kit material are either a Codex plate from the kit
(`3d/research/shaders/demo/tex/pl/`, with fixes in `kzkit.FIX`) or a **CC0 scan**
(`kzkit.SCANS`, `SCANS_B`). Each is converted to `pl_<asset>_{base,nh}` at 512 or 1024 px:
- base: sRGB
- nh: RG normal, B height, A wet-film mask

Only the shipped KTX2 is stored. The 2K source maps stay in `.scratch/cc0mat/`.

| material | texture source | licence |
|---|---|---|
| basalt_wet | Poly Haven dark_rock_02, https://polyhaven.com/a/dark_rock_02 (darkened, cooled; wet look from the film layer) | CC0 1.0 |
| basalt_dry | Poly Haven dark_rock, https://polyhaven.com/a/dark_rock (albedo lifted ×2.2) | CC0 1.0 |
| paving | Poly Haven slab_tiles, https://polyhaven.com/a/slab_tiles (plain tiling, joints darkened) | CC0 1.0 |
| tatami | Poly Haven tatami_mat, https://polyhaven.com/a/tatami_mat | CC0 1.0 |
| black_sand | Poly Haven sand_02, https://polyhaven.com/a/sand_02 (near-black) | CC0 1.0 |
| ash_clay | Poly Haven clay_plaster, https://polyhaven.com/a/clay_plaster (desaturated) | CC0 1.0 |
| cave_rock | self-made Codex tile refs/gen/tile-cave-rock.png (4 m; ships as pl_tile_cave_rock, darkened) | owner-approved, self-made |
| stepping_stone | Poly Haven seaside_rock, https://polyhaven.com/a/seaside_rock | CC0 1.0 |
| hinoki | Poly Haven japanese_cedar_planks, https://polyhaven.com/a/japanese_cedar_planks (aged tint) | CC0 1.0 |
| noren | Poly Haven rough_linen, https://polyhaven.com/a/rough_linen (recoloured indigo) | CC0 1.0 |
| iron | Poly Haven metal_plate_02, https://polyhaven.com/a/metal_plate_02 (black oxide, rust in pits) | CC0 1.0 |
| bark | Poly Haven pine_bark, https://polyhaven.com/a/pine_bark (Dimitrios Savva; 2 m) | CC0 1.0 |
| linen | Poly Haven rough_linen, https://polyhaven.com/a/rough_linen (neutral off-white weave; colour via tint) | CC0 1.0 |
| noren | (same rough_linen scan, neutral weave; indigo default tint, variants black / vermilion / cream) | CC0 1.0 |
| ceramic | self-made procedural glaze (library_defs.pat_ceramic); variants tenmoku / white / celadon | self-made |
| moss | ambientCG Moss002, https://ambientcg.com/a/Moss002 (1K, 1 m) | CC0 1.0 |
| kawara, gold_leaf, lacquer_black, terry, glass_clear | self-made procedural (library_defs pat_kawara / pat_gold_leaf / pat_lacquer / pat_terry / pat_glass_clear) | self-made |
| foliage_fern, blossom, maple_leaf | self-made procedural alpha cards (kzkit gen_fern / gen_blossom / gen_maple) | self-made |
| gravel, koi, lantern_andon_plain | self-made procedural (library_defs pat_gravel / pat_koi / pat_lantern_plain) | self-made |
| lava_molten, mirror, copper, wicker, food, broth, ceramic_tenmoku, sinter_amber, skin, hair, lacquer_dark (clean) | self-made procedural (library_defs pat_*) | self-made |
| lacquer_mottled | self-made Codex plate (old lacquer_dark look) | owner-approved, self-made |
| foliage_pine | self-made procedural needle-tuft alpha card (tools/matlib/kzkit.py gen_pine_needles) | self-made |
| bamboo | ambientCG Bamboo001B, https://ambientcg.com/a/Bamboo001B | CC0 1.0 |
| rope | ambientCG Rope001, https://ambientcg.com/a/Rope001 | CC0 1.0 |
| rimstone, sinter, lava, lava_flow, glacier_ice, washi, washi_backlit, bronze | self-made Codex seamless tiles refs/gen/tile-*.png (pl_tile_*) | owner-approved, self-made |
| obsidian, lacquer_dark | self-made Codex plates (kit) | owner-approved, self-made |
| water, glass, neon, lanterns, caustics, macro | procedural (library) | self-made |

Licence quotes are in `.scratch/cc0mat/README.md`. No attribution is required. If the owner wants
a credits line: "Textures from Poly Haven (polyhaven.com) and ambientCG (ambientCG.com), CC0 1.0."

## Painted plates (round 2 library sets, now the fallback)

25 sets come from the owner-approved, self-made Codex plates:
`refs/gen/sheet-tex-{stone,rock,wood,cloth}.png`, a 3×2 grid of about 480 px plates per sheet.
`tools/matlib/plates.py` processes each plate in these steps:

1. **Cut.** The plate is cut out of the gutters, which are found automatically.
2. **Resample.** Lanczos-3, to the working texel size.
3. **De-light.** Painted specular highlights are found against a local median and removed from
   albedo; they become the gloss and wet-film mask. A residual low-frequency lighting gradient is
   divided out of the luminance.
4. **Make seamless.** Periodic image quilting (Efros–Freeman blocks with min-error boundary cuts
   that wrap around the tile edges), with a reuse penalty. The plate is rearranged over a tile 2–4×
   its area instead of being repeated. Isotropic materials also use rotated and flipped blocks.
   Boards, culms and ribs are cropped at their joints and quilted along the grain only. Hinoki,
   bamboo and lacquer are built from 2–4 independently quilted strips, so neighbouring boards differ.
5. **Derive the maps.** Height from frequency-separated log luminance (three bands in metres, with
   darks pushed deep). Normal and cavity AO from that height. Roughness from a per-material
   luminance or height curve plus the gloss mask. Metal from hue (bronze verdigris is non-metal),
   emission from hot or glowing pixels (lava, lantern ribs), and foam from white, unsaturated pixels.

The recipes are in `library_defs.PLATES`: plate, metres across the plate, quilting settings,
albedo target, roughness curve and rule. Obsidian is a hybrid: its albedo comes from the plate and
its height and roughness from the procedural planar facets. These materials stay procedural:
water_still, waterfall, caustics_decal, neon_tube, lantern_andon, lava_glass and the macro texture.
New materials from the plates: `cave_rock`, `stepping_stone` and `sinter`.

## How a material is built

The library materials sample the **shipped** texture sets: the same 512/1024 px PNGs that become
KTX2. So Blender shows exactly what the phone gets. The procedural generators (`KZP_<set>`) stay
in `library.blend` as the source of those textures.

Each material is one group node named `KZ` (`KZM_<id>`). It exposes the same 7 settings:

| setting | meaning |
|---|---|
| `tint` | linear RGB multiplier on albedo, worn colour, emission and absorption |
| `wetness` | 0..1 water film. Darkens porous albedo. Films in hollows and wet-mask pockets go mirror-wet (roughness 0.04); tops stay damp (0.32). |
| `wear` | 0..1. Moves high points towards the material's worn colour, roughness and metal (wood: silvering, capped at 60 %) |
| `roughness_offset` | added to roughness |
| `scale` | metres per repeat along u (UV0 in metres; `uv_mode: object` materials keep 1) |
| `normal_strength` | detail normal strength |
| `emissive_level` | emission multiplier (0 = off) |

Inside `KZM_<id>`:
- `KZ_Tile` turns metric UVs into tile coordinates, so non-square tiles work (hinoki is 2 m × 0.25 m; bamboo is 0.25 m around × 1 m along).
- The texture set feeds the shared `KZ_Core`, together with an optional side set blended by world normal (rimstone) and the shared 8 m macro texture.
- `KZ_Core` applies the settings with the formulas in `materials.json → kz_core.formulas`; the web shader uses the same ones.

## Textures per set (`3d/materials/tex/`)

| file | content |
|---|---|
| `<set>_base.ktx2` | albedo, sRGB. A = mask: foam (water/ice/glass), thinness (paper), coverage (decals) |
| `<set>_orm.ktx2` | R occlusion (pattern AO × cavity baked from height), G roughness, B metal, A height. The mip chain carries Toksvig roughness. |
| `<set>_nh.ktx2` | R,G normal XY (OpenGL/glTF +Y), B height, A wet-film mask |
| `<set>_emis.ktx2` | emission, sRGB (× `emissive.map_scale`) |
| `kz_macro_base.ktx2` | shared, linear, 8 m repeat: R brightness, G hue, B wetness/roughness, A vertical stain streaks |

On walls, V points up, because drip streaks and run-off run along v.

Asset-side controls (vertex colour or uniforms):
- the waterline and shoreline wetness masks
- walking-path polish
- condensation bands on glass
- per-board offset, flip and tint on hinoki
- per-pole v offset on bamboo
- hem fade on noren

## Using it from an asset generator

```python
import sys; sys.path.insert(0, '/home/agent-tom/Desktop/volcanospa/tools/matlib')
import matlib
matlib.assign(obj, 'basalt_wet')                                   # library defaults
matlib.assign(obj, 'hinoki', slot=1, wear=0.4, tint=(0.9, 0.85, 0.8))
matlib.assign(obj, 'hinoki', variant='dark_timber')                # named variants from materials.json
matlib.assign(obj, 'water_still', variant='mirror')                # Obsidian Mirror pool
mat = matlib.material('paving', wetness=0.8)
```

`assign()` appends the library material once and reuses the shared node groups. Different params
create a thin variant `<id>~<hash>`: a copy of the one-node material with new `KZ` inputs.
Each material carries `mat["kz_id"]` and `mat["kz_params"]`; export them to glTF extras.
If an asset needs something the library lacks, ask for a new library material.

## Phone notes

Water, ice and glass do not use transmission on the phone. They use:
- depth-fade colour
- a fake under-glow emissive
- the normal texture sampled twice at two scales
- a caustics decal
- alpha panes

Each material's `three.note` gives the details. All textures are self-made procedurally (CC0);
`materials.json → texture_source` records the source of each one.
