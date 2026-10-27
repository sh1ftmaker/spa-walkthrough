"""Mist Steps water stair (stair_cascade): one flight of wide polished basalt steps with a water sheet
sliding over every nosing, a stepped side run-off channel, and timber lantern-post rails on both sides.

Concepts: refs/gen/ref-mist-steps.png (hero: ~12-14 m wide flight of black wet basalt treads, white
water curtains over every nosing, glossy wet treads, dark timber balustrade with square andon lanterns
on taller posts every ~3 posts, rock + small falls at the left side); lookbook 33 (B1 plan C4 'Mist
Steps down to B2': flight ~13 m wide, ~25-30 m long incl. landings, measured at 20 m grid = 150 px);
lookbook 34 (B2 plan C3 'Mist Steps up to B1', ~10-12 m wide, run of ~20 m to the restaurant deck).
Row: 13 x 30 m run, 20 m drop for 2 flights -> one flight (this generator) = 10 m drop, ~15 m run.

Targets (one flight, defaults): width 13.0 m overall (stone surface 11.2 m + channel 0.6 m + kerbs),
drop 10 m, riser 0.17 m -> 59 risers, going 0.26 m (seeded 0.26-0.30), nosing radius 0.04 m,
water sheet 8 mm, kerb 0.32 m wide standing 0.18 m above the nosing line, handrail at 0.95 m,
lantern posts 1.55 m with 0.28 x 0.50 m andon heads (w:h 0.56) every third post (~2.3 m spacing).
Scale check (ref-mist-steps): a 0.17 m riser against the 1.0 m balustrade = 1:6, matches the image.

Construction: the stair surface is ONE continuous zig-zag strip (tread -> rounded nosing -> riser) swept
across the width in columns. The wet lane (all but 0.5 m dry margins) is raised by `sheet` (water
depth, 0-20 mm), its nosing + riser faces carry the `waterfall` slot (the curtain over each nosing:
pushed 15-25 mm out from the stone) and its treads a polished wet basalt slot that the runtime flow
shader scrolls along (kz_anim). Nosings wobble +-3 cm (smooth noise along x) so the steps read as
hand-laid slabs, not an extrusion. The run-off channel is a stepped chute 0.25 m below the steps
between an inner and outer kerb; its floor is the `waterfall` slot (running water).
The underside is open: the flight sits in the cavern rock (place model supplies the ground).

Parameters:
  width     4-14 m overall (default by style: 13 / 13 / 9)
  drop      vertical drop of this flight (default 10.0)
  riser     0.17 (n = round(drop / riser), riser re-fitted)
  going     0.26-0.30 (seeded)
  nosing_r  0.02-0.06 (default 0.04)
  sheet     water sheet depth 0-0.02 m (default 0.008)
  channel_w 0.3-1.0 m (default 0.6)
  channels  'right' | 'both' | 'left'
  landings  list of fractions of the flight where a 2.4 m landing breaks it (e.g. [0.5])
Styles (C.cycle by seed): 1 'right' channel, continuous flight (the ref image); 2 channels both sides
+ one mid landing; 3 narrow 9 m flight, left channel 0.9 m, two landings, deeper sheet.
Seeds change: style (above), going, nosing wobble field, post spacing phase.

Materials (slots by part): tread_wet basalt_wet wet 1.0 rough -0.08 (lane treads, flow shader);
tread_dry basalt_wet 0.75 (margins); riser basalt_wet 0.85; water waterfall emissive 0.35 (curtains,
channel floor); kerb basalt_wet 0.6; timber hinoki dark_timber (posts, rails); iron; paper lantern_andon.
`stepping_stone` (listed in the row) is not used: it renders pale tan (GUIDE 7), the concept is black.

Animation: shader. obj['kz_anim'] = {type: 'shader_flow', slots: [water, tread_wet], attr: 'kz_flow_s'};
float point attribute 'kz_flow_s' = distance (m) along the flow path from the top lip (scroll coord).
Lights: kz_lights at every lantern (2200 K, 25 W). Lightmap: UV1 from genlib.finish.
Budget per flight 6000 / 2400 / 720 / 150.
"""
import math

import bmesh
from mathutils import Vector, noise

import genlib
import kzgeo_common as C

