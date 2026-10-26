#!/usr/bin/env bash
# Run Chromium on the discrete GPU inside its own weston (headless backend, GL renderer)
# through Xwayland. Meant to be started under sbg:
#   sbg start kz-shot-browser -- tools/gpu_chrome.sh --name shot --port 9310 --display 31
# Args: --name <id> (weston socket + profile name), --port <cdp port>, --display <X display number>,
#       --size WxH (default 1600x1000), --fresh (wipe the profile first)
set -euo pipefail
NAME=shot PORT=9310 DISP=31 SIZE=1600x1000 FRESH=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2;; --port) PORT="$2"; shift 2;;
    --display) DISP="$2"; shift 2;; --size) SIZE="$2"; shift 2;;
    --fresh) FRESH=1; shift;; *) echo "unknown arg $1" >&2; exit 2;;
  esac
done
case "$PORT" in 9222) echo "port 9222 is the shared browser; refusing" >&2; exit 2;; esac
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="$ROOT/.scratch/chrome-profiles/kz-$NAME"
if [[ $FRESH == 1 && -d "$PROFILE" ]]; then rm -rf -- "$PROFILE"; fi
mkdir -p "$PROFILE"
W=${SIZE%x*} H=${SIZE#*x}
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
SOCK="kz-weston-$NAME"
# Discrete GPU for Vulkan (ANGLE) and NVIDIA for GLX/EGL
export MESA_VK_DEVICE_SELECT=10de:2684
export __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
BEFORE=" $(ls /tmp/.X11-unix 2>/dev/null | tr '\n' ' ') "
weston --backend=headless --renderer=gl --socket="$SOCK" --width="$W" --height="$H" --xwayland --idle-time=0 &
WPID=$!
trap 'kill $CPID 2>/dev/null || true; kill $WPID 2>/dev/null || true; wait 2>/dev/null || true' EXIT INT TERM
# weston picks its own X display (Xwayland starts lazily on first client): find the new socket
XN=""
for i in $(seq 1 60); do
  for s in $(ls /tmp/.X11-unix 2>/dev/null); do
    [[ "$BEFORE" == *" $s "* ]] || { XN=${s#X}; break; }
  done
  [[ -n "$XN" ]] && break
  sleep 0.25
done
[[ -n "${XN:-}" ]] || { echo "Xwayland did not come up" >&2; exit 1; }
echo "weston $SOCK pid $WPID, Xwayland :$XN, CDP $PORT, profile $PROFILE"
DISPLAY=":$XN" WAYLAND_DISPLAY= chromium \
  --user-data-dir="$PROFILE" --remote-debugging-port="$PORT" --remote-debugging-address=127.0.0.1 \
  --ozone-platform=x11 --use-gl=angle --use-angle=vulkan --enable-features=Vulkan,DefaultANGLEVulkan,VulkanFromANGLE \
  --ignore-gpu-blocklist --enable-gpu-rasterization --disable-gpu-driver-bug-workarounds \
  --no-first-run --no-default-browser-check --disable-background-timer-throttling \
  --disable-renderer-backgrounding --disable-backgrounding-occluded-windows \
  --window-size="$W,$H" --window-position=0,0 about:blank &
CPID=$!
wait $CPID
