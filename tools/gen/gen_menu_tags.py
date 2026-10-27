"""Hanging menu tags (menu_tags): the cream menu tags hung under the pass of the neon ramen counter.

TARGETS (measured before coding)
  lookbook/img/09-neon-ramen-counter.jpg: four tags (ラーメン 溶岩卵 黒豚 火山味噌) ~65 px wide x 180 px tall where
  the chef's head is ~60 px (0.23 m) at the same depth -> ~0.25 x 0.70 m tags; cream paper with a darker
  top edge, black brush kanji filling ~0.75 of the width in one vertical column, hung edge to edge under the
  noren rail. refs/gen/sheet-mod-kawagiri.png panel 4 shows the same four tags on the 12 m counter.
  Row: tag w 0.2-0.4, h 0.6-1.0, proxy 0.3 x 0.02 x 0.9 (one tag incl. its hanger).
  Built: body 0.22-0.30 x 0.60-0.78 m, paper 3 mm on hinoki battens (top 22 x 16 mm, bottom 16 x 12 mm),
  wood style 12 mm board with clipped top corners; hanger cords rise 0.10-0.14 m to one hook point.

FEATURES kept at every LOD: tall cream tag, brushed black kanji column (LOD2: blocks), hanger.

PARAMETERS
  w      0.20-0.40 m (tag body width)
  h      0.60-1.00 m (overall incl. hanger)
  text   any string, set vertically (default: seeded from TEXT_SET)
  count  tags in a row on a shared rail (default 1 = one tag, the proxy; >1 exceeds the proxy by design)
  style  'paper' (washi on top + bottom battens, two cords to a hook) | 'wood' (hinoki board, clipped corners,
         one cord through a hole)

SEEDS change shape: style cycles (paper, wood); text (1-4 characters -> body length), width, length,
  hanger height, bottom batten on/off (paper).

MATERIALS (slots by part): paper = washi, board = hinoki natural, battens = hinoki wet_oiled,
  ink = lacquer_black (NOT in the row: proposed), cord = rope.
  Ink is flat (front face only, 0.8 mm proud): real ink has no relief.
ANIMATION: kz_anim vertex sway about the hook; per-vertex weight in the float attribute 'kz_sway'
  (0 at the hook, 1 at the bottom).
BUDGET (row) 100 / 40 / 16 / 6 -- one tag with real glyph geometry needs ~300 / 150 / 22 / 6: see report.
"""
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_common as C

ASSET = 'menu_tags'
FEATURES = ['tall cream tag', 'brushed kanji column', 'hanger']
STYLES = ['paper', 'wood']
TEXT_SET = ['ラーメン', '溶岩卵', '黒豚', '火山味噌', '餃子', '地ビール', '温泉卵']


def ink_text(mb, text, cx, z_top, y, size, gap, mi, lod):
    """flat glyph triangles facing +Y, one character per row from z_top down; glyph x -> world -X"""
    bm = mb.bm
    fs = []
    for i, ch in enumerate(text):
        zc = z_top - (i + 0.5) * size * gap
        if lod >= 2:
            # one dark block per character, sized by its ink box
            hw = size * (0.36 if ch in 'ーンラメ' else 0.42)
            hh = size * (0.12 if ch == 'ー' else 0.4)
            q = [bm.verts.new((cx + sx * hw, y, zc + sz * hh)) for sx, sz in ((1, -1), (-1, -1), (-1, 1), (1, 1))]
            f = bm.faces.new(q)
            if f.normal.y < 0:
                f.normal_flip()
            fs.append(f)
            continue
        groups, (x0, y0, x1, y1) = C.glyph_tri_groups(ch, C.FONT_KANJI, res=C.lod_pick(lod, 2, 1))
        if not groups:
            continue
        s = size / max(x1 - x0, y1 - y0)
        gx, gy = (x0 + x1) / 2, (y0 + y1) / 2
        for pts, tris in groups:
            vs = [bm.verts.new((cx - (px - gx) * s, y, zc + (py - gy) * s)) for px, py in pts]
            for t in tris:
                if len(set(t)) < 3:
                    continue
                try:
                    f = bm.faces.new([vs[j] for j in t])
                except ValueError:
                    continue
                if f.normal.y < 0:
                    f.normal_flip()
                fs.append(f)
        for v in vs:
            pass
    loose = [v for v in bm.verts if not v.link_faces]
    for v in loose:
        bm.verts.remove(v)
    mb._tag(fs, mi)
    return fs


