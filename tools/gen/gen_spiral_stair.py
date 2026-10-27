"""Spiral Stair (drum) and Lava Stair helix: ONE TURN (or `turns`) of a carved stone helix round an open core.

Identifying features kept at every LOD: helical carved stone treads round an open core (lift well / slide
shaft, not part of the asset), a continuous curved bronze-capped timber rail with lantern posts on the core
side, landings, and a landing door (lit shoji portal) at each level stop.

Styles (variants)
  drum  Spiral Stair round the main lift well (ref-spiral-stair, ref-b1-lobby, sheet-vs-stairs #3): wet basalt
        treads on a massive carved-rock soffit band, low carved kerb on the wall side, kumiko-baluster rail.
        Layout defaults: r_walk 5.6, width 2.6, pitch 14.6 m per turn, hand -1, doors on the wall at r 8.
  lava  Lava Stair round the glass slide shaft (sheet-ref-deep #02): the same treads and rail code on a hinoki
        fascia stringer with bronze cantilever brackets, and timber balconies bowing out over the shaft at
        every 2nd landing. Defaults: r_walk 7.2, width 2.2, pitch 19.06, hand +1, wall r 9.
  Default style: 'drum', except seed % 3 == 0 -> 'lava' (so the 3-seed check sheet shows both); pass style=.

Geometry / construction
  * Per turn: N = round(pitch / 0.17) risers; a landing after every `landing_every` risers (13 -> 44 landings
    over the 100 m main stair, as in layout.json), the first item of every turn is a landing at walk z 0, so
    turns stack (turn k at z + k * pitch). Treads are 0.29 m at the walk line; landing length closes the turn.
  * Treads: closed carved blocks (riser, rounded/chamfered nosing lip overhanging the tread below, underside on
    the pitch line so the stepped profile shows from the well). Seeded: some treads split into two stones,
    worn / tilted tops, lip size. Landings: 2-3 paving slabs, extended to the wall at door landings.
  * Soffit (drum): helical band swept under the treads, noise-displaced and facet-quantised (carved rock),
    with a bead moulding under the nosings; depth and roughness are seeded.
  * Rail: posts (chamfered hinoki, bronze shoe and cap) at `post_spacing`; continuous helical top rail
    (timber body, bronze cap), bottom rail, infill by `rail` style: kumiko (vertical bars) | ring (bronze ring
    per bay) | timber (mid rail) | bronze (bronze tube rails). Lantern (andon box or hex) on every
    `lantern_every`-th post. Rail height is smoothed through the landings (continuous rail).
  * Door: hinoki portal (posts, lintel, kasagi or lit transom by seed), two lit shoji leaves with kumiko bars,
    bronze threshold and two bracket lanterns, on the wall chord at `r_wall`, facing the axis.

Parameters build(lod, seed, **p)
  style          drum | lava
  r_walk, width  walk-line radius and tread width (or radius_in / radius_out)    r_wall  door wall radius
  pitch          rise per turn (m)                    turns    turns built (default 1; fractions ok)
  riser          nominal riser 0.17                   tread    0.29 at the walk line
  landing_every  risers between landings (13)         landing_z  walk-z list of door landings (default [0.0])
  rail           kumiko | ring | timber | bronze       lantern_every  lantern on every n-th post (3)
  post_spacing   1.3-1.9 m (seeded)                   hand     +1 climbs clockwise seen from above, -1 ccw
  a0             bearing (deg, clockwise from +Y) of the start landing / first door (default 180: the -Y side,
                 so the door faces a viewer at +Y through the open core)
  balconies      lava: every n-th landing gets a balcony (2); 0 = none
Pivot: helix axis; z = 0 is the lowest point of the soffit; the walk surface of the start landing is at
obj['kz_stair']['z_walk0'] above the pivot. +Y = front (viewer side, opposite the default door).
Custom properties: kz_stair (JSON: z_walk0, pitch, N, riser, tread, landing length, r_in/r_out/r_walk,
landings [bearing deg, walk z], doors), kz_lights (lantern and door glow centres, colour, watts).
Budget per turn: 9000 / 3600 / 1080 / 200. Animation: none. Lighting: lightmap (+ emissive lantern_andon).
"""
import json
import math

from mathutils import Matrix, Vector

import genlib
import kzgeo_bridge_arched as kg
import kzgeo_lift_drum as G
import kzgeo_spiral_stair as S

ASSET = 'spiral_stair'
FEATURES = ['helical carved stone treads round an open core', 'continuous curved bronze-capped timber rail',
            'lantern posts', 'landings', 'landing door per level']
STYLES = {
    'drum': dict(r_walk=5.6, width=2.6, pitch=14.6, hand=-1, r_wall=8.0, rail='kumiko'),
    'lava': dict(r_walk=7.2, width=2.2, pitch=19.06, hand=1, r_wall=9.0, rail='timber'),
}
WARM = (1.0, 0.58, 0.26)
LODS = {
    0: dict(seg=0.5, rseg=0.56, lrseg=1.0, tread='full', split=True, sof=7, bal=0.3, kerb=8, post='oct', psp=1.0, strut=1),
    1: dict(seg=0.85, rseg=0.85, lrseg=1.7, tread='block', split=False, sof=5, bal=0.75, kerb=4, post='box', psp=1.25, strut=1),
    2: dict(seg=1.6, rseg=1.6, lrseg=0, tread='coarse', coarse_n=44, split=False, sof=3, bal=0, kerb=0, post='box2', psp=1.7, strut=0),
    3: dict(seg=2.4, rseg=2.6, lrseg=0, tread='coarse', split=False, sof=0, bal=0, kerb=0, post=None, psp=0, strut=0),
}
# the Lava Stair turn is ~1.4x longer than the drum turn (r 7.2, pitch 19 m): coarser sweeps keep it on budget
LAVA = {
    0: dict(seg=0.6, rseg=0.62, lrseg=1.5, psp=1.0, post='box', kerb=4, tread='nolip', strut=0),
    1: dict(seg=1.2, rseg=1.1, lrseg=2.4, psp=1.5, tread='ribbon', strut=0),
    2: dict(seg=2.2, rseg=2.2, psp=2.2, tread='coarse', coarse_n=48),
    3: dict(rseg=3.4, coarse_n=12),
}


