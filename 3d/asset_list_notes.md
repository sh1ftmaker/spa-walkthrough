# Kazan-yu master asset list: notes

Files: `3d/asset_list.csv` (UTF-8, one header row) and `3d/asset_list.xlsx` (sheet "assets" with frozen header, autofilter, wrapped text and set column widths; sheet "summary" with counts). Both are built from `.scratch/asset_list/rows.py` by `.scratch/asset_list/build.py`. To change the list, edit the rows file and re-run the build, so the CSV and the xlsx stay identical.

**165 rows**: Must 136, Should 15, Stretch 10, n/a (place model) 4. The 4 place-model rows are no longer generators, so the list has 161 generators. Updated after the owner answered the open questions (round 1, see "Owner decisions"). One row per generator (parameters, LOD0-3, seeded variants), not per instance. Rows are sorted by priority, then by the first location on the guest route, then by tier. Within Must, the vertical slice (arrival hall, B1 lobby, Mirror corridor, koi junction, Obsidian Mirror) comes first, then the rest of Ground, B1, B2 and B3 in walking order.

The header uses the column strings from the brief exactly, including the bracketed hints (`locations (space ids)`, `priority (Must/Should/Stretch)` and so on). If a tool wants bare names, strip everything from ` (` onwards.

## Owner decisions (round 1)

1. **People: animated and skinned.**
   - `guest_figure` is now Must. It covers adult women and men, an elder and a child in yukata or as bathers, posed walking, standing, soaking, seated and floating.
   - Staff (server, attendant, chef) are a separate generator, `staff_figure`.
   - New rows: `figure_rig`, the shared skinned base mesh and rig, plus the cycles `figure_anim_walk`, `figure_anim_idle`, `figure_anim_sit`, `figure_anim_soak` and `figure_anim_float`.
   - The plan:
     - one shared skinned base mesh with parametric proportions and clothing
     - LOD0 about 2-4k tris, one low LOD, and impostor cards far away
     - only a few animated instances per zone (about 4-12)
     - CC0 or self-made rigs and animation only
   - `slide_rider` stays Stretch, but it is nearly free from the same rig: one held pose on the tube spline.
2. **Lodges.**
   - Added `cliff_lodge_b3`, the cliff-hung lit timber lodges on the B3 cavern walls (13, 14, 18, 19, 20). I judged it **Must**, because every B3 concept shows them and the vault reads empty without them.
   - Added `summit_lodge` with its lava window (11), as Should.
   - `facade_timber` no longer carries the cliff-lodge variant.
3. **Kawagiri seating is mixed by pod.**
   - `zabuton_cushion` and `table_low` stay.
   - `chair_dining` now has side-chair and armchair styles.
   - Proposed pod map for `b2_kawagiri`:
     - chairs: T4 (chef_table, armchairs), T5, T6 and T10-T12 (side chairs), each with a dining-height `table_low`
     - floor seating: T1-T3 and T7-T9, with `zabuton_cushion` and a low `table_low`
4. **Place models.** `cave_shell`, `terrain_exterior`, `hall_shell` and `floor_surface` are now modelled as part of each place model. They stay in the list with category `place_model` and priority `n/a (place model)` so the mapping remains visible. They have no sheet.
5. **People concept sheet.** Added `sheet-people` (see the grouping below).

## How it was derived

Sources read for every location:
- the concept art `lookbook/img/01-22`, and the layout sheets 23, 24, 25, 28, 29, 30-36
- `refs/gen/`: all six `sheet-mod-*`, the three `sheet-ref-*`, and `ref-b1-lobby`, `ref-mist-steps` and `ref-spiral-stair`
- `lookbook/index.html`
- all 61 space files in `3d/spaces/`, including each space's hero, anchored items, dressing rules, `why` notes and lead_requests
- `3d/placements.json`: 3,737 placements across 108 asset ids, counted by asset and by space (`.scratch/asset_list/counts.txt`)
- `3d/inventory.csv`, `3d/assets.json`, and `3d/materials.json` (32 library ids)

I opened every image listed above. I did **not** open 03 (master plan, superseded), 26 (route map), 27 (level stack) or 37 (alignment sheet). They are routing and alignment diagrams that add no props. I also did not open the `mat-*` and `sheet-tex-*` swatch sheets beyond using them as material references.

`est_instances` uses the placement count where one exists. Otherwise it is my estimate from the space rules, marked `~`. Triangle budgets follow brief 6.2: featured LOD0 5-20k, LOD1 about 40 %, LOD2 about 12 %, LOD3 a few hundred at most. Small props are far lower, and structural generators are budgeted per metre or per 100 m².

### Per location: what the images show and what it produced

