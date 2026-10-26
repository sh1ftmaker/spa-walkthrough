# Brief: build Kazan-yu as a walkable 3D scene in the browser

You are the **lead agent** on a long autonomous build. Your job is to model **Kazan-yu 火山湯**, a fictional luxury spa inside a dormant volcano, in **Blender**. You bake its lighting there, then ship it as a **three.js** walkaround that runs well on a **phone**, because the owner mostly views on a phone.

## How to read this brief
- **§2 contains hard rules.** They keep the machine and the owner's accounts safe. Follow them exactly.
- **Everything else is suggestions** from earlier builds and from a review of what went wrong. Treat it as a strong default, not a script.
- **When the brief, the spec, the plans and the concept art disagree,** or a suggestion clearly doesn't work in practice, make your own decision. Write it down in `3d/decisions.md` (one or two lines: what conflicted, what you chose, and why), then carry on. Don't stop to ask unless the decision is outward-facing or can't be undone.
- **What matters most, in order:**
  1. Every place can be reached on foot, at a believable human scale.
  2. Walking through it feels like walking into the concept art.
  3. It runs smoothly on a phone.
  4. Everything can be rebuilt from scripts.

  When you have to trade one of these against another, use this order.
- **Earlier builds failed at assembly.** The individual models were good, but they were placed haphazardly, with no thought for walkability or appearance. §5 is the most important section; give it the most care.

---

## 1. Inputs
Project root: `/home/agent-tom/Desktop/volcanospa/`
- `layout-spec.md`: the grid, elevations, places, stairs and the water path. It also lists **suggested heights** and **known conflicts** for you to resolve.
- `images/24-isometric-cutaway.png`: the best overall reference for where everything goes.
- `images/30`–`37`: plans for every level, plus an alignment key. Use them for room shapes and detail. They are paintings and drift by about one grid cell: B1 draws the lift at E4, B4 at E2, B2 draws the slide shaft at I4, and the Mist Steps are drawn at C4 on B1 and D3 on B2. Ignore `images/03` for layout; it is only a style reference.
- `images/01`–`22`: concept art showing how each place **looks** (materials, light, mood). The concept geometry sometimes contradicts the plans. For example, image 06 shows a lava window behind Kawagiri. When it does, match the *mood and framing*, not the exact geometry.
- `images/23`–`29`: overall layout views: cross-section, route map, water journey, level stack, aerial, river section.
- `lookbook/index.html`: names, temperatures, the restaurant concept and the 10 attractions.
- **Art direction:** black basalt and glossy obsidian; teal mineral water; warm amber lanterns; orange lava behind thick glass; low white mist on every water surface; aged hinoki wood and washi paper. Magenta and cyan neon appear **only** in Kawagiri.

---

## 2. Hard rules
Keep these rules in `3d/AGENT_RULES.md`, in two parts. Every subagent prompt includes **Part A**. **Part B** is yours alone.

### Part A: every agent
- **Browsers run on the GPU, never headless.** Browsers run inside weston on the GPU, using `tools/gpu_chrome.sh` (X11 through Xwayland, with `MESA_VK_DEVICE_SELECT` set to the discrete GPU). Blender's `-b` mode is fine. Use only the browser, CDP port, profile and weston socket the lead assigned to you. Never use `:9222` or ports other sessions are using. Never touch the shared browser (`gpu-chrome-profile`, `slg-chrome-profile`, Xvfb `:99`, `bu-default`). Use a fresh profile after a crash.
- **Long-running processes go under `sbg`**, never `&`, `nohup` or `setsid`: `sbg start <name> -- <cmd>`. Stop only your own units, by their exact names. Never run `pkill -f` with a pattern that could match your own shell. Clean up before you finish.
- **Scratch files go only under the project's `.scratch/`.** No wildcard paths. Never use `rm`, `mv` or `cp` with shell variables in their paths.
- **Write only the paths your task names.** Shared files (`layout.json`, `spaces/`, the material library, the master `.blend`, `inventory.csv`) belong to the lead.
- **Give links in the proxied form**, `https://terminal.sels.tech/lp/<port>/<path>`, never as localhost.
- **Start and finish your report the same way.** Begin by echoing the SHA-256 of `3d/AGENT_RULES.md`. End by listing every process you started and confirming that each one has stopped.