def _params(seed, p):
    r = genlib.rng(seed, ASSET)
    style = p.get('style') or ('lava' if seed % 3 == 0 else 'drum')
    D = dict(STYLES[style])
    for k in ('r_walk', 'width', 'pitch', 'hand', 'r_wall', 'rail'):
        if p.get(k) is not None:
            D[k] = p[k]
    if p.get('radius_in') is not None and p.get('radius_out') is not None:
        D['r_walk'] = (p['radius_in'] + p['radius_out']) / 2
        D['width'] = p['radius_out'] - p['radius_in']
    if p.get('rail') is None and style == 'drum':
        D['rail'] = 'ring' if seed % 3 == 2 else 'kumiko'
    D['style'] = style
    D['turns'] = float(p.get('turns') or 1.0)
    D['riser'] = float(p.get('riser') or 0.17)
    D['tread'] = float(p.get('tread') or 0.29)
    # landing rhythm varies by seed (12 / 13 / 14 risers); pass landing_every=13 to match layout.json exactly
    D['landing_every'] = int(p.get('landing_every') or [13, 13, 12, 14][seed % 4])
    D['landing_z'] = list(p.get('landing_z') if p.get('landing_z') is not None else [0.0])
    # posts 1.3-1.5 m apart, a post lantern on every 2nd post (~2.6-3 m of rail, as in ref-spiral-stair)
    D['lantern_every'] = int(p.get('lantern_every') or 2)
    D['post_spacing'] = float(p.get('post_spacing') or r.uniform(1.3, 1.5))
    D['andon_every'] = int(p.get('andon_every') if p.get('andon_every') is not None else (4 if style == 'drum' else 0))
    D['a0'] = math.radians(p.get('a0', 180.0))
    D['balconies'] = int(p.get('balconies', 3 if style == 'lava' else 0))
    # seeded shape choices
    # carved rock band: shallow (0.8-0.95 m) on odd seeds, deep (1.45-1.7 m) on even seeds
    D['sof_depth'] = (r.uniform(0.8, 0.95) if seed % 2 else r.uniform(1.45, 1.7)) if style == 'drum' else r.uniform(0.5, 0.65)
    D['sof_rough'] = r.uniform(0.05, 0.11)
    D['sof_freq'] = r.uniform(0.6, 1.1)
    D['sof_belly'] = r.uniform(0.0, 0.35)            # how much the underside bulges below the inner face
    D['split_p'] = r.uniform(0.12, 0.3) * (1.0 if style == 'drum' else 0.3)
    D['lip'] = r.uniform(0.06, 0.09)
    D['ov'] = r.uniform(0.04, 0.06)
    # wall side: low kerb, or (1 seed in 3) a waist-high carved parapet
    D['kerb_h'] = r.uniform(0.14, 0.3) if r.random() < 0.65 else r.uniform(0.75, 0.95)
    D['lamp'] = 'tall'
    D['door_style'] = 'kasagi' if seed % 2 else 'transom'
    D['land_slabs'] = r.choice([2, 3])
    D['bal_phase'] = r.choice([1, 2])
    D['wet'] = round(r.uniform(0.7, 1.0), 2)
    D['tint'] = (1.0, r.uniform(0.95, 1.02), r.uniform(0.92, 1.0))
    D['rng'] = r
    return D


def _plan(D):
    rw = D['r_walk']
    C = 2 * math.pi * rw
    N = max(8, int(round(D['pitch'] / D['riser'])))
    riser = D['pitch'] / N
    k = max(3, D['landing_every'])
    nl = 1 + (N - 1) // k
    nt = N - nl
    tread = D['tread']
    Ld = (C - nt * tread) / nl
    if Ld < 1.2:
        Ld = 1.2
        tread = (C - nl * Ld) / nt
    dt, dl = tread / rw, Ld / rw
    items = []
    th = 0.0
    total = int(round(N * D['turns']))
    for i in range(total):
        li = i % N
        kind = 'land' if li % k == 0 else 'tread'
        d = dl if kind == 'land' else dt
        items.append(dict(kind=kind, i=i, th0=th, th1=th + d, z=i * riser))
        th += d
    return dict(N=N, riser=riser, tread=tread, Ld=Ld, items=items, th_end=th, C=C)


class Line:
    """piecewise-linear functions of the unrolled angle th: underside (pitch) line L and smoothed rail line"""

    def __init__(self, items, riser, tt):
        self.k = []
        for it in items:
            self.k.append((it['th0'], it['z'] - riser - tt))
        last = items[-1]
        self.k.append((last['th1'], last['z'] - tt))
        self.riser, self.tt = riser, tt

    def L(self, th):
        k = self.k
        if th <= k[0][0]:
            return k[0][1] + (th - k[0][0]) * (k[1][1] - k[0][1]) / (k[1][0] - k[0][0])
        if th >= k[-1][0]:
            return k[-1][1] + (th - k[-1][0]) * (k[-1][1] - k[-2][1]) / (k[-1][0] - k[-2][0])
        lo, hi = 0, len(k) - 1
        while hi - lo > 1:
            m = (lo + hi) // 2
            if k[m][0] <= th:
                lo = m
            else:
                hi = m
        (a, za), (b, zb) = k[lo], k[hi]
        return za + (zb - za) * (th - a) / (b - a)

    def nose(self, th):
        """walk surface (approx.): the line through the nosings"""
        return self.L(th) + self.riser + self.tt

    def rail(self, th, H, w):
        """rail height H above the nosing line, smoothed over +-w radians"""
        n = 8
        wts = [n + 1 - abs(i - n) for i in range(2 * n + 1)]
        return sum(c * self.nose(th + w * (i - n) / n) for i, c in enumerate(wts)) / sum(wts) + H


