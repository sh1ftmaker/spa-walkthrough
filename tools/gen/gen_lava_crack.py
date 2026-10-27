"""Emissive lava crack seam (lava_crack): an inset strip of dark basalt plates split by thin jagged amber
fissures, laid on cavern floors and walls (B3 cavern, lazy river). Replaces lava_crack_seam.

Targets (refs/gen/sheet-vs-lava-glass.png panel 5 "Emissive lava crack seam W 0.4 x L 8 x D 0.1 m",
1 m bar 636-740 px = 104 px/m along the strip; lookbook 12 wall seams, 14 floor seams):
  * strip 0.4 wide x 8 long x 0.1 deep (proxy w 0.4, d 8, h 0.1): length runs along Y, the glow faces +Z.
  * front view: a main crack wandering down the length plus cross cracks every 0.25-0.6 m (cells
    0.15-0.35 m across, 2-3 across the width); crack gaps 8-60 mm, the main one widest; edges jagged.
  * side view: plates 0.06-0.1 m proud of the glowing bed; the outline of the strip is irregular.
  * colour: near-black rock tops (basalt_dry, dark in the current library), hot amber gaps (1600 K),
    plate edges with orange veins.

Construction (one mesh):
  * glow bed   - flat ribbon under the plates (z 0.045, 15-50 mm under the tops so the lava shows at grazing
                 views), slot `glow` (bright amber emitter).
  * plates     - Voronoi cells of seeded points in 2-4 columns, each cell clipped by the bisectors shifted
                 by half the crack gap (so the gaps are real geometry), jagged by subdividing every cell edge
                 with inward jitter, extruded to 0.06-0.1 m with a seeded tilt; tops `rock` (basalt_dry),
                 sides `edge` (lava with an orange tint: glowing crack walls). Open bottom: the strip is inset.
Materials: glow   lava_molten, emissive_level = glow (default 1.1), scale 1.0 m (rafts small in thin gaps)
           rock   basalt_dry        edge   lava tint (1.0, 0.35, 0.15)

Parameters (build kwargs):
  w        strip width 0.05-0.4 m (default 0.4)       length   0.5-8 m (default 8, the proxy)
  branching cross-crack density 0.5-2.0 (default by style; scales the cell spacing along the strip)
  glow     emissive level 0.6-1.3 (default 1.1)        path     optional [(x, y), ...] polyline in the
           host plane; the strip is bent along it (default: straight along Y)
  style    'seam' | 'braided' | 'web' | 'fissure' (default seed-cycled; 4 seeds):
           seam = one zigzag main crack with cross cracks; braided = two wandering parallel cracks with
           links; web = a crazed network of small cells; fissure = one wide meandering main crack, 70 % of the cross joints closed.
Seeds change shape: style, cell spacing, column offsets, crack widths, plate heights and tilt, outline.

LODs (row budget is per metre: 200 / 80 / 30 / 10 tris per m -> 1600 / 640 / 240 / 80 for the 8 m default;
same cells at LOD0-2): LOD0 jagged edges (1-3 cuts per cell edge) with crack walls, LOD1 straight edges with
walls (web style: tops only), LOD2 flat tops (5-point tops when the budget is tight), LOD3 one dark strip per
column whose inner edges follow the cells, over the glowing bed: the main crack(s) stay as glowing lines.
Edge jag / walls fall back on resolution to fit the per-metre budget, printed when it happens.
Animation (shader, slow pulse): `kz_heat` (FLOAT, POINT) 1.0 bed, 0.6 crack-wall bottoms, 0 tops;
`kz_pulse` (FLOAT, POINT) phase 0-1 along the strip with noise, packed with heat into colour attribute
`kz_pulse_col` (heat, phase, 0, 1). obj['kz_anim'] = {type shader, period_s, amp, attrs}.
Lights: kz_lights one 'area' strip light over the seam (1600 K, 40 W per 8 m, scaled by length).
"""
import math

import bmesh
import bpy
from mathutils import Vector

import genlib
import kzgeo_common as C

ASSET = 'lava_crack'
FEATURES = ['thin jagged glowing fissures', 'dark rock plates', 'main crack along the strip', 'amber glow']
STYLES = ['seam', 'braided', 'web', 'fissure']
TINT_EDGE = (1.0, 0.35, 0.15)
PER_M = [200, 80, 30, 10]
BED_Z = 0.045          # glow bed 15-50 mm under the plate tops: the cracks read lit from a 25 deg grazing view


def kelvin_rgb(k):
    t = k / 100.0
    r = 255.0 if t <= 66 else 329.7 * (t - 60) ** -0.1332
    g = 99.47 * math.log(t) - 161.12 if t <= 66 else 288.12 * (t - 60) ** -0.0755
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.52 * math.log(t - 10) - 305.04)
    c = [max(0.0, min(255.0, x)) / 255.0 for x in (r, g, b)]
    m = max(c)
    return [round(x / m, 3) for x in c]


