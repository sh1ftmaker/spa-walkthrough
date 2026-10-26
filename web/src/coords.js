// Coordinate conventions
//   layout / Blender: x east, y north, z up (metres)       -> JSON files (places, probes, water, spaces)
//   three / glTF:     X = x, Y = z, Z = -y                  -> GLB parts (the Blender glTF exporter does this with +Y up)
// Heading (yaw) in JSON is degrees clockwise from north (0 = +y north, 90 = +x east).
// In three a camera with rotation.y = 0 looks along -Z = north, so rotation.y = -heading.
import { Vector3 } from 'three';

export const L2T = (x, y, z, out = new Vector3()) => out.set(x, z, -y);
export const l2t = (a, out = new Vector3()) => out.set(a[0], a[2], -a[1]);
export const t2l = (v) => [v.x, -v.z, v.y];
export const headingToYaw = (deg) => (-deg * Math.PI) / 180;
export const yawToHeading = (yaw) => ((((-yaw * 180) / Math.PI) % 360) + 360) % 360;
// layout 2D bounds [minx, miny, maxx, maxy] -> three xz rect [minX, minZ, maxX, maxZ]
export const boundsToXZ = (b) => [b[0], -b[3], b[2], -b[1]];
