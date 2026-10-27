// Kazan-yu model gallery: grid (Models / Materials / Places) + the model browser (viewer.js).
// Data: gallery/data/index.json (models) and gallery/data/materials.json (library), written by
// tools/export/export_gallery.py. Every GLB, texture and image loads lazily, per model.
// Deep links: #m=<asset>[&lod=0-3][&seed=n][&clip=name], #tab=materials[&mat=<id>], #tab=places.
import { Viewer, ENVS } from './viewer.js';

const BASE = new URL('gallery/', document.baseURI);
const $ = (id) => document.getElementById(id);
const h = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'style') e.style.cssText = v; else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return e;
};
const img = (rel, alt = '', cls) => h('img', { src: new URL(rel, BASE).href, alt, loading: 'lazy', decoding: 'async', class: cls });
const fmt = (n) => (n == null ? '–' : n >= 1e6 ? `${(n / 1e6).toFixed(2)}M` : n >= 1e4 ? `${(n / 1e3).toFixed(1)}k` : String(Math.round(n)));
const mb = (b) => `${(b / 1048576).toFixed(b > 1048576 * 10 ? 0 : 1)} MB`;
const kb = (b) => (b > 1048576 ? mb(b) : `${Math.round(b / 1024)} kB`);
const CAT_LABEL = (c) => c.replace(/_/g, ' ');
const PRI = { Must: 0, Should: 1, Stretch: 2 };

const state = { tab: 'models', q: '', cat: 'all', sort: 'name', mq: '', mcat: 'all' };
let INDEX = null, MATS = null, viewer = null, current = null;
const errors = [];
const gal = { ready: null, lastLoad: null, errors };
window.__gallery = gal;

