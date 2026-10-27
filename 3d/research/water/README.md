# Kazan-yu water: research and prototypes (round 2)

**Goal:** water that is cheap but beautiful in the three.js walkaround (three r186 / `0.186.1`, lightmapped scene, mid-range phones).

**What the owner asked for in round 2:**
- waves that curl;
- a laminar Kawagiri curtain;
- spray and particles that are not chintzy;
- waterfall texture without visible tiling;
- more simulation and less baking;
- emulating the best real-time water in three.js.

**What changed:**
- **The waterfall, river foam and pools are now driven by small GPU simulations:**
  - a falling-sheet sim for the waterfall;
  - foam advected along the river flow;
  - the existing ripple height-field for the pools.
- **Spray and mist are dense, physically sized, lit particles.** Lanterns light them through a forward-scattering phase, and on High they are depth-softened against the scene.
- **The curtain is a refractive glass sheet.** It parts at the nozzle and the gap falls with the water.
- **Breakers have a crest-driven curling lip.** The lip peels along the wave.
- **Pipeline:** every page now renders in linear HDR and tone-maps once.
  - High adds a scene-texture pass, which gives refraction (Evan Wallace style) and depth-softened particles.
  - Low stays WebGL2 at roughly the same cost as round 1.
- **New WebGPU experiment:** a real MLS-MPM particle fluid for the geyser pool.

**Round-1 pages** are kept for comparison under `v1/<name>/`.

## Prototypes

Open them on a phone and press **Low tier**.

| Page | What it shows now | Link |
|---|---|---|
| `river-falls/` | Thunder Curtain Falls driven by a sheet simulation, simulated foam in the plunge pool and B2 rapids, 24k lit droplets, eroded lit mist, refraction through the river (High) | https://terminal.sels.tech/lp/8742/3d/research/water/river-falls/ |
| `wave-grotto/` | Shoaling waves with steep concave faces, crest-driven plunging lips that peel along the crest, barrel shading, moonlight through the lip, lit lip spray and plunge mist, swash and wet-sand memory, refraction (High) | https://terminal.sels.tech/lp/8742/3d/research/water/wave-grotto/ |
| `hot-pool/` | Ripple-sim pool, seen through its surface on High; a 16k-droplet lit geyser jet with a 3D-noise core; volumetric-looking lit steam that also appears in the Obsidian Mirror | https://terminal.sels.tech/lp/8742/3d/research/water/hot-pool/ |
| `sheets/` | Laminar refractive Kawagiri curtain whose gap falls with the water, edge and meniscus highlights, breakup and drops only at the bottom, splash ring; infinity edge and Mist Steps with refraction | https://terminal.sels.tech/lp/8742/3d/research/water/sheets/ |
| `webgpu-geyser/` | WebGPU only. A real particle fluid (MLS-MPM, 64³ grid, 16k/32k/64k particles) filling a 6 m basin, with a timed jet. Rendering is still droplets, not a liquid surface (see §5). | https://terminal.sels.tech/lp/8742/3d/research/water/webgpu-geyser/ |

**On every WebGL page:**
- The HUD shows fps, frame ms, draw calls, triangles and texture MB.
- Buttons: **Low tier**, **camera**, **pause**, **bench**.
- URL parameters: `?t=`, `cam=`, `tier=low`, `clean`, `freeze`, `hide=<group>`, `pos=x,y,z&tgt=x,y,z`.

**Renders** are in `3d/renders/water/`:
- 1600×900 stills and `*_phone_low.jpg` (390×844 with Low tier on);
- 7-second `*_clip.mp4` files, recorded from the GPU browser:
  - `river-falls_clip`, `river-falls_rapids_clip`
  - `wave-grotto_clip`, `wave-grotto_shore_clip`
  - `hot-pool_clip`, `sheets_clip`
  - `webgpu-geyser_clip`

---

## 1. What I took from the best real-time water (code read, not screenshots)

