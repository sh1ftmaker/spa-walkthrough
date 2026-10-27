#!/usr/bin/env bash
# usage: gen4.sh <name> <comma-separated lookbook image basenames used as references> <prompt>  -> refs/gen/<name>.png
cd /home/agent-tom/Desktop/volcanospa
name="$1"; refs="$2"; prompt="$3"; style="$(cat prompts/style.txt)"
log="prompts/logs/$name.log"; mkdir -p prompts/logs refs/gen
[ -f "refs/gen/$name.png" ] && exit 0
iargs=()
IFS=',' read -ra rs <<< "$refs"; for r in "${rs[@]}"; do [ -n "$r" ] && iargs+=(-i "lookbook/img/$r.jpg"); done
timeout 1200 codex exec --skip-git-repo-check -s workspace-write -C "$PWD" "${iargs[@]}" -- \
  "Use your image generation tool to create exactly ONE image, using the attached images as visual references for style, materials, lighting and mood (they are concept art of the same place; stay consistent with them). Do not do anything else and do not ask questions. SUBJECT: $prompt  $style" </dev/null >"$log" 2>&1
sid=$(grep -m1 'session id:' "$log" | awk '{print $3}')
f=$(ls -t ~/.codex/generated_images/"$sid"/*.png 2>/dev/null | head -1)
if [ -n "$f" ]; then cp "$f" "refs/gen/$name.png"; echo "OK $name"; else echo "FAIL $name"; fi
