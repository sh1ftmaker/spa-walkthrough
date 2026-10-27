"""Bronze culvert grate over a steaming slot (culvert_grate): a heavy bronze bar grate set flush in a paving
kerb surround, over a dark slot with falling water below (g_terrace).

Target dimensions: proxy 3.0 x 1.2 x 0.1 m (w along the slot x, d across y, h = paving thickness). The row's
"typical 2.4 x 3 x 0.1" disagrees with the proxy; the proxy is the default build size (GUIDE §1), so the
default is a long slot across the terrace path: overall 3.0 x 1.2, paving surround 0.20 m wide, opening
2.6 x 0.8 m. No sheet shows the grate (lookbook 31 only places it), so part sizes are engineering ones:
bronze angle rim 35 mm top band + 70 mm leg, flat bars 18-30 mm thick x 55-75 mm deep at 50-80 mm pitch
(row: pitch 40-80 mm), tops 3 mm under the paving (flush, no trip edge).
Styles (cycle with the seed; seeds 4-6 repeat them with other joints / ties / panel counts):
  transverse (seed 1): ~43 bars across the slot at 60 mm pitch, 20 x 60 mm, two 16 mm tie rods along it
  panels     (seed 2): 3-4 lift-out panels, each with end members, bars running along the slot at 50 mm
                       pitch and two lifting lugs
  heavy      (seed 3): 30 x 75 mm bars across at 80 mm pitch over a visible centre bearer, wider 0.24 m
                       surround
Parameters (build kwargs): w 1-3 (overall), d 1-3 (overall, proxy 1.2), pitch 0.04-0.08, frame (surround
width 0.15-0.3), style.
The slot and its water are runtime: the place model cuts the slot below z = 0 (kz_slot gives the opening,
a suggested depth and the falling-water side), fx_steam emitters are in kz_fx. Nothing is built under the
paving except the bronze rim leg (GUIDE §8.5).
LOD0 chamfered (15 mm) flags with seeded joints and +/-3 mm level differences, closed bar boxes, tie rods, lugs.
LOD1 chamfered flags, bars as top + sides (6 tris), 4-sided ties. LOD2 4 plain flags, bars and rim as top
quads. LOD3 one paving ring, the grate as one bronze plate (and panel members / bearer as quads).
Materials: surround paving, slot wall (inner faces) basalt_wet, rim / bars / ties / lugs bronze.
Animation: none (steam: fx_steam). Lighting: lightmap (UV1 from genlib.finish).
"""
import genlib
import kzgeo_common as C
import kzgeo_culvert_grate as G

ASSET = 'culvert_grate'
FEATURES = ['bronze bar grate', 'flush paving surround', 'dark slot below', 'bronze angle rim']
STYLES = ['transverse', 'panels', 'heavy']
STYLE = {'transverse': dict(pitch=0.060, bt=0.020, bd=0.060, fw=0.20),
         'panels':     dict(pitch=0.050, bt=0.018, bd=0.055, fw=0.20),
         'heavy':      dict(pitch=0.080, bt=0.030, bd=0.075, fw=0.24)}


def layout(seed, style, w, d, pitch, frame):
    st = STYLE[style]
    g = C.rng(seed, ASSET + ':layout')
    gj = C.rng(seed, ASSET + ':joints')
    fw = frame if frame is not None else st['fw']
    L = dict(style=style, W=w, D=d, H=0.10, fw=fw, ow=w - 2 * fw, od=d - 2 * fw,
             pitch=pitch if pitch is not None else st['pitch'], bt=st['bt'], bd=st['bd'], rw=0.035, rd=0.07,
             npanels=g.choice([3, 3, 4]), ties=sorted([g.uniform(0.22, 0.32), g.uniform(0.68, 0.78)]))
    L['joints'] = {}
    for side in (-1, 1):                             # 2-3 flag joints per long run, flags 0.6-1.3 m
        n = gj.choice([2, 3])
        cuts = sorted(gj.uniform(-0.5, 0.5) * w * 0.15 + (k + 1) * w / (n + 1) - w / 2 for k in range(n))
        L['joints'][side] = cuts
    L['flag_dz'] = [gj.uniform(-0.003, 0.003) for _ in range(12)]
    return L


def build(lod, seed, w=3.0, d=1.2, pitch=None, frame=None, style=None):
    style = style or C.cycle(seed, STYLES)
    L = layout(seed, style, w, d, pitch, frame)
    mb = genlib.MeshBuilder()
    m_pave = mb.slot('paving')
    m_slot = mb.slot('basalt_wet', wetness=0.9)
    m_bronze = mb.slot('bronze', wear=0.5)
    G.surround(mb, L, lod, m_pave, m_slot)
    G.rim(mb, L, lod, m_bronze)
    nb = G.bars(mb, L, lod, m_bronze)
    C.centre_base(mb)
    o = mb.to_object(ASSET)
    genlib.finish(o)
    ow, od = L['ow'], L['od']
    C.set_json_props(o,
                     kz_slot=dict(outline=[[-ow / 2, -od / 2], [ow / 2, -od / 2], [ow / 2, od / 2], [-ow / 2, od / 2]],
                                  top_z=L['H'], depth_suggest=0.9, water='falling sheet along +Y wall, 0.5 m down'),
                     kz_fx=[dict(type='fx_steam', pos=[round(x * ow / 2, 3), 0.0, L['H']], rate=0.6)
                            for x in (-0.6, 0.0, 0.6)],
                     kz_params=dict(style=style, w=w, d=d, pitch=L['pitch'], frame=L['fw'], bars=nb))
    return o
