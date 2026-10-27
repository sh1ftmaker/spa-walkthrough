"""Timber piers, cross-bracing and stone footings (pier_trestle): heavy square posts on cut-stone footings
standing in white water, X / K cross-bracing, iron straps, a dark cap beam on lacquered corbels. Per bay.

Targets (measured):
  refs/gen/sheet-mod-kawagiri.png #1 'Kawagiri dining pod' (front + side, 5.0 m bar = 318 px in the 2x
  crop -> 64 px/m; crop .scratch/op20/m_pod.png): posts 0.35-0.40 m square; stone footings 1.0-1.1 m wide
  at the base, ~0.8 m at the top, 0.6-0.7 m tall, rough coursed blocks; corbels on the post heads under a
  0.3 m beam; knee braces at 45 deg; X bracing in the side bay.
  lookbook 06 (crops .scratch/op20/c06_piers*.png; seated diners ~1.2 m): posts ~0.45 m, footings
  ~1.2-1.5 m tall truncated pyramids of 2-3 stone courses, deck 3-4 m over the water, X braces between
  posts below the deck, dark iron bands round the posts near the foot and the head, boulders and white
  water round the footings. lookbook 07 section A-A (5 m bar): posts 0.4, footings 0.8 x 1.0 m tall.
  Row: post 0.3-0.5, height 2-6, bay 2.5-5, bracing X|K|none, footing h 0.6-1.5, per bay 4 x 0.5 x 4 m.
  Built (seed 1): bay 4.0 m between post centres, post 0.40, overall height 4.0 m to the cap-beam top,
  footing 1.0 m tall in 3 courses, 0.86 -> 0.66 m wide (batter), cap beam 0.30 x 0.34 on 1.2 m
  lacquer_dark corbels, braces 0.12 x 0.22, two iron straps per post, iron shoe 0.25 tall at the post foot.

Proxy: assets.json has no w/d/h for pier_trestle (genlib.proxy falls back to 1 x 1 x 1, so the check
reports w / d / h for every variant). Proposed proxy: w 5.0, d 1.1, h 4.0 (one 4 m bay with its two posts,
footings and boulders; d is the footing + boulders, the timber line itself is 0.5 deep).

Parameters build(lod, seed, **p)
  bracing   X | K | none (default cycles with the seed)
  post      0.30-0.50 post size (default per seed 0.40 / 0.45 / 0.32)
  height    2-6 m overall to the cap-beam top (default 4.0 / 4.0 / 3.2)
  bay       2.5-5 m between post centres (default 4.0 / 3.6 / 3.0)
  bays      number of bays in the run (default 1); posts = bays + 1
  footing   footing height 0.6-1.5 (default 1.0 / 1.3 / 0.7)
  straps    iron straps per post 1-3 (default 2 / 3 / 1)
  end_posts (first, last) posts present (default both; chained runs drop one)
  rocks     boulders round each footing (default True)
Seeds change shape: bracing style (X / K chevron + mid girt / knee braces only), post size, bay, height,
footing height and course count (3 / 3 / 2), footing batter, strap count, boulder layout.
LOD0 chamfered posts, braces and beams, coursed footing blocks (2 per course, joints alternate) with
bevelled edges, 14-point boulders, straps, shoes, brace plates with 4 bolt heads. LOD1 same parts as boxes,
one block per course, 8-point boulders, no bolts. LOD2 one tapered footing block, posts, beam, braces as
boxes, one strap per post, the largest boulder per footing. LOD3 footing frusta, post and beam boxes,
braces as cards (~50 tris).
Materials: posts / braces / girts / cap beam hinoki dark_timber, corbels lacquer_dark (on the cap beam it
glared pale grey under the warm key, so it stays on the small corbels), straps / shoes /
plates iron, footings + boulders basalt_wet (wetness 0.75 at the water course, 0.45 above).
Props: kz_cap_z (top of the cap beam, where deck stringers bear), kz_posts [[x, y], ...], kz_params.
Animation none. Lighting lightmap.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_boardwalk as K

ASSET = 'pier_trestle'
FEATURES = ['heavy square posts', 'X cross-bracing', 'iron straps', 'cut-stone footings']
STYLES = ['X', 'K', 'none']
SD = {1: dict(post=0.40, height=4.0, bay=4.0, footing=1.0, straps=2, courses=3, batter=0.10),
      2: dict(post=0.45, height=4.0, bay=3.6, footing=1.3, straps=3, courses=3, batter=0.14),
      3: dict(post=0.32, height=3.2, bay=3.0, footing=0.7, straps=1, courses=2, batter=0.07)}
X = Vector((1, 0, 0)); Y = Vector((0, 1, 0)); Zv = Vector((0, 0, 1))


def build(lod, seed, bracing=None, post=None, height=None, bay=None, bays=1, footing=None, straps=None,
          end_posts=(True, True), rocks=True):
    D = SD[(seed - 1) % 3 + 1]
    bracing = bracing or C.cycle(seed, STYLES)
    ps = post or D['post']
    H = height or D['height']
    bay = bay or D['bay']
    fh = footing or D['footing']
    nstrap = straps or D['straps']
    g = C.rng(seed, ASSET + ':layout')
    batter = D['batter'] * g.uniform(0.85, 1.15)

    mb = genlib.MeshBuilder()
    m_post = mb.slot('hinoki', variant='dark_timber')
    m_cap = mb.slot('hinoki', variant='dark_timber', wear=0.25)    # cap beam (lacquer_dark glared pale grey under the key)
    m_cor = mb.slot('lacquer_dark')                                 # corbels
    m_iron = mb.slot('iron')
    m_stone_w = mb.slot('basalt_wet', wetness=0.75)
    m_stone = mb.slot('basalt_wet', wetness=0.45)

    cap_h, cap_d = 0.34, 0.30
    cor_h, cor_l = 0.22, ps * 3.0
    z_cap0 = H - cap_h                 # cap beam underside
    z_post_top = z_cap0 - cor_h        # corbel underside / post top
    xs = [-bay * bays / 2 + bay * i for i in range(bays + 1)]
    keep = [i for i in range(bays + 1) if not ((i == 0 and not end_posts[0]) or (i == bays and not end_posts[1]))]
    fw0 = ps * 2.15                    # footing base width (both axes)
    fw1 = fw0 * (1 - 2 * batter) * 0.95

    # ---------------- layout drawn before any LOD branch
    rf = C.rng(seed, ASSET + ':footings')
    courses = []
    nc = D['courses']
    for i in keep:
        cs = []
        z = 0.0
        for k in range(nc):
            hk = fh / nc * rf.uniform(0.9, 1.1) if k < nc - 1 else fh - z
            w0 = fw0 + (fw1 - fw0) * (z / fh); w1 = fw0 + (fw1 - fw0) * ((z + hk) / fh)
            cs.append(dict(z0=z, z1=z + hk, w0=w0, w1=w1, split=rf.uniform(0.38, 0.62), axis=k % 2,
                           jit=(rf.uniform(-0.015, 0.015), rf.uniform(-0.015, 0.015)), yaw=rf.uniform(-0.03, 0.03)))
            z += hk
        courses.append((i, cs))
    rr = C.rng(seed, ASSET + ':rocks')
    boulders = []
    if rocks:
        for i in keep:
            for k in range(2 if seed % 3 != 2 else 3):
                side = -1 if k % 2 == 0 else 1
                rx = rr.uniform(0.22, 0.42)
                boulders.append(dict(c=(xs[i] + side * (fw0 / 2 + rx * 0.35), rr.uniform(-0.25, 0.25)),
                                     size=(rx, rr.uniform(0.2, 0.32), rr.uniform(0.18, 0.36)), rot=rr.uniform(0, math.pi),
                                     big=rx, k=len(boulders)))

    # ---------------- footings
    for i, cs in courses:
        x = xs[i]
        if lod == 0:
            for k, c in enumerate(cs):
                mi = m_stone_w if k == 0 else m_stone
                hz = c['z1'] - c['z0'] - 0.012
                wm = (c['w0'] + c['w1']) / 2
                if c['axis'] == 0:      # two blocks split along X
                    xa = -wm / 2 + wm * c['split']
                    for a0, a1 in ((-wm / 2, xa), (xa, wm / 2)):
                        C.board(mb, (x + (a0 + a1) / 2 + c['jit'][0], c['jit'][1], c['z0'] + hz / 2 + 0.006),
                                (a1 - a0 - 0.012, wm, hz), mi, bevel=0.03, rot=(0, 0, c['yaw']))
                else:
                    ya = -wm / 2 + wm * c['split']
                    for a0, a1 in ((-wm / 2, ya), (ya, wm / 2)):
                        C.board(mb, (x + c['jit'][0], (a0 + a1) / 2 + c['jit'][1], c['z0'] + hz / 2 + 0.006),
                                (wm, a1 - a0 - 0.012, hz), mi, bevel=0.03, rot=(0, 0, c['yaw']))
        elif lod == 1:
            for k, c in enumerate(cs):
                K.frustum(mb, (x + c['jit'][0], c['jit'][1]), c['w0'], c['w0'], c['w1'], c['w1'], c['z0'], c['z1'] - 0.004,
                          m_stone_w if k == 0 else m_stone, yaw=c['yaw'], top=True)
        else:
            K.frustum(mb, (x, 0), fw0, fw0, fw1, fw1, 0.0, fh, m_stone, top=(lod == 2))
    for b in boulders:
        if lod >= 2 and b['k'] % (3 if seed % 3 == 2 else 2):
            continue
        if lod == 3:
            continue
        npts = C.lod_pick(lod, 14, 8, 6)
        rk = C.rng(seed, ASSET + ':rock%d' % b['k'])
        C.hull_rock(mb, (b['c'][0], b['c'][1], b['size'][2] * 0.35), b['size'], m_stone_w, rk, npts=npts,
                    ground=0.0, rot=b['rot'], rmin=0.8)

    # ---------------- posts, shoes, straps
    for i in keep:
        x = xs[i]
        a = Vector((x, 0, fh)); b = Vector((x, 0, z_post_top + 0.02))
        if lod == 0:
            K.beam(mb, a, b, X, ps, ps, m_post, kind='oct', ch=0.025, caps=(False, False))
        else:
            K.beam(mb, a, b, X, ps, ps, m_post, caps=(False, False))
        if lod <= 1:
            K.beam(mb, a - Vector((0, 0, 0.02)), a + Vector((0, 0, 0.25)), X, ps + 0.03, ps + 0.03, m_iron, caps=(False, True))
        L_post = z_post_top - fh
        zs = [fh + 0.25 + L_post * (0.18 + 0.5 * k / max(1, nstrap - 1) if nstrap > 1 else 0.22) for k in range(nstrap)]
        zs.append(z_post_top - 0.14)                       # head strap under the corbel
        if lod == 2:
            zs = [zs[-1]]
        if lod <= 2:
            for z in zs:
                K.beam(mb, Vector((x, 0, z - 0.04)), Vector((x, 0, z + 0.04)), X, ps + 0.022, ps + 0.022, m_iron,
                       caps=(False, False))

    # ---------------- corbels + cap beam
    x0, x1 = xs[0] - ps / 2 - 0.28, xs[-1] + ps / 2 + 0.28
    for i in keep:
        x = xs[i]
        lo, hi = max(x - cor_l / 2, x0 + 0.05), min(x + cor_l / 2, x1 - 0.05)
        if lod <= 2:
            kind = 'oct' if lod == 0 else 'rect'
            K.beam(mb, Vector((lo, 0, z_post_top + cor_h / 2)), Vector((hi, 0, z_post_top + cor_h / 2)), Y, ps * 0.9, cor_h, m_cor,
                   kind=kind, ch=0.02)
    if lod == 3:
        K.beam(mb, Vector((x0, 0, z_post_top + (cap_h + cor_h) / 2)), Vector((x1, 0, z_post_top + (cap_h + cor_h) / 2)), Y,
               cap_d, cap_h + cor_h, m_cap)
    else:
        K.beam(mb, Vector((x0, 0, z_cap0 + cap_h / 2)), Vector((x1, 0, z_cap0 + cap_h / 2)), Y, cap_d, cap_h, m_cap,
               kind='oct' if lod == 0 else 'rect', ch=0.025)

    # ---------------- bracing (members on the front and back faces of the posts)
    bt, bd = 0.12, 0.22
    yf = ps / 2 + bt / 2
    plates = []
    kind = 'oct' if lod == 0 else 'rect'

    def member(p0, p1, y, card=False):
        p0 = Vector((p0[0], y, p0[1])); p1 = Vector((p1[0], y, p1[1]))
        if lod == 3:
            d = (p1 - p0).normalized(); nrm = Vector((-d.z, 0, d.x)) * bd / 2
            K.quad(mb, [p0 - nrm, p1 - nrm, p1 + nrm, p0 + nrm], m_post)
        else:
            K.beam(mb, p0, p1, Y, bt, bd, m_post, kind=kind, ch=0.015)

    for j in range(bays):
        xa, xb = xs[j], xs[j + 1]                     # face members lap over the post: run to its centre line
        ga, gb = xs[j] + ps / 2 - 0.02, xs[j + 1] - ps / 2 + 0.02   # girts frame into the post sides
        zl, zh = fh + 0.35, z_post_top - 0.12
        if bracing == 'X':
            member((xa, zl), (xb, zh), yf); plates += [(xa, zl, yf), (xb, zh, yf)]
            if lod == 3:
                member((xa, zh), (xb, zl), yf)
            else:
                member((xa, zh), (xb, zl), -yf); plates += [(xa, zh, -yf), (xb, zl, -yf)]
        elif bracing == 'K':
            zm = fh + (z_post_top - fh) * 0.42
            member((ga, zm), (gb, zm), 0.0 if lod < 3 else yf)                      # mid girt between the posts
            xm = (xa + xb) / 2
            member((xm - 0.1, zm + bd / 2), (xa, zh), yf); member((xm + 0.1, zm + bd / 2), (xb, zh), yf)
            plates += [(xa, zh, yf), (xb, zh, yf), (xa, zm, 0.0), (xb, zm, 0.0)]
        else:
            kl = min(1.0, (xb - xa) * 0.3)
            zm = fh + (z_post_top - fh) * 0.40
            if lod < 3:
                member((ga, zm), (gb, zm), 0.0)
                plates += [(xa, zm, 0.0), (xb, zm, 0.0)]
            member((xa, z_post_top - kl), (xa + kl, z_post_top), yf)
            member((xb, z_post_top - kl), (xb - kl, z_post_top), yf)
            plates += [(xa, z_post_top - kl, yf), (xb, z_post_top - kl, yf)]
    # iron plates where braces meet the posts (over the lap, on the brace face), 4 bolt heads at LOD0
    if lod <= 1:
        for (x, z, y) in plates:
            sg = 1 if y >= 0 else -1
            yy = sg * (ps / 2 + (bt if abs(y) > 1e-3 else 0.0) + 0.007)
            c = Vector((x, yy, z))
            K.beam(mb, c - Zv * 0.14, c + Zv * 0.14, X, 0.26, 0.014, m_iron)
            if lod == 0:
                for dx in (-0.08, 0.08):
                    for dz in (-0.08, 0.08):
                        q = c + Vector((dx, sg * 0.006, dz))
                        K.beam(mb, q, q + Vector((0, sg * 0.014, 0)), X, 0.03, 0.03, m_iron, caps=(False, True))

    C.centre_base(mb, centre_x=True, centre_y=False)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    K.grain_uv(o, [m_post, m_cap, m_cor])
    C.set_json_props(o, kz_cap_z=round(H, 3), kz_posts=[[round(xs[i], 3), 0.0] for i in keep], kz_anim=dict(type='none'),
                     kz_params=dict(bracing=bracing, post=ps, height=H, bay=bay, bays=bays, footing=fh, straps=nstrap,
                                    courses=nc))
    return o