### Part B: lead only
- **Publishing.** Publish ONLY to the private repository `midjourney/spa-walkthrough`, with **private** GitHub Pages. Publish from a clean checkout that contains only the built site, never the build packet (this brief, the images, the plans, the spec). Upload heavy data as content-addressed release parts, and upload only parts that changed. Deploy in this order: parts, then the per-tier manifests, then the HTML. After each deploy, check that every quality tier loads. Fail the deploy if any file the site references returns 404. An unpublished tier folder once broke the live page.
- **Commit at every gate** (§3), passing the owner's identity on each command (`git -c user.name=… -c user.email=…`). Never set a global git config.
- **Run `tm-notify`** at gates, when a bake finishes or fails, with each review round's score, when a fly-through film is ready, and when the site is published. A fly-through film is an MP4 walking the main route at eye height, recorded from the browser.
- **Run the machine.** Blender **5.2.2** is at `/home/agent-tom/.local/bin/blender` (run it with `-b -P script.py`). The GPU is an RTX 4090 with 24 GB, so use Cycles with OptiX. Node 22 is installed. For previews, run `tm-meta preview http://localhost:<port>`. Previous builds pushed this machine into swap, so keep **at most two** browsers running at once. A good pattern is one screenshot service under `sbg`, which you own and which works through a queue of camera requests that subagents submit.

---

## 3. Suggested phases and gates
Each phase ends at a **gate**. At a gate, run that phase's checks, commit, publish (once publishing works), check every tier, update `3d/status.json` and the progress site, and send a `tm-notify`. If a phase goes better in a different order, change it and log why.

0. **Preflight** (you, before anything else):
   - Run `git init` and add a `.gitignore` covering `.scratch/`, EXR files and bake caches.
   - Write `tools/gpu_chrome.sh`, and confirm that WebGL reports the RTX 4090.
   - Start the screenshot service, and make sure the progress site is being served (see §8). Set `status.json` to Preflight and send the owner its link with `tm-notify`.
   - Confirm that `gh` can reach `midjourney/spa-walkthrough`, then deploy one test file and check that a page can actually fetch a release part. Private Pages needs GitHub Enterprise Cloud, and private release downloads need a token and may be blocked by CORS. If this doesn't work, consider putting the data inside the Pages artifact itself, which has a 1 GB limit. If the repository can't be reached, notify the owner, keep building, and queue publishing. Don't stop.
   - Ask the owner for their git name and email once, and continue while you wait.
1. **Plan.** Read every input. Turn the spec into a **metric** `3d/layout.json` (§5.1), write a `3d/spaces/<id>.json` for each space (§5.2), and start `3d/inventory.csv` (§6). Resolve the spec's known conflicts in `decisions.md`.
2. **Graybox and material library, in parallel.**
   - **Graybox:** build every level from simple massing, with real stairs and level water planes. Give each inventory asset one **proxy**: its final bounding box, its pivot at the base centre, +Y facing forward, in metres. Place proxies with the assembly process (§5). The walk check and the placement checks should pass, and contact sheets should be reviewed, before any detailed model exists. From here on, nothing moves by more than about 0.3 m unless its space file changes.
   - **Material library:** build it at the same time (§6.1). A subagent can do this while you build the graybox.
3. **Vertical slice:** the arrival hall, one mist corridor and the Obsidian Mirror, finished end to end. That means the materials and generators these spaces need, the baking, the export, and the full browser rendering.
4. **Remaining generators**, each built to its proxy's dimensions (§6.2).
5. **Art pass, one zone at a time:** swap proxies for real assets, re-run the placement checks, bake, export, and check in the browser. Each zone is its own gate.
6. **Review rounds** (§5.5), then the final checks (§9).

**Scope tiers.** Not everything will fit in one run. When you need to cut, cut from the bottom of this list up, and never cut the checks or review rounds.

| Tier | What's in it |
|---|---|
| **Must** | Ground and B1–B3, walkable end to end; lightmaps (§7.1 B) with probes; one planar mirror; fog-based mist; water; walk mode; the place list; Low and High quality tiers. |
| **Should** | Summit, north cliff suites, B4; the directional bake for highlights (§7.2); dollhouse mode; LOD crossfades. |
| **Stretch** | Per-vertex baking (§7.1 A); screen-space reflections; zone streaming; GPU adaptive subdivision for displacement (§7.6). |

