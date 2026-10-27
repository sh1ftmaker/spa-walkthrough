"""Lit timber sign tower: a tall hinoki post-box whose front is a glowing washi face with raised dark-ink
火山湯 / KAZAN-YU and the mountain crest, standing on a basalt plinth under a kasagi cap.

Identifying features kept at every LOD: tall timber post box, glowing (amber andon) face carrying the dark
kanji + crest, plinth foot, overhanging cap.
Proxy (3d/assets.json): 1.1 x 0.6 x 4.5 m (w and d include the cap overhang). Front faces +Y.

Variants (default from the seed: 1 hall, 2 grotto, 3 ramen):
  hall    4.2-4.5 m, hip cap with upswept eaves, bronze hoju finial, lattice (kumiko) side faces
  grotto  3.0-3.4 m, flat stepped cap like the grotto sign in the lookbook, kumiko sides
  ramen   1.3-1.5 m floor box, gabled cap, 火山 + crest
Parameters: h (1.2-4.5 m), w (0.5-1.1 m), text (face kanji, stacked), crest (bool), cap ('hip'|'flat'|'gable'),
variant ('hall'|'grotto'|'ramen').

Light / animation data (for the lightmap bake and the web runtime):
  obj['kz_lights']  JSON list of spill lights {pos [x,y,z] (object space), color, energy (W), size}: one in front of
                    the face, one per side. The glow itself is the 'lantern_andon' faces (emissive).
  float point attribute '_flicker' : 1 on the glowing face faces, 0 elsewhere (soft flicker on the emissive
                    strength in the shader; obj['kz_anim'] = {'type': 'shader_flicker', 'attr': '_flicker', ...}).
"""
import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import genlib
import kzgeo_signboard_kanji as K
import kzgeo_bridge_arched as B

ASSET = 'sign_tower_lit'
FEATURES = ['tall timber post box', 'glowing washi face with kanji and crest', 'basalt plinth', 'overhanging cap']
PARAMS = dict(h=(1.2, 4.5), w=(0.5, 1.1), text='str', crest=(True, False), cap=('hip', 'flat', 'gable'),
              variant=('hall', 'grotto', 'ramen'))
VARIANTS = ['hall', 'grotto', 'ramen']


def build(lod, seed, w=None, h=None, text=None, crest=True, cap=None, variant=None):
    p = genlib.proxy(ASSET)
    budget = genlib.budget_of(ASSET) or [1500, 600, 180, 40]
    var = variant or VARIANTS[(seed - 1) % 3]
    for attempt in range(5):
        o = _build_once(lod, seed, var, w, h, text, crest, cap, attempt, p)
        if genlib.tris(o) <= budget[lod] * 1.05 or attempt == 4:
            break
        bpy.data.meshes.remove(o.data)
    return genlib.finish(o, smooth_angle=50)


def _scale_xy(mb, faces, cx, cy, kx, ky):
    vs = list({v for f in faces for v in f.verts})
    for v in vs:
        v.co.x = cx + (v.co.x - cx) * kx
        v.co.y = cy + (v.co.y - cy) * ky


