"""Lava window: tall thick lava glass in a dark bronze mullion grid with a heavy sill (hero, 5 sizes).

Identifying features kept at every LOD: tall thick glass panes, the dark bronze mullion grid (mullions plus
transom rows), the heavy sill, the deep head beam and the end posts; lava glow behind (lava_backdrop asset).

Construction (one mesh, library materials lava_glass / bronze / iron):
  * glass     - one thick pane per bay and row (glass thickness param), edges chamfered at LOD0 so the thick
                edge catches the lava light; panes sit in the mullion plane at y = 0.
  * mullions  - extruded bronze sections, seeded profile: 'tee' (deep web + wide face cap + back flange) or
                'box' (box section with a shadow groove down the face). Bronze shoes at the sill and the head.
  * major posts (seeded rhythm 'major'): every 2nd-4th mullion is a heavier post with a deeper face, a base
                block and a bracket capital under the head.
  * transoms  - optional bronze bars between the mullions (default: clean full-height bays, see `transoms`).
  * joints    - bolted bronze splice plates with iron hex bolts where transoms meet mullions (LOD0).
  * sill      - heavy iron plinth with a bronze nosing (drip groove, chamfered lip) and a toe strip.
  * head      - iron beam, seeded style: 'cornice' (stepped bronze cornice) or 'corbel' (plain deep beam on
                tapered bronze brackets over every mullion).
  * end posts - bronze pilasters full height with base plinth, inset face panel, stud rows (LOD0) and a
                stepped capital.
Seeded (shape, not just tint): mullion spacing (inside the param range), bay rhythm ('even' | 'major' |
'centre' wide middle bay), transom count and heights, head style, mullion profile, post width, sill height.

Parameters (defaults: proxy 34 x 0.6 x 12 m in 3d/assets.json, do not exceed it by > 5 %):
  w          overall width 1.4-34 m (hall 34, corridor slot 1.4-2.4, grotto panel ~6, shaft wall ~10, slide foot ~8)
  h          overall height 2.4-12 m
  d          overall depth (default proxy 0.6)
  spacing    target mullion spacing 1.5-4 m (seeded 2.4-3.4 by default; the bays divide the width evenly)
  mull_depth mullion face projection in front of the glass, m (default 0.2 * d/0.6 ... 0.24)
  transoms   number of transom rows 0-3 (default seeded: 0 about 60 %, 1 high clerestory bar at 0.88-0.92 of the
             glass height about 30 %, 2 about 10 %; no low kick rail on walls over 6 m)
  sill_h     sill height, m (default seeded 0.45-0.7, scaled down on short windows)
  glass_t    glass thickness, m (default 0.08)
  rhythm     'even' | 'major' | 'centre' (default seeded)
  head       'cornice' | 'corbel' (default seeded)
  profile    'tee' | 'box' (default seeded)

Animation (shader, heat shimmer on the glass): the glass panes carry the float point attribute
'kz_shimmer' (0 on frame, 0.35 at the top of the glass rising to 1.0 at the sill: shimmer is strongest
low down where the heat rises) and the colour attribute 'kz_shimmer_col' (same value in R). obj['kz_anim']
(JSON) names the attribute and the material slot. The runtime distorts the refraction/emission UV by
noise(t) * kz_shimmer on the lava_glass material only. No moving geometry.

Lights: obj['kz_lights'] (JSON list): one area light behind the glass (centre, size, normal +Y towards the
room, colour of 1600 K, watts scaled from the proxy's 4000 W by glass area). The glass slot is lava_glass
with emissive_level 1.0 (emissive + lightmap).
"""
import json
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_bridge_arched as kz

ASSET = 'lava_window'
FEATURES = ['tall thick glass panes', 'dark bronze mullion grid with transoms', 'heavy sill',
            'deep head beam and end posts', 'lava glow behind the glass']

# per-LOD detail switches
RES = {
    0: dict(glass_bev=0.022, prof='full', shoes=True, joints=2, studs=True, post_detail=2, cornice=3, bolts=4),
    1: dict(glass_bev=0.012, prof='simple', shoes=True, joints=1, studs=False, post_detail=1, cornice=2, bolts=0),
    2: dict(glass_bev=0.0, prof='box', shoes=True, joints=0, studs=False, post_detail=1, cornice=2, bolts=0),
    3: dict(glass_bev=0.0, prof='strip', shoes=False, joints=0, studs=False, post_detail=-1, cornice=0, bolts=0),
}


