"""kzgeo_groundcover: plant helpers shared by gen_groundcover, gen_shrub_clump, gen_bonsai_potted and
gen_sakura_small (op05).  Candidates for promotion into kzgeo_common.

  Plant(mb)            per-vertex sway / phase / leaf float layers on the MeshBuilder bmesh
  Plant.tube(...)      C.tube + sway weight per ring (branches, trunks, stems, roots)
  Plant.puff(...)      C.hull_rock used as a soft blob (blossom clusters, leaf masses), sway-tagged
  Plant.frond(...)     a fern frond: tapered arching strip with saw-tooth pinnae (6 tris / segment)
  Plant.blade(...)     a grass / sedge blade: tapered arching strip (2 tris / segment + tip)
  Plant.tag_faces()    tag the verts of already-built faces (C.foliage_pad cores / cards)
  slot(mb, mid, ...)   library slot, or a stand-in for a NEW: library id (recorded as pending)
  post(o, ...)         after genlib.finish(): soft normals on foliage, optional faceted slots, and the
                       `kz_sway` colour attribute (R weight, G phase, B leaf) + `sway` vertex group
                       (same convention as gen_pine_niwaki).
"""
import json
import math

import bmesh
from mathutils import Vector

import genlib
import kzgeo_common as C

# NEW: library ids requested by the asset rows that do not exist yet -> closest library stand-in
STAND_IN = {
    'foliage_fern': ('moss', dict(tint=(0.85, 1.3, 0.45), roughness_offset=0.1, normal_strength=0.6)),
    'blossom': ('washi', dict(tint=(1.0, 0.8, 0.84), roughness_offset=0.15)),
}


def slot(mb, mid, pending, **params):
    """library slot for `mid`; if the id is not in the library use STAND_IN and note it in `pending`"""
    if mid in genlib.matlib.manifest():
        return mb.slot(mid, **params)
    sid, base = STAND_IN[mid]
    p = dict(base); p.update(params)
    pending[mid] = f'stand-in {sid} {json.dumps(p)}'
    return mb.slot(sid, **p)


