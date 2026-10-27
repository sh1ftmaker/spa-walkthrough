"""Blender-side helpers for the model gallery export (tools/export/export_gallery.py).

Everything here works in the asset's own space: pivot at the base centre, +Y forward, metres (tools/gen/genlib.py).
Arrays come out in three / glTF space (X = x, Y = z, Z = -y) with glTF v (v = 1 - v_blender), the same convention
as tools/export/export_place.py, so the node packer (gallery_pack.mjs) can hand them to web/tools/lib/pack.mjs as is.
Library material handling (kz_id / kz_params) and sprite extraction come from kzexport_common.
"""
import json, os
import bpy
import numpy as np
from mathutils import Matrix

import kzexport_common as K


def l2t(a):
    a = np.asarray(a, np.float32).reshape(-1, 3)
    return np.stack([a[:, 0], a[:, 2], -a[:, 1]], 1)


def write_bin(path, arrays):
    meta, off = {}, 0
    with open(path, 'wb') as fh:
        for k, a in arrays.items():
            a = np.ascontiguousarray(a, np.float32)
            fh.write(a.tobytes())
            meta[k] = {'offset': off, 'count': int(a.shape[0]), 'size': int(a.shape[1]) if a.ndim > 1 else 1}
            off += a.nbytes
    return meta


def mesh_arrays(me):
    """Triangle soup per loop: position, normal, uv0 (first / 'UVMap' layer), flow (kz_flow projected into UV0)."""
    me.calc_loop_triangles()
    tris = me.loop_triangles
    nt = len(tris)
    loops = np.zeros(nt * 3, np.int32); tris.foreach_get('loops', loops)
    verts = np.zeros(nt * 3, np.int32); tris.foreach_get('vertices', verts)
    mi = np.zeros(nt, np.int32); tris.foreach_get('material_index', mi)
    co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    cn = np.zeros(len(me.loops) * 3, np.float32); me.corner_normals.foreach_get('vector', cn); cn = cn.reshape(-1, 3)
    pos = co[verts]
    out = {'position': l2t(pos), 'normal': l2t(cn[loops])}
    layer = me.uv_layers.get('UVMap') or (me.uv_layers[0] if me.uv_layers else None)
    uv0 = None
    if layer is not None:
        u = np.zeros(len(me.loops) * 2, np.float32); layer.data.foreach_get('uv', u); uv0 = u.reshape(-1, 2)[loops]
        uv0[:, 1] = 1.0 - uv0[:, 1]
        out['uv0'] = uv0
    fa = me.attributes.get('kz_flow')
    if fa is not None and uv0 is not None and fa.domain == 'POINT' and fa.data_type == 'FLOAT_VECTOR':
        # same projection as export_place.py: flow direction (layout space) -> UV0 direction per triangle
        f = np.zeros(len(me.vertices) * 3, np.float32); fa.data.foreach_get('vector', f); f = f.reshape(-1, 3)[verts]
        p = pos.reshape(-1, 3, 3); t = uv0.reshape(-1, 3, 2).copy(); t[:, :, 1] = 1 - t[:, :, 1]
        e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
        d1, d2 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
        det = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
        det = np.where(np.abs(det) < 1e-12, 1e-12, det)
        T = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / det[:, None]
        B = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / det[:, None]
        fl = f.reshape(-1, 3, 3)
        du = np.einsum('tij,tj->ti', fl, T) / np.maximum((T * T).sum(1), 1e-9)[:, None]
        dv = np.einsum('tij,tj->ti', fl, B) / np.maximum((B * B).sum(1), 1e-9)[:, None]
        out['flow'] = np.stack([du.reshape(-1), -dv.reshape(-1)], 1).astype(np.float32)
    return out, np.repeat(mi, 3)


def _attr(me, name):
    a = me.attributes.get(name)
    n = len(me.vertices)
    v = np.zeros(n, np.float32)
    if a is not None and a.domain == 'POINT' and a.data_type == 'FLOAT':
        a.data.foreach_get('value', v)
    return v


def extract_stars(me):
    """moon_sky: loose star points (kz_star > 0) -> sprite rows [x, y, z, size, phase, bright, hz, kind] (asset space)."""
    if me.attributes.get('kz_star') is None:
        return []
    n = len(me.vertices)
    co = np.zeros(n * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    used = np.zeros(n, bool)
    for p in me.polygons:
        used[list(p.vertices)] = True
    star, phase, bright = _attr(me, 'kz_star'), _attr(me, 'kz_phase'), _attr(me, 'kz_bright')
    rows = []
    for i in np.nonzero((~used) & (star > 0))[0]:
        b = float(bright[i]) if bright[i] > 0 else float(star[i])
        rows.append([*co[i], 0.05, float(phase[i]), min(1.0, b), 0.6, 1.0])
    return rows


def evaluated_mesh(o, deps, skip_mods=()):
    """Evaluated copy of o's mesh in asset space (o's rotation / scale kept, its sheet offset dropped)."""
    saved = []
    for m in o.modifiers:
        if m.name in skip_mods:
            saved.append((m, m.show_viewport, m.show_render)); m.show_viewport = False; m.show_render = False
    if saved:
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(deps), preserve_all_data_layers=True, depsgraph=deps)
    for m, v, r in saved:
        m.show_viewport, m.show_render = v, r
    M = o.matrix_world.copy(); M.translation = (0, 0, 0)
    if M != Matrix.Identity(4):
        me.transform(M)
    return me


def mat_entry(m):
    return {'id': K.mat_id(m), 'params': K.mat_params(m)}


def obj_json(o, key):
    v = o.get(key)
    if v is None:
        return None
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    try:
        return v.to_dict() if hasattr(v, 'to_dict') else (list(v) if hasattr(v, '__len__') else v)
    except Exception:
        return str(v)


def bbox(arr):
    """three-space position array -> asset-space dims {w, d, h, zmin}."""
    if not len(arr):
        return None
    mn, mx = arr.min(0), arr.max(0)
    return {'w': round(float(mx[0] - mn[0]), 4), 'd': round(float(mx[2] - mn[2]), 4), 'h': round(float(mx[1] - mn[1]), 4),
            'zmin': round(float(mn[1]), 4), 'min': [round(float(x), 4) for x in mn], 'max': [round(float(x), 4) for x in mx]}
