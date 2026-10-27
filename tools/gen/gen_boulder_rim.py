"""Pool-rim boulder (boulder_rim): a single rounded, faceted wet basalt boulder with a flat-ish top that sits
half in the pool water. The most instanced rock (647 placed), so LOD3 stays under 60 tris.

Targets (refs/gen/sheet-mod-nature.png, panels "Pool-rim boulder S / M / L", labels 0.6 / 1.2 / 1.8 m;
the drawn 1 m bars measure ~72 px/m against ~141 px/m from the M label, so I built to the labels as the
proxy and the row do, guide 1):
  * M: label 1.2 m = 169 px; front height ~110 px -> h/w 0.65; side view a little narrower -> d/w 0.83.
    Proxy 1.2 x 1.0 x 0.7 -> default build 1.2 x 1.0 x 0.68.
  * S: 0.6 m = 102 px, height ~77 px -> h/w 0.75 (rounder); L: 1.8 m = 212 px, height ~130 px -> h/w 0.6
    (the L rock also spreads past its arrow: ~1.15 x the label).
  * silhouette: broad belly at 30-40 % of the height, rounded shoulders, a flat-ish lumpy top (the M top is
    nearly flat over 60 % of the width), widest at the base (it is sunk, the waterline cuts the belly).
  * surface: many planar fracture facets and chips with glossy rims, one near-black wet material.

Construction: one convex hull (kzgeo_rock_cluster.basalt_hull) of 64 seeded shell points on an ellipsoid
whose centre sits 0.3 h above the ground (so the ground cuts the belly: wide base, no undercut), clamped to
a flat top at (1 - 0.22 x flatness) of the ellipsoid top; LOD0 subdivides 3 cuts + fractal noise, then
8 chip planes (up-biased so the top stays flat-ish) clip fracture facets. Style 'split' adds a second lobe
hull leaning on the first, so the top shows a cleft; it stays one boulder at every LOD.

Parameters (build kwargs; proxy 1.2 x 1.0 x 0.7, embed 0.2):
  size      'S' 0.6 | 'M' 1.2 | 'L' 1.8 m, or a number (width in m). Default 'M'.
  flatness  0-1 (default seeded 0.45-0.8): how much of the top is cut flat.
  embed     metres the placer sinks the boulder into the water/bed (default 0.2 x w/1.2); written as
            kz_embed, and the wetter 'waterline' slot covers faces below 1.4 x embed.
  wetness   0-1 (default 0.85): top wetness; sides 0.7 x, the splash band 1.0.
  style     'dome' | 'table' | 'wedge' | 'split' (default: seed-cycled in that order, so 4 seeds = 4 styles).
            dome = rounded crown; table = broad flat top; wedge = top tilted 8-14 deg, one high side;
            split = two lobes with a cleft.

Seeds change: style (cycle), plan aspect 0.72-0.86, height x0.9-1.1, rotation, top tilt, chip layout.
Every part has its own rng stream; all draws happen before the LOD branches.

LOD: same hull points at LOD0-1 (LOD0 3 cuts; LOD1 2 cuts, 1 on split lobes, light noise), LOD2 the same shell points, no cut, LOD3 a
separate 12-point envelope drawn every LOD (always the same points). Budget 2500/1000/300/60.
Materials: basalt_wet cooled near-black (TINT), slots top / side / waterline. Animation: none.
Lighting: lightmap (UV1 from genlib.finish).
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_rock_cluster as R

ASSET = 'boulder_rim'
FEATURES = ['single rounded wet basalt boulder', 'flat-ish top', 'faceted chips', 'sits half in water']
SIZES = {'S': 0.6, 'M': 1.2, 'L': 1.8}
HW = {'S': 0.75, 'M': 0.57, 'L': 0.55}          # h / w (M from the proxy 0.7 / 1.2 incl. a 2 % margin)
STYLES = ['dome', 'table', 'wedge', 'split']


def _size(size):
    if isinstance(size, str):
        return SIZES[size.upper()], HW[size.upper()]
    w = float(size)
    hw = 0.75 + (0.57 - 0.75) * min(1.0, max(0.0, (w - 0.6) / 0.6)) if w < 1.2 else 0.57 - 0.02 * min(1.0, (w - 1.2) / 0.6)
    return w, hw


def _lobe(mb, g, lod, W, D, H, cx, cy, rot, flat, tilt, slots, n_shell0=64, split=False):
    side, top, wl, embed = slots
    off = Vector((g.uniform(0, 99), g.uniform(0, 99), g.uniform(0, 99)))
    rx, ry = W / 2 * 1.08, D / 2 * 1.08             # the ground cuts the ellipsoid at ~0.93 r
    zc = 0.30 * H                                   # ellipsoid centre: the ground cuts the belly
    rz = H - zc
    shell = R.draw_points(g, n_shell0, rx, ry, rz, rmin=0.96)
    env = []                                        # LOD3 envelope: base ring, belly ring, top points
    for i in range(6):
        a = 2 * math.pi * (i + g.uniform(-0.2, 0.2)) / 6
        env.append(Vector((math.cos(a) * rx * 0.93, math.sin(a) * ry * 0.93, -zc)))
    for i in range(6):
        a = 2 * math.pi * (i + 0.5 + g.uniform(-0.2, 0.2)) / 6
        env.append(Vector((math.cos(a) * rx * 1.0, math.sin(a) * ry * 1.0, 0.1 * H)))
    for i in range(3):
        a = 2 * math.pi * (i + g.uniform(-0.2, 0.2)) / 3
        env.append(Vector((math.cos(a) * rx * 0.5, math.sin(a) * ry * 0.5, rz)))
    chips = R.draw_chips(g, 8, up_bias=0.9, depth=(0.03, 0.09))
    if lod >= 3:
        local = env
    else:
        local = shell[:C.lod_pick(lod, 64, 64, 64, 0)]
    pts = R.place(local, (cx, cy, zc), rot)
    # flat-ish top, tilted for the wedge style: clamp each point under a plane
    z_top = H * (1.0 - 0.22 * flat)
    tx, ty = tilt
    for p in pts:
        lim = z_top + tx * (p.x - cx) + ty * (p.y - cy)
        if p.z > lim:
            p.z = lim + (p.z - lim) * 0.15        # soft clamp keeps a slight crown, no knife plane
    faces = R.basalt_hull(mb, pts, side, top, ground=0.0,
                          cuts=C.lod_pick(lod, 3, 2 if n_shell0 > 40 and not split else 1, 0, 0),
                          amp=C.lod_pick(lod, 0.03, 0.018, 0.0, 0.0) * W / 1.2, freq=3.0 * 1.2 / W, off=off,
                          chips=chips[:C.lod_pick(lod, 8, 8, 4, 0)], top_thresh=0.55)
    for f in faces:                               # waterline band: wetter, polished
        if f.is_valid and f.material_index == side and f.calc_center_median().z < 1.4 * embed:
            f.material_index = wl
    return faces


def build(lod, seed, size='M', flatness=None, embed=None, wetness=0.85, style=None):
    W0, hw = _size(size)
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'layout')
    aspect = g.uniform(0.72, 0.86)
    hmul = g.uniform(0.9, 1.04)
    rot = g.uniform(-0.5, 0.5)
    fl = g.uniform(0.45, 0.8) if flatness is None else max(0.0, min(1.0, float(flatness)))
    ta = math.radians(g.uniform(8, 14)) * (1 if g.random() < 0.5 else -1)
    ld = g.uniform(-0.7, 0.7)                                 # split: where the second lobe sits
    if style == 'table':
        fl = max(fl, 0.85)
    if style == 'dome':
        fl = min(fl, 0.4)
    W, D, H = W0, W0 * aspect, W0 * hw * hmul
    emb = (0.2 * W0 / 1.2) if embed is None else float(embed)
    wet = max(0.0, min(1.0, float(wetness)))
    mb = genlib.MeshBuilder()
    m_side = mb.slot('basalt_wet', wetness=round(0.7 * wet, 3), tint=R.TINT)
    m_top = mb.slot('basalt_wet', wetness=round(wet, 3), tint=R.TINT, roughness_offset=-0.05)
    m_wl = mb.slot('basalt_wet', wetness=1.0, tint=R.TINT, roughness_offset=-0.08)
    slots = (m_side, m_top, m_wl, emb)
    tilt = (math.tan(ta) * math.cos(rot), math.tan(ta) * math.sin(rot)) if style == 'wedge' else (0.0, 0.0)
    if style == 'split':
        # two lobes: the main one 80 % wide, a lower lobe leaning on it; the cleft between them reads on top
        _lobe(mb, C.rng(seed, 'lobe_a'), lod, W * 0.78, D * 0.95, H, -0.11 * W * math.cos(ld), -0.05 * D, rot, fl, tilt, slots, split=True)
        _lobe(mb, C.rng(seed, 'lobe_b'), lod, W * 0.55, D * 0.8, H * 0.82, 0.22 * W, 0.08 * D * ld, rot + 0.6, fl, tilt,
              slots, n_shell0=40, split=True)
    else:
        _lobe(mb, C.rng(seed, 'lobe_a'), lod, W, D, H, 0.0, 0.0, rot, fl, tilt, slots)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    C.set_json_props(o, kz_embed=round(emb, 3), kz_style=style)
    return genlib.finish(o)
