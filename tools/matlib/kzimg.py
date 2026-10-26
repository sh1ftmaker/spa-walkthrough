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


def normals_from_height(h, depth_m, tile_m):
    """Tangent-space normal (OpenGL / glTF convention, +Y = +v) from a periodic height field.

    h in [0,1]; displacement = h * depth_m; texel = tile_m / width.  Central differences
    with wrap-around, so the normal map tiles exactly like the height does.
    """
    H, W = h.shape
    px = tile_m / W
    py = tile_m / H
    z = h * depth_m
    gx = (np.roll(z, -1, axis=1) - np.roll(z, 1, axis=1)) / (2.0 * px)
    gy = (np.roll(z, -1, axis=0) - np.roll(z, 1, axis=0)) / (2.0 * py)
    n = np.stack([-gx, -gy, np.ones_like(z)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


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
