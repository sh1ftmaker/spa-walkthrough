// Scripted walks through the real layout (layout metres, compass heading). Used by the offline preview renders
// and by the demo's "Walk the route" button. Each key: t (s), level, x, y, heading.
const K = (t, level, x, y, heading) => ({ t, level, x, y, heading });

export const SCENARIOS = {
  p1_arrival: { title: 'Basalt Gate to the lava window', secs: 25, keys: [
    K(0, 'ground', 28, 55, 90), K(4, 'ground', 40, 55, 90), K(9, 'ground', 50, 60, 45), K(13, 'ground', 56, 64, 20), K(18, 'ground', 60, 73, 0), K(25, 'ground', 68, 76, 20)] },
  p2_mist_corridor: { title: 'Mist corridor: lobby rill, junction bell, wall trickles', secs: 25, keys: [
    K(0, 'b1', 86, 76, 300), K(3, 'b1', 78, 72, 280), K(7, 'b1', 72, 74.5, 320), K(11, 'b1', 67.5, 80, 340), K(14, 'b1', 66.9, 85, 0), K(18, 'b1', 70, 92, 90), K(22, 'b1', 80, 92, 90), K(25, 'b1', 88, 92, 90)] },
  p3_obsidian_mirror: { title: 'Into the Obsidian Mirror (near silence)', secs: 25, events: [{ t: 11, fire: 'mirror_drips' }, { t: 19.5, fire: 'mirror_drips' }], keys: [
    K(0, 'b1', 84, 92, 90), K(6, 'b1', 93.5, 92, 90), K(10, 'b1', 98.5, 93, 60), K(15, 'b1', 99.5, 97.5, 30), K(25, 'b1', 104, 103.5, 60)] },
  p4_kawagiri: { title: 'Kawagiri deck over the river', secs: 25, keys: [
    K(0, 'b2', 70, 69, 0), K(3, 'b2', 70, 74, 0), K(7, 'b2', 70, 84, 60), K(15, 'b2', 90, 84, 90), K(22, 'b2', 110, 84, 90), K(25, 'b2', 117, 84, 90)] },
  p5_thunder_curtain: { title: 'Falls head, behind the Thunder Curtain, plunge deck', secs: 25, keys: [
    K(0, 'b2', 45.5, 66, 270), K(6, 'b2', 44, 67, 290), K(6.5, 'b3', 42, 78.5, 270), K(13, 'b3', 29, 78.5, 270), K(17, 'b3', 15, 78.5, 270), K(17.5, 'b3', 40.5, 66, 200), K(25, 'b3', 40, 58, 250)] },
  p6_wave_grotto: { title: 'Shore path to the sea mouth', secs: 25, keys: [
    K(0, 'b3', 151, 36.5, 100), K(6, 'b3', 160.8, 34.5, 90), K(10, 'b3', 168, 36, 80), K(17, 'b3', 180, 40, 70), K(25, 'b3', 190, 42, 90)] },
  p7_geyser: { title: 'Geyser Plaza: the big eruption', secs: 25, opts: { demoGeyser: false }, events: [{ t: 3, fire: 'geyser_big' }], keys: [
    K(0, 'b3', 100.5, 42, 90), K(25, 'b3', 103, 45, 100)] },
  p8_magma_heartbeat: { title: 'Down to the magma chamber: the heartbeat', secs: 25, keys: [
    K(0, 'b4', 88, 73, 230), K(5, 'b4', 77, 64, 220), K(11, 'b4', 62, 50, 200), K(15, 'b4', 56, 36, 180), K(20, 'b4', 68, 24, 150), K(25, 'b4', 80, 17, 180)] },
  p11_summit_infinity: { title: 'Summit: along the infinity edge', secs: 25, keys: [
    K(0, 'summit', 66, 70.5, 90), K(5, 'summit', 75, 65, 100), K(10, 'summit', 89, 63.6, 90), K(17, 'summit', 105, 64.5, 90), K(25, 'summit', 125, 64.5, 90)] },
  p12_cavern_to_falls: { title: 'Across the Aqua Cavern to Thunder Curtain', secs: 30, keys: [
    K(0, 'b3', 88, 66, 270), K(4, 'b3', 78, 70, 280), K(8, 'b3', 70, 70, 270), K(11, 'b3', 66, 66, 240), K(16, 'b3', 56, 63, 260), K(21, 'b3', 46, 61, 280), K(25, 'b3', 41, 63, 320), K(30, 'b3', 37, 70, 330)] },
  p9_quiet_hours: { title: 'Quiet hours (after 22:00): same corridor walk', secs: 25, opts: { quiet: true }, keys: null /* copy of p2 */ },
  p10_kawagiri_speaker: { title: 'Kawagiri, phone-speaker mode', secs: 25, opts: { mode: 'speaker' }, keys: null /* copy of p4 */ },
};
SCENARIOS.p9_quiet_hours.keys = SCENARIOS.p2_mist_corridor.keys;
SCENARIOS.p10_kawagiri_speaker.keys = SCENARIOS.p4_kawagiri.keys;

// The demo's guided walk: the scenario walks back to back (level changes are cuts, as if taking the stair/lift).
export const ROUTE = ['p11_summit_infinity', 'p1_arrival', 'p2_mist_corridor', 'p3_obsidian_mirror', 'p4_kawagiri', 'p5_thunder_curtain', 'p12_cavern_to_falls', 'p7_geyser', 'p6_wave_grotto', 'p8_magma_heartbeat'];
