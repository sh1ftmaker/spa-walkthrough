"""Prepare the texture inputs for the Kazan-yu shader kit demo.

1. Cut the 24 Codex plates out of refs/gen/sheet-tex-{stone,rock,wood,cloth}.png
   (black gutters detected automatically) -> .scratch/shaders/plates/<name>.png
2. Turn each plate into a 512 px PBR set for the runtime shader
   -> 3d/research/shaders/demo/tex/pl/<name>_base.jpg  (sRGB albedo, de-lit)
      3d/research/shaders/demo/tex/pl/<name>_nh.png    (RG normal XY +Y up, B height, A wet-film mask)
      3d/research/shaders/demo/tex/pl/<name>_orm.png   (R occlusion, G roughness, B metal, A height)
   The plates are photographs-style and NOT seamless; the kit's hex "patch" sampler only reads a
   disc around the plate centre, so no seams are needed for it. For plain tiling / Low tier we still
   make a seamless version with an offset cross-fade (the centre of the result is the untouched plate).
3. Snapshot the current library sets the demo compares against (downsampled to 512 px)
   -> demo/tex/lib/<set>_{base.jpg,nh.png,orm.png}
4. Write a 256 px tileable RGBA value-noise texture (kz_noise.png): R,G fbm at 1x/2x, B 4x, A vertical streaks.

Run: .venv/bin/python 3d/research/shaders/tools/prep_textures.py
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
SHEETS = os.path.join(ROOT, 'refs', 'gen')
PLATES = os.path.join(ROOT, '.scratch', 'shaders', 'plates')
OUT_PL = os.path.join(ROOT, '3d', 'research', 'shaders', 'demo', 'tex', 'pl')
OUT_LIB = os.path.join(ROOT, '3d', 'research', 'shaders', 'demo', 'tex', 'lib')
OUT_TEX = os.path.join(ROOT, '3d', 'research', 'shaders', 'demo', 'tex')
LIB_SRC = os.path.join(ROOT, '.scratch', 'matlib', 'tex')

NAMES = {
    'stone': ['basalt_columnar_wet', 'basalt_vesicular', 'paving_wet', 'obsidian', 'rimstone', 'black_sand'],
    'rock': ['rock_wet_ore', 'rock_teal_glass', 'sulfur_travertine', 'ash_clay', 'lava_crust', 'glacier_ice'],
    'wood': ['hinoki', 'lacquer', 'bamboo', 'tatami', 'washi', 'washi_backlit'],
    'cloth': ['noren', 'rope', 'bronze', 'iron', 'water_teal', 'foam_sand'],
}
# per-plate processing: height polarity (+1: bright is high), normal strength (slope per unit height
# across 512 px), roughness (dry, glossy-pocket), metal, de-light strength, specular clamp, crop box
# fraction (l, t, r, b) inside the plate (noren: avoid the logo).
P = {
    'basalt_columnar_wet': dict(pol=1, ns=6, r=(0.55, 0.06), metal=0, delight=0.85, spec=1.0, sat=0.3),
    'basalt_vesicular':    dict(pol=1, ns=8, r=(0.80, 0.45), metal=0, delight=0.85, spec=0.4, sat=0.35),
    'paving_wet':          dict(pol=1, ns=5, r=(0.45, 0.05), metal=0, delight=0.8, spec=1.0, sat=0.45),
    'obsidian':            dict(pol=1, ns=2, r=(0.12, 0.03), metal=0, delight=0.7, spec=1.0, sat=0.3),
    'rimstone':            dict(pol=1, ns=6, r=(0.60, 0.20), metal=0, delight=0.6, spec=0.3),
    'black_sand':          dict(pol=1, ns=7, r=(0.75, 0.15), metal=0, delight=0.85, spec=0.8, sat=0.45),
    'rock_wet_ore':        dict(pol=1, ns=6, r=(0.50, 0.06), metal=0, delight=0.85, spec=1.0, sat=0.25),
    'rock_teal_glass':     dict(pol=1, ns=4, r=(0.30, 0.05), metal=0, delight=0.8, spec=1.0),
    'sulfur_travertine':   dict(pol=1, ns=5, r=(0.65, 0.30), metal=0, delight=0.5, spec=0.3),
    'ash_clay':            dict(pol=1, ns=4, r=(0.85, 0.70), metal=0, delight=0.7, spec=0.0),
    'lava_crust':          dict(pol=-1, ns=6, r=(0.75, 0.40), metal=0, delight=0.3, spec=0.0),
    'glacier_ice':         dict(pol=1, ns=3, r=(0.15, 0.04), metal=0, delight=0.5, spec=0.5),
    'hinoki':              dict(pol=1, ns=3, r=(0.70, 0.50), metal=0, delight=0.6, spec=0.0, boards=[0, 74, 184, 283, 392, 483]),
    'lacquer':             dict(pol=1, ns=1.5, r=(0.25, 0.10), metal=0, delight=0.7, spec=0.8, boards=[0, 147, 312, 482]),
    'bamboo':              dict(pol=1, ns=4, r=(0.45, 0.30), metal=0, delight=0.5, spec=0.3),
    'tatami':              dict(pol=1, ns=5, r=(0.75, 0.60), metal=0, delight=0.6, spec=0.0, crop=(0.1, 0.0, 1.0, 1.0)),
    'washi':               dict(pol=1, ns=2, r=(0.85, 0.80), metal=0, delight=0.6, spec=0.0),
    'washi_backlit':       dict(pol=1, ns=1, r=(0.85, 0.80), metal=0, delight=0.2, spec=0.0),
    'noren':               dict(pol=1, ns=3, r=(0.90, 0.85), metal=0, delight=0.6, spec=0.0, crop=(0.0, 0.0, 0.36, 0.42)),
    'rope':                dict(pol=1, ns=8, r=(0.85, 0.75), metal=0, delight=0.5, spec=0.0),
    'bronze':              dict(pol=1, ns=2, r=(0.40, 0.25), metal=1, delight=0.6, spec=0.6),
    'iron':                dict(pol=1, ns=5, r=(0.80, 0.55), metal=0.3, delight=0.6, spec=0.0),
    'water_teal':          dict(pol=1, ns=2, r=(0.05, 0.03), metal=0, delight=0.5, spec=0.5),
    'foam_sand':           dict(pol=1, ns=4, r=(0.60, 0.10), metal=0, delight=0.6, spec=0.5),
}
LIB_SETS = ['basalt_dry', 'basalt_wet', 'obsidian', 'paving', 'black_sand', 'rimstone', 'rimstone_side', 'ash_clay',
            'hinoki', 'tatami', 'washi', 'lava', 'glacier_ice', 'iron', 'bronze', 'bamboo', 'lacquer_dark', 'noren', 'rope', 'lava_flow']


def runs(v, thr=40):
    m = v < thr
    out, s = [], None
    for i, x in enumerate(m):
        if x and s is None:
            s = i
        if not x and s is not None:
            out.append((s, i - 1)); s = None
    if s is not None:
        out.append((s, len(v) - 1))
    return out


def cells(img):
    a = np.asarray(img.convert('L')).astype(float)
    cr, rr = runs(a.max(0)), runs(a.max(1))
    xs = [(cr[i][1] + 1, cr[i + 1][0] - 1) for i in range(len(cr) - 1)]
    ys = [(rr[i][1] + 1, rr[i + 1][0] - 1) for i in range(len(rr) - 1)]
    assert len(xs) == 3 and len(ys) == 2, (xs, ys)
    return [(x0 + 4, y0 + 4, x1 - 4, y1 - 4) for (y0, y1) in ys for (x0, x1) in xs]


def s2l(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def l2s(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def gw(a, s):
    return gaussian_filter(a, s, mode='wrap')


def seamless(a, w=0.18, axes='uv'):
    """Offset cross-fade: centre = original, borders = half-rolled copy (which is continuous there)."""
    n = a.shape[0]
    r = np.roll(a, n // 2, 0)
    if 'u' in axes:
        r = np.roll(r, n // 2, 1)
    t = np.linspace(0, 1, n)
    e = np.minimum(t, 1 - t)  # 0 at the border, 0.5 at the centre
    m1 = np.clip(e / w, 0, 1)
    m = m1[:, None] * (m1[None, :] if 'u' in axes else np.ones((1, n)))
    m = m * m * (3 - 2 * m)
    if a.ndim == 3:
        m = m[..., None]
    return a * m + r * (1 - m)


def process(name, rgb_srgb, prm):
    lin = s2l(rgb_srgb)
    L = lin @ np.array([0.2126, 0.7152, 0.0722])
    meanL = L.mean()
    # 1. de-light: remove low-frequency shading (keeps the albedo pattern, flattens the photo light)
    Lb = gaussian_filter(L, 40, mode='reflect') + 1e-4
    k = prm['delight']
    flat = lin * ((meanL / Lb) ** k)[..., None]
    # 2. specular pockets: pixels much brighter than their surroundings and desaturated = baked glints
    Lf = flat @ np.array([0.2126, 0.7152, 0.0722])
    loc = gaussian_filter(Lf, 6, mode='reflect') + 1e-4
    sat = (flat.max(-1) - flat.min(-1)) / (flat.max(-1) + 1e-4)
    spec = np.clip((Lf / loc - 1.35) / 1.2, 0, 1) * np.clip(1.4 - 1.6 * sat, 0, 1)
    spec = gaussian_filter(spec, 1.0)
    # replace glints: soft-clip luminance above a knee relative to the median (wet plates: low knee,
    # i.e. the photo's specular sheen is removed from albedo and comes back from the roughness map)
    med = np.median(Lf)
    knee = med * (1.4 + 3.0 * (1.0 - prm['spec']))
    L2 = np.where(Lf > knee, knee + (knee * 0.35) * (1 - np.exp(-(Lf - knee) / (knee * 0.35 + 1e-6))), Lf)
    alb = flat * (L2 / (Lf + 1e-6))[..., None]
    blur = np.stack([gaussian_filter(alb[..., i], 3, mode='reflect') for i in range(3)], -1)
    sm = (spec * prm['spec'])[..., None]
    alb = alb * (1 - 0.6 * sm) + blur * 0.6 * sm
    if 'sat' in prm:   # stone plates: remove the photo's warm cast, keep a slightly cool neutral
        La = (alb @ np.array([0.2126, 0.7152, 0.0722]))[..., None]
        alb = (La + (alb - La) * prm['sat']) * np.array([0.96, 1.0, 1.07])
    # 3. height from luminance band-pass
    hsrc = gaussian_filter(L, 1.0, mode='reflect') - gaussian_filter(L, 30, mode='reflect')
    hsrc = hsrc * prm['pol']
    lo, hi = np.percentile(hsrc, [1, 99])
    h = np.clip((hsrc - lo) / (hi - lo + 1e-6), 0, 1)
    # 4. occlusion from cavity
    cav = gaussian_filter(h, 10, mode='reflect') - h
    ao = np.clip(1 - 1.6 * np.clip(cav, 0, 1), 0.35, 1)
    # 5. roughness: dry value, glossy where the photo had glints or in hollows of wet materials
    r0, r1 = prm['r']
    wet = np.clip(spec * 1.5 + np.clip(0.45 - h, 0, 1) * (1 if r1 < 0.2 else 0.3), 0, 1)
    wet = gaussian_filter(wet, 2.0, mode='reflect')
    rough = r0 + (r1 - r0) * wet
    metal = np.full_like(h, float(prm['metal']))
    # make everything seamless (offset cross-fade), then normals from the seamless height
    ax = 'v' if 'boards' in prm else 'uv'
    alb, h, ao, rough, metal, wet = [seamless(x, axes=ax) for x in (alb, h, ao, rough, metal, wet)]
    hs = gw(h, 0.7)
    gy, gx = np.gradient(hs)
    ns = prm['ns']
    nx, ny = -gx * ns * 2.5, gy * ns * 2.5  # image rows go down; +Y normal = +v (up)
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny = nx / ln, ny / ln
    base = (l2s(alb) * 255 + 0.5).astype(np.uint8)
    nh = np.stack([nx * 0.5 + 0.5, ny * 0.5 + 0.5, h, wet], -1)
    orm = np.stack([ao, np.clip(rough, 0.02, 1), metal, h], -1)
    Image.fromarray(base).save(os.path.join(OUT_PL, f'{name}_base.jpg'), quality=92)
    Image.fromarray((np.clip(nh, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA').save(os.path.join(OUT_PL, f'{name}_nh.png'))
    Image.fromarray((np.clip(orm, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA').save(os.path.join(OUT_PL, f'{name}_orm.png'))
    mean_alb = alb.reshape(-1, 3).mean(0)
    return dict(mean_albedo_linear=[round(float(x), 4) for x in mean_alb],
                albedo_std_srgb255=round(float((l2s(alb) * 255).std()), 1),
                mean_roughness=round(float(rough.mean()), 3))


def value_noise_tile(n, f, rng):
    g = rng.random((f, f))
    x = np.arange(n) * f / n
    i0 = np.floor(x).astype(int); t = x - i0; t = t * t * (3 - 2 * t)
    i1 = (i0 + 1) % f
    a = g[i0][:, i0] * (1 - t)[None, :] + g[i0][:, i1] * t[None, :]
    b = g[i1][:, i0] * (1 - t)[None, :] + g[i1][:, i1] * t[None, :]
    return a * (1 - t)[:, None] + b * t[:, None]


def fbm(n, f0, octs, rng):
    s, a, tot = np.zeros((n, n)), 1.0, 0.0
    for o in range(octs):
        s += a * value_noise_tile(n, f0 * 2 ** o, rng); tot += a; a *= 0.5
    s /= tot
    return (s - s.min()) / (s.max() - s.min())


def main():
    os.makedirs(PLATES, exist_ok=True); os.makedirs(OUT_PL, exist_ok=True); os.makedirs(OUT_LIB, exist_ok=True)
    stats = {}
    for sheet, names in NAMES.items():
        img = Image.open(os.path.join(SHEETS, f'sheet-tex-{sheet}.png')).convert('RGB')
        for name, box in zip(names, cells(img)):
            plate = img.crop(box)
            plate.save(os.path.join(PLATES, f'{name}.png'))
            prm = P[name]
            if 'crop' in prm:
                l, t, r, b = prm['crop']; W, H = plate.size
                plate = plate.crop((int(l * W), int(t * H), int(r * W), int(b * H)))
            if 'boards' in prm:   # regularise: N equal-width boards side by side
                b = prm['boards']; N = len(b) - 1; W, H = plate.size
                reg = Image.new('RGB', (512, 512))
                for i in range(N):
                    strip = plate.crop((b[i], 0, b[i + 1], H)).resize((512 // N if i < N - 1 else 512 - (512 // N) * (N - 1), 512), Image.LANCZOS)
                    reg.paste(strip, ((512 // N) * i, 0))
                plate = reg
            plate = plate.resize((512, 512), Image.LANCZOS)
            a = np.asarray(plate).astype(np.float64) / 255
            stats[name] = dict(sheet=sheet, box=box, **process(name, a, prm))
            print(name, stats[name])
    with open(os.path.join(OUT_PL, 'plates.json'), 'w') as f:
        json.dump(stats, f, indent=1)
    # library snapshot
    for s in LIB_SETS:
        for ch in ('base', 'nh', 'orm'):
            src = os.path.join(LIB_SRC, f'{s}_{ch}.png')
            if not os.path.exists(src):
                print('missing', src); continue
            im = Image.open(src)
            w, h = im.size
            sc = 512 / max(w, h) if max(w, h) > 512 else 1
            im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS)
            if ch == 'base':
                im.convert('RGB').save(os.path.join(OUT_LIB, f'{s}_base.jpg'), quality=92)
            else:
                im.save(os.path.join(OUT_LIB, f'{s}_{ch}.png'))
    mac = os.path.join(LIB_SRC, 'kz_macro_base.png')
    if os.path.exists(mac):
        Image.open(mac).save(os.path.join(OUT_TEX, 'kz_macro_lib.png'))
    rng = np.random.default_rng(7)
    n = 256
    R = fbm(n, 4, 5, rng); G = fbm(n, 8, 4, rng); B = fbm(n, 16, 3, rng)
    # vertical streaks: noise stretched along v (rows), so A varies fast in x, slow in y
    st = np.zeros((n, n))
    for o, a in ((32, 1.0), (64, 0.5)):
        st += a * value_noise_tile(n, o, rng)[:, :1].T.repeat(n, 0) * value_noise_tile(n, 2, rng)
    st = (st - st.min()) / (st.max() - st.min())
    A = np.clip((st - 0.55) * 3, 0, 1)
    tex = np.stack([R, G, B, A], -1)
    Image.fromarray((tex * 255 + 0.5).astype(np.uint8), 'RGBA').save(os.path.join(OUT_TEX, 'kz_noise.png'))
    print('done')


if __name__ == '__main__':
    sys.exit(main())
