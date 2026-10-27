# Kazan-yu generator guide (for Haiku-tier builders)

Read this before writing a generator. It is the distilled result of 28 assets and 84 review rounds. Assets built this way pass review (**6/10 or better**: the mean of six 1–5 scores, times two) in one or two rounds. The five assets that did not follow it (oke_bucket, stool, bench, towel_folded, stepping_stone) took 3–7 rounds each; their mistakes are the pitfalls in §8.

Hard rules you already have (`3d/AGENT_RULES.md` Part A) still apply: one Blender GPU job at a time, scratch only under `.scratch/`, write only the paths your brief names, never edit `genlib.py`, `render_lod_sheet.py`, `assets.json`, `asset_list.csv` or the material library.

Helpers used by every snippet below live in `tools/gen/kzgeo_common.py` (import as `C`). They are tested: `.scratch/guide/recipes.jpg` shows one of each, all closed solids verified manifold.

---

## 1. Workflow (do the steps in this order)

1. **Read your row** in `3d/asset_list.csv`: identifying features, parameter ranges, dims, materials, budget `LOD0/1/2/3`, animation. Read the proxy in `3d/assets.json` (`genlib.proxy(asset)`). The proxy is the *default build size*, not the range maximum.
2. **Open every concept image** in the row. Lookbook names are under `lookbook/img/`, the rest under `refs/gen/`. Then look for the asset on a **scale-bar sheet** (`refs/gen/sheet-vs-*.png`, `sheet-mod-*.png`): front and side views with a 1 m bar. Reviewers claimed twice that the stepping stone had no sheet; it is panel 5 of `sheet-vs-bath-props.png`. Look.
3. **Measure the sheet with PIL** before you code (snippet below). Write the numbers into your module docstring as the targets: overall w/d/h, the ratio that defines the silhouette (towel 0.40 × 0.30 footprint, 3 towels ≈ 0.20–0.23 m tall; chochin body h/w 1.0–1.05; stepping stone 0.60 wide × 0.20 thick, 0.14 above water), part sizes (rim lip 15–20 mm, hoop 15 mm, slat 0.09–0.11 m) and counts (30 staves, 5 posts, 14–18 ribs).
4. **List the parts** of the concept object with their construction: joint, profile, chamfer, lathe, sweep, rock. Every part in the concept must exist in geometry at LOD0. The reviewers score what is missing (the ladle scoop, the tub under the drape, the weirs, the wall brackets, the rod end caps) more than what is imperfect.
5. **Write `build(lod, seed, **params)`** with the recipes in §4. Styles cycle with the seed (§6). Build LOD0 first and get it right, then derive LOD1–3 (§5).
6. **Check:** `genlib.check(obj, ASSET, lod, budget)` has no problems at every LOD × seed; `C.check_closed(mb.bm)` reports 0 open edges on parts meant to be solid.
7. **Render:** `blender -b -P tools/gen/render_lod_sheet.py -- <asset>` then `.venv/bin/python tools/gen/compose_lod_sheet.py <asset>`. If the stock front view reads badly (wide, deep or flat assets), also write `sheet_34.jpg` (¾ views) and always `styles.jpg` when you have styles. Write `canonical.jpg` (Cycles, 1600 × 900, LOD0 seed 1, warm key + rim + small point lights for wet glints, concept crop strip on the right).
8. **Self-check** against §10 with the images open. Fix, re-render, keep `canonical_r<N>.jpg`.
9. **Report** per §11. Fixes you say are done need a crop that shows them.

### Measuring a concept panel with PIL

```python
# .venv/bin/python (the only Python here with PIL).  Full script: .scratch/guide/measure_crop.py
from PIL import Image, ImageDraw
im = Image.open('refs/gen/sheet-vs-bath-props.png')          # 1536 x 1024, 3 x 2 panels
crop = im.crop((520, 490, 1030, 1020))                         # panel 5 (stepping stone): x0, y0, x1, y1
big = crop.resize((crop.width * 2, crop.height * 2)); d = ImageDraw.Draw(big)
for x in range(0, big.width, 100): d.line([(x, 0), (x, big.height)], fill=(255, 80, 80))   # 50 px grid
for y in range(0, big.height, 100): d.line([(0, y), (big.width, y)], fill=(255, 80, 80))
big.save('.scratch/<me>/measure_stone.png')                   # open it, read pixels off the grid
bar_px = 392 - 102            # the 1 m bar in crop pixels          -> 290 px/m
front_w = (255 - 50) / 290    # stone width in the FRONT view        -> 0.71 m (label says 0.60: note both)
height = (160 - 95) / 290     # base to top                          -> 0.22 m (label 0.20)
above_water = (135 - 95) / 290  #                                    -> 0.14 m above the waterline
```

When the bar and the printed label disagree by more than 10 %, build to the label (the proxy and the asset row come from the labels) and write the discrepancy in your docstring and report. Ratios measured off the drawing (thickness : width, cap : body, post : pipe) are reliable either way.

---

## 2. The quality bar: what the six scores mean

Each is 1–5. Pass is a mean of 3.0. The examples are real review quotes.