| Source | What it actually does | Where we use it |
|---|---|---|
| **Evan Wallace, WebGL Water** ([water.js](https://github.com/evanw/webgl-water/blob/master/water.js), [renderer.js](https://github.com/evanw/webgl-water/blob/master/renderer.js)) | See notes below the table. | `hot-pool`: the same height-field sim (128² half-float, fixed 60 Hz). The surface refracts the pool; the Laplacian is used as cheap focusing. Bed caustics are bent by the sim gradient. Full caustic projection is listed under next steps. |
| **three.js `webgl_gpgpu_water` / `webgpu_compute_water`** ([files.json](https://github.com/mrdoob/three.js/blob/dev/examples/files.json)) | 128² Verlet height field, viscosity 0.93–0.96, mouse "drop" with a cosine profile. | Same sim family. Taps on the pool splash. |
| **three.js `webgpu_backdrop_water`** | Screen-space refraction: offset `screenUV` by the normal, and fall back to the unoffset UV when the sampled depth is in front of the water (leak guard). Water depth = scene depth − fragment depth. | The High tier `tScene` path in `common/kit.js`. The same leak guard is in the river, grotto, pool, infinity and curtain shaders. |
| **three.js `webgpu_compute_particles_fluid`** (MLS-MPM; follows matsuoka-601) | Kernels clearGrid → p2g1 → p2g2 → updateGrid → g2p on a 64³ grid. 32k particles by default, 131k maximum. Fixed-point atomics, stiffness 50, rest density 1.5. | Adapted in `webgpu-geyser/`, with a vent jet force and a basin. |
| **matsuoka-601/WebGPU-Ocean** ([render/](https://github.com/matsuoka-601/WebGPU-Ocean/tree/main/render)) and **Simon Green, "Screen Space Fluid Rendering for Games"** (GDC 2010) | See notes below the table. | The missing rendering step for `webgpu-geyser` (§5). |
| **Sea of Thieves, SIGGRAPH 2018** ([pdf](https://history.siggraph.org/wp-content/uploads/2022/09/2018-Talks-Ang_The-Technical-Art-of-Sea-of-Thieves.pdf)) | Waterfalls and streams run a small shallow-water sim in the mesh's texture space. Subsurface colour comes from a wave-peak mask. Foam comes from depth with feedback. | The waterfall sheet sim in `river-falls` is the same idea: a sim in the sheet's own texture space. |
| **Thürey et al. 2007, "Real-time breaking waves for shallow water simulations"** ([patent](https://patents.google.com/patent/US8204725)) | Detect steep fronts, trace a "wave line" polyline, and spawn a particle-driven sheet that falls ballistically and pushes water back on impact. | The grotto lip strips are the analytic version: the crest line comes from the wave model, and the sheet is an arc thrown from the crest. |
| **Fournier & Reeves 1986** (via survey [arXiv 1109.6494](https://arxiv.org/abs/1109.6494)) | Elliptical orbits that flatten and tilt in shallow water, plus a phase lag of the high points, give a forward-leaning crest that curls. | Grotto base waves use the explicit steep, concave front profile; the overhang is left to the lip strip. |
| **Mei et al. 2007 virtual pipes** ([WebGL demo source](https://github.com/LanLou123/Webgl-Erosion/blob/master/src/shaders/flow-frag.glsl)) | A GPU shallow-water solver with flux per neighbour. | The candidate for interactive rivers in a later round (§6). |
| **Valve, "Water Flow in Portal 2"** ([pdf](https://www.advances.realtimerendering.com/s2010/Vlachos-Waterflow(SIGGRAPH%202010%20Advanced%20RealTime%20Rendering%20Course).pdf)) | Two-phase flow-map blending with a noise phase offset. | River normals and foam lace. The foam *density* now comes from the advection sim. |

**Evan Wallace, WebGL Water: what the code does**
- Simulation:
  - 256² float height field.
  - Each step: `vel += (avg4 − h)·2; vel *= 0.995; h += vel`, two steps per frame.
  - Normals are taken from neighbour cross products.
- Shading:
  - Ray-traces the pool box analytically for refraction and reflection.
  - Fresnel is `mix(0.25, 1, (1 − N·V)³)`.
- Caustics:
  - Rendered into a 1024² texture by projecting the refracted surface mesh onto the floor.
  - Brightness is `oldArea/newArea`, computed with `dFdx`/`dFdy`.

**matsuoka-601/WebGPU-Ocean and Simon Green (GDC 2010): screen-space fluid rendering**
1. Sphere-impostor depth into an `r32float` target.
2. Separable bilateral depth filter, with a filter size that scales with 1/depth, run for 4 iterations.
3. Additive thickness pass, then a Gaussian blur.
4. Normals from depth.
5. Composite: `bg·exp(−k·thickness·(1 − waterColour))` mixed with the cubemap by Fresnel, plus specular.

**Other sources:**
- Catlike Coding, [Texture Distortion](https://catlikecoding.com/unity/tutorials/flow/texture-distortion/)
- Klemen Lozar, [Frame Blending with Motion Vectors](https://klemenlozar.com/frame-blending-with-motion-vectors/)
- Qualcomm, [Adreno best practices](https://docs.qualcomm.com/bundle/publicresource/80-78185-2/topics/mobile_best_practices.md): `discard` and alpha-test cost early-Z/LRZ; prefer blending.

**WebGPU availability:**
- Chrome 121 and later ships WebGPU on Android 12+ devices with Qualcomm or ARM GPUs ([Chrome blog](https://developer.chrome.com/blog/new-in-webgpu-121)).
- Safari 26 ships WebGPU on iOS. This is per WebKit's Safari 26.0 release notes, quoted in WebKit bug 299237; I could not open the post itself.
- At least one Safari 26 report had `navigator.gpu` undefined, so a WebGL2 fallback is required.

---

## 2. Technique per water type (round 2)

Phone costs in the table:
- They are estimates for a mid-range 2023 phone at the Low tier, about 0.75 Mpx.
- "Same as round 1" means measured against the v1 page under the same GPU load (§4).

| Water type | Technique now | Simulation or stateless? | Low tier (WebGL2) | High tier |
|---|---|---|---|---|
| **Waterfall** | 2 ballistic sheets textured by the **sheet sim**: 256 columns across the lip × 112 rows, one row per 1/60 s of fall. Lip supply varies along the lip and over time. Parcels drift sideways, surface tension pulls them into strands, buffeting comes from 3D noise, and aeration grows with fall and shear. Fine fibres come from a 64³ 3D noise in material coordinates. White where aerated; thin glassy water is refracted and teal-tinted on High. | **Sim:** 256×112 RGBA16F, about 30k texels per step. | 1 sheet. Sim unchanged (it is cheap). | 2 sheets plus refraction of the cliff through the glassy top. |
| **Spray and mist** | Droplets 6–16 mm, never thinner than about 1.3 px; alpha is reduced when the clamp applies, so energy is conserved. One frame of motion blur. Lit per vertex with an 8-light list and Henyey-Greenstein g ≈ 0.6. Shed from the sheet where the sim says it is aerated. Mist and churn: many low-alpha particles eroded by animated 3D noise, lit with a mostly isotropic phase. | Stateless (seed, time), gated by sim textures. | 3k droplets, 70 mist, 160 churn, at higher alpha. Analytic water-plane fade. | 24k droplets, 420 mist, 1000 churn, depth-softened against the scene. |
| **Rivers and rapids** | **Foam advection sim** on the river domain: 128×352 RGBA16F, second-order semi-Lagrangian along the flow field. Sources: plunge line, drop faces, boulder pillows and shoulders, with gusty 3D-noise modulation. Decay 0.22/s. Standing waves stay stationary; detail lace is two-phase advected. | **Sim:** 45k texels per step. | Same sim, one normal octave. | Refraction of the bed through the surface. |
| **Ocean breakers** | Explicit crest-relative profile: gentle back slope, and a front face that shrinks to about 0.75 H after the per-wave breaking depth (Green's law, H/D ≈ 0.9). **Lip strips**, one per crest in the surf zone, are a spiral arc thrown from the crest. The arc length follows the breaking stage, which varies along x, so the lip **peels**. The barrel interior is darker, the face under the lip is shaded as a barrel, and moonlight shines through the thin lip. Lip spray and plunge mist are born on the lip. Swash and wet sand are as in round 1. | Stateless; analytic crest lines. | 100×12 lip strips, half grids, 3k spray. | 220×24 lip strips, refraction through faces and the lip. |
| **Thin sheets** (curtain, infinity edge, Mist Steps) | Curtain: a **laminar** cylinder sheet, see notes below the table. | Stateless; nozzle gate. | Glass via Fresnel reflection, edge and meniscus glow, and a little tint, with no refraction. | Refraction of the pod through the sheet. Far half drawn first, near half lets about 20% through. |
| **Bubbling pools and geyser** | Ripple sim as in round 1. On High you look into the pool through the rippled surface. Geyser: 16k lit droplets (drag varies with size, so small drops form a mist sheath), a 3D-noise core that rides up with the water, and lit eroded steam (220 plume, 260 wisps, 90 fumarole). | **Sim** (ripples) plus stateless particles. | 64² sim, 4k droplets, about 140 steam particles. | Also reflected in the Obsidian Mirror: layer 2 is visible to the reflection camera; droplets are excluded. |
| **Obsidian Mirror** | Half-res planar reflection on High. The reflection camera sees opaque objects plus the geyser column and steam (layer 2). | — | Baked probe. | Planar reflection. |
| **Mist layer over water** | As in round 1: analytic height fog in every shader. | — | Same. | Same. |
| **WebGPU fluid** (experiment) | MLS-MPM, 64³ grid, 16k/32k/64k particles, vent jet force on a timer. | **Full particle fluid.** | Not available on Low. | Desktop only until screen-space fluid rendering lands. |

**Curtain technique, in full:**
- **Ripples:** streamwise ripples are carried at free-fall speed, so they stretch as the water accelerates.
- **Highlights:**
  - Fresnel against the cave probe;
  - sharp lantern highlights;
  - light escaping at grazing angles (edges);
  - a bright gutter meniscus.
- **Breakup:** the sheet breaks into strands only in the last 12% of the fall. Drops are lit by the lanterns, and a splash ring forms where the sheet lands.
- **Gap:** decided per nozzle from where the server was when that water left the gutter. Valves lead the server by 0.35 s. The gap then falls with the water, and its edges have thickened bright rims.

**Kit changes the runtime should copy (`common/kit.js`):**
- **Render all water pages in linear HDR, then apply AgX once.**
  - three.js applies tone mapping inside each material when drawing to the canvas.
  - With dozens of stacked low-alpha mist layers, each faint layer is lifted by AgX before blending, and the result blows out to white. This was visible in the first round-2 Low-tier phone shot.
  - The fix: one RGBA16F target plus an output pass. On a phone this costs about 0.3–0.5 ms.
- **High tier:**
  1. Opaque objects (layer 0) render into target A, with a float depth texture.
  2. A half-res copy into B: rgb is scene colour, a is linear view depth.
  3. Effects (layers 1–2) render into A and sample B for refraction, soft particles and thickness.
  4. Output to the screen.
- **Effect layers:** `app.fx()` puts a mesh on layer 1; `app.fxReflected()` puts it on layer 2, which planar reflections also see.
- **Shared GLSL:**
  - `GLSL_FRAG`: `sceneColor`, `sceneGap`, `softFade`, plus the leak guard.
  - `litScatter()`: an 8-light HG + isotropic phase.
  - `tNoise3`: a 64³ tileable 3D noise baked on the GPU at load into a `WebGL3DRenderTarget`. It holds fBm, a second fBm, turbulence and Worley, and is 1 MB.
- **`createSim()`, `fixedStep()`:** ping-pong float sims at a fixed rate.

## 3. What we will NOT do, and why (updated)

- **SPH, PBF or MLS-MPM on Low.**
  - The WebGPU experiment runs, but it needs compute shaders, storage buffers and atomics, and still lacks its surface pass.
  - Use it only as an opt-in WebGPU High tier for one or two hero pools, if at all.
- **Refraction on Low.** The scene copy plus the extra pass, about 1 ms on phones, buys too little in a dark cave. Low uses probe reflection and bed-side absorption.
- **Flipbook or tiled waterfall textures.** The sheet sim costs less than a 1024² flipbook and never repeats.
- **FFT ocean.** The grotto is shaped by its beach. FFT is only worth considering for the open sea beyond the mouth, on High.
- **VAT splashes.** They loop visibly at walking pace. Simulated and stateless particles look better and use no memory.

## 4. Measurements and the phone estimate

**Measurement caveat:**
- During round 2 the RTX 4090 sat at 100% because of 4–5 concurrent Blender Cycles renders from other sessions.
- All numbers below are therefore inflated and noisy. Only same-session ratios are trustworthy.
- Raw output: `.scratch/water/bench2.txt`.

**Per-page numbers (bench: back-to-back renders with a readPixels sync, under contention):**

| Page | Tier, pipeline | Calls | Visible tris | 1600×900 | 3840×2160 |
|---|---|---|---|---|---|
| river-falls | High, scene texture | 14 | 206k | 3.9 ms | 16.4 ms |
| river-falls | Low, HDR single pass, before trimming | 13 | 86k | 1.9 ms | 9.2 ms |
| wave-grotto | High | 13 | 258k | 1.7 ms | 4.0 ms |
| wave-grotto | Low | 12 | 72k | 1.1 ms | 3.4 ms |
| hot-pool | High | 23 | 273k | 1.8 ms | 7.4 ms |
| hot-pool | Low | 13 | 48k | 0.8 ms | 2.2 ms |
| sheets | High | 25 | 70k | 0.9 ms | 4.2 ms |
| sheets | Low | 24 | 45k | 0.4 ms | 2.2 ms |

Texture memory is 4.8–6.0 MB per page, including the sims, the 3D noise and the probe.

**Same-session v1 vs v2 at 4K:**

| Comparison | v1 | v2 | Ratio |
|---|---|---|---|
| river-falls, High | 4.3 ms | 17.2 ms | 4.0× |
| hot-pool, High | 2.4 ms | 5.5 ms | 2.3× |
| river-falls, Low (after trimming counts) | 2.0 ms | 2.6 ms | 1.3× |
| hot-pool, Low | 2.9 ms | 2.5 ms | 0.9× |

**Verdict:**
- **Low tier costs about what round 1 cost**, which was estimated at 3–6 ms for all water on a mid-range phone, plus about 0.3–0.5 ms for the HDR output pass.
- It is still at the edge of the 3–5 ms budget in the busiest views. The levers are the same: sprite count and size at the waterfall base and in the geyser plume.
- **High tier is 2–4× Low.** That is fine on desktop and recent flagship phones, not on mid-range ones.
- **The WebGPU fluid** ran at about 20 fps under the same contention (64k particles plus 262k-cell grid clears per step). It is a desktop experiment until measured on a quiet GPU and a real device.
- **The real check:** open the links on the owner's phone with Low tier on and read the HUD fps.

## 5. Honest status: what still looks fake

**Waterfall: much better.**
- Heavy, white, evolving strands, no tiling, a lit mist halo, lantern-lit spray.
- Still fake:
  - The sheet is two cards, so there is no volume in close-ups from the side.
  - The base explosion is softer than in concept 19. Bloom would help.
  - Foam in the plunge pool still reads slightly "dappled".

**Rapids: improved.**
- Foam forms behind boulders and drop faces and streams away.
- Still fake: water heights are a stationary noise, not a true shallow-water solution, so there is no real hydraulic jump.

**Breakers: improved, but not yet good enough.**
- The lip curls and peels, and reads well at oblique views (`wave-grotto_hero.jpg`).
- Still fake:
  - Face-on from the beach, the lip mostly reads as a glowing band with whitewater.
  - The base face is smooth, with no streaks or ridges.
  - The lip geometry is clean and tube-like in places.
  - There is no wave-to-wave interaction.
- The next steps are a hero breaker mesh with authored variation, and spray sheets torn off the lip.

**Curtain: now a laminar glass sheet.**
- Refraction, rim highlights and a gap that falls with the water all work.
- Still fake:
  - The far half shows a busy streak pattern from refracted background lights.
  - On Low there is no refraction, so it reads as a soft glassy veil.

**Geyser and steam: much better.**
- Lit, volumetric-looking steam, a dense lit jet, and both reflect in the mirror.
- Still fake: the core is still a textured cylinder inside the droplets.

**WebGPU fluid.**
- The simulation is real and looks physically right in motion.
- Rendered as glossy beads, it looks like a pile of marbles, not water. It needs screen-space fluid rendering:
  1. sphere depth;
  2. a bilateral or narrow-range filter;
  3. thickness;
  4. Beer-Lambert absorption over refracted background, plus Fresnel.
- That is about 5 fullscreen passes. It is not built yet.

**Placeholders:** rocks, lanterns and stalactites are placeholders, with vertex-colour stand-ins for lightmaps.

## 6. Implementation plan (ordered, for generator and runtime agents)

1. **Runtime: adopt the kit pipeline.**
   - HDR target with tone mapping once.
   - Scene-texture pass on High.
   - `fx` / `fxReflected` layers.
   - Fixed-rate sims.
   - Shared `tNoise3` and `litScatter`.
   - Do not use `powerPreference: 'high-performance'`: it fails to create a WebGL2 context in the GPU browser (ANGLE/Vulkan). `web/src/main.js:48` uses it inside a try.
2. **Runtime: bed shading via `onBeforeCompile`** (absorption, caustics, wet band), driven by an `aLevel` vertex attribute.
3. **Generator: water-body schema in the space files.**
   - Waterfalls: lip polyline, launch velocity, sheet-sim resolution.
   - Rivers: centreline, drops, boulders.
   - Beaches: slope, P, A.
   - Pools: vents.
   - Curtains: radius, height, server-path hook.
   - Also: the flow-map baker writing a *generation* channel rather than baked foam, and bed `aLevel`.
4. **Runtime: waterfall sheet sim, base particles, river foam sim.** Thunder Curtain Falls and the B2 river first.
5. **Runtime: pools.** Ripple sim (one per visible pool), geyser timer, steam sets, Obsidian Mirror (planar on High, probe on Low).
6. **Runtime: Kawagiri curtains.** The NPC server feeds the nozzle gate, a short history of positions as a uniform array.
7. **Runtime: Wave Grotto.** Profile, lip strips and swash. Then a hero breaker pass: authored lip variation and torn lip sheets.
8. **Optional High tier (WebGPU):** add screen-space fluid rendering to `webgpu-geyser` and evaluate it for the geyser plaza and the falls base. Only if it beats the WebGL2 look on a real phone.
9. **QA:** measure on a real phone on a quiet machine. Tune sprite counts per tier. Then a Cycles-vs-browser AgX colour check.
