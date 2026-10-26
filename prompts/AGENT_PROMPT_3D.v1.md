# One-shot brief: build Kazan-yu as a walkable, baked-lit 3D scene in the browser

You are building a real-time 3D version of **Kazan-yu 火山湯**, a fictional luxury spa inside a dormant volcano. Model it in **Blender**, bake the lighting there, and ship it as a website that runs smoothly in a **phone browser**. Its owner mostly views it on a phone. Work autonomously from start to finish. Everything you need is listed below.

## 1. Inputs (read all of these first)

Project root: `/home/agent-tom/Desktop/volcanospa/`

- `layout-spec.md` is the **source of truth** for positions, elevations, the shared A–J / 1–6 grid (200 × 120 m, 20 m cells) and every walking connection between places. Where images disagree, the spec wins. After the spec, `images/24-isometric-cutaway.png` wins.
- `images/30-…` to `images/37-…` are per-level plans (Summit, Ground, North Cliff suites, B1, B2, B3, B4) plus the alignment key. Use them for room shapes and detail. Use the spec for coordinates.
- Known plan deviations. The plans are hand-painted, so they drift by about one grid cell. Always place things at the **spec** coordinates. These specific drifts are known:
  - Main lift and Spiral Stair: drawn at E4 on B1 and at E2 on B4. Use **E3** on every level.
  - Slide shaft: drawn at I4 on B2. Use **H4**.
  - Mist Steps: drawn at C4 on B1 and at D3 on B2. Use **C3** on both.
  - Kawagiri, the Caldera Crown and the arrival hall are drawn larger than their spec footprints. Keep their interior layout and shapes, and scale them to fit the spec cells.
  - Ignore `images/03-master-floorplan.png` for layout. It came before the spec and puts several levels together on one floor; it is only a style reference.
- `images/01-…` to `images/22-…` are concept art for each place. They show how each amenity should **look** once built: materials, light colour and mood.
- `images/23-…` to `images/29-…` are overall layout views: cross-section, isometric, route map, water journey and level stack.
- `lookbook/index.html` contains the concept write-up: names, temperatures, the restaurant concept and the 10 attractions.

Art direction: black basalt and glossy obsidian; glowing teal mineral water; warm amber lantern light; orange lava seen behind thick glass; low white mist lying on every water surface; aged hinoki wood and washi screens. Magenta and cyan neon appear **only** in the Kawagiri restaurant.

## 2. How to work
- **Plan first.** Study the concept art, the lookbook and the level plans. Work out the floor plans and how the spaces fit together in 3D: what sits above what, where each stair lands, which way water falls, and the ceiling heights. Decide which assets and materials the world needs. Write that list to a spreadsheet, `3d/inventory.csv`, before you model anything. Update it as you go. Give each asset one row with these columns: id, name, level, grid cell, concept image(s) it must match, detail tier (hero / standard / low-poly / instanced), lighting storage (vertex / lightmap), materials, triangle budget, status, owner (you or a subagent ID) and notes.
- **Build your own material library first, then the asset list.** The material library is a separate phase that comes before any modelling (see 5.1). Every model is a parametric generator with levels of detail and variations (see 5.2). Decide which assets deserve detailed modelling and which can stay low-poly. As a rule, model in detail what guests touch or look at closely: the torii, Kawagiri pods and aqueducts, stepping stones, tubs and railings. Keep background rock walls, distant cliffs and ceilings simple, and let the baked lighting and materials carry them.
- **Use subagents in parallel however you see fit.** Choose each subagent's model by how complex its task is: a small, fast model for mechanical work such as batch exports, CSV upkeep and screenshot runs; a mid-tier model for building individual assets and materials; the most capable model for the layout and blockout, the baking pipeline, shaders and review. Give each subagent a narrow scope, the relevant rows from the inventory, and the files it may write to. Keep the shared files (`layout.json`, the material library and the master .blend) under your own control, so subagents don't edit the same files at once.
- **Model in Blender from the command line** (`blender -b -P …`). Optionally, before committing to an area, generate concept images or fly-through stills to check your understanding of it. You can use the grok CLI (`~/.grok/bin/grok`) for this, or Codex image generation through `prompts/gen.sh` or `prompts/gen3.sh`, which already contain the house style.
- **Keep a progress website running in the terminal.** Start it with `sbg start progress -- …` and give the user its proxied URL. It should show the plan and current phase, every row of the inventory with its status and a thumbnail render, every subagent (task, model, status, last update), the latest review round's screenshots beside the matching concept images, and the latest fps and draw-call numbers. Update it after every meaningful step.
- **The final goal** is a three.js walkaround in the browser, with baked lighting and a lighting setup that stays fast.

