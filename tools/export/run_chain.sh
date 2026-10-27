#!/usr/bin/env bash
# Bake + export one place for one or both tiers:  tools/export/run_chain.sh <space> [low|high|both] [extra bake args...]
# Input 3d/places/<space>.blend, output 3d/bake/<space>/<tier>/ (EXR intermediates, baked.blend, dump/, pkg/).
# Then merge with: (cd web && node tools/build-mixed.mjs)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
B=/home/agent-tom/.local/bin/blender
SPACE="$1"; TIERS="${2:-both}"; shift || true; shift || true
[[ "$TIERS" == both ]] && TIERS="low high"
SRC="$ROOT/3d/places/$SPACE.blend"
[[ -f "$SRC" ]] || { echo "no $SRC" >&2; exit 2; }
for T in $TIERS; do
  OUT="$ROOT/3d/bake/$SPACE/$T"
  "$B" -b "$SRC" -P "$ROOT/tools/export/bake_place.py" -- --tier "$T" --out "$OUT" "$@" 2>&1 | grep -E '^\[bake\]|Error|Traceback' || true
  [[ -f "$OUT/bake.json" ]] || { echo "bake failed for $SPACE/$T" >&2; exit 1; }
  "$B" -b -P "$ROOT/tools/export/export_place.py" -- --bake "$OUT" 2>&1 | grep -E '^\[export\]|^\[pack\]|Error|Traceback' || true
  [[ -f "$OUT/pkg/place.json" ]] || { echo "export failed for $SPACE/$T" >&2; exit 1; }
done