class Plant:
    def __init__(self, mb):
        self.mb = mb
        L = mb.bm.verts.layers.float
        self.ls = L.get('_kz_sw') or L.new('_kz_sw')
        self.lp = L.get('_kz_ph') or L.new('_kz_ph')
        self.lf = L.get('_kz_lf') or L.new('_kz_lf')

    def tag(self, v, sway, ph=0.0, leaf=0.0):
        v[self.ls] = max(0.0, min(1.0, sway)); v[self.lp] = ph; v[self.lf] = leaf

    def tag_faces(self, faces, sway, ph=0.0, leaf=1.0):
        """sway may be a float or fn(vert) -> float"""
        for f in faces:
            for v in f.verts:
                self.tag(v, sway(v) if callable(sway) else sway, ph, leaf)

    def tube(self, pts, radii, mi, sides, sway=lambda t: 0.0, ph=0.0, cap0=False, cap1=False, mod=None):
        rings, faces = C.tube(self.mb, pts, radii, mi, sides=sides, cap0=cap0, cap1=cap1, mod=mod)
        n = len(rings)
        for i, ring in enumerate(rings):
            for v in ring:
                self.tag(v, sway(i / max(n - 1, 1)), ph, 0.0)
        return rings, faces

    def puff(self, c, size, mi, r, npts=10, sway=0.8, ph=0.0, ground=None, rot=0.0):
        faces = C.hull_rock(self.mb, c, size, mi, r, npts=npts, ground=ground, rot=rot, rmin=0.82)
        self.tag_faces(faces, sway, ph, 1.0)
        return faces

    def _strip(self, base, d, length, width_fn, mi, segs, rise, droop, sway0, sway1, ph, pinnae, twist=0.0):
        """arching strip: starts along d (unit, with elevation baked in), bends down by `droop` (rad over the
        length). width_fn(t) half-width; pinnae adds saw-tooth leaflet tips. Leaf plane ~ faces up."""
        bm = self.mb.bm
        d = Vector(d).normalized()
        hz = Vector((d.x, d.y, 0))
        hz = hz.normalized() if hz.length > 1e-4 else Vector((1, 0, 0))
        side = Vector((-hz.y, hz.x, 0))
        p = Vector(base)
        el0 = math.asin(max(-1.0, min(1.0, d.z)))
        pts, sides_ = [], []
        step = length / segs
        for i in range(segs + 1):
            t = i / segs
            pts.append(p.copy())
            el = el0 - droop * t ** 1.3
            tw = twist * t
            sides_.append((side * math.cos(tw) + Vector((0, 0, 1)) * math.sin(tw)).normalized())
            p = p + (hz * math.cos(el) + Vector((0, 0, 1)) * math.sin(el)) * step
        faces = []
        S, Lr, Rr = [], [], []
        for i, q in enumerate(pts):
            t = i / segs
            w = width_fn(t)
            s = sides_[i]
            lift = Vector((0, 0, 1)) * w * 0.25            # shallow V (keel) so the frond has some body
            S.append(bm.verts.new(q))
            Lr.append(bm.verts.new(q + s * w + lift))
            Rr.append(bm.verts.new(q - s * w + lift))
            for v in (S[-1], Lr[-1], Rr[-1]):
                self.tag(v, sway0 + (sway1 - sway0) * t ** 1.2, ph, 1.0)
        tip = None
        for i in range(segs):
            last = i == segs - 1 and width_fn(1.0) < 1e-4
            if last:
                faces.append(bm.faces.new((S[i], Lr[i], S[i + 1])))
                faces.append(bm.faces.new((S[i], S[i + 1], Rr[i])))
            else:
                faces.append(bm.faces.new((S[i], Lr[i], Lr[i + 1], S[i + 1])))
                faces.append(bm.faces.new((S[i], S[i + 1], Rr[i + 1], Rr[i])))
            if pinnae and not last:
                t = (i + 0.7) / segs
                mid = pts[i].lerp(pts[i + 1], 0.75)
                w = width_fn(t) * pinnae
                s = sides_[i]
                fwd = (pts[i + 1] - pts[i]).normalized()
                for sg, ring in ((1, Lr), (-1, Rr)):
                    tp = bm.verts.new(mid + s * sg * w + fwd * w * 0.35 + Vector((0, 0, w * 0.1)))
                    self.tag(tp, sway0 + (sway1 - sway0) * t ** 1.2, ph, 1.0)
                    tri = (ring[i], tp, ring[i + 1]) if sg > 0 else (ring[i], ring[i + 1], tp)
                    faces.append(bm.faces.new(tri))
        for f in faces:
            f.material_index = mi
            f.normal_update()
            if f.normal.z < 0:            # leaf plane faces up (open sheet: the material renders both sides)
                f.normal_flip()
        return faces, pts

    def spine(self, base, d, length, segs, droop):
        d = Vector(d).normalized()
        hz = Vector((d.x, d.y, 0))
        hz = hz.normalized() if hz.length > 1e-4 else Vector((1, 0, 0))
        el0 = math.asin(max(-1.0, min(1.0, d.z)))
        p = Vector(base); pts = []
        for i in range(segs + 1):
            pts.append(p.copy())
            el = el0 - droop * (i / segs) ** 1.3
            p = p + (hz * math.cos(el) + Vector((0, 0, 1)) * math.sin(el)) * (length / segs)
        return pts, Vector((-hz.y, hz.x, 0))

    def fishbone(self, base, d, length, width, mi, segs, ph=0.0, droop=1.2, sway=(0.25, 1.0), lean=0.45):
        """fern frond as a fishbone: one narrow lanceolate pinna triangle per side per segment, bases sharing
        the rachis verts (2 tris / segment), so the outline is the saw-tooth fern silhouette. Pinnae are
        longest ~1/3 out, lean forward by `lean`, droop slightly; the leaf plane stays roughly horizontal."""
        bm = self.mb.bm
        pts, side = self.spine(base, d, length, segs, droop)
        sw = lambda t: sway[0] + (sway[1] - sway[0]) * t ** 1.2
        S = []
        for i, q in enumerate(pts):
            v = bm.verts.new(q); self.tag(v, sw(i / segs), ph, 1.0); S.append(v)
        faces = []
        for i in range(segs):
            t = (i + 0.5) / segs
            w = width * min(1.0, (0.45 + 2.2 * t)) * (1 - t) ** 0.75
            fwd = (pts[i + 1] - pts[i]).normalized()
            seg = (pts[i + 1] - pts[i]).length
            for sg in (1, -1):
                # pinna: base on the rachis, tip out and forward past the next pinna's base (they overlap
                # like a real frond instead of reading as bunting)
                tip = pts[i + 1] + side * sg * w + fwd * (w * lean + seg * 0.35) - Vector((0, 0, w * 0.18))
                tv = bm.verts.new(tip); self.tag(tv, sw(t), ph, 1.0)
                faces.append(bm.faces.new((S[i], S[i + 1], tv) if sg > 0 else (S[i], tv, S[i + 1])))
        for f in faces:
            f.material_index = mi
            f.normal_update()
            if f.normal.z < 0:
                f.normal_flip()
        return faces, pts

    def frond(self, base, d, length, width, mi, segs, ph=0.0, droop=1.2, pinnae=1.7, sway=(0.25, 1.0)):
        wf = lambda t: width * (0.55 + 1.6 * t) * (1 - t) ** 0.9 if t < 1 else 0.0   # widest ~1/3 out, tip 0
        return self._strip(base, d, length, wf, mi, segs, 0, droop, sway[0], sway[1], ph, pinnae)

    def blade(self, base, d, length, width, mi, segs, ph=0.0, droop=1.0, sway=(0.1, 1.0)):
        wf = lambda t: width * (1 - t) ** 0.8 if t < 1 else 0.0
        return self._strip(base, d, length, wf, mi, segs, 0, droop, sway[0], sway[1], ph, 0, twist=0.6)


