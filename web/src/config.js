// Runtime constants. Keep in sync with ASSET_CONTRACT.md.
export const EYE_HEIGHT = 1.6; // m above the walk surface
export const CAPSULE_RADIUS = 0.3; // m
export const CAPSULE_TOP = 1.75; // m above the feet
export const STEP_HEIGHT = 0.2; // m, max step-up (layout risers are <= 0.175)
export const GRAVITY = 9.81;
export const WALK_SPEED = 1.5; // m/s
export const RUN_SPEED = 3.2;
export const PHYSICS_HZ = 120;

// Colour management. Blender: View Transform AgX, Look None, Exposure E (stops).
// three: AgXToneMapping with toneMappingExposure = 2^E. The manifest may override E.
export const BLENDER_EXPOSURE_STOPS = 0.0;
// Cycles Diffuse bake (Direct+Indirect, Color off) stores E such that radiance = albedo * E.
// three's Lambert divides irradiance by PI, so lightMapIntensity = PI reproduces it.
export const LIGHTMAP_INTENSITY = Math.PI;

export const TIERS = {
  low: { dprMax: 1.5, planar: 1, planarScale: 0.25, planarOwnZone: true, bloom: false, msaa: 2, labelMax: 4 },
  high: { dprMax: 2.0, planar: 2, planarScale: 0.5, bloom: true, msaa: 4, labelMax: 8 },
};

export const BLOOM = { strength: 0.08, radius: 0.3, threshold: 2.5 }; // r2: halved; lamp highlights on wet floors bloomed the arrival hall +1.3 stops // linear HDR threshold, High only

export const FOG = {
  color: [0.018, 0.015, 0.013], // linear
  density: 0.012, // 1/m, base cave haze
  mistColor: [0.15, 0.14, 0.13], // linear, steam lit by lanterns
  mistDensity: 0.55, // 1/m at the water surface
  mistHeight: 0.3, // m, e-folding height (dense in the first 0-0.5 m)
  maxWaters: 8,
  // Blender places: haze / mist colour = mean probe radiance x gain (the defaults above match a probe mean of ~0.05)
  hazeFromProbe: 0.25,
  mistFromProbe: 1.5,
  mistTint: [0.8, 0.93, 1.1],
};
