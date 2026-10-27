"""Carved basalt stele (stele_stone): a rough upright basalt slab on a low base stone, one polished front
face carrying gilt 火山湯 (or 源泉 at the spring) under the bronze-and-gilt Kazan-yu crest.

Target dimensions (row: 0.9 x 0.6 x 2.6 m typical; h 1.4-2.6, w 0.6-0.9; proxy 0.9 x 0.6 x 2.6). No sheet
shows the stele (sheet-mod-landmarks does not exist yet); lookbook 31 / 30 only mark its position, and
22-brand-board gives the mark (gilt mountain with three steam wisps, gilt serif 火山湯 on black stone).
Proportions from the row and from Japanese road-marker stones: slab thickness : width ~ 0.38-0.42,
base stone 1.25-1.4 x the slab width, 0.12-0.2 m tall. 火山湯 glyphs fill ~55 % of the polished panel width.
  road    (seed 1): total h 1.60, slab 0.62 w x 0.24 t, base 0.80 x 0.48 x 0.14, 火山湯 + crest
  summit  (seed 2): total h 2.60, slab 0.80 w x 0.32 t, base 0.90 x 0.58 x 0.20, 火山湯 + crest (the summit
                    marker, lookbook 30). A KAZAN-YU / '+120 m' line was built and dropped: 2700 tris at
                    LOD0 against the 1500 budget (see the report).
  spring  (seed 3): total h 2.00, slab 0.70 w x 0.28 t, base 0.86 x 0.54 x 0.17 in wet basalt, 源泉
                    ("hot-spring source") + crest
Seeds 4-6 repeat the styles with a different crown, taper and rough edge (the crown shape, skew, taper,
side bulge and back narrowing are drawn per seed).

Parameters (build kwargs): style ('road' | 'summit' | 'spring', default cycles with the seed), h (total height
1.4-2.6), w (slab width 0.6-0.9), text (the vertical inscription, default per style), polish (0-1: panel
roughness offset), base (True: base stone).
Construction (kzgeo_stele_stone): body = convex hull of per-level sections (flat polished +Y panel inset
from a rough split rim, bulging sides, narrower rough back, seeded irregular crown); plinth = chamfered
rough hull; crest = bronze lathe roundel with a raised rim + gilt mountain + 3 tube wisps; inscription =
kzgeo_common.text_solid (closed per-contour glyph solids, reads correctly from +Y), gilt, 5 mm relief.
LOD0 6 levels, 9-point crown, glyph solids res 2 (~890 tris for 火山湯). LOD1 4 levels, glyphs as a res-2
front-only decal 1.5 mm proud (no relief walls), 3-sided wisps. LOD2 3 levels, the inscription as unequal
gilt bars, mountain without wisps. LOD3 2 levels + crown, one gilt quad, no crest.
Materials: slab sides / back / crown basalt_dry (cool tint), polished panel obsidian, inscription and mark
gold_leaf, roundel bronze (smooth), base basalt_dry (spring: basalt_wet). Front is +Y.
Animation: none. Lighting: lightmap (UV1 from genlib.finish).
"""
import genlib
import kzgeo_common as C
import kzgeo_stele_stone as S

ASSET = 'stele_stone'
FEATURES = ['rough upright basalt slab', 'polished obsidian front panel', 'gilt vertical 火山湯',
            'bronze crest roundel', 'base stone']
STYLES = ['road', 'summit', 'spring']
TINT = (0.40, 0.47, 0.64)        # basalt_dry library default x 0.75: near-black, cool
STYLE = {
    'road':   dict(h=1.60, w=0.62, t=0.24, bw=0.80, bd=0.48, bh=0.14, text='火山湯', extra=None),
    'summit': dict(h=2.60, w=0.80, t=0.32, bw=0.90, bd=0.58, bh=0.20, text='火山湯', extra='summit'),
    'spring': dict(h=2.00, w=0.70, t=0.28, bw=0.86, bd=0.54, bh=0.17, text='源泉', extra=None),
}


