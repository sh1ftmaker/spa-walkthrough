"""Noren door curtain: split cloth panels hung from a rod at a door head, with the dyed Kazan-yu crest.

Identifying features kept at every LOD: split cloth panels (at least the centre slit), the rod they hang
from, the crest print, the cloth colour (indigo / black / vermilion / cream). Proxy (3d/assets.json):
1.2 x 0.1 x 1.8 m.

Construction
  * Cloth: one sheet per panel, joined across a 0.08-0.12 m sewn head band (darker double layer) and split
    below it. The grid columns sit on pleat ridges and valleys; pleat depth grows from ~0.5 cm under the
    band to ~2 cm at the hem. The slits open towards the hem (~1.5 cm), every panel swings, drifts and
    ends at its own hem height (1-2 cm spread), and a turned 8 mm hem band runs along the bottom.
  * Hang style: 'tabs' (chichi loops round the rod) or 'sleeve' (the head wraps round the rod).
  * Rod: a 33 mm turned rod ('hinoki' oiled wood, or 'bronze' tube) with bronze ball finials,
    overhanging the cloth by ~0.08 m each side, on two bronze hook brackets that stand it 0.07 m off the
    door-head plane (y = -d/2).
  * Crest: 'kazan_full' (mountain + three wisps + KAZAN-YU / 火山湯 lettering; default on indigo, black and
    cream door noren), 'kazan' (mark only; default on vermilion and half noren), 'onsen' or 'none'. The
    crest is a dyed-colour decal mapped onto the folded cloth 3-4 mm in front of it and split by the
    slits. LOD0 carries real glyphs; LOD1-3 keep the mark and two cream bars for the two text lines.
    Visible from the front (+Y); the cloth is a single surface: render it double-sided.
  * Styles by seed (when w/h/splits/colour are not given), all inside the proxy:
      seed % 4 == 1: indigo door noren 1.2 x 1.8, 3 splits
      seed % 4 == 2: vermilion half noren (counter) 1.2 x 0.5-0.6, 4-5 splits
      seed % 4 == 3: black narrow door noren 0.8-0.95 x 1.45-1.65, 2 splits
      seed % 4 == 0: cream door noren 1.0-1.15 x 1.6-1.75, 3 splits
    Wide 2.4-3.6 m noren come from explicit w (they exceed this proxy and need their own proxy).

Pivot / placement: base centre, z = 0 is the lowest hem, the rod is at obj['kz_hang']['rod_z'].

Animation (vertex sway, parts when walked through) - data only, no runtime here:
  * float point attribute '_sway'  : 0 at the rod/head band, rising to 1 at the hem (cloth and crest).
  * float point attribute '_panel' : panel index 0..n-1 (-1 for rod, brackets, tabs). At LOD3 a 4-5
                                      split noren is drawn as 2 panels (the centre slit is kept).
  * float point attribute '_u'     : 0..1 across the panel, for parting about each panel's centre line.
  * colour attribute 'kz_sway'     : (sway, panel/(n-1), u, 1).
  * obj['kz_anim'] (JSON)          : {'type': 'vertex_sway', 'attrs', 'splits', 'panel_x', 'band_z'}.
"""
import json
import math
import random

import bmesh
import bpy
from mathutils import Vector

import genlib
import kzgeo_noren as KG

ASSET = 'noren'
FEATURES = ['split cloth panels', 'rod at the door head', 'crest print', 'indigo / black / vermilion / cream cloth']
PARAMS = dict(w=(0.8, 3.6), h=(0.45, 1.8), splits=(2, 5), colour=('indigo', 'black', 'vermilion', 'cream'),
              crest=('kazan_full', 'kazan', 'onsen', 'none'), rod=('hinoki', 'bronze'), hang=('tabs', 'sleeve'))


def _tint(colour):
    m = genlib.matlib.manifest()['noren']
    if colour == 'indigo' or colour not in m.get('variants', {}):
        return tuple(m['params']['tint'])
    return tuple(m['variants'][colour]['tint'])