## 3. Machine and house rules

- Blender **5.2.2** is at `/home/agent-tom/.local/bin/blender` (run it headless with `blender -b -P script.py`). The GPU is an **RTX 4090 with 24 GB**, so use Cycles with OptiX for all baking. Node 22 is installed.
### Machine and safety rules (copy this whole block into every subagent brief)
- **Browsers run on the GPU, never `--headless`.** Every browser runs inside weston on the GPU using `tools/gpu_chrome.sh`: X11 through Xwayland, with `MESA_VK_DEVICE_SELECT` set to the discrete GPU. If `tools/gpu_chrome.sh` doesn't exist in this project yet, write it first, and make sure WebGL reports the RTX 4090 as the renderer.
- **One Chrome per agent.** Each agent has its own CDP port, profile directory and weston socket. Never use `:9222` or any port another session is using. The shared browser on `:9222` (`gpu-chrome-profile`, `slg-chrome-profile`, Xvfb `:99`, `bu-default`) belongs to other agents: never touch or kill it. Use a fresh profile after a crash.
- **Long-running processes go under `sbg`**, never `&`, `nohup` or `setsid`: `sbg start <name> -- <cmd>`. Stop only your own units, by their exact names, and clean up before you finish. Never run `pkill -f` with a pattern that could match your own shell.
- **Scratch files go only under the project's `.scratch/`.** No wildcard paths. Never use `rm`, `mv` or `cp` with shell variables in their paths.
- **Serve locally** and give the owner links in the form `https://terminal.sels.tech/lp/<port>/<path>`. For dev-server previews, run `tm-meta preview http://localhost:<port>`.
- **Send `tm-notify` at milestones**: a bake finishes (or fails), a review round's score, a fly-through film is ready, the site is published.
- **Publishing.** Publish ONLY to the private repository `midjourney/spa-walkthrough`, with **private** GitHub Pages. Upload heavy data as content-addressed release parts, and upload only the parts that changed. Re-publish after each bake. After every deploy, verify that the live site loads at **every** quality tier: an unpublished tier folder once made the live page 404. The build packet itself (this brief, the concept images, the plans and the spec) is never published. If the repository doesn't exist or isn't reachable with the current `gh` login, stop and ask the owner; don't create it or publish anywhere else.
- **Commit once per review round**, passing the owner's identity on each command (`git -c user.name=… -c user.email=… commit …`). Never set a global git config. If the identity isn't known, ask the owner once at the start.
- Keep every step **scripted and reproducible**: Blender Python scripts in `3d/blender/`, the web app in `3d/web/`, and a `3d/README.md` that explains how to rebuild everything from scratch.

## 4. Rendering approach (decided; do not swap it for real-time GI)

The aim is for the browser to show something close to what a Cycles render looks like while doing almost no lighting work itself. All light from static sources is baked. The browser adds reflections, moving water, mist and lava on top.

**Glow comes from lanterns and baked light, not from bright emissive materials.** Light sources are actual objects in the scene: lanterns, recessed lights under the water, neon tubes and the lava. Each one bakes real light onto the surfaces around it, and that baked light is what makes a space glow. Emissive values are only for the small visible surface of each light source, such as the lantern paper, the neon tube or the lava face. Keep those values moderate so they never blow out to flat colour. The water's teal comes from absorption plus baked light from underwater fixtures, not from the water surface emitting light. Keep bloom subtle: a high threshold and low intensity, so only lantern cores and neon get a soft halo.

### 4.1 Baked diffuse lighting: two storage methods, picked per mesh
Bake **irradiance only**, never albedo. In Cycles, bake Diffuse with Direct and Indirect on and Color off. Albedo then stays in sharp tiling textures, and the lighting stays smooth and low-frequency. Lanterns, neon and lava are **emissive meshes**, so Cycles includes their light in the bake. Bake in linear HDR and remove noise with OIDN.

