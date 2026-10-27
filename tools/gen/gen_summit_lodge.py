"""Summit lodge with lava window (s_pool, Caldera Crown): timber lodge on the crater rim (owner addition, concept 11).

Identifying features kept at every LOD: timber lodge with a glowing shoji ground floor behind a veranda, deep tiled
eaves, and a tall glass wall upstairs showing lava inside the rock.

Targets (measured / derived):
  * lookbook 11 (caldera crown, crop .scratch/op24/c_lodge11.png): two-storey hinoki lodge at the pool edge: ground
    floor a run of lit shoji bays (panel ~0.9 x 2.2 m, kumiko grid 3-4 x 6-7) behind an engawa veranda with a
    koran railing and floor lanterns; a tiled pent roof (hisashi) with deep eaves over the veranda on slim veranda
    posts; above it a tall glass wall (about 2.6-3 m, dark mullions every ~1.5 m) through which the molten rock face
    glows orange; heavy dark eaves above; people (1.7 m) give storey heights of ~2.6-2.8 m.
  * lookbook 30 (summit plan): the lodge sits on the rim of the Caldera Crown infinity pool.
  * Row: w 10-20 m, d 6-10 m, storeys 1-2, lava window w/h, veranda depth, roof via roof_tiled; dims 16 x 8 x 8 m;
    budget 12000/4800/1440/200.  Proxy 16 x 8 x 8 m.  The 8 m height cap forces ~22-26 deg roofs for two storeys
    (ground 2.5-2.7 m, glass storey 2.6-2.9 m).

Construction (one mesh): stone-less timber plinth skirt (lacquer_dark) to the floor at 0.45 m, closed core walls
(hinoki dark_timber boards), ground floor of shoji bays on the front and sides (washi_backlit paper, light hinoki
frames, kumiko at LOD0, koshi kick board), corner and bay posts, floor band beam, engawa veranda (planks, edge beam,
railing with giboshi newels, 3-riser front stair, andon lanterns on the stair newels and corners), pent roof over
the veranda on veranda posts (2 storeys) or the main roof's deep front eave on veranda posts (1 storey), upper
storey: a tall lava_glass wall in bronze mullions (sill, head, end posts) set in front of a 1.1 m deep recess
whose back is a relief of molten lava rock (lava), dark lacquer recess cheeks, timber wall panels either side;
main roof from kzgeo_roof_tiled (irimoya / hip) shifted over the walls; a ceiling slab closes the roof underside.

Parameters (defaults inside the proxy):
  w 10-20 m (eave to eave, default 15.5-15.9)   d 6-10 m (default 7.8-7.95)   h (default 7.85-7.95)
  storeys 1 | 2 (default: seed 1 -> 2, 2 -> 2, 3 -> 1)
  lava_w  glass wall width, m (default 0.55-0.7 of the front wall)      lava_h glass height (default: the storey)
  veranda 1.2-1.7 m (default seeded)      roof 'irimoya' | 'hip' (default: 1 irimoya, 2 hip, 3 irimoya)
Seeds change: storeys, roof type, bay count / rhythm, glass width and mullion spacing, veranda depth, which
ground bay is a slid-open entrance, side shoji count, lantern positions, pitch.

Materials: hinoki dark_timber (posts, beams, core walls), hinoki natural (shoji frames, kumiko), hinoki wet_oiled
(veranda deck, stair), hinoki stained (railing), lacquer_dark (plinth skirt, recess cheeks, ceiling), washi_backlit
(shoji paper, emissive 0.5), lava_glass (glass wall panes; `glass='clear'` swaps in glass_clear, `glow` sets its
emissive_level, default 0 as on lava_window), bronze smooth (mullions, sill, head), lava (emissive 1.0, scale 2.5:
crusted bosses of the rock face in the 1.1 m recess behind the glass) + lava_flow (emissive 1.2, scale 3: the hollows
between them; LOD3 puts lava_flow on the glass plane itself), lantern_andon (veranda lanterns), iron (lantern
frames), kawara (roofs).
Material note: the recess relief is this asset's stand-in for lava_backdrop (not built yet). With the current
library lava / lava_flow are mostly dark crust with sparse veins, so the glass wall reads dark, not the molten orange
of concept 11; the canonical overrides the relief with a render-only molten shader (as the lava_window canonical did)
and the report asks for a brighter lava_backdrop / lava_flow.
Lighting: lightmap + emissive.  obj['kz_lights']: one area light behind the glass (1600 K), one area light per lit
shoji wall (2700 K), one point per lantern.  Animation: shader only: obj['kz_anim'] = {type: 'shader', slots:
lava_flow (flow), lava (glow pulse), washi_backlit (flicker)}.
"""
import math

