"""Bench (bench): long low bench in five styles (slatted, slab, cushioned, seat_step, niche).

Identifying features kept at every LOD: long low bench, slatted hinoki on legs, stone slab, cushioned island,
wet stone seat-step.
Construction (boxes with chamfer at LOD0/1, one part per member, hinoki/basalt/noren slots)
  * slatted: n hinoki slats across the top on two end legs and a lower stretcher; LOD2 keeps 3 slats, LOD3 a
    solid top on a plinth.
  * slab: basalt_dry slab on two stone pier blocks; LOD3 slab on one pier.
  * cushioned: hinoki frame with a noren cushion on top (cushion thickness seeded); LOD3 frame plus cushion.
  * seat_step: a wet basalt step block with a dry lip along the front edge; LOD3 one block.
  * niche: basalt back wall (height = proxy h) with a hinoki seat board on two stone supports.
Animation: none. Lighting: lightmap (UV1 from genlib.finish).

Parameters (build kwargs; proxy 2.4 x 0.6 x 0.45 m):
  l       length 1.2-6 m (default 2.4)
  h       height 0.4-0.5 m (default 0.45)
  d       depth 0.4-0.9 m (default 0.6)
  style   slatted | slab | cushioned | seat_step | niche (default slatted)
  cushion cushion thickness override in metres, 0.06-0.12
Seeds change slat count (5-7 at LOD0), slab thickness, cushion thickness, leg inset and lip width.
"""
import math
import genlib

ASSET = 'bench'
FEATURES = ['long low bench', 'slatted hinoki on legs', 'stone slab', 'cushioned island', 'wet stone seat-step']


def taper_box(mb, xy, z1, top, bot, mi, chamfer=0.0):
    """Leg: rectangle `top` (w along x, d along y) at z = z1 down to `bot` at z = 0, centred on xy."""
    x0, y0 = xy
    (tw, td), (bw, bd) = top, bot
    vs = [mb.bm.verts.new((x0 + sx * w / 2, y0 + sy * d / 2, z))
          for (w, d, z) in ((bw, bd, 0.0), (tw, td, z1))
          for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    b, t_ = vs[:4], vs[4:]
    faces = [mb.bm.faces.new(b[::-1]), mb.bm.faces.new(t_)]
    for k in range(4):
        faces.append(mb.bm.faces.new((b[k], b[(k + 1) % 4], t_[(k + 1) % 4], t_[k])))
    mb._tag(faces, mi)
    if chamfer > 0:
        edges = list({e for f in faces for e in f.edges})
        import bmesh
        bmesh.ops.bevel(mb.bm, geom=edges, offset=chamfer, segments=1, affect='EDGES', profile=0.5)


def build(lod, seed, l=None, h=None, d=None, style=None, cushion=None):
    g = genlib.rng(seed, ASSET)
    style = style or 'slatted'
    L = l or 2.4
    H = h or 0.45
    D = d or 0.6
    bev = 0.012 if lod <= 1 else 0.0
    inset = g.uniform(0.15, 0.35)
    mb = genlib.MeshBuilder()
    wood = mb.slot('hinoki', variant='wet_oiled')          # library variant, warm oiled timber
    dry = mb.slot('basalt_dry')
    wet = mb.slot('basalt_wet')
    cush = mb.slot('noren')

    if style == 'slatted':
        # open bench: five long boards across the depth, tapered chamfered legs (0.10 x 0.12 m at the top),
        # two lower stretchers at 0.10 m with tenons proud of the legs. Underside open.
        n = 5
        gap = 0.004
        bw = min(g.uniform(0.11, 0.12) if lod == 0 else 0.115, (D - (n - 1) * gap) / n)
        bd = 0.045
        y0 = -(n * bw + (n - 1) * gap) / 2 + bw / 2
        lx = L / 2 - inset
        leg_top = H - bd
        for i in range(n if lod < 3 else 0):
            mb.box((0, y0 + i * (bw + gap), H - bd / 2), (L, bw, bd), wood, bevel=0.008 if lod == 0 else 0.0)
        for x in (-lx, lx):
            for y in (-0.24, 0.24):
                if lod == 3:
                    break
                taper_box(mb, (x, y), leg_top, (0.10, 0.12), (0.085, 0.105), wood,
                          chamfer=0.007 if lod == 0 else 0.0)
        if lod == 3:
            for x in (-lx, lx):
                mb.cylinder((x, 0, leg_top / 2), 0.04, leg_top, wood, segs=4, cap=False)
        elif lod <= 1:
            tenon = 0.025
            x_end = lx + 0.05 + tenon
            for y in (-0.24, 0.24):
                mb.box((0, y, 0.10), (2 * x_end, 0.04, 0.04), wood, bevel=0.0)
        if lod == 3:
            mb.box((0, 0, H - bd / 2), (L, D, bd), wood, bevel=0.0)

    elif style == 'slab':
        t = g.uniform(0.08, 0.12)
        if lod == 3:
            mb.box((0, 0, H - t / 2), (L, D, t), dry, bevel=0.0)
            mb.box((0, 0, (H - t) / 2), (L * 0.5, D * 0.8, H - t), dry, bevel=0.0)
        else:
            mb.box((0, 0, H - t / 2), (L, D, t), dry, bevel=bev)
            for x in (-L * 0.32, L * 0.32):
                mb.box((x, 0, (H - t) / 2), (0.5, D * 0.85, H - t), wet, bevel=bev)

    elif style == 'cushioned':
        ct = cushion or g.uniform(0.06, 0.12)
        F = H - ct                                  # frame top; the cushion sits on it, total height stays H
        if lod == 3:
            mb.box((0, 0, F / 2), (L * 0.9, D * 0.8, F), wood, bevel=0.0)
            mb.box((0, 0, F + ct / 2), (L * 0.92, D * 0.8, ct), cush, bevel=0.0)
        else:
            mb.box((0, 0, F - 0.03), (L, D, 0.06), wood, bevel=bev)
            for x in (-L / 2 + inset, L / 2 - inset):
                mb.box((x, 0, (F - 0.06) / 2), (0.10, D * 0.92, F - 0.06), wood, bevel=bev)
            mb.box((0, 0, F + ct / 2), (L * 0.92, D * 0.8, ct), cush, bevel=0.03 if lod == 0 else 0.0)

    elif style == 'seat_step':
        if lod == 3:
            mb.box((0, 0, H / 2), (L, D, H), wet, bevel=0.0)
        else:
            mb.box((0, 0, H / 2), (L, D, H), wet, bevel=0.03 if lod == 0 else 0.015)
            mb.box((0, -D / 2 + 0.02, H - 0.012), (L * 0.98, 0.04, 0.024), dry, bevel=0.0)

    elif style == 'niche':
        if lod == 3:
            mb.box((0, -0.22, H / 2), (L, 0.16, H), dry, bevel=0.0)
            mb.box((0, 0.06, H * 0.55), (L - 0.3, D * 0.6, 0.05), wood, bevel=0.0)
        else:
            mb.box((0, -0.22, H / 2), (L, 0.16, H), dry, bevel=bev)
            mb.box((0, 0.06, H * 0.55), (L - 0.3, D * 0.6, 0.05), wood, bevel=bev)
            for x in (-L / 2 + 0.3, L / 2 - 0.3):
                mb.box((x, 0.06, H * 0.27), (0.12, D * 0.5, H * 0.55), dry, bevel=bev)

    else:
        raise ValueError(f'unknown bench style {style}')

    o = mb.to_object(ASSET)
    return genlib.finish(o)
