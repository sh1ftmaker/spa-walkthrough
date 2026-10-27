"""Model gallery export: every generator asset -> web/public/gallery/ (GLBs, images, index.json).

    .venv/bin/python tools/export/export_gallery.py [--assets a,b,c] [--skip-blender] [--skip-images] [--skip-pack]

Three stages (each can be skipped; the dump lives in .scratch/gallery/dump/):
  1. Blender (this file, re-run inside `blender -b -P ... -- --blender`): opens 3d/assets/<asset>.blend and dumps
     seed 1 at LOD0-3 and seeds 2-3 at LOD0 as raw arrays per material slot (three space, asset pivot), glowworm
     points / threads and moon_sky stars as sprite rows, library materials (kz_id + kz_params) and the kz_anim,
     kz_lights, kz_fx properties. guest_figure / staff_figure are exported skinned (glTF exporter, no animation)
     and the 13 clips of 3d/assets/figure_anims.blend go into one shared clip GLB (not force-sampled).
  2. Images (PIL): 512 px thumbnails from each canonical, canonical / styles / LOD sheet / phone test, the concept
     images the asset rows name and the material previews, as JPEG <= 1600 px wide, content-addressed.
  3. node tools/export/gallery_pack.mjs: meshopt + quantized GLBs (web/tools/lib/pack.mjs), library KTX2,
     index.json + materials.json, prunes unreferenced files.
"""
import csv, hashlib, json, os, re, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
DUMP = os.path.join(ROOT, '.scratch', 'gallery', 'dump')
OUT = os.path.join(ROOT, 'web', 'public', 'gallery')
BLENDER = '/home/agent-tom/.local/bin/blender'
FIGURES = ('guest_figure', 'staff_figure')


def all_assets():
    d = os.path.join(ROOT, 'tools', 'gen')
    return sorted(f[4:-3] for f in os.listdir(d) if f.startswith('gen_') and f.endswith('.py'))


