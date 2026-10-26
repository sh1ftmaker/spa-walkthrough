# Space files (`3d/spaces/<id>.json`)

One file per space in `3d/layout.json` (same `id`). It says what the space is **for**; `tools/assembly/place.py` turns
its rules into `placements.json`. Never write raw clutter coordinates: write rules. Coordinates are layout metres
(x east, y north, z up). Bearings: `facing_deg` is a compass bearing of the asset's forward (+Y) axis: 0 = north,
90 = east, 180 = south, 270 = west. Eye height is 1.6 m above the floor.

```jsonc
{
  "id": "g_arrival", "name": "...", "level": "ground",
  "purpose": "one sentence: why a guest is here and what they feel",
  "floor_z": 0.0, "ceiling_z": 16.0,
  "ceiling_profile": {"type": "vault|dome|flat|cave|tube|open", "min_z": 9.0, "max_z": 16.0, "note": "..."},
  "footprint": [[x, y], ...],               // copied from layout.json (do not change here)
  "portals": [{"id": "p_gate_hall", "to": "g_gate", "at": [x, y], "width": 6.0, "height": 4.5}],
  "spine": [[x, y, z], ...],                 // the walking line through the space, portal to portal
  "hero": {"asset": "lava_window", "at": [x, y, z], "facing_deg": 180, "dims": {"w": 34, "h": 12},
           "why": "what makes it the focal point"},
  "anchored": [                              // hand-placed secondaries (bridges, railings, pods, counters)
    {"id": "bridge_1", "asset": "bridge_arched", "at": [x, y, z], "facing_deg": 90, "dims": {...}, "why": "..."}],
  "water": [{"id": "w_hall_stream", "kind": "flow|still|fall", "z": -0.35, "rim_z": 0.0,
             "path": [[x, y], ...], "width": 2.5}],
  "sightlines": [{"from": "p_gate_hall", "see": "lava glow on the left, torii framed behind",
                  "target": [x, y, z]}],
  "cameras": {
    "entry":   {"pos": [x, y, z], "target": [x, y, z], "fov_v": 60},
    "reveal":  {"pos": [x, y, z], "target": [x, y, z], "fov_v": 60},
    "concept": {"image": "lookbook/img/04-arrival-gate.jpg", "pos": [x, y, z], "target": [x, y, z], "fov_v": 55,
                "match": "framing and mood to match"}},
  "lights": [                                // placed BEFORE clutter; lanterns are real light sources in the bake
    {"asset": "lantern_floor", "along": "spine", "side": "both", "spacing": [5, 7], "offset": 1.8, "face": "path"}],
  "dressing": [                              // rules only; verbs: at, along, ring, scatter; modifiers: avoid, snap, face, embed
    {"asset": "rock_cluster", "scatter": "edge_band", "band": [0.3, 2.5], "density": 0.12, "avoid": ["nav", "portals"]}],
  "mood": {"key": "lava window", "palette": "amber lantern + orange lava, teal water", "mist": "low over the stream"},
  "waivers": [{"check": "clearance", "where": "...", "reason": "..."}]
}
```

Rule verbs:
- `at`: explicit point(s) — only for anchored things with a stated reason.
- `along`: along a polyline (`"spine"`, `"water:<id>"`, `"wall"`, or explicit points), `spacing` [min,max] m, `offset` m to the side, `side` left|right|both, `jitter` m.
- `ring`: around a point/feature at `radius`, `count` or `spacing`.
- `scatter`: `"edge_band"` (band [min,max] m from the walls), `"area"` (polygon), `density` per m², `min_dist`.
Modifiers: `avoid` ["nav","portals","water","hero", radius], `snap` ground|wall|ceiling|water_edge, `face` path|hero|wall|out|<bearing>, `embed` m (allowed sink), `scale` [min,max], `variants` [seeds], `allow_overlap` [asset ids].
