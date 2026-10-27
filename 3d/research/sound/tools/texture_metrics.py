#!/usr/bin/env python3
"""Texture metrics to compare procedural water against CC0 reference recordings (and round 1 vs round 2).

  .venv/bin/python -I 3d/research/sound/tools/texture_metrics.py <out.json> <label=path.wav> [...]

Per file:
  octave_rel_db   octave-band levels (31.5 Hz .. 16 kHz) relative to the file's total level
  centroid_hz     spectral centroid
  low_share_db    energy below 250 Hz relative to total   ("rumble/thunder")
  hi_slope_db_oct slope of the octave spectrum from 1 kHz to 8 kHz
  flatness_mid    mean spectral flatness 400 Hz-4 kHz per 46 ms frame (1 = pure noise, lower = tonal/bubbly)
  accents_per_s   onsets per second: 1-8 kHz envelope (5 ms) jumping > 6 dB above its previous 40 ms mean
  env_std_db      std of the 20 ms RMS envelope in dB, per band (low <250, mid 250-2k, high >2k): fluctuation depth
"""
import sys, json, math
import numpy as np
from scipy.io import wavfile
from scipy import signal


def load(p):
    sr, x = wavfile.read(p)
    k = x.dtype.kind
    x = x.astype(np.float64)
    if k != 'f':
        x /= 32768.0
    if x.ndim > 1:
        x = x.mean(axis=1)
    return sr, x


def metrics(sr, x):
    x = x - np.mean(x)
    f, p = signal.welch(x, sr, nperseg=8192)
    tot = np.sum(p) + 1e-20
    octs = {}
    for fc in [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]:
        m = (f >= fc / math.sqrt(2)) & (f < fc * math.sqrt(2))
        octs[str(fc)] = round(10 * math.log10(np.sum(p[m]) / tot + 1e-20), 1) if m.any() and fc < sr / 2 else None
    cen = float(np.sum(f * p) / tot)
    low = 10 * math.log10(np.sum(p[f < 250]) / tot + 1e-20)
    o = [octs[k] for k in ['1000', '2000', '4000', '8000'] if octs.get(k) is not None]
    slope = float(np.polyfit(np.arange(len(o)), o, 1)[0]) if len(o) >= 3 else None
    nf = 2048
    _, _, Z = signal.stft(x, sr, nperseg=nf, noverlap=nf // 2)
    A = np.abs(Z) + 1e-12
    ff = np.fft.rfftfreq(nf, 1 / sr)
    band = (ff >= 400) & (ff <= 4000)
    Ab = A[band]
    flat = np.exp(np.mean(np.log(Ab), axis=0)) / np.mean(Ab, axis=0)
    # accents: abrupt rises of the 1-8 kHz envelope (5 ms frames): > 6 dB above the mean of the previous 40 ms
    sos = signal.butter(4, [1000, min(8000, sr / 2 - 100)], 'bandpass', fs=sr, output='sos')
    yb = signal.sosfilt(sos, x); w5 = int(0.005 * sr)
    eb = 10 * np.log10(np.convolve(yb ** 2, np.ones(w5) / w5, 'valid')[::w5] + 1e-20)
    prev = np.convolve(eb, np.ones(8) / 8, 'valid')[:-1]; cur = eb[8:]
    on = (cur - prev) > 6; acc = int(np.sum(on[1:] & ~on[:-1]))
    secs = len(x) / sr
    env = {}
    for name, (lo, hi) in {'low': (20, 250), 'mid': (250, 2000), 'high': (2000, min(12000, sr / 2 - 100))}.items():
        sos = signal.butter(4, [lo, hi], 'bandpass', fs=sr, output='sos')
        y = signal.sosfilt(sos, x)
        w = int(0.02 * sr)
        e = np.sqrt(np.convolve(y ** 2, np.ones(w) / w, 'valid')[::w] + 1e-20)
        env[name] = round(float(np.std(20 * np.log10(e))), 2)
    return {'secs': round(secs, 1), 'sr': sr, 'centroid_hz': round(cen), 'low_share_db': round(low, 1),
            'hi_slope_db_oct': None if slope is None else round(slope, 1), 'flatness_mid': round(float(np.mean(flat)), 3),
            'accents_per_s': round(acc / secs, 2), 'env_std_db': env, 'octave_rel_db': octs}


def main():
    out = sys.argv[1]
    rep = {}
    for arg in sys.argv[2:]:
        label, path = arg.split('=', 1)
        sr, x = load(path)
        rep[label] = metrics(sr, x)
        m = rep[label]
        print(f"{label:28s} cen {m['centroid_hz']:5d}  low<250 {m['low_share_db']:6.1f}  slope {m['hi_slope_db_oct']}  flat {m['flatness_mid']:.3f}  acc/s {m['accents_per_s']:5.2f}  env {m['env_std_db']}")
    json.dump(rep, open(out, 'w'), indent=1)


if __name__ == '__main__':
    main()