import bmesh
from mathutils import Vector, noise

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_common as C
import kzgeo_roof_tiled as KR

ASSET = 'summit_lodge'
FEATURES = ['timber lodge with glowing shoji ground floor', 'veranda under deep tiled eaves',
            'tall glass wall upstairs showing lava inside the rock']


def params(seed, w=None, d=None, h=None, storeys=None, lava_w=None, lava_h=None, veranda=None, roof=None,
           glass=None, glow=None):
    p = genlib.proxy(ASSET)
    g = C.rng(seed, 'lodge')
    P = dict(w=float(w) if w else p['w'] * g.uniform(0.97, 0.995),
             d=float(d) if d else p['d'] * g.uniform(0.975, 0.995),
             h=float(h) if h else p['h'] * g.uniform(0.98, 0.995))
    P['storeys'] = int(storeys) if storeys else C.cycle(seed, [2, 2, 1])
    P['roof'] = roof or C.cycle(seed, ['irimoya', 'hip', 'irimoya'])
    P['veranda'] = float(veranda) if veranda else g.uniform(1.3, 1.6)
    P['eave'] = g.uniform(1.0, 1.2)
    P['pitch'] = g.uniform(22, 26)
    P['up'] = g.uniform(0.12, 0.22)
    P['tp'] = g.uniform(0.25, 0.28)
    P['p'] = g.uniform(1.15, 1.3)
    P['g_h'] = g.uniform(2.5, 2.7)
    gw = C.rng(seed, 'glass')
    P['lava_frac'] = gw.uniform(0.55, 0.7)
    P['lava_w'] = float(lava_w) if lava_w else None
    P['lava_h'] = float(lava_h) if lava_h else None
    P['mull'] = gw.uniform(1.3, 1.7)
    P['glass'] = glass or 'lava_glass'
    P['glow'] = 0.0 if glow is None else float(glow)
    gb = C.rng(seed, 'bays')
    P['bay'] = gb.uniform(1.75, 2.1)
    P['open_bay'] = gb.random() < 0.6
    P['corner_lanterns'] = gb.random() < 0.6
    P['kumiko'] = gb.choice([(3, 6), (3, 7), (4, 7)])
    return P


def _quad(mb, pts, mi):
    bm = mb.bm
    f = bm.faces.new([bm.verts.new(p) for p in pts]); f.material_index = mi
    return f


def _roof_mats(mb):
    return dict(tile=mb.slot('kawara'), ridge=mb.slot('kawara'), wood=mb.slot('hinoki', variant='dark_timber'),
                wood_d=mb.slot('lacquer_dark', wear=0.1), iron=mb.slot('iron', wear=0.2))


