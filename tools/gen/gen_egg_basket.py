"""Bamboo egg basket on a rope (onsen-tamago basket lowered into the spring steam at the Spring Source, s_spring).

Identifying features kept at every LOD: bell-shaped woven bamboo basket, the dark bound rim, the rope rising from
the crown.

Targets (measured / derived):
  * lookbook 30 (spring source D2, crop .scratch/op24/c_eggs30.png): four bell / egg-shaped open-weave baskets
    hanging on single ropes from the gantry beam, about as tall as a bather's head-and-shoulders; body h:w ~ 1.1-1.3,
    widest in the lower third, domed crown narrowing to a small collar where the rope ties on; a darker bound rim at
    the mouth; weave reads as a fine lattice (vertical splits + horizontal courses).
  * lookbook 24 (cutaway, Spring Source with Egg Baskets): baskets hang in steam a little above the water.
  * Row: r 0.15-0.30 m, h 0.30-0.60 m; dims 0.5 x 0.5 x 0.6 m; budget 800/320/100/30.  Proxy 0.5 x 0.5 x 0.6.
  Built: body radius R 0.19-0.24 m (w 0.40-0.49 incl. rim binding), body height 0.34-0.42 m, collar + bail
  + rope stub to the 0.6 m proxy height (rope_length default fills the proxy; longer ropes are runtime: the
  gantry records its hang points and the basket's kz_anim carries the rope length to draw / lower).

Construction (one mesh): woven shell (lathe whose ring verts alternate in / out by 3.5 mm in a checker, rib or
coil pattern so the weave reads in geometry at LOD0), shallow domed base, bound rim hoop at the mouth (2 rings,
darker bamboo), crown collar band, a bent-bamboo bail loop over the crown, a rope knot and a twisted rope stub up to
the hang point.

Parameters (defaults inside the proxy):
  r        0.15-0.30 m   body max radius (default seeded 0.19-0.24)
  h        0.30-0.60 m   body height, rim to crown (default seeded 0.34-0.42, capped so the whole fits 0.6 m)
  weave    'check' | 'rib' | 'coil'   (default seeded per style)
  rope_length  m above the bail (default: whatever fills the 0.6 m proxy, >= 0.06)
  style    'bell' | 'egg' | 'cloche'   (cycles with the seed: 1 bell, 2 egg, 3 cloche)
Seeds change: silhouette style (flared bell / ovoid egg narrow at the mouth / straight-sided cloche), radius,
height, weave pattern, bail orientation, rim depth.

Materials: bamboo scale 0.35 (shell, bail), rope tint (0.62, 0.55, 0.48) (cord-wrapped rim binding, crown collar; a
tinted-bamboo band rendered copper-metallic), rope (knot,
rope stub).
Animation: rigid (lowered and raised on its rope) + vertex rope sway.  obj['kz_anim'] = {type: 'hang', pivot:
[0, 0, top], rope_length, raise_range_m, attr: '_sway'}; float POINT attribute '_sway' = 0 at the hang point ->
1 at the basket mouth, also colour attribute 'kz_sway' (R).  Lighting: probe (moving), no lights.
"""
import json
import math

import bmesh

import genlib
import kzgeo_common as C

ASSET = 'egg_basket'
FEATURES = ['bell-shaped woven bamboo basket', 'dark bound rim', 'rope rising from the crown']
STYLES = ['bell', 'egg', 'cloche']

# profiles: (radius fraction of R, height fraction of H) mouth -> crown
PROF = {
    'bell': [(1.0, 0.0), (0.985, 0.1), (0.93, 0.3), (0.84, 0.5), (0.72, 0.68), (0.56, 0.83), (0.36, 0.94), (0.2, 1.0)],
    'egg': [(0.74, 0.0), (0.9, 0.1), (0.99, 0.28), (1.0, 0.45), (0.93, 0.63), (0.76, 0.8), (0.48, 0.93), (0.2, 1.0)],
    'cloche': [(1.0, 0.0), (1.0, 0.16), (0.98, 0.38), (0.93, 0.58), (0.8, 0.76), (0.58, 0.9), (0.34, 0.97), (0.2, 1.0)],
}


