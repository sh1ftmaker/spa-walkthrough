// Procedural stand-in textures + KTX2 (Basis Universal UASTC) encoding.
import { encodeToKTX2 } from 'ktx2-encoder';

// ---------- tileable value noise ----------
function hash(x, y, s) {
  let h = (x * 374761393 + y * 668265263 + s * 2147483647) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}
function vnoise(u, v, period, seed) {
  const x = u * period, y = v * period;
  const x0 = Math.floor(x), y0 = Math.floor(y), fx = x - x0, fy = y - y0;
  const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
  const w = (a) => ((a % period) + period) % period;
  const a = hash(w(x0), w(y0), seed), b = hash(w(x0 + 1), w(y0), seed);
  const c = hash(w(x0), w(y0 + 1), seed), d = hash(w(x0 + 1), w(y0 + 1), seed);
  return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
}
export function fbm(u, v, base, oct, seed) {
  let s = 0, amp = 0.5, norm = 0, p = base;
  for (let i = 0; i < oct; i++) { s += amp * vnoise(u, v, p, seed + i * 17); norm += amp; amp *= 0.5; p *= 2; }
  return s / norm;
}
const srgb = (c) => Math.round(255 * Math.max(0, Math.min(1, c)));

// Albedo generators return sRGB-encoded 0..1 triples for (u, v) in [0,1)
export const ALBEDO = {
  // pale warm stone tiles, 1 m tiles over a 2 m texture -> 2x2 tiles
  stone_floor: (u, v) => {
    const n = fbm(u, v, 8, 5, 1), g = Math.min(Math.abs(((u * 2) % 1) - 0.5), Math.abs(((v * 2) % 1) - 0.5));
    const grout = g > 0.488 ? 0.55 : 1;
    const k = (0.52 + 0.2 * n) * grout;
    return [k * 1.02, k * 0.97, k * 0.9];
  },
  // dark basalt with columnar streaks
  basalt: (u, v) => {
    const n = fbm(u, v, 6, 5, 7), s = fbm(u * 1, v * 0.25, 16, 3, 9);
    const k = 0.16 + 0.12 * n + 0.06 * s;
    return [k, k * 0.97, k * 0.95];
  },
  rock_ceiling: (u, v) => {
    const k = 0.12 + 0.12 * fbm(u, v, 4, 6, 3);
    return [k * 1.05, k, k * 0.95];
  },
  // warm cedar planks along u
  wood: (u, v) => {
    const plank = Math.floor(v * 8), f = (v * 8) % 1;
    const grain = fbm(u * 0.5 + plank * 0.37, f * 0.1, 24, 4, 11 + plank);
    const seam = f < 0.04 ? 0.6 : 1;
    const k = (0.42 + 0.18 * grain) * seam;
    return [k * 1.18, k * 0.86, k * 0.6];
  },
  // teal-grey pool tile, 25 cm mosaic
  pool_tile: (u, v) => {
    const g = Math.min(Math.abs(((u * 8) % 1) - 0.5), Math.abs(((v * 8) % 1) - 0.5));
    const k = g > 0.45 ? 0.5 : 0.62 + 0.08 * fbm(u, v, 32, 2, 5);
    return [k * 0.55, k * 0.8, k * 0.82];
  },
  plaster: (u, v) => {
    const k = 0.62 + 0.06 * fbm(u, v, 8, 4, 21);
    return [k * 1.0, k * 0.95, k * 0.86];
  },
};

export function makeAlbedo(name, size) {
  const f = ALBEDO[name];
  const d = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const c = f(x / size, y / size), i = (y * size + x) * 4;
    d[i] = srgb(c[0]); d[i + 1] = srgb(c[1]); d[i + 2] = srgb(c[2]); d[i + 3] = 255;
  }
  return { data: d, width: size, height: size };
}

// Tileable water normal map (tangent space, linear)
export function makeWaterNormal(size) {
  const h = new Float32Array(size * size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) h[y * size + x] = fbm(x / size, y / size, 6, 5, 33);
  const d = new Uint8Array(size * size * 4), s = 6.0;
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const hx = h[y * size + ((x + 1) % size)] - h[y * size + ((x - 1 + size) % size)];
    const hy = h[((y + 1) % size) * size + x] - h[((y - 1 + size) % size) * size + x];
    let nx = -hx * s, ny = -hy * s, nz = 1; const l = Math.hypot(nx, ny, nz); nx /= l; ny /= l; nz /= l;
    const i = (y * size + x) * 4;
    d[i] = Math.round((nx * 0.5 + 0.5) * 255); d[i + 1] = Math.round((ny * 0.5 + 0.5) * 255); d[i + 2] = Math.round((nz * 0.5 + 0.5) * 255); d[i + 3] = 255;
  }
  return { data: d, width: size, height: size };
}

// RGBM encode (contract): L = range * (rgb * m)^gamma, stored linear 8-bit (no sRGB transfer).
export function rgbmEncode(rgb, range, gamma) {
  const e = rgb.map((c) => Math.pow(Math.max(0, c) / range, 1 / gamma));
  let m = Math.min(1, Math.max(e[0], e[1], e[2], 1e-6));
  m = Math.ceil(m * 255) / 255;
  return [e[0] / m, e[1] / m, e[2] / m, m].map((c) => Math.round(Math.max(0, Math.min(1, c)) * 255));
}

// Radiance .hdr writer (flat RGBE, no RLE) for UASTC HDR encoding
export function writeHDR(width, height, rgbFloat) {
  const head = Buffer.from(`#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y ${height} +X ${width}\n`);
  const px = Buffer.alloc(width * height * 4);
  for (let i = 0; i < width * height; i++) {
    const r = rgbFloat[i * 3], g = rgbFloat[i * 3 + 1], b = rgbFloat[i * 3 + 2];
    const m = Math.max(r, g, b);
    if (m < 1e-32) continue;
    const e = Math.ceil(Math.log2(m) + 1e-9);
    const sc = 256 / Math.pow(2, e);
    px[i * 4] = Math.min(255, Math.floor(r * sc)); px[i * 4 + 1] = Math.min(255, Math.floor(g * sc)); px[i * 4 + 2] = Math.min(255, Math.floor(b * sc)); px[i * 4 + 3] = e + 128;
  }
  return new Uint8Array(Buffer.concat([head, px]));
}

async function quiet(fn) {
  const log = console.log, warn = console.warn;
  console.log = () => {}; console.warn = () => {};
  try { return await fn(); } finally { console.log = log; console.warn = warn; }
}

// kind: 'srgb' | 'linear' | 'normal'
// etc1s: small downloads (Low-tier albedo); otherwise UASTC LDR 4x4 + zstd.
export async function encodeLDR(img, kind, { etc1s = false } = {}) {
  const opts = {
    isUASTC: !etc1s, generateMipmap: true, needSupercompression: !etc1s,
    ...(etc1s ? { qualityLevel: 160, compressionLevel: 2 } : {}),
    isSetKTX2SRGBTransferFunc: kind === 'srgb', isPerceptual: kind === 'srgb', isNormalMap: kind === 'normal',
    imageDecoder: async () => img,
  };
  return quiet(() => encodeToKTX2(new Uint8Array(1), opts));
}
export async function encodeHDR(hdrBytes) {
  return quiet(() => encodeToKTX2(hdrBytes, { isHDR: true, imageType: 'hdr', generateMipmap: true }));
}
