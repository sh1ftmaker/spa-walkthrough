"""Compressed timber passage and porch frames (timber_passage; also covers genkan_porch as the suite variant).

Targets (no scale sheet shows the passage; measured from lookbook and the ground sheet):
  sheet-ref-ground.png panel 02 (treatment hall): the timber portal at the end of the walk reads ~1.3 x the
  1.65 m guests -> clear h ~2.6-2.8 m; posts ~0.18 m square (1/9 of the clear width), lintel ~0.2 m deep,
  low eaves projecting ~0.3 m. Lookbook 04 / 32: dark hinoki frames at close rhythm (1.0-1.5 m), the roof
  barely above the lintels: a tunnel of timber before the reveal.
  Built: clear w 3.6 (range 3-4.4), clear h 2.6 (2.6-3.2), posts 0.18 sq, kamoi lintel 0.20 x 0.16,
  nuki tie 0.12 x 0.05 at 0.42 m below the lintel, through-tenoned 0.12 m past each post with a wedge;
  keta plates 0.18 x 0.16 on the post tops, rafters 0.06 x 0.09 at ~0.45 m, eave overhang 0.28 m,
  gable rise 0.18 m (low), 35 mm roof boards, lacquer_dark fascia and ridge cap.
  Default bbox (porch, 6 m): 4.58 x 6.0 x 3.28 m (proxy 4.4 x 6 x 3.2 within the +5 % check tolerance;
  clear w 4.4 or clear h 3.2 exceed it by design: those are range maxima).
  Lintel 0.18, keta 0.16, rise 0.14 were trimmed from the first targets to stay inside the proxy height.

Variants (seed 1, 2, 3 cycle; pass variant=):
  porch    L 6.0, frame spacing 1.5, gable roof, low koshi lattice infill (0.9 m) on both sides
  gallery  gallery stair cover: L 6.0, frames at 1.0 m (closest rhythm), shed roof, no infill, slope param
  genkan   suite genkan: L 3.0, clear w 3.0, gable roof, full-height tategoshi slat screens both sides
Parameters build(lod, seed, **p)
  variant, length 2-12, clear_w 3-4.4, clear_h 2.6-3.2, spacing 1-2, roof (True/False), infill
  ('none' | 'koshi' | 'screen'), slope (rise in m over the length, for a stair cover; default 0)
Seeds change shape: the variant; within a variant +-8 % spacing, +-0.1 m clear h, rafter pitch, nuki height,
slat pitch. Each part has its own rng stream; all draws before the LOD branches.
LOD0 everything with chamfers; LOD1 same parts and counts, no chamfers, wedges dropped; LOD2 frames +
plates + roof slab + infill as one panel per bay (rafters dropped); LOD3 every frame as 3-sided posts +
lintel, roof as one slab per pitch, infill panels.
Materials: hinoki stained (structure, near-black), hinoki dark_timber (infill slats), lacquer_dark (fascia, ridge,
post shoes). Animation none. Lighting lightmap (UV1 from genlib.finish). Front is +Y (passage axis Y).
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_railing as R
import kzgeo_bridge_arched as KB

ASSET = 'timber_passage'
FEATURES = ['low dark hinoki portal frames at close rhythm', 'low eaves roof', 'tunnel of timber']
VARIANTS = {'porch': dict(length=6.0, clear_w=3.6, clear_h=2.6, spacing=1.5, roof='gable', infill='koshi'),
            'gallery': dict(length=6.0, clear_w=3.6, clear_h=2.65, spacing=1.0, roof='shed', infill='none'),
            'genkan': dict(length=3.0, clear_w=3.0, clear_h=2.6, spacing=1.0, roof='gable', infill='screen')}


def build(lod, seed, variant=None, length=None, clear_w=None, clear_h=None, spacing=None, roof=None,
          infill=None, slope=0.0):
    variant = variant or C.cycle(seed, ['porch', 'gallery', 'genkan'])
    V = VARIANTS[variant]
    g = C.rng(seed, 'layout')
    L = length if length is not None else V['length']
    W = clear_w if clear_w is not None else V['clear_w']
    Hc = clear_h if clear_h is not None else V['clear_h'] + g.uniform(0.0, 0.05)
    sp = spacing if spacing is not None else V['spacing'] * g.uniform(0.92, 1.08)
    roof_kind = (V['roof'] if roof is None or roof is True else ('none' if roof is False else roof))
    infill = infill if infill is not None else V['infill']
    raf_pitch = g.uniform(0.40, 0.50)
    nuki_drop = g.uniform(0.38, 0.48)
    slat_pitch = g.uniform(0.10, 0.13)

    PW, LIN_H, LIN_D, KETA, OV, RISE = 0.18, 0.18, 0.16, 0.16, 0.28, 0.14
    END = 0.24                                            # end frame centre inset from the piece ends
    span_y = L - 2 * END
    nb = max(1, int(round(span_y / sp)))
    ys = [-span_y / 2 + span_y * k / nb for k in range(nb + 1)]
    zf = lambda y: slope * (y + L / 2) / L               # floor height under a frame (stair cover)
    xp = W / 2 + PW / 2                                   # post centre x
    ch = 0.012 if lod == 0 else 0.0

    mb = genlib.MeshBuilder()
    wood = mb.slot('hinoki', variant='stained')
    slat = mb.slot('hinoki', variant='dark_timber')
    lac = mb.slot('lacquer_dark')

    def post(x, y, z0, z1, w=PW, d=PW, mi=wood):
        if lod == 3:
            R.vprism(mb, (x, y), 0.0, w, d, z0, z1, mi, sides=3, cap_top=False)
        else:
            R.vprism(mb, (x, y), 0.0, w, d, z0, z1, mi, ch=ch, cap_top=(lod <= 1))

    def beam(c, size, mi=wood, b=0.01, rot=(0, 0, 0)):
        if lod >= 2:
            mb.box(c, size, mi, rot=rot)
        else:
            C.board(mb, c, size, mi, bevel=b if lod == 0 else 0.0, rot=rot)

    zt = Hc + LIN_H                                       # post top = lintel top
    # ---------------------------------------------------------------- frames
    for y in ys:
        z0 = zf(y)
        for sx in (-1, 1):
            post(sx * xp, y, z0, z0 + zt)
            if lod <= 1:                                 # lacquered post shoe
                R.band(mb, (sx * xp, y), 0.0, PW, PW, z0 + 0.06, 0.12, lac, t=0.008)
        if lod == 3:
            continue
        beam((0, y, z0 + Hc + LIN_H / 2), (2 * xp + PW, LIN_D, LIN_H))               # kamoi lintel
        if lod <= 2:
            nl = 2 * xp + PW + 0.24
            beam((0, y, z0 + Hc - nuki_drop), (nl, 0.05, 0.12), b=0.006)            # nuki tie, tenons out
            if lod == 0:
                for sx in (-1, 1):                                                  # wedges (kusabi)
                    beam((sx * (xp + PW / 2 + 0.03), y, z0 + Hc - nuki_drop + 0.075), (0.035, 0.07, 0.05), b=0.004)
    # ---------------------------------------------------------------- keta plates along both sides
    yk0, yk1 = ys[0] - 0.2, ys[-1] + 0.2
    zk = zt
    if lod <= 2:
        for sx in (-1, 1):
            if slope:
                R.rail(mb, R.Path([(sx * xp, yk0, zf(ys[0]) + zk), (sx * xp, yk1, zf(ys[-1]) + zk)]), 0, 99,
                       KETA / 2, R.rect_prof(0.16, KETA), wood, None)
            else:
                beam((sx * xp, 0, zk + KETA / 2), (0.16, yk1 - yk0, KETA))
    ztop = zk + KETA                                     # rafter seat
    # ---------------------------------------------------------------- roof
    X = xp + PW / 2 + OV                                  # eave line
    if roof_kind != 'none':
        if roof_kind == 'gable':
            pitches = [(-X, 0.0, ztop, ztop + RISE), (X, 0.0, ztop, ztop + RISE)]   # (x eave, x ridge, z eave, z ridge)
        else:
            pitches = [(-X, X, ztop + RISE, ztop)]                                    # shed: high side at -X
        nr = max(2, int(round((yk1 - yk0) / raf_pitch)))
        for xe, xr, ze, zr in pitches:
            run, rise = xr - xe, zr - ze
            slen = math.hypot(run, rise)
            ux, uz = run / slen, rise / slen                                          # eave -> ridge
            nx, nz = (-uz, ux) if ux > 0 else (uz, -ux)                               # upward normal
            ang = math.atan2(uz, ux)
            cx, cz = (xe + xr) / 2, (ze + zr) / 2
            if lod <= 1:                                                              # rafters (taruki)
                for k in range(nr + 1):
                    y = yk0 + (yk1 - yk0) * k / nr
                    beam((cx + 0.045 * nx, y, cz + 0.045 * nz + zf(y)), (slen + 0.04, 0.06, 0.09), b=0.0, rot=(0, -ang, 0))
            # roof boards on the rafters, one slab per pitch, swept along the length (profile x = world +X)
            off = 0.09 + 0.0175 if lod <= 1 else 0.03
            bx, bz = cx + off * nx, cz + off * nz
            hw, ht = slen / 2 + 0.03, 0.0175
            prof = [(bx - cx + sa * hw * ux + sb * ht * nx, bz - cz + sa * hw * uz + sb * ht * nz)
                    for sa, sb in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
            pts = [(cx, yk0 - 0.04, cz + zf(yk0)), (cx, yk1 + 0.04, cz + zf(yk1))]
            C.sweep(mb, pts, prof, wood, caps=True)
            if lod <= 2:                                                              # lacquer fascia at the eave
                ex = xe - math.copysign(0.0, xe)
                R.rail(mb, R.Path([(ex, yk0 - 0.04, ze + zf(yk0)), (ex, yk1 + 0.04, ze + zf(yk1))]), 0, 99,
                       0.07, R.rect_prof(0.035, 0.14), lac, None)
        if roof_kind == 'gable' and lod <= 2:
            R.rail(mb, R.Path([(0, yk0 - 0.04, ztop + RISE + zf(yk0)), (0, yk1 + 0.04, ztop + RISE + zf(yk1))]), 0, 99,
                   0.14, R.rect_prof(0.16, 0.08, 0.02 if lod == 0 else 0.0), lac, None)  # ridge cap
            if lod <= 1:
                for y in (ys[0], ys[-1]):                                             # ridge post (tsuka) on end frames
                    post(0.0, y, zf(y) + zt, zf(y) + ztop + RISE + 0.05, 0.12, 0.12)
    # ---------------------------------------------------------------- side infill
    rs = C.rng(seed, 'infill')
    if infill != 'none':
        top = 0.9 if infill == 'koshi' else Hc - nuki_drop - 0.06
        for sx in (-1, 1):
            if lod == 3:
                mb.box((sx * xp, 0, zf(0) + top / 2 + 0.03), (0.05, ys[-1] - ys[0], top - 0.06), slat)
                continue
            for a, b in zip(ys[:-1], ys[1:]):
                z0 = zf((a + b) / 2)
                ya, yb = a + PW / 2, b - PW / 2
                span = yb - ya
                if lod >= 2:
                    mb.box((sx * xp, (ya + yb) / 2, z0 + top / 2 + 0.03), (0.05, span, top - 0.06), slat)
                    continue
                beam((sx * xp, (ya + yb) / 2, z0 + 0.06), (0.10, span, 0.12), b=0.006)            # sill (dodai)
                beam((sx * xp, (ya + yb) / 2, z0 + top), (0.08, span, 0.06), b=0.006)            # head rail
                if infill == 'screen':
                    beam((sx * xp, (ya + yb) / 2, z0 + 0.42), (0.03, span, 0.5), mi=slat, b=0.004)  # koshi-ita board
                    z_s0 = 0.67
                else:
                    z_s0 = 0.12
                n = max(2, int(round(span / slat_pitch)))
                for k in range(1, n):
                    y = ya + span * k / n
                    R.vprism(mb, (sx * xp, y), 0.0, 0.035, 0.045, z0 + z_s0, z0 + top - 0.03, slat, cap_top=False)
                if infill == 'koshi' and lod == 0:
                    beam((sx * xp, (ya + yb) / 2, z0 + 0.5), (0.05, span, 0.035), mi=slat, b=0.004)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    if lod <= 1:
        KB.uv_grain(o, [wood, slat])
    C.set_json_props(o, kz_params=dict(variant=variant, length=L, clear_w=W, clear_h=round(Hc, 3), spacing=round(sp, 3),
                                       frames=len(ys), roof=roof_kind, infill=infill, slope=slope),
                     kz_clear=dict(w=W, h=round(Hc, 3)))
    return o
