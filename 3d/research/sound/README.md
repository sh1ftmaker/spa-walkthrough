# Kazan-yu: sound and ambience research

How the spa should sound, how to do it in a phone browser, and a working prototype that proves it.

- **Live demo:** https://terminal.sels.tech/lp/8742/3d/research/sound/demo/ (tap to start; headphones recommended; `?bank=bake` synthesises everything on the device instead of loading the 1.9 MB pre-rendered bank)
- **Offline renders with spectrograms:** https://terminal.sels.tech/lp/8742/3d/research/sound/previews/
- Everything you hear is **self-made procedural audio**. No third-party recording is used anywhere.

> **Round 3 (26 Oct): CC0 anchor recordings under Thunder Curtain, the B2 river and the sea-cave surf. See section 12 and `CREDITS.md`.**
>
> **Round 2 (owner feedback, 26 Oct): "the bubbling and trickling sounds are far too prevalent; more rushing and waterfall thunder".** Section 11 has the new research, the CC0 references, the rebuilt water and the before/after numbers. It supersedes sections 3, 4.2 and 9 wherever they disagree.

## 1. Summary

1. **Water can be synthesised convincingly on a phone, in the right ways.** Babbling streams, tinkling rills, drips, bubbling pools, water curtains and big waterfalls all come out of two models. One is the Minnaert bubble with van den Doel's rising-pitch damping. The other is shaped noise. Wind with gusts, steam, lava churn, bells, wind bells and a geyser eruption work too. Close-up crowd murmur still sounds synthetic and should be replaced by a CC0 recording when one is found. Surf is passable, but a CC0 recording would beat it.
2. **Do the synthesis offline and only play buffers at runtime.** The same generator code renders 18 seamless loops and 37 one-shot variants. After round 2 they are 24 loops and 37 one-shot variants, shipped as **2.22 MB of Ogg Opus**, with a 3.24 MB AAC fallback for iOS before 18.4. They load in 0.6 s on desktop. Baking them on the device works too (5.5 s on desktop Chrome, roughly 15–25 s on a phone), which is why it is the fallback and not the default.
3. **The runtime is cheap.** After round 2, 16 real voices (wide sources read their loop twice), one convolution reverb, a compressor and a limiter measure **4.4–6.3 % of one desktop core** (Chrome 155, Ryzen 9 9950X). On a mid-range phone that is an estimated 15–35 % of the audio thread. The per-update JavaScript (portal graph, 87 emitters, voice selection) costs **0.1–0.4 ms per 50 ms tick**.
4. **Occlusion comes from the portal graph, not raycasts.** Spaces are grouped into acoustic rooms. Each update runs a Dijkstra over the layout's 76 portals, so you hear the river at Kawagiri up the Mist Steps, from the direction of the stair mouth, quieter and duller. This is the Wwise "rooms and portals" idea, done in about 60 lines.
5. **The biggest performance trap was found and fixed.** Leaving `setTargetAtTime` automations running on `PannerNode` position and `BiquadFilter` frequency kept Chrome on its per-sample path. That made the same scene cost **9.8 % instead of 3.9 %**. Write positions as plain `.value`, and use finite linear ramps for gains.

## 2. How the place should sound (design intent)

The lookbook's organising idea is **one stream, followed downhill**, and the sound should tell that story. The water is the score. It is everywhere, but it is never the same twice: a thread in a basin, a rill under the stepping stones, a sheet over a lip, a fast river, a 17 m curtain, the sea. Each level has a different water voice and a different room. The deepest places are the quietest, except for the mountain itself.

Rules:
- **Loudness follows the water's energy, not the room's importance.** Thunder Curtain and the geyser are the loudest things in the spa, at about −15 LUFS integrated over a walk. The Obsidian Mirror is the quietest place you can stand in, at −37 LUFS. Silence is a feature there and must be protected.
- **Every room has its own acoustic.** Low stone corridors are short and dense (1.3 s). The Mirror dome is long and dark (3.8 s). The Aqua Cavern is huge (5 s). Kawagiri is timber over water (2.6 s river hall). The reverb change is half of what tells you that you walked through a door.
- **Sound leads you.** You hear the next place before you see it: the outfall roar down the dark spur, surf at the end of the shore path, the curtain's roar at the falls head. Portal propagation does this automatically.
- **Human sound is rare and small.** The only people are at Kawagiri and the ramen counter: murmur, bowls, a wok. Quiet hours remove them.

## 3. Sound design, level by level

Levels are integrated loudness over the 25 s walk renders (headphones mode). "Bed" is a non-spatial loop for the space. The other sounds are positioned emitters.

### Ground (0 m): arrival, about −25 LUFS
| Space | What you hear, from where | Changes as you walk |
|---|---|---|
| Approach road | The flank falls on your left (`road_falls`, point at the hero sheet, 14 m drop), a stream under the slab bridge, sea wind bed. | It gets louder as you cross the bridge, then falls behind you. |
| Basalt Gate | The road falls fading behind, wind, steam over the south parapet. | Outdoor spaces are one acoustic room, so there is no occlusion. |
| Cascade pools | The A4 falls sheet into the top pool, the outflow rill. | |
| Arrival hall | Through the gate portal the wind drops away and the hall's 2.4 s stone reverb takes over. The warm stream runs past reception (a line emitter that follows `w_hall_stream`). The **lava window** is a 34 m line emitter: a slow, heaving, muffled churn, with random **blorps** along the glass every 3–10 s. The chōzubachi basin trickles. | The lava is felt more than heard: a low heave that grows as you cross the bridge toward the glass. |
| East terrace, cliff path | Strong gusty wind, surf 70 m below (line at sea level, low-passed), a furin (iron wind bell) that rings in the gusts. | |

### B1 thermal (−20 m): the mist corridors, −28 LUFS (quiet hours −35)
| Space | What you hear | Notes |
|---|---|---|
| Lift lobby | The lobby rill (a line along `w_b1_lobby_rill`) and the spout into the basin. Corridor mist and drips leak in from both mouths. | 1.3 s corridor reverb. |
| Mist corridor to the Mirror | **Wall trickles** (point emitters at each `wall_trickle`), ceiling **drips** into the ankle-deep pool along the spine every 2–7 s. Footsteps are left out (see section 7). | Tinkling and close. Voices would drop here. |
| Koi junction | **The bell**: a small bronze bell, struck when you pass within 4 m (25 s cooldown) and otherwise every 1–2.5 min. Koi plops in the pond. | During quiet hours the bell is the only made sound. |
| Mist corridor west, Mist Steps | The pool slides over the spill lip as a sheet, and the Mist Steps fall away below as a cascade. Steam puffs at the grotto door. | Kawagiri is audible down the steps through the stair portal. |
| Steam Grotto | Five fumarole vents hiss and surge, plus a lava panel. A damped 1.1 s steam-room reverb. | |
| **Obsidian Mirror** | Almost nothing. A very low room tone, a single meltwater drip every 9–26 s with a 3.8 s dark dome tail, and the corridor trickles faint through the arch. | **−37 LUFS.** The silence is the design. Do not add music. |
| Corridor east, Glacier Plunge | Drips get faster and higher toward the glacier, ending in a meltwater curtain. A brighter ice-cave reverb. | |
| Return corridor | The north-branch thread falling into its basin at the elbow. | |
| Outfall | All of B1's water falling 22 m into the shaft. You hear it down the spur before you see it. | |
| Treatment rooms | A dry, hushed, short timber reverb, at room tone only. | |
| Slide top | The lava glass, and water hissing in the glass tube below. | |

### B2 river (−40 m): Kawagiri, −20 LUFS
| Space | What you hear | Notes |
|---|---|---|
| River (one acoustic room with the deck, the boat landing, the boardwalk and the falls head) | **The river** is a 180 m line emitter on the `w_river` centreline: rushing white water with gurgle. Its sound position slides along the polyline (nearest point) as you walk, so it is always "below you". The **river head** cascade sits at J2. The **Thunder Curtain lip** sits at the west end. | Rolloff 0.7 (a line source falls about 3 dB per doubling, not 6). |
| Kawagiri deck | **12 water curtains** (one emitter per `kawagiri_pod`; voice management keeps the nearest 4–6 real), a **murmur** area over the deck, and **bowls** clinking at random pods. Thunder Curtain comes up the falls shaft at about −14 dB. | Phone-speaker mode measures −14.8 LUFS with more compression. |
| Core / ramen counter | Wok sizzle, kitchen vent steam, counter murmur and bowls. The Mist Steps sheet arrives from the stair. Short timber reverb. | Human sounds are muted during quiet hours. |
| Boat landing | Hull lapping. | |

