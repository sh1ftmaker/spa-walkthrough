"""Hand-bent neon kanji sign (neon_sign): Kawagiri / ramen-counter neon.

TARGETS (measured before coding)
  lookbook/img/09-neon-ramen-counter.jpg: the 火山 sign is a VERTICAL dark panel ~75 x 215 px next to a red
  chochin of ~70 px (0.45 m) at the same depth -> ~0.5-0.65 m x 1.4-1.7 m; magenta kanji + a magenta
  border tube ~0.04 m in from the edge, a cyan mountain crest under the text (~0.7 of the inner width).
  lookbook/img/06-kawagiri-restaurant.jpg: 食事処 vertical magenta (h/w ~3), 火山湯 vertical cyan with a crest
  circle above the text (h/w ~4), 川の宴 far right. refs/gen/sheet-mod-kawagiri.png panel 2 (sign gate,
  7.5 m bar): 川霧 magenta panel ~0.9 x 1.8 m over a cyan crest panel ~0.9 x 0.8 m (one 0.9 x 2.6 m sign),
  panel 4: ラーメン horizontal magenta, ~4 m (the row's w 4.2) -- here at the proxy size 1.5 x 0.6.
  Tube: 6-10 mm radius (row); strokes ~2 % of the character height, standing ~18 mm off the backing.
  PROXY 1.5 x 0.1 x 0.8 is a horizontal sign; every lookbook neon is vertical, so the vertical styles exceed
  the proxy height (reported, proxy change proposed). Only 'ramen' fits the proxy.

FEATURES kept at every LOD: glowing tube strokes forming the text, border tube, crest, dark backing.
  LOD2 turns tubes into flat glowing ribbons (same strokes, coarser), LOD3 is the backing + a glow quad.

PARAMETERS
  text     any CJK / kana string (strokes come from the font skeleton, kzgeo_neon_sign.glyph_strokes)
  colour   'magenta' | 'cyan' | 'both' (text magenta, border + crest cyan)
  tube_r   0.006-0.010 m
  backing  True | False (False: tubes on two dark raceway bars, no panel)
  w, h     panel size (m); vertical when h > w
  style    'kazan' (火山 + mountain crest, 09) | 'shokuji' (食事処, 06) | 'kazanyu' (火山湯 cyan + circle crest, 06)
           | 'kawagiri' (川霧 panel over a cyan tomoe crest panel, sheet panel 2) | 'ramen' (ラーメン horizontal)

SEEDS change shape: the style cycles (text, layout, crest, two-panel or one), plus tube radius, panel
  w/h x0.92-1.08, border corner radius, crest size.

MATERIALS (slots by part): tube = neon_tube (magenta) / neon_tube variant cyan, backing = lacquer_dark.
ANIMATION: kz_anim neon buzz/flicker on the tube slots. LIGHT: kz_lights emissive entry at the panel front
  with the dominant colour.
BUDGET (row) 600 / 240 / 80 / 20 -- too small for one tube per stroke on multi-stroke kanji: see report.
"""
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_common as C
import kzgeo_neon_sign as K

ASSET = 'neon_sign'
FEATURES = ['glowing tube strokes forming kanji', 'border tube', 'crest', 'dark backing']
STYLES = ['kazan', 'shokuji', 'kazanyu', 'kawagiri', 'ramen']
STYLE_DEF = dict(
    kazan=dict(text='火山', w=0.62, h=1.6, colour='both', crest='mountain', crest_pos='bottom'),
    shokuji=dict(text='食事処', w=0.5, h=1.55, colour='magenta', crest=None, crest_pos=None),
    kazanyu=dict(text='火山湯', w=0.55, h=2.1, colour='cyan', crest='circle', crest_pos='top'),
    kawagiri=dict(text='川霧', w=0.9, h=2.6, colour='both', crest='tomoe', crest_pos='panel'),
    ramen=dict(text='ラーメン', w=1.5, h=0.6, colour='magenta', crest=None, crest_pos=None),
)


