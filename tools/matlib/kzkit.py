"""Blender mirror of the shader kit (3d/research/shaders/kzshader.js, kzShade) for the library.

The web runtime shades kit materials with kzShade(): Codex plates sampled with hex-tiling (or a
world biplanar projection, or a plank shuffle), ALU macro variation, wet film and run-off streaks,
and hybrid procedural overlays.  This module builds the same thing as Blender node groups so
library previews and bakes match the web:

  KZ_HexGrid     Mikkelsen 2022 / Heitz-Neyret triangle grid: 3 vertices, barycentric weights,
                 per-vertex random rotation (kz_rot), scale jitter and patch offset (KZ_PATCH)
  kit_sample     3 taps per map, normals turned into height derivatives and rotated back with their
                 tile, weights w^7 x height metric (beta 0.6), contrast gain
  triplanar      world projection for 'biplanar' materials (Z-up; X->(y,z), Y->(x,z), Z->(x,y)),
                 height-aware blend; 'floor' = XY only
  boards         per-board shuffle of the plate's planks (hinoki, lacquer)
  macro          3 octaves of world-space noise (bright, hue, wet patches) + vertical run-off streaks
  overlays       basalt facet chips, obsidian flat facets + ridges, lava seams as emission with macro
                 hot/cool regions, a large (~20 m) hot/cool mask and downhill flow bands
The normal is built as a surface gradient (Mikkelsen 2020) and handed to KZ_Core, which applies
the 7 settings with the kit's formulas.  The view-layer property `kz_bake` = 1 removes all normal
detail (geometric normals only) for the Cycles irradiance bake, as the kit README asks.

Plate fixes from review r2 (`fix` in the KIT table) are applied when the kit plates are converted
to library PNGs: de-light residue, rot spots, glitch crosses, colour corrections.
"""
import json
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
KIT_DIR = os.path.join(ROOT, '3d', 'research', 'shaders')
PL_DIR = os.path.join(KIT_DIR, 'demo', 'tex', 'pl')
NOISE_PNG = os.path.join(KIT_DIR, 'demo', 'tex', 'kz_noise.png')


# ----------------------------------------------------------------------------- kzmaterials.js
def parse_js_object(src):
    """Very small JS-object-literal -> JSON converter (enough for kzmaterials.js)."""
    s = re.sub(r'//[^\n]*', '', src)
    s = s.replace("'", '"')
    s = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', s)
    s = re.sub(r',(\s*[}\]])', r'\1', s)
    return json.loads(s)


def load_kzm(path=os.path.join(KIT_DIR, 'kzmaterials.js')):
    src = open(path).read()
    body = src[src.index('export const KZM = ') + len('export const KZM = '):]
    body = body[:body.index('\n};') + 2]
    return parse_js_object(body)


# Overrides on top of the kit's table (review r2 + coordinator's known-bad list).
OVERRIDES = {
    'paving': dict(tech='plain+macro', note='Discrete flagstones: hex blending made ghost joints. Use per-stone '
                   'UV islands with a random offset/rotation into the plate (layout geometry), plain sampling.'),
    'glacier_ice': dict(tech='plain+macro', note='Hex blending made the ice blobby: plain sampling + macro; '
                        'interior/parallax look belongs to the ice shader.'),
    'lava': dict(lavaMask=dict(sizeM=20.0, flow=[3.0, 25.0], low=0.2, high=1.35),
                 note='Hybrid crust plate, seams as emission; a 20 m hot/cool mask and 3 x 25 m downhill flow '
                      'bands break the uniform busyness at 40 m.'),
    'lava_flow': dict(lavaMask=dict(sizeM=14.0, flow=[2.0, 18.0], low=0.35, high=1.4)),
    'lacquer_dark': dict(tech='keep', note='Clean procedural urushi (round 5); the plate mottle is lacquer_mottled.'),
    'lacquer_mottled': dict(family='wood', tech='boards', proj='uv', plate='lacquer', plateM=1.8,
                            boards=dict(n=3, widthM=0.24, margin=0.03), rot=0, rough=[0.25, 0.1], porosity=0,
                            macro=dict(amount=0.4, size1=3, size2=9, hue=[1, 1, 1], streak=0)),
    'washi_backlit': dict(glow=dict(color=[1.0, 0.66, 0.18], fibre=0.12, mean=0.55),
                          note='Even warm back-lit glow (emissive), fibre variation +-~10 %.'),
    'rimstone': dict(note='Plate on tops and sides (world projection); the procedural side variant read as wood.'),
    'obsidian': dict(tech='antitile', proc=None, gain=0.7, rough=[0.03, 0.06],
                     note='Continuous black gloss (facet overlay removed, review r3); plate veins as thin fractures.'),
    'hinoki': dict(note='Board shuffle. Default is the darker aged timber (review r2); variant natural = pale.'),
    # library-only materials brought onto kit plates
    'cave_rock': dict(family='stone', tech='hybrid', proj='biplanar', plate='rock_wet_ore', plateM=3.0, gain=1.3,
                      plate2='basalt_vesicular', layer=dict(amount=0.35, sizeM=8), rot=1, rough=[0.6, 0.2],
                      porosity=0.6, proc='basalt', procA=[0.8, 0.25, 0.22, 0.12],
                      macro=dict(amount=1, size1=7, size2=24, hue=[0.88, 0.97, 1.15], streak=0.7),
                      note='Cave ceiling/walls: wet-ore plate + vesicular layer, patchy gloss (0.2-0.6).'),
    'stepping_stone': dict(family='stone', tech='plain+macro', proj='uv', plate='rock_teal_glass', plateM=0.9,
                           rot=0, rough=[0.35, 0.08], porosity=0.4,
                           macro=dict(amount=0.6, size1=2, size2=6, hue=[0.92, 0.98, 1.06], streak=0),
                           note='Per-stone object UVs (whole plate on one stone top, 3 variants by rotation); '
                                'teal camouflage removed; wear param = polished centre.'),
    'sinter': dict(family='stone', tech='antitile', proj='uv', plate='sulfur_travertine', plateM=2.6, rot=1,
                   rough=[0.55, 0.15], porosity=0.4,
                   macro=dict(amount=0.7, size1=4, size2=12, hue=[0.96, 1.0, 1.04], streak=0.5),
                   note='Cream/grey sinter with ochre and iron streaks; hex anti-tiling at 2.6 m.'),
}

# Plate fixes (applied to the kit plates when they become library textures).
FIX = {
    'rock_wet_ore': dict(desat=0.3, cool=True),             # pink de-light residue
    'basalt_columnar_wet': dict(desat=0.45, cool=True),
    'basalt_vesicular': dict(desat=0.6, gain=1.35),         # lift dark grey (r2: mean 0.04-0.05)
    'rock_teal_glass': dict(desat=0.12, cool=True),         # stepping stone: no teal camouflage
    'sulfur_travertine': dict(desat=0.12, tint=[1.0, 0.98, 0.90], gain=1.05),  # cream/grey, not pink
    'rimstone': dict(desat=0.45, tint=[1.0, 0.95, 0.84]),   # cream with ochre
    'ash_clay': dict(desat=0.35, tint=[1.0, 0.97, 0.92]),   # ash grey-beige
    'lacquer': dict(spots=True, desat=0.35, gain=0.45, clip_hi=1.3),
    'obsidian': dict(desat=0.12, clip_hi=1.12, gain=0.55),                            # orange rot spots -> black-brown
    'noren': dict(clip_hi=1.25),                            # white glitch crosses
    'black_sand': dict(clip_hi=1.6),                        # bright ring discs
    'glacier_ice': dict(clip_hi=1.5),                       # white swirls contrast
    'iron': dict(iron=True),                                # mostly black oxide, rust in cavities
    'bronze': dict(bronze=True),                            # verdigris only in cavities
}