| score | a **2** looks like | a **4** looks like |
|---|---|---|
| **likeness** | "grey chamfered boxes on a dark slab read as tiles or foam blocks, not folded towels" (towel r1); "the drum reads as a bin or a log" (stool bath r3) | "unmistakably the Basalt Gate" (torii r2); "a clear bucket with handle at phone size" (bucket r3) |
| **silhouette & proportion** | "the cabin is squat: h/D 0.85 against the concept's 1.15" (lift_car r2); "stack is a third of the concept height" (towel r2) | "0.72 m height and 0.42 m seat match the ramen-counter stool" (stool r3); measured h/D 1.10 vs 1.15 (lift_car r3) |
| **construction detail** | "legs butt straight onto the seat, no tenon, apron or stretcher" (stool r2); "a single plain beam with a flat water ramp, no coursing" (stream r1); "flat decal plane: no weave, no drape, thin hardware" (banner r3) | "rafter ends, ribbed tile courses, a koran rail" (pavilion r1); "fascia is one smooth dark laminated arch with iron straps" (bridge r3) |
| **material use** | "cloth renders lavender-grey; towel-white tint does not work" (towel r1); "slipper covers use noren with tints of 26–34×, which comes out pink" (cubbies r1); a pale tan band from `basalt_dry` on a stone that should be one near-black material (stone r4–r6) | "one near-black wet basalt across side and top" (stone r7); "hinoki walnut tray reads correctly, no change needed" (towel r4) |
| **LOD & recognition** | "LOD3 is a hexagonal bipyramid: a gem, not a flat stone" (stone r1); "LOD0 is a closed box, LOD1 an open frame: the silhouette changes shape at the first switch" (bench r1); "LOD2 shows 2 towels, LOD3 shows 4" (towel r5) | "LOD2/LOD3 stay a capped lantern at 6 m and 17 m" (chochin r3); "LOD3 silhouette is excellent" (torii r2, scored 5 in r3) |
| **variation** | "the three seeds look nearly identical; only the hoop count changes" (bucket r1); "seeds change only colour" (banner r2) | "six variants all read as the concept chochin" (chochin r3, scored 5); "cluster / spire / slab give real shape variety" (monolith r3) |

Notes on the rubric:

- Library colour problems are listed separately and are **not** held against you, but a wrong *choice* of material is (pale `basalt_dry` on a wet stone, `noren` with a 30× tint, `lava_glass` for clear cabin glass).
- Small props: an LOD3 that is a few pixels at its switch distance is accepted. A wrong *shape* at LOD2/3 (gem, '=' bar, pagoda) is not.
- "Reads as" is judged at the real viewing distance: 1.6 m eye height, 2–5 m away for props.

---

## 3. Why the five Haiku assets took 3–7 rounds (read this once)

- **They built what they imagined, not what the sheet shows.** The towel stack was a third of the sheet height; the bucket had 16 staves against the sheet's 30; the stool footrest was square where the brief says ring; the bench had skirt boards no concept shows.
- **One real bug per asset ate rounds:** the towel's zero-thickness edge (`T/2·sqrt(1-s²)` → 0 at the rim) survived r1–r4 because nobody looked at the edge in the render; the stepping stone's pale band came from the wrong material slot on a shoulder ring (`stepping_stone` / `basalt_dry`) and the builder kept "fixing" the other slot.
- **Fixes were reported done but did not show** (continuous plinth glow, crease position, yaw range). Reviewers now check earlier fixes against the render; "landed in code, not visible" counts as not done.
- **Seeds changed tint and small offsets, never shape.** Every one of the five scored 1–2 on variation in r1.
- **LOD2/3 were built separately** (new boxes) instead of being derived, so counts and silhouettes changed at the switch.
- **The three same-tier reviewers oscillated** (thinner / thicker stones, skirt off / apron on, 22–26 ribs then 14–18). Builders followed the latest voice instead of measuring the sheet. §9 tells you what to do.

---

## 4. Recipes

All snippets assume:

```python
import math, genlib, kzgeo_common as C
mb = genlib.MeshBuilder()
wood = mb.slot('hinoki', variant='wet_oiled'); stone = mb.slot('basalt_wet', wetness=0.6)
r = C.rng(seed, 'partname')          # one stream per part (see §6)
```

Every helper tags the faces it makes with the slot you pass. Build everything in one `MeshBuilder`, call `C.centre_base(mb)` last, `o = mb.to_object(ASSET)`, then `genlib.finish(o)`.

### 4.1 Rounded or chamfered board and slab, with real thickness
Thin boards need a visible edge: 3 mm chamfer minimum at LOD0, 6–10 mm rounds on seat edges (bench r2 asked for exactly this). A board thinner than 20 mm reads as paper.

```python
C.board(mb, (0, 0, 0.42), (2.4, 0.11, 0.045), wood, bevel=0.006, segs=2)   # a seat plank, rounded edges
C.slab(mb, (0, 0, 0.05), 0.5, 0.2, 0.10, stone, rc=0.03)                    # rounded-corner stone slab
C.chamfered_bar(mb, (0, 0, 0.1), (0.06, 0.06, 0.2), wood, ch=0.008, axis='z') # octagonal post / rail
```

`board()` clamps the bevel to 45 % of the thinnest dimension and tags every face (bevel faces included) through an int layer; see §8 for why `bmesh` tags are not safe.

### 4.2 Turned (lathe) profile
Buckets, bowls, stools, finials, caps, cups. Profile is `[(r, z)]` bottom → top; `r == 0` makes a pole; `closed=False` leaves an open band (hoops, bucket wall).

```python
R, r0, H, t, drop = 0.19, 0.15, 0.22, 0.012, 0.06
wall = [(r0, 0), (R*0.98, H*0.5), (R, H-0.018), (R+0.007, H-0.006), (R-t, H), (R-t, H-drop)]  # rolled lip
C.lathe_grooved(mb, wall, 30, 0.0015, wood)                 # 30 staves, 1.5 mm V-grooves (LOD0)
C.lathe(mb, [(r0, 0), (0, 0)], 30, wood)                    # base disc
for hz in (0.05, 0.17):                                     # copper hoops: open bands, 15 mm tall
    ro = r0 + (R - r0) * hz / H - 0.002
    C.lathe(mb, [(ro, hz-0.007), (ro+0.006, hz-0.007), (ro+0.006, hz+0.007), (ro, hz+0.007)], 30, bronze, closed=False)
```