**Approach road and Basalt Gate (g_road, g_gate). Sources: 01, 04, 31, sheet-mod-arrival.**
- The road is a lantern-lined causeway with a slab bridge, low basalt parapets and a flank waterfall. This produced `parapet_stone`, `bridge_slab`, `falls_lip_rock`, `plunge_basin` and `fx_falls_sheet`.
- There is one quiet brand stone, `stele_stone`.
- The gate has the basalt torii with its 火山湯 plaque, a timber porch passage, crest banners on the lit facade, and a hanging lantern cluster in front of the porch (04). This produced `torii_basalt`, `timber_passage`, `banner_hanging`, `facade_timber`, and the `chochin` cluster_n parameter.

**Arrival hall (g_arrival). Sources: 04, 31, sheet-mod-arrival.**
- Clusters of tall cylindrical chochin, not only round ones.
- The slipper wall, with slippers in the cells.
- A reception counter with folded towels.
- The lava window, which behind its mullions is a full lava landscape with falls, arches and lit bridges. That landscape is its own row, `lava_backdrop`.
- A rock-lined stream with weirs and a bamboo kakehi on posts.
- A white-blossom sakura, niwaki pines, an arched bridge rail along the window, and upper timber galleries (`hall_shell`).

**Changing halls (g_changing). Source: sheet-ref-ground 01; there is no lookbook painting.**
- Backlit towel and yukata shelves with woven baskets.
- Locker doors with a crest, and noren booths.
- A vanity with round backlit mirrors, stone bowls and cushioned stools.
- A long cushioned bench, and a vase with blossom branches.

**South terrace and cable lift (g_terrace). Sources: 30, 31, 11.**
- The cable lift splits into three rows: `cable_station` (bottom and top), `cable_cabin` and `cable_line` (cables and pylons).
- A bronze culvert grate.

**Cascade terraces (g_cascade). Sources: 01, 30, sheet-ref-ground 03.**
- Stepped scalloped pools with stone lips, and square floor andon on rocks.
- A carved rock portal with guardian-statue niches above the pools (01). This is `rock_carved_portal`, Stretch, because no space file places it.
- The Terrace Path is stone treads with a timber rail and lanterns, which is the `stair` generator.

**East cliff (g_east, g_east_path). Source: 31.**
- The glass oculus, the momiji tree, sea stacks and the tall cape toro (`toro_tall`).
- A rock overhang.

**North cliff ledge and suites (g_north_ledge, suite_*). Sources: 21, 32, sheet-ref-cliff-cavern 01.**
- The trickle basins and the Cliff Stair zigzag.
- The suite: a futon on tatami, a hanging scroll, a vase, a tansu chest, andon, a zabuton, and a tea tray with an iron tetsubin.
- The stone tub with a hinoki bucket and towel, the bamboo spout, a slat privacy fence, and tall conifers on the cliff.

**B1 lobby (b1_lobby). Sources: ref-b1-lobby, ref-spiral-stair.**
- A round bronze drum with kumiko glazing, double doors and a level plaque, plus a separate glass-and-bronze car. This is why `lift_core` splits into `lift_drum` and `lift_car`.
- A curved bronze-capped rail with cylindrical bonbori lanterns.
- Stepping stones in teal water.

**Mist corridors and koi junction (b1_cor_*, b1_junction_w). Sources: 05, 33.**
- Shoji bays with sill plants, a bonsai in a hinoki planter box, and ferns in the rock (`groundcover`).
- Ankle niche lanterns, square andon, polished stepping stones and wall trickle threads.
- The koi pond. The lookbook names black and gold koi, which gives `koi_fish`, and a junction bell.

**Obsidian Mirror (b1_mirror). Sources: 15, 10.**
- A glowworm dome with hanging threads and two engawa pavilions.
- A pale-lit niwaki and a low rock rim.
- A far arch with a falls glimpse.
- Map 10 shows black monoliths standing in the pool. That is an open question.

**Steam grotto (b1_grotto). Source: 16.**
- The 火山湯 sign tower, temperature boards on the arch lintels, and a lava-glass panel.
- Hinoki buckets with a ladle and bowl, a bucket stack and a towel shelf.
- A slatted timber fence, stone slab benches and light shafts.

**Glacier plunge (b1_glacier). Source: 17.**
- An ice wall and a separate icicle curtain (`icicle_cluster`), and a faceted obsidian monolith.
- The warming hut, stone steps with a bronze handrail, and floor lanterns.

**Treatment rooms (b1_treatment). Source: sheet-ref-ground 02.**
- Rooms with a massage bed and a hanging scroll.
- A courtyard with a niwaki, moss, ferns and a water rill.