def layout(seed, style, h, w, base):
    st = STYLE[style]
    g = C.rng(seed, ASSET + ':shape')
    gj = C.rng(seed, ASSET + ':jitter')
    H = h if h is not None else st['h']
    W = w if w is not None else st['w']
    k = W / st['w']
    z0 = st['bh'] - 0.03 if base else 0.0
    L = dict(w=W, t=st['t'] * k, z0=z0, h=H - z0, bw=min(0.9, st['bw'] * k), bd=min(0.6, st['bd'] * k),
             rim=g.uniform(0.03, 0.045), margin=g.uniform(0.06, 0.085), shoulder=g.uniform(0.80, 0.88),
             taper=g.uniform(0.04, 0.12), bulge=g.uniform(0.015, 0.035), back=g.uniform(0.82, 0.94),
             ph=g.uniform(0, 6.28), crown_c=g.uniform(0.55, 1.0), skew=g.uniform(-0.5, 0.5),
             panel_b=g.uniform(0.06, 0.10))
    L['crown_jit'] = [gj.uniform(0.0, 0.02) for _ in range(9)]
    L['jit'] = [(gj.uniform(-0.012, 0.012), gj.uniform(-0.012, 0.012), gj.uniform(-0.01, 0.01)) for _ in range(40)]
    return L


def build(lod, seed, style=None, h=None, w=None, text=None, polish=0.8, base=True):
    style = style or C.cycle(seed, STYLES)
    st = STYLE[style]
    text = text or st['text']
    L = layout(seed, style, h, w, base)

    mb = genlib.MeshBuilder()
    m_rough = mb.slot('basalt_dry', tint=TINT)
    m_polish = mb.slot('obsidian', roughness_offset=round(-0.1 * polish, 3))
    m_gilt = mb.slot('gold_leaf')
    m_disc = mb.slot('bronze', variant='smooth')
    m_base = mb.slot('basalt_wet', wetness=0.55, tint=TINT) if style == 'spring' else m_rough

    S.body(mb, L, lod, m_rough, m_polish)
    if base:
        S.plinth(mb, L, lod, m_base)

    # ---- panel layout (front plane y = t/2): crest at the top, inscription below
    yF = L['t'] / 2
    z0, H, W = L['z0'], L['h'], L['w']
    zt = z0 + H * L['shoulder']
    pw = W / 2 * (1 - L['taper']) - L['margin']          # narrowest panel half width (top)
    R = min(0.22 * W, 0.16)
    cz = zt - R * 0.35
    if lod < 3:                                           # LOD3 (80 m+): the crest is sub-pixel; dropped
        S.crest(mb, 0.0, cz, yF, R, lod, m_disc, m_gilt)
    n = len(text)
    top = cz - R - 0.06
    bottom = z0 + L['panel_b'] + 0.10 * H / 2.6 * 1.6
    gap = 1.18
    ch = min(pw * 2 * 0.55, (top - bottom) / (n * gap))
    tz = (top + bottom) / 2 + (top - bottom - n * gap * ch) / 2 * 0.6      # sit a little high
    if lod == 0:
        C.text_solid(mb, text, 0.0, tz, yF, ch, m_gilt, depth=0.005, vertical=True, gap=gap, res=2)
    elif lod == 1:
        S.text_decal(mb, text, 0.0, tz, yF, ch, m_gilt, gap=gap, res=2)
    elif lod == 2:                                        # three unequal gilt bars per line
        for i in range(n):
            zc = tz + ((n - 1) / 2.0 - i) * gap * ch
            C.board(mb, (0.0, yF + 0.002, zc), (ch * (0.95 - 0.12 * (i % 2)), 0.004, ch * 0.8), m_gilt, bevel=0.0)
    else:                                                 # one gilt strip (a single front quad)
        hgt = n * gap * ch
        bm = mb.bm
        vs = [bm.verts.new((x, yF + 0.0015, z)) for x, z in ((ch * 0.45, tz - hgt * 0.45), (-ch * 0.45, tz - hgt * 0.45),
                                                             (-ch * 0.45, tz + hgt * 0.45), (ch * 0.45, tz + hgt * 0.45))]
        f = bm.faces.new(vs); f.normal_update()
        if f.normal.y < 0:
            f.normal_flip()
        f.material_index = m_gilt

    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    C.set_json_props(o, kz_params=dict(style=style, text=text, h=round(L['z0'] + L['h'], 3), w=round(W, 3),
                                       t=round(L['t'], 3), base=base))
    return o