def clip(poly, a, b, c):
    """keep the part of a convex polygon with a*x + b*y <= c"""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        fp, fq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if fp <= 0:
            out.append(p)
        if (fp < 0 < fq) or (fq < 0 < fp):
            t = fp / (fp - fq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))


def layout(seed, W, Lm, style, branching):
    g = C.rng(seed, 'cells')
    br = branching if branching is not None else {'seam': 1.0, 'braided': 1.1, 'web': 1.0, 'fissure': 0.6}[style]
    cols = {'seam': 2, 'braided': 3, 'web': 3, 'fissure': 2}[style]
    step = {'seam': 0.34, 'braided': 0.42, 'web': 0.32, 'fissure': 0.3}[style] / br * g.uniform(0.9, 1.15)
    step = min(step, W * 2.2) if W < 0.2 else step
    pts = []
    if style == 'web':
        for ci in range(cols):
            xc = -W / 2 + W * (ci + 0.5) / cols
            y = -Lm / 2 + g.uniform(0, step)
            while y < Lm / 2:
                jx = W / cols * 0.32
                pts.append((xc + g.uniform(-jx, jx), y + g.uniform(-0.25, 0.25) * step, ci))
                y += step * g.uniform(0.8, 1.25)
    else:
        # rows shared by the columns (no sawtooth) and a slow seeded meander of the whole column set,
        # so the main crack(s) wander down the strip like the panel-5 seam
        lam = g.uniform(1.6, 3.2); ph = g.uniform(0, 2 * math.pi); A = W / cols * g.uniform(0.25, 0.4)
        lam2 = g.uniform(0.5, 0.9); ph2 = g.uniform(0, 2 * math.pi)
        y = -Lm / 2 + g.uniform(0, step) * 0.5
        while y < Lm / 2:
            mx = A * math.sin(2 * math.pi * y / lam + ph) + 0.35 * A * math.sin(2 * math.pi * y / lam2 + ph2)
            for ci in range(cols):
                xc = -W / 2 + W * (ci + 0.5) / cols + mx
                pts.append((xc + g.uniform(-0.08, 0.08) * W / cols, y + g.uniform(-0.18, 0.18) * step, ci))
            y += step * g.uniform(0.8, 1.25)
    # crack widths per column pair: the main crack (between columns at the middle) is the widest
    main_w = {'seam': (0.025, 0.045), 'braided': (0.02, 0.035), 'web': (0.012, 0.025), 'fissure': (0.045, 0.07)}[style]
    cross_w = {'seam': (0.01, 0.022), 'braided': (0.01, 0.02), 'web': (0.008, 0.018), 'fissure': (0.012, 0.025)}[style]
    scale = min(1.0, W / 0.4) ** 0.5
    rect = [(-W / 2, -Lm / 2), (W / 2, -Lm / 2), (W / 2, Lm / 2), (-W / 2, Lm / 2)]
    gw = C.rng(seed, 'gaps')
    gaps = {}
    cells = []
    for i, (x, y, ci) in enumerate(pts):
        poly = list(rect)
        for j, (x2, y2, cj) in enumerate(pts):
            if i == j or abs(y2 - y) > step * 3 + W:
                continue
            key = (min(i, j), max(i, j))
            if key not in gaps:
                lo, hi = main_w if ci != cj else cross_w
                gaps[key] = gw.uniform(lo, hi) * scale
                if style == 'fissure' and ci == cj and gw.random() < 0.7:
                    gaps[key] = 0.0          # most cross joints closed: one long meandering fissure
            dx, dy = x2 - x, y2 - y
            d = math.hypot(dx, dy)
            a, b = dx / d, dy / d
            mx, my = (x + x2) / 2, (y + y2) / 2
            poly = clip(poly, a, b, a * mx + b * my - gaps[key] / 2)
            if len(poly) < 3:
                break
        if len(poly) >= 3 and abs(area(poly)) > 0.0015:
            if area(poly) < 0:
                poly = poly[::-1]
            gc = C.rng(seed * 1000 + i, 'plate')
            cells.append(dict(poly=poly, c=(x, y), col=ci, h=gc.uniform(0.06, 0.095), tx=gc.uniform(-0.05, 0.05),
                              ty=gc.uniform(-0.03, 0.03), jag=[gc.uniform(-1, 1) for _ in range(64)],
                              phase=(y / Lm + 0.5 + gc.uniform(-0.08, 0.08)) % 1.0))
    return cells, step, cols


def simplify(poly, k):
    """drop the vertex spanning the smallest triangle until k remain (keeps the cell's shape)"""
    poly = list(poly)
    while len(poly) > k:
        n = len(poly)
        i = min(range(n), key=lambda i: abs(area([poly[i - 1], poly[i], poly[(i + 1) % n]])))
        poly.pop(i)
    return poly