**A. Per-vertex lighting for organic, dense meshes** (sculpted cave rock, the lava tube, rimstone, the ice cave). Do **not** point-sample at the vertices. A vertex sitting in a concave corner reads light from inside or behind the geometry, which gives black blotches and light bleeding through. Instead, integrate the lighting across each triangle and solve for the vertex values:
1. Give the mesh a temporary second UV unwrap (Lightmap Pack, with padding). Bake irradiance into a high-resolution 32-bit float EXR. Cycles can only bake to textures or point-sample at vertices; it cannot bake at arbitrary points, so the texture is how you get triangle-interior samples.
2. For each triangle, take stratified samples. Use more samples for bigger triangles, about one per bake texel. At each sample, read the irradiance `L` and the barycentric weights `(w0, w1, w2)`.
3. **Least-squares vertex baking** (Kavan, Bargteil and Sloan, 2011). Accumulate `b_i += w_i · L · dA` and assemble the consistent mass matrix `M_ij = Σ_tri ∫ φ_i φ_j`. That is area/6 on the diagonal and area/12 for neighbouring vertices. Solve `(M + λ·R) x = b` with a weak Laplacian regulariser `R` using conjugate gradients (numpy/scipy). Clamp the results to ≥ 0. A quick fallback is the lumped version, `x_i = b_i / Σ w_i dA`. That is plain barycentric-weighted averaging; it works but blurs shadow edges.
4. **Adaptive refinement.** For each triangle, compare the solved lighting with the bake samples. Where the error is above a set threshold, which happens mainly at sharp shadow edges, subdivide the edges there and solve again. Stop when the vertex budget for the zone is reached.
5. Store the result as a float16 RGB vertex attribute named `_IRRADIANCE` (HDR), not as 8-bit `COLOR_0`, which would clip the bright lantern areas.

**B. UV lightmaps for flat or sparse geometry** (wooden decks, tatami, suite interiors, stairs, the restaurant pods, the arrival hall). These surfaces have too few vertices to show shadows. Give them a dedicated non-overlapping UV1 at a consistent texel density, bake the lightmap, denoise it, and ship it as **KTX2** (UASTC HDR, or RGBM in UASTC LDR as a fallback). In three.js, use `material.lightMap` with `lightMap.channel = 1`. Pack each zone's lightmaps into a few texture atlases.

Write one Blender script that applies A or B to each object based on a custom property. Use the same light units, exposure and view transform for both, so they meet without a visible seam.

### 4.2 Directional data for highlights on wet surfaces
Plain irradiance gives flat lighting. Wet basalt and lacquered wood need highlights that move as the camera moves. Use the **ambient-cube / L1 spherical-harmonic** trick on the hero surfaces: wet rock near water, the corridor floors and the lacquered wood.
- Bake irradiance six times. Each time, override the shading normal in the material to a world axis (±X, ±Y, ±Z) while keeping the real geometry. Convert the six results to L1 SH, which is 4 coefficients × RGB. Store them per vertex (method A) or in lightmap atlases (method B).
- In the shader, use the SH to compute diffuse lighting from the normal map. For specular, extract the dominant light direction and colour from the L1 band and evaluate a GGX lobe from them. Gate it by roughness and a baked AO term so occluded areas don't get highlights.
- This is **required** on every surface with strong normal-map detail (rock, wood, stone paving), because without it normal maps can't affect diffuse lighting (see 5.1). Minor surfaces may stay irradiance-only and use the cavity term instead.

### 4.3 Reflections
Use this order of preference, each tier cheaper than the next:
1. **Box-projected reflection probes, used everywhere.** Place one probe per room or zone (about 25–40 in total). Render each in Blender Cycles as an HDR 6-face cubemap of the final baked scene, including emissives. Prefilter each into roughness mips, either offline or with three's `PMREMGenerator` at load. Save each probe's **box bounds** to JSON and apply **parallax-corrected box projection** in the material shader by patching `MeshStandardMaterial` / `MeshPhysicalMaterial` through `onBeforeCompile`. Inside a zone, blend between the two nearest probes. Every material gets roughness-correct reflections this way.
2. **Real-time planar reflections**, only where mirror-like water is the main feature: the Obsidian Mirror pool, the reflecting-pool corridors and the Kawagiri river. Run **at most one or two** at a time, picked by which zone the camera is in. Render them at half resolution, and disturb them with the water's normal map. Every other water surface uses tier 1.
3. **Screen-space reflections**, only on the desktop "High" quality tier (for example the pmndrs `postprocessing` / realism-effects SSR), blended over the probe result.