def build(lod, seed, **p):
    D = _params(seed, p)
    C = dict(LODS[min(lod, 3)])
    if D['style'] == 'lava':
        C.update(LAVA[min(lod, 3)])
    P = _plan(D)
    r = D['rng']
    hand, a0 = D['hand'], D['a0']
    bear = lambda th: a0 + hand * th
    rw, W = D['r_walk'], D['width']
    r_in, r_out = rw - W / 2, rw + W / 2
    r_wall = max(D['r_wall'], r_out + 0.3)
    TT = 0.2 if D['style'] == 'drum' else 0.16
    ln = Line(P['items'], P['riser'], TT)
    th_end = P['th_end']
    mb = genlib.MeshBuilder()
    bm = mb.bm
    bm.faces.layers.float_vector.new('kz_n')
    M = dict(
        # merged / flat LOD1-3 tread tops mirror the key light (they read white): rougher, darker stone there
        stone=mb.slot('paving', wetness=D['wet'], wear=0.35, tint=D['tint'], scale=1.6) if lod == 0 else
        mb.slot('paving', wetness=0.35, wear=0.35, tint=(0.62, 0.6, 0.58), scale=1.6, roughness_offset=0.35),
        land=mb.slot('paving', wetness=D['wet'], wear=0.5, tint=(0.9, 0.88, 0.85), scale=2.2) if lod == 0 else
        mb.slot('paving', wetness=0.35, wear=0.5, tint=(0.58, 0.56, 0.54), scale=2.2, roughness_offset=0.35),
        rock=mb.slot('basalt_wet', wetness=0.8, normal_strength=1.4, tint=(0.85, 0.83, 0.8), scale=3.0),
        wood=mb.slot('hinoki', variant='stained'),
        rail=mb.slot('hinoki', tint=(0.3, 0.14, 0.08), roughness_offset=-0.2),   # dark red polished timber (dark_timber-like tint)          # polished handrail timber (sheen fixed in the library)
        washi=mb.slot('washi_backlit', emissive_level=1.5),
        bronze=mb.slot('bronze', wear=0.3, roughness_offset=0.05),
        bronze_dk=mb.slot('bronze', wear=0.1, roughness_offset=0.1),
        glow=mb.slot('washi_backlit', emissive_level=2.0),          # lit shoji door leaves / transom
    )
    info = dict(lights=[], doors=[])
    # ---------------------------------------------------------------- landing roles
    lands = [it for it in P['items'] if it['kind'] == 'land']
    door_l = set()
    for zq in D['landing_z']:
        best = min(lands, key=lambda it: abs(it['z'] - zq))
        door_l.add(best['i'])
    bal_l = set()
    if D['style'] == 'lava' and D['balconies']:
        for n, it in enumerate(lands):
            if it['i'] not in door_l and n % D['balconies'] == D['bal_phase'] and it['th1'] < th_end - 0.05:
                bal_l.add(it['i'])
    gaps = []          # rail gaps (unrolled th ranges) at balconies
    for it in P['items']:
        if it['i'] in bal_l:
            gaps.append((it['th0'] + 0.15 / r_in, it['th1'] - 0.15 / r_in))
    # ---------------------------------------------------------------- treads + landings
    _treads(mb, bm, M, C, lod, D, P, ln, bear, r_in, r_out, r_wall, door_l, TT)
    # ---------------------------------------------------------------- soffit / stringer
    if C['sof'] == 0:
        pass
    elif D['style'] == 'drum':
        _soffit_rock(mb, bm, M, C, lod, D, P, ln, bear, r_in, r_out, seed)
    else:
        _stringer_timber(mb, bm, M, C, lod, D, P, ln, bear, r_in, r_out, r_wall)
    # ---------------------------------------------------------------- outer kerb
    if C['kerb']:
        _kerb(mb, bm, M, C, lod, D, P, ln, bear, r_out)
    # ---------------------------------------------------------------- rail
    _rail(mb, bm, M, C, lod, D, P, ln, bear, r_in + 0.11, gaps, info)
    for it in P['items']:
        if it['i'] in bal_l:
            _balcony(mb, bm, M, C, lod, D, it, ln, bear, r_in, info)
        if it['i'] in door_l:
            _door(mb, bm, M, C, lod, D, it, bear, r_wall, info)
    o = mb.to_object(ASSET)
    G.fix_normals(o)
    # pivot: lowest soffit point at z = 0
    zmin = min(v.co.z for v in o.data.vertices)
    for v in o.data.vertices:
        v.co.z -= zmin
    for L in info['lights']:
        L['pos'][2] = round(L['pos'][2] - zmin, 3)
    genlib.finish(o)
    kg.uv_grain(o, [M['wood'], M['rail']])
    kg.uv_unit(o, [M['glow']])
    S.uv_slabs(o, [M['stone'], M['land']], seed)
    o['kz_lights'] = json.dumps(info['lights'])
    o['kz_stair'] = json.dumps(dict(
        style=D['style'], z_walk0=round(-zmin, 3), pitch=D['pitch'], turns=D['turns'], risers_per_turn=P['N'],
        riser=round(P['riser'], 4), tread_walk=round(P['tread'], 3), landing_len=round(P['Ld'], 3),
        r_in=round(r_in, 3), r_out=round(r_out, 3), r_walk=rw, r_wall=r_wall, hand=hand, a0_deg=math.degrees(a0),
        landings=[[round(math.degrees(bear((it['th0'] + it['th1']) / 2)) % 360, 1), round(it['z'], 3)] for it in lands],
        doors=info['doors']))
    o['kz_params'] = json.dumps({k: v for k, v in D.items() if k not in ('rng',)}, default=str)
    return o


# ==================================================================== treads
def _bears(b0, b1, step_r, r):
    n = max(1, int(math.ceil(abs(b1 - b0) * r / step_r)))
    return [b0 + (b1 - b0) * i / n for i in range(n + 1)]


def _treads(mb, bm, M, C, lod, D, P, ln, bear, r_in, r_out, r_wall, door_l, TT):
    r = D['rng']
    hand = D['hand']
    riser = P['riser']
    mode = C['tread']
    if mode == 'coarse':
        _coarse(bm, M, D, P, ln, bear, r_in, r_out, C.get('coarse_n', 17), under=(lod == 3))
        return
    for it in P['items']:
        b0, b1 = bear(it['th0']), bear(it['th1'])
        z = it['z']
        zb0, zb1 = ln.L(it['th0']), ln.L(it['th1'])
        if it['kind'] == 'land':
            ro = r_wall + 0.05 if it['i'] in door_l else r_out
            if mode == 'ribbon':
                _ribbon(bm, M['land'], r_in, ro, b0, b1, z, zb0, zb1, D, it, ln, bear, arc=True)
                continue
            ns = D['land_slabs'] if lod == 0 else 1
            cuts = [it['th0'] + (it['th1'] - it['th0']) * k / ns for k in range(ns + 1)]
            for k in range(ns):
                t0, t1 = cuts[k] + (0.006 if k else 0), cuts[k + 1] - (0.006 if k < ns - 1 else 0)
                bs = _bears(bear(t0), bear(t1), 0.45 if lod == 0 else 0.9, ro)
                th_of = lambda b: (b - D['a0']) / hand
                S.polar_block(bm, r_in, ro, bs, z + (r.uniform(-0.006, 0.006) if lod == 0 else 0.0),
                              lambda b: ln.L(th_of(b)), M['land'])
            continue
        if mode == 'ribbon':
            _ribbon(bm, M['stone'], r_in, r_out, b0, b1, z, zb0, zb1, D, it, ln, bear)
            continue
        full = mode in ('full', 'nolip')
        ov = D['ov'] if mode == 'full' else 0.0
        lip = D['lip'] if mode == 'full' else 0.0
        ch = (0.035 if mode == 'full' else 0.03) if full else 0.0
        jit = None
        if full:
            jit = {'r0': (r.uniform(-0.012, 0.004), r.uniform(-0.006, 0.006)),
                   'r1': (r.uniform(-0.008, 0.004), r.uniform(-0.006, 0.006))}
        if C['split'] and r.random() < D['split_p']:
            rs = r.uniform(r_in + 0.35 * (r_out - r_in), r_in + 0.7 * (r_out - r_in))
            for (ra, rb) in ((r_in, rs - 0.006), (rs + 0.006, r_out)):
                S.tread_block(bm, ra, rb, b0, b1, hand, z + r.uniform(-0.006, 0.004), zb0, zb1, M['stone'],
                              ov=ov, lip=lip, ch=ch, jit=jit)
        else:
            S.tread_block(bm, r_in, r_out, b0, b1, hand, z, zb0, zb1, M['stone'], ov=ov, lip=lip, ch=ch, jit=jit)


