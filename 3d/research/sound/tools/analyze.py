#!/usr/bin/env python3
"""Listen-by-analysis for the Kazan-yu sound research.

  .venv/bin/python 3d/research/sound/tools/analyze.py bank     <wav dir> <out json> <out sheet.jpg>
  .venv/bin/python 3d/research/sound/tools/analyze.py previews <wav dir> <out json> <img dir>

Per file: integrated loudness (ITU-R BS.1770-4, K-weighted, gated), short-term (3 s) max, sample peak and
4x-oversampled true peak, clipped samples, crest factor, spectral centroid, octave-band levels.
For loops: seam check, the wrap-around (end -> start) compared with the rest of the file:
sample jump, 10 ms RMS step and spectral flux at the seam vs. the file's own 99th percentile.
Spectrograms: log-frequency 30 Hz - 16 kHz, dB colour, written with PIL (no matplotlib in the venv).
"""
import sys, os, json, glob, math
import numpy as np
from scipy.io import wavfile
from scipy import signal
from PIL import Image, ImageDraw, ImageFont


def load(path):
    sr, x = wavfile.read(path)
    kind = x.dtype.kind
    x = x.astype(np.float64)
    if kind != 'f':
        x = x / 32768.0
    if x.ndim == 1:
        x = x[:, None]
    return sr, x


def k_weight(x, sr):
    # BS.1770 pre-filter (high shelf) + RLB high-pass, coefficients derived for any rate (Mansbridge et al. form)
    f0, G, Q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    K = math.tan(math.pi * f0 / sr); Vh = 10 ** (G / 20); Vb = Vh ** 0.4996667741545416
    a0 = 1 + K / Q + K * K
    b = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    y = signal.lfilter(b, a, x, axis=0)
    f0, Q = 38.13547087602444, 0.5003270373238773
    K = math.tan(math.pi * f0 / sr)
    a = [1, 2 * (K * K - 1) / (1 + K / Q + K * K), (1 - K / Q + K * K) / (1 + K / Q + K * K)]
    b = [1, -2, 1]
    return signal.lfilter(b, a, y, axis=0)


def loudness(x, sr):
    y = k_weight(x, sr)
    blk, hop = int(0.4 * sr), int(0.1 * sr)
    if len(y) < blk:
        return None, None
    ms = np.array([np.mean(np.sum(y[i:i + blk] ** 2, axis=1)) for i in range(0, len(y) - blk + 1, hop)])
    l = -0.691 + 10 * np.log10(ms + 1e-20)
    g = ms[l > -70]
    if len(g) == 0:
        return -70.0, None
    rel = -0.691 + 10 * np.log10(np.mean(g)) - 10
    g2 = ms[(l > -70) & (l > rel)]
    integ = -0.691 + 10 * np.log10(np.mean(g2)) if len(g2) else -70.0
    st = int(3 * sr)
    stl = [-0.691 + 10 * np.log10(np.mean(np.sum(y[i:i + st] ** 2, axis=1)) + 1e-20) for i in range(0, max(1, len(y) - st + 1), int(0.5 * sr))]
    return float(integ), float(max(stl))


def stats(x, sr):
    integ, stmax = loudness(x, sr)
    peak = float(np.max(np.abs(x)))
    tp = float(np.max(np.abs(signal.resample_poly(x, 4, 1, axis=0)))) if len(x) < sr * 120 else peak
    rmsv = float(np.sqrt(np.mean(x ** 2)))
    mono = x.mean(axis=1)
    f, p = signal.welch(mono, sr, nperseg=4096)
    cen = float(np.sum(f * p) / (np.sum(p) + 1e-20))
    bands = {}
    for fc in [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]:
        m = (f >= fc / math.sqrt(2)) & (f < fc * math.sqrt(2))
        bands[str(fc)] = round(10 * math.log10(np.sum(p[m]) + 1e-20), 1) if m.any() else None
    return {
        'secs': round(len(x) / sr, 2), 'sr': sr, 'ch': x.shape[1],
        'lufs_i': None if integ is None else round(integ, 1), 'lufs_st_max': None if stmax is None else round(stmax, 1),
        'rms_dbfs': round(20 * math.log10(rmsv + 1e-20), 1), 'peak_dbfs': round(20 * math.log10(peak + 1e-20), 2),
        'true_peak_dbtp': round(20 * math.log10(tp + 1e-20), 2), 'clipped_samples': int(np.sum(np.abs(x) >= 0.99997)),
        'crest_db': round(20 * math.log10((peak + 1e-20) / (rmsv + 1e-20)), 1), 'centroid_hz': round(cen),
        'octave_db': bands,
    }