function fatal(msg) { const e = $('g-error'); e.hidden = false; e.textContent = msg; console.error('[gallery]', msg); }
async function getJSON(rel) {
  const r = await fetch(new URL(rel, BASE), { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}: gallery/${rel}`);
  return r.json();
}

gal.ready = (async () => {
  [INDEX, MATS] = await Promise.all([getJSON('data/index.json'), getJSON('data/materials.json')]);
  INDEX.byId = new Map(INDEX.assets.map((a) => [a.id, a]));
  MATS.byId = new Map(MATS.library.map((m) => [m.id, m]));
  buildModels(); buildMaterials(); buildPlaces();
  for (const b of document.querySelectorAll('.g-tabs button')) b.addEventListener('click', () => go({ tab: b.dataset.tab }));
  addEventListener('hashchange', route);
  route();
})().catch((e) => { fatal(`Gallery failed to load:\n${e.message}`); throw e; });
gal.ready.catch(() => {});

// ------------------------------------------------------------------ routing
function parseHash() { return Object.fromEntries(new URLSearchParams(location.hash.slice(1))); }
function go(p, replace = false) {
  const s = new URLSearchParams(Object.entries(p).filter(([, v]) => v != null && v !== '')).toString();
  const url = `${location.pathname}${location.search}${s ? `#${s}` : ''}`;
  if (replace) history.replaceState(null, '', url); else history.pushState(null, '', url);
  route();
}
function route() {
  const p = parseHash();
  if (p.m && INDEX.byId.has(p.m)) { openModel(p.m, { lod: p.lod != null ? +p.lod : null, seed: p.seed != null ? +p.seed : null, clip: p.clip }); return; }
  if (p.mat && p.view === '1') { openMaterial(p.mat, p.v); return; }
  closeViewer();
  setTab(p.tab || 'models');
  if (p.mat) highlightMaterial(p.mat);
}
function setTab(t) {
  state.tab = t;
  for (const b of document.querySelectorAll('.g-tabs button')) b.classList.toggle('on', b.dataset.tab === t);
  for (const s of document.querySelectorAll('.g-tab')) s.hidden = s.id !== `tab-${t}`;
}

// ------------------------------------------------------------------ models tab
function buildModels() {
  const cats = new Map();
  for (const a of INDEX.assets) cats.set(a.category, (cats.get(a.category) ?? 0) + 1);
  const chips = $('g-chips');
  const chip = (id, label, n) => h('button', { type: 'button', 'data-cat': id, class: state.cat === id ? 'on' : null, onclick: () => { state.cat = id; renderGrid(); } }, label, h('span', { class: 'c', text: n }));
  chips.replaceChildren(chip('all', 'All', INDEX.assets.length), ...[...cats.entries()].sort().map(([c, n]) => chip(c, CAT_LABEL(c), n)));
  $('g-search').addEventListener('input', (e) => { state.q = e.target.value.trim().toLowerCase(); renderGrid(); });
  $('g-sort').addEventListener('change', (e) => { state.sort = e.target.value; renderGrid(); });
  renderGrid();
}
function filtered() {
  const q = state.q;
  let list = INDEX.assets.filter((a) => state.cat === 'all' || a.category === state.cat);
  if (q) list = list.filter((a) => [a.id, a.name, a.category, a.features, a.parameters, a.library_ids.join(' '), a.locations.join(' '), a.notes].join(' ').toLowerCase().includes(q));
  const by = {
    name: (x, y) => x.name.localeCompare(y.name),
    category: (x, y) => x.category.localeCompare(y.category) || x.name.localeCompare(y.name),
    tris: (x, y) => y.tris_lod0 - x.tris_lod0,
    'tris-asc': (x, y) => x.tris_lod0 - y.tris_lod0,
    priority: (x, y) => (PRI[x.priority] ?? 9) - (PRI[y.priority] ?? 9) || x.name.localeCompare(y.name),
  }[state.sort];
  return list.sort(by);
}
function renderGrid() {
  for (const b of $('g-chips').children) b.classList.toggle('on', b.dataset.cat === state.cat);
  const list = filtered();
  state.list = list.map((a) => a.id);
  $('g-count').textContent = `${list.length} of ${INDEX.assets.length} models`;
  $('g-grid').replaceChildren(...list.map((a) => h('a', { class: 'g-card', href: `#m=${a.id}`, 'data-id': a.id },
    h('div', { class: 'im' }, a.images.thumb ? img(a.images.thumb.uri, a.name) : null,
      h('span', { class: 'badge', text: CAT_LABEL(a.category) }),
      a.skinned ? h('span', { class: 'badge anim', text: 'animated' }) : a.variants.some((v) => v.points) ? h('span', { class: 'badge anim', text: 'sprites' }) : null),
    h('div', { class: 'tx' }, h('span', { class: 'nm', text: a.name }),
      h('span', { class: 'mt', text: `${fmt(a.tris_lod0)} tris · ${a.priority || '–'} · ${a.id}` })))));
}