def _ribbon(bm, mi, r0, r1, b0, b1, z, zb0, zb1, D, it, ln, bear, arc=False):
    """LOD2: open stepped ribbon - riser quad, top quad(s), inner end face (normals recorded)."""
    bs = _bears(b0, b1, 1.4, r1) if arc else [b0, b1]
    up = Vector((0, 0, 1))
    zprev = z - D.get('riser_', 0.17)
    # riser (from the previous top down to the underside it is hidden anyway; build from zb0 to z)
    vs = [bm.verts.new(S.polar(r0, b0, zb0 + 0.17)), bm.verts.new(S.polar(r1, b0, zb0 + 0.17)),
          bm.verts.new(S.polar(r1, b0, z)), bm.verts.new(S.polar(r0, b0, z))]
    f = bm.faces.new(vs); f.material_index = mi
    tdir = (S.polar(1, b0 - D['hand'] * 0.01) - S.polar(1, b0)).normalized()
    G.intend(bm, f, tdir)
    for j in range(len(bs) - 1):
        vs = [bm.verts.new(S.polar(r0, bs[j], z)), bm.verts.new(S.polar(r1, bs[j], z)),
              bm.verts.new(S.polar(r1, bs[j + 1], z)), bm.verts.new(S.polar(r0, bs[j + 1], z))]
        f = bm.faces.new(vs); f.material_index = mi; G.intend(bm, f, up)
    # inner end face: the stepped profile seen from the well
    pts = [(bs[0], zb0)] + [(b, z) for b in bs] + [(bs[-1], zb1)]
    vs = [bm.verts.new(S.polar(r0, b, zz)) for b, zz in pts]
    f = bm.faces.new(vs); f.material_index = mi
    bm_ = (bs[0] + bs[-1]) / 2
    G.intend(bm, f, -S.polar(1, bm_))


def _coarse(bm, M, D, P, ln, bear, r_in, r_out, per_turn=16, under=False):
    """LOD3 (lava LOD2): `per_turn` big steps as an open ribbon (top, riser, inner face) - the helix silhouette."""
    n = max(4, int(round(per_turn * D['turns'])))
    th_end = P['th_end']
    up = Vector((0, 0, 1))
    for j in range(n):
        t0, t1 = th_end * j / n, th_end * (j + 1) / n
        b0, b1 = bear(t0), bear(t1)
        z = ln.nose(t0 + (t1 - t0) * 0.5)
        zb0, zb1 = ln.L(t0) - 0.3, ln.L(t1) - 0.3
        zp = ln.nose(t0 - (t1 - t0) * 0.5) if j else zb0
        vs = [bm.verts.new(S.polar(r_in, b0, zp)), bm.verts.new(S.polar(r_out, b0, zp)),
              bm.verts.new(S.polar(r_out, b0, z)), bm.verts.new(S.polar(r_in, b0, z))]
        f = bm.faces.new(vs); f.material_index = M['stone']
        G.intend(bm, f, (S.polar(1, b0 - D['hand'] * 0.01) - S.polar(1, b0)).normalized())
        vs = [bm.verts.new(S.polar(r_in, b0, z)), bm.verts.new(S.polar(r_out, b0, z)),
              bm.verts.new(S.polar(r_out, b1, z)), bm.verts.new(S.polar(r_in, b1, z))]
        f = bm.faces.new(vs); f.material_index = M['stone']; G.intend(bm, f, up)
        # inner face incl. the carved band below (one quad + the step triangle)
        vs = [bm.verts.new(S.polar(r_in, b0, zb0 - D['sof_depth'] * 0.8)), bm.verts.new(S.polar(r_in, b1, zb1 - D['sof_depth'] * 0.8)),
              bm.verts.new(S.polar(r_in, b1, z)), bm.verts.new(S.polar(r_in, b0, z))]
        f = bm.faces.new(vs); f.material_index = M['rock']; G.intend(bm, f, -S.polar(1, (b0 + b1) / 2))
        if under:   # LOD3: underside ribbon to the wall, so the soffit reads as one continuous band
            dd = D['sof_depth'] * 0.8
            vs = [bm.verts.new(S.polar(r_in, b0, zb0 - dd)), bm.verts.new(S.polar(r_out + 0.3, b0, zb0 + 0.25)),
                  bm.verts.new(S.polar(r_out + 0.3, b1, zb1 + 0.25)), bm.verts.new(S.polar(r_in, b1, zb1 - dd))]
            f = bm.faces.new(vs); f.material_index = M['rock']; G.intend(bm, f, Vector((0, 0, -1)))


