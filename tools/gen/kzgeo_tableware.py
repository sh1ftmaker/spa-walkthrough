"""Lathe profiles for gen_tableware. Each returns [(r, z)] from the underside pole to the inner (or lid)
pole, so kzgeo_common.lathe makes one closed solid with real wall thickness and a turned foot ring.
All sizes in metres; the profiles never reach zero thickness at a rim (3-4 mm rounded lip)."""


def bowl(R, H, t=0.006, foot_r=0.38, foot_h=0.010, lod=0):
    """ramen bowl (donburi): foot ring, deep rounded belly, slight flare, rounded lip"""
    rf = R * foot_r
    if lod >= 2:
        return [(0.0, 0.0), (rf, 0.0), (R * 0.82, H * 0.45), (R, H), (R - t, H), (R * 0.4, t + foot_h), (0.0, t + foot_h)]
    p = [(0.0, 0.0), (rf, 0.0), (rf + 0.003, foot_h),
         (R * 0.78, H * 0.40), (R * 0.95, H * 0.80), (R, H - 0.003), (R - 0.003, H), (R - t, H - 0.004),
         (R * 0.93 - t, H * 0.78), (R * 0.75 - t, H * 0.40), (R * 0.35, foot_h + t), (0.0, foot_h + t)]
    if lod == 1:
        p = [p[0], p[1], p[2], p[3], p[4], p[6], p[7], p[8], p[9], p[11]]
    return p


def bowl_outer(R, H, t=0.006, foot_r=0.38, foot_h=0.010, lod=0):
    """a bowl nested under another: outer wall, foot and lip only, capped just below the lip (hidden)"""
    rf = R * foot_r
    p = [(0.0, 0.0), (rf, 0.0), (rf + 0.003, foot_h), (R * 0.78, H * 0.40), (R * 0.95, H * 0.80), (R, H - 0.003),
         (R - 0.003, H), (R - t, H - 0.004), (0.0, H - 0.03)]
    if lod >= 1:
        p = [p[0], p[1], p[3], p[4], p[6], p[7], p[8]]
    return p


def cup(R, H, t=0.005, lod=0):
    """yunomi tea cup: straight, slightly bellied wall, low foot"""
    if lod >= 2:
        return [(0.0, 0.0), (R * 0.85, 0.0), (R, H), (R - t, H), (R - t, t + 0.006), (0.0, t + 0.006)]
    p = [(0.0, 0.0), (R * 0.86, 0.0), (R * 0.9, 0.008), (R * 1.02, H * 0.55), (R, H - 0.002), (R - 0.0025, H),
         (R - t, H - 0.003), (R * 1.02 - t, H * 0.55), (0.0, t + 0.008)]
    if lod == 1:
        p = [p[0], p[1], p[3], p[5], p[6], p[7], p[8]]
    return p


def jar(R, H, lod=0):
    """lidded condiment jar: foot, round belly, shoulder, neck, overhanging lid with a knob (one solid)"""
    rn = R * 0.62
    if lod >= 2:
        return [(0.0, 0.0), (R * 0.75, 0.0), (R, H * 0.45), (rn * 1.1, H * 0.82), (rn * 0.5, H * 0.95), (0.0, H)]
    p = [(0.0, 0.0), (R * 0.72, 0.0), (R, H * 0.45), (R * 0.88, H * 0.70), (rn, H * 0.78),
         (rn + 0.005, H * 0.78), (rn + 0.005, H * 0.83), (rn * 0.75, H * 0.90), (0.012, H * 0.95), (0.0, H)]
    if lod == 1:
        p = [p[0], p[1], p[2], p[3], p[5], p[6], p[7], p[8], p[9]]
    return p


def dish(R, H, t=0.005, lod=0):
    """small soy dish: low foot, flared shallow well, rounded lip"""
    if lod >= 2:
        return [(0.0, 0.0), (R * 0.6, 0.0), (R, H), (R - t, H), (R * 0.5, t + 0.004), (0.0, t + 0.004)]
    p = [(0.0, 0.0), (R * 0.62, 0.0), (R * 0.9, H * 0.7), (R, H - 0.002), (R - 0.0025, H), (R - t, H - 0.002),
         (R * 0.55, t + 0.005), (0.0, t + 0.004)]
    if lod == 1:
        p = [p[0], p[1], p[2], p[4], p[5], p[6], p[7]]
    return p


def dish_outer(R, H, lod=0):
    """a dish stacked under another: outer wall and lip only"""
    return [(0.0, 0.0), (R * 0.62, 0.0), (R * 0.9, H * 0.7), (R - 0.0025, H), (0.0, H - 0.004)]