Segments: LOD0 24–32 on anything a guest stands next to (the stool seat at 16 showed facets, bucket bowl at 12 showed facets); LOD1 12–14; LOD2 8; LOD3 6. Put a 12 mm two-step edge on seats and rims; a plain cylinder edge reads as a tin can.

### 4.3 Swept rail or beam along a curve
Handrails, girders, kasagi beams, pipes. The profile is `(x, z)` across the path; joints are mitred so the width stays constant.

```python
pts = [Vector((x, 0, 0.9 + 0.3*math.sin(math.pi*(x+3)/6))) for x in [-3 + 6*i/12 for i in range(13)]]
prof = [(0.03,0),(0.04,0.012),(0.04,0.03),(0.03,0.042),(-0.03,0.042),(-0.04,0.03),(-0.04,0.012),(-0.03,0)]
C.sweep(mb, pts, prof, wood)                                # 8-sided rail, 80 x 42 mm
rings, _ = C.tube(mb, pts, [0.03]*len(pts), bamboo, sides=10, cap0=True, cap1=True)   # round pipe
```

Use 12+ stations per metre of curve at LOD0, 4–6 at LOD1, 2 at LOD2 (the bridge fascia built from short straight boards read as "stair-stepped with kinks").

### 4.4 Boulders: faceted vs rounded, and when to use which
Reviewers rejected rounded boulders five times ("pillows", "sandbags", "dumplings", "glossy beads", "bead necklace") wherever the concept shows basalt. Basalt is **faceted and craggy**; use rounded forms only for river cobbles under water or when the concept is visibly smooth.

```python
C.hull_rock(mb, (x, y, 0), (0.25, 0.22, 0.18), stone, r, npts=12, ground=0.0)   # faceted chunk, size = radii
C.crag_rock(mb, C.frame((x, y, 0), (0, 1, 0)), 0.3, 0.26, 0.0, 0.38, stone, r, nside=7, bands=3)  # flat-topped bank mass
C.rounded_rock(mb, (x, y, 0.1), (0.3, 0.26, 0.2), stone, r, cuts=3, round_r=0.05, amp=0.012, clamp_z=0.0)  # smooth
```

Rules that passed: 2–3 size classes (0.2–0.6 m), overlap 30–40 % along a bank, every rock seated on z = 0 or sunk 30–40 % (never floating: bridge r1, chozubachi), `npts` 12–16 at LOD0 for 0.3 m rocks (12-point hulls read as "shards"), flat tops where people stand. Lower LODs keep the largest rocks (sort by volume), never a different set.

### 4.5 Irregular stone outline (smooth angular noise)
Per-vertex random jitter gives polygons with straight runs (stepping stone r2–r6). Low harmonics with seeded phases give lobes.

```python
f = C.stone_outline(r, R=0.3, aspect=r.uniform(0.72, 1.35), bites=r.choice([1, 2]))   # theta -> (x, y)
C.cobble(mb, f, N=54, t=0.17, mi_side=side, mi_top=top,
         top_fn=lambda x, y: -0.003*math.exp(-(x*x+y*y)/0.02), side_noise=0.007, r=r)   # closed solid, no ledge
```

`cobble()` runs the side rings straight into a rounded shoulder and the top: there is no horizontal ledge (the C1 ring that cost the stepping stone three rounds). Use it for stepping stones, basins (see 4.12) and footings.

### 4.6 Cloth panel with pleats and a belly (noren, banners, drapes)
A flat tinted plane is a 2. Pleats below 1 cm "do not read at all" (noren r2). Targets that passed: 1.5 cm ripple under the band, 3–4 cm peak-to-peak at the hem, 4–6 ripples per door panel, a 2–3 cm forward belly over the lower third, a turned hem, a head band, the slits opening 1.5–3.5 cm at the hem.

```python
cloth = mb.slot('noren', normal_strength=1.8); band = mb.slot('noren', tint=(0.0096, 0.0192, 0.0634))
for x0 in (-0.23, 0.23):                                   # two panels with a centre slit
    C.cloth_panel(mb, 0.45, 1.6, cloth, r, cols=8, rows=5, pleat0=0.0075, pleat1=0.018, belly=0.022,
                  band_h=0.07, mi_band=band, x0=x0)         # single-sided, faces +Y, writes '_sway'
```

Then the hardware the concept shows: a 0.03–0.04 m rod overhanging 0.08 m each side with turned or bronze end caps, 3–5 tab loops 0.07 m wide (not 8: they read as a checker strip), brackets standing the rod 0.06–0.08 m off the wall. Cloth is single-sided: say so in the docstring (double-sided render).

### 4.7 Soft folded fabric (towels, cushions): no knife edges
The towel profile `T/2·sqrt(1-s²)` is zero at the outline, so every towel had a knife edge and read as a lens or a tile. `pillow()` keeps full thickness to a shoulder 7 mm in from the edge, then rolls to 35 % of T at the outline.