def one_tag(mb, x0, lod, style, W, Hb, hang, text, bottom, mats):
    """one tag; its hook at (x0, 0, Hb + hang). Returns the hook z."""
    paper, board, batten, ink, cord = mats
    zt = Hb                                    # top of the body
    if style == 'paper':
        T = 0.003
        bt_h, bt_d = 0.022, 0.016
        if lod <= 1:
            (C.board if lod == 0 else (lambda mb_, c, s, mi, bevel=0: mb_.box(c, s, mi)))(
                mb, (x0, 0, zt - bt_h / 2), (W + 0.02, bt_d, bt_h), batten, bevel=0.004)
            z_p1 = zt - bt_h * 0.6
            z_p0 = 0.016 if bottom else 0.0
            mb.box((x0, 0, (z_p0 + z_p1) / 2), (W, T, z_p1 - z_p0), paper)
            if bottom:
                (C.board if lod == 0 else (lambda mb_, c, s, mi, bevel=0: mb_.box(c, s, mi)))(
                    mb, (x0, 0, 0.008), (W + 0.012, 0.012, 0.016), batten, bevel=0.003)
        elif lod == 2:
            from kzgeo_lantern_floor import open_box
            open_box(mb, (x0, 0, Hb / 2), (W, T * 2, Hb), paper, skip=('top', 'bottom', 'left', 'right'))
            open_box(mb, (x0, 0, zt - bt_h / 2), (W + 0.02, bt_d, bt_h), batten, skip=('bottom', 'left', 'right'))
        face_y = T / 2 if lod <= 1 else T
        top_ink = zt - bt_h - 0.03
    else:
        T = 0.012
        clip = W * 0.18
        poly = [(-W / 2, 0), (W / 2, 0), (W / 2, zt - clip), (W / 2 - clip, zt), (-W / 2 + clip, zt), (-W / 2, zt - clip)]
        if lod <= 2:
            bm = mb.bm
            A = [bm.verts.new((x0 + x, -T / 2, z)) for x, z in poly]
            B = [bm.verts.new((x0 + x, T / 2, z)) for x, z in poly]
            fs = [bm.faces.new(A[::-1]), bm.faces.new(B)] + (C.bridge_rings(bm, B, A) if lod <= 1 else [])
            bmesh.ops.recalc_face_normals(bm, faces=fs)
            mb._tag(fs, board)
        face_y = T / 2
        top_ink = zt - clip - 0.03
    hook = zt + hang
    if lod <= 1:
        sides = C.lod_pick(lod, 4, 3)
        if style == 'paper':
            for sx in (-1, 1):
                C.tube(mb, [(x0 + sx * W * 0.42, 0, zt - 0.004), (x0, 0, hook)], [0.0025, 0.0025], cord, sides=sides)
        else:
            C.tube(mb, [(x0, 0, zt - 0.03), (x0, 0, hook)], [0.003, 0.003], cord, sides=sides)
            if lod == 0:   # cord loop over the top edge
                C.tube(mb, [(x0, T / 2 + 0.003, zt - 0.03), (x0, T / 2 + 0.003, zt + 0.004), (x0, -T / 2 - 0.003, zt + 0.004),
                            (x0, -T / 2 - 0.003, zt - 0.03)], [0.003] * 4, cord, sides=3)
    elif lod == 2:
        bm = mb.bm
        q = [bm.verts.new(p) for p in ((x0 - W * 0.42, 0, zt), (x0 + W * 0.42, 0, zt), (x0, 0, hook))]
        mb._tag([bm.faces.new(q)], cord)
    if lod <= 2:
        n = max(1, len(text))
        avail = top_ink - 0.05
        size = min(W * 0.74, avail / n / 1.08)
        ink_text(mb, text, x0, top_ink, face_y + 0.0008, size, 1.08, ink, lod)
    else:
        # LOD3: the tag as a two-sided quad + the hanger triangle (6 tris)
        bm = mb.bm
        for yy, flip in ((0.001, False), (-0.001, True)):
            q = [bm.verts.new((x0 + sx, yy, z)) for sx, z in ((-W / 2, 0), (W / 2, 0), (W / 2, zt), (-W / 2, zt))]
            f = bm.faces.new(q[::-1] if flip else q)
            f.material_index = paper if style == 'paper' else board
        q = [bm.verts.new(p) for p in ((x0 - W * 0.42, 0, zt), (x0 + W * 0.42, 0, zt), (x0, 0, hook))]
        f = bm.faces.new(q); f.material_index = cord
        f2 = bm.faces.new([bm.verts.new(p) for p in ((x0 + W * 0.42, -0.0005, zt), (x0 - W * 0.42, -0.0005, zt), (x0, -0.0005, hook))])
        f2.material_index = cord
    return hook


def build(lod, seed, w=None, h=None, text=None, count=1, style=None):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'dims')
    W = w or g.uniform(0.22, 0.30)
    hang = g.uniform(0.10, 0.14)
    gt = C.rng(seed, 'text')
    texts = [text] if text else []
    while len(texts) < count:
        t = TEXT_SET[(gt.randrange(len(TEXT_SET)) + len(texts)) % len(TEXT_SET)]
        texts.append(t)
    n_max = max(len(t) for t in texts)
    Ht = h or min(1.0, max(0.6, 0.28 + 0.12 * n_max + g.uniform(0.0, 0.04) + hang))
    Hb = Ht - hang
    bottom = C.pick(seed, 'bottom', [True, False]) if style == 'paper' else False

    mb = genlib.MeshBuilder()
    mats = (mb.slot('washi'), mb.slot('hinoki', variant='natural'), mb.slot('hinoki', variant='wet_oiled'),
            mb.slot('lacquer_black', roughness_offset=0.35), mb.slot('rope'))
    pitch = W + 0.025
    hooks = []
    for i, t in enumerate(texts):
        x = (count - 1) / 2 * pitch - i * pitch           # first tag on the viewer's left (+X)
        hooks.append(one_tag(mb, x, lod, style, W, Hb, hang, t, bottom, mats))
    if count > 1 and lod <= 2:
        span = (count - 1) * pitch + W
        mb.box((0, 0, Ht + 0.01), (span + 0.04, 0.02, 0.02), mats[2])
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    # sway weight: 0 at the hook, 1 at the bottom
    me = o.data
    att = me.attributes.get('kz_sway') or me.attributes.new('kz_sway', 'FLOAT', 'POINT')
    top = max(v.co.z for v in me.vertices)
    for v in me.vertices:
        att.data[v.index].value = max(0.0, min(1.0, (top - v.co.z) / max(1e-6, top)))
    C.set_json_props(o, kz_anim={'type': 'vertex_sway', 'attribute': 'kz_sway', 'pivot': [0, 0, round(top, 3)],
                                 'amp_deg': 2.5, 'hz': 0.6, 'axis': 'x'},
                     kz_params=dict(style=style, w=round(W, 3), h=round(Ht, 3), texts=texts, count=count, bottom_batten=bottom))
    return o
