#!/usr/bin/env bash
# Rebuild layout -> graybox -> placements -> proxies -> checks -> review renders -> contact sheets.
#   tools/rebuild_graybox.sh [--no-renders] [space ...]
set -euo pipefail
cd "$(dirname "$0")/.."
B=/home/agent-tom/.local/bin/blender
PY=.venv/bin/python
RENDER=1; [[ "${1:-}" == "--no-renders" ]] && { RENDER=0; shift; }
$PY tools/plan/build_layout.py | tail -1
$PY tools/plan/render_overlay.py
$B -b -P tools/graybox/build_graybox.py 2>&1 | grep -E "SAVED|Traceback|Error" || true
$PY tools/assembly/place.py | tail -16
$B -b 3d/blend/graybox.blend -P tools/assembly/assemble.py 2>&1 | grep -E "ASSEMBLED|Traceback" | cut -c1-400
$B -b 3d/blend/assembled.blend -P checks/walk.py -- --res 0.5 2>&1 | grep -E "WALK|Traceback"
$PY checks/walk_map.py
$B -b 3d/blend/assembled.blend -P checks/placement.py 2>&1 | grep -E "PLACEMENT|Traceback"
if [[ $RENDER == 1 ]]; then
  SPACES=("$@"); if [[ ${#SPACES[@]} -eq 0 ]]; then mapfile -t SPACES < <(ls 3d/spaces/*.json | xargs -n1 basename | sed 's/\.json$//' | grep -v -E '^(SCHEMA|suite_template)$'); fi
  $B -b 3d/blend/assembled.blend -P tools/graybox/render_views.py -- --set spaces --space "${SPACES[@]}" 2>&1 | grep -c WROTE
  for s in "${SPACES[@]}"; do $PY tools/review/render_contact_sheet.py "$s" --round 1 >/dev/null; done
  echo "contact sheets: ${#SPACES[@]}"
fi
