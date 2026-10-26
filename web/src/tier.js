// Quality tier detection: URL override > saved manual choice > heuristics, then a frame-time probe can downgrade.
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* private mode */ } },
};

export function gpuString(gl) {
  try {
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    return ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : String(gl.getParameter(gl.RENDERER));
  } catch { return 'unknown'; }
}

export function detectTier(gl) {
  const q = new URLSearchParams(location.search).get('tier');
  const gpu = gpuString(gl);
  const ua = navigator.userAgent;
  const coarse = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
  const mobile = /Android|iPhone|iPad|iPod|Mobile|Silk/i.test(ua) || (navigator.maxTouchPoints > 1 && coarse);
  const mem = navigator.deviceMemory; // undefined on Safari / Firefox
  const cores = navigator.hardwareConcurrency ?? 4;
  const strongGPU = /RTX|GTX 1[06-9]\d|GTX 16|Radeon RX|Radeon Pro|Apple M\d|Arc\(TM\) A|Arc A\d/i.test(gpu);
  const weakGPU = /SwiftShader|llvmpipe|softpipe|Microsoft Basic|Mali-[GT][0-7]\d\b|Adreno \(TM\) [1-5]\d\d|PowerVR|Intel\(R\) HD Graphics [2-5]/i.test(gpu);
  const facts = { gpu, mobile, coarse, mem: mem ?? null, cores, strongGPU, weakGPU };
  if (q === 'low' || q === 'high') return { tier: q, reason: 'url', locked: true, facts };
  const saved = store.get('kz.tier');
  if (saved === 'low' || saved === 'high') return { tier: saved, reason: 'saved', locked: true, facts };
  let tier = 'low';
  if (!mobile && !weakGPU && (strongGPU || ((mem ?? 8) >= 8 && cores >= 8))) tier = 'high';
  return { tier, reason: 'auto', locked: false, facts };
}

export const saveTier = (t) => store.set('kz.tier', t === 'auto' ? null : t);
export const savedTier = () => store.get('kz.tier') ?? 'auto';
export { store };

// Measures median frame interval over n frames (call tick() every frame); resolves with ms.
export function frameProbe(n = 45) {
  const samples = [];
  let last = 0, resolve;
  const done = new Promise((r) => (resolve = r));
  return {
    done,
    tick(now) {
      if (last) samples.push(now - last);
      last = now;
      if (samples.length === n) {
        const s = samples.slice(5).sort((a, b) => a - b);
        resolve(s[Math.floor(s.length / 2)]);
      }
    },
  };
}
