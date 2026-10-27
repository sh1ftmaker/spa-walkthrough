"""Woven float ring (float_ring): dark woven rattan rings drifting down the B3 lava-tube lazy river.

Identifying features kept at every LOD: dark woven rattan torus; some with a cushion (LOD0-2).

Targets (measured before coding)
  * lookbook 12 (lazy river, people for scale: shoulder width ~0.42 m): the near ring is ~3.1 shoulder widths
    across (~1.3 m outer), the tube is fat, ~0.3 m thick (r_minor ~0.15), the hole ~0.55-0.65 m (a seated
    bather fills it). Near-black woven rattan with a diagonal over-under weave; the near ring carries a
    darker padded roll (cushion) on the inner top rim; the far rings are plain. They float about half
    submerged. sheet-ref-cliff-cavern shows the same rings at distance.
  * Row: r_major 0.55-0.7 m (taken as the OUTER radius, since the proxy is 1.3 x 1.3 x 0.3), r_minor
    0.12-0.18 m, weave pitch, cushion on/off. The proxy height 0.3 caps r_minor at 0.155.
  Built: outer radius 0.56-0.65, r_minor 0.13-0.155 (section slightly flattened, 0.94), 1.12-1.30 m across,
  0.25-0.30 m tall; weave pitch = number of diagonal weave cells round the ring (20 at LOD0).

Construction
  * body: a torus whose minor rings are phase-shifted half a step per major ring (helical, diagonal facets) and
    pushed in / out in a checker (3.5 mm) so the surface reads as a coarse over-under weave; `rope` (woven
    fibre normal) tinted near-black for the dark rattan (bamboo's culm stripes read as bark in r1).
    'banded' style: 3-4 binding bands, strips of the same torus whose rings are
    pushed 8 mm proud and given `rope` (no extra triangles); 'banded' only.
  * cushion (style 'cushion', or cushion=True): a padded roll on the inner top rim, `noren` black variant.
  * grab loops ('banded'): two rope loops on the outer side.
  * Closed solids throughout. Water is runtime: obj['kz_waterline'] = 0.45 h.
LOD1: 12 x 7 torus, cushion 10 x 4, bands kept, loops 4-sided. LOD2: 6 x 4 torus + 6 x 3 cushion, no loops.
LOD3: 5 x 3 torus (30 tris).
Animation: rigid (drift with the current, slow spin, bob): obj['kz_anim']. Lighting: probe (moving).

Parameters (build kwargs)
  style    cushion | plain | banded   (cycles with the seed)
  r_major  outer radius 0.55-0.7 (seeded 0.56-0.65)     r_minor 0.12-0.18 (seeded 0.13-0.155)
  pitch    weave cells round the ring 16-24 (LOD0)      cushion True/False (default by style)
Seeds change: style (cushion roll / plain fat ring / rope bands + grab loops), outer radius, tube
thickness, section flattening, band count and placement, weave phase.
"""
import math

from mathutils import Vector

import genlib
import kzgeo_common as C

ASSET = 'float_ring'
FEATURES = ['dark woven rattan torus', 'cushion (some)']
STYLES = ['cushion', 'plain', 'banded']
RATTAN_TINT = (0.12, 0.095, 0.075)


