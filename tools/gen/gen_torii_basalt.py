"""Basalt Gate torii (g_gate hero, the first thing a guest walks through).

Identifying features kept at every LOD: two thick single-column basalt posts, the upswept kasagi crossbeam
(with its shimaki under-beam), the nuki tie beam passing through the posts, the central 火山湯 plaque.

Construction (all real geometry, one mesh, three library materials):
  * posts     - lofted rough-hewn basalt columns: an irregular 6-9-sided "columnar joint" cross-section,
                tapered, flared into the plinth, with a slight inward lean (uchikorobi). Surface is carved by
                vertically stretched Voronoi chunks (scaly plates + cracks) and fBm noise; a few chunk faces are
                glassy obsidian inclusions.
  * kasagi    - swept stone slab along X: cambered profile (wider top, chamfered edges), upswept tips
                (t^p curve) that thicken toward the ends, tips cut on a raking angle. Hewn-stone noise.
  * shimaki   - the second, shorter, slightly less upswept beam directly under the kasagi.
  * nuki      - chamfered tie beam passing through both posts, ends protruding and raked, stone wedges
                (kusabi) where it leaves each post.
  * gakuzuka + plaque - stone strut between nuki and shimaki, obsidian plaque panel in a bevelled bronze frame,
                bronze 火山湯 characters (Noto Serif CJK Black outlines) on both faces.
  * plinths   - cobbled basalt footing blocks (rounded, battered, chunk-cracked) with loose rubble stones.

Parameters (defaults = proxy 9 x 1.6 x 8.5 m in 3d/assets.json; do not exceed it by > 5 %):
  w          overall width, kasagi tip to tip (9 m)
  h          overall height to the kasagi tips (8.5-11 m in asset_list; > 8.9 m fails the proxy check)
  post_d     post diameter at the base (1.2-1.6 m, default 1.5)
  overhang   kasagi overhang beyond the posts' outer face at the top (1.5-2.0 m, default 1.6)
  upsweep    rise of the kasagi tips above the centre (0.25-0.8 m, default seeded 0.6-0.75)
  plaque     plaque size factor (0.8-1.25, default 1.0; 1.0 = 1.15 x 2.0 m, hangs from the shimaki over the nuki)
  roughness  rock carving strength factor (0-1.5, default 1.0)
Seeded: cross-section facets, lean, taper, flare, chunk pattern, upsweep curve exponent, nuki height/overhang,
rubble layout, material tint/wear.

Animation: none.  Lighting: lightmap only (UV1).  Moving parts: none.
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

import genlib

ASSET = 'torii_basalt'
FEATURES = ['two thick single-column basalt posts', 'upswept kasagi crossbeam', 'nuki tie beam',
            'central 火山湯 plaque']
FONT = '/usr/share/fonts/noto-cjk/NotoSerifCJK-Black.ttc'
CHARS = '火山湯'

# per-LOD resolution
RES = {
    0: dict(post_u=40, post_v=34, beam_x=40, shim_x=32, nuki_x=18, prof=1, plinth_cuts=4, rubble=0, rub_sub=1,
            text_res=2, text_ext=0.018, disp=1.0, crack=1.0, chips=True, frame_bev=0.02),
    1: dict(post_u=20, post_v=22, beam_x=20, shim_x=16, nuki_x=10, prof=1, plinth_cuts=2, rubble=0, rub_sub=1,
            text_res=1, text_ext=0.015, disp=0.8, crack=0.7, chips=True, frame_bev=0.0),
    2: dict(post_u=10, post_v=10, beam_x=12, shim_x=10, nuki_x=4, prof=0, plinth_cuts=1, rubble=0, rub_sub=0,
            text_res=1, text_ext=0.0, disp=0.35, crack=0.0, chips=False, frame_bev=0.0),
    3: dict(post_u=6, post_v=2, beam_x=6, shim_x=0, nuki_x=2, prof=-1, plinth_cuts=0, rubble=0, rub_sub=0,
            text_res=0, text_ext=0.0, disp=0.0, crack=0.0, chips=False, frame_bev=0.0),
}

# ------------------------------------------------------------------ rock surface field
class Rock:
    """Deterministic carved-rock displacement: Voronoi chunks (stretched), cracks between them, fBm."""

    def __init__(self, r, cell=0.5, stretch=(1.0, 1.0, 1.8), amp=0.07, crack=0.08, glassy=0.12, width=0.3,
                 fbm=0.15):
        self.off = Vector((r.uniform(-500, 500), r.uniform(-500, 500), r.uniform(-500, 500)))
        self.cell, self.stretch, self.amp, self.crack, self.glassy = cell, stretch, amp, crack, glassy
        self.width, self.fbm = width, fbm

    def sample(self, p, k_amp=1.0, k_crack=1.0):
        """returns (displacement along outward normal, chunk id hash in 0..1)"""
        q = p + self.off
        st = self.stretch
        c = Vector((q.x / (self.cell * st[0]), q.y / (self.cell * st[1]), q.z / (self.cell * st[2])))
        ds, pts = noise.voronoi(c, distance_metric='DISTANCE', exponent=2.5)
        edge = ds[1] - ds[0]
        h = noise.noise(pts[0] * 3.731 + Vector((7.1, 3.3, 1.7)))          # per-chunk value (-1..1)
        chunk = 0.6 * h - 0.6 * min(1.0, ds[0]) ** 2                       # pillowed plates at their own depth
        crack = -max(0.0, 1.0 - edge / self.width) ** 1.6
        fbm = noise.fractal(q * 0.9, 0.7, 2.1, 2)
        d = self.amp * k_amp * (chunk + self.fbm * 4 * fbm) + self.crack * k_crack * crack
        return d, (abs(noise.noise(pts[0] * 9.17 + Vector((1.3, 5.9, 2.2)))) * 91.7) % 1.0

    def seam(self, p):
        """0..1: how deep inside a seam (crack between plates) the point lies"""
        q = p + self.off
        st = self.stretch
        c = Vector((q.x / (self.cell * st[0]), q.y / (self.cell * st[1]), q.z / (self.cell * st[2])))
        ds, _ = noise.voronoi(c, distance_metric='DISTANCE', exponent=2.5)
        return max(0.0, 1.0 - (ds[1] - ds[0]) / self.width) ** 1.6


def tag_seams(faces, rock, seam_mi, thr=0.3):
    """seam faces get the rough seam slot; plate faces keep the glossy plate slot"""
    if seam_mi is None or rock is None:
        return
    for f in faces:
        if f.is_valid and rock.seam(f.calc_center_median()) > thr:
            f.material_index = seam_mi


# ------------------------------------------------------------------ mesh helpers
def grid_faces(bm, rows, mi, close_u=True, flip=False):
    """rows: list (along v) of lists (along u) of BMVerts -> quads"""
    out = []
    nv, nu = len(rows), len(rows[0])
    for j in range(nv - 1):
        for i in range(nu if close_u else nu - 1):
            i2 = (i + 1) % nu
            q = (rows[j][i], rows[j][i2], rows[j + 1][i2], rows[j + 1][i])
            f = bm.faces.new(q[::-1] if flip else q)
            f.material_index = mi
            out.append(f)
    return out


def cap(bm, ring, mi, flip=False):
    f = bm.faces.new(ring[::-1] if flip else ring)
    f.material_index = mi
    return f


def _mark_old(bm):
    """flag all existing verts/faces in an int layer (bmesh ops clear BMElem.tag, so tags are unsafe)"""
    lv = bm.verts.layers.int.get('kz_old') or bm.verts.layers.int.new('kz_old')
    lf = bm.faces.layers.int.get('kz_old') or bm.faces.layers.int.new('kz_old')
    for v in bm.verts:
        v[lv] = 1
    for f in bm.faces:
        f[lf] = 1
    return lv, lf


def bev_box(mb, center, size, mi, bevel=0.0, segs=1):
    """box with bevelled edges; every face (incl. the ones bevel rebuilds) gets `mi`.
    (genlib.MeshBuilder.box(bevel>0) only tags the new bevel faces, its flat faces keep slot 0.)"""
    bm = mb.bm
    lv, lf = _mark_old(bm)
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=r['verts'])
    bmesh.ops.translate(bm, vec=center, verts=r['verts'])
    if bevel > 0:
        edges = list({e for v in r['verts'] for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=segs, affect='EDGES', profile=0.5)
    faces = [f for f in bm.faces if not f[lf]]
    for f in faces:
        f.material_index = mi
    return faces


def rounded_rock(mb, center, size, mi, rock, cuts, k_amp, k_crack, round_r=0.18, batter=0.0, rot_z=0.0,
                 clamp_z=None, glassy_mi=None):
    """subdivided box mapped to a rounded box, battered, carved by `rock`."""
    bm = mb.bm
    lv, lf = _mark_old(bm)                    # existing geometry flagged; new elements come in as 0
    r = bmesh.ops.create_cube(bm, size=2.0)
    if cuts > 0:
        edges = list({e for v in r['verts'] for e in v.link_edges})
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True)
    vs = [v for v in bm.verts if not v[lv]]
    faces = [f for f in bm.faces if not f[lf]]
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    rr = min(round_r, hx * 0.9, hy * 0.9, hz * 0.9)
    M = Matrix.Rotation(rot_z, 3, 'Z')
    for v in vs:
        p = Vector((v.co.x * hx, v.co.y * hy, v.co.z * hz))
        inner = Vector((max(-hx + rr, min(hx - rr, p.x)), max(-hy + rr, min(hy - rr, p.y)), max(-hz + rr, min(hz - rr, p.z))))
        dvec = p - inner
        n = dvec.normalized() if dvec.length > 1e-6 else Vector((p.x / hx, p.y / hy, p.z / hz)).normalized()
        p = inner + n * rr if cuts > 0 else p
        zf = (p.z + hz) / (2 * hz)
        p.x *= 1 - batter * zf
        p.y *= 1 - batter * zf
        p = M @ p + Vector(center)
        if rock is not None and (k_amp > 0 or k_crack > 0):
            d, _ = rock.sample(p, k_amp, k_crack)
            p = p + (M @ n) * d
        if clamp_z is not None:
            p.z = max(clamp_z, p.z)
        v.co = p
    for f in faces:
        f.material_index = mi
    if k_crack > 0:
        tag_seams(faces, rock, glassy_mi)
    return faces


# ------------------------------------------------------------------ parts
def post(mb, cx, z0, z1, rb, rt, lean, r, R, mi, glassy_mi, rock):
    """rough columnar basalt post between z0 and z1, centred at x=cx at the base (lean toward x=0)."""
    bm = mb.bm
    nu, nv = R['post_u'], R['post_v']
    nf = r.randint(6, 9)
    phis = [2 * math.pi * (i + r.uniform(-0.3, 0.3)) / nf for i in range(nf)]
    dists = [1.0 + r.uniform(-0.07, 0.07) for _ in range(nf)]
    twist = 0.0
    facet_k = 0.85 if nu >= 9 else 0.0
    flare = r.uniform(0.02, 0.04)
    ell = r.uniform(0.92, 1.0)                      # slightly deeper in X than in Y
    H = z1 - z0
    rows = []
    sgn = 1 if cx > 0 else -1
    for j in range(nv + 1):
        t = j / nv
        # cluster rings toward the base (flare) at high LOD
        t = t ** 1.15 if nv > 8 else t
        z = z0 + H * t
        rad = rb + (rt - rb) * t + flare * rb * math.exp(-t * H / 0.55) * (1 if nv > 2 else 0.4)
        xc = cx - sgn * lean * (z - z0)
        row = []
        for i in range(nu):
            th = 2 * math.pi * i / nu + (0.5 * math.pi / nu if nu <= 10 else 0)
            # polygonal (facet) support radius
            rp = min(d / max(0.25, math.cos(th - (ph + twist * z))) for ph, d in zip(phis, dists)
                     if math.cos(th - (ph + twist * z)) > 0.25)
            rp = min(rp, 1.25)
            rr = rad * (1 - facet_k + facet_k * rp / 1.08)
            dirv = Vector((math.cos(th), math.sin(th) * ell, 0))
            p = Vector((xc, 0, z)) + dirv * rr
            if 0 < j < nv or nv <= 2:
                d, _ = rock.sample(p, R['disp'], R['crack'])
                p = p + Vector((math.cos(th), math.sin(th), 0)) * d
            row.append(bm.verts.new(p))
        rows.append(row)
    faces = grid_faces(bm, rows, mi)
    cap(bm, rows[-1], mi)
    if R['crack'] > 0:
        tag_seams(faces, rock, glassy_mi)
    return rows


def beam(mb, half, z_base, thick, depth_b, depth_t, up_b, up_t, p_exp, slant, nx, prof_lv, mi, rock, k_amp,
         k_crack, cham=0.045, end_cap=True, sweep_len=1.5, groove=None, seam_mi=None):
    """swept stone beam along X. Flat and level for |x| < half - sweep_len; the tips rise up_b (underside) /
    up_t (top) over the outer `sweep_len` metres (u^p curve). The tip is cut on a rake (`slant`: the bottom is
    shorter than the top). groove=(width, depth, emissive_mi): recessed soffit channel with its own slot."""
    bm = mb.bm
    c = cham if prof_lv >= 0 else 0
    gk = None
    if prof_lv >= 1:
        bot = [(-depth_b / 2 + c, 0.0)]
        if groove:
            gw, gd = groove[0] / 2, groove[1] / thick
            bot += [(-gw, 0.0), (-gw, gd), (gw, gd), (gw, 0.0)]
            gk = 2                                  # profile segment (-gw,gd)->(gw,gd) = groove ceiling
        bot += [(depth_b / 2 - c, 0.0)]
        prof = bot + [(depth_b / 2, c / thick), (depth_t / 2, 0.66), (depth_t / 2 - c, 1.0), (-depth_t / 2 + c, 1.0),
                      (-depth_t / 2, 0.66), (-depth_b / 2, c / thick)]
    elif prof_lv == 0:
        prof = [(-depth_b / 2, 0.0), (depth_b / 2, 0.0), (depth_t / 2, 0.7), (depth_t / 2 - c, 1.0),
                (-depth_t / 2 + c, 1.0), (-depth_t / 2, 0.7)]
    else:
        prof = [(-depth_b / 2, 0.0), (depth_b / 2, 0.0), (depth_t / 2, 1.0), (-depth_t / 2, 1.0)]
    in_groove = set()
    if gk is not None:
        in_groove = {gk - 1, gk, gk + 1, gk + 2}
    pn = []
    for k, (y, zf) in enumerate(prof):
        a, b = prof[k - 1], prof[(k + 1) % len(prof)]
        ty, tz = b[0] - a[0], (b[1] - a[1]) * thick
        nrm = Vector((0, tz, -ty))
        if nrm.length < 1e-6:
            nrm = Vector((0, 0, 1))
        pn.append(nrm.normalized())
    # stations: a few across the flat centre (they carry the carving), dense over the upswept tips
    x_flat = max(0.0, half - sweep_len)
    n_out = max(2, round(nx * 0.36))
    n_in = max(1, nx - 2 * n_out)
    ss = []
    for j in range(n_out):
        ss.append(-(half - (half - x_flat) * j / n_out))
    for j in range(n_in + 1):
        ss.append(-x_flat + 2 * x_flat * j / n_in)
    for j in range(n_out - 1, -1, -1):
        ss.append(half - (half - x_flat) * j / n_out)
    rows = []
    for j, xs in enumerate(ss):
        s = xs / half
        row = []
        for k, (y, zf) in enumerate(prof):
            x = s * (half - slant * (1 - zf))
            u = max(0.0, (abs(x) - x_flat) / max(1e-6, half - x_flat))
            zb = z_base + up_b * u ** p_exp
            zt = z_base + thick + up_t * u ** p_exp
            p = Vector((x, y, zb + (zt - zb) * zf))
            if 0 < j < len(ss) - 1 and (k_amp > 0 or k_crack > 0) and k not in in_groove:
                d, _ = rock.sample(p, k_amp, k_crack)
                p = p + pn[k] * d
            row.append(bm.verts.new(p))
        rows.append(row)
    faces = grid_faces(bm, rows, mi, flip=True)
    if k_crack > 0:
        tag_seams(faces, rock, seam_mi)
    if gk is not None:
        nu = len(prof)
        for idx, f in enumerate(faces):
            if idx % nu == gk:
                f.material_index = groove[2]
    if end_cap:
        faces.append(cap(bm, rows[0], mi, flip=False))
        faces.append(cap(bm, rows[-1], mi, flip=True))
    return faces


def text_glyphs(mb, chars, x, ys_face, zc, size, gap, res, ext, mi):
    """bronze characters stacked vertically, centred at (x, zc); one copy per face sign in ys_face {(y, sign)}"""
    if not os.path.exists(FONT) or res <= 0:
        return False
    font = None
    for f in bpy.data.fonts:
        if f.filepath == FONT:
            font = f
    font = font or bpy.data.fonts.load(FONT)
    n = len(chars)
    for ci, ch in enumerate(chars):
        cu = bpy.data.curves.new('kz_glyph', 'FONT')
        cu.body = ch; cu.font = font; cu.resolution_u = res; cu.extrude = ext
        cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.size = size
        ob = bpy.data.objects.new('kz_glyph', cu)
        bpy.context.scene.collection.objects.link(ob)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        bpy.data.objects.remove(ob); bpy.data.curves.remove(cu)
        for p in me.polygons:
            p.material_index = mi
        zz = zc + (n - 1) / 2 * gap - ci * gap
        for (yy, sg) in ys_face:
            tmp = me.copy()
            # glyph plane XY (+Z out) -> XZ plane facing sign*Y
            R = Matrix.Rotation(math.pi / 2, 4, 'X')
            if sg > 0:
                R = Matrix.Rotation(math.pi, 4, 'Z') @ R
            tmp.transform(Matrix.Translation((x, yy + sg * ext, zz)) @ R)
            mb.bm.from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
        bpy.data.meshes.remove(me)
    return True


def _orient_flat_glyphs(o, y_abs):
    bm = bmesh.new(); bm.from_mesh(o.data)
    for f in bm.faces:
        c = f.calc_center_median()
        if abs(abs(c.y) - y_abs) < 1e-4 and abs(f.normal.y) > 0.9 and f.normal.y * c.y < 0:
            f.normal_flip()
    bm.to_mesh(o.data); bm.free()


# ------------------------------------------------------------------ build
def build(lod, seed, w=None, h=None, d=None, post_d=None, overhang=None, upsweep=None, plaque=1.0,
          roughness=1.0):
    P = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    R = dict(RES[min(3, max(0, lod))])
    W = w or P['w']
    H = h or 8.5                            # default 8.5 m (proxy); h up to 11 m is allowed by the row
    D = min(d or P['d'], P['d'])
    post_d = post_d or 1.6
    overhang = overhang or 1.6
    upsweep = upsweep if upsweep is not None else r.uniform(0.42, 0.58)
    p_exp = r.uniform(1.4, 1.8)
    R['disp'] *= roughness; R['crack'] *= roughness

    mb = genlib.MeshBuilder()
    tint = (1.0, r.uniform(0.96, 1.0), r.uniform(0.94, 1.0))
    # near-black basalt: glossy plate faces, rough darker seams
    stone = mb.slot('basalt_dry', tint=tuple(round(0.5 * c, 3) for c in tint), wear=0.3, wetness=0.35, scale=1.3)   # ~0.5 tint: near-black under the warm key
    glass = None   # per-face seam slot tried in r3: reads as blocky squares at this mesh density; seams are geometry
    panel = mb.slot('lacquer_black')           # jet-black plaque field
    bronze = mb.slot('bronze', wear=0.35)      # blackened bronze, gold wear edges: frame, studs, lamp cups
    gold = mb.slot('gold_leaf')                # gilded 火山湯 glyphs
    emit = mb.slot('lantern_paper', emissive_level=1.2) if lod <= 2 else None   # emits at 2200 K
    lights = []

    # chunky columnar plates, the same language on posts, beams and footings
    rock = Rock(r, cell=0.5 * r.uniform(0.85, 1.15), stretch=(1.0, 1.0, r.uniform(1.2, 1.45)), amp=0.11,
                crack=0.05, glassy=0.0, width=0.17, fbm=0.0)
    rock_b = Rock(r, cell=0.5 * r.uniform(0.85, 1.15), stretch=(1.35, 1.0, 1.0), amp=0.08, crack=0.045,
                  width=0.17, fbm=0.0)
    rock_p = Rock(r, cell=0.42, stretch=(1.0, 1.0, 0.85), amp=0.09, crack=0.05, width=0.17, fbm=0.05)

    # ---- vertical stack
    plinth_h = 1.0 * r.uniform(0.96, 1.04)
    kas_th = 0.72 * H / 8.5                 # kasagi thickness at centre
    shim_th = 0.40 * H / 8.5
    z_kas_top_c = H - upsweep               # top of kasagi in the flat centre; the tips reach H
    z_kas = z_kas_top_c - kas_th
    z_shim = z_kas - shim_th
    rb = post_d / 2
    rt = rb * r.uniform(0.76, 0.8)          # ~1.6 m at the base -> ~1.25 m under the beams
    half = W / 2
    post_cx = half - overhang - rt          # post centre at the top
    lean = r.uniform(0.006, 0.012)          # inward lean, m per m
    post_x0 = post_cx + lean * (z_shim - plinth_h)
    nuki_th = 0.68 * H / 8.5
    nuki_d = min(0.62, rt * 1.0)
    z_nuki = z_shim - r.uniform(1.3, 1.45) * H / 8.5 - nuki_th
    nuki_half = post_cx + rt + r.uniform(0.95, 1.15)
    groove = (lambda: (0.12, 0.04, emit)) if (R['prof'] >= 1 and emit is not None) else (lambda: None)

    # ---- posts
    for sx in (-1, 1):
        post(mb, sx * post_x0, plinth_h - 0.15, z_shim + 0.08, rb, rt, lean, genlib.rng(seed, f'post{sx}'), R,
             stone, glass, rock)

    # ---- plinths: rough stacked-boulder footings (~2.4 m wide, overhanging the post ~0.4 m per side)
    pw = min(post_d + 0.85, 2.4)
    pdp = D * 0.97
    for sx in (-1, 1):
        rr = genlib.rng(seed, f'plinth{sx}')
        px = sx * post_x0
        if lod >= 3:
            mb.box((px, 0, plinth_h / 2), (pw, pdp, plinth_h), stone)
            continue
        cuts = R['plinth_cuts']
        top_z = []
        # two big lower boulders, side by side
        for k in (-1, 1):
            bh = plinth_h * rr.uniform(0.55, 0.68)
            bw = pw * rr.uniform(0.54, 0.6)
            rounded_rock(mb, (px + k * pw * 0.22 + rr.uniform(-0.04, 0.04), rr.uniform(-0.03, 0.03), bh / 2),
                         (bw, pdp * rr.uniform(0.94, 1.0), bh), stone, rock_p, cuts, R['disp'], R['crack'],
                         round_r=min(0.22, bh * 0.35) if lod < 2 else 0.0, batter=0.08, rot_z=rr.uniform(-0.08, 0.08),
                         clamp_z=0.0, glassy_mi=glass)
        # one or two capping boulders, top edge jittered +-0.1 m
        n_cap = 2 if lod == 0 else 1
        for k in range(n_cap):
            ch = plinth_h * rr.uniform(0.42, 0.55)
            ztop = plinth_h + rr.uniform(-0.1, 0.1)
            cw = pw * (rr.uniform(0.5, 0.6) if n_cap == 2 else rr.uniform(0.78, 0.88))
            ox = (k - 0.5) * pw * 0.4 if n_cap == 2 else 0.0
            rounded_rock(mb, (px + ox, rr.uniform(-0.04, 0.04), ztop - ch / 2), (cw, pdp * rr.uniform(0.8, 0.9), ch),
                         stone, rock_p, max(0, cuts - 1), R['disp'], R['crack'],
                         round_r=min(0.2, ch * 0.35) if lod < 2 else 0.0, batter=0.12,
                         rot_z=rr.uniform(-0.12, 0.12), clamp_z=0.0, glassy_mi=glass)
            top_z.append(ztop)
        # recessed amber uplights in the footing top, two per post (front / back), aimed up the post
        if emit is not None:
            for sy in (-1, 1):
                cxl = px - sx * rb * 0.15
                cyl = sy * (rb * 0.95 + 0.16)
                ztop = min(top_z) - 0.02
                if lod <= 1:
                    mb.cylinder((cxl, cyl, ztop - 0.03), radius=0.13, depth=0.14, mi=bronze if lod == 0 else stone,
                                segs=10 if lod == 0 else 6, cap=False)
                    mb.cylinder((cxl, cyl, ztop - 0.07), radius=0.125, depth=0.01, mi=emit, segs=10 if lod == 0 else 6)
                lights.append(dict(kind='uplight', pos=[round(cxl, 3), round(cyl, 3), round(ztop - 0.06, 3)],
                                   aim=[round(px, 3), 0.0, round(plinth_h + 2.0, 3)], color_k=2400, watts=60,
                                   cone_deg=40, throw_m=2.2))

    # ---- nuki (tie beam) + kusabi wedges
    beam(mb, nuki_half, z_nuki, nuki_th, nuki_d, nuki_d, 0.0, 0.0, 1.0, 0.10 if lod < 3 else 0.0, R['nuki_x'],
         R['prof'], stone, rock_b, R['disp'], R['crack'], cham=0.04, sweep_len=0.0, groove=groove(), seam_mi=glass)
    if R['chips']:
        for sx in (-1, 1):
            for sy in (-1, 1):
                xw = sx * (post_cx + rt * 0.92)
                bev_box(mb, (xw, sy * nuki_d * 0.28, z_nuki + nuki_th * 0.5), (0.22, 0.12, nuki_th * 0.86), stone,
                        bevel=0.012 if lod == 0 else 0.0)

    # ---- shimaki + kasagi: level through the middle, upswept only over the outer ~1.5 m
    if R['shim_x'] > 0:
        sh_half = half - overhang * 0.42
        beam(mb, sh_half, z_shim, shim_th + 0.02, D * 0.66, D * 0.70, upsweep * 0.3, upsweep * 0.38, p_exp, 0.10,
             R['shim_x'], R['prof'], stone, rock_b, R['disp'], R['crack'], cham=0.04, sweep_len=1.1,
             groove=groove(), seam_mi=glass)
        beam(mb, half, z_kas, kas_th, D * 0.86, D * 0.985, upsweep * 0.8, upsweep, p_exp, 0.3, R['beam_x'],
             R['prof'], stone, rock_b, R['disp'], R['crack'], cham=0.045, sweep_len=1.5, groove=groove(), seam_mi=glass)
    else:   # LOD3: kasagi + shimaki as one sweep (2 segments per upswept tip)
        beam(mb, half, z_shim, kas_th + shim_th, D * 0.75, D * 0.985, upsweep * 0.6, upsweep, p_exp, 0.3,
             R['beam_x'], R['prof'], stone, rock_b, 0, 0, sweep_len=1.5)
    if groove() is not None:
        for name, zz, hx in (('soffit_kasagi', z_kas, half - 0.3), ('soffit_shimaki', z_shim, half - overhang * 0.42 - 0.2),
                             ('soffit_nuki', z_nuki, nuki_half - 0.2)):
            lights.append(dict(kind='line', name=name, a=[-round(hx, 3), 0, round(zz + 0.02, 3)],
                               b=[round(hx, 3), 0, round(zz + 0.02, 3)], color_k=2200, watts_per_m=8))

    # ---- gakuzuka strut + plaque
    pl_w, pl_h = 1.15 * plaque, 2.0 * plaque * H / 8.5
    gap_z = z_shim - (z_nuki + nuki_th)
    pl_h = min(pl_h, gap_z + nuki_th * 0.8)
    pl_zc = z_shim + 0.02 - pl_h / 2          # hangs from the shimaki, overlapping the nuki in front
    pl_t = nuki_d + 0.1
    if lod < 3:
        mb.box((0, 0, (z_nuki + nuki_th + z_shim) / 2), (0.36, nuki_d * 0.75, gap_z + 0.1), stone)
    fr = 0.09 * plaque
    if lod <= 1:
        bev = R['frame_bev']
        for sz in (-1, 1):   # top / bottom rails
            bev_box(mb, (0, 0, pl_zc + sz * (pl_h / 2 - fr / 2)), (pl_w + 0.04, pl_t + 0.04, fr), gold, bevel=bev)
        for sx in (-1, 1):   # stiles
            bev_box(mb, (sx * (pl_w / 2 - fr / 2), 0, pl_zc), (fr, pl_t + 0.03, pl_h - 2 * fr + 0.01), gold, bevel=bev)
        bev_box(mb, (0, 0, pl_zc), (pl_w - 2 * fr + 0.02, pl_t - 0.02, pl_h - 2 * fr + 0.02), panel,
                bevel=0.01 if lod == 0 else 0.0)
        if lod == 0:   # corner bosses (bronze studs)
            for sx in (-1, 1):
                for szz in (-1, 1):
                    for sy in (-1, 1):
                        mb.cylinder((sx * (pl_w / 2 - fr / 2), sy * (pl_t / 2 + 0.03), pl_zc + szz * (pl_h / 2 - fr / 2)),
                                    radius=0.035, depth=0.03, mi=bronze, segs=8, rot=(math.pi / 2, 0, 0))
    else:
        mb.box((0, 0, pl_zc), (pl_w + 0.04, pl_t + 0.04, pl_h), gold)
        mb.box((0, 0, pl_zc), (pl_w - 2 * fr, pl_t + 0.06, pl_h - 2 * fr), panel)
    # characters (both faces)
    face_y = (pl_t - 0.02) / 2 if lod <= 1 else (pl_t + 0.06) / 2
    glyph_sz = (pl_w - 2 * fr) * 0.98
    gap = (pl_h - 2 * fr) / 3.0
    if lod <= 2:
        ok = text_glyphs(mb, CHARS, 0.0, [(-face_y - 0.002, -1), (face_y + 0.002, 1)], pl_zc, glyph_sz, gap,
                         R['text_res'], R['text_ext'], gold)
        if not ok:
            for k in range(3):
                for sy in (-1, 1):
                    mb.box((0, sy * (face_y + 0.01), pl_zc + (1 - k) * gap), (glyph_sz * 0.6, 0.02, glyph_sz * 0.6), gold)

    # keep inside the proxy depth: carved rock can bulge past it, so fit Y (a few % at most)
    ys = [v.co.y for v in mb.bm.verts]
    dd = max(ys) - min(ys)
    if dd > D * 0.995:
        k = D * 0.995 / dd
        for v in mb.bm.verts:
            v.co.y *= k
    for seq in (mb.bm.verts, mb.bm.faces):
        lay = seq.layers.int.get('kz_old')
        if lay is not None:
            seq.layers.int.remove(lay)
    o = mb.to_object(ASSET)
    if lod == 2:   # flat (single-sided) glyphs: recalc_face_normals cannot orient open islands, so set them here
        _orient_flat_glyphs(o, face_y + 0.002)
    o['kz_lights'] = json.dumps(lights)
    o['kz_params'] = repr(dict(w=W, h=H, post_d=post_d, overhang=overhang, upsweep=round(upsweep, 3),
                               plaque=plaque, roughness=roughness))
    return genlib.finish(o, smooth_angle=40)