# ==================================================================== soffit
def _soffit_rock(mb, bm, M, C, lod, D, P, ln, bear, r_in, r_out, seed):
    th_end = P['th_end']
    Dp = D['sof_depth']
    belly = D['sof_belly']
    seg = C['seg']
    n = max(8, int(math.ceil(th_end * r_in / seg)))
    ths = sorted(set([th_end * j / n for j in range(n + 1)] +
                     [it['th0'] for it in P['items'] if it['kind'] == 'land'] +
                     [it['th1'] for it in P['items'] if it['kind'] == 'land' and it['th1'] <= th_end]))
    # clean near-duplicates
    t2 = [ths[0]]
    for t in ths[1:]:
        if t - t2[-1] > 0.25 * seg / r_in:
            t2.append(t)
    if t2[-1] < th_end:
        t2.append(th_end)
    ths = t2
    samples = [(bear(t), r_in, ln.L(t)) for t in ths]
    W = r_out - r_in
    if C['sof'] >= 7:
        sec = [(0.05, 0.03), (-0.02, -0.07), (0.02, -0.2), (0.04, -Dp * 0.65),
               (0.25, -Dp), (W * 0.55, -Dp * (1.0 + belly) + 0.1), (W + 0.35, -Dp * 0.55), (W + 0.35, 0.03)]
        mis = [M['stone'], M['stone'], M['rock'], M['rock'], M['rock'], M['rock'], M['rock'], M['rock']]
        keep = (0, 1, 2, 7)
    elif C['sof'] >= 5:
        sec = [(0.05, 0.03), (-0.01, -0.12), (0.04, -Dp * 0.65), (0.25, -Dp), (W * 0.55, -Dp * (1.0 + belly) + 0.1),
               (W + 0.35, -Dp * 0.55), (W + 0.35, 0.03)]
        mis = [M['stone']] + [M['rock']] * 6
        keep = (0, 1, 6)
    else:
        sec = [(0.04, 0.03), (0.04, -Dp), (W * 0.6, -Dp * (1.0 + belly * 0.6)), (W + 0.3, 0.03)]
        mis = [M['rock']] * 4
        keep = (0, 3)
    amp = D['sof_rough'] * (1.0 if lod == 0 else 0.7 if lod == 1 else 0.0)
    disp = S.rock_disp(amp, D['sof_freq'], seed, keep=keep) if amp > 0 else None
    S.hsweep(bm, samples, sec, mis, caps=True, disp=disp)


def _stringer_timber(mb, bm, M, C, lod, D, P, ln, bear, r_in, r_out, r_wall):
    """lava: hinoki fascia beam under the tread ends + stone underside slab + bronze cantilever brackets"""
    th_end = P['th_end']
    n = max(8, int(math.ceil(th_end * r_in / C['seg'])))
    ths = [th_end * j / n for j in range(n + 1)]
    samples = [(bear(t), r_in, ln.L(t)) for t in ths]
    Dp = D['sof_depth']
    W = r_out - r_in
    if lod <= 1:
        fas = [(-0.06, 0.05), (-0.06, -0.07), (-0.05, -Dp + 0.06), (0.0, -Dp), (0.16, -Dp), (0.16, 0.05)]
        mis = [M['bronze'], M['wood'], M['wood'], M['wood'], M['wood'], M['wood']]
        if lod == 1:
            fas = [(-0.06, 0.05), (-0.06, -Dp), (0.16, -Dp), (0.16, 0.05)]
            mis = M['wood']
        S.hsweep(bm, samples, fas, mis)
        slab = [(0.16, 0.04), (0.16, -0.22), (W + 0.6, -0.34), (W + 0.6, 0.04)]
        S.hsweep(bm, samples, slab, M['rock'])
    else:
        S.hsweep(bm, samples, [(-0.05, 0.05), (-0.05, -Dp), (W + 0.5, -0.3), (W + 0.5, 0.05)], [M['wood'], M['rock'], M['rock'], M['rock']])
    # bronze cantilever brackets from the wall up to the fascia (one per post bay at LOD0, every 2nd at LOD1)
    if C['strut']:
        sp = D['post_spacing'] * (1 if lod == 0 else 2)
        nb = int(th_end * r_in / sp)
        for j in range(nb):
            t = (j + 0.5) * sp / r_in
            b = bear(t)
            zl = ln.L(t)
            a = S.polar(r_in + 0.06, b, zl - Dp + 0.02)
            c = S.polar(min(r_wall - 0.1, r_out + 0.55), b, zl - Dp - 0.85)
            G.strut(bm, a, c, 0.07, 0.09, M['bronze_dk'])


def _kerb(mb, bm, M, C, lod, D, P, ln, bear, r_out):
    th_end = P['th_end']
    n = max(8, int(math.ceil(th_end * r_out / (C['seg'] * 2.0))))
    ths = [th_end * j / n for j in range(n + 1)]
    H = D['kerb_h']
    samples = [(bear(t), r_out, ln.L(t)) for t in ths]
    if C['kerb'] >= 8:
        sec = [(-0.22, 0.0), (-0.22, 0.0)]
    hfun = [ln.rail(t, H, 0.25) - ln.L(t) for t in ths]
    if C['kerb'] >= 8:
        sec = lambda j: [(-0.2, 0.0), (-0.22, hfun[j] - 0.05), (-0.17, hfun[j]), (0.3, hfun[j]), (0.3, 0.0)]
        mis = [M['stone'], M['stone'], M['stone'], M['rock'], M['rock']]
    else:
        sec = lambda j: [(-0.2, 0.0), (-0.2, hfun[j]), (0.3, hfun[j]), (0.3, 0.0)]
        mis = [M['stone'], M['stone'], M['rock'], M['rock']]
    S.hsweep(bm, samples, sec, mis)


# ==================================================================== rail
def _in_gap(t, gaps):
    return any(a <= t <= b for a, b in gaps)


def _rail_runs(th_end, gaps):
    runs, a = [], 0.0
    for g0, g1 in sorted(gaps):
        if g0 > a:
            runs.append((a, g0))
        a = g1
    if a < th_end:
        runs.append((a, th_end))
    return runs


