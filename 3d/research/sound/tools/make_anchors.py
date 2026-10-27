#!/usr/bin/env python3
"""Turn CC0 field recordings into seamless anchor loops that sit UNDER the procedural water layers.

  .venv/bin/python -I 3d/research/sound/tools/make_anchors.py <spec.json> <out_dir>

spec.json: {"name": {"src": "<decoded wav>", "secs": 24, "sr": 32000, "hp": 40, "shelf_hz": 5000, "shelf_db": -4,
                     "lowshelf_hz": 0, "lowshelf_db": 0, "rms_db": -20, "xf": 1.5}}

For each anchor:
  1. mono, resampled to sr;
  2. picks the best `secs + xf` window (0.5 s steps) by a score that penalises clicks/handling (crest outliers),
     wind rumble bursts (< 40 Hz level swings) and spectral mismatch between the window's head and tail (loopability),
     and rewards mid-band level fluctuation (the irregularity the procedural layer lacks);
  3. EQ: high-pass, optional low shelf, high shelf cut (the procedural spray layer owns the top octave);
  4. folds the tail onto the head with an equal-power crossfade of xf seconds (seamless loop);
  5. normalises to rms_db and keeps sample peaks under -1 dBFS (gentle tanh only if needed).
Writes <out_dir>/anchor_<name>.wav (16-bit) and anchors.json with the chosen segment and metrics.
"""
import sys, json, math, os
import numpy as np
from scipy.io import wavfile
from scipy import signal


def load(p, sr):
    s, x = wavfile.read(p)
    k = x.dtype.kind
    x = x.astype(np.float64)
    if k != 'f':
        x /= 32768.0
    if x.ndim > 1:
        x = x.mean(axis=1)
    if s != sr:
        g = math.gcd(s, sr)
        x = signal.resample_poly(x, sr // g, s // g)
    return x


def band_env_db(x, sr, lo, hi, w=0.02):
    sos = signal.butter(4, [lo, hi], 'bandpass', fs=sr, output='sos')
    y = signal.sosfilt(sos, x) ** 2
    n = int(w * sr); m = len(y) // n
    return 10 * np.log10(y[:m * n].reshape(m, n).mean(axis=1) + 1e-20)


def spec(x, sr):
    f, p = signal.welch(x, sr, nperseg=2048)
    return 10 * np.log10(p + 1e-20)


def score(seg, sr, xf, slow_w=0.0):
    n = int(xf * sr)
    head, tail = seg[:n * 2], seg[-n * 2:]
    mism = float(np.mean(np.abs(spec(head, sr) - spec(tail, sr))))           # dB, lower = better loop
    lvl = float(abs(10 * np.log10(np.mean(head ** 2) / np.mean(tail ** 2))))  # level mismatch, dB
    crest = 20 * np.log10(np.max(np.abs(seg)) / (np.sqrt(np.mean(seg ** 2)) + 1e-12))
    sub = band_env_db(seg, sr, 15, 40, 0.1)
    wind = float(np.std(sub))                                                  # rumble bursts
    mid = float(np.std(band_env_db(seg, sr, 250, 2000)))                       # irregularity (wanted, up to ~8 dB)
    slow = float(np.std(band_env_db(seg, sr, 100, 4000, 0.5)))                 # wave sets (surf): slow level swings
    s = 1.5 * mism + 2.0 * lvl + 0.6 * max(0.0, crest - 18) + 0.8 * max(0.0, wind - 4) - 0.5 * min(mid, 8) - slow_w * min(slow, 6)
    return s, dict(slow_env_std_db=round(slow, 2), loop_spec_mismatch_db=round(mism, 2), loop_level_mismatch_db=round(lvl, 2), crest_db=round(float(crest), 1),
                   sub40_std_db=round(wind, 2), mid_env_std_db=round(mid, 2))


def main():
    spec_all = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    rep = {}
    for name, c in spec_all.items():
        sr = c.get('sr', 32000)
        x = load(c['src'], sr)
        L = int((c['secs'] + c.get('xf', 1.5)) * sr)
        if len(x) < L:
            raise SystemExit(f'{name}: source too short ({len(x)/sr:.1f}s)')
        best = None
        skip = int(c.get('skip_s', 2.5) * sr)  # avoid fade-ins at the file start/end
        for st in range(skip, max(skip + 1, len(x) - L - skip), int(0.5 * sr)):
            s, m = score(x[st:st + L], sr, c.get('xf', 1.5), c.get('slow_w', 0.0))
            if best is None or s < best[0]:
                best = (s, st, m)
        _, st, m = best
        y = x[st:st + L].copy()
        sos = signal.butter(2, c.get('hp', 40), 'highpass', fs=sr, output='sos')
        y = signal.sosfiltfilt(sos, y)

        def shelf(y, f0, gdb, kind):
            A = 10 ** (gdb / 40); w = 2 * math.pi * f0 / sr; cw, sw = math.cos(w), math.sin(w); al = sw / 2 * math.sqrt(2); r = 2 * math.sqrt(A) * al
            if kind == 'high':
                b = [A * ((A + 1) + (A - 1) * cw + r), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - r)]
                a = [(A + 1) - (A - 1) * cw + r, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - r]
            else:
                b = [A * ((A + 1) - (A - 1) * cw + r), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - r)]
                a = [(A + 1) + (A - 1) * cw + r, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - r]
            return signal.lfilter(b, a, y)
        if c.get('shelf_db'):
            y = shelf(y, c.get('shelf_hz', 5000), c['shelf_db'], 'high')
        if c.get('lowshelf_db'):
            y = shelf(y, c.get('lowshelf_hz', 150), c['lowshelf_db'], 'low')
        n = int(c.get('xf', 1.5) * sr); body = y[:-n].copy()
        t = (np.arange(n) + 0.5) / n
        body[:n] = y[:n] * np.sin(t * np.pi / 2) + y[-n:] * np.cos(t * np.pi / 2)
        body *= 10 ** (c.get('rms_db', -20) / 20) / np.sqrt(np.mean(body ** 2))
        pk = np.max(np.abs(body))
        if pk > 0.89:
            body = np.tanh(body / 0.89 * 1.0) * 0.89 if pk > 1.2 else body * (0.89 / pk)
        wavfile.write(os.path.join(out, f'anchor_{name}.wav'), sr, (np.clip(body, -1, 1) * 32767).astype(np.int16))
        rep[name] = dict(src=c['src'], start_s=round(st / sr, 2), secs=round(len(body) / sr, 2), sr=sr,
                         peak_dbfs=round(20 * math.log10(np.max(np.abs(body)) + 1e-12), 2), **m)
        print(name, json.dumps(rep[name]))
    json.dump(rep, open(os.path.join(out, 'anchors.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