---

## 4. Agents and models
- **Subagents.** Use them in parallel wherever the work divides cleanly. Pick each subagent's model by how hard its task is:
  - small or fast models for mechanical work: exports, CSV upkeep, screenshot queues
  - mid-tier models for individual generators and materials
  - the most capable model for layout and assembly, the bake pipeline, shaders and reviews
- **Build every subagent prompt with a small script** such as `tools/brief.py`. It joins rules Part A, the task, the relevant inventory rows, the paths the subagent may write, and its screenshot-queue access or assigned browser port. That way no rule gets lost when the lead writes a prompt quickly.
- **Use fresh eyes for review.** Review subagents should not have built what they are reviewing. Give them the images and the rubric, not your conclusions.

---

## 5. Layout and assembly (the part that failed before)
Earlier builds failed here for a few recognisable reasons:
- agents write raw coordinates for scenes they can't see;
- assets are built without any space in mind;
- no room has a stated purpose, so dressing turns into evenly spread clutter, or objects sit on grid-cell centres;
- reviews use flattering overhead orbit shots.

Research on scene generation (SceneCraft, Holodeck, Infinigen Indoors, LayoutVLM) points to the same fix. The language model writes **intent and rules**. A script **computes the transforms**. Renders and critique close the loop. The rest of this section is one way to do that. Adapt it as you need to.

### 5.1 A metric layout first
- **Convert the grid spec to metres** in `layout.json`:
  - x increases east from the west edge of column A
  - y increases north from the south edge of row 6
  - z is the elevation
- **Trace each plan's room outlines at its scale bar** to get footprint polygons. Move a shape onto its spec cell only if it is off by more than about half a cell.
- **Where two things claim the same space,** for example the lift core and the Obsidian Mirror, connections generally keep their position and rooms are shaped around them. Use your judgement and log the decision.
- **Size stairs from their rise:** about 17 cm risers and 29 cm treads, with a landing every 12–16 steps. Long drops need switchbacks (see the spec).
- **Check the layout by eye.** Render an overlay of every level's outline with the vertical connections drawn through them, and check that it makes physical sense in 3D. Keep at least 4–5 m of rock between levels, stairs that land where they should, and water that only flows downhill.

### 5.2 One file per space, describing intent
Each `3d/spaces/<id>.json` describes what the space is *for*. A suggested shape:
- **`floor_z`, `ceiling_z`, `footprint`**
- **`portals`**: a list of `{id, at, width}` for each opening to another space.
- **`spine`**: the line along which people walk through the space.
- **`hero`**: `{asset, at, why}`. The single focal point, and why it is the focal point.
- **`sightlines`**: what you should see from each portal, especially a glimpse of the next space's light.
- **`cameras`**: an entry camera, a reveal camera and a concept-match camera. Each has its image, position, look target and vertical FOV, at an eye height of 1.6 m.
- **`water`**: a list of `{id, z}`, giving each water surface's exact height.
- **`dressing`**: placement rules. Examples:
  - lanterns along the walking path:
    ```json
    {"asset":"lantern","along":"spine","side":"both","spacing":[4,6],"offset":0.7,"face":"path"}
    ```
  - rocks scattered in a band at the edges, kept off the walk path and out of doorways:
    ```json
    {"asset":"rock_cluster","scatter":"edge_band","band":[0.3,2.5],"density":0.12,"avoid":["nav","portals"]}
    ```

  Useful rule verbs are `at`, `along`, `ring` and `scatter`. Useful modifiers are `avoid`, `snap` (ground, wall or ceiling), `face` and `embed`.

A `place.py` script reads the rules and writes `placements.json`. Each entry records the rule that produced it. A good discipline is to never hand-edit `placements.json`. Put deliberate nudges in `overrides.json`, each with a reason. When something looks wrong, **fix the rule, not the coordinates**, because vision-language models are weak at precise metric edits.

### 5.3 A suggested order inside each space
1. The shell, floor, water and stairs.
2. **The hero.** Place it by hand, framed from the reveal camera. Arrange things so the next space's light is visible from the exit.
3. Anchored secondaries: railings, bridges, pods along the aqueduct.
4. **Lights before clutter.**
   - Lantern rows should lead the eye toward the hero.
   - Alternate pools of light with darker gaps.
   - The hero should be the brightest point in its space.
