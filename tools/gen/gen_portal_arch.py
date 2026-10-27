"""Portal arches and door frames (mid tier, 6 instances): three styles from one generator.

Identifying features kept at every LOD:
  basalt        one continuous craggy basalt mass (flared jambs 1.1 -> 0.9 m, a 0.9 m crown overhanging the
                jambs by 0.2-0.3 m, optional arched soffit) round a dark hinoki frame (posts, noren tie beam, struts,
                kibana head beam projecting 0.35 m), 0.15 m basalt threshold step,
                optional noren hanging from the lintel  (refs/gen/sheet-mod-pavilions.png #06, 16-steam-grotto)
  timber_gate   hinoki gate: two thick posts on basalt footing stones, lintel, and either a small gabled board
                roof or a flat kabuki-mon head (heavy straight kabuki beam, solid head panel, plaque); never an
                upswept kasagi (that is the torii_basalt asset)
  bronze_frame  bronze-and-timber door frame: deep hinoki jamb casings clad with bronze shoes, bands and studs,
                bronze threshold, head beam, transom (kumiko lattice or bronze plaque, seeded), cornice

Construction (one mesh, library materials basalt_dry / basalt_wet / hinoki / bronze / noren):
  * basalt blocks: subdivided rounded boxes carved by the torii's Voronoi chunk-and-crack rock field
    (gen_torii_basalt.Rock / rounded_rock), stacked in courses with seeded heights, widths, set-backs and a
    slight batter; some faces get basalt_wet (seeded) so the arch reads damp like the grotto. The crown
    blocks have seeded heights so the top silhouette is craggy, not a straight line.
  * timber: chamfered (octagonal) hinoki posts, chamfered beams, short struts (tsuka) between lintel and head
    rail, bronze end caps (kanamono) and post shoes; UV grain follows each member (kzgeo_bridge_arched.uv_grain).
  * noren: split cloth panels hung under the lintel (seeded 2-4 panels, gentle folds). This is a static
    stand-in: obj['kz_noren'] gives the hang line so assembly can swap in the animated `noren` asset.

Seeded (shape, not just tint): basalt course layout, block widths, jamb set-back, crown crag heights, lintel
style (single / doubled with struts), wet-face pattern; timber_gate top ('kasagi' | 'roof'), upsweep, nuki
height, brace; bronze_frame transom ('kumiko' | 'plaque'), stud rows, band count; noren panel count.
The default style follows the seed: (seed-1) % 3 -> basalt, timber_gate, bronze_frame (so seeds 1/4 are
basalt, 2/5 timber_gate, 3/6 bronze_frame; the row's '3 styles x 2 seeds').

Parameters (defaults fit the proxy 5.0 x 1.2 x 3.4 m in 3d/assets.json; do not exceed it by > 5 %):
  clear_w   clear opening width 2.4-6 m (default per style: basalt 2.9-3.1, gate 3.3-3.6, frame 2.8-3.1)
  clear_h   clear opening height 2.6-4.5 m (default 2.6; anything over ~2.65 makes the default build taller
            than the 3.4 m proxy: the whole portal scales with it)
  depth     0.5-1.5 m (default: basalt 1.2, gate 1.2, frame 0.7)
  style     'basalt' | 'timber_gate' | 'bronze_frame'
  noren     True / False (default: basalt on, timber_gate seeded, bronze_frame off)
Overall width = clear_w + jambs (basalt jambs ~0.85-1.0 each, capped at the proxy width when clear_w is default).

Pivot: base centre, +Y faces the approach side (noren crest side). Walk-through: proxy frame=true.
Animation: none (the noren is its own row). Lighting: lightmap only (UV1).
Custom props: kz_params (JSON), kz_noren (JSON hang line or null), kz_clear (JSON opening box for the
clearance check: x0, x1, z1).
"""
import json
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_bridge_arched as kz
from gen_torii_basalt import Rock, rounded_rock

ASSET = 'portal_arch'
FEATURES = ['rough basalt arch round a timber lintel frame', 'optional noren under the lintel',
            'timber gate posts and top beam', 'bronze-and-timber door frame']
STYLES = ('basalt', 'timber_gate', 'bronze_frame')

RES = {
    0: dict(cuts=3, amp=1.0, crack=1.0, cham=True, bev=0.012, studs=True, noren_grid=(6, 5), struts=True, lattice=2, extra=True),
    1: dict(cuts=1, amp=0.8, crack=0.5, cham=True, bev=0.0, studs=False, noren_grid=(3, 3), struts=True, lattice=1, extra=True),
    2: dict(cuts=1, amp=0.5, crack=0.0, cham=False, bev=0.0, studs=False, noren_grid=(1, 1), struts=False, lattice=0, extra=False),
    3: dict(cuts=0, amp=0.0, crack=0.0, cham=False, bev=0.0, studs=False, noren_grid=(1, 1), struts=False, lattice=-1, extra=False),
}


# ------------------------------------------------------------------ helpers
def beam_x(mb, x0, x1, y, z0, z1, dy, mi, cham=0.0, caps=True):
    """chamfered beam along X, cross-section dy (depth) x (z1 - z0)"""
    c = min(cham, (z1 - z0) * 0.3, dy * 0.3)
    if c > 0:
        poly = [(y - dy / 2 + c, z0), (y + dy / 2 - c, z0), (y + dy / 2, z0 + c), (y + dy / 2, z1 - c), (y + dy / 2 - c, z1),
                (y - dy / 2 + c, z1), (y - dy / 2, z1 - c), (y - dy / 2, z0 + c)]
    else:
        poly = [(y - dy / 2, z0), (y + dy / 2, z0), (y + dy / 2, z1), (y - dy / 2, z1)]
    return kz.prism_x(mb, poly, x0, x1, mi, caps=(caps, caps))