def _rail(mb, bm, M, C, lod, D, P, ln, bear, rr, gaps, info):
    th_end = P['th_end']
    style = D['rail']
    H = 1.06
    sm = 1.6 / rr
    bronze, wood = M['bronze'], M['rail']
    if lod == 3:
        # rail band (top rail + dark infill read as one band) for the silhouette
        # 0.15 m rail band, double-sided (seen from the well and from across it)
        for t0, t1 in _rail_runs(th_end, gaps):
            n = max(2, int(round(16 * (t1 - t0) / (2 * math.pi))))
            ths = [t0 + (t1 - t0) * j / n for j in range(n + 1)]
            for j in range(n):
                ta, tb = ths[j], ths[j + 1]
                for sgn in (1, -1):
                    vs = [bm.verts.new(S.polar(rr, bear(ta), ln.rail(ta, H - 0.11, sm))), bm.verts.new(S.polar(rr, bear(tb), ln.rail(tb, H - 0.11, sm))),
                          bm.verts.new(S.polar(rr, bear(tb), ln.rail(tb, H + 0.04, sm))), bm.verts.new(S.polar(rr, bear(ta), ln.rail(ta, H + 0.04, sm)))]
                    f = bm.faces.new(vs if sgn > 0 else vs[::-1]); f.material_index = wood
                    G.intend(bm, f, -S.polar(1, bear((ta + tb) / 2)) * sgn)
        # two lantern glow quads per turn
        for t in [th_end * (j + 0.5) / 2 for j in range(max(1, int(2 * D['turns'])))]:
            b = bear(t); z = ln.rail(t, H + 0.1, sm)
            nrm = -S.polar(1, b)
            tg = Vector((nrm.y, -nrm.x, 0)) * 0.14
            c = S.polar(rr - 0.12, b, z)
            vs = [bm.verts.new(c - tg), bm.verts.new(c + tg), bm.verts.new(c + tg + Vector((0, 0, 0.3))), bm.verts.new(c - tg + Vector((0, 0, 0.3)))]
            f = bm.faces.new(vs); f.material_index = M['glow']; G.intend(bm, f, nrm)
        return
    # --- posts
    sp = D['post_spacing'] * C['psp']
    hel = math.hypot(rr, D['pitch'] / (2 * math.pi))
    dth = sp / hel
    posts = []
    t = dth * 0.35
    while t < th_end - dth * 0.2:
        if not _in_gap(t, gaps):
            posts.append(t)
        t += dth
    # also posts at the ends of every gap
    for g0, g1 in gaps:
        posts += [g0, g1]
    posts.sort()
    pw = 0.18 if D['style'] == 'lava' else (0.13 if style != 'bronze' else 0.09)
    for n_, t in enumerate(posts):
        b = bear(t)
        c = S.polar(rr, b)
        z0 = ln.L(t) + 0.15
        zt = ln.rail(t, H, sm) + 0.07
        pmat = bronze if style == 'bronze' else wood
        if C['post'] == 'oct':
            kg.post_oct(mb, c.x, c.y, z0, zt, pw, pmat, chamfer=0.3)
            # bronze shoe and cap
            mb.cylinder((c.x, c.y, zt + 0.035), radius=pw * 0.78, radius2=pw * 0.45, depth=0.07, mi=bronze, segs=4,
                        rot=(0, 0, -b + math.pi / 4))
        elif C['post'] == 'box':
            mb.box((c.x, c.y, (z0 + zt) / 2), (pw, pw, zt - z0), pmat, rot=(0, 0, -b))
            mb.cylinder((c.x, c.y, zt + 0.03), radius=pw * 0.75, radius2=pw * 0.4, depth=0.06, mi=bronze, segs=4,
                        rot=(0, 0, -b + math.pi / 4), cap=False)
        else:
            mb.cylinder((c.x, c.y, (z0 + zt) / 2), radius=pw * 0.7, depth=zt - z0, mi=pmat, segs=4,
                        rot=(0, 0, -b + math.pi / 4), cap=False)
        if (n_ % D['lantern_every']) == 0 and not any(abs(t - g) < 1e-6 for gg in gaps for g in gg):
            _lantern(mb, bm, M, lod, D, Vector((c.x, c.y, zt + 0.07)), b, info)
        if D['andon_every'] and lod == 0 and n_ % D['andon_every'] == 1:
            # low floor andon on the tread at the well edge, just behind the post
            ta = t + 0.35 / rr
            ca = S.polar(rr + 0.28, bear(ta))
            za = _tread_top(P, ta)
            mb.box((ca.x, ca.y, za + 0.015), (0.2, 0.2, 0.03), M['bronze_dk'], rot=(0, 0, -bear(ta)))
            mb.box((ca.x, ca.y, za + 0.03 + 0.12), (0.16, 0.16, 0.24), M['washi'], rot=(0, 0, -bear(ta)))
            mb.cylinder((ca.x, ca.y, za + 0.3), radius=0.15, radius2=0.03, depth=0.06, mi=M['bronze'], segs=4,
                        rot=(0, 0, -bear(ta) + math.pi / 4), cap=lod == 0)
            info['lights'].append(dict(pos=[round(ca.x, 3), round(ca.y, 3), round(za + 0.15, 3)], color=list(WARM), watts=6))
    # --- rails (continuous helical sweeps, split only at balcony gaps)
    for t0, t1 in _rail_runs(th_end, gaps):
        n = max(2, int(math.ceil((t1 - t0) * hel / C['rseg'])))
        ths = [t0 + (t1 - t0) * j / n for j in range(n + 1)]
        top = [(bear(t), rr, ln.rail(t, H, sm)) for t in ths]
        # fat round 0.13 m timber handrail + separate 0.03 m bronze cap strip (sheet-vs-stairs RAIL DETAIL); the
        # section is set in the vertical radial plane, so heights are stretched by 1/cos(slope) to stay round
        kz = math.hypot(1.0, D['pitch'] / (2 * math.pi * rr) * 1.15)
        if style == 'bronze':
            nc, rad = (8, 0.035) if lod == 0 else (4, 0.035)
            mis = bronze
        else:
            nc, rad = {0: 9, 1: 6, 2: 4}[lod], 0.065
            mis = wood
        sec = [(rad * math.cos(2 * math.pi * k / nc + math.pi / 2), rad * kz * math.sin(2 * math.pi * k / nc + math.pi / 2)) for k in range(nc)]
        S.hsweep(bm, top, sec, mis)
        if style != 'bronze' and lod <= 1:
            cap = [(-0.015, rad * kz - 0.006), (0.015, rad * kz - 0.006), (0.0, rad * kz + 0.018)]
            S.hsweep(bm, top, cap, bronze)
        if lod <= 1:
            nb = max(2, int(math.ceil((t1 - t0) * hel / C['lrseg'])))
            ths2 = [t0 + (t1 - t0) * j / nb for j in range(nb + 1)]
            lows = [0.2]
            if style == 'bronze':
                lows = [0.16, 0.55]
            elif style == 'timber':
                lows = [0.45]
            for zlow in lows:
                bot = [(bear(t), rr, ln.L(t) + P['riser'] + 0.2 + zlow) for t in ths2]
                bsec = [(-0.035, -0.03), (0.035, -0.03), (0.035, 0.03), (-0.035, 0.03)]
                if style == 'bronze':
                    bsec = [(-0.02, -0.02), (0.02, -0.02), (0.0, 0.025)]
                S.hsweep(bm, bot, bsec, bronze if style == 'bronze' else wood)
        elif style == 'kumiko' or True:
            # LOD2: dark infill band (reads as the baluster screen at distance)
            nb = max(2, n)
            ths2 = [t0 + (t1 - t0) * j / nb for j in range(nb + 1)]
            for j in range(nb):
                ta, tb = ths2[j], ths2[j + 1]
                zl = lambda t: ln.L(t) + P['riser'] + 0.4
                zh = lambda t: ln.rail(t, H - 0.08, sm)
                vs = [bm.verts.new(S.polar(rr, bear(ta), zl(ta))), bm.verts.new(S.polar(rr, bear(tb), zl(tb))),
                      bm.verts.new(S.polar(rr, bear(tb), zh(tb))), bm.verts.new(S.polar(rr, bear(ta), zh(ta)))]
                f = bm.faces.new(vs); f.material_index = M['bronze_dk']; G.intend(bm, f, -S.polar(1, bear((ta + tb) / 2)))
        # --- infill
        if (lod <= 1 and style == 'kumiko') or (lod == 0 and style == 'ring'):
            sp_b = C['bal']
            if style == 'kumiko':
                nbal = int((t1 - t0) * rr / sp_b)
                for j in range(nbal):
                    t = t0 + (j + 0.5) * sp_b / rr
                    if any(abs((t - pt) * rr) < 0.1 for pt in posts):
                        continue
                    b = bear(t)
                    za = ln.L(t) + P['riser'] + 0.42
                    zb_ = ln.rail(t, H - 0.07, sm)
                    c = S.polar(rr, b)
                    mb.cylinder((c.x, c.y, (za + zb_) / 2), radius=0.017, depth=zb_ - za, mi=bronze if lod == 0 else wood,
                                segs=4, rot=(0, 0, -b + math.pi / 4), cap=False)
            else:
                for a_, b_ in zip(posts[:-1], posts[1:]):
                    if b_ < t0 or a_ > t1 or _in_gap((a_ + b_) / 2, gaps):
                        continue
                    t = (a_ + b_) / 2
                    b = bear(t)
                    zc = (ln.rail(t, H - 0.07, sm) + ln.L(t) + P['riser'] + 0.42) / 2
                    rad = min(0.28, (b_ - a_) * rr * 0.32)
                    pts = []
                    nseg = 6
                    tg = Vector((math.cos(b), -math.sin(b), 0)) * D['hand']
                    cc = S.polar(rr, b, zc)
                    for k in range(nseg):
                        a = 2 * math.pi * k / nseg
                        pts.append(cc + tg * rad * math.cos(a) + Vector((0, 0, rad * math.sin(a))))
                    ring_sweep(bm, pts, 0.018, bronze, S.polar(1, b))


