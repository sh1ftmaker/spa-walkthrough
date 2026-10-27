"""Kawagiri restaurant sign gate (kawagiri_sign_gate): hinoki post-and-beam gate on dry-laid stone footings.

TARGETS (refs/gen/sheet-mod-kawagiri.png panel 2, crop .scratch/op18/m_gate.png at 2x)
  Labels 5.0 m x 7.5 m. The drawing's two bars disagree (7.5 m bar = 72.5 px/m, 5.0 m bar = 117 px/m), so
  heights are taken off the 7.5 m bar and widths off the 5.0 m bar, then scaled so the post tops land on 7.5 m:
    stone footings 1.3 m tall (1.0-1.15 m wide), a dark timber plinth block on each, posts ~0.45 m;
    ASYMMETRIC legs: viewer-left leg is TWO posts ~1.0 m apart carrying the neon panel between them, the
    viewer-right leg is one post with the red chochin and a small andon on its front;
    neon panel 0.82 x 3.0 m (magenta 川霧 over a cyan crest panel, z 3.0-6.05);
    gold 川霧 / KAWAGIRI board between the legs: 2.4 x 1.5 m (drawing aspect 1.7), z 4.7-6.2, hung between a
    tie beam (nuki, z 4.35-4.6) and the top beam (keta, z 6.3-6.6) with corbel brackets under the keta;
    tiled cap roof (kawara) eave 6.75 m, ridge ~7.15 m, span 5.2 m (row 4-5.6) with upturned eaves;
    aqueduct = open timber U-trough riding the ridge (the cyan strip on the front view; the side view spills it).
  Lookbook 06 / sheet-ref-cliff-cavern #03: the same gold board and magenta neon on dark timber.
  Depth: the side view shows a gabled cap roof ~1.8-2 m deep; the proxy d 0.8 m only covers the posts, so the
  default roof is 1.9 m deep (proposed proxy d 2.0, reported).

FEATURES kept at every LOD: posts on stone footings, tiled cap roof, gold 川霧 board, neon panel, red chochin,
  aqueduct trough on the roof ridge.  LOD1: no bevels, lower resolution, glyphs res 1, no Latin line.
  LOD2: text as blocks, neon as flat ribbons, footings keep one cobble course.  LOD3: boxes + roof + glow quads.

PARAMETERS  span 4.0-5.6 (default 5.2) | h 7.5 | post 0.38-0.5 (0.45) | footing_h 1.0-1.5 (1.3) |
  roof 'gable' | 'irimoya' | 'hip' | board_w / board_h (sign sizes) | neon_h 2.6-3.2 | neon_side +1 (viewer-left,
  sheet) / -1 | chochin 1 | 2 | roof_d 1.6-2.1
SEEDS change shape: roof type cycles (gable / irimoya / hip), span, post size, footing height, board size,
  neon panel height, one or two chochin, which side the neon leg stands on (seed 2 mirrors the legs; text
  still reads left-to-right), trough spout end.
MATERIALS (slots by part): posts/beams hinoki dark_timber; plinth blocks + corbels hinoki walnut; board field
  lacquer_black, board frame hinoki walnut, letters gold_leaf; neon neon_tube (magenta) + neon_tube cyan on a
  lacquer_black backing; caps and straps bronze smooth; footings basalt_dry; roof kawara + lacquer_dark;
  chochin lantern_paper red (tint 1, 0.05, 0.02; emissive 0.5) with lacquer_black caps; andon lantern_andon.
ANIMATION kz_anim shader_flicker (neon buzz) on the neon slots. LIGHTS kz_lights: neon emissive, chochin, andon.
WATER kz_water_path along the trough, kz_spill at the spout end (runtime fx).
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_kawagiri_pod as KK
import kzgeo_roof_tiled as KR

ASSET = 'kawagiri_sign_gate'
FEATURES = ['hinoki post-and-beam gate on stone footings', 'tiled cap roof', 'gold 川霧 board', 'neon panel',
            'red chochin', 'aqueduct trough on the beam']
ROOFS = ['gable', 'irimoya', 'hip']


def params(seed, span=None, h=None, post=None, footing_h=None, roof=None, board_w=None, board_h=None,
           neon_h=None, neon_side=None, chochin=None, roof_d=None):
    g = C.rng(seed, 'layout')
    P = dict(span=g.uniform(4.6, 5.4), post=g.uniform(0.4, 0.48), footing_h=g.uniform(1.05, 1.45),
             board_k=g.uniform(0.9, 1.08), neon_h=g.uniform(2.7, 3.1), roof_d=g.uniform(1.7, 2.0))
    if seed == 1:
        P.update(span=5.2, post=0.45, footing_h=1.3, board_k=1.0, neon_h=3.05, roof_d=1.9)
    P['span'] = span or P['span']
    P['h'] = h or 7.5
    P['post'] = post or P['post']
    P['footing_h'] = footing_h or P['footing_h']
    P['roof'] = roof or C.cycle(seed, ROOFS)
    P['neon_h'] = neon_h or P['neon_h']
    P['roof_d'] = roof_d or P['roof_d']
    P['neon_side'] = neon_side or (1 if seed % 3 != 2 else -1)
    P['chochin'] = chochin or (1 if seed % 2 else 2)
    P['board_h'] = board_h or 1.5 * P['board_k']
    P['board_w'] = board_w
    P['spout'] = C.pick(seed, 'spout', [-1, 1])
    return P


def build(lod, seed, span=None, h=None, post=None, footing_h=None, roof=None, board_w=None, board_h=None,
          neon_h=None, neon_side=None, chochin=None, roof_d=None, **_):
    P = params(seed, span, h, post, footing_h, roof, board_w, board_h, neon_h, neon_side, chochin, roof_d)
    S, H, Ps, FH = P['span'], P['h'], P['post'], P['footing_h']
    sg = P['neon_side']
    mb = genlib.MeshBuilder()
    M = dict(
        wood=mb.slot('hinoki', variant='dark_timber'), walnut=mb.slot('hinoki', variant='walnut'),
        field=mb.slot('lacquer_black'), gold=mb.slot('gold_leaf'),
        neon_m=mb.slot('neon_tube'), neon_c=mb.slot('neon_tube', variant='cyan'), back=mb.slot('lacquer_black'),
        bronze=mb.slot('bronze', variant='smooth'), stone=mb.slot('basalt_dry'), tile=mb.slot('kawara'),
        roof_d=mb.slot('lacquer_dark', wear=0.1), iron=mb.slot('iron', wear=0.2),
        paper=mb.slot('lantern_paper', tint=(1.0, 0.05, 0.02), emissive_level=0.5),
        andon=mb.slot('lantern_andon', emissive_level=0.9))
    cho_m = dict(paper=M['paper'], cap=M['back'], ink=M['back'], cord=M['iron'])
    lights = []

    # ---------------- layout (x: +X is the viewer's LEFT when standing on +Y)
    xo = S / 2 - 0.55                       # outer post centres
    gap = 1.0
    x_tw = [sg * xo, sg * (xo - gap)]       # twin leg (neon)
    x_si = -sg * xo                         # single post (chochin)
    z_post0 = FH + 0.3
    z_keta0, z_keta1 = H - 1.2, H - 0.88
    z_nuki0, z_nuki1 = 4.35, 4.6
    z_e = H - 0.75                           # roof eave line
    # ---------------- footings + plinths
    rf = C.rng(seed, 'footings')
    for x in x_tw + [x_si]:
        KK.stone_footing(mb, lod, rf, (x, 0, 0), 1.05, 1.1, FH, M['stone'])
        KK.timber(mb, lod, (x, 0, FH + 0.15), (Ps + 0.18, Ps + 0.18, 0.3), M['walnut'], 0.02)
    # ---------------- posts (through the roof, bronze caps)
    for x in x_tw + [x_si]:
        KK.post(mb, lod, x, 0, z_post0, H - 0.06, Ps, M['wood'])
        if lod <= 2:
            mb.box((x, 0, H - 0.03), (Ps + 0.06, Ps + 0.06, 0.06), M['bronze'])
            if lod == 0:                     # bronze straps at the plinth and under the nuki
                for zz in (z_post0 + 0.12, z_nuki0 - 0.15):
                    mb.box((x, 0, zz), (Ps + 0.02, Ps + 0.02, 0.06), M['bronze'])
    # ---------------- beams
    KK.beam_x(mb, lod, -S / 2 + 0.3, S / 2 - 0.3, 0, z_keta0, z_keta1, 0.36, M['wood'])
    x_in = sg * (xo - gap)
    KK.beam_x(mb, lod, min(x_in, x_si) - Ps / 2 - 0.25, max(x_in, x_si) + Ps / 2 + 0.25, 0, z_nuki0, z_nuki1, 0.24, M['wood'])
    if lod <= 2:
        for zz in (2.6, z_keta0 - 0.45):     # twin-leg ties
            KK.beam_x(mb, lod, min(x_tw) - Ps / 2 - 0.12, max(x_tw) + Ps / 2 + 0.12, 0, zz, zz + 0.2, 0.2, M['wood'])
    if lod <= 1:                             # corbel brackets under the keta (hijiki), both sides of each post
        for x in x_tw + [x_si]:
            for s in (-1, 1):
                xc = x + s * (Ps / 2 + 0.28)
                if abs(xc) < S / 2 - 0.3:
                    KK.timber(mb, lod, (xc, 0, z_keta0 - 0.09), (0.56, 0.26, 0.18), M['walnut'], 0.015)
    # ---------------- gold board
    bx0 = min(x_in, x_si) + Ps / 2 + 0.12
    bx1 = max(x_in, x_si) - Ps / 2 - 0.12
    bw = P['board_w'] or (bx1 - bx0)
    bh = min(P['board_h'], z_keta0 - z_nuki1 - 0.2)
    bxc = (bx0 + bx1) / 2
    bzc = (z_nuki1 + z_keta0) / 2
    yb = 0.0
    fr = 0.11
    KK.timber(mb, lod, (bxc, yb, bzc), (bw, 0.1, bh), M['field'], 0.01)
    yf = yb + 0.05
    if lod <= 2:
        for (cx, cz, sx, sz) in ((bxc, bzc + bh / 2 - fr / 2, bw + 0.04, fr), (bxc, bzc - bh / 2 + fr / 2, bw + 0.04, fr),
                                 (bxc - bw / 2 + fr / 2, bzc, fr, bh), (bxc + bw / 2 - fr / 2, bzc, fr, bh)):
            KK.timber(mb, lod, (cx, yb + 0.02, cz), (sx, 0.14, sz), M['walnut'], 0.012)
        for x in (bxc - bw * 0.3, bxc + bw * 0.3):          # struts to the nuki and keta
            mb.box((x, yb, (z_nuki1 + bzc - bh / 2) / 2), (0.14, 0.12, bzc - bh / 2 - z_nuki1 + 0.02), M['wood'])
            mb.box((x, yb, (z_keta0 + bzc + bh / 2) / 2), (0.14, 0.12, z_keta0 - bzc - bh / 2 + 0.02), M['wood'])
    th = bh * 0.46
    if lod <= 1:
        C.text_solid(mb, '川霧', bxc, bzc + bh * 0.1, yf + 0.02, th, M['gold'], depth=0.014, res=2 - lod,
                     vertical=False)
        if lod == 0:
            C.tracked_text(mb, 'KAWAGIRI', bxc, bzc - bh * 0.3, yf + 0.02, bh * 0.08, M['gold'], depth=0.008, tracking=0.35)
    elif lod == 2:
        for i in range(2):
            mb.box((bxc + (0.5 - i) * th * 1.1, yf + 0.03, bzc + bh * 0.1), (th * 0.8, 0.02, th * (0.9 - 0.12 * i)), M['gold'])
        mb.box((bxc, yf + 0.03, bzc - bh * 0.3), (bw * 0.45, 0.02, bh * 0.06), M['gold'])
    else:
        KK.quad_y(mb, bxc, yf + 0.01, bzc + bh * 0.05, bw * 0.55, bh * 0.5, M['gold'])
    # ---------------- neon panel on the twin leg (front)
    nx = sg * (xo - gap / 2)
    nw = 0.82
    nz0 = 6.05 - P['neon_h']
    nz1 = 6.05
    ny = Ps / 2 + 0.01
    split = nz0 + P['neon_h'] * 0.34
    if lod <= 2:
        KK.timber(mb, lod, (nx, ny + 0.035, (nz0 + nz1) / 2), (nw, 0.07, nz1 - nz0), M['back'], 0.008)
        yt = ny + 0.07 + 0.018
        tr = 0.011
        nc = C.lod_pick(lod, 3, 1, 1)
        m = 0.05
        KK.neon_line(mb, lod, [(nx + px, (split + nz1) / 2 + pz) for px, pz in KK.rrect_pts(nw - 2 * m, nz1 - split - m - 0.02, 0.05, nc)],
                     yt, tr, M['neon_m'], closed=True)
        KK.neon_line(mb, lod, [(nx + px, (nz0 + split) / 2 + pz) for px, pz in KK.rrect_pts(nw - 2 * m, split - nz0 - m - 0.02, 0.05, nc)],
                     yt, tr, M['neon_c'], closed=True)
        ih = nz1 - split - m - 0.2
        size = min((nw - 2 * m) * 0.72, ih / 2 / 1.08)
        for i, ch in enumerate('川霧'):
            KK.neon_glyph(mb, lod, ch, nx, nz1 - m - 0.08 - (i + 0.5) * ih / 2, size, yt, tr, M['neon_m'])
        # tomoe crest: circle + three comma arcs
        cz = (nz0 + split) / 2
        R = min(nw - 2 * m, split - nz0 - m) * 0.36
        segs = C.lod_pick(lod, 16, 10, 8)
        KK.neon_line(mb, lod, [(nx + R * math.cos(2 * math.pi * k / segs), cz + R * math.sin(2 * math.pi * k / segs)) for k in range(segs)],
                     yt, tr, M['neon_c'], closed=True)
        if lod <= 1:
            for j in range(3):
                a0 = 2 * math.pi * j / 3
                n = C.lod_pick(lod, 6, 3)
                KK.neon_line(mb, lod, [(nx + R * 0.66 * t * math.cos(a0 + 2.4 * t), cz + R * 0.66 * t * math.sin(a0 + 2.4 * t))
                                       for t in [0.15 + 0.85 * i / n for i in range(n + 1)]], yt, tr, M['neon_c'])
    else:
        mb.box((nx, ny + 0.035, (nz0 + nz1) / 2), (nw, 0.07, nz1 - nz0), M['back'])
        KK.quad_y(mb, nx, ny + 0.075, (split + nz1) / 2, nw * 0.75, (nz1 - split) * 0.85, M['neon_m'])
        KK.quad_y(mb, nx, ny + 0.075, (nz0 + split) / 2, nw * 0.75, (split - nz0) * 0.8, M['neon_c'])
    # ---------------- chochin + andon on the single post (and optionally the twin leg's outer post)
    cho_posts = [x_si] + ([x_tw[0]] if P['chochin'] == 2 and lod < 3 else [])   # LOD3 keeps one chochin
    for x in cho_posts:
        za = z_nuki0 - 0.08
        ya = Ps / 2 + 0.32
        if lod <= 2:
            mb.box((x, (Ps / 2 + ya) / 2, za), (0.04, ya - Ps / 2 + 0.04, 0.04), M['iron'])
        cen = KK.chochin(mb, cho_m, lod, (x, ya, za), r=0.27, h=0.78, cord=0.1)
        lights.append(C.light_entry(cen, color_k=1900, watts=30, color=[1.0, 0.25, 0.12]))
    if lod <= 2:
        for sy in (1, -1):
            yy = sy * (Ps / 2 + 0.2)
            cen = KK.andon(mb, dict(iron=M['iron'], paper=M['andon']), lod, (x_si, yy, 4.95), size=0.2, height=0.34,
                           arm=(0, -sy * 0.2))
            lights.append(C.light_entry(cen, color_k=2200, watts=12))
    # ---------------- roof (dry run for its height, then lift so the ridge sits under the post caps)
    mats = dict(tile=M['tile'], ridge=M['tile'], wood=M['wood'], wood_d=M['roof_d'], iron=M['iron'])
    hd = P['roof_d'] / 2
    budget = genlib.budget_of(ASSET)
    rb = int(budget[lod] * C.lod_pick(lod, 0.3, 0.3, 0.3, 0.14)) if budget else None
    vlay = mb.bm.verts.layers.int.get('_vold') or mb.bm.verts.layers.int.new('_vold')
    for v in mb.bm.verts:
        v[vlay] = 1
    info = KR.roof_into(mb, mats, lod, P['roof'], S / 2 - 0.18, hd, z_e=0.0, pitch=C.lod_pick(0, 30), eave=0.5, eave_s=0.32,
                        up=0.14, tp=0.22, budget=rb)
    if info['notes']:
        print(f'{ASSET} LOD{lod} s{seed} roof resolution fallback: {info["notes"]}')
    vs = [v for v in mb.bm.verts if v[vlay] == 0]
    top_target = H - 0.38
    dz = top_target - max(v.co.z for v in vs)
    for v in vs:
        v.co.z += dz
    wall_top = info['wall_top'] + dz
    ridge_z = info['ridge_z'] + dz
    if wall_top > z_keta1 + 0.02:             # close the gap between the keta and the roof's wall plate
        KK.beam_x(mb, lod, -S / 2 + 0.3, S / 2 - 0.3, 0, z_keta1 - 0.01, wall_top + 0.02, 0.3, M['wood'])
    # ---------------- aqueduct trough on the ridge
    ztr = top_target - 0.04
    xa, xb = -S / 2 + 0.2, S / 2 - 0.2
    KK.water_trough(mb, lod, [(xa, 0, ztr), (xb, 0, ztr)], 0.34, 0.24, 0.04, M['wood'])
    if lod <= 1:
        for x in (xa + 0.4, 0.0, xb - 0.4):     # saddles + bronze straps
            mb.box((x, 0, ztr - 0.03), (0.16, 0.42, 0.08), M['walnut'])
            mb.box((x, 0, ztr + 0.12), (0.05, 0.36, 0.25), M['bronze'])
    sp = P['spout']
    xs_end = sp * (S / 2 - 0.2)
    if lod <= 2:                            # short spout lip at the spill end
        mb.box((xs_end + sp * 0.12, 0, ztr + 0.04), (0.26, 0.2, 0.05), M['wood'])
    C.centre_base(mb, centre_x=True, centre_y=True)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    neon = sorted({M['neon_m'], M['neon_c']})
    lights.append(C.light_entry((nx, ny + 0.2, (nz0 + nz1) / 2), kind='emissive', color_k=0, watts=40,
                                color=[1.0, 0.15, 0.7], size=[nw, nz1 - nz0]))
    C.set_json_props(o, kz_lights=lights, kz_flicker=neon,
                     kz_anim={'type': 'shader_flicker', 'mode': 'neon_buzz', 'slots': neon, 'amount': 0.06, 'hz': [50.0, 0.4],
                              'stutter_prob': 0.02},
                     kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()})
    C.water_props(o, level_z=ztr + 0.17, path=[[xa, 0, ztr + 0.17], [xb, 0, ztr + 0.17]],
                  kz_spill=dict(pos=[round(xs_end + sp * 0.25, 3), 0, round(ztr + 0.06, 3)], dir=[sp, 0, -1], width=0.2,
                                fx='fx_water_spill'))
    return o