5. Clutter, worked from the edges inward. Keep the middle of each floor open, and put the most detail at edges, rims, doorways and counters.
6. **Contrast between spaces.** For example, put a compressed passage (about 4 m wide and 3 m high at most) before each big reveal space.

### 5.4 Automated placement checks
Write a script such as `checks/placement.py` and run it on every zone at every gate. Suggested thresholds:
- **Contact:** nothing floats more than 2 cm above the surface it rests on, and nothing sinks deeper than its own `embed` allowance.
- **Overlaps:** only the overlaps a space file explicitly allows.
- **Clearance:** a clear corridor about 1.2 m wide × 2.1 m high along every walk edge, stair and doorway.
- **Water:** every still water surface sits about 3–8 cm below its lowest rim. Every waterfall begins at a lip and ends in a pool, and the sea is a single level surface.
- **The hero can be seen:** at least about 30% of the hero is visible by raycast from each entry camera.
- **No empty areas:** no walkable patch of about 6 × 6 m is more than about 4 m from either dressing or a light.
- **Spacing:** a nearest-neighbour spacing test flags both rigid grids and clumps. Flag anything sitting within 0.5 m of a grid-cell centre. Report counts for each rule.
- **Scale:** railings 0.95–1.1 m high, doors at least 2.1 m, steps 15–18 cm.
- **Walk graph:** every place can be reached on foot from the Basalt Gate. Lifts, the boat, the cable lift and the slide don't count towards this.

If a threshold is genuinely wrong for a particular space, waive it **in the space file, with a reason**. Don't quietly loosen a threshold to make a check pass.

### 5.5 Visual review loop
For each space, render a contact sheet, for example with `render_contact_sheet.py`. It shows:
- a **labelled top-down plan** with object ids, the walk graph and sight-line rays, with check failures marked in red. A labelled plan is something an LLM can act on.
- the **entry, reveal and concept-match views** at eye height, in both 9:16 (phone) and 16:9, each placed next to its concept image;
- an **8-frame strip** walking along the spine.

Then give the sheet to a fresh review subagent with a rubric:
- What is the focal point of each frame? Can you see where to go next?
- Name up to 5 object ids that look random, floating or in the way, and say which way and how many metres each should move.
- Score composition, density and light rhythm from 1 to 5.

Apply the fixes as **rule changes**, then re-run. A sensible stopping point is 3 rounds, or every score at 4 or above. Use your judgement if a space needs more. "Concept-match" means matching the framing and mood, not the exact camera position.

Image generation is useful here mainly as **paint-overs of graybox renders**: an image model redraws your screenshot in the house style, so you can see what the space should become. You can use the grok CLI (`~/.grok/bin/grok`) or the Codex scripts in `prompts/gen*.sh`.

---

## 6. Assets

### 6.1 Material library (build it before any detailed model)
- **What it contains:** about 20–30 materials, taken from the concept art.
  - **Stone:** dry basalt, wet basalt, polished obsidian, rimstone and travertine, black sand, ash clay, worn paving.
  - **Wood, paper and cloth:** hinoki, lacquered dark wood, bamboo, tatami, washi (including a back-lit version for lanterns), noren cloth, rope.
  - **Metal, ice and glass:** iron and bronze, glacier ice, thick lava glass.
  - **Water:** still water, river water, sea water, a waterfall sheet.
  - **Light-source surfaces:** lava, neon tube, lantern paper.
- **How to build it:** generate a `library.blend` with a script. Procedural materials work well for rock, sand and ice. Use tiling textures where procedural won't hold up up close (wood grain, tatami), and only CC0 or self-made textures, with their source recorded. Each material exposes a few named settings: tint, wetness, wear, roughness offset, scale, normal strength and emissive level. Assets vary a shared material rather than copying it. Avoid one-off materials; if an asset needs something new, add it to the library.
- **Detail goes in textures, not polygons.** This lets the models stay low-poly.
  - **Detail normal map:** each material has a small tiling detail normal map. It stores two channels (XY) as KTX2 with UASTC normal mode or BC5, at about 512² (1024² for a few materials seen up close), with mipmaps.
  - **Height map:** pack a greyscale height map into a spare channel. Use it for bump on distant LODs, for a cavity term that darkens cracks, and, on the High tier only, for a single-step parallax effect on a few close surfaces.
  - **Two scales:** blend a macro normal (large forms) with a micro detail normal that fades with distance so it doesn't shimmer.
  - **Directional light:** a normal map only affects diffuse shading if the lighting has a direction. Pair rock, wood and paving with the directional bake (§7.2) where it exists. Elsewhere, the cavity term keeps the detail readable.
