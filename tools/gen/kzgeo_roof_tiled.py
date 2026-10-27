"""Geometry for the roof_tiled component (also called by gen_facade_timber and, later, other host generators).

The tiled surface, tile ribs, eave discs, ridges, onigawara, gable boards, fascia, soffit and rafter tails come from
kzgeo_pavilion_engawa.roof (the roof that passed review on the engawa pavilion).  This module adds:
  * one entry point `roof_into(mb, mats, lod, typ, hw, hd, ...)` for hosts: a roof of any of the five types over an
    eave outline of half extents hw x hd, eave line at z_e, built into the host's MeshBuilder;
  * 'pyramid' (hokei: square hip roof with a roban block and an iron hoju finial at the apex);
  * 'two_tier' (a hip skirt roof, a timber frieze storey and an irimoya / hip upper roof);
  * `pent_into(...)`: a mono-pitch tiled pent roof (hisashi) running along x and draining to +y, for facades;
  * a resolution ladder that falls back on resolution (rib segments, disc sides, ring counts), never on presence.
"""
import math

import bmesh
from mathutils import Matrix, Vector

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_common as C
import kzgeo_pavilion_engawa as kp

TYPES = ['irimoya', 'hip', 'pyramid', 'gable', 'two_tier']

# per-LOD resolution of kp.roof (LOD0 = the pavilion's LOD0 with a slightly coarser surface)
RES = {
    0: dict(rings=6, n_long=16, n_short=10, up_rows=4, ribs=True, rib_segs=3, rib_prof=3, discs=True,
            disc_n=5, rafters=True, rafter_sp=0.36, fascia=True, fascia_n=8, soffit=True, ridge_prof='full', teeth=0),
    1: dict(rings=4, n_long=8, n_short=6, up_rows=2, ribs=True, rib_segs=2, rib_prof=2, discs=False,
            disc_n=4, rafters=False, fascia=True, fascia_n=4, soffit=True, ridge_prof='box', teeth=0),
    2: dict(rings=2, n_long=4, n_short=2, up_rows=1, ribs=False, rib_segs=0, rib_prof=0, discs=False,
            disc_n=0, rafters=False, fascia=True, fascia_n=2, soffit=True, ridge_prof='box', teeth=0.55),
    3: dict(rings=1, n_long=2, n_short=1, up_rows=1, ribs=False, rib_segs=0, rib_prof=0, discs=False,
            disc_n=0, rafters=False, fascia=False, fascia_n=1, soffit=False, ridge_prof='tri', teeth=0),
}
# resolution fallbacks, applied in order when an estimate is over budget (presence never changes)
LADDER = {
    0: [dict(rib_segs=2), dict(disc_n=4), dict(rings=4, n_long=10, n_short=6), dict(rafter_sp=0.45), dict(up_rows=2),
        dict(rib_prof=2), dict(fascia_n=5), dict(tp_k=1.12), dict(rib_segs=1), dict(tp_k=1.25), dict(tp_k=1.5)],
    1: [dict(rings=3, n_long=6, n_short=4), dict(rib_segs=1), dict(fascia_n=2), dict(rib_prof=1), dict(tp_k=1.25),
        dict(tp_k=1.5)],
    2: [dict(teeth=0.8), dict(fascia_n=1), dict(n_long=2, n_short=1, rings=1), dict(teeth=1.2), dict(teeth=2.0)],
    3: [],
}


def _new_verts(mb, lay):
    return list({v for f in mb._new_faces(lay) for v in f.verts})


def finial(mb, base, mi, lod, scale=1.0):
    """hoju finial on a square roban plinth (iron): turned bulb, 0.8 m tall at scale 1"""
    s = scale
    segs = C.lod_pick(lod, 12, 8, 6, 4)
    prof = [(0.17 * s, 0.0), (0.17 * s, 0.08 * s), (0.07 * s, 0.12 * s), (0.05 * s, 0.32 * s), (0.11 * s, 0.38 * s),
            (0.14 * s, 0.48 * s), (0.11 * s, 0.6 * s), (0.04 * s, 0.7 * s), (0.0, 0.8 * s)]
    if lod >= 2:
        prof = [(0.16 * s, 0.0), (0.05 * s, 0.14 * s), (0.13 * s, 0.45 * s), (0.0, 0.8 * s)]
    C.lathe(mb, prof, segs, mi, base=base)


