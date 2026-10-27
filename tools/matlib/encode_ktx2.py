"""Encode the library's shipping PNGs to KTX2 and record files and sizes in 3d/materials.json.

    python3 tools/matlib/encode_ktx2.py [--dry-run] [--only set,set]

Tool: KTX-Software 4.4.2 `ktx create`, official GitHub release
(KTX-Software-4.4.2-Linux-x86_64.tar.bz2, sha1 c6b08c817f8c8dd299deccae4f2fbb8d55e9acd2),
unpacked to tools/bin/ktx-4.4.2/{bin,lib} (the binary finds ../lib/libktx.so.4 via its rpath).

Per texture set (manifest texture_sets; sources .scratch/matlib/tex/<set>_<kind>.png):
  base  sRGB (kz_macro: linear).  Close-up sets (>= 1024 px): UASTC q2 + RDO + zstd; others ETC1S/BasisLZ.
  orm   linear RGBA (R AO, G rough, B metal, A height): UASTC q3 + RDO(l=0.5) + zstd, with the
        supplied mip chain (.scratch/matlib/tex/mips/<set>_orm_L<k>.png, Toksvig roughness).
  nh    linear RGBA (R,G normal XY, B height, A wet mask): UASTC q3 + RDO(l=0.25) + zstd.
        Not `--normal-mode` (that keeps only X and Y and would drop height and the wet mask);
        UASTC transcodes losslessly to ASTC 4x4 on phones, so XY quality is kept.
  emis  sRGB: UASTC q2 + zstd (1024 sets) or ETC1S.
Generated mips use --mipmap-wrap wrap (the textures tile).
GPU memory after transcoding: UASTC/ETC1S -> ASTC 4x4 / BC7 / ETC2 RGBA = 8 bits per texel
(ETC2 RGB for ETC1S opaque = 4 bpp; counted as 8 to be safe), full mip chain = x 4/3.
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


def jobs(ts):
    sid = ts['set']
    out = []
    base = os.path.join(SRC, f'{sid}_base.png')
    rgba = png_channels(base) == 4
    if not ts['srgb_base']:                               # kz_macro: linear data
        out.append(('base', [base], ['--format', 'R8G8B8A8_UNORM', '--assign-tf', 'linear', *UASTC,
                                     '--uastc-quality', '3', '--uastc-rdo-l', '0.5', *MIP]))
        return out
    fmt = 'R8G8B8A8_SRGB' if rgba else 'R8G8B8_SRGB'
    enc = (UASTC + ['--uastc-quality', '2', '--uastc-rdo-l', '1.0']) if ts['close_up'] else ETC1S
    out.append(('base', [base], ['--format', fmt, '--assign-tf', 'srgb', *enc, *MIP]))
    n = ts.get('orm_mips') or 0
    mips = [os.path.join(SRC, 'mips', f'{sid}_orm_L{k}.png') for k in range(n)]
    if n and all(os.path.exists(p) for p in mips):
        out.append(('orm', mips, ['--format', 'R8G8B8A8_UNORM', '--assign-tf', 'linear', '--levels', str(n),
                                  *UASTC, '--uastc-quality', '3', '--uastc-rdo-l', '0.5']))
    else:
        out.append(('orm', [os.path.join(SRC, f'{sid}_orm.png')],
                    ['--format', 'R8G8B8A8_UNORM', '--assign-tf', 'linear', *UASTC, '--uastc-quality', '3',
                     '--uastc-rdo-l', '0.5', *MIP]))
    out.append(('nh', [os.path.join(SRC, f'{sid}_nh.png')],
                ['--format', 'R8G8B8A8_UNORM', '--assign-tf', 'linear', *UASTC, '--uastc-quality', '3',
                 '--uastc-rdo-l', '0.25', *MIP]))
    if 'emis' in ts['files']:
        enc = (UASTC + ['--uastc-quality', '2']) if ts['close_up'] else ETC1S
        out.append(('emis', [os.path.join(SRC, f'{sid}_emis.png')],
                    ['--format', 'R8G8B8_SRGB', '--assign-tf', 'srgb', *enc, *MIP]))
    return out


def gpu_bytes(w, h):
    tot, lw, lh = 0, w, h
    while True:
        tot += max(1, (lw + 3) // 4) * max(1, (lh + 3) // 4) * 16       # 4x4 blocks, 16 bytes (8 bpp)
        if lw == 1 and lh == 1:
            return tot
        lw, lh = max(1, lw // 2), max(1, lh // 2)


def main():
    os.makedirs(DST, exist_ok=True)
    man = json.load(open(MANIFEST))
    version = 'not run'
    if not DRY:
        version = subprocess.run([KTX, '--version'], capture_output=True, text=True, check=True).stdout.strip()
    status = {'_tool': {'tool': 'KTX-Software ktx create', 'version': version,
                        'release': 'KTX-Software-4.4.2-Linux-x86_64.tar.bz2 (GitHub, sha1 '
                                   'c6b08c817f8c8dd299deccae4f2fbb8d55e9acd2)', 'encoded': not DRY}}
    for ts in man['texture_sets']:
        sid = ts['set']
        if ONLY and sid not in ONLY:
            continue
        st = {'encoded': False, 'files': {}}
        for kind, srcs, opts in jobs(ts):
            dst = os.path.join(DST, f'{sid}_{kind}.ktx2')
            cmd = [KTX, 'create', *opts, *srcs, dst]
            print(' '.join(os.path.relpath(c, ROOT) if c.startswith(ROOT) else c for c in cmd), flush=True)
            if DRY:
                continue
            subprocess.run(cmd, check=True)
            v = subprocess.run([KTX, 'validate', dst], capture_output=True, text=True)
            st['files'][kind] = {'bytes': os.path.getsize(dst), 'codec': 'uastc' if 'uastc' in opts else 'basis-lz',
                                 'gpu_bytes_8bpp': gpu_bytes(*ts['size']),
                                 'valid': v.returncode == 0}
            if v.returncode != 0:
                print('VALIDATE FAILED', dst, v.stdout[-400:], v.stderr[-400:], flush=True)
        st['encoded'] = not DRY
        status[sid] = st
    if DRY:
        return
    old = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    old.update(status)
    status = old
    json.dump(status, open(STATUS, 'w'), indent=1)
    man['ktx2'] = status['_tool']
    total = gpu = 0
    for ts in man['texture_sets']:
        if ts['set'] in status:
            ts['ktx2'] = status[ts['set']]
            for f in status[ts['set']].get('files', {}).values():
                total += f['bytes']
                gpu += f['gpu_bytes_8bpp']
    for m in man['materials']:
        src = os.path.basename(m['textures']['base'])[:-len('_base.ktx2')]
        m['ktx2'] = status.get(src, {'encoded': False})
    man['ktx2']['total_bytes'] = total
    man['ktx2']['gpu_bytes_all_sets_8bpp'] = gpu
    json.dump(man, open(MANIFEST, 'w'), indent=1)
    print(f'encoded {len(status) - 1} texture sets: {total / 1e6:.2f} MB on disk, '
          f'{gpu / 2**20:.1f} MiB GPU if every set is resident (8 bpp + mips)')


main()