// ------------------------------------------------------------------ materials tab
const libHex = (m) => m?.albedo_hex ?? m?.tint_hex ?? '#555';
function buildMaterials() {
  const cats = new Map();
  for (const m of MATS.library) cats.set(m.category, (cats.get(m.category) ?? 0) + 1);
  const labels = new Map((MATS.categories ?? []).map((c) => [c.id, c.label]));
  const chip = (id, label, n) => h('button', { type: 'button', 'data-cat': id, onclick: () => { state.mcat = id; renderMats(); } }, label, h('span', { class: 'c', text: n }));
  $('g-mchips').replaceChildren(chip('all', 'All', MATS.library.length), ...[...cats.entries()].map(([c, n]) => chip(c, labels.get(c) ?? CAT_LABEL(c), n)));
  $('g-msearch').addEventListener('input', (e) => { state.mq = e.target.value.trim().toLowerCase(); renderMats(); });
  renderMats();
}
function renderMats() {
  for (const b of $('g-mchips').children) b.classList.toggle('on', b.dataset.cat === state.mcat);
  const q = state.mq;
  const list = MATS.library.filter((m) => (state.mcat === 'all' || m.category === state.mcat) && (!q || `${m.id} ${m.name} ${m.category} ${m.variants.map((v) => v.name).join(' ')}`.toLowerCase().includes(q)));
  $('g-mgrid').replaceChildren(...list.map(matCard));
}
function matCard(m) {
  const pic = h('div', { class: 'im' }, m.preview ? img(m.preview.uri, m.name) : null);
  const setPic = (p) => { pic.replaceChildren(p ? img(p.uri, m.name) : h('div')); };
  const vars = m.variants.map((v) => h('button', { type: 'button', title: `${v.name}: tint ${v.tint_hex}`, onclick: () => setPic(v.preview ?? m.preview) }, h('i', { style: `background:${v.albedo_hex ?? v.tint_hex}` }), v.name));
  const used = m.used_by.length
    ? h('div', { class: 'used' }, `Used by ${m.used_by.length}: `, ...m.used_by.slice(0, 8).flatMap((id, i) => [i ? ', ' : '', h('a', { href: `#m=${id}`, text: INDEX.byId.get(id)?.name ?? id })]), m.used_by.length > 8 ? ` +${m.used_by.length - 8}` : '')
    : h('div', { class: 'used', text: 'Not used by a generator yet' });
  return h('div', { class: 'g-mat', id: `mat-${m.id}` }, pic,
    h('div', { class: 'tx' },
      h('div', {}, h('span', { class: 'nm', text: m.name }), ' ', h('span', { class: 'id', text: m.id })),
      h('div', { style: 'display:flex;gap:10px;flex-wrap:wrap' },
        h('span', { class: 'g-sw', title: 'library tint (linear -> sRGB)' }, h('i', { style: `background:${m.tint_hex}` }), `tint ${m.tint_hex}`),
        m.albedo_hex ? h('span', { class: 'g-sw', title: 'calibrated mean albedo x tint (linear -> sRGB)' }, h('i', { style: `background:${m.albedo_hex}` }), `albedo ${m.albedo_hex}`) : null),
      h('div', { class: 'id', text: [m.tech, m.tiling_m ? `${m.tiling_m} m/repeat` : null, m.mean_roughness != null ? `rough ${m.mean_roughness}` : null, m.emissive ? 'emissive' : null, m.transparent ? 'transparent' : null, m.water ? 'water' : null].filter(Boolean).join(' · ') }),
      vars.length ? h('div', { class: 'g-vars' }, ...vars) : null,
      used,
      h('div', { class: 'acts' }, h('button', { type: 'button', onclick: () => go({ mat: m.id, view: 1 }) }, 'Live sphere'))));
}
function highlightMaterial(id) {
  state.mcat = 'all'; state.mq = ''; $('g-msearch').value = ''; renderMats();
  const el = $(`mat-${id}`);
  if (!el) return;
  for (const x of document.querySelectorAll('.g-mat.hl')) x.classList.remove('hl');
  el.classList.add('hl');
  requestAnimationFrame(() => el.scrollIntoView({ block: 'center', behavior: 'smooth' }));
}

// ------------------------------------------------------------------ places tab
function buildPlaces() {
  $('g-pgrid').replaceChildren(...(INDEX.places ?? []).map((p) => h('a', { class: 'g-place', href: `./index.html?place=${encodeURIComponent(p.id)}` },
    p.canonical ? img(p.canonical.uri, p.name ?? p.id) : null,
    h('div', { class: 'tx' }, h('div', { class: 'nm', text: p.name ?? p.id }), h('div', { class: 'mt', text: `${p.id}${p.level ? ` · ${p.level}` : ''}` }),
      h('span', { class: 'go', text: 'Walk it in the walkthrough →' })))));
}

