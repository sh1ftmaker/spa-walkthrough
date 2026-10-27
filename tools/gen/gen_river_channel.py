"""Underground river bed, banks and inflow slot (B2, 220 m: b2_river b2_kawagiri b2_boat b2_boardwalk
b2_falls_head). A per-reach generator: bed + wet banks along a centreline; the surface and rapids are fx_river,
the bed glow is a shader on this mesh (riverbed_glow), the falls themselves are falls_lip_rock + fx_falls_sheet.

Concepts: lookbook/img/34-plan-b2-river.jpg (0-60 m bar = 270 px -> 4.5 px/m: the river runs east -> west
from the 'UNDERGROUND RIVER FROM B1' slot at J2 to the Thunder Curtain at A3-A4; water 8-20 m wide (14-18 m
at the boat landing, 8-10 m past the kitchen and at the bends), black boulders in the stream and along both
banks, white water at the narrows, the falls head ~12 m wide), lookbook/img/29-river-section.jpg (B2: the
river runs over a rocky sloping bed and leaves over a broad lip into the B3 falls), lookbook/img/06-kawagiri-
restaurant.jpg (diners ~1.7 m: banks 1.2-2.2 m of wet black faceted rock above the water, boulders 0.5-1.5 m
breaking the surface, white water round them, glowing teal bed).

Targets (default reach module, 10 m long, the row budget is per 10 m: 3000/1200/360/80):
  water width 8-20 m (narrows reach 11-13 -> 5-6.5 m at the throat; slot reach 10-12; lip reach 12.5-14
  with the lip itself lip_w = 12 m), bed 0.9-1.2 m under the water at the thalweg, rocky (noise 0.12 m),
  banks 1.3-2.2 m above the water over a 2.0-2.4 m run (toe rocks at the waterline), slope 1-3 %
  (narrows add a 0.35 m rapid drop at the throat), 6-14 bed boulders 0.35-1.6 m (2/3 break the surface in
  the narrows), 8-12 bank rocks 0.4-0.9 m.
  slot (J2 inflow): a cut 1.2-1.6 m wide, 2.0-2.6 m deep into a 3.6-4.0 m cliff bank, sill 0.3 m above the
  water; lip (Thunder Curtain head): the bed shallows to 0.25 m over the last 3 m, a polished rounded crest,
  then the face drops 1.6 m (falls_lip_rock 'lip' carries on below).
Parameters: path [(x, y, z_bed_ref, width)] nodes (default: a 10 m module along +Y), length, width, slope,
  narrows [(s, factor, length)], rock_density 0.5-1.5, slot (s, side, w, depth) or None, lip_w (12), style.
Styles (C.cycle): narrows (rapids, white-water throat), slot (J2 inflow slot in a cliff bank), lip (falls
  head). Seeds also change widths, meander, bank heights and asymmetry, boulder layout / sizes, slot side.
Materials (slots by part): m_bed basalt_wet 0.98 polish -0.05 (bed, lip crest), m_bank basalt_wet 0.85
  (banks up to 1 m over the water, toe and bed boulders), m_cliff cave_rock (bank tops, slot cliff), m_glow
  caustics_decal (riverbed_glow: an emissive caustics ribbon 2 cm over the thalweg; vertex attr '_glow').
  water_river is runtime (fx_river), not built.
Custom props: kz_centerline (JSON [x, y, z_water, half_width] per station), kz_water_path, kz_narrows,
  kz_rapids, kz_slot, kz_falls (lip polyline, width, drop, dir), kz_lights (none: lightmap), kz_anim
  (shader riverbed_glow), kz_tris_per_10m.
LODs from one layout: stations 0.3 / 0.7 / 1.7 / ends + mid + features m; profile points 21 / 13 / 9 / 5; LOD0-1
  keep every rock, LOD2 the 5 largest, LOD3 none (the profile still carries slot notch and lip).
Pivot: bbox centre x/y, z = 0 at the lowest point. Front +Y = downstream.
"""
import math

from mathutils import Vector, noise

import genlib
import kzgeo_common as C

ASSET = 'river_channel'
FEATURES = ['rocky sloping bed with white-water narrows and boulders', 'wet black banks',
            'the J2 inflow slot cut in the rock', 'the Thunder Curtain lip']
STYLES = ['narrows', 'slot', 'lip']
PROXY_SHEET = dict(w=19.0, d=10.5, h=5.2)    # proposed proxy for the default 10 m reach module