**Slide launch and outfall (b1_slide_top, b1_outfall). Sources: 13, 33, 25.**
- The tube with bronze ring clamps and vertical bronze columns.
- The launch gate, the spill weir and the J2 shaft.

**B2 core and ramen counter (b2_core). Sources: 09, 07, 34, sheet-mod-kawagiri.**
- The giant red ラーメン chochin and the hanging paper menu tags.
- The black noren with the 火山湯 crest.
- Bowl stacks and chopstick pots, which go into `tableware`.
- Red-cushioned bar stools, a lit floor sign box, and the magenta/cyan neon.
- Open kitchen fire, and header tanks with copper hoops.

**Kawagiri (b2_kawagiri). Sources: 06, 07, 08, sheet-mod-kawagiri, sheet-ref-cliff-cavern 03.**
- Pods on cross-braced piers standing on cut-stone footings (`pier_trestle`).
- Water curtains, red crest chochin, and neon 食事処, 火山湯 and 川の宴.
- A two-storey timber hall carrying the 川霧 board (06 left). It is a `facade_timber` variant.
- A small vermilion torii in the distance (`torii_small` variant) and a magenta-lit sakura.
- Concept 08 adds the arched aqueduct with its sluice and a hexagonal-lattice table andon, plus a ramen bowl, a lidded jar, a soy dish, a tea cup, a side tray and a crest napkin.
- 07 section A-A shows armchairs and the pod sheet shows floor cushions. The owner chose a mix by pod (see "Owner decisions").

**Boat landing, boardwalk, river and falls head (b2_boat, b2_boardwalk, b2_river, b2_falls_head). Sources: 06, 29, 34.**
- The plank boat with a pole lantern, a pontoon (a `boardwalk` style) and bollards with rope.
- Midstream rocks, the inflow slot and the 12 m lip.

**Thunder Curtain and gallery (b3_falls, b3_falls_gallery). Sources: 19, sheet-ref-deep 01.**
- A robing pavilion, bonsai, massage spouts in arched niches, and seat steps.
- The gallery's piers are real basalt piers, so they become `arcade_pier`. The space file had used `obsidian_monolith` as a stand-in.

**Rimstone terraces (b3_rimstone). Source: 18.**
- White scalloped trays, floor lanterns on the rims, and pavilions on both sides.
- Pines on rock islands.

**Lazy river (b3_lazy). Source: 12.**
- A ribbed tube with amber cracks and glowworms.
- Woven rings, some with cushions.
- Square and hexagonal floating lanterns with a crest.
- A two-tier pagoda pavilion on the island (`pavilion_tower`, Stretch because it is not placed), an arched bridge, and side falls from the tube walls.

**Geyser plaza (b3_geyser). Sources: 14, sheet-mod-water 1.**
- Carved seigaiha seat blocks with an under-light strip.
- The vent mound, a multi-jet display, and stalactites.

**Slide foot and shore (b3_slide_foot, b3_shore). Sources: 13, 20.**
- The tube outlet, the lava window, Lava Stair balconies (`spiral_stair` style 2) and the sea torii.

**Wave grotto (b3_wave). Source: 20.**
- Loungers with mattresses and rolled towels.
- Side tables with an iron kettle.
- The lounge pavilion, a stalactite-fringed sea arch, sea stacks, the moon and breakers.

**B3 cavern walls. Sources: 13, 14, 18, 19, 20, 23, 29.**
- Every view shows multi-storey lit timber buildings hung on the cavern walls, but no space file places any. They are now `cliff_lodge_b3` (Must, owner-approved).

**B4 (b4_lobby, b4_tunnel, b4_chamber). Sources: 23, 36, sheet-ref-deep 03.**
- Bronze-framed glass bays with proud mullions, and slatted hinoki benches.
- A railing at the glass, ceiling beams (`hall_shell` style), radial boards, and the brass gauge.

**Summit (s_*). Sources: 11, 30, 24, 25.**
- The infinity lip with rock islands and pines, and the egg gantry with bell-shaped bamboo baskets.
- The moon pavilion and the summit toro and stele.
- 11 shows a timber lodge with a lava-glass window on the crater rim. It is now `summit_lodge` (Should, owner-approved).

## Merges and splits