// ------------------------------------------------------------------ viewer
function ensureViewer() {
  if (viewer) return viewer;
  viewer = new Viewer($('g-canvas'), { base: BASE, materialsDoc: MATS, onStats: showStats });
  viewer.ensureLib(MATS);
  $('g-close').addEventListener('click', () => { if (history.length > 1 && gal.cameFromGrid) history.back(); else go({ tab: state.tab }); });
  $('g-prev').addEventListener('click', () => step(-1));
  $('g-next').addEventListener('click', () => step(1));
  addEventListener('keydown', (e) => {
    if ($('g-viewer').hidden || e.target.matches('input, select')) return;
    if (e.key === 'Escape') $('g-close').click();
    if (e.key === 'ArrowRight') step(1);
    if (e.key === 'ArrowLeft') step(-1);
  });
  $('g-clip').addEventListener('change', (e) => { viewer.playClip(e.target.value); if (current) go({ m: current.asset.id, lod: current.lod || null, seed: current.seed !== current.asset.variants[0]?.seed ? current.seed : null, clip: e.target.value }, true); });
  // toggles + environment
  const tg = $('g-toggles');
  for (const [k, label] of [['wire', 'Wireframe'], ['rotate', 'Auto-rotate'], ['figure', '1.7 m figure'], ['grid', 'Grid'], ['lamps', 'Lamps']]) {
    const b = h('button', { type: 'button', 'data-opt': k, title: k === 'lamps' ? 'the asset\'s own point lamps (kz_lights)' : null, class: viewer.opts[k] ? 'on' : null, onclick: () => { viewer.setOpt(k, !viewer.opts[k]); b.classList.toggle('on', viewer.opts[k]); } }, label);
    tg.append(b);
  }
  tg.append(h('button', { type: 'button', onclick: () => viewer.resetView() }, 'Reset view'));
  const env = $('g-env');
  env.append(h('span', { class: 'lb', text: 'Light' }));
  for (const [k, e] of Object.entries(ENVS)) env.append(h('button', { type: 'button', 'data-env': k, class: viewer.opts.env === k ? 'on' : null, onclick: () => { viewer.setOpt('env', k); for (const b of env.querySelectorAll('button')) b.classList.toggle('on', b.dataset.env === k); } }, e.label));
  addEventListener('click', (e) => { const a = e.target.closest?.('.g-card'); if (a) gal.cameFromGrid = true; });
  return viewer;
}
function step(d) {
  if (!current?.asset) return;
  const list = state.list?.length ? state.list : INDEX.assets.map((a) => a.id);
  const i = list.indexOf(current.asset.id);
  const id = list[(i + d + list.length) % list.length];
  go({ m: id }, true);
}
function showStats(s) {
  if (!current) return;
  const now = performance.now();
  if (now - (showStats.t ?? 0) < 250) return;
  showStats.t = now;
  const v = current.v;
  $('g-stats').textContent = `${fmt(s.tris)} tris  ${s.calls} draws${s.points ? `  ${fmt(s.points)} pts` : ''}  ${s.fps ? s.fps.toFixed(0) : '–'} fps` +
    (v ? `\nLOD${v.lod} s${v.seed}  ${kb(v.bytes)}  model ${fmt(v.tris)} tris / ${v.draws} draws` : '');
}
function openViewerShell() {
  $('g-viewer').hidden = false;
  document.body.classList.add('g-lock');
  ensureViewer().start();
}
function closeViewer() {
  if ($('g-viewer').hidden) return;
  $('g-viewer').hidden = true;
  document.body.classList.remove('g-lock');
  viewer?.stop();
  current = null;
}

