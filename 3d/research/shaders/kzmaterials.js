// Per-material recommendations for the Kazan-yu library -> kzshader.js configurations.
// tech: 'procedural' | 'hybrid' (plate textures + procedural layer) | 'antitile' | 'boards' | 'plain+macro' | 'keep'
// plate: Codex plate set in demo/tex/pl (metres covered by one plate = plateM)
// lib: current library texture set (3d/materials/tex, snapshot in demo/tex/lib)
// proc: procedural id in kzshader.js; procA/procB/albedoA/albedoB its parameters
// The 7 shared settings come from 3d/materials.json at runtime (params + constants).
export const KZM = {
  basalt_dry: {
    family: 'stone', tech: 'hybrid', proj: 'biplanar', plate: 'basalt_vesicular', plateM: 2.2, gain: 0.65,
    plate2: 'rock_wet_ore', layer: { amount: 0.45, sizeM: 5 }, rot: 1, rough: [0.82, 0.5], porosity: 0.6,
    proc: 'basalt', procA: [0.9, 0.22, 0.14, 0.2], albedoA: [0.03, 0.032, 0.036], albedoB: [0.16, 0.15, 0.13],
    macro: { amount: 1, size1: 6, size2: 21, hue: [0.88, 0.97, 1.15], streak: 0.6 },
    note: 'Cave walls. Biplanar world projection (no UVs needed), hex inside each projection, vesicular plate + wet-ore plate blended by height at 5 m.',
  },
  basalt_wet: {
    family: 'stone', tech: 'hybrid', proj: 'biplanar', plate: 'rock_wet_ore', plateM: 2.4, gain: 1.6,
    plate2: 'basalt_columnar_wet', layer: { amount: 0.35, sizeM: 7 }, rot: 1, rough: [0.5, 0.06], porosity: 0.6,
    proc: 'basalt', procA: [0.8, 0.25, 0.16, 0.16], albedoA: [0.02, 0.022, 0.026], albedoB: [0.12, 0.12, 0.11],
    macro: { amount: 1, size1: 6, size2: 21, hue: [0.88, 0.97, 1.15], streak: 0.9 },
    note: 'Blocky wet-rock plate (rotation free), columnar plate blended in by height at 7 m; drips come from the macro streak term so they stay vertical.',
  },
  obsidian: {
    family: 'stone', tech: 'hybrid', proj: 'biplanar', plate: 'obsidian', plateM: 1.6, gain: 1.1, rot: 1, rough: [0.04, 0.16], porosity: 0,
    proc: 'obsidian', procA: [0.32, 0.22, 0.007, 0], albedoA: [0.016, 0.016, 0.018], albedoB: [0.05, 0.035, 0.03],
    macro: { amount: 0.4, size1: 5, size2: 17, hue: [0.95, 0.98, 1.06], streak: 0 },
    note: 'Hybrid: plate colour and veins, relief replaced by flat 3D-Voronoi facets (constant gradient per cell) so probe reflections break into long clean planes with crisp ridges.',
  },
  rimstone: {
    family: 'stone', tech: 'antitile', proj: 'biplanar', plate: 'rimstone', plateM: 1.4, rot: 1, rough: [0.5, 0.08], porosity: 0.3,
    proc: 'rimstone', procA: [0.7, 7, 0.035, 0], albedoA: [0.74, 0.69, 0.6], albedoB: [0.6, 0.42, 0.2],
    macro: { amount: 0.7, size1: 5, size2: 15, hue: [0.95, 1.0, 1.05], streak: 0.3 },
    note: 'Plate (gour rims) hex-tiled reads right; the procedural gours/flowstone variant (KZ_PROC rimstone) is experimental and still reads as wood figure on sides.',
  },
  black_sand: {
    family: 'stone', tech: 'hybrid', proj: 'floor', plate: 'black_sand', plateM: 1.6, gain: 1.4, rot: 1, rough: [0.78, 0.2], porosity: 0.7,
    proc: 'sand', procA: [0.16, 0.006, 0, 0], albedoA: [0.02, 0.019, 0.019], albedoB: [0.07, 0.068, 0.066],
    macro: { amount: 1, size1: 4, size2: 13, hue: [0.94, 0.98, 1.06], streak: 0 },
    note: 'Plate hex-tiled for the grain look; procedural ripples + roughness glints on High.',
  },
  ash_clay: {
    family: 'stone', tech: 'antitile', proj: 'uv', plate: 'ash_clay', plateM: 2.4, rot: 1, rough: [0.88, 0.75], porosity: 0.5,
    macro: { amount: 0.8, size1: 4, size2: 12, hue: [0.95, 1, 1.05], streak: 0.4 },
  },
  paving: {
    family: 'stone', tech: 'antitile', proj: 'uv', plate: 'paving_wet', plateM: 2.6, gain: 1.3, rot: 1, gainR: 0.8, rough: [0.3, 0.04], porosity: 0.5,
    macro: { amount: 1, size1: 5, size2: 17, hue: [0.9, 0.97, 1.12], streak: 0 },
    note: 'Discrete flagstones: hex with high contrast gain (r = 0.8) so blends fall in joints; wetness from layout puddles.',
  },
  hinoki: {
    family: 'wood', tech: 'boards', proj: 'uv', plate: 'hinoki', plateM: 1.8, boards: { n: 5, widthM: 0.16, margin: 0.02 }, rot: 0,
    rough: [0.68, 0.5], porosity: 0.4, macro: { amount: 0.6, size1: 4, size2: 11, hue: [0.95, 1, 1.04], streak: 0 },
    note: 'Per-board shuffle: each board picks one of 5 plate boards, random offset/flip, staggered end joints. 1 tap per map.',
  },
  lacquer_dark: {
    family: 'wood', tech: 'boards', proj: 'uv', plate: 'lacquer', plateM: 1.8, boards: { n: 3, widthM: 0.24, margin: 0.03 }, rot: 0,
    rough: [0.25, 0.1], porosity: 0, macro: { amount: 0.4, size1: 3, size2: 9, hue: [1, 1, 1], streak: 0 },
  },
  bamboo: { family: 'wood', tech: 'keep', proj: 'uv', lib: 'bamboo', note: 'Per-pole UVs on geometry; add per-pole hash offset (asset-side), macro only.' },
  tatami: {
    family: 'wood', tech: 'plain+macro', proj: 'uv', plate: 'tatami', plateM: 0.9, rot: 0, rough: [0.75, 0.6], porosity: 0.3,
    macro: { amount: 0.7, size1: 2.5, size2: 7, hue: [1.06, 1.0, 0.9], streak: 0 },
    note: 'Regular weave: repetition is correct, anti-tiling would ghost the weave. Macro = sun-fade / wear only.',
  },
  washi: { family: 'paper', tech: 'antitile', proj: 'uv', plate: 'washi', plateM: 0.8, rot: 1, rough: [0.85, 0.8], porosity: 0, macro: { amount: 0.5, size1: 2, size2: 6, hue: [1.04, 1, 0.94], streak: 0 } },
  washi_backlit: { family: 'paper', tech: 'antitile', proj: 'uv', plate: 'washi', plateM: 0.8, rot: 1, rough: [0.85, 0.8], porosity: 0, note: 'Same as washi + emissive (thinness from height).' },
  noren: { family: 'cloth', tech: 'plain+macro', proj: 'uv', plate: 'noren', plateM: 0.5, rot: 0, rough: [0.9, 0.85], porosity: 0, macro: { amount: 0.6, size1: 1.5, size2: 4, hue: [1, 1, 1.05], streak: 0 } },
  rope: { family: 'cloth', tech: 'keep', proj: 'uv', lib: 'rope', note: 'Tube UVs; texture is fine at its size.' },
  iron: {
    family: 'metal', tech: 'antitile', proj: 'uv', plate: 'iron', plateM: 0.9, rot: 1, rough: [0.8, 0.55], metal: 0.3, porosity: 0.2,
    macro: { amount: 0.8, size1: 2, size2: 6, hue: [1.05, 1, 0.92], streak: 0.8 },
  },
  bronze: {
    family: 'metal', tech: 'antitile', proj: 'uv', plate: 'bronze', plateM: 0.9, rot: 1, rough: [0.4, 0.25], metal: 1, porosity: 0,
    macro: { amount: 0.6, size1: 2, size2: 6, hue: [0.9, 1.05, 1.0], streak: 0.6 },
  },
  glacier_ice: {
    family: 'ice', tech: 'antitile', proj: 'biplanar', plate: 'glacier_ice', plateM: 2.0, rot: 1, rough: [0.05, 0.12], porosity: 0,
    proc: 'ice', procA: [0.08, 0.35, 1.6, 0], albedoA: [0.03, 0.12, 0.2], albedoB: [0.5, 0.72, 0.8], emissive: { color: [0.004, 0.03, 0.045], fromBase: 0 },
    macro: { amount: 0.5, size1: 4, size2: 12, hue: [0.9, 1, 1.1], streak: 0 },
    note: 'Plate hex-tiled is the best look; the procedural parallax-layer ice (KZ_PROC ice) adds depth but its cracks still read as a cell network.',
  },
  lava_glass: { family: 'glass', tech: 'keep', proj: 'uv', lib: 'lava_glass', note: 'Transparent pane; add macro smudge/condensation only (water agent).' },
  water_still: { family: 'water', tech: 'keep', note: 'Owned by the water research (normal scrolling, depth fade).' },
  water_river: { family: 'water', tech: 'keep', note: 'Owned by the water research.' },
  water_sea: { family: 'water', tech: 'keep', note: 'Owned by the water research.' },
  waterfall: { family: 'water', tech: 'keep', note: 'Owned by the water research.' },
  caustics_decal: { family: 'water', tech: 'procedural', proc: 'caustics', note: 'kzCaustic() on the pool floor material (emissive add) replaces the decal texture.' },
  lava: {
    family: 'lava', tech: 'hybrid', proj: 'uv', plate: 'lava_crust', plateM: 3.0, rot: 1, rough: [0.8, 0.4], porosity: 0,
    proc: 'lava', procA: [0.8, 0.028, 9.0, 0], procB: [0.02, 0.006, 0, 0], albedoA: [0.03, 0.026, 0.024], albedoB: [0.08, 0.02, 0.01],
    emissive: { color: [0, 0, 0], fromBase: 7 }, macro: { amount: 0.6, size1: 4, size2: 12, hue: [1, 1, 1], streak: 0 },
    note: 'Hybrid: hex-tiled crust plate with its glowing seams as emissive, modulated by a flowing noise (breathing glow). Pure procedural (KZ_PROC lava: drifting plates, seams, cracks) kept for lava_flow.',
  },
  lava_flow: {
    family: 'lava', tech: 'hybrid', proj: 'uv', plate: 'lava_crust', plateM: 2.0, rot: 1, rough: [0.7, 0.4], porosity: 0,
    proc: 'lava', procA: [0.35, 0.16, 14.0, 0], procB: [0.25, 0.03, 0, 0], albedoA: [0.03, 0.02, 0.018], albedoB: [0.2, 0.04, 0.01],
    emissive: { color: [0, 0, 0], fromBase: 9 },
  },
  neon_tube: { family: 'light', tech: 'keep', note: 'Emissive tube, object UVs.' },
  lantern_paper: { family: 'light', tech: 'keep', note: 'Object UVs.' },
  lantern_andon: { family: 'light', tech: 'keep', note: 'Object UVs.' },
};

// extra demo-only material: pool floor = paving under water with caustics
export const KZM_DEMO = {
  pool_floor: { ...KZM.paving, caustics: 1.0, settings: { wetness: 1 }, note: 'paving + kzCaustic' },
};
