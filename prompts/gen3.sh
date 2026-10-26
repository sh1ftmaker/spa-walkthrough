#!/usr/bin/env bash
# usage: gen2.sh <name> <comma-separated ref basenames> <prompt>
cd /home/agent-tom/Desktop/volcanospa
name="$1"; refs="$2"; prompt="$3"; spec="$(cat layout-spec.md)"
log="prompts/logs/$name.log"; mkdir -p prompts/logs
[ -f "images/$name.png" ] && exit 0
iargs=(-i refs/all-places-sheet.jpg -i lookbook/img/24-isometric-cutaway.jpg -i lookbook/img/03-master-floorplan.jpg)
IFS=',' read -ra rs <<< "$refs"; for r in "${rs[@]}"; do [ -n "$r" ] && iargs+=(-i "lookbook/img/$r.jpg"); done
timeout 1200 codex exec --skip-git-repo-check -s workspace-write -C "$PWD" "${iargs[@]}" -- \
  "Use your image generation tool to create exactly ONE image, using the attached images as visual references. The isometric cutaway is the source of truth for where things are; the B1 master plan image is the DRAWING STYLE to copy (top-down, richly rendered plan with glowing teal water, lantern-lit wood, dark rock, fine white outlines, labels, legend, scale bar, north arrow), but ignore its room arrangement. Draw every amenity so it matches its own individual concept image. Print the shared A-J / 1-6 grid faintly and mark the vertical connections (lift, stairs, slide) with symbols at their grid cells. Every place must be reachable by walking; draw the walkways and stairs clearly. Follow the layout spec at the end exactly. Do not do anything else and do not ask questions. SUBJECT: $prompt  LAYOUT SPEC: $spec" </dev/null >"$log" 2>&1
sid=$(grep -m1 'session id:' "$log" | awk '{print $3}')
f=$(ls -t ~/.codex/generated_images/"$sid"/*.png 2>/dev/null | head -1)
if [ -n "$f" ]; then cp "$f" "images/$name.png"; echo "OK $name"; else echo "FAIL $name"; fi
