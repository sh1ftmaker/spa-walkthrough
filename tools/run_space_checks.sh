#!/usr/bin/env bash
# Isolated place -> assemble -> checks -> views -> contact sheet for a few spaces, for parallel agents.
#   tools/run_space_checks.sh <tag> [--no-renders] space [space ...]
# Outputs only under .scratch/runs/<tag>/ (placements.json, resolved.json, assembled.blend, checks.json,
# views/<space>/..., contact/<space>/contact-r1.jpg). Reads the shared graybox.blend, layout.json, 3d/spaces.
set -euo pipefail
cd "$(dirname "$0")/.."
TAG="$1"; shift
RENDER=1; [[ "${1:-}" == "--no-renders" ]] && { RENDER=0; shift; }
case "$TAG" in *[!a-z0-9_-]*|"") echo "tag must be [a-z0-9_-]" >&2; exit 2;; esac
RUN=".scratch/runs/$TAG"; mkdir -p "$RUN"
B=/home/agent-tom/.local/bin/blender; PY=.venv/bin/python
export KZ_PLACEMENTS="$RUN/placements.json" KZ_RESOLVED="$RUN/resolved.json" KZ_CHECKS="$RUN/checks.json" KZ_CONTACT_DIR="$RUN/contact"
rm -f "$KZ_CHECKS"
$PY tools/assembly/place.py "$@" | tail -20
$B -b 3d/blend/graybox.blend -P tools/assembly/assemble.py -- --out "$RUN/assembled.blend" 2>&1 | grep -E "ASSEMBLED|Traceback|Error" | cut -c1-300 || true
$B -b "$RUN/assembled.blend" -P checks/placement.py -- --space "$@" 2>&1 | grep -E "CHECK|Traceback|Error" || true
$PY - "$KZ_CHECKS" <<'PYEOF'
import json, sys
R = json.load(open(sys.argv[1]))
for sid, r in R.items():
    bad = {k: v for k, v in r.items() if v['status'] in ('fail', 'warn')}
    for k, v in bad.items():
        detail = {kk: vv for kk, vv in v.items() if kk not in ('status', 'fails', 'warns', 'rules') and vv}
        print(f'  {sid} {k} {v["status"]}: {json.dumps(detail)[:400]}')
PYEOF
if [[ $RENDER == 1 ]]; then
  $B -b "$RUN/assembled.blend" -P tools/graybox/render_views.py -- --set spaces --outdir "$RUN/views" --space "$@" 2>&1 | grep -c WROTE || true
  for s in "$@"; do $PY tools/review/render_contact_sheet.py "$s" --round 1 --views-dir "$RUN/views"; done
fi