def seam(x, sr):
    m = x.mean(axis=1)
    d = np.abs(np.diff(m))
    jump = abs(m[0] - m[-1])
    w = max(32, int(0.01 * sr))
    xx = np.concatenate([m[-sr:], m[:sr]])  # 1 s either side of the wrap
    r = np.sqrt(np.convolve(xx ** 2, np.ones(w) / w, 'valid') + 1e-20)
    lr = 20 * np.log10(r)
    step = np.abs(lr[w:] - lr[:-w])
    allr = 20 * np.log10(np.sqrt(np.convolve(m ** 2, np.ones(w) / w, 'valid') + 1e-20))
    allstep = np.abs(allr[w::w] - allr[:-w:w])
    seam_step = float(np.max(step[sr - 2 * w:sr]))
    # spectral flux at the seam vs elsewhere
    nfft = 1024
    def flux(sig):
        _, _, Z = signal.stft(sig, sr, nperseg=nfft, noverlap=nfft // 2)
        A = np.abs(Z)
        return np.sqrt(np.sum(np.diff(A, axis=1).clip(0) ** 2, axis=0))
    fs = flux(xx); fa = flux(m)
    mid = len(fs) // 2
    return {
        'jump': round(float(jump), 5), 'median_abs_diff': round(float(np.median(d)), 5),
        'jump_vs_p99_diff': round(float(jump / (np.percentile(d, 99) + 1e-12)), 2),
        'rms10ms_step_at_seam_db': round(seam_step, 2), 'rms10ms_step_p99_db': round(float(np.percentile(allstep, 99)), 2),
        'flux_at_seam_vs_p99': round(float(np.max(fs[mid - 2:mid + 3]) / (np.percentile(fa, 99) + 1e-12)), 2),
    }


LUT = np.array([[0, 0, 4], [40, 11, 84], [101, 21, 110], [159, 42, 99], [212, 72, 66], [245, 125, 21], [250, 193, 39], [252, 255, 164]], float)


def cmap(v):
    v = np.clip(v, 0, 1) * (len(LUT) - 1)
    i = np.floor(v).astype(int).clip(0, len(LUT) - 2)
    f = (v - i)[..., None]
    return (LUT[i] * (1 - f) + LUT[i + 1] * f).astype(np.uint8)


def spectrogram_img(x, sr, w=900, h=260, title='', floor_db=-100, top_db=None, env=True):
    m = x.mean(axis=1)
    nfft = 2048 if sr >= 32000 else 1024
    hop = max(1, len(m) // w)
    f, t, Z = signal.stft(m, sr, nperseg=nfft, noverlap=max(0, nfft - hop), boundary=None)
    S = 20 * np.log10(np.abs(Z) + 1e-12)
    fmin, fmax = 30, min(16000, sr / 2)
    ys = np.geomspace(fmax, fmin, h)
    idx = np.clip(np.searchsorted(f, ys), 0, len(f) - 1)
    img = S[idx, :]
    if img.shape[1] != w:
        xs = np.linspace(0, img.shape[1] - 1, w).astype(int)
        img = img[:, xs]
    top = top_db if top_db is not None else np.percentile(img, 99.7)
    v = (img - (top - 80)) / 80
    rgb = cmap(v)
    pad_l, pad_t, pad_b = 46, 22, 18 + (40 if env else 0)
    canvas = Image.new('RGB', (w + pad_l + 8, h + pad_t + pad_b), (14, 14, 18))
    canvas.paste(Image.fromarray(rgb), (pad_l, pad_t))
    dr = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    dr.text((pad_l, 4), title, fill=(230, 230, 230), font=font)
    for fr in [50, 100, 200, 500, 1000, 2000, 5000, 10000]:
        if fmin < fr < fmax:
            yy = pad_t + int((math.log(fmax) - math.log(fr)) / (math.log(fmax) - math.log(fmin)) * h)
            dr.line([(pad_l - 4, yy), (pad_l, yy)], fill=(200, 200, 200))
            dr.text((2, yy - 6), f'{fr // 1000}k' if fr >= 1000 else str(fr), fill=(180, 180, 180), font=font)
    secs = len(m) / sr
    stepS = 5 if secs > 12 else 1 if secs < 5 else 2
    for s in np.arange(0, secs + 1e-6, stepS):
        xx = pad_l + int(s / secs * w)
        dr.line([(xx, pad_t + h), (xx, pad_t + h + 3)], fill=(200, 200, 200))
        dr.text((xx - 4, pad_t + h + 4), f'{s:g}s', fill=(180, 180, 180), font=font)
    if env:
        # short-term loudness-ish envelope strip (RMS dBFS, 100 ms), -60..0
        y0 = pad_t + h + 18
        n = int(0.1 * sr)
        r = [20 * math.log10(math.sqrt(np.mean(m[i:i + n] ** 2)) + 1e-9) for i in range(0, len(m) - n, n)]
        pts = [(pad_l + int(i / max(1, len(r) - 1) * w), y0 + 36 - int(np.clip((v + 60) / 60, 0, 1) * 36)) for i, v in enumerate(r)]
        dr.rectangle([pad_l, y0, pad_l + w, y0 + 36], outline=(60, 60, 70))
        if len(pts) > 1:
            dr.line(pts, fill=(120, 220, 210), width=1)
        dr.text((2, y0 + 12), 'RMS', fill=(150, 150, 150), font=font)
    return canvas


def main():
    mode = sys.argv[1]
    src = sys.argv[2]
    out_json = sys.argv[3]
    out_img = sys.argv[4]
    files = sorted(glob.glob(os.path.join(src, '*.wav')))
    rep = {}
    imgs = []
    for p in files:
        name = os.path.splitext(os.path.basename(p))[0]
        sr, x = load(p)
        st = stats(x, sr)
        if mode == 'bank' and name.startswith('loop_'):
            st['seam'] = seam(x, sr)
        rep[name] = st
        if mode == 'bank':
            if name.startswith('loop_') or name.endswith('_0'):
                imgs.append(spectrogram_img(x, sr, w=560, h=150, title=f'{name}  {st["secs"]}s  {sr//1000}k  rms {st["rms_dbfs"]} dBFS', env=False))
        else:
            im = spectrogram_img(x, sr, title=f'{name}   {st["lufs_i"]} LUFS-I  (st max {st["lufs_st_max"]})  peak {st["true_peak_dbtp"]} dBTP')
            im.save(os.path.join(out_img, f'spec_{name}.jpg'), quality=88)
        print(name, json.dumps({k: v for k, v in st.items() if k != 'octave_db'}))
    json.dump(rep, open(out_json, 'w'), indent=1)
    if mode == 'bank' and imgs:
        cols = 2
        W, H = imgs[0].size
        rows = math.ceil(len(imgs) / cols)
        sheet = Image.new('RGB', (W * cols, H * rows), (10, 10, 12))
        for i, im in enumerate(imgs):
            sheet.paste(im, ((i % cols) * W, (i // cols) * H))
        sheet.save(out_img, quality=85)


if __name__ == '__main__':
    main()