def post(o, soft_slots=(), sharp_slots=(), sway=True):
    """after genlib.finish(o): smooth edges between faces of `soft_slots`, hard edges on `sharp_slots`
    (faceted rocks), then the kz_sway colour attribute + `sway` vertex group from the float layers."""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    for e in bm.edges:
        mis = {f.material_index for f in e.link_faces}
        if mis and mis <= set(soft_slots):
            e.smooth = True
        if mis & set(sharp_slots) and len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(20):
            e.smooth = False
    bm.to_mesh(me); bm.free()
    n = len(me.vertices)
    names = ('_kz_sw', '_kz_ph', '_kz_lf')
    if sway and all(a in me.attributes for a in names):
        s = [0.0] * n; p_ = [0.0] * n; l_ = [0.0] * n
        me.attributes['_kz_sw'].data.foreach_get('value', s)
        me.attributes['_kz_ph'].data.foreach_get('value', p_)
        me.attributes['_kz_lf'].data.foreach_get('value', l_)
        col = me.color_attributes.new('kz_sway', 'FLOAT_COLOR', 'POINT')
        flat = []
        for i in range(n):
            flat += [s[i], p_[i], l_[i], 1.0]
        col.data.foreach_set('color', flat)
        me.color_attributes.active_color = col
        me.color_attributes.render_color_index = me.color_attributes.active_color_index
        vg = o.vertex_groups.new(name='sway')
        for i in range(n):
            if s[i] > 0:
                vg.add([i], s[i], 'REPLACE')
    for a in names:
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])
    return o


def fit_xy(mb, w, d):
    """uniformly shrink x/y about the bbox centre so the footprint fits w x d (never grows)"""
    b = C.bbox(mb.bm)
    k = min(1.0, w / max(b['w'], 1e-4), d / max(b['d'], 1e-4))
    if k < 1.0:
        xs = [v.co.x for v in mb.bm.verts]; ys = [v.co.y for v in mb.bm.verts]
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        for v in mb.bm.verts:
            v.co.x = cx + (v.co.x - cx) * k; v.co.y = cy + (v.co.y - cy) * k
    return k


def fit_h(mb, h):
    b = C.bbox(mb.bm)
    k = min(1.0, h / max(b['h'], 1e-4))
    if k < 1.0:
        z0 = b['zmin']
        for v in mb.bm.verts:
            v.co.z = z0 + (v.co.z - z0) * k
    return k
