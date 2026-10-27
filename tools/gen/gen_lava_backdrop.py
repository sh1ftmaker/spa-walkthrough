"""Lava field behind glass (lava_backdrop): the molten landscape seen through every lava window, the magma
glass wall, the summit lodge glass and the slide foot. 2.5D relief, never walked; authored geometry plus
flow-map data that the web runtime scrolls.

Targets (refs/gen/sheet-vs-lava-glass.png panel 2 "Lava field behind glass, W 34 x D 20 x H 12 m";
lookbook 04 right-hand glass, 13 slide-foot glass, 23 B4 chamber, 11 summit lodge glass):
  * box 34 x 20 x 12 m (proxy); viewer side is +Y (the glass), the far cliff is at -Y.
  * far: a dark crusted cliff wall rising to ~12 m with 1-4 bright lava falls 1.2-3.5 m wide pouring from
    glowing ledges at 55-90 % of the height (04, 13, panel 2 front);
  * mid: an orange-yellow molten field broken into dark crust plates 0.6-2 m across with glowing gaps,
    1-3 brighter rivers 1.2-3 m wide meandering from the fall feet to the glass (04, 13, 23);
  * a distant rock arch (1-2 spans, 7-12 m) carrying a bridge with a row of warm lanterns (04: "rock arches
    and lit bridges in the distance"; panel 2 front/side);
  * near: black basalt silhouettes at the front corners and a few low rocks along the glass (panel 2,
    13 foreground of the glass), dark side walls framing the box.
  The concept field reads ~55-70 % glowing area at mid distance (04 / 13 measured on the glass crops), so the
  default crust coverage is 0.4-0.6 and the gaps between plates are 0.15-0.45 m.

Construction (one mesh):
  * molten sheet  - grid following the floor relief (z rises 0.3 m at the glass -> 1.5-3.2 m at the cliff
                    foot, relief amp 0.1-1.0 m), river channels sunk 0.25 m. Slot `molten`.
  * river cores   - ribbons 62 % of the river width on the sunk channel. Slot `hot`.
  * crust plates  - irregular 8-gon prisms, domed tops, seeded tilt, sitting on the floor with gaps; no plate
                    in a river or under the cliff. Slot `crust_top` (lava_flow) / `crust_side` (lava).
  * cliff         - (x, z) grid with a ragged top, pushed forward by seeded bulges and a ledge band whose
                    height wanders +-1.3 m along x; slot `cliff` (lava crust, orange veins).
  * falls         - ribbons 0.25 m in front of the cliff from the ledge / top to the floor, 3-4 streak columns
                    alternating `hot` / `molten`, ragged edges, widening 35 % toward the foot.
  * arch + bridge - rock tubes (7 sides, thicker legs) with a humped deck swept along the arch crowns
                    (0.12-0.88 pi of each span) and lantern boxes on posts on both edges (`lantern`).
  * side walls    - (y, z) grids at x = +-W/2 rising toward the back (`rock`).
  * near rocks    - faceted hulls (C.hull_rock) at the front corners and along the glass (`rock`).

Materials (library ids; slot names by part):
  molten   lava_molten (library, bright orange-yellow field with dark crust rafts; swatch #ae7720 mean)
  hot      lava_molten emissive_level 1.3 (river cores, fall streaks; #b98335 mean)
  crust_top  lava_flow (dark crust, faint veins)        crust_side lava tint (1.0, 0.35, 0.15) (hot edges)
  cliff      lava tint (1.0, 0.35, 0.15) (veins read orange, not white)   rock  basalt_dry (near rocks, arch, walls)
  lantern    lantern_andon_plain (bridge lanterns)

Parameters (build kwargs; defaults are the proxy and the seeded style):
  w, d, h      box 8-34 x 6-20 x 4-12 m (default 34 x 20 x 12)
  relief       floor relief amplitude 0.1-1.0 m (default seeded 0.25-0.6)
  rivers       flow paths 0-3 (default by style)
  falls        fall count 0-4 (default by style)
  crust        crust coverage 0.3-0.8 (default by style)
  arch         distant arch on/off (default by style); arch_spans 1-2
  style        'cascade' | 'gorge' | 'field' | 'delta' (default seed-cycled; 4 seeds = 4 styles):
               cascade = 3-4 falls over a high ledge, 1-2 rivers, single arch;
               gorge   = 2 falls, 2 rivers converging, high side walls, two-span viaduct;
               field   = 0-1 fall, a wide molten lake with sparse plates (crust 0.35), no arch, low cliff;
               delta   = 2 falls, 3 braided rivers, dense crust 0.65, single arch.
Seeds change shape: style (above), fall positions / widths / heights, river meanders, ledge height, cliff
bulges, plate layout and size, arch position / span / height, rock layout.

LODs (budget 8000 / 3200 / 960 / 200; derived from one layout):
  LOD0 full grids, 8-gon domed plates, 7-sided arch, lanterns, 14-point rocks.
  LOD1 half grids, 6-gon plates (all), 6-sided arch, lanterns, 9-point rocks.
  LOD2 quarter grids, the largest 45 % of the plates as 5-gon tops with sides, 5-sided arch, deck, no lanterns.
  LOD3 coarse grids, the 12 largest plates as flat 5-gon tops, falls and river cores as single strips,
       3-sided arch + flat deck, the 6 largest rocks.  Falls, rivers, arch and glow kept at every LOD.

Animation (shader, flow-map scroll): per-vertex attribute `kz_flow` (FLOAT_VECTOR, POINT): unit flow
direction x speed factor (rivers 1.0 along the river tangent, open field 0.35 down-slope toward +Y, falls
1.0 straight down (0, 0, -1), ledges 0.25); `kz_heat` (FLOAT, POINT): 1.0 hot core / falls, 0.8 molten
sheet, 0.25 crust sides, 0 rock. Colour attribute `kz_flow_col` packs (0.5 + 0.5 * flow.xyz, heat) for
exporters that keep only colours. obj['kz_anim'] = {type: 'shader', what: 'flow-map emissive lava',
flow_attr, speeds (m/s), slots}. No moving geometry.
Lights: obj['kz_lights']: one area light on the glass plane (normal +Y, 1600 K) sized to the box front plus
one point per fall; emissive lights the bake.
"""
import json
import math