- **Export for the web:** export base colour, packed ORM (occlusion, roughness, metalness) and normal/height as KTX2, and list them in `3d/materials.json`.
- **Check the library:** render a preview sphere and a flat swatch of each material under the same baked lantern light, in Blender and in the browser. Put them side by side next to the concept source on the progress site, and do one review pass before modelling begins.

### 6.2 Parametric generators
- **One generator per asset type.** Each takes `(lod, variant_seed, **dimensions)` and returns a mesh with library materials assigned. Geometry Nodes inside the generator are fine. Some examples:
  - `lantern(lod, seed, height, style)`
  - `stair(lod, seed, rise, run, width, steps)`
  - `kawagiri_pod(lod, seed, width, curtain)`
  - `rock_wall(lod, seed, footprint)`

  Every generator's dimensions come from its proxy, and its parameters and seeds are stored in the data files.
- **Four levels of detail, LOD0 to LOD3, from the same parameters.** The silhouette stays fixed while the detail drops. Lower curve and bevel resolution, segment counts and displacement level; avoid blind decimation. Suggested triangle budgets:
  - LOD0, for featured assets: about 5–20k
  - LOD1: about 40% of LOD0
  - LOD2: about 12%
  - LOD3: a few hundred at most. A lantern's LOD3 is about 60–150 triangles.
- **Recognisable at the lowest detail.** Each asset records its identifying features in the inventory: the torii's posts and upswept crossbeam, the lantern's box, cap and glowing panel, the aqueduct's arches on stilts. Those features stay in the geometry at every LOD.
  - Everything else becomes baked texture. Bake LOD0 onto each lower LOD (Cycles "Selected to Active") as a small normal and AO map, about 256–512². Use baked bevel normals for rounded edges.
  - Trim-sheet assets take their bevels from the trim sheet.
- **Recognition test.** Render LOD2 and LOD3 at phone size at their switch distance, both shaded and as a silhouette. A fresh subagent has to name each asset. If it can't, add geometry back to the identifying features or strengthen the baked normals.
- **Variations from the seed.** Proportions, chips and wear, paper patterns, and material tint and wetness all vary. Ship 3–6 variants for each instanced asset, so repeated objects don't look cloned.
- **Lighting stays matched across LODs.** Bake once on LOD0 and transfer that lighting to the lower LODs, so switching between them doesn't change the lighting.
- **Switching LODs in the browser.** Switch by distance or screen size, with hysteresis and a short dithered crossfade.
- **Check each generator.** Before a generator is used, post a sheet showing each LOD × 3 variants, with triangle counts and geometry-check results.
- **Inventory.** `inventory.csv` has one row per asset: id, name, space, concept images, detail tier, identifying features, lighting storage, materials, triangle budget per LOD, status, owner and notes. Assets guests touch or look at closely deserve detail. Distant rock and ceilings can stay simple.

---

## 7. Lighting and rendering (suggested approach)
The goal is a browser image close to a Cycles render, with almost no lighting work done at runtime. Bake all static lighting. The browser adds reflections, water, mist and lava on top.

### 7.1 Baked diffuse lighting
- **Bake irradiance only.** Use Cycles Diffuse with Direct and Indirect on and Color off. This keeps the albedo in sharp tiling textures. Bake in linear HDR and denoise with OIDN. Lanterns, under-water fixtures, neon and lava are real emissive objects, so they light the bake.
- **B. Lightmaps (the default).** Give each mesh a non-overlapping UV1 at a consistent texel density, packed into a few atlases per zone. Use `material.lightMap` with `lightMap.channel = 1`.
  - Encoding: RGBM in UASTC LDR is the safe choice for the Low tier. UASTC HDR needs three.js r170 or later, and devices without HDR texture support fall back to uncompressed half-float, which costs a lot of memory.