class _Path:
    def __init__(self, nodes):
        self.P = [Vector((n[0], n[1], 0.0)) for n in nodes]
        self.Z = [n[2] for n in nodes]
        self.Wd = [n[3] for n in nodes]
        self.S = [0.0]
        for a, b in zip(self.P[:-1], self.P[1:]):
            self.S.append(self.S[-1] + (b - a).length)
        self.L = self.S[-1]

    def at(self, s):
        s = max(0.0, min(self.L, s))
        for i in range(len(self.S) - 1):
            if s <= self.S[i + 1] + 1e-9:
                f = (s - self.S[i]) / max(1e-9, self.S[i + 1] - self.S[i])
                p = self.P[i].lerp(self.P[i + 1], f)
                t = (self.P[i + 1] - self.P[i]).normalized()
                z = self.Z[i] + (self.Z[i + 1] - self.Z[i]) * f
                w = self.Wd[i] + (self.Wd[i + 1] - self.Wd[i]) * f
                return p, t, z, w
        return self.P[-1], (self.P[-1] - self.P[-2]).normalized(), self.Z[-1], self.Wd[-1]


def _layout(seed, path, length, width, slope, narrows, rock_density, slot, lip_w, style):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'reach')
    L = dict(style=style)
    Lm = length or 10.0
    W0 = width or {'narrows': g.uniform(11, 13), 'slot': g.uniform(10, 12), 'lip': g.uniform(12.5, 14)}[style]
    sl = slope if slope is not None else {'narrows': g.uniform(0.02, 0.03), 'slot': g.uniform(0.01, 0.015), 'lip': 0.01}[style]
    if path is None:
        amp = g.uniform(0.15, 0.35) * g.choice([-1, 1]) * (0.3 if style == 'lip' else 1.0)
        n = 6
        path = [(amp * (1 - math.cos(2 * math.pi * i / n)) / 2, Lm * i / n, -sl * Lm * i / n, W0) for i in range(n + 1)]
        if style == 'lip':
            lw = lip_w or 12.0
            path = [(x, y, z, W0 + (lw - W0) * max(0.0, (y - Lm * 0.5) / (Lm * 0.5))) for x, y, z, _ in path]
    L['path'] = _Path(path)
    PL = L['path'].L
    if narrows is None:
        narrows = [(PL * g.uniform(0.45, 0.6), g.uniform(0.45, 0.55), g.uniform(3.5, 4.5))] if style == 'narrows' else []
    L['narrows'] = narrows
    L['dep'] = g.uniform(0.9, 1.2)
    gb = C.rng(seed, 'banks')
    L['bank'] = (gb.uniform(1.3, 2.2), gb.uniform(1.3, 2.2))
    L['run'] = gb.uniform(2.0, 2.4)
    L['noff'] = Vector((gb.uniform(0, 90), gb.uniform(0, 90), gb.uniform(0, 90)))
    if slot is None and style == 'slot':
        gs = C.rng(seed, 'slot')
        slot = (PL * gs.uniform(0.4, 0.6), gs.choice([-1, 1]), gs.uniform(1.2, 1.6), gs.uniform(2.0, 2.6))
    L['slot'] = slot
    L['cliff'] = C.rng(seed, 'slot').uniform(3.6, 4.0)
    L['lip'] = style == 'lip'
    L['lip_w'] = lip_w or 12.0
    # rocks
    gr = C.rng(seed, 'rocks')
    dens = rock_density if rock_density is not None else 1.0
    nb = int(round((12 if style == 'narrows' else 7) * dens * PL / 10))
    rocks = []
    for i in range(nb):
        if narrows and gr.random() < 0.75:
            s0, f, ln = narrows[0]
            s = max(1.0, min(PL - 1.0, s0 + gr.uniform(-0.6, 0.6) * ln))
            sz = gr.uniform(0.6, 1.6)
        else:
            s = gr.uniform(0.5, PL - (3.5 if L['lip'] else 0.5))
            sz = gr.uniform(0.35, 1.0)
        rocks.append(dict(kind='bed', s=s, u=gr.uniform(-0.8, 0.8), sz=sz, sq=(gr.uniform(0.75, 1.0), gr.uniform(0.55, 0.85)),
                          rot=gr.uniform(0, 3.1), rs=gr.randint(0, 10 ** 6)))
    nk = int(round(10 * dens * PL / 10))
    for i in range(nk):
        side = (-1, 1)[i % 2]
        s = max(0.9, min(PL - 0.9, (i // 2 + gr.uniform(0.1, 0.9)) * PL / max(1, nk // 2)))
        if L['slot'] and side == L['slot'][1] and abs(s - L['slot'][0]) < L['slot'][2]:
            continue
        if L['lip'] and s > PL - 2.0:
            continue
        rocks.append(dict(kind='bank', s=s, side=side, sz=gr.uniform(0.45, 0.9), rot=gr.uniform(0, 3.1),
                          rs=gr.randint(0, 10 ** 6)))
    rocks.sort(key=lambda d: -d['sz'])
    L['rocks'] = rocks
    return L


def _hw(L, s, w):
    hw = w / 2
    for s0, f, ln in L['narrows']:
        hw *= 1 - (1 - f) * math.exp(-((s - s0) / (ln * 0.45)) ** 2)
    return hw


def _zw(L, s, zref):
    """water level at s: the path z (bed reference, sloped) + a rapid drop through each narrows"""
    z = zref
    for s0, f, ln in L['narrows']:
        z -= 0.35 * (0.5 + 0.5 * math.tanh((s - s0) / (ln * 0.2)))
    return z


def _stations(L, lod):
    PL = L['path'].L
    step = C.lod_pick(lod, 0.3, 0.7, 1.7, PL / 2)
    ss = [PL * i / max(1, int(round(PL / step))) for i in range(int(round(PL / step)) + 1)]
    extra = []
    if L['slot']:
        s0, side, w, dep = L['slot']
        e = [s0 - w / 2 - 0.12, s0 - w / 2, s0 + w / 2, s0 + w / 2 + 0.12]
        extra += e if lod < 3 else [s0 - w / 2, s0 + w / 2]
    if L['lip']:
        extra += [PL - 3.0, PL - 0.45, PL - 0.18] if lod < 3 else [PL - 0.45]
    if lod == 3 and L['narrows']:
        extra += [L['narrows'][0][0]]
    ss = sorted(set(round(s, 4) for s in ss + extra if 0 <= s <= PL))
    out = []
    for s in ss:
        if not out or s - out[-1] > 0.05:
            out.append(s)
    if out[-1] < PL - 1e-3:
        out.append(PL)
    return out


def build(lod, seed, path=None, length=None, width=None, slope=None, narrows=None, rock_density=None, slot=None,
          lip_w=None, style=None):
    L = _layout(seed, path, length, width, slope, narrows, rock_density, slot, lip_w, style)
    mb = genlib.MeshBuilder()
    m_bed = mb.slot('basalt_wet', wetness=0.98, roughness_offset=-0.05)
    m_bank = mb.slot('basalt_wet', wetness=0.85)
    m_cliff = mb.slot('cave_rock')
    m_glow = mb.slot('caustics_decal')
    bm = mb.bm
    glow = bm.verts.layers.float.new('_glow')
    P = L['path']
    PL = P.L
    dep = L['dep']
    run = L['run']
    off = L['noff']
    ss = _stations(L, lod)
    # lateral profile parameters u in [-1, 1] (left bank top -> right bank top); bed = |u| < 0.5
    us = C.lod_pick(lod,
                    [-1, -0.9, -0.8, -0.7, -0.6, -0.5, -0.4, -0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1],
                    [-1, -0.85, -0.7, -0.6, -0.5, -0.3, 0, 0.3, 0.5, 0.6, 0.7, 0.85, 1],
                    [-1, -0.8, -0.6, -0.5, 0, 0.5, 0.6, 0.8, 1],
                    [-1, -0.55, 0, 0.55, 1])
    amp = C.lod_pick(lod, 1.0, 0.8, 0.4, 0.0)
    rows, rowmeta, cl = [], [], []
    for s in ss:
        p, t, zref, w = P.at(s)
        n = Vector((t.y, -t.x, 0.0))          # +x for flow along +Y (right bank when looking downstream is -x)
        hw = _hw(L, s, w)
        zw = _zw(L, s, zref)
        lipf = 0.0
        d_ = dep
        bh = list(L['bank'])
        if L['lip']:
            lipf = max(0.0, min(1.0, (s - (PL - 3.0)) / 2.55))
            d_ = dep + (0.25 - dep) * lipf
            bh = [b + (0.6 - b) * lipf for b in bh]
        row, meta = [], []
        for u in us:
            side = -1 if u < 0 else 1
            a = abs(u)
            B = bh[0 if side < 0 else 1]
            if L['slot'] and side == L['slot'][1]:
                B = L['cliff']
            if a <= 0.5:              # bed: parabolic thalweg
                d = u / 0.5 * hw * 0.92
                z = zw - d_ * (1 - 0.75 * (d / hw) ** 2)
                kind = 'bed'
            elif a <= 0.6:            # waterline toe
                d = side * hw * (0.92 + 0.08 * (a - 0.5) / 0.1)
                z = zw - d_ * 0.25 * (0.6 - a) / 0.1 - 0.05
                kind = 'toe'
            else:                     # bank face -> shoulder -> top
                f = (a - 0.6) / 0.4
                d = side * (hw + run * (0.15 + 0.85 * f ** 1.4))
                z = zw + B * (1 - (1 - f) ** 1.8) - 0.05
                kind = 'bank'
            nz = noise.noise(Vector((s * 0.55, d * 0.55, 0.0)) + off) + 0.5 * noise.noise(Vector((s * 1.4, d * 1.4, 3.0)) + off)
            z += amp * (0.12 if kind == 'bed' else 0.2) * nz
            dd = d + amp * (0.18 * nz if kind == 'bank' else 0.0)
            # slot: a notch cut back into the cliff bank, sill 0.3 m over the water
            if L['slot'] and side == L['slot'][1] and kind == 'bank':
                s0, sd, sw, sdep = L['slot']
                if abs(s - s0) <= sw / 2 + 1e-3:
                    if f < 0.45:
                        dd = side * (hw + 0.25 + sdep * f / 0.45)
                        z = zw + 0.3 + 0.1 * f
                    else:
                        dd = side * (hw + 0.25 + sdep + 0.3 * (f - 0.45))
                        z = zw + 0.4 + (B - 0.4) * (f - 0.45) / 0.55
            # lip: the polished crest, then the face drops away
            if L['lip'] and s > PL - 0.3:
                k = (s - (PL - 0.3)) / 0.3
                z = min(z, zw - 0.25) - 1.35 * k ** 1.5 - 0.1 * k
            v = p + n * dd
            vv = bm.verts.new((v.x, v.y, z))
            vv[glow] = max(0.0, 1 - a / 0.45) if kind == 'bed' else 0.0
            row.append(vv)
            meta.append((kind, z - zw))
        rows.append(row)
        rowmeta.append(meta)
        cl.append([round(p.x, 3), round(p.y, 3), round(zw, 3), round(hw, 3)])
    nu = len(us)
    for i in range(len(rows) - 1):
        for j in range(nu - 1):
            f = bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
            hz = (rowmeta[i][j][1] + rowmeta[i][j + 1][1] + rowmeta[i + 1][j][1] + rowmeta[i + 1][j + 1][1]) / 4
            kinds = {rowmeta[i][j][0], rowmeta[i][j + 1][0]}
            f.material_index = m_cliff if hz > 1.0 else (m_bed if kinds <= {'bed', 'toe'} and hz < 0.0 else m_bank)

    # ------------------------------------------------ riverbed glow ribbon (caustics decal over the thalweg)
    if lod < 2:
        gu = C.lod_pick(lod, [-0.6, -0.3, 0.0, 0.3, 0.6], [-0.5, 0.0, 0.5])
        grow = []
        for s in ss:
            if L['lip'] and s > PL - 0.5:
                break
            p, t, zref, w = P.at(s)
            n = Vector((t.y, -t.x, 0.0))
            hw = _hw(L, s, w); zw = _zw(L, s, zref)
            d_ = dep + ((0.25 - dep) * max(0.0, min(1.0, (s - (PL - 3.0)) / 2.55)) if L['lip'] else 0.0)
            r_ = []
            for g_ in gu:
                d = g_ * hw * 0.5
                z = zw - d_ * (1 - 0.75 * (d / hw) ** 2)
                nz = noise.noise(Vector((s * 0.55, d * 0.55, 0.0)) + off) + 0.5 * noise.noise(Vector((s * 1.4, d * 1.4, 3.0)) + off)
                z += amp * 0.12 * nz + 0.03
                v = p + n * d
                vv = bm.verts.new((v.x, v.y, z)); vv[glow] = 1 - abs(g_)
                r_.append(vv)
            grow.append(r_)
        for A, Bq in zip(grow[:-1], grow[1:]):
            for j in range(len(gu) - 1):
                f = bm.faces.new((A[j], A[j + 1], Bq[j + 1], Bq[j])); f.material_index = m_glow

    # ------------------------------------------------ boulders: bed breakers and waterline bank rocks
    keep = C.lod_pick(lod, len(L['rocks']), len(L['rocks']), 5, 0)
    for rk in L['rocks'][:keep]:
        p, t, zref, w = P.at(rk['s'])
        n = Vector((t.y, -t.x, 0.0))
        hw = _hw(L, rk['s'], w); zw = _zw(L, rk['s'], zref)
        rr = genlib.rng(rk['rs'], 'rock')
        sz = rk['sz']
        if rk['kind'] == 'bed':
            d = rk['u'] * hw * 0.85
            zb = zw - L['dep'] * (1 - 0.75 * (d / hw) ** 2)
            c = p + n * d
            C.hull_rock(mb, (c.x, c.y, zb + sz * rk['sq'][1] * 0.45), (sz, sz * rk['sq'][0], sz * rk['sq'][1]), m_bank, rr,
                        npts=C.lod_pick(lod, 14, 9, 6), rot=rk['rot'], ground=zb - 0.05)
        else:
            d = rk['side'] * (hw + sz * 0.35)
            c = p + n * d
            M = C.frame((c.x, c.y, 0.0), (t.x, t.y, 0.0))
            if lod == 0:
                C.crag_rock(mb, M, sz, sz * 0.8, zw - 0.45, zw + sz * 0.75, m_bank, rr, nside=7, bands=3)
            else:
                C.hull_rock(mb, (c.x, c.y, zw + sz * 0.1), (sz, sz * 0.8, sz * 0.65), m_bank, rr, npts=C.lod_pick(lod, 14, 8, 6),
                            rot=rk['rot'], ground=zw - 0.45)

    # ------------------------------------------------ object + data
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=45)
    sh = lambda q: [round(q[0] + dx, 3), round(q[1] + dy, 3), round(q[2] + dz, 3)]
    cl = [[c[0] + dx, c[1] + dy, c[2] + dz, c[3]] for c in cl]
    if L['lip']:
        cl = [c for s, c in zip(ss, cl) if s <= PL - 0.3]
    C.set_json_props(o, kz_centerline=[[round(v, 3) for v in c] for c in cl], kz_water_path=[c[:3] for c in cl[::max(1, len(cl) // 12)]],
                     kz_style=L['style'], kz_anim=dict(type='shader', what='riverbed_glow', slot='caustics_decal', attr='_glow'),
                     kz_tris_per_10m=round(genlib.tris(o) * 10.0 / PL), kz_lights=[])
    o['kz_water_level'] = cl[0][2]
    if L['narrows']:
        C.set_json_props(o, kz_narrows=[[round(s0, 2), round(f, 3), round(ln, 2)] for s0, f, ln in L['narrows']],
                         kz_rapids=[[round(s0, 2), 0.35] for s0, f, ln in L['narrows']])
    if L['slot']:
        s0, side, sw, sdep = L['slot']
        p, t, zref, w = P.at(s0)
        n = Vector((t.y, -t.x, 0.0)) * side
        hw = _hw(L, s0, w); zw = _zw(L, s0, zref)
        mouth = p + n * (hw + 0.25)
        C.set_json_props(o, kz_slot=dict(pos=sh((mouth.x, mouth.y, zw + 0.3)), dir=[round(-n.x, 3), round(-n.y, 3), 0.0],
                                         w=round(sw, 2), depth=round(sdep, 2), h=round(L['cliff'] - 0.3, 2),
                                         note='J2 inflow: fx_river side inflow / falls_lip_rock slot host'))
    if L['lip']:
        p, t, zref, w = P.at(PL - 0.3)
        n = Vector((t.y, -t.x, 0.0))
        zw = _zw(L, PL - 0.3, zref)
        half = L['lip_w'] / 2
        lip = [sh(p + n * (half * k / 4)) for k in range(-4, 5)]
        for q in lip:
            q[2] = round(zw - 0.25 + dz + 0.02, 3)
        C.set_json_props(o, kz_falls=dict(lip=lip, width=L['lip_w'], drop=50.0, dir=[round(t.x, 3), round(t.y, 3), 0.0],
                                          overhang=0.3, note='Thunder Curtain head: falls_lip_rock lip style continues below'))
    return o