def torus(mb, R, rm, nM, nm, mi, ell=0.94, z0=0.0, weave=0.0, band_rings=(), mi_band=None, band_out=0.0,
          phase0=0.0, twist=True):
    """closed torus about Z; minor rings phase-shifted half a step per major ring (a helical wrap: diagonal
    facets like wound rattan; needs an even nM);
    checker radial offset `weave`; the face strip after each ring in band_rings (its two rings pushed out
    by band_out) gets slot mi_band."""
    bm = mb.bm
    rings = []
    for i in range(nM):
        a = phase0 + 2 * math.pi * i / nM
        ca, sa = math.cos(a), math.sin(a)
        ph = (math.pi / nm) * i if twist else 0.0          # helical wrap: half a step per ring
        ring = []
        for j in range(nm):
            b = ph + 2 * math.pi * j / nm
            pushed = i in band_rings or (i - 1) % nM in band_rings
            rr = rm + (weave if (i + j) % 2 == 0 and not pushed else -weave if not pushed else 0.0) + (band_out if pushed else 0.0)
            x = R + rr * math.cos(b)
            ring.append(bm.verts.new((x * ca, x * sa, z0 + rr * ell * math.sin(b))))
        rings.append(ring)
    faces = []
    for i in range(nM):
        A, B = rings[i], rings[(i + 1) % nM]
        sh = (nM // 2) % nm if (twist and i == nM - 1) else 0     # the helix closes with an index shift
        for j in range(nm):
            f = bm.faces.new((A[j], B[(j + sh) % nm], B[(j + 1 + sh) % nm], A[(j + 1) % nm]))
            f.material_index = mi_band if (mi_band is not None and i in band_rings) else mi
            faces.append(f)
    return faces


def build(lod, seed, style=None, r_major=None, r_minor=None, pitch=None, cushion=None):
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'ring')
    Ro = max(0.5, min(0.7, r_major)) if r_major else g.uniform(0.56, 0.65)
    rm = max(0.12, min(0.18, r_minor)) if r_minor else g.uniform(0.13, 0.155)
    if style == 'plain' and not r_minor:
        rm = min(0.155, rm + 0.012)
    ell = g.uniform(0.9, 0.97)
    phase0 = g.uniform(0, math.pi)
    R = Ro - rm
    cush = (style == 'cushion') if cushion is None else bool(cushion)
    gb = C.rng(seed, 'bands')
    nbands = gb.choice([3, 4]) if style == 'banded' else 0
    band_a0 = gb.uniform(0, 1)
    pitch_n = int(pitch) if pitch else 20
    pitch_n += pitch_n % 2

    mb = genlib.MeshBuilder()
    m_body = mb.slot('rope', tint=RATTAN_TINT, roughness_offset=0.1, normal_strength=1.6)
    m_band = mb.slot('rope', tint=(0.55, 0.47, 0.38))
    m_cush = mb.slot('noren', variant='black', normal_strength=1.2)

    nM, nm = C.lod_pick(lod, (pitch_n, 10), (12, 7), (6, 4), (5, 3))
    bands = []
    if nbands and lod <= 1:
        for k in range(nbands):
            bands.append(int(round((band_a0 + k / nbands) * nM)) % nM)
    torus(mb, R, rm, nM, nm, m_body, ell=ell, z0=rm * ell, weave=C.lod_pick(lod, 0.0035, 0.0025, 0.0),
          band_rings=set(bands), mi_band=m_band, band_out=C.lod_pick(lod, 0.008, 0.006),
          phase0=phase0, twist=lod <= 1)

    if cush and lod <= 2:
        rc = rm * 0.42
        Rc = R - rm * 0.38
        zc = rm * ell * 1.62
        cM, cm = C.lod_pick(lod, (16, 6), (10, 4), (6, 3))
        torus(mb, Rc, rc, cM, cm, m_cush, ell=0.8, z0=zc, weave=0.0, twist=False, phase0=phase0)

    if style == 'banded' and lod <= 1:
        for k in range(2):
            a = phase0 + math.pi * k + math.pi / 2
            ca, sa = math.cos(a), math.sin(a)
            pts = []
            n = C.lod_pick(lod, 7, 5)
            for i in range(n):
                t = math.pi * i / (n - 1)
                off = 0.08 * math.cos(t)
                out = Ro - 0.01 + 0.05 * math.sin(t)
                z = rm * ell * 1.05 - 0.035 * math.sin(t)
                pts.append(Vector((out * ca - off * sa, out * sa + off * ca, z)))
            C.tube(mb, pts, [0.011] * n, m_band, sides=C.lod_pick(lod, 6, 4), cap0=True, cap1=True)

    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o, smooth_angle=80)
    H = genlib.bbox(o)['h']
    C.set_json_props(o, kz_waterline=round(H * 0.45, 3),
                     kz_anim=dict(type='rigid', what='drift with the current along the lazy-river path, slow yaw '
                                  'spin, bob', spin_deg_s=6.0, bob_amp_m=0.025, bob_period_s=3.2,
                                  roll_deg=2.0, follows='kz_water_path of the channel'),
                     kz_params=dict(style=style, r_major=round(Ro, 3), r_minor=round(rm, 3), cushion=cush,
                                    bands=nbands, pitch=pitch_n))
    return o