def roof_into(mb, mats, lod, typ, hw, hd, z_e=0.0, pitch=27.0, eave=1.0, eave_s=None, up=0.18, tp=0.26, p=1.25,
              dg=None, budget=None, r=None, frieze_h=1.1, upper=None):
    """Build one roof into mb. Eave outline: |x| <= hw, |y| <= hd, eave tile edge at z_e.
    mats: dict(tile, ridge, wood, wood_d, iron[, frieze]).  eave / eave_s: overhang beyond the wall line at the
    front-back / ends (drives soffit, rafter tails and the gable board position).  pitch: mean slope in degrees.
    budget: triangle cap for this roof; the resolution ladder (LADDER[lod]) is walked on a dry run until the roof
    fits, so only resolution changes, never which parts exist.
    Returns dict(ridge_z, top_z, wall_top, wall_hw, wall_hd, notes)."""
    R = dict(RES[lod])
    notes = []
    args = (mats, lod, typ, hw, hd, z_e, pitch, eave, eave_s, up, tp, p, dg, frieze_h, upper)
    if budget:
        steps = list(LADDER[lod])
        while True:
            tmp = genlib.MeshBuilder()
            _roof(tmp, R, *args)
            n = C.tri_count(tmp.bm)
            tmp.bm.free()
            if n <= budget * 1.06 or not steps:
                break
            st = steps.pop(0)
            R.update(st)
            notes.append(','.join(f'{k}={v}' for k, v in st.items()))
    out = _roof(mb, R, *args)
    out['notes'] = notes
    return out


def _roof(mb, R, mats, lod, typ, hw, hd, z_e, pitch, eave, eave_s, up, tp, p, dg, frieze_h, upper):
    tp = tp * R.get('tp_k', 1.0)
    eave_s = eave if eave_s is None else eave_s
    th = 0.13
    if typ == 'pyramid':
        hw = hd = min(hw, hd)
        eave_s = eave
    if typ == 'two_tier':
        ut = upper or 'irimoya'
        rise1 = hd * math.tan(math.radians(pitch * 0.8))
        S1 = kp.RoofShape(hw, hd, z_e, rise1, p=p + 0.25, up=up, style='hip')
        R1 = dict(R, tp=tp, thick=th, rafters=False)
        kp.roof(mb, S1, R1, mats, None, wall=dict(ov=eave, ovs=eave_s, z_beam=z_e - 0.3))
        fx, fy = hw * 0.6, hd * 0.6                    # frieze storey wall half extents, standing on the skirt
        d_f = hd - fy
        z0 = S1.zd(d_f) - 0.12
        eave2 = max(0.45, eave * 0.7)
        hw2, hd2 = fx + eave2, fy + eave2
        z_e2 = max(S1.zd(d_f) + frieze_h, z_e + rise1 + th + 0.15) + th
        _frieze(mb, mats, lod, fx, fy, z0, z_e2 - th - 0.06)
        S2 = kp.RoofShape(hw2, hd2, z_e2, hd2 * math.tan(math.radians(pitch)), p=p, up=up * 0.8, style=ut,
                          dg=None if dg is None else hd2 * dg)
        info = _kp_roof(mb, S2, dict(R, tp=tp, thick=th), mats, lod, dict(ov=eave2, ovs=eave2, z_beam=z_e2 - th - 0.2))
        return dict(ridge_z=info['ridge_z'], top_z=info['ridge_z'] + 0.33, wall_top=S1.zd(eave) - th - 0.12,
                    wall_hw=hw - eave_s, wall_hd=hd - eave)
    style = 'hip' if typ == 'pyramid' else typ
    R = dict(R)
    if typ == 'pyramid' and R['ridge_prof'] == 'full':
        R['ridge_prof'] = 'box'
    rise = hd * math.tan(math.radians(pitch))
    S = kp.RoofShape(hw, hd, z_e, rise, p=p, up=up, style=style, dg=None if dg is None else hd * dg)
    wall_top = S.zd(eave) - th - 0.12
    info = _kp_roof(mb, S, dict(R, tp=tp, thick=th), mats, lod, dict(ov=eave, ovs=eave_s, z_beam=wall_top))
    top = info['ridge_z'] + (0.33 if R['ridge_prof'] == 'full' else 0.2)
    if typ == 'pyramid':
        fz = info['ridge_z'] + (0.18 if R['ridge_prof'] != 'tri' else 0.05)
        sc = min(1.2, 0.55 + hw * 0.1)
        if lod <= 2:
            finial(mb, (0, 0, fz), mats['iron'], lod, scale=sc)
        else:
            mb.box((0, 0, fz + 0.4 * sc), (0.2 * sc, 0.2 * sc, 0.8 * sc), mats['iron'])
        top = fz + 0.8 * sc
    return dict(ridge_z=info['ridge_z'], top_z=top, wall_top=wall_top, wall_hw=hw - eave_s, wall_hd=hd - eave)