def layout(P):
    """plan and heights (independent of the LOD)"""
    L = {}
    W, D, H = P['w'], P['d'], P['h']
    hw = W / 2
    vd = P['veranda']
    if P['storeys'] == 2:
        eave = P['eave']
        ext = 0.62                                    # pent eave beyond the veranda (covers the stair)
        wd = D - eave - vd - ext
    else:
        eave = vd + 0.62                              # deep front eave covers the veranda and the stair
        wd = D - 2 * eave
    y0 = -D / 2 + eave
    y1 = y0 + wd
    L.update(hw=hw, hd=wd / 2 + eave, eave=eave, eave_s=min(P['eave'], 1.2), xw=hw - min(P['eave'], 1.2), y0=y0, y1=y1,
             ym=(y0 + y1) / 2, vd=vd, wd=wd)
    fz = 0.45
    L['fz'] = fz

    def dry(pitch):
        tmp = genlib.MeshBuilder()
        info = KR.roof_into(tmp, _roof_mats(tmp), 2, P['roof'], hw, L['hd'], z_e=0.0, pitch=pitch, eave=eave,
                            eave_s=L['eave_s'], up=P['up'], tp=P['tp'], p=P['p'])
        tmp.bm.free()
        return info
    pitch = P['pitch']
    for _ in range(8):
        info = dry(pitch)
        part = info['top_z'] - info['wall_top']
        if P['storeys'] == 2:
            g_top = fz + P['g_h']
            u0 = g_top + 0.35
            u_h = H - u0 - part
            if u_h < 2.6 and pitch > 18.5:
                pitch -= 1.5; continue
            if u_h > 3.2 and pitch < 32:
                pitch += 1.5; continue
            wall_top = u0 + u_h
            L.update(g_top=g_top, u0=u0, u_h=u_h)
        else:
            g_h = H - fz - part
            if g_h < 3.4 and pitch > 18.5:
                pitch -= 1.5; continue
            if g_h > 4.4 and pitch < 34:
                pitch += 1.5; continue
            wall_top = fz + g_h
            L.update(g_top=wall_top, u0=None, u_h=0.0)
        break
    L.update(pitch=pitch, wall_top=wall_top, z_e=wall_top - info['wall_top'], roof_info=info)
    # bays across the front wall
    xw = L['xw']
    nb = max(4, int(round(2 * xw / P['bay'])))
    L['bx'] = [-xw + 2 * xw * i / nb for i in range(nb + 1)]
    return L


def _shoji_bay(mb, lod, x0, x1, z0, z1, plane, out, M, P, open_one=False):
    """one bay of two shoji panels between posts. plane: 'y' (front, at y = out[0], facing out[1] sign) or 'x'.
    M: dict(paper, frame, koshi)"""
    pos, sgn = out
    def P3(u, v, off):
        return (u, pos + sgn * off, v) if plane == 'y' else (pos + sgn * off, u, v)
    w = (x1 - x0) / 2
    if lod == 3:
        pts = [P3(x0, z0 + 0.3, 0.03), P3(x1, z0 + 0.3, 0.03), P3(x1, z1, 0.03), P3(x0, z1, 0.03)]
        if (plane == 'y') != (sgn > 0):
            pts = pts[::-1]
        if plane == 'x':
            pts = pts[::-1]
        _quad(mb, pts, M['paper'])
        return
    for k in range(2):
        a, b = x0 + k * w, x0 + (k + 1) * w
        if open_one and k == 1:
            a, b = a - w * 0.85, b - w * 0.85            # slid behind its neighbour: a lit gap opens
        za, zb = z0 + 0.32, z1 - 0.05
        pts = [P3(a, za, 0.03), P3(b, za, 0.03), P3(b, zb, 0.03), P3(a, zb, 0.03)]
        if (plane == 'y') != (sgn > 0):
            pts = pts[::-1]
        if (plane == 'x'):
            pts = pts[::-1]
        _quad(mb, pts, M['paper'])
        if lod >= 2:
            continue
        def bx(u0, u1, v0, v1, d0, d1, mi):
            c = P3((u0 + u1) / 2, (v0 + v1) / 2, (d0 + d1) / 2)
            s = (u1 - u0, d1 - d0, v1 - v0) if plane == 'y' else (d1 - d0, u1 - u0, v1 - v0)
            mb.box(c, s, mi)
        st = 0.045
        # frame: stiles + top rail + kick board (koshi)
        bx(a, a + st, z0, z1, 0.02, 0.07, M['frame'])
        bx(b - st, b, z0, z1, 0.02, 0.07, M['frame'])
        bx(a, b, z1 - 0.06, z1, 0.02, 0.07, M['frame'])
        bx(a, b, z0, z0 + 0.32, 0.01, 0.065, M['koshi'])
        if lod == 0:
            cols, rows = P['kumiko']
            for i in range(1, cols):
                u = a + st + (b - a - 2 * st) * i / cols
                bx(u - 0.011, u + 0.011, za, zb, 0.03, 0.055, M['frame'])
            for j in range(1, rows):
                v = za + (zb - za) * j / rows
                bx(a + st, b - st, v - 0.011, v + 0.011, 0.03, 0.055, M['frame'])