```python
cloth = mb.slot('terry', variant='cream'); tray = mb.slot('hinoki', variant='walnut', wear=0.1)
W, D, T, PITCH = 0.36, 0.27, 0.044, 0.062
C.board(mb, (0, 0, 0.01), (W + 0.02, D, 0.02), tray, bevel=0.003)
for k in range(n):                                          # n = 4 or 5 (seeded)
    c1 = r.uniform(-0.3, 0.3) * W
    C.pillow(mb, (r.uniform(-.02, .02), r.uniform(-.02, .02), 0.02 + k*PITCH), W*r.uniform(.95, 1), D, T, cloth,
             rc=0.045, m=2, puff=0.017, creases=[(c1, 0.009, 0.02)], yaw=r.uniform(-.15, .15), tilt=math.radians(r.uniform(-2, 2)))
```

Pitch = T + puff + 2 mm so towels rest on each other (70 mm pitch on 52 mm towels read as "floating plates"). Put the main crease at ±W/3 on the top towel so it shows on the front; a seeded crease anywhere in ±0.35 W was invisible in every render. A cushion is one pillow with `puff` 0.04–0.05 and a 6 mm welt (`lathe` band).

### 4.8 Rope wraps
Concepts show rope as 10–15 mm cord, 2–6 tight turns with a tail. Thin lines (4 mm) and "crumpled ribbon" lashings were marked down (chochin r3, kakehi r2).

```python
rope = mb.slot('rope')
C.rope_turns(mb, (x, y, z), axis=(1, 0, 0), radius=0.03, n=4, mi=rope)      # 4 turns round a 60 mm tube
C.rope_band(mb, (x, y, z), (0, 0, 1), 0.04, 0.06, rope)                      # wound sleeve, 60 mm tall
C.rope_knot(mb, (x, y, z + 0.05), 0.014, rope)
C.rope_cord(mb, (0, 0, 0.6), (0, 0, 0.95), 0.006, rope, sides=6)             # twisted hanging cord
```

LOD1: 2 turns, no knot. LOD2: one band. LOD3: nothing (the tube carries the read).

### 4.9 Lantern head (iron frame + glowing paper)
Concept lanterns are **slender** (0.22–0.25 m wide, 0.4–0.6 m tall, w:h ≈ 0.5) with a dark frame, a hip roof and a finial. "Fat 0.45 m white cubes" lost points on bridge, stair and pavilion.

```python
iron = mb.slot('iron'); paper = mb.slot('lantern_andon', emissive_level=1.0)   # amber; see §7
centre = C.lantern_head(mb, (x, y, post_top), dict(iron=iron, paper=paper), lod, size=0.24, height=0.42, roof='hip')
lights.append(C.light_entry(centre, color_k=2200, watts=25))
...
C.set_json_props(o, kz_lights=lights)
```

Round chochin: `lantern_paper`; shoji and flat lit faces: `washi_backlit`. Always record the light position and colour as `kz_lights`; the bake needs it.

### 4.10 Glyphs and text (no mirroring, no broken strokes)
Author text on the plane facing **+Y**. A viewer standing on +Y sees world +X on their **left**, so glyph x must run towards −X. `text_solid` and `tracked_text` do that; if you place glyphs yourself and forget, the text is mirrored. Blender's text-to-mesh uses even-odd fill, which punches holes where CJK strokes cross (the "broken 火 / 湯" of signboard r3 and lift_drum r1); the helpers fill each outer contour separately.

```python
gold = mb.slot('gold_leaf'); black = mb.slot('lacquer_black')
C.board(mb, (0, -0.02, 1.2), (0.6, 0.04, 2.4), black, bevel=0.004)          # board behind the plane y = 0
C.text_solid(mb, '火山湯', 0.0, 1.5, 0.0, 0.42, gold, depth=0.008, vertical=True, gap=1.15)   # closed solids
C.tracked_text(mb, 'KAZAN-YU', 0.0, 0.35, 0.0, 0.05, gold, depth=0.005, tracking=0.3)
```

Sizes that read: 火山湯 fills ~60 % of the plaque width (torii r3); KAZAN-YU cap height ≥ 0.03 m on a 0.5 m lantern; relief 6–15 mm. LOD1: same glyphs with `res=1`; LOD2: three unequal dark blocks per line; LOD3: one quad. Text faces another way? Build facing +Y, then rotate those verts about Z. Check the front render: it must read, not mirror.

### 4.11 Card foliage
Opaque core first (it carries the silhouette and the LOD2/3 read), then cards 20–35° off the surface, a quarter of them hanging on the rim. Rectangles 0.32–0.45 m with a broadleaf-looking texture read as "lettuce"; keep cards ≤ 0.3 m on a 1 m pad and use `foliage_pine` (alpha-tested, double-sided).

```python
core = mb.slot('moss', tint=(0.45, 0.55, 0.32)); fol = mb.slot('foliage_pine')
C.foliage_pad(mb, (x, y, z), R=0.6, T=0.18, mi_core=core, mi_card=fol, r=r, n_cards=C.lod_pick(lod, 120, 50, 8, 0))
```

Pad thickness 0.25–0.33 R, flat underside, limbs visible between tiers with a 0.2–0.35 m dark gap. LOD3: core only, as a 6-sided lens, never a cone (reads as a pagoda).

### 4.12 Water-hosting geometry
The water surface is runtime FX. Build the vessel or channel and **record the level as a custom property**; never ship a water mesh in `build()`. A preview disc may go in your canonical render script.

```python
f = C.stone_outline(r, 0.3, aspect=0.85, harmonics=((3, .06), (5, .04), (7, .03)), bites=0)
C.cobble(mb, f, 24, 0.75, stone, stone, rings=((0.8, 0), (0.95, 0.25), (1, 0.6), (0.98, 0.85)),
         shoulder=(0.93, 0.97), top_scale=0.86, top_fn=lambda x, y: -0.3*max(0, 1 - (x*x+y*y)/0.045), side_noise=0.012, r=r)
o = mb.to_object(ASSET)
C.water_props(o, level_z=0.72, outline_xy=[f(2*math.pi*k/24) for k in range(24)], kz_overflow_dir=[0, 1])
```