def _to_object(mb, name):
    """like MeshBuilder.to_object but keeps our explicit winding (no normal recalculation on open sheets)"""
    me = bpy.data.meshes.new(name)
    mb.bm.to_mesh(me)
    mb.bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    for i, (mid, params) in enumerate(mb.slots):
        genlib.matlib.assign(o, mid, slot=i, **params)
    return o


def _face(bm, vs, mi, out=None):
    f = bm.faces.new(vs)
    f.material_index = mi
    if out is not None:
        f.normal_update()
        if f.normal.dot(Vector(out)) < 0:
            f.normal_flip()
    return f


class Cloth:
    """Rest-space cloth: panels (with slits), rows (head band + body + hem band), displaced positions."""

    def __init__(self, cloth_w, z_top, z_band, hems, n, gap, amp0, amp1, swings, drifts, y0, flat=False):
        self.cw, self.z_top, self.z_band, self.hems, self.n = cloth_w, z_top, z_band, hems, n
        self.amp0, self.amp1, self.swings, self.drifts, self.y0, self.flat = amp0, amp1, swings, drifts, y0, flat
        pw = cloth_w / n
        self.edges = [(-cloth_w / 2 + i * pw + (gap / 2 if i else 0), -cloth_w / 2 + (i + 1) * pw - (gap / 2 if i < n - 1 else 0))
                      for i in range(n)]
        self.z_low = min(hems)
        self.belly, self.peel = 0.0, 0.0

    def panel_of(self, x):
        for i, (a, b) in enumerate(self.edges):
            if x <= b + 1e-6:
                return i
        return self.n - 1

    def depth(self, z):
        return max(0.0, min(1.0, (self.z_top - z) / max(1e-3, self.z_top - self.z_low)))

    def below(self, z):
        return max(0.0, min(1.0, (self.z_band - z) / max(1e-3, self.z_band - self.z_low)))

    def z_of(self, t, p):
        band_t = (self.z_top - self.z_band) / max(1e-3, self.z_top - self.hems[p])
        if t <= band_t:
            return self.z_top - t * (self.z_top - self.z_band) / max(1e-6, band_t)
        return self.z_band - (t - band_t) / max(1e-6, 1 - band_t) * (self.z_band - self.hems[p])

    def pos(self, x, t, p, fv=0.0):
        z = self.z_of(t, p)
        s, b = self.depth(z), self.below(z)
        a, bb = self.edges[p]
        u = (x - a) / max(1e-6, bb - a)
        if self.flat:
            return Vector((x, self.y0, z)), s, u
        A = self.amp0 + (self.amp1 - self.amp0) * s ** 1.4      # pleat depth: ~0.5 cm under the band, ~2 cm at the hem
        curl = 0.012 * b * (abs(math.cos(math.pi * u)) ** 6) * (1 if (p % 2) else -1)
        belly = self.belly * math.sin(math.pi * min(1.0, max(0.0, (s - 0.4) / 0.6))) ** 1.2   # forward belly, lower third
        hem = 0.004 * max(0.0, 1.0 - (z - self.hems[p]) / 0.012)  # turned hem stands proud
        y = self.y0 + A * fv + self.swings[p] * b ** 1.3 + curl + hem + belly
        # panels pull in towards their own centre line below the band: the slits open towards the hem
        xx = x - (2 * u - 1) * self.peel * b ** 1.5 + self.drifts[p] * b ** 1.6   # slit edges peel apart at the hem
        return Vector((xx, y, z)), s, u


def _style(seed, r):
    k = seed % 4
    if k == 1:
        return dict(w=1.2, h=1.8, splits=2, colour='indigo')       # concept hero: 2 panels, one centre slit
    if k == 2:
        return dict(w=1.2, h=round(r.uniform(0.5, 0.6), 3), splits=r.choice([4, 5]), colour='vermilion')
    if k == 3:
        return dict(w=round(r.uniform(0.8, 0.95), 3), h=round(r.uniform(1.45, 1.65), 3), splits=2, colour='black')
    return dict(w=round(r.uniform(1.0, 1.15), 3), h=round(r.uniform(1.6, 1.75), 3), splits=3, colour='cream')


