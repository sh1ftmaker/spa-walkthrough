"""Geometry for gen_board_small_hanging: raised numerals without a back face.

The numeral sits flat on the plate, so its back face can never be seen; kzgeo_common.tracked_text builds
closed solids (front + back + walls). open_text() builds the front faces and the side walls only, which
saves ~40 % of the glyph triangles. Layout and orientation match C.tracked_text (reads left-to-right
from +Y, glyph x -> world -X)."""
import bmesh

import kzgeo_common as C


def _extrude_open(bm, pts, tris, y, depth):
    vb, vf = {}, {}

    def back(i):
        if i not in vb:
            vb[i] = bm.verts.new((pts[i][0], y, pts[i][1]))
        return vb[i]

    def front(i):
        if i not in vf:
            vf[i] = bm.verts.new((pts[i][0], y + depth, pts[i][1]))
        return vf[i]
    edge_count = {}
    faces = []
    for t in tris:
        if len(set(t)) < 3:
            continue
        for i in range(3):
            e = tuple(sorted((t[i], t[(i + 1) % 3])))
            edge_count[e] = edge_count.get(e, 0) + 1
        try:
            faces.append(bm.faces.new([front(i) for i in t]))
        except ValueError:
            pass
    for (a, b), n in edge_count.items():
        if n == 1:
            try:
                faces.append(bm.faces.new((back(a), back(b), front(b), front(a))))
            except ValueError:
                pass
    faces = [f for f in faces if f.is_valid]
    # every face must point away from the plate: front faces +Y, walls outwards
    for f in faces:
        f.normal_update()
    fr = [f for f in faces if abs(f.normal.y) > 0.99]
    if fr and sum(1 for f in fr if f.normal.y < 0) > len(fr) / 2:
        for f in faces:
            f.normal_flip()
    return faces


def open_text(mb, text, cx, cz, y, cap_h, mi, depth=0.006, font=C.FONT_LATIN, tracking=0.08, res=1):
    """like C.tracked_text, open at the back (sits on a plate at y)"""
    bm = mb.bm
    _, (rx0, ry0, rx1, ry1) = C.glyph_tris('H', font, res)
    s = cap_h / max(1e-6, ry1)
    adv = []
    for ch in text:
        if ch == ' ':
            adv.append(([], 0.0, 0.3)); continue
        groups, (x0, y0, x1, y1) = C.glyph_tri_groups(ch, font, res)
        adv.append((groups, x0, (x1 - x0) if groups else 0.3))
    total = sum(w for _, _, w in adv) * s + tracking * cap_h * (len(adv) - 1)
    x = -total / 2
    faces = []
    for groups, x0, w in adv:
        for pts, tris in groups:
            if tris:
                faces += _extrude_open(bm, [(cx - (x + (px - x0) * s), cz + py * s - cap_h / 2) for px, py in pts], tris, y, depth)
        x += w * s + tracking * cap_h
    mb._tag(faces, mi)
    return total
