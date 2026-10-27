"""Hanging crest banner: one long cloth panel (cream, indigo or vermilion) hung from a top rod on two rope cords,
with the Kazan-yu mountain crest dyed into the upper third, folded hem pocket with a bronze weight bar.

Identifying features kept at every LOD: long single cloth panel, the rod it hangs from, the mountain crest.
Proxy (3d/assets.json): 1 x 0.05 x 4 m.  h is the overall height from the bottom of the weight bar to the top of
the cords.  Front (the crest side) faces +Y; the cloth is a single surface, render it double-sided.

Variants: colour by seed ((seed-1) % 3: cream, indigo, vermilion; seeds 1-3 and 4-6 give two seeds per colour) and
hem / hang style from the seed: hem 'straight' | 'notch' (swallowtail) | 'taper' (slanted), hang 'tabs' | 'sleeve'.
Parameters: w (0.6-1.2 m, default <= 1.0), h (2-5 m, default <= 4.2), colour ('cream'|'indigo'|'red'),
crest (bool), weight (bool, bronze hem bar), hem, hang.

Animation (vertex sway, data only; no runtime here):
  float point attribute '_sway' : 0 at the rod, rising to 1 at the hem (cloth, crest, hem bar); rod/cords = 0.
  colour attribute 'kz_sway'    : (sway, u across the cloth 0..1, v down the cloth 0..1, 1).
  obj['kz_anim'] (JSON)         : {'type': 'vertex_sway', 'attrs': ['_sway', 'kz_sway'], 'rod_z': .., 'cloth_len': ..}
  Shader idea: offset_y = sway * (wind(t, x) * 0.06 + weight * 0.0), offset_x = 0.2 * sway^2 * wind2(t).
"""
import json
import math
import random

import bmesh
import bpy
from mathutils import Vector

import genlib
import kzgeo_bridge_arched as B
from kzgeo_signboard_kanji import crest_polys

ASSET = 'banner_hanging'
FEATURES = ['long cloth panel', 'top rod on cords', 'mountain crest', 'hem weight bar']
PARAMS = dict(w=(0.6, 1.2), h=(2.0, 5.0), colour=('cream', 'indigo', 'red'), crest=(True, False), weight=(True, False),
              hem=('straight', 'notch', 'taper'), hang=('tabs', 'sleeve'))
# linear tints on the (indigo) noren library albedo
CLOTH_TINT = {'cream': (9.0, 6.8, 3.2), 'indigo': (1.0, 1.0, 1.0), 'red': (22.0, 1.0, 0.3)}
CREST_TINT = {'cream': (0.6, 0.7, 0.9), 'indigo': (9.0, 6.8, 3.2), 'red': (9.0, 6.8, 3.2)}
VARIANT = {'cream': dict(variant='cream'), 'indigo': {}, 'red': dict(tint=(0.30, 0.03, 0.018))}      # #E9DDC1 / #1E2F5A / #8A1F1A
CREST_VAR = {'cream': {}, 'indigo': dict(variant='cream'), 'red': dict(variant='cream')}
COLOURS = ['cream', 'indigo', 'red']


def build(lod, seed, w=None, h=None, colour=None, crest=True, weight=True, hem=None, hang=None):
    p = genlib.proxy(ASSET)
    budget = genlib.budget_of(ASSET) or [300, 120, 40, 12]
    for attempt in range(6):
        o = _build_once(lod, seed, w, h, colour, crest, weight, hem, hang, attempt, p)
        if genlib.tris(o) <= budget[lod] * 1.05 or attempt == 5:
            break
        bpy.data.meshes.remove(o.data)
    return genlib.finish(o, smooth_angle=40)


def _face(bm, vs, mi, out=None):
    f = bm.faces.new(vs)
    f.material_index = mi
    if out is not None:
        f.normal_update()
        if f.normal.dot(Vector(out)) < 0:
            f.normal_flip()
    return f


