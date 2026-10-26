"""Encode the library's tiling PNGs to KTX2 for the web, and record the result in 3d/materials.json.

    python3 tools/matlib/encode_ktx2.py [--dry-run] [--only id,id]

Tool: KTX-Software 4.4.2 `ktx create`, official GitHub release
(KTX-Software-4.4.2-Linux-x86_64.tar.bz2, sha1 c6b08c817f8c8dd299deccae4f2fbb8d55e9acd2),
unpacked to tools/bin/ktx-4.4.2/{bin,lib} (the binary finds ../lib/libktx.so.4 via its rpath).

Per texture set (sources .scratch/matlib/tex/<id>_{base,orm,nh,emis}.png -> 3d/materials/tex/*.ktx2):
  base  sRGB.  1024 px close-up materials: UASTC q2 + RDO + zstd; 512 px: ETC1S/BasisLZ.
  orm   linear RGBA (R AO, G rough, B metal, A height): UASTC q3 + RDO(l=0.5) + zstd.
  nh    linear RGBA (R,G normal XY, B height, A 1): UASTC q3 + RDO(l=0.25) + zstd.
        Not `--normal-mode`: that converts to (RGB=X, A=Y) and would drop the height channel.
        UASTC transcodes losslessly to ASTC 4x4 on phones, so XY quality is kept anyway.
  emis  sRGB (lava only): ETC1S/BasisLZ.
All: full mip chain generated with --mipmap-wrap wrap (the textures tile), lanczos4 filter.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
KTX = os.path.join(ROOT, 'tools', 'bin', 'ktx-4.4.2', 'bin', 'ktx')
SRC = os.path.join(ROOT, '.scratch', 'matlib', 'tex')
DST = os.path.join(ROOT, '3d', 'materials', 'tex')
MANIFEST = os.path.join(ROOT, '3d', 'materials.json')
STATUS = os.path.join(ROOT, '.scratch', 'matlib', 'ktx_status.json')
CLOSE_UP = {'basalt_wet', 'obsidian', 'hinoki', 'tatami', 'paving'}
MIP = ['--generate-mipmap', '--mipmap-wrap', 'wrap', '--mipmap-filter', 'lanczos4']
UASTC = ['--encode', 'uastc', '--uastc-rdo', '--zstd', '18']
ETC1S = ['--encode', 'basis-lz', '--clevel', '4', '--qlevel', '255']

argv = sys.argv[1:]
DRY = '--dry-run' in argv
ONLY = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None


def png_channels(path):
    with open(path, 'rb') as f:
        head = f.read(26)
    return {0: 1, 4: 2, 2: 3, 6: 4}[head[25]]


def jobs(mid):
    out = []
    base = os.path.join(SRC, f'{mid}_base.png')
    rgba = png_channels(base) == 4
    fmt = 'R8G8B8A8_SRGB' if rgba else 'R8G8B8_SRGB'
    if mid in CLOSE_UP:
        enc = UASTC + ['--uastc-quality', '2', '--uastc-rdo-l', '1.0']
    else:
        enc = ETC1S
    out.append(('base', base, ['--format', fmt, '--assign-tf', 'srgb', *enc]))
    out.append(('orm', os.path.join(SRC, f'{mid}_orm.png'),
                ['--format', 'R8G8B8A8_UNORM', '--assign-tf', 'linear', *UASTC, '--uastc-quality', '3',
                 '--uastc-rdo-l', '0.5']))
    out.append(('nh', os.path.join(SRC, f'{mid}_nh.png'),
                ['--format', 'R8G8B8A8_UNORM', '--assign-tf', 'linear', *UASTC, '--uastc-quality', '3',
                 '--uastc-rdo-l', '0.25']))
    emis = os.path.join(SRC, f'{mid}_emis.png')
    if mid == 'lava' and os.path.exists(emis):
        out.append(('emis', emis, ['--format', 'R8G8B8_SRGB', '--assign-tf', 'srgb', *ETC1S]))
    return out


def main():
    os.makedirs(DST, exist_ok=True)
    man = json.load(open(MANIFEST))
    version = 'not run'
    if not DRY:
        version = subprocess.run([KTX, '--version'], capture_output=True, text=True, check=True).stdout.strip()
    status = {'_tool': {'tool': 'KTX-Software ktx create', 'version': version,
                        'release': 'KTX-Software-4.4.2-Linux-x86_64.tar.bz2 (GitHub, sha1 '
                                   'c6b08c817f8c8dd299deccae4f2fbb8d55e9acd2)', 'encoded': not DRY}}
    sources = sorted({os.path.basename(m['textures']['base'])[:-len('_base.ktx2')] for m in man['materials']})
    for mid in sources:
        if ONLY and mid not in ONLY:
            continue
        st = {'encoded': False, 'files': {}}
        for kind, src, opts in jobs(mid):
            dst = os.path.join(DST, f'{mid}_{kind}.ktx2')
            cmd = [KTX, 'create', *opts, *MIP, src, dst]
            print(' '.join(os.path.relpath(c, ROOT) if c.startswith(ROOT) else c for c in cmd), flush=True)
            if DRY:
                continue
            subprocess.run(cmd, check=True)
            subprocess.run([KTX, 'validate', dst], check=True, capture_output=True)
            st['files'][kind] = {'bytes': os.path.getsize(dst), 'codec': 'uastc' if 'uastc' in opts else 'basis-lz'}
        st['encoded'] = not DRY
        status[mid] = st
    if DRY:
        return
    json.dump(status, open(STATUS, 'w'), indent=1)
    man['ktx2'] = status['_tool']
    for m in man['materials']:
        src = os.path.basename(m['textures']['base'])[:-len('_base.ktx2')]
        if src in status:
            m['ktx2'] = status[src]
    json.dump(man, open(MANIFEST, 'w'), indent=1)
    total = sum(f['bytes'] for k, v in status.items() if k != '_tool' for f in v['files'].values())
    print(f'encoded {len(status) - 1} texture sets, {total / 1e6:.1f} MB total; manifest updated')


main()