def jagged(poly, cuts, amp, jag, cen, bound=lambda p: False):
    """subdivide each edge, pushing the new points toward the cell centre by up to amp (never outward,
    so the crack never closes)"""
    out = []
    k = 0
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        out.append(p)
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        nc = min(cuts, int(L / 0.03))
        if bound(p) and bound(q):
            nc = 0                   # the strip's outer edge stays flush with the bed edge
        for s in range(1, nc + 1):
            t = s / (nc + 1)
            x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
            dx, dy = cen[0] - x, cen[1] - y
            dd = math.hypot(dx, dy) or 1
            push = amp * (0.5 + 0.5 * jag[k % len(jag)]) * min(1.0, L / 0.12)
            out.append((x + dx / dd * push, y + dy / dd * push))
            k += 1
    return out


def to_object(mb, name):
    me = bpy.data.meshes.new(name); mb.bm.to_mesh(me); mb.bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    import matlib
    for i, (mid, params) in enumerate(mb.slots):
        matlib.assign(o, mid, slot=i, **params)
    return o


def build(lod=0, seed=1, w=None, length=None, branching=None, glow=1.1, path=None, style=None, d=None, h=None):
    p = genlib.proxy(ASSET)
    W = float(w or p['w']); Lm = float(length or d or p['d'])
    style = style or C.cycle(seed, STYLES)
    cells, step, cols = layout(seed, W, Lm, style, branching)
    gap_main = {'seam': 0.035, 'braided': 0.028, 'web': 0.02, 'fissure': 0.058}[style] * min(1.0, W / 0.4) ** 0.5
    mb = genlib.MeshBuilder(); bm = mb.bm
    m_glow = mb.slot('lava_molten', emissive_level=round(float(glow), 3), scale=1.0)
    m_rock = mb.slot('basalt_dry')
    m_edge = mb.slot('lava', tint=TINT_EDGE)
    L_heat = bm.verts.layers.float.new('kz_heat')
    L_pulse = bm.verts.layers.float.new('kz_pulse')
    # bed
    nb = max(1, int(Lm / 0.5)) if lod < 3 else max(1, int(Lm / 2))
    bed = []
    for k in range(nb + 1):
        y = -Lm / 2 + Lm * k / nb
        row = [bm.verts.new((x, y, BED_Z)) for x in (-W / 2 + 0.003, W / 2 - 0.003)]
        for v in row:
            v[L_heat] = 1.0; v[L_pulse] = (k / nb) % 1.0
        bed.append(row)
    fs = [bm.faces.new((bed[k][0], bed[k][1], bed[k + 1][1], bed[k + 1][0])) for k in range(nb)]
    mb._tag(fs, m_glow)
    # plates: pick the jag resolution from the per-metre budget
    budget = int(PER_M[lod] * Lm)
    left = budget - C.tri_count(bm)
    opts = {0: [(3, True), (2, True), (1, True), (0, True)], 1: [(1, True), (0, True), (-1, True), (0, False)],
            2: [(0, False), (-1, False)], 3: [(-2, False)]}[lod]

    def cost(o):
        t = 0
        if o[0] == -2:
            return 2 * cols * (max(2, int(Lm / 0.8)) - 1)
        for c in cells:
            n = len(c['poly']) if o[0] >= 0 else min(5, len(c['poly']))
            if o[0] > 0:
                n += sum(min(o[0], int(math.hypot(c['poly'][(i + 1) % len(c['poly'])][0] - c['poly'][i][0],
                                                  c['poly'][(i + 1) % len(c['poly'])][1] - c['poly'][i][1]) / 0.03))
                         for i in range(len(c['poly'])))
            t += (n - 2) + (2 * n if o[1] else 0)
        return t
    choice = next((o for o in opts if cost(o) <= left), opts[-1])
    if choice != opts[0]:
        print(f'{ASSET} LOD{lod} seed {seed}: plate edges at {choice} (budget left {left})')
    cuts, sides = choice
    amp = {'web': 0.012, 'fissure': 0.02}.get(style, 0.016) * min(1.0, W / 0.4)
    if cuts == -2:
        # LOD3: one dark strip per column; adjacent strips meet at the bisector of the two nearest seeds
        # (the main crack line), leaving that crack's gap open over the glowing bed
        ns = max(2, int(Lm / 0.8))
        rows_x = []
        for k in range(ns):
            y = -Lm / 2 + Lm * k / (ns - 1)
            xs = [(-W / 2, 0.0)]
            for ci in range(cols - 1):
                a_ = min((c for c in cells if c['col'] == ci), key=lambda c: abs(c['c'][1] - y))
                b_ = min((c for c in cells if c['col'] == ci + 1), key=lambda c: abs(c['c'][1] - y))
                (ax, ay), (bx, by) = a_['c'], b_['c']
                xm = ((bx * bx - ax * ax) + (by * by - ay * ay) - 2 * y * (by - ay)) / (2 * (bx - ax)) if abs(bx - ax) > 1e-4 else (ax + bx) / 2
                xm = max(-W / 2 + 0.02, min(W / 2 - 0.02, xm))
                xs.append((xm, gap_main / 2))
            xs.append((W / 2, 0.0))
            rows_x.append((y, xs))
        for ci in range(cols):
            rows = []
            for y, xs in rows_x:
                x0 = xs[ci][0] + xs[ci][1]; x1 = xs[ci + 1][0] - xs[ci + 1][1]
                row = [bm.verts.new((x, y, 0.08)) for x in (x0, max(x0 + 0.005, x1))]
                for v in row:
                    v[L_heat] = 0.0; v[L_pulse] = (y / Lm + 0.5) % 1.0
                rows.append(row)
            fs = [bm.faces.new((rows[k][0], rows[k][1], rows[k + 1][1], rows[k + 1][0])) for k in range(ns - 1)]
            mb._tag(fs, m_rock)
    for c in (cells if cuts > -2 else []):
        poly = c['poly']
        if cuts < 0:     # 5-point outline: keeps the cell and its gaps for budget-tight LODs
            poly = simplify(poly, 5)
        elif cuts > 0:
            poly = jagged(poly, cuts, amp, c['jag'], c['c'], lambda q: abs(abs(q[0]) - W / 2) < 1e-4 or abs(abs(q[1]) - Lm / 2) < 1e-4)
        cx, cy = c['c']
        top = [bm.verts.new((x, y, c['h'] + c['tx'] * (x - cx) + c['ty'] * (y - cy))) for x, y in poly]
        for v in top:
            v[L_heat] = 0.0; v[L_pulse] = c['phase']
        ft = bm.faces.new(top)
        mb._tag([ft], m_rock)
        if sides:
            bot = [bm.verts.new((x, y, 0.0)) for x, y in poly]
            for v in bot:
                v[L_heat] = 0.6; v[L_pulse] = c['phase']
            n = len(poly)
            fs = [bm.faces.new((bot[k], bot[(k + 1) % n], top[(k + 1) % n], top[k])) for k in range(n)]
            mb._tag(fs, m_edge)
    for f in bm.faces:
        f.normal_update()
        if f.material_index in (m_glow, m_rock) and f.normal.z < 0:
            f.normal_flip()
    # optional bend along a host path (x, y) polyline: strip y -> arc length, strip x -> normal offset
    if path:
        pts = [Vector((px, py, 0)) for px, py in path]
        seg = [(pts[i], pts[i + 1], (pts[i + 1] - pts[i]).length) for i in range(len(pts) - 1)]
        tot = sum(s[2] for s in seg)
        for v in bm.verts:
            s = (v.co.y + Lm / 2) / Lm * tot
            for a, b, ln in seg:
                if s <= ln or (a, b, ln) == seg[-1]:
                    t = (b - a).normalized(); nrm = Vector((-t.y, t.x, 0))
                    q = a + t * s + nrm * v.co.x
                    v.co.x, v.co.y = q.x, q.y
                    break
                s -= ln
    C.centre_base(mb)
    o = to_object(mb, ASSET)
    me = o.data
    col = me.color_attributes.new('kz_pulse_col', 'FLOAT_COLOR', 'POINT')
    ha, pa = me.attributes['kz_heat'], me.attributes['kz_pulse']
    for i in range(len(me.vertices)):
        col.data[i].color = (ha.data[i].value, pa.data[i].value, 0.0, 1.0)
    gpulse = C.rng(seed, 'pulse')
    C.set_json_props(o, kz_anim=dict(type='shader', what='slow pulse of the crack glow', heat_attr='kz_heat',
                                     phase_attr='kz_pulse', color_attr='kz_pulse_col', period_s=round(gpulse.uniform(4.0, 7.0), 2),
                                     amp=0.25, travel='phase runs along the strip (a slow wave)', slot=m_glow),
                     kz_lights=[C.light_entry((0, 0, 0.08), color_k=1600, watts=round(40 * Lm / 8, 1), kind='area',
                                              size=[round(W, 3), round(Lm, 3)], normal=[0, 0, 1], color=kelvin_rgb(1600))],
                     kz_snap='surface', kz_params=dict(style=style, w=W, length=Lm, cells=len(cells), cols=cols,
                                                       step=round(step, 3), glow=glow, edge_cuts=cuts,
                                                       budget_per_m=PER_M, path=bool(path)))
    genlib.finish(o, smooth_angle=30)
    return o