def build(lod, seed, w=None, h=None, splits=None, colour=None, crest=None, rod=None, hang=None, **_):
    p = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    budget = genlib.budget_of(ASSET) or [400, 160, 50, 12]
    st = _style(seed, r)
    w = min(max(w or st['w'], 0.8), 3.6)
    h = min(max(h or st['h'], 0.45), 1.8)
    d = p['d']
    colour = colour or st['colour']
    splits = max(2, min(5, int(splits or (st['splits'] if w <= 1.25 else (4 if w < 2.6 else 5)))))
    crest = crest or ('kazan' if (colour == 'vermilion' or h < 1.0) else 'kazan_full')
    door = h >= 1.0
    rod = rod or ('hinoki' if door else r.choice(['hinoki', 'bronze']))     # concept: tab loops on a turned wooden rod
    hang = hang or ('tabs' if door else r.choice(['tabs', 'sleeve']))
    rr = genlib.rng(seed, ASSET + 'shape')
    lim = int(budget[lod] * 1.1)             # the check's 10 % tolerance (lettering needs it at LOD0)
    for attempt in range(14):
        o = _build_once(lod, seed, w, h, d, splits, colour, crest, rod, hang, rr.getstate(), attempt)
        if genlib.tris(o) <= lim or attempt == 13:
            break
        bpy.data.meshes.remove(o.data)
    o['kz_params'] = json.dumps(dict(w=round(w, 3), h=round(h, 3), splits=splits, colour=colour, crest=crest, rod=rod, hang=hang))
    return genlib.finish(o, smooth_angle=70)