ASSET = 'stair_cascade'
FEATURES = ['wide polished basalt steps', 'water sheet over every nosing', 'side run-off channel',
            'lantern-post rails both sides']
STYLES = ['right', 'both', 'left']
# proposed proxy (assets.json has none for this per-flight generator): default flight incl. lantern tops
PROXY_SHEET = dict(w=13.2, d=22.0, h=13.4)


def layout(seed, width=None, drop=None, riser=None, going=None, nosing_r=None, sheet=None, channel_w=None,
           channels=None, landings=None):
    style = channels or C.cycle(seed, STYLES)
    g = C.rng(seed, 'layout')
    L = dict(style=style)
    L['W'] = width if width is not None else {'right': 13.0, 'both': 13.0, 'left': 9.0}[style]
    L['drop'] = drop if drop is not None else 10.0
    r0 = riser if riser is not None else 0.17
    L['n'] = max(2, round(L['drop'] / r0)); L['riser'] = L['drop'] / L['n']
    L['going'] = going if going is not None else g.uniform(0.26, 0.30)
    L['nr'] = nosing_r if nosing_r is not None else 0.04
    L['sheet'] = sheet if sheet is not None else {'right': 0.008, 'both': 0.008, 'left': 0.014}[style]
    L['cw'] = channel_w if channel_w is not None else {'right': 0.6, 'both': 0.5, 'left': 0.9}[style]
    L['ch'] = {'right': (False, True), 'both': (True, True), 'left': (True, False)}[style]
    L['land'] = landings if landings is not None else {'right': [], 'both': [0.5], 'left': [0.33, 0.67]}[style]
    L['land_d'] = 2.4
    L['off'] = Vector((g.uniform(0, 50), g.uniform(0, 50), g.uniform(0, 50)))
    L['post_phase'] = g.uniform(0.0, 0.6)
    L['kw'], L['ikw'] = 0.32, 0.16          # outer kerb, inner (channel) kerb widths
    # x layout (left -> right)
    x = -L['W'] / 2
    xs = {}
    xs['kerbL'] = (x, x + L['kw']); x += L['kw']
    if L['ch'][0]:
        xs['chL'] = (x, x + L['cw']); x += L['cw']
        xs['ikL'] = (x, x + L['ikw']); x += L['ikw']
    xr = L['W'] / 2
    xs['kerbR'] = (xr - L['kw'], xr); xr -= L['kw']
    if L['ch'][1]:
        xs['chR'] = (xr - L['cw'], xr); xr -= L['cw']
        xs['ikR'] = (xr - L['ikw'], xr); xr -= L['ikw']
    xs['surf'] = (x, xr)
    L['xs'] = xs
    # steps: (y0, going, z_top)
    land_idx = sorted({min(L['n'] - 2, max(1, int(round(f * L['n'])))) for f in L['land']})
    steps, y, z = [], 0.0, L['drop']
    for i in range(L['n']):
        gi = L['land_d'] if i in land_idx else L['going']
        steps.append((y, gi, z))
        y += gi; z -= L['riser']
    L['steps'] = steps; L['y_end'] = y; L['top_land'] = 0.8; L['bot_run'] = 0.8
    return L


def C_up(o, slots):
    """open walking / channel strips: make every connected region of these slots face up (recalc on an
    open strip can pick either side)"""
    bm = bmesh.new(); bm.from_mesh(o.data)
    seen = set()
    for f in bm.faces:
        if f.index in seen or f.material_index not in slots:
            continue
        reg, stack = [], [f]
        seen.add(f.index)
        while stack:
            g = stack.pop(); reg.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen and h.material_index in slots:
                        seen.add(h.index); stack.append(h)
        if sum(g.normal.z * g.calc_area() for g in reg) < 0:
            for g in reg:
                g.normal_flip()
    bm.to_mesh(o.data); bm.free()


def wob(L, x, i, amp=0.03):
    return amp * noise.noise(Vector((x * 0.55, i * 0.83, 0.0)) + L['off'])


