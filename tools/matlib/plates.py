"""Painted texture plates -> seamless PBR texture sets (numpy only).

Source: refs/gen/sheet-tex-{stone,rock,wood,cloth}.png, self-made Codex paintings, 3x2 grid
of ~500 px flat-lit plates separated by black gutters (owner-approved, licence fine).

Pipeline per plate (see make_set):
 1. cut      find the gutters (columns/rows whose 98th-percentile luminance is ~black), inset.
 2. resample Lanczos-3 to the working texel size (upscale for close-up materials).
 3. de-light painted specular highlights are detected against the local median and removed
             from albedo (they become the gloss / wet mask); the residual low-frequency lighting
             gradient is divided out (luminance only, so hue and local contrast stay).
 4. quilt    periodic image quilting (Efros & Freeman 2001) with min-error boundary cuts:
             blocks wrap around the output edges, so the result tiles exactly and the plate is
             re-arranged (not repeated) over a tile 2-4x its area.  Oriented materials (boards,
             culms, ribs, streaks) keep their orientation and can quilt along one axis only;
             isotropic ones also use rotated / flipped blocks.
 5. maps     height = frequency-separated luminance (fine / mid / large bands), normal and
             cavity from height (kzimg), roughness from a material-specific curve of
             luminance and gloss mask, metal / emission / foam masks from colour rules.
"""
import math

import numpy as np

SHEETS = {}