def kelvin_rgb(k):
    """approximate linear-ish RGB of a black body (Tanner Helland fit), normalised to max 1"""
    t = k / 100.0
    r = 255.0 if t <= 66 else 329.7 * (t - 60) ** -0.1332
    g = 99.47 * math.log(t) - 161.12 if t <= 66 else 288.12 * (t - 60) ** -0.0755
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.52 * math.log(t - 10) - 305.04)
    c = [max(0.0, min(255.0, x)) / 255.0 for x in (r, g, b)]
    m = max(c)
    return [round(x / m, 3) for x in c]


# ------------------------------------------------------------------ parts
def zprism(mb, poly, x, y, z0, z1, mi):
    """extrude an (x, y) polygon placed at (x, y) between z0 and z1"""
    return mb.poly_prism([(x + px, y + py) for px, py in poly], z0, z1, mi)


def xprism(mb, poly_yz, x0, x1, mi):
    return kz.prism_x(mb, poly_yz, x0, x1, mi)


def mullion_poly(style, mw, yf, yb, lvl):
    """mullion cross-section (x, y), centred on x = 0; front face at y = yf, back at y = -yb"""
    if lvl == 'strip':
        return None
    if lvl == 'box' or style == 'box' and lvl == 'simple':
        c = 0.012 if lvl != 'box' else 0.0
        if c:
            return [(mw / 2 - c, yf), (mw / 2, yf - c), (mw / 2, -yb + c), (mw / 2 - c, -yb),
                    (-mw / 2 + c, -yb), (-mw / 2, -yb + c), (-mw / 2, yf - c), (-mw / 2 + c, yf)]
        return [(mw / 2, yf), (mw / 2, -yb), (-mw / 2, -yb), (-mw / 2, yf)]
    if style == 'box':
        c, g, gd = 0.035, max(0.06, mw * 0.16), 0.03          # chamfered arrises + a groove that reads at 20 m
        return [(g / 2, yf), (g / 2, yf - gd), (-g / 2, yf - gd), (-g / 2, yf), (-mw / 2 + c, yf), (-mw / 2, yf - c),
                (-mw / 2, -yb + c), (-mw / 2 + c, -yb), (mw / 2 - c, -yb), (mw / 2, -yb + c), (mw / 2, yf - c),
                (mw / 2 - c, yf)]
    # tee: wide face cap, deep web, narrower back flange
    cw, fw, bw = mw, mw * 0.42, mw * 0.7
    ct, bt, c = 0.06, 0.03, 0.035
    if lvl == 'simple':
        return [(cw / 2, yf), (-cw / 2, yf), (-cw / 2, yf - ct), (-fw / 2, yf - ct), (-fw / 2, -yb), (fw / 2, -yb),
                (fw / 2, yf - ct), (cw / 2, yf - ct)]
    return [(cw / 2 - c, yf), (-cw / 2 + c, yf), (-cw / 2, yf - c), (-cw / 2, yf - ct), (-fw / 2, yf - ct),
            (-fw / 2, -yb + bt), (-bw / 2, -yb + bt), (-bw / 2, -yb), (bw / 2, -yb), (bw / 2, -yb + bt),
            (fw / 2, -yb + bt), (fw / 2, yf - ct), (cw / 2, yf - ct), (cw / 2, yf - c)]


def transom_poly(tw, yf, yb, lvl, zc):
    """transom cross-section (y, z) centred on z = zc"""
    if lvl in ('box', 'strip'):
        return [(-yb, zc - tw / 2), (yf, zc - tw / 2), (yf, zc + tw / 2), (-yb, zc + tw / 2)]
    c = 0.01
    ct = 0.035
    fw = tw * 0.45
    pts = [(-yb, zc - fw / 2), (yf - ct, zc - fw / 2), (yf - ct, zc - tw / 2), (yf - c, zc - tw / 2), (yf, zc - tw / 2 + c),
           (yf, zc + tw / 2 - c), (yf - c, zc + tw / 2), (yf - ct, zc + tw / 2), (yf - ct, zc + fw / 2), (-yb, zc + fw / 2)]
    return pts


def bolt(mb, x, y, z, mi, r=0.022):
    mb.cylinder((x, y + 0.012, z), radius=r, depth=0.024, mi=mi, segs=6, rot=(-math.pi / 2, 0, 0))