# =============================================================================== 1. Blender
def blender_stage(assets):
    import bpy
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'export'))
    import gallery_common as G
    import kzexport_common as K
    import numpy as np

    def export_skinned(o, path):
        rig = next((m.object for m in o.modifiers if m.type == 'ARMATURE' and m.object), None)
        # shape keys: bake the build mix into the mesh (the gallery shows the seed's body as built)
        if o.data.shape_keys:
            k = o.shape_key_add(name='kz_mix', from_mix=True)
            co = np.zeros(len(o.data.vertices) * 3, np.float32); k.data.foreach_get('co', co)
            o.shape_key_clear()
            o.data.vertices.foreach_set('co', co); o.data.update()
        o.location = (0, 0, 0)
        bpy.context.view_layer.update()
        mw_rig, mw_o = rig.matrix_world.copy(), o.matrix_world.copy()
        rig.parent = None; rig.matrix_world = mw_rig
        o.parent = rig; o.matrix_world = mw_o
        if rig.animation_data:
            rig.animation_data.action = None
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True); rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_animations=False,
                                  export_skins=True, export_extras=False, export_materials='EXPORT', export_image_format='NONE',
                                  export_apply=False, export_morph=False)

    for ai, asset in enumerate(assets):
        t0 = time.time()
        src = os.path.join(ROOT, '3d', 'assets', f'{asset}.blend')
        d = os.path.join(DUMP, asset)
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
        rec = {'asset': asset, 'variants': [], 'materials': {}, 'errors': [], 'skinned': asset in FIGURES}
        if not os.path.exists(src):
            rec['errors'].append(f'missing {src}')
            json.dump(rec, open(os.path.join(d, 'asset.json'), 'w'), indent=1)
            continue
        bpy.ops.wm.open_mainfile(filepath=src)
        o1 = bpy.data.objects.get(f'{asset}_s1_LOD0')
        if o1 is not None:
            for k in ('kz_anim', 'kz_lights', 'kz_fx', 'kz_features', 'kz_light', 'kz_flicker', 'kz_light_mode', 'kz_steam', 'kz_water_fx'):
                v = G.obj_json(o1, k)
                if v is not None:
                    rec[k] = v
        # seeds as saved by render_lod_sheet.py (normally 1-3; a few assets were sheeted with other seeds, e.g. boulder_rim 1, 2, 4)
        c0 = bpy.data.collections.get(f'{asset}_LOD0')
        seeds = sorted({int(o.get('kz_seed', 0)) for o in (c0.objects if c0 else []) if o.type == 'MESH' and o.get('kz_seed')}) or [1, 2, 3]
        s1 = seeds[0]
        rec['seeds'] = seeds[:3]
        for lod, seed in [(0, s1), (1, s1), (2, s1), (3, s1)] + [(0, s) for s in seeds[1:3]]:
            name = f'{asset}_s{seed}_LOD{lod}'
            o = bpy.data.objects.get(name)
            if o is None or o.type != 'MESH':
                rec['errors'].append(f'no mesh object {name}')
                continue
            for s in o.material_slots:
                if s.material:
                    rec['materials'][s.material.name] = G.mat_entry(s.material)
            v = {'lod': lod, 'seed': seed, 'object': name}
            if rec['skinned'] and any(m.type == 'ARMATURE' and m.object for m in o.modifiers):
                fn = f'v{lod}_{seed}.glb'
                export_skinned(o, os.path.join(d, fn))
                v.update(kind='skinned', file=fn)
                rec['variants'].append(v)
                continue
            deps = bpy.context.evaluated_depsgraph_get()
            pm = str(o.get('kz_preview_modifier') or '')
            skip = [m.name for m in o.modifiers if (pm and pm.split(' ')[0] == m.name) or 'preview' in m.name.lower()]
            me = G.evaluated_mesh(o, deps, skip)
            pts, thr = K.extract_sprites(me, o)
            stars = G.extract_stars(me)
            # drop loose verts / wire edges (sprites, threads, helpers) from the render mesh
            n_before = len(me.vertices)
            K.strip_loose(me)
            arr, mi = G.mesh_arrays(me)
            slots = [s.material.name if s.material else 'missing' for s in o.material_slots]
            prims = []
            for idx in sorted(set(mi.tolist())):
                sel = mi == idx
                sub = {k: a[sel] for k, a in arr.items()}
                fn = f'v{lod}_{seed}_m{idx}.bin'
                prims.append({'file': fn, 'attrs': G.write_bin(os.path.join(d, fn), sub), 'material': slots[idx] if idx < len(slots) else 'missing',
                              'tris': int(sel.sum() // 3)})
            v.update(kind='static', prims=prims, tris=int(len(mi) // 3), bbox=G.bbox(arr['position']), loose_removed=n_before - len(me.vertices))
            sprites = {}
            for key, rows, stride in (('sprites', pts + stars, 8), ('threads', thr, 8)):
                if rows:
                    a = np.asarray(rows, np.float32)
                    a[:, 0:3] = G.l2t(a[:, 0:3])
                    if key == 'threads':
                        a[:, 3:6] = G.l2t(a[:, 3:6])
                    fn = f'v{lod}_{seed}_{key}.bin'
                    a.tofile(os.path.join(d, fn))
                    sprites[key] = {'file': fn, 'count': int(a.shape[0]), 'stride': stride, 'stars': len(stars) if key == 'sprites' else 0}
            if sprites:
                v['sprites'] = sprites
                v['glow_color'] = [0.0, 0.48, 1.0] if pts or thr else [0.75, 0.82, 1.0]
            bpy.data.meshes.remove(me)
            rec['variants'].append(v)
        json.dump(rec, open(os.path.join(d, 'asset.json'), 'w'), indent=1)
        print(f'[gallery] {ai + 1}/{len(assets)} {asset}: {len(rec["variants"])} variants, {len(rec["errors"])} errors, {time.time() - t0:.1f} s', flush=True)

    # shared figure clips: the reference rig with all actions, keyframes as baked (no forced sampling)
    if any(a in FIGURES for a in assets):
        fa = os.path.join(ROOT, '3d', 'assets', 'figure_anims.blend')
        bpy.ops.wm.open_mainfile(filepath=fa)
        sc = bpy.context.scene
        sc.render.fps = 30; sc.render.fps_base = 1.0
        rig = bpy.data.objects['kz_figure_rig']
        clips = {}
        for a in bpy.data.actions:
            try:
                clips[a.name] = json.loads(a.get('kz_clip') or '{}')
            except Exception:
                clips[a.name] = {}
        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True); bpy.context.view_layer.objects.active = rig
        d = os.path.join(DUMP, '_figure_clips'); os.makedirs(d, exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=os.path.join(d, 'clips.glb'), export_format='GLB', use_selection=True, export_yup=True,
                                  export_animations=True, export_animation_mode='ACTIONS', export_force_sampling=False,
                                  export_skins=False, export_extras=False, export_materials='NONE', export_def_bones=False,
                                  export_anim_slide_to_zero=False)
        ref = rig.get('kz_rig_ref')
        json.dump({'clips': clips, 'rig': json.loads(ref) if isinstance(ref, str) else None, 'file': 'clips.glb'},
                  open(os.path.join(d, 'clips.json'), 'w'), indent=1)
        print(f'[gallery] figure clips: {len(clips)} -> {d}', flush=True)


# =============================================================================== 2. images + metadata (PIL)
def sha16(b):
    return hashlib.sha256(b).hexdigest()[:16]


class Images:
    def __init__(self):
        from PIL import Image
        self.Image = Image
        self.cache = {}
        self.dir = os.path.join(OUT, 'img')
        os.makedirs(self.dir, exist_ok=True)

    def put(self, rel, max_w=1600, q=80, thumb=False):
        """rel (relative to ROOT) -> {'uri': 'img/<sha16>.jpg', w, h, bytes} or None.
        thumb: drop the concept crop strip the canonical renders carry on the right, then centre-crop to 16:9."""
        key = (rel, max_w, q, thumb)
        if key in self.cache:
            return self.cache[key]
        src = os.path.join(ROOT, rel)
        if not os.path.isfile(src):
            self.cache[key] = None
            return None
        im = self.Image.open(src)
        im = im.convert('RGB')
        if thumb:
            im = self.crop_strip(im)
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), self.Image.LANCZOS)
        import io
        buf = io.BytesIO(); im.save(buf, 'JPEG', quality=q, optimize=True, progressive=True)
        b = buf.getvalue()
        name = f'{sha16(b)}.jpg'
        p = os.path.join(self.dir, name)
        if not os.path.exists(p):
            open(p, 'wb').write(b)
        r = {'uri': f'img/{name}', 'w': im.width, 'h': im.height, 'bytes': len(b), 'src': rel}
        self.cache[key] = r
        return r


def _crop_strip(self, im):
    import numpy as np
    g = np.asarray(im.convert('L'), np.float32)
    w = g.shape[1]
    frac = (np.abs(np.diff(g, axis=1)) > 12).mean(0)        # rows with a hard vertical edge, per column
    lo, hi = int(w * 0.6), int(w * 0.95)
    x = lo + int(frac[lo:hi].argmax())
    if frac[x] > 0.35:                                       # the strip boundary runs the full height
        im = im.crop((0, 0, x, im.height))
    tw = min(im.width, round(im.height * 16 / 9)); th = min(im.height, round(tw * 9 / 16))
    x0, y0 = (im.width - tw) // 2, (im.height - th) // 2
    return im.crop((x0, y0, x0 + tw, y0 + th))


Images.crop_strip = _crop_strip


def find_concept(name):
    name = name.strip().strip(',;')
    if not name:
        return None
    cands = [name, os.path.join('lookbook', 'img', os.path.basename(name)), os.path.join('refs', 'gen', os.path.basename(name))]
    for c in cands:
        if os.path.isfile(os.path.join(ROOT, c)):
            return c
    return None


def parse_budget(s):
    m = re.findall(r'\d+', (s or '').replace(',', ''))
    return [int(x) for x in m[:4]] if len(m) >= 4 else None


def images_stage(assets):
    IM = Images()
    rows = {r['id']: r for r in csv.DictReader(open(os.path.join(ROOT, '3d', 'asset_list.csv'), newline='', encoding='utf-8'))}
    proxies = json.load(open(os.path.join(ROOT, '3d', 'assets.json')))['assets']
    meta = {'assets': {}, 'materials': {}, 'places': []}
    col = lambda r, pre: next((v for k, v in r.items() if k.startswith(pre)), '') or ''
    for a in assets:
        r = rows.get(a, {})
        chk = os.path.join(ROOT, '3d', 'checks', 'gen', f'{a}.json')
        checks = json.load(open(chk)) if os.path.exists(chk) else {}
        mdir, ldir = os.path.join('3d', 'renders', 'models', a), os.path.join('3d', 'renders', 'lod', a)
        imgs = {}
        canon = os.path.join(mdir, 'canonical.jpg')
        if os.path.isfile(os.path.join(ROOT, canon)):
            imgs['thumb'] = IM.put(canon, 512, 78, thumb=True)
            imgs['canonical'] = IM.put(canon)
        for k, cands in (('styles', [os.path.join(mdir, 'styles.jpg'), os.path.join(ldir, 'styles.jpg')]),
                         ('sheet', [os.path.join(ldir, 'sheet.jpg')]), ('sheet_34', [os.path.join(ldir, 'sheet_34.jpg')]),
                         ('phone', [os.path.join(ldir, 'phone-lod2-lod3.jpg')])):
            for c in cands:
                if os.path.isfile(os.path.join(ROOT, c)):
                    imgs[k] = IM.put(c)
                    break
        concepts = []
        for tok in re.split(r'[\s,;]+', col(r, 'concept_refs')):
            p = find_concept(tok)
            if p and p not in [c['src'] for c in concepts]:
                im = IM.put(p)
                if im:
                    concepts.append({**im, 'name': os.path.basename(p)})
        meta['assets'][a] = {
            'id': a, 'name': r.get('name') or a.replace('_', ' '), 'category': r.get('category') or 'other',
            'priority': col(r, 'priority'), 'detail_tier': col(r, 'detail_tier'), 'locations': col(r, 'locations').split(),
            'features': col(r, 'identifying_features'), 'parameters': col(r, 'parameters'), 'variants_text': col(r, 'variants'),
            'dims_text': col(r, 'dims_m'), 'materials_text': col(r, 'materials').split(), 'budget_text': col(r, 'tri_budget'),
            'budget': checks.get('budget') or parse_budget(col(r, 'tri_budget')), 'animation_text': col(r, 'animation'),
            'lighting_text': col(r, 'lighting'), 'notes': r.get('notes', ''), 'in_asset_list': bool(r),
            'proxy': proxies.get(a, {}) and {k: proxies[a][k] for k in ('w', 'd', 'h') if k in proxies[a]},
            'snap': proxies.get(a, {}).get('snap'),
            'checks': [{'lod': x['lod'], 'seed': x['seed'], 'tris': x['tris'], 'problems': x.get('problems', []), 'bbox': x.get('bbox')} for x in checks.get('results', [])],
            'images': {k: v for k, v in imgs.items() if v}, 'concepts': concepts,
        }
    # material previews (3d/renders/materials/<id>.jpg and <id>__<variant>.jpg)
    mdir = os.path.join(ROOT, '3d', 'renders', 'materials')
    for f in sorted(os.listdir(mdir)):
        if f.endswith('.jpg') and f != 'sheet.jpg':
            stem = f[:-4]
            mid, _, var = stem.partition('__')
            meta['materials'].setdefault(mid, {})[var or ''] = IM.put(os.path.join('3d', 'renders', 'materials', f), 800, 80)
    sheet = os.path.join('3d', 'renders', 'materials', 'sheet.jpg')
    meta['material_sheet'] = IM.put(sheet) if os.path.isfile(os.path.join(ROOT, sheet)) else None
    # the three slice places
    for pid in ('g_arrival', 'b1_mirror', 'b1_cor_mirror'):
        pd = os.path.join('3d', 'renders', 'places', pid)
        ent = {'id': pid}
        for k, f in (('canonical', 'canonical.jpg'), ('entry', 'entry_169.jpg'), ('plan', 'plan.jpg')):
            if os.path.isfile(os.path.join(ROOT, pd, f)):
                ent[k] = IM.put(os.path.join(pd, f))
        sf = os.path.join(ROOT, '3d', 'spaces', f'{pid}.json')
        if os.path.exists(sf):
            s = json.load(open(sf))
            ent['name'] = s.get('name') or s.get('title')
            ent['level'] = s.get('level')
        meta['places'].append(ent)
    os.makedirs(DUMP, exist_ok=True)
    json.dump(meta, open(os.path.join(DUMP, 'meta.json'), 'w'), indent=1)
    n = sum(len(v['images']) + len(v['concepts']) for v in meta['assets'].values())
    print(f'[gallery] images: {len(IM.cache)} unique sources, {n} asset image refs', flush=True)


# =============================================================================== main
def main():
    argv = sys.argv[1:]
    if '--' in sys.argv:
        argv = sys.argv[sys.argv.index('--') + 1:]
    sel = None
    if '--assets' in argv:
        sel = [x for x in argv[argv.index('--assets') + 1].split(',') if x]
    assets = sel or all_assets()
    if '--blender' in argv:
        blender_stage(assets)
        return
    t0 = time.time()
    if '--skip-blender' not in argv:
        cmd = [BLENDER, '-b', '--factory-startup', '-P', os.path.abspath(__file__), '--', '--blender', '--assets', ','.join(assets)]
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            raise SystemExit(f'blender stage failed ({r.returncode})')
    if '--skip-images' not in argv:
        images_stage(all_assets())
    if '--skip-pack' not in argv:
        r = subprocess.run(['node', os.path.join(ROOT, 'tools', 'export', 'gallery_pack.mjs'), DUMP, OUT], cwd=os.path.join(ROOT, 'web'))
        if r.returncode != 0:
            raise SystemExit(f'gallery_pack.mjs failed ({r.returncode})')
    print(f'[gallery] done in {time.time() - t0:.0f} s -> {OUT}')


if __name__ == '__main__':
    main()