- **A. Per-vertex lighting (stretch goal), only for meshes that are already dense,** such as sculpted cave rock. Sample across each triangle rather than at the vertices, because vertices in corners pick up light leaks.
  - Read the samples from a high-resolution EXR bake.
  - Solve for vertex values with least-squares vertex baking (Kavan et al. 2011). Lumped barycentric averaging is a simpler fallback, but it blurs.
  - Skip adaptive mesh refinement. It isn't worth the complexity, and it conflicts with the LOD system.
  - glTF has no float16 vertex attribute, so store the values as float32, or as normalized uint16 RGBM.
- **Bake the same way everywhere.** Use the same units, exposure and view transform for every bake, so surfaces using different storage don't show seams.

### 7.2 Directional bake for highlights (should-tier)
- Bake irradiance six times, each time with the shading normal overridden to a world axis (±X, ±Y, ±Z). Convert the results to L1 spherical harmonics and store them alongside the lightmap or the vertex lighting.
- The shader then uses them two ways: diffuse lighting from the normal map, and a GGX highlight in the dominant light direction, gated by roughness and AO.
- This is what makes wet basalt and lacquered wood glint.

### 7.3 Reflections
- **Everywhere: box-projected reflection probes.** Render one HDR cubemap per space in Cycles, prefilter it into roughness levels, and apply parallax-corrected box projection by patching the material through `onBeforeCompile`. Blend between the two nearest probes.
- **Planar reflections: only for mirror-like water.** That means the Obsidian Mirror, the corridors and the river. Run one or two at a time, at half or quarter resolution, disturbed by the water's normal map. A planar reflection roughly doubles the draw calls of whatever it reflects, so budget for it.
- **Screen-space reflections: desktop High tier only** (a stretch goal).

### 7.4 Moving and unbaked elements
These are all done in shaders:
- **Water:** scrolling normal maps, Fresnel, teal absorption with depth, and caustics. The teal comes from baked light under the water, not from the water surface glowing.
- **Falls and curtains:** layered scrolling cards and spray. The Kawagiri water curtains part as you approach.
- **Mist:** height fog that is dense in the first 0–0.5 m above the water, plus a few soft sprites. No raymarched volumes.
- **Lava:** a flow-map emissive surface behind glass.
- **Geysers:** timed particles.
- **Moving props (boats, float rings):** lit from a baked grid of SH probes.

### 7.5 Glow and colour
- **Glow comes from lanterns and baked light.** Use emissive only on the small visible surfaces of light sources, at moderate strength, and keep bloom subtle (high threshold, low intensity).
- **Match Blender's colour management.** Use AgX in Blender and `AgXToneMapping` in three.js, with matched exposure. Compare a Cycles render with a browser screenshot from the same camera in three zones.

### 7.6 Optional experiment: GPU adaptive subdivision
Only consider this after everything in the must tier works. One option is zalo's crack-free adaptive subdivision for TSL/WebGPU (https://github.com/zalo/three.js/blob/tsl-adaptive-subdivision/examples/webgpu_tsl_adaptive_subdivision.html). It could add real displaced silhouettes to a few close-up surfaces on the High tier.

Its limitations:
- It runs on WebGPU only.
- It lives on a fork branch, not in released three.js.
- The displaced surface can drift away from both the baked lighting and the walk mesh.

If you try it, bake on the displaced LOD0 and keep collision on the undisplaced mesh.

---

## 8. Web app and progress site
- **Export:**
  - glTF/GLB with meshopt compression and quantized attributes
  - KTX2 textures
  - JSON for probes, the SH grid, zones, the walk graph and placements
- **Stack:** Vite and three.js, pinned to one release, on WebGL2. WebGPU is optional, except for §7.6.
- **No pop-in.** The world should feel solid.
  - Load the starting zone and everything visible from it before the player can move.
  - After that, preload at least two portals ahead, and unload only zones that are out of sight and three or more steps away.
  - Portal culling toggles visibility only for zones that are already loaded.
  - If a zone isn't ready, hold the player at the portal, for example by thickening the mist.
  - If everything fits the Low-tier memory budget, simply load it all upfront.
- **Modes:**
  - **Walk:** a touch joystick and drag-to-look on phones; WASD and mouse on desktop.
  - **Dollhouse:** a cutaway orbit of the volcano; tap a place to travel there.
  - **Place list:** teleport to any place.
  - On-screen labels for the 10 attractions and the main places.