def build(lod, seed, w=None, h=None, d=None, spacing=None, mull_depth=None, transoms=None, sill_h=None,
          glass_t=None, rhythm=None, head=None, profile=None, glow=0.0, _detail=0):
    p = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    W = float(w or p['w']); H = float(h or p['h']); D = float(d or p['d'])
    R = dict(RES[lod])
    if _detail >= 1:                       # budget fallback for very wide / dense windows
        R['bolts'] = min(R['bolts'], 2); R['studs'] = False
    if _detail >= 2:
        R['joints'] = min(R['joints'], 1); R['glass_bev'] = 0.0
    if _detail >= 3:
        R['shoes'] = False; R['prof'] = 'simple' if R['prof'] == 'full' else R['prof']
    # ---- seeded design choices (drawn in a fixed order so params do not shift other choices)
    sp_seed = r.uniform(3.1, 4.0)          # wide walls: few, bold bays (concept sheet: ~7-9 bays on 34 m)
    rhythm_s = r.choice(['major', 'major', 'even', 'centre'])
    head_s = r.choice(['cornice', 'corbel'])
    prof_s = r.choice(['tee', 'box'])
    nt_seed = r.choice([0, 0, 0, 0, 0, 0, 1, 1, 1, 2])      # concept: clean full-height bays (60 % none)
    sill_seed = r.uniform(0.9, 1.1)
    post_k = r.uniform(0.85, 1.2)
    major_every = r.choice([2, 3, 4])
    clere = r.uniform(0.88, 0.92)
    kick = r.uniform(0.13, 0.2)
    head_k = r.uniform(0.92, 1.08)
    tv = r.uniform(0.18, 0.25)                                   # near-black dark bronze (linear albedo)
    tint = (round(tv * 1.08, 3), round(tv, 3), round(tv * 0.86, 3))
    wear = round(r.uniform(0.08, 0.2), 2)
    spacing = float(spacing or (sp_seed if W >= 12 else sp_seed * 0.72))
    spacing = min(4.0, max(1.5, spacing))
    rhythm = rhythm or rhythm_s
    head = head or head_s
    profile = profile or prof_s
    scale = min(1.0, H / 12.0) ** 0.5            # members thin out on small windows
    if transoms is None:
        transoms = nt_seed
    transoms = max(0, min(3, int(transoms)))
    sill_h = float(sill_h if sill_h is not None else
                   (sill_seed if H >= 8 else sill_seed * (H / 8.0) ** 1.2))
    glass_t = float(glass_t or 0.08)

    mb = genlib.MeshBuilder()
    m_glass = mb.slot('lava_glass', emissive_level=glow)
    m_bronze = mb.slot('bronze', wear=wear)                          # library bronze: blackened, gold wear edges
    m_bronze_d = mb.slot('bronze', wear=round(wear * 0.5, 2))
    m_iron = mb.slot('iron', wear=round(0.15 + wear * 0.5, 2))

    hd = D / 2                                    # half depth
    yf_sill = hd                                  # sill nosing = front of bbox
    yb_all = -hd
    # mullion face 0.15 m in front of the glass, so the sill nosing (at the front of the box) projects
    # 0.15 m past it; the mullions run deeper on the lava side instead
    md = float(mull_depth or min(hd - 0.05, 0.15 * D / 0.6))
    yb_m = min(hd - 0.05, 0.22 * D / 0.6)
    mw = (0.47 if profile == 'tee' else 0.44) * (0.5 + 0.5 * scale)     # 0.42-0.48 m faces on the 12 m wall
    post_k = 0.94 + 0.12 * (post_k - 0.85) / 0.35
    pw = min(W * 0.16, 1.05 * post_k * max(0.4, min(1.0, H / 12.0) ** 0.6))   # end post (0.95 shaft + base step)
    head_h = max(0.25, min(0.95, 0.075 * H)) * head_k
    if W < 2.6:                                   # corridor slot: at least 70 % of the width is glass
        pw = min(pw, 0.12 * W)
        head_h = min(head_h, 0.3)
        sill_h = min(sill_h, 0.35)
    z_glass0 = sill_h
    z_glass1 = H - head_h

    # ---- bays
    inner = W - 2 * pw
    n_bays = max(1, int(round(inner / spacing)))
    if W < 2.6:
        n_bays = 1
    widths = [1.0] * n_bays
    if rhythm == 'centre' and n_bays >= 3:
        mid = n_bays // 2
        if n_bays % 2 == 1:
            widths[mid] = 1.6
        else:
            widths[mid - 1] = widths[mid] = 1.4
    tot = sum(widths)
    xs = [-inner / 2]
    for wd in widths:
        xs.append(xs[-1] + inner * wd / tot)
    mull_x = xs[1:-1]
    majors = set()
    if rhythm == 'major' and len(mull_x) >= 3:
        off = (len(mull_x) % major_every) // 2
        for i in range(len(mull_x)):
            if (i + 1 + off) % major_every == 0:
                majors.add(i)
    # rows (transom centre heights)
    gh = z_glass1 - z_glass0
    t_z = []
    if transoms >= 1:
        t_z.append(z_glass0 + gh * clere)                       # high clerestory bar
    if transoms >= 2:
        t_z.append(z_glass0 + gh * (kick if H <= 6 else 0.5))   # no low kick rail on walls over 6 m
    if transoms >= 3:
        t_z.append(z_glass0 + gh * ((kick + 0.5) / 2 if H <= 6 else 0.25))
    t_z.sort()
    tw = 0.17 * (0.6 + 0.4 * scale)
    tyf, tyb = md - 0.03, yb_m * 0.8
    # ---------------------------------------------------------------- glass
    glass_faces = []
    row_edges = [z_glass0] + [z for z in t_z] + [z_glass1]
    lv = R['prof']
    if lod == 3:
        bm = mb.bm
        for yy, flip in ((glass_t / 2, False),):      # one pane: two would double the glass tint
            q = [bm.verts.new(c) for c in ((-inner / 2, yy, z_glass0), (inner / 2, yy, z_glass0), (inner / 2, yy, z_glass1),
                                            (-inner / 2, yy, z_glass1))]
            f = bm.faces.new(q[::-1] if flip else q); f.material_index = m_glass
    elif lod == 2:
        # one slab across the whole opening (the grid sits on it)
        glass_faces += mb.box((0, 0, (z_glass0 + z_glass1) / 2), (inner + 0.04, glass_t, gh + 0.04), m_glass)
    else:
        web = mw * 0.42 if profile == 'tee' else mw
        for i in range(n_bays):
            x0 = xs[i] + (web / 2 + 0.006 if i > 0 else -0.02)
            x1 = xs[i + 1] - (web / 2 + 0.006 if i < n_bays - 1 else -0.02)
            for k in range(len(row_edges) - 1):
                z0 = row_edges[k] + (tw * 0.225 + 0.006 if k > 0 else -0.02)
                z1 = row_edges[k + 1] - (tw * 0.225 + 0.006 if k < len(row_edges) - 2 else -0.02)
                glass_faces += mb.box(((x0 + x1) / 2, 0, (z0 + z1) / 2), (x1 - x0, glass_t, z1 - z0), m_glass,
                                      bevel=R['glass_bev'], bevel_segs=1)
    # ---------------------------------------------------------------- mullions
    for i, x in enumerate(mull_x):
        major = i in majors
        if lv == 'strip':
            # front + two sides only (silhouette LOD)
            bm = mb.bm
            a, b = mw * (1.4 if major else 1.0) / 2, md + (0.04 if major else 0)
            v = [bm.verts.new(c) for c in ((x - a, -0.02, z_glass0), (x - a, b, z_glass0), (x + a, b, z_glass0),
                                            (x + a, -0.02, z_glass0), (x - a, -0.02, z_glass1), (x - a, b, z_glass1),
                                            (x + a, b, z_glass1), (x + a, -0.02, z_glass1))]
            fs = [bm.faces.new((v[0], v[1], v[5], v[4])), bm.faces.new((v[1], v[2], v[6], v[5])),
                  bm.faces.new((v[2], v[3], v[7], v[6]))]
            mb._tag(fs, m_bronze)
            continue
        if major:
            # heavy post: double-width box section standing on its own plinth (floor to head), proud of the
            # mullions, with a polished face strip, a bracket capital and bolted collar bands at the transoms
            pmw, pyf = mw * 1.7, hd - 0.035
            poly = mullion_poly('box', pmw, pyf, yb_m + 0.04, 'simple' if lv != 'box' else 'box')
            zprism(mb, poly, x, 0, sill_h, z_glass1, m_bronze_d)
            if lv != 'box':
                zprism(mb, [(-pmw * 0.22, pyf), (pmw * 0.22, pyf), (pmw * 0.16, pyf + 0.018), (-pmw * 0.16, pyf + 0.018)],
                       x, 0, sill_h + 0.5, z_glass1 - 0.6, m_bronze)
                for zc in t_z:
                    mb.box((x, (pyf - yb_m) / 2, zc), (pmw * 1.12, pyf + yb_m + 0.05, tw * 1.6), m_bronze,
                           bevel=0.01 if lod == 0 else 0.0)
                # bracket capital: tapered block widening up into the head
                xprism(mb, [(-yb_m - 0.04, z_glass1 - 0.7), (pyf, z_glass1 - 0.7), (pyf + 0.01, z_glass1 - 0.6),
                            (hd - 0.012, z_glass1), (-yb_m - 0.04, z_glass1)], x - pmw * 0.7, x + pmw * 0.7, m_bronze_d)
            # plinth from the floor through the sill
            mb.box((x, 0.0, (sill_h + 0.3) / 2), (pmw * 1.3, D - 0.01, sill_h + 0.3), m_iron,
                   bevel=0.015 if lod == 0 else 0.0)
            continue
        poly = mullion_poly(profile, mw, md, yb_m, lv)
        zprism(mb, poly, x, 0, z_glass0, z_glass1, m_bronze_d)
        if lv in ('full', 'simple'):
            # raised polished bead down the face: the line that glints in the lava light
            bw_ = mw * (0.16 if profile == 'box' else 0.3)
            ox = mw * 0.3 if profile == 'box' else 0.0
            for sx_ in ((-1, 1) if profile == 'box' else (0,)):
                zprism(mb, [(-bw_ / 2, md), (bw_ / 2, md), (bw_ * 0.3, md + 0.014), (-bw_ * 0.3, md + 0.014)],
                       x + sx_ * ox, 0, z_glass0 + 0.05, z_glass1 - 0.05, m_bronze)
        if R['shoes']:
            # stepped shoe on the sill (0.6 m, 1.4x face) and bracket capital under the head (0.5 m, 1.5x face)
            k_ = 0.4 + 0.6 * scale
            sh, chp = 0.6 * k_, 0.5 * k_
            yc_, dy_ = (md - yb_m) / 2 + 0.01, md + yb_m + 0.05
            bv = 0.02 if lod == 0 else 0.0
            mb.box((x, yc_, z_glass0 + sh / 2), (mw * 1.4, dy_, sh), m_bronze_d, bevel=bv)
            if lod <= 1:
                mb.box((x, yc_, z_glass0 + sh + 0.04), (mw * 1.25, dy_ - 0.02, 0.08), m_bronze, bevel=bv * 0.5)
            if head != 'corbel':                 # the corbel head's brackets are the capitals
                mb.box((x, yc_, z_glass1 - chp * 0.35), (mw * 1.5, dy_, chp * 0.7), m_bronze_d, bevel=bv)
                if lod <= 1:
                    mb.box((x, yc_, z_glass1 - chp * 0.85), (mw * 1.28, dy_ - 0.02, chp * 0.3), m_bronze_d, bevel=bv)
    # ---------------------------------------------------------------- transoms
    for zc in t_z:
        if lv == 'strip':
            # one full-width bar (front + top + bottom)
            bm = mb.bm
            x0, x1 = -inner / 2, inner / 2
            a, b = zc - tw / 2, zc + tw / 2
            v = [bm.verts.new(c) for c in ((x0, -0.02, a), (x1, -0.02, a), (x1, tyf, a), (x0, tyf, a),
                                            (x0, -0.02, b), (x1, -0.02, b), (x1, tyf, b), (x0, tyf, b))]
            fs = [bm.faces.new((v[3], v[2], v[6], v[7]))]
            mb._tag(fs, m_bronze)
            continue
        if lv == 'box':
            xprism(mb, transom_poly(tw, tyf, tyb, lv, zc), -inner / 2, inner / 2, m_bronze)
            continue
        for i in range(n_bays):
            x0 = xs[i] + (mw * 0.5 if i > 0 else 0)
            x1 = xs[i + 1] - (mw * 0.5 if i < n_bays - 1 else 0)
            xprism(mb, transom_poly(tw, tyf, tyb, lv, zc), x0, x1, m_bronze)
    # ---------------------------------------------------------------- joints: splice plates + bolts
    if R['joints']:
        for i, x in enumerate(mull_x):
            if i in majors:
                continue
            for zc in t_z:
                ph = tw * 2.4
                mb.box((x, md + 0.006, zc), (mw * 1.5, 0.012, ph), m_bronze_d, bevel=0.004 if lod == 0 else 0.0)
                if R['bolts']:
                    pts = [(-1, -1), (1, -1), (-1, 1), (1, 1)] if R['bolts'] >= 4 else [(0, -1), (0, 1)]
                    for bx, bz in pts:
                        bolt(mb, x + bx * mw * 0.48, md + 0.012, zc + bz * ph * 0.36, m_iron)
    # ---------------------------------------------------------------- sill (between the end posts)
    x0, x1 = -W / 2 + pw * 0.98, W / 2 - pw * 0.98
    # heavy sill: dark iron block course with recessed vertical joints under a 0.2 m bronze nosing that
    # projects 0.15 m past the mullion faces (nosing at the front of the box, mullion faces at y = md)
    nose_t = min(0.2, sill_h * 0.3)
    zc1 = sill_h - nose_t
    if R['cornice'] >= 2:
        # backing core (the joints are recessed 0.02 m to it)
        xprism(mb, [(yb_all + 0.03, 0), (hd - 0.07, 0), (hd - 0.07, zc1), (yb_all + 0.03, zc1)], x0, x1, m_iron)
        if lod <= 1 and zc1 > 0.25:
            joints = []
            xx = x0
            while xx < x1 - 0.6:
                joints.append(xx)
                xx += r.uniform(1.2, 1.6)
            joints.append(x1)
            courses = 2 if zc1 > 0.55 else 1
            for k in range(len(joints) - 1):
                for c_ in range(courses):
                    za, zb_ = zc1 * c_ / courses, zc1 * (c_ + 1) / courses
                    off = 0.0 if c_ == 0 else (joints[k + 1] - joints[k]) * 0.5
                    a_, b_ = joints[k] + off, min(x1, joints[k + 1] + off)
                    if b_ - a_ < 0.3:
                        continue
                    mb.box(((a_ + b_) / 2, hd - 0.05 - 0.04, (za + zb_) / 2), (b_ - a_ - 0.02, 0.08, zb_ - za - 0.02),
                           m_iron, bevel=0.012 if lod == 0 else 0.0)
        else:
            # LOD2: the block course as one band, proud of the core
            xprism(mb, [(hd - 0.07, 0.0), (hd - 0.05, 0.0), (hd - 0.05, zc1 - 0.01), (hd - 0.07, zc1 - 0.01)], x0, x1, m_iron)
        # bronze nosing: chamfered lip with a drip groove under it
        xprism(mb, [(-0.06, zc1), (hd - 0.04, zc1), (hd - 0.04, zc1 + 0.03), (hd, zc1 + 0.05), (hd, sill_h - 0.03),
                    (hd - 0.03, sill_h), (-0.06, sill_h + 0.012)], x0, x1, m_bronze)
        # polished bronze glazing beads on the sill top, both faces of the glass
        if lod <= 1:
            for sy_ in (1, -1):
                yy = sy_ * (glass_t / 2 + 0.012)
                xprism(mb, [(yy - 0.012, sill_h), (yy + 0.012, sill_h), (yy + 0.006, sill_h + 0.05),
                            (yy - 0.006, sill_h + 0.05)], x0, x1, m_bronze)
        # back of the glass channel
        xprism(mb, [(yb_all + 0.03, zc1), (-0.06, zc1), (-0.06, sill_h + 0.03), (yb_all + 0.05, sill_h + 0.03)],
               x0, x1, m_bronze_d)
    else:
        kz.prism_x(mb, [(yb_all + 0.03, 0), (hd, 0), (hd, sill_h), (yb_all + 0.03, sill_h)], x0, x1, m_bronze_d,
                   caps=(False, False))
    # ---------------------------------------------------------------- head beam
    zh = H - head_h
    hf = md                                        # head face plane: flush with the mullion faces
    if R['cornice'] >= 2:
        xprism(mb, [(yb_all + 0.04, zh), (hf, zh), (hf, H - 0.1), (yb_all + 0.04, H - 0.1)], x0, x1, m_iron)
        if head == 'cornice':
            # stepped bronze cornice: bed mould, fascia, two steps out to a crown at the front of the box
            if R['cornice'] >= 3:
                prof = [(-0.05, H - 0.42), (hf + 0.02, H - 0.42), (hf + 0.02, H - 0.36), (hf + 0.06, H - 0.33),
                        (hf + 0.06, H - 0.26), (hf + 0.1, H - 0.23), (hf + 0.1, H - 0.17), (hd, H - 0.13), (hd, H - 0.02),
                        (hd - 0.02, H), (yb_all + 0.02, H), (yb_all + 0.02, H - 0.12)]
            else:
                prof = [(-0.05, H - 0.42), (hf + 0.04, H - 0.42), (hf + 0.04, H - 0.26), (hd, H - 0.14), (hd, H),
                        (yb_all + 0.02, H), (yb_all + 0.02, H - 0.12)]
            xprism(mb, prof, x0 - pw * 0.02, x1 + pw * 0.02, m_bronze_d)
            # crown band runs 0.12 m past the end posts so the stepped cornice shows in the front outline
            xprism(mb, [(yb_all + 0.02, H - 0.16), (hd, H - 0.16), (hd, H), (yb_all + 0.02, H)], -W / 2 - 0.12, W / 2 + 0.12,
                   m_bronze_d)
            # bronze face band along the bottom of the beam
            xprism(mb, [(hf, zh), (hf + 0.02, zh), (hf + 0.02, zh + 0.1), (hf, zh + 0.1)], x0, x1, m_bronze)
        else:
            # plain deep beam + console brackets over every mullion, rising 0.18 m above the head line
            xprism(mb, [(yb_all + 0.04, H - 0.1), (hf, H - 0.1), (hf, H - 0.18 + 0.18), (yb_all + 0.04, H)], x0, x1, m_iron)
            cb = min(0.75, gh * 0.075)
            rise = 0.25
            ztop = H + 0.0
            for i, x in enumerate(mull_x + [-inner / 2, inner / 2]):
                cwid = mw * (1.6 if i not in majors else 2.0)
                xprism(mb, [(md - 0.02, zh - cb), (md + 0.02, zh - cb), (hd - 0.01, zh - cb * 0.2), (hd - 0.01, H - rise - 0.02),
                            (hd - 0.04, H - rise), (md - 0.02, H - rise)], x - cwid / 2, x + cwid / 2, m_bronze_d)
            # the brackets carry a bronze cap rail; the head line steps down between them
            ztop = H - rise
            xprism(mb, [(yb_all + 0.04, ztop - 0.02), (hd - 0.04, ztop - 0.02), (hd - 0.04, ztop), (yb_all + 0.04, ztop)],
                   x0, x1, m_bronze)
            for i, x in enumerate(mull_x + [-inner / 2, inner / 2]):
                cwid = mw * (1.6 if i not in majors else 2.0)
                mb.box((x, -0.02, H - rise / 2), (cwid * 1.1, D - 0.1, rise), m_bronze_d, bevel=0.012 if lod == 0 else 0.0)
        if lod == 0:
            # bolt bosses on the head over every mullion
            for x in mull_x:
                for dx in (-1, 1):
                    bolt(mb, x + dx * mw * 0.3, hf + (0.02 if head == 'cornice' else 0.0), zh + head_h * 0.35, m_iron, r=0.03)
    else:
        kz.prism_x(mb, [(yb_all + 0.04, zh), (hd, zh), (hd, H), (yb_all + 0.04, H)], x0, x1, m_bronze_d,
                   caps=(False, False))
    # ---------------------------------------------------------------- end posts (pilasters)
    for sx in (-1, 1):
        xc = sx * (W / 2 - pw / 2)
        if R['post_detail'] < 0:
            bm = mb.bm
            a, yb2 = pw / 2, yb_all + 0.02
            v = [bm.verts.new(c) for c in ((xc - a, yb2, 0), (xc - a, hd, 0), (xc + a, hd, 0), (xc + a, yb2, 0),
                                            (xc - a, yb2, H), (xc - a, hd, H), (xc + a, hd, H), (xc + a, yb2, H))]
            fs = [bm.faces.new((v[0], v[1], v[5], v[4])), bm.faces.new((v[1], v[2], v[6], v[5])),
                  bm.faces.new((v[2], v[3], v[7], v[6]))]
            mb._tag(fs, m_bronze_d)
            continue
        base_h = sill_h + 0.15                       # plinth step 0.15 m above the sill
        cap_h = head_h + 0.12
        c = 0.03 if R['post_detail'] >= 1 else 0.0
        sw = pw - 0.1                                # 0.75 m shaft on the 12 m wall
        sy0, sy1 = yb_all + 0.01, hd - 0.03          # full depth
        poly = [(-sw / 2 + c, sy1), (-sw / 2, sy1 - c), (-sw / 2, sy0), (sw / 2, sy0), (sw / 2, sy1 - c), (sw / 2 - c, sy1)]
        zprism(mb, poly, xc, 0, base_h, H - cap_h, m_bronze_d)
        if R['post_detail'] >= 1:
            # base plinth (stepped) and capital (stepped), inset face panel
            mb.box((xc, 0, base_h * 0.5 - 0.04), (pw, D, base_h - 0.08), m_bronze_d, bevel=0.02 if lod == 0 else 0.0)
            mb.box((xc, 0, base_h - 0.04), (pw - 0.05, D - 0.02, 0.08), m_bronze, bevel=0.01 if lod == 0 else 0.0)
            mb.box((xc, 0, H - cap_h * 0.5 + 0.06), (pw, D, cap_h - 0.12), m_bronze_d, bevel=0.02 if lod == 0 else 0.0)
            mb.box((xc, 0.0, H - cap_h + 0.06), (pw - 0.05, D - 0.02, 0.12), m_bronze, bevel=0.01 if lod == 0 else 0.0)
            zprism(mb, [(-sw * 0.3, sy1), (sw * 0.3, sy1), (sw * 0.3, sy1 + 0.02), (-sw * 0.3, sy1 + 0.02)],
                   xc, 0, base_h + 0.35, H - cap_h - 0.35, m_bronze)
            for ex in (-1, 1):
                zprism(mb, [(-0.02, 0), (0.02, 0), (0.02, 0.02), (-0.02, 0.02)], xc + ex * (sw / 2 - 0.02), sy1,
                       base_h, H - cap_h, m_bronze)
            jx = xc - sx * (sw / 2 + mw * 0.28)
            zprism(mb, mullion_poly('box', mw * 0.55, md, yb_m, 'simple'), jx, 0, z_glass0, z_glass1, m_bronze_d)
        else:
            mb.box((xc, 0, base_h / 2), (pw, D, base_h), m_bronze_d)
            mb.box((xc, 0, H - cap_h / 2), (pw, D, cap_h), m_bronze_d)
        if R['studs']:
            n = max(3, int((H - cap_h - base_h - 0.8) / 0.9))
            for k in range(n + 1):
                zz = base_h + 0.4 + (H - cap_h - base_h - 0.8) * k / n
                for dx in (-1, 1):
                    mb.cylinder((xc + dx * sw * 0.4, sy1 + 0.008, zz), radius=0.03, radius2=0.012, depth=0.02,
                                mi=m_iron, segs=6, rot=(-math.pi / 2, 0, 0))
    o = mb.to_object(ASSET)
    budget = genlib.budget_of(ASSET)
    if budget and genlib.tris(o) > budget[min(lod, 3)] * 1.08 and _detail < 3:
        import bpy
        me = o.data
        bpy.data.objects.remove(o); bpy.data.meshes.remove(me)
        return build(lod, seed, w=w, h=h, d=d, spacing=spacing, mull_depth=mull_depth, transoms=transoms,
                     sill_h=sill_h, glass_t=glass_t, rhythm=rhythm, head=head, profile=profile, glow=glow, _detail=_detail + 1)
    # ---------------------------------------------------------------- shimmer attribute, lights, params
    me = o.data
    attr = me.attributes.new('kz_shimmer', 'FLOAT', 'POINT')
    col = me.color_attributes.new('kz_shimmer_col', 'FLOAT_COLOR', 'POINT')
    glass_v = set()
    for poly in me.polygons:
        if poly.material_index == m_glass:
            glass_v.update(poly.vertices)
    for v in me.vertices:
        s = 0.0
        if v.index in glass_v:
            t = (v.co.z - z_glass0) / max(0.01, gh)
            s = round(1.0 - 0.65 * max(0.0, min(1.0, t)), 3)
        attr.data[v.index].value = s
        col.data[v.index].color = (s, 0, 0, 1)
    area = inner * gh
    o['kz_anim'] = json.dumps({'type': 'shader', 'what': 'heat shimmer on the glass', 'attr': 'kz_shimmer',
                               'color_attr': 'kz_shimmer_col', 'material_slot': m_glass, 'material': 'lava_glass'})
    o['kz_lights'] = json.dumps([{'type': 'area', 'pos': [0.0, round(-hd - 0.3, 3), round((z_glass0 + z_glass1) / 2, 3)],
                                  'size': [round(inner, 3), round(gh, 3)], 'normal': [0, 1, 0],
                                  'color': kelvin_rgb(1600), 'color_k': 1600,
                                  'watts': round(4000 * area / (30.4 * 10.5), 1), 'note': 'lava behind the glass'}])
    o['kz_params'] = json.dumps(dict(w=round(W, 3), h=round(H, 3), d=round(D, 3), spacing=round(spacing, 3),
                                     bays=n_bays, mull_depth=round(md, 3), transoms=transoms,
                                     transom_z=[round(z, 3) for z in t_z], sill_h=round(sill_h, 3),
                                     glass_t=glass_t, rhythm=rhythm, head=head, profile=profile,
                                     majors=sorted(majors), detail_fallback=_detail))
    genlib.finish(o, smooth_angle=30)
    return o
