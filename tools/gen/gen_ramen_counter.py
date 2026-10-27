"""Neon ramen counter (ramen_counter): dark hinoki counter with stools, kitchen pass, menu tags, black crest noren,
bowls and ladles behind, ラーメン neon above.

TARGETS (refs/gen/sheet-mod-kawagiri.png panel 4 'LACQUERED WOOD COUNTER (12 m)', crop .scratch/op18/m_ramen.png;
lookbook 09 and 07 plan)
  Label 12.0 m x 3.0 m (side), 3.0 m height bar; the row says 15 x 3 x 2.6 and the proxy 12 x 3 x 2.6. The sheet's
  bars disagree (3.0 m bar 121 px/m, 12 m bar 80 px/m), heights are read off the 3.0 m bar:
    counter top 1.0 m, stools 0.72 m with red cushions (8 on 12 m in the drawing), header beam ~2.5-2.7 m;
    noren (dark indigo/black) on the viewer-left 45 % of the header, 4 cream menu tags (ラーメン 溶岩卵 黒豚 火山味噌,
    ~0.35 x 0.85 m) hanging in front of it; magenta ラーメン neon + bowl icon on a dark panel over the right half
    (~5 x 0.6 m); hanging lanterns over the work counter; back shelving with bowl stacks, stock pots and
    ladles; side view: stools | counter + pass | work counter | back shelf, 3.0 m deep, slatted ceiling.
  Built 12.0 m (sheet label = proxy) x 3.0 m x 2.72 m (proxy h 2.6 + 5 %: the header must clear 1.9 m noren hems).
  Row says 15 m / 14 stools: w is a parameter (12-15); stool pitch follows the seed (see SEEDS).

FEATURES kept at every LOD: long dark counter, stools, kitchen pass, menu tags, black crest noren, bowls/ladles
  behind, ラーメン neon.  LOD1: no bevels, glyphs res 1, fewer lathe segments, no condiments.  LOD2: neon as
  ribbons, text blocks, bowl stacks as single lathes, stools without footrests.  LOD3: boxes, glow quad.

PARAMETERS  w 12-15 (12) | stools 8-16 (by seed) | pass_h 0.15-0.25 above the counter | shelf_rows 2-3 |
  menu tags 3-5 | neon_text (ラーメン) | chochin 0-2
SEEDS change: stool count / pitch (seed 1: 8 like the sheet, seed 2: 11 = row pitch 1.07 m, seed 3: 13), shelf
  rows (3 / 2 / 3), menu tag count (4 / 5 / 3), noren panel count (4 / 5 / 3) and crest panel, pendant
  lantern count, chochin at the ends (1 / 2 / 0), pot count.
MATERIALS (slots by part): counter + stools hinoki stained (near-black); frame hinoki dark_timber; counter front
  panels lacquer_dark; kick plinth lacquer_black; tags hinoki natural with lacquer_black ink; noren noren
  black, crest linen; neon neon_tube on a lacquer_black backing; cushions noren vermilion; pots/ladles/foot
  rail iron (stool footrest rings LOD0 only); bowls ceramic tenmoku / white; lanterns lantern_andon, chochin lantern_paper red.
ANIMATION kz_anim shader_flicker (neon buzz) on the neon slot; noren '_sway' vertex layer; kz_steam points over
  the pots (fx_steam). LIGHTS kz_lights: neon emissive, pendant andon, chochin, counter area light.
"""
import math

import genlib
import kzgeo_common as C
import kzgeo_kawagiri_pod as KK

ASSET = 'ramen_counter'
FEATURES = ['long dark hinoki counter with stools', 'kitchen pass', 'menu tags', 'black crest noren',
            'bowls and ladles behind', 'ラーメン neon above']
TAGS = ['ラーメン', '溶岩卵', '黒豚', '火山味噌', '餃子']


def params(seed, w=None, stools=None, pass_h=None, shelf_rows=None, tags=None, neon_text=None, chochin=None):
    k = (seed - 1) % 3
    g = C.rng(seed, 'layout')
    W = w or 12.0
    P = dict(w=W, stools=stools or [8, 11, 13][k] + (0 if seed <= 3 else g.randint(-1, 1)),
             pass_h=pass_h or [0.2, 0.16, 0.24][k], shelf_rows=shelf_rows or [3, 2, 3][k], tags=tags or [4, 5, 3][k],
             neon_text=neon_text or 'ラーメン', chochin=[1, 2, 0][k] if chochin is None else chochin,
             noren=[4, 5, 3][k], pendants=[4, 3, 5][k], pots=[3, 4, 2][k])
    return P