**Merged** (one generator, the variants are parameters):
- `chochin`: round logo, tall cylinder, red crest, giant ラーメン, long-cord chain, and the porch cluster rig
- `lantern_post`: box head, bonbori and boat pole
- `lantern_floor`: includes the small table andon
- `railing`: 5 styles; the suite privacy fence goes to `slat_screen`
- `stair`: straight, switchback, cliff, pool entry, ladder and cantilever. The Terrace Path and the Cliff Stair are runs of it.
- `spiral_stair`: the drum Spiral Stair and the Lava Stair
- `bench`: slatted, slab, cushioned, seat-step and niche
- `pool_shell`: covers `mist_pool_corridor` and `splash_pool`
- `portal_arch`: basalt, timber gate and bronze frame
- `timber_passage`: absorbs `genkan_porch`
- `rock_opening_glazed`: `slot_window` and `rock_window`
- `signboard_kanji`: wall, standing, level board and gold lintel
- `ice_formation`: includes the frost patches
- `cascade_pool`: the upper terraces reuse it (listed separately only because they ship later)
- `boardwalk`: includes the pontoon
- `lava_window`: 5 sizes
- `magma_glass_wall`: absorbs the B4 `beam_pier` bronze mullions

**Split**, because each part has its own identifying features or its own animation:
- `pine_bonsai` → `pine_niwaki` (ground-planted) and `bonsai_potted`
- `banner` → `banner_hanging` and `noren`
- `sign_kanji` → `signboard_kanji`, `board_small_hanging` (temperatures, T1-T12), `sign_tower_lit`, `menu_tags` and `stele_stone`
- `lift_core` → `lift_drum` (static, baked) and `lift_car` (rigid, probe-lit)
- `cable_car` → `cable_station`, `cable_cabin` and `cable_line`
- `stalactite_cluster` → `icicle_cluster` (ice, drips)
- `egg_baskets` → the gantry (`egg_baskets`) and `egg_basket` (moving)
- `bench_stone` used as stools, low tables and the carved geyser seats → `stool`, `table_low` and `seat_block_carved`
- `steam_bench`/`towel_basket` bucket uses → `oke_bucket`; real baskets → `basket_woven`
- `obsidian_monolith` used as gallery piers → `arcade_pier`
- `suite_module` futon cases → `futon_bed`
- `beam_pier` → `pier_trestle`

**New component generators** that other generators call, with no placements of their own: `roof_tiled` and `shoji_panel`.

**FX rows owned by the runtime** are not modelled: `fx_falls_sheet`, `fx_water_curtain`, `fx_spray`, `fx_mist`, `fx_steam`, `fx_geyser_jet`, `fx_water_surface`, `fx_river`, `fx_waves`, `fx_drips`, `fx_light_shaft`, `fx_cloud_sea` and `fx_petals`.

`light_emitters` is listed only so that every marker id (uplights, glows) is covered. It has no geometry.

**Coverage check.** Every id in `3d/inventory.csv` and `3d/assets.json` appears in some row's `existing_ids`. The check is scripted, and none are uncovered.

## Animation summary

Counts give the first type listed in a row; the number in brackets includes rows where the type appears as a secondary one.
- **none**: 78.
- **shader**: 34 (37). Lantern and neon flicker, lava flow, glowworm twinkle, crack pulse, water sheets on the steps, lips and rims, heat shimmer, window glow (lodges included).
- **vertex**: 13 (15). Noren, banners and nobori, menu tags, scrolls, sakura, pine, momiji, conifers, shrubs, ferns, the koi wiggle, rope.
- **rigid**: 15 (16). Lift car, cable cabin and bull wheel, boat, pontoon, float rings, floating lanterns, koi paths, the chochin pendulum, bell, sluice, egg basket, gauge needle, slide rider, tea-box lift, figures drifting in rings.
- **sim-driven (runtime)**: 17 (18). All fx_* rows except the light shafts, plus the emitters on the pod curtains, fumaroles, the kitchen, massage spouts, the geyser vents, icicle drips and wall trickles.
- **skinned**: 8. These are `guest_figure`, `staff_figure`, `figure_rig` and the 5 `figure_anim_*` cycles. Nothing else is skinned; slide riders and koi are rigid (plus vertex).

## New materials the list needs (proposed for the library)

