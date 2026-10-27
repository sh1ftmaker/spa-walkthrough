"""Assign Kazan-yu library materials to objects (for asset generators).

    import sys; sys.path.insert(0, '<root>/tools/matlib')
    import matlib
    matlib.assign(obj, 'basalt_wet')                          # library defaults
    matlib.assign(obj, 'hinoki', tint=(0.9, 0.8, 0.7), wear=0.4, slot=1)
    matlib.assign(obj, 'neon_tube', variant='cyan')           # named variant from materials.json

How variation works: the library material `<id>` is appended once (its node groups
KZM_<id>, KZ_Core, KZ_Tile ... are shared).  If params differ from the library defaults, a
thin variant material `<id>~<hash>` is made: a copy of the one-node material whose group node
"KZ" gets the new inputs.  All logic stays in the shared groups, so nothing is duplicated;
identical param sets reuse the same variant.  Each material carries
    mat["kz_id"] = '<id>'   and   mat["kz_params"] = JSON of all 7 settings
which the glTF exporter writes to extras, so the web app can rebuild it from materials.json.

UV0 must be in metres (1 UV unit = 1 m); `scale` is metres per texture repeat.
"""
import hashlib
import json
import os

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
LIBRARY = os.path.join(ROOT, '3d', 'materials', 'library.blend')
MANIFEST = os.path.join(ROOT, '3d', 'materials.json')
SETTINGS = ('tint', 'wetness', 'wear', 'roughness_offset', 'scale', 'normal_strength', 'emissive_level')
_manifest = None


def manifest():
    global _manifest
    if _manifest is None:
        with open(MANIFEST) as f:
            _manifest = {m['id']: m for m in json.load(f)['materials']}
    return _manifest


def _norm(k, v):
    if k == 'tint':
        v = tuple(float(x) for x in v)[:3]
        if len(v) != 3:
            raise ValueError('tint needs 3 linear RGB values')
        return tuple(round(x, 5) for x in v)
    return round(float(v), 5)


def base_material(material_id, link=False):
    """The library material itself (appended once; node groups re-used, never duplicated)."""
    for m in bpy.data.materials:
        if m.get('kz_id') == material_id and '~' not in m.name and m.get('kz_base', True):
            return m
    if material_id not in manifest():
        raise KeyError(f'unknown library material {material_id!r}; see 3d/materials.json')
    before = set(bpy.data.materials)
    with bpy.data.libraries.load(LIBRARY, link=link) as (src, dst):
        dst.materials = [material_id]
    new = [m for m in bpy.data.materials if m not in before]
    mat = new[0] if new else bpy.data.materials[material_id]
    _dedupe_groups()
    return mat


def _dedupe_groups():
    """Appending a second material brings KZ_Core.001 etc.; remap them onto the first copy."""
    for ng in list(bpy.data.node_groups):
        stem, dot, num = ng.name.rpartition('.')
        if dot and num.isdigit() and stem in bpy.data.node_groups and ng.library is None:
            keep = bpy.data.node_groups[stem]
            if keep.library is None:
                ng.user_remap(keep)
                bpy.data.node_groups.remove(ng)
    for im in list(bpy.data.images):
        stem, dot, num = im.name.rpartition('.')
        if dot and num.isdigit() and stem in bpy.data.images:
            im.user_remap(bpy.data.images[stem])
            bpy.data.images.remove(im)


def material(material_id, variant=None, link=False, **params):
    """Return the library material, or a thin variant with the given settings."""
    info = manifest()[material_id]
    if variant:
        params = dict(info['variants'][variant], **params)
    bad = set(params) - set(SETTINGS)
    if bad:
        raise KeyError(f'unknown settings {sorted(bad)}; allowed: {SETTINGS}')
    base = base_material(material_id, link=link)
    defaults = {k: _norm(k, v) for k, v in info['params'].items()}
    want = dict(defaults)
    want.update({k: _norm(k, v) for k, v in params.items()})
    if want == defaults:
        base['kz_params'] = json.dumps(defaults)
        return base
    h = hashlib.sha1(json.dumps(want, sort_keys=True).encode()).hexdigest()[:8]
    name = f'{material_id}~{variant or h}'
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = base.copy()
        mat.name = name
        mat['kz_base'] = False
        node = mat.node_tree.nodes['KZ']
        for k, v in want.items():
            s = node.inputs[k]
            s.default_value = tuple(v) + (1.0,) if k == 'tint' else v
        mat['kz_id'] = material_id
        mat['kz_params'] = json.dumps(want)
        mat.use_fake_user = False
    return mat


def assign(obj, material_id, slot=0, variant=None, link=False, **params):
    """Put library material `material_id` (optionally varied by params) into obj's slot."""
    mat = material(material_id, variant=variant, link=link, **params)
    mats = obj.data.materials
    while len(mats) <= slot:
        mats.append(None)
    mats[slot] = mat
    return mat


def refresh(material_ids=None):
    """Replace library materials already appended in this .blend with the current library versions.

    assign() reuses a material that is already in the file, so files built before a library fix keep the
    old shader (e.g. the old hazy lava_glass).  refresh() appends fresh copies, remaps every user of the
    old material and of the old KZ_* node groups onto them, and deletes the stale data.  Variants
    (<id>~...) are rebuilt from the fresh base with their stored kz_params."""
    olds = [m for m in bpy.data.materials if m.get('kz_id') and '~' not in m.name and m.library is None
            and (material_ids is None or m['kz_id'] in material_ids)]
    if not olds:
        return []
    ids = sorted({m['kz_id'] for m in olds})
    old_groups = {ng.name: ng for ng in bpy.data.node_groups if ng.name.startswith(('KZ_', 'KZM_', 'KZP_'))}
    for ng in old_groups.values():
        ng.name = ng.name + '__stale'
    for m in olds:
        m.name = m.name + '__stale'
    with bpy.data.libraries.load(LIBRARY, link=False) as (src, dst):
        dst.materials = ids
    for m in olds:
        new = bpy.data.materials.get(m['kz_id'])
        if new is not None:
            m.user_remap(new)
            bpy.data.materials.remove(m)
    for name, ng in old_groups.items():
        base = name[:-len('__stale')] if name.endswith('__stale') else name
        new = bpy.data.node_groups.get(base)
        if new is not None and new is not ng:
            ng.user_remap(new)
            bpy.data.node_groups.remove(ng)
    for v in [m for m in bpy.data.materials if '~' in m.name and m.get('kz_id') in ids]:
        params = json.loads(v.get('kz_params', '{}'))
        node = v.node_tree.nodes.get('KZ')
        fresh = bpy.data.materials.get(v['kz_id'])
        if node and fresh:
            node.node_tree = fresh.node_tree.nodes['KZ'].node_tree
            for k, val in params.items():
                node.inputs[k].default_value = tuple(val) + (1.0,) if k == 'tint' else val
    _dedupe_groups()
    return ids
