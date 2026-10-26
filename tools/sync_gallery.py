"""Post new renders to the progress-site gallery (3d/gallery.json), append-only, once per image.

  python3 tools/sync_gallery.py

Scans:  3d/renders/materials/<id>.jpg   -> kind material  (concept from 3d/materials.json)
        3d/renders/lod/<asset>/*.jpg    -> kind lod       (concept from 3d/inventory.csv)
        3d/renders/models/<asset>/*.jpg -> kind render    (generator previews)
Run it whenever an agent delivers materials or models, so the owner sees them as they arrive.
"""
import csv, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kz

D3 = kz.D3
gal = kz.read_json('gallery.json', [])
have = {g['image'] for g in gal}
added = []


def concept_path(name):
    m = re.match(r'(\d\d-[a-z0-9-]+\.jpg)', name or '')
    return f'../lookbook/img/{m.group(1)}' if m else None


mats = {}
if os.path.exists(os.path.join(D3, 'materials.json')):
    mj = json.load(open(os.path.join(D3, 'materials.json')))
    for m in mj.get('materials', []):
        mats[m['id']] = m
for f in sorted(glob.glob(os.path.join(D3, 'renders', 'materials', '*.jpg'))):
    rel = os.path.relpath(f, D3); mid = os.path.splitext(os.path.basename(f))[0]
    if rel in have or mid == 'sheet':
        continue
    m = mats.get(mid.split('~')[0], {})
    c = concept_path((m.get('concept') or [None])[0])
    added.append(dict(title=f"Material: {m.get('name', mid)}", kind='material', image=rel, concept=c, agent='matlib',
                      status='review', notes=f"{m.get('category', '')} · tiling {m.get('tiling_m_per_repeat', '?')} m · params {m.get('params', {})}"))

inv = {}
if os.path.exists(os.path.join(D3, 'inventory.csv')):
    for r in csv.DictReader(open(os.path.join(D3, 'inventory.csv'))):
        inv[r['id']] = r
for kind, sub in (('lod', 'lod'), ('render', 'models')):
    for f in sorted(glob.glob(os.path.join(D3, 'renders', sub, '*', '*.jpg'))):
        rel = os.path.relpath(f, D3)
        if rel in have:
            continue
        aid = os.path.basename(os.path.dirname(f)); r = inv.get(aid, {})
        imgs = (r.get('concept_images') or '').split()
        c = None
        if imgs:
            hits = glob.glob(os.path.join(kz.ROOT, 'lookbook', 'img', imgs[0].zfill(2) + '-*.jpg'))
            c = '../lookbook/img/' + os.path.basename(hits[0]) if hits else None
        added.append(dict(title=f"{'LOD sheet' if kind == 'lod' else 'Model'}: {r.get('name', aid)} — {os.path.splitext(os.path.basename(f))[0]}",
                          kind=kind, image=rel, concept=c, agent=r.get('owner', ''), status='review',
                          notes=f"features: {r.get('identifying_features', '')} · budget {r.get('tri_budget_lod0-3', '')}"))
for a in added:
    kz.gallery(**a)
print(f'added {len(added)} gallery entries')