async function openModel(id, { lod = null, seed = null, clip = null } = {}) {
  const a = INDEX.byId.get(id);
  openViewerShell();
  const seeds = a.variants.filter((v) => v.lod === 0).map((v) => v.seed);
  const s1 = seeds[0] ?? 1;
  lod = lod ?? 0;
  seed = lod === 0 && seed != null && seeds.includes(seed) ? seed : s1;
  const v = a.variants.find((x) => x.lod === lod && x.seed === seed) ?? a.variants[0];
  const sameAsset = current?.asset?.id === id;
  current = { asset: a, v, lod: v.lod, seed: v.seed, kind: 'model' };
  $('g-vcat').textContent = `${CAT_LABEL(a.category)} · ${a.priority || ''}`;
  $('g-vtitle').textContent = a.name;
  document.title = `${a.name} · Kazan-yu models`;
  buildSeg('g-lod', 'LOD', [0, 1, 2, 3].map((l) => ({ v: l, label: String(l), on: l === v.lod, disabled: !a.variants.some((x) => x.lod === l) })), (l) => go({ m: id, lod: l || null }, true));
  buildSeg('g-seed', 'Seed', seeds.map((s) => ({ v: s, label: String(s), on: s === v.seed, disabled: v.lod !== 0 })), (s) => go({ m: id, seed: s !== s1 ? s : null, clip: viewer.clipName && a.skinned ? viewer.clipName : null }, true));
  if (!sameAsset) $('g-info').replaceChildren(infoPanel(a));
  // figures: shared clips first
  const cb = $('g-clipbox');
  cb.hidden = !a.skinned;
  if (a.skinned && INDEX.figure_clips) {
    await viewer.loadClips(INDEX.figure_clips.uri, INDEX.figure_clips.ref_height);
    const sel = $('g-clip');
    if (!sel.options.length) for (const c of INDEX.figure_clips.clips) sel.append(h('option', { value: c.name, text: `${c.name}${c.group ? ` (${c.group})` : ''}` }));
    viewer.clipName = clip ?? viewer.clipName ?? 'idle_shift';
    sel.value = viewer.clipName;
  }
  $('g-vload').hidden = false; $('g-verr').hidden = true;
  const t0 = performance.now();
  let res;
  try {
    res = await viewer.show(a, v, { keepCamera: viewer.model?.asset?.id === id });
  } catch (e) {
    $('g-vload').hidden = true;
    const msg = `${a.id} LOD${v.lod} s${v.seed}: ${e.message}`;
    errors.push(msg); $('g-verr').hidden = false; $('g-verr').textContent = msg; console.error('[gallery]', msg);
    gal.lastLoad = { id, ok: false, error: e.message };
    return gal.lastLoad;
  }
  if (!res) return null; // superseded
  $('g-vload').hidden = true;
  if (res.errors.length) { $('g-verr').hidden = false; $('g-verr').textContent = res.errors.join('\n'); res.errors.forEach((x) => console.error('[gallery]', x)); }
  if (a.skinned && clip) viewer.playClip(clip);
  const st = viewer.modelStats();
  gal.lastLoad = { id, lod: v.lod, seed: v.seed, ok: !res.errors.length, ms: performance.now() - t0, tris: st.geoTris, renderedTris: st.tris, draws: st.calls, points: st.points, lines: st.lines, expectTris: v.tris, errors: res.errors, clip: a.skinned ? viewer.clipName : null, playing: !!viewer.action?.isRunning?.() };
  return gal.lastLoad;
}
gal.open = async (id, opts = {}) => {
  await gal.ready;
  const p = { m: id, lod: opts.lod || null, seed: opts.seed ?? null, clip: opts.clip ?? null };
  history.replaceState(null, '', `${location.pathname}${location.search}#${new URLSearchParams(Object.entries(p).filter(([, v]) => v != null)).toString()}`);
  const r = await openModel(id, { lod: opts.lod ?? null, seed: opts.seed ?? null, clip: opts.clip ?? null });
  return r;
};
gal.ids = () => INDEX.assets.map((a) => a.id);
gal.viewer = () => viewer;

function buildSeg(elId, label, items, onPick) {
  const el = $(elId);
  el.replaceChildren(h('span', { class: 'lb', text: label }), ...items.map((it) => h('button', { type: 'button', class: it.on ? 'on' : null, disabled: it.disabled || null, onclick: () => onPick(it.v) }, it.label)));
}