def _build_once(lod, seed, var, w, h, text, crest, cap, attempt, p):
    r = genlib.rng(seed, ASSET + var)
    lod3 = lod == 3
    lod = min(lod, 2)
    mb = genlib.MeshBuilder()
    preset = dict(hall=dict(H=4.2, W=1.1, cap='box', text='火山湯', rd=0.54), grotto=dict(H=2.8, W=0.95, cap='hip', text='火山湯', rd=0.58),
                  ramen=dict(H=1.4, W=0.72, cap='gable', text='火山', rd=0.8))[var]
    if h is not None:
        H = h
    else:
        H = preset['H'] * (r.uniform(0.92, 1.0) if var == 'hall' else r.uniform(0.92, 1.08) if var == 'grotto' else r.uniform(0.92, 1.1))
    W = (w if w is not None else preset['W'] * r.uniform(0.92, 1.0))
    W = min(W, p['w'])
    Dt = min(p['d'], W * preset['rd'] * 1.0 + 0.02)
    capk = cap or preset['cap']
    txt = text or preset['text']
    wood = mb.slot('hinoki', variant='stained', wear=0.1)
    wood_d = mb.slot('hinoki', variant='dark_timber', wear=0.2)
    dark = mb.slot('lacquer_black')
    glow = mb.slot('washi_backlit', emissive_level=round(r.uniform(1.4, 1.8), 2), tint=(1.0, 0.72, 0.4))
    glow_mid = mb.slot('washi_backlit', emissive_level=round(r.uniform(2.2, 2.6), 2), tint=(1.0, 0.82, 0.55))
    glow_hot = mb.slot('washi_backlit', emissive_level=round(r.uniform(3.0, 3.6), 2), tint=(1.0, 0.9, 0.7))
    ink = mb.slot('lacquer_black', tint=(1.0, 0.7, 0.5))
    bronze = mb.slot('bronze', wear=0.3)
    stone = mb.slot('basalt_dry', wear=0.0)

    ov = 0.08 if capk != 'gable' else 0.05
    bw, bd = W - 2 * ov, Dt - 2 * ov                          # body width / depth under the cap
    bd = max(bd, 0.2)
    plinth_h = 0.25 if H > 2 else 0.12
    post = 0.125 if var == 'hall' else 0.1 if var == 'grotto' else 0.06
    low_h = min(0.8, max(0.2, 0.17 * H))
    head_h = 0.06 + 0.008 * H
    cap_h = {'hip': 0.2 + 0.02 * H, 'box': 0.3, 'flat': 0.11 + 0.01 * H, 'gable': 0.17}[capk]
    fin_h = 0.14 if capk == 'hip' and H > 3 else 0.0
    z_low0 = plinth_h
    z_g0 = plinth_h + low_h
    z_g1 = H - cap_h - fin_h - head_h
    z_cap0 = H - cap_h - fin_h
    gh = z_g1 - z_g0
    gz = (z_g0 + z_g1) / 2
    yf = bd / 2                                               # front face plane of the body
    face_y = yf - post * 0.55                                 # glowing face sits just inside the post fronts
    wood_post = wood
    # ------------------------------------------------ plinth
    if lod == 0:
        mb.box((0, 0, plinth_h / 2), (bw + 0.1, bd + 0.1, plinth_h), stone, bevel=0.012)
    else:
        mb.box((0, 0, plinth_h / 2), (bw + 0.1, bd + 0.1, plinth_h), stone)
    # ------------------------------------------------ four corner posts, full height of the body
    zp0, zp1 = z_low0, z_g1 + head_h
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = (sx * (bw / 2 - post / 2), sy * (bd / 2 - post / 2), (zp0 + zp1) / 2)
            if lod == 0:
                K.chamfered_bar(mb, c, (post, post, zp1 - zp0), wood_post, ch=post * 0.16, axis='z')
            elif lod == 1:
                mb.box(c, (post, post, zp1 - zp0), wood_post)
            else:
                mb.box(c, (post, post, zp1 - zp0), wood_post)
    # ------------------------------------------------ lower solid section: lacquer infill + raised panels + rails
    inw, ind = bw - post * 1.2, bd - post * 1.2
    if lod <= 1:
        mb.box((0, 0, z_g0 - low_h / 2), (inw, ind, low_h), dark)
    else:
        mb.box((0, 0, z_g0 - low_h / 2), (bw * 0.96, bd * 0.96, low_h), dark)
    if lod == 0:
        pw = bw - 2.6 * post
        mb.box((0, yf - post * 0.28, z_g0 - low_h / 2), (pw, 0.014, low_h - 0.14), dark, bevel=0.003)
        mb.box((0, yf - post * 0.28 - 0.001, z_g0 - low_h / 2), (pw - 0.07, 0.022, low_h - 0.21), wood_d, bevel=0.003)
        for sx in (-1, 1):
            mb.box((sx * (bw / 2 - post * 0.28), 0, z_g0 - low_h / 2), (0.014, bd - 2.6 * post, low_h - 0.14), dark)
    # rails above and below the glow zone (front and sides)
    if lod <= 1:
        rh = 0.035
        for zz in (z_g0 + rh / 2, z_g1 - rh / 2):
            mb.box((0, 0, zz), (bw - post * 0.4, bd - post * 0.4, rh), wood)
        # kasagi-shita header band
        mb.box((0, 0, z_g1 + head_h / 2), (bw + 0.02, bd + 0.02, head_h), wood_d if lod == 0 else wood, bevel=0.006 if lod == 0 else 0.0)
    else:
        mb.box((0, 0, z_g1 + head_h / 2), (bw + 0.02, bd + 0.02, head_h), wood_d)
    # ------------------------------------------------ glowing core (the washi box) + lattices
    core_w, core_d = bw - post * 1.1, bd - post * 1.1
    gcore = mb.box((0, 0, gz), (core_w, core_d, gh), glow)
    if lod <= 1:
        # stepped falloff: dark amber edge, creamier middle, hot centre (2 mm steps proud of the face)
        for k, (mi_, fx, fz) in enumerate(((glow_mid, 0.82, 0.9), (glow_hot, 0.5, 0.7))):
            mb.box((0, core_d / 2 - face_y * 0 - 0.0 + 0.0, gz), (core_w * fx, core_d + 0.004 * (k + 1) - 0.0, gh * fz), mi_) if False else \
                mb.box((0, 0, gz), (core_w * fx, core_d + 0.004 * (k + 1), gh * fz), mi_)
    # ------------------------------------------------ face: ink glyphs + crest
    gw = core_w - 0.06
    crest_bot = z_g0 + 0.0
    n = len(txt)
    s_cap = (gh * 0.52) / (n * 1.18)
    s = min(gw * 0.6, s_cap)
    zt = z_g1 - 0.14 - n * 1.18 * s / 2
    yi = face_y + 0.009
    if gw > 0.2:
        if lod == 0:
            K.add_text(mb, txt, 0, zt, yi, s, ink, res=2 if attempt == 0 else 1, vertical=True, dissolve=0.14 if attempt == 0 else 0.35, gap=1.18, max_w=gw * 0.8)
        elif lod == 1:
            K.add_text(mb, txt, 0, zt, yi, s, ink, res=1, vertical=True, dissolve=0.4, gap=1.18, max_w=gw * 0.8)
        else:
            for i in range(n):                              # three stacked glyph blocks of unequal width, then a crest triangle
                zz = zt + ((n - 1) / 2 - i) * 1.18 * s
                ww_ = s * (0.42, 0.34, 0.46)[i % 3]
                K.flat_poly(mb, [(ww_, zz + s * 0.4), (-ww_, zz + s * 0.4), (-ww_, zz - s * 0.4), (ww_, zz - s * 0.4)], yi, ink)
            if crest:
                zc_ = zt - n * 1.18 * s / 2 - 0.1
                K.flat_poly(mb, [(gw * 0.2, zc_ - 0.15), (-gw * 0.2, zc_ - 0.15), (0.0, zc_)], yi, ink)
        zl = zt - n * 1.18 * s / 2 - gw * 0.08
        if var != 'ramen':
            if lod == 0:
                K.add_latin(mb, 'KAZAN-YU', 0, zl, yi, gw * 0.1, ink, max_w=gw * 0.78)
            elif lod == 1:
                K.flat_poly(mb, [(gw * 0.33, zl + gw * 0.035), (-gw * 0.33, zl + gw * 0.035), (-gw * 0.33, zl - gw * 0.035), (gw * 0.33, zl - gw * 0.035)], yi, ink)
            zl -= gw * 0.09
        if crest and lod <= 1:
            cs = min(gw * 0.62, max(0.1, (zl - z_g0 - 0.1) * 0.9))
            polys = K.crest_polys('kazan', 0 if lod == 0 else 1, r)
            crest_bot = zl - 0.95 * cs
            if cs > 0.07:
                for poly in polys:
                    K.flat_poly(mb, [(-px * cs, zl - 0.95 * cs + py * cs) for px, py in poly], yi, ink)
    if var == 'grotto' and lod <= 1:
        # a mid rail splits the face into a text panel and a lower panel (the temperature-board position)
        zr = z_g0 + gh * 0.34
        mb.box((0, face_y + 0.01, zr), (gw + 0.04, 0.02, 0.04), wood)
        if lod == 0:
            for sx in (-1, 1):
                mb.box((sx * (gw / 2 + 0.005), face_y + 0.014, zr), (0.03, 0.03, 0.06), bronze)
    # kumiko lattices on the two side faces and a border frame on the front
    if lod == 0:
        t = 0.014
        lw_ = bd - post * 1.1
        for sx in (-1, 1):
            xs = sx * (bw / 2 - post * 0.55 + 0.002)
            ny = 3
            for k in range(1, ny + 1):
                yk = -lw_ / 2 + lw_ * k / (ny + 1)
                mb.box((xs + sx * t / 2, yk, gz), (t, t, gh - 0.04), wood)
            nz = max(2, int(gh / 0.42))
            for k in range(1, nz + 1):
                zk = z_g0 + gh * k / (nz + 1)
                mb.box((xs + sx * t / 2, 0, zk), (t, lw_, t), wood)
        # front lattice: a skirt in the lower part of the face, always below the crest
        zl_top = min(z_g0 + gh / 3, crest_bot - 0.04)
        if zl_top - z_g0 > 0.16:
            nx = 3
            hl = zl_top - z_g0
            for k in range(1, nx + 1):
                mb.box((-gw / 2 + gw * k / (nx + 1), face_y + 0.004, z_g0 + hl / 2), (t, t, hl - 0.04), wood)
            for k in (1, 2):
                mb.box((0, face_y + 0.004, z_g0 + hl * k / 3), (gw, t, t), wood)
        # front inner border rails
        for sx in (-1, 1):
            mb.box((sx * (gw / 2 + 0.012), face_y + 0.004, gz), (t, t, gh - 0.04), wood)
        for zz in (z_g0 + 0.03, z_g1 - 0.03):
            mb.box((0, face_y + 0.004, zz), (gw + 0.05, t, t), wood)
    elif lod == 1:
        t = 0.014
        for sx in (-1, 1):
            xs = sx * (bw / 2 - post * 0.55 + 0.002)
            mb.box((xs + sx * t / 2, 0, gz), (t, t, gh - 0.04), wood)
    if lod == 0:
        iron = mb.slot('iron', wear=0.35)
        # iron corner brackets where the posts meet the rails, plus straps on the lower section
        for sx in (-1, 1):
            xq = sx * (bw / 2 - post / 2)
            for zz in (z_g0, z_g1):
                mb.box((xq, yf + 0.004, zz), (post * 0.9, 0.008, 0.11), iron)
            mb.box((xq, yf + 0.004, z_g0 - low_h / 2), (post * 0.9, 0.008, low_h * 0.8), iron)
            for fz_ in (0.33, 0.66):
                mb.box((xq, yf + 0.004, z_g0 + gh * fz_), (post * 0.9, 0.008, 0.1), iron)
        for sx in (-1, 1):
            for zz in (z_g1 + head_h * 0.5,):
                for k in range(3):
                    mb.box((sx * (bw * 0.12 + k * bw * 0.2), yf + head_h * 0.0 + 0.012, zz), (0.022, 0.012, 0.022), bronze)
    # ------------------------------------------------ cap
    cap_w, cap_d = W, Dt
    zc0 = z_cap0
    if capk == 'hip':
        R = math.sqrt(2) * 0.5
        if lod <= 1:
            # eave slab, then a concave-sided pyramid with upswept corners
            mb.box((0, 0, zc0 + 0.018), (cap_w, cap_d, 0.036), wood_d, bevel=0.005 if lod == 0 else 0.0)
            prof = [(R * 1.0, 0.036), (R * 0.9, 0.05), (R * 0.62, 0.1 + cap_h * 0.2), (R * 0.34, 0.1 + cap_h * 0.55), (R * 0.12, cap_h * 0.9), (0.0, cap_h)] if lod == 0 else \
                   [(R * 0.98, 0.036), (R * 0.5, cap_h * 0.55), (0.0, cap_h)]
            prof = [(rr * cap_w, zc0 + z) for rr, z in prof]
            fs = B.lathe(mb, (0, 0, 0), prof, dark, segs=4, rot=math.pi / 4)
            _scale_xy(mb, fs, 0, 0, 1.0, cap_d / cap_w)
            # under-eave brackets
            if lod == 0:
                nb = 4
                for k in range(nb):
                    xk = -cap_w / 2 * 0.72 + cap_w * 0.72 * k / (nb - 1)
                    mb.box((xk, cap_d / 2 * 0.9, zc0 - 0.012), (0.05, 0.05, 0.03), wood)
                    mb.box((xk, -cap_d / 2 * 0.9, zc0 - 0.012), (0.05, 0.05, 0.03), wood)
        else:
            mb.box((0, 0, zc0 + 0.02), (cap_w, cap_d, 0.04), wood_d)
            fs = B.lathe(mb, (0, 0, 0), [(R * cap_w * 0.98, zc0 + 0.04), (0.0, zc0 + cap_h)], dark, segs=4, rot=math.pi / 4)
            _scale_xy(mb, fs, 0, 0, 1.0, cap_d / cap_w)
        if fin_h:
            zf = zc0 + cap_h
            if lod == 0:
                B.lathe(mb, (0, 0, 0), [(0.022, zf - 0.01), (0.032, zf + 0.03), (0.016, zf + 0.05), (0.04, zf + 0.085), (0.0, zf + fin_h)], bronze, segs=6)
            elif lod == 1:
                B.lathe(mb, (0, 0, 0), [(0.03, zf - 0.01), (0.035, zf + 0.06), (0.0, zf + fin_h)], bronze, segs=4)
    elif capk == 'box':
        # deep boxed lintel: eave slab, dark box, thin top slab; two bracket blocks per side under the eave
        mb.box((0, 0, zc0 + 0.03), (cap_w, cap_d, 0.06), wood, bevel=0.008 if lod == 0 else 0.0)
        mb.box((0, 0, zc0 + 0.06 + (cap_h - 0.1) / 2), (cap_w * 0.9, cap_d * 0.9, cap_h - 0.1), dark)
        mb.box((0, 0, zc0 + cap_h - 0.02), (cap_w * 0.97, cap_d * 0.97, 0.04), wood)
        if lod == 0:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    mb.box((sx * cap_w * 0.3, sy * (bd / 2 - 0.01), zc0 - 0.05), (0.08, 0.08, 0.1), wood)
                    mb.box((sx * (bw / 2 - 0.01), sy * bd * 0.22, zc0 - 0.05), (0.08, 0.08, 0.1), wood)
            for k in range(7):
                xk = -cap_w * 0.42 + cap_w * 0.84 * k / 6
                for sy in (-1, 1):
                    mb.box((xk, sy * (cap_d / 2 - 0.02), zc0 - 0.012), (0.03, 0.05, 0.04), wood)       # rafter ends under the eave
    elif capk == 'flat':
        # two stepped slabs with a recessed lip, like the grotto sign
        mb.box((0, 0, zc0 + 0.025), (cap_w, cap_d, 0.05), wood_d, bevel=0.008 if lod == 0 else 0.0)
        if lod <= 1:
            mb.box((0, 0, zc0 + 0.05 + (cap_h - 0.05) / 2), (cap_w * 0.82, cap_d * 0.82, cap_h - 0.05), dark, bevel=0.006 if lod == 0 else 0.0)
            if lod == 0:
                for k in range(5):
                    xk = -cap_w * 0.4 + cap_w * 0.8 * k / 4
                    mb.box((xk, cap_d / 2 * 0.92, zc0 - 0.012), (0.045, 0.045, 0.03), wood)
        else:
            mb.box((0, 0, zc0 + 0.05 + (cap_h - 0.05) / 2), (cap_w * 0.82, cap_d * 0.82, cap_h - 0.05), dark)
    else:   # gable: ridge along X
        gl = cap_w
        sec = [(cap_d / 2, zc0), (-cap_d / 2, zc0), (-cap_d / 2 + 0.01, zc0 + 0.03), (0.0, zc0 + cap_h), (cap_d / 2 - 0.01, zc0 + 0.03)]
        _prism_x(mb, sec, -gl / 2, gl / 2, dark)
        if lod <= 1:
            # barge boards at the gable ends
            for sx in (-1, 1):
                mb.box((sx * (gl / 2 - 0.01), 0, zc0 + 0.012), (0.02, cap_d, 0.025), wood_d)
        if lod == 0:
            mb.box((0, 0, zc0 + cap_h + 0.01), (gl * 0.96, 0.03, 0.02), wood_d)
    if lod3:
        mb.bm.clear()
        _lod3(mb, bw, bd, H, W, Dt, plinth_h, z_cap0, cap_h, capk, glow, dark, wood, ink)
    o = K.to_object(mb, ASSET)
    me = o.data
    # shader flicker mask: 1 on the glowing faces
    fl = me.attributes.new('_flicker', 'FLOAT', 'POINT')
    gi = [i for i, (mid, prm) in enumerate(mb.slots) if mid == 'lantern_andon']
    for poly in me.polygons:
        if poly.material_index in gi:
            for vi in poly.vertices:
                fl.data[vi].value = 1.0
    lights = [dict(pos=[0, yf + 0.38, gz], color=[1.0, 0.62, 0.28], energy=14 + 4 * gh, size=0.25, note='front spill')] + \
             [dict(pos=[sx * (bw / 2 + 0.3), 0, gz], color=[1.0, 0.6, 0.26], energy=6 + 2 * gh, size=0.2, note='side spill') for sx in (-1, 1)]
    o['kz_lights'] = json.dumps(lights)
    o['kz_anim'] = json.dumps({'type': 'shader_flicker', 'attr': '_flicker', 'amount': 0.12, 'hz': [3.1, 7.3]})
    o['kz_params'] = json.dumps(dict(variant=var, w=round(W, 3), h=round(H, 3), cap=capk, text=txt, crest=crest))
    return o


