"""Arched timber bridge (taiko-bashi style) on rough basalt abutments, after refs/gen/sheet-mod-arrival.png #5.

Identifying features kept at every LOD: arched plank deck with a smooth laminated fascia girder, rail with
capped posts, slim lanterns on the four stone pier tops, stone abutments.
Proxy (3d/assets.json): w 3.2 (x) x d 7.0 (y, the span) x h 2.0 m. Pivot at base centre, the deck runs along Y
(either end is a front; +Y is the 'front' end), units metres.

What the concept shows (measured on sheet-mod-arrival #5 front + side, ~200 px/m in a 2x crop):
    5 tall rail posts per side between the lanterns at ~1.2-1.3 m pitch, giboshi caps on iron collars;
    a heavy top rail + one mid rail (a low kerb rail with a single strut per bay is a minority variant);
    one continuous arched fascia beam ~0.35 m deep with dark iron strap plates where each post lands;
    the 4 lanterns are separate from the rail: slender (~0.25 x 0.5 m) iron-framed lanterns on a short iron
    base on top of the stone piers that flank the deck ends; the piers are stacked rough basalt ~1.3-1.5 m
    long rising to the deck-end level, spilling into boulders at the water.

Parameters (all optional; defaults from the proxy):
    span    4-9 m    overall length along Y (alias: d)
    w       2.4-3.5  overall width incl. the flanking piers; clear deck = w - 2 * pier width
    rise    0.4-1.5  deck height at the crown above the base (alias: h -> rise = h - 1.0, clamped)
    posts   4-6      rail posts per side incl. the two end posts (default 5)
    abutment 'block' | 'rock'   coursed rough basalt blocks or piled rock lumps (both spill boulders)
    lanterns True | False       pier-top lanterns
Seeded shape variation (when the layout does not fix it): rise (seed%3: 1 -> 0.45-0.55 low, 2 -> 0.9-1.0 steep
taiko hump, 0 -> 0.7-0.8), arch curve exponent, post count 4-6, rail scheme (2 rails; every third seed a kerb
rail with struts), finial (giboshi; hoshu ball on every third seed), plank width, pier course layout and spill
boulders, lantern roof, wood tint and wear.
Lights: no runtime light (lightmap); the four lanterns carry emissive washi_backlit panels.
Custom properties: kz_lights = JSON list of {pos, color, radius}; kz_deck = JSON {crown_z, end_z, clear_width}.
Materials: hinoki (timber; girder in the darker slot), iron (caps, straps, lantern frames), basalt_dry
(abutments), washi_backlit (lantern panels).
Animation: none.
"""
import json
import math
from mathutils import Matrix, Vector
import genlib
import kzgeo_bridge_arched as kg

ASSET = 'bridge_arched'
FEATURES = ['arched plank deck + fascia girder', 'rail with capped posts', 'lanterns on the 4 pier tops', 'stone abutments']


def _params(seed, span, w, rise, h, d, posts, abutment, lanterns):
    p = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    span = float(span or d or p['d'])
    w = float(w or p['w'])
    humped = False
    if rise is None and h:
        rise = h - 1.0
    if rise is None:
        humped = seed % 3 == 2
        rise = {1: r.uniform(0.45, 0.55), 2: r.uniform(0.9, 1.0), 0: r.uniform(0.7, 0.8)}[seed % 3]
    rise = min(max(float(rise), 0.4), 1.6)
    return r, dict(span=span, w=w, rise=round(rise, 3), posts=int(posts or r.choice([5, 5, 4, 6])), humped=humped,
                   abutment=abutment or ('rock' if seed % 3 == 0 else 'block'),
                   lanterns=True if lanterns is None else bool(lanterns))