def post(mb, x, y, z0, z1, wx, wy, mi, cham):
    if cham:
        c = min(wx, wy) * 0.14
        poly = [(-wx / 2 + c, wy / 2), (-wx / 2, wy / 2 - c), (-wx / 2, -wy / 2 + c), (-wx / 2 + c, -wy / 2),
                (wx / 2 - c, -wy / 2), (wx / 2, -wy / 2 + c), (wx / 2, wy / 2 - c), (wx / 2 - c, wy / 2)]
    else:
        poly = [(-wx / 2, wy / 2), (-wx / 2, -wy / 2), (wx / 2, -wy / 2), (wx / 2, wy / 2)]
    return mb.poly_prism([(x + px, y + py) for px, py in poly], z0, z1, mi)


def lathe_at(mb, base, prof, mi, segs, axis_y=1):
    """lathe about +Y (axis_y=1) or -Y from `base` (used for studs / bolt heads on vertical faces)"""
    bm = mb.bm
    lay = mb._mark_old()
    kz.lathe(mb, (0, 0, 0), prof, mi, segs=segs)
    new = mb._new_faces(lay)
    vs = list({v for f in new for v in f.verts})
    from mathutils import Matrix
    M = Matrix.Translation(Vector(base)) @ Matrix.Rotation(-math.pi / 2 * axis_y, 4, 'X')
    bmesh.ops.transform(bm, matrix=M, verts=vs)
    return new


def noren_panels(mb, x0, x1, ztop, length, n, y, mi, grid, r, lod, crest_mi=None):
    """split cloth panels under a lintel: joined top band, slits below, gentle folds growing to the hem"""
    bm = mb.bm
    nu, nv = grid
    gap = 0.025 if lod < 3 else 0.0
    band = min(0.14, length * 0.14)
    if lod == 3:
        n, band = 1, 0.0
    pw = (x1 - x0 - gap * (n - 1)) / n
    faces = []
    for k in range(n):
        px0 = x0 + k * (pw + gap)
        ph = length * r.uniform(0.96, 1.0) if lod < 2 else length
        centre = (k == n // 2) if n % 2 else (k in (n // 2 - 1, n // 2))
        if centre and lod < 3:
            ph *= 1.25                       # the crest panel hangs longest (concept #06)
        swing = r.uniform(-0.03, 0.03)
        phase = r.uniform(0, math.tau)
        rows = []
        for j in range(nv + 1):
            t = j / nv
            z = ztop - ph * t
            row = []
            for i in range(nu + 1):
                u = i / nu
                xx = px0 + pw * u
                amp = (0.025 + 0.08 * t) if nu > 1 else 0.0
                yy = y + amp * math.sin(u * math.tau * 1.5 + phase) + swing * t * t
                row.append(bm.verts.new((xx, yy, z)))
            rows.append(row)
        for j in range(nv):
            for i in range(nu):
                f = bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
                f.material_index = mi
                faces.append(f)
    if crest_mi is not None and lod <= 1:
        # crest slot: a dark decal quad on the centre panel(s), 15 mm proud of the cloth (or swap the noren row)
        cx = (x0 + x1) / 2
        cs = min(0.42, pw * 0.8)
        zc = ztop - band - cs * 0.75
        q = [bm.verts.new(c) for c in ((cx - cs / 2, y + 0.06, zc - cs / 2), (cx + cs / 2, y + 0.06, zc - cs / 2),
                                         (cx + cs / 2, y + 0.06, zc + cs / 2), (cx - cs / 2, y + 0.06, zc + cs / 2))]
        f = bm.faces.new(q); f.material_index = crest_mi; faces.append(f)
    if band > 0 and n > 1:
        # bridge the slits in the top band (the sewn head of the noren)
        for k in range(n - 1):
            gx0 = x0 + (k + 1) * pw + k * gap
            q = [bm.verts.new(c) for c in ((gx0, y, ztop), (gx0 + gap, y, ztop), (gx0 + gap, y, ztop - band), (gx0, y, ztop - band))]
            f = bm.faces.new(q); f.material_index = mi; faces.append(f)
    return faces


# ------------------------------------------------------------------ styles
def yprism(mb, poly_xz, y0, y1, mi, caps=(True, True)):
    """extrude an (x, z) outline (side-on silhouette) between y0 and y1"""
    bm = mb.bm
    ar = sum(poly_xz[i][0] * poly_xz[(i + 1) % len(poly_xz)][1] - poly_xz[(i + 1) % len(poly_xz)][0] * poly_xz[i][1]
             for i in range(len(poly_xz)))
    if ar > 0:
        poly_xz = poly_xz[::-1]
    A = [bm.verts.new((x, y0, z)) for x, z in poly_xz]
    B = [bm.verts.new((x, y1, z)) for x, z in poly_xz]
    faces = ([bm.faces.new(A[::-1])] if caps[0] else []) + ([bm.faces.new(B)] if caps[1] else [])
    n = len(poly_xz)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((A[i], A[j], B[j], B[i])))
    mb._tag(faces, mi)
    return faces