def _lava_face(mb, lod, x0, x1, z0, z1, y, r, mi, mi_flow=None):
    """molten rock face behind the glass: a displaced grid bulging towards +Y (closed by the recess cheeks)"""
    nx = C.lod_pick(lod, 26, 12, 4, 1)
    nz = C.lod_pick(lod, 10, 5, 2, 1)
    bm = mb.bm
    ph = Vector((r.uniform(0, 50), r.uniform(0, 50), r.uniform(0, 50)))
    rows = []
    for j in range(nz + 1):
        z = z0 + (z1 - z0) * j / nz
        row = []
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx
            edge = min(i, nx - i, j, nz - j)
            amp = 0.0 if edge == 0 or lod >= 2 else 0.32
            n = noise.noise(Vector((x * 0.45, z * 0.5, 0)) + ph) * 0.6 + noise.noise(Vector((x * 1.3, z * 1.4, 3)) + ph) * 0.4
            row.append(bm.verts.new((x, y + amp * (0.5 + n), z)))
        rows.append(row)
    fs = []
    for j in range(nz):
        for i in range(nx):
            f = bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
            # proud bosses are dark crusted rock; the hollows between them run molten
            proud = sum(v.co.y for v in f.verts) / 4 - y
            f.material_index = mi if (mi_flow is None or proud > 0.2 or lod >= 2) else mi_flow
            fs.append(f)
    if mi_flow is not None and lod >= 2:
        for f in fs:
            f.material_index = mi_flow