def build(lod, seed, span=None, w=None, rise=None, h=None, d=None, posts=None, abutment=None, lanterns=None,
          **_unused):
    r, P = _params(seed, span, w, rise, h, d, posts, abutment, lanterns)
    L, W, RISE = P['span'], P['w'], P['rise']
    # ---- seeded shape choices
    arch_k = 1.6 if P['humped'] else r.uniform(1.0, 1.45)   # 1 parabola .. 1.6 bell
    gd = r.uniform(0.35, 0.40)             # fascia girder depth (constant, laminated)
    kerb = seed % 3 == 0                   # minority variant: low kerb rail + one strut per bay
    finial = 'hoshu' if seed % 3 == 0 else 'giboshi'
    plank_w = r.uniform(0.19, 0.24)
    roof = r.choice(['hip', 'hip', 'round'])
    pier_w = min(0.5, max(0.42, 0.14 * W))
    pier_l = r.uniform(1.3, 1.5) * (0.85 + 0.15 * L / 7.0)
    pier_h = r.uniform(0.9, 1.05)
    mb = genlib.MeshBuilder()
    wood = mb.slot('hinoki', variant=r.choice(['wet_oiled', 'walnut']))
    wood_d = mb.slot('hinoki', variant='stained')
    wood_l = mb.slot('hinoki', variant='wet_oiled', wear=0.35)
    plank_mats = [wood, wood, wood, wood_l, wood_d] if lod == 0 else [wood]
    iron = mb.slot('iron', wear=round(r.uniform(0.15, 0.35), 2))
    stone = mb.slot('basalt_dry', wetness=round(r.uniform(0.15, 0.35), 2))
    stone_w = mb.slot('basalt_wet', wetness=0.7)
    paper = mb.slot('washi_backlit', emissive_level=round(r.uniform(0.45, 0.6), 2))
    M = dict(iron=iron, paper=paper)

    deck_w = W - 2 * pier_w - 0.06          # girder outer faces
    half = L / 2
    z_end = 0.07
    pt = 0.06                               # plank thickness

    def f(t):
        t = min(1.0, abs(t))
        return (1 - t * t) ** arch_k

    def zt(y):
        return z_end + (RISE - z_end) * f(y / half)

    def slope(y):
        e = 0.01
        return (zt(y + e) - zt(y - e)) / (2 * e)

    y_in = half - pier_l                    # abutment inner face
    H = 0.80                                # rail height above deck
    rail_heights = [H, H - 0.32] + ([0.16] if kerb else [])
    post_w = 0.13
    post_x = deck_w / 2 + post_w / 2 - 0.02
    nseg = {0: 18, 1: 8, 2: 6, 3: 4}[lod]

    def arc(y0, y1, n, dz=0.0, x=0.0):
        return [Vector((x, y0 + (y1 - y0) * i / n, zt(y0 + (y1 - y0) * i / n) + dz)) for i in range(n + 1)]

    def gdep(y):
        return max(0.06, min(gd, zt(y) - pt))      # constant depth; only clipped where it dives into the abutment

    lights = []
    gy = y_in + 0.3                          # girder bears 0.3 m into the abutment
    # ------------------------------------------------------------------ deck + fascia girders
    if lod <= 1:
        yp = gy - 0.05
        arc_len = 0.0
        y = -yp
        while y < yp:
            arc_len += math.hypot(0.005, zt(y + 0.005) - zt(y))
            y += 0.005
        n = max(8, int(round(arc_len / plank_w)))
        if lod == 1:
            n = max(8, n // 2)
        ys = [-yp]
        acc = 0.0
        step = arc_len / n
        y = -yp
        while y < yp and len(ys) < n + 1:
            y2 = y + 0.005
            acc += math.hypot(0.005, zt(y2) - zt(y))
            y = y2
            if acc >= step * len(ys):
                ys.append(min(y, yp))
        ys = ys[:n] + [yp]
        for i in range(len(ys) - 1):
            y0, y1 = ys[i], ys[i + 1]
            yc = (y0 + y1) / 2
            s = slope(yc)
            level = min(1.0, max(0.0, (abs(s) - 0.22) / 0.25))
            ang = math.atan(s) * (1 - level)
            run = math.hypot(y1 - y0, zt(y1) - zt(y0))
            run = run * (1 - level) + (y1 - y0) * level
            thick = pt + level * abs(zt(y1) - zt(y0)) * 0.9
            jit = r.uniform(-0.004, 0.004) if lod == 0 else 0
            Mx = kg.frame(Vector((0, yc, 0)), Vector((0, math.cos(ang), math.sin(ang))))
            top = zt(yc) if level < 0.5 else max(zt(y0), zt(y1))
            Mx.translation = Vector((0, yc, top - thick / 2 + jit))
            gap = 0.012 if lod == 0 else 0.0
            # planks stop inside the fascia (no notched plank ends on the elevation)
            kg.cbox(mb, Mx, (deck_w - 0.2, run - gap, thick), r.choice(plank_mats))
        # one smooth swept laminated beam per side: top 0.03 above the deck edge, constant depth
        def gprof(dep):
            if lod == 0:
                return [(-0.07, 0.03 + pt), (0.07, 0.03 + pt), (0.07, -dep + 0.025), (0.05, -dep), (-0.07, -dep)]
            return [(-0.07, 0.03 + pt), (0.07, 0.03 + pt), (0.07, -dep), (-0.07, -dep)]
        for sx in (-1, 1):
            pts = arc(-gy, gy, nseg, dz=-pt, x=sx * (deck_w / 2 - 0.07))
            profs = [gprof(gdep(p_.y)) for p_ in pts]
            if sx < 0:
                profs = [[(-x, z) for x, z in pr] for pr in profs]
            kg.sweep(mb, pts, None, wood_d, profs=profs)
        if lod == 0:
            for k in range(1, 6):
                yy = -y_in + 2 * y_in * k / 6
                Mc = kg.frame(Vector((0, yy, zt(yy) - pt - 0.075)), Vector((0, 1, slope(yy))).normalized())
                kg.cbox(mb, Mc, (deck_w - 0.16, 0.1, 0.13), wood_d)
    else:
        # LOD2/3: deck + fascia as one arched slab
        thick = gd + pt + (0.03 if lod == 2 else 0.0)
        prof = [(-deck_w / 2, 0.03), (deck_w / 2, 0.03), (deck_w / 2, -thick), (-deck_w / 2, -thick)]
        ye = gy if lod == 2 else half - 0.02
        pts = arc(-ye, ye, nseg)
        for p_ in pts:
            p_.z = max(p_.z, thick)
        kg.sweep(mb, pts, prof, wood_d, caps=lod == 2)

    # ------------------------------------------------------------------ rail posts + rails
    npost = min(6, max(4, P['posts']))
    y_rail = y_in - 0.05
    post_ys = [-y_rail + 2 * y_rail * i / (npost - 1) for i in range(npost)]
    if lod == 3:
        bm = mb.bm
        for sx in (-1, 1):
            pts = arc(-y_rail, y_rail, 4, x=sx * post_x)
            kg.sweep(mb, pts, [(0.0, H + 0.03), (0.0, H - 0.07)], wood_d, caps=False, closed_prof=False)
            for py in (-y_rail * 0.5, y_rail * 0.5):
                q = [bm.verts.new(c) for c in ((sx * post_x, py - 0.06, zt(py)), (sx * post_x, py + 0.06, zt(py)),
                                              (sx * post_x, py + 0.06, zt(py) + H), (sx * post_x, py - 0.06, zt(py) + H))]
                mb._tag([bm.faces.new(q)], wood_d)
    else:
        for sx in (-1, 1):
            for i, py in enumerate(post_ys):
                if lod == 2 and 0 < i < npost - 1 and i % 2 == 0 and npost > 4:
                    continue
                zb = max(0.02, zt(py) - (gdep(py) * 0.9 if lod <= 1 else 0.1))
                ztop = zt(py) + H + 0.08
                if lod == 0:
                    kg.post_oct(mb, sx * post_x, py, zb, ztop, post_w, wood_d)
                    kg.band(mb, (sx * post_x, py, zb + 0.07), post_w + 0.016, post_w + 0.016, 0.12, iron)
                    for rz in rail_heights:
                        kg.band(mb, (sx * post_x, py, zt(py) + rz), post_w + 0.016, post_w + 0.016, 0.06, iron)
                    kg.band(mb, (sx * post_x, py, ztop - 0.02), post_w + 0.02, post_w + 0.02, 0.04, iron)   # collar
                    kg.giboshi(mb, (sx * post_x, py, ztop), iron, lod, style=finial, rscale=1.1)
                elif lod == 1:
                    mb.box((sx * post_x, py, (zb + ztop) / 2), (post_w, post_w, ztop - zb), wood_d)
                    kg.giboshi(mb, (sx * post_x, py, ztop), iron, lod, style=finial, rscale=1.1)
                else:
                    mb.box((sx * post_x, py, (zb + ztop) / 2), (post_w, post_w, ztop - zb), wood_d)
                    mb.cylinder((sx * post_x, py, ztop + 0.06), radius=0.08, radius2=0.0, depth=0.12, mi=iron, segs=4,
                                rot=(0, 0, math.pi / 4), cap=False)
            # iron strap plates (0.12 m) wrapping the fascia where each post lands, 2 bolt heads at LOD0
            if lod <= 1:
                for py in post_ys:
                    zg = zt(py) - pt
                    dep = gdep(py)
                    Ms = kg.frame(Vector((sx * deck_w / 2, py, zg)), Vector((0, 1, slope(py))).normalized())
                    if sx < 0:
                        Ms = Ms @ Matrix.Scale(-1, 4, Vector((1, 0, 0)))
                    if lod == 0:
                        poly = [(0.0, 0.03 + pt), (0.012, 0.03 + pt), (0.012, -dep - 0.012), (-0.15, -dep - 0.012),
                                (-0.15, -dep), (0.0, -dep)]
                        kg.prism_local_y(mb, poly, -0.06, 0.06, iron, Ms)
                        for bz in (-dep * 0.25, -dep * 0.7):
                            pb = Ms @ Vector((0.018, 0, bz))
                            mb.cylinder((pb.x, pb.y, pb.z), radius=0.014, radius2=0.006, depth=0.014, mi=iron, segs=3,
                                        rot=(0, math.pi / 2, 0), cap=False)
                    else:
                        kg.cbox(mb, Ms @ Matrix.Translation((0.006, 0, (pt + 0.03 - dep) / 2)), (0.012, 0.12, dep + pt + 0.03), iron)
            # rails: heavy top rail + mid rail (+ kerb rail with one strut per bay on the minority variant)
            rs = {0: nseg, 1: nseg, 2: 5}[lod]
            top_prof = [(-0.065, -0.04), (0.065, -0.04), (0.065, 0.02), (0.042, 0.045), (-0.042, 0.045), (-0.065, 0.02)]
            if lod >= 1:
                top_prof = [(-0.06, -0.04), (0.06, -0.04), (0.06, 0.04), (-0.06, 0.04)]
            pts = arc(-y_rail - 0.1, y_rail + 0.1, rs, dz=H, x=sx * post_x)
            kg.sweep(mb, pts, top_prof, wood)
            mid_prof = [(-0.035, -0.045), (0.035, -0.045), (0.035, 0.045), (-0.035, 0.045)]
            for rz in (rail_heights[1:] if lod <= 1 else [rail_heights[1]]):
                pts = arc(-y_rail, y_rail, rs, dz=rz, x=sx * post_x)
                kg.sweep(mb, pts, mid_prof, wood)
            if lod == 0 and kerb:
                for i in range(npost - 1):
                    yy = (post_ys[i] + post_ys[i + 1]) / 2
                    z0, z1 = zt(yy) + rail_heights[2], zt(yy) + rail_heights[1]
                    kg.band(mb, (sx * post_x, yy, (z0 + z1) / 2), 0.04, 0.04, z1 - z0, wood)

    # ------------------------------------------------------------------ abutments
    for sy in (-1, 1):
        y0, y1 = sy * y_in, sy * half
        ylo, yhi = min(y0, y1), max(y0, y1)
        # stone steps from the base up to the deck (the deck end bears on them)
        z_deck = zt(gy - 0.05) - (pt if lod <= 1 else 0.0)
        nst = max(1, int(round(z_deck / 0.15))) if lod < 3 else 0
        if lod == 2:
            nst = min(nst, 2)
        y_st_in = gy - 0.05
        ylen = half - y_st_in
        for k in range(nst):
            ya = half - ylen * k / nst
            ztop = z_deck * (k + 1) / nst
            yb_ = y_in - 0.02 if k == nst - 1 else half - ylen * (k + 1) / nst
            yc_, yl_ = sy * (ya + yb_) / 2, ya - yb_
            nb = 2 if lod == 0 else 1
            for j in range(nb):
                xa = -deck_w / 2 + deck_w * j / nb
                xb = -deck_w / 2 + deck_w * (j + 1) / nb
                Mst = kg.frame(Vector(((xa + xb) / 2, yc_, ztop / 2)), Vector((0, 1, 0)))
                kg.cbox(mb, Mst, (xb - xa - (0.012 if lod == 0 else 0), yl_ - (0.01 if lod == 0 else 0), ztop), stone,
                        jitter=0.01 if lod == 0 else 0.0, r=r, drop_bottom=True)
        # bearing wall across the full width at the abutment face (rough rock face, girders land on it)
        if lod <= 1:
            zf = max(0.05, zt(y_in) - pt - gd)
            kg.rock_body(mb, Matrix.Translation((0, sy * y_in, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'Z'),
                         -deck_w / 2, deck_w / 2, -sy * 0.06, sy * 0.3, lambda s_: zf, lambda s_: 0.0,
                         4 if lod == 0 else 1, 2 if lod == 0 else 1, 0.05 if lod == 0 else 0.0, r, stone)
        # flanking piers
        for sx in (-1, 1):
            xo, xi = sx * W / 2, sx * (W / 2 - pier_w)
            xlo, xhi = min(xo, xi), max(xo, xi)
            cx, cy = (xlo + xhi) / 2, (ylo + yhi) / 2
            if lod >= 2:
                kg.cbox(mb, kg.frame(Vector((cx, cy, pier_h / 2)), Vector((0, 1, 0))), (xhi - xlo, yhi - ylo, pier_h), stone,
                        drop_bottom=True)
            elif P['abutment'] == 'block':
                # 3 (LOD1: 2) courses of rough basalt blocks, staggered joints, battered, chipped by jitter
                nc = 3 if lod == 0 else 2
                zc = [0.0] + sorted(r.uniform(0.85, 1.15) * (pier_h - 0.1) * (k + 1) / nc for k in range(nc - 1)) + [pier_h - 0.1]
                for ci in range(nc):
                    za, zb = zc[ci], zc[ci + 1]
                    nb = (r.choice([2, 3]) if (ci + (sy > 0)) % 2 == 0 else 2) if lod == 0 else 1
                    cuts = [ylo] + sorted(r.uniform(ylo + 0.2 * (yhi - ylo), ylo + 0.8 * (yhi - ylo)) for _ in range(nb - 1)) + [yhi]
                    inset = 0.015 * ci
                    for k in range(len(cuts) - 1):
                        g = 0.016 if lod == 0 else 0.0
                        Mb = kg.frame(Vector((cx + (r.uniform(-0.03, 0.03) if lod == 0 else 0), (cuts[k] + cuts[k + 1]) / 2, (za + zb) / 2)),
                                      Vector((0, 1, 0)))
                        kg.cbox(mb, Mb, (xhi - xlo - 2 * inset - g, cuts[k + 1] - cuts[k] - g, zb - za - g), stone,
                                jitter=0.03 if lod == 0 else 0.0, r=r, drop_bottom=ci == 0)
                Mc = kg.frame(Vector((cx, cy, pier_h - 0.05)), Vector((0, 1, 0)))
                kg.cbox(mb, Mc, (xhi - xlo + 0.02, yhi - ylo + 0.02, 0.1), stone, bevel=0.02 if lod == 0 else 0.0)
            else:
                layers = [(0.0, pier_h * 0.55), (pier_h * 0.45, pier_h - 0.08)] if lod == 0 else [(0.0, pier_h - 0.08)]
                for za, zb in layers:
                    for k in range(2):
                        rx = cx + r.uniform(-0.05, 0.05)
                        ry = ylo + (yhi - ylo) * (k + 0.5) / 2 + r.uniform(-0.04, 0.04)
                        hz = zb - za
                        fs, vs = kg.rock(mb, (rx, ry, za + hz * 0.5), ((xhi - xlo) * r.uniform(1.0, 1.2), (yhi - ylo) / 2 * 1.4, hz * 1.15),
                                         stone, r, subdiv=1 if lod == 0 else 0, rough=0.22 if lod == 0 else 0.1,
                                         facets=3 if lod == 0 else 1, zmin=za, zmax=zb)
                        kg.clamp_verts(vs, xlim=(-W / 2, W / 2), ylim=(-half, half))
                Mc = kg.frame(Vector((cx, cy, pier_h - 0.04)), Vector((0, 1, 0)))
                kg.cbox(mb, Mc, (xhi - xlo - 0.02, yhi - ylo - 0.04, 0.08), stone, bevel=0.02 if lod == 0 else 0.0)
            # slim lantern on a short iron base on the pier top
            if P['lanterns']:
                lx, ly = cx, sy * (y_in + 0.32)
                if lod <= 1:
                    mb.box((lx, ly, pier_h + 0.04), (0.16, 0.16, 0.08), iron)
                c = kg.lantern_slim(mb, (lx, ly, pier_h + (0.08 if lod <= 1 else 0.0)), M, lod, size=0.26, height=0.38,
                                    roof=roof, frame=0.03)
                lights.append([round(c.x, 3), round(c.y, 3), round(c.z, 3)])
        # boulders spilling from the abutment toward the water (seated on z = 0, under the girder line)
        if lod <= 1:
            nb_ = r.randint(3, 5) if lod == 0 else 2
            for k in range(nb_):
                bx = -W / 2 + 0.35 + (W - 0.7) * (k + r.uniform(0.2, 0.8)) / nb_
                by = sy * (y_in - r.uniform(0.1, 0.45))
                dia = r.uniform(0.4, 0.8)
                zcap = max(0.12, zt(by) - pt - gd - 0.03) if abs(bx) < deck_w / 2 + 0.1 else 0.6
                hz = min(dia * 0.7, zcap)
                fs, vs = kg.rock(mb, (bx, by, hz * 0.45), (dia, dia * r.uniform(0.7, 1.0), hz * 1.1), stone_w, r,
                                 subdiv=1 if lod == 0 else 0, rough=0.25, facets=2, zmin=0.0, zmax=hz)
                kg.clamp_verts(vs, xlim=(-W / 2, W / 2), ylim=(-half, half))

    for v in mb.bm.verts:
        if v.co.z < 0.0:
            v.co.z = 0.0
        v.co.y = min(max(v.co.y, -half), half)
    o = mb.to_object(ASSET)
    o['kz_lights'] = json.dumps([dict(pos=p_, color=[1.0, 0.55, 0.25], radius=4.0, source='washi_backlit') for p_ in lights])
    o['kz_deck'] = json.dumps(dict(crown_z=round(RISE, 3), end_z=z_end, clear_width=round(deck_w - 0.2, 3),
                                   span=L, abutment=P['abutment']))
    o['kz_params'] = json.dumps(P)
    genlib.finish(o)
    kg.uv_grain(o, [wood, wood_d, wood_l])
    return o