The library has 32 ids. Rows that need surfaces it lacks use a `NEW:` prefix:
- `NEW:foliage_pine`, `NEW:foliage_fern`, `NEW:bark`, `NEW:blossom`, `NEW:maple_leaf`, `NEW:moss`
- `NEW:linen` (yukata, towels, futon, mattresses)
- `NEW:ceramic` (tableware, vases, wash bowls)
- `NEW:glass_clear` (the slide tube's clear glass, if `lava_glass` is tinted)
- `NEW:gravel` (raked gravel)
- `NEW:koi`
- `NEW:glowworm` (emissive point sprite)
- `NEW:sky` (moon, stars, cloud sea)
- `NEW:skin` and `NEW:hair` (figures)

The inventory also names `hinoki_old`, `paving_worn`, `neon`, `waterfall_sheet`, `glowworm`, `bark`, `foliage` and `blossom`, which are not in `materials.json`. I mapped them to `hinoki`, `paving`, `neon_tube` and `waterfall`, and the rest to the NEW ids above.

## Open questions still pending

These were not covered by the owner's round-1 answers:
1. **Obsidian monoliths in the Mirror pool** (map 10). Add, or keep the pool clear for the reflection?
2. **Red outside Kawagiri.** Red nobori (map 10) and a vermilion torii (06). Allow them?
3. **Carved rock portal with guardian niches** above the cascade pools (01). Currently Stretch.
4. **Two-storey Kawagiri hall** with the 川霧 board (06). It is a `facade_timber` variant; place it?
5. **The far snow-capped cone** (01). Keep or drop?
6. **Lookbook extras:** ash mud bath, lantern release, tea-box lift, and the shops on map 10.
7. **Animated koi.**

## Concept-art batch sheets

Each sheet is one Codex image showing front and side views with a scale bar, in the style of `refs/gen/sheet-mod-lights.png`. Assets already drawn well on an existing `sheet-mod-*` are marked **covered** and not re-batched. Runtime FX rows get no sheet.

### Covered by existing sheets (not re-batched)

- `refs/gen/sheet-mod-arrival.png`: torii_basalt, chozubachi, slipper_cubbies, reception_counter, bridge_arched, railing
- `refs/gen/sheet-mod-kawagiri.png`: kawagiri_pod, kawagiri_sign_gate, aqueduct, ramen_counter, boat, header_tank
- `refs/gen/sheet-mod-lights.png`: lantern_floor, chochin, lantern_stone, lantern_post, lantern_niche, signboard_kanji, noren
- `refs/gen/sheet-mod-nature.png`: pine_niwaki, sakura_small, momiji_small, rock_cluster, boulder_rim, stalactite_cluster, sea_stack
- `refs/gen/sheet-mod-pavilions.png`: pavilion_engawa, treatment_room, moon_pavilion, shoji_wall_bay, portal_arch
- `refs/gen/sheet-mod-water.png`: geyser_vent, seat_block_carved, rimstone_terrace, spill_lip, koi_pond, stone_tub, massage_spout

Three covered assets have only one style drawn: `railing` (timber lattice only), `chochin` (round logo only) and `lantern_post` (box head only). `lantern_floor` also lacks its table-andon variant. These extra variants get variant panels on S01 and S04 below, not a full re-batch.

### Proposed new sheets (about 6 assets each)

Listed as `sheet id: [asset ids]`, with the input images each Codex prompt should get. Pass `refs/gen/sheet-mod-lights.png` as the style and layout anchor for every sheet.

**S01 sheet-mod-stairs** (Must): [stair, stair_cascade, spiral_stair, parapet_stone, bridge_slab] + variant panel: railing styles bronze_handrail / curved_cap / ring (sheet-mod-arrival shows timber_lattice only)
  - inputs: `refs/gen/ref-mist-steps.png`, `refs/gen/ref-spiral-stair.png`, `refs/gen/sheet-ref-ground.png`, `refs/gen/sheet-ref-cliff-cavern.png`, `lookbook/img/17-glacier-plunge.jpg`, `lookbook/img/31-plan-ground.jpg`

**S02 sheet-mod-decks** (Must): [boardwalk, deck_slatted, pier_trestle, timber_passage, slat_screen, arcade_pier]
  - inputs: `lookbook/img/06-kawagiri-restaurant.jpg`, `lookbook/img/07-restaurant-plan.jpg`, `lookbook/img/34-plan-b2-river.jpg`, `lookbook/img/16-steam-grotto.jpg`, `lookbook/img/19-thunder-curtain.jpg`, `refs/gen/sheet-mod-kawagiri.png`

**S03 sheet-mod-timber-kit** (Must/Should): [roof_tiled, shoji_panel, facade_timber, cliff_lodge_b3, summit_lodge, rock_opening_glazed]
  - inputs: `refs/gen/sheet-mod-pavilions.png`, `lookbook/img/04-arrival-gate.jpg`, `lookbook/img/05-mist-corridor.jpg`, `lookbook/img/13-magma-glass-slide.jpg`, `refs/gen/sheet-tex-wood.png`, `refs/gen/sheet-tex-stone.png`

**S04 sheet-mod-lights-2** (Must): [toro_tall, sign_tower_lit, lantern_float] + variant panels: chochin (tall cylinder, red crest, red ラーメン giant), lantern_post (bonbori head, boat pole), lantern_floor (table andon)
  - inputs: `refs/gen/sheet-mod-lights.png`, `lookbook/img/04-arrival-gate.jpg`, `lookbook/img/09-neon-ramen-counter.jpg`, `lookbook/img/12-lava-tube-lazy-river.jpg`, `lookbook/img/16-steam-grotto.jpg`, `lookbook/img/08-table-aqueduct.jpg`, `refs/gen/ref-spiral-stair.png`

**S05 sheet-people** (Must/Stretch): [guest_figure, staff_figure, slide_rider] front and side views at true scale (1 m bar, all figures on one ground line): guests in yukata linen/indigo/near-black and bathers (adult woman, adult man, elder, child) in walking, standing, soaking, seated and floating poses; staff server, attendant, chef; slide rider pose
  - inputs: `lookbook/img/04-arrival-gate.jpg`, `lookbook/img/05-mist-corridor.jpg`, `lookbook/img/09-neon-ramen-counter.jpg`, `lookbook/img/14-geyser-plaza.jpg`, `lookbook/img/15-obsidian-mirror.jpg`, `lookbook/img/22-brand-board.jpg`, `refs/gen/sheet-ref-ground.png`

**S06 sheet-mod-lift-cable** (Must): [lift_drum, lift_car, cable_station, cable_cabin, cable_line, slide_launch_gate]
  - inputs: `refs/gen/ref-b1-lobby.png`, `refs/gen/ref-spiral-stair.png`, `refs/gen/sheet-ref-cliff-cavern.png`, `lookbook/img/30-plan-summit.jpg`, `lookbook/img/31-plan-ground.jpg`, `lookbook/img/13-magma-glass-slide.jpg`

**S07 sheet-mod-lava-glass** (Must/Should): [lava_window, lava_backdrop, slide_tube, lava_tube, lava_crack, magma_glass_wall]
  - inputs: `lookbook/img/04-arrival-gate.jpg`, `lookbook/img/13-magma-glass-slide.jpg`, `lookbook/img/16-steam-grotto.jpg`, `lookbook/img/12-lava-tube-lazy-river.jpg`, `lookbook/img/23-descent-v2.jpg`, `refs/gen/sheet-ref-deep.png`, `refs/gen/mat-lava-glass.png`

**S08 sheet-mod-water-2** (Must): [pool_shell, stream_channel, plunge_basin, falls_lip_rock, cascade_pool, wall_trickle]
  - inputs: `refs/gen/sheet-mod-water.png`, `lookbook/img/01-hero-exterior.jpg`, `lookbook/img/04-arrival-gate.jpg`, `lookbook/img/05-mist-corridor.jpg`, `lookbook/img/19-thunder-curtain.jpg`, `lookbook/img/32-suites-cliff.jpg`

**S09 sheet-mod-water-3** (Must/Should): [mirror_pool, river_channel, beach_terrain, fumarole_vent, caldera_rim, cascade_terrace_upper]
  - inputs: `lookbook/img/15-obsidian-mirror.jpg`, `lookbook/img/06-kawagiri-restaurant.jpg`, `lookbook/img/29-river-section.jpg`, `lookbook/img/20-wave-grotto.jpg`, `lookbook/img/16-steam-grotto.jpg`, `lookbook/img/11-caldera-crown.jpg`, `lookbook/img/30-plan-summit.jpg`

**S10 sheet-mod-rock-ice** (Must): [rock_overhang, obsidian_monolith, ice_formation, icicle_cluster]
  - inputs: `lookbook/img/05-mist-corridor.jpg`, `lookbook/img/17-glacier-plunge.jpg`, `lookbook/img/20-wave-grotto.jpg`, `lookbook/img/01-hero-exterior.jpg`, `refs/gen/sheet-tex-rock.png`, `refs/gen/mat-glacier-ice.png`, `refs/gen/mat-obsidian.png`

**S11 sheet-mod-changing** (Must): [yukata_shelves, locker_bank, changing_booth_row, vanity_counter, stool, bench]
  - inputs: `refs/gen/sheet-ref-ground.png`, `lookbook/img/04-arrival-gate.jpg`, `lookbook/img/09-neon-ramen-counter.jpg`, `lookbook/img/16-steam-grotto.jpg`, `refs/gen/sheet-ref-deep.png`, `lookbook/img/22-brand-board.jpg`

**S12 sheet-mod-bath-props** (Must/Stretch): [oke_bucket, towel_folded, kakehi_spout, board_small_hanging, stepping_stone, basket_woven]
  - inputs: `lookbook/img/16-steam-grotto.jpg`, `lookbook/img/22-brand-board.jpg`, `lookbook/img/21-private-suite.jpg`, `lookbook/img/05-mist-corridor.jpg`, `refs/gen/ref-b1-lobby.png`, `refs/gen/sheet-ref-ground.png`

**S13 sheet-mod-grotto-garden** (Must/Stretch): [steam_room, tsuboniwa, junction_bell, koi_fish, hanging_scroll, ikebana_vase]
  - inputs: `lookbook/img/16-steam-grotto.jpg`, `refs/gen/sheet-ref-ground.png`, `lookbook/img/05-mist-corridor.jpg`, `refs/gen/sheet-mod-water.png`, `lookbook/img/21-private-suite.jpg`

**S14 sheet-mod-kawagiri-2** (Must): [kitchen_block, neon_sign, menu_tags, tableware, table_low, chair_dining]
  - inputs: `lookbook/img/06-kawagiri-restaurant.jpg`, `lookbook/img/07-restaurant-plan.jpg`, `lookbook/img/08-table-aqueduct.jpg`, `lookbook/img/09-neon-ramen-counter.jpg`, `refs/gen/sheet-mod-kawagiri.png`

**S15 sheet-mod-soft-props** (Must/Should): [zabuton_cushion, mooring_post, float_ring, lounger, tea_set, sake_counter]
  - inputs: `lookbook/img/12-lava-tube-lazy-river.jpg`, `lookbook/img/20-wave-grotto.jpg`, `lookbook/img/21-private-suite.jpg`, `lookbook/img/22-brand-board.jpg`, `refs/gen/sheet-mod-kawagiri.png`, `lookbook/img/30-plan-summit.jpg`

**S16 sheet-mod-nature-2** (Must/Should): [bonsai_potted, groundcover, glowworm_ceiling, moon_sky, conifer_tall, shrub_clump]
  - inputs: `lookbook/img/05-mist-corridor.jpg`, `lookbook/img/12-lava-tube-lazy-river.jpg`, `lookbook/img/15-obsidian-mirror.jpg`, `lookbook/img/20-wave-grotto.jpg`, `lookbook/img/21-private-suite.jpg`, `lookbook/img/32-suites-cliff.jpg`, `refs/gen/sheet-mod-nature.png`

**S17 sheet-mod-landmarks** (Must/Should): [torii_small, stele_stone, banner_hanging, glass_oculus, culvert_grate, egg_baskets]
  - inputs: `lookbook/img/06-kawagiri-restaurant.jpg`, `lookbook/img/20-wave-grotto.jpg`, `lookbook/img/04-arrival-gate.jpg`, `lookbook/img/31-plan-ground.jpg`, `lookbook/img/30-plan-summit.jpg`, `lookbook/img/24-isometric-cutaway.jpg`, `lookbook/img/25-water-journey.jpg`

**S18 sheet-mod-suite-b4** (Should): [suite_module, futon_bed, tansu_chest, egg_basket, geothermal_gauge]
  - inputs: `lookbook/img/21-private-suite.jpg`, `lookbook/img/32-suites-cliff.jpg`, `refs/gen/sheet-ref-cliff-cavern.png`, `lookbook/img/30-plan-summit.jpg`, `lookbook/img/36-plan-b4-magma.jpg`

**S19 sheet-mod-stretch** (Stretch): [pavilion_tower, rock_carved_portal, nobori_flag, tea_box_lift, ash_mud_pit]
  - inputs: `lookbook/img/12-lava-tube-lazy-river.jpg`, `lookbook/img/13-magma-glass-slide.jpg`, `lookbook/img/01-hero-exterior.jpg`, `lookbook/img/10-waterpark-map.jpg`, `lookbook/img/11-caldera-crown.jpg`, `lookbook/img/04-arrival-gate.jpg`

Totals:
- 19 new sheets carrying 103 assets.
- 38 assets covered by the 6 existing sheets.
- No sheet needed for:
  - 14 runtime FX/marker rows (fx_cloud_sea, fx_drips, fx_falls_sheet, fx_geyser_jet, fx_light_shaft, fx_mist, fx_petals, fx_river, fx_spray, fx_steam, fx_water_curtain, fx_water_surface, fx_waves, light_emitters)
  - 4 place-model rows (cave_shell, floor_surface, hall_shell, terrain_exterior)
  - 6 rig/animation rows (figure_anim_float, figure_anim_idle, figure_anim_sit, figure_anim_soak, figure_anim_walk, figure_rig)

Suggested order: run S01-S17 first, because together they carry every Must asset that has no sheet yet (a few Should and Stretch assets ride along). `sheet-people` is S05. S18 covers the Should suites and B4 props, and S19 is Stretch. Each sheet should show front and side views, a 1 m scale bar and the dims from `dims_m`. For generators with styles (stair, railing, bench, chochin), draw one panel per style. On the people sheet, put every figure on one ground line at true scale.

## Proposed changes to shared files (not written; for the lead)

1. **`3d/inventory.csv`**: replace the inventory rows with one row per generator in this list.
   - Map the columns: `id`, `name`, `space` = locations, `concept_images` = concept_refs, `detail_tier`, `identifying_features`, `lighting`, `materials`, `tri_budget_lod0-3` = tri_budget, `status` = planned, `owner` = lead, and `notes`.
   - Keep the old ids as aliases until `placements.json` is regenerated. Each row's `existing_ids` column is the alias map.
   - The place-model rows (`cave_shell`, `terrain_exterior`, `hall_shell`, `floor_surface`) map to the place models.
2. **`3d/assets.json`**: add proxies for the new ids. Exact w/d/h are in `.scratch/asset_list/proposed_assets_patch.json`. Snap and light settings to copy from the parent id:
   - `chochin` ← `lantern_hanging`
   - `pine_niwaki` and `bonsai_potted` ← `pine_bonsai`
   - `banner_hanging` and `noren` ← `banner`
   - `signboard_kanji`, `board_small_hanging`, `sign_tower_lit`, `menu_tags` and `stele_stone` ← `sign_kanji`
   - `bench`, `stool`, `table_low` and `seat_block_carved` ← `bench_stone`
   - `lift_drum` (structural) and `lift_car` (moving) ← `lift_core`
   - `cable_station` and `cable_cabin` ← `cable_car`
   - `icicle_cluster` ← `stalactite_cluster`
   - `arcade_pier` ← `obsidian_monolith`
   - `pier_trestle` ← `beam_pier`
   - `toro_tall` ← `lantern_stone` with hero_glow
   - `staff_figure` ← `guest_figure`, which should get `moving: true` so it is lit by probes and not baked
   - `cliff_lodge_b3` and `summit_lodge`: `host: true`, `hero_glow` off
3. **Space files** (proposals only; the lead owns `3d/spaces/`):
   - **Stepping stones.** `stepping_stone` has 0 placements, although concept 05, ref-b1-lobby and the lookbook make it the signature of every B1 corridor. Proposed dressing rule for `b1_cor_mirror`, `b1_cor_east`, `b1_cor_west`, `b1_cor_north`, `b1_cor_south`, `b1_junction_w` and `b1_lobby`:
     `{"asset": "stepping_stone", "along": "spine", "side": "both", "offset": 0.35, "spacing": [0.55, 0.7], "jitter": 0.08, "snap": "water_edge", "top_z": [-20.06, -20.03], "variants": [0,1,2,3,4,5,6,7], "why": "Two staggered rows of polished stones just under the surface (concept 05)."}`
   - **`b2_kawagiri` seating (owner: mixed by pod).**
     - T4 chef_table: `chair_dining` armchair x 4 with a dining-height `table_low`.
     - T5, T6 and T10-T12: `chair_dining` side chair x 4 with a dining-height `table_low`.
     - T1-T3 and T7-T9: `zabuton_cushion` x 4 with a low `table_low` (h 0.35).
   - **`b3_cavern`.** Add 6-10 `cliff_lodge_b3` anchors on the vault walls: behind the rimstone terraces (18), above the falls basin west wall (19), the geyser side walls (14), the slide cave (13), and the beach lounge wing (20). Each `why` should cite its concept. They are backdrop only, off the walk graph.
   - **`s_pool`.** Add one `summit_lodge` anchor on the north crater rock behind the pool (11), facing south over the water.
   - **People.** Each space gets a `people` rule: count 0-12 animated `guest_figure`/`staff_figure`, with the pose set drawn from the space's use (soak in pools, float in b1_mirror and b3_lazy, sit at counters and benches, walk on the spine). Everything beyond the zone's animated budget becomes impostors.
   - **Rename variant strings.** Repoint them to the split ids:
     - `bench_stone`/`bar_stool` → `stool`
     - `bench_stone`/`low_table` → `table_low`
     - `sign_kanji` temperature boards and pod numbers → `board_small_hanging`
     - `sign_kanji`/`menu_board` → `menu_tags`
     - `banner`/`noren*` → `noren`
     - `obsidian_monolith` in `b3_falls_gallery` → `arcade_pier`
     - `beam_pier`/`bronze_mullion` → part of `magma_glass_wall`
     - `steam_bench`/`bucket_only` → `oke_bucket`
     - the futon anchor in `suite_template` → `futon_bed`
     - `stalactite_cluster`/`icicles` → `icicle_cluster`
     - `lantern_stone`/`misaki_toro` and `summit_toro` → `toro_tall`
4. **`3d/materials.json`**: add the NEW: materials listed above (the lead or the material-library agent owns this file).