def profile(L, lod, wet):
    """zig-zag (y, z, tag) from the top lip to the bottom run-out. tag is the segment that STARTS here."""
    nr, R = L['nr'], L['riser']
    sd = L['sheet'] if wet else 0.0
    out = (0.012 + sd) if wet else 0.0                  # curtain stands proud of the stone
    P = [(-L['top_land'], L['drop'] + sd, 'tread', -1)]
    for i, (y0, gi, z) in enumerate(L['steps']):
        zt = z + sd
        if i > 0:
            P.append((y0 + (0.012 + out if wet else 0.0), zt, 'tread', i))
        if lod == 0:
            P.append((y0 + gi - nr, zt, 'nose', i))
            a = math.radians(45)
            P.append((y0 + gi - nr + (nr + sd) * math.sin(a) + out * 0.5, z - nr + (nr + sd) * math.cos(a), 'nose', i))
            P.append((y0 + gi + out, z - nr, 'riser', i))
        elif lod == 1:
            P.append((y0 + gi - nr, zt, 'nose', i))
            P.append((y0 + gi + out, z - nr, 'riser', i))
        else:
            P.append((y0 + gi + out, zt, 'riser', i))
    zb = L['drop'] - L['n'] * R
    P.append((L['y_end'] + (0.012 + out if wet else 0.0), zb + sd, 'tread', L['n']))
    P.append((L['y_end'] + L['bot_run'], zb + sd, 'end', L['n']))
    return P