function infoPanel(a) {
  const sec = (title, ...kids) => [h('h3', { text: title }), ...kids];
  const budget = a.budget ?? [];
  const actual = (lod, seed) => a.variants.find((v) => v.lod === lod && v.seed === seed)?.tris;
  const seeds = a.variants.filter((v) => v.lod === 0).map((v) => v.seed);
  const rows = [0, 1, 2, 3].map((l) => {
    const t = actual(l, seeds[0]);
    const b = budget[l];
    const cls = b && t != null ? (t <= b * 1.05 ? 'ok' : 'over') : '';
    return h('tr', {}, h('td', { text: `LOD${l}` }), h('td', { text: b != null ? fmt(b) : '–' }), h('td', { class: cls, text: t != null ? fmt(t) : '–' }),
      h('td', { text: l === 0 ? seeds.slice(1).map((s) => fmt(actual(0, s))).join(' / ') || '–' : '' }),
      h('td', { text: kb(a.variants.find((v) => v.lod === l && v.seed === seeds[0])?.bytes ?? 0) }));
  });
  const v0 = a.variants.find((v) => v.lod === 0);
  const dims = v0?.bbox ? `${v0.bbox.w} × ${v0.bbox.d} × ${v0.bbox.h} m` : '–';
  const proxy = a.proxy?.w != null ? `${a.proxy.w} × ${a.proxy.d} × ${a.proxy.h} m` : '–';
  const params = (a.parameters || '').split(/;\s*/).filter(Boolean);
  const mats = a.library_ids.map((id) => {
    const m = MATS.byId.get(id);
    return h('a', { class: 'g-mchip', href: `#tab=materials&mat=${id}`, title: m?.name ?? id }, h('i', { style: `background:${libHex(m)}` }), id);
  });
  const shots = [['canonical', 'Canonical'], ['styles', 'Styles'], ['sheet', 'LOD sheet'], ['sheet_34', '¾ sheet'], ['phone', 'Phone test']].filter(([k]) => a.images[k]);
  const shotBox = h('div');
  const shotTabs = h('div', { class: 'g-imgtabs' });
  const showShot = (k) => {
    const im = a.images[k];
    for (const b of shotTabs.children) b.classList.toggle('on', b.dataset.k === k);
    const el = img(im.uri, `${a.name} ${k}`, 'g-shot');
    el.addEventListener('click', () => lightbox(im.uri, `${a.name}: ${k} (${im.src})`));
    shotBox.replaceChildren(el);
  };
  for (const [k, label] of shots) shotTabs.append(h('button', { type: 'button', 'data-k': k, onclick: () => showShot(k) }, label));
  if (shots.length) showShot(shots[0][0]);
  const anim = a.kz_anim && a.kz_anim.type !== 'none' ? a.kz_anim : null;
  const kv = (pairs) => h('div', { class: 'g-kv' }, ...pairs.filter(([, v]) => v != null && v !== '').flatMap(([k, v]) => [h('span', { text: k }), h('span', {}, v)]));
  return h('div', {},
    ...sec('About',
      kv([['id', a.id], ['category', CAT_LABEL(a.category)], ['priority', a.priority], ['detail', a.detail_tier], ['places', a.locations.join(', ')], ['variants', a.variants_text], ['size', `${dims} (LOD0, built)`], ['proxy', proxy], ['typical', a.dims_text]]),
      a.features ? h('p', {}, a.features) : null,
      a.features_list.length ? h('ul', {}, ...a.features_list.map((f) => h('li', { text: f }))) : null,
      a.notes ? h('p', { class: 'dim', text: a.notes }) : null),
    ...sec('Images', shotTabs, shotBox),
    ...sec('Triangles: budget vs built', h('table', { class: 'g-tbl' }, h('tr', {}, h('th', { text: '' }), h('th', { text: 'budget' }), h('th', { text: `seed ${seeds[0]}` }), h('th', { text: seeds.length > 1 ? `seeds ${seeds.slice(1).join('/')}` : '' }), h('th', { text: 'GLB' })), ...rows)),
    ...sec('Parameters', params.length ? h('ul', {}, ...params.map((p) => h('li', { text: p }))) : h('p', { class: 'dim', text: '–' })),
    ...sec('Materials', h('div', {}, ...mats), a.materials_text.length ? h('p', { class: 'dim', text: `asset list: ${a.materials_text.join(', ')}` }) : null),
    ...sec('Animation, lights, effects',
      kv([['animation', a.animation_text], ['kz_anim', anim ? `${anim.type}${anim.what ? `: ${anim.what}` : ''}` : 'none'],
        ['lighting', a.lighting_text], ['kz_lights', a.kz_lights ? `${a.kz_lights.count} (${Object.entries(a.kz_lights.kinds).map(([k, n]) => `${n} ${k}`).join(', ')})${a.kz_lights.watts ? `, ${a.kz_lights.watts} W` : ''}` : 'none'],
        ['kz_fx', a.kz_fx ? Object.entries(a.kz_fx.kinds).map(([k, n]) => `${n} × ${k}`).join(', ') : 'none'],
        ['sprites', v0?.points ? `${fmt(v0.points)} points${v0.lines ? `, ${fmt(v0.lines)} threads` : ''}${v0.stars ? ' (stars)' : ''}` : null]])),
    ...sec('Concept images', a.concepts.length ? h('div', { class: 'g-concepts' }, ...a.concepts.map((c) => {
      const el = img(c.uri, c.name); el.addEventListener('click', () => lightbox(c.uri, c.src));
      return h('div', {}, el, h('div', { class: 'cap', text: c.name }));
    })) : h('p', { class: 'dim', text: 'none listed' })),
  );
}