import bmesh
import bpy
from mathutils import Vector

import genlib
import kzgeo_common as C

ASSET = 'lava_backdrop'
FEATURES = ['glowing lava rivers', 'lava falls', 'dark crust plates with glowing gaps', 'dark crusted cliff',
            'distant rock arch with lit bridge', 'near rock silhouettes']
STYLES = ['cascade', 'gorge', 'field', 'delta']

RES = {
    0: dict(cliff=(44, 14), side=(12, 8), sheet=(34, 20), plate_n=8, dome=True, plate_keep=1.0, sides=True,
            fall=(4, 14), river_st=34, arch=(20, 7), deck=True, lanterns=True, rock_n=14, rocks_keep=99),
    1: dict(cliff=(22, 7), side=(6, 4), sheet=(17, 10), plate_n=6, dome=False, plate_keep=1.0, sides=True,
            fall=(3, 7), river_st=16, arch=(12, 6), deck=True, lanterns=True, rock_n=9, rocks_keep=99),
    2: dict(cliff=(11, 4), side=(3, 2), sheet=(9, 5), plate_n=5, dome=False, plate_keep=0.45, sides=True,
            fall=(2, 3), river_st=8, arch=(8, 5), deck=True, lanterns=False, rock_n=6, rocks_keep=99),
    3: dict(cliff=(5, 2), side=(1, 1), sheet=(5, 3), plate_n=5, dome=False, plate_keep=12, sides=False,
            fall=(1, 1), river_st=4, arch=(5, 3), deck=True, lanterns=False, rock_n=5, rocks_keep=6),
}

TINT_CRUST = (1.0, 0.35, 0.15)        # pushes the lava veins from white-hot to orange (emission x tint)


# ------------------------------------------------------------------ small tools
def kelvin_rgb(k):
    t = k / 100.0
    r = 255.0 if t <= 66 else 329.7 * (t - 60) ** -0.1332
    g = 99.47 * math.log(t) - 161.12 if t <= 66 else 288.12 * (t - 60) ** -0.0755
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.52 * math.log(t - 10) - 305.04)
    c = [max(0.0, min(255.0, x)) / 255.0 for x in (r, g, b)]
    m = max(c)
    return [round(x / m, 3) for x in c]


def noise2(r, n=5, f0=0.12, f1=0.6):
    """smooth 2D noise in [-1, 1]: a sum of seeded oblique sines"""
    waves = []
    for k in range(n):
        f = f0 * (f1 / f0) ** (k / max(1, n - 1))
        a = r.uniform(0, math.pi)
        waves.append((f * math.cos(a), f * math.sin(a), r.uniform(0, 2 * math.pi), 1.0 / (1 + k * 0.6)))
    tot = sum(w[3] for w in waves)
    return lambda x, y: sum(w[3] * math.sin(w[0] * x + w[1] * y + w[2]) for w in waves) / tot * 1.6


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def orient(faces, d):
    """make a sheet face toward d (reverse all if the mean normal points away)"""
    s = Vector()
    for f in faces:
        f.normal_update(); s += f.normal * f.calc_area()
    if s.dot(Vector(d)) < 0:
        for f in faces:
            f.normal_flip()
            f.normal_update()