def _build_once(lod, seed, w, h, d, splits, colour, crest, rod, hang, state, attempt):
    r = random.Random()
    r.setstate(state)
    mb = genlib.MeshBuilder()
    bm = mb.bm
    L_sway = bm.verts.layers.float.new('_sway')
    L_panel = bm.verts.layers.float.new('_panel')
    L_u = bm.verts.layers.float.new('_u')
    ct = _tint(colour)
    cloth_m = mb.slot('noren', tint=ct, wear=round(r.uniform(0.05, 0.25), 2), normal_strength=1.8)
    band_m = mb.slot('noren', tint=tuple(round(c * 0.96, 4) for c in ct), normal_strength=1.8)     # sewn head: same cloth, a hair darker
    ink = _tint('indigo') if colour == 'cream' else _tint('cream')
    crest_m = mb.slot('noren', tint=ink, normal_strength=1.2)
    bronze = mb.slot('bronze', wear=round(r.uniform(0.15, 0.4), 2))
    wood = mb.slot('hinoki', variant='wet_oiled') if rod == 'hinoki' else bronze    # dark oiled turned rod (concept)

    # ---------------- layout
    rod_r = 0.0215 if rod == 'hinoki' else 0.018            # 43 / 36 mm
    rod_y = -d / 2 + 0.055                                  # 0.055 m stand-off (proxy depth 0.1 m leaves room for the belly)
    z_rod = h - 0.036
    tab_len = 0.075 if hang == 'tabs' else 0.0           # loops ~0.08 m tall
    z_top = z_rod - rod_r - 0.004 - tab_len
    cloth_h = z_top
    band = 0.07 if cloth_h > 1.0 else 0.055        # slits start just under the tab line (concept)
    z_band = z_top - band
    hems = [r.uniform(0.0, 0.02) for _ in range(splits)]
    m0 = min(hems)
    hems = [x - m0 for x in hems]
    fin_l = 0.06                                            # 0.06 m bronze end caps
    over = min(0.08, 0.07 * w)
    cloth_w = w - 2 * (fin_l + over)
    hs = min(1.0, cloth_h / 1.2)
    amp0, amp1 = 0.0075, 0.0075 + 0.0105 * hs            # +-0.75 cm under the band, +-1.8 cm (3.6 cm p-p) at the hem
    swings = [r.uniform(-0.004, 0.008) * hs for _ in range(splits)]
    drifts = [r.uniform(-0.008, 0.008) * hs for _ in range(splits)]
    drifts[0], drifts[-1] = min(drifts[0], 0.0) * 0.3, max(drifts[-1], 0.0) * 0.3
    n = splits
    if lod == 3 and splits * 2 + 2 + 5 > 13:
        n = 2                                               # LOD3: keep the centre slit only
    C = Cloth(cloth_w, z_top, z_band, hems[:n] if n == splits else [0.0, 0.0], n, 0.008, amp0, amp1, swings, drifts, rod_y, flat=(lod == 3))
    C.belly, C.peel = 0.022 * hs, 0.014 * hs                # 2-3 cm belly; slits open ~3.5 cm at the hem
    if lod == 3:
        C.y0 = rod_y - 0.008

    # ---------------- grid resolution per LOD (reduced on retries)
    if lod == 0:
        cols_pp = max(2, round(16 / n) - attempt // 2)      # ridge/valley columns: 4 ripples per door panel
        body_rows = max(2, 4 - attempt % 2 - attempt // 6)
        hem_row = True
    elif lod == 1:
        cols_pp = max(2, round(8 / n) + 1 - attempt)
        body_rows, hem_row = 2, False
    elif lod == 2:
        cols_pp, body_rows, hem_row = max(1, 2 - attempt), 1, False
    else:
        cols_pp, body_rows, hem_row = 1, 1, False
    band_rows = 1 if lod <= 2 else 0

    def t_rows(pi):
        band_t = (z_top - z_band) / max(1e-3, z_top - C.hems[pi])
        ts = [0.0] + ([band_t] if band_rows else [])
        t0 = band_t if band_rows else 0.0
        ends = [t0 + (1 - t0) * (k / body_rows) ** 0.9 for k in range(1, body_rows + 1)]
        if hem_row:
            ends = ends[:-1] + [1 - 0.008 / max(0.1, z_top - C.hems[pi]), 1.0]
        return ts + ends

    grid, xcols = {}, []
    for pi, (a, b) in enumerate(C.edges):
        rf = random.Random(f'{seed}:fold:{pi}')
        jit = [0.0] + [rf.uniform(-0.18, 0.18) for _ in range(cols_pp - 1)] + [0.0]
        xs = [a + (b - a) * (k + jit[k]) / cols_pp for k in range(cols_pp + 1)]
        sign = rf.choice((-1, 1))
        lod_k = {0: 1.0, 1: 0.85, 2: 0.6}.get(lod, 0.0)
        fvs = [sign * (-1) ** k * rf.uniform(0.6, 1.0) * (0.5 if k in (0, cols_pp) else 1.0) * lod_k for k in range(cols_pp + 1)]
        xcols.append(xs)
        for ci, x in enumerate(xs):
            for ri, t in enumerate(t_rows(pi)):
                P, s, u = C.pos(x, t, pi, fvs[ci])
                v = bm.verts.new(P)
                v[L_sway] = C.below(P.z) ** 1.4 if lod < 3 else (1.0 if ri else 0.0)
                v[L_panel] = pi
                v[L_u] = u
                grid[(pi, ci, ri)] = v
    for pi in range(n):
        nr = len(t_rows(pi))
        for ci in range(cols_pp):
            for ri in range(nr - 1):
                q = (grid[(pi, ci, ri)], grid[(pi, ci + 1, ri)], grid[(pi, ci + 1, ri + 1)], grid[(pi, ci, ri + 1)])
                mi = band_m if (band_rows and ri == 0) or (hem_row and ri == nr - 2) else cloth_m
                _face(bm, q, mi, out=(0, 1, 0))
    if band_rows:
        for pi in range(n - 1):
            q = (grid[(pi, cols_pp, 0)], grid[(pi + 1, 0, 0)], grid[(pi + 1, 0, 1)], grid[(pi, cols_pp, 1)])
            _face(bm, q, band_m, out=(0, 1, 0))

    def cloth_point(x, z):
        pi = C.panel_of(x)
        a, b = C.edges[pi]
        xs = xcols[pi]
        zr = [C.z_of(t, pi) for t in t_rows(pi)]
        xx = min(max(x, a), b)
        ci = 0
        while ci < cols_pp - 1 and xx > xs[ci + 1]:
            ci += 1
        ri = 0
        while ri < len(zr) - 2 and z < zr[ri + 1]:
            ri += 1
        fx = min(max((xx - xs[ci]) / max(1e-9, xs[ci + 1] - xs[ci]), 0.0), 1.0)
        fz = min(max((zr[ri] - z) / max(1e-9, zr[ri] - zr[ri + 1]), 0.0), 1.0)
        g = lambda c, rr_: grid[(pi, c, rr_)].co
        P = g(ci, ri).lerp(g(ci + 1, ri), fx).lerp(g(ci, ri + 1).lerp(g(ci + 1, ri + 1), fx), fz)
        return P, pi, (xx - a) / max(1e-9, b - a)

    # ---------------- crest (mark + lettering) decal
    if crest != 'none':
        full = crest == 'kazan_full'
        top_u, bot_u = 0.92, (-0.44 if full else 0.0)
        cw = min(cloth_w * (0.48 if n <= 3 else 0.4), 0.62 * (z_band - 0.03) / (top_u - bot_u))
        zc = z_top - 0.45 * cloth_h if full else z_band - 0.5 * (z_band - 0.0)
        cz = zc - cw * (top_u + bot_u) / 2
        cz = max(0.03 - cw * bot_u, cz)
        mlod = min(3, lod + (1 if attempt >= 10 else 0))
        if lod >= 3:
            mark = [[(-0.45, 0.0), (0.45, 0.0), (0.0, 0.4)]]
        else:
            mark = KG.mark_polys('kazan' if full else crest, mlod, r)
        text = KG.lettering_tris(0) if (full and lod == 0 and attempt < 12) else []   # lettering is LOD0 only

        def decal(polys, tris, cut_cols):
            cb = bmesh.new()
            # crest space x runs left-to-right as read from the front (+Y), i.e. along world -X
            made = [cb.faces.new([cb.verts.new((-px * cw, 0.0, cz + py * cw)) for px, py in poly]) for poly in polys]
            if made:
                bmesh.ops.triangulate(cb, faces=made, quad_method='BEAUTY', ngon_method='EAR_CLIP')
            for t in tris:
                cb.faces.new([cb.verts.new((-px * cw, 0.0, cz + py * cw)) for px, py in t])
            if lod <= 2:
                cuts = sorted({x for xs in xcols for x in xs}) if cut_cols else sorted({x for a, b in C.edges for x in (a, b)})
                for x in cuts:
                    bmesh.ops.bisect_plane(cb, geom=cb.verts[:] + cb.edges[:] + cb.faces[:], plane_co=(x, 0, 0), plane_no=(1, 0, 0))
                if band_rows:
                    bmesh.ops.bisect_plane(cb, geom=cb.verts[:] + cb.edges[:] + cb.faces[:], plane_co=(0, 0, z_band), plane_no=(0, 0, 1))
                dead = [f for f in cb.faces if f.calc_center_median().z < z_band - 1e-4 and
                        not any(a - 1e-5 <= f.calc_center_median().x <= b + 1e-5 for a, b in C.edges)]
                bmesh.ops.delete(cb, geom=dead, context='FACES')
                bmesh.ops.triangulate(cb, faces=[f for f in cb.faces if len(f.verts) > 3], quad_method='BEAUTY', ngon_method='EAR_CLIP')
                bmesh.ops.dissolve_degenerate(cb, dist=1e-5, edges=cb.edges[:])
            off = {0: 0.003, 1: 0.004, 2: 0.007}.get(lod, 0.004) + (0.001 if not cut_cols else 0.0)
            vmap = {}
            for v in cb.verts:
                if lod >= 3:
                    P, pi, u = Vector((v.co.x, C.y0, v.co.z)), C.panel_of(v.co.x), 0.5
                else:
                    P, pi, u = cloth_point(v.co.x, v.co.z)
                nv = bm.verts.new(P + Vector((0, off, 0)))
                nv[L_sway] = C.below(P.z) ** 1.4
                nv[L_panel] = pi
                nv[L_u] = u
                vmap[v] = nv
            for f in cb.faces:
                vs = [vmap[v] for v in f.verts]
                if len(set(vs)) == len(vs):
                    try:
                        _face(bm, vs, crest_m, out=(0, 1, 0))
                    except ValueError:
                        pass
            cb.free()

        decal(mark, [], True)
        if text:
            decal([], text, lod > 0)          # glyphs (LOD0) are small: cut at the slits only

    # ---------------- rod + finials
    rod_len = w - 2 * fin_l
    segs = {0: 8, 1: 6, 2: 4}.get(lod, 0)
    if lod <= 2:
        mb.cylinder((0, rod_y, z_rod), rod_r, rod_len, wood, segs=segs, rot=(0, math.pi / 2, 0), cap=(lod == 2))
        if lod <= 1:
            for sx in (-1, 1):
                _finial(bm, sx, rod_len / 2, fin_l, rod_r, rod_y, z_rod, 8 if lod == 0 else 5, bronze, lod, rod)
    else:
        vs = [bm.verts.new((-w / 2, rod_y + rod_r, z_rod - rod_r)), bm.verts.new((w / 2, rod_y + rod_r, z_rod - rod_r)),
              bm.verts.new((w / 2, rod_y + rod_r, z_rod + rod_r)), bm.verts.new((-w / 2, rod_y + rod_r, z_rod + rod_r))]
        for v in vs:
            v[L_panel] = -1
        _face(bm, vs, wood, out=(0, 1, 0))

    # ---------------- brackets
    if lod <= 1:
        for sx in (-1, 1):
            _bracket(bm, sx * (cloth_w / 2 + over * 0.55), -d / 2 + 0.002, rod_y, z_rod, rod_r, bronze, lod)

    # ---------------- tabs / sleeve
    if lod <= 1:
        arc = 2
        if hang == 'tabs':
            tab_w = min(0.07, cloth_w / (n * 3.0))
            xs = [C.edges[0][0] + tab_w / 2] + [(C.edges[i][1] + C.edges[i + 1][0]) / 2 for i in range(n - 1)] + [C.edges[-1][1] - tab_w / 2]
            if n <= 3:
                xs += [(a + b) / 2 for a, b in C.edges]          # concept: 5 loops on a 2-panel noren
            for x in xs:
                _loop(bm, x, tab_w, rod_y, z_rod, rod_r + 0.003, z_top + 0.004, arc, cloth_m, L_panel)
        else:
            _loop(bm, 0.0, cloth_w, rod_y, z_rod, rod_r + 0.005, z_top + 0.002, arc + 2, band_m, L_panel)

    o = _to_object(mb, ASSET)
    me = o.data
    ca = me.color_attributes.new('kz_sway', 'FLOAT_COLOR', 'POINT')
    sw, pa, uu = me.attributes['_sway'].data, me.attributes['_panel'].data, me.attributes['_u'].data
    for i in range(len(me.vertices)):
        ca.data[i].color = (sw[i].value, max(0.0, pa[i].value) / max(1, n - 1), uu[i].value, 1.0)
    o['kz_anim'] = json.dumps({'type': 'vertex_sway', 'attrs': ['_sway', '_panel', '_u', 'kz_sway'], 'splits': n,
                               'panel_x': [[round(a, 4), round(b, 4)] for a, b in C.edges], 'band_z': round(z_band, 4)})
    o['kz_hang'] = json.dumps({'rod_z': round(z_rod, 4), 'rod_r': round(rod_r, 4), 'rod_y': round(rod_y, 4),
                               'bracket_plane_y': round(-d / 2, 4)})
    return o


def _finial(bm, sx, x_end, L, rod_r, y, z, segs, mi, lod, style='bronze'):
    """bronze end piece along X: a cylindrical cap with a domed end (wooden rod, as the concept) or a ball knob"""
    if style == 'hinoki':
        prof = [(0.0, rod_r * 1.14), (0.75, rod_r * 1.14), (1.0, rod_r * 0.75)]
    elif lod == 0:
        prof = [(0.0, rod_r * 1.05), (0.5, rod_r * 1.65), (1.0, rod_r * 0.45)]
    else:
        prof = [(0.0, rod_r * 1.1), (0.55, rod_r * 1.55), (1.0, rod_r * 0.4)]
    rings = []
    for t, rad in prof:
        x = sx * (x_end + t * L)
        rings.append([bm.verts.new((x, y + rad * math.cos(2 * math.pi * k / segs), z + rad * math.sin(2 * math.pi * k / segs))) for k in range(segs)])
    for a, b in zip(rings, rings[1:]):
        for k in range(segs):
            q = (a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k])
            c = sum((v.co for v in q), Vector()) / 4
            _face(bm, q, mi, out=(0, c.y - y, c.z - z))
    _face(bm, rings[-1], mi, out=(sx, 0, 0))


def _bracket(bm, x, y_wall, y_rod, z_rod, rod_r, mi, lod):
    """bronze hook: down the door-head plane, out under the rod, upturned lip"""
    t = 0.016
    zb = z_rod - rod_r - t / 2
    if lod == 0:
        path = [(y_wall + t / 2, z_rod + 0.032), (y_wall + t / 2, zb), (y_rod + rod_r + t * 0.5, zb + rod_r * 0.6)]
    else:
        path = [(y_wall + t / 2, zb), (y_rod + rod_r + t * 0.5, zb + rod_r * 0.6)]
    rings = []
    for i, (py, pz) in enumerate(path):
        j0, j1 = max(0, i - 1), min(len(path) - 1, i + 1)
        dy, dz = path[j1][0] - path[j0][0], path[j1][1] - path[j0][1]
        nn = math.hypot(dy, dz) or 1
        ny, nz = -dz / nn, dy / nn
        rings.append([bm.verts.new((x + sx * t / 2, py + sn * ny * t / 2, pz + sn * nz * t / 2))
                      for sx, sn in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    for a, b in zip(rings, rings[1:]):
        m = sum((v.co for v in a + b), Vector()) / 8
        for k in range(4):
            q = (a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k])
            c = sum((v.co for v in q), Vector()) / 4
            _face(bm, q, mi, out=c - m)
    _face(bm, rings[-1], mi, out=(0, 1, 0.3))
    if lod == 0:                        # wall plate of the L-bracket
        pw, ph, zc = 0.04, 0.09, z_rod - 0.005
        vs = [bm.verts.new((x - pw / 2, y_wall + 0.001, zc - ph / 2)), bm.verts.new((x + pw / 2, y_wall + 0.001, zc - ph / 2)),
              bm.verts.new((x + pw / 2, y_wall + 0.001, zc + ph / 2)), bm.verts.new((x - pw / 2, y_wall + 0.001, zc + ph / 2))]
        _face(bm, vs, mi, out=(0, 1, 0))


def _loop(bm, x, width, y, z_rod, rad, z_attach, arc, mi, L_panel):
    """cloth loop round the rod: front strap up, over the top, down the back (a tab, or the whole sleeve)"""
    pts = [(y + rad * 0.6, z_attach)]
    for k in range(arc + 1):
        ang = -0.95 + (math.pi + 1.9) * k / arc
        pts.append((y + rad * math.cos(ang), z_rod + rad * math.sin(ang)))
    if arc > 2:
        pts.append((y - rad * 0.6, z_attach - 0.01))
    L, R = [], []
    for py, pz in pts:
        a = bm.verts.new((x - width / 2, py, pz)); b = bm.verts.new((x + width / 2, py, pz))
        a[L_panel] = -1; b[L_panel] = -1
        L.append(a); R.append(b)
    for i in range(len(pts) - 1):
        q = (L[i], R[i], R[i + 1], L[i + 1])
        c = sum((v.co for v in q), Vector()) / 4
        _face(bm, q, mi, out=(0, c.y - y, c.z - z_rod) if c.z > z_attach + 0.006 else (0, 1 if c.y > y else -1, 0))
