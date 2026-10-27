"""Carved seat block (seat_block_carved) for the geyser plaza ring (b3_geyser): a square, dark, hewn basalt
block with a carved wave relief on its outward face, raised on a recessed plinth with a warm light strip
glowing under its edge.

Targets
  * lookbook 14 (geyser plaza, crop .scratch/op22/c14.png): blocks ring the pool on a stone kerb; each is a
    rough-hewn near-black block, w:h ~ 2.1-2.4 (front), slightly irregular arrises, a flat seat top; the
    outward face carries 4-5 parallel copper-coloured wave lines breaking around a central curl (about
    70 % of the face width, 65 % of its height); a warm strip glows in the shadow gap at the base.
    The bathers behind give ~1.3 x 0.6 m, but they stand farther back, so the row size governs.
  * refs/gen/sheet-mod-water.png #1 (geyser pool, 8 m): ~12 blocks around the rim, each with a carved
    circular/wave motif and a lantern between pairs.
  * Row: w 1.2-1.8, h 0.6-0.9, typical 1.6 x 1.0 x 0.9 (= proxy). Built: seed 1 1.60 x 0.95 x 0.80;
    other seeds w 1.25-1.75, d 0.80-0.98, h 0.62-0.88. Plinth 55 mm tall, inset 40 mm under the block
    edge; the strip is its upper 30 mm. Carving: V-ridges 22 mm wide, 7 mm proud, inlaid bronze.

Parts (LOD0): hewn block (noisy rounded-rect loft, chamfered foot, rounded top shoulder, flat top),
carved relief on the +Y face, stone plinth, glowing strip on all four sides of the plinth.

Styles (cycle with the seed):  1 'wave'      concept 14: 6 swells breaking round a 2.6-turn curl
                               2 'seigaiha'  row's pattern: 3-arc scales, rows hide the row behind
                               3 'wave'      mirrored curl, 7 swells, lower and wider block
  carving='plain' gives an uncarved block (row parameter).
Seeds change: style, w / d / h, corner radius and roughness, curl side, swell count.

Parameters (build kwargs)
  w 1.2-1.8, d 0.8-1.0, h 0.6-0.9 (m); carving 'wave' | 'seigaiha' | 'plain'; light_strip True | False;
  back (bool, default False): carve the -Y face too (+~1000 tris at LOD0; over budget, for hero spots).

Materials: basalt_dry roughness_offset -0.15 (block and plinth; the library entry is near-black now),
bronze smooth (the inlaid relief lines: the concept's lines read copper), lantern_andon_plain
emissive_level 0.8 (strip). Animation: none. Lighting: lightmap + emissive; obj['kz_lights'] = two
warm low point lights at the front and back strips.

LOD: LOD1 coarser outline, half the line points, same pattern; LOD2 a 3-ring block, the pattern as flat
bronze ribbons (outer arcs only for seigaiha), plinth + strip; LOD3 a box, one swell ribbon, strip quad.
"""
import genlib
import kzgeo_common as C
import kzgeo_sake_counter as K
import kzgeo_seat_block_carved as S

ASSET = 'seat_block_carved'
FEATURES = ['square dark stone block', 'seigaiha / wave carving', 'warm light strip under the edge']
STYLES = ['wave', 'seigaiha', 'wave']


def build(lod, seed, w=None, d=None, h=None, carving=None, light_strip=True, back=False):
    carving = carving or C.cycle(seed, STYLES)
    g = C.rng(seed, 'block')
    if seed == 1:
        W, D, H = 1.60, 0.95, 0.80
    else:
        W, D, H = g.uniform(1.25, 1.75), g.uniform(0.80, 0.98), g.uniform(0.62, 0.88)
        if seed % 3 == 0:                            # the third style: lower and wider
            H = min(H, 0.70); W = max(W, 1.5)
    W, D, H = w or W, d or D, h or H
    rc = C.rng(seed, 'corner').uniform(0.03, 0.07)
    rough = C.rng(seed, 'rough').uniform(0.005, 0.010)
    flip = 1 if seed % 3 != 0 else -1
    nlines = 6 if seed % 3 != 0 else 7

    mb = genlib.MeshBuilder()
    m_stone = mb.slot('basalt_dry', roughness_offset=-0.15)
    m_line = mb.slot('bronze', variant='smooth')
    m_glow = mb.slot('lantern_andon_plain', emissive_level=0.8)

    PH, PI = 0.055, 0.04                             # plinth height, inset
    # plinth: stone foot (lower part) + glowing strip (upper 30 mm), both inset under the block
    if lod <= 2:
        K.box_faces(mb, -W / 2 + PI, W / 2 - PI, -D / 2 + PI, D / 2 - PI, 0.0, PH - 0.03, m_stone, skip=('bottom', 'top'))
        if light_strip:
            K.box_faces(mb, -W / 2 + PI + 0.004, W / 2 - PI - 0.004, -D / 2 + PI + 0.004, D / 2 - PI - 0.004,
                        PH - 0.03, PH, m_glow, skip=('bottom', 'top'))
    else:
        bm = mb.bm
        y = D / 2 - PI
        vs = [bm.verts.new(p) for p in ((W / 2 - PI, y, 0), (-W / 2 + PI, y, 0), (-W / 2 + PI, y, PH), (W / 2 - PI, y, PH))]
        mb._tag([bm.faces.new(vs)], m_glow if light_strip else m_stone)
    # block
    S.hewn_block(mb, W, D, H - PH, PH, m_stone, seed, lod, amp=rough, rc=rc)
    # carving on the +Y face (and optionally -Y)
    if carving != 'plain':
        pw, ph = W * 0.72, (H - PH) * 0.64
        oz = PH + (H - PH) * 0.48
        if carving == 'wave':
            lines = S.wave_lines(pw, ph, nlines if lod <= 1 else (3 if lod == 2 else 1), ph * 0.40, flip, lod)
            if lod == 3:
                lines = lines[:1]
        else:
            lines = S.seigaiha_lines(pw, ph, min(0.15, pw / 7.0), lod)
            if lod == 3:
                lines = [max(lines, key=len)]
        S.ridges(mb, lines, (0.0, oz), D / 2, m_line, lod)
        if back and lod <= 1:
            first = len(mb.bm.verts)
            S.ridges(mb, lines, (0.0, oz), D / 2, m_line, lod)
            for v in list(mb.bm.verts)[first:]:
                v.co.x, v.co.y = -v.co.x, -v.co.y

    C.centre_base(mb)
    o = mb.to_object(ASSET)
    o = genlib.finish(o, smooth_angle=40)
    lights = []
    if light_strip:
        for s in (1, -1):
            lights.append(C.light_entry((0.0, s * (D / 2 - PI + 0.02), PH - 0.015), color_k=2300, watts=6))
    C.set_json_props(o, kz_lights=lights,
                     kz_params=dict(w=round(W, 3), d=round(D, 3), h=round(H, 3), carving=carving, light_strip=light_strip))
    return o