def _prism_x(mb, sec_yz, x0, x1, mi):
    bm = mb.bm
    a = [bm.verts.new((x0, y, z)) for y, z in sec_yz]
    b = [bm.verts.new((x1, y, z)) for y, z in sec_yz]
    n = len(sec_yz)
    faces = [bm.faces.new(a), bm.faces.new(b[::-1])]
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((a[i], b[i], b[j], a[j])))
    mb._tag(faces, mi)


def _lod3(mb, bw, bd, H, W, Dt, plinth_h, z_cap0, cap_h, capk, glow, dark, wood, ink):
    """40-triangle silhouette: slim body (glow front quad + sides), plinth, cap"""
    b = bd * 0.9
    mb.box((0, 0, plinth_h / 2), (bw + 0.08, bd + 0.08, plinth_h), dark)                 # 12
    # body: 3 visible sides (front glow, two dark sides) without top/bottom caps -> 6 tris
    zb0, zb1 = plinth_h, z_cap0
    K.flat_poly(mb, [(bw / 2, zb0), (-bw / 2, zb0), (-bw / 2, zb1), (bw / 2, zb1)], b / 2, glow)
    zt_ = zb0 + (zb1 - zb0) * 0.66
    for i in range(3):
        zz = zt_ + (1 - i) * (zb1 - zb0) * 0.14
        ww_ = bw * (0.2, 0.16, 0.22)[i]
        K.flat_poly(mb, [(ww_, zz + (zb1 - zb0) * 0.05), (-ww_, zz + (zb1 - zb0) * 0.05), (-ww_, zz - (zb1 - zb0) * 0.05), (ww_, zz - (zb1 - zb0) * 0.05)], b / 2 + 0.003, ink)
    for sx in (-1, 1):
        # side face as an upright quad in the YZ plane
        v = [mb.bm.verts.new((sx * bw / 2, -b / 2, zb0)), mb.bm.verts.new((sx * bw / 2, b / 2, zb0)),
             mb.bm.verts.new((sx * bw / 2, b / 2, zb1)), mb.bm.verts.new((sx * bw / 2, -b / 2, zb1))]
        f = mb.bm.faces.new(v if sx > 0 else v[::-1])
        f.material_index = wood
        f[K.sheet_layer(mb)] = 1
    # cap: 4-sided cone (8 tris with base) or a box
    if capk == 'hip':
        fs = B.lathe(mb, (0, 0, 0), [(math.sqrt(2) * W * 0.5, z_cap0), (0.0, z_cap0 + cap_h)], dark, segs=4, rot=math.pi / 4)      # 4 + 2 base
        _scale_xy(mb, fs, 0, 0, 1.0, Dt / W)
    else:
        mb.box((0, 0, z_cap0 + cap_h / 2), (W, Dt, cap_h), dark)                                                                 # 12
