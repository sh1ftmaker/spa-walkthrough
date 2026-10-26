# Kazan-yu material library

26 materials in five categories (stone; wood, paper & cloth; metal, ice & glass; water; light sources).
Contact sheet: `3d/renders/materials/sheet.jpg`. Per-material previews: `3d/renders/materials/<id>.jpg`.
Manifest for the web app: `3d/materials.json`.

## Rebuild

```bash
B=/home/agent-tom/.local/bin/blender
$B -b -P tools/matlib/build_library.py      # groups + materials + tiling PNGs + materials.json (~30 s)
python3 tools/matlib/encode_ktx2.py         # PNG -> 3d/materials/tex/*.ktx2, marks them encoded in materials.json
$B -b -P tools/matlib/render_previews.py    # sphere + swatch per material (Cycles/OptiX, AgX)
python3 tools/matlib/contact_sheet.py       # 3d/renders/materials/sheet.jpg
```

Options: `build_library.py -- --skip-bake` reuses the PNGs; `render_previews.py -- --only id,id`.
Tiling PNG sources are build intermediates in `.scratch/matlib/tex/`.

Files: `library_defs.py` (material data + procedural patterns), `kzdsl.py` (node DSL),
`kzimg.py` (PNG / normal maps), `matlib.py` (asset helper), `build_library.py`,
`encode_ktx2.py`, `render_previews.py`, `contact_sheet.py`, all in `tools/matlib/`.

## How a material is built

Each material has one group node named `KZ` (`KZM_<id>`) with the same 7 settings:

| setting | meaning |
|---|---|
| `tint` | linear RGB multiplier on albedo, worn colour, emission and water/ice absorption |
| `wetness` | 0..1 water film: darkens porous albedo, roughness goes to 0.04, low areas first |
| `wear` | 0..1 polish or abrasion of high points towards the material's worn colour, roughness and metal |
| `roughness_offset` | added to roughness |
| `scale` | metres per texture repeat (UV0 is in metres) |
| `normal_strength` | detail normal / bump strength |
| `emissive_level` | emission multiplier (0 = off) |

Inside, `KZ_Tile` divides UV by `scale`. Then either a procedural pattern `KZP_<id>` (stone,
metal, ice, glass, water, lights) or the baked tiling images (wood, paper and cloth) feed the shared
`KZ_Core`, which applies the settings. Every pattern samples its noise through a flat 4D
torus, so all patterns tile exactly. `KZ_Core` uses only data that is also in the web textures
(albedo, ORM, height). `materials.json → kz_core.formulas` gives the same maths for the three.js
shader.

## Using it from an asset generator

UV0 must be in metres (1 UV unit = 1 m).

```python
import sys; sys.path.insert(0, '/home/agent-tom/Desktop/volcanospa/tools/matlib')
import matlib

matlib.assign(obj, 'basalt_wet')                                   # library defaults
matlib.assign(obj, 'hinoki', slot=1, wear=0.4, tint=(0.9, 0.85, 0.8))
matlib.assign(obj, 'neon_tube', variant='cyan')                    # named variant from materials.json
mat = matlib.material('paving', wetness=0.8)                       # just get the material
```

`assign()` appends the library material once and re-uses the shared node groups (no `.001`
copies). Different params create a thin variant material named `<id>~<hash>`, which is a copy of
the one-node material with new `KZ` inputs. Identical params reuse the same variant. Every
material carries `mat["kz_id"]` and `mat["kz_params"]` (JSON). Export them to glTF extras so
the web app can rebuild the material from `materials.json`. Unknown setting names raise `KeyError`.
Need something the library lacks? Ask for a new library material; don't make one-off materials.

## Web textures (per texture set, `3d/materials/tex/`)

| file | content | encoding |
|---|---|---|
| `<id>_base.ktx2` | albedo, sRGB (alpha = foam coverage for transparent materials) | UASTC (1024² close-up sets) or ETC1S |
| `<id>_orm.ktx2` | R occlusion, G roughness, B metalness, A height, linear | UASTC + zstd |
| `<id>_nh.ktx2` | R,G normal XY (OpenGL/glTF +Y), B height, A 1, linear | UASTC + zstd |
| `lava_emis.ktx2` | emission colour, sRGB | ETC1S |

All sets have full mip chains generated with wrap addressing. Texture sizes are 512², except 1024²
for wet basalt, obsidian, hinoki, tatami and paving. `washi_backlit` shares the washi textures.
The normal map is not encoded in UASTC "normal mode", because that layout (RGB=X, A=Y) has no room
for height. UASTC transcodes losslessly to ASTC on phones.

All textures are self-made procedurally (CC0). The source for each one is listed in
`materials.json → texture_source`.
