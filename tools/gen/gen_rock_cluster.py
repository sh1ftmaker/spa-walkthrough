"""Wet basalt rock cluster (rock_cluster): 3-5 glossy faceted basalt boulders that interpenetrate.

Targets (measured on refs/gen/sheet-mod-nature.png, panel 4 "Wet basalt cluster - 2.4 m", crop
.scratch/gen40_o/measure_cluster.png):
  * labelled 2.4 m wide and 1.8 m deep (the side view measures 1.82 m on the label scale); tallest crag
    1.15-1.20 m (117 px at 102 px/m).
  * the sheet's own 1 m bar measures 74 px/m, against 102 px/m from the 2.4 m dimension line. The bar is the
    outlier; I built to the labels, as the proxy and the asset row do (guide 1).
  * front silhouette, left to right: small lump 0.25 m; big lobe 1.0 m left of centre; tall crag 1.15 m
    just right of centre with a shoulder; low right slab 0.62 m. Rim highlights along the top edges.
  * side view: one tall tapering crag right of centre, lower lobes either side.

Construction (op07 rebuild on the shared rock recipe, tools/gen/kzgeo_rock_cluster.py):
  * each boulder part is a convex hull of 40 seeded shell points + 7 envelope points (own hull, clamped to
    z >= 0); LOD0 subdivides it (2 cuts) and adds fractal noise along the normals (knobs, dents), then 6 seeded
    chip planes clip it into flat fracture faces with crisp rims. The earlier build (36-point hull, ~330 tris
    at LOD0 against a 3000 budget) read as a few big smooth slabs; the concept shows many small facets.
  * tall crags are two overlapping hulls: a broad base and a narrower pinnacle, so the silhouette is composed.
  * wet top faces (normal z > 0.6) get the top slot, the rest the side slot; moss goes on noise-clustered
    top patches (moss param).
  * two debris chips at the foot of the big parts (LOD0-1 only; not identifying).
  * materials: basalt_wet only, cooled to near-black with the stepping-stone tint (0.32, 0.36, 0.46)
    (side wetness 0.7 x wetness, top = wetness with -0.05 roughness), moss. basalt_dry is not used:
    every surface in the concept reads wet, and the library dry basalt renders paler (guide 7).
  * Every LOD uses the same parts in the same places. Lower LODs drop hull points, displacement and chips.
  * LOD0 47-point hull, 2 cuts + noise + 6 chips; LOD1 37 points, 1 cut + lighter noise + 6 chips; LOD2
    23 points + 3 chips; LOD3 6 envelope points per part. Budget 3000/1200/360/80.

Animation: none. Lighting: lightmap (UV1 from genlib.finish).

Parameters (build kwargs; proxy 2.4 x 1.8 x 1.2 m):
  w        footprint width, 0.8-6 m (default 2.4). All x, y and heights scale with w / 2.4.
  count    2-5 boulders (default: seed-cycled 4, 3, 5). Lower counts drop from the end of the priority list.
  height   height ratio 0.7-1.3 (default 1.0), applied to every crag top.
  facet    facet and displacement scale 0.5-1.5 (default 1.0).
  wetness  0-1 (default 0.8).
  moss     0-0.3 share of top area with moss (default 0.1).
  style    'peaked' | 'twin' | 'flat' (default: seed-cycled peaked, twin, flat).
           peaked = tall pinnacle on the centre crag; twin = the left lobe rises into a second shoulder;
           flat = the lobe base and the slab have walkable flat tops.

Seeds change shape: seed 1 peaked with 4 boulders, seed 2 twin with 3, seed 3 flat table with 5.
Every part draws its own rng stream, and all shape values are drawn before the LOD branches.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_rock_cluster as R

ASSET = 'rock_cluster'
FEATURES = ['2-5 glossy faceted basalt boulders', 'interpenetrating crags', 'tall central pinnacle',
            'low right slab', 'big left lobe']

BASE_W = 2.4
# group, part name, x, y, rx, ry (plan radii, m), top height (m). A group is kept or dropped as a whole.
TEMPLATE = [
    dict(group='peak', name='base', x=0.10, y=0.03, rx=0.60, ry=0.50, top=0.62),
    dict(group='peak', name='pinnacle', x=0.16, y=0.02, rx=0.38, ry=0.34, top=1.12),
    dict(group='lobe', name='base', x=-0.60, y=0.02, rx=0.64, ry=0.54, top=0.52),
    dict(group='lobe', name='top', x=-0.55, y=0.05, rx=0.44, ry=0.40, top=0.92),
    dict(group='slab', name='slab', x=0.74, y=-0.04, rx=0.48, ry=0.40, top=0.62),
    dict(group='front', name='front', x=-0.10, y=-0.55, rx=0.40, ry=0.34, top=0.30),
    dict(group='lump', name='lump_l', x=-0.92, y=0.60, rx=0.30, ry=0.28, top=0.32),
]
GROUP_ORDER = ['peak', 'lobe', 'slab', 'front', 'lump']     # count 2 = peak + lobe; 3 adds slab; 4 front; 5 lump
COUNT_CYCLE = [4, 3, 5]
STYLE_CYCLE = ['peaked', 'twin', 'flat']
DEBRIS_GROUPS = ('peak', 'lobe')


def _groups_for(count):
    keep = GROUP_ORDER[:max(2, min(5, int(count)))]
    return [t for t in TEMPLATE if t['group'] in keep]


def _hull_part(mb, spec, s, height, facet, g, lod, mi_side, mi_top, mi_moss, moss,
               flat_top=None, shift=(0.0, 0.0), top_mul=1.0):
    """one faceted boulder part (kzgeo_rock_cluster.basalt_hull), clamped to the ground.
    All random draws happen before any LOD branch: 40 shell points, 7 envelope points, 6 chip planes."""
    off = Vector((g.uniform(0, 99), g.uniform(0, 99), g.uniform(0, 99)))
    rot = g.uniform(0, 2 * math.pi)
    rx = spec['rx'] * s * g.uniform(0.92, 1.08)
    ry = spec['ry'] * s * g.uniform(0.92, 1.08)
    top = spec['top'] * s * height * top_mul * g.uniform(0.96, 1.04)
    cx = spec['x'] * s + shift[0] * s + g.uniform(-0.02, 0.02) * s
    cy = spec['y'] * s + shift[1] * s + g.uniform(-0.02, 0.02) * s
    shell = R.draw_points(g, 40, rx, ry, top, rmin=0.80)
    # envelope: a broad top (three points, not one apex: a pointed apex reads as a spike or a gem) and a
    # bulging shoulder ring at 45-65 % of the height so the mass is chunky, not a cone
    tx, ty = g.uniform(-0.15, 0.15) * rx, g.uniform(-0.15, 0.15) * ry
    env = [Vector((tx + 0.55 * rx * math.cos(a), ty + 0.55 * ry * math.sin(a), top * g.uniform(0.92, 1.0)))
           for a in (0.3, 2.4, 4.3)]
    for ax, ay in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        k = g.uniform(0.92, 1.0)
        env.append(Vector((ax * rx * k, ay * ry * k, top * g.uniform(0.45, 0.65))))
    chips = R.draw_chips(g, 6, up_bias=0.6, depth=(0.04, 0.12))
    n_shell = C.lod_pick(lod, 40, 30, 16, 0)
    if lod >= 3:
        # LOD3 (80-tri budget): the broad top + the shoulder ring dropped to the ground (a frustum that sits
        # on z = 0; shoulders alone left the hull floating at half height and the parts read as flat shards)
        env = env[:3] + [Vector((p.x * 0.96, p.y * 0.96, 0.0)) for p in env[3:]]
    pts = R.place(shell[:n_shell] + env, (cx, cy, 0.0), rot)
    if flat_top is not None:
        for p in pts:
            p.z = min(p.z, flat_top * top)
    return R.basalt_hull(mb, pts, mi_side, mi_top, ground=0.0,
                         cuts=C.lod_pick(lod, 2, 1, 0, 0),
                         amp=C.lod_pick(lod, 0.035, 0.025, 0.0, 0.0) * facet * s, freq=3.2 / max(0.4, s), off=off,
                         chips=chips[:C.lod_pick(lod, 6, 6, 3, 0)],
                         mi_moss=mi_moss if lod < 3 else None, moss=moss)


def _debris(mb, spec, s, g, lod, mi_side, mi_top):
    """two small chips at the foot of a big part (LOD0-1 only)"""
    if lod >= 2:
        return
    for _ in range(2):
        a = g.uniform(0.0, 2 * math.pi)
        rr = g.uniform(0.07, 0.12) * s
        cx = spec['x'] * s + (spec['rx'] + 0.02) * s * math.cos(a)
        cy = spec['y'] * s + (spec['ry'] + 0.02) * s * math.sin(a)
        fs = C.hull_rock(mb, (cx, cy, 0.0), (rr * 1.3, rr, rr * g.uniform(0.9, 1.3)), mi_side, g,
                         npts=C.lod_pick(lod, 12, 8, 6, 6), ground=0.0, rot=a, rmin=0.78)
        for f in fs:
            if f.is_valid:
                f.material_index = mi_top if f.normal.z > 0.6 else mi_side


def build(lod, seed, w=BASE_W, count=None, height=1.0, facet=1.0, wetness=0.8, moss=0.1, style=None):
    s = w / BASE_W
    # choices drawn once per seed, independent of lod
    style = style or C.cycle(seed, STYLE_CYCLE)
    n = count if count is not None else C.cycle(seed, COUNT_CYCLE)
    moss = max(0.0, min(0.3, float(moss)))
    wet = max(0.0, min(1.0, float(wetness)))
    facet = max(0.5, min(1.5, float(facet)))
    mb = genlib.MeshBuilder()
    side = mb.slot('basalt_wet', wetness=round(0.7 * wet, 3), tint=R.TINT)
    top = mb.slot('basalt_wet', wetness=round(wet, 3), tint=R.TINT, roughness_offset=-0.05)
    mossm = mb.slot('moss', tint=(0.45, 0.55, 0.32)) if moss > 0 else top
    for spec in _groups_for(n):
        g = C.rng(seed, f'rock_{spec["group"]}_{spec["name"]}')
        shift, top_mul, flat_top = (0.0, 0.0), 1.0, None
        if style == 'twin' and spec['name'] == 'top':           # the left lobe rises into a second shoulder
            shift, top_mul = (0.10, 0.0), 1.06
        if style == 'flat' and spec['group'] in ('lobe', 'slab') and spec['name'] in ('base', 'slab'):
            flat_top = 0.92                                      # walkable table top
        _hull_part(mb, spec, s, height, facet, g, lod, side, top, mossm, moss, flat_top=flat_top,
                   shift=shift, top_mul=top_mul)
        if spec['group'] in DEBRIS_GROUPS and spec['name'] in ('base', 'top', 'pinnacle'):
            _debris(mb, spec, s, C.rng(seed, f'debris_{spec["group"]}_{spec["name"]}'), lod, side, top)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    return genlib.finish(o)
