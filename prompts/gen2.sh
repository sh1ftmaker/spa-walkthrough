#!/usr/bin/env bash
# usage: gen2.sh <name> <comma-separated ref basenames> <prompt>
cd /home/agent-tom/Desktop/volcanospa
name="$1"; refs="$2"; prompt="$3"; spec="$(cat prompts/layout-spec.txt)"
log="prompts/logs/$name.log"; mkdir -p prompts/logs
[ -f "images/$name.png" ] && exit 0
iargs=(-i refs/all-places-sheet.jpg)
IFS=',' read -ra rs <<< "$refs"; for r in "${rs[@]}"; do [ -n "$r" ] && iargs+=(-i "lookbook/img/$r.jpg"); done
timeout 1200 codex exec --skip-git-repo-check -s workspace-write -C "$PWD" "${iargs[@]}" -- \
  "Use your image generation tool to create exactly ONE image, using the attached images as visual references. Do not do anything else and do not ask questions. SUBJECT: $prompt  $spec" </dev/null >"$log" 2>&1
sid=$(grep -m1 'session id:' "$log" | awk '{print $3}')
f=$(ls -t ~/.codex/generated_images/"$sid"/*.png 2>/dev/null | head -1)
if [ -n "$f" ]; then cp "$f" "images/$name.png"; echo "OK $name"; else echo "FAIL $name"; fi
