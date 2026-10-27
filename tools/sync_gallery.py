"""Post new and changed renders to the progress-site gallery (3d/gallery.json). Runs every minute as the
`kz-gallery-sync` service (tools/sync_gallery_loop.sh), so the owner sees work as it lands.

  .venv/bin/python tools/sync_gallery.py

Each posted image is snapshotted to 3d/renders/_v/ (keyed by content hash), so a render that an agent
overwrites in place becomes a NEW version in that asset's history instead of silently replacing the old one.
Entries carry `src` (the live path), `role` (canonical | extra) and `md5`.

Scans:  3d/renders/materials/<id>.jpg                 canonical material preview
        3d/renders/materials/{scale,tiles,close,repeat}/<id>.jpg   extras (links inside the card)
        3d/renders/models/<asset>/canonical*.jpg      canonical model render
        3d/renders/lod/<asset>/*.jpg                  LOD check sheets (extras; canonical until a beauty render exists)
        refs/gen/*.png                                Codex references (Reference) and dollhouses dh-* (Locations)
"""
import csv, glob, hashlib, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kz

D3 = kz.D3
VDIR = os.path.join(D3, 'renders', '_v'); os.makedirs(VDIR, exist_ok=True)
gal = kz.read_json('gallery.json', [])
# one-time migration: hash legacy entries and drop exact duplicates of the same subject (keep the earliest)
_seen = set(); _keep = []
for g in gal:
    if not g.get('md5') and g.get('image') and not re.match(r'^(https?:|/|\.\./)', g['image']) and os.path.exists(os.path.join(D3, g['image'])):
        g['md5'] = hashlib.md5(open(os.path.join(D3, g['image']), 'rb').read()).hexdigest(); g.setdefault('src', g['image'])
    k = (g.get('section'), g.get('subject'), g.get('md5'))
    if g.get('md5') and k in _seen:
        continue
    _seen.add(k); _keep.append(g)
gal = _keep
known_md5 = {(g.get('section'), g.get('subject'), g['md5']) for g in gal if g.get('md5')}
srcs = {}
for g in gal:
    srcs.setdefault(g.get('src') or g.get('image'), []).append(g)
added = []


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def concept_path(name):
    m = re.match(r'(?:lookbook/img/)?(\d\d-[a-z0-9-]+\.jpg)', name or '')
    return f'../lookbook/img/{m.group(1)}' if m else None


def post(live, **entry):
    """live: path relative to 3d/. Post once per distinct content per subject."""
    f = os.path.join(D3, live)
    if not os.path.exists(f):
        return
    h = md5(f)
    key = (entry.get('section'), entry.get('subject'), h)
    if key in known_md5:
        return
    old = srcs.get(live, [])
    if old and not any(g.get('md5') for g in old):
        # legacy entry for this file: adopt it as the current version (no new post)
        for g in old:
            g['md5'] = h; g['src'] = live
        known_md5.add(key)
        return
    snap = os.path.join(VDIR, live.replace('/', '__').rsplit('.', 1)[0] + f'__{h[:8]}.jpg')
    shutil.copyfile(f, snap)
    entry.update(image=os.path.relpath(snap, D3), src=live, md5=h)
    known_md5.add(key); added.append(entry)


# ---------------------------------------------------------------- materials
mats = {}
if os.path.exists(os.path.join(D3, 'materials.json')):
    for m in json.load(open(os.path.join(D3, 'materials.json'))).get('materials', []):
        mats[m['id']] = m
for mid, m in mats.items():
    c = concept_path((m.get('concept') or [None])[0])
    post(f'renders/materials/{mid}.jpg', section='materials', subject=mid, role='canonical', kind='material',
         title=f"Material: {m.get('name', mid)}", concept=c, agent='matlib', status='review')
    for sub, label in (('scale', 'real-scale view'), ('tiles', 'tiling check'), ('close', 'close-up'), ('repeat', '10 m repeat')):
        post(f'renders/materials/{sub}/{mid}.jpg', section='materials', subject=mid, role='extra', kind='material',
             title=f'{label}: {mid}', agent='matlib')

# ---------------------------------------------------------------- references and dollhouses
lists = {}
for lf in sorted(glob.glob(os.path.join(kz.ROOT, 'prompts', 'list*.tsv'))):
    for line in open(lf):
        p = line.rstrip('\n').split('\t')
        if len(p) >= 2:
            lists[p[0]] = p[1]
