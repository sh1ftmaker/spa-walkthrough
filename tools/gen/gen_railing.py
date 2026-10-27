"""Railing generator (railing): posts every ~1.5 m with rails, along any polyline, five styles.

Targets (measured):
  sheet-mod-arrival.png #6 'Railing section W 1.0 x H 1.0' (crop .scratch/op04/measure_rail.png). The drawn
  1 m bar is half the labelled scale (bar says 1.96 m wide), so the label wins (465 px/m in the 2x crop):
  overall height to the finial 0.96 m, post 0.09-0.10 m square, basalt plinth 0.24 m high x 0.30 m deep,
  bottom rail centre 0.31, second rail 0.59, top rail 0.71, post top 0.80, cap + knob 0.16; 4 balusters per
  metre between the bottom and second rails; dark iron plates where the rails meet the posts.
  Built to the row's 1.0-1.05 m overall (sheet proportions x 1.09): plinth 0.26 x 0.32, bottom rail 0.33,
  second 0.64, top 0.77, post top 0.87, finial top 1.04.
  ref-spiral-stair / lookbook 13: curved heavy rounded timber rail (0.11 x 0.08) with a bronze cap strip on
  posts every ~1.5 m, close vertical balusters (~0.12 m) between a mid and a bottom rail, 1.0-1.05 m.
  lookbook 17: dark round bronze handrail (~50 mm) on slim stained timber posts, one thin mid rail.
  lookbook 06: Kawagiri balcony: dark timber posts, flat top rail, square lattice infill, kick board.
  ring: the gallery rings round the spiral well (ref-spiral-stair top): bronze tube rail, bronze posts,
  thin iron bars, on an arc.

Size: default piece 1.5 m long (proxy w). height = overall height (top of post / finial / handrail).
Proxy note: proxy d 0.10 cannot hold the sheet's 0.32 m basalt plinth nor a curved run; proposed d = 0.34.

Parameters build(lod, seed, **p)
  style      timber_lattice | bronze_handrail | curved_cap | balcony | ring  (default: cycles with the seed)
  length     run length when no path is given (default 1.5)
  path       polyline [(x, y, z), ...]; z follows stair treads (rails slope, posts stay vertical)
  radius     plan radius of the default path for curved_cap (4.0) and ring (2.4); 0 = straight
  height     0.9-1.3 m overall (style defaults 1.04 / 1.0 / 1.05 / 1.0 / 1.04)
  spacing    post spacing 1.2-2.0 m (seeded); the run is divided into equal bays
  plinth     basalt plinth on/off (default on for timber_lattice only)
  gates      [(s0, s1), ...] gaps along the path (m): no rails, infill or plinth there, posts at the edges
  end_post   post at the far end (default True; False when pieces are chained)
Seeds change shape: the style (seeds 1-5 walk the five styles), post spacing, baluster pitch, height +-4 %,
plinth block length, rail section. Every part draws from its own stream, before any LOD branch.
LOD0 all parts (finials, iron bands, plinth blocks with bulged faces); LOD1 all parts and counts, cheaper
sections (4-sided rails, triangular balusters), no finial knob detail; LOD2 posts, rails and plinth, infill
dropped (balusters are ~1 px at the 14 m switch), LOD3 plinth + top rail + posts as thin boxes.
Budget is per metre (600/240/72/20 per m); the default 1.5 m piece is held to the unscaled row numbers.
Materials: hinoki (per style variant), iron (bands, caps, bars), bronze smooth (handrails, cap strips),
basalt_dry cooled (plinth). Animation none. Lighting lightmap (UV1 from genlib.finish).
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_railing as R
import kzgeo_bridge_arched as KB

ASSET = 'railing'
FEATURES = ['posts every ~1.5 m', 'top rail 1.0-1.05 m', 'style infill (lattice / handrail / balusters)',
            'basalt plinth (timber_lattice)']
STYLES = ['timber_lattice', 'bronze_handrail', 'curved_cap', 'balcony', 'ring']
TINT = (0.36, 0.36, 0.42)            # basalt_dry cooled and darkened toward the sheet's near-black blocks
INSET = 0.065

DEF = dict(timber_lattice=dict(height=1.04, plinth=True, radius=0.0, wood='walnut'),
           bronze_handrail=dict(height=1.0, plinth=False, radius=0.0, wood='stained'),
           curved_cap=dict(height=1.05, plinth=False, radius=4.0, wood='walnut'),
           balcony=dict(height=1.0, plinth=False, radius=0.0, wood='dark_timber'),
           ring=dict(height=1.04, plinth=False, radius=2.4, wood='stained'))


def _default_path(L, radius):
    if not radius:
        return [(-L / 2, 0, 0), (L / 2, 0, 0)]
    a = L / radius                                   # arc of length L, bulging to -Y (centre on +Y)
    n = 48
    return [(radius * math.sin(-a / 2 + a * k / n), radius - radius * math.cos(-a / 2 + a * k / n) - radius * (1 - math.cos(a / 2)) / 2, 0)
            for k in range(n + 1)]


def _runs(L, gates):
    """[0, L] minus the gate gaps -> list of (s0, s1)"""
    cuts, s = [], 0.0
    for g0, g1 in sorted(gates):
        if g0 > s:
            cuts.append((s, min(g0, L)))
        s = max(s, g1)
    if s < L:
        cuts.append((s, L))
    return [c for c in cuts if c[1] - c[0] > 0.05]


def _lod3(mb, path, post_s, runs, style, H, plinth, M, plinth_runs=None):
    """LOD3: plinth (top + faces, no ends) and, per run, one inverted-U frame of triangular section
    (end post up, top rail across, end post down) in the style's rail material; ~20-24 tris per piece."""
    from mathutils import Vector
    rail_mi = M['bronze'] if style in ('bronze_handrail', 'ring') else M['wood']
    zb = 0.0
    if plinth:
        zb = 0.26
        for s0, s1 in plinth_runs or runs:
            a, ta, _ = path.at(s0); b, tb, _ = path.at(s1)
            na, nb_ = Vector((-ta.y, ta.x, 0)), Vector((-tb.y, tb.x, 0))
            bm = mb.bm
            v = [bm.verts.new(a + na * 0.16), bm.verts.new(a + na * 0.16 + Vector((0, 0, zb))), bm.verts.new(a - na * 0.16 + Vector((0, 0, zb))), bm.verts.new(a - na * 0.16),
                 bm.verts.new(b + nb_ * 0.16), bm.verts.new(b + nb_ * 0.16 + Vector((0, 0, zb))), bm.verts.new(b - nb_ * 0.16 + Vector((0, 0, zb))), bm.verts.new(b - nb_ * 0.16)]
            fs = [bm.faces.new((v[0], v[4], v[5], v[1])), bm.faces.new((v[1], v[5], v[6], v[2])), bm.faces.new((v[2], v[6], v[7], v[3]))]
            mb._tag(fs, M['stone'])
    tri = [(0.03, -0.03), (0.0, 0.035), (-0.03, -0.03)]
    for s0, s1 in runs:
        ks = [s for s in post_s if s0 - 1e-4 <= s <= s1 + 1e-4] or [s0, s1]
        a, _, _ = path.at(ks[0]); b, _, _ = path.at(ks[-1])
        top = H - 0.05
        pts = [a + Vector((0, 0, zb)), a + Vector((0, 0, top)), b + Vector((0, 0, top)), b + Vector((0, 0, zb))]
        C.sweep(mb, pts, tri, rail_mi, caps=False)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_params=dict(style=style, height=round(H, 3), lod3=True))
    return o