Water sits 1–2 cm under the rim low point (chozubachi), 5 cm under stepping-stone tops (decisions), 0.06 m under a bucket rim so the inner wall shows (bucket r1). Channels: `kz_water_path` as `[x, y, z]` per pool end and `kz_weirs`; nothing below the bed (§8, stream monoliths).

---

## 5. LOD rules

**Derive, never rebuild.** One layout (positions, counts, sizes) computed once per seed; each LOD chooses resolution and which small parts to keep. If LOD2 has 2 towels and LOD3 has 4, or LOD1 is an open frame while LOD0 is a closed box, the asset fails LOD.

| LOD | keep | drop | typical resolution |
|---|---|---|---|
| 0 | everything in the concept; full budget on the identifying features | nothing | lathe 24–32, 2-seg bevels, rope turns, glyphs |
| 1 | all parts, all counts | bevels on small parts, grooves, knots, latin line | lathe 12–14, 1-seg chamfers |
| 2 | identifying features as shapes (rim flare, hoop, footring, crest, caps, posts) | small parts, text → blocks | lathe 8, no bevels |
| 3 | silhouette with the features that name it: seat **and** legs, bucket **and** one hoop, lantern **with** dark caps, stone as a flat disc | everything else | lathe 5–6, boxes, 20–150 tris |

**Budget without silently losing features.** Budgets come from `genlib.budget_of(ASSET)`; the check allows +10 %. Do not write a loop that rebuilds with less detail until it fits: that is how slipper pairs turned into "a box with a card" in the hero view (cubbies r3) and how a pine motif vanished (lift_drum r3). Instead:

- compute the triangle cost per part up front (lathe = 2·segs per ring, box = 12, bevelled box = 12 + 8·segs·edges) and pick resolutions that fit;
- if you must fall back, fall back on **resolution** (segments, rings, cards) of the biggest consumer, never on **presence** of a part, and print what you reduced;
- if the budget cannot hold the identifying features, build them anyway and propose the new budget in your report with the counts (stone r1 → LOD3 16 → 20 tris was accepted).

**The switch rule.** On a 390 × 844 phone with a 60° vertical FOV, LOD2 shows when the asset is below ~80 px tall, LOD3 below ~30 px, capped at 35 m and 80 m. Distance ≈ `844 · size / (2 · tan 30° · px)`: a 0.5 m prop switches to LOD2 at ~4.6 m and LOD3 at ~12 m; a 3 m object at 27 m / 80 m. The sheet renders `phone-lod2-lod3.jpg` at those distances: look at it. If your LOD2 is a dark dot at 5 m, give it a lighter top or a lump in the outline, not more triangles.

**No pops.** Same material slots on the same parts at every LOD (a `lacquer_dark` cap that becomes paper at LOD3 loses the lantern; a bronze rod that becomes black at LOD2 was flagged). Same colour values; if LOD3 merges parts, give the merged part the dominant material.

---

## 6. Seed variation: shape, not tint

Every first-round "seeds look alike" came from tinting and jitter. Pass-level variation changes what you see in the LOD sheet at thumbnail size: counts, proportions, style, layout.

```python
STYLES = ['bar', 'vanity', 'bath']                     # or the row's variants
style = style or C.cycle(seed, STYLES)                 # seeds 1, 2, 3 show three styles on the sheet
g = C.rng(seed, 'layout')                              # one stream per concern
n = g.randint(4, 5); taper = g.uniform(0.60, 0.90); H = g.uniform(0.16, 0.30)
cushion = cushion or C.pick(seed, 'cushion', ['red', 'indigo', 'cream'])
```

- Use `C.cycle` for the style so the three sheet seeds differ by construction, and `C.pick(seed, salt, options)` for secondary choices.
- **One `rng` per part** (`C.rng(seed, 'legs')`, `C.rng(seed, 'rocks')`). If one part draws from the stream another part uses, adding a draw (a new parameter, a `randint` for a count) reshuffles every part after it and your seed 1 silently becomes a different object between rounds. Never seed from a value drawn from another stream (`genlib.rng(rng.random(), ...)`).
- Draw the shape parameters **before** the LOD branches and independent of `lod`, or LOD0 and LOD2 of the same seed will differ.
- Ranges wide enough to see: height ±20 %, aspect 0.72–1.35, count ±1, leg splay 0.10–0.20, length ±0.3 m, one seed with a clearly different sub-feature (splayed legs, second crease, two bites).
- Document in the docstring exactly what seeds change.

---

## 7. Materials cheat sheet

Use `mb.slot(id, variant=..., **params)`; params are only `tint, wetness, wear, roughness_offset, scale, normal_strength, emissive_level`. Ids and variants: `3d/materials.json`.