def build(lod=0, seed=1, width=None, drop=None, riser=None, going=None, nosing_r=None, sheet=None, channel_w=None,
          channels=None, landings=None):
    L = layout(seed, width, drop, riser, going, nosing_r, sheet, channel_w, channels, landings)
    mb = genlib.MeshBuilder()
    m_wet = mb.slot('basalt_wet', wetness=1.0, roughness_offset=-0.08)
    m_dry = mb.slot('basalt_wet', wetness=0.75)
    m_riser = mb.slot('basalt_wet', wetness=0.85)
    m_water = mb.slot('waterfall', emissive_level=0.35)
    m_kerb = mb.slot('basalt_wet', wetness=0.6)
    m_wood = mb.slot('hinoki', variant='dark_timber')
    m_iron = mb.slot('iron')
    m_paper = mb.slot('lantern_andon', emissive_level=1.0)
    bm = mb.bm
    xs = L['xs']
    sx0, sx1 = xs['surf']
    marg = 0.5
    lane = (sx0 + marg, sx1 - marg)
    lod3 = lod >= 3
    # ---------------------------------------------------------------- stair surface (columns across x)
    nl = C.lod_pick(lod, 4, 1, 1, 1)
    cols = [(sx0, False)]
    if lod == 0:
        cols.append((lane[0] - 0.04, False))
    for k in range(nl + 1):
        cols.append((lane[0] + (lane[1] - lane[0]) * k / nl, True))
    if lod == 0:
        cols.append((lane[1] + 0.04, False))
    cols.append((sx1, False))
    if lod >= 2:          # LOD2/3: margins merge into the lane strip (lane treads stay wet stone)
        cols = [(sx0, True), (sx1, True)]
    stride = 1 if not lod3 else max(1, math.ceil(L['n'] / 10))
    profs = {}
    grid = []
    for x, wet in cols:
        P = profile(L, min(lod, 2), wet)
        if lod3:      # LOD3: the flight as ~12 big steps (same top, bottom, landings)
            P = [(-L['top_land'], L['drop'], 'tread', -1)]
            for i in range(0, L['n'], stride):
                y0, gi, z = L['steps'][i]
                if i > 0:
                    P.append((y0, z, 'tread', i))
                i2 = min(L['n'], i + stride)
                P.append((L['steps'][i2][0] if i2 < L['n'] else L['y_end'], z, 'riser', i))
            zb3 = L['drop'] - L['n'] * L['riser']
            P.append((L['y_end'], zb3, 'tread', L['n'])); P.append((L['y_end'] + L['bot_run'], zb3, 'end', L['n']))
        row = []
        for y, z, t, i in P:
            dy = wob(L, x, i) if (t != 'tread' or True) and 0 <= i < L['n'] and lod <= 1 and t in ('nose', 'riser') else 0.0
            dz = 0.006 * noise.noise(Vector((x * 0.9, i * 1.3, 5.0)) + L['off']) if lod <= 1 and 0 <= i < L['n'] else 0.0
            row.append(bm.verts.new((x, y + dy, z + dz)))
        grid.append((row, P, wet))
    surf_faces = []
    for (A, PA, wa), (B, PB, wb) in zip(grid[:-1], grid[1:]):
        wet = wa and wb
        for j in range(len(A) - 1):
            f = bm.faces.new((A[j], B[j], B[j + 1], A[j + 1]))
            t = PA[j][2]
            if t == 'tread' or t == 'end':
                f.material_index = m_wet if wet else m_dry
            else:
                f.material_index = m_water if wet else m_riser
            surf_faces.append(f)
    # ---------------------------------------------------------------- kerbs (stringers) + channels
    nos = [(-L['top_land'], L['drop'])]
    for i, (y0, gi, z) in enumerate(L['steps']):
        if gi > L['going'] * 1.5:                   # landing: break the pitch line
            nos.append((y0, z + 0.0)); nos.append((y0 + gi, z))
    zb = L['drop'] - L['n'] * L['riser']
    nos.append((L['y_end'], zb)); nos.append((L['y_end'] + L['bot_run'], zb))
    # pitch polyline: top lip, nosing line, bottom
    path = [nos[0], (0.0, L['drop'])]
    for p in nos[1:-2]:
        path.append(p)
    path.append((L['y_end'], zb)); path.append(nos[-1])
    clean = []
    for p in path:
        if not clean or abs(p[0] - clean[-1][0]) > 0.05:
            clean.append(p)
    path = clean

    def kerb(xa, xb, top, bot, mi):
        prof = [(-(xb - xa) / 2, bot), ((xb - xa) / 2, bot), ((xb - xa) / 2, top), (-(xb - xa) / 2, top)]
        if lod >= 2:                      # far LODs: open 3-sided section (the base sits in rock)
            hw = (xb - xa) / 2
            pts = [Vector(((xa + xb) / 2, y, z)) for y, z in path]
            prof = [(-hw, bot), (-hw, top), (hw, top), (hw, bot)] if lod == 2 else [(-hw, bot), (0.0, top), (hw, bot)]
            return C.sweep(mb, pts, prof, mi, up=Vector((0, 0, 1)),
                           caps=False, closed_prof=False)
        if lod == 0:
            c = 0.025
            prof = [(-(xb - xa) / 2, bot), ((xb - xa) / 2, bot), ((xb - xa) / 2, top - c), ((xb - xa) / 2 - c, top),
                    (-(xb - xa) / 2 + c, top), (-(xb - xa) / 2, top - c)]
        pts = [Vector(((xa + xb) / 2, y, z)) for y, z in path]
        return C.sweep(mb, pts, prof, mi, up=Vector((0, 0, 1)))
    ktop = 1.15 if lod3 else 0.18           # LOD3: kerb + balustrade merge into one parapet ridge
    kerb(*xs['kerbL'], ktop, -0.75, m_kerb)
    kerb(*xs['kerbR'], ktop, -0.75, m_kerb)
    for side in ('L', 'R'):
        if 'ik' + side in xs:
            if lod <= 2:
                kerb(*xs['ik' + side], 0.10, -0.75, m_kerb)
            a, b = xs['ch' + side]
            P = profile(L, 2 if lod >= 1 else 0, False)
            if lod >= 2:                      # far LODs: the chute as a ramp along the pitch line
                P = [(y, z, 't', 0) for y, z in path]
            A = [bm.verts.new((a, y, z - 0.25)) for y, z, t, i in P]
            B = [bm.verts.new((b, y, z - 0.25)) for y, z, t, i in P]
            for j in range(len(A) - 1):
                f = bm.faces.new((A[j], B[j], B[j + 1], A[j + 1])); f.material_index = m_water
    # ---------------------------------------------------------------- rails + lantern posts
    lights = []
    # positions along the path (plan length), spacing ~2.3 m
    seglen = [math.hypot(path[k + 1][0] - path[k][0], path[k + 1][1] - path[k][1]) for k in range(len(path) - 1)]
    tot = sum(seglen)

    def at(s):
        for k, sl in enumerate(seglen):
            if s <= sl or k == len(seglen) - 1:
                f = min(1.0, s / sl) if sl > 0 else 0
                return (path[k][0] + (path[k + 1][0] - path[k][0]) * f, path[k][1] + (path[k + 1][1] - path[k][1]) * f)
            s -= sl
    npost = max(3, int(round((tot - 0.4) / 2.3)) + 1)
    sp = [0.2 + (tot - 0.4) * k / (npost - 1) for k in range(npost)]
    for side, (xa, xb) in (('L', xs['kerbL']), ('R', xs['kerbR'])):
        xc = (xa + xb) / 2
        posts = []
        for k, s in enumerate(sp):
            y, z = at(s)
            lantern = (k % 3 == 0) or k == npost - 1
            hp = 1.55 if lantern else 1.08
            ps = 0.13 if lantern else 0.10
            z0 = z + 0.15
            if lod <= 1:
                mb.box((xc, y, z0 + hp / 2), (ps, ps, hp), m_wood)
            elif lod == 2:
                mb.box((xc, y, z0 + hp / 2), (ps, ps, hp), m_wood) if lantern else None
            posts.append((y, z0))
            if lantern:
                if lod <= 2:
                    c = C.lantern_head(mb, (xc, y, z0 + hp - 0.02), dict(iron=m_iron, paper=m_paper), max(lod, 1) if lod < 2 else 2,
                                       size=0.28, height=0.5)
                else:
                    q = [bm.verts.new((xc - 0.15, y, z0 + hp - 0.3)), bm.verts.new((xc + 0.15, y, z0 + hp - 0.3)),
                         bm.verts.new((xc + 0.15, y, z0 + hp + 0.2)), bm.verts.new((xc - 0.15, y, z0 + hp + 0.2))]
                    f = bm.faces.new(q); f.material_index = m_paper
                    c = Vector((xc, y, z0 + hp))
                lights.append(C.light_entry(c, color_k=2200, watts=25))
        # handrail + mid rail follow the kerb top
        rail_pts = [Vector((xc, y, z + 0.15 + 0.95)) for y, z in path]
        mid_pts = [Vector((xc, y, z + 0.15 + 0.5)) for y, z in path]
        if lod <= 1:
            rp = [(-0.045, 0), (0.045, 0), (0.045, 0.05), (0.03, 0.065), (-0.03, 0.065), (-0.045, 0.05)] if lod == 0 else \
                 [(-0.045, 0), (0.045, 0), (0.045, 0.065), (-0.045, 0.065)]
            C.sweep(mb, rail_pts, rp, m_wood)
            C.sweep(mb, mid_pts, [(-0.03, 0), (0.03, 0), (0.03, 0.05), (-0.03, 0.05)], m_wood)
        elif lod == 2:   # LOD2: the balustrade as one thin card band (rail + panel read)
            band = [(xc, y, z + 0.15) for y, z in path]
            lo = [bm.verts.new((x, y, z + 0.35)) for x, y, z in band]
            hi = [bm.verts.new((x, y, z + 1.0)) for x, y, z in band]
            for j in range(len(lo) - 1):
                f = bm.faces.new((lo[j], lo[j + 1], hi[j + 1], hi[j])); f.material_index = m_wood
    # flow coordinate: distance along the flight from the top lip (for the scroll shader)
    lay = bm.verts.layers.float.new('kz_flow_s')
    y0p = -L['top_land']
    for v in bm.verts:
        v[lay] = (v.co.y - y0p) + max(0.0, L['drop'] - v.co.z)
    dx, dy, dz = C.centre_base(mb)
    o = mb.to_object(ASSET)
    C_up(o, {m_wet, m_dry, m_riser, m_water})
    genlib.finish(o)
    for e in lights:
        e['pos'] = [round(e['pos'][0] + dx, 3), round(e['pos'][1] + dy, 3), round(e['pos'][2] + dz, 3)]
    C.set_json_props(o, kz_lights=lights,
                     kz_anim=dict(type='shader_flow', what='water sheet over treads/nosings + channel', slots=[m_water, m_wet],
                                  attr='kz_flow_s', dir=[0, 1, -1], speed_mps=0.6),
                     kz_sheet_depth=L['sheet'],
                     kz_flight=dict(top=[0, round(-L['top_land'] + dy, 3), round(L['drop'] + dz, 3)],
                                    bottom=[0, round(L['y_end'] + L['bot_run'] + dy, 3), round(zb + dz, 3)]),
                     kz_params=dict(style=L['style'], width=L['W'], drop=L['drop'], risers=L['n'], riser=round(L['riser'], 4),
                                    going=round(L['going'], 3), nosing_r=L['nr'], sheet=L['sheet'], channel_w=L['cw'],
                                    landings=L['land']))
    return o