def params(seed, r=None, h=None, weave=None, rope_length=None, style=None):
    g = C.rng(seed, 'shape')
    P = dict(style=style or C.cycle(seed, STYLES))
    P['r'] = float(r) if r else g.uniform(0.19, 0.235)
    P['h'] = float(h) if h else g.uniform(0.34, 0.42)
    P['weave'] = weave or {'bell': 'check', 'egg': 'coil', 'cloche': 'rib'}[P['style']]
    if not weave and g.random() < 0.25:
        P['weave'] = C.pick(seed, 'weave', ['check', 'rib', 'coil'])
    P['rim_h'] = g.uniform(0.022, 0.034)
    P['bail_yaw'] = g.uniform(0, math.pi)
    P['bail_h'] = g.uniform(0.06, 0.08)
    top = P['h'] + 0.012 + P['bail_h']
    P['rope'] = float(rope_length) if rope_length else max(0.06, genlib.proxy(ASSET)['h'] - top)
    return P


def _shell(mb, R, H, prof, segs, rings, weave, groove, mi):
    """woven shell: lathe with checker / rib / coil offsets; returns the crown ring radius / z"""
    bm = mb.bm
    # resample the profile to `rings` rings (linear in the profile polyline)
    pts = [(R * a, H * b) for a, b in prof]
    L = [0.0]
    for (x0, z0), (x1, z1) in zip(pts[:-1], pts[1:]):
        L.append(L[-1] + math.hypot(x1 - x0, z1 - z0))
    out = []
    for j in range(rings):
        s = L[-1] * j / (rings - 1)
        for i in range(len(pts) - 1):
            if L[i + 1] >= s - 1e-9:
                t = (s - L[i]) / max(1e-9, L[i + 1] - L[i])
                out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t))
                break
    ring_vs = []
    for j, (rr, z) in enumerate(out):
        vs = []
        for k in range(segs):
            if weave == 'check':
                off = groove * ((k + j) % 2)
            elif weave == 'rib':
                off = groove * (k % 2)
            else:
                off = groove * (j % 2)
            if j in (0, rings - 1):
                off = 0.0
            a = 2 * math.pi * k / segs
            vs.append(bm.verts.new(((rr - off) * math.cos(a), (rr - off) * math.sin(a), z)))
        ring_vs.append(vs)
    faces = []
    for A, B in zip(ring_vs[:-1], ring_vs[1:]):
        faces += C.bridge_rings(bm, A, B)
    # shallow domed base (rises 12 % of R into the basket): a fan to a centre vertex
    c = bm.verts.new((0, 0, 0.12 * R * 0.5))
    A = ring_vs[0]
    for k in range(segs):
        faces.append(bm.faces.new((A[(k + 1) % segs], A[k], c)))
    # crown: close with a fan just above the last ring
    t = bm.verts.new((0, 0, out[-1][1] + 0.004))
    B = ring_vs[-1]
    for k in range(segs):
        faces.append(bm.faces.new((B[k], B[(k + 1) % segs], t)))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    mb._tag(faces, mi)
    return out[0][0], out[-1]