- **Quality tiers.** Detect the tier automatically, with a manual override.
  - **Low:** probes, one planar reflection at quarter resolution, DPR at most 1.5.
  - **High:** two planar reflections, full-resolution effects, DPR 2, and SSR as a stretch goal.
- **Budgets for Low (suggested):**
  - ≤ 150 draw calls, including reflection passes
  - ≤ 500k visible triangles
  - ≤ 250 MB of GPU texture memory
  - interactive within 5 seconds

  You can't measure frame rate on a phone from this machine. Log `renderer.info` and desktop timings at each gate, and ask the owner to try one real phone at the vertical slice and again at the end.
- **Progress site (already built).** The site lives at `3d/progress/index.html` and has three tabs: Gallery, Agents and Spec. The owner watches it on their phone at `https://terminal.sels.tech/lp/8742/3d/progress/`. Serve the **project root** with `sbg start kazanyu-progress -- python3 -m http.server 8742 --bind 127.0.0.1 --directory /home/agent-tom/Desktop/volcanospa`. If that unit is already running, leave it alone. The page needs no rebuilding: it re-reads these files every 5 seconds, so updating it simply means writing them. You may extend the page if you need to.
  - `3d/status.json`: the overview.
    ```
    {updated, phase, phase_index, scope_tier, headline, phases[], gates[],
     metrics:{draw_calls, triangles, texture_mb, desktop_ms},
     checks:{walk, placement, geometry},
     publish:{url, last_deploy, tiers_ok}}
    ```
    Checks are `"pass"`, `"fail"` or `"warn"`.
  - `3d/agents.json`: one entry per subagent, **including finished ones**.
    ```
    [{id, name, role, model, status, updated, last, outputs[]}]
    ```
    `status` is one of queued, running, blocked, failed or done; `last` is a one-line latest update. Update the entry when you start a subagent, when it reports, and when it finishes. Subagents report to you; only you write this file.
  - `3d/gallery.json`: append-only, newest entry last.
    ```
    [{title, kind, image, concept, space, round, score, agent, time, status, notes}]
    ```
    `kind` is one of graybox, contact, material, lod, render, compare or paintover. `image` is a path relative to `3d/`, such as `renders/b1/contact-r2.jpg`. `concept`, if set, is a concept image shown next to it, such as `../lookbook/img/05-mist-corridor.jpg`. Save renders as JPEG of about 1600 px under `3d/renders/` so the page stays light on a phone. Every graybox pass, contact sheet, material or LOD sheet, review round and concept comparison gets an entry.
  - The Spec tab shows `layout-spec.md`, this brief and `3d/decisions.md` exactly as they are, so keep `decisions.md` up to date. `3d/inventory.csv` is linked from the same tab.
  - Write each JSON file atomically: write to a temporary file in `.scratch/`, then `mv` it into place, so the page never reads half a file.

---

## 9. Done means
- **Everywhere is walkable at a believable scale.** The walk graph reaches every place from the Basalt Gate on foot. Stairs, doors and railings are human-sized, and the views at 1.6 m eye height match the scale of the concept art.
- **Placement is deliberate.** Placement checks pass in every zone, with any waivers recorded. Every space has a clear focal point and sight lines that lead to the next space. In the last review round, every space scores 4 or higher, or its exceptions are explained.
- **The geometry is clean.** No z-fighting and no intersecting faces, checked on every export by methods you choose and with the results recorded.
- **Water behaves like water.** It flows downhill and settles level a few centimetres below each rim, and the sea is a single level surface.
- **The world feels solid.** No pop-in, no light leaks, and no seams between lighting methods or LODs.
- **Glow comes from lanterns and baked light, with bloom kept subtle.**
- **Assets meet the asset standard.** They are parametric, with LOD0–3 and seeded variants, use library materials only, and pass the recognition test at LOD3.
- **Performance and publishing hold up.** The Low-tier budgets are met, or the gap is explained. The published site loads at every tier.
- **It can be rebuilt.** `3d/README.md` rebuilds everything from scripts. The inventory shows a final status for every asset, and `decisions.md` explains every deviation from this brief.

**Final report:**
- what's done, which scope tier you reached, and what was cut and why
- results against the budgets
- the published URL and the proxied dev URL

Then send a `tm-notify`.