def _tread_top(P, t):
    for it in P['items']:
        if it['th0'] <= t < it['th1']:
            return it['z']
    return P['items'][-1]['z']


def ring_sweep(bm, pts, th, mi, nrm):
    """closed square-section ring through pts (a loop), section th, in the plane with normal nrm"""
    n = len(pts)
    rings = []
    c = sum(pts, Vector()) / n
    for p in pts:
        rad = (p - c).normalized()
        rings.append([bm.verts.new(p + rad * th), bm.verts.new(p + nrm * th - rad * th * 0.5), bm.verts.new(p - nrm * th - rad * th * 0.5)])
    for j in range(n):
        A, B = rings[j], rings[(j + 1) % n]
        for k in range(3):
            k2 = (k + 1) % 3
            f = bm.faces.new((A[k], A[k2], B[k2], B[k])); f.material_index = mi


def _lantern(mb, bm, M, lod, D, base, b, info, scale=1.0):
    """post lantern: 0.22 x 0.45 m washi_backlit body, bronze base plate, corner posts (LOD0) and a flared bronze
    roof cap with finial (ref-spiral-stair / sheet-vs-stairs #3); records the light"""
    s, h = 0.22 * scale, 0.45 * scale
    x, y, z = base
    rot = -b
    body = M['washi']
    if lod >= 2:
        mb.box((x, y, z + h / 2), (s, s, h), body, rot=(0, 0, rot))
    elif lod == 1:
        mb.box((x, y, z + h / 2), (s, s, h), body, rot=(0, 0, rot))
        mb.cylinder((x, y, z + h + 0.04), radius=s * 0.85, radius2=0.02, depth=0.08, mi=M['bronze'], segs=4,
                    rot=(0, 0, rot + math.pi / 4), cap=False)
    else:
        mb.box((x, y, z + 0.015), (s + 0.04, s + 0.04, 0.03), M['bronze'], rot=(0, 0, rot))
        mb.box((x, y, z + 0.03 + (h - 0.06) / 2), (s, s, h - 0.06), body, rot=(0, 0, rot))
        mb.box((x, y, z + h - 0.015), (s + 0.05, s + 0.05, 0.03), M['bronze'], rot=(0, 0, rot))
        mb.cylinder((x, y, z + h + 0.055), radius=(s + 0.1) * 0.75, radius2=0.02, depth=0.11, mi=M['bronze'], segs=4,
                    rot=(0, 0, rot + math.pi / 4), cap=lod == 0)
        if lod == 0:
            mb.cylinder((x, y, z + h + 0.13), radius=0.022, radius2=0.0, depth=0.05, mi=M['bronze'], segs=4, cap=False)
    info['lights'].append(dict(pos=[round(x, 3), round(y, 3), round(z + h / 2, 3)], color=list(WARM), watts=14))


