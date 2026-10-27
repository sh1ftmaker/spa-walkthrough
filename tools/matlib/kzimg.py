"""numpy image helpers for the material bake: PNG writer, sRGB, normals from height, seam check.

Arrays are (H, W, C) float, row 0 = bottom (Blender pixel order, v = 0).  write_png flips to
top-first, so the PNG/KTX2 image has v = 1 on its first row, which is how Blender and the
glTF exporter expect images.
"""
import struct
import zlib

import numpy as np


def lin_to_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def to_u8(x):
    return np.clip(np.rint(np.clip(x, 0.0, 1.0) * 255.0), 0, 255).astype(np.uint8)


def write_png(path, arr):
    """arr: (H, W) or (H, W, C) uint8 or uint16, row 0 = bottom."""
    a = np.ascontiguousarray(arr[::-1])
    if a.ndim == 2:
        a = a[:, :, None]
    h, w, c = a.shape
    ctype = {1: 0, 2: 4, 3: 2, 4: 6}[c]
    depth = 16 if a.dtype == np.uint16 else 8
    if depth == 16:
        a = a.astype('>u2')
    raw = a.reshape(h, -1).view(np.uint8)
    raw = np.concatenate([np.zeros((h, 1), np.uint8), raw], axis=1).tobytes()

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, ctype, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 7))
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)


def normals_from_height(h, depth_m, tile_u_m, tile_v_m=None):
    """Tangent-space normal (OpenGL / glTF convention, +Y = +v) from a periodic height field.

    h in [0,1]; displacement = h * depth_m; texel = tile / pixels per axis (non-square tiles
    allowed).  Central differences with wrap-around, so the normal map tiles like the height.
    """
    H, W = h.shape
    px = tile_u_m / W
    py = (tile_v_m if tile_v_m else tile_u_m) / H
    z = h * depth_m
    gx = (np.roll(z, -1, axis=1) - np.roll(z, 1, axis=1)) / (2.0 * px)
    gy = (np.roll(z, -1, axis=0) - np.roll(z, 1, axis=0)) / (2.0 * py)
    n = np.stack([-gx, -gy, np.ones_like(z)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def blur_wrap(a, sigma_px):
    """Periodic gaussian blur (FFT), sigma in pixels; (sy, sx) tuple allowed."""
    sy, sx = (sigma_px, sigma_px) if np.isscalar(sigma_px) else sigma_px
    H, W = a.shape
    fy = np.fft.fftfreq(H)[:, None]
    fx = np.fft.fftfreq(W)[None, :]
    g = np.exp(-2.0 * (np.pi ** 2) * ((fy * sy) ** 2 + (fx * sx) ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def cavity_ao(h, depth_m, tile_u_m, tile_v_m, strength=1.0):
    """Cavity / local occlusion from a periodic height field.

    How far each texel sits below its surroundings at three radii (5 mm, 2 cm, 8 cm), in metres,
    turned into an occlusion factor: a pit 1 cm below its 2 cm neighbourhood loses about 35 %.
    """
    H, W = h.shape
    pu, pv = tile_u_m / W, tile_v_m / H
    z = h * depth_m
    occ = np.zeros_like(z)
    for r_m, w in ((0.005, 0.5), (0.02, 0.35), (0.08, 0.15)):
        b = blur_wrap(z, (max(r_m / pv, 0.5), max(r_m / pu, 0.5)))
        occ += w * np.maximum(0.0, b - z) / r_m
    return np.clip(1.0 - strength * 2.2 * occ, 0.0, 1.0)


def downsample2(a):
    """Box downsample by 2 along each axis that is still > 1 (power-of-two sizes; non-square ok)."""
    H, W = a.shape[:2]
    fy, fx = (2 if H > 1 else 1), (2 if W > 1 else 1)
    return a.reshape(H // fy, fy, W // fx, fx, *a.shape[2:]).mean(axis=(1, 3))


def toksvig_mips(orm, n, min_size=1):
    """Mip chain for the ORM texture with Toksvig specular anti-aliasing in roughness.

    orm: (H,W,4) float in [0,1]; n: (H,W,3) unit normals.  Each level box-filters ORM and the
    normals; where the averaged normal is shorter than 1 (detail that the mip can no longer show)
    roughness is raised: r' = sqrt(r^2 + (1-|n|)/|n|).  Level 0 is unchanged.
    """
    levels = [orm]
    o, nn, r2 = orm, n, orm[..., 1] ** 2
    while max(o.shape[:2]) > min_size:
        o, nn, r2 = downsample2(o), downsample2(nn), downsample2(r2)
        ln = np.clip(np.linalg.norm(nn, axis=-1), 1e-4, 1.0)
        var = (1.0 - ln) / ln
        out = o.copy()
        out[..., 1] = np.sqrt(np.clip(r2 + np.minimum(var * 2.0, 0.6), 0, 1))
        levels.append(out)
    return levels


def seam_ratio(a):
    """Wrap-edge step vs. typical neighbour step (1.0 = edge is as smooth as the interior).

    Returns max of the horizontal and vertical ratios over all channels.
    """
    a = a.astype(np.float64)
    if a.ndim == 2:
        a = a[:, :, None]
    dx_in = np.abs(np.diff(a, axis=1)).mean() + 1e-9
    dy_in = np.abs(np.diff(a, axis=0)).mean() + 1e-9
    dx_edge = np.abs(a[:, 0] - a[:, -1]).mean()
    dy_edge = np.abs(a[0] - a[-1]).mean()
    return float(max(dx_edge / dx_in, dy_edge / dy_in))