def kibana_beam(mb, x0, x1, z0, z1, y, dy, mi, cut=0.1):
    """head beam with raked, cut ends (kibana): side outline extruded through the depth"""
    poly = [(x0, z0 + cut), (x0 + cut * 0.6, z0), (x1 - cut * 0.6, z0), (x1, z0 + cut), (x1, z1), (x0, z1)]
    return yprism(mb, poly, y - dy / 2, y + dy / 2, mi)


def flare_pass(mb, lay, sx, x_in, xo0, xo1, z0, z1):
    """push the outer side of the jamb verts out so the jamb swells from xo1 (head) to xo0 (floor)"""
    vs = list({v for f in mb._new_faces(lay) for v in f.verts})
    for v in vs:
        t = max(0.0, min(1.0, (v.co.z - z0) / max(0.01, z1 - z0)))
        xo = xo0 + (xo1 - xo0) * t ** 0.8
        u = (abs(v.co.x) - x_in) / max(0.01, xo1 - x_in)            # 0 at the opening, 1 at the head-level outer face
        v.co.x = sx * (x_in + max(0.0, u) * (xo - x_in)) if u > 0 else v.co.x


def build_basalt(mb, R, r, lod, cw, ch, D, M, P):
    """one continuous craggy basalt mass (flared jambs, overhanging crown) round a dark hinoki frame"""
    W, H = P['W'], P['H']
    rock = Rock(r, cell=0.3, stretch=(1.0, 1.0, 0.8), amp=0.11, crack=0.06, glassy=0.1, width=0.2, fbm=0.18)
    pw = P['post_w']
    over = P['crown_over']                       # crown overhang in front of the jambs
    yj1 = D / 2 - over                           # jamb front face
    tdy = 0.32
    ty = yj1 - tdy / 2 + 0.12                    # timber stands 0.12 proud of the jamb face, under the crown
    x_in = cw / 2 + pw * 0.5                     # posts half-embedded in the rock
    xo0, xo1 = W / 2, W / 2 - P['flare']         # outer face at the floor / at the head
    ch = ch + 0.1                                # the 0.25 m platform: clear height above it is ch - 0.15
    tie_z0, tie_z1 = ch, ch + 0.14
    hb0 = ch + 0.22
    hb1 = hb0 + 0.3
    arch = P['arch']
    rise = P['arch_rise']
    ka, kc = R['amp'], R['crack']
    glassy = None      # single-face wet patches read as texture errors: keep the rock one material
    plat = 0.25                                  # raised stone platform the arch stands on
    crown0 = hb1 - 0.04 if not arch else ch + 0.05
    # ---- one layout for every LOD (its own rng), so LOD switches never add or move rocks
    L = genlib.rng(P['seed'], 'portal_basalt_layout')
    gap = 0.08                                   # recessed joints between rocks (the core shows dark behind)
    jambs = []                                   # (x0, x1, z0, z1, yfront) per rock
    outline = {-1: [], 1: []}                    # outer x per course, for the LOD3 silhouette
    jtop = crown0 + 0.3
    for sx in (-1, 1):
        nc = L.choice([4, 5, 5, 6])
        hs = [L.uniform(0.75, 1.25) for _ in range(nc)]
        tot = sum(hs)
        z = plat - 0.05
        for k in range(nc):
            hgt = (jtop - z if k == nc - 1 else (jtop - plat) * hs[k] / tot)
            t = (z + hgt / 2 - plat) / max(0.1, crown0 - plat)
            flare = P['foot_flare'] * max(0.0, 1 - t * 1.6) ** 1.5          # flared foot over the lower courses
            xo = W / 2 - P['flare'] + flare + L.uniform(-0.15, 0.15) * (0.4 if k == 0 else 1.0)
            xo = min(W / 2, xo)
            outline[sx].append((xo, z, z + hgt))
            nb = 2 if (xo - x_in) > 0.85 and L.random() < 0.6 else 1
            cuts_x = [x_in - 0.04, xo] if nb == 1 else [x_in - 0.04, x_in + (xo - x_in) * L.uniform(0.4, 0.6), xo]
            for j in range(nb):
                jambs.append((sx, cuts_x[j], cuts_x[j + 1], z, z + hgt, yj1 + L.uniform(-0.1, 0.1), L.uniform(-0.04, 0.04)))
            z += hgt
    nk = L.choice([4, 5, 5, 6])
    edges = [-W / 2 + 0.02 + (W - 0.04) * (k + (L.uniform(-0.15, 0.15) if 0 < k < nk else 0)) / nk for k in range(nk + 1)]
    crown = []
    for k in range(nk):
        a_, b_ = edges[k], edges[k + 1]
        xc = (a_ + b_) / 2
        top = H - L.uniform(0.0, 0.4)
        if arch:
            tt = max(0.0, 1 - (xc / (cw / 2 + 0.2)) ** 2)
            zb = ch + rise * tt
        else:
            zb = crown0
        if k in (0, nk - 1):
            zb = min(zb, crown0) - 0.35
        crown.append((a_, b_, zb, top, L.uniform(-0.03, 0.03)))
    crags = []
    for k in range(L.choice([2, 3, 4])):
        s_ = L.uniform(0.4, 0.65)
        crags.append((-W / 2 + 0.6 + (W - 1.2) * (k + L.uniform(0.2, 0.8)) / 3.5, L.uniform(-0.2, 0.2), s_))
    moss = [(L.choice([-1, 1]) * L.uniform(0.5, W / 2 - 0.4), L.choice(['crown', 'course'])) for _ in range(L.choice([2, 3, 4]))]
    if lod == 3:
        # silhouette from the same layout: ragged jamb outline + crown skyline (irregular, not a box)
        for sx in (-1, 1):
            o_ = outline[sx]
            mid = o_[len(o_) // 2]
            poly = [(sx * x_in, plat), (sx * o_[0][0], plat), (sx * mid[0], mid[1]), (sx * o_[-1][0], jtop), (sx * x_in, jtop)]
            yprism(mb, poly if sx > 0 else poly[::-1], -D / 2, yj1, M['rock'])
        sky = [(-W / 2 + 0.05, crown0 - 0.35), (W / 2 - 0.05, crown0 - 0.35)]
        for a_, b_, zb, top, _ in reversed(crown[::2] if len(crown) > 3 else crown):
            sky.append(((a_ + b_) / 2, top))
        sky = sky[:2] + [(W / 2 - 0.1, H - 0.3)] + sky[2:] + [(-W / 2 + 0.1, H - 0.3)]
        yprism(mb, sky, -D / 2, D / 2, M['rock'])
    else:
        cuts_j = {0: 2, 1: 1, 2: 0}[lod]
        cuts_c = {0: 3, 1: 1, 2: 0}[lod]
        rr_ = 0.12 if lod < 2 else 0.0
        # dark core behind the joints (inset, so the gaps read as deep recesses)
        for sx in (-1, 1):
            xo_min = min(o[0] for o in outline[sx])
            mb.box((sx * (x_in + xo_min) / 2, (yj1 - 0.12 - D / 2) / 2, (plat + jtop) / 2),
                   (xo_min - x_in - 0.1, yj1 - 0.12 + D / 2, jtop - plat), M['core'])
        mb.box((0, 0, (crown0 + H - 0.35) / 2), (W - 0.3, D - 0.25, H - 0.35 - crown0), M['core'])
        for sx, x0_, x1_, z0_, z1_, yf, rz in jambs:
            sz = (x1_ - x0_ - gap, yf + D / 2 - gap, z1_ - z0_ - gap)
            ctr = (sx * (x0_ + x1_) / 2, (yf - D / 2) / 2, (z0_ + z1_) / 2)
            rounded_rock(mb, ctr, sz, M['rock'], rock, cuts_j, ka, kc, round_r=rr_, rot_z=rz, clamp_z=plat - 0.05)
        for a_, b_, zb, top, rz in crown:
            sz = (b_ - a_ - gap, D * 0.98, top - zb - gap * 0.5)
            rounded_rock(mb, ((a_ + b_) / 2, 0.0, (zb + top) / 2), sz, M['rock'], rock, cuts_c, ka, kc,
                         round_r=rr_ * 1.5, rot_z=rz)
        for cx_, cy_, s_ in crags:
            rounded_rock(mb, (cx_, cy_, H - s_ * 0.34), (s_ * 1.7, D * 0.7, s_ * 0.72), M['rock'], rock,
                         max(0, cuts_c - 1), ka, kc, round_r=rr_)
        if lod == 0:
            # moss clumps on the crown ledges and course tops (front edge)
            for mx, where in moss:
                if where == 'crown':
                    zc_ = max(t for a_, b_, zb, t, _ in crown if a_ <= mx <= b_) - 0.02
                    yc_ = D / 2 - 0.25
                else:
                    sx = 1 if mx > 0 else -1
                    zc_ = outline[sx][min(2, len(outline[sx]) - 1)][2] - 0.02
                    mx = sx * (x_in + 0.3); yc_ = yj1 - 0.1
                mrk = genlib.rng(int(mx * 1000), 'moss')
                for j in range(3):          # a tuft: three overlapping cushions, not a strip
                    rounded_rock(mb, (mx + mrk.uniform(-0.12, 0.12), yc_ + mrk.uniform(-0.06, 0.06), zc_ + 0.02),
                                 (mrk.uniform(0.16, 0.26), mrk.uniform(0.14, 0.22), mrk.uniform(0.08, 0.13)), M['moss'], rock,
                                 1, 0.4, 0.0, round_r=0.05)
    # ---- timber frame (dark hinoki): posts, tie beam (noren), struts, kibana head beam projecting 0.35 m
    cham = R['cham']
    xp = cw / 2 + pw / 2
    for sx in (-1, 1):
        post(mb, sx * xp, ty, 0.24, hb1 if not arch else ch + 0.14, pw, tdy * 0.9, M['wood'], cham)
        if lod <= 1:
            mb.box((sx * xp, ty, 0.25 + 0.11), (pw + 0.03, tdy * 0.9 + 0.03, 0.22), M['bronze'], bevel=R['bev'])
    if lod <= 2:
        beam_x(mb, -(xp + pw / 2 + 0.06), xp + pw / 2 + 0.06, ty, tie_z0, tie_z1, tdy * 0.7, M['wood'],
               cham=0.02 if cham else 0.0)
    if not arch:
        lx = xp + pw / 2 + 0.35
        kibana_beam(mb, -lx, lx, hb0, hb1, ty, tdy, M['wood'], cut=0.1 if lod <= 2 else 0.0)
        if R['struts']:
            for xx in (-cw * 0.28, 0.0, cw * 0.28):
                mb.box((xx, ty, (tie_z1 + hb0) / 2), (0.12, tdy * 0.6, hb0 - tie_z1 + 0.02), M['wood'])
        if lod <= 1:
            for sx in (-1, 1):       # bronze kanamono caps on the beam ends
                mb.box((sx * (lx - 0.05), ty, (hb0 + hb1) / 2 + 0.03), (0.1, tdy + 0.012, hb1 - hb0 - 0.04), M['bronze'],
                       bevel=R['bev'])
    # ---- raised stone platform (0.25 m) under the whole arch, apron to the front
    if lod <= 1:
        rounded_rock(mb, (0, 0, plat / 2 - 0.02), (W - 0.02, D - 0.02, plat + 0.04), M['wet'], rock, 1, ka * 0.25, 0.0,
                     round_r=0.05, clamp_z=0.0)
    else:
        mb.box((0, 0, plat / 2), (W - 0.04, D - 0.04, plat), M['wet'])
    return dict(noren_ztop=tie_z0 - 0.02, noren_x=(-cw / 2 + 0.02, cw / 2 - 0.02), noren_y=ty + tdy * 0.35 + 0.03,
                clear=(-cw / 2, cw / 2, ch))


def build_gate(mb, R, r, lod, cw, ch, D, M, P):
    """hinoki gate: posts on basalt footings, nuki, lintel, kasagi or small gabled roof"""
    W, H = P['W'], P['H']
    pw = P['post_w']
    cham = R['cham']
    top = P['gate_top']
    rock = Rock(r, cell=0.3, amp=0.03, crack=0.03, width=0.2)
    xs = [sx * (cw / 2 + pw / 2) for sx in (-1, 1)]
    foot_h = 0.32
    for x in xs:
        if lod <= 2:
            rounded_rock(mb, (x, 0, foot_h / 2), (pw * 2.1, pw * 2.1, foot_h), M['rock'], rock, R['cuts'], R['amp'], R['crack'],
                         round_r=0.06, batter=0.15, clamp_z=0.0)
        else:
            mb.box((x, 0, foot_h / 2), (pw * 2.0, pw * 2.0, foot_h), M['rock'])
        post(mb, x, 0, foot_h - 0.02, (H - 0.5) if top == 'flat' else ch + 0.25, pw, pw, M['wood'], cham)
        if lod <= 1:
            mb.box((x, 0, foot_h + 0.07), (pw + 0.03, pw + 0.03, 0.14), M['bronze'], bevel=R['bev'])
    # lintel (kamoi) and nuki
    lw = cw / 2 + pw + 0.12
    beam_x(mb, -lw, lw, 0, ch, ch + 0.18, pw * 0.75, M['wood'], cham=0.02 if cham else 0.0)
    nz = ch * P['nuki_k']
    if lod <= 2 and top != 'flat':
        # tie beam framed between the posts (no through-tenon ends: that would read as a torii nuki)
        beam_x(mb, -(cw / 2 + 0.01), cw / 2 + 0.01, 0, nz, nz + 0.16, pw * 0.45, M['wood'], cham=0.015 if cham else 0.0)
        if lod <= 1:
            for x in xs:      # bronze joint plates where it meets the posts
                mb.box((x - math.copysign(pw / 2 + 0.02, x), pw * 0.23 + 0.006, nz + 0.08), (0.06, 0.012, 0.22), M['bronze'])
    if top == 'flat':
        # kabuki-mon: heavy flat kabuki beam on the post heads with raked ends, a board coping with bronze
        # edge strips, and a hinoki plaque in the middle; straight, no upsweep, no second crossbeam
        kb0, kb1 = H - 0.5, H - 0.14
        lx = cw / 2 + pw + 0.22                 # short raked overhang (a torii kasagi runs far past the posts)
        kibana_beam(mb, -lx, lx, kb0, kb1, 0, pw * 1.3, M['wood'], cut=0.12 if lod <= 2 else 0.0)
        kz.prism_x(mb, [(-D / 2 + 0.05, kb1), (D / 2 - 0.05, kb1), (D / 2 - 0.05, kb1 + 0.05), (0, H),
                        (-D / 2 + 0.05, kb1 + 0.05)], -lx - 0.15, lx + 0.15, M['wood'])
        # solid head panel (ranma boards) between lintel and kabuki beam: a gate head, not an open torii
        mb.box((0, 0, (ch + 0.18 + kb0) / 2), (cw + 0.02, pw * 0.3, kb0 - ch - 0.18 + 0.02), M['wood'])
        if lod <= 1:
            for sy in (-1, 1):
                beam_x(mb, -lx - 0.15, lx + 0.15, sy * (D / 2 - 0.07), kb1 + 0.02, kb1 + 0.07, 0.05, M['bronze'])
            # plaque (gaku) between lintel and kabuki beam
            mb.box((0, pw * 0.3, (ch + 0.18 + kb0) / 2), (0.9, 0.06, kb0 - ch - 0.26), M['wood'], bevel=R['bev'])
            mb.box((0, pw * 0.3 + 0.032, (ch + 0.18 + kb0) / 2), (0.78, 0.01, kb0 - ch - 0.36), M['bronze_d'])
        if lod <= 2:
            for x in xs:       # post heads carry the beam: short daito blocks
                mb.box((x, 0, kb0 - 0.06), (pw * 1.25, pw * 1.25, 0.12), M['wood'])
    else:
        # small gabled board roof over the lintel
        z_e = ch + 0.42
        ridge = H
        ov = W / 2 - 0.02
        yd = D / 2 - 0.01
        th = 0.06
        # head beam carrying the roof
        beam_x(mb, -(cw / 2 + pw + 0.3), cw / 2 + pw + 0.3, 0, ch + 0.25, ch + 0.42, pw * 0.85, M['wood'], cham=0.02 if cham else 0.0)
        for sy in (-1, 1):
            poly = [(0, ridge - th), (sy * yd, z_e), (sy * yd, z_e + th), (0, ridge)]
            kz.prism_x(mb, poly, -ov, ov, M['wood'])
        if lod <= 1:
            # ridge cap (bronze) and gable boards + rafter tails
            beam_x(mb, -ov - 0.01, ov + 0.01, 0, ridge - 0.05, ridge, 0.12, M['bronze'])
            for sx in (-1, 1):
                kz.prism_x(mb, [(0, ridge - 0.02), (yd, z_e - 0.04), (yd, z_e + 0.03), (0, ridge + 0.0)][::1],
                           sx * ov - 0.03, sx * ov, M['wood'])
                kz.prism_x(mb, [(0, ridge - 0.02), (-yd, z_e - 0.04), (-yd, z_e + 0.03), (0, ridge + 0.0)],
                           sx * ov - 0.03, sx * ov, M['wood'])
            if lod == 0:
                n = int(W / 0.4)
                for k in range(n + 1):
                    x = -ov + 0.1 + (2 * ov - 0.2) * k / n
                    for sy in (-1, 1):
                        mb.box((x, sy * (yd - 0.08), z_e + 0.02 - 0.05), (0.05, 0.16, 0.06), M['wood'])
    # basalt threshold step (0.15 m) between the footings
    mb.box((0, 0, 0.075), (cw + 0.1, min(D, 1.0), 0.15), M['wet'], bevel=0.02 if lod == 0 else 0.0)
    if P['brace'] and lod <= 1:
        for x in xs:
            sx = math.copysign(1, x)
            a = Vector((x + sx * pw / 2, 0, ch - 0.6)); b2 = Vector((x + sx * (pw / 2 + 0.45), 0, ch + 0.15))
            kz.sweep(mb, [a, b2], [(-0.04, -0.05), (0.04, -0.05), (0.04, 0.05), (-0.04, 0.05)], M['wood'],
                     up=Vector((0, 1, 0)))
    return dict(noren_ztop=ch - 0.02, noren_x=(-cw / 2 + 0.02, cw / 2 - 0.02), noren_y=pw * 0.38 + 0.03,
                clear=(-cw / 2, cw / 2, ch))


def build_frame(mb, R, r, lod, cw, ch, D, M, P):
    """bronze-and-timber door frame"""
    H = P['H']
    jw = P['jamb_w']
    cham = R['cham']
    dy = D
    for sx in (-1, 1):
        x = sx * (cw / 2 + jw / 2)
        post(mb, x, 0, 0.0, ch, jw, dy * 0.92, M['wood'], cham)
        # stepped bronze plinth (0.35 m) and a full bronze shoe over the bottom 0.6 m, kept down to LOD3
        if lod == 3:
            mb.box((x, 0, 0.3), (jw + 0.1, min(D, dy * 0.92 + 0.08), 0.6), M['bronze'])
        else:
            mb.box((x, 0, 0.1), (jw + 0.14, min(D, dy * 0.92 + 0.1), 0.2), M['bronze_d'], bevel=0.02 if lod == 0 else 0.0)
            mb.box((x, 0, 0.275), (jw + 0.08, dy * 0.92 + 0.06, 0.15), M['bronze'], bevel=0.015 if lod == 0 else 0.0)
            mb.box((x, 0, 0.475), (jw + 0.03, dy * 0.92 + 0.03, 0.25), M['bronze'], bevel=R['bev'])
        if lod <= 2:
            mb.box((x, 0, 0.6), (jw + 0.05, dy * 0.92 + 0.05, 0.05), M['bronze'], bevel=R['bev'])
            # bronze edge angles (50 mm) up the jamb arrises (front pair from LOD2, all four at LOD0-1)
            for ex in (-1, 1):
                for ey in ((-1, 1) if lod <= 1 else (1,)):
                    mb.box((x + ex * (jw / 2 - 0.02), ey * (dy * 0.46 - 0.02), (0.6 + ch) / 2), (0.055, 0.055, ch - 0.6),
                           M['bronze'])
        if R['studs'] or lod == 1:
            # stud rows down the front (and at LOD0 the back) faces of the jambs
            nrow = int((ch - 0.9) / 0.34)
            for k in range(nrow + 1):
                zz = 0.8 + (ch - 1.0) * k / max(1, nrow)
                for sy in ((-1, 1) if lod == 0 else (1,)):
                    for dx in (-1, 1):
                        lathe_at(mb, (x + dx * jw * 0.22, sy * (dy * 0.46 + 0.005), zz),
                                 [(0.032, 0), (0.026, 0.018), (0, 0.03)], M['bronze'], 6 if lod == 0 else 4, axis_y=sy)
        if lod <= 1:
            for k in range(P['bands']):
                zb = 0.6 + (ch - 0.6) * (k + 1) / (P['bands'] + 1)
                mb.box((x, 0, zb), (jw + 0.02, dy * 0.92 + 0.02, 0.1), M['bronze'], bevel=R['bev'])
                if R['studs']:
                    for sy in (-1, 1):
                        for dx in (-1, 0, 1):
                            lathe_at(mb, (x + dx * jw * 0.3, sy * (dy * 0.46 + 0.01), zb),
                                     [(0.018, 0), (0.014, 0.012), (0, 0.018)], M['bronze'], 6, axis_y=sy)
            # bronze reveal strip on the opening face
            mb.box((sx * (cw / 2 + 0.006), 0, ch / 2), (0.012, dy * 0.5, ch - 0.1), M['bronze'])
    # threshold: basalt step (0.15 m) with a bronze sill plate
    mb.box((0, 0, 0.065), (cw + 0.02, dy * 0.9, 0.13), M['wet'], bevel=0.015 if lod == 0 else 0.0)
    if lod <= 2:
        mb.box((0, 0, 0.14), (cw, dy * 0.5, 0.02), M['bronze'])
    # head beam, transom, cornice
    zh = ch
    head_h = 0.28
    ow = cw / 2 + jw + 0.06
    beam_x(mb, -ow, ow, 0, zh, zh + head_h, dy * 0.95, M['wood'], cham=0.025 if cham else 0.0)
    if lod <= 1:
        beam_x(mb, -ow - 0.005, ow + 0.005, 0, zh + 0.09, zh + 0.17, dy * 0.95 + 0.02, M['bronze'])
    zt0, zt1 = zh + head_h, H - 0.16
    if zt1 - zt0 > 0.1:
        # transom posts (end) + infill
        for sx in ((-1, 1) if lod <= 2 else ()):
            mb.box((sx * (cw / 2 + jw / 2), 0, (zt0 + zt1) / 2), (jw, dy * 0.8, zt1 - zt0), M['wood'])
        if P['transom'] == 'kumiko' and R['lattice'] >= 0:
            mb.box((0, 0, (zt0 + zt1) / 2), (cw, 0.02, zt1 - zt0), M['bronze_d'])          # dark backing panel
            n = {2: 14, 1: 8, 0: 4}[R['lattice']]
            for k in range(n + 1):
                xx = -cw / 2 + cw * k / n
                mb.box((xx, 0, (zt0 + zt1) / 2), (0.03, 0.08, zt1 - zt0), M['wood'])
            if R['lattice'] >= 1:
                for zz in (zt0 + (zt1 - zt0) * 0.33, zt0 + (zt1 - zt0) * 0.66):
                    mb.box((0, 0, zz), (cw, 0.06, 0.025), M['wood'])
        else:
            mb.box((0, 0, (zt0 + zt1) / 2), (cw, dy * 0.3, zt1 - zt0), M['wood'] if lod <= 2 else M['bronze_d'])
            if lod <= 2:
                mb.box((0, dy * 0.15 + 0.01, (zt0 + zt1) / 2), (cw * 0.5, 0.02, (zt1 - zt0) * 0.75), M['bronze'], bevel=R['bev'])
            if R['studs']:
                for sx in (-1, 1):
                    lathe_at(mb, (sx * cw * 0.21, dy * 0.15 + 0.02, (zt0 + zt1) / 2), [(0.03, 0), (0.024, 0.016), (0, 0.026)],
                             M['bronze'], 8)
    # cornice
    cz = H - 0.16
    beam_x(mb, -ow - 0.08, ow + 0.08, 0, cz, H - 0.05, dy, M['wood'], cham=0.03 if cham else 0.0)
    # bronze cap on the cornice
    beam_x(mb, -ow - 0.1, ow + 0.1, 0, H - 0.055, H, dy, M['bronze'] if lod <= 2 else M['wood'])
    if lod <= 1:
        for sx in (-1, 1):
            mb.box((sx * (ow + 0.03), 0, cz + 0.08), (0.12, dy + 0.005, 0.17), M['bronze'], bevel=R['bev'])
    return dict(noren_ztop=ch - 0.02, noren_x=(-cw / 2 + 0.02, cw / 2 - 0.02), noren_y=dy * 0.25 + 0.03,
                clear=(-cw / 2, cw / 2, ch))


# ------------------------------------------------------------------ main
def build(lod, seed, clear_w=None, clear_h=None, depth=None, style=None, noren=None, w=None, h=None, d=None):
    p = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    R = RES[lod]
    style = style or STYLES[(seed - 1) % 3]
    # seeded draws in a fixed order
    cw_b, cw_g, cw_f = r.uniform(2.75, 2.9), r.uniform(3.1, 3.4), r.uniform(2.8, 3.0)
    head_style = r.choice(['single', 'double', 'double'])
    gate_top = r.choice(['kasagi', 'roof'])
    upsweep = r.uniform(0.1, 0.22)
    nuki_k = r.uniform(0.8, 0.88)
    brace = r.random() < 0.5
    transom = r.choice(['kumiko', 'plaque'])
    bands = r.choice([1, 2, 2, 3])
    n_noren = r.choice([2, 3, 3, 4])
    noren_gate = r.random() < 0.5
    tint_w = (r.uniform(0.85, 1.0), r.uniform(0.82, 0.95), r.uniform(0.78, 0.9))
    wear = round(r.uniform(0.2, 0.5), 2)
    rock_tint = r.uniform(0.9, 1.05)
    jamb_k = r.uniform(0.9, 1.05)
    noren_len_k = r.uniform(0.4, 0.48)
    post_w = r.uniform(0.28, 0.32)
    crown_over = r.uniform(0.2, 0.3)
    flare = r.uniform(0.25, 0.35)              # jamb foot flares this much past the head-level outer face
    arch_rise = r.uniform(0.4, 0.6)
    cloth = r.choice(['cream', 'cream', 'cream', 'indigo', 'black'])
    # alternate the big binary choices between successive seeds of the same style (seeds 1/4, 2/5, 3/6
    # always differ in silhouette); the seeded draws above still vary everything else
    alt = ((seed - 1) // 3) % 2
    head_style = 'double'
    arch = (False, True)[alt]                 # second basalt seed: grotto arch with an arched soffit
    if alt == 0:
        cloth = 'cream'                       # concept noren: off-white with a dark crest
    gate_top = ('roof', 'flat')[alt]          # never an upswept kasagi: that is the torii asset
    transom = ('kumiko', 'plaque')[alt]
    cw = float(clear_w or {'basalt': cw_b, 'timber_gate': cw_g, 'bronze_frame': cw_f}[style])
    ch = float(clear_h or 3.0)
    D = float(depth or d or {'basalt': p['d'], 'timber_gate': 1.2, 'bronze_frame': 0.7}[style])
    # overall height: basalt = clear + frame (0.52) + crown 0.9-0.95; gate ~ +1.05; frame ~ +0.85
    H = float(h or {'basalt': min(p['h'] * 0.99, ch + 1.45), 'timber_gate': ch + 1.05, 'bronze_frame': ch + 0.85}[style])
    if style == 'basalt':
        wb = cw + post_w + 2 * 0.95 * jamb_k
        W = float(w or (min(p['w'], wb) if clear_w is None else wb))
    elif style == 'timber_gate':
        W = float(w or (min(p['w'], cw + 1.5) if clear_w is None else cw + 1.5))
    else:
        W = float(w or cw + 2 * 0.36 * jamb_k + 0.28)
    noren = noren if noren is not None else {'basalt': True, 'timber_gate': noren_gate, 'bronze_frame': False}[style]
    P = dict(W=W, H=H, head_style=head_style, gate_top=gate_top, upsweep=upsweep, nuki_k=nuki_k, brace=brace,
             transom=transom, bands=bands, post_w=post_w, jamb_w=0.36 * jamb_k, crown_over=crown_over, flare=flare,
             arch=arch, arch_rise=arch_rise, seed=seed, foot_flare=flare)
    mb = genlib.MeshBuilder()
    # dark-stained timber: library hinoki__stained
    M = dict(rock=mb.slot('basalt_dry', tint=(round(rock_tint, 3),) * 3, wear=0.3, wetness=0.35),
             wet=mb.slot('basalt_wet', tint=(round(rock_tint, 3),) * 3),
             wood=mb.slot('hinoki', variant='stained', wear=round(0.08 + wear * 0.15, 2)),
             core=mb.slot('basalt_dry', tint=(0.25, 0.25, 0.25), wear=0.0),
             moss=mb.slot('moss'),
             crest=mb.slot('noren', tint=(0.018, 0.018, 0.02)),
             bronze=mb.slot('bronze', wear=round(min(0.45, 0.25 + wear * 0.4), 2)),
             bronze_d=mb.slot('bronze', wear=0.1),
             cloth=mb.slot('noren', **({} if cloth == 'indigo' else {'tint': {'cream': (1.0, 0.92, 0.76),
                                                                           'black': (0.018, 0.018, 0.02)}[cloth]})))
    fn = {'basalt': build_basalt, 'timber_gate': build_gate, 'bronze_frame': build_frame}[style]
    info = fn(mb, R, r, lod, cw, ch, D, M, P)
    hang = None
    if noren:
        L = ch * noren_len_k
        x0, x1 = info['noren_x']
        noren_panels(mb, x0, x1, info['noren_ztop'], L, n_noren, info['noren_y'], M['cloth'], R['noren_grid'], r, lod,
                     crest_mi=M['crest'] if cloth != 'black' else None)
        hang = dict(rod_z=round(info['noren_ztop'], 3), x0=round(x0, 3), x1=round(x1, 3), y=round(info['noren_y'], 3),
                    length=round(L, 3), centre_length=round(L * 1.25, 3), panels=n_noren,
                    crest='kazan (decal slot on the centre panel)', swap_asset='noren')
    o = mb.to_object(ASSET)
    # keep every vertex inside the declared box (rock displacement can bulge past it)
    me = o.data
    for v in me.vertices:
        v.co.x = max(-W / 2, min(W / 2, v.co.x))
        v.co.y = max(-D / 2, min(D / 2, v.co.y))
        v.co.z = max(0.0, min(H, v.co.z))
    genlib.finish(o, smooth_angle=40)
    kz.uv_grain(o, [M['wood']])
    o['kz_params'] = json.dumps(dict(style=style, clear_w=round(cw, 3), clear_h=round(ch, 3), depth=round(D, 3),
                                     w=round(W, 3), h=round(H, 3), noren=bool(noren), head_style=head_style,
                                     gate_top=gate_top, transom=transom, bands=bands, brace=brace, arch=arch,
                                     post_w=round(post_w, 3), crown_over=round(crown_over, 3), cloth=cloth))
    o['kz_noren'] = json.dumps(hang)
    c = info['clear']
    o['kz_clear'] = json.dumps(dict(x0=round(c[0], 3), x1=round(c[1], 3), z1=round(c[2], 3)))
    return o