def ribbon(mb, pts, half, y, mi, closed=False):
    """flat strip (facing +Y) along a polyline in (x, z) -- LOD2 neon"""
    bm = mb.bm
    n = len(pts)
    L_, R_ = [], []
    for i in range(n):
        a = pts[max(i - 1, 0)] if not closed else pts[(i - 1) % n]
        b = pts[min(i + 1, n - 1)] if not closed else pts[(i + 1) % n]
        tx, tz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, tz) or 1.0
        nx, nz = -tz / ln, tx / ln
        L_.append(bm.verts.new((pts[i][0] + nx * half, y, pts[i][1] + nz * half)))
        R_.append(bm.verts.new((pts[i][0] - nx * half, y, pts[i][1] - nz * half)))
    fs = []
    for i in range(n - 1 if not closed else n):
        j = (i + 1) % n
        f = bm.faces.new((L_[i], R_[i], R_[j], L_[j]))
        if f.normal.y < 0:
            f.normal_flip()
        fs.append(f)
    mb._tag(fs, mi)
    return fs


def build(lod, seed, text=None, colour=None, tube_r=None, backing=True, w=None, h=None, style=None):
    style = style or C.cycle(seed, STYLES)
    S = dict(STYLE_DEF[style])
    g = C.rng(seed, 'dims')
    W = w or S['w'] * g.uniform(0.92, 1.08)
    H = h or S['h'] * g.uniform(0.92, 1.08)
    text = text or S['text']
    colour = colour or S['colour']
    r = tube_r or C.rng(seed, 'tube').uniform(0.0075, 0.010)
    gb = C.rng(seed, 'border')
    corner = gb.uniform(0.02, 0.06)
    crest_k = gb.uniform(0.62, 0.78)
    vertical = H > W

    mb = genlib.MeshBuilder()
    slots = {}

    def tubemat(c):
        if c not in slots:
            slots[c] = mb.slot('neon_tube') if c == 'magenta' else mb.slot('neon_tube', variant='cyan')
        return slots[c]
    back = mb.slot('lacquer_dark')
    c_text = 'cyan' if colour == 'cyan' else 'magenta'
    c_deco = 'cyan' if colour in ('cyan', 'both') else 'magenta'

    D = 0.035                                  # backing depth
    y_t = D + 0.018                            # tube centre plane
    # ---- backing
    if backing:
        if lod == 0:
            C.board(mb, (0, D / 2, H / 2), (W, D, H), back, bevel=0.008)
        elif lod <= 2:
            mb.box((0, D / 2, H / 2), (W, D, H), back)
        else:
            from kzgeo_lantern_floor import open_box
            open_box(mb, (0, D / 2, H / 2), (W, D, H), back, skip=('back', 'bottom'))
    else:
        for zz in (0.25, 0.75) if not vertical else (0.5,):
            if vertical:
                mb.box((0, D / 2, H / 2), (0.05, D, H * 0.92), back)
            else:
                mb.box((0, D / 2, H * zz), (W * 0.92, D, 0.05), back)

    sides = C.lod_pick(lod, 6, 4)
    eps_px = C.lod_pick(lod, 1.0, 1.6, 2.6)

    def put_line(pts, mi, closed=False):
        """pts in (x, z) world"""
        if closed:
            pts = list(pts) + [pts[0]]
        if lod <= 1:
            C.tube(mb, [(x, y_t, z) for x, z in pts], [r] * len(pts), mi, sides=sides, cap0=not closed, cap1=not closed)
        else:
            ribbon(mb, pts, r * 1.3, y_t + r, mi)

    def glyph(ch, cx, cz, size, mi):
        strokes, _ = K.glyph_strokes(ch, eps=eps_px)
        for s in strokes:
            if len(s) < 2:
                continue
            put_line([(cx - x * size, cz + y * size) for x, y in s], mi)       # glyph x -> world -X (reads from +Y)

    def border(cx, cz, bw, bh, mi):
        n_c = C.lod_pick(lod, 3, 1, 1)
        rr = min(corner, bw * 0.2, bh * 0.2)
        pts = [(cx + x, cz + z) for x, z in K.rounded_rect(bw, bh, rr, n_c)]
        put_line(pts, mi, closed=True)

    def crest(kind, cx, cz, size, mi):
        segs = C.lod_pick(lod, 14, 8, 8)
        R = size / 2
        if kind in ('circle', 'tomoe'):
            put_line([(cx + R * math.cos(2 * math.pi * k / segs), cz + R * math.sin(2 * math.pi * k / segs)) for k in range(segs)], mi, closed=True)
        if kind == 'tomoe':
            if lod <= 1:
                for j in range(3):          # three comma arcs swirling from the centre
                    a0 = 2 * math.pi * j / 3
                    arc = [(cx + R * 0.62 * t * math.cos(a0 + 2.4 * t), cz + R * 0.62 * t * math.sin(a0 + 2.4 * t))
                           for t in [0.15 + 0.85 * i / C.lod_pick(lod, 5, 3) for i in range(C.lod_pick(lod, 5, 3) + 1)]]
                    put_line(arc, mi)
        if kind in ('mountain', 'circle'):
            k = 0.62 if kind == 'circle' else 1.0
            m = [(-0.75, -0.32), (-0.18, 0.3), (0.0, 0.38), (0.18, 0.3), (0.75, -0.32)]
            put_line([(cx - x * R * k, cz + y * R * k) for x, y in m], mi)
            if kind == 'mountain':
                put_line([(cx - 0.9 * R, cz - 0.46 * R), (cx + 0.9 * R, cz - 0.46 * R)], mi)
                if lod == 0:            # snow-line zigzag under the peak
                    put_line([(cx - x * R, cz + y * R) for x, y in [(-0.34, 0.08), (-0.14, -0.02), (0.0, 0.1), (0.14, -0.02), (0.34, 0.08)]], mi)

    m = 0.045                                   # border inset from the panel edge
    if lod >= 3:
        # backing + one glow quad over the lettering
        bm = mb.bm
        ins = m + 0.03
        q = [bm.verts.new((x, y_t, z)) for x, z in ((W / 2 - ins, ins), (-W / 2 + ins, ins), (-W / 2 + ins, H - ins), (W / 2 - ins, H - ins))]
        f = bm.faces.new(q)
        if f.normal.y < 0:
            f.normal_flip()
        f.material_index = tubemat(c_text)
    else:
        n = len(text)
        if S['crest_pos'] == 'panel':
            split = H * 0.31
            border(0, (split + H - m) / 2, W - 2 * m, H - m - split - 0.02, tubemat(c_text))
            border(0, (m + split) / 2, W - 2 * m, split - m - 0.02, tubemat(c_deco))
            inner_h = H - m - split - 0.02 - 0.16
            size = min((W - 2 * m) * 0.7, inner_h / n / 1.08)
            top = H - m - 0.08
            for i, ch in enumerate(text):
                glyph(ch, 0, top - (i + 0.5) * inner_h / n, size, tubemat(c_text))
            crest(S['crest'], 0, (m + split) / 2, min(W - 2 * m, split - m) * crest_k, tubemat(c_deco))
        elif vertical:
            border(0, H / 2, W - 2 * m, H - 2 * m, tubemat(c_deco if colour == 'both' and not S['crest'] else c_text))
            iw = W - 2 * m - 0.06
            ch_ = iw * crest_k if S['crest'] else 0.0
            avail = H - 2 * m - 0.1 - (ch_ + 0.06 if ch_ else 0)
            cell = avail / n
            size = min(iw * 0.86, cell / 1.06)
            z_top = H - m - 0.05 - (ch_ + 0.06 if S['crest_pos'] == 'top' else 0)
            for i, ch in enumerate(text):
                glyph(ch, 0, z_top - (i + 0.5) * cell, size, tubemat(c_text))
            if S['crest']:
                cz = (m + 0.05 + ch_ / 2) if S['crest_pos'] == 'bottom' else (H - m - 0.05 - ch_ / 2)
                crest(S['crest'], 0, cz, ch_, tubemat(c_deco))
        else:
            border(0, H / 2, W - 2 * m, H - 2 * m, tubemat(c_deco if colour == 'both' else c_text))
            iw = W - 2 * m - 0.1
            cell = iw / n
            size = min((H - 2 * m) * 0.74, cell * 0.95)
            for i, ch in enumerate(text):
                glyph(ch, iw / 2 - (i + 0.5) * cell, H / 2, size, tubemat(c_text))       # first char on the viewer's left (+X)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    tube_slots = sorted(slots.values())
    col = {'magenta': [1.0, 0.15, 0.7], 'cyan': [0.1, 0.8, 1.0]}[c_text]
    C.set_json_props(o, kz_lights=[C.light_entry((0, y_t + 0.05, H / 2), kind='emissive', color_k=0, watts=20, color=col,
                                                 size=[round(W, 3), round(H, 3)])],
                     kz_flicker=tube_slots,
                     kz_anim={'type': 'shader_flicker', 'mode': 'neon_buzz', 'slots': tube_slots, 'amount': 0.06,
                              'hz': [50.0, 0.4], 'stutter_prob': 0.02},
                     kz_params=dict(style=style, text=text, colour=colour, tube_r=round(r, 4), backing=backing,
                                    w=round(W, 3), h=round(H, 3)))
    return o
