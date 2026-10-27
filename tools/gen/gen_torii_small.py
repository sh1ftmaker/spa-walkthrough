"""Small torii (sea torii on b3_shore, vermilion torii in the Kawagiri distance on b2_kawagiri).

Identifying features kept at every LOD: two round posts (slight inward lean), the upswept kasagi (black cap
beam), the nuki tie beam passing through the posts with protruding ends; LOD0-2 add the shimaki under the
kasagi, the central gakuzuka strut and the plaque.

Targets (measured; no scale sheet for this asset, sheet-mod-landmarks does not exist yet):
  * lookbook 06 Kawagiri, far right (x 1400-1560, y 270-370; crop .scratch/op25/c06_torii.png): myojin torii,
    vermilion posts / nuki / shimaki under a black, strongly upswept kasagi; post height : kasagi width ~ 0.7
    (perspective-flattened), post diameter ~ 0.09 x height, nuki at ~ 0.72 x height with ends protruding about
    one post diameter, central strut + small plaque between nuki and shimaki, black sleeves (nemaki) at the post
    feet, stands on stone steps.
  * lookbook 20 wave grotto: no torii visible at lookbook resolution; the row asks for a black one at the sea,
    so the sea variant stands on wet basalt footing rocks (black lacquer reads against the moonlit water).
  * Row: w 2.4-3.4 m, h 3-3.6 m, proxy 3.4 x 0.6 x 3.6 m.  Built: kasagi tip-to-tip = w, post span (centres at
    the top) = w / 1.42-1.55, post diameter 0.22-0.29 m at the base (0.08 x h), kasagi 0.16 x 0.30 m (top) at
    h 3.6, shimaki 0.12 m, upsweep 0.14-0.26 m, nuki 0.14 x 0.10 m at 0.70-0.76 h, plaque 0.30 x 0.46 m.

Parameters:
  w       2.4-3.4 m kasagi tip to tip (default seeded 2.9-3.4)
  h       3.0-3.6 m to the kasagi tips (default seeded 3.15-3.6)
  post_r  base post radius (default 0.04 x h, seeded +-8 %)
  colour  black | vermilion (default cycles with the seed: 1 black, 2 vermilion, 3 black, ...)
  base    sea | kamebara | daiishi (default cycles: 1 sea rock, 2 kamebara mound, 3 turned stone)
  plaque  True | False (default: on, except every third seed)
  text    plaque glyphs (default 火山湯 on black, 川霧 on vermilion)
Seeds change: colour, base style, plaque on/off, w, h, span ratio, post radius, upsweep height and curve,
nuki height and overhang, lean.

Materials (slots named by part): body = lacquer_dark (black) or hinoki tinted (1.5, 0.3, 0.15), normal 0.4,
roughness -0.15 (vermilion: the library has no vermilion lacquer, see report); cap = lacquer_black (kasagi,
nemaki sleeves, daiwa rings, plaque field); gold = gold_leaf (glyphs); foot = basalt_dry (kamebara / daiishi)
or basalt_wet 0.6 (sea rocks).  Animation: none.  Lighting: lightmap.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C

ASSET = 'torii_small'
FEATURES = ['two round posts', 'upswept kasagi', 'nuki tie beam through the posts']
COLOURS = ['black', 'vermilion']
BASES = ['sea', 'kamebara', 'daiishi']
VERMILION = dict(tint=(1.5, 0.3, 0.15), normal_strength=0.4, roughness_offset=-0.15)


def params(seed, w=None, h=None, post_r=None, colour=None, base=None, plaque=None, text=None):
    g = C.rng(seed, 'shape')
    P = dict(colour=colour or C.cycle(seed, COLOURS), base=base or C.cycle(seed, BASES))
    P['w'] = float(w) if w else g.uniform(2.9, 3.4)
    P['h'] = float(h) if h else g.uniform(3.15, 3.6)
    P['span'] = P['w'] / g.uniform(1.42, 1.55)
    P['post_r'] = float(post_r) if post_r else 0.04 * P['h'] * g.uniform(0.92, 1.08)
    P['up'] = g.uniform(0.14, 0.26) * P['h'] / 3.6
    P['p_exp'] = g.uniform(1.6, 2.4)
    P['nuki_k'] = g.uniform(0.70, 0.76)
    P['nuki_over'] = g.uniform(0.16, 0.30)
    P['lean'] = g.uniform(0.012, 0.025)                 # inward lean, m per m (uchikorobi)
    P['plaque'] = plaque if plaque is not None else (seed % 3 != 0)
    P['text'] = text or ('火山湯' if P['colour'] == 'black' else '川霧')
    return P


def _beam(mb, half, z0, th, dt, db, up, p_exp, n, prof_lv, mi, flat=0.45):
    """swept beam along X: flat for |x| < flat*half, tips rising `up` (u^p).  Profile wider on top (dt)
    than below (db); prof_lv 2 = chamfered 8-gon, 1 = 6-gon, 0 = 4-gon."""
    c = min(0.02, th * 0.15)
    if prof_lv >= 2:
        prof = [(-db / 2 + c, 0), (db / 2 - c, 0), (db / 2, c), (dt / 2, th * 0.72), (dt / 2, th - c),
                (dt / 2 - c, th), (-dt / 2 + c, th), (-dt / 2, th - c), (-dt / 2, th * 0.72), (-db / 2, c)]
    elif prof_lv == 1:
        prof = [(-db / 2, 0), (db / 2, 0), (dt / 2, th * 0.72), (dt / 2, th), (-dt / 2, th), (-dt / 2, th * 0.72)]
    else:
        prof = [(-db / 2, 0), (db / 2, 0), (dt / 2, th), (-dt / 2, th)]
    xf = flat * half
    xs = []
    if n <= 4:
        xs = [-half, -xf, xf, half]
    else:
        n_out = max(2, (n - 3) // 2)
        xs = [-half + (half - xf) * k / n_out for k in range(n_out)] + [-xf, 0.0, xf] + \
             [xf + (half - xf) * k / n_out for k in range(1, n_out + 1)]
    pts = []
    for x in xs:
        u = max(0.0, (abs(x) - xf) / (half - xf))
        pts.append(Vector((x, 0, z0 + up * u ** p_exp)))
    # profile x maps to -Y in C.sweep's frame (path along +X): symmetric, so no matter
    return C.sweep(mb, pts, [(x, z) for x, z in prof], mi)


def build(lod, seed, w=None, h=None, post_r=None, colour=None, base=None, plaque=None, text=None, **_):
    P = params(seed, w, h, post_r, colour, base, plaque, text)
    W, H = P['w'], P['h']
    mb = genlib.MeshBuilder()
    body = mb.slot('lacquer_dark') if P['colour'] == 'black' else mb.slot('hinoki', **VERMILION)
    cap = mb.slot('lacquer_black')
    gold = mb.slot('gold_leaf')
    foot = mb.slot('basalt_wet', wetness=0.6) if P['base'] == 'sea' else mb.slot('basalt_dry', wear=0.2)

    # ---- vertical stack (all heights measured at the centre line)
    s = H / 3.6
    kt, kdt, kdb = 0.16 * s, 0.30 * s, 0.24 * s            # kasagi thickness, top / bottom depth
    st, sd = 0.12 * s, 0.20 * s                            # shimaki
    up = P['up']
    z_kas = H - up - kt                                    # kasagi underside at the centre
    z_shim = z_kas - st
    r0 = P['post_r']
    r1 = r0 * 0.88
    half_span = P['span'] / 2
    z_post = z_shim + 0.02                                 # posts run up into the shimaki
    nk_t, nk_d = 0.14 * s, 0.10 * s
    z_nk = H * P['nuki_k']                                 # nuki top
    lean = P['lean']
    base_h = {'sea': 0.0, 'kamebara': 0.28 * s, 'daiishi': 0.22 * s}[P['base']]
    sleeve_h = 0.30 * s

    sides = C.lod_pick(lod, 24, 12, 8, 6)
    nst = C.lod_pick(lod, 29, 15, 7, 4)
    prof_lv = C.lod_pick(lod, 2, 1, 1, 0)

    # ---- posts (+ nemaki sleeve, daiwa ring), sheared for the inward lean
    for sg in (-1, 1):
        x = sg * half_span
        lay = mb._mark_old()
        if lod <= 2:
            prof = [(r0 * 1.02, base_h), (r1, z_post)] if lod >= 2 else \
                [(r0 * 1.02, base_h), (r0, base_h + sleeve_h), (r1 * 1.01, z_post - 0.3 * s), (r1, z_post)]
            C.lathe(mb, prof, sides, body, base=(x, 0, 0))
            # nemaki: black sleeve at the foot, 12-15 mm proud, with a rolled top edge
            if lod <= 1:
                sl = [(r0 + 0.014, base_h), (r0 + 0.014, base_h + sleeve_h - 0.02 * s), (r0 + 0.006, base_h + sleeve_h),
                      (r0 - 0.002, base_h + sleeve_h)]
            else:
                sl = [(r0 + 0.014, base_h), (r0 + 0.014, base_h + sleeve_h)]
            C.lathe(mb, sl, sides, cap, base=(x, 0, 0), closed=lod >= 2)
            # daiwa: black ring where the post meets the shimaki
            dr = [(r1 + 0.02, z_shim - 0.10 * s), (r1 + 0.03, z_shim - 0.06 * s), (r1 + 0.03, z_shim),
                  (r1 - 0.005, z_shim)]
            C.lathe(mb, dr if lod <= 1 else [(r1 + 0.025, z_shim - 0.09 * s), (r1 + 0.025, z_shim)], sides, cap,
                    base=(x, 0, 0), closed=True)
        else:
            C.lathe(mb, [(r0 * 1.05, 0.0), (r1, z_post)], sides, body, base=(x, 0, 0), closed=False)
        for v in {v for f in mb._new_faces(lay) for v in f.verts}:
            v.co.x += sg * lean * (z_post - v.co.z)

    # ---- footings (unsheared, under the foot of each post)
    if lod <= 2:
        for sg in (-1, 1):
            xb = sg * (half_span + lean * (z_post - base_h))
            if P['base'] == 'kamebara':
                segs = C.lod_pick(lod, 20, 10, 6)
                rb = min(0.29, r0 * 2.2)
                C.lathe(mb, [(rb, 0.0), (rb * 0.98, base_h * 0.35), (rb * 0.8, base_h * 0.8), (r0 * 1.1, base_h),
                             (0.0, base_h)], segs, foot, base=(xb, 0, 0))
            elif P['base'] == 'daiishi':
                segs = C.lod_pick(lod, 8, 8, 6)                       # octagonal turned stone
                rb = min(0.27, r0 * 2.0)
                C.lathe(mb, [(rb, 0.0), (rb, base_h * 0.7), (rb * 0.9, base_h), (0.0, base_h)], segs, foot,
                        base=(xb, 0, 0), phase=math.pi / 8)
            else:                                                        # sea: craggy wet basalt rocks
                npts = C.lod_pick(lod, 16, 10, 8)
                ra, rb_ = C.rng(seed, f'rock{sg}'), C.rng(seed, f'rubble{sg}')
                C.hull_rock(mb, (xb, 0.0, 0.10), (0.33, 0.27, 0.36), foot, ra, npts=npts, ground=0.0)
                if lod <= 1:
                    C.hull_rock(mb, (xb + sg * 0.30, rb_.uniform(-0.08, 0.08), 0.02), (0.17, 0.15, 0.16), foot, rb_,
                                npts=C.lod_pick(lod, 12, 8), ground=0.0)
                    C.hull_rock(mb, (xb - sg * 0.22, rb_.uniform(0.06, 0.12), 0.0), (0.13, 0.12, 0.11), foot, rb_,
                                npts=C.lod_pick(lod, 10, 8), ground=0.0)

    # ---- nuki: passes through the posts, ends protrude, wedges (kusabi) outside each post
    nx = half_span + r1 + P['nuki_over']
    if lod == 0:
        C.chamfered_bar(mb, (0, 0, z_nk - nk_t / 2), (2 * nx, nk_d, nk_t), body, ch=0.012, axis='x')
    else:
        mb.box((0, 0, z_nk - nk_t / 2), (2 * nx, nk_d, nk_t), body)
    if lod <= 1:
        for sg in (-1, 1):
            xw = sg * (half_span + lean * (z_post - z_nk) + r1 + 0.03)
            mb.box((xw, 0, z_nk - nk_t / 2), (0.05, nk_d * 1.2, nk_t * 0.55), body)

    # ---- gakuzuka (central strut) and plaque
    if lod <= 2:
        gz0, gz1 = z_nk, z_shim
        mb.box((0, 0, (gz0 + gz1) / 2), (0.12 * s, 0.09 * s, gz1 - gz0), body)
        if P['plaque']:
            ph = min(0.46 * s, (gz1 - gz0) * 0.86)
            pw = 0.30 * s
            pz = (gz0 + gz1) / 2
            yf = 0.045 * s + 0.03
            if lod <= 1:
                C.board(mb, (0, yf, pz), (pw, 0.05, ph), body, bevel=0.008 if lod == 0 else 0.0)   # frame
                C.board(mb, (0, yf + 0.026, pz), (pw - 0.06, 0.01, ph - 0.06), cap, bevel=0.0)    # field
                C.text_solid(mb, P['text'], 0.0, pz, yf + 0.031, (ph - 0.1) / (len(P['text']) * 1.12), gold,
                             depth=0.008, vertical=True, gap=1.12, res=C.lod_pick(lod, 2, 1))
            else:
                mb.box((0, yf, pz), (pw, 0.05, ph), cap)
                n = len(P['text'])
                ch = (ph - 0.1) / n
                for i in range(n):
                    mb.box((0, yf + 0.03, pz + ((n - 1) / 2 - i) * ch), (pw * 0.45, 0.01, ch * 0.7), gold)

    # ---- shimaki (under-beam) and kasagi (black, upswept)
    half_k = W / 2
    if lod <= 2:
        half_s = half_k - 0.12 * s
        _beam(mb, half_s, z_shim, st, sd, sd, up * 0.82, P['p_exp'], nst, prof_lv, body)
        _beam(mb, half_k, z_kas, kt, kdt, kdb, up, P['p_exp'], nst, prof_lv, cap)
    else:
        _beam(mb, half_k, z_shim, kt + st, kdt, kdb, up, P['p_exp'], nst, 0, cap)

    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()},
                     kz_lights=[])
    return o
