"""Shoji and sliding panel component (pavilions, treatment rooms, suites, pods, shoji bays).

Identifying features kept at every LOD: a kumiko grid over glowing washi in a hinoki frame (shoji), the solid
fusuma, the open tategoshi lattice and the yukimi glazed panel; LOD2 keeps the grid as front strips, LOD3 is a
lit slab (grid meant to come from a baked texture, see the report).

Targets (measured):
  * refs/gen/mat-hinoki-washi.png (close-up, door frame ~0.12 m for scale): stiles ~0.03 m on face, kumiko ~8-9 mm,
    panes ~0.20 w x 0.25 h (cols 4 x rows 6-7 on a 0.9 x 1.8 panel), paper warm amber, frame dark oiled hinoki.
  * lookbook 05 mist corridor (woman ~1.6 m for scale): bay shoji 0.85-0.95 m wide x 1.8-1.9 m, 4 x 7 grid, a
    0.25-0.3 m wooden koshi board at the bottom on some bays.
  * lookbook 21 private suite: tall 4 x 8 shoji (~2.2 m) and a tateshige (dense vertical) variant beside the bed.
  * lookbook 15 obsidian mirror: pavilion with vertical lattice (tategoshi) panels next to plain shoji.
  * Panel thickness 30-34 mm, top rail 40 mm, bottom rail 55-60 mm (proxy 0.9 x 0.05 x 1.8 m).

Parameters (defaults = proxy 0.9 x 0.05 x 1.8):
  w      0.8-1.8 m      panel width
  h      1.5-2.4 m      panel height
  cols, rows            kumiko grid (default from the seeded pattern and the panel size)
  style  shoji | fusuma | lattice | glazed   (default cycles with the seed: seeds 1-4 = the four styles)
  open   0-1            slide fraction: not geometry; recorded as obj['kz_slide'] = {axis [1,0,0], travel m} for the
                        host (the panel slides along local x by open * (w - stile) on its track)
Seeds change: style (cycle), kumiko pattern (masu square cells / yokoshige dense horizontals / tateshige dense
verticals / 3-4 x 5-8 grids), koshi kick board on / off and height, fusuma pull shape and side, fusuma paper
tone, lattice bar pitch / width / tie count / kick board, glazed glass fraction and muntin.

Materials: hinoki wet_oiled (frame, kumiko, lattice), washi_backlit (lit shoji paper, emissive), washi (fusuma
face, warm tint), lacquer_black (fusuma frame; lacquer_dark mottling read as speckle on the 3 cm fuchi), glass_clear (yukimi pane), bronze smooth (hikite pull).
Lighting: lightmap + emissive; obj['kz_lights'] = one area entry per lit paper field (behind the panel, facing +y).
Paper is two-sided (front and back quads 1 mm apart); kumiko sit on the +y face.  Animation: none.
"""
import genlib
import kzgeo_bridge_arched as kg
import kzgeo_common as C
import kzgeo_shoji_panel as KS
from mathutils import Matrix

ASSET = 'shoji_panel'
FEATURES = ['kumiko grid over glowing washi', 'hinoki frame', 'fusuma / lattice / glazed variants']
STYLES = ['shoji', 'fusuma', 'lattice', 'glazed']
PATTERNS = ['masu', 'yokoshige', 'tateshige', 'grid']


def params(seed, w, h, style=None, cols=None, rows=None):
    """all shape parameters, drawn before any LOD branch (one stream per concern)"""
    style = style or C.cycle(seed, STYLES)
    g = C.rng(seed, 'panel')
    P = dict(style=style, T=0.032, stile=0.03, top=0.04, bot=0.058, kw=0.0085, kd=0.016, mid=0.028)
    iw, ih = w - 2 * P['stile'], h - P['top'] - P['bot']
    pat = C.pick(seed, 'pattern', PATTERNS) if seed != 1 else 'grid'
    P['pattern'] = pat
    P['koshi'] = 0.0 if C.pick(seed, 'koshi', [0, 1, 1]) == 0 else round(g.uniform(0.2, 0.32), 3)
    if style == 'glazed':
        P['koshi'] = 0.0
    fh = ih - P['koshi'] - (P['mid'] if P['koshi'] else 0)
    if pat == 'masu':
        c = max(3, round(iw / 0.2)); rr = max(4, round(fh / (iw / c)))
    elif pat == 'yokoshige':
        c = g.choice([2, 3]); rr = max(8, round(fh / 0.11))
    elif pat == 'tateshige':
        c = max(6, round(iw / 0.11)); rr = g.choice([3, 4])
    else:
        c = max(3, round(iw / g.uniform(0.2, 0.24))); rr = max(5, round(fh / g.uniform(0.24, 0.28)))
    P['cols'], P['rows'] = int(cols or c), int(rows or rr)
    # fusuma
    P['pull'] = C.pick(seed, 'pull', ['round', 'square'])
    P['pull_side'] = C.pick(seed, 'pull_side', [1, -1])
    P['pull_z'] = round(h * g.uniform(0.44, 0.5), 3)
    P['washi_tint'] = C.pick(seed, 'washi', [(1.0, 0.93, 0.8), (0.86, 0.8, 0.7), (0.92, 0.86, 0.74)])
    # lattice
    P['bar_w'] = round(g.uniform(0.02, 0.026), 4)
    gap = g.uniform(0.03, 0.045)
    P['nbars'] = max(8, round(iw / (P['bar_w'] + gap)))
    P['ties'] = g.choice([1, 2])
    P['kick'] = round(g.uniform(0.18, 0.3), 3) if C.pick(seed, 'kick', [0, 1]) else 0.0
    # glazed
    P['glass'] = round(g.uniform(0.36, 0.52), 3)
    P['muntin'] = C.pick(seed, 'muntin', [False, True])
    P['glow'] = round(g.uniform(0.85, 1.0), 2)
    return P


def build(lod, seed, w=None, h=None, cols=None, rows=None, style=None, open=0.0, **_):
    p = genlib.proxy(ASSET)
    w = float(w or p['w'])
    h = float(h or p['h'])
    P = params(seed, w, h, style, cols, rows)
    mb = genlib.MeshBuilder()
    mats = dict(wood=mb.slot('hinoki', variant='wet_oiled'),
                paper=mb.slot('washi_backlit', emissive_level=P['glow']),
                washi=mb.slot('washi', tint=P['washi_tint'], normal_strength=0.35),
                lacquer=mb.slot('lacquer_black'),
                glass=mb.slot('glass_clear'),
                metal=mb.slot('bronze', variant='smooth'))
    lit = KS.panel_into(mb, Matrix.Identity(4), w, h, P['style'], mats, lod, P)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    if lod <= 1:
        kg.uv_grain(o, [mats['wood'], mats['lacquer']])
    lights = [C.light_entry(((a + b) / 2, -0.15, (z0 + z1) / 2), color_k=2400, watts=round(18 * (b - a) * (z1 - z0), 1),
                            kind='area', normal=[0, 1, 0], size=[round(b - a, 3), round(z1 - z0, 3)])
              for a, b, z0, z1 in lit]
    C.set_json_props(o, kz_lights=lights, kz_slide=dict(axis=[1, 0, 0], travel=round(float(open) * (w - P['stile']), 3)),
                     kz_params={k: v for k, v in P.items() if not isinstance(v, tuple)},
                     kz_flicker=[mats['paper']] if lit else [])
    return o