### B3 Aqua Cavern (−70 m): the loud level, −15 to −20 LUFS
| Space | What you hear | Notes |
|---|---|---|
| Falls head, gallery, plunge deck | The **Thunder Curtain**: a 12 m line emitter at mid-height, broadband roar, enveloping within 10 m (diffuse share up to 85 %). Behind the curtain it is all around you. Then the plunge churn and the massage spouts. A structure-borne path (−34 dB, 220 Hz low-pass) lets the roar rumble through the rock into nearby rooms. | **−15 LUFS**, the loudest walk. |
| Rimstone Terraces | 13 tiers as one long cascade line (many small spills), plus the feed runnel. 5 s cavern reverb. | |
| Geyser Plaza | The pool bubbling. Small vents fire every 9–16 s around the island. **The big eruption** (every 20 min in the build, every 75 s in the demo) has a 2.5 s rising gurgle, a whoosh, a 7 s jet roar, and water falling back after 1.7 s (the fall time from 14 m), then a steam tail. | −15 LUFS, short-term max −11.5. It is the event of the level. |
| Lazy River | Slow laps and bloops along the 120 m loop (a closed polyline). 1.8 s tube reverb. | |
| Shore path | A dark tube with the runnel. Surf grows ahead through the beach-step portal. | |
| Wave Grotto | **Surf** is a line emitter along the beach edge with a 9 s wave period (from the `waves` data in the space file): swell, break, foam fizz, backwash. Open water laps. **Wind at the sea mouth** is a line across the mouth. A **furin** on the beach pavilion rings in the gusts (the strike rate follows the wind loop's own gust envelope). 2.8 s sea-cave reverb. | −20 LUFS, short-term max −14 at the breaks. |

### B4 magma (−100 m): the heartbeat, −24 LUFS
| Space | What you hear | Notes |
|---|---|---|
| Lift lobby | The **heartbeat** starts very low: a non-spatial bed at −16 dB. | |
| Tunnel gallery | The heartbeat at −9 dB, plus 1.8 s tube reverb. | |
| Magma chamber | The heartbeat at full level, the 82 m magma glass as a line emitter (deep churn), and slow blorps along the glass. | See below. |

**The heartbeat** follows the lookbook: "the mountain's own rumble, slowed down". It is generated as a seismic rumble, then time-stretched 4× by resampling, which drops it two octaves. A slow double pulse at 22 bpm, a 34 Hz fundamental, is added. Phone speakers stop around 150 Hz, so the pulse carries an explicit harmonic series at 2–5× the fundamental. The ear then infers the missing fundamental. On headphones you feel the fundamental. On a phone speaker you hear the beat.

## 4. Research findings

### 4.1 Web Audio architecture on phones

| Topic | Finding | Decision |
|---|---|---|
| Unlock | Chrome has applied its autoplay policy to Web Audio since M71. A context created before a gesture stays suspended until `resume()` is called after user interaction [Chrome autoplay]. iOS also needs a sound started inside the gesture. | A tap-to-start card. Inside the gesture: create the context, play a 1-sample buffer, then `resume()`. |
| iOS silent switch | Safari's default audio session type is ambient, so the silent switch mutes the page. Setting `navigator.audioSession.type = 'playback'` makes audio play anyway (Safari 16.4+) [W3C Audio Session; MDN AudioSession.type; WebKit bug 237322]. | Set it when the property exists (done in the demo). |
| Background, interruptions | iOS Safari moves the context to `"interrupted"` when you leave the page or lock the screen. Several WebKit bugs report that `resume()` does not always recover [MDN state; WebKit 276016, 273511, 217606]. | Suspend the context on `visibilitychange` (it also saves battery). On return, show "Tap to resume sound" whenever the state is not `running`. |
| Panning | HRTF needs its database loaded and does convolution per voice. The working group made `equalpower` the default for that reason [public-audio 2014; Mozilla bug 1128494]. **Measured:** HRTF on 14 voices adds only 0.4–0.5 % of a core (offline bench), but 3.3 points in the in-page test, which includes the HRTF database load. | Default to equal-power. Offer HRTF as a "headphones" option for the 4–6 loudest voices. One-shots always use equal-power. |
| Distance model | `PannerNode` distance models are inverse, linear and exponential, with `refDistance`, `maxDistance` and `rolloffFactor` [MDN distanceModel]. They cannot express portal path length or line sources. | Panners do **direction only** (`rolloffFactor = 0`, positions written as unit vectors relative to a fixed listener). The engine computes gain itself: `(ref/max(d,ref))^rolloff`, with rolloff 1 for points and 0.7–0.75 for lines and areas. |
| Listener | `AudioListener` AudioParams vary across Safari versions (older Safari only has `setPosition` and `setOrientation`). | Keep the listener at the origin facing −Z. Rotate emitter positions into listener space in JavaScript. In three.js, take x, y, z and heading from the camera each frame instead of using `THREE.AudioListener` and `PositionalAudio`. |
| Automation cost | **Measured trap:** endless `setTargetAtTime` on panner position and filter frequency kept Chrome on its per-sample path: **9.8 % vs 3.9 %** of a core for the same scene, and 16.5 % vs 5.2 % at 24 voices. | Write `.value` directly for positions and filter cutoffs. Use short `linearRampToValueAtTime` ramps (60–300 ms) for gains. Skip changes under 1 %. |
| Occlusion | Raycasts against cave geometry are expensive and noisy. Wwise's rooms-and-portals model routes sound through portals and adds a transmission path through walls when no portal path exists [Audiokinetic rooms & portals]. | Portal-graph Dijkstra each update: path length, summed portal loss (2 dB + width term; open falls shaft 0–4 dB), first portal for direction, low-pass ×0.5 per hop. The loudest emitters also get a `leak_db` structure-borne path (low-passed at 220 Hz). |
| Reverb | `ConvolverNode` with generated IRs: two-band exponential noise, early taps, predelay. **Measured:** one 3–4.5 s stereo IR costs about 1.7 % of a core. | One convolver per preset, created lazily. Only the listener's room preset is fed; it crossfades in 1.5 s and is disconnected after its tail. The cap is 4.5 s, even for the 5 s cavern. A feedback-delay network is the fallback for low-end devices (not needed so far). |
| Simultaneous sources | Rough community figures say low-end phones glitch above 10–15 positional sources [abratabia, unverified]. | **14 real voices** by audibility, with 3 dB hysteresis. Beds (≤2) and one-shots (≤8, gated at −42 dB) come on top. 75 emitters exist; 26–65 are "audible" at any one moment. |
| Codecs | Safari 18.4 added Ogg container support for Opus and Vorbis on macOS, iOS and iPadOS [WebKit 18.4]. Before that, Opus decoding in Web Audio on Safari was inconsistent [WebKit 238546, 226922]. `decodeAudioData` always resamples to the context rate. | Ship Ogg Opus, falling back to AAC `.m4a` when decode fails. After decoding, resample low-band assets back to their bake rate (8–32 kHz) to save memory. |
| Loop seams with lossy codecs | AAC adds encoder priming and padding, and Opus has pre-skip. Either can shift or pad a loop. | Each loop is encoded with **0.25 s of wrapped audio on both sides**. Cutting the loop length anywhere inside the pad is still seamless, so any codec offset under 0.25 s is harmless. |
| Latency | `latencyHint: 'playback'` (bigger buffers, fewer underruns). Measured base 21 ms, output 56–72 ms on desktop. | An ambience doesn't need low latency. |
| Loudness | Phone speakers: no bass below about 150 Hz, small dynamic range. Headphones: full range. | Two output modes. Headphones: high-pass at 28 Hz, gentle compressor (−20 dB, 2.5:1), limiter at −2 dBFS. **Phone speaker:** high-pass at 160 Hz, +4 dB at 2.8 kHz, compressor at −30 dB 4:1, +6 dB makeup. Kawagiri measures −20.2 LUFS in headphones mode and −14.8 in speaker mode. |

### 4.2 Procedural synthesis vs. recordings

The bubble model: f₀ = (1/2πr)·√(3γp₀/ρ), which gives **f₀·r ≈ 3.26 m/s** for air in water at 1 atm [Minnaert 1933, via Moss et al.]. Bubbles from 0.15 mm to 15 cm cover the audible range [Moss et al.]. Each bubble is a damped sine. Its decay is d = 0.043·f₀ + 0.0014·f₀^1.5 /s, and its pitch rises as f(t) = f₀(1 + σt) with σ = ξ·d [van den Doel 2005; ξ ≈ 0.1 for free bubbles, 0.15–0.35 for drop-impact "plinks"]. Bubbles are created as a Poisson process. Radii follow a power law r^−α: α ≈ 2.9 for rain [Pumphrey & Elmore] and 1.5–3.3 for breaking waves [Deane & Stokes], both via Moss et al. van den Doel builds streams, pouring, rain and waves stochastically from this single primitive, in real time [van den Doel 2005]. Farnell's *Designing Sound* teaches fire, running water and bubbles, wind and rain as Pure Data patches built from first principles [Farnell 2010; Pd workshop]. The same approach is used commercially by QMUL's Nemisindo for browser-based procedural effects [QMUL]. In a 2026 listening study, procedural "air" and similar models were rated highly believable in drama and sci-fi scenes, and less so for everyday actions in cartoons [Garcia & Reiss 2026].

| Sound | Method here | Verdict |
|---|---|---|
| Babbling stream, lobby rill | Clustered bubbles (r 0.8–9 mm, rate following a gurgle envelope) + soft wash + spray | **Convincing.** The bubble chirps are the real thing. |
| Tinkling rills, wall trickles, basin spouts | Sparse small bubbles with strong drop chirps, plus fizz | **Convincing**, and the most characterful sound in the set. |
| Drips | Impact click + one strongly rising bubble | **Convincing.** Variety comes from 10 variants × pitch randomisation. |
| Fast river | Brown/pink body + white-water hiss + dense small and large bubble clouds | **Good at a distance.** Up close it is a bit "noise-like". A CC0 white-water recording would add detail. |
| Big falls (Thunder Curtain, inflow) | Broadband noise with 18 Hz impact flutter + a big-bubble cloud | **Good.** Real big falls are noise-like too. |
| Water curtains, sheets, cascades | Band-passed hiss + very dense tiny droplets | **Good.** |
| Lapping (lazy river, pools, hull) | Swell-gated large bubbles + band noise | **OK.** Reads as gentle water. |
| Surf | Per-wave envelope (swell, 0.35 s break, foam fizz, backwash) through a moving low-pass | **Passable.** The break is too regular and the backwash lacks pebble or sand detail. **Replace with a CC0 recording** when available. |
| Wind | One gust envelope drives band-pass noise + low rumble + a Strouhal whistle only in strong gusts [Farnell] | **Good.** The gust envelope is reused to ring the furin. |
| Steam, fumarole | High-passed jet hiss + breathing surges + low chuff | **Good.** |
| Lava behind glass | Low churn with slow heave + muffled crust ticks + "blorp" one-shots | **Good**, and plausible because nobody knows what lava behind glass sounds like. |
| Bells, furin, bowls | Modal synthesis (inharmonic partials, beating pairs, exponential decays) | **Convincing** for the bronze bell and the iron furin. The bowls are fine at a distance. |
| Geyser eruption | Gurgle → whoosh → jet roar → fall-back splatter → steam | **Good.** |
| Restaurant murmur | 22 synthetic talkers (glottal pulse → two moving formants, syllable rhythm, turns) | **Recognisably synthetic up close.** Fine beyond about 15 m and under reverb. **Replace with a CC0 crowd recording.** |
| Wok sizzle | Poisson crackle → band-pass + hiss | Fine. |
| Heartbeat | Slowed rumble + harmonic double pulse | Fine. It is a designed sound by brief. |

### 4.3 Emitter design

Game practice for rivers and coasts is a spline emitter that tracks the listener's nearest point. Examples are BeamNG's Audio Ribbon, which has a quad mode for rivers, and Unity River Modeler, which pools emitters around the camera [BeamNG; 80.lv]. Open-world talks describe systemic ambience placement and region beds [Dying Light 2 GDC 2023; Ghost of Tsushima GDC 2021; Gotham Knights GDC 2023; Hellblade II GDC 2025]. The prototype implements:

- **point**: fountains, vents, spouts, pods, basins. One emitter per anchored instance (12 pods, 5 vents, 3 massage spouts).
- **line**: the nearest point on a polyline, taken from `water:<id>` paths (river, hall stream, runnels, lazy-river loop with `closed`) or explicit points (lava windows, spill lips, the falls lip, the surf line, the sea mouth).
- **area**: the nearest point on a polygon, enveloping inside (geyser pool, sea, the Kawagiri diners).
- **beds**: non-spatial per-space loops (room tone, wind, the heartbeat), crossfading over 2.5 s.
- **one-shots**: `along` a polyline or spine, `area`, `around` a point, `points`, plus triggers `timer` (geyser), `proximity` (junction bell) and `gust` (furin). Each has pitch and gain randomisation and a −42 dB audibility gate.
- **spread**: within `spread_m` of a line or area, up to 85 % of the signal goes to a shared diffuse bus (two short allpass/delay paths to L and R). Standing behind the curtain is then enveloping, not "in the middle of your head".

### 4.4 Asset sourcing and licences

| Source | Licence | Usable here? |
|---|---|---|
| **Self-made (this folder)** | Our own; generated by `demo/js/dsp.js`, no third-party input | **Yes.** Everything shipped is this. |
| Freesound, filtered to CC0 | CC0 per sound. Filter with `license:"Creative Commons 0"` in the API [Freesound API] or the CC0 filter on the site | **Yes, per file.** Record the URL, author and licence of each file in a sources table. Check that a file isn't a re-upload of someone else's material. Candidates to look for: surf on a black-sand or pebble beach, restaurant or izakaya murmur, white-water river close-up. |
| Sonniss GameAudioGDC bundles | Proprietary EULA v2.0 (27 Aug 2026): commercial use, no attribution. But "may not distribute, publish, sub-license or otherwise supply the sound effects as sound effects", AI training is prohibited, and copyright stays with the rights holders [Sonniss licence] | **No.** It is not CC0, and a web build ships the files to every visitor. |
| BBC Sound Effects (RemArc) | Personal, educational and research use only; commercial use needs a purchased licence [press coverage of the RemArc licence] | **No.** |

## 5. Recommended architecture and phone budget

```
camera pose (x, y, z, heading) ──► SoundEngine.update() @ 20 Hz (main thread, ~0.2 ms)
  ├─ listener space = smallest footprint containing (x,y) on the camera's level
  ├─ portal Dijkstra (76 portals) ─► per emitter: path length, portal loss, first portal, hops
  ├─ score 75 emitters ─► keep the 14 loudest as real voices (3 dB hysteresis)
  ├─ beds of the listener's space (≤2) ─ crossfade
  ├─ reverb preset of the listener's room ─ crossfade between ≤2 convolvers
  └─ one-shot scheduler (timer / proximity / gust / random intervals)

voice: BufferSource(loop, random offset, rate 0.96–1.04) → Gain → Lowpass → [Panner (direction) → dry]
                                                                         → [diffuse bus] → [reverb send]
master: dry + diffuse + beds + wet → (speaker HP/EQ) → Compressor → Limiter → destination
```

| Budget item | Target | Measured (desktop Chrome 155, Ryzen 9 9950X) | Phone estimate |
|---|---|---|---|
| Real voices | 14 (12 on low-end) | 14–16 including one-shot overlap | — |
| Audio DSP (16 voices + 1 convolver + compressor + limiter) | < 35 % of the audio thread | round 2: 4.4–6.3 % (equal-power), 5.7 % (HRTF), 3.2 % without reverb, 6.6 % at 24 voices (round 1: 3.2–4.6 % at 14 voices) | 15–35 % (assuming phones are 3–6× slower single-threaded) |
| Engine update (JS) | < 1 ms / 50 ms tick | 0.1–0.4 ms | 0.5–1.5 ms |
| Decoded audio memory | ≤ 48 MB (≤ 20 MB per level when streamed by level) | 45.1 MB for the whole bank (round 1: 36.6 MB) | same |
| Download | ≤ 2.5 MB | 2.22 MB Opus / 3.24 MB AAC (round 1: 1.87 / 2.62 MB) | same |
| Startup | < 1 s after tap | 0.5 s (pre-rendered) / 3.3 s (bake in Chrome) | about 1–2 s / 10–15 s |
| Loudness | quiet −35…−40, typical −20…−28, peak places −15 LUFS-I; true peak ≤ −1 dBTP | −37.0 … −15.2 LUFS-I; true peak ≤ −1.39 dBTP; 0 clipped samples | — |

## 6. Proposed `audio` block for `3d/spaces/<id>.json`

All demo data is in `demo/data/audio_blocks.json`, in exactly this shape. It has 43 spaces filled in, with presets, overrides and rules. The lead can copy each entry into its space file.

```jsonc
"audio": {
  "reverb": "corridor",                     // key into the global reverb_presets table
  "open_to": ["b1_cor_mirror"],             // spaces that share air with this one (no portal loss); see section 10
  "beds": [{ "asset": "roomtone", "gain_db": -2 }],
  "emitters": [
    { "id": "river", "asset": "river", "shape": "line",          // point | line | area
      "from": "water:w_river",                                  // water:<id>[,<id>] | anchored:<id> | anchored_asset:<asset> | hero | spine
      // or "at": [x, y] | "points": [[x, y], ...] | "polygon": [[x, y], ...]
      "z": -42.8, "gain_db": -3, "ref_m": 6, "rolloff": 0.7,     // gain at ref_m; inverse-power falloff beyond
      "spread_m": 7,                                             // within this distance the sound envelops
      "lp_hz": 2500,                                             // optional fixed muffling (grates, glass)
      "leak_db": -34,                                            // optional through-rock path (very loud sources only)
      "closed": false, "send_db": 0, "tags": ["feature"] }       // tags: human | feature | trickle (quiet-hours rules)
  ],
  "oneshots": [
    { "id": "cor_drips", "asset": "drip", "along": "spine", "z": -20, "every_s": [2, 7], "gain_db": -8, "pitch": [0.8, 1.3] },
    { "id": "junction_bell", "asset": "bell", "from": "anchored:bell", "trigger": "proximity", "radius_m": 4, "cooldown_s": 25, "every_s": [60, 150] },
    { "id": "geyser_big", "asset": "geyser_big", "from": "hero", "trigger": "timer", "period_s": 1200, "leak_db": -30 },
    { "id": "pavilion_furin", "asset": "furin", "from": "anchored:beach_pavilion", "trigger": "gust", "rate_hz": 0.9 }
  ]
}
```
Global (proposed `3d/audio.json`): `reverb_presets` {rt, rtHigh, predelay, size, wet_db}, `portal_overrides` {loss_db, lp}, and `rules` (quiet hours: `mute_tags ["human"]`, `duck_tags {feature: -6, trickle: -15}`; `max_voices`; geyser period). Assets are names from `demo/js/bank.js`.

## 7. What we will NOT do, and why

- **No footsteps or wading sounds.** Barefoot on wet stone in ankle-deep water would be lovely, but they need step detection from camera motion, many variants, and they compete with the water for the scarce voices. Revisit later as a "walk" layer with 2 voices.
- **No raycast occlusion or geometric acoustics.** The portal graph gives 90 % of the effect for 0.2 ms.
- **No per-source HRTF by default.** Equal-power on all voices; HRTF is an option for the few nearest.
- **No music.** The lookbook's spa is quiet, and the water is the score. The heartbeat is the only "designed" bed.
- **No live AudioWorklet synthesis on the phone.** It costs more CPU and battery than buffer playback, and the result is the same: the textures are stationary, and variety comes from random offsets, rates and one-shots.
- **No BBC or Sonniss material**, and no CC-BY or CC-BY-NC Freesound material. Only CC0 or self-made.
- **No sound for every pool or lantern.** 75 emitters and 14 voices are enough. More emitters only make the voice selection churn.
- **No per-room reverb transmission through portals** (Wwise's "reverb of the adjacent room heard through the door"). That would mean 2–3 convolvers running at once on phones. A cheap version is noted in section 9.

## 8. Implementation plan for the web runtime agent

1. **Copy the engine** (`demo/js/engine.js`, `geom.js`, `dsp.js` for IRs only, `bank.js#loadEncoded`) into `web/`, as a module that owns one `AudioContext`. Keep the API: `new SoundEngine(ctx, layout, audio, bank).init()`, `setListener({x, y, heading, level})`, `update()` at 20 Hz, `setMode`, `setQuiet`, `setPanning`, `fireById`.
2. **Tap-to-start and lifecycle**: unlock inside the first tap (silent buffer + `resume()`), `navigator.audioSession.type = 'playback'`, suspend when hidden, and a "tap to resume" prompt when the state is `interrupted` or `suspended`. Add a mute toggle in the UI.
3. **Wire the camera**: layout x, y, z and compass heading from the three.js camera. Derive the level from the camera's z, or from the walk system's current space. Do not use `THREE.PositionalAudio`.
4. **Data**: the lead adds the `audio` blocks to the space files and the global `3d/audio.json` (section 6). The runtime reads them together with `layout.json`. The demo's `extract_layout.py` shows the joins (`water:`, `anchored:`, synthetic stair portals).
5. **Assets**: run `tools/encode_bank.mjs`, ship `assets/*.opus` + `*.m4a` + `manifest.json`, and load with `loadEncoded()`. Later, load per level (current level ±1) to keep decoded memory under 20 MB.
6. **Budget guard**: `maxVoices` 14 on desktop and 12 when `navigator.hardwareConcurrency <= 4` or `deviceMemory <= 4`. Cap reverb IRs at 4.5 s. Never use endless automation on panners or filters (see 4.1).
7. **Tie-ins**: the geyser timer to the visual eruption (one shared clock); Kawagiri curtains that part in sync with the server animation (duck that pod's emitter by −20 dB for 3 s); quiet hours from the scene clock (22:00).
8. **Replace** the murmur and surf with CC0 recordings once found (sources table + licence check). The engine needs no changes: they are just loops in the bank.
9. **Nice to have**: an adjacent-room reverb leak (feed the neighbour's convolver from portal-weighted sends when the listener is within 6 m of a portal); a small footsteps layer; a HRTF toggle in settings.

## 9. The prototype

| Path | What |
|---|---|
| `demo/index.html`, `demo/js/main.js` | The live demo: level tabs, a map of the real layout (a following 70 m window on phones), a draggable listener, a guided walk, quiet hours, output mode, panning model, geyser and bell buttons, an on-device DSP benchmark, and stats and voice readouts. |
| `demo/js/engine.js` | The soundscape engine (rooms, portals, emitters, voices, beds, reverb, one-shots) and `renderOffline()`. |
| `demo/js/dsp.js` | Every generator: bubbles, textures, wind, surf, lava, murmur, bells, heartbeat, geyser, IRs. |
| `demo/js/bank.js` | The asset list (18 loops, 8 one-shot families, 37 variants) with bake rates; `bakeAll()`; `loadEncoded()`. |
| `demo/js/geom.js`, `demo/js/scenarios.js` | Geometry helpers; scripted walks used by the renders and the guided walk. |
| `demo/data/layout_extract.json` | Generated from `3d/layout.json` + space files by `tools/extract_layout.py` (read-only use). |
| `demo/data/audio_blocks.json` | The proposed audio data (section 6). |
| `demo/assets/` | Pre-rendered bank: `.opus`, `.m4a`, `manifest.json` (2.22 / 3.24 MB). |
| `demo/preview.html` | The offline render harness used by the tools. |
| `previews/` | 10 renders × (`.wav`, `.opus`, `.m4a`), `preview_report.json` (loudness), `bank_report.json` (per-asset levels and seam checks), `render_results.json` (render timings and the CPU benchmark), `index.html`. |
| `tools/` | `extract_layout.py`, `render_loops.mjs` (bake to WAV in Node), `encode_bank.mjs`, `render_previews.mjs` (GPU browser, CDP 9310), `demo_check.mjs`, `analyze.py` (LUFS, true peak, seams, spectrograms). |
| `3d/renders/sound/` | Spectrograms per render, `descent_spectrograms.jpg`, `bank_spectrograms.jpg`, `demo_phone.png`, `demo_desktop.png`. |

Regenerate everything from the project root:
```
python3 3d/research/sound/tools/extract_layout.py
node 3d/research/sound/tools/render_loops.mjs 48000          # bank → .scratch/sound/bank/*.wav
node 3d/research/sound/tools/encode_bank.mjs                 # → demo/assets
node 3d/research/sound/tools/render_previews.mjs all         # renders + CPU bench in the GPU browser
.venv/bin/python 3d/research/sound/tools/analyze.py previews 3d/research/sound/previews 3d/research/sound/previews/preview_report.json 3d/renders/sound
.venv/bin/python 3d/research/sound/tools/analyze.py bank .scratch/sound/bank 3d/research/sound/previews/bank_report.json 3d/renders/sound/bank_spectrograms.jpg
```

### Check results
- **Renders** (25 s each, 48 kHz stereo; LUFS-I / short-term max / true peak): arrival −24.7 / −21.9 / −9.6; mist corridor −28.3 / −24.8 / −6.1; Obsidian Mirror −37.0 / −32.5 / −15.4; Kawagiri −20.2 / −19.4 / −8.0; Thunder Curtain −15.2 / −13.2 / −1.7; geyser −15.3 / −11.5 / −1.4; wave grotto −20.1 / −14.2 / −1.4; magma −24.1 / −21.5 / −4.7; quiet hours −35.0 / −30.2 / −16.2; Kawagiri in speaker mode −14.8 / −14.5 / −3.9. **0 clipped samples** in all of them.
- **Loop seams** (wrap-around vs the rest of each file): spectral flux at the seam is 0.18–1.12× the file's own 99th percentile. The 10 ms RMS step at the seam is below the file's 99th percentile for every loop. The sample jump is ≤ 0.45× the 99th-percentile sample difference, except `basin` at 1.39×, where a bubble onset lands on the seam (no discontinuity).
- **Spectral balance**: the first renders were bass-heavy, with the 31.5 Hz octave 8 dB above 1 kHz. Sub content was cut in the wind, river, falls and surf, and spray and white-water layers were added. Kawagiri's centroid is now 1.1 kHz and the mist corridor's 1.2 kHz. Magma stays at 52 Hz by design.
- **Bugs found by the renders**: the junction bell never fired. `b1_junction_w` and `b1_cor_mirror` overlap with no portal, so the bell was unreachable; this is fixed with `open_to` (and is a layout note, see section 10). Distant one-shots also filled the slots, so the gate was raised from −60 to −42 dB.

### Honest notes: what still sounds synthetic
- **The crowd murmur** at Kawagiri and the ramen counter, within about 10 m. It has the rhythm but not the voices. It is the first thing to replace with a CC0 recording.
- **The surf**: the wave timing is too regular, and the backwash on black sand lacks grain.
- **The river up close**: convincing rush, but less "detail" (individual splashes) than a recording.
- **Stationary loops**: a 12 s loop is noticeable if you stand still and listen for a minute. This is mitigated by random start offsets, ±4 % rate per emitter, and one-shots on top. Longer loops cost memory.
- None of this was heard through speakers. These judgements come from spectrograms, loudness and seam analysis. The owner's ears on a phone with headphones are the real test.

## 10. Proposed changes to shared files (for the lead)

- **Space files**: add the `audio` blocks from `demo/data/audio_blocks.json` → `spaces.<id>` to each `3d/spaces/<id>.json` as `"audio": {...}`, and document the block in `3d/spaces/SCHEMA.md` (section 6 text).
- **New `3d/audio.json`**: `reverb_presets`, `portal_overrides`, `rules` from the same file.
- **Layout connectivity (`3d/layout.json`)**: these overlapping spaces share air but have no portal, so sound (and probably walking) can't pass between them:
  - `b1_junction_w` ↔ `b1_cor_mirror`. Suggest a portal at about [70, 76] (width 3.2); the corridor's `w_cor_mirror` path runs straight through the junction.
  - `b2_kawagiri` ↔ `b2_river`, plus `b2_boat`, `b2_boardwalk` and `b2_falls_head` ↔ `b2_river`: deck over water; handled acoustically with `open_to`.
  - `b3_cavern` ↔ `b3_rimstone`, `b3_geyser`, `b3_slide_foot`, and `b3_falls` ↔ `b3_falls_gallery`: the envelope and its parts; handled with `open_to`.
- **Mist Steps**: `mist_steps` has a portal only on the B1 side (`p_b1_cor_ms`). The B2 side is missing; the extract synthesises one at about [49, 72, −40].
- **Gallery**: see the report.

## 11. Round 2: rushing water and thunder (owner feedback)

> "The bubbling and trickling sounds are far too prevalent. There should be more rushing and waterfall thunder sounds."

The owner was right, and the measurements back him up. Round 1 built nearly every water from Minnaert bubble clouds. Real rivers and falls are broadband noise with almost no audible individual events. Round 2 rebuilds the big waters as **spectrally calibrated noise banks** fitted to measured CC0 recordings. It keeps bubbles only as quiet, close-range accents. It adds a through-rock rumble to the corridors, and it makes the river and Thunder Curtain the beds of their levels.

### 11.1 What large moving water sounds like (research)

- **Waterfall acoustics.** A JASA study of 11 waterfalls found the same spectral shape everywhere: a sharp rise above background, a mid-frequency plateau with small broad peaks, then a power-law decay. Total acoustic power is roughly proportional to **hydraulic power (discharge × drop × g × ρ)**, with an efficiency of about 10⁻⁶, and the spectrum shifts lower as discharge grows [Anderson, Ortiz & Barber 2026]. Lilly's field survey covered flows from 0.2 to 20,000 cfs and drops from 1 to 270 ft, and fitted empirical octave-band sound-power formulas [Lilly 2007]. A study of water features over traffic noise found that **only high-flow waterfalls generate large low-frequency levels** comparable to road traffic. Streams and fountains are mid and high frequency [Galbrun & Ali 2013]. Surf measured by Katayama carries most of its energy at 250 Hz–4 kHz (as cited by NOAA) [NOAA]. Waterfall sound extends down into infrasound [Springer 2021 review]. → **We size sources by flow × drop, and only the big falls get real sub-bass ("thunder").**
- **How sound designers build big water.** Library makers layer several waterfalls into "one large roaring mass". They record large falls between rock formations for "a deep roar with minimal high frequencies", and warn against the generic "pink noise" sound [asoundeffect, Rivers & Waterfalls; Best Service, Streams and Rivers]. Close and far perspectives differ: individual splashes read as *small* water, while a dense roar with bass reads as *large*. Distance and occlusion take the top end away [morphic notes]. Audiokinetic's practice for rivers is one emitter moved to the point nearest the listener, plus a spread curve, rather than many emitters [Audiokinetic Q&A 1177]. Audiokinetic's pure-synthesis rain builds a noise-based bed and then adds individual drops on top as a separate layer [Audiokinetic, Generating Rain With Pure Synthesis]. Particle and granular models treat water as dense stochastic clouds of micro-events, with density as the control [Verron & Drettakis; DAFx-15 granular synthesis]. Farnell's "Running water" practical uses layered noise-driven flow objects at different rates [Farnell practical 13]. I did not find a public RDR2 or TLOU water-system talk; the closest material is TLOU2's depth-aware splashes [gamemusic.net TLOU2].
- **The layer structure we adopted:** (1) a broadband **rush bed** (an octave-band noise bank with slow, independent per-band modulation, so it is not static pink noise); (2) a **low rumble or thunder** layer with sub swell and pounding low impacts, for big falls only; (3) **distance-dependent high-frequency roll-off** (now 16 kHz/(1 + d/35 m)) and portal muffling; (4) **near-field spray**: a separate emitter of granular noise grains that only reaches you within a few metres (rolloff 1.6); (5) the **room**: cave convolution reverbs, plus a **through-rock path** (`leak_db`, low-passed at 300 Hz) for the river, inflow, outfall and Thunder Curtain; (6) **bubbles** only as a texture layer at −16 to −18 dB inside the stream and cascade, and as close-range accents (rills, basins, drips, hot pools).

### 11.2 CC0 reference recordings (measured, not shipped)

All of these are CC0 on Freesound. Each licence was checked on its sound page on 26 Oct 2026. HQ previews were analysed with `tools/texture_metrics.py`. None of this audio is in the build; the recordings are used as **measurement targets**, and could also be shipped as anchor beds later (section 11.6).

| Ref | Freesound | Author | Licence | What |
|---|---|---|---|---|
| ref_waterfall_nsmusic | https://freesound.org/people/nsmusic/sounds/321886/ | nsmusic | CC0 | Waterfall, Ostrova, Estonia (Zoom H1) |
| ref_huge_waterfall | https://freesound.org/people/deleted_user_7146007/sounds/383732/ | deleted_user_7146007 | CC0 | "Huge Waterfall" |
| ref_big_waterfall_Adeathy | https://freesound.org/people/A.Deathy/sounds/44880/ | A.Deathy | CC0 | "loud and big waterfall (full loopable)" |
| ref_waterfall_fabrizio | https://freesound.org/people/Fabrizio84/sounds/458711/ | Fabrizio84 | CC0 | Waterfall, 6 min |
| ref_river_auxide | https://freesound.org/people/Auxide_Audio/sounds/588180/ | Auxide_Audio | CC0 | Rocky mountain river, Alberta, medium rapids, 3 m |
| ref_rapids_kyles | https://freesound.org/people/kyles/sounds/454154/ | kyles | CC0 | River rushing rapids, close (48 kHz FLAC) |
| ref_rush_loop_tfti | https://freesound.org/people/ThanksForTheInspiration/sounds/523022/ | ThanksForTheInspiration | CC0 | Churning white water, seamless loop |
| ref_rapids_breviceps | https://freesound.org/people/Breviceps/sounds/573585/ | Breviceps | CC0 | River rapids |
| ref_seacave_gardner | https://freesound.org/people/Andy_Gardner/sounds/196713/ | Andy_Gardner | CC0 | Waves and drips in a sea cave, Ayrshire (96 kHz) |
| ref_seacave_plantmonkey | https://freesound.org/people/plantmonkey/sounds/376710/ | plantmonkey | CC0 | Small sea cave, Cornwall |

**What they measure** (`previews/texture_metrics.json`): spectral flatness in 400 Hz–4 kHz is 0.70–0.79 (noise-like). The top end falls **2–4.6 dB per octave** from 1 to 8 kHz. Per-band 20 ms envelope fluctuation is only **1–3 dB** (the 7–9 dB first measured for the kyles rapids came from the file's fade-in; see 12.3). Audible high-band onsets ("accents") run **0–1.8 per second**. Energy below 250 Hz sits at −1 to −4 dB of the total for big falls and sea caves, and at −8 to −18 dB for rivers and rapids. Round 1's procedural water was far off: the stream and rill loops had **19–26 accents per second**, flatness 0.46–0.58 and 8–10 dB envelope fluctuation. That is the "bubbly, trickly" character the owner heard. Round 1's river and falls also had a *rising* top end (+0.5 to +0.8 dB/oct), which makes them hiss.

### 11.3 New generators (`demo/js/dsp.js`, round-2 block)

- `noiseBank()`: 9–10 octave bands of noise, each slowly modulated on its own (0.4–3 Hz, ±2.2 dB; ±3 dB below 250 Hz), plus a shared 0.15 Hz surge. The band gains are **calibrated in three passes to an octave template measured from the references**, including any grain or impact layers mixed in. `TEMPLATES` covers rapids, thunder, falls, sheet, stream, sea cave and rock.
- `rush()` for rivers, inflow, medium falls, sheets, cascades and the shallow stream (granular "spray" grains at −8 to −14 dB; optional bubble texture at −16 to −18 dB). `thunder()` for heavy falls (thunder template + Poisson low impacts at 9–12/s + spray). `spray()` for near-field droplet hiss. `rockRumble()` for the river and falls heard through basalt (energy below 250 Hz only). `surf2()` uses the round-1 wave envelope on a sea-cave noise bank.
- **The bank now has 24 loops.** New: `river`, `river2` (a second take), `falls` (thunder), `falls2`, `falls_mid`, `inflow`, `sheet`, `curtain`, `cascade`, `stream`, `spray`, `rumble`, `surf`. Bubble models remain only in `boil` (hot pools and the spring), `rill`, `basin`, `lapping`, `drip` and `plop`.

Loop metrics vs. references:

| Loop | Centroid (Hz) | <250 Hz share (dB) | Slope 1–8 kHz (dB/oct) | Flatness | Accents/s |
|---|---|---|---|---|---|
| refs, rivers & rapids | 1151–1848 | −8.4 … −17.6 | −2.0 … −4.6 | 0.70–0.75 | 0–1.4 |
| refs, big falls | 375–1124 | −1.3 … −3.8 | −1.8 … −2.8 | 0.70–0.79 | 0 |
| round 1 river / falls | 1893 / 884 | −2.5 / −4.3 | **+0.8 / +0.5** | 0.79 / 0.70 | 0 |
| round 1 stream / rill | 1055 / 1874 | −27 / −40 | −6.8 / −5.2 | **0.58 / 0.46** | **18.9 / 26.3** |
| **round 2 river** | 1702 | −11.6 | −2.4 | 0.77 | 0 |
| **round 2 falls (thunder)** | 779 | −2.6 | −1.7 | 0.76 | 0 |
| round 2 falls_mid / inflow | 1839 / 2291 | −10.3 / −11.9 | −1.7 / −1.1 | 0.78 / 0.80 | 0 |
| round 2 sheet / cascade / stream | 2025 / 1957 / 2362 | −11.2 / −11.2 / −17.8 | −1.4 / −1.5 / −1.6 | 0.79 / 0.78 / 0.81 | 0 |

All 24 loops pass the seam check: flux at the seam is ≤ 1.12× the file's own 99th percentile, and the RMS step is ≤ its 99th percentile. The one exception is `surf`, at 5.6 vs 5.2 dB, which is marginal and sits inside a wave break.

### 11.4 The rebalanced soundscape (`demo/data/audio_blocks.json`)

Sources are sized by hydraulic power. Taking Thunder Curtain as about 3 m³/s × 17 m, the J2 inflow is about −7 to −10 dB, the outfall shaft −7 dB, the road flank falls −11 dB and the A4 falls −20 dB.
- **Thunder Curtain:** a `falls` (thunder) line at +7 dB, ref 8 m, spread 14 m, rolloff 0.8. It also has a heavy plunge-pool area (`falls2`), curtain-base spray within 3 m, and a through-rock leak at −20 dB. `b3_falls_east` (the shaft's east part, added by the lead today) now shares a room with the basin. The new `p_b2_falls_balcony` portal is nearly open (1 dB), so the roar comes up to the Falls Stair head. *Walking from the B3 lobby across the cavern to the curtain* (new render `p12_cavern_to_falls`), it builds continuously from the lobby to the deck (−16.3 LUFS over the walk). Behind the curtain it is enveloping and low (the `p5` walk: −14.0 LUFS, 31.5–125 Hz up 4–6 dB vs round 1).
- **B2 river under the slatted Kawagiri deck:** the river line is now +3 dB, spread 12 m, rolloff 0.6, with a through-rock leak. A second, uncorrelated take (`river2`) is an **area emitter over the whole deck footprint 4 m below your feet**, so it is enveloping wherever you stand on the slats. The solid core is a separate room, so the river is occluded only there (through its 4 m and 6 m doorways). The river line now stops 15 m short of the lip, which has its own thunder emitter. Kawagiri: −20.2 → **−14.4 LUFS**, the loudest place after the falls.
- **Own character per big water:** the J2 inflow uses `inflow` (aerated, bright falls template) with spray at its foot. The outfall shaft uses `falls_mid` 8 m down the shaft, with a leak. The cascade terraces (rimstone and the south-face pools) use `cascade`. The **infinity edge** (new summit level in the demo) is a 40 m `sheet` line along the south lip, with a spray line below it. The road flank falls use `falls_mid` and a plunge spray.
- **Accents demoted:** rills, wall trickles and basins are now −11 to −18 dB with rolloff 1.4–1.5, so they are only heard within 1–2 m. Drip intervals are about 2× longer and 3–5 dB quieter. Koi plops come every 15–40 s. The hall stream and runnels became `stream` (rush with a −16 dB bubble texture).
- **Corridors stay intimate, with the mountain behind them:** every B1 space has a `rumble` bed: −6 dB at the outfall, −8 at the Mist Steps fork, −12 to −16 in the corridors, −22 in the Mirror, −24 in the treatment rooms. Through-rock leaks from the river and outfall come on top of that. The Mirror walk stays the quietest place (−35.8 LUFS).

### 11.5 Before and after (same walks, same engine harness)

| Walk | LUFS-I r1 → r2 | Centroid r1 → r2 (Hz) | <250 Hz share r1 → r2 | Accents/s r1 → r2 | Flatness r1 → r2 |
|---|---|---|---|---|---|
| Arrival (gate → lava window) | −24.7 → −23.8 | 356 → 551 | −1.5 → −1.6 | **4.0 → 0.0** | 0.69 → 0.77 |
| Mist corridor | −28.3 → −30.1 | 1217 → **395** | −6.3 → **−1.5** | **12.5 → 0.5** | 0.72 → 0.71 |
| Kawagiri deck | −20.2 → **−14.4** | 1079 → 1426 | −3.3 → −8.0 | 0.04 → 0.04 | 0.75 → 0.76 |
| Thunder Curtain | −15.2 → −14.0 | 731 → 751 | −4.3 → **−2.6** | 0 → 0 | 0.71 → 0.76 |
| Wave Grotto | −20.1 → −19.3 | 737 → 637 | −3.3 → −3.1 | **3.6 → 0.0** | 0.70 → 0.71 |
| Cavern → falls (new) | — → −16.3 | 975 | −3.4 | 0 | 0.77 |
| Summit infinity edge (new) | — → −19.1 | 1876 | −10.4 | 0.04 | 0.78 |

Accent density has dropped from 4–12.5 per second to at most 0.5 in every walk. The corridors moved from a bright trickle (1.2 kHz centroid) to a low distant rush (0.4 kHz) with the trickles only close by. Thunder Curtain gained low end (31.5–125 Hz: +4 to +6 dB) and lost the bubble chirps. Kawagiri gained about 6 dB of rushing water, almost all of it at 1–4 kHz (+8 to +10 dB); its bands below 250 Hz are unchanged. Images: `3d/renders/sound/round2_before_after.jpg`, `descent_spectrograms.jpg`, `bank_spectrograms.jpg`; round-1 originals are in `3d/renders/sound/round1/`.

**Bug found and fixed on the way: comb filtering from the spread path.** Round 1's "diffuse" path (two short delays) and a velvet-noise decorrelator I tried next [Alary, Politis & Välimäki, DAFx-17] both comb-filtered against the dry signal. It showed as horizontal stripes in the spectrograms once rushing water had large spread, with a spectral ripple std of 2.5 dB. Wide sources now play a **second, uncorrelated read of the same loop** (half a loop apart) on the opposite channel, with no delays. The ripple is now 0.34 dB, the same as with spread disabled. Also new: gain, cutoff and direction are smoothed in JavaScript, and portal loss fades in over the 5 m around each doorway, so walking through a door is a glide and not a step.

**CPU and size, round 2:** 16 voices, 87 emitters, 24 loops. DSP 4.4–6.3 % of one desktop core (round 1: 3.2–4.6 %); with HRTF 5.7 %; without reverb 3.2 %. In-page benchmark: 5.0 % (HRTF 8.4 %). Engine update 0.1–0.4 ms. 45.1 MB decoded. 2.22 MB Opus / 3.24 MB AAC. Start-up 0.6–0.7 s pre-rendered and 5.5 s baked (desktop). The loudest walk peaks at −0.6 dBTP (target −1). Lowering the limiter threshold from −3 to −4.5 dB, or adding a look-ahead limiter worklet, would fix that.

### 11.6 What still sounds wrong (honest)

- **Smooth, not wet.** The noise banks now match the references' spectra and envelopes, but real rapids have splash bursts and spectral detail that ours lack. (Correction from round 3: the "7–9 dB envelope swings" I quoted here were the fade-in at the start of the kyles file. Within the recording, fluctuation is 1.3–2 dB per 2 s, close to ours.) Up close the river can read as "big hiss with movement". The quickest fix is to **ship one CC0 recording as an anchor bed per big water** (e.g. Auxide_Audio 588180 for the river, A.Deathy 44880 or deleted_user_7146007 383732 for Thunder Curtain). They would be layered under the procedural bank, which then supplies distance, size and variation. They cost about 60–120 KB each as Opus. Each needs its source page and author recorded at the time of download.
- **Thunder at a distance** depends on headphones. On a phone speaker (high-pass at 160 Hz) the falls read as rush, not thunder.
- **Murmur** at Kawagiri is still synthetic within about 10 m. The rushing river now masks it more, which helps.
- **Surf** is better (no bubble fizz) but still too regular.
- **Kawagiri is nearly as loud as Thunder Curtain** (−14.4 vs −14.0 LUFS). If the owner wants a clearer hierarchy, lower `river_under_deck` by 3 dB.
- Still judged by analysis only. Nothing was heard through speakers.

### 11.7 Round-2 sources
- J. F. Anderson, H. D. Ortiz, J. R. Barber, "Waterfall infrasound", JASA 159(6):5566–5577 (2026). https://pubs.aip.org/asa/jasa/article/159/6/5566/3395883/Waterfall-infrasound
- J. Lilly, "Waterfall noise", JASA 122(5) Suppl. 2991 (2007). https://pubs.aip.org/asa/jasa/article/122/5_Supplement/2991/712120/Waterfall-noise
- L. Galbrun, T. T. Ali, "Acoustical and perceptual assessment of water sounds and their use over road traffic noise", JASA 133:227–237 (2013). https://researchportal.hw.ac.uk/en/publications/acoustical-and-perceptual-assessment-of-water-sounds-and-their-us/
- NOAA, waterfall low-frequency vibrations and infrasound (surf energy 250 Hz–4 kHz citing Katayama 2003). https://repository.library.noaa.gov/view/noaa/44367/noaa_44367_DS1.pdf · Springer review: https://link.springer.com/article/10.1007/s00359-021-01510-5
- Hanbury Brown–Twiss for waterfall sound (about 60 dB(A) at the falls). https://arxiv.org/pdf/2106.08137
- Audiokinetic, "Generating Rain With Pure Synthesis". https://www.audiokinetic.com/en/generating-rain-with-pure-synthesis · Single river emitter at the nearest point: https://www.audiokinetic.com/qa/1177/how-do-i-simulate-a-sound-that-is-not-a-point-sound-source · Spline volumetric emitter: https://blog.audiokinetic.com/volumetric_audio_emitter_for_custom_shapes_in_ue4/
- C. Verron, G. Drettakis, "Procedural audio modeling for particle-based environmental effects". https://hal.archives-ouvertes.fr/hal-00759818 · DAFx-15 granular rain and running water: https://www.ntnu.edu/documents/1001201110/1266017954/DAFx-15_submission_7.pdf/e66b153c-1b7b-4c29-b13c-83197d5c7c92
- A. Farnell, *Designing Sound*, practical 13 "Running water" (companion code). https://mitp-content-server.mit.edu/books/content/sectbyfn/books_pres_0/8375/designing_sound.zip/practical13.html
- Library and design notes on big water: https://www.asoundeffect.com/sound-library/rivers-and-waterfalls · https://www.bestservice.com/en/streams_and_rivers.html · https://designingsound.org/2011/08/02/rabbit-ears-audio-releases-brooks-streams-waterfalls/ · https://morphic.com/resources/sounds/waterfall-sound-effects
- TLOU2 water (depth-aware splashes): https://gamemusic.net/?p=6073 · RDR2: no public water-system talk found (Cujo Sound analysis is footsteps-only): https://charlieasound.myblog.arts.ac.uk/2023/11/06/sound-design-in-red-dead-redemption-2-a-comprehensive-analysis-and-review-of-cujo-sounds-insights/
- B. Alary, A. Politis, V. Välimäki, "Velvet-noise decorrelator", DAFx-17. https://dafx.de/paper-archive/details/QFIYNG5NjGx5Nsrw_3s-GA
- Freesound CC0 references: see the table in 11.2 (licence checked on each sound page).

## 12. Round 3: CC0 anchor recordings for the big three waters

The owner approved CC0 anchors for Thunder Curtain Falls, the B2 river under Kawagiri and the sea-cave surf. Each anchor is one real recording, processed into a seamless loop and layered **under** the procedural bed. Sources, licences (re-verified on each Freesound page at download time, 2026-10-27 00:15 UTC), segments and hashes are in **`CREDITS.md`**.

### 12.1 Choice and processing
| Water | Recording | Why | Loop | Opus / AAC |
|---|---|---|---|---|
| Thunder Curtain | "Huge Waterfall", deleted_user_7146007 (383732) | Biggest low end of the references (below 250 Hz at −3.8 dB) | 20 s, 32 kHz | 73 KB / 127 KB |
| B2 river and Kawagiri deck | "river rushing rapids close", kyles (454154) | The most splash detail: 1.4–1.6 onsets/s, flatness 0.68–0.70 | 24 s, 32 kHz | 87 KB / 152 KB |
| Sea-cave surf | "Cornish Seacave", plantmonkey (376710) | Real in/out surges: slow-envelope std 3.7 dB vs 1.6 dB for the Gardner cave | 28 s, 24 kHz | 100 KB / 175 KB |

`tools/make_anchors.py` does the processing:
- picks the best window automatically: loop match, no clicks, no wind rumble, and the strongest surges for surf;
- high-pass at 25–60 Hz, and a high shelf of −3 to −5 dB above 5–6 kHz, so the procedural spray keeps the top octave;
- equal-power seam crossfade of 1.5–2 s;
- RMS −18 to −20 dBFS, with peaks at −1 dBFS or lower.

Seam check: flux at the seam is 0.2–0.6× each file's own 99th percentile, and the RMS step is below its 99th percentile. `tools/encode_bank.mjs` encodes the anchors with the same wrapped pad as every other loop. In bake mode, `bank.js#addAnchors` loads just the anchors.

### 12.2 Layering
Each anchor is its own emitter, on the same geometry as the procedural bed it supports: the curtain line, the river line, a deck area and the surf line. The anchor has a **steeper rolloff (1.0)** than the bed (0.6–0.8), so **near the water the recording leads, and with distance the procedural bed takes over** (size, distance high-frequency roll-off, through-rock paths and per-space character). Levels:

| Place | Procedural bed | Anchor |
|---|---|---|
| Thunder Curtain | +5 | +6 |
| River | −1 | +2 |
| Under the deck | −7 (3 dB lower than the requested −5, to make room for the anchor) | −3 |
| Surf | 0 | +3 |

The other requested changes:
- **Surf timing is irregular:** intervals of 0.65–1.45 × the period, a 20 % chance of a second wave 2–3.5 s behind, and per-wave size and break sharpness.
- **Limiter** threshold lowered to −4.5 dB, plus a 4× oversampled soft clipper that never exceeds −1.2 dBFS.
- **Tool fix:** the shared browser had been serving cached JS/JSON to the render tool. `render_previews.mjs` and `demo_check.mjs` now disable the cache through CDP. The numbers below come from fresh files. The round-2 numbers changed after each edit, so they were not served from cache.

### 12.3 Results (round 2 → round 3)
| Walk | LUFS-I | True peak (dBTP) | Centroid (Hz) | Slope 1–8 kHz (dB/oct) | Flatness | Accents/s |
|---|---|---|---|---|---|---|
| Thunder Curtain | −14.0 → **−12.9** (loudest place) | −0.7 → **−1.5** | 751 → 750 | −2.0 → −2.6 | 0.76 → 0.76 | 0 → 0 |
| Kawagiri deck | −14.4 → **−14.2** | −2.6 → −2.0 | 1426 → **1133** | −2.6 → **−3.9** | 0.76 → **0.72** | 0.04 → 0.08 |
| Wave Grotto | −19.3 → −18.2 | −2.2 → −1.7 | 637 → 568 | −5.0 → −5.4 | 0.71 → **0.66** | 0 → 0.12 |
| Cavern → falls | −16.3 → −15.5 | −1.6 → −1.8 | 974 → 970 | −2.0 → −2.2 | 0.78 → 0.77 | 0.03 → 0 |
| references (kyles / huge falls / plantmonkey) | | | 1198 / 1124 / 578 | −4.6 / −1.8 / −3.8 | 0.70 / 0.79 / 0.57 | 1.4 / 0 / 0.8 |

- **True peak:** every walk is now at or below **−1.47 dBTP**. Thunder Curtain is the loudest place, 1.3 dB above Kawagiri.
- **Kawagiri moved onto the real river:** centroid, top-end slope and flatness are now close to the kyles recording.
- **Surf:** has real cave booms and irregular sets (see `3d/renders/sound/round3_before_after.jpg`).
- **Correction to round 2:** the "7–9 dB envelope swings" quoted for the kyles rapids were the file's fade-in. Inside the recording the 20 ms fluctuation per 2 s is 1.3–2 dB, so the procedural beds were never far off on that measure. What the anchors add is **spectral and temporal fine structure**: real splashes, cave resonance and the non-uniform texture of a recording. That shows up as lower flatness and a steeper top end, not as bigger envelope swings.
- **Cost:**
  - DSP: 5.0–6.5 % of a desktop core at 16 voices (round 2: 4.4–6.3 %); HRTF 6.0–6.3 %; in-page test 5.7 % (HRTF 9.1 %).
  - Download: 2.52 MB Opus / 3.75 MB AAC (+260 KB / +510 KB for the anchors).
  - Memory: 54.4 MB decoded.
  - Start-up: 0.7–0.8 s pre-rendered, 5.9 s baked.

### 12.4 Still wrong
- **Thunder Curtain hardly changed** in the metrics, because the procedural thunder already matched this recording closely. Its anchor mostly adds realism in the 2–5 kHz detail. A second, larger CC0 falls (e.g. A.Deathy 44880, only 10 s) could be crossfaded in later.
- **The anchors are 128 kbps MP3 previews** (Freesound originals need a login). They are fine under the procedural layers. If the owner downloads the originals, re-run `make_anchors.py`.
- **Anchor loops of 20–28 s repeat** if you stand still for minutes. A second segment per water could alternate with the first.
- **Still judged by analysis only.** The owner's ears are the real test.

## Sources

- K. van den Doel, "Physically-based models for liquid sounds", ACM Transactions on Applied Perception 2(4):534–546, 2005; ICAD 2004. https://repository.gatech.edu/entities/publication/dcc121b6-5fdb-42db-b758-971522f01c70 · https://dblp1.uni-trier.de/rec/conf/icad/Doel04.html
- W. Moss, H. Yeh, J.-M. Hong, M. C. Lin, D. Manocha, "Sounding Liquids: Automatic Sound Synthesis from Fluid Simulation", UNC TR09-012 (Minnaert's formula, damping, r^−α bubble distributions citing Pumphrey & Elmore 1990 and Deane & Stokes 2002). https://techreports.cs.unc.edu/papers/09-012.pdf · https://gamma.cs.unc.edu/SoundingLiquids/soundingliquids.pdf
- M. Minnaert, "On musical air-bubbles and the sounds of running water", Phil. Mag. 16, 1933 (via Moss et al.).
- C. Zheng, D. L. James, "Harmonic Fluids", SIGGRAPH 2009. https://research.cs.cornell.edu/HarmonicFluids/harmonicfluids-lowres.pdf
- A. Farnell, *Designing Sound*, MIT Press 2010. https://mitpressbookstore.mit.edu/book/9780262014410 · Pd sound design workshop (fire, running water and bubbles, wind and rain): https://goto10.org/pure-data-and-sound-design-workshop/
- QMUL / Nemisindo procedural sound in the browser. https://qmul.ac.uk/media/news/2021/se/queen-mary-spinout-nemisindo-launches-online-sound-design-service-based-on-procedural-audio-technology-.html · N. Garcia, J. Reiss, recorded vs synthetic sound effects (2026). https://arxiv.org/pdf/2605.31082
- MDN, PannerNode.distanceModel. https://developer.mozilla.org/docs/Web/API/PannerNode/distanceModel · W3C public-audio on HRTF cost and the equalpower default: https://lists.w3.org/Archives/Public/public-audio/2014JulSep/0033.html · https://bugzilla.mozilla.org/show_bug.cgi?id=1128494
- Chrome autoplay policy (Web Audio since M71). https://developer.chrome.com/blog/autoplay · AudioWorklet render quantum: https://developer.chrome.com/blog/audio-worklet
- W3C Audio Session. https://www.w3.org/TR/audio-session/ · MDN AudioSession.type: https://developer.mozilla.org/docs/Web/API/AudioSession/type · WebKit 237322 (silent switch): https://auto-bugs.webkit.org/show_bug.cgi?id=237322
- iOS interrupted state: https://bugs.webkit.org/show_bug.cgi?id=276016 · https://bugs.webkit.org/show_bug.cgi?id=273511 · https://bugs.webkit.org/show_bug.cgi?id=217606
- WebKit in Safari 18.4 (Ogg Opus and Vorbis). https://webkit.org/blog/16574/webkit-features-in-safari-18-4/ · Earlier Opus and Web Audio issues: https://bugs.webkit.org/show_bug.cgi?id=238546 · https://bugs.webkit.org/show_bug.cgi?id=226922
- Audiokinetic, "Reverb Needs Spatialization Too: A Guide to Rooms and Portals in Wwise Spatial Audio". https://www.audiokinetic.com/en/blog/rooms-and-portals-with-wwise-spatial-audio
- Spline and ribbon emitters: BeamNG Audio Ribbon Editor https://documentation.beamng.com/world_editor/tools/audio_ribbon_editor/ · Unity River Modeler https://80.lv/articles/turn-unity-s-splines-into-dynamic-rivers-with-automatic-spatial-audio
- GDC: Open World Audio in Dying Light 2 https://gdcvault.com/play/1029272/Open-World-Audio-in-Dying · Ghost of Tsushima ambience system https://gdcvault.com/play/1027222/Big-World-Small-Team-Designing · Gotham Knights https://gdcvault.com/play/1029150/-Gotham-Knights-Using-Systemic · Hellblade II https://gdcvault.com/play/1035513/Ambience-Design-and-Acoustic-Systems
- Freesound API (licence filter). https://freesound.org/docs/api/resources_apiv2.html
- Sonniss GDC bundle licence v2.0. https://sonniss.com/gdc-bundle-license/
- BBC Sound Effects / RemArc licence (coverage): https://musictech.com/news/music/the-bbc-sound-effects-archive-over-33000-free-samples
- Source-count rule of thumb (unverified): https://www.abratabia.com/web-game-audio/spatial-audio-games.php