for f in sorted(glob.glob(os.path.join(kz.ROOT, 'refs', 'gen', '*.png'))):
    name = os.path.splitext(os.path.basename(f))[0]
    jpg = os.path.join(D3, 'renders', 'ref', name + '.jpg')
    if not os.path.exists(jpg) or os.path.getmtime(jpg) < os.path.getmtime(f):
        from PIL import Image
        im = Image.open(f).convert('RGB'); im.thumbnail((1600, 1600)); im.save(jpg, quality=86)
    refs = lists.get(name, '')
    first = next((r for r in refs.split(',') if r and '/' not in r), None)
    dh = name.startswith('dh-')
    post(os.path.relpath(jpg, D3), section='locations' if dh else 'reference', subject=name[3:] if dh else name, role='canonical',
         title=f'Dollhouse concept: {name[3:]}' if dh else f'Codex reference: {name}', kind='concept' if dh else 'reference',
         concept=f'../lookbook/img/{first}.jpg' if first else None, agent='codex', status='reference', notes=f'generated with inputs {refs}')

# ---------------------------------------------------------------- models
rows = {}
for fn in ('inventory.csv', 'asset_list.csv'):                      # the master list wins
    p = os.path.join(D3, fn)
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            rows[r['id']] = r


def model_concept(r):
    refs = next((v for k, v in r.items() if k.startswith('concept_refs')), '') or r.get('concept_images', '')
    for x in refs.split():
        if x.startswith('lookbook/img/'):
            return '../' + x
        if re.match(r'^\d+$', x):
            hits = glob.glob(os.path.join(kz.ROOT, 'lookbook', 'img', x.zfill(2) + '-*.jpg'))
            if hits:
                return '../lookbook/img/' + os.path.basename(hits[0])
    return None


assets = sorted({os.path.basename(d) for d in glob.glob(os.path.join(D3, 'renders', 'lod', '*')) + glob.glob(os.path.join(D3, 'renders', 'models', '*')) if os.path.isdir(d)})
for aid in assets:
    r = rows.get(aid, {}); c = model_concept(r)
    canon = sorted(glob.glob(os.path.join(D3, 'renders', 'models', aid, 'canonical_r*.jpg')), key=lambda p: int(re.search(r'_r(\d+)', p).group(1))) \
        + glob.glob(os.path.join(D3, 'renders', 'models', aid, 'canonical.jpg'))
    for f in canon:
        post(os.path.relpath(f, D3), section='models', subject=aid, role='canonical', kind='render', concept=c, agent='gen', status='review',
             title=f"Model: {r.get('name', aid)}" + (f" (self-critique round {re.search(r'_r(\d+)', f).group(1)})" if '_r' in os.path.basename(f) else ''))
    for f in sorted(glob.glob(os.path.join(D3, 'renders', 'lod', aid, '*.jpg'))):
        b = os.path.splitext(os.path.basename(f))[0]
        post(os.path.relpath(f, D3), section='models', subject=aid, role='canonical' if (b == 'sheet' and not canon) else 'extra', kind='lod',
             concept=c, agent='gen', status='review', title={'sheet': 'LOD sheet', 'phone-lod2-lod3': 'phone recognition test'}.get(b, b))
    # once a beauty render exists, LOD sheets become links inside the card
    if canon:
        for g in gal + added:
            if g.get('section') == 'models' and g.get('subject') == aid and g.get('kind') == 'lod':
                g['role'] = 'extra'

# ---------------------------------------------------------------- place models (3d/PLACE_CONTRACT.md)
for d in sorted(glob.glob(os.path.join(D3, 'renders', 'places', '*'))):
    sid = os.path.basename(d)
    sp = os.path.join(D3, 'spaces', f'{sid}.json')
    s = json.load(open(sp)) if os.path.exists(sp) else {}
    c = concept_path(((s.get('cameras') or {}).get('concept') or {}).get('image'))
    post(f'renders/places/{sid}/canonical.jpg', section='locations', subject=sid, role='canonical', kind='place',
         title=f"Place model: {s.get('name', sid)}", concept=c, agent='place', status='review')
    post(f'renders/places/{sid}/views.jpg', section='locations', subject=sid, role='extra', kind='place',
         title=f'views: {sid}', agent='place')
if added or any(g.get('md5') for g in gal):
    kz.write_json('gallery.json', gal + [dict(time=kz.now(), **a) for a in added])
print(f'added {len(added)} gallery entries')