def kit_table():
    kzm = load_kzm()
    for k, v in OVERRIDES.items():
        kzm[k] = dict(kzm.get(k, {}), **v)
    return kzm


def write_kzmaterials(path, kzm):
    with open(path, 'w') as f:
        f.write('// Canonical per-material shader-kit table for the Kazan-yu library (generated by\n'
                '// tools/matlib/kzkit.py from 3d/research/shaders/kzmaterials.js + library overrides).\n'
                '// tech: procedural | hybrid | antitile | boards | plain+macro | keep\n'
                'export const KZM = ' + json.dumps(kzm, indent=1) + ';\n\n'
                'export const KZM_DEMO = { pool_floor: { ...KZM.paving, caustics: 1.0, settings: { wetness: 1 },'
                ' note: \'paving + kzCaustic\' } };\n')


# ----------------------------------------------------------------------------- plate fixes
def _load(path):
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4).astype(np.float64)        # row 0 = bottom, values as stored


def _s2l(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def _l2s(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def _lum(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def fix_plate(name, base_srgb, nh):
    """base_srgb (H,W,3) sRGB-encoded, nh (H,W,4) linear.  Returns fixed sRGB base."""
    f = FIX.get(name)
    if not f:
        return base_srgb
    lin = _s2l(base_srgb)
    L = _lum(lin)[..., None]
    h = nh[..., 2:3]
    if 'desat' in f:
        lin = L + (lin - L) * f['desat']
    if f.get('cool'):
        lin = lin * np.array([0.95, 0.99, 1.08])
    if 'tint' in f:
        lin = lin * np.array(f['tint'])
    if 'gain' in f:
        lin = lin * f['gain']
    if 'clip_hi' in f:                                   # soft-clip luminance above k x median
        med = np.median(L)
        knee = med * f['clip_hi']
        Lc = np.where(L > knee, knee + (L - knee) * 0.25, L)
        lin = lin * (Lc / np.maximum(L, 1e-6))
    if f.get('spots'):                                    # saturated orange flecks -> lacquer black-brown
        sat = (lin.max(-1) - lin.min(-1))[..., None] / np.maximum(lin.max(-1)[..., None], 1e-6)
        m = np.clip((sat - 0.55) / 0.25, 0, 1) * np.clip((lin[..., 0:1] - 0.03) / 0.05, 0, 1)
        lin = lin * (1 - m) + m * np.array([0.022, 0.010, 0.008])
    if f.get('iron'):                                     # black oxide on the highs, rust in cavities
        rust = np.clip((0.36 - h) / 0.16, 0, 1)
        ox = np.array([0.036, 0.034, 0.033]) * (0.7 + 0.6 * L / max(float(L.mean()), 1e-6))
        lin = lin * rust + ox * (1 - rust)
    if f.get('bronze'):                                   # teal verdigris only where low
        sat_g = lin[..., 1:2] + lin[..., 2:3] * 0.6 - lin[..., 0:1] * 1.2
        verd = np.clip(sat_g / 0.05, 0, 1)
        keep = np.clip((0.5 - h) / 0.2, 0, 1)
        metal = np.array([0.32, 0.21, 0.10]) * (0.6 + 0.8 * L / max(float(L.mean()), 1e-6))
        lin = lin * (1 - verd) + (lin * keep + metal * (1 - keep)) * verd
    return _l2s(lin)


def prepare_plates(names, out_dir, write_png):
    """Kit plates -> fixed library PNGs pl_<name>_{base,nh}.png (+ kz_noise.png).  Returns paths."""
    out = {}
    for n in sorted(names):
        b = _load(os.path.join(PL_DIR, f'{n}_base.jpg'))
        nh = _load(os.path.join(PL_DIR, f'{n}_nh.png'))
        base = fix_plate(n, b[..., :3], nh)
        pb = os.path.join(out_dir, f'pl_{n}_base.png')
        pn = os.path.join(out_dir, f'pl_{n}_nh.png')
        write_png(pb, np.clip(np.rint(base * 255), 0, 255).astype(np.uint8))
        write_png(pn, np.clip(np.rint(nh * 255), 0, 255).astype(np.uint8))
        out[n] = (pb, pn)
    nz = _load(NOISE_PNG)
    pz = os.path.join(out_dir, 'kz_noise.png')
    write_png(pz, np.clip(np.rint(nz * 255), 0, 255).astype(np.uint8))
    out['_noise'] = pz
    return out


# ----------------------------------------------------------------------------- node building
TAU = 6.2831853


def build_hexgrid(B, new_group, sock):
    """KZ_HexGrid: tile coords -> 3 vertex sample coords, angles, scales and barycentric weights."""
    import bpy  # noqa: F401
    ng = new_group('KZ_HexGrid')
    sock(ng, 'S', 'INPUT', 'v', (0, 0, 0))
    sock(ng, 'Rot', 'INPUT', 'f', 1.0)
    sock(ng, 'Jit', 'INPUT', 'f', 0.25)
    sock(ng, 'ScaleJit', 'INPUT', 'f', 0.25)
    for i in (1, 2, 3):
        sock(ng, f'ST{i}', 'OUTPUT', 'v')
        sock(ng, f'A{i}', 'OUTPUT', 'f')
        sock(ng, f'SC{i}', 'OUTPUT', 'f')
    sock(ng, 'W', 'OUTPUT', 'v')
    b = B(ng)
    gi = b.node('NodeGroupInput')
    I = lambda n: b.out(gi, n)  # noqa: E731
    x, y, _ = b.sep(I('S'))
    X, Y = x * 3.46410162, y * 3.46410162
    skx = X - Y * 0.57735027
    sky = Y * 1.15470054
    bx, by, tx, ty = skx.floor(), sky.floor(), skx.fract(), sky.fract()
    tz = 1.0 - tx - ty
    s_ = b.math('LESS_THAN', tz, 0.0)
    s2 = s_ * 2.0 - 1.0
    w = b.xyz((tz * s2) * -1.0, s_ - ty * s2, s_ - tx * s2)
    verts = [(bx + s_, by + s_), (bx + s_, by + 1.0 - s_), (bx + 1.0 - s_, by + s_)]
    outs = {'W': w}
    for i, (vx, vy) in enumerate(verts, 1):
        cx = (vx + vy * 0.5) * 0.28867513
        cy = vy * 0.8660254 * 0.28867513
        hn = b.node('ShaderNodeTexWhiteNoise', {'Vector': b.xyz(vx, vy, 17.0)}, {'noise_dimensions': '3D'})
        hx, hy, hz = b.rgb_sep(b.out(hn, 'Color'))
        ang = (hz - 0.5) * TAU * I('Rot')
        sc = (hx - 0.5) * I('ScaleJit') + 1.0
        rel = b.xyz(x - cx, y - cy, 0.0)
        rot = b.node('ShaderNodeVectorRotate', {'Vector': rel, 'Angle': ang}, {'rotation_type': 'Z_AXIS'})
        st = b.cadd(b.cmul(b.out(rot, 'Vector'), sc), b.xyz((hx - 0.5) * I('Jit') + 0.5, (hy - 0.5) * I('Jit') + 0.5, 0.0))
        outs[f'ST{i}'], outs[f'A{i}'], outs[f'SC{i}'] = st, ang, sc
    b.node('NodeGroupOutput', outs)
    return ng


def build_deriv(B, new_group, sock):
    """KZ_Deriv: nh colour -> height derivative (x, y, 0) of the tangent normal (kit kzDeriv)."""
    ng = new_group('KZ_Deriv')
    sock(ng, 'Color', 'INPUT', 'c', (0.5, 0.5, 1.0))
    sock(ng, 'D', 'OUTPUT', 'v')
    b = B(ng)
    gi = b.node('NodeGroupInput')
    r, g, _ = b.rgb_sep(b.out(gi, 'Color'))
    mx, my = r * 2.0 - 1.0, g * 2.0 - 1.0
    mz = (1.0 - mx * mx - my * my).max(0.0).sqrt().max(0.06)
    b.node('NodeGroupOutput', {'D': b.xyz(mx * -1.0 / mz, my * -1.0 / mz, 0.0)})
    return ng


class Kit:
    """Builds the kit sampling network for one KZM group (b = DSL builder of that group)."""

    def __init__(self, b, cfg, imgs, imgs2=None):
        import bpy
        self.bpy = bpy
        self.b, self.cfg, self.imgs, self.imgs2 = b, cfg, imgs, imgs2

    def img(self, im, vec, label):
        return self.b.node('ShaderNodeTexImage', {'Vector': vec}, {'image': im, 'interpolation': 'Linear',
                                                                   'extension': 'REPEAT'}, label=label)

    def tap(self, imgs, st):
        b = self.b
        nb = self.img(imgs['base'], st, 'base')
        nn = self.img(imgs['nh'], st, 'nh')
        dg = b.node('ShaderNodeGroup', {}, {'node_tree': self.bpy.data.node_groups['KZ_Deriv']})
        b.set_in(dg, 'Color', b.out(nn, 'Color'))
        _, _, hh = b.rgb_sep(b.out(nn, 'Color'))
        return dict(base=b.out(nb, 'Color'), film=b.out(nn, 'Alpha'), h=hh, d=b.out(dg, 'D'))

    def mix3(self, taps, W):
        """Blend dicts of sockets by weight sockets W (3 floats)."""
        b = self.b
        o = {}
        for k in ('base', 'd'):
            acc = b.cmul(taps[0][k], W[0])
            for t, w in zip(taps[1:], W[1:]):
                acc = b.cadd(acc, b.cmul(t[k], w))
            o[k] = acc
        for k in ('film', 'h'):
            o[k] = taps[0][k] * W[0] + taps[1][k] * W[1] + taps[2][k] * W[2]
        return o

    def mix2(self, A, Bt, t):
        b = self.b
        return dict(base=b.mixc(t, A['base'], Bt['base']), d=b.mixc(t, A['d'], Bt['d']),
                    film=b.mixf(t, A['film'], Bt['film']), h=b.mixf(t, A['h'], Bt['h']))

    def sample(self, imgs, t, hex_on):
        """Plain (1 tap) or hex (3 taps) sampling at tile coords t (vector)."""
        b = self.b
        if not hex_on:
            return self.tap(imgs, t)
        hg = b.node('ShaderNodeGroup', {}, {'node_tree': self.bpy.data.node_groups['KZ_HexGrid']})
        b.set_in(hg, 'S', t)
        b.set_in(hg, 'Rot', float(self.cfg.get('rot', 1.0)))
        taps, Ws = [], []
        wx, wy, wz = b.sep(b.out(hg, 'W'))
        for i, w in zip((1, 2, 3), (wx, wy, wz)):
            tp = self.tap(imgs, b.out(hg, f'ST{i}'))
            rot = b.node('ShaderNodeVectorRotate', {'Vector': tp['d'], 'Angle': b.out(hg, f'A{i}')},
                         {'rotation_type': 'Z_AXIS', 'invert': True})
            tp['d'] = b.cmul(b.out(rot, 'Vector'), b.out(hg, f'SC{i}'))
            w2 = w * w
            w7 = w2 * w2 * w2 * w
            Ws.append(w7 * (tp['h'] * 0.6 + 0.4))
            taps.append(tp)
        k = 1.0 / max(1.0 - float(self.cfg.get('gainR', 0.7)), 0.05) ** 0.5   # contrast gain on weights
        Ws = [w ** k for w in Ws]
        tot = Ws[0] + Ws[1] + Ws[2] + 1e-6
        return self.mix3(taps, [w / tot for w in Ws])

    def layer2(self, T, t, hex_on, wp):
        """Second plate height-blended by a ~6-7 m world noise (kit KZ_LAYER2)."""
        b = self.b
        lay = self.cfg.get('layer') or {}
        if not self.imgs2 or not lay.get('amount'):
            return T
        n = b.node('ShaderNodeTexNoise', {'Vector': b.cmul(wp, 1.0 / lay.get('sizeM', 6.0)), 'Scale': 1.0,
                                          'Detail': 1.0}, {'noise_dimensions': '3D'})
        lt = ((b.out(n, 'Fac') - 0.5) * 2.0 * 0.8 + 0.5 + (T['h'] - 0.5) * 0.5).smooth(0.35, 0.65) * lay['amount']
        T2 = self.sample(self.imgs2, b.cadd(b.cmul(t, 0.93), (0.21, 0.21, 0.0)), hex_on)
        lt = ((T2['h'] - T['h']) * 0.5 + lt - 0.5).smooth(-0.12, 0.12)
        return self.mix2(T, T2, lt)


def build_kzm_kit(m, cfg, imgs, imgs2, H):
    """KZM_<id> for a kit material.  H = dict of build_library helpers (B, new_group, sock, ...)."""
    import bpy
    B, new_group, sock = H['B'], H['new_group'], H['sock']
    ng = new_group('KZM_' + m['id'])
    H['settings_iface'](ng, m)
    sock(ng, 'Shader', 'OUTPUT', 's')
    sock(ng, 'Volume', 'OUTPUT', 's')
    b = B(ng)
    gi = b.node('NodeGroupInput')
    I = lambda n: b.out(gi, n)  # noqa: E731
    kit = Kit(b, cfg, imgs, imgs2)
    geo = b.node('ShaderNodeNewGeometry')
    N, P = b.out(geo, 'Normal'), b.out(geo, 'Position')
    tc = b.node('ShaderNodeTexCoord')
    UV = b.out(tc, 'UV')
    tileM = I('scale')
    tech = cfg.get('tech')
    proj = cfg.get('proj', 'uv')
    hex_on = tech in ('antitile', 'hybrid')
    emis_extra = None
    joint = None
    board_rnd = None
    if tech == 'boards':
        bd = cfg['boards']
        u, v, _ = b.sep(UV)
        Wb, nB, mg = bd['widthM'], float(bd['n']), bd.get('margin', 0.02)
        j = (v / Wb).floor()
        a = (v / Wb).fract()
        hj = b.node('ShaderNodeTexWhiteNoise', {'Vector': b.xyz(j, 5.0, 0.0)}, {'noise_dimensions': '3D'})
        hjx, _, _ = b.rgb_sep(b.out(hj, 'Color'))
        along = u / tileM + hjx * 7.0
        seg, fa = along.floor(), along.fract()
        hs = b.node('ShaderNodeTexWhiteNoise', {'Vector': b.xyz(j, seg, 11.0)}, {'noise_dimensions': '3D'})
        hsx, hsy, _ = b.rgb_sep(b.out(hs, 'Color'))
        bidx = (hsx * nB).floor()
        fl = b.math('GREATER_THAN', hsy, 0.5)
        across = b.mixf(fl, a, 1.0 - a)
        st = b.xyz((bidx + mg + across * (1.0 - 2.0 * mg)) / nB, along, 0.0)
        T = kit.tap(imgs, st)
        dx, dy, _ = b.sep(T['d'])
        T['d'] = b.xyz(dy, dx * (1.0 - fl * 2.0), 0.0)
        joint = 1.0 - fa.min(1.0 - fa).smooth(0.0, 0.004)
        board_rnd = hsx
        proj = 'uv'
    elif proj == 'uv':
        t = b.vmath('DIVIDE', UV, b.xyz(tileM, tileM, 1.0))
        T = kit.sample(imgs, t, hex_on)
        T = kit.layer2(T, t, hex_on, P)
    else:
        nx, ny, nz = b.sep(N)
        axes = [((1, 0, 0), (0, 1, 0), nz)] if proj == 'floor' else \
               [((1, 0, 0), (0, 1, 0), nz), ((0, 1, 0), (0, 0, 1), nx), ((1, 0, 0), (0, 0, 1), ny)]
        Ts, Wts = [], []
        for k, (ea, eb, nc) in enumerate(axes):
            pa = b.vmath('DOT_PRODUCT', P, ea, out='Value')
            pb = b.vmath('DOT_PRODUCT', P, eb, out='Value')
            t = b.xyz(pa / tileM + 0.37 * k, pb / tileM + 0.21 * k, 0.0)
            Tp = kit.sample(imgs, t, hex_on)
            if k == 0 or proj != 'floor':
                Tp = kit.layer2(Tp, t, hex_on, P)
            dxp, dyp, _ = b.sep(Tp['d'])
            Tp['g'] = b.cadd(b.cmul(ea, dxp), b.cmul(eb, dyp))
            w = (nc.abs() ** 4.0) if proj != 'floor' else 1.0          # smooth, never all zero (was clamp((|n|-0.577)/0.42))
            if proj != 'floor':
                w = w * ((Tp['h'] + 0.25) * 0.7 + 0.3)
            Ts.append(Tp)
            Wts.append(w)
        if len(Ts) == 1:
            T = Ts[0]
            g = T['g']
        else:
            tot = Wts[0] + Wts[1] + Wts[2] + 1e-5
            Wn = [w / tot for w in Wts]
            T = kit.mix3(Ts, Wn)
            g = b.cadd(b.cadd(b.cmul(Ts[0]['g'], Wn[0]), b.cmul(Ts[1]['g'], Wn[1])), b.cmul(Ts[2]['g'], Wn[2]))
    if proj == 'uv':
        tg = b.node('ShaderNodeTangent', {}, {'direction_type': 'UV_MAP'})
        Tt = b.out(tg, 'Tangent')
        Bt = b.vmath('CROSS_PRODUCT', N, Tt)
        dx, dy, _ = b.sep(T['d'])
        g = b.cadd(b.cmul(Tt, dx), b.cmul(Bt, dy))

    gain = float(cfg.get('gain', 1.0))
    albedo = b.cmul(T['base'], gain)
    h, film = T['h'], T['film']
    ao = b.mixf(0.6, 1.0, h.smooth(0.0, 0.55) * 0.5 + 0.5)
    r0, r1 = cfg.get('rough', [0.7, 0.1])
    rough = b.mixf(film, r0, r1)
    if joint is not None:
        albedo = b.cmul(albedo, ((board_rnd - 0.5) * 0.22 + 1.0) * (1.0 - joint * 0.7))
        ao = ao * (1.0 - joint * 0.5)

    # ---------------- macro (world space, Blender Z up) ----------------
    mac = cfg.get('macro') or {}
    s1, s2 = mac.get('size1', 7.0), mac.get('size2', 23.0)

    def noise(vec, offs):
        n = b.node('ShaderNodeTexNoise', {'Vector': b.cadd(vec, (offs, offs * 0.7, offs * 1.3)), 'Scale': 1.0,
                                          'Detail': 0.0, 'Roughness': 0.5}, {'noise_dimensions': '3D'})
        return ((b.out(n, 'Fac') - 0.5) * 2.2 + 0.5).clamp()
    na = noise(b.cmul(P, 1.0 / s1), 3.1)
    nb = noise(b.cmul(P, 1.0 / s2), 11.7)
    nc_ = noise(b.cmul(P, 1.0 / (s1 * 0.37)), 5.3)
    nd = noise(b.cmul(P, 1.0 / (s1 * 0.6)), -7.1)
    bright = na * 0.6 + nc_ * 0.4
    wetp = na * 0.5 + nd * 0.5
    _, _, nzz = b.sep(N)
    q = b.cmul(P, b.xyz(1.0 / 0.09, 1.0 / 0.09, 1.0 / 1.6))
    streak = noise(q, 0.0).smooth(0.62, 0.85) * noise(b.cmul(P, 1.0 / 2.5), 1.3).smooth(0.35, 0.7) * \
        (1.0 - nzz.abs().smooth(0.4, 0.8)) * float(mac.get('streak', 0.0))

    # ---------------- hybrid overlays ----------------
    proc = cfg.get('proc') if tech == 'hybrid' else None
    pA = cfg.get('procA', [1, 0.1, 0.02, 0])
    emis = None
    if proc == 'basalt':
        cd, cc = b.voronoi4((b.cmul(P, 1.0 / pA[2]), 0.0), scale=1.0, feature='F1', out=['Distance', 'Color'])
        cr, cg, cb = b.rgb_sep(cc)
        g = b.cadd(g, b.cmul(b.vmath('SUBTRACT', b.cmul(cc, 2.0), (1.0, 1.0, 1.0)), pA[3]))
        albedo = b.cmul(albedo, (cr - 0.5) * 0.25 + 1.0)
        rough = rough + (cg - 0.5) * 0.25
    elif proc == 'obsidian':
        cd, cc = b.voronoi4((b.cmul(P, 1.0 / pA[0]), 0.0), scale=1.0, feature='F1', out=['Distance', 'Color'])
        e = b.voronoi4((b.cmul(P, 1.0 / pA[0]), 0.0), scale=1.0, feature='DISTANCE_TO_EDGE')
        ridge = 1.0 - e.smooth(0.0, 0.0175)
        g = b.cadd(b.cmul(b.vmath('SUBTRACT', b.cmul(cc, 2.0), (1.0, 1.0, 1.0)), pA[1]), b.cmul(g, 0.15))
        rough = b.mixf(ridge.max(film * 0.5), r0, r1)
        albedo = b.cmul(albedo, ridge * 0.2 + 1.0)
        film = film * 0.0
    if (cfg.get('emissive') or {}).get('fromBase'):
        fb = float(cfg['emissive']['fromBase'])
        br, bg_, bb = b.rgb_sep(T['base'])
        hot = (br - bb * 1.4).smooth(0.08, 0.35) * br.smooth(0.05, 0.4)
        emis = b.cmul(b.cmul(T['base'], T['base']), hot * fb)
        albedo = b.cmul(albedo, 1.0 - hot * 0.8)
        breathe = noise(b.cmul(P, 0.9), 2.2).smooth(0.2, 0.8) * 1.1 + 0.45
        emis = b.cmul(emis, (bright.smooth(0.3, 0.7) * 1.5 + 0.25) * breathe)
        lm = cfg.get('lavaMask')
        if lm:
            big = noise(b.cmul(P, 1.0 / lm['sizeM']), 4.3).smooth(0.35, 0.65)
            fx, fz = lm['flow']
            flow = noise(b.cmul(P, b.xyz(1.0 / fx, 1.0 / fx, 1.0 / fz)), 8.1).smooth(0.4, 0.7)
            emis = b.cmul(emis, b.mixf(big * 0.6 + flow * 0.4, lm['low'], lm['high']))
        er, eg, eb2 = b.rgb_sep(emis)
        tt = ((er * 0.3 + eg * 0.6 + eb2 * 0.1) / fb * 4.0).clamp()
        bb = b.ramp(tt, [(0.0, (0.9, 0.07, 0.005)), (0.15, (0.9, 0.07, 0.005)), (0.55, (1.0, 0.33, 0.04)),
                         (0.6, (1.0, 0.33, 0.04)), (1.0, (1.0, 0.75, 0.38))])
        emis = b.cmul(bb, tt * tt * (tt * 3.0 + 1.0) * fb * 0.1)

    if emis is None and cfg.get('glow'):                 # even back-lit glow with only subtle fibre variation
        gw = cfg['glow']
        br, bg_, bb = b.rgb_sep(T['base'])
        lumb = br * 0.2126 + bg_ * 0.7152 + bb * 0.0722
        emis = b.cmul(tuple(gw['color']), (lumb - gw.get('mean', 0.55)) * gw.get('fibre', 0.25) + 1.0)
    if emis is None and m.get('emissive') and H.get('legacy_emis'):   # library emissive map
        le = H['legacy_emis'](m['id'])
        if le is not None:
            tcv = b.vmath('DIVIDE', UV, b.xyz(tileM, tileM, 1.0))
            emis = b.out(kit.img(le, tcv, 'emis (library)'), 'Color')      # KZ_Core applies EmitStrength
    core = b.node('ShaderNodeGroup', {}, {'node_tree': bpy.data.node_groups['KZ_Core']}, name='Core')
    for k in H['SETTINGS']:
        b.set_in(core, k, I(k))
    consts = H['core_consts'](m)
    consts.update(MacroAmount=float(mac.get('amount', 0.0)), MacroHue=tuple(mac.get('hue', [0.9, 1.0, 1.12])),
                  UseGrad=1.0, Porosity=float(cfg.get('porosity', consts['Porosity'])))
    if emis is not None:
        consts.update(EmitStrength=1.0, EmitMapScale=1.0, EmitMacro=0.0)
    H['set_inputs'](core, consts)
    for k, v in (('Albedo', albedo), ('AO', ao), ('Roughness', rough.clamp()), ('Metallic', float(cfg.get('metal', 0.0))),
                 ('Height', h), ('WetMask', film), ('Mask', 0.0 if m.get('transparent') else 1.0), ('Grad', g),
                 ('Macro', b.rgb(bright, nb, wetp)), ('MacroA', streak)):
        b.set_in(core, k, v)
    if emis is not None:
        b.set_in(core, 'Emission', emis)
    b.node('NodeGroupOutput', {'Shader': b.out(core, 'Shader'), 'Volume': b.out(core, 'Volume')})
    return ng


LAVA_PATCH_FROM = """      emis *= 0.45 + 1.1 * smoothstep(0.2, 0.8, kzNoised2(uvm * 0.9 - kz_procB.xy * kz_time * 4.0 + vec2(0.0, kz_time * 0.03)).x);
"""
LAVA_PATCH_TO = LAVA_PATCH_FROM + """      // library patch (tools/matlib/kzkit.py): ~20 m hot/cool mask + downhill flow bands (three: Y up),
      // so a lava field is not uniformly busy at 40 m (shader-kit README open problem)
      emis *= mix(0.2, 1.35, smoothstep(0.35, 0.65, kzNoised3(wp / 20.0 + 4.3).x) * 0.6
                           + smoothstep(0.4, 0.7, kzNoised3(wp * vec3(1.0 / 3.0, 1.0 / 25.0, 1.0 / 3.0) + 8.1).x) * 0.4);
      // graded seams (review r2): temperature from seam intensity -> red edge, orange body, yellow-white core
      emis = kzBlackbody(KZ_SAT(dot(emis, vec3(0.3, 0.6, 0.1)) / max(kz_emisFromBase * kz_emisLevel, 1e-3) * 4.0))
             * kz_emisFromBase * kz_emisLevel * 0.1 * kz_tint;
"""


def write_kzshader(dst):
    src = open(os.path.join(KIT_DIR, 'kzshader.js')).read()
    if LAVA_PATCH_FROM in src:
        src = src.replace(LAVA_PATCH_FROM, LAVA_PATCH_TO, 1)
    else:
        print('[kzkit] WARNING: lava patch anchor not found; kzshader.js copied unpatched')
    head = ('// Canonical copy of the Kazan-yu shader kit for the material library (from\n'
            '// 3d/research/shaders/kzshader.js; patched by tools/matlib/kzkit.py: lava large-scale mask).\n')
    with open(dst, 'w') as f:
        f.write(head + src)


# ----------------------------------------------------------------------------- CC0 scans
# Owner-approved CC0 scans (research in .scratch/cc0mat, licences checked there).  Each becomes a
# kit "plate" set pl_<asset>_{base,nh}.png at our KTX2 size; the kit layers sit on top.
CC0_DIR = os.path.join(ROOT, '.scratch', 'cc0mat')
PH_LIC = 'CC0 1.0 (Poly Haven, https://polyhaven.com/license)'
ACG_LIC = 'CC0 1.0 (ambientCG, https://docs.ambientcg.com/license)'
SCANS = {
    # material: (folder, asset, kind, size_m, url, res, fix, kit overrides)
    'basalt_wet': ('basalt_wet/polyhaven_dark_rock_02', 'dark_rock_02', 'ph', 2.0,
                   'https://polyhaven.com/a/dark_rock_02', 1024, dict(desat=0.0, clip_hi=2.0, target=[0.02, 0.02, 0.021], film=0.12, film_break=0.6),
                   dict(gain=1.0, plate2=None, layer=None, rough=[0.5, 0.08],
                        macro=dict(amount=1, size1=6, size2=21, hue=[0.97, 1.0, 1.03], streak=0.3))),
    'basalt_dry': ('basalt_dry/polyhaven_dark_rock', 'dark_rock', 'ph', 2.42, 'https://polyhaven.com/a/dark_rock',
                   1024, dict(desat=0.0, clip_hi=1.05, target=[0.05, 0.05, 0.052]), dict(gain=1.0, plate2=None, layer=None, rough=[0.88, 0.72],
                   macro=dict(amount=1, size1=6, size2=21, hue=[0.98, 1.0, 1.02], streak=0.6))),
    'paving': ('paving/polyhaven_slab_tiles', 'slab_tiles', 'ph', 2.37, 'https://polyhaven.com/a/slab_tiles', 1024,
               dict(desat=0.25, cool=True, joints=0.9, gain=0.55, film=0.3), dict(tech='plain+macro', gain=1.0, rough=[0.25, 0.04])),
    'tatami': ('tatami/polyhaven_tatami_mat', 'tatami_mat', 'ph', 1.8, 'https://polyhaven.com/a/tatami_mat', 1024,
               dict(), dict(tech='plain+macro')),
}
SCANS_B = {
    'black_sand': ('black_sand/polyhaven_sand_02', 'sand_02', 'ph', 2.14, 'https://polyhaven.com/a/sand_02', 1024,
                   dict(desat=0.05, gain=0.25, cool=True), dict(gain=1.0)),
    'ash_clay': ('ash_clay/polyhaven_clay_plaster', 'clay_plaster', 'ph', 2.0, 'https://polyhaven.com/a/clay_plaster',
                 512, dict(desat=0.3, tint=[1.0, 0.97, 0.92], clip_lo=0.7), dict(tech='plain+macro', plateM=2.0)),
    'cave_rock': ('cave_rock/polyhaven_rock_face_04', 'rock_face_04', 'ph', 2.0, 'https://polyhaven.com/a/rock_face_04',
                  1024, dict(desat=0.6, gain=0.45, cool=True), dict(gain=1.0, plate2=None, layer=None)),
    'stepping_stone': ('stepping_stone/polyhaven_seaside_rock', 'seaside_rock', 'ph', 2.0,
                       'https://polyhaven.com/a/seaside_rock', 1024, dict(desat=0.0, clip_hi=1.15, target=[0.02, 0.02, 0.021], film=0.45),
                       dict(rough=[0.4, 0.05])),
    'hinoki': ('hinoki/polyhaven_japanese_cedar_planks', 'japanese_cedar_planks', 'ph', 1.13,
               'https://polyhaven.com/a/japanese_cedar_planks', 1024, dict(desat=0.7, gain=0.8),
               dict(tech='plain+macro', boards=None)),
    'noren': ('noren/polyhaven_rough_linen', 'rough_linen', 'ph', 0.27, 'https://polyhaven.com/a/rough_linen', 512,
              dict(neutral=0.7, weave=2.0), dict(plateM=0.27)),
    'linen': ('noren/polyhaven_rough_linen', 'rough_linen', 'ph', 0.27, 'https://polyhaven.com/a/rough_linen', 512,
              dict(neutral=0.7, weave=1.0, flatten=0.4, **{'as': 'linen_offwhite'}),
              dict(plateM=0.27, family='cloth', tech='plain+macro', proj='uv', rot=0, rough=[0.9, 0.85], porosity=0.4,
                   macro=dict(amount=0.4, size1=1.5, size2=4, hue=[1, 1, 1], streak=0))),
    'moss': ('moss/ambientcg_Moss002', 'Moss002', 'acg1k', 1.0, 'https://ambientcg.com/a/Moss002', 512,
             dict(desat=0.9, gain=0.85),
             dict(family='plant', tech='antitile', proj='uv', rot=1, rough=[0.85, 0.6], porosity=0.8,
                  macro=dict(amount=0.7, size1=1.5, size2=5, hue=[1.08, 1.0, 0.85], streak=0))),
    'bark': ('bark/polyhaven_pine_bark', 'pine_bark', 'ph', 2.0, 'https://polyhaven.com/a/pine_bark', 1024,
             dict(desat=0.45, target=[0.05, 0.036, 0.026]),
             dict(family='wood', tech='plain+macro', proj='uv', rot=0, rough=[0.85, 0.6], porosity=0.5,
                  macro=dict(amount=0.6, size1=3, size2=9, hue=[1.05, 1.0, 0.92], streak=0.3))),
    'iron': ('iron/polyhaven_metal_plate_02', 'metal_plate_02', 'ph', 2.0, 'https://polyhaven.com/a/metal_plate_02',
             512, dict(iron=True), dict(metal=0.9, rough=[0.45, 0.3])),
    'bamboo': ('bamboo/ambientcg_Bamboo001B', 'Bamboo001B', 'acg', 1.3, 'https://ambientcg.com/a/Bamboo001B', 1024,
               dict(desat=0.35, tint=[0.92, 0.68, 0.42], gain=0.7), dict(tech='plain+macro', proj='uv', rot=0, rough=[0.4, 0.25], porosity=0.2,
                            macro=dict(amount=0.5, size1=2, size2=6, hue=[1.05, 1.0, 0.92], streak=0))),
    'rope': ('rope/ambientcg_Rope001', 'Rope001', 'acg', 0.5, 'https://ambientcg.com/a/Rope001', 512,
             dict(), dict(tech='plain+macro', proj='uv', rot=0, rough=[0.85, 0.75], porosity=0.3,
                          macro=dict(amount=0.4, size1=1.5, size2=4, hue=[1.0, 1.0, 1.0], streak=0))),
}
SCAN_FILES = {'ph': dict(base='{a}_diff_2k.jpg', nor='{a}_nor_gl_2k.jpg', disp='{a}_disp_2k.png', rough='{a}_rough_2k.jpg'),
              'acg1k': dict(base='{a}_1K-JPG_Color.jpg', nor='{a}_1K-JPG_NormalGL.jpg', disp='{a}_1K-JPG_Displacement.jpg',
                            rough='{a}_1K-JPG_Roughness.jpg'),
              'acg': dict(base='{a}_2K-JPG_Color.jpg', nor='{a}_2K-JPG_NormalGL.jpg', disp='{a}_2K-JPG_Displacement.jpg',
                          rough='{a}_2K-JPG_Roughness.jpg')}


def active_scans(which):
    out = {}
    if 'a' in which:
        out.update(SCANS)
    if 'b' in which:
        out.update(SCANS_B)
    return out


def _load_scaled(path, res):
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    if img.size[0] != res:
        img.scale(res, res)
    a = np.empty(res * res * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(res, res, 4).astype(np.float64)


def recolour(lin, h, fix):
    """Round-4 parameter/mask pass: neutralise, darken, clip veins, fill pits, cavity masks."""
    L = _lum(lin)[..., None]
    if 'clip_hi' in fix:                                 # pale veins / speckle -> soft-clip
        med = float(np.median(L)); knee = med * fix['clip_hi']
        Lc = np.where(L > knee, knee + (L - knee) * 0.15, L)
        lin = lin * (Lc / np.maximum(L, 1e-6)); L = Lc
    if 'clip_lo' in fix:                                 # dark pits (star lattice) -> lifted
        med = float(np.median(L)); knee = med * fix['clip_lo']
        Lc = np.where(L < knee, knee - (knee - L) * 0.2, L)
        lin = lin * (Lc / np.maximum(L, 1e-6)); L = Lc
    if 'desat' in fix:
        lin = L + (lin - L) * fix['desat']
    if fix.get('cool'):
        lin = lin * np.array([0.95, 0.99, 1.08])
    if 'tint' in fix:
        lin = lin * np.array(fix['tint'])
    if 'gain' in fix:
        lin = lin * fix['gain']
    if 'target' in fix:                                  # scale per channel to a target mean colour (linear)
        lin = lin / np.maximum(lin.reshape(-1, 3).mean(0), 1e-6) * np.array(fix['target'])
    if 'flatten' in fix:                                 # reduce albedo contrast (fibre/fur, mottling)
        m = lin.reshape(-1, 3).mean(0)
        lin = m + (lin - m) * fix['flatten']
    if fix.get('crust'):                                 # lava_flow: mostly black crust, molten only in rivers
        Ln = _lum(lin) / max(float(np.percentile(_lum(lin), 99)), 1e-6)
        k = np.clip((Ln - fix['crust']) / (1 - fix['crust']), 0, 1) ** 1.5
        lin = lin * k[..., None] + np.array([0.012, 0.010, 0.009]) * (1 - k[..., None])
    return lin


def prepare_scan(mid, spec, out_dir, write_png):
    folder, asset, kind, size_m, url, res, fix, _ = spec
    d = os.path.join(CC0_DIR, folder)
    out_name = fix.get('as', asset)
    f = {k: os.path.join(d, v.format(a=asset)) for k, v in SCAN_FILES[kind].items()}
    base = _load_scaled(f['base'], res)[..., :3]
    nor = _load_scaled(f['nor'], res)
    disp = _load_scaled(f['disp'], res)[..., 0]
    rough = _load_scaled(f['rough'], res)[..., 0]
    h = (disp - disp.min()) / max(disp.max() - disp.min(), 1e-6)
    lin = recolour(_s2l(base), h[..., None], fix)
    L = _lum(lin)[..., None]
    if fix.get('joints'):                                # darken/cool mortar joints (warm, low pixels)
        s0 = _s2l(base)
        warm = (s0[..., 0] - s0[..., 2]) / np.maximum(_lum(s0), 1e-4)
        jm = np.clip(np.maximum((warm - np.percentile(warm, 80)) / 0.25, (0.15 - h) / 0.1), 0, 1)[..., None]
        lin = lin * (1 - jm * fix['joints'] * 2) + jm * fix['joints'] * 2 * np.array([0.012, 0.012, 0.014])
    if fix.get('neutral'):                               # dye-neutral weave (mean = fix value), colour from tint
        Ln = _lum(lin)[..., None] / max(float(_lum(lin).mean()), 1e-6)
        lin = np.ones(3) * fix['neutral'] * np.clip(Ln, 0.05, 3.0) ** fix.get('weave', 1.6)
    if fix.get('iron'):                                  # black oxide, rust only in the lowest pits
        rust = np.clip((0.3 - h) / 0.15, 0, 1)[..., None]
        ox = np.array([0.036, 0.034, 0.033]) * (0.8 + 0.4 * L / max(float(L.mean()), 1e-6))
        lin = lin * rust + ox * (1 - rust)
    film = np.clip((1.0 - h) * 0.7 + (1.0 - rough) * 0.5 - 0.35 + fix.get('film', 0.0), 0, 1)
    if fix.get('film_break'):                            # broken wet film: patches dry out at 2-15 cm (tileable)
        rng = np.random.default_rng(11)
        import plates as P
        nz = sum(P.blur(rng.random(h.shape), sg, wrap=True) * w for sg, w in ((2.0, 0.3), (6.0, 0.4), (14.0, 0.3)))
        nz = (nz - nz.mean()) / (nz.std() + 1e-6)
        film = np.clip(film * np.clip(0.5 + nz * fix['film_break'], 0, 1.2), 0, 1)
    nh = np.dstack([nor[..., 0], nor[..., 1], h, film])
    pb = os.path.join(out_dir, f'pl_{out_name}_base.png')
    pn = os.path.join(out_dir, f'pl_{out_name}_nh.png')
    write_png(pb, np.clip(np.rint(_l2s(lin) * 255), 0, 255).astype(np.uint8))
    write_png(pn, np.clip(np.rint(nh * 255), 0, 255).astype(np.uint8))
    return out_name, res, dict(url=url, licence=PH_LIC if kind == 'ph' else ACG_LIC, size_m=size_m,
                            files=[os.path.relpath(f[k], ROOT) for k in ('base', 'nor', 'disp', 'rough')])


def apply_scans(kit, which):
    """Point kit entries at the scan plates.  Returns {material: scan info}."""
    info = {}
    for mid, spec in active_scans(which).items():
        asset, size_m, over = spec[6].get('as', spec[1]), spec[3], spec[7]
        base = dict(kit.get(mid) or {})
        if not base:
            base = dict(family='misc', tech='plain+macro', proj='uv', rot=0, rough=[0.7, 0.3], porosity=0.4,
                        macro=dict(amount=0.5, size1=3, size2=9, hue=[1, 1, 1], streak=0))
        base.update(plate=asset, plateM=over.get('plateM', size_m))
        for k, v in over.items():
            if v is None:
                base.pop(k, None)
            else:
                base[k] = v
        base['scan'] = dict(asset=asset, url=spec[4], licence=PH_LIC if spec[2] == 'ph' else ACG_LIC, res=spec[5])
        kit[mid] = base
        info[mid] = spec
    return info


# ----------------------------------------------------------------------------- Codex seamless tiles
# Owner-approved Codex tiles (refs/gen/tile-*.png, prompts/list9.tsv): one seamless square per
# material, covering `cover_m`.  De-lit, height from frequency-separated luminance, normal from the
# float height (no 8-bit banding), wet-film mask from residual gloss + hollows.
TILES = {
    # material: (tile, cover_m, res, fix, kit overrides)
    'rimstone': ('tile-rimstone', 3.0, 1024, dict(desat=0.2, tint=[1.0, 0.98, 0.93], gain=1.1), dict()),
    'sinter': ('tile-sinter', 2.0, 512, dict(desat=0.55), dict()),
    'lava': ('tile-lava-crust', 6.0, 1024, dict(), dict()),
    'lava_flow': ('tile-lava-flow', 6.0, 1024, dict(crust=0.55), dict(emissive=dict(color=[0, 0, 0], fromBase=0.8))),
    'glacier_ice': ('tile-glacier-ice', 4.5, 512, dict(desat=0.7), dict(tech='antitile')),
    # obsidian, lacquer_dark: tiles tested, current versions won (tile obsidian too vein-bright, lacquer tile has orange rot blotches)
    'washi': ('tile-washi', 1.0, 512, dict(flatten=0.45), dict()),
    'washi_backlit': ('tile-washi', 1.0, 512, dict(flatten=0.3), dict()),
    'bronze': ('tile-bronze', 3.0, 512, dict(desat=0.35, flatten=0.3, target=[0.042, 0.023, 0.012]), dict(tech='antitile', metal=1.0, rough=[0.4, 0.34],
               macro=dict(amount=0.8, size1=2.5, size2=7, hue=[0.9, 1.05, 1.0], streak=0.4))),
    'cave_rock': ('tile-cave-rock', 4.0, 1024, dict(desat=0.12, gain=0.45, cool=True, film=0.3, clip_hi=1.25), dict(plate2=None, layer=None)),
}


def tile_path(name):
    return os.path.join(ROOT, 'refs', 'gen', name + '.png')


def prepare_tile(mid, spec, out_dir, write_png):
    import plates as P
    import kzimg
    name, cover, res, fix, _ = spec
    a = _load_scaled(tile_path(name), res)[::-1, :, :3]          # top-first like plates
    lin = P.srgb_to_lin(np.clip(a, 0, 1))
    alb, gloss = P.delight(lin, spec_thresh=2.2, grad_strength=0.6, keep_spec=mid.startswith('lava'))
    px_m = cover / res
    h = P.height_from(alb, px_m, bands=(0.004 * cover, 0.02 * cover, 0.08 * cover), weights=(0.3, 0.45, 0.25),
                      dark_deep=0.2)
    n = kzimg.normals_from_height(h, 0.012 * cover, cover, cover)
    film = np.clip(P.blur(gloss, 2.0, wrap=True) * 1.5 + (1 - h) * 0.4 - 0.2 + fix.get('film', 0.0), 0, 1)
    out_alb = recolour(alb if not mid.startswith('lava') else lin, h[..., None], fix)           # lava keeps its glow in base (kit fromBase)
    nh = np.dstack([n[..., 0] * 0.5 + 0.5, n[..., 1] * 0.5 + 0.5, h, film])
    seam = kzimg.seam_ratio(np.clip(lin, 0, 1))
    pb = os.path.join(out_dir, f'pl_{name.replace("-", "_")}_base.png')
    pn = os.path.join(out_dir, f'pl_{name.replace("-", "_")}_nh.png')
    write_png(pb, np.clip(np.rint(_l2s(np.clip(out_alb, 0, 1)) * 255), 0, 255).astype(np.uint8)[::-1])
    write_png(pn, np.clip(np.rint(nh * 255), 0, 255).astype(np.uint8)[::-1])
    return name.replace('-', '_'), res, seam


def apply_tiles(kit, only=None):
    info = {}
    for mid, spec in TILES.items():
        if only is not None and mid not in only:
            continue
        if not os.path.exists(tile_path(spec[0])):
            continue
        asset = spec[0].replace('-', '_')
        base = dict(kit.get(mid) or {})
        base.update(plate=asset, plateM=spec[1])
        base.pop('scan', None)
        for k, v in spec[4].items():
            if v is None:
                base.pop(k, None)
            else:
                base[k] = v
        base['tile'] = dict(file=f'refs/gen/{spec[0]}.png', cover_m=spec[1],
                            licence='self-made Codex tile for this project (owner-approved), prompts/list9.tsv')
        kit[mid] = base
        info[mid] = spec
    return info


def gen_pine_needles(W, H, seed=7):
    """Self-made alpha needle-tuft card (pine): radiating needle clusters on twigs, dark green, alpha-tested.
    Returns bake_set-style px dict (rows bottom-first)."""
    rng = np.random.default_rng(seed)
    alb = np.zeros((H, W, 3)); a = np.zeros((H, W)); hgt = np.zeros((H, W))
    yy, xx = np.mgrid[0:H, 0:W]
    def line(x0, y0, x1, y1, w, col, hv):
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.5) + 2
        for t in np.linspace(0, 1, n):
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            xi, yi = int(x) % W, int(y) % H
            r = int(np.ceil(w))
            ys, xs = slice(max(yi - r, 0), min(yi + r + 1, H)), slice(max(xi - r, 0), min(xi + r + 1, W))
            d = np.hypot(xx[ys, xs] - x, yy[ys, xs] - y)
            m = np.clip(w - d + 0.5, 0, 1) * (1 - 0.25 * t)
            sel = m > a[ys, xs]
            a[ys, xs] = np.maximum(a[ys, xs], m)
            for c in range(3):
                alb[ys, xs, c] = np.where(sel, col[c] * (0.8 + 0.4 * t), alb[ys, xs, c])
            hgt[ys, xs] = np.maximum(hgt[ys, xs], m * hv)
    for k in range(14):                                       # twigs with needle tufts
        x0, y0 = rng.uniform(0.1, 0.9) * W, rng.uniform(0.05, 0.3) * H
        ang = rng.uniform(0, 2 * np.pi)
        L = rng.uniform(0.45, 0.8) * H
        x1, y1 = x0 + np.cos(ang) * L, y0 + np.sin(ang) * L
        line(x0, y0, x1, y1, 2.2, (0.06, 0.035, 0.02), 0.6)
        for t in np.linspace(0.05, 1.0, 26):
            cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            g = rng.uniform(0.6, 1.0)
            col = np.array([0.09, 0.12, 0.026]) * g + np.array([0.015, 0.012, 0.0]) * rng.uniform()
            for side in (-1, 1):
                for j in range(8):
                    na = ang + side * rng.uniform(0.35, 1.1)
                    nl = rng.uniform(0.07, 0.13) * H
                    line(cx, cy, cx + np.cos(na) * nl, cy + np.sin(na) * nl, 1.15, col, 1.0)
    one = np.ones((H, W))
    rough = 0.55 - 0.15 * hgt
    px = {'albedo': np.dstack([alb[::-1], one]), 'orm': np.dstack([one * (0.75 + 0.25 * a[::-1]), rough[::-1], 0 * one, one]),
          'hmw': np.dstack([hgt[::-1], a[::-1], 0 * one, one])}
    return px


def _card_canvas(W, H):
    return np.zeros((H, W, 3)), np.zeros((H, W)), np.zeros((H, W)), np.mgrid[0:H, 0:W]


def _stamp(alb, a, hgt, yy, xx, x, y, r, col, hv, ell=(1.0, 1.0, 0.0)):
    """Soft ellipse stamp (wrapping)."""
    H, W = a.shape
    sx, sy, ang = ell
    R_ = int(np.ceil(r * max(sx, sy))) + 2
    xi, yi = int(x), int(y)
    ys = np.arange(yi - R_, yi + R_ + 1) % H
    xs = np.arange(xi - R_, xi + R_ + 1) % W
    gy, gx = np.meshgrid(np.arange(yi - R_, yi + R_ + 1) - y, np.arange(xi - R_, xi + R_ + 1) - x, indexing='ij')
    c, s_ = np.cos(ang), np.sin(ang)
    u = (gx * c + gy * s_) / (r * sx)
    v = (-gx * s_ + gy * c) / (r * sy)
    d = np.sqrt(u * u + v * v)
    m = np.clip((1.0 - d) * r * 0.6, 0, 1)
    sub = np.ix_(ys, xs)
    sel = m > a[sub]
    a[sub] = np.maximum(a[sub], m)
    for k in range(3):
        alb[..., k][sub] = np.where(sel, col[k] * (0.85 + 0.3 * (1 - d.clip(0, 1))), alb[..., k][sub])
    hgt[sub] = np.maximum(hgt[sub], m * hv * (1 - d.clip(0, 1)))


def _pack(alb, a, hgt):
    one = np.ones(a.shape)
    return {'albedo': np.dstack([alb[::-1], one]), 'orm': np.dstack([one * (0.8 + 0.2 * a[::-1]), 0.55 - 0.1 * hgt[::-1], 0 * one, one]),
            'hmw': np.dstack([hgt[::-1], a[::-1], 0 * one, one])}


def gen_fern(W, H, seed=5):
    """Self-made fern frond card: curved rachis with paired leaflets, ~#5a8a2a."""
    rng = np.random.default_rng(seed)
    alb, a, hgt, (yy, xx) = _card_canvas(W, H)
    for f in range(4):
        x0, y0 = rng.uniform(0.15, 0.85) * W, rng.uniform(0.85, 0.95) * H
        ang, curl = -np.pi / 2 + rng.uniform(-0.4, 0.4), rng.uniform(-0.6, 0.6)
        L = rng.uniform(0.6, 0.85) * H
        n = 34
        for i in range(n):
            t = i / n
            aa = ang + curl * t
            x = x0 + np.cos(aa) * L * t
            y = y0 + np.sin(aa) * L * t
            _stamp(alb, a, hgt, yy, xx, x, y, 2.5, (0.05, 0.10, 0.02), 0.5)
            ll = (1 - t) * 0.09 * H + 6
            for side in (-1, 1):
                la = aa + side * 1.35
                g = rng.uniform(0.8, 1.15)
                col = np.array([0.08, 0.36, 0.035]) * g
                _stamp(alb, a, hgt, yy, xx, x + np.cos(la) * ll * 0.5, y + np.sin(la) * ll * 0.5, ll * 0.5, col, 1.0,
                       ell=(1.0, 0.28, la))
    return _pack(alb, a, hgt)


def gen_blossom(W, H, seed=9):
    """Self-made cherry-blossom cluster card: 5-petal flowers ~#f2d4de with deeper pink centres."""
    rng = np.random.default_rng(seed)
    alb, a, hgt, (yy, xx) = _card_canvas(W, H)
    for c in range(9):
        cx, cy = rng.uniform(0.15, 0.85) * W, rng.uniform(0.15, 0.85) * H
        for f in range(rng.integers(4, 8)):
            fx, fy = cx + rng.normal(0, 0.06 * W), cy + rng.normal(0, 0.06 * H)
            r = rng.uniform(0.022, 0.032) * W
            rot = rng.uniform(0, 2 * np.pi)
            g = rng.uniform(0.9, 1.05)
            for p in range(5):
                pa = rot + p * 2 * np.pi / 5
                _stamp(alb, a, hgt, yy, xx, fx + np.cos(pa) * r * 0.7, fy + np.sin(pa) * r * 0.7, r * 0.62,
                       np.array([0.86, 0.62, 0.70]) * g, 1.0, ell=(1.0, 0.75, pa))
            _stamp(alb, a, hgt, yy, xx, fx, fy, r * 0.28, (0.6, 0.22, 0.3), 1.2)
    return _pack(alb, a, hgt)


def gen_maple(W, H, seed=13):
    """Self-made momiji card: 7-lobed palmate leaves ~#B8301E with darker veins, random rotation."""
    rng = np.random.default_rng(seed)
    alb, a, hgt, (yy, xx) = _card_canvas(W, H)
    for k in range(13):
        cx, cy = rng.uniform(0.1, 0.9) * W, rng.uniform(0.1, 0.9) * H
        R_ = rng.uniform(0.11, 0.17) * W
        rot = rng.uniform(0, 2 * np.pi)
        g = rng.uniform(0.85, 1.1)
        col = np.array([0.48, 0.03, 0.013]) * g
        for j in range(7):
            la = rot + (j - 3) * 0.55
            ln = R_ * (1.0 - abs(j - 3) * 0.14)
            _stamp(alb, a, hgt, yy, xx, cx + np.cos(la) * ln * 0.6, cy + np.sin(la) * ln * 0.6, ln * 0.6,
                   col, 1.0, ell=(1.0, 0.3, la))
        _stamp(alb, a, hgt, yy, xx, cx, cy, R_ * 0.22, col * 0.8, 1.0)
    return _pack(alb, a, hgt)