def build(lod, seed, style=None, length=1.5, path=None, radius=None, height=None, spacing=None, plinth=None,
          gates=(), end_post=True):
    style = style or C.cycle(seed, STYLES)
    D = DEF[style]
    g = C.rng(seed, 'layout')
    H = height if height is not None else D['height'] * g.uniform(0.96, 1.02)
    sp = spacing if spacing is not None else g.uniform(1.2, 2.0)
    bal_pitch = g.uniform(0.2, 0.27) if style == 'timber_lattice' else g.uniform(0.10, 0.14)
    blen = g.uniform(0.42, 0.56)
    sec = g.uniform(0.9, 1.12)                       # rail / post section scale
    plinth = D['plinth'] if plinth is None else plinth
    radius = D['radius'] if radius is None else radius
    path = R.Path(path or _default_path(length, radius))
    L = path.L
    nb = max(1, int(math.ceil(L / sp - 0.15)))
    ins = INSET                                      # end posts sit inside the piece, so w == length
    e1 = L - ins if end_post else L
    post_s = [ins + (e1 - ins) * k / nb for k in range(nb + 1)]
    if not end_post:
        post_s = post_s[:-1]
    for g0, g1 in gates:                             # posts close every gate gap
        post_s += [g0, g1]
    post_s = sorted({round(min(max(s, 0), L), 4) for s in post_s})
    runs = _runs(L, gates)
    plinth_runs = runs
    runs = [(max(a, ins) if a < 1e-6 else a, min(b, e1) if b > L - 1e-6 else b) for a, b in runs]
    ds = C.lod_pick(lod, 0.17, 0.33, 0.75, 99.0)

    mb = genlib.MeshBuilder()
    wood = mb.slot('hinoki', variant=D['wood'])
    iron = mb.slot('iron')
    bronze = mb.slot('bronze', variant='smooth')
    stone = mb.slot('basalt_dry', tint=TINT)
    rp = C.rng(seed, 'plinth')

    if lod == 3:
        return _lod3(mb, path, post_s, runs, style, H, plinth, dict(wood=wood, iron=iron, bronze=bronze, stone=stone), plinth_runs)
    z_base = 0.0
    if plinth:
        ph, pd = 0.26, 0.32
        for s0, s1 in plinth_runs:
            R.plinth_blocks(mb, path, s0, s1, ph, pd, stone, rp, blen, lod)
        z_base = ph

    def posts(w, d, top, mi, ch, cap=None):
        for s in post_s:
            p, t, yaw = path.at(s)
            if lod == 3:
                R.vprism(mb, (p.x, p.y), yaw, w, d, p.z + z_base, p.z + top, mi)
                continue
            R.vprism(mb, (p.x, p.y), yaw, w, d, p.z + z_base, p.z + top, mi, ch=ch if lod == 0 else 0.0)
            if cap:
                cap(p, yaw)

    def infill(z0f, z1f, pitch, w, d, mi):
        """vertical bars between posts, z0f/z1f(s) -> absolute heights"""
        if lod >= 2:
            return
        for s0, s1 in runs:
            ks = [s for s in post_s if s0 - 1e-4 <= s <= s1 + 1e-4]
            ks = sorted(set([s0] + ks + [s1]))
            for a, b in zip(ks[:-1], ks[1:]):
                n = max(1, int(round((b - a) / pitch)))
                for k in range(1, n):
                    s = a + (b - a) * k / n
                    p, t, yaw = path.at(s)
                    R.vprism(mb, (p.x, p.y), yaw, w, d, p.z + z0f, p.z + z1f, mi, cap_top=False,
                             sides=3 if lod == 1 else None)

    def rails(dz, prof, mi):
        for s0, s1 in runs:
            R.rail(mb, path, s0, s1, dz, prof, mi, ds)

    def rprof(w, h, ch):
        return R.rect_prof(w, h, ch if lod == 0 else 0.0)

    if style == 'timber_lattice':
        pw = 0.10 * sec; top = H - 0.17
        rails_z = [z_base + 0.07, z_base + 0.38, H - 0.27]            # bottom, second, top (rail centres)

        def cap(p, yaw):
            if lod >= 2:
                return
            R.vprism(mb, (p.x, p.y), yaw, pw + 0.03, pw + 0.03, p.z + top, p.z + top + 0.035, iron, cap_bot=True)
            KB.giboshi(mb, (p.x, p.y, p.z + top + 0.035), iron, lod, scale=0.78, rscale=0.9, segs=6 if lod == 0 else 4)
            for zr in (rails_z[0], rails_z[2]):
                if lod == 0:
                    R.band(mb, (p.x, p.y), yaw, pw, pw, p.z + zr, 0.075, iron)
        posts(pw, pw, top, wood, 0.012, cap)
        for k, zr in enumerate(rails_z):
            rails(zr, rprof(0.055, 0.065 if k != 1 else 0.05, 0.008), wood)
        infill(rails_z[0] + 0.03, rails_z[1] - 0.025, bal_pitch, 0.045, 0.04, wood)
        if lod == 3:
            pass
    elif style == 'bronze_handrail':
        pw = 0.085 * sec; top = H - 0.05
        posts(pw, pw, top, wood, 0.01)
        hr = 0.026 * sec
        rails(H - hr, R.round_prof(hr, C.lod_pick(lod, 10, 6, 4, 4)), bronze)
        if lod <= 2:
            rails(0.45, R.round_prof(0.013, C.lod_pick(lod, 6, 4, 3)), bronze)
        if lod <= 1:
            for s in post_s:                                         # iron shoe at each post foot
                p, t, yaw = path.at(s)
                R.band(mb, (p.x, p.y), yaw, pw, pw, p.z + 0.04, 0.08, iron, t=0.006)
    elif style == 'curved_cap':
        pw = 0.10 * sec; rw, rh = 0.115 * sec, 0.075
        top = H - rh
        posts(pw, pw, top, wood, 0.012)
        rails(H - rh / 2, R.cap_rail_prof(rw, rh, lod) if lod < 3 else R.rect_prof(rw, rh), wood)
        if lod <= 1:
            rails(H + 0.004, R.rect_prof(0.03, 0.012), bronze)          # bronze cap strip on the rail crown
        if lod <= 2:
            rails(H - 0.24, rprof(0.05, 0.045, 0.006), wood)
            rails(0.10, rprof(0.05, 0.05, 0.006), wood)
        infill(0.125, H - 0.262, bal_pitch, 0.026, 0.026, wood)
        if lod <= 1:
            for s in post_s:
                p, t, yaw = path.at(s)
                R.band(mb, (p.x, p.y), yaw, pw, pw, p.z + 0.035, 0.07, bronze, t=0.006)
    elif style == 'balcony':
        pw = 0.11 * sec; top = H - 0.02
        posts(pw, pw, top, wood, 0.012)
        rails(H - 0.025, rprof(0.13, 0.05, 0.01), wood)                  # flat top rail, wider than the posts
        if lod <= 2:
            rails(0.12, rprof(0.13, 0.20, 0.008), wood)                  # kick board / fascia
        rails(H - 0.20, rprof(0.045, 0.04, 0.006), wood)
        if lod <= 1:
            rails(0.48, rprof(0.04, 0.035, 0.0), wood)                   # lattice cross rail
        infill(0.22, H - 0.22, bal_pitch * 1.15, 0.032, 0.032, wood)
        if lod == 0:
            for s in post_s:
                p, t, yaw = path.at(s)
                R.band(mb, (p.x, p.y), yaw, pw, pw, p.z + H - 0.20, 0.06, iron)
    elif style == 'ring':
        pw = 0.07 * sec; top = H - 0.04
        posts(pw, pw, top, bronze, 0.008)
        hr = 0.028
        rails(H - hr, R.round_prof(hr, C.lod_pick(lod, 10, 6, 4, 4)), bronze)
        if lod <= 2:
            rails(0.08, R.rect_prof(0.04, 0.03), bronze)
        if lod <= 1:
            rails(H - 0.16, R.round_prof(0.012, C.lod_pick(lod, 6, 4, 3)), iron)
        infill(0.095, H - 0.172, bal_pitch, 0.016, 0.016, iron)

    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    KB.uv_grain(o, [wood])
    C.set_json_props(o, kz_params=dict(style=style, height=round(H, 3), spacing=round(sp, 3), plinth=bool(plinth),
                                       length=round(L, 3), posts=len(post_s)))
    return o