async function openMaterial(id, variant) {
  const m = MATS.byId.get(id);
  if (!m) return;
  openViewerShell();
  const key = variant ? `lib:${id}~${variant}` : m.key;
  current = { asset: null, v: null, kind: 'material' };
  $('g-vcat').textContent = 'material';
  $('g-vtitle').textContent = `${m.name}${variant ? ` · ${variant}` : ''}`;
  $('g-clipbox').hidden = true;
  buildSeg('g-lod', 'Variant', [{ v: '', label: 'base', on: !variant }, ...m.variants.map((x) => ({ v: x.name, label: x.name, on: x.name === variant }))], (x) => go({ mat: id, view: 1, v: x || null }, true));
  $('g-seed').replaceChildren();
  $('g-info').replaceChildren(h('div', {},
    h('h3', { text: 'Material' }),
    h('div', { class: 'g-kv' }, ...[['id', m.id], ['category', m.category], ['tech', m.tech], ['tiling', m.tiling_m ? `${m.tiling_m} m per repeat` : null], ['tint', m.tint_hex], ['albedo', m.albedo_hex], ['source', m.source], ['licence', m.licence]].filter(([, v]) => v).flatMap(([k, v]) => [h('span', { text: k }), h('span', { text: v })])),
    m.preview ? h('div', { style: 'margin-top:10px' }, img((m.variants.find((x) => x.name === variant)?.preview ?? m.preview).uri, m.name, 'g-shot')) : null,
    h('h3', { text: 'Used by' }), h('div', {}, ...m.used_by.map((x) => h('a', { class: 'g-mchip', href: `#m=${x}`, text: INDEX.byId.get(x)?.name ?? x }))),
    h('p', {}, h('a', { href: `#tab=materials&mat=${id}`, text: '← all materials' }))));
  $('g-vload').hidden = false; $('g-verr').hidden = true;
  try { await viewer.showMaterial(key); } catch (e) { $('g-verr').hidden = false; $('g-verr').textContent = e.message; console.error('[gallery]', e); }
  $('g-vload').hidden = true;
}

function lightbox(uri, cap) {
  const lb = $('g-lightbox');
  $('g-lbimg').src = new URL(uri, BASE).href; $('g-lbcap').textContent = cap ?? '';
  lb.hidden = false;
}
$('g-lightbox').addEventListener('click', () => { $('g-lightbox').hidden = true; });