### 4.4 Dynamic and unbaked elements (all done in shaders, cheap)
- **Water:** two scrolling normal maps, Fresnel, teal absorption that deepens with depth (lit by the baked underwater fixtures, not emissive), and a projected scrolling caustics texture on the pool floors. Every still water surface is **perfectly level**, sitting at a height recorded in `layout.json`. Every tub and pool is filled to just below its rim, so the water settles inside its container. The sea is a single level plane at one height everywhere, including inside the Wave Grotto, where the waves move on top of that level.
- **Waterfalls and water curtains:** layered scrolling alpha cards with soft edges, plus spray particles where they land. Water always flows **downward**: each fall starts at a lip on a higher pool or the river and ends in a pool below. No water appears from nowhere or vanishes in midair. Flow direction on rivers and the lazy river follows the water path in the spec. The Kawagiri water curtains are thin cards that can "part" when you approach.
- **Mist:** a height-fog term added to every material shader, very dense in a 0–0.5 m band above the water and fading quickly above it, plus a few large soft-particle sprites with depth fade and noise. **Do not use raymarched volumetrics.**
- **Lava:** an emissive flow-map shader behind glass.
- **Neon and lanterns:** a small, moderate emissive surface with a slight flicker. The light they cast on their surroundings is baked, and bloom stays subtle, as described above.
- **Geysers:** particles on a timed schedule.
- **Moving objects such as boats and float rings:** lit by an irradiance grid of SH light probes baked in Blender (a regular 3D grid per zone, exported as JSON).

### 4.5 Matching Blender's colours
Use the same view transform in Blender and the browser: AgX in Blender, `THREE.AgXToneMapping` in three.js, with the exposure set to match. Bakes are linear HDR, and tone mapping happens only at the end of the browser's pipeline. Put a Cycles render and a browser screenshot from the same camera side by side for three zones, and adjust until they match.

## 5. Building the scene in Blender
1. **Blockout from the spec, by script.** Turn `layout-spec.md` into `3d/layout.json`, containing levels, elevations, places with their grid cells and footprints, vertical connections and the water path. Build every level from that file on the shared grid. **Line up the vertical connections exactly across levels.** These are the Spiral Stair and lift at E3, Mist Steps at C3, Falls Stair at B3–B4, Lava Stair and slide shaft at H4, Terrace Path, Cliff Stair and cable lift.
2. **Make sure everything can be walked to.** Every place must be reachable on foot from the Basalt Gate. Build a walk graph (a navmesh, or walkable polygons plus a node graph) and run an automated check that reaches every place. The lifts, boat, cable lift and slide are optional extras that fail the check if they are the only route.
3. **Cave forms.** Start from blockout volumes, then remesh, add noise displacement and sculpt the rock. Keep it closed and watertight, because that stops light leaking into the bakes. Add architecture inside the caves: Kawagiri's beams and pods, suites, stairs, the torii and lanterns.
4. **Materials.** Every model uses materials from the library you built in phase 1 (see 5.1). Never create a one-off material inside an asset. If something new is needed, add it to the library first. Use trim sheets for the architecture.
5. **Parametric models** (see 5.2). Every asset is generated from parameters, never modelled by hand as a single fixed object. Use instancing for lanterns, stepping stones, rings, pods and tables, mixing several variants of each.

### 5.1 Material library, built before any models
Build this as its own phase, finished and reviewed before modelling starts.
- **Contents.** About 20–30 materials, each derived from what the concept art shows. At minimum:
  - rock and stone: dry basalt, wet basalt, polished obsidian, rimstone and travertine, volcanic black sand, ash clay
  - wood and paper: weathered hinoki, lacquered dark wood, bamboo, tatami, washi paper (with a back-lit variant for lanterns), noren cloth
  - stone and metal: worn stone paving, iron and bronze fittings, rope
  - ice and glass: glacier ice, thick lava glass
  - water: still water, river water, sea water, a waterfall sheet
  - light sources: lava, neon tube, lantern paper (the emissive surfaces from 4.4)