def _to_object(mb, name):
    me = bpy.data.meshes.new(name)
    mb.bm.to_mesh(me); mb.bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    for i, (mid, params) in enumerate(mb.slots):
        genlib.matlib.assign(o, mid, slot=i, **params)
    return o


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _build_once(lod, seed, w, h, colour, crest, weight, hem, hang, attempt, p):
    r = genlib.rng(seed, ASSET)
    colour = colour or COLOURS[(seed - 1) % 3]
    hem = hem or ['straight', 'notch', 'point'][(seed + (seed - 1) // 3) % 3]
    hang = hang or ('sleeve' if seed % 2 == 0 else 'tabs')
    W = min(w if w is not None else {1: 0.98, 2: 0.74, 0: 0.62}[seed % 3] * r.uniform(0.97, 1.0), 1.2)
    Htot = h if h is not None else p['h'] * r.uniform(0.8, 1.04)
    lod3 = lod == 3
    mb = genlib.MeshBuilder()
    bm = mb.bm
    L_sway = bm.verts.layers.float.new('_sway')
    L_u = bm.verts.layers.float.new('_u')
    L_v = bm.verts.layers.float.new('_v')
    cloth_m = mb.slot('noren', **VARIANT[colour], wear=round(r.uniform(0.05, 0.2), 2), normal_strength=1.4, emissive_level=0.12)
    crest_m = mb.slot('noren', **CREST_VAR[colour], wear=0.0, normal_strength=0.8)
    bronze = mb.slot('bronze', wear=round(r.uniform(0.2, 0.45), 2))
    wood = mb.slot('hinoki', wear=0.1)
    rope = mb.slot('rope')

    # ------------------------------------------------ layout
    cord_len = min(0.34, 0.07 * Htot) * r.uniform(0.8, 1.1)
    rod_r = 0.02
    z_rod = Htot - cord_len
    cw = W - 0.16                                          # cloth width; the rod and its finials stand 6 cm proud each side
    z_top = z_rod - rod_r * 0.6                            # cloth top edge (the sewn head)
    bar_r = 0.015 if weight else 0.004
    z_bot0 = bar_r * 1.2 if (weight and hem == 'straight' and lod <= 1) else 0.0   # lowest point of the cloth hem (the bar rides in the hem pocket)
    ph = r.uniform(0, 6.28)
    # hem profile: z of the bottom edge as a function of u (0..1 across)
    def hem_z(u):
        if hem == 'notch':
            return z_bot0 + 0.22 * (1 - abs(2 * u - 1))
        if hem == 'point':
            return z_bot0 + 0.3 * abs(2 * u - 1)
        if hem == 'taper':
            return z_bot0 + 0.2 * u
        return z_bot0
    # crest zone
    cs = cw * 0.5
    z_ctop = z_top - 0.3 - 0.03 * (Htot - 3.0)
    z_cbase = z_ctop - cs * 0.95
    amp = 0.016 * min(1.2, W / 0.9)
    bow = 0.008 * r.choice([-1, 1]) * r.uniform(0.7, 1.0)
    phs = r.uniform(0, 6.28)
    cloth_len = z_top - z_bot0
    ncols = {0: 8 if attempt < 2 else 6, 1: 4, 2: 2}.get(lod, 1)
    kf = r.choice([2.0, 2.5, 3.0]); phf = r.uniform(0, 6.28)
    fold_sign = r.choice([-1, 1])
    colw = [r.uniform(0.75, 1.25) if hem == 'straight' else 1.0 for _ in range(ncols)]
    sc = sum(colw)
    ux = [0.0]
    for k in colw:
        ux.append(ux[-1] + k / sc)
    folds = [fold_sign * (-1) ** i * r.uniform(0.55, 1.0) * (0.45 if i in (0, ncols) else 1.0) for i in range(ncols + 1)]
    kscale = {0: 1.0, 1: 0.75, 2: 0.4}.get(lod, 0.0)

    def surf(u, z):
        """cloth surface point for u in 0..1 across, z height"""
        x = (0.5 - u) * cw                                  # u = 0 at the viewer's left (+X), the text reads towards -X
        t = max(0.0, (z_top - z) / max(1e-6, cloth_len))
        # fold amplitude: pressed flat under the rod and in the crest zone, opening towards the hem
        a = amp * kscale * _smooth((z_cbase - z) / max(0.3, z_cbase * 0.5)) ** 1.1 if crest else amp * kscale * _smooth((t - 0.1) / 0.5)
        # fold shape across the cloth: interpolate the column fold values (triangular pleats)
        fv = math.sin(2 * math.pi * kf * u + phf)                    # 2-3 soft folds across the width
        y = a * fv + bow * math.sin(1.7 * math.pi * min(t, 1.0) + phs) + 0.002 * math.sin(ph + 5 * t)       # S-curve drape
        return Vector((x, y, z))

    # row heights (rows from the top edge down to each column's hem)
    nrows = {0: 7, 1: 5, 2: 2}.get(lod, 1) - max(0, attempt - 2) * (1 if lod == 0 else 0)
    nrows = max(3 if lod == 0 else nrows, nrows)
    nrows = max(nrows, 2 if lod == 0 else 1)
    # cloth grid
    grid = {}
    crest_rows = [z_ctop + 0.02, z_cbase - 0.02] if crest and lod <= 1 else []
    for ci in range(ncols + 1):
        u = ux[ci]
        zb = hem_z(u)
        zs = [z_top]
        if lod <= 1 and crest:
            zs += [z_ctop + 0.03, z_cbase - 0.03]
        n_rest = max(1, nrows - (len(zs) - 1))
        z_from = zs[-1]
        for k in range(1, n_rest + 1):
            zs.append(z_from - (z_from - zb) * (k / n_rest) ** 0.85)
        zs = sorted(set(round(z, 5) for z in zs), reverse=True)
        zs[-1] = zb
        # keep the same row count per column: pad by splitting the last cell
        grid[ci] = zs
    rows_n = max(len(v) for v in grid.values())
    for ci in grid:
        zs = grid[ci]
        while len(zs) < rows_n:
            # split the largest gap
            gi = max(range(len(zs) - 1), key=lambda i: zs[i] - zs[i + 1])
            zs.insert(gi + 1, (zs[gi] + zs[gi + 1]) / 2)
        grid[ci] = zs
    V = {}
    for ci in range(ncols + 1):
        for ri, z in enumerate(grid[ci]):
            P = surf(ux[ci], z)
            v = bm.verts.new(P)
            tv = (z_top - z) / max(1e-6, cloth_len)
            v[L_sway] = max(0.0, min(1.0, tv)) ** 1.35
            v[L_u] = ux[ci]; v[L_v] = max(0.0, min(1.0, tv))
            V[(ci, ri)] = v
    for ci in range(ncols):
        for ri in range(rows_n - 1):
            _face(bm, (V[(ci, ri)], V[(ci + 1, ri)], V[(ci + 1, ri + 1)], V[(ci, ri + 1)]), cloth_m, out=(0, 1, 0))

    def on_cloth(x, z, off):
        u = 0.5 - x / cw
        u = max(0.0, min(1.0, u))
        P = surf(u, z)
        return Vector((x, P.y + off, z)), u

    # ------------------------------------------------ crest (dyed on, follows the surface: the crest zone is pressed flat)
    if crest and lod <= 2:
        polys = crest_polys('kazan', 0 if lod == 0 else 1, r)
        if lod == 2:
            polys = [[(-0.5, 0.0), (0.5, 0.0), (0.0, 0.46)], [(-0.05, 0.5), (0.05, 0.5), (0.0, 0.95)]]
        if lod == 0:                                          # ringed roundel around the crest
            nseg = 10 if attempt < 2 else 8
            Ro, Ri = 0.66, 0.60
            for k in range(nseg):
                a0, a1 = 2 * math.pi * k / nseg, 2 * math.pi * (k + 1) / nseg
                polys.append([(Ro * math.cos(a0), 0.42 + Ro * math.sin(a0)), (Ro * math.cos(a1), 0.42 + Ro * math.sin(a1)), (Ri * math.cos(a1), 0.42 + Ri * math.sin(a1)), (Ri * math.cos(a0), 0.42 + Ri * math.sin(a0))])
        made = []
        cb = bmesh.new()
        for poly in polys:
            vs = [cb.verts.new((-px * cs, 0, z_cbase + py * cs)) for px, py in poly]
            made.append(cb.faces.new(vs))
        bmesh.ops.triangulate(cb, faces=made, quad_method='BEAUTY', ngon_method='EAR_CLIP')
        off = 0.0035 if lod == 0 else 0.005
        vm = {}
        for v in cb.verts:
            P, u = on_cloth(v.co.x, v.co.z, off)
            nv = bm.verts.new(P)
            tv = (z_top - v.co.z) / max(1e-6, cloth_len)
            nv[L_sway] = max(0.0, min(1.0, tv)) ** 1.35; nv[L_u] = u; nv[L_v] = tv
            vm[v] = nv
        for f in cb.faces:
            vs = [vm[v] for v in f.verts]
            if len(set(vs)) == len(vs):
                try:
                    _face(bm, vs, crest_m, out=(0, 1, 0))
                except ValueError:
                    pass
        cb.free()
    # ------------------------------------------------ rod, finials, cords
    rl = W
    if lod <= 1:
        segs = 6 if lod == 0 else 4
        mb.cylinder((0, 0.0, z_rod), rod_r, rl - 0.04, wood, segs=8 if lod == 0 else 4, rot=(0, math.pi / 2, 0), cap=False)
        fin = [(rod_r * 1.15, 0.0), (rod_r * 1.4, 0.02), (rod_r * 0.8, 0.045), (0.0, 0.055)] if lod == 0 else [(rod_r * 1.5, 0.0), (0.0, 0.03)]
        for sx in (-1, 1):
            x0 = sx * (rl / 2 - 0.02)
            rings = []
            for rr, dx in fin:
                if rr <= 1e-6:
                    rings.append([bm.verts.new((x0 + sx * dx, 0.0, z_rod))])
                else:
                    rings.append([bm.verts.new((x0 + sx * dx, rr * math.cos(2 * math.pi * k / segs), z_rod + rr * math.sin(2 * math.pi * k / segs))) for k in range(segs)])
            for a_, b_ in zip(rings, rings[1:]):
                if len(b_) == 1:
                    for k in range(segs):
                        _face(bm, (a_[k], a_[(k + 1) % segs], b_[0]), bronze, out=(sx, 0, 0))
                else:
                    for k in range(segs):
                        q = (a_[k], a_[(k + 1) % segs], b_[(k + 1) % segs], b_[k])
                        c = sum((v.co for v in q), Vector()) / 4
                        _face(bm, q, bronze, out=(0, c.y, c.z - z_rod))
        # cords: two thin ropes from the rod up to the ceiling anchor (a small ring above)
        for sx in (-1, 1):
            xc = sx * rl * 0.36
            mb.cylinder((xc, 0.0, z_rod + cord_len / 2), 0.006 if lod == 0 else 0.008, cord_len, bronze, segs=4 if lod == 0 else 3, cap=False)
            if lod == 0:
                B.lathe(mb, (xc, 0.0, Htot - 0.012), [(0.016, 0.0), (0.016, 0.012), (0.006, 0.012)], bronze, segs=5)
    else:
        mb.box((0, 0, z_rod), (rl, 0.03, 0.03), wood)
        for sx in (-1, 1):
            xc = sx * rl * 0.36
            vs = [bm.verts.new((xc + 0.01, 0, z_rod)), bm.verts.new((xc - 0.01, 0, z_rod)), bm.verts.new((xc - 0.01, 0, Htot)), bm.verts.new((xc + 0.01, 0, Htot))]
            for v in vs:
                v[L_sway] = 0.0
            _face(bm, vs, rope, out=(0, 1, 0))
    # tabs / sleeve
    if lod == 0:
        if hang == 'tabs':
            nt = 5 if attempt < 3 else 4
            tw = 0.09
            for k in range(nt):
                x = (k - (nt - 1) / 2) * (cw - tw) / (nt - 1)
                _loop(bm, x, tw, z_rod, rod_r + 0.003, z_top - 0.12, cloth_m, surf, L_sway)
        else:
            _loop(bm, 0.0, cw, z_rod, rod_r + 0.004, z_top - 0.05, cloth_m, surf, L_sway)
    # hem weight bar
    if weight and lod <= 1:
        bz = bar_r
        mb.cylinder((0, surf(0.5, bz).y - 0.0, bz + 0.0), bar_r, cw * 0.97, bronze, segs=5 if lod == 0 else 4, rot=(0, math.pi / 2, 0), cap=False) if hem == 'straight' else None
        if hem != 'straight':
            # the bar follows a straight hem only; notched / slanted hems carry two end weights
            for u in (0.06, 0.94):
                xw = (0.5 - u) * cw
                zz = hem_z(u) + 0.026
                mb.cylinder((xw, 0.0, zz), 0.014, 0.052, bronze, segs=5, cap=True)
    if lod3:
        bmesh.ops.delete(bm, geom=bm.verts[:], context='VERTS')
        # 12 triangles: cloth strip, crest block, rod
        zt, zb = z_top, z_bot0
        for (x0, x1, z0, z1, mi) in ((-cw / 2, cw / 2, zb, zt, cloth_m), (-cw * 0.3, cw * 0.3, z_cbase, z_ctop, crest_m)):
            yy_ = 0.002 if mi == crest_m else 0.0
            if mi == crest_m:                                 # a mountain triangle, not a block
                vs = [bm.verts.new((cw * 0.3, yy_, z_cbase)), bm.verts.new((-cw * 0.3, yy_, z_cbase)), bm.verts.new((0.0, yy_, z_ctop))]
            else:
                vs = [bm.verts.new((x1, yy_, z0)), bm.verts.new((x0, yy_, z0)), bm.verts.new((x0, yy_, z1)), bm.verts.new((x1, yy_, z1))]
            for v in vs:
                v[L_sway] = (z_top - v.co.z) / cloth_len
            _face(bm, vs, mi, out=(0, 1, 0))
        for sx in (-1, 1):
            xc = sx * rl * 0.36
            vs = [bm.verts.new((xc + 0.01, 0, z_rod)), bm.verts.new((xc - 0.01, 0, z_rod)), bm.verts.new((xc - 0.01, 0, Htot)), bm.verts.new((xc + 0.01, 0, Htot))]
            _face(bm, vs, bronze, out=(0, 1, 0))
        vs = [bm.verts.new((rl / 2, 0, z_rod - 0.015)), bm.verts.new((-rl / 2, 0, z_rod - 0.015)), bm.verts.new((-rl / 2, 0, z_rod + 0.015)), bm.verts.new((rl / 2, 0, z_rod + 0.015))]
        _face(bm, vs, wood, out=(0, 1, 0))
    o = _to_object(mb, ASSET)
    me = o.data
    ca = me.color_attributes.new('kz_sway', 'FLOAT_COLOR', 'POINT')
    sw, uu, vv = me.attributes['_sway'].data, me.attributes['_u'].data, me.attributes['_v'].data
    for i in range(len(me.vertices)):
        ca.data[i].color = (sw[i].value, uu[i].value, vv[i].value, 1.0)
    o['kz_anim'] = json.dumps({'type': 'vertex_sway', 'attrs': ['_sway', '_u', '_v', 'kz_sway'], 'rod_z': round(z_rod, 4), 'cloth_len': round(cloth_len, 4)})
    o['kz_params'] = json.dumps(dict(w=round(W, 3), h=round(Htot, 3), colour=colour, crest=crest, weight=weight, hem=hem, hang=hang))
    return o


def _loop(bm, x, width, z_rod, rad, z_attach, mi, surf, L_sway):
    """cloth loop (chichi tab or the whole sleeve) round the rod: front strap up, over the top, down the back"""
    arc = 4
    pts = [(rad * 0.4, z_attach)]
    for k in range(arc + 1):
        ang = -0.9 + (math.pi + 1.8) * k / arc
        pts.append((rad * math.cos(ang), z_rod + rad * math.sin(ang)))
    pts.append((-rad * 0.5, z_attach - 0.012))
    L, R = [], []
    for (py, pz) in pts:
        a = bm.verts.new((x + width / 2, py, pz)); b = bm.verts.new((x - width / 2, py, pz))
        a[L_sway] = 0.0; b[L_sway] = 0.0
        L.append(a); R.append(b)
    for i in range(len(pts) - 1):
        q = (R[i], L[i], L[i + 1], R[i + 1])
        c = sum((v.co for v in q), Vector()) / 4
        m = Vector((x, 0, z_rod))
        d = c - m
        f = bm.faces.new(q)
        f.material_index = mi
        f.normal_update()
        if f.normal.dot(Vector((0, d.y, d.z))) < 0:
            f.normal_flip()