def srgb_to_lin(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def lum(lin):
    return lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722


# ----------------------------------------------------------------------- loading / cutting
def load_sheet(path):
    """(H, W, 3) sRGB-encoded floats, row 0 = top.  Uses Blender's image loader."""
    if path in SHEETS:
        return SHEETS[path]
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    a = a.reshape(h, w, 4)[::-1, :, :3].astype(np.float64)
    SHEETS[path] = a
    return a


def _runs(flags, min_len):
    out, start = [], None
    for i, f in enumerate(list(flags) + [False]):
        if f and start is None:
            start = i
        if not f and start is not None:
            if i - start >= min_len:
                out.append((start, i))
            start = None
    return out


def cut(sheet, inset=6):
    """The 6 plates of a 3x2 sheet, row-major (top-left first)."""
    L = sheet.mean(-1)
    cols = np.percentile(L, 98, axis=0) > 0.07
    rows = np.percentile(L, 98, axis=1) > 0.07
    xs = _runs(cols, 150)
    ys = _runs(rows, 150)
    plates = []
    for y0, y1 in ys:
        for x0, x1 in xs:
            plates.append(sheet[y0 + inset:y1 - inset, x0 + inset:x1 - inset])
    return plates


# ----------------------------------------------------------------------- resampling / blur
def _lanczos_matrix(n_in, n_out, a=3):
    scale = n_in / n_out
    support = a * max(scale, 1.0)
    m = np.zeros((n_out, n_in))
    for i in range(n_out):
        c = (i + 0.5) * scale - 0.5
        j0, j1 = int(math.floor(c - support)), int(math.ceil(c + support))
        js = np.arange(j0, j1 + 1)
        x = (js - c) / max(scale, 1.0)
        w = np.sinc(x) * np.sinc(x / a) * (np.abs(x) < a)
        jc = np.clip(js, 0, n_in - 1)
        for jj, ww in zip(jc, w):
            m[i, jj] += ww
        m[i] /= m[i].sum()
    return m


def resize(img, h, w):
    my = _lanczos_matrix(img.shape[0], h)
    mx = _lanczos_matrix(img.shape[1], w)
    out = np.tensordot(my, img, axes=(1, 0))
    out = np.tensordot(out, mx, axes=(1, 1))
    return np.moveaxis(out, -1, 1) if img.ndim == 3 else out


def blur(a, sigma, wrap=False):
    """Gaussian blur; wrap=False pads by reflection (plates are not periodic yet)."""
    if sigma <= 0:
        return a
    if wrap:
        pad = 0
        b = a
    else:
        pad = int(min(3 * sigma, min(a.shape[:2]) - 1))
        b = np.pad(a, ((pad, pad), (pad, pad)) + ((0, 0),) * (a.ndim - 2), mode='reflect')
    H, W = b.shape[:2]
    fy = np.fft.fftfreq(H)[:, None]
    fx = np.fft.fftfreq(W)[None, :]
    g = np.exp(-2.0 * (np.pi ** 2) * (sigma ** 2) * (fy ** 2 + fx ** 2))
    if b.ndim == 3:
        g = g[..., None]
    out = np.real(np.fft.ifft2(np.fft.fft2(b, axes=(0, 1)) * g, axes=(0, 1)))
    return out[pad:H - pad, pad:W - pad] if pad else out


def median_like(L, sigma):
    """Robust local level: blur of the luminance with bright outliers clipped."""
    b = blur(L, sigma)
    return blur(np.minimum(L, b * 1.4), sigma)


# ----------------------------------------------------------------------- de-lighting
def delight(lin, spec_thresh=1.9, spec_sigma=4.0, grad_sigma_frac=0.2, grad_strength=0.9, keep_spec=False):
    """Returns (albedo_lin, gloss_mask).  gloss_mask = painted highlights (0..1)."""
    L = lum(lin) + 1e-5
    loc = median_like(L, spec_sigma)
    ratio = L / (loc + 1e-5)
    gloss = np.clip((ratio - spec_thresh * 0.75) / (spec_thresh * 0.5), 0, 1)
    if not keep_spec:
        target = np.minimum(L, loc * spec_thresh * 0.8)
        lin = lin * (target / L)[..., None]
        L = lum(lin) + 1e-5
    s = grad_sigma_frac * min(L.shape)
    big = blur(np.log(L), s)
    corr = np.exp((big - big.mean()) * grad_strength)
    return lin / corr[..., None], gloss


# ----------------------------------------------------------------------- quilting
def _min_path(e):
    """Vertical min-error path through e (rows x cols); returns column index per row."""
    R, C = e.shape
    cum = e.copy()
    for r in range(1, R):
        prev = cum[r - 1]
        left = np.concatenate([[np.inf], prev[:-1]])
        right = np.concatenate([prev[1:], [np.inf]])
        cum[r] += np.minimum(np.minimum(left, prev), right)
    path = np.zeros(R, int)
    path[-1] = int(np.argmin(cum[-1]))
    for r in range(R - 2, -1, -1):
        c = path[r + 1]
        lo, hi = max(0, c - 1), min(C, c + 2)
        path[r] = lo + int(np.argmin(cum[r, lo:hi]))
    return path


def _xform(p, k, flip):
    p = np.rot90(p, k, axes=(0, 1))
    return p[:, ::-1] if flip else p


def quilt(src, out_h, out_w, block, overlap, axis='both', rotate=False, seed=1, candidates=80,
          exclude=None, err_channels=3):
    """Periodic image quilting.  src (h, w, C) -> (out_h, out_w, C) that tiles exactly.

    axis 'both': square blocks in a wrapping grid.  axis 'v': full-width strips stacked and cut
    along v only (src must already tile in u, e.g. cropped at a board joint); axis 'u' likewise.
    exclude: (y0, y1, x0, x1) region of src never used (e.g. a printed logo)."""
    rng = np.random.default_rng(seed)
    sh, sw, C = src.shape
    if axis == 'v':
        bh, bw = block, out_w
        assert sw == out_w, 'axis v quilting needs src width == out width'
    elif axis == 'u':
        bh, bw = out_h, block
        assert sh == out_h, 'axis u quilting needs src height == out height'
    else:
        bh = bw = block
    sy, sx = bh - (overlap if axis != 'u' else 0), bw - (overlap if axis != 'v' else 0)
    ny, nx = (out_h // sy if axis != 'u' else 1), (out_w // sx if axis != 'v' else 1)
    assert (axis == 'u' or ny * sy == out_h) and (axis == 'v' or nx * sx == out_w), 'block/overlap must divide output'
    out = np.zeros((out_h, out_w, C))
    filled = np.zeros((out_h, out_w), bool)
    used = []                                        # (y, x) of placed source blocks: reuse penalty
    trans = [(0, False)]
    if rotate:
        trans = [(k, f) for k in range(4) for f in (False, True)]
    for iy in range(ny):
        for ix in range(nx):
            rows = (np.arange(bh) + iy * sy) % out_h
            cols = (np.arange(bw) + ix * sx) % out_w
            ex = out[np.ix_(rows, cols)]
            fm = filled[np.ix_(rows, cols)]
            best, best_e = None, np.inf
            cands = []
            tries = 0
            while len(cands) < candidates and tries < candidates * 40:
                tries += 1
                k, f = trans[rng.integers(len(trans))]
                hh, ww = (bh, bw) if k % 2 == 0 else (bw, bh)
                if hh > sh or ww > sw:
                    k, f, hh, ww = 0, f, bh, bw
                y0 = rng.integers(0, sh - hh + 1)
                x0 = rng.integers(0, sw - ww + 1) if axis != 'v' else 0
                if exclude is not None:
                    ey0, ey1, ex0, ex1 = exclude
                    if y0 < ey1 and y0 + hh > ey0 and x0 < ex1 and x0 + ww > ex0:
                        continue
                p = _xform(src[y0:y0 + hh, x0:x0 + ww], k, f)
                if fm.any():
                    d = ((p[..., :err_channels] - ex[..., :err_channels]) ** 2).sum(-1)
                    e = d[fm].mean()
                else:
                    e = rng.random()
                near = sum(math.exp(-((y0 - uy) ** 2 + (x0 - ux) ** 2) / (2 * (0.35 * bh) ** 2)) for uy, ux in used)
                cands.append((e * (1.0 + 0.8 * near) + 1e-12 * near, p, (y0, x0)))
            cands.sort(key=lambda t: t[0])
            emin = cands[0][0]
            pool = [c for c in cands if c[0] <= emin * 1.15 + 1e-9][:5] or cands[:1]
            e_sel, p, pos = pool[rng.integers(len(pool))]
            used.append(pos)
            M = np.ones((bh, bw))
            if fm.any():
                d = ((p[..., :err_channels] - ex[..., :err_channels]) ** 2).sum(-1)
                ov_y = overlap if axis != 'u' else 0
                ov_x = overlap if axis != 'v' else 0
                if ov_x and fm[:, :ov_x].all():
                    path = _min_path(d[:, :ov_x])
                    for r, c in enumerate(path):
                        M[r, :c] = 0
                if ov_x and fm[:, bw - ov_x:].all():
                    path = _min_path(d[:, bw - ov_x:][:, ::-1])
                    for r, c in enumerate(path):
                        M[r, bw - c:] = 0
                if ov_y and fm[:ov_y, :].all():
                    path = _min_path(d[:ov_y, :].T)
                    for c, r in enumerate(path):
                        M[:r, c] = 0
                if ov_y and fm[bh - ov_y:, :].all():
                    path = _min_path(d[bh - ov_y:, :][::-1].T)
                    for c, r in enumerate(path):
                        M[bh - r:, c] = 0
                M = np.where(fm, M, 1.0)
                Mb = blur(M, 1.0)
                M = np.where(fm, Mb, 1.0)
            blk = M[..., None] * p + (1 - M[..., None]) * ex
            out[np.ix_(rows, cols)] = blk
            filled[np.ix_(rows, cols)] = True
    return out


# ----------------------------------------------------------------------- map derivation
def norm01(a, lo=1.0, hi=99.0):
    p0, p1 = np.percentile(a, lo), np.percentile(a, hi)
    return np.clip((a - p0) / max(p1 - p0, 1e-9), 0, 1)


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def height_from(lin, px_m, bands=(0.004, 0.02, 0.08), weights=(0.25, 0.45, 0.3), sign=1.0, dark_deep=0.0):
    """Frequency-separated height from log-luminance (wrapping blur: the input tiles).

    bands are blur radii in metres; each band = blur(r_i/2) - blur(r_i*2).  dark_deep pushes the
    darkest pixels (cracks, holes, joints) down."""
    L = np.log(lum(lin) + 1e-4)
    h = np.zeros_like(L)
    for r, w in zip(bands, weights):
        s0, s1 = max(r / 2 / px_m, 0.5), r * 2 / px_m
        b = blur(L, s0, wrap=True) - blur(L, s1, wrap=True)
        h += w * b / (b.std() + 1e-9)
    h = norm01(h * sign)
    if dark_deep:
        d = 1 - norm01(L, 0.5, 30.0)
        h = np.clip(h - dark_deep * d, 0, 1)
        h = norm01(h, 0.5, 99.5)
    return h


def joint_crop(lin):
    """Crop a board / culm plate at its outermost strong vertical joints so it tiles in u."""
    col = blur(lum(lin).mean(0)[None, :], 1.5)[0]
    W = col.size
    med = np.median(col)
    mins = [i for i in range(2, W - 2) if col[i] <= col[i - 2:i + 3].min() and col[i] < med * 0.75]
    left = [i for i in mins if 0.02 * W < i < 0.3 * W]
    right = [i for i in mins if 0.7 * W < i < 0.98 * W]
    if not left or not right:
        return lin
    j0 = min(left, key=lambda i: col[i])
    j1 = min(right, key=lambda i: col[i])
    return lin[:, j0:j1]


def make_set(p, plate_img):
    """Build the baked-channel dict (as build_library.bake_set returns) from a plate recipe."""
    src_lin = srgb_to_lin(plate_img)
    if p.get('joints'):
        src_lin = joint_crop(src_lin)
    if p.get('crop'):
        y0, y1, x0, x1 = p['crop']
        H0, W0 = src_lin.shape[:2]
        src_lin = src_lin[int(y0 * H0):int(y1 * H0), int(x0 * W0):int(x1 * W0)]
    if p.get('rot90'):
        src_lin = np.rot90(src_lin, p['rot90'], axes=(0, 1)).copy()
    up = p.get('upscale', 1.0)
    sh, sw = src_lin.shape[:2]
    src_px_m = p['plate_m'] / sw                       # metres per source pixel (plate width)
    if p.get('src_w'):                                  # exact working width (boards: crop to joints, fit pow2)
        nw = p['src_w']
        nh = int(round(sh * nw / sw))
    else:
        nw, nh = int(round(sw * up)), int(round(sh * up))
    src_lin = np.clip(resize(src_lin, nh, nw), 1e-5, None)
    px_m = p['plate_m'] / nw
    alb, gloss = delight(src_lin, **p.get('delight', {}))
    extra = []
    if p.get('glow'):                                  # emissive plates: keep the original glow colour
        extra = [src_lin]
    stack = np.dstack([alb, gloss[..., None]] + extra)
    out_h, out_w = p['out']
    strips = []
    for i in range(p.get('strips', 1)):                # several differently-quilted strips side by side
        q = quilt(stack, out_h, out_w, p['block'], p['overlap'], axis=p.get('axis', 'both'),
                  rotate=p.get('rotate', False), seed=p.get('seed', 1) + 17 * i,
                  exclude=None if not p.get('exclude') else tuple(int(v * s) for v, s in zip(
                      p['exclude'], (nh, nh, nw, nw))))
        strips.append(np.roll(q, (i * out_h // 3 + 97 * i, i * out_w // 3), axis=(0, 1)))   # no mirroring (butterfly pairs)
    q = np.concatenate(strips, axis=1)
    out_w = q.shape[1]
    alb, gloss = np.clip(q[..., :3], 0, None), np.clip(q[..., 3], 0, 1)
    glow = q[..., 4:7] if extra else None
    # albedo calibration: scale luminance to the target mean, optional saturation
    L = lum(alb)
    if p.get('sat') is not None:
        alb = L[..., None] + (alb - L[..., None]) * p['sat']
    if p.get('tint') is not None:
        alb = alb * np.array(p['tint'])
    L = lum(alb)
    alb = alb * (p['albedo_mean'] / max(L.mean(), 1e-6))
    if p.get('contrast'):
        L = lum(alb)
        m = L.mean()
        alb = alb * ((m + (L - m) * p['contrast']) / np.maximum(L, 1e-6))[..., None]
    alb = np.clip(alb, 0, 0.95)
    h = height_from(alb, px_m, **p.get('height', {}))
    Ln = norm01(np.log(lum(alb) + 1e-4))
    r = p['rough']                                    # (lo, hi, mode)
    lo, hi, mode = r
    if mode == 'lum':                                  # brighter = rougher (dry crust on dark wet stone)
        rough = lo + (hi - lo) * Ln
    elif mode == 'inv':                                # brighter = smoother (polished highs)
        rough = hi - (hi - lo) * Ln
    elif mode == 'height':                             # highs rough, lows smooth (water in hollows)
        rough = lo + (hi - lo) * h
    else:
        rough = np.full_like(Ln, (lo + hi) / 2)
    gl = blur(gloss, 1.5, wrap=True)
    rough = rough * (1 - gl * p.get('gloss_rough', 0.8)) + p.get('gloss_floor', 0.04) * gl * p.get('gloss_rough', 0.8)
    rough = np.clip(rough + (blur(np.random.default_rng(3).random(h.shape), 2.0, wrap=True) - 0.5) * 0.08, 0.02, 1)
    wet = np.clip(blur(gloss, 3.0, wrap=True) * 1.5 + (1 - h) * p.get('wet_hollows', 0.4) - 0.2, 0, 1)
    metal = np.zeros_like(h)
    mask = np.ones_like(h)
    emis = None
    ao = np.ones_like(h)
    rule = p.get('rule')
    if rule == 'bronze':                               # teal-green verdigris = non-metal crust
        g = alb[..., 1] / (alb.sum(-1) + 1e-6)
        b = alb[..., 2] / (alb.sum(-1) + 1e-6)
        verd = smooth(g + b * 0.6, 0.52, 0.62)
        metal = 1 - verd
        rough = np.clip(rough * (1 - verd) + 0.85 * verd, 0, 1)
    elif rule == 'rust':
        rc = alb[..., 0] / (alb.sum(-1) + 1e-6)
        rust = smooth(rc, 0.42, 0.52)
        rough = np.clip(rough * (1 - rust) + 0.88 * rust, 0, 1)
    elif rule == 'lava':                               # glowing seams -> emissive; crust albedo dark
        g0 = srgb_to_lin(np.clip(glow, 0, 1)) if glow is not None else alb
        gl_l = lum(glow)
        t0, t1 = p.get('hot', (0.18, 0.45))
        hot = smooth((glow[..., 0] - glow[..., 2]) * 1.0 + gl_l * 0.5, t0, t1)
        emis = glow * hot[..., None]
        emis = emis / max(np.percentile(lum(emis), 99.7), 1e-6)
        alb = alb * (1 - hot[..., None] * 0.85) + hot[..., None] * np.array([0.22, 0.05, 0.01])
        alb = alb * (p['albedo_mean'] / max(lum(alb).mean(), 1e-6))
        h = np.clip(h - hot * 0.4, 0, 1)
        rough = np.clip(rough - hot * 0.25, 0.02, 1)
    elif rule == 'ice':                                # white fracture planes -> mask; fake inner glow
        sat = alb.max(-1) - alb.min(-1)
        white = smooth(lum(alb) - sat * 1.5, 0.15, 0.45)
        mask = np.clip(white * 0.8, 0, 1)
        emis = alb * (1 - white[..., None] * 0.5)
        emis = emis / max(np.percentile(lum(emis), 99.5), 1e-6)
    elif rule == 'lantern':                            # emissive = paper glow, ribs dark, vertical gradient
        src = glow if glow is not None else alb
        gl_l = lum(src)
        gn = np.clip(gl_l / max(np.percentile(gl_l, 99.0), 1e-6), 0, 1.1)
        rib = 1 - smooth(gn, 0.2, 0.55)
        H = gn.shape[0]
        v = 1.0 - (np.arange(H) + 0.5) / H                 # row 0 = top = v 1
        g = (np.sin(np.pi * v) ** 0.8)[:, None]
        cap = (smooth(v, 0.0, 0.05) * (1 - smooth(v, 0.95, 1.0)))[:, None]
        edge, centre = (np.array(c) for c in p['colors'])
        col = edge[None, None, :] * (1 - g[..., None]) + centre[None, None, :] * g[..., None]
        emis = col * (gn * (0.45 + 0.55 * g) * cap)[..., None]
        alb = alb * (1 - rib[..., None] * 0.55)
        mask = np.clip(gn, 0, 1)
    elif rule in ('paper', 'paper_glow'):
        thin = 1 - norm01(blur(lum(alb), 2.0, wrap=True))     # darker cloud = fewer fibres = thinner
        mask = thin
        if rule == 'paper_glow':
            fib = norm01(blur(lum(alb), 0.7, wrap=True) - blur(lum(alb), 4.0, wrap=True))
            edge, centre = (np.array(c) for c in p['colors'])
            glow_l = np.clip(0.35 + 0.75 * thin - 0.35 * fib, 0, 1)
            emis = (edge[None, None, :] * (1 - glow_l[..., None]) * 0.5 + centre[None, None, :] * glow_l[..., None]) \
                * glow_l[..., None]
    elif rule == 'foam':                                # only bright, unsaturated pixels are foam
        sat = alb.max(-1) - alb.min(-1)
        w = lum(alb) / max(np.percentile(lum(alb), 99.5), 1e-6) - sat / max(alb.max(), 1e-6) * 1.5
        mask = smooth(w, 0.45, 0.8) * 0.85
    if p.get('water'):                                 # water: base rgb is the foam colour
        alb = np.ones_like(alb) * np.array([0.9, 0.95, 0.95])
        rough = np.clip(rough * 0 + 0.02 + mask * 0.4, 0.02, 1)
        wet = np.ones_like(h)
    return {'albedo': alb, 'ao': ao, 'rough': rough, 'metal': metal, 'height': h, 'mask': mask, 'wet': wet,
            'emis': emis, 'px_m': px_m, 'size': (out_w, out_h)}