# ==================================================================== balcony (lava)
def _balcony(mb, bm, M, C, lod, D, it, ln, bear, r_in, info):
    tm = (it['th0'] + it['th1']) / 2
    b = bear(tm)
    z = it['z']
    half = (it['th1'] - it['th0']) / 2 * r_in - 0.15
    depth = min(1.3, half * 1.05)
    out = S.polar(1, b)                     # radial outward unit
    tg = Vector((out.y, -out.x, 0))
    c = S.polar(r_in + 0.05, b, 0)
    n = 9 if lod == 0 else 6 if lod == 1 else 4 if lod == 2 else 3
    pts = []
    for k in range(n + 1):
        a = math.pi * k / n
        pts.append(c + tg * (half * math.cos(a)) - out * (depth * math.sin(a)))
    poly = [(p.x, p.y) for p in pts]
    mb.poly_prism(poly, z - 0.14, z, M['rail'])
    # brackets under
    if lod <= 1:
        for k in (n // 3, 2 * n // 3) if lod == 0 else (n // 2,):
            p = pts[k]
            G.strut(bm, (p.x, p.y, z - 0.15), S.polar(r_in + 0.05, bear(tm), z - D['sof_depth'] - 0.6) + tg * (p - c).dot(tg),
                    0.08, 0.1, M['rail'])
    # railing on the edge
    if lod <= 2:
        H = 1.0
        for k in range(0, n + 1, 3):
            p = pts[k]
            mb.box((p.x, p.y, z + H / 2), (0.12, 0.12, H + 0.06), M['rail'], rot=(0, 0, -b))
            if lod == 0:
                mb.cylinder((p.x, p.y, z + H + 0.06), radius=0.09, radius2=0.05, depth=0.06, mi=M['bronze'], segs=4, rot=(0, 0, -b + math.pi / 4))
        prof = [(-0.05, -0.06), (0.05, -0.06), (0.05, 0.02), (0.0, 0.05), (-0.05, 0.02)] if lod < 2 else [(-0.05, -0.06), (0.05, -0.06), (0.0, 0.04)]
        kg.sweep(mb, [Vector((p.x, p.y, z + H)) for p in pts], prof, M['rail'])
        if lod == 0:
            kg.sweep(mb, [Vector((p.x, p.y, z + 0.45)) for p in pts], [(-0.03, -0.03), (0.03, -0.03), (0.03, 0.03), (-0.03, 0.03)], M['rail'])
            p = pts[n // 2]
            _lantern(mb, bm, M, lod, D, Vector((p.x, p.y, z + H + 0.06)), b, info)


# ==================================================================== door
def _door(mb, bm, M, C, lod, D, it, bear, r_wall, info):
    tm = (it['th0'] + it['th1']) / 2
    b = bear(tm)
    z = it['z']
    Md = G.frame(b + math.pi, -r_wall, z)          # local +y = inward (towards the axis), x = tangent
    w, h = 1.8, 2.4
    wood, bronze, glow = M['wood'], M['bronze'], M['glow']
    bev = 0.012 if lod == 0 else 0.0
    if lod == 3:
        G.obox(bm, Md, (0, 0.02, h / 2 + 0.1), (w + 0.5, 0.06, h + 0.35), wood)
        G.quad(bm, Md, -w / 2, w / 2, 0.0, h, 0.06, glow)
        info['doors'].append(dict(bearing=round(math.degrees(b) % 360, 2), walk_z=round(z, 3), w=w, h=h))
        return
    # posts, lintel, kasagi / transom
    for sx in (-1, 1):
        G.obox(bm, Md, (sx * (w / 2 + 0.11), 0.11, (h + 0.35) / 2), (0.22, 0.22, h + 0.35), wood, bevel=bev)
        if lod <= 1:
            G.obox(bm, Md, (sx * (w / 2 + 0.11), 0.11, 0.08), (0.27, 0.27, 0.16), bronze)
    G.obox(bm, Md, (0, 0.11, h + 0.12), (w + 0.22, 0.2, 0.18), wood, bevel=bev)
    if D['door_style'] == 'kasagi' or lod >= 2:
        G.obox(bm, Md, (0, 0.13, h + 0.42), (w + 1.1, 0.28, 0.13), wood, bevel=bev)
        if lod <= 1:
            for sx in (-1, 1):
                G.obox(bm, Md, (sx * (w / 2 + 0.55), 0.13, h + 0.42), (0.06, 0.3, 0.15), bronze)
            G.obox(bm, Md, (0, 0.12, h + 0.3), (0.3, 0.16, 0.12), wood)       # centre strut (tsuka)
    else:
        G.obox(bm, Md, (0, 0.06, h + 0.38), (w, 0.04, 0.3), glow)
        G.obox(bm, Md, (0, 0.11, h + 0.56), (w + 0.5, 0.22, 0.08), bronze)
        if lod == 0:
            for k in range(1, 6):
                G.bar(bm, Md, (-w / 2 + w * k / 6, h + 0.23), (-w / 2 + w * k / 6, h + 0.53), 0.025, 0.03, wood, y=0.08)
    # leaves: lit shoji with kumiko
    for sx in (-1, 1):
        cx = sx * w / 4
        G.obox(bm, Md, (cx, 0.04, h / 2 + 0.02), (w / 2 - 0.02, 0.04, h - 0.04), glow)
        if lod <= 1:
            lw = w / 2 - 0.02
            fw = 0.06
            for xx in (cx - lw / 2 + fw / 2, cx + lw / 2 - fw / 2):
                G.bar(bm, Md, (xx, 0.04), (xx, h), fw, 0.04, wood, y=0.06)
            for zz in (0.04 + 0.1, h - 0.03):
                G.bar(bm, Md, (cx - lw / 2, zz), (cx + lw / 2, zz), 0.08 if zz < 1 else fw, 0.04, wood, y=0.06)
            if lod == 0:
                for k in (1, 2):
                    xx = cx - lw / 2 + lw * k / 3
                    G.bar(bm, Md, (xx, 0.2), (xx, h - 0.06), 0.022, 0.025, wood, y=0.06)
                for k in range(1, 6):
                    zz = 0.2 + (h - 0.26) * k / 6
                    G.bar(bm, Md, (cx - lw / 2 + fw, zz), (cx + lw / 2 - fw, zz), 0.022, 0.025, wood, y=0.06)
                G.bar(bm, Md, (cx - sx * (lw / 2 - 0.09), 1.0), (cx - sx * (lw / 2 - 0.09), 1.3), 0.03, 0.04, bronze, y=0.1)
    G.obox(bm, Md, (0, 0.2, 0.025), (w + 0.5, 0.4, 0.05), bronze)
    info['lights'].append(dict(pos=[round(x, 3) for x in (Md @ Vector((0, 0.3, h / 2)))], color=list(WARM), watts=60))
    if lod <= 1:
        for sx in (-1, 1):
            G.obox(bm, Md, (sx * (w / 2 + 0.11), 0.3, 1.85), (0.05, 0.2, 0.05), bronze)
            pw = Md @ Vector((sx * (w / 2 + 0.11), 0.42, 1.75))
            _lantern(mb, bm, M, lod, D, pw, b, info, scale=0.8)
    info['doors'].append(dict(bearing=round(math.degrees(b) % 360, 2), walk_z=round(z, 3), w=w, h=h))