- **Format.** Write one `3d/blender/materials/library.blend`, generated by a script. Use procedural node setups where they work well (rock, sand, ice); create or source tiling textures where procedural won't hold up up close (wood grain, tatami, washi). Use only CC0 or self-made textures, and record their source. Each material exposes a few **named parameters**: tint, wetness, wear/age, roughness offset, scale and an emissive level for the light sources. Assets can then vary a shared material instead of copying it.
- **Ready for the web.** Every material bakes down to a texture set the browser can use: base colour, packed ORM (occlusion, roughness, metalness) and normal, as tiling KTX2. Its parameters map onto three.js material settings, or onto a shared shader with per-instance uniforms. Write a `3d/materials.json` manifest that lists each material's parameters, texture set and texel density. The Blender and browser versions must look the same under AgX.
- **Surface detail lives in light textures, not geometry.** Every material includes a tiling **detail normal map**, so models can have far fewer polygons. The normal map carries the rock pores and cracks, wood grain, tatami weave, washi fibres, ice fractures, stone chisel marks and rope twist. A low-poly flat wall should still read as wet, cracked basalt.
  - **Keep the textures small.** Store normal maps as **two-channel** (XY only; the shader rebuilds Z) in KTX2 with UASTC normal mode or BC5. Use 512² for most materials and 1024² only for hero materials seen up close. Use mipmaps throughout, and author the textures so they tile without visible seams.
  - **Height and bump.** Bake a greyscale height map alongside each normal map and pack it into a spare channel. Height is used for three things: cheap bump on far LODs, a cavity/occlusion term that darkens the cracks, and (High tier only, a handful of hero surfaces such as the stepping stones and the paving) a single-step parallax offset. Never use full parallax occlusion mapping on Low.
  - **Two scales of detail.** Materials blend a **macro** normal (large forms, sampled at low frequency) with a **micro** detail normal (fine grain, fading out with distance so it doesn't shimmer). Both have a strength parameter in the library. Variants can turn them up or down; for example, wet basalt flattens the micro normal and lowers roughness.
  - **Normal maps need directional light to show.** With flat irradiance-only lighting, a normal map changes only the reflections, so diffuse shading stays flat. To make normal-mapped detail visible in the diffuse lighting too, every material samples the directional SH / ambient-cube data from 4.2 where it exists. Where that data doesn't exist (Low tier, minor surfaces), the material uses the cavity/AO term from the height map so the detail still reads. Promote the directional bake (4.2) from a phase 2 extra to required for every surface with strong normal detail: rock, wood and stone paving.
- **Check before use.** Render each material on a preview sphere and a flat swatch under the same baked lantern lighting, in Blender and in the browser. Put both side by side on the progress site. Compare each against the concept image it came from, and do a review pass on the whole library before phase 2 starts.

### 5.2 Parametric models: levels of detail and variations
- **One generator per asset type.** Write each asset as a Python generator function in `3d/blender/assets/` (Geometry Nodes are fine inside it). The generator takes `(lod, variant_seed, **dimensions)` and returns a mesh with materials from the library assigned. Examples:
  - `lantern(lod, seed, height, style)`
  - `stepping_stone(lod, seed, radius)`
  - `kawagiri_pod(lod, seed, width, curtain=True)`
  - `stair(lod, seed, rise, run, width, steps)`
  - `rock_wall(lod, seed, footprint)`
- Asset parameters and seeds are stored in `layout.json` and `inventory.csv`, so the whole world can be rebuilt from data.
- **Levels of detail.** Each generator produces LOD0 to LOD3 from the same parameters: the shape and outline stay fixed while the detail goes down. Reduce detail by lowering curve and bevel resolution, sculpt and displacement level, and segment counts, not by blind decimation. Set a triangle budget per LOD in the inventory. Rock and cave shells generate their LODs from the same noise field at decreasing resolution, so the outline stays put.
- **Recognisable even at the lowest detail.** Each generator states the **identifying features** of its asset in the inventory. These are what make it recognisable at a glance: the torii's two posts, double crossbeam and upswept top; the lantern's box shape, roof cap and glowing panel; the aqueduct's arches on stilts; a pod's water-curtain frame; a stair's step rhythm; a geyser vent's raised cone. Those features stay in the geometry at **every** LOD, including LOD3. Everything else moves into textures:
  - Bake LOD0's surface onto each lower LOD with Cycles **Selected to Active**. This gives a small per-asset **normal and AO map** at 256–512², which is layered under the tiling detail normal from the material library.
  - Bevels, panel lines, carved kanji, rope bindings, nail heads and wood joints become baked normal detail. Hard edges get a **baked bevel normal** (Cycles Bevel node) so low-poly corners still look rounded.
  - Assets on the architecture trim sheet get bevels and mouldings from the trim's normal channel and need no unique bake.
  - Recommended triangle ranges as a starting point, so the reduction is deliberate: LOD0 hero 5–20k, LOD1 about 40%, LOD2 about 12%, LOD3 a few hundred triangles or fewer. A lantern's LOD3 should be about 60–150 triangles and still read as a lantern.
- **Recognition test.** For every asset, render LOD2 and LOD3 at the size they appear on a phone at their switch distance, both shaded and as a flat silhouette. Have a fresh subagent that hasn't seen the asset list identify each one. If it can't name an asset, or mixes two up, add geometry back to the identifying features or strengthen the baked normals, then test again. Post the results on the progress site.
- **Variations.** `variant_seed` controls the asset's shape: proportions within set ranges, chips and wear, the lantern's paper pattern, how stones are arranged. It also sets the material parameters (tint, wear, wetness), so repeated objects never look cloned. Each instanced asset ships with 3–6 variants, and the world mixes them by seed.
- **Lighting across LODs.** Bake once on LOD0. Lower LODs get their lighting transferred from it, not baked separately. For per-vertex lighting, sample LOD0's high-resolution bake for each lower LOD's vertices with the same least-squares solve. For lightmaps, project from LOD0 onto each LOD's own UV1 using closest point plus normal. Every LOD must look identical in lighting when they switch.
- **Switching LODs in the browser.** Use `THREE.LOD`, or a custom switch on instanced batches, based on distance and screen size. Add hysteresis so objects don't flicker back and forth between LODs. Fade between LODs with a short dithered crossfade, so a switch is never visible as a pop. Set the switch distances for each LOD in `materials.json` / `assets.json`, and tighten them on the Low quality tier.
- **Check every generator.** Before anything uses a generator, render a sheet showing every LOD × 3 variants on the progress site, with triangle counts. Run the geometry checks (no z-fighting, no faces passing through each other, watertight where needed) on every LOD.
5. **Zones.** Split the scene into about 12–20 zones that follow the caves' natural portals: corridors, stairs and doorways. Export one glTF per zone, plus a `zones.json` listing which zones are adjacent and the portal openings between them.

## 6. Exporting and the web app
- **Export:** glTF 2.0 / GLB with **meshopt** compression, quantized attributes, KTX2 textures and the custom `_IRRADIANCE` and SH attributes. Export probe cubemaps as KTX2 or HDR, plus JSON for probe boxes, the SH grid, zones and the walk graph.
- **Stack:** Vite and **three.js**, pinned to a specific release (WebGL2 baseline; WebGPURenderer optional). Write the custom shader chunks against that exact version.
- **Loading and culling, with no visible pop-in.** The world must feel solid: no floors, walls or lighting appearing in front of the player. Load everything the player can reach before they can see it. The first load fills in the starting zone and **every zone visible from it** before the player can move. After that, load in the background at least two portal steps ahead of the player. Unload only zones three or more steps away that are out of sight. Use the portal graph to draw only zones visible through portals. Turning visibility on and off is fine, because the hidden zones are already loaded. If a zone isn't ready when the player reaches its portal, briefly hold the player at the portal (for example, the mist thickens) rather than showing a half-loaded room. If the whole compressed world fits the Low-tier memory budget, simply load it all upfront.
- **Modes:**
  - (1) **Walk**: first person on the walk graph. Touch joystick plus drag-to-look on phones, WASD and mouse on desktop. Stairs work by walking.
  - (2) **Dollhouse**: an orbit view of the whole volcano cut open like the isometric reference, where tapping a place travels there.
  - (3) A **place list** for teleporting.
  - The 10 attractions and the main places get on-screen labels.
- **Quality tiers:** detect Low/Med/High automatically, with a manual override. Low (phones) uses probes only, one planar reflection at quarter resolution, no SSR, half-resolution bloom, and DPR capped at 1.5. High adds SSR, two planar reflections, full-resolution effects and DPR 2.
- **Budgets for Low:** 60 fps on a recent mid-range phone, ≤ 150 draw calls, ≤ 500k triangles visible, ≤ 250 MB of GPU texture memory, first zone interactive within 5 seconds.

## 7. Order of work, and what counts as done
0. **Plan.** Analyse the layout in 3D, write `3d/inventory.csv` and the material library list, and get the progress website running. Send the user its URL with `tm-notify` before you start modelling.
1. **Material library** (5.1). Build all the materials, check each one in Blender and in the browser, and do a review pass, all before any model exists.
2. **Asset generators** (5.2). Write the parametric generators, with LOD0–3 and variants for each, and post their review sheets to the progress site.
3. Generate the layout JSON and the blockout of every level, with the walk check passing. Render screenshots of the cutaway and post them to the progress site.
4. One **vertical slice**: the arrival hall, a mist corridor and the Obsidian Mirror. This slice proves the whole pipeline: method A and B bakes, box-projected probes, a planar mirror, mist and AgX matching.
5. All remaining zones, each baked with directional SH on its normal-mapped surfaces as part of its bake (prove this in the vertical slice), then the dynamic effects, streaming, dollhouse mode and quality tiers.
6. **Review rounds.** Run several rounds of your own review, with a fresh-eyed subagent judging each one. In each round, put browser screenshots side by side with the matching concept images, and look for anything that breaks the feeling of walking into the art: scale, light colour, mist height, materials, empty areas. Fix what you find and run another round. Keep going until it really does feel like walking into the concept art. Record each round on the progress site.

### What counts as done
- **Clean geometry.** No z-fighting and no faces passing through each other. Choose your own methods to detect and fix these, run them on every export, and record the results on the progress site. For example, you could test for coplanar overlapping faces with a BVH, run intersect checks with Blender's 3D Print toolbox, use a depth-precision check with a sensible near plane, or take screenshots with a flicker-diff test.
- **Water behaves like water.** It falls downward. It settles level in tubs and pools, filled to just below the rim. The sea sits at one level everywhere. No water floats or ends abruptly.
- **The world feels solid.** No pop-in and no floors streaming in. The baked lighting reads correctly everywhere: no light leaks at corners, no black blotches, no visible seams between vertex-lit and lightmapped surfaces, and no moving objects lit differently from the static scene around them.
- **Glow comes from lanterns and baked light**, not from bright emissive materials. Bloom stays subtle.
- **Every space can be reached on foot, at a believable scale.** The automated walk check passes from the Basalt Gate. Stairs have real step heights (about 15–18 cm) and doorways and railings are human-sized. A person at eye height (about 1.6 m) sees the spaces at the scale the concept art shows.
- **It stands up to review.** Screenshots from the camera position of each concept image (`images/04`, `05`, `06`, `11`–`20`) are saved in `3d/compare/` next to the concept images, and the last review round found nothing major.
- **It meets the performance budgets.** fps and draw calls are logged for each quality tier, and the Low tier meets its budgets.
- **Models are parametric, with no visible LOD pops.** Every asset comes from a generator with LOD0–3 and seeded variants. LODs crossfade without visible pops or lighting changes. Repeated objects never look cloned. Every material in the world comes from the library. Surface detail comes from lightweight two-channel normal and height maps rather than polygons. Every asset still passes the recognition test at LOD3.
- **It can be rebuilt.** `3d/README.md` explains how to rebuild everything and lists what is left undone. `3d/inventory.csv` shows the final status of every asset.

Report what is finished, what isn't, and how it measured against the budgets. Give the URL in its proxied form, then send a notification.