def _kp_roof(mb, S, R, mats, lod, wall):
    """kp.roof; at LOD3 the gable board and bargeboard sweeps (about 110 tris on their own) are replaced by one
    flat gable triangle per end, so gable and irimoya LOD3 keep their gable read inside the 80-tri budget"""
    lay = mb._mark_old() if lod == 3 else None
    info = kp.roof(mb, S, R, mats, None, wall=wall)
    if lod == 3 and S.style in ('irimoya', 'gable'):
        dead = [f for f in mb._new_faces(lay) if f.material_index == mats['wood_d']]
        bmesh.ops.delete(mb.bm, geom=dead, context='FACES_ONLY')
        hd = S.hd
        if S.style == 'irimoya':
            xg, d0 = S.hw - S.dg - 0.04, S.dg
            zb = S.z(xg, hd - d0, d0, 'f')
        else:
            xg, d0 = S.hw - 0.02, 0.0
            zb = S.z(xg, hd, 0.0, 'f') - 0.13
        zt = S.z(xg, 0.0, hd, 'f') - 0.02
        for sx in (-1, 1):
            vs = [mb.bm.verts.new((sx * xg, y, z)) for y, z in ((hd - d0, zb), (0.0, zt), (-(hd - d0), zb))]
            f = mb.bm.faces.new(vs if sx > 0 else vs[::-1]); f.material_index = mats['wood_d']
    return info


def _frieze(mb, mats, lod, fx, fy, z0, z1):
    """timber frieze storey between the two tiers: corner posts, a lacquered panel band, a head beam (and at LOD0-1
    a row of short posts dividing the panel into bays)"""
    wood, wood_d = mats['wood'], mats['wood_d']
    panel = mats.get('frieze', wood_d)
    h = z1 - z0
    mb.box((0, 0, z0 + h / 2), (2 * fx, 2 * fy, h), panel)
    if lod >= 3:
        return
    pw = 0.16
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((sx * (fx - pw / 2 + 0.03), sy * (fy - pw / 2 + 0.03), z0 + h / 2), (pw, pw, h), wood)
    bh = min(0.22, h * 0.25)
    mb.box((0, 0, z1 - bh / 2), (2 * fx + 0.08, 2 * fy + 0.08, bh), wood)
    if lod <= 1:
        for sy in (-1, 1):
            n = max(2, int(2 * fx / 0.9))
            for k in range(1, n):
                x = -fx + 2 * fx * k / n
                mb.box((x, sy * (fy + 0.02), z0 + (h - bh) / 2), (0.08, 0.05, h - bh), wood)
        for sx in (-1, 1):
            n = max(2, int(2 * fy / 0.9))
            for k in range(1, n):
                y = -fy + 2 * fy * k / n
                mb.box((sx * (fx + 0.02), y, z0 + (h - bh) / 2), (0.05, 0.08, h - bh), wood)


def pent_into(mb, mats, lod, x0, x1, y_wall, depth, z_top, pitch=22.0, tp=0.26, brackets=None):
    """Mono-pitch tiled pent roof (hisashi) along x from x0 to x1, its top against the wall plane y = y_wall at
    z_top, draining to +y over `depth`.  LOD0-1: kp.lean_to (tile ribs, eave discs, fascia with tile lip, soffit)
    built in a rotated frame (it runs along y, draining to +x) and turned +90 deg about z.  LOD2-3: one tiled sheet,
    a fascia with its tile lip, a soffit and two end boards (10 tris).  Returns the eave height."""
    z_eave = z_top - depth * math.tan(math.radians(pitch))
    bm = mb.bm
    if lod <= 1:
        R = dict(ribs=True, fascia=True, rib_prof=3 if lod == 0 else 2, discs=lod == 0, disc_n=5)
        lay = mb._mark_old()
        kp.lean_to(mb, 1, 0.0, depth, -x1, -x0, z_top, z_eave, tp, R, dict(tile=mats['tile'], wood=mats['wood']), None)
        vs = _new_verts(mb, lay)
        M = Matrix.Translation((0, y_wall, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'Z')
        bmesh.ops.transform(bm, matrix=M, verts=vs)
        return z_eave
    th = 0.13
    yf = y_wall + depth

    def q(pts, mi):
        f = bm.faces.new([bm.verts.new(p) for p in pts]); f.material_index = mi

    q([(x0, y_wall, z_top), (x0, yf, z_eave), (x1, yf, z_eave), (x1, y_wall, z_top)], mats['tile'])
    q([(x0, yf, z_eave), (x0, yf, z_eave - 0.06), (x1, yf, z_eave - 0.06), (x1, yf, z_eave)], mats['tile'])
    q([(x0, yf, z_eave - 0.06), (x0, yf, z_eave - th), (x1, yf, z_eave - th), (x1, yf, z_eave - 0.06)], mats['wood'])
    q([(x0, y_wall, z_top - th), (x1, y_wall, z_top - th), (x1, yf, z_eave - th), (x0, yf, z_eave - th)], mats['wood'])
    if lod == 2:
        for x, flip in ((x0, False), (x1, True)):
            pts = [(x, y_wall, z_top), (x, y_wall, z_top - th), (x, yf, z_eave - th), (x, yf, z_eave)]
            q(pts[::-1] if flip else pts, mats['wood'])
    return z_eave