def grid(mb, nu, nv, P, mi):
    bm = mb.bm
    V = [[bm.verts.new(P(i / nu, j / nv)) for j in range(nv + 1)] for i in range(nu + 1)]
    faces = []
    for i in range(nu):
        for j in range(nv):
            faces.append(bm.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1])))
    mb._tag(faces, mi)
    return V, faces


def to_object(mb, name):
    """genlib.MeshBuilder.to_object without the global normal recalculation (open sheets keep the
    winding set by orient(); recalc flips whole open islands unpredictably)."""
    me = bpy.data.meshes.new(name); mb.bm.to_mesh(me); mb.bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    import matlib
    for i, (mid, params) in enumerate(mb.slots):
        matlib.assign(o, mid, slot=i, **params)
    return o


# ------------------------------------------------------------------ layout (LOD independent)
def layout(seed, W, D, H, style, relief, n_rivers, n_falls, crust, arch, arch_spans):
    g = C.rng(seed, 'shape')
    L = dict(W=W, D=D, H=H, style=style)
    z_front = 0.3
    z_back = {'cascade': g.uniform(1.6, 2.6), 'gorge': g.uniform(1.2, 2.0), 'field': g.uniform(1.0, 1.6),
              'delta': g.uniform(2.0, 3.2)}[style] * H / 12
    relief = relief if relief is not None else g.uniform(0.25, 0.6)
    nf = noise2(C.rng(seed, 'floor'), 6, 0.15, 0.9)
    L.update(z_front=z_front, z_back=z_back, relief=relief)
    # cliff
    gc = C.rng(seed, 'cliff')
    ncl = noise2(gc, 6, 0.12, 0.8)
    ledge_z = H * gc.uniform(0.55, 0.72) if style != 'field' else H * gc.uniform(0.4, 0.5)
    ledge_d = gc.uniform(1.0, 1.8)
    L.update(ledge_z=ledge_z, ledge_d=ledge_d)
    yb = -D / 2

    lph = (gc.uniform(0, 6.3), gc.uniform(0, 6.3))
    ledge_at = lambda x: ledge_z + 0.9 * math.sin(x * 0.22 + lph[0]) + 0.45 * math.sin(x * 0.61 + lph[1])
    L['ledge_at'] = ledge_at
    top_at = lambda x: H - 0.9 * (1.2 + math.sin(x * 0.33 + lph[1]) + 0.6 * math.sin(x * 0.9 + lph[0])) / 2.8 - 0.05

    def cliff_y(x, z):
        lz = ledge_at(x)
        bul = 0.5 + 0.9 * (0.5 + 0.5 * ncl(x * 0.8, z))
        led = ledge_d * smooth((lz - z) / 1.6 + 1) if z < lz + 0.2 else ledge_d * (1 - smooth((z - lz) / 0.5)) * 0.4
        notch = 0.0
        for fx, fw, *_ in L.get('falls', []):
            notch -= 0.6 * math.exp(-((x - fx) / (0.6 * fw)) ** 2)
        return yb + bul + led * (0.7 + 0.3 * math.sin(x * 0.4 + 1.3)) + notch

    # falls
    gf = C.rng(seed, 'falls')
    nfalls = n_falls if n_falls is not None else {'cascade': gf.choice([3, 4]), 'gorge': 2,
                                                  'field': gf.choice([0, 1]), 'delta': 2}[style]
    falls = []
    for k in range(nfalls):
        for _ in range(40):
            fx = gf.uniform(-W * 0.36, W * 0.36)
            if all(abs(fx - f[0]) > W * 0.16 for f in falls):
                break
        fw = gf.uniform(1.2, 3.5) * min(1.0, W / 20)
        ztop = ledge_at(fx) + 0.15 if gf.random() < 0.6 else top_at(fx) - gf.uniform(0.3, 1.0)
        falls.append((fx, fw, ztop))
    falls.sort()
    L['falls'] = falls
    L['ledge_run'] = {round(f[0], 3): (gf.uniform(1.0, 2.6), gf.uniform(1.0, 2.6)) for f in falls}
    # rivers
    gr = C.rng(seed, 'rivers')
    nriv = n_rivers if n_rivers is not None else {'cascade': gr.choice([1, 2]), 'gorge': 2, 'field': 1, 'delta': 3}[style]
    rivers = []
    for k in range(nriv):
        if falls:
            src = falls[k % len(falls)][0] + (gr.uniform(-1, 1) if k >= len(falls) else 0.0)
        else:
            src = gr.uniform(-W * 0.3, W * 0.3)
        if style == 'gorge':
            end = gr.uniform(-W * 0.06, W * 0.06) + (k - 0.5) * 2.5
        elif style == 'delta':
            end = (k - (nriv - 1) / 2) * W * 0.28 + gr.uniform(-1.5, 1.5)
        else:
            end = src * gr.uniform(0.3, 0.8) + gr.uniform(-W * 0.12, W * 0.12)
        amp = gr.uniform(1.0, 3.0) * min(1.0, W / 20)
        fq = gr.uniform(0.7, 1.6); ph = gr.uniform(0, 2 * math.pi)
        w0, w1 = gr.uniform(1.0, 1.6), gr.uniform(1.8, 3.0)
        if style == 'field':
            w1 *= 1.3
        rivers.append(dict(src=src, end=end, amp=amp, fq=fq, ph=ph, w0=w0, w1=w1))
    L['rivers'] = rivers

    def river_xy(rv, t):
        y0 = cliff_y(rv['src'], z_back) + 0.4
        y = y0 + (D / 2 - y0) * t
        x = rv['src'] + (rv['end'] - rv['src']) * smooth(t) + rv['amp'] * math.sin(2 * math.pi * rv['fq'] * t + rv['ph']) * math.sin(math.pi * min(1, t * 1.6))
        return x, y

    # dense river samples for distance queries
    rsamp = []
    for ri, rv in enumerate(rivers):
        pts = [river_xy(rv, k / 60) for k in range(61)]
        for k, (x, y) in enumerate(pts):
            a = pts[max(0, k - 1)]; b = pts[min(60, k + 1)]
            tx, ty = b[0] - a[0], b[1] - a[1]; ln = math.hypot(tx, ty) or 1
            rsamp.append((x, y, tx / ln, ty / ln, rv['w0'] + (rv['w1'] - rv['w0']) * k / 60, ri))

    def river_q(x, y):
        """(distance to nearest river centre, half width there, tangent)"""
        best = (1e9, 1.0, (0.0, 1.0))
        for sx, sy, tx, ty, w, _ in rsamp:
            dd = (x - sx) ** 2 + (y - sy) ** 2
            if dd < best[0]:
                best = (dd, w / 2, (tx, ty))
        return math.sqrt(best[0]), best[1], best[2]

    def zf(x, y, channel=True):
        t = max(0.0, min(1.0, (D / 2 - y) / D))
        z = z_front + (z_back - z_front) * t ** 1.3 + relief * nf(x, y) * (0.4 + 0.6 * t)
        if channel and rivers:
            dist, hw, _ = river_q(x, y)
            z -= 0.25 * math.exp(-(dist / max(0.3, hw * 1.2)) ** 2)
        return z

    L.update(top_at=top_at, cliff_y=cliff_y, river_xy=river_xy, river_q=river_q, zf=zf)
    # arch
    ga = C.rng(seed, 'arch')
    has_arch = arch if arch is not None else style != 'field'
    spans = arch_spans if arch_spans is not None else (2 if style == 'gorge' else 1)
    if has_arch:
        span = ga.uniform(7.0, 10.0) * min(1.0, W / 24)
        ax = ga.uniform(-W * 0.18, W * 0.18)
        if rivers:
            ax = 0.5 * ax + 0.5 * river_xy(rivers[0], 0.25)[0]
        tot = span * spans
        ax = max(-W / 2 + tot / 2 + 1.5, min(W / 2 - tot / 2 - 1.5, ax))
        ay = yb + ga.uniform(4.6, 5.6) * D / 20 + 2.0
        rise = ga.uniform(4.0, 5.5) * H / 12
        rad = ga.uniform(0.7, 0.95)
        L['arch'] = dict(x=ax, y=ay, span=span, spans=spans, rise=rise, rad=rad, tot=tot)
    else:
        L['arch'] = None
    # plates: jittered candidates, coverage by noise quantile
    gp = C.rng(seed, 'plates')
    crust = crust if crust is not None else {'cascade': gp.uniform(0.62, 0.7), 'gorge': gp.uniform(0.66, 0.74),
                                             'field': 0.4, 'delta': 0.78}[style]
    L['crust'] = crust
    ncov = noise2(C.rng(seed, 'cover'), 4, 0.15, 0.5)
    cands = []
    y = D / 2 - 0.5
    while y > yb + 0.5:
        t = (D / 2 - y) / D
        s = 1.3 + 1.0 * t
        x = -W / 2 + 0.6 + gp.uniform(0, s * 0.5)
        while x < W / 2 - 0.6:
            px, py = x + gp.uniform(-0.3, 0.3) * s, y + gp.uniform(-0.3, 0.3) * s
            r = 0.6 * s * gp.uniform(0.85, 1.12)
            cands.append([px, py, r, gp.uniform(0.08, 0.22), gp.uniform(-0.05, 0.05), gp.uniform(-0.05, 0.05),
                          gp.uniform(0, 2 * math.pi), [gp.uniform(0, 2 * math.pi) for _ in range(4)], gp.uniform(0.0, 1.0)])
            x += s
        y -= s * 0.88
    ok = []
    for c in cands:
        px, py, r = c[0], c[1], c[2]
        if abs(px) > W / 2 - r * 0.8:
            continue
        if py - r < cliff_y(px, zf(px, py, False)) + 0.3:
            continue
        if rivers:
            dist, hw, _ = river_q(px, py)
            if dist < hw + r * 0.45 + 0.15:
                continue
        if L['arch']:
            A = L['arch']
            legs = [A['x'] - A['tot'] / 2 + A['span'] * k for k in range(A['spans'] + 1)]
            if abs(py - A['y']) < r + A['rad'] * 1.6 and any(abs(px - lx) < r + A['rad'] * 1.6 for lx in legs):
                continue
        ok.append(c)
    ok.sort(key=lambda c: 0.2 * ncov(c[0], c[1]) + c[8])
    plates = ok[:int(round(len(ok) * min(1.0, crust / 0.8)))]    # crust 0.8 = every candidate
    L['plates'] = plates
    # near rocks
    gk = C.rng(seed, 'rocks')
    rocks = []
    nr = gk.randint(5, 7)
    for side in (-1, 1):
        for k in range(nr if side < 0 else nr - 1):
            sx = gk.uniform(1.0, 2.6); sy = gk.uniform(0.8, 1.7); sz = gk.uniform(1.0, 2.6) * (1.0 - 0.12 * k)
            x = side * (W / 2 - 0.4 - sx * 0.7 - gk.uniform(0, 4.0) * (k / nr) * 1.6)
            yk = D / 2 - sy - gk.uniform(0, 3.0)
            rocks.append((x, yk, sx, sy, sz))
    for k in range(gk.randint(6, 8)):
        for _ in range(30):
            x = gk.uniform(-W * 0.4, W * 0.4)
            if not rivers or all(abs(x - river_xy(rv, 1.0)[0]) > rv['w1'] + 1.2 for rv in rivers):
                break
        rocks.append((x, D / 2 - gk.uniform(0.7, 1.6), gk.uniform(0.6, 1.4), gk.uniform(0.5, 0.9), gk.uniform(0.35, 1.1)))
    L['rocks'] = sorted(rocks, key=lambda r: -r[2] * r[3] * r[4])
    L['rock_seed'] = [gk.randint(0, 10 ** 6) for _ in rocks]
    gs = C.rng(seed, 'sides')
    L['side_h'] = (gs.uniform(0.25, 0.4) * H, gs.uniform(0.8, 1.0) * H) if style != 'gorge' else (0.5 * H, H)
    L['side_n'] = noise2(gs, 5, 0.2, 0.9)
    return L