def build(lod, seed, w=None, stools=None, pass_h=None, shelf_rows=None, tags=None, neon_text=None, chochin=None, **_):
    P = params(seed, w, stools, pass_h, shelf_rows, tags, neon_text, chochin)
    W = P['w']
    hw = W / 2
    mb = genlib.MeshBuilder()
    M = dict(counter=mb.slot('hinoki', variant='stained'), frame=mb.slot('hinoki', variant='dark_timber'),
             panel=mb.slot('lacquer_dark', wear=0.2), kick=mb.slot('lacquer_black'),
             tag=mb.slot('hinoki', variant='natural'), ink=mb.slot('lacquer_black'),
             noren=mb.slot('noren', variant='black', normal_strength=1.6), crest=mb.slot('linen'),
             neon=mb.slot('neon_tube'), back=mb.slot('lacquer_black'), cushion=mb.slot('noren', variant='vermilion'),
             iron=mb.slot('iron', wear=0.25), tenmoku=mb.slot('ceramic', variant='tenmoku'),
             white=mb.slot('ceramic', variant='white'), andon=mb.slot('lantern_andon', emissive_level=0.9),
             paper=mb.slot('lantern_paper', tint=(1.0, 0.05, 0.02), emissive_level=0.5))
    lights = []
    steam = []
    H = 2.72
    if lod >= 3:
        return _lod3(mb, M, P, W, H, seed)
    y_hf, y_hb = 0.62, -1.38            # header beam lines (front / back)
    z_h0, z_h1 = 2.42, 2.62             # header beam
    # ---------------- frame: posts, headers, ceiling joists
    xs_back = [hw - 0.1 - (W - 0.2) * i / 4 for i in range(5)]
    for x in (hw - 0.1, -hw + 0.1):
        KK.post(mb, lod, x, y_hf, 0, z_h1, 0.16, M['frame'])
    for x in xs_back:
        KK.post(mb, lod, x, y_hb, 0, z_h1, 0.16, M['frame'])
    KK.beam_x(mb, lod, -hw, hw, y_hf, z_h0, z_h1, 0.16, M['frame'])
    KK.beam_x(mb, lod, -hw, hw, y_hb, z_h0, z_h1, 0.16, M['frame'])
    nj = C.lod_pick(lod, 13, 13, 7, 3)
    for i in range(nj):
        x = -hw + 0.1 + (W - 0.2) * i / (nj - 1)
        if lod == 0:
            KK.beam_y(mb, lod, y_hb - 0.1, y_hf + 0.1, x, z_h1, H, 0.09, M['frame'])
        else:
            mb.box((x, (y_hb + y_hf) / 2, (z_h1 + H) / 2), (0.09, y_hf - y_hb + 0.2, H - z_h1), M['frame'])
    # ---------------- counter: kick plinth, front panel + battens, top, pass, foot rail
    y_cf = 0.55                          # counter front face
    z_top = 1.0
    mb.box((0, y_cf - 0.25, 0.06), (W - 0.3, 0.46, 0.12), M['kick'])
    KK.timber(mb, lod, (0, y_cf - 0.22, (0.12 + z_top - 0.05) / 2), (W - 0.34, 0.06, z_top - 0.17), M['panel'], 0.006)
    if lod <= 1:
        nb = int((W - 0.4) / 0.6) + 1
        for i in range(nb):
            x = -hw + 0.2 + (W - 0.4) * i / (nb - 1)
            KK.timber(mb, lod, (x, y_cf - 0.175, (0.12 + z_top - 0.05) / 2), (0.07, 0.04, z_top - 0.17), M['counter'], 0.008)
    KK.timber(mb, lod, (0, 0.47, z_top - 0.03), (W - 0.2, 0.62, 0.06), M['counter'], 0.012)         # top, 0.62 deep
    z_pass = z_top + P['pass_h']
    KK.timber(mb, lod, (0, 0.12, z_pass - 0.025), (W - 0.3, 0.3, 0.05), M['counter'], 0.008)        # pass shelf
    if lod <= 2:
        nps = int(W / 1.5) + 1
        for i in range(nps):
            x = -hw + 0.3 + (W - 0.6) * i / (nps - 1)
            mb.box((x, 0.12, (z_top + z_pass - 0.05) / 2), (0.08, 0.26, z_pass - z_top - 0.05 + 0.002), M['counter'])
    if lod <= 1:
        rail = [(-hw + 0.3, y_cf + 0.02, 0.2), (hw - 0.3, y_cf + 0.02, 0.2)]
        C.tube(mb, rail, [0.022, 0.022], M['iron'], sides=C.lod_pick(lod, 8, 6), cap0=True, cap1=True)
        for i in range(5):
            x = -hw + 0.4 + (W - 0.8) * i / 4
            mb.box((x, y_cf - 0.07, 0.2), (0.03, 0.16, 0.03), M['iron'])
    # ---------------- stools + place settings
    n = P['stools']
    pitch = (W - 1.2) / n
    rs = C.rng(seed, 'stools')
    stool_m = dict(wood=M['counter'], cushion=M['cushion'])
    for i in range(n):
        x = -hw + 0.6 + (i + 0.5) * pitch
        KK.bar_stool(mb, lod, (x, 1.08, 0), stool_m, h=0.72, r=0.17, yaw=rs.uniform(-0.2, 0.2))
        if lod == 0:                     # condiment cup + chopstick box per seat
            C.lathe(mb, [(0.03, 0), (0.035, 0.08), (0, 0.08)], 8, M['white'], base=(x + 0.18, 0.4, z_top))
            mb.box((x - 0.15, 0.38, z_top + 0.04), (0.16, 0.06, 0.08), M['frame'])
    # bowls on the pass
    rb = C.rng(seed, 'pass')
    npb = max(3, n // 2)
    for i in range(npb):
        x = -hw + 0.8 + (W - 1.6) * (i + rb.uniform(0.2, 0.8)) / npb
        if lod <= 1:
            KK.bowl(mb, lod, (x, 0.12, z_pass), 0.11, 0.09, M['tenmoku'] if i % 2 else M['white'])
    # ---------------- work counter (stock pots, bowl stacks) + back shelving
    y_w = -0.62
    KK.timber(mb, lod, (0, y_w, 0.44), (W - 0.4, 0.62, 0.88), M['panel'], 0.008)
    KK.timber(mb, lod, (0, y_w, 0.9), (W - 0.36, 0.66, 0.04), M['counter'], 0.006)
    npot = P['pots']
    rp = C.rng(seed, 'pots')
    for i in range(npot):
        x = hw - 1.2 - (W - 2.4) * (i + 0.5) / npot * 0.55 - rp.uniform(0, 0.3)
        R = rp.uniform(0.2, 0.26)
        KK.pot(mb, lod, (x, y_w, 0.92), R, rp.uniform(0.3, 0.42), M['iron'])
        steam.append([round(x, 3), y_w, 1.35])
    for i in range(6):
        x = -hw + 1.0 + (W * 0.42) * i / 5
        KK.bowl_stack(mb, lod, (x, y_w + 0.05, 0.92), 0.1, 0.08, 5 - i % 2, M['white'] if i % 2 else M['tenmoku'], steps=3,
                      simple_from=1)
    # back shelf: uprights + boards + bowl stacks / jars
    y_s = -1.3
    nbay = int(W / 1.5)
    for i in range(nbay + 1):
        x = -hw + 0.25 + (W - 0.5) * i / nbay
        if lod >= 2 and i % 2 and i != nbay:
            continue
        mb.box((x, y_s, 1.2), (0.06, 0.3, 1.2), M['frame'])
    rows = P['shelf_rows']
    rsh = C.rng(seed, 'shelf')
    for j in range(rows):
        z = 1.05 + j * (1.1 / max(1, rows - 1) if rows > 1 else 0) * 0.9
        KK.timber(mb, lod, (0, y_s, z), (W - 0.4, 0.32, 0.035), M['counter'], 0.004)
        if lod >= 2:                     # LOD2: one row of ware per shelf
            mb.box((0, y_s, z + 0.1), (W - 0.8, 0.2, 0.17), M['white'] if j % 2 else M['tenmoku'])
            continue
        for i in range(nbay):
            x = -hw + 0.25 + (W - 0.5) * (i + 0.3 + 0.4 * (j % 2)) / nbay
            nst = 3 + rsh.randint(0, 2)
            if j == rows - 1 and i % 2:
                C.lathe(mb, [(0.06, 0), (0.09, 0.08), (0.08, 0.2), (0.04, 0.24), (0, 0.24)], C.lod_pick(lod, 10, 6),
                        M['tenmoku'], base=(x, y_s, z + 0.018))                      # jar
            else:
                KK.bowl_stack(mb, lod, (x, y_s, z + 0.018), 0.09, 0.07, nst, M['white'] if (i + j) % 2 else M['tenmoku'],
                              segs=C.lod_pick(lod, 8, 6), steps=2, simple_from=1)
    # ladle rail with hanging ladles
    if lod <= 1:
        C.tube(mb, [(-hw + 0.5, y_s + 0.22, 1.85), (hw - 0.5, y_s + 0.22, 1.85)], [0.012, 0.012], M['iron'], sides=6, cap0=True, cap1=True)
        for i in range(6):
            x = hw - 0.9 - (W * 0.45) * i / 5
            KK.ladle(mb, lod, (x, y_s + 0.22, 1.84), 0.36 + 0.06 * (i % 3), M['iron'])
    # ---------------- pendant lanterns over the work counter
    npd = P['pendants']
    for i in range(npd):
        x = hw - 1.0 - (W - 2.0) * i / max(1, npd - 1)
        zb = 1.85
        if lod <= 2:
            C.stick(mb, (x, y_w, zb + 0.32), (x, y_w, z_h1), 0.006, 0.006, M['iron'], segs=4)
        cen = KK.andon(mb, dict(iron=M['iron'], paper=M['andon']), lod, (x, y_w, zb), size=0.2, height=0.3)
        lights.append(C.light_entry(cen, color_k=2200, watts=15))
    # ---------------- noren (viewer-left = +X), crest on one panel
    nn = P['noren']
    x_n0, x_n1 = 0.15, hw - 0.25
    pw = (x_n1 - x_n0) / nn
    rn = C.rng(seed, 'noren')
    hn = 0.55
    for i in range(nn):
        xc = x_n0 + (i + 0.5) * pw
        if lod <= 1:
            fs = C.cloth_panel(mb, pw - 0.03, hn, M['noren'], rn, cols=C.lod_pick(lod, 6, 3), rows=C.lod_pick(lod, 4, 2),
                               pleat0=0.008, pleat1=0.02, belly=0.015, band_h=0.06, mi_band=M['noren'], x0=xc)
            # cloth_panel spans z 0..hn: lift to the header
            for v in {v for f in fs for v in f.verts}:
                v.co.z += z_h0 - hn
                v.co.y += y_hf + 0.1
        else:
            KK.quad_y(mb, xc, y_hf + 0.1, z_h0 - hn / 2, pw - 0.03, hn, M['noren'])
    # crest (mountain + KAZAN-YU) on the middle panel, printed slightly proud
    ic = nn // 2
    xc = x_n0 + (ic + 0.5) * pw
    if lod <= 1:
        bm = mb.bm
        s = 0.22
        mpts = [(-0.75, -0.3), (-0.2, 0.28), (-0.08, 0.36), (0.0, 0.3), (0.08, 0.36), (0.2, 0.28), (0.75, -0.3), (0.5, -0.3),
                (0.12, 0.12), (0.0, 0.16), (-0.12, 0.12), (-0.5, -0.3)]
        vs = [bm.verts.new((xc - px * s * 1.6, y_hf + 0.1 + 0.03, z_h0 - 0.2 + pz * s)) for px, pz in mpts]
        f = bm.faces.new(vs)
        f.normal_update()
        if f.normal.y < 0:
            f.normal_flip()
        f.material_index = M['crest']
    # ---------------- menu tags in front of the noren
    ntg = P['tags']
    for i in range(ntg):
        xt = x_n1 - 0.4 - (x_n1 - x_n0 - 0.8) * (i + 0.5) / ntg      # first tag on the viewer's left (+X)
        tw_, th_ = 0.34, 0.86
        zt = z_h0 - 0.06
        yt = y_hf + 0.2
        KK.timber(mb, lod, (xt, yt, zt - th_ / 2), (tw_, 0.025, th_), M['tag'], 0.005)
        if lod <= 2:
            mb.box((xt, yt, zt + 0.03), (tw_ + 0.04, 0.03, 0.03), M['frame'])          # top bar
        txt = TAGS[i % len(TAGS)]
        nch = len(txt)
        size = min(tw_ * 0.62, (th_ - 0.14) / nch / 1.08)
        if lod == 1:
            KK.flat_text(mb, txt, xt, zt - th_ / 2, yt + 0.0135, size, M['ink'], vertical=True, gap=1.08)
        elif lod == 0:
            C.text_solid(mb, txt, xt, zt - th_ / 2, yt + 0.0125, size, M['ink'], depth=0.004, font=C.FONT_KANJI,
                         vertical=True, gap=1.08, res=1)
        elif lod == 2:
            mb.box((xt, yt + 0.015, zt - th_ / 2), (tw_ * 0.35, 0.006, th_ * 0.7), M['ink'])
    # ---------------- neon ラーメン + bowl icon on a dark panel (viewer-right = -X)
    nx0, nx1 = -hw + 0.35, -0.15
    nz0, nz1 = 1.84, 2.4
    ncx = (nx0 + nx1) / 2
    ny = y_hf + 0.08
    KK.timber(mb, lod, (ncx, ny + 0.03, (nz0 + nz1) / 2), (nx1 - nx0, 0.06, nz1 - nz0), M['back'], 0.008)
    yt = ny + 0.06 + 0.018
    tr = 0.012
    txt = P['neon_text']
    iw = nx1 - nx0 - 0.3
    icon = 0.55
    cell = (iw - icon) / len(txt)
    size = min((nz1 - nz0) * 0.72, cell * 0.98)
    zc = (nz0 + nz1) / 2
    if lod <= 2:
        for i, ch in enumerate(txt):
            KK.neon_glyph(mb, lod, ch, nx1 - 0.15 - (i + 0.5) * cell, zc, size, yt, tr, M['neon'])
        # bowl icon: bowl arc, rim, foot, chopsticks
        bx = nx0 + 0.15 + icon / 2
        R = icon * 0.42
        nseg = C.lod_pick(lod, 10, 6, 4)
        arc = [(bx + R * math.cos(math.pi + math.pi * k / nseg), zc - 0.02 + R * 0.75 * math.sin(math.pi + math.pi * k / nseg)) for k in range(nseg + 1)]
        KK.neon_line(mb, lod, arc, yt, tr, M['neon'])
        KK.neon_line(mb, lod, [(bx - R * 1.1, zc - 0.02), (bx + R * 1.1, zc - 0.02)], yt, tr, M['neon'])
        KK.neon_line(mb, lod, [(bx - R * 0.3, zc - 0.02 - R * 0.85), (bx + R * 0.3, zc - 0.02 - R * 0.85)], yt, tr, M['neon'])
        if lod <= 1:
            KK.neon_line(mb, lod, [(bx - R * 0.6, zc + 0.04), (bx + R * 0.9, zc + R * 0.7)], yt, tr, M['neon'])
            KK.neon_line(mb, lod, [(bx - R * 0.4, zc + 0.04), (bx + R * 1.1, zc + R * 0.55)], yt, tr, M['neon'])
    else:
        KK.quad_y(mb, ncx, ny + 0.065, zc, nx1 - nx0 - 0.2, (nz1 - nz0) * 0.6, M['neon'])
    # ---------------- chochin at the ends + andon on the viewer-left post
    cho_m = dict(paper=M['paper'], cap=M['ink'], ink=M['ink'], cord=M['iron'])
    for i in range(P['chochin']):
        x = (hw - 0.35) * (1 if i == 0 else -1)
        if lod <= 2:
            mb.box((x, y_hf + 0.15, z_h0 - 0.05), (0.04, 0.3, 0.04), M['iron'])
        cen = KK.chochin(mb, cho_m, lod, (x, y_hf + 0.3, z_h0 - 0.05), r=0.22, h=0.6, cord=0.08,
                         segs={0: 12, 1: 8, 2: 6, 3: 4})
        lights.append(C.light_entry(cen, color_k=1900, watts=25, color=[1.0, 0.25, 0.12]))
    if lod <= 2:
        cen = KK.andon(mb, dict(iron=M['iron'], paper=M['andon']), lod, (hw - 0.1, y_hf + 0.3, 1.55), size=0.22, height=0.38,
                       arm=(0, -0.22))
        lights.append(C.light_entry(cen, color_k=2200, watts=15))
    lights.append(C.light_entry((ncx, ny + 0.2, zc), kind='emissive', color_k=0, watts=40, color=[1.0, 0.15, 0.7],
                                size=[nx1 - nx0, nz1 - nz0]))
    lights.append(C.light_entry((0, 0.2, 2.3), kind='area', color_k=2700, watts=300, size=[W - 1, 1.5]))
    off = C.centre_base(mb, centre_x=True, centre_y=True)
    KK.shift_points(off, lights, steam)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_lights=lights, kz_flicker=[M['neon']],
                     kz_anim={'type': 'shader_flicker', 'mode': 'neon_buzz', 'slots': [M['neon']], 'amount': 0.06,
                              'hz': [50.0, 0.4], 'stutter_prob': 0.02},
                     kz_steam=dict(fx='fx_steam', points=steam), kz_counter_z=z_top,
                     kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()})
    return o


