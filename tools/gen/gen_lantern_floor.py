"""Floor andon lantern (reference generator: copy this structure).

Identifying features kept at every LOD: square box body, pyramidal cap, glowing washi panels, short legs.
Proxy (3d/assets.json): 0.45 x 0.45 x 1.05 m. Light source in bakes: the washi panels (emissive).
"""
import math
import genlib

ASSET = 'lantern_floor'
FEATURES = ['square box body', 'pyramidal cap', 'glowing washi panels', 'short legs']


def build(lod, seed, w=None, h=None, style=None):
    p = genlib.proxy(ASSET)
    r = genlib.rng(seed, ASSET)
    w = (w or p['w']) * r.uniform(0.92, 1.0)
    h = (h or p['h']) * r.uniform(0.9, 1.0)
    style = style or r.choice(['plain', 'lattice', 'tall_cap'])
    mb = genlib.MeshBuilder()
    wood = mb.slot('hinoki', wear=round(r.uniform(0.2, 0.6), 2), tint=(1.0, r.uniform(0.85, 0.95), r.uniform(0.75, 0.9)))
    paper = mb.slot('lantern_paper', emissive_level=round(r.uniform(0.8, 1.2), 2))
    dark = mb.slot('lacquer_dark')
    leg_h = 0.12 * h
    cap_h = (0.22 if style == 'tall_cap' else 0.16) * h
    body_h = h - leg_h - cap_h
    post = 0.035 * (w / 0.45)
    bev = 0.006 if lod == 0 else 0.0
    z0 = leg_h
    if lod >= 2:
        # silhouette only: glowing body box (the panel), plinth for the legs, corner posts at LOD2
        mb.box((0, 0, leg_h / 2), (w * 0.9, w * 0.9, leg_h), wood)
        mb.box((0, 0, z0 + body_h / 2), (w - post * 0.4, w - post * 0.4, body_h), paper)
        if lod == 2:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    mb.box((sx * (w / 2 - post / 2), sy * (w / 2 - post / 2), z0 + body_h / 2), (post, post, body_h), wood)
    else:
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * (w / 2 - post), sy * (w / 2 - post), leg_h / 2), (post * 1.4, post * 1.4, leg_h), wood, bevel=bev)
                mb.box((sx * (w / 2 - post / 2), sy * (w / 2 - post / 2), z0 + body_h / 2), (post, post, body_h), wood, bevel=bev)
        rails = [z0 + post / 2, z0 + body_h - post / 2] + ([z0 + body_h * 0.5] if style == 'lattice' and lod == 0 else [])
        for z in rails:
            for ang in range(4):
                a = ang * math.pi / 2
                cx, cy = math.sin(a) * (w / 2 - post / 2), math.cos(a) * (w / 2 - post / 2)
                mb.box((cx, cy, z), (w - 2 * post if ang % 2 == 0 else post, post if ang % 2 == 0 else w - 2 * post, post), wood, bevel=bev)
        inset = post * 0.6
        for ang in range(4):
            a = ang * math.pi / 2
            cx, cy = math.sin(a) * (w / 2 - inset), math.cos(a) * (w / 2 - inset)
            size = (w - 2 * post, 0.004, body_h - 2 * post) if ang % 2 == 0 else (0.004, w - 2 * post, body_h - 2 * post)
            mb.box((cx, cy, z0 + body_h / 2), size, paper)
            if style == 'lattice' and lod == 0:
                for k in (1, 2):
                    zz = z0 + post + (body_h - 2 * post) * k / 3
                    sz = (w - 2 * post, 0.012, 0.012) if ang % 2 == 0 else (0.012, w - 2 * post, 0.012)
                    mb.box((math.sin(a) * (w / 2 - inset * 0.4), math.cos(a) * (w / 2 - inset * 0.4), zz), sz, wood)
    # pyramidal cap (4-sided cone) + finial
    segs = 4
    mb.cylinder((0, 0, z0 + body_h + cap_h / 2), radius=w * 0.70, radius2=w * 0.12, depth=cap_h, mi=dark, segs=segs, rot=(0, 0, math.pi / 4))
    if lod < 2:
        mb.cylinder((0, 0, z0 + body_h + cap_h + 0.02), radius=0.02, depth=0.04, mi=dark, segs=8 if lod == 0 else 6)
    o = mb.to_object(ASSET)
    # the cap is 0.70*w*cos45 = 0.495 w each side, inside the proxy width
    return genlib.finish(o)