# ------------------------------------------------------------------ build
def build(lod=0, seed=1, w=None, d=None, h=None, relief=None, rivers=None, falls=None, crust=None, arch=None,
          arch_spans=None, style=None):
    p = genlib.proxy(ASSET)
    W = float(w or p['w']); D = float(d or p['d']); H = float(h or p['h'])
    style = style or C.cycle(seed, STYLES)
    L = layout(seed, W, D, H, style, relief, rivers, falls, crust, arch, arch_spans)
    R = RES[lod]
    mb = genlib.MeshBuilder()
    bm = mb.bm
    m_molten = mb.slot('lava_molten')
    m_hot = mb.slot('lava_molten', emissive_level=1.3)
    m_ctop = mb.slot('lava_flow')
    m_cside = mb.slot('lava', tint=TINT_CRUST)
    m_cliff = mb.slot('lava', tint=TINT_CRUST)
    m_rock = mb.slot('basalt_dry')
    m_lant = mb.slot('lantern_andon_plain')
    L_flow = bm.verts.layers.float_vector.new('kz_flow')
    L_heat = bm.verts.layers.float.new('kz_heat')
    zf, cliff_y, river_q, river_xy = L['zf'], L['cliff_y'], L['river_q'], L['river_xy']
    yb = -D / 2

    def setv(vs, flow, heat):
        for v in vs:
            v[L_flow] = flow; v[L_heat] = heat

    # ---- molten sheet
    nx, ny = R['sheet']

    def P_sheet(u, v):
        x = -W / 2 + W * u; y = yb + D * v
        return Vector((x, y, zf(x, y) - 0.03))
    V, F = grid(mb, nx, ny, P_sheet, m_molten)
    orient(F, (0, 0, 1))
    for col in V:
        for vv in col:
            x, y = vv.co.x, vv.co.y
            if L['rivers']:
                dist, hw, (tx, ty) = river_q(x, y)
                k = math.exp(-(dist / (hw * 2.0)) ** 2)
            else:
                k, tx, ty = 0.0, 0.0, 1.0
            fx = k * tx; fy = k * ty + (1 - k) * 0.35
            vv[L_flow] = Vector((fx, fy, 0.0)) * (0.35 + 0.65 * k) / max(1e-6, math.hypot(fx, fy))
            vv[L_heat] = 0.8 + 0.2 * k
    # ---- river cores
    for rv in L['rivers']:
        n = R['river_st']
        rows = []
        for k in range(n + 1):
            t = k / n
            x, y = river_xy(rv, t)
            a = river_xy(rv, max(0, t - 0.02)); b = river_xy(rv, min(1, t + 0.02))
            tx, ty = b[0] - a[0], b[1] - a[1]; ln = math.hypot(tx, ty) or 1; tx, ty = tx / ln, ty / ln
            hw = 0.62 * (rv['w0'] + (rv['w1'] - rv['w0']) * t) / 2
            row = []
            for s in (-1, 1):
                px, py = x - ty * hw * s, y + tx * hw * s
                py = min(py, D / 2)
                vv = bm.verts.new((px, py, zf(px, py) + 0.0))
                vv[L_flow] = Vector((tx, ty, 0)); vv[L_heat] = 1.0
                row.append(vv)
            rows.append(row)
        fs = [bm.faces.new((rows[k][0], rows[k + 1][0], rows[k + 1][1], rows[k][1])) for k in range(n)]
        mb._tag(fs, m_hot); orient(fs, (0, 0, 1))
    # ---- cliff
    cx_n, cz_n = R['cliff']

    def P_cliff(u, v):
        x = -W / 2 + W * u
        z0 = zf(x, yb + 0.5, False) - 0.4
        z = z0 + (L['top_at'](x) - z0) * v
        return Vector((x, cliff_y(x, z), z))
    V, F = grid(mb, cx_n, cz_n, P_cliff, m_cliff)
    orient(F, (0, 1, 0))
    # ---- falls
    fc, fr = R['fall']
    for fx, fw, ztop in L['falls']:
        zbot = zf(fx, cliff_y(fx, 1.0) + 0.6, False) - 0.1
        rows = []
        for j in range(fr + 1):
            t = j / fr
            z = ztop + (zbot - ztop) * t
            row = []
            for i in range(fc + 1):
                u = i / fc - 0.5
                edge = abs(u) > 0.49
                x = fx + u * fw * (1 + 0.35 * t * t) + (0.18 * math.sin(7.0 * z + i * 2.1 + fx) * fw * 0.25 if edge else 0.04 * math.sin(5 * z + i))
                y = cliff_y(x, z) + 0.25 + 0.3 * math.sin(math.pi * min(1, t * 1.4))
                vv = bm.verts.new((x, y, z))
                vv[L_flow] = Vector((0, 0, -1)); vv[L_heat] = 1.0
                row.append(vv)
            rows.append(row)
        fs = [bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i])) for j in range(fr) for i in range(fc)]
        gst = C.rng(int(fx * 100) + seed, 'streaks')
        streak = [m_hot if (i % 2 == 0) == (gst.random() < 0.7) else m_molten for i in range(fc)] if fc > 1 else [m_hot]
        for j in range(fr):
            for i in range(fc):
                fs[j * fc + i].material_index = streak[i]
        orient(fs, (0, 1, 0))
    # ---- side walls
    sy_n, sz_n = R['side']
    hs0, hs1 = L['side_h']; nsd = L['side_n']
    for side in (-1, 1):
        def P_side(u, v, side=side):
            y = yb + (D - 0.6) * u
            ztop = hs1 + (hs0 - hs1) * u ** 0.8 + 1.2 * nsd(y, side * 3)
            z0 = zf(side * W / 2, y, False) - 0.4
            z = z0 + (min(H, ztop) - z0) * v
            inset = 0.4 + 1.6 * (0.5 + 0.5 * nsd(y * 1.3, z)) * math.sin(math.pi * min(1.0, v * 1.15) * 0.9 + 0.1)
            return Vector((side * (W / 2 - inset), y, z))
        V, F = grid(mb, sy_n, sz_n, P_side, m_rock)
        orient(F, (-side, 0, 0))
    # ---- arch + bridge
    A = L['arch']
    if A:
        st, sides = R['arch']
        z_legs = [zf(A['x'] - A['tot'] / 2 + A['span'] * k, A['y'], False) for k in range(A['spans'] + 1)]
        zbase = min(z_legs) - 0.6
        for k in range(A['spans']):
            x0 = A['x'] - A['tot'] / 2 + A['span'] * k
            pts, radii = [], []
            for i in range(st + 1):
                th = math.pi * i / st
                x = x0 + A['span'] / 2 * (1 - math.cos(th))
                z = zbase + (A['rise'] + 0.6) * math.sin(th) ** 0.85
                pts.append((x, A['y'], z))
                radii.append(A['rad'] * (1 + 0.6 * (1 - math.sin(th)) ** 2))
            gk = C.rng(k, 'archmod')
            jit = [[gk.uniform(0.82, 1.15) for _ in range(sides)] for _ in pts]
            C.tube(mb, pts, radii, m_rock, sides=sides, mod=lambda i, kk, th, jit=jit: jit[i][kk])
        if R['deck']:
            # walkway on the arch crowns (humped bridge, 04): follows each arch's extrados between
            # 0.12 pi and 0.88 pi, so every deck point sits on the rock below it.
            nper = max(2, st // 2)
            dpts = []
            for k in range(A['spans']):
                x0 = A['x'] - A['tot'] / 2 + A['span'] * k
                for i in range(nper + 1):
                    if k and i == 0:
                        continue
                    th = math.pi * (0.12 + 0.76 * i / nper)
                    x = x0 + A['span'] / 2 * (1 - math.cos(th))
                    rr = A['rad'] * (1 + 0.6 * (1 - math.sin(th)) ** 2)
                    z = zbase + (A['rise'] + 0.6) * math.sin(th) ** 0.85 + rr * 0.8
                    dpts.append((x, A['y'], z))
            prof = [(-0.75, 0.0), (0.75, 0.0), (0.75, 0.3), (-0.75, 0.3)] if lod < 3 else [(-0.75, 0.15), (0.75, 0.15)]
            C.sweep(mb, dpts, prof, m_rock, caps=lod < 3, closed_prof=lod < 3)
            if R['lanterns']:
                for i, (x, y, z) in enumerate(dpts[1:-1]):
                    for sg in (-1, 1):
                        if lod == 0:
                            mb.box((x, y + sg * 0.66, z + 0.6), (0.08, 0.08, 0.6), m_rock)
                        mb.box((x, y + sg * 0.66, z + 1.0), (0.22, 0.22, 0.3), m_lant)
    # ---- near rocks
    rocks = L['rocks'][:R['rocks_keep']]
    for (x, y, sx, sy, sz), rs in zip(rocks, L['rock_seed']):
        z0 = zf(x, y, False)
        sx = min(sx, W / 2 - abs(x) - 0.05) if abs(x) + sx > W / 2 else sx
        sy = min(sy, D / 2 - y - 0.05) if y + sy > D / 2 else sy
        C.hull_rock(mb, (x, y, z0 + sz * 0.35), (sx, sy, sz), m_rock, genlib.rng(rs, 'rock'),
                    npts=R['rock_n'], ground=z0 - 0.3)
    # ---- crust plates (built last: resolution picked from the triangle budget left, never presence at LOD0/1)
    plates = L['plates']
    keep = R['plate_keep']
    if keep != 1.0:
        nkeep = int(round(len(plates) * keep)) if keep < 1 else int(keep)
        plates = sorted(plates, key=lambda c: -c[2])[:nkeep]
    budget = genlib.budget_of(ASSET) or [8000, 3200, 960, 200]
    left = budget[lod] - C.tri_count(bm)
    opts = {0: [(8, True, True), (7, True, True), (6, True, True), (6, False, True), (5, False, True)],
            1: [(6, False, True), (5, False, True), (4, False, True)],
            2: [(5, False, True), (4, False, True), (4, False, False)],
            3: [(5, False, False), (4, False, False)]}[lod]
    cost = lambda o: len(plates) * ((o[0] if o[1] else o[0] - 2) + (2 * o[0] if o[2] else 0))
    choice = next((o for o in opts if cost(o) <= left), opts[-1])
    if choice != opts[0]:
        print(f'{ASSET} LOD{lod} seed {seed}: plates {len(plates)} at {choice} (budget left {left})')
    N, dome, with_sides = choice
    for px, py, r, th, tx_, ty_, rot, ph, _ in plates:
        z0 = zf(px, py)
        outline = []
        for k in range(N):
            a = rot + 2 * math.pi * k / N
            rr = r * (1 + 0.2 * math.sin(2 * a + ph[0]) + 0.13 * math.sin(3 * a + ph[1]) + 0.09 * math.sin(5 * a + ph[2]) + 0.05 * math.sin(7 * a + ph[3]))
            outline.append((px + rr * math.cos(a), py + rr * math.sin(a)))
        def ztop(x, y):
            return z0 + th + tx_ * (x - px) + ty_ * (y - py)
        top = [bm.verts.new((x, y, ztop(x, y))) for x, y in outline]
        faces_top = []
        if dome:
            c = bm.verts.new((px, py, z0 + th + 0.06 * r))
            for k in range(N):
                faces_top.append(bm.faces.new((c, top[k], top[(k + 1) % N])))
        else:
            faces_top.append(bm.faces.new(top))
        orient(faces_top, (0, 0, 1))
        mb._tag(faces_top, m_ctop)
        if with_sides:
            bot = [bm.verts.new((x, y, min(zf(x, y), z0) - 0.12)) for x, y in outline]
            fs = [bm.faces.new((bot[k], bot[(k + 1) % N], top[(k + 1) % N], top[k])) for k in range(N)]
            for f in fs:
                f.normal_update()
                cen = f.calc_center_median()
                if (cen.x - px) * f.normal.x + (cen.y - py) * f.normal.y < 0:
                    f.normal_flip()
            mb._tag(fs, m_cside)
            setv(bot, Vector((0, 0, 0)), 0.25)
        setv(top, Vector((0, 0, 0)), 0.0)
    # ---- finish
    dx, dy, dz = C.centre_base(mb)
    o = to_object(mb, ASSET)
    me = o.data
    col = me.color_attributes.new('kz_flow_col', 'FLOAT_COLOR', 'POINT')
    fa = me.attributes['kz_flow']; ha = me.attributes['kz_heat']
    for i in range(len(me.vertices)):
        f = fa.data[i].vector; hh = ha.data[i].value
        col.data[i].color = (0.5 + 0.5 * f.x, 0.5 + 0.5 * f.y, 0.5 + 0.5 * f.z, hh)
    lights = [C.light_entry((0, D / 2 + dy, H * 0.35 + dz), color_k=1600, watts=round(4000 * W * H * 0.6 / (30.4 * 10.5), 1),
                            kind='area', size=[round(W, 2), round(H * 0.6, 2)], normal=[0, 1, 0], color=kelvin_rgb(1600),
                            note='lava field glow through the glass')]
    for fx, fw, ztop in L['falls']:
        lights.append(C.light_entry((fx + dx, cliff_y(fx, ztop * 0.5) + 1.5 + dy, ztop * 0.5 + dz), color_k=1700,
                                    watts=round(150 * fw, 1), color=kelvin_rgb(1700), note='lava fall'))
    C.set_json_props(o, kz_lights=lights,
                     kz_anim=dict(type='shader', what='flow-map emissive lava, slow; falls scroll', flow_attr='kz_flow',
                                  heat_attr='kz_heat', color_attr='kz_flow_col',
                                  speeds_m_s=dict(river=0.12, field=0.04, falls=0.6, ledge=0.03),
                                  slots=dict(molten=m_molten, hot=m_hot, crust_top=m_ctop, crust_side=m_cside)),
                     kz_snap='ground', kz_glass_side='+Y',
                     kz_params=dict(style=style, w=W, d=D, h=H, relief=round(L['relief'], 3), rivers=len(L['rivers']),
                                    falls=len(L['falls']), crust=round(L['crust'], 3), arch=bool(A),
                                    arch_spans=A['spans'] if A else 0, plates=len(L['plates']),
                                    ledge_z=round(L['ledge_z'] + dz, 2)))
    genlib.finish(o, smooth_angle=40)
    return o