| part | use | notes |
|---|---|---|
| pale new timber, bath stools, kumiko, deck boards | `hinoki` (default), `variant='natural'` | reads pale and orange under warm light; reviewers want aged timber almost everywhere |
| structure, counters, posts, benches in bath zones | `hinoki variant='wet_oiled'` (warm oiled) or `'dark_timber'` (0.26/0.18/0.12) | pavilion, bridge, bench r3 all asked for 25–40 % darker structure |
| bar stool, ramen counter, stained frames | `hinoki variant='stained'` (mid-brown #5e3927) or `'walnut'` (near-black #33221a); `'dark_timber'` #4d3124 | warm-key calibrated, check with tools/matlib/calibrate.py |
| trays, rails, plaques frames | `hinoki variant='walnut'` | the towel tray that passed |
| matte black caps, urushi | `lacquer_black` (clean) / `lacquer_dark` (worn, mottled) | `lacquer_dark` mottling reads as rust on small parts; use `lacquer_black` for caps and plaque fields |
| wet stone: stepping stones, basins, banks, treads | `basalt_wet` with `wetness` 0.35 (sides) → 0.95 (tops), `roughness_offset` −0.05 for polish | one material across the stone, vary wetness per slot |
| dry stone: plinths, piers, kerbs | `basalt_dry` | renders paler and browner than the concept; never on a part the concept shows wet. Cool it with `tint=(0.5,0.5,0.55)` if you must (torii used 0.5×) |
| flagstones, kerb tops | `paving` | |
| plaque fields, water preview disc | `obsidian` | reads as glass at small scale: not for stone edges (stone r3) |
| hoops, straps, brackets | `bronze variant='smooth'` for bands and rails; `iron` for black frames, straps and lantern cages | plain `bronze` has a crumpled normal that reads as foil on small parts |
| gilt text, brass rims | `gold_leaf` | |
| noren, cushions, banners | `noren` (indigo) and its variants `black / vermilion / cream` | **never** multiply the tint by 10× or more to get another colour: 26–34× gave "pink paper". Use the variant, or ask for one |
| towels, robes | `terry variant='cream'` | |
| off-white cloth, slipper uppers | `linen` | |
| bowls, cups | `ceramic variant='celadon' / 'tenmoku' / 'white'` | |
| square lanterns (andon) | `lantern_andon` | amber, emissive |
| round paper lanterns | `lantern_paper` | emissive; red: `tint=(1, 0.05, 0.02)`, `emissive_level` ≈ 0.5 |
| shoji, lit sign faces | `washi_backlit` | emissive 0.45 base; add a `kz_lights` entry so the bake has a source |
| ropes, cords, lashings | `rope` | |
| bamboo | `bamboo`; node bands `bamboo` with `tint=(0.5, 0.45, 0.38), wear=0.5` | |
| moss, pad cores | `moss` (tint it darker: (0.45, 0.55, 0.32)) | |
| needles | `foliage_pine` | alpha card material, double-sided |
| trunks, limbs | `bark` | reads orange-tan (library issue): note it, do not compensate |

**Never:** tint multipliers above ~2.5 (gold from bronze used 2.5 and was accepted; 26× was not); `basalt_dry` or `stepping_stone` on a surface the concept shows black and wet; emissive levels above ~1.2 (AgX desaturates and blows out); `lava_glass` for clear glass (`glass_clear` exists); one-off materials (ask the lead).

**Check a colour in pixels, don't guess:**

```python
from PIL import Image; im = Image.open('3d/renders/models/<asset>/canonical.jpg').convert('RGB')
box = (x0, y0, x1, y1)                                   # a flat, lit patch of the part
px = list(im.crop(box).getdata()); avg = tuple(sum(c[i] for c in px) // len(px) for i in range(3))
print('#%02x%02x%02x' % avg)                             # compare with the concept crop measured the same way
```

Reviewers do exactly this ("render stile #6F3916, concept stile #402817"). If your part is more than ~30 % off in value or clearly off in hue, say so in the report with both numbers, and name the library id so the material agent can act.

**Lighting:** dark stone is near-black now. Light the canonical with a warm key, a rim light and 1–2 small point lights so wet surfaces glint; do not brighten albedo to compensate.

---

## 8. Pitfalls: symptom, cause, fix

1. **Knife-edge pillows** (towel r1–r4). Symptom: towels read as lenses, diamonds, cardboard; LOD2 "pointed diamond stack". Cause: top and bottom profile both → 0 at the outline. Fix: `C.pillow()` (full thickness to a shoulder, rolled edge at 35 % T). General rule: no closed solid should have a zero-thickness edge; check the profile value at s = 1.
2. **Bevel slot tagging.** Symptom: flat faces of a bevelled box render in slot 0's material (wrong wood / stone on a box). Cause: `bmesh.ops.bevel` rebuilds faces; faces collected before the bevel are stale. Fix: `genlib.MeshBuilder.box(bevel>0)` and `C.board()` tag every face via `_mark_old()` / `_new_faces()`. Do the same in your own code.
3. **bmesh `tag` pitfall.** Symptom: "new faces" lists empty or wrong after a bevel or subdivide. Cause: those ops clear `BMElem.tag`. Fix: an int layer (`lay = mb._mark_old()` before, `mb._new_faces(lay)` after). Never use `.tag` across an op.
4. **Mirrored text.** Symptom: 火山湯 or KAZAN-YU reads backwards from the front. Cause: glyph x mapped to world +X on a +Y-facing plane. Fix: glyph x → −X (`C.text_solid`); verify on the front render. Related: broken CJK strokes from even-odd fill; use the helpers (per-contour fill), not raw text-to-mesh.
5. **Skirts and under-floor mass** (stream r1–r4, bench r1). Symptom: "monolithic blocks with a puddle on top", "enclosed shelter, not a bench", kerbs 3–4× taller than the channel. Cause: building terrain, skirts or filler below the bed / under the seat. Fix: build only what the concept shows above grade; the place model supplies the ground (`kz_ground_profile`). Open undersides are fine when they sit in the ground.
6. **RNG draw order** (§6). Symptom: seed 1 changes shape when you add a parameter, or LOD2 differs from LOD0 of the same seed. Fix: one stream per part, shape parameters drawn before LOD branches, never seed from another stream's draw.
7. **Fallback LOD paths that drop detail** (§5). Symptom: a hero view showing the cheap tier of a part, a motif gone at r3. Fix: budget by arithmetic; fall back on resolution and print it; never on presence.
8. **Material slot mix-ups** (stone r4–r6). Symptom: a pale band in the render that the docstring says is dark; two reviewers point at two different slots. Cause: a ring assigned `m_side` where the docstring promised `basalt_dry`, and a shoulder ring added "for the chamfer" with its own slot. Fix: name slots by *part* (`m_top, m_side, m_skirt`), assign in one place, and render a crop per slot once (or temporarily give each slot a loud tint) to see where each one lands. Keep the docstring and the code in agreement.
9. **Ledges and steps in profiles** (stone r1, r5, r6; stool "cake" seat). Symptom: a horizontal line around a part that should be one convex curve. Cause: two rings at nearly the same height with different radii. Fix: monotone, convex profiles; one ring per real feature.
10. **Pivot and proxy.** Symptom: `pivot off centre (0.03, 0.05)` on the sheet; "h 1.31 > proxy 0.90". Fix: `C.centre_base` last; for props with an axis, centre on the axis and keep extras inside 5 % of the proxy. A proxy that is clearly too small for the concept: build to the concept and propose the proxy value, do not shrink the object.
11. **Stale materials in reopened .blend files** (found by the material agent). Symptom: a render script that opens `3d/assets/<asset>.blend` or an older scene still shows milky `lava_glass`, pale `basalt_wet` or pink `washi_backlit` after the library was fixed, because `matlib.assign()` reuses the material already appended in that file. Fix: call `matlib.refresh()` (optionally `matlib.refresh(['lava_glass'])`) at the start of any script that opens an existing .blend; it re-appends the current library versions and remaps all users. Fresh `blender -b -P` builds from an empty scene do not need it.
12. **Flat planes with a texture** standing in for geometry (banner, towels on the counter, plaque straight on the wall). Symptom: "flat decal plane", "cuboids that read as books". Fix: every part the guest sees from 2 m gets real section: hem, rod, fold, frame, bracket, relief.
13. **The canonical hides the problem.** Symptom: the reviewer's first sentence is about something your render did not show (the drape tub, the open underside, the back). Fix: ¾ view at 1.6 m eye height, every style in `styles.jpg`, a crop of each disputed part.
14. **Styles not rendered.** The bench reached r3 before its five styles were seen. If the row lists styles or variants, `styles.jpg` (LOD0 and LOD2 of each) is part of round 1.

---

## 9. Reviewer conflicts: the concept sheet decides

Reviews come from the same model tier as the builder and they oscillate (stones thinner in r1, thicker in r3; bench skirts off in r1, apron on in r3; chochin ribs 22–26 then 14–18). Rules:

1. When two rounds disagree, **measure the sheet** (§1) and build to the measurement. Quote it in the report: "r1 asked for 0.10–0.13 m, r3 for 0.13–0.16 m; sheet-vs-bath-props #5 measures 0.20 m by the label and 1:3 thickness to width, so I built 0.15–0.21 m."
2. If no sheet shows the part, use the lookbook image and say which one and where you measured.
3. Never silently follow the latest voice. Reviewers from round 3 on read the earlier reviews and may only reverse a target with sheet evidence; give them that evidence.
4. If the sheet contradicts the asset row (towel W arrow spans the cloth, not the rod; torii proxy h), build to the sheet and propose the row / proxy change in the report. Do not edit shared files.

---

## 10. Worked example: the stepping stone (what finally passed at r7)

**Row:** r 0.25–0.45 m, thickness 0.15–0.30 m, polish, edge roughness, ovality; materials `stepping_stone basalt_wet obsidian`; budget 1000/300/60/20; proxy 0.75 × 0.75 × 0.22.

**Measure** (`refs/gen/sheet-vs-bath-props.png`, panel 5; crop in `.scratch/guide/measure_stone.png`, 290 px/m): labelled 0.60 × 0.60 × 0.20; the drawn front is ~0.70 wide (label wins, note it); top sits 0.14 m above the water, so 0.06 m is under; thickness : width ≈ 1 : 3; plan is a rounded irregular polygon with one deeper bite; the side is a near-vertical crust with chips; the top is flat, near-black, wet, with many small glints. Lookbook 05 and `ref-b1-lobby.png` agree: one dark wet material across top and side.

**Targets written before coding:** footprint 0.5–0.75 m, aspect 0.72–1.35, thickness 0.15–0.21, flat top with a 2–4 mm dish and seeded tilt, no ledge, lumpy outline (harmonics 2–9, 1–2 bites 6–11 %), 4–9 mm side displacement with 2–4 chips, `basalt_wet` everywhere (side wetness 0.35, shoulder 0.5, top 0.95), tint cooled to (0.32, 0.36, 0.46) so the library basalt reads near-black.

**Build** (this is `gen_stepping_stone.py` in short):

```python
g = C.rng(seed, ASSET)
R, t = g.uniform(0.25, 0.36), g.uniform(0.15, 0.21); aspect = g.uniform(0.72, 1.35); pol = g.uniform(0.4, 1.0)
f = C.stone_outline(g, R, aspect=aspect, bites=g.choice([1, 2, 2]), bite_depth=(0.06, 0.11))
N = C.lod_pick(lod, 54, 24, 10, 5)
side = mb.slot('basalt_wet', wetness=0.35, roughness_offset=0.12, tint=TINT)
top = mb.slot('basalt_wet', wetness=0.95, tint=TINT, roughness_offset=round(-0.05 + 0.2*(1-pol), 3))
dish = (g.uniform(-.1, .1), g.uniform(-.1, .1), g.uniform(.001, .004))
C.cobble(mb, f, N, t, side, top, rings=C.lod_pick(lod, RINGS0, RINGS1, RINGS2, RINGS3),
         top_fn=lambda x, y: -dish[2]*math.exp(-((x-dish[0])**2+(y-dish[1])**2)/0.03), side_noise=0.008*(lod == 0), r=g)
```

Then clamp the long axis to 0.355 m half-extent (proxy), `C.centre_base`, `to_object`, `finish`, a cylindrical UV on the sides so the texture has no vertical seam.

**Why it passed (r7, 6.33):** "one near-black wet basalt, flat top, rounded lumpy outline, three clearly different seeds." **What it still lost points on:** thick "loaf" proportion (the reviewer measured 1:5 off the lookbook; the sheet says 1:3, so this is a §9 case to argue with the crop), no fine crust glints on top, LOD2/3 tops paler than LOD0. Fixes for a 7+: thickness 0.12–0.18 with more batter, a second noise octave on the side, LOD2 at 12 segments with a one-ring chamfer, LOD2/3 top tint matched to LOD0.

**What cost six rounds before that:** a shoulder ring (ledge), `basalt_dry` and `stepping_stone` slots on visible bands (pale tan), per-vertex jitter (polygonal outline), a 12-tri bipyramid LOD3 (gem), a boolean-looking notch, seeds that differed by 15 %. Every one of those is a §4/§8 item.

---

## 11. Pre-report checklist (answer every line yes before you report)

1. I measured the concept sheet (or the named lookbook image) and the targets are in my docstring with numbers.
2. Every part visible in the concept exists in LOD0 geometry (list them against the sheet).
3. The overall w/d/h and the defining ratio are within 10 % of the measured targets, and the bbox is inside the proxy +5 % (or I proposed a new proxy with values).
4. No zero-thickness edges, ledges, floating parts or boolean-looking notches: I checked `C.check_closed` on solid parts and looked at the edges in a close crop.
5. Every slot is named by part, assigned in one place, and matches the docstring; `basalt_dry` / `stepping_stone` are not on anything the concept shows wet; no tint multiplier above 2.5.
6. Seeds 1, 2, 3 differ in shape (count, proportion, style or layout), visibly at sheet thumbnail size; each part has its own `rng` stream; shape parameters are drawn before the LOD branches.
7. LOD1–3 are derived from the same layout: same part counts, same slots, identifying features kept; LOD3 names the object (seat and legs, bucket and hoop, lantern and caps).
8. Triangle counts are within the row budget +10 % at every LOD × seed, with no silent fallback (if I reduced something, the report says what).
9. `render_lod_sheet.py` + `compose_lod_sheet.py` ran clean: no PROBLEMS line, pivot centred, `3d/assets/<asset>.blend` written.
10. `phone-lod2-lod3.jpg`: I can name the object in the LOD2 shaded pane and the LOD3 silhouette is the right shape.
11. `canonical.jpg` is a ¾ view at eye height, LOD0 seed 1, warm key + rim + glint lights, with labelled concept crops on the right; `styles.jpg` shows every style / variant at LOD0 and LOD2.
12. **I looked at my final canonical and every styles and sheet image myself**, at full size, and compared each with the concept crop beside it.
13. Text reads correctly (not mirrored, no broken strokes) in the front render; emissive panels glow amber, not white or pink; `kz_lights` recorded.
14. Water, if any, is a custom property (`kz_water_level` / `kz_water_path`), not a mesh in `build()`.
15. Any script of mine that opens an existing `.blend` calls `matlib.refresh()` first, so the renders show the current library.
16. For every fix a reviewer asked for, the report says done / partial / not done, and every "done" that a reviewer disputed earlier has a proof crop (`3d/renders/models/<asset>/proof_<fix>.jpg`) showing it.
17. Reviewer conflicts are settled by a sheet measurement quoted in the report, not by following the latest review.
18. Library colour problems are reported by material id with measured pixel values, not compensated for with tint.

---

## 12. Report template

```
rules sha256: <sha256sum 3d/AGENT_RULES.md>
asset: <id>   styles: <list>   seeds shown: 1 2 3
measured targets: <from the sheet: w x d x h, ratio, counts> (sheet <file> #<panel>, <px/m>)
tris per LOD (seed 1/2/3): LOD0 a/b/c  LOD1 ...   budget: <row>   check problems: none
parameters: <name range default> ...
seeds change: <shape things>
materials: <slot -> id/variant/params>; colour notes: <id: measured #rrggbb vs concept #rrggbb>
LOD: what LOD1/2/3 keep and drop; switch distances from the sheet; recognition result
self-critique rounds: r1 -> r2 changes ...
fixes from review r<N>: <fix>: done (proof crop path) | partial (why) | not done (why)
reviewer conflicts: <what r1 and r3 said; what the sheet measures; what I built>
still weak: <honest list>
proposed changes to shared files: <proxy / row / budget values, exact>
paths: sheet.jpg, phone-lod2-lod3.jpg, styles.jpg, canonical.jpg, proof crops
processes started: <none | sbg units, all stopped>
```

Keep it short. Numbers, paths and proof crops are what the lead and the reviewer read.

### Pitfall: bmesh reuses freed vertex slots
After any delete (including inside helpers such as `C.hull_rock`), "every vertex after index n" can include recycled old vertices and miss new ones. Never find new geometry by index range. Use an int-layer marker (`MeshBuilder._mark_old()` / `_new_faces()`, or `kzgeo_tea_set.mark_verts` / `new_verts`).