def build(lod, seed, r=None, h=None, weave=None, rope_length=None, style=None, **_):
    P = params(seed, r, h, weave, rope_length, style)
    R, H = P['r'], P['h']
    mb = genlib.MeshBuilder()
    m_shell = mb.slot('bamboo', scale=0.35)
    m_bind = mb.slot('rope', tint=(0.62, 0.55, 0.48))
    m_rope = mb.slot('rope')
    segs = C.lod_pick(lod, 24, 12, 8, 5)
    rings = C.lod_pick(lod, 9, 6, 4, 3)
    prof = PROF[P['style']]
    if lod == 3:
        prof = [prof[0], prof[3], prof[-1]]
    r_mouth, (r_top, z_top) = _shell(mb, R, H, prof, segs, rings, P['weave'] if lod == 0 else 'none',
                                     0.0035, m_shell)
    # bound rim at the mouth: a proud hoop (closed band), darker bamboo
    rh = P['rim_h']
    if lod <= 1:
        C.lathe(mb, [(r_mouth - 0.004, -0.003), (r_mouth + 0.01, 0.0), (r_mouth + 0.009, rh),
                     (r_mouth - 0.004, rh + 0.002)], segs, m_bind, closed=False)
    elif lod == 2:
        C.lathe(mb, [(r_mouth + 0.01, -0.002), (r_mouth + 0.009, rh)], segs, m_bind, closed=False)
    # LOD3: the shell's mouth carries the read (30-tri budget)
    # crown collar
    cz = z_top
    if lod <= 1:
        C.lathe(mb, [(r_top * 0.95, cz - 0.02), (r_top * 1.08 + 0.006, cz - 0.012), (r_top * 1.05 + 0.006, cz + 0.008),
                     (r_top * 0.7, cz + 0.014)], max(6, segs // 2), m_bind, closed=True)
    # bail loop: a bent bamboo strip over the crown
    bh = P['bail_h']
    top = cz + 0.012 + bh
    yaw = P['bail_yaw']
    if lod <= 1:
        n = C.lod_pick(lod, 9, 5)
        span = r_top * 0.9
        pts = []
        for i in range(n):
            a = math.pi * i / (n - 1)
            x = -span * math.cos(a)
            z = cz + 0.004 + (bh + 0.008) * math.sin(a)
            pts.append((x * math.cos(yaw), x * math.sin(yaw), z))
        C.tube(mb, pts, [0.0055] * n, m_shell, sides=C.lod_pick(lod, 5, 4), cap0=True, cap1=True)
    elif lod == 2:
        C.stick(mb, (0, 0, cz), (0, 0, top), 0.012, 0.008, m_shell, segs=4)
    # knot + rope stub to the hang point
    rope_top = top + P['rope']
    if lod == 0:
        C.rope_knot(mb, (0, 0, top + 0.002), 0.013, m_rope)
        C.rope_cord(mb, (0, 0, top - 0.004), (0, 0, rope_top), 0.0075, m_rope, sides=6, seg_len=0.03)
    elif lod == 1:
        C.rope_cord(mb, (0, 0, top - 0.004), (0, 0, rope_top), 0.0075, m_rope, sides=4, twist=False)
    elif lod == 2:
        C.rope_cord(mb, (0, 0, top - 0.004), (0, 0, rope_top), 0.009, m_rope, sides=2)
    else:
        C.rope_cord(mb, (0, 0, cz - 0.01), (0, 0, rope_top), 0.012, m_rope, sides=1)
    # pivot: the hang axis is the body axis; base at z = 0 (shell base / rim bottom)
    dx, dy, dz = C.centre_base(mb, centre_x=False, centre_y=False)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    # rope sway attribute: 0 at the hang point, 1 at the mouth
    me = o.data
    ztop = max(v.co.z for v in me.vertices)
    att = me.attributes.new('_sway', 'FLOAT', 'POINT')
    col = me.color_attributes.new('kz_sway', 'FLOAT_COLOR', 'POINT')
    for i, v in enumerate(me.vertices):
        s = max(0.0, min(1.0, (ztop - v.co.z) / max(1e-6, ztop)))
        att.data[i].value = s
        col.data[i].color = (s, 0.0, 0.0, 1.0)
    C.set_json_props(o, kz_anim=dict(type='hang', modes=['rigid_lower_raise', 'vertex_rope_sway'],
                                     pivot=[0.0, 0.0, round(ztop, 4)], rope_length=round(P['rope'], 3),
                                     raise_range_m=[0.0, 1.2], attr='_sway', color_attr='kz_sway'),
                     kz_params={k: (round(v, 4) if isinstance(v, float) else v) for k, v in P.items()},
                     kz_lights=[])
    return o
