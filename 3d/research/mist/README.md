# Kazan-yu mist: a cheap Navier–Stokes mist layer on another thread

**Goal (the owner's ask):** "some kind of cheap navier stokes fog or mist on another thread", for the low white mist over every water surface (concept 05, 12, 15, 16, 19, 20). The mist must run on phones in the three.js walkaround (r186).

**Bottom line**
- A 2D stable-fluids solver runs in a module Web Worker at 20 Hz (Low) or 30 Hz (High). It posts one RGBA8 field per step: density, heat, and velocity. The ArrayBuffer is transferred, not copied.
- The main thread interpolates the two latest fields on the GPU. The shader turns the field into a height-fog layer 0–0.5 m deep (taller over hot water and spray). The layer is lit by lanterns and by teal light from the water.
- **Threading works.** With the worker, the main thread spends **0.01–0.05 ms per frame** on the mist. With the solver on the main thread it spends 0.2–2 ms on this desktop, and **1.1–7.3 ms with the CPU throttled 4×** (a phone-class main thread). The worker step does not change under throttling, because DevTools throttling only applies to the main thread.
- **Desktop step cost** (Ryzen 9 9950X, Chromium 155): 0.4 ms at 64² and 1.8 ms at 128². **Phone estimate:** about 1.6–2.4 ms at 64² and 7–11 ms at 128², per step, on the worker thread. At 20 Hz, 64² uses about 3–5% of one phone core. So Low is 64² at 20 Hz, and 128² is for desktop High only.
- **Looks:** the corridor is closest to concept 05. The mist banks against the walls and around the lanterns, the centre line stays clearer where guests walk, and a walker leaves a trough. The hot pool and the falls read correctly but are plainer than the concept. See "Honest status".
- **GPU cost** is the open risk. On Low the estimate is about 1 ms per frame on a mid-range phone (±50%; method in §4). That is several times the 0.1–0.3 ms the water README budgets for analytic mist. The cuts are listed in §4.

## Prototypes

Open them on a phone; Low is the default there.

| Page | Shows | Link |
|---|---|---|
| `corridor/` | B1 Kiri-no-Michi (`b1_cor_mirror`). Geometry comes from `layout.json` and the space file: footprint mask, water path, niche lanterns, shoji bays, the dark arch with the teal leak. You walk with WASD or touch, and a guest walks the stones; both are moving obstacles in the sim. | https://terminal.sels.tech/lp/8742/3d/research/mist/corridor/ |
| `hot-pool/` | A grotto pool at 45 °C with a 55 °C upwelling. Four fumarole vents burst every 4–9 s, and a draft pulls steam out through the east arch. | https://terminal.sels.tech/lp/8742/3d/research/mist/hot-pool/ |
| `falls/` | The base of Thunder Curtain Falls. Pool and lip come from `layout.json`. Air dragged down by the sheet spreads out as a gust over the pool and carries the spray mist outward in eddies. The curtain is a cheap stand-in. | https://terminal.sels.tech/lp/8742/3d/research/mist/falls/ |
| `bench/` | The same solver, stepped in a worker and on the main thread, for grid sizes 32²–256². | https://terminal.sels.tech/lp/8742/3d/research/mist/bench/?auto |

**HUD on every page:**
- Main thread: fps, frame ms (and worst), and JS+submit ms. Also the mist's own main-thread JS per frame, average and max.
- Worker: step ms (and p95) and the actual sim Hz.
- Grid size, cell size, fluid cells and solver iterations.
- Memory for the sim and the textures, and GPU draw calls.

**Buttons:** Low/High, **sim: worker / main thread** (the threading comparison), mist on/off, camera, walk (corridor only) and bench.

**URL parameters:**
- `tier=low|high`, `mode=worker|main`, `cam=N`, `clean` (no HUD).
- `field=1` shows the live sim field as an overlay.
- `pos=x,y,z&tgt=x,y,z` sets the camera.
- `follow` (corridor) trails the guest with the camera.
- `offline` renders frame-locked, for clips.

## 1. How it works

### Solver (`mist-worker.js`, about 460 lines, plain JS typed arrays)
- **Grid and pressure:** a MAC (staggered) grid with a solid mask (Müller, Ten Minute Physics #17). Pressure uses Gauss-Seidel with over-relaxation 1.9, in red-black order so the sweep does not drift the mist sideways. Low uses 12 sweeps and High 16.
  - Each sweep can include a **divergence source** (1/s), for steam expanding out of a vent or the down-draft spreading from under a waterfall.
  - Open domain edges act as p = 0. Closed rooms subtract the mean source, which means the extra air leaves the layer upward.
- **Advection:** semi-Lagrangian advection of velocity, density and heat (Stam 1999), bilinear, with 2 scratch fields.
- **Vorticity confinement:** f = ε·h·(N × ω) (Fedkiw/Stam/Jensen 2001; GPU Gems 38).
- **"Buoyancy" in a horizontal layer:** heat cannot rise in 2D, so heat does three things here:
  - it raises the layer locally, because the renderer maps heat to layer height, up to Hmax;
  - it lifts mist out of the layer (a loss rate proportional to heat);
  - over vents it comes with an expansion source.

  Dense mist also **slumps**: a gravity-current force −g′∇ρ makes it spread and pool like dry-ice fog.
- **Sources from temperature:** the evaporation rate is the excess saturation vapour pressure of the water over cave air (Magnus formula, 28 °C, RH 0.9). That gives 0.3 at 34 °C, 0.6 at 39 °C, 1.0 at 45 °C, 2.1 at 55 °C and 3.6 at 65 °C. A drifting value-noise multiplier breaks the evaporation into thermals and patches; without it the layer is a flat sheet.
- **Swirl and inputs:**
  - **Vorticles** (after Ghost of Tsushima's wind): 10–16 short-lived swirls spawned over the water that drift with the flow.
  - **Drafts:** a per-cell wind field that velocity relaxes toward (portal drafts).
  - **Jets:** inflows and spray lines.
  - **Timed bursts:** geysers and fumaroles, with a fast rise and slow tail.
- **Guests (`setMovers`):** each guest is a disc obstacle moving at walking speed, so the pressure solve pushes the mist aside.
  - A mixing disc behind the walker thins the layer into the clear air above (legs stirring).
  - Alternating eddies are shed every 0.45 m walked.
  - The trough fills back in over several seconds.
- **Output:** RGBA8 per cell.
  - R is the square root of density (more precision in thin mist).
  - G is heat, 3×3 blurred so plume tops stay round.
  - B and A are velocity in ±3 m/s.
  - Solid cells are filled with the mean of their fluid neighbours, so there is no dark seam along walls.

### Threading (`mist.js` → `MistZone`)
- **Worker:** `new Worker(new URL('./mist-worker.js', import.meta.url), {type:'module'})`, written inline in that form so Vite bundles it. The worker runs a fixed-rate loop and never spirals: it does at most 2 catch-up steps.
- **Buffers:** a pool of 3 ArrayBuffers moves back and forth with zero-copy transfer. On receipt, the main thread copies the frame into the older of its two textures (one `texSubImage2D` of 17–64 KB) and returns the buffer.
- **Interpolation:** the shader mixes the two textures with `uMistBlend = (now − received) / period`, so it shows one sim step of latency.
- **Motion between steps:** a two-phase flow noise (Vlachos 2010) advects fine detail with the sim velocity at the display rate.
- **Main-thread mode:** the same class can step the solver on the main thread instead (`mode=main`). That is the comparison mode.
- **Restarts:** on a tier change the zone re-rasterizes its masks and prewarms 6–14 s of simulation inside the worker before the first frame. That takes 80–600 ms on desktop and never blocks the main thread.

### Rendering (`MIST_GLSL` in `mist.js`)
- **Where it runs:** the mist is a function every surface shader calls, `mistApply(col, worldPos)`, exactly like the runtime's `kzFogTerms`. There are no extra passes, no depth texture and no volume texture.
- **Clipping:** the ray from the camera to the surface is clipped to the zone's slab: its rectangle × [water y, y + 1.45·Hmax].
- **Low (analytic):** the in-slab piece is split in two, with a fixed 2.5 m split from where the ray enters the layer.
  - Each half gets one field tap and one flow-noise tap. Its vertical profile (1 − h/Ht)³ is integrated **exactly** along the straight half.
  - Lighting is evaluated once per half with the first 3 lights.
  - The taps sit at fixed distances, not segment fractions, so neighbouring pixels on bumpy walls share taps. Fraction-based taps striped the walls.
  - In total: 8 texture fetches and about 260 ALU per pixel.
- **High (raymarch):** 3–14 slices, proportional to the path length in the layer (0.3 m spacing), with a static interleaved-gradient jitter.
  - Each slice reads the field, the flow noise, a coarse "billow" height field for a lumpy top silhouette, and 3D noise for wisps.
  - Each slice is lit by 6 lights with a Henyey-Greenstein lobe (g = 0.6), which gives the lantern halos.
  - Fine detail fades out where the slices are too far apart to resolve it. Without that, the layer's top aliases into hair-like spikes.
- **Lighting:** the in-scatter combines lanterns (warm, HG lobe), teal light from the water (exponential with height above the water), ambient and a little heat brightening. The mist has no colour of its own, so it takes the light of the place.
- **Blended surfaces** (curtains, spray, foam): use `mistApplyPM`, which only fades the surface by the mist in front of it. The opaque surface behind already carries the mist of the whole ray, and adding the in-scatter again doubled it (a bright rectangle at the falls base).

### Coupling the 2D sim to 3D (the 2.5D trick)
The sim is the layer's **plan**: how much mist sits over each square metre, how hot it is, and where it is moving. The vertical shape is procedural: a profile scaled by heat, a lumpy top and wisps.

This is the same split games use for ground fog. A 2D or analytic density drives a height-fog term in the surface shaders, and the volumetric froxel fog of Frostbite, AC4 and RDR2 is the expensive general version.

Ghost of Tsushima drives particles and grass from cheap wind "vorticles" and height-map lookups rather than a full sim. The water agent's spray and steam particles could sample this field's velocity the same way (see §3).

## 2. Measurements

**Setup:**
- Desktop: Ryzen 9 9950X and RTX 4090, Chromium 155 on ANGLE/Vulkan, in the lead's GPU browser on CDP 9310.
- `performance.now()` is coarsened to 0.1 ms because the page is not cross-origin isolated, so values ≤ 0.1 ms read as 0.0–0.1.
- **The shared machine was heavily loaded during this work:** CPU load average 5–68, and the GPU at 100% from 4–5 other agents' Cycles jobs. CPU numbers come from the quietest run (load average about 5). GPU numbers are bounds, not clean timings.
- Raw output is in `.scratch/mist/bench_cpu.txt`, `bench_modes.txt` and `bench_gpu.txt`.

### Solver step per grid size (`bench/`, median of 200 steps)

A square pool domain with a jet, a burst, a walker and 10 vorticles. Iterations are 12 at ≤ 64² and 16 above.

| Grid | Cells | Worker, desktop | Main thread, desktop | Main, CPU 4× | Main, CPU 6× | Pack | Sim memory |
|---|---|---|---|---|---|---|---|
| 32² | 1 024 | 0.1 ms | 0.1 ms | 0.4 ms | 0.8 ms | 0.04 ms | 0.08 MB |
| **64²** | 4 096 | **0.4 ms** | 0.4 ms | **1.6 ms** | **2.4 ms** | 0.09 ms | 0.30 MB |
| 96² | 9 216 | 1.0 ms | 1.0 ms | 4.0 ms | 6.1 ms | 0.12 ms | 0.66 MB |
| **128²** | 16 384 | **1.8 ms** | 1.8 ms | **7.1 ms** | **10.9 ms** | 0.17 ms | 1.16 MB |
| 192² | 36 864 | 4.1 ms | 4.1 ms | 16.2 ms | 25.2 ms | 0.28 ms | 2.58 MB |
| 256² | 65 536 | 7.2 ms | 7.4 ms | 29.5 ms | 44.0 ms | 0.42 ms | 4.57 MB |

- **Transfer round trip** (a frame to a worker and back): ≤ 0.1 ms at every size.
- **Node 22**, the same code: 64² takes 0.41 ms, 128² 1.84 ms and 256² 8.3 ms.
- **Projection quality:** 16 SOR sweeps remove about 77% of the divergence per step, 24 sweeps about 90%, and 40 sweeps about 96%.
  - These are tested with an open outlet. A closed room with a net source plateaus, which is why the code subtracts the mean source (`divBalance`).
  - Pressure stays approximate, as in every game solver (Stam 2003 uses 20 Gauss-Seidel sweeps, GPU Gems recommends 20 or more Jacobi iterations, and Pavel's demo uses 20). The look holds because velocity persists from step to step.

### Worker vs main thread inside the prototypes (6 s per run)

"mist JS" is the main-thread time the mist takes per frame: messages, upload and, in main mode, the solver step.

| Page / tier (grid) | Worker: mist JS avg / max | Main thread: avg / max | Main thread, CPU 4×: avg / max |
|---|---|---|---|
| corridor Low (125×34 @ 25 cm) | 0.013 / 0.1 ms | 0.29 / 0.7 ms | 1.34 / 5.1 ms |
| corridor High (250×69 @ 12.5 cm) | 0.039 / 0.2 ms | 0.90 / 2.9 ms | 3.27 / 8.1 ms |
| hot-pool Low (64×64 @ 25 cm) | 0.010 / 0.1 ms | 0.19 / 1.2 ms | 0.64 / 2.8 ms |
| hot-pool High (128×128 @ 12.5 cm) | 0.011 / 0.1 ms | 1.78 / 3.6 ms | 6.79 / 14.7 ms |
| falls Low (64×60 @ 60 cm) | 0.016 / 0.1 ms | 0.29 / 1.0 ms | 1.11 / 3.4 ms |
| falls High (129×120 @ 30 cm) | 0.014 / 0.1 ms | 2.10 / 3.9 ms | 7.34 / 20.2 ms |

- With the CPU throttled 4×, the worker numbers did not move: 0.013–0.046 ms average. Only the main thread is throttled.
- In main mode on a phone, the High solver alone would take a 14–20 ms bite out of some frames. That is a visible hitch at 60 Hz, and the worker removes it entirely.
- The fps figures in the raw file were limited by the shared GPU, not by the mist, so they are not quoted.

### Phone estimate (worker step)
**Method:**
- Chrome DevTools CPU throttling slows only the main thread. So the throttled main-thread runs of the same solver stand in for a phone core.
- Chrome's own calibration post says a fixed multiplier means different things on different machines. The 9950X is among the fastest single-thread CPUs, so 4× is taken as a recent mid-range phone and 6× as an older or low-end one.
- This is UNVERIFIED on a device.

**Result, per step on the phone's worker core:**
- 64²: about 1.6–2.4 ms; at 20 Hz that is 3–5% of a core.
- 125×34 (the corridor on Low): about 1.3–2 ms.
- 128²: about 7–11 ms; at 30 Hz that is 21–33% of a core.

**Recommendation:** Low uses a grid of about 64² or fewer cells at 20 Hz. High (128², 30 Hz) is for desktop only. One zone is live at a time.

### Memory per zone
- **Sim:** 17 float fields × (nx+2)(ny+2) × 4 B. That is 0.30 MB at 64² and 1.16 MB at 128², plus 3 transfer buffers of 16–64 KB.
- **GPU:** 2 RGBA8 field textures (32 KB at 64², 128 KB at 128²), plus the shared noise: 256² RGBA8 with mips (0.35 MB) and 32³ RGBA8 (0.13 MB).

### GPU cost of the mist (contended GPU: lower bounds)
**Method:**
- `bench` renders N frames into an offscreen target with the mist on, then off, then on, and syncs with a 1-pixel `readPixels`.
- Each case ran 7 times at 3840×2160. Because other jobs only ever add time, the minimum is the best estimate of the true cost.

**Minimum mist cost at 4K, Low → High:**

| Page | Low | High |
|---|---|---|
| corridor | 0.09 ms | 0.9 ms |
| hot pool | 0.12 ms | 1.0 ms |
| falls | 0.17 ms | 5.2 ms (a 6.5 m slab, so 14 slices on most pixels) |

The medians were 2–20× higher, which is the contention, not the mist.

**Phone estimate for Low:**
- The water README's formula, (4K ms ÷ 8.3 Mpx) × 0.75 Mpx × 80–150, gives 0.6–2.3 ms.
- An op count gives the same range. Low costs about 260 ALU and 8 fetches per covered pixel; at 0.75 Mpx on a ~1 TFLOP Adreno 6xx/7xx that is ≈0.4 ms ideal, so ≈1 ms realistic.
- **So about 1 ms ±50%.**

**Cuts, if the device says so:**
1. One tap instead of two on Low: about −45%.
2. `MIST_NL = 2` lights.
3. Skip the mist on surfaces more than about 25 m away, where the base haze takes over.
4. Evaluate the mist only on the floor, water and wall shaders, not on small props.

## 3. Integration

### With the runtime (do not edit `web/`; these are proposals)
- **`runtime-materials.patch`** is a unified diff against `web/src/materials.js`. I smoke-tested it from `.scratch/mist/patch/b/test.html`: both tiers compile, there are no shader errors, and the zone writes into the shared `KZ` uniform objects. The patch:
  - imports `MIST_GLSL` and `MistZone` from a proposed `web/src/mist/` (copy `mist.js` and `mist-worker.js` there unchanged);
  - creates one stable uniform block `MIST_U` and spreads it into `KZ`, so `water.js`'s two-pass water picks the mist up with no change;
  - in `kzFogTerms`, skips the analytic layer of the water index `kzMistWater` while a zone is live, and composites `mistTerms(wp)` over the base haze and the remaining analytic layers;
  - adds the tier to the program cache key and defines `MIST_HIGH` (10 slices) on High.
- **The runtime must also:**
  1. **Create the zone:** when the camera enters a space with a `mist` block, call `new MistZone({ uniforms: KZ, ...block, look: { haze: 0 } })` and `zone.setNoise(noise2D, noise3D)`, then `zone.start(tier, 'worker')`. Stop it when the camera leaves. Prewarm runs in the worker, so there is no hitch.
  2. **Each frame:** call `zone.setMovers([{ x, z, vx, vz, r: 0.3 }])` from `walk.js` with the player's three.js X/Z position and velocity, plus any NPCs. Then call `zone.update(performance.now(), kzTime)`.
  3. **Mist lights:** `zone.setLights()` with the 3 (Low) or 6 (High) lanterns nearest the camera, from the space's `lights` and `anchored` entries. Put the most important light first: Low uses the first 3.
  4. **Events:** geyser and fumarole timers call `zone.event({...})`. These are the same timers that drive the water agent's geyser.
- **Proposed `mist` block for space files** (the lead owns `3d/spaces/` and `SCHEMA.md`). `rect_xy` is in layout coordinates [minx, miny, maxx, maxy]; the runtime converts it with `boundsToXZ`. All values are in metres:
  ```json
  "mist": { "water": "w_cor_mirror", "rect_xy": [64.4, 86.0, 95.6, 94.6],
            "H0": 0.5, "Hmax": 0.85, "sigma": 5.0,
            "tiers": { "low": { "h": 0.25, "hz": 20, "iters": 12 }, "high": { "h": 0.125, "hz": 30, "iters": 16 } },
            "open": ["portal:p_b1_cor_mirror", "portal:p_b1_junction_mirror"],
            "wind": { "along": "water.path", "speed": 0.1 },
            "sources": { "water_temp": 34, "kerb_temp": 35.5 },
            "vents": [], "jets": [], "params": { "wakeMix": 3.0, "srcScale": 0.26 } }
  ```
  - The solid mask comes from the footprint. The prototype rasterizes `b1_cor_mirror`'s footprint with `pointInPoly`.
  - Temperature comes from `layout.water[].temp`.
  - Open edges come from portals.
  - Values for the other two spaces are at the top of `hot-pool/index.html` and `falls/index.html`.

### With the water agent's work (`3d/research/water/`)
- **Division of work:** mist is only the low layer. Spray streaks, spume, billow sprites, steam wisps, the geyser column and the curtain all stay with the water agent. The falls page's curtain is a deliberately plain stand-in.
- **`kit.js` analytic fog:** the water kit's analytic `fogAmount` 0–0.5 m layer is what `MIST_GLSL` replaces wherever a zone is live. Elsewhere, the runtime's existing analytic `kzWaterMist` layer stays the fallback, so distant pools still look misty.
- **Cheap wins for the water effects:**
  - Their steam and spume sprites can read `tMistB` (velocity in B/A) to drift with the same air: one fetch in the vertex shader, sampled per sprite.
  - The geyser timer should call `zone.event`, so the eruption also pushes the low mist outward.
- **Blended water surfaces:** these should composite mist with `mistApplyPM`, which only fades. The kit's `applyFogPM` adds fog colour scaled by alpha, which double-counts in-scatter once a dense live layer sits in front of an already-fogged background.

## 4. Research notes

### Why this solver
- **Stam 1999, "Stable Fluids":** semi-Lagrangian advection plus a projection is unconditionally stable, so 20–30 Hz steps with dt = 1/20 s cannot blow up.
- **Stam 2003, "Real-Time Fluid Dynamics for Games":** 20 Gauss-Seidel sweeps, about 100 lines of C.
- **Harris, GPU Gems ch. 38:** the force/advect/project order, Jacobi pressure (40–80 iterations recommended, never below 20), vorticity confinement, and buoyancy from T − T₀.
- **Müller, Ten Minute Physics #17:** the MAC grid with a solid mask and SOR at ω = 1.9. Obstacles, including moving ones, come almost free with this formulation, which is why it was chosen.
- **Pavel Dobryakov, WebGL-Fluid-Simulation:** a 128² velocity sim under a 1024² dye (512 on mobile), 20 pressure iterations, and pressure carried over between frames. That is the "coarse sim, fine detail" idea, done here with flow-advected noise instead of a dye texture.

### Worker transport
- **Transferable ArrayBuffers vs SharedArrayBuffer:**
  - Transferring an ArrayBuffer is zero-copy and detaches the sender (MDN). A round trip measured ≤ 0.1 ms for 64 KB, and with a 3-buffer pool there is no garbage.
  - `SharedArrayBuffer` needs cross-origin isolation through COOP and COEP headers. Without them the constructor is hidden and `postMessage` throws (MDN). GitHub Pages cannot send those headers.
- **coi-serviceworker** emulates the headers from a service worker. **I don't think it is acceptable here, and it is not needed:**
  - the first visit reloads the page;
  - the file has to be served unbundled from our own origin;
  - COEP breaks cross-origin resources without CORP or CORS;
  - the gain over a 17–64 KB transfer at 20–30 Hz is nil.
- **OffscreenCanvas** (rendering from the worker) is not needed: the worker produces data, not pixels, and rendering stays in the main WebGL context.

### WASM SIMD vs plain JS
- The JS solver costs about 3–5% of a phone core at Low.
- WASM SIMD would need a toolchain and a `.wasm` artifact. The project has no build step for research pages, and the runtime would need a Vite wasm plugin.
- Red-black SOR does not vectorize cleanly: its stride-2 accesses would need shuffles. A Jacobi or multigrid rewrite would vectorize better.
- I did not measure WASM. The published SIMD speed-ups I found are either unmeasured blog claims or tasks unrelated to a stencil solver (UNVERIFIED). **Verdict: not worth it at these grid sizes.** Revisit only if a 128² grid on phones becomes a requirement. A coarser pressure solve (multigrid V-cycle) in JS is the better first lever.

### Games and 2.5D fog
- **Frostbite** (Hillaire 2015) and **AC4** (Wronski 2014): froxel volumetric fog with participating-media density, many lights and a lookup applied during shading. AC4 reported a fixed 1.1 ms on PS4/Xbox One. That is the expensive general solution, and on phones it is not an option.
- **RDR2** (Bauer, SIGGRAPH 2019 Advances): an integrated sky, cloud and volumetric pipeline. I could only confirm the course listing.
- **Ghost of Tsushima:** wind from "vorticles", cheap vortex primitives in a world array summed per particle query, plus height-map lookahead. This simulates wind, not fog, and I found no primary source on its ground fog.
- **What I took from these:** the plan/height split (a 2D field, procedural vertical shape) and vorticles as cheap swirl injectors on the grid.

## 5. Honest status

**Looks good:**
- **Corridor, both tiers:** knee-high mist banked against the walls and kerbs, lantern pools glowing warm inside the layer, the far stretch tinted teal by the arch, the centre line thinner where guests wade. In motion the mist drifts toward the Mirror, curls, and opens around the guest. This is the closest to concept 05.
- **Hot pool:** steam boils off the 55 °C upwelling more than off the 45 °C water. Fumarole bursts push a visible puff across the pool.
- **Falls:** a dense spray cloud sits at the impact line and spreads across the pool, low and tinted teal. It rolls onto the east deck.
- **No flicker in the clips.** Mean frame-to-frame difference is 0.2–1.6/255, with no spikes.

**Still fake or weak:**
1. **High has static dither grain** at the layer top. There is no TAA to resolve it.
2. **Low reads as a smooth sheet with a marbled texture** when you look down into it, and a faint vertical banding on far walls in the hot pool, where the layer is tall.
3. **Hot pool steam:** it does not rise in the tall columns of concept 16. The 2.5D model cannot make plumes above about 2 m; those must be the water agent's sprites. Its top edge still has some spiky fringes near the vents.
4. **Falls:** the base cloud is too uniform and too flat-topped compared with concept 19. Billows there need the water agent's spume sprites on top. The stand-in curtain looks like a card.
5. **The wake** is a subtle thinning in a trailing trough, not a crisp parting. It reads best from behind (`?follow`) and on the `field=1` overlay.
6. **Lighting** is point lights only, with no shadowing of the mist by rocks and no bloom. Lantern halos would gain a lot from the planned High-tier bloom.
7. **Stand-ins:** geometry, lanterns (boxes) and water (a dark mirror) are placeholders.

## 6. Files
- `mist-worker.js`: `MistSim` and the worker loop. The same file is imported for main-thread mode.
- `mist.js`: `MistZone` (threading, interpolation, uniforms), `MIST_GLSL`, and layout helpers (`pointInPoly`, `distToPolyline`, `layoutToWorld`).
- `common.js`: the prototype shell, with HUD, toggles, procedural noise, stand-in materials, walk controls, GPU bench and frame-locked clip mode.
- `corridor/`, `hot-pool/`, `falls/`, `bench/`: the pages.
- `tools/shot.mjs`: modes `shot`, `stats`, `bench`, `eval`, `clip` and `frames`. `THROTTLE=4` sets CPU throttling.
- `runtime-materials.patch`: the proposed `web/src/materials.js` change.
- **Renders** (`3d/renders/mist/`):
  - `*_hero.jpg` (1600×900, High), `corridor_low.jpg`, `corridor_wake.jpg`, `falls_east.jpg`;
  - `*_phone_low.jpg` (390×844, Low, HUD visible);
  - `*_clip.mp4` (8 s, 30 fps; `corridor-low_clip.mp4` 7 s). The clips were rendered in the GPU browser frame-locked (`offline&mode=main`), so the contended GPU could not drop frames. The solver code is identical in both modes.

## 7. Sources
Labels: **[F]** fetched and read this session; **[S]** seen in search results only.

- **Stable Fluids and Stam's game solver:**
  - J. Stam, *Stable Fluids*, SIGGRAPH 1999 [S]: https://pages.cs.wisc.edu/~chaol/data/cs777/stam-stable_fluids.pdf (also https://history.siggraph.org/?p=116411)
  - J. Stam, *Real-Time Fluid Dynamics for Games*, GDC 2003 [F, pdftotext]: https://www.dgp.toronto.edu/public_user/stam/reality/Research/pdf/GDC03.pdf. Gauss-Seidel with `k<20` in both diffuse and project.
- **GPU solver:** M. Harris, *Fast Fluid Dynamics Simulation on the GPU*, GPU Gems ch. 38 [F]: https://developer.nvidia.com/gpugems/gpugems/part-vi-beyond-triangles/chapter-38-fast-fluid-dynamics-simulation-gpu
- **WebGL demo:** P. Dobryakov, *WebGL-Fluid-Simulation* [F, `script.js` config]: https://github.com/PavelDoGreat/WebGL-Fluid-Simulation. Defaults: SIM_RESOLUTION 128, DYE_RESOLUTION 1024 (512 on mobile), PRESSURE_ITERATIONS 20, CURL 30.
- **Ten Minute Physics** (M. Müller):
  - index [F]: https://matthias-research.github.io/pages/tenMinutePhysics/index.html
  - #17 Eulerian fluid source [F]: https://github.com/matthias-research/pages/blob/master/tenMinutePhysics/17-fluidSim.html. Over-relaxation 1.9, 40–100 iterations, solid mask `s`.
  - #21 fire [S].
- **Flow noise:** A. Vlachos, *Water Flow in Portal 2*, SIGGRAPH 2010 (two-phase flow-map blending), as cited in `3d/research/water/README.md`.
- **Ghost of Tsushima:**
  - *Using vorticles to simulate wind in Ghost of Tsushima*, Game Developer [F]: https://gamedeveloper.com/design/using-vorticles-to-simulate-wind-in-i-ghost-of-tsushima-i-
  - GDC 2021 talk [S]: https://gdcvault.com/play/1027124/Blowing-from-the-West-Simulating
- **Volumetric fog in games:**
  - S. Hillaire, *Physically Based and Unified Volumetric Rendering in Frostbite*, SIGGRAPH 2015 [S]: https://www.frostbite.com/2015/08/physically-based-unified-volumetric-rendering-in-frostbite/
  - B. Wronski, *Volumetric Fog*, AC4, GDC/SIGGRAPH 2014 [S]: https://bartwronski.com/wp-content/uploads/2014/03/ac4_gdc.pdf
  - F. Bauer, *Creating the Atmospheric World of Red Dead Redemption 2*, SIGGRAPH 2019 Advances (Crossref record only) [S]: https://api.crossref.org/works/10.1145%2F3450623.3464676. Technique details UNVERIFIED.
- **Web platform:**
  - MDN, *SharedArrayBuffer* (security requirements) [F]: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer
  - MDN, *Transferable objects* [F]: https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Transferable_objects
  - gzuidhof, *coi-serviceworker* [F]: https://github.com/gzuidhof/coi-serviceworker
  - Chrome DevTools CPU-throttling calibration [S]: https://developer.chrome.com/blog/devtools-grounded-real-world
- **WASM SIMD:** I found no primary benchmark relevant to stencil solvers. The search hits were blog posts (UNVERIFIED), e.g. https://dev.to/bence_rcz_fe471c168707c1/rust-webassembly-performance-javascript-vs-wasm-bindgen-vs-raw-wasm-with-simd-4pco