def _lod3(mb, M, P, W, H, seed):
    """LOD3 (~200 tris): the same layout as boxes: counter, stool row with the red cushion strip, header, posts,
    shelf, noren + tags + neon as quads, chochin (lean lathe)."""
    hw = W / 2
    y_hf, y_hb, z_h0, z_h1 = 0.62, -1.38, 2.42, 2.62
    mb.box((0, 0.33, 0.5), (W - 0.3, 0.46, 1.0), M['panel'])                       # counter body
    mb.box((0, 0.47, 0.97), (W - 0.2, 0.62, 0.06), M['counter'])                   # top
    mb.box((0, 1.08, 0.33), (W - 1.4, 0.2, 0.62), M['counter'])                    # stool row
    mb.box((0, 1.08, 0.67), (W - 1.3, 0.3, 0.05), M['cushion'])
    mb.box((0, -0.62, 0.45), (W - 0.4, 0.62, 0.9), M['panel'])                     # work counter
    mb.box((0, -1.3, 1.5), (W - 0.4, 0.3, 1.0), M['tenmoku'])                      # shelf ware
    mb.box((0, y_hf, (z_h0 + H) / 2), (W, 0.16, H - z_h0), M['frame'])             # headers
    mb.box((0, y_hb, (z_h0 + H) / 2), (W, 0.16, H - z_h0), M['frame'])
    for x in (hw - 0.1, -hw + 0.1):
        mb.box((x, y_hf, z_h0 / 2), (0.16, 0.16, z_h0), M['frame'])
        mb.box((x, y_hb, z_h0 / 2), (0.16, 0.16, z_h0), M['frame'])
    KK.quad_y(mb, (0.15 + hw - 0.25) / 2, y_hf + 0.1, z_h0 - 0.275, hw - 0.4, 0.55, M['noren'])
    for i in range(P['tags']):
        xt = 0.15 + 0.4 + (hw - 0.25 - 0.15 - 0.8) * (i + 0.5) / P['tags']
        KK.quad_y(mb, xt, y_hf + 0.2, z_h0 - 0.49, 0.34, 0.86, M['tag'])
    nx0, nx1 = -hw + 0.35, -0.15
    mb.box(((nx0 + nx1) / 2, y_hf + 0.11, 2.12), (nx1 - nx0, 0.06, 0.56), M['back'])
    KK.quad_y(mb, (nx0 + nx1) / 2, y_hf + 0.145, 2.12, nx1 - nx0 - 0.2, 0.34, M['neon'])
    cho_m = dict(paper=M['paper'], cap=M['ink'], ink=M['ink'], cord=M['iron'])
    lights = []
    for i in range(P['chochin']):
        x = (hw - 0.35) * (1 if i == 0 else -1)
        lights.append(C.light_entry(KK.chochin(mb, cho_m, 3, (x, y_hf + 0.3, z_h0 - 0.05), r=0.22, h=0.6, cord=0.08,
                                               lod3_caps=False), color_k=1900, watts=25))
    off = C.centre_base(mb, centre_x=True, centre_y=True)
    KK.shift_points(off, lights)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_lights=lights, kz_flicker=[M['neon']],
                     kz_params={k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items()})
    return o
