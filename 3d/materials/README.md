# Kazan-yu material library (round 2)

29 materials in five categories: stone; wood, paper & cloth; metal, ice & glass; water; light
sources. They are built from 30 texture sets, which include one shared macro texture and a
side set for rimstone.

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