def build(lod, seed, w=None, d=None, h=None, storeys=None, lava_w=None, lava_h=None, veranda=None, roof=None,
          glass=None, glow=None, **_):
    P = params(seed, w, d, h, storeys, lava_w, lava_h, veranda, roof, glass, glow)
    clear = P['glass'] == 'clear'
    L = layout(P)
    budget = genlib.budget_of(ASSET)
    mb = genlib.MeshBuilder()
    rm = _roof_mats(mb)
    m_post, m_lac, m_iron = rm['wood'], rm['wood_d'], rm['iron']
    m_frame = mb.slot('hinoki', variant='natural', wear=0.15)
    m_deck = mb.slot('hinoki', variant='wet_oiled', wear=0.3)
    m_rail = mb.slot('hinoki', variant='stained', wear=0.2)
    m_paper = mb.slot('washi_backlit', emissive_level=0.5)
    m_glass = mb.slot('glass_clear') if clear else mb.slot('lava_glass', emissive_level=P['glow'])
    m_bronze = mb.slot('bronze', variant='smooth')
    m_lava = mb.slot('lava', emissive_level=1.0, scale=2.5)
    m_flow = mb.slot('lava_flow', emissive_level=1.2, scale=3.0)
    m_andon = mb.slot('lantern_andon', emissive_level=0.9)
    Msh = dict(paper=m_paper, frame=m_frame, koshi=m_post)
    lights = []
    xw, y0, y1, fz = L['xw'], L['y0'], L['y1'], L['fz']
    g_top, wall_top, vd = L['g_top'], L['wall_top'], L['vd']
    two = P['storeys'] == 2
    ps = 0.24
    # ---------------------------------------------------------------- main roof (shifted over the walls)
    rb = int(budget[lod] * C.lod_pick(lod, 0.45, 0.4, 0.45, 0.25)) if budget else None
    lay = mb._mark_old()
    info = KR.roof_into(mb, rm, lod, P['roof'], L['hw'], L['hd'], z_e=L['z_e'], pitch=L['pitch'], eave=L['eave'],
                        eave_s=L['eave_s'], up=P['up'], tp=P['tp'], p=P['p'], budget=rb)
    if info['notes'] and any(info['notes']):
        print(f'summit_lodge LOD{lod} s{seed} roof resolution fallback: {info["notes"]}')
    vs = list({v for f in mb._new_faces(lay) for v in f.verts})
    bmesh.ops.translate(mb.bm, vec=(0, L['ym'], 0), verts=vs)
    wt = wall_top
    # ceiling slab closing the roof underside over the walls
    if lod <= 2:
        mb.box((0, L['ym'], wt + 0.06), (2 * xw + 0.1, L['wd'] + 0.1, 0.12), m_lac)
    # ---------------------------------------------------------------- plinth skirt + core walls
    if lod <= 2:
        mb.box((0, L['ym'], fz / 2), (2 * xw + 0.06, L['wd'] + 0.06, fz), m_lac)
    rec = 1.1                                           # lava recess depth behind the glass
    if two:
        gw_ = P['lava_w'] or 2 * xw * P['lava_frac']
        gx = min(gw_, 2 * xw - 1.0) / 2
        gz0 = L['u0'] + 0.12
        gz1 = gz0 + (P['lava_h'] or (L['u_h'] - 0.25))
    else:
        gx = (P['lava_w'] or min(2 * xw * 0.32, 4.6)) / 2
        gz0, gz1 = fz + 0.25, (P['lava_h'] + fz + 0.25) if P['lava_h'] else wt - 0.35
    if lod == 3:                                        # one block; the glass sits on its face
        mb.box((0, L['ym'], wt / 2), (2 * xw, L['wd'], wt), m_post)
        rec = -0.012
    elif two:
        mb.box((0, L['ym'], (fz + g_top) / 2), (2 * xw, L['wd'], g_top - fz), m_post)          # ground core
        mb.box((0, (y0 + y1 - rec) / 2, (g_top + wt) / 2), (2 * xw, L['wd'] - rec, wt - g_top), m_post)   # upper core
        for sx in (-1, 1):                              # upper wall either side of the glass
            xa, xb = sx * gx, sx * xw
            mb.box(((xa + xb) / 2, y1 - rec / 2, (g_top + wt) / 2), (abs(xb - xa), rec, wt - g_top), m_post)
            mb.box((sx * (gx + 0.02), y1 - rec / 2, (gz0 + gz1) / 2), (0.04, rec - 0.02, gz1 - gz0), m_lac)  # cheek
        mb.box((0, y1 - rec / 2, (g_top + gz0) / 2), (2 * gx, rec, gz0 - g_top), m_post)     # recess floor
        mb.box((0, y1 - rec / 2, (gz1 + wt) / 2), (2 * gx, rec, wt - gz1), m_post)           # recess head
    else:
        mb.box((0, (y0 + y1 - rec) / 2, (fz + wt) / 2), (2 * xw, L['wd'] - rec, wt - fz), m_post)
        for sx in (-1, 1):
            xa, xb = sx * gx, sx * xw
            mb.box(((xa + xb) / 2, y1 - rec / 2, (fz + wt) / 2), (abs(xb - xa), rec, wt - fz), m_post)
            mb.box((sx * (gx + 0.02), y1 - rec / 2, (gz0 + gz1) / 2), (0.04, rec - 0.02, gz1 - gz0), m_lac)
        mb.box((0, y1 - rec / 2, (fz + gz0) / 2), (2 * gx, rec, gz0 - fz), m_post)
        mb.box((0, y1 - rec / 2, (gz1 + wt) / 2), (2 * gx, rec, wt - gz1), m_post)
    # molten rock face at the back of the recess
    if lod <= 2:
        _lava_face(mb, lod, -gx, gx, gz0, gz1, y1 - rec, C.rng(seed, 'lava'), m_lava, m_flow)
    # ---------------------------------------------------------------- glass wall in bronze mullions
    yg = y1 - 0.06 if lod <= 2 else y1 + 0.012
    if lod <= 2:
        nm = max(2, int(round(2 * gx / P['mull'])))
        mw = C.lod_pick(lod, 0.09, 0.09, 0.1)
        for i in range(nm + 1):
            x = -gx + 2 * gx * i / nm
            mb.box((x, yg + 0.04, (gz0 + gz1) / 2), (mw if 0 < i < nm else 0.16, 0.16, gz1 - gz0), m_bronze)
        mb.box((0, yg + 0.06, gz0 - 0.06), (2 * gx + 0.3, 0.26, 0.14), m_bronze)          # sill
        mb.box((0, yg + 0.05, gz1 + 0.07), (2 * gx + 0.3, 0.22, 0.16), m_bronze)          # head
        if lod == 0:                                    # transom bar high up (clerestory line) + glass chamfer strips
            mb.box((0, yg + 0.03, gz1 - (gz1 - gz0) * 0.16), (2 * gx, 0.08, 0.06), m_bronze)
    _quad(mb, [(-gx, yg, gz0), (gx, yg, gz0), (gx, yg, gz1), (-gx, yg, gz1)], m_glass if lod <= 2 else m_flow)
    if lod <= 1:                                        # back face so the pane has thickness from inside angles
        _quad(mb, [(-gx, yg - 0.04, gz1), (gx, yg - 0.04, gz1), (gx, yg - 0.04, gz0), (-gx, yg - 0.04, gz0)], m_glass)
    lights.append(C.light_entry((0, y1 - rec + 0.3, (gz0 + gz1) / 2), color_k=1600, watts=900, kind='area',
                                size=[round(2 * gx, 2), round(gz1 - gz0, 2)], normal=[0, 1, 0]))
    # ---------------------------------------------------------------- ground floor: posts + shoji bays (front, sides)
    zt_sh = g_top - (0.3 if two else 0.9)              # shoji head (1-storey: a ranma band above)
    bxs = L['bx']
    mid = len(bxs) // 2
    for i, x in enumerate(bxs):
        if lod <= 2 and not (not two and -gx - 0.1 < x < gx + 0.1):
            mb.box((x, y1 + 0.05, (fz + (g_top if two else wt)) / 2), (ps, ps, (g_top if two else wt) - fz), m_post)
    for i in range(len(bxs) - 1):
        x0, x1 = bxs[i] + ps / 2, bxs[i + 1] - ps / 2
        if not two and (x1 > -gx - 0.05 and x0 < gx + 0.05):
            continue                                    # 1-storey: the glass bay replaces these shoji
        _shoji_bay(mb, lod, x0, x1, fz, zt_sh, 'y', (y1, 1), Msh, P, open_one=P['open_bay'] and i == mid - 1 and two)
    for sx in (-1, 1):                                  # side shoji (2 bays per side)
        ys = [y1 - (L['wd'] - 0.4) * k / 2 - 0.2 for k in range(3)]
        for k in range(2):
            _shoji_bay(mb, lod, min(ys[k], ys[k + 1]) + ps / 2, max(ys[k], ys[k + 1]) - ps / 2, fz, zt_sh, 'x',
                       (sx * xw, sx), Msh, P)
        for yy in ys:
            if lod <= 2:
                mb.box((sx * (xw + 0.03), yy, (fz + g_top) / 2), (ps, ps, g_top - fz), m_post)
    lights.append(C.light_entry((0, y1 + 0.6, (fz + zt_sh) / 2), color_k=2700, watts=400, kind='area',
                                size=[round(2 * xw, 2), round(zt_sh - fz, 2)], normal=[0, 1, 0]))
    # floor band / head beams round the ground storey
    if lod <= 2:
        hb = 0.3 if two else 0.26
        mb.box((0, y1 + 0.06, g_top - hb / 2 + (0.04 if two else 0.0)), (2 * xw + 0.3, 0.26, hb), m_post)
        if not two and lod <= 1:                       # ranma band over the shoji (1-storey): lit lattice strip
            for i in range(len(bxs) - 1):
                x0, x1 = bxs[i] + ps / 2, bxs[i + 1] - ps / 2
                if x1 > -gx - 0.05 and x0 < gx + 0.05:
                    continue
                _quad(mb, [(x0, y1 + 0.03, zt_sh + 0.15), (x1, y1 + 0.03, zt_sh + 0.15), (x1, y1 + 0.03, wt - 0.4),
                           (x0, y1 + 0.03, wt - 0.4)], m_paper)
                n = max(3, int((x1 - x0) / 0.12))
                for k in range(1, n) if lod == 0 else ():
                    u = x0 + (x1 - x0) * k / n
                    mb.box((u, y1 + 0.05, (zt_sh + wt - 0.25) / 2), (0.03, 0.04, wt - 0.4 - zt_sh - 0.15), m_frame)
        for sx in (-1, 1):
            mb.box((sx * (xw + 0.06), L['ym'], g_top - hb / 2), (0.26, L['wd'] + 0.2, hb), m_post)
    # ---------------------------------------------------------------- veranda: deck, stair, railing, lanterns
    yv = y1 + vd
    xv = xw + 0.15
    if lod == 0:
        nrow = max(5, int(vd / 0.17))
        for j in range(nrow):
            y = y1 + 0.08 + (vd - 0.08) * (j + 0.5) / nrow
            mb.box((0, y, fz - 0.03), (2 * xv, (vd - 0.08) / nrow - 0.012, 0.06), m_deck)
    elif lod <= 2:
        mb.box((0, y1 + vd / 2 + 0.04, fz - 0.03), (2 * xv, vd - 0.08, 0.06), m_deck)
    else:
        mb.box((0, y1 + vd / 2 + 0.04, fz / 2), (2 * xv, vd - 0.08, fz), m_deck)
    sw = 2.4
    if lod <= 2:
        mb.box((0, yv - 0.05, fz / 2 - 0.03), (2 * xv + 0.1, 0.12, fz - 0.06), m_post)   # edge beam to the ground
        for k in (1, 2):                                # 3 risers of 0.15 m
            ztop = fz - 0.15 * k
            mb.box((0, yv + 0.28 * (k - 0.5), ztop / 2), (sw, 0.28, ztop), m_deck)
    else:
        mb.box((0, yv + 0.28, 0.15), (sw, 0.56, 0.3), m_deck)
    # veranda posts: carry the pent eave (2 storeys) or the deep main eave (1 storey)
    yp = yv - 0.14
    if two:
        z_pent_top = g_top + 0.32
        ext = 0.62
        z_ev = KR.pent_into(mb, rm, lod, -xv - 0.25, xv + 0.25, y1 + 0.1, vd + ext - 0.1, z_pent_top, pitch=21,
                            tp=P['tp'])
        frac = (yp - y1) / (vd + ext - 0.1)
        z_beam = z_pent_top - 0.14 + (z_ev - z_pent_top) * frac - 0.02
    else:
        e = L['eave']
        frac = (yp - y1) / e
        z_soff_wall = wt + 0.12
        z_soff_eave = L['z_e'] - 0.13
        z_beam = z_soff_wall + (z_soff_eave - z_soff_wall) * frac - 0.12
    vxs = [x for x in bxs] if lod <= 2 else [bxs[0], bxs[-1]]
    vstep = 2 if len(vxs) > 6 and lod <= 2 else 1
    vxs = vxs[::vstep] if vxs[-1] in vxs[::vstep] else vxs[::vstep] + [vxs[-1]]
    for x in vxs:
        if abs(x) < sw / 2 + 0.1:
            continue
        mb.box((x, yp, (fz + z_beam) / 2), (0.18, 0.18, z_beam - fz), m_post)
    mb.box((0, yp, z_beam + 0.09), (2 * xv + 0.4, 0.2, 0.2), m_post)                  # eave beam
    if lod <= 1:                                        # tie beams back to the wall at each veranda post
        for x in vxs:
            if abs(x) < sw / 2 + 0.1:
                continue
            mb.box((x, (y1 + yp) / 2, z_beam - 0.06), (0.1, yp - y1, 0.12), m_post)
    # railing along the veranda front (gap for the stair) and the ends
    rh = 0.75
    runs = [((-xv + 0.05, yv - 0.1), (-sw / 2 - 0.05, yv - 0.1)), ((sw / 2 + 0.05, yv - 0.1), (xv - 0.05, yv - 0.1)),
            ((-xv + 0.05, y1 + 0.15), (-xv + 0.05, yv - 0.1)), ((xv - 0.05, y1 + 0.15), (xv - 0.05, yv - 0.1))]
    newel_spots = []
    for (xa, ya), (xb, yb) in runs:
        Ln = math.hypot(xb - xa, yb - ya)
        ux = abs(xb - xa) > abs(yb - ya)
        m = max(1, int(math.ceil(Ln / 1.4)))
        for k in range(m + 1):
            px, py = xa + (xb - xa) * k / m, ya + (yb - ya) * k / m
            end = k in (0, m)
            if lod <= 2 and (end or lod <= 1):
                mb.box((px, py, fz + (rh + 0.1 * end) / 2), (0.09 + 0.02 * end, 0.09 + 0.02 * end, rh + 0.1 * end), m_rail)
            if lod <= 1 and end and ux:
                kg.giboshi(mb, (px, py, fz + rh + 0.1), m_rail, lod, scale=1.0)
        cx, cy = (xa + xb) / 2, (ya + yb) / 2
        if lod == 3:
            _quad(mb, [(xa, ya, fz + rh - 0.2), (xb, yb, fz + rh - 0.2), (xb, yb, fz + rh), (xa, ya, fz + rh)], m_rail)
            continue
        for z, t, hh in ((rh - 0.03, 0.07, 0.055), (0.38, 0.045, 0.04)):
            if lod >= 2 and z < 0.5:
                continue
            mb.box((cx, cy, fz + z), (Ln, t, hh) if ux else (t, Ln, hh), m_rail)
    newel_spots = [(-sw / 2 - 0.05, yv - 0.1), (sw / 2 + 0.05, yv - 0.1)]
    if P['corner_lanterns']:
        newel_spots += [(-xv + 0.05, yv - 0.1), (xv - 0.05, yv - 0.1)]
    for x, y in newel_spots:
        base = (x, y, fz + rh + 0.1 + (0.18 if lod <= 1 else 0.0))
        if lod <= 2:
            c = C.lantern_head(mb, base, dict(iron=m_iron, paper=m_andon), lod, size=0.22, height=0.38, roof='hip')
        else:
            _quad(mb, [(x - 0.11, y + 0.02, base[2]), (x + 0.11, y + 0.02, base[2]), (x + 0.11, y + 0.02, base[2] + 0.38),
                       (x - 0.11, y + 0.02, base[2] + 0.38)], m_andon)
            c = Vector((x, y, base[2] + 0.19))
        lights.append(C.light_entry(c, color_k=2200, watts=15))
    # ---------------------------------------------------------------- finish
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    kg.uv_grain(o, [m_post, m_frame, m_deck, m_rail])
    for Lg in lights:
        Lg['pos'] = [round(Lg['pos'][0] + dx, 4), round(Lg['pos'][1] + dy, 4), round(Lg['pos'][2] + dz, 4)]
    C.set_json_props(o, kz_lights=lights,
                     kz_anim=dict(type='shader', slots={'lava_flow': 'flow', 'lava': 'glow_pulse',
                                                        'washi_backlit': 'flicker'}),
                     kz_floor_z=round(fz + dz, 3),
                     kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()})
    return o
